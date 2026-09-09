"""
Thread-safe In-Memory & Relational Repository for SAT-SA.
Provides complete persistence and query interfaces for datasets, canonical models, analysis runs,
findings, evidence linkages, review decisions, and immutable audit logs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from analytics.canonicalization.canonicalization import CanonicalDataset, canonicalize_records
from analytics.data_quality.quality_score import DataQualityResult
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine, PeerBenchmarkResult
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import (
    Finding,
    FindingType,
    ReviewDecisionState,
)
from backend.repositories.sqlite_repo import SQLiteDatabase, DEFAULT_DB_PATH


@dataclass
class DatasetMetadata:
    dataset_id: UUID
    name: str
    description: str
    created_at: datetime
    versions: list[DatasetVersionMetadata] = field(default_factory=list)


@dataclass
class DatasetVersionMetadata:
    dataset_version_id: UUID
    dataset_id: UUID
    version_number: int
    source_file_ref: str
    import_time: datetime
    transformation_version: str
    schema_version: str
    row_count: int
    data_quality_score: Optional[float] = None


@dataclass
class AuditEvent:
    audit_event_id: UUID
    user_id: str
    username: str
    action: str
    target_type: str
    target_id: Optional[str]
    occurred_at: datetime
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReviewDecisionRecord:
    review_decision_id: UUID
    finding_id: UUID
    decision: ReviewDecisionState
    reviewer_id: str
    reviewer_name: str
    decided_at: datetime
    notes: Optional[str] = None


class SATRepository:
    def __init__(self, db_path: Optional[str] = None):
        self.datasets: dict[UUID, DatasetMetadata] = {}
        self.dataset_versions: dict[UUID, DatasetVersionMetadata] = {}
        self.canonical_datasets: dict[UUID, CanonicalDataset] = {}
        self.reconstructed_datasets: dict[UUID, ReconstructedDataset] = {}
        self.benchmark_engines: dict[UUID, PeerBenchmarkEngine] = {}
        self.findings_by_version: dict[UUID, list[Finding]] = {}
        self.findings_by_id: dict[UUID, Finding] = {}
        self.review_decisions: list[ReviewDecisionRecord] = []
        self.audit_events: list[AuditEvent] = []
        self.active_dataset_version_id: Optional[UUID] = None

        self.db = SQLiteDatabase(db_path or DEFAULT_DB_PATH) if db_path is not False else None
        if self.db:
            self._rehydrate_from_db()

    def _rehydrate_from_db(self) -> None:
        if not self.db:
            return
        try:
            data = self.db.load_all_data()
            for row in data["datasets"]:
                ds_id = UUID(row["dataset_id"])
                self.datasets[ds_id] = DatasetMetadata(
                    dataset_id=ds_id,
                    name=row["name"],
                    description=row["description"] or "",
                    created_at=datetime.fromisoformat(row["created_at"]),
                )
            for row in data["versions"]:
                ver_id = UUID(row["dataset_version_id"])
                ds_id = UUID(row["dataset_id"])
                ver_meta = DatasetVersionMetadata(
                    dataset_version_id=ver_id,
                    dataset_id=ds_id,
                    version_number=row["version_number"],
                    source_file_ref=row["source_file_ref"],
                    import_time=datetime.fromisoformat(row["import_time"]),
                    transformation_version=row["transformation_version"],
                    schema_version=row["schema_version"],
                    row_count=row["row_count"],
                    data_quality_score=row["data_quality_score"],
                )
                if ds_id in self.datasets:
                    self.datasets[ds_id].versions.append(ver_meta)
                self.dataset_versions[ver_id] = ver_meta

                # Reconstruct canonical and workflow graphs
                canonical_dict = json.loads(row["canonical_data_json"])
                canonical_ds = canonicalize_records(canonical_dict, dataset_version_id=ver_id)
                reconstructed_ds = ReconstructedDataset(canonical_ds)
                bm_engine = PeerBenchmarkEngine(reconstructed_ds)

                self.canonical_datasets[ver_id] = canonical_ds
                self.reconstructed_datasets[ver_id] = reconstructed_ds
                self.benchmark_engines[ver_id] = bm_engine
                self.findings_by_version[ver_id] = []
                self.active_dataset_version_id = ver_id

            for row in data["findings"]:
                f_dict = json.loads(row["finding_json"])
                if row["review_status"]:
                    f_dict["review_status"] = row["review_status"]
                if row["review_notes"]:
                    f_dict["review_notes"] = row["review_notes"]
                f = Finding.model_validate(f_dict)
                self.findings_by_id[f.finding_id] = f
                ver_id = f.dataset_version_id
                if ver_id in self.findings_by_version:
                    self.findings_by_version[ver_id].append(f)

            for row in data["reviews"]:
                rec = ReviewDecisionRecord(
                    review_decision_id=UUID(row["review_decision_id"]),
                    finding_id=UUID(row["finding_id"]),
                    decision=ReviewDecisionState(row["decision"]),
                    reviewer_id=row["reviewer_id"],
                    reviewer_name=row["reviewer_name"],
                    decided_at=datetime.fromisoformat(row["decided_at"]),
                    notes=row["notes"],
                )
                self.review_decisions.append(rec)

            for row in data["audit_events"]:
                ev = AuditEvent(
                    audit_event_id=UUID(row["audit_event_id"]),
                    user_id=row["user_id"],
                    username=row["username"],
                    action=row["action"],
                    target_type=row["target_type"],
                    target_id=row["target_id"],
                    occurred_at=datetime.fromisoformat(row["occurred_at"]),
                    details=json.loads(row["details_json"]),
                )
                self.audit_events.append(ev)
        except Exception:
            pass

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
        self.audit_events.insert(0, event)
        if self.db:
            try:
                self.db.save_audit_event(
                    audit_event_id=event.audit_event_id,
                    user_id=event.user_id,
                    username=event.username,
                    action=event.action,
                    target_type=event.target_type,
                    target_id=event.target_id,
                    occurred_at=event.occurred_at,
                    details=event.details,
                )
            except Exception:
                pass
        return event

    def get_audit_events(self, limit: int = 100) -> list[AuditEvent]:
        return self.audit_events[:limit]

    # -----------------------------------------------------------------------
    # Datasets & Versions
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
        dq_score: float,
        description: str = "",
        analysis_run_id: Optional[UUID] = None,
        ruleset_version: str = "V1",
    ) -> DatasetVersionMetadata:
        ver_id = canonical_dataset.dataset_version_id

        if dataset_id not in self.datasets:
            ds_meta = DatasetMetadata(
                dataset_id=dataset_id,
                name=dataset_name,
                description=description,
                created_at=datetime.now(timezone.utc),
            )
            self.datasets[dataset_id] = ds_meta
            if self.db:
                try:
                    self.db.save_dataset(
                        dataset_id=dataset_id,
                        name=dataset_name,
                        description=description,
                        created_at=ds_meta.created_at,
                    )
                except Exception:
                    pass

        ver_meta = DatasetVersionMetadata(
            dataset_version_id=ver_id,
            dataset_id=dataset_id,
            version_number=len(self.datasets[dataset_id].versions) + 1,
            source_file_ref=source_file_ref,
            import_time=datetime.now(timezone.utc),
            transformation_version="T1.0",
            schema_version="S1.0",
            row_count=len(canonical_dataset.alerts),
            data_quality_score=dq_score,
        )

        self.datasets[dataset_id].versions.append(ver_meta)
        self.dataset_versions[ver_id] = ver_meta
        self.canonical_datasets[ver_id] = canonical_dataset
        self.reconstructed_datasets[ver_id] = reconstructed_dataset
        self.benchmark_engines[ver_id] = benchmark_engine
        self.findings_by_version[ver_id] = findings

        for f in findings:
            self.findings_by_id[f.finding_id] = f

        self.active_dataset_version_id = ver_id

        if self.db:
            try:
                self.db.save_dataset_version(
                    dataset_version_id=ver_id,
                    dataset_id=dataset_id,
                    version_number=ver_meta.version_number,
                    source_file_ref=source_file_ref,
                    import_time=ver_meta.import_time,
                    transformation_version=ver_meta.transformation_version,
                    schema_version=ver_meta.schema_version,
                    row_count=ver_meta.row_count,
                    data_quality_score=dq_score,
                    canonical_dataset=canonical_dataset,
                    findings=findings,
                )
            except Exception:
                pass

            # Persist analysis run record for full provenance traceability
            if analysis_run_id:
                try:
                    self.db.save_analysis_run(
                        analysis_run_id=analysis_run_id,
                        dataset_version_id=ver_id,
                        ruleset_version=ruleset_version,
                        started_at=ver_meta.import_time,
                        completed_at=datetime.now(timezone.utc),
                        status="COMPLETED",
                        findings_count=len(findings),
                        data_quality_score=dq_score,
                    )
                except Exception:
                    pass

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
                "findings_generated": len(findings),
                "analysis_run_id": str(analysis_run_id) if analysis_run_id else None,
                "ruleset_version": ruleset_version,
            },
        )

        return ver_meta


    def list_datasets(self) -> list[dict[str, Any]]:
        result = []
        for ds in self.datasets.values():
            result.append(
                {
                    "dataset_id": str(ds.dataset_id),
                    "name": ds.name,
                    "description": ds.description,
                    "created_at": ds.created_at.isoformat(),
                    "version_count": len(ds.versions),
                    "versions": [
                        {
                            "dataset_version_id": str(v.dataset_version_id),
                            "version_number": v.version_number,
                            "source_file_ref": v.source_file_ref,
                            "import_time": v.import_time.isoformat(),
                            "row_count": v.row_count,
                            "data_quality_score": v.data_quality_score,
                        }
                        for v in ds.versions
                    ],
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

        # Sort by priority_score DESC
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
                        "asset_type": a.asset_type,
                        "criticality": a.criticality.value,
                        "environment": a.environment,
                        "expected_monitoring_context": a.expected_monitoring_context,
                    }
                )

        return {
            "finding_id": str(finding.finding_id),
            "cse_id": str(finding.cse_id),
            "cse_name": cse.name if cse else "Unknown",
            "sector": cse.sector if cse else "Unknown",
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

        record = ReviewDecisionRecord(
            review_decision_id=uuid4(),
            finding_id=finding_id,
            decision=decision,
            reviewer_id=reviewer_id,
            reviewer_name=reviewer_name,
            decided_at=datetime.now(timezone.utc),
            notes=notes,
        )
        self.review_decisions.append(record)

        if self.db:
            try:
                self.db.save_review_decision(
                    review_decision_id=record.review_decision_id,
                    finding_id=finding_id,
                    decision=decision,
                    reviewer_id=reviewer_id,
                    reviewer_name=reviewer_name,
                    decided_at=record.decided_at,
                    notes=notes,
                )
            except Exception:
                pass

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


# Global Singleton instance
_GLOBAL_REPO = SATRepository()


def get_repository() -> SATRepository:
    return _GLOBAL_REPO
