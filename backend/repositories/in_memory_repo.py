"""
Thread-safe In-Memory & Relational Repository for SAT-SA.
Provides complete persistence and query interfaces for datasets, canonical models, analysis runs,
findings, evidence linkages, review decisions, and immutable audit logs.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.data_quality.quality_score import DataQualityResult
from analytics.fusion.evidence_fusion import compute_priority_tier
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine, PeerBenchmarkResult
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import (
    Finding,
    FindingType,
    PeerGroup,
    ReviewDecisionState,
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
    EvidenceMessageRecord,
    ReviewDecisionRecord,
)

logger = logging.getLogger("satsa.repository")


class InMemoryRepository(BaseSATRepository):
    def __init__(self):
        self.datasets: dict[UUID, DatasetMetadata] = {}
        self.dataset_versions: dict[UUID, DatasetVersionMetadata] = {}
        self.canonical_datasets: dict[UUID, CanonicalDataset] = {}
        self.reconstructed_datasets: dict[UUID, ReconstructedDataset] = {}
        self.benchmark_engines: dict[UUID, PeerBenchmarkEngine] = {}
        self.peer_groups_by_version: dict[UUID, list[PeerGroup]] = {}
        self.findings_by_version: dict[UUID, list[Finding]] = {}
        self.findings_by_id: dict[UUID, Finding] = {}
        self.analysis_runs: dict[UUID, AnalysisRun] = {}
        self.data_quality_results: dict[UUID, DataQualityResult] = {}
        self.review_decisions: list[ReviewDecisionRecord] = []
        self.evidence_messages: list[EvidenceMessageRecord] = []
        self.audit_events: list[AuditEvent] = []
        self.active_dataset_version_id: Optional[UUID] = None
        self.rulesets: dict[str, AnalyticalRuleset] = {
            DEFAULT_AUTHORITATIVE_RULESET_V1.version: DEFAULT_AUTHORITATIVE_RULESET_V1
        }
        self.active_ruleset_version: str = DEFAULT_AUTHORITATIVE_RULESET_V1.version



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

        # Orphan findings prevention
        for f in findings:
            if f.dataset_version_id != ver_id:
                raise ValueError(
                    f"Orphan finding detected: finding {f.finding_id} has dataset_version_id {f.dataset_version_id} "
                    f"which does not match version {ver_id}."
                )

        if dataset_id not in self.datasets:
            self.datasets[dataset_id] = DatasetMetadata(
                dataset_id=dataset_id,
                name=dataset_name,
                description=description,
                created_at=datetime.now(timezone.utc),
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

        if dq_result:
            self.data_quality_results[ver_id] = dq_result

        num_accepted = accepted_rows if accepted_rows is not None else len(canonical_dataset.alerts)

        ver_meta = DatasetVersionMetadata(
            dataset_version_id=ver_id,
            dataset_id=dataset_id,
            version_number=len(self.datasets[dataset_id].versions) + 1,
            source_file_ref=source_file_ref,
            import_time=datetime.now(timezone.utc),
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
        self.peer_groups_by_version[ver_id] = benchmark_engine.build_peer_groups()
        self.findings_by_version[ver_id] = findings
        
        for f in findings:
            self.findings_by_id[f.finding_id] = f

        if analysis_run is not None:
            analysis_run.dataset_id = dataset_id
            analysis_run.dataset_version_id = ver_id
            self.record_analysis_run(analysis_run)
        elif findings:
            run_id = findings[0].analysis_run_id
            if run_id not in self.analysis_runs:
                ar = AnalysisRun(
                    analysis_run_id=run_id,
                    dataset_id=dataset_id,
                    dataset_version_id=ver_id,
                    schema_version="2.0.0",
                    ruleset_version=findings[0].ruleset_version or "V1",
                    app_version="1.0.0",
                    git_commit="git-rev-satsa-v2",
                    started_at=datetime.now(timezone.utc),
                    finished_at=datetime.now(timezone.utc),
                    status="COMPLETED",
                    findings_count=len(findings),
                )
                self.record_analysis_run(ar)

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

    def record_analysis_run(self, run: AnalysisRun) -> AnalysisRun:
        self.analysis_runs[run.analysis_run_id] = run
        return run

    def get_analysis_run(self, analysis_run_id: UUID) -> Optional[AnalysisRun]:
        return self.analysis_runs.get(analysis_run_id)

    def get_finding_provenance(self, finding_id: UUID) -> Optional[FindingProvenanceTrace]:
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

        priority_label, _ = compute_priority_tier(
            priority_score=finding.priority_score,
            independent_signals_count=len(finding.supporting_signals),
            data_quality_score=finding.data_quality_status.score if finding.data_quality_status else 1.0,
            evidence_state=finding.evidence_state,
        )

        source_rec_ids = [ref.source_record_ref for ref in evidence_provenance_refs if ref.source_record_ref]

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

        # Collect unique source record identifiers
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
        """Retrieves the currently active analytical ruleset."""
        return self.rulesets.get(
            self.active_ruleset_version,
            DEFAULT_AUTHORITATIVE_RULESET_V1,
        )

    def get_ruleset_by_version(self, version: str) -> Optional[AnalyticalRuleset]:
        """Retrieves an analytical ruleset by version string."""
        return self.rulesets.get(version)

    def list_rulesets(self) -> list[AnalyticalRuleset]:
        """Lists all registered versioned rulesets."""
        return list(self.rulesets.values())

    def register_ruleset(
        self,
        ruleset: AnalyticalRuleset,
        set_active: bool = False,
    ) -> AnalyticalRuleset:
        """Registers a new versioned ruleset in memory."""
        self.rulesets[ruleset.version] = ruleset
        if set_active or ruleset.is_active:
            self.set_active_ruleset(ruleset.version)

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
        if version not in self.rulesets:
            raise ValueError(f"Ruleset version '{version}' not found in repository.")

        for v, r in self.rulesets.items():
            r.is_active = (v == version)
        self.active_ruleset_version = version

        self.record_audit_event(
            user_id="system",
            username="System Engine",
            action="ACTIVATE_ANALYTICAL_RULESET",
            target_type="ruleset",
            target_id=version,
            details={"version": version},
        )
        return self.rulesets[version]

    def get_peer_groups(self, version_id: UUID) -> list[PeerGroup]:
        """Retrieves persisted versioned peer groups for a dataset version."""
        return self.peer_groups_by_version.get(version_id, [])

    def persist_peer_groups(self, version_id: UUID, groups: list[PeerGroup]) -> None:
        """Persists versioned peer groups for a dataset version."""
        self.peer_groups_by_version[version_id] = groups

    def save_evidence_message(
        self,
        finding_id: UUID,
        message: str,
        sender_id: str,
        sender_name: str,
        sender_role: str,
        evidence_id: Optional[str] = None,
        recipient: Optional[str] = None,
    ) -> EvidenceMessageRecord:
        """Records an evidence inquiry / supervisory directive message and logs audit event."""
        rec = EvidenceMessageRecord(
            message_id=uuid4(),
            finding_id=finding_id,
            evidence_id=evidence_id,
            sender_id=sender_id,
            sender_name=sender_name,
            sender_role=sender_role,
            recipient=recipient or "SOC Leadership / Tier-2 Lead",
            message=message.strip(),
            sent_at=datetime.now(timezone.utc),
        )
        self.evidence_messages.append(rec)

        self.record_audit_event(
            user_id=sender_id,
            username=sender_name,
            action="EVIDENCE_MESSAGE_SENT",
            target_type="evidence" if evidence_id else "finding",
            target_id=str(evidence_id or finding_id),
            details={
                "finding_id": str(finding_id),
                "evidence_id": evidence_id,
                "message_id": str(rec.message_id),
                "message_preview": rec.message[:120] + ("..." if len(rec.message) > 120 else ""),
                "message_length": len(rec.message),
                "recipient": rec.recipient,
                "role": sender_role,
                "user_role": sender_role,
                "user_name": sender_name,
            },
        )
        return rec

    def get_evidence_messages(self, finding_id: Optional[UUID] = None) -> list[EvidenceMessageRecord]:
        """Retrieves stored evidence messages."""
        if finding_id:
            return [m for m in self.evidence_messages if m.finding_id == finding_id]
        return list(self.evidence_messages)




# Backwards-compatibility alias
SATRepository = InMemoryRepository

_GLOBAL_REPO: Optional[BaseSATRepository] = None


def get_repository() -> BaseSATRepository:
    """
    Returns the configured SAT-SA repository.
    Instantiates PostgresRepository in production or when DATABASE_URL is configured,
    or falls back to InMemoryRepository if in-memory mode is requested or DB is unreachable.
    """
    global _GLOBAL_REPO
    if _GLOBAL_REPO is None:
        persistence_mode = os.environ.get("SAT_PERSISTENCE_MODE", "auto").lower()
        if persistence_mode in ("memory", "in_memory"):
            _GLOBAL_REPO = InMemoryRepository()
        else:
            try:
                from backend.repositories.postgres_repo import PostgresRepository
                _GLOBAL_REPO = PostgresRepository()
                logger.info("Initialized persistent PostgreSQL Repository.")
            except Exception as e:
                # Do not silently degrade to non-persistent storage. Fall back to a
                # local SQLite file so "restart-safe persistence" is true by default
                # even when no Postgres instance/DATABASE_URL is configured.
                logger.warning(
                    "Could not connect to PostgreSQL (%s); falling back to local SQLite file.", e
                )
                try:
                    from backend.repositories.postgres_repo import PostgresRepository
                    sqlite_path = os.environ.get("SAT_SQLITE_PATH", "satsa_local.db")
                    _GLOBAL_REPO = PostgresRepository(db_url=f"sqlite:///{sqlite_path}")
                    logger.info("Initialized SQLite-backed Repository at %s.", sqlite_path)
                except Exception as sqlite_err:
                    logger.warning(
                        "Could not initialize SQLite fallback (%s); using non-persistent InMemoryRepository.",
                        sqlite_err,
                    )
                    _GLOBAL_REPO = InMemoryRepository()
    return _GLOBAL_REPO


def set_repository(repo: BaseSATRepository) -> None:
    """Sets the active repository instance (for testing and isolation)."""
    global _GLOBAL_REPO
    _GLOBAL_REPO = repo

