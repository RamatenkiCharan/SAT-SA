"""
SQLite Durable Persistence Engine for SAT-SA.
Provides robust relational persistence for Datasets, Versions, Canonical Entities,
Findings, Evidence linkages, Review Decisions, Rulesets, and Immutable Audit Logs.
Guarantees full state recovery across application restarts (SRS §7.2 / §24).
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.data_quality.quality_score import DataQualityResult
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.rulesets.ruleset_manager import RulesetRecord
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import (
    CSE,
    Action,
    Alert,
    Asset,
    AssetCriticality,
    Case,
    Closure,
    CoverageObservation,
    DataQualityComponents,
    DataQualityScore,
    Escalation,
    EvidenceRef,
    ExpectationBasis,
    Finding,
    FindingType,
    Investigation,
    ReviewDecisionState,
    Severity,
)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "sat_sa.db"


class SQLiteDatabase:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = str(db_path)
        self._init_schema()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS dataset_versions (
                    dataset_version_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    version_number INTEGER NOT NULL,
                    source_file_ref TEXT NOT NULL,
                    import_time TEXT NOT NULL,
                    transformation_version TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    row_count INTEGER NOT NULL,
                    data_quality_score REAL,
                    canonical_data_json TEXT NOT NULL,
                    FOREIGN KEY (dataset_id) REFERENCES datasets(dataset_id)
                );

                CREATE TABLE IF NOT EXISTS findings (
                    finding_id TEXT PRIMARY KEY,
                    dataset_version_id TEXT NOT NULL,
                    cse_id TEXT NOT NULL,
                    reporting_period_id TEXT NOT NULL,
                    finding_type TEXT NOT NULL,
                    priority_score REAL NOT NULL,
                    priority_components_json TEXT NOT NULL,
                    evidentiary_confidence REAL NOT NULL,
                    expectation_basis TEXT NOT NULL,
                    expected_behavior TEXT NOT NULL,
                    observed_behavior TEXT NOT NULL,
                    supporting_signals_json TEXT NOT NULL,
                    contradicting_signals_json TEXT NOT NULL,
                    peer_context TEXT,
                    temporal_context TEXT,
                    analytical_method TEXT NOT NULL,
                    ruleset_version TEXT NOT NULL,
                    analysis_run_id TEXT NOT NULL,
                    review_status TEXT,
                    review_notes TEXT,
                    evidence_refs_json TEXT NOT NULL,
                    finding_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(dataset_version_id)
                );

                CREATE TABLE IF NOT EXISTS review_decisions (
                    review_decision_id TEXT PRIMARY KEY,
                    finding_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reviewer_id TEXT NOT NULL,
                    reviewer_name TEXT NOT NULL,
                    decided_at TEXT NOT NULL,
                    notes TEXT,
                    FOREIGN KEY (finding_id) REFERENCES findings(finding_id)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    audit_event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_type TEXT NOT NULL,
                    target_id TEXT,
                    occurred_at TEXT NOT NULL,
                    details_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS rulesets (
                    ruleset_id TEXT PRIMARY KEY,
                    ruleset_version TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    data_quality_weights_json TEXT NOT NULL,
                    fusion_weights_json TEXT NOT NULL,
                    detector_thresholds_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis_runs (
                    analysis_run_id TEXT PRIMARY KEY,
                    dataset_version_id TEXT NOT NULL,
                    ruleset_version TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    findings_count INTEGER,
                    data_quality_score REAL,
                    error_info TEXT,
                    FOREIGN KEY (dataset_version_id) REFERENCES dataset_versions(dataset_version_id)
                );
                """
            )

    # -----------------------------------------------------------------------
    # Datasets and Versions Persistence
    # -----------------------------------------------------------------------
    def save_dataset(self, dataset_id: UUID, name: str, description: str, created_at: datetime) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO datasets (dataset_id, name, description, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (str(dataset_id), name, description, created_at.isoformat()),
            )

    def save_dataset_version(
        self,
        dataset_version_id: UUID,
        dataset_id: UUID,
        version_number: int,
        source_file_ref: str,
        import_time: datetime,
        transformation_version: str,
        schema_version: str,
        row_count: int,
        data_quality_score: Optional[float],
        canonical_dataset: CanonicalDataset,
        findings: list[Finding],
    ) -> None:
        canonical_dict = canonical_dataset.to_dict()
        canonical_json = json.dumps(canonical_dict)

        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO dataset_versions (
                    dataset_version_id, dataset_id, version_number, source_file_ref,
                    import_time, transformation_version, schema_version, row_count,
                    data_quality_score, canonical_data_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(dataset_version_id),
                    str(dataset_id),
                    version_number,
                    source_file_ref,
                    import_time.isoformat(),
                    transformation_version,
                    schema_version,
                    row_count,
                    data_quality_score,
                    canonical_json,
                ),
            )

            # Insert findings
            for f in findings:
                finding_dict = f.model_dump(mode="json")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO findings (
                        finding_id, dataset_version_id, cse_id, reporting_period_id,
                        finding_type, priority_score, priority_components_json,
                        evidentiary_confidence, expectation_basis, expected_behavior,
                        observed_behavior, supporting_signals_json, contradicting_signals_json,
                        peer_context, temporal_context, analytical_method, ruleset_version,
                        analysis_run_id, review_status, review_notes, evidence_refs_json,
                        finding_json, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(f.finding_id),
                        str(f.dataset_version_id),
                        str(f.cse_id),
                        str(f.reporting_period_id),
                        f.finding_type.value,
                        f.priority_score,
                        json.dumps(f.priority_components),
                        f.evidentiary_confidence,
                        f.expectation_basis.value,
                        f.expected_behavior,
                        f.observed_behavior,
                        json.dumps(f.supporting_signals),
                        json.dumps(f.contradicting_signals),
                        f.peer_context,
                        f.temporal_context,
                        f.analytical_method,
                        f.ruleset_version,
                        str(f.analysis_run_id),
                        f.review_status.value if f.review_status else None,
                        f.review_notes,
                        json.dumps([r.model_dump(mode="json") for r in f.evidence_refs]),
                        json.dumps(finding_dict),
                        f.created_at.isoformat(),
                    ),
                )

    def save_review_decision(
        self,
        review_decision_id: UUID,
        finding_id: UUID,
        decision: ReviewDecisionState,
        reviewer_id: str,
        reviewer_name: str,
        decided_at: datetime,
        notes: Optional[str],
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO review_decisions (
                    review_decision_id, finding_id, decision, reviewer_id,
                    reviewer_name, decided_at, notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(review_decision_id),
                    str(finding_id),
                    decision.value,
                    reviewer_id,
                    reviewer_name,
                    decided_at.isoformat(),
                    notes,
                ),
            )
            # Update finding review status in findings table
            conn.execute(
                """
                UPDATE findings
                SET review_status = ?, review_notes = ?
                WHERE finding_id = ?
                """,
                (decision.value, notes, str(finding_id)),
            )

    def save_audit_event(
        self,
        audit_event_id: UUID,
        user_id: str,
        username: str,
        action: str,
        target_type: str,
        target_id: Optional[str],
        occurred_at: datetime,
        details: dict[str, Any],
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO audit_events (
                    audit_event_id, user_id, username, action, target_type,
                    target_id, occurred_at, details_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(audit_event_id),
                    user_id,
                    username,
                    action,
                    target_type,
                    target_id,
                    occurred_at.isoformat(),
                    json.dumps(details),
                ),
            )

    def save_analysis_run(
        self,
        analysis_run_id: UUID,
        dataset_version_id: UUID,
        ruleset_version: str,
        started_at: datetime,
        completed_at: Optional[datetime],
        status: str,
        findings_count: int,
        data_quality_score: Optional[float],
        error_info: Optional[str] = None,
    ) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO analysis_runs (
                    analysis_run_id, dataset_version_id, ruleset_version,
                    started_at, completed_at, status, findings_count,
                    data_quality_score, error_info
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(analysis_run_id),
                    str(dataset_version_id),
                    ruleset_version,
                    started_at.isoformat(),
                    completed_at.isoformat() if completed_at else None,
                    status,
                    findings_count,
                    data_quality_score,
                    error_info,
                ),
            )

    def save_ruleset(self, ruleset: RulesetRecord) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO rulesets (
                    ruleset_id, ruleset_version, name, description, created_at,
                    data_quality_weights_json, fusion_weights_json, detector_thresholds_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(ruleset.ruleset_id),
                    ruleset.ruleset_version,
                    ruleset.name,
                    ruleset.description,
                    ruleset.created_at.isoformat(),
                    json.dumps(ruleset.data_quality_weights),
                    json.dumps(ruleset.fusion_weights),
                    json.dumps(ruleset.detector_thresholds),
                ),
            )

    # -----------------------------------------------------------------------
    # Data Loading / Rehydration
    # -----------------------------------------------------------------------
    def load_all_data(self) -> dict[str, Any]:
        """Loads complete state from SQLite on startup to rehydrate in-memory query structures."""
        with self._connection() as conn:
            datasets_rows = conn.execute("SELECT * FROM datasets ORDER BY created_at ASC").fetchall()
            versions_rows = conn.execute("SELECT * FROM dataset_versions ORDER BY import_time ASC").fetchall()
            findings_rows = conn.execute("SELECT * FROM findings").fetchall()
            reviews_rows = conn.execute("SELECT * FROM review_decisions ORDER BY decided_at ASC").fetchall()
            audit_rows = conn.execute("SELECT * FROM audit_events ORDER BY occurred_at DESC").fetchall()
            ruleset_rows = conn.execute("SELECT * FROM rulesets").fetchall()

        return {
            "datasets": datasets_rows,
            "versions": versions_rows,
            "findings": findings_rows,
            "reviews": reviews_rows,
            "audit_events": audit_rows,
            "rulesets": ruleset_rows,
        }
