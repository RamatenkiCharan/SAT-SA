"""
Production PostgreSQL & SQL-backed Repository for SAT-SA.
Provides complete relational persistence for datasets, canonical models, analysis runs,
findings, evidence linkages, review decisions, audit logs, and users.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.engine import Engine

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.data_quality.quality_score import DataQualityComponents as DQComponentsScore, DataQualityResult
from analytics.fusion.evidence_fusion import compute_priority_tier
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import (
    Action,
    Alert,
    AlertStatus,
    Asset,
    AssetCriticality,
    Case,
    Closure,
    CoverageObservation,
    CSE,
    DataQualityComponents,
    DataQualityScore,
    Escalation,
    EvidenceRef,
    ExpectationBasis,
    Finding,
    FindingType,
    Investigation,
    ReportingPeriod,
    ReviewDecisionState,
    Severity,
)
from backend.models.provenance import (
    AnalysisRun,
    EvidenceProvenanceRef,
    FindingProvenanceTrace,
)
from backend.models.ruleset import (
    DEFAULT_AUTHORITATIVE_RULESET_V1,
    AnalyticalRuleset,
)
from backend.repositories.base import (
    AuditEvent,
    BaseSATRepository,
    DatasetMetadata,
    DatasetVersionMetadata,
    ReviewDecisionRecord,
)

logger = logging.getLogger("satsa.repository.postgres")



def _get_database_url() -> str:
    """Resolves database URL from environment variables without hardcoded production credentials."""
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
        elif db_url.startswith("postgresql://") and not db_url.startswith("postgresql+"):
            db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return db_url

    user = os.environ.get("POSTGRES_USER", "satsa")
    password = os.environ.get("POSTGRES_PASSWORD", "satsa_dev_only_change_me")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    db = os.environ.get("POSTGRES_DB", "satsa")

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


class PostgresRepository(BaseSATRepository):
    """
    Relational database repository connecting to PostgreSQL (or SQLite for isolated testing).
    Guarantees that all datasets, versions, canonical entities, analysis runs, findings,
    evidence links, review decisions, and audit events survive application restart.
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or _get_database_url()
        self.is_sqlite = "sqlite" in self.db_url.lower()

        # Create SQLAlchemy engine
        if self.is_sqlite:
            connect_args = {"check_same_thread": False}
            kwargs = {"connect_args": connect_args, "pool_pre_ping": True}
            if ":memory:" in self.db_url:
                kwargs["poolclass"] = sa.pool.StaticPool
            self.engine: Engine = sa.create_engine(self.db_url, **kwargs)
            with self.engine.connect() as conn:
                conn.execute(text("PRAGMA foreign_keys = ON;"))
                conn.commit()
        else:
            self.engine = sa.create_engine(
                self.db_url,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20,
            )

        # In-memory working cache populated from DB
        self.datasets: dict[UUID, DatasetMetadata] = {}
        self.dataset_versions: dict[UUID, DatasetVersionMetadata] = {}
        self.canonical_datasets: dict[UUID, CanonicalDataset] = {}
        self.reconstructed_datasets: dict[UUID, ReconstructedDataset] = {}
        self.benchmark_engines: dict[UUID, PeerBenchmarkEngine] = {}
        self.findings_by_version: dict[UUID, list[Finding]] = {}
        self.findings_by_id: dict[UUID, Finding] = {}
        self.analysis_runs: dict[UUID, AnalysisRun] = {}
        self.data_quality_results: dict[UUID, DataQualityResult] = {}
        self.review_decisions: list[ReviewDecisionRecord] = []
        self.audit_events: list[AuditEvent] = []
        self.active_dataset_version_id: Optional[UUID] = None


        # Ensure schema tables exist and load state
        self._initialize_schema()
        self._load_state_from_db()

    # -----------------------------------------------------------------------
    # Schema DDL Initialization
    # -----------------------------------------------------------------------
    def _initialize_schema(self):
        """Creates required relational tables if they do not already exist."""
        ddl_statements = [
            """
            CREATE TABLE IF NOT EXISTS roles (
                role_id VARCHAR(64) PRIMARY KEY,
                role_name VARCHAR(64) NOT NULL UNIQUE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id VARCHAR(64) PRIMARY KEY,
                username VARCHAR(128) NOT NULL UNIQUE,
                password_hash VARCHAR(256) NOT NULL,
                role_id VARCHAR(64) NOT NULL,
                full_name VARCHAR(256),
                created_at TIMESTAMP NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS datasets (
                dataset_id VARCHAR(64) PRIMARY KEY,
                cse_id VARCHAR(64),
                name VARCHAR(256) NOT NULL,
                description TEXT,
                created_at TIMESTAMP NOT NULL,
                created_by VARCHAR(64)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS dataset_versions (
                dataset_version_id VARCHAR(64) PRIMARY KEY,
                dataset_id VARCHAR(64) NOT NULL REFERENCES datasets(dataset_id),
                version_number INTEGER NOT NULL,
                source_file_ref TEXT NOT NULL,
                import_time TIMESTAMP NOT NULL,
                transformation_version VARCHAR(32) NOT NULL,
                schema_version VARCHAR(32) NOT NULL,
                row_count INTEGER NOT NULL DEFAULT 0,
                data_quality_score NUMERIC,
                data_quality_components TEXT,
                data_quality_warnings TEXT,
                file_format VARCHAR(32),
                sha256_hash VARCHAR(128),
                accepted_rows INTEGER NOT NULL DEFAULT 0,
                rejected_rows INTEGER NOT NULL DEFAULT 0,
                rejection_reasons TEXT,
                is_immutable BOOLEAN NOT NULL DEFAULT 1,
                UNIQUE (dataset_id, version_number)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS cse (
                cse_id VARCHAR(64) PRIMARY KEY,
                dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
                name VARCHAR(256) NOT NULL,
                sector VARCHAR(128) NOT NULL,
                scale VARCHAR(64) NOT NULL,
                reporting_period_id VARCHAR(64),
                source_record_ref TEXT,
                ingest_time TIMESTAMP NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS reporting_periods (
                reporting_period_id VARCHAR(64) PRIMARY KEY,
                cse_id VARCHAR(64) NOT NULL REFERENCES cse(cse_id),
                period_start TIMESTAMP NOT NULL,
                period_end TIMESTAMP NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS assets (
                asset_id VARCHAR(64) PRIMARY KEY,
                dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
                cse_id VARCHAR(64) NOT NULL REFERENCES cse(cse_id),
                criticality VARCHAR(32) NOT NULL,
                asset_type VARCHAR(128) NOT NULL,
                environment VARCHAR(128) NOT NULL,
                expected_monitoring_context TEXT,
                source_record_ref TEXT,
                ingest_time TIMESTAMP NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS alerts (
                alert_id VARCHAR(64) PRIMARY KEY,
                dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
                cse_id VARCHAR(64) NOT NULL REFERENCES cse(cse_id),
                asset_id VARCHAR(64) NOT NULL REFERENCES assets(asset_id),
                reporting_period_id VARCHAR(64) NOT NULL REFERENCES reporting_periods(reporting_period_id),
                event_time TIMESTAMP NOT NULL,
                severity VARCHAR(32) NOT NULL,
                alert_category VARCHAR(128) NOT NULL,
                source VARCHAR(128) NOT NULL,
                status VARCHAR(32) NOT NULL,
                source_record_ref TEXT,
                ingest_time TIMESTAMP NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS investigations (
                investigation_id VARCHAR(64) PRIMARY KEY,
                dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
                alert_id VARCHAR(64) NOT NULL REFERENCES alerts(alert_id),
                started_at TIMESTAMP NOT NULL,
                ended_at TIMESTAMP,
                analyst_id VARCHAR(128),
                evidence_count INTEGER NOT NULL DEFAULT 0,
                disposition VARCHAR(128),
                source_record_ref TEXT,
                ingest_time TIMESTAMP NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id VARCHAR(64) PRIMARY KEY,
                dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
                alert_id VARCHAR(64) NOT NULL REFERENCES alerts(alert_id),
                opened_at TIMESTAMP NOT NULL,
                closed_at TIMESTAMP,
                severity VARCHAR(32) NOT NULL,
                outcome VARCHAR(128),
                source_record_ref TEXT,
                ingest_time TIMESTAMP NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS escalations (
                escalation_id VARCHAR(64) PRIMARY KEY,
                dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
                case_id VARCHAR(64) NOT NULL REFERENCES cases(case_id),
                escalated_at TIMESTAMP NOT NULL,
                level VARCHAR(64) NOT NULL,
                target VARCHAR(128) NOT NULL,
                source_record_ref TEXT,
                ingest_time TIMESTAMP NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS actions (
                action_id VARCHAR(64) PRIMARY KEY,
                dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
                case_id VARCHAR(64) NOT NULL REFERENCES cases(case_id),
                action_type VARCHAR(128) NOT NULL,
                performed_at TIMESTAMP NOT NULL,
                outcome VARCHAR(128),
                source_record_ref TEXT,
                ingest_time TIMESTAMP NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS closures (
                closure_id VARCHAR(64) PRIMARY KEY,
                dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
                case_id VARCHAR(64) NOT NULL REFERENCES cases(case_id),
                closed_at TIMESTAMP NOT NULL,
                reason VARCHAR(256) NOT NULL,
                reviewer VARCHAR(128),
                source_record_ref TEXT,
                ingest_time TIMESTAMP NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS coverage_observations (
                observation_id VARCHAR(64) PRIMARY KEY,
                dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
                cse_id VARCHAR(64) NOT NULL REFERENCES cse(cse_id),
                asset_id VARCHAR(64),
                alert_category VARCHAR(128),
                period_id VARCHAR(64) NOT NULL REFERENCES reporting_periods(reporting_period_id),
                expected_count NUMERIC NOT NULL,
                observed_count NUMERIC NOT NULL,
                source_record_ref TEXT,
                ingest_time TIMESTAMP NOT NULL
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS rulesets (
                ruleset_id VARCHAR(64) PRIMARY KEY,
                ruleset_name VARCHAR(128) NOT NULL,
                version VARCHAR(64) NOT NULL,
                weights_json TEXT NOT NULL,
                author VARCHAR(128),
                rationale TEXT,
                effective_date TIMESTAMP NOT NULL,
                is_active BOOLEAN DEFAULT false,
                UNIQUE (ruleset_name, version)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS analysis_runs (
                analysis_run_id VARCHAR(64) PRIMARY KEY,
                dataset_id VARCHAR(64),
                dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
                schema_version VARCHAR(32) NOT NULL DEFAULT '2.0.0',
                ruleset_id VARCHAR(64),
                ruleset_version VARCHAR(64) NOT NULL DEFAULT 'V1',
                detector_config TEXT,
                app_version VARCHAR(32) NOT NULL DEFAULT '1.0.0',
                git_commit VARCHAR(64),
                model_version_id VARCHAR(64),
                started_at TIMESTAMP NOT NULL,
                finished_at TIMESTAMP,
                status VARCHAR(32) NOT NULL DEFAULT 'COMPLETED',
                error_message TEXT,
                findings_count INTEGER NOT NULL DEFAULT 0
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS findings (
                finding_id VARCHAR(64) PRIMARY KEY,
                cse_id VARCHAR(64) NOT NULL REFERENCES cse(cse_id),
                reporting_period_id VARCHAR(64) NOT NULL,
                finding_type VARCHAR(64) NOT NULL,
                priority_score NUMERIC NOT NULL,
                priority_components TEXT NOT NULL,
                evidentiary_confidence NUMERIC NOT NULL,
                data_quality_score NUMERIC NOT NULL,
                data_quality_components TEXT NOT NULL,
                expectation_basis VARCHAR(64) NOT NULL,
                expected_behavior TEXT NOT NULL,
                observed_behavior TEXT NOT NULL,
                supporting_signals TEXT NOT NULL,
                contradicting_signals TEXT NOT NULL,
                peer_context TEXT,
                temporal_context TEXT,
                analytical_method VARCHAR(128) NOT NULL,
                ruleset_id VARCHAR(64),
                ruleset_version VARCHAR(64),
                model_version_id VARCHAR(64),
                model_version VARCHAR(64),
                dataset_version_id VARCHAR(64) NOT NULL REFERENCES dataset_versions(dataset_version_id),
                analysis_run_id VARCHAR(64) NOT NULL,
                review_status VARCHAR(64),
                review_notes TEXT,
                created_at TIMESTAMP NOT NULL,
                superseded_by VARCHAR(64)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS finding_evidence (
                finding_id VARCHAR(64) NOT NULL REFERENCES findings(finding_id),
                entity_type VARCHAR(64) NOT NULL,
                entity_id VARCHAR(64) NOT NULL,
                PRIMARY KEY (finding_id, entity_type, entity_id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS review_decisions (
                review_decision_id VARCHAR(64) PRIMARY KEY,
                finding_id VARCHAR(64) NOT NULL REFERENCES findings(finding_id),
                decision VARCHAR(64) NOT NULL,
                reviewer_id VARCHAR(64),
                reviewer_name VARCHAR(128),
                decided_at TIMESTAMP NOT NULL,
                notes TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                audit_event_id VARCHAR(64) PRIMARY KEY,
                user_id VARCHAR(64),
                username VARCHAR(128),
                action VARCHAR(128) NOT NULL,
                target_type VARCHAR(64),
                target_id VARCHAR(128),
                occurred_at TIMESTAMP NOT NULL,
                details_json TEXT
            );
            """,
        ]

        with self.engine.begin() as conn:
            for stmt in ddl_statements:
                conn.execute(text(stmt))

            # Seed default roles if not present
            role_rows = conn.execute(text("SELECT COUNT(*) FROM roles")).scalar()
            if not role_rows:
                for r_name in ["admin", "supervisor", "analyst"]:
                    conn.execute(
                        text("INSERT INTO roles (role_id, role_name) VALUES (:rid, :rname)"),
                        {"rid": f"role_{r_name}", "rname": r_name},
                    )

            # Seed default authoritative ruleset V1 if not present
            ruleset_rows = conn.execute(text("SELECT COUNT(*) FROM rulesets")).scalar()
            if not ruleset_rows:
                conn.execute(
                    text("""
                    INSERT INTO rulesets (ruleset_id, ruleset_name, version, weights_json, author, rationale, effective_date, is_active)
                    VALUES (:rid, :rname, :ver, :weights, :author, :rat, :eff, :active)
                    """),
                    {
                        "rid": str(DEFAULT_AUTHORITATIVE_RULESET_V1.ruleset_id),
                        "rname": DEFAULT_AUTHORITATIVE_RULESET_V1.name,
                        "ver": DEFAULT_AUTHORITATIVE_RULESET_V1.version,
                        "weights": json.dumps(DEFAULT_AUTHORITATIVE_RULESET_V1.to_dict()),
                        "author": DEFAULT_AUTHORITATIVE_RULESET_V1.author,
                        "rat": DEFAULT_AUTHORITATIVE_RULESET_V1.rationale,
                        "eff": DEFAULT_AUTHORITATIVE_RULESET_V1.effective_timestamp.isoformat(),
                        "active": True,
                    },
                )

            # Seed default users if not present
            user_rows = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
            if not user_rows:
                now_str = datetime.now(timezone.utc).isoformat()
                from backend.security.auth import hash_password
                seeds = [
                    ("usr_admin_01", "admin", "Admin@SAT2026!", "role_admin", "NCIIPC Lead Administrator"),
                    ("usr_sup_01", "supervisor", "Supervisor@SAT2026!", "role_supervisor", "Senior NCIIPC Examiner"),
                    ("usr_analyst_01", "analyst", "Analyst@SAT2026!", "role_analyst", "SOC Evidence Analyst"),
                ]
                for uid, uname, raw_pwd, rid, fname in seeds:
                    conn.execute(
                        text("""
                        INSERT INTO users (user_id, username, password_hash, role_id, full_name, created_at, is_active)
                        VALUES (:uid, :uname, :phash, :rid, :fname, :cat, 1)
                        """),
                        {
                            "uid": uid,
                            "uname": uname,
                            "phash": hash_password(raw_pwd),
                            "rid": rid,
                            "fname": fname,
                            "cat": now_str,
                        },
                    )

    # -----------------------------------------------------------------------
    # Reconstitution of State from DB on Startup / Restart
    # -----------------------------------------------------------------------
    def _load_state_from_db(self):
        """Loads all persisted datasets, canonical models, findings, and reviews from the database."""
        self.datasets.clear()
        self.dataset_versions.clear()
        self.canonical_datasets.clear()
        self.reconstructed_datasets.clear()
        self.benchmark_engines.clear()
        self.findings_by_version.clear()
        self.findings_by_id.clear()
        self.analysis_runs.clear()
        self.data_quality_results.clear()
        self.review_decisions.clear()
        self.audit_events.clear()

        with self.engine.connect() as conn:
            # 1. Load Audit Events
            audit_rows = conn.execute(
                text("SELECT audit_event_id, user_id, username, action, target_type, target_id, occurred_at, details_json FROM audit_events ORDER BY occurred_at DESC")
            ).mappings().all()

            for r in audit_rows:
                details = json.loads(r["details_json"]) if r["details_json"] else {}
                occ_at = r["occurred_at"]
                if isinstance(occ_at, str):
                    occ_at = datetime.fromisoformat(occ_at)
                if occ_at.tzinfo is None:
                    occ_at = occ_at.replace(tzinfo=timezone.utc)
                self.audit_events.append(
                    AuditEvent(
                        audit_event_id=UUID(r["audit_event_id"]),
                        user_id=r["user_id"] or "",
                        username=r["username"] or "",
                        action=r["action"],
                        target_type=r["target_type"] or "",
                        target_id=r["target_id"],
                        occurred_at=occ_at,
                        details=details,
                    )
                )

            # 2. Load Datasets
            ds_rows = conn.execute(
                text("SELECT dataset_id, name, description, created_at FROM datasets ORDER BY created_at ASC")
            ).mappings().all()

            for r in ds_rows:
                ds_id = UUID(r["dataset_id"])
                c_at = r["created_at"]
                if isinstance(c_at, str):
                    c_at = datetime.fromisoformat(c_at)
                if c_at.tzinfo is None:
                    c_at = c_at.replace(tzinfo=timezone.utc)
                self.datasets[ds_id] = DatasetMetadata(
                    dataset_id=ds_id,
                    name=r["name"],
                    description=r["description"] or "",
                    created_at=c_at,
                    versions=[],
                )

            # 3. Load Dataset Versions
            ver_rows = conn.execute(
                text("""
                SELECT dataset_version_id, dataset_id, version_number, source_file_ref, import_time,
                       transformation_version, schema_version, row_count, data_quality_score,
                       data_quality_components, data_quality_warnings, file_format, sha256_hash,
                       accepted_rows, rejected_rows, rejection_reasons
                FROM dataset_versions ORDER BY version_number ASC
                """)
            ).mappings().all()

            for vr in ver_rows:
                ver_id = UUID(vr["dataset_version_id"])
                ds_id = UUID(vr["dataset_id"])
                imp_time = vr["import_time"]
                if isinstance(imp_time, str):
                    imp_time = datetime.fromisoformat(imp_time)
                if imp_time.tzinfo is None:
                    imp_time = imp_time.replace(tzinfo=timezone.utc)

                dq_score = float(vr["data_quality_score"]) if vr["data_quality_score"] is not None else None
                dq_comps = json.loads(vr["data_quality_components"]) if vr["data_quality_components"] else None
                dq_warns = json.loads(vr["data_quality_warnings"]) if vr["data_quality_warnings"] else []
                rej_reasons = json.loads(vr["rejection_reasons"]) if vr["rejection_reasons"] else []

                ver_meta = DatasetVersionMetadata(
                    dataset_version_id=ver_id,
                    dataset_id=ds_id,
                    version_number=vr["version_number"],
                    source_file_ref=vr["source_file_ref"],
                    import_time=imp_time,
                    transformation_version=vr["transformation_version"],
                    schema_version=vr["schema_version"],
                    row_count=vr["row_count"],
                    data_quality_score=dq_score,
                    data_quality_components=dq_comps,
                    data_quality_warnings=dq_warns,
                    file_format=vr["file_format"],
                    sha256_hash=vr["sha256_hash"],
                    accepted_rows=vr["accepted_rows"],
                    rejected_rows=vr["rejected_rows"],
                    rejection_reasons=rej_reasons,
                )

                if ds_id in self.datasets:
                    self.datasets[ds_id].versions.append(ver_meta)
                self.dataset_versions[ver_id] = ver_meta
                self.active_dataset_version_id = ver_id

                # 4. Reconstitute Canonical Entities for this version
                canonical_ds = self._reconstitute_canonical_dataset(conn, ver_id)
                self.canonical_datasets[ver_id] = canonical_ds
                reconstructed_ds = ReconstructedDataset(canonical_ds)
                self.reconstructed_datasets[ver_id] = reconstructed_ds
                self.benchmark_engines[ver_id] = PeerBenchmarkEngine(reconstructed_ds)

                # Reconstruct DataQualityResult if score is available
                if dq_comps:
                    comp_obj = DQComponentsScore(
                        completeness_ratio=dq_comps.get("completeness_ratio", 1.0),
                        consistency_ratio=dq_comps.get("consistency_ratio", 1.0),
                        coverage_ratio=dq_comps.get("coverage_ratio", 1.0),
                        sample_sufficiency_ratio=dq_comps.get("sample_sufficiency_ratio", 1.0),
                    )
                    self.data_quality_results[ver_id] = DataQualityResult(
                        dataset_version_id=ver_id,
                        score=dq_score or 1.0,
                        components=comp_obj,
                        ruleset_version="V1",
                        computed_at=imp_time,
                        warnings=dq_warns,
                    )

                # 5. Load Findings and Linkages for this version
                findings = self._load_findings_for_version(conn, ver_id)
                self.findings_by_version[ver_id] = findings
                for f in findings:
                    self.findings_by_id[f.finding_id] = f

            # 5b. Load Analysis Runs
            run_rows = conn.execute(
                text("""
                SELECT analysis_run_id, dataset_id, dataset_version_id, schema_version, ruleset_id,
                       ruleset_version, detector_config, app_version, git_commit, started_at,
                       finished_at, status, error_message, findings_count
                FROM analysis_runs
                """)
            ).mappings().all()

            for rr in run_rows:
                st_at = rr["started_at"]
                if isinstance(st_at, str):
                    st_at = datetime.fromisoformat(st_at)
                if st_at.tzinfo is None:
                    st_at = st_at.replace(tzinfo=timezone.utc)

                fin_at = rr["finished_at"]
                if fin_at:
                    if isinstance(fin_at, str):
                        fin_at = datetime.fromisoformat(fin_at)
                    if fin_at.tzinfo is None:
                        fin_at = fin_at.replace(tzinfo=timezone.utc)

                det_cfg = json.loads(rr["detector_config"]) if rr["detector_config"] else {}
                ds_id = UUID(rr["dataset_id"]) if rr["dataset_id"] else UUID(rr["dataset_version_id"])

                ar = AnalysisRun(
                    analysis_run_id=UUID(rr["analysis_run_id"]),
                    dataset_id=ds_id,
                    dataset_version_id=UUID(rr["dataset_version_id"]),
                    schema_version=rr["schema_version"] or "2.0.0",
                    ruleset_version=rr["ruleset_version"] or "V1",
                    ruleset_id=UUID(rr["ruleset_id"]) if rr["ruleset_id"] else None,
                    detector_config=det_cfg,
                    app_version=rr["app_version"] or "1.0.0",
                    git_commit=rr["git_commit"] or "git-rev-satsa-v2",
                    started_at=st_at,
                    finished_at=fin_at,
                    status=rr["status"] or "COMPLETED",
                    error_message=rr["error_message"],
                    findings_count=int(rr["findings_count"] or 0),
                )
                self.analysis_runs[ar.analysis_run_id] = ar

            # 6. Load Review Decisions
            review_rows = conn.execute(
                text("""
                SELECT review_decision_id, finding_id, decision, reviewer_id, reviewer_name, decided_at, notes
                FROM review_decisions ORDER BY decided_at ASC
                """)
            ).mappings().all()

            for rr in review_rows:
                dec_at = rr["decided_at"]
                if isinstance(dec_at, str):
                    dec_at = datetime.fromisoformat(dec_at)
                if dec_at.tzinfo is None:
                    dec_at = dec_at.replace(tzinfo=timezone.utc)
                
                f_id = UUID(rr["finding_id"])
                dec_state = ReviewDecisionState(rr["decision"])
                self.review_decisions.append(
                    ReviewDecisionRecord(
                        review_decision_id=UUID(rr["review_decision_id"]),
                        finding_id=f_id,
                        decision=dec_state,
                        reviewer_id=rr["reviewer_id"] or "",
                        reviewer_name=rr["reviewer_name"] or "",
                        decided_at=dec_at,
                        notes=rr["notes"],
                    )
                )
                if f_id in self.findings_by_id:
                    self.findings_by_id[f_id].review_status = dec_state
                    self.findings_by_id[f_id].review_notes = rr["notes"]

    def _reconstitute_canonical_dataset(self, conn: sa.Connection, ver_id: UUID) -> CanonicalDataset:
        """Reads relational rows for a given dataset_version_id and returns a CanonicalDataset."""
        v_str = str(ver_id)

        # CSE
        cse_rows = conn.execute(
            text("SELECT cse_id, name, sector, scale, reporting_period_id, source_record_ref, ingest_time FROM cse WHERE dataset_version_id = :vid"),
            {"vid": v_str},
        ).mappings().all()

        cse_list = []
        for r in cse_rows:
            ing_time = r["ingest_time"]
            if isinstance(ing_time, str):
                ing_time = datetime.fromisoformat(ing_time)
            if ing_time.tzinfo is None:
                ing_time = ing_time.replace(tzinfo=timezone.utc)
            cse_list.append(
                CSE(
                    cse_id=UUID(r["cse_id"]),
                    dataset_version_id=ver_id,
                    name=r["name"],
                    sector=r["sector"],
                    scale=r["scale"],
                    reporting_period_id=UUID(r["reporting_period_id"]) if r["reporting_period_id"] else UUID(r["cse_id"]),
                    source_record_ref=r["source_record_ref"],
                    ingest_time=ing_time,
                )
            )

        # Reporting Periods
        rp_rows = conn.execute(
            text("""
            SELECT rp.reporting_period_id, rp.cse_id, rp.period_start, rp.period_end
            FROM reporting_periods rp
            JOIN cse c ON c.cse_id = rp.cse_id
            WHERE c.dataset_version_id = :vid
            """),
            {"vid": v_str},
        ).mappings().all()

        reporting_periods = []
        for r in rp_rows:
            p_start = r["period_start"]
            p_end = r["period_end"]
            if isinstance(p_start, str):
                p_start = datetime.fromisoformat(p_start)
            if isinstance(p_end, str):
                p_end = datetime.fromisoformat(p_end)
            if p_start.tzinfo is None:
                p_start = p_start.replace(tzinfo=timezone.utc)
            if p_end.tzinfo is None:
                p_end = p_end.replace(tzinfo=timezone.utc)
            reporting_periods.append(
                ReportingPeriod(
                    reporting_period_id=UUID(r["reporting_period_id"]),
                    cse_id=UUID(r["cse_id"]),
                    period_start=p_start,
                    period_end=p_end,
                )
            )

        # Assets
        asset_rows = conn.execute(
            text("SELECT asset_id, cse_id, criticality, asset_type, environment, expected_monitoring_context, source_record_ref, ingest_time FROM assets WHERE dataset_version_id = :vid"),
            {"vid": v_str},
        ).mappings().all()

        assets = []
        for r in asset_rows:
            ing_time = r["ingest_time"]
            if isinstance(ing_time, str):
                ing_time = datetime.fromisoformat(ing_time)
            if ing_time.tzinfo is None:
                ing_time = ing_time.replace(tzinfo=timezone.utc)
            assets.append(
                Asset(
                    asset_id=UUID(r["asset_id"]),
                    dataset_version_id=ver_id,
                    cse_id=UUID(r["cse_id"]),
                    criticality=AssetCriticality(r["criticality"]),
                    asset_type=r["asset_type"],
                    environment=r["environment"],
                    expected_monitoring_context=r["expected_monitoring_context"],
                    source_record_ref=r["source_record_ref"],
                    ingest_time=ing_time,
                )
            )

        # Alerts
        alert_rows = conn.execute(
            text("SELECT alert_id, cse_id, asset_id, reporting_period_id, event_time, severity, alert_category, source, status, source_record_ref, ingest_time FROM alerts WHERE dataset_version_id = :vid"),
            {"vid": v_str},
        ).mappings().all()

        alerts = []
        for r in alert_rows:
            ev_time = r["event_time"]
            ing_time = r["ingest_time"]
            if isinstance(ev_time, str):
                ev_time = datetime.fromisoformat(ev_time)
            if isinstance(ing_time, str):
                ing_time = datetime.fromisoformat(ing_time)
            if ev_time.tzinfo is None:
                ev_time = ev_time.replace(tzinfo=timezone.utc)
            if ing_time.tzinfo is None:
                ing_time = ing_time.replace(tzinfo=timezone.utc)
            alerts.append(
                Alert(
                    alert_id=UUID(r["alert_id"]),
                    dataset_version_id=ver_id,
                    cse_id=UUID(r["cse_id"]),
                    asset_id=UUID(r["asset_id"]),
                    reporting_period_id=UUID(r["reporting_period_id"]),
                    event_time=ev_time,
                    severity=Severity(r["severity"]),
                    alert_category=r["alert_category"],
                    source=r["source"],
                    status=AlertStatus(r["status"]),
                    source_record_ref=r["source_record_ref"],
                    ingest_time=ing_time,
                )
            )

        # Investigations
        inv_rows = conn.execute(
            text("SELECT investigation_id, alert_id, started_at, ended_at, analyst_id, evidence_count, disposition, source_record_ref, ingest_time FROM investigations WHERE dataset_version_id = :vid"),
            {"vid": v_str},
        ).mappings().all()

        investigations = []
        for r in inv_rows:
            st_at = r["started_at"]
            ed_at = r["ended_at"]
            ing_time = r["ingest_time"]
            if isinstance(st_at, str):
                st_at = datetime.fromisoformat(st_at)
            if isinstance(ed_at, str):
                ed_at = datetime.fromisoformat(ed_at)
            if isinstance(ing_time, str):
                ing_time = datetime.fromisoformat(ing_time)
            if st_at.tzinfo is None:
                st_at = st_at.replace(tzinfo=timezone.utc)
            if ed_at and ed_at.tzinfo is None:
                ed_at = ed_at.replace(tzinfo=timezone.utc)
            if ing_time.tzinfo is None:
                ing_time = ing_time.replace(tzinfo=timezone.utc)

            investigations.append(
                Investigation(
                    investigation_id=UUID(r["investigation_id"]),
                    dataset_version_id=ver_id,
                    alert_id=UUID(r["alert_id"]),
                    started_at=st_at,
                    ended_at=ed_at,
                    analyst_id=r["analyst_id"],
                    evidence_count=r["evidence_count"],
                    disposition=r["disposition"],
                    source_record_ref=r["source_record_ref"],
                    ingest_time=ing_time,
                )
            )

        # Cases
        case_rows = conn.execute(
            text("SELECT case_id, alert_id, opened_at, closed_at, severity, outcome, source_record_ref, ingest_time FROM cases WHERE dataset_version_id = :vid"),
            {"vid": v_str},
        ).mappings().all()

        cases = []
        for r in case_rows:
            op_at = r["opened_at"]
            cl_at = r["closed_at"]
            ing_time = r["ingest_time"]
            if isinstance(op_at, str):
                op_at = datetime.fromisoformat(op_at)
            if isinstance(cl_at, str):
                cl_at = datetime.fromisoformat(cl_at)
            if isinstance(ing_time, str):
                ing_time = datetime.fromisoformat(ing_time)
            if op_at.tzinfo is None:
                op_at = op_at.replace(tzinfo=timezone.utc)
            if cl_at and cl_at.tzinfo is None:
                cl_at = cl_at.replace(tzinfo=timezone.utc)
            if ing_time.tzinfo is None:
                ing_time = ing_time.replace(tzinfo=timezone.utc)

            cases.append(
                Case(
                    case_id=UUID(r["case_id"]),
                    dataset_version_id=ver_id,
                    alert_id=UUID(r["alert_id"]),
                    opened_at=op_at,
                    closed_at=cl_at,
                    severity=Severity(r["severity"]),
                    outcome=r["outcome"],
                    source_record_ref=r["source_record_ref"],
                    ingest_time=ing_time,
                )
            )

        # Escalations
        esc_rows = conn.execute(
            text("SELECT escalation_id, case_id, escalated_at, level, target, source_record_ref, ingest_time FROM escalations WHERE dataset_version_id = :vid"),
            {"vid": v_str},
        ).mappings().all()

        escalations = []
        for r in esc_rows:
            esc_at = r["escalated_at"]
            ing_time = r["ingest_time"]
            if isinstance(esc_at, str):
                esc_at = datetime.fromisoformat(esc_at)
            if isinstance(ing_time, str):
                ing_time = datetime.fromisoformat(ing_time)
            if esc_at.tzinfo is None:
                esc_at = esc_at.replace(tzinfo=timezone.utc)
            if ing_time.tzinfo is None:
                ing_time = ing_time.replace(tzinfo=timezone.utc)

            escalations.append(
                Escalation(
                    escalation_id=UUID(r["escalation_id"]),
                    dataset_version_id=ver_id,
                    case_id=UUID(r["case_id"]),
                    escalated_at=esc_at,
                    level=r["level"],
                    target=r["target"],
                    source_record_ref=r["source_record_ref"],
                    ingest_time=ing_time,
                )
            )

        # Actions
        act_rows = conn.execute(
            text("SELECT action_id, case_id, action_type, performed_at, outcome, source_record_ref, ingest_time FROM actions WHERE dataset_version_id = :vid"),
            {"vid": v_str},
        ).mappings().all()

        actions = []
        for r in act_rows:
            pf_at = r["performed_at"]
            ing_time = r["ingest_time"]
            if isinstance(pf_at, str):
                pf_at = datetime.fromisoformat(pf_at)
            if isinstance(ing_time, str):
                ing_time = datetime.fromisoformat(ing_time)
            if pf_at.tzinfo is None:
                pf_at = pf_at.replace(tzinfo=timezone.utc)
            if ing_time.tzinfo is None:
                ing_time = ing_time.replace(tzinfo=timezone.utc)

            actions.append(
                Action(
                    action_id=UUID(r["action_id"]),
                    dataset_version_id=ver_id,
                    case_id=UUID(r["case_id"]),
                    action_type=r["action_type"],
                    performed_at=pf_at,
                    outcome=r["outcome"],
                    source_record_ref=r["source_record_ref"],
                    ingest_time=ing_time,
                )
            )

        # Closures
        clo_rows = conn.execute(
            text("SELECT closure_id, case_id, closed_at, reason, reviewer, source_record_ref, ingest_time FROM closures WHERE dataset_version_id = :vid"),
            {"vid": v_str},
        ).mappings().all()

        closures = []
        for r in clo_rows:
            cl_at = r["closed_at"]
            ing_time = r["ingest_time"]
            if isinstance(cl_at, str):
                cl_at = datetime.fromisoformat(cl_at)
            if isinstance(ing_time, str):
                ing_time = datetime.fromisoformat(ing_time)
            if cl_at.tzinfo is None:
                cl_at = cl_at.replace(tzinfo=timezone.utc)
            if ing_time.tzinfo is None:
                ing_time = ing_time.replace(tzinfo=timezone.utc)

            closures.append(
                Closure(
                    closure_id=UUID(r["closure_id"]),
                    dataset_version_id=ver_id,
                    case_id=UUID(r["case_id"]),
                    closed_at=cl_at,
                    reason=r["reason"],
                    reviewer=r["reviewer"],
                    source_record_ref=r["source_record_ref"],
                    ingest_time=ing_time,
                )
            )

        # Coverage Observations
        cov_rows = conn.execute(
            text("SELECT observation_id, cse_id, asset_id, alert_category, period_id, expected_count, observed_count, source_record_ref, ingest_time FROM coverage_observations WHERE dataset_version_id = :vid"),
            {"vid": v_str},
        ).mappings().all()

        coverage_observations = []
        for r in cov_rows:
            ing_time = r["ingest_time"]
            if isinstance(ing_time, str):
                ing_time = datetime.fromisoformat(ing_time)
            if ing_time.tzinfo is None:
                ing_time = ing_time.replace(tzinfo=timezone.utc)

            coverage_observations.append(
                CoverageObservation(
                    observation_id=UUID(r["observation_id"]),
                    dataset_version_id=ver_id,
                    cse_id=UUID(r["cse_id"]),
                    asset_id=UUID(r["asset_id"]) if r["asset_id"] else None,
                    alert_category=r["alert_category"],
                    period_id=UUID(r["period_id"]),
                    expected_count=float(r["expected_count"]),
                    observed_count=float(r["observed_count"]),
                    source_record_ref=r["source_record_ref"],
                    ingest_time=ing_time,
                )
            )

        return CanonicalDataset(
            dataset_version_id=ver_id,
            cse_list=cse_list,
            reporting_periods=reporting_periods,
            assets=assets,
            alerts=alerts,
            investigations=investigations,
            cases=cases,
            escalations=escalations,
            actions=actions,
            closures=closures,
            coverage_observations=coverage_observations,
        )

    def _load_findings_for_version(self, conn: sa.Connection, ver_id: UUID) -> list[Finding]:
        """Loads findings and evidence linkages for a given dataset_version_id."""
        v_str = str(ver_id)

        finding_rows = conn.execute(
            text("""
            SELECT finding_id, cse_id, reporting_period_id, finding_type, priority_score,
                   priority_components, evidentiary_confidence, data_quality_score,
                   data_quality_components, expectation_basis, expected_behavior,
                   observed_behavior, supporting_signals, contradicting_signals,
                   peer_context, temporal_context, analytical_method, ruleset_version,
                   model_version, analysis_run_id, review_status, review_notes, created_at
            FROM findings WHERE dataset_version_id = :vid
            """),
            {"vid": v_str},
        ).mappings().all()

        if not finding_rows:
            return []

        # Load all evidence links for this version's findings
        f_ids = [r["finding_id"] for r in finding_rows]
        ev_rows = conn.execute(
            text("SELECT finding_id, entity_type, entity_id FROM finding_evidence WHERE finding_id IN :fids").bindparams(
                sa.bindparam("fids", expanding=True)
            ),
            {"fids": f_ids},
        ).mappings().all()

        evidence_map: dict[str, list[EvidenceRef]] = {fid: [] for fid in f_ids}
        for ev in ev_rows:
            evidence_map[ev["finding_id"]].append(
                EvidenceRef(
                    entity_type=ev["entity_type"],
                    entity_id=UUID(ev["entity_id"]),
                )
            )

        findings = []
        for r in finding_rows:
            fid_str = r["finding_id"]
            p_comps = json.loads(r["priority_components"]) if r["priority_components"] else {}
            dq_comps_data = json.loads(r["data_quality_components"]) if r["data_quality_components"] else {}
            sup_sigs = json.loads(r["supporting_signals"]) if r["supporting_signals"] else []
            con_sigs = json.loads(r["contradicting_signals"]) if r["contradicting_signals"] else []

            cr_at = r["created_at"]
            if isinstance(cr_at, str):
                cr_at = datetime.fromisoformat(cr_at)
            if cr_at.tzinfo is None:
                cr_at = cr_at.replace(tzinfo=timezone.utc)

            dq_score_val = float(r["data_quality_score"])
            dq_status = DataQualityScore(
                dataset_version_id=ver_id,
                score=dq_score_val,
                components=DataQualityComponents(
                    completeness_ratio=dq_comps_data.get("completeness_ratio", 1.0),
                    consistency_ratio=dq_comps_data.get("consistency_ratio", 1.0),
                    coverage_ratio=dq_comps_data.get("coverage_ratio", 1.0),
                    sample_sufficiency_ratio=dq_comps_data.get("sample_sufficiency_ratio", 1.0),
                ),
                ruleset_version=r["ruleset_version"] or "V1",
                computed_at=cr_at,
            )

            rev_status = ReviewDecisionState(r["review_status"]) if r["review_status"] else None

            f = Finding(
                finding_id=UUID(fid_str),
                cse_id=UUID(r["cse_id"]),
                reporting_period_id=UUID(r["reporting_period_id"]),
                finding_type=FindingType(r["finding_type"]),
                priority_score=float(r["priority_score"]),
                priority_components=p_comps,
                evidentiary_confidence=float(r["evidentiary_confidence"]),
                data_quality_status=dq_status,
                expectation_basis=ExpectationBasis(r["expectation_basis"]),
                expected_behavior=r["expected_behavior"],
                observed_behavior=r["observed_behavior"],
                supporting_signals=sup_sigs,
                contradicting_signals=con_sigs,
                peer_context=r["peer_context"],
                temporal_context=r["temporal_context"],
                evidence_refs=evidence_map.get(fid_str, []),
                analytical_method=r["analytical_method"],
                ruleset_version=r["ruleset_version"] or "V1",
                model_version=r["model_version"],
                dataset_version_id=ver_id,
                analysis_run_id=UUID(r["analysis_run_id"]),
                review_status=rev_status,
                review_notes=r["review_notes"],
                created_at=cr_at,
            )
            findings.append(f)

        return findings

    # -----------------------------------------------------------------------
    # Audit Log
    # -----------------------------------------------------------------------
    def record_audit_event(
        self,
        user_id: str,
        username: str,
        action: str,
        target_type: str,
        target_id: Optional[str] = None,
        details: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            audit_event_id=uuid4(),
            user_id=user_id,
            username=username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            occurred_at=datetime.now(timezone.utc),
            details=details or {},
        )

        with self.engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO audit_events (audit_event_id, user_id, username, action, target_type, target_id, occurred_at, details_json)
                VALUES (:eid, :uid, :uname, :act, :ttype, :tid, :occ, :det)
                """),
                {
                    "eid": str(event.audit_event_id),
                    "uid": event.user_id,
                    "uname": event.username,
                    "act": event.action,
                    "ttype": event.target_type,
                    "tid": event.target_id,
                    "occ": event.occurred_at.isoformat(),
                    "det": json.dumps(event.details),
                },
            )

        self.audit_events.insert(0, event)
        return event

    def get_audit_events(self, limit: int = 100) -> list[AuditEvent]:
        return self.audit_events[:limit]

    # -----------------------------------------------------------------------
    # Datasets & Versions Persistence
    # -----------------------------------------------------------------------
    def register_dataset_version(
        self,
        dataset_id: UUID,
        dataset_name: str,
        source_file_ref: str,
        canonical_dataset: CanonicalDataset,
        reconstructed_dataset: ReconstructedDataset,
        benchmark_engine: PeerBenchmarkEngine,
        findings: list[Finding],
        dq_score: Optional[float] = None,
        dq_result: Optional[DataQualityResult] = None,
        description: str = "",
        file_format: Optional[str] = None,
        sha256_hash: Optional[str] = None,
        accepted_rows: Optional[int] = None,
        rejected_rows: int = 0,
        rejection_reasons: Optional[list[str]] = None,
        analysis_run: Optional[AnalysisRun] = None,
    ) -> DatasetVersionMetadata:
        ver_id = canonical_dataset.dataset_version_id
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()

        # Orphan findings prevention
        for f in findings:
            if f.dataset_version_id != ver_id:
                raise ValueError(
                    f"Orphan finding detected: finding {f.finding_id} has dataset_version_id {f.dataset_version_id} "
                    f"which does not match version {ver_id}."
                )

        computed_score = dq_result.score if dq_result else (dq_score if dq_score is not None else 1.0)
        comps_dict = (
            {
                "completeness_ratio": dq_result.components.completeness_ratio,
                "consistency_ratio": dq_result.components.consistency_ratio,
                "coverage_ratio": dq_result.components.coverage_ratio,
                "sample_sufficiency_ratio": dq_result.components.sample_sufficiency_ratio,
            }
            if dq_result
            else None
        )
        warnings = dq_result.warnings if dq_result else []
        num_accepted = accepted_rows if accepted_rows is not None else len(canonical_dataset.alerts)

        with self.engine.begin() as conn:
            # 1. Datasets Table
            existing_ds = conn.execute(
                text("SELECT dataset_id FROM datasets WHERE dataset_id = :did"),
                {"did": str(dataset_id)},
            ).scalar()

            if not existing_ds:
                conn.execute(
                    text("""
                    INSERT INTO datasets (dataset_id, cse_id, name, description, created_at, created_by)
                    VALUES (:did, :cid, :name, :desc, :cat, :cby)
                    """),
                    {
                        "did": str(dataset_id),
                        "cid": str(canonical_dataset.cse_list[0].cse_id) if canonical_dataset.cse_list else None,
                        "name": dataset_name,
                        "desc": description,
                        "cat": now_str,
                        "cby": None,
                    },
                )

            # Get current version number
            current_ver_count = conn.execute(
                text("SELECT COUNT(*) FROM dataset_versions WHERE dataset_id = :did"),
                {"did": str(dataset_id)},
            ).scalar() or 0
            version_number = current_ver_count + 1

            # 2. Dataset Versions Table
            conn.execute(
                text("""
                INSERT INTO dataset_versions (
                    dataset_version_id, dataset_id, version_number, source_file_ref, import_time,
                    transformation_version, schema_version, row_count, data_quality_score,
                    data_quality_components, data_quality_warnings, file_format, sha256_hash,
                    accepted_rows, rejected_rows, rejection_reasons, is_immutable
                ) VALUES (
                    :vid, :did, :vnum, :sref, :itime,
                    :tver, :sver, :rcount, :dqscore,
                    :dqcomps, :dqwarns, :fformat, :shash,
                    :acount, :rcount_rej, :rreasons, 1
                )
                """),
                {
                    "vid": str(ver_id),
                    "did": str(dataset_id),
                    "vnum": version_number,
                    "sref": source_file_ref,
                    "itime": now_str,
                    "tver": "T1.0",
                    "sver": "S1.0",
                    "rcount": len(canonical_dataset.alerts),
                    "dqscore": computed_score,
                    "dqcomps": json.dumps(comps_dict) if comps_dict else None,
                    "dqwarns": json.dumps(warnings),
                    "fformat": file_format,
                    "shash": sha256_hash,
                    "acount": num_accepted,
                    "rcount_rej": rejected_rows,
                    "rreasons": json.dumps(rejection_reasons or []),
                },
            )

            # 3. Canonical CSE Table
            for cse in canonical_dataset.cse_list:
                conn.execute(
                    text("""
                    INSERT OR IGNORE INTO cse (cse_id, dataset_version_id, name, sector, scale, reporting_period_id, source_record_ref, ingest_time)
                    VALUES (:cid, :vid, :name, :sec, :scale, :rpid, :sref, :itime)
                    """),
                    {
                        "cid": str(cse.cse_id),
                        "vid": str(ver_id),
                        "name": cse.name,
                        "sec": cse.sector,
                        "scale": cse.scale,
                        "rpid": str(cse.reporting_period_id),
                        "sref": cse.source_record_ref,
                        "itime": cse.ingest_time.isoformat(),
                    },
                )

            # 4. Reporting Periods
            rp_dict: dict[UUID, ReportingPeriod] = {rp.reporting_period_id: rp for rp in canonical_dataset.reporting_periods}
            default_cse_id = canonical_dataset.cse_list[0].cse_id if canonical_dataset.cse_list else uuid4()
            for cse in canonical_dataset.cse_list:
                if cse.reporting_period_id not in rp_dict:
                    rp_dict[cse.reporting_period_id] = ReportingPeriod(
                        reporting_period_id=cse.reporting_period_id,
                        cse_id=cse.cse_id,
                        period_start=now,
                        period_end=now,
                    )
            for alt in canonical_dataset.alerts:
                if alt.reporting_period_id not in rp_dict:
                    rp_dict[alt.reporting_period_id] = ReportingPeriod(
                        reporting_period_id=alt.reporting_period_id,
                        cse_id=alt.cse_id or default_cse_id,
                        period_start=now,
                        period_end=now,
                    )

            for rp in rp_dict.values():
                conn.execute(
                    text("""
                    INSERT OR IGNORE INTO reporting_periods (reporting_period_id, cse_id, period_start, period_end)
                    VALUES (:rpid, :cid, :pstart, :pend)
                    """),
                    {
                        "rpid": str(rp.reporting_period_id),
                        "cid": str(rp.cse_id),
                        "pstart": rp.period_start.isoformat(),
                        "pend": rp.period_end.isoformat(),
                    },
                )

            # 5. Assets
            for a in canonical_dataset.assets:
                conn.execute(
                    text("""
                    INSERT OR IGNORE INTO assets (asset_id, dataset_version_id, cse_id, criticality, asset_type, environment, expected_monitoring_context, source_record_ref, ingest_time)
                    VALUES (:aid, :vid, :cid, :crit, :atype, :env, :ctx, :sref, :itime)
                    """),
                    {
                        "aid": str(a.asset_id),
                        "vid": str(ver_id),
                        "cid": str(a.cse_id),
                        "crit": a.criticality.value,
                        "atype": a.asset_type,
                        "env": a.environment,
                        "ctx": a.expected_monitoring_context,
                        "sref": a.source_record_ref,
                        "itime": a.ingest_time.isoformat(),
                    },
                )

            # 6. Alerts
            for alt in canonical_dataset.alerts:
                conn.execute(
                    text("""
                    INSERT OR IGNORE INTO alerts (alert_id, dataset_version_id, cse_id, asset_id, reporting_period_id, event_time, severity, alert_category, source, status, source_record_ref, ingest_time)
                    VALUES (:aid, :vid, :cid, :asid, :rpid, :etime, :sev, :cat, :src, :st, :sref, :itime)
                    """),
                    {
                        "aid": str(alt.alert_id),
                        "vid": str(ver_id),
                        "cid": str(alt.cse_id),
                        "asid": str(alt.asset_id),
                        "rpid": str(alt.reporting_period_id),
                        "etime": alt.event_time.isoformat(),
                        "sev": alt.severity.value,
                        "cat": alt.alert_category,
                        "src": alt.source,
                        "st": alt.status.value,
                        "sref": alt.source_record_ref,
                        "itime": alt.ingest_time.isoformat(),
                    },
                )

            # 7. Investigations
            for inv in canonical_dataset.investigations:
                conn.execute(
                    text("""
                    INSERT OR IGNORE INTO investigations (investigation_id, dataset_version_id, alert_id, started_at, ended_at, analyst_id, evidence_count, disposition, source_record_ref, ingest_time)
                    VALUES (:invid, :vid, :aid, :sat, :eat, :anid, :evcnt, :disp, :sref, :itime)
                    """),
                    {
                        "invid": str(inv.investigation_id),
                        "vid": str(ver_id),
                        "aid": str(inv.alert_id),
                        "sat": inv.started_at.isoformat(),
                        "eat": inv.ended_at.isoformat() if inv.ended_at else None,
                        "anid": inv.analyst_id,
                        "evcnt": inv.evidence_count,
                        "disp": inv.disposition,
                        "sref": inv.source_record_ref,
                        "itime": inv.ingest_time.isoformat(),
                    },
                )

            # 8. Cases
            for case in canonical_dataset.cases:
                conn.execute(
                    text("""
                    INSERT OR IGNORE INTO cases (case_id, dataset_version_id, alert_id, opened_at, closed_at, severity, outcome, source_record_ref, ingest_time)
                    VALUES (:cid, :vid, :aid, :oat, :cat, :sev, :outc, :sref, :itime)
                    """),
                    {
                        "cid": str(case.case_id),
                        "vid": str(ver_id),
                        "aid": str(case.alert_id),
                        "oat": case.opened_at.isoformat(),
                        "cat": case.closed_at.isoformat() if case.closed_at else None,
                        "sev": case.severity.value,
                        "outc": case.outcome,
                        "sref": case.source_record_ref,
                        "itime": case.ingest_time.isoformat(),
                    },
                )

            # 9. Escalations
            for esc in canonical_dataset.escalations:
                conn.execute(
                    text("""
                    INSERT OR IGNORE INTO escalations (escalation_id, dataset_version_id, case_id, escalated_at, level, target, source_record_ref, ingest_time)
                    VALUES (:eid, :vid, :cid, :eat, :lvl, :tgt, :sref, :itime)
                    """),
                    {
                        "eid": str(esc.escalation_id),
                        "vid": str(ver_id),
                        "cid": str(esc.case_id),
                        "eat": esc.escalated_at.isoformat(),
                        "lvl": esc.level,
                        "tgt": esc.target,
                        "sref": esc.source_record_ref,
                        "itime": esc.ingest_time.isoformat(),
                    },
                )

            # 10. Actions
            for act in canonical_dataset.actions:
                conn.execute(
                    text("""
                    INSERT OR IGNORE INTO actions (action_id, dataset_version_id, case_id, action_type, performed_at, outcome, source_record_ref, ingest_time)
                    VALUES (:aid, :vid, :cid, :atype, :pat, :outc, :sref, :itime)
                    """),
                    {
                        "aid": str(act.action_id),
                        "vid": str(ver_id),
                        "cid": str(act.case_id),
                        "atype": act.action_type,
                        "pat": act.performed_at.isoformat(),
                        "outc": act.outcome,
                        "sref": act.source_record_ref,
                        "itime": act.ingest_time.isoformat(),
                    },
                )

            # 11. Closures
            for clo in canonical_dataset.closures:
                conn.execute(
                    text("""
                    INSERT OR IGNORE INTO closures (closure_id, dataset_version_id, case_id, closed_at, reason, reviewer, source_record_ref, ingest_time)
                    VALUES (:cid, :vid, :csid, :cat, :rsn, :rev, :sref, :itime)
                    """),
                    {
                        "cid": str(clo.closure_id),
                        "vid": str(ver_id),
                        "csid": str(clo.case_id),
                        "cat": clo.closed_at.isoformat(),
                        "rsn": clo.reason,
                        "rev": clo.reviewer,
                        "sref": clo.source_record_ref,
                        "itime": clo.ingest_time.isoformat(),
                    },
                )

            # 12. Coverage Observations
            for cov in canonical_dataset.coverage_observations:
                conn.execute(
                    text("""
                    INSERT OR IGNORE INTO coverage_observations (observation_id, dataset_version_id, cse_id, asset_id, alert_category, period_id, expected_count, observed_count, source_record_ref, ingest_time)
                    VALUES (:oid, :vid, :cid, :aid, :cat, :pid, :exp, :obs, :sref, :itime)
                    """),
                    {
                        "oid": str(cov.observation_id),
                        "vid": str(ver_id),
                        "cid": str(cov.cse_id),
                        "aid": str(cov.asset_id) if cov.asset_id else None,
                        "cat": cov.alert_category,
                        "pid": str(cov.period_id),
                        "exp": cov.expected_count,
                        "obs": cov.observed_count,
                        "sref": cov.source_record_ref,
                        "itime": cov.ingest_time.isoformat(),
                    },
                )

            # 13. Analysis Run
            if analysis_run is not None:
                analysis_run.dataset_id = dataset_id
                analysis_run.dataset_version_id = ver_id
                run_to_save = analysis_run
            elif findings:
                run_to_save = AnalysisRun(
                    analysis_run_id=findings[0].analysis_run_id,
                    dataset_id=dataset_id,
                    dataset_version_id=ver_id,
                    schema_version="2.0.0",
                    ruleset_version=findings[0].ruleset_version or "V1",
                    app_version="1.0.0",
                    git_commit="git-rev-satsa-v2",
                    started_at=now,
                    finished_at=now,
                    status="COMPLETED",
                    findings_count=len(findings),
                )
            else:
                run_to_save = AnalysisRun(
                    analysis_run_id=uuid4(),
                    dataset_id=dataset_id,
                    dataset_version_id=ver_id,
                    schema_version="2.0.0",
                    ruleset_version="V1",
                    app_version="1.0.0",
                    git_commit="git-rev-satsa-v2",
                    started_at=now,
                    finished_at=now,
                    status="COMPLETED",
                    findings_count=0,
                )

            conn.execute(
                text("""
                INSERT INTO analysis_runs (
                    analysis_run_id, dataset_id, dataset_version_id, schema_version, ruleset_id,
                    ruleset_version, detector_config, app_version, git_commit, started_at,
                    finished_at, status, error_message, findings_count
                ) VALUES (
                    :arid, :did, :vid, :sver, :rid,
                    :rver, :dcfg, :aver, :gcom, :sat,
                    :fat, :st, :err, :fcnt
                )
                """),
                {
                    "arid": str(run_to_save.analysis_run_id),
                    "did": str(dataset_id),
                    "vid": str(ver_id),
                    "sver": run_to_save.schema_version,
                    "rid": str(run_to_save.ruleset_id) if run_to_save.ruleset_id else None,
                    "rver": run_to_save.ruleset_version,
                    "dcfg": json.dumps(run_to_save.detector_config),
                    "aver": run_to_save.app_version,
                    "gcom": run_to_save.git_commit,
                    "sat": run_to_save.started_at.isoformat(),
                    "fat": run_to_save.finished_at.isoformat() if run_to_save.finished_at else now_str,
                    "st": run_to_save.status,
                    "err": run_to_save.error_message,
                    "fcnt": run_to_save.findings_count,
                },
            )
            self.analysis_runs[run_to_save.analysis_run_id] = run_to_save

            # 14. Findings & Evidence Linkages
            for f in findings:
                conn.execute(
                    text("""
                    INSERT INTO findings (
                        finding_id, cse_id, reporting_period_id, finding_type, priority_score,
                        priority_components, evidentiary_confidence, data_quality_score,
                        data_quality_components, expectation_basis, expected_behavior,
                        observed_behavior, supporting_signals, contradicting_signals,
                        peer_context, temporal_context, analytical_method, ruleset_version,
                        model_version, dataset_version_id, analysis_run_id, review_status,
                        review_notes, created_at
                    ) VALUES (
                        :fid, :cid, :rpid, :ftype, :pscore,
                        :pcomps, :econf, :dqscore,
                        :dqcomps, :expbasis, :expb,
                        :obsb, :supsig, :consig,
                        :pctx, :tctx, :amethod, :rver,
                        :mver, :vid, :arid, :rstat,
                        :rnotes, :cat
                    )
                    """),
                    {
                        "fid": str(f.finding_id),
                        "cid": str(f.cse_id),
                        "rpid": str(f.reporting_period_id),
                        "ftype": f.finding_type.value,
                        "pscore": f.priority_score,
                        "pcomps": json.dumps(f.priority_components),
                        "econf": f.evidentiary_confidence,
                        "dqscore": f.data_quality_status.score,
                        "dqcomps": json.dumps({
                            "completeness_ratio": f.data_quality_status.components.completeness_ratio,
                            "consistency_ratio": f.data_quality_status.components.consistency_ratio,
                            "coverage_ratio": f.data_quality_status.components.coverage_ratio,
                            "sample_sufficiency_ratio": f.data_quality_status.components.sample_sufficiency_ratio,
                        }),
                        "expbasis": f.expectation_basis.value,
                        "expb": f.expected_behavior,
                        "obsb": f.observed_behavior,
                        "supsig": json.dumps(f.supporting_signals),
                        "consig": json.dumps(f.contradicting_signals),
                        "pctx": f.peer_context,
                        "tctx": f.temporal_context,
                        "amethod": f.analytical_method,
                        "rver": f.ruleset_version,
                        "mver": f.model_version,
                        "vid": str(ver_id),
                        "arid": str(f.analysis_run_id),
                        "rstat": f.review_status.value if f.review_status else None,
                        "rnotes": f.review_notes,
                        "cat": f.created_at.isoformat(),
                    },
                )

                # Finding Evidence Linkages
                for ev in f.evidence_refs:
                    conn.execute(
                        text("""
                        INSERT INTO finding_evidence (finding_id, entity_type, entity_id)
                        VALUES (:fid, :etype, :eid)
                        """),
                        {
                            "fid": str(f.finding_id),
                            "etype": ev.entity_type,
                            "eid": str(ev.entity_id),
                        },
                    )

        # Update In-Memory Structures
        if dataset_id not in self.datasets:
            self.datasets[dataset_id] = DatasetMetadata(
                dataset_id=dataset_id,
                name=dataset_name,
                description=description,
                created_at=now,
            )

        ver_meta = DatasetVersionMetadata(
            dataset_version_id=ver_id,
            dataset_id=dataset_id,
            version_number=version_number,
            source_file_ref=source_file_ref,
            import_time=now,
            transformation_version="T1.0",
            schema_version="S1.0",
            row_count=len(canonical_dataset.alerts),
            data_quality_score=computed_score,
            data_quality_components=comps_dict,
            data_quality_warnings=warnings,
            file_format=file_format,
            sha256_hash=sha256_hash,
            accepted_rows=num_accepted,
            rejected_rows=rejected_rows,
            rejection_reasons=rejection_reasons or [],
        )

        self.datasets[dataset_id].versions.append(ver_meta)
        self.dataset_versions[ver_id] = ver_meta
        self.canonical_datasets[ver_id] = canonical_dataset
        self.reconstructed_datasets[ver_id] = reconstructed_dataset
        self.benchmark_engines[ver_id] = benchmark_engine
        self.findings_by_version[ver_id] = findings

        if dq_result:
            self.data_quality_results[ver_id] = dq_result

        for f in findings:
            self.findings_by_id[f.finding_id] = f

        self.active_dataset_version_id = ver_id

        self.record_audit_event(
            user_id="system",
            username="System Administrator",
            action="INGEST_DATASET_VERSION",
            target_type="dataset_version",
            target_id=str(ver_id),
            details={
                "dataset_name": dataset_name,
                "version_number": ver_meta.version_number,
                "row_count": ver_meta.row_count,
                "data_quality_score": ver_meta.data_quality_score,
                "file_format": file_format,
                "sha256_hash": sha256_hash,
                "accepted_rows": num_accepted,
                "rejected_rows": rejected_rows,
                "findings_generated": len(findings),
            },
        )

        return ver_meta

    def list_datasets(self) -> list[dict[str, Any]]:
        result = []
        for ds in self.datasets.values():
            versions_list = []
            for v in ds.versions:
                dq_res = self.data_quality_results.get(v.dataset_version_id)
                comps = dq_res.components if dq_res else None
                breakdown = None
                if comps:
                    breakdown = {
                        "overall_score": round((v.data_quality_score or 0) * 100, 1),
                        "completeness": round(comps.completeness_ratio * 100, 1),
                        "consistency": round(comps.consistency_ratio * 100, 1),
                        "coverage": round(comps.coverage_ratio * 100, 1),
                        "sample_sufficiency": round(comps.sample_sufficiency_ratio * 100, 1),
                        "warnings": dq_res.warnings if dq_res else v.data_quality_warnings,
                    }
                elif v.data_quality_components:
                    breakdown = {
                        "overall_score": round((v.data_quality_score or 0) * 100, 1),
                        "completeness": round(v.data_quality_components.get("completeness_ratio", 1.0) * 100, 1),
                        "consistency": round(v.data_quality_components.get("consistency_ratio", 1.0) * 100, 1),
                        "coverage": round(v.data_quality_components.get("coverage_ratio", 1.0) * 100, 1),
                        "sample_sufficiency": round(v.data_quality_components.get("sample_sufficiency_ratio", 1.0) * 100, 1),
                        "warnings": v.data_quality_warnings,
                    }

                versions_list.append(
                    {
                        "dataset_version_id": str(v.dataset_version_id),
                        "version_number": v.version_number,
                        "source_file_ref": v.source_file_ref,
                        "import_time": v.import_time.isoformat(),
                        "row_count": v.row_count,
                        "data_quality_score": v.data_quality_score,
                        "data_quality_breakdown": breakdown,
                        "provenance": {
                            "file_format": v.file_format,
                            "sha256_hash": v.sha256_hash,
                            "accepted_rows": v.accepted_rows,
                            "rejected_rows": v.rejected_rows,
                            "rejection_reasons": v.rejection_reasons,
                        },
                    }
                )

            result.append(
                {
                    "dataset_id": str(ds.dataset_id),
                    "name": ds.name,
                    "description": ds.description,
                    "created_at": ds.created_at.isoformat(),
                    "version_count": len(ds.versions),
                    "versions": versions_list,
                }
            )
        return result

    # -----------------------------------------------------------------------
    # Findings & Evidence Drill-Down
    # -----------------------------------------------------------------------
    def get_findings(
        self,
        dataset_version_id: Optional[UUID] = None,
        sector: Optional[str] = None,
        finding_type: Optional[str] = None,
        cse_id: Optional[UUID] = None,
        min_priority: Optional[float] = None,
    ) -> list[Finding]:
        target_version = dataset_version_id or self.active_dataset_version_id
        if not target_version or target_version not in self.findings_by_version:
            return []

        all_findings = self.findings_by_version[target_version]
        canonical_ds = self.canonical_datasets.get(target_version)
        cse_map = {c.cse_id: c for c in canonical_ds.cse_list} if canonical_ds else {}

        filtered = []
        for f in all_findings:
            if cse_id and f.cse_id != cse_id:
                continue
            if finding_type and f.finding_type.value != finding_type:
                continue
            if min_priority and f.priority_score < min_priority:
                continue
            if sector:
                cse = cse_map.get(f.cse_id)
                if not cse or cse.sector.lower() != sector.lower():
                    continue
            filtered.append(f)

        filtered.sort(key=lambda x: x.priority_score, reverse=True)
        return filtered

    def get_finding_by_id(self, finding_id: UUID) -> Optional[Finding]:
        return self.findings_by_id.get(finding_id)

    def get_finding_evidence_records(self, finding_id: UUID) -> dict[str, Any]:
        finding = self.get_finding_by_id(finding_id)
        if not finding:
            return {}

        ver_id = finding.dataset_version_id
        canonical_ds = self.canonical_datasets.get(ver_id)
        reconstructed_ds = self.reconstructed_datasets.get(ver_id)

        if not canonical_ds or not reconstructed_ds:
            return {}

        cse = reconstructed_ds.cse_by_id.get(finding.cse_id)

        evidence_alerts = []
        evidence_cases = []
        evidence_investigations = []
        evidence_escalations = []
        evidence_actions = []
        evidence_closures = []
        evidence_assets = []

        ref_ids = {r.entity_id for r in finding.evidence_refs}

        for alt in canonical_ds.alerts:
            if alt.alert_id in ref_ids:
                asset = reconstructed_ds.assets_by_id.get(alt.asset_id)
                evidence_alerts.append(
                    {
                        "alert_id": str(alt.alert_id),
                        "source_record_id": alt.source_record_ref or f"alert_{alt.alert_id}",
                        "source_record_ref": alt.source_record_ref,
                        "severity": alt.severity.value,
                        "alert_category": alt.alert_category,
                        "source": alt.source,
                        "status": alt.status.value,
                        "event_time": alt.event_time.isoformat(),
                        "asset_type": asset.asset_type if asset else "Unknown",
                        "environment": asset.environment if asset else "Production",
                        "asset_criticality": asset.criticality.value if asset else "HIGH",
                    }
                )

        for case in canonical_ds.cases:
            if case.case_id in ref_ids:
                evidence_cases.append(
                    {
                        "case_id": str(case.case_id),
                        "source_record_id": case.source_record_ref or f"case_{case.case_id}",
                        "source_record_ref": case.source_record_ref,
                        "opened_at": case.opened_at.isoformat(),
                        "closed_at": case.closed_at.isoformat() if case.closed_at else None,
                        "severity": case.severity.value,
                        "outcome": case.outcome,
                    }
                )

        for inv in canonical_ds.investigations:
            if inv.investigation_id in ref_ids:
                evidence_investigations.append(
                    {
                        "investigation_id": str(inv.investigation_id),
                        "source_record_id": inv.source_record_ref or f"inv_{inv.investigation_id}",
                        "source_record_ref": inv.source_record_ref,
                        "analyst_id": inv.analyst_id,
                        "evidence_count": inv.evidence_count,
                        "started_at": inv.started_at.isoformat(),
                        "ended_at": inv.ended_at.isoformat() if inv.ended_at else None,
                        "disposition": inv.disposition,
                    }
                )

        for esc in canonical_ds.escalations:
            if esc.escalation_id in ref_ids or esc.case_id in ref_ids:
                evidence_escalations.append(
                    {
                        "escalation_id": str(esc.escalation_id),
                        "source_record_id": esc.source_record_ref or f"esc_{esc.escalation_id}",
                        "source_record_ref": esc.source_record_ref,
                        "case_id": str(esc.case_id),
                        "escalated_at": esc.escalated_at.isoformat(),
                        "level": esc.level,
                        "target": esc.target,
                    }
                )

        for act in canonical_ds.actions:
            if act.action_id in ref_ids or act.case_id in ref_ids:
                evidence_actions.append(
                    {
                        "action_id": str(act.action_id),
                        "source_record_id": act.source_record_ref or f"act_{act.action_id}",
                        "source_record_ref": act.source_record_ref,
                        "action_type": act.action_type,
                        "performed_at": act.performed_at.isoformat(),
                        "outcome": act.outcome,
                    }
                )

        for clo in canonical_ds.closures:
            if clo.closure_id in ref_ids or clo.case_id in ref_ids:
                evidence_closures.append(
                    {
                        "closure_id": str(clo.closure_id),
                        "source_record_id": clo.source_record_ref or f"clo_{clo.closure_id}",
                        "source_record_ref": clo.source_record_ref,
                        "closed_at": clo.closed_at.isoformat(),
                        "reason": clo.reason,
                        "reviewer": clo.reviewer,
                    }
                )

        for a in canonical_ds.assets:
            if a.asset_id in ref_ids or (finding.cse_id == a.cse_id and finding.finding_type == FindingType.COVERAGE_GAP):
                evidence_assets.append(
                    {
                        "asset_id": str(a.asset_id),
                        "source_record_id": a.source_record_ref or f"asset_{a.asset_id}",
                        "source_record_ref": a.source_record_ref,
                        "asset_type": a.asset_type,
                        "criticality": a.criticality.value,
                        "environment": a.environment,
                        "expected_monitoring_context": a.expected_monitoring_context,
                    }
                )

        all_source_ids = set()
        for item_list in [evidence_alerts, evidence_cases, evidence_investigations, evidence_escalations, evidence_actions, evidence_closures, evidence_assets]:
            for item in item_list:
                s_id = item.get("source_record_id")
                if s_id:
                    all_source_ids.add(s_id)

        evidence_references = [
            {
                "entity_type": ref.entity_type,
                "entity_id": str(ref.entity_id),
                "source_record_ref": ref.source_record_ref,
            }
            for ref in finding.evidence_refs
        ]

        return {
            "finding_id": str(finding.finding_id),
            "cse_id": str(finding.cse_id),
            "cse_name": cse.name if cse else "Unknown",
            "sector": cse.sector if cse else "Unknown",
            "evidence_state": finding.evidence_state.value if finding.evidence_state else "SUPPORTED",
            "total_evidence_count": len(evidence_alerts) + len(evidence_cases) + len(evidence_investigations) + len(evidence_escalations) + len(evidence_actions) + len(evidence_closures) + len(evidence_assets),
            "source_record_ids": sorted(list(all_source_ids)),
            "evidence_references": evidence_references,
            "alerts": evidence_alerts,
            "cases": evidence_cases,
            "investigations": evidence_investigations,
            "escalations": evidence_escalations,
            "actions": evidence_actions,
            "closures": evidence_closures,
            "assets": evidence_assets,
        }

    # -----------------------------------------------------------------------
    # Review Decisions
    # -----------------------------------------------------------------------
    def record_review_decision(
        self,
        finding_id: UUID,
        decision: ReviewDecisionState,
        reviewer_id: str,
        reviewer_name: str,
        notes: Optional[str] = None,
    ) -> ReviewDecisionRecord:
        finding = self.get_finding_by_id(finding_id)
        if finding:
            finding.review_status = decision
            finding.review_notes = notes

        record_id = uuid4()
        now = datetime.now(timezone.utc)
        record = ReviewDecisionRecord(
            review_decision_id=record_id,
            finding_id=finding_id,
            decision=decision,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            decided_at=now,
            notes=notes,
        )

        with self.engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO review_decisions (review_decision_id, finding_id, decision, reviewer_id, reviewer_name, decided_at, notes)
                VALUES (:rid, :fid, :dec, :uid, :uname, :dat, :notes)
                """),
                {
                    "rid": str(record_id),
                    "fid": str(finding_id),
                    "dec": decision.value,
                    "uid": reviewer_id,
                    "uname": reviewer_name,
                    "dat": now.isoformat(),
                    "notes": notes,
                },
            )
            conn.execute(
                text("UPDATE findings SET review_status = :stat, review_notes = :notes WHERE finding_id = :fid"),
                {"stat": decision.value, "notes": notes, "fid": str(finding_id)},
            )

        self.review_decisions.append(record)

        self.record_audit_event(
            user_id=reviewer_id,
            username=reviewer_name,
            action="SUBMIT_SUPERVISORY_REVIEW_DECISION",
            target_type="finding",
            target_id=str(finding_id),
            details={
                "decision": decision.value,
                "notes": notes,
                "finding_type": finding.finding_type.value if finding else "UNKNOWN",
            },
        )

        return record

    # -----------------------------------------------------------------------
    # Ruleset Management
    # -----------------------------------------------------------------------
    def get_active_ruleset(self) -> AnalyticalRuleset:
        """Retrieves the currently active analytical ruleset from the database."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT weights_json FROM rulesets WHERE is_active = true LIMIT 1")
            ).mappings().first()
            if row and row["weights_json"]:
                try:
                    data = json.loads(row["weights_json"])
                    return AnalyticalRuleset.from_dict(data)
                except Exception as e:
                    logger.warning("Could not parse active ruleset JSON (%s); returning fallback V1.", e)

        return DEFAULT_AUTHORITATIVE_RULESET_V1

    def get_ruleset_by_version(self, version: str) -> Optional[AnalyticalRuleset]:
        """Retrieves an analytical ruleset by version string."""
        with self.engine.connect() as conn:
            row = conn.execute(
                text("SELECT weights_json FROM rulesets WHERE version = :ver LIMIT 1"),
                {"ver": version},
            ).mappings().first()
            if row and row["weights_json"]:
                try:
                    data = json.loads(row["weights_json"])
                    return AnalyticalRuleset.from_dict(data)
                except Exception as e:
                    logger.warning("Could not parse ruleset JSON for version %s (%s).", version, e)
        return None

    def list_rulesets(self) -> list[AnalyticalRuleset]:
        """Lists all registered versioned rulesets."""
        rulesets: list[AnalyticalRuleset] = []
        with self.engine.connect() as conn:
            rows = conn.execute(
                text("SELECT weights_json FROM rulesets ORDER BY effective_date ASC")
            ).mappings().all()
            for r in rows:
                if r["weights_json"]:
                    try:
                        data = json.loads(r["weights_json"])
                        rulesets.append(AnalyticalRuleset.from_dict(data))
                    except Exception:
                        pass
        return rulesets or [DEFAULT_AUTHORITATIVE_RULESET_V1]

    def register_ruleset(
        self,
        ruleset: AnalyticalRuleset,
        set_active: bool = False,
    ) -> AnalyticalRuleset:
        """Registers a new versioned ruleset in PostgreSQL."""
        w_json = json.dumps(ruleset.to_dict())
        with self.engine.begin() as conn:
            if set_active or ruleset.is_active:
                conn.execute(text("UPDATE rulesets SET is_active = false"))
                ruleset.is_active = True

            # Insert or update ruleset
            existing = conn.execute(
                text("SELECT ruleset_id FROM rulesets WHERE version = :ver"),
                {"ver": ruleset.version},
            ).scalar()

            if existing:
                conn.execute(
                    text("""
                    UPDATE rulesets
                    SET ruleset_name = :rname,
                        weights_json = :wjson,
                        author = :auth,
                        rationale = :rat,
                        effective_date = :eff,
                        is_active = :act
                    WHERE version = :ver
                    """),
                    {
                        "rname": ruleset.name,
                        "wjson": w_json,
                        "auth": ruleset.author,
                        "rat": ruleset.rationale,
                        "eff": ruleset.effective_timestamp.isoformat(),
                        "act": ruleset.is_active,
                        "ver": ruleset.version,
                    },
                )
            else:
                conn.execute(
                    text("""
                    INSERT INTO rulesets (ruleset_id, ruleset_name, version, weights_json, author, rationale, effective_date, is_active)
                    VALUES (:rid, :rname, :ver, :wjson, :auth, :rat, :eff, :act)
                    """),
                    {
                        "rid": str(ruleset.ruleset_id),
                        "rname": ruleset.name,
                        "ver": ruleset.version,
                        "wjson": w_json,
                        "auth": ruleset.author,
                        "rat": ruleset.rationale,
                        "eff": ruleset.effective_timestamp.isoformat(),
                        "act": ruleset.is_active,
                    },
                )

        self.record_audit_event(
            user_id="system",
            username="System Engine",
            action="REGISTER_ANALYTICAL_RULESET",
            target_type="ruleset",
            target_id=str(ruleset.ruleset_id),
            details={
                "ruleset_name": ruleset.name,
                "version": ruleset.version,
                "set_active": set_active,
            },
        )
        return ruleset

    def set_active_ruleset(self, version: str) -> AnalyticalRuleset:
        """Activates a specific versioned ruleset."""
        target = self.get_ruleset_by_version(version)
        if not target:
            raise ValueError(f"Ruleset version '{version}' not found in database.")

        with self.engine.begin() as conn:
            conn.execute(text("UPDATE rulesets SET is_active = false"))
            conn.execute(
                text("UPDATE rulesets SET is_active = true WHERE version = :ver"),
                {"ver": version},
            )

        target.is_active = True
        self.record_audit_event(
            user_id="system",
            username="System Engine",
            action="ACTIVATE_ANALYTICAL_RULESET",
            target_type="ruleset",
            target_id=version,
            details={"version": version},
        )
        return target

    # -----------------------------------------------------------------------
    # Analysis Runs & Provenance
    # -----------------------------------------------------------------------
    def record_analysis_run(self, run: AnalysisRun) -> AnalysisRun:
        """Records or updates an analytical execution run in the database."""
        now_str = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text("""
                INSERT INTO analysis_runs (
                    analysis_run_id, dataset_id, dataset_version_id, schema_version, ruleset_id,
                    ruleset_version, detector_config, app_version, git_commit, started_at,
                    finished_at, status, error_message, findings_count
                ) VALUES (
                    :arid, :did, :vid, :sver, :rid,
                    :rver, :dcfg, :aver, :gcom, :sat,
                    :fat, :st, :err, :fcnt
                )
                ON CONFLICT (analysis_run_id) DO UPDATE
                SET status = EXCLUDED.status,
                    finished_at = EXCLUDED.finished_at,
                    error_message = EXCLUDED.error_message,
                    findings_count = EXCLUDED.findings_count
                """),
                {
                    "arid": str(run.analysis_run_id),
                    "did": str(run.dataset_id),
                    "vid": str(run.dataset_version_id),
                    "sver": run.schema_version,
                    "rid": str(run.ruleset_id) if run.ruleset_id else None,
                    "rver": run.ruleset_version,
                    "dcfg": json.dumps(run.detector_config),
                    "aver": run.app_version,
                    "gcom": run.git_commit,
                    "sat": run.started_at.isoformat(),
                    "fat": run.finished_at.isoformat() if run.finished_at else now_str,
                    "st": run.status,
                    "err": run.error_message,
                    "fcnt": run.findings_count,
                },
            )
        self.analysis_runs[run.analysis_run_id] = run
        return run

    def get_analysis_run(self, analysis_run_id: UUID) -> Optional[AnalysisRun]:
        """Retrieves an analysis run by ID from cache or database."""
        if analysis_run_id in self.analysis_runs:
            return self.analysis_runs[analysis_run_id]

        with self.engine.connect() as conn:
            row = conn.execute(
                text("""
                SELECT analysis_run_id, dataset_id, dataset_version_id, schema_version, ruleset_id,
                       ruleset_version, detector_config, app_version, git_commit, started_at,
                       finished_at, status, error_message, findings_count
                FROM analysis_runs WHERE analysis_run_id = :arid
                """),
                {"arid": str(analysis_run_id)},
            ).mappings().first()

            if not row:
                return None

            st_at = row["started_at"]
            if isinstance(st_at, str):
                st_at = datetime.fromisoformat(st_at)
            if st_at.tzinfo is None:
                st_at = st_at.replace(tzinfo=timezone.utc)

            fin_at = row["finished_at"]
            if fin_at:
                if isinstance(fin_at, str):
                    fin_at = datetime.fromisoformat(fin_at)
                if fin_at.tzinfo is None:
                    fin_at = fin_at.replace(tzinfo=timezone.utc)

            det_cfg = json.loads(row["detector_config"]) if row["detector_config"] else {}
            ds_id = UUID(row["dataset_id"]) if row["dataset_id"] else UUID(row["dataset_version_id"])

            ar = AnalysisRun(
                analysis_run_id=UUID(row["analysis_run_id"]),
                dataset_id=ds_id,
                dataset_version_id=UUID(row["dataset_version_id"]),
                schema_version=row["schema_version"] or "2.0.0",
                ruleset_version=row["ruleset_version"] or "V1",
                ruleset_id=UUID(row["ruleset_id"]) if row["ruleset_id"] else None,
                detector_config=det_cfg,
                app_version=row["app_version"] or "1.0.0",
                git_commit=row["git_commit"] or "git-rev-satsa-v2",
                started_at=st_at,
                finished_at=fin_at,
                status=row["status"] or "COMPLETED",
                error_message=row["error_message"],
                findings_count=int(row["findings_count"] or 0),
            )
            self.analysis_runs[ar.analysis_run_id] = ar
            return ar

    def get_finding_provenance(self, finding_id: UUID) -> Optional[FindingProvenanceTrace]:
        """Retrieves complete 6-tier provenance lineage trace for a finding."""
        finding = self.get_finding_by_id(finding_id)
        if not finding:
            return None

        ver_id = finding.dataset_version_id
        ver_meta = self.dataset_versions.get(ver_id)
        ds_id = ver_meta.dataset_id if ver_meta else ver_id
        ds_meta = self.datasets.get(ds_id)
        ds_name = ds_meta.name if ds_meta else "Unknown Dataset"

        run = self.get_analysis_run(finding.analysis_run_id)
        if not run:
            run = AnalysisRun(
                analysis_run_id=finding.analysis_run_id,
                dataset_id=ds_id,
                dataset_version_id=ver_id,
                schema_version="2.0.0",
                ruleset_version=finding.ruleset_version or "V1",
                app_version="1.0.0",
                git_commit="git-rev-satsa-v2",
                started_at=finding.created_at,
                finished_at=finding.created_at,
                status="COMPLETED",
                findings_count=1,
            )

        # Build source ref map from canonical dataset
        canonical_ds = self.canonical_datasets.get(ver_id)
        source_ref_map: dict[UUID, str] = {}
        if canonical_ds:
            for c in canonical_ds.cse_list:
                if c.source_record_ref:
                    source_ref_map[c.cse_id] = c.source_record_ref
            for a in canonical_ds.assets:
                if a.source_record_ref:
                    source_ref_map[a.asset_id] = a.source_record_ref
            for alt in canonical_ds.alerts:
                if alt.source_record_ref:
                    source_ref_map[alt.alert_id] = alt.source_record_ref
            for inv in canonical_ds.investigations:
                if inv.source_record_ref:
                    source_ref_map[inv.investigation_id] = inv.source_record_ref
            for case in canonical_ds.cases:
                if case.source_record_ref:
                    source_ref_map[case.case_id] = case.source_record_ref
            for esc in canonical_ds.escalations:
                if esc.source_record_ref:
                    source_ref_map[esc.escalation_id] = esc.source_record_ref
            for act in canonical_ds.actions:
                if act.source_record_ref:
                    source_ref_map[act.action_id] = act.source_record_ref
            for clo in canonical_ds.closures:
                if clo.source_record_ref:
                    source_ref_map[clo.closure_id] = clo.source_record_ref

        evidence_provenance_refs = [
            EvidenceProvenanceRef(
                entity_type=ref.entity_type,
                entity_id=ref.entity_id,
                source_record_ref=ref.source_record_ref or source_ref_map.get(ref.entity_id, f"{ref.entity_type}_{ref.entity_id}"),
            )
            for ref in finding.evidence_refs
        ]

        source_rec_ids = [ref.source_record_ref for ref in evidence_provenance_refs if ref.source_record_ref]

        priority_label, _ = compute_priority_tier(
            priority_score=finding.priority_score,
            independent_signals_count=len(finding.supporting_signals),
            data_quality_score=finding.data_quality_status.score if finding.data_quality_status else 1.0,
            evidence_state=finding.evidence_state,
        )

        return FindingProvenanceTrace(
            source_file_ref=ver_meta.source_file_ref if ver_meta else "unknown_source",
            sha256_hash=ver_meta.sha256_hash if ver_meta else None,
            file_format=ver_meta.file_format if ver_meta else None,
            import_time=ver_meta.import_time if ver_meta else finding.created_at,
            dataset_id=ds_id,
            dataset_name=ds_name,
            dataset_version_id=ver_id,
            version_number=ver_meta.version_number if ver_meta else 1,
            row_count=ver_meta.row_count if ver_meta else len(canonical_ds.alerts) if canonical_ds else 0,
            data_quality_score=finding.data_quality_status.score,
            analysis_run_id=run.analysis_run_id,
            schema_version=run.schema_version,
            ruleset_version=run.ruleset_version,
            detector_config=run.detector_config,
            app_version=run.app_version,
            git_commit=run.git_commit,
            started_at=run.started_at,
            finished_at=run.finished_at,
            status=run.status,
            error_message=run.error_message,
            finding_id=finding.finding_id,
            finding_type=finding.finding_type.value,
            detector=finding.finding_type.value,
            detector_version=finding.model_version or "1.0.0",
            reason=finding.observed_behavior or finding.expected_behavior,
            source_entity={
                "cse_id": str(finding.cse_id),
                "cse_name": ds_name,
                "sector": "Critical Infrastructure",
            },
            source_record_ids=source_rec_ids,
            priority_score=finding.priority_score,
            priority_label=priority_label,
            evidentiary_confidence=finding.evidentiary_confidence,
            calculation_inputs={
                "signal_count": len(finding.supporting_signals),
                "priority_components": finding.priority_components,
                "data_quality_score": finding.data_quality_status.score if finding.data_quality_status else 1.0,
                "evidence_state": finding.evidence_state.value if finding.evidence_state else "SUPPORTED",
                "peer_context": finding.peer_context,
                "temporal_context": finding.temporal_context,
            },
            calculation_result={
                "priority_score": finding.priority_score,
                "priority_label": priority_label,
                "evidentiary_confidence": finding.evidentiary_confidence,
                "components": finding.priority_components,
            },
            evidence_records_count=len(finding.evidence_refs),
            evidence_refs=evidence_provenance_refs,
        )


