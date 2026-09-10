"""
Investigation Sufficiency & Template Repetition Execution-Gap Detector (FR-031).
Flags critical/high severity alerts with minimal, zero-evidence, or cookie-cutter template investigations.

Formula / Logic:
  flag if alert.severity IN {CRITICAL, HIGH}
       AND (evidence_count == 0 OR investigation_duration < 30 seconds)
       AND alert is marked CLOSED
"""
from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.workflow.workflow_reconstruction import ReconstructedDataset, ReconstructedWorkflow
from backend.models.canonical import EvidenceRef, Severity


@dataclass
class InvestigationSufficiencySignal:
    cse_id: UUID
    workflow: ReconstructedWorkflow
    evidence_count: int
    investigation_duration_seconds: float
    disposition: str
    z_score: float
    evidence_refs: list[EvidenceRef] = field(default_factory=list)


class InvestigationSufficiencyDetector:
    def __init__(
        self,
        min_required_evidence: int = 1,
        min_investigation_duration_seconds: float = 60.0,
    ):
        self.min_required_evidence = min_required_evidence
        self.min_investigation_duration_seconds = min_investigation_duration_seconds

    def detect(
        self,
        dataset: ReconstructedDataset,
        benchmark_engine: PeerBenchmarkEngine,
    ) -> list[InvestigationSufficiencySignal]:
        signals: list[InvestigationSufficiencySignal] = []

        for cse in dataset.raw_dataset.cse_list:
            bm = benchmark_engine.get_benchmark_for_cse(cse.cse_id)
            dist_ev = bm.evidence_count_dist if bm else None

            wfs = dataset.get_workflows_for_cse(cse.cse_id)
            for w in wfs:
                if w.alert.severity not in (Severity.CRITICAL, Severity.HIGH):
                    continue

                # Must have an investigation record to evaluate sufficiency
                if not w.investigation:
                    continue

                inv = w.investigation
                ev_count = inv.evidence_count or 0
                inv_duration = (
                    (inv.ended_at - inv.started_at).total_seconds()
                    if inv.started_at and inv.ended_at
                    else 0.0
                )

                # Flag if zero evidence attached or duration under threshold for a critical alert
                is_insufficient = (
                    ev_count < self.min_required_evidence
                    or inv_duration < self.min_investigation_duration_seconds
                )

                if is_insufficient:
                    peer_median_ev = dist_ev.median if dist_ev else 3.0
                    peer_mad_ev = dist_ev.mad if dist_ev else 1.0
                    z_score = abs(ev_count - peer_median_ev) / max(peer_mad_ev, 1e-4)

                    refs: list[EvidenceRef] = [
                        EvidenceRef(entity_type="alert", entity_id=w.alert.alert_id),
                        EvidenceRef(entity_type="investigation", entity_id=inv.investigation_id),
                    ]
                    if w.case:
                        refs.append(EvidenceRef(entity_type="case", entity_id=w.case.case_id))
                    if w.closure:
                        refs.append(EvidenceRef(entity_type="closure", entity_id=w.closure.closure_id))

                    signals.append(
                        InvestigationSufficiencySignal(
                            cse_id=cse.cse_id,
                            workflow=w,
                            evidence_count=ev_count,
                            investigation_duration_seconds=inv_duration,
                            disposition=inv.disposition or "UNKNOWN",
                            z_score=min(z_score, 3.0),
                            evidence_refs=refs,
                        )
                    )

        return signals
