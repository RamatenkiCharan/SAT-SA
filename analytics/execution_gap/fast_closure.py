"""
Fast Closure Execution-Gap Detector (FR-030).
Flags critical and high severity alerts that were closed significantly faster than the peer baseline
with substandard investigation evidence attached.

Formula:
  flag if severity IN {CRITICAL, HIGH}
      AND closure_duration < peer_median(closure_duration) - 2.5 * peer_MAD(closure_duration)
      AND evidence_count(investigation) < peer_p25(evidence_count)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.workflow.workflow_reconstruction import ReconstructedDataset, ReconstructedWorkflow
from backend.models.canonical import EvidenceRef, PeerFallbackState, Severity
from backend.models.ruleset import FastClosureConfig


@dataclass
class FastClosureSignal:
    cse_id: UUID
    workflow: ReconstructedWorkflow
    closure_duration_seconds: float
    evidence_count: int
    peer_median_duration: float
    peer_mad_duration: float
    threshold_duration: float
    peer_p25_evidence: float
    z_score: float
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
    peer_group: str = ""
    peer_size: int = 0
    fallback_state: PeerFallbackState = PeerFallbackState.DIRECT
    peer_confidence: float = 1.0


class FastClosureDetector:
    def __init__(
        self,
        mad_multiplier: float = 2.5,
        investigation_evidence_percentile: int = 25,
        config: FastClosureConfig | None = None,
        min_peer_group_size: int = 5,
    ):
        if config is not None:
            self.mad_multiplier = config.mad_multiplier
            self.investigation_evidence_percentile = config.investigation_evidence_percentile
            self.min_peer_group_size = config.min_peer_group_size
        else:
            self.mad_multiplier = mad_multiplier
            self.investigation_evidence_percentile = investigation_evidence_percentile
            self.min_peer_group_size = min_peer_group_size


    def detect(
        self,
        dataset: ReconstructedDataset,
        benchmark_engine: PeerBenchmarkEngine,
    ) -> list[FastClosureSignal]:
        signals: list[FastClosureSignal] = []

        for cse in dataset.raw_dataset.cse_list:
            bm = benchmark_engine.get_benchmark_for_cse(cse.cse_id)
            if not bm:
                continue

            dist_dur = bm.closure_duration_dist
            dist_ev = bm.evidence_count_dist

            # Threshold for rapid closure: median - (mad_multiplier * MAD)
            threshold_dur = max(0.0, dist_dur.median - (self.mad_multiplier * dist_dur.mad))
            threshold_ev = dist_ev.p25

            wfs = dataset.get_workflows_for_cse(cse.cse_id)
            for w in wfs:
                if w.alert.severity not in (Severity.CRITICAL, Severity.HIGH):
                    continue

                dur = w.closure_duration_seconds
                if dur is None:
                    continue

                ev_count = w.evidence_count

                # Extract asset dimensions if present
                asset = w.asset
                asset_class = (asset.asset_type or "UNKNOWN").upper() if asset else None
                crit = (
                    (asset.criticality.value if hasattr(asset.criticality, "value") else str(asset.criticality)).upper()
                    if asset
                    else w.alert.severity.value
                )
                env = (asset.environment or "PRODUCTION").upper() if asset else None
                op_profile = (asset.expected_monitoring_context or "STANDARD_OPERATION").upper() if asset else None

                # Multi-dimensional peer comparison check
                comparison = benchmark_engine.compare_metric(
                    entity_value=dur,
                    asset_class=asset_class,
                    criticality=crit,
                    environment=env,
                    operational_profile=op_profile,
                    sector=cse.sector,
                    scale=cse.scale,
                    metric_name="closure_duration",
                )

                # If peer data is insufficient, strictly suppress finding
                if comparison.is_suppressed or comparison.fallback_state == PeerFallbackState.INSUFFICIENT_PEER_DATA:
                    continue

                ev_comparison = benchmark_engine.compare_metric(
                    entity_value=float(ev_count),
                    asset_class=asset_class,
                    criticality=crit,
                    environment=env,
                    operational_profile=op_profile,
                    sector=cse.sector,
                    scale=cse.scale,
                    metric_name="evidence_count",
                )

                effective_median = comparison.peer_median
                effective_mad = comparison.mad
                effective_threshold_dur = max(0.0, effective_median - (self.mad_multiplier * effective_mad))
                effective_threshold_ev = max(1.0, ev_comparison.p25 if not ev_comparison.is_suppressed else threshold_ev)

                # Core FR-030 condition
                if dur < effective_threshold_dur and ev_count <= effective_threshold_ev:
                    z_score = abs(dur - effective_median) / max(effective_mad, 1e-4)

                    refs: list[EvidenceRef] = [
                        EvidenceRef(entity_type="alert", entity_id=w.alert.alert_id)
                    ]
                    if w.case:
                        refs.append(EvidenceRef(entity_type="case", entity_id=w.case.case_id))
                    if w.investigation:
                        refs.append(
                            EvidenceRef(
                                entity_type="investigation",
                                entity_id=w.investigation.investigation_id,
                            )
                        )
                    if w.closure:
                        refs.append(
                            EvidenceRef(entity_type="closure", entity_id=w.closure.closure_id)
                        )

                    signals.append(
                        FastClosureSignal(
                            cse_id=cse.cse_id,
                            workflow=w,
                            closure_duration_seconds=dur,
                            evidence_count=ev_count,
                            peer_median_duration=effective_median,
                            peer_mad_duration=effective_mad,
                            threshold_duration=effective_threshold_dur,
                            peer_p25_evidence=effective_threshold_ev,
                            z_score=z_score,
                            evidence_refs=refs,
                            peer_group=comparison.peer_group,
                            peer_size=comparison.peer_size,
                            fallback_state=comparison.fallback_state,
                            peer_confidence=comparison.confidence,
                        )
                    )

        return signals
