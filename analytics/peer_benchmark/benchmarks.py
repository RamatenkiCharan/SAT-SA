"""
Peer Benchmarking Engine (SRS §7.7, FR-060-064).
Calculates peer-relative robust statistics (median, MAD, robust z-scores) across
multi-dimensional cohorts:
  1. Asset Class (asset_type)
  2. Criticality (AssetCriticality / Severity)
  3. Environment (PRODUCTION, STAGING, DEV, CORP, etc.)
  4. Operational Profile (expected_monitoring_context / sector-scale)

Enforces minimum sample size (N >= 5) for high-confidence comparison with explicit
4-tier fallback hierarchy:
  - DIRECT (N >= 5 on all dimensions, Confidence >= 0.85)
  - RELAXED_COHORT (N >= 5 on primary dimensions, Confidence ~ 0.65)
  - GLOBAL_FALLBACK (N >= 5 on global baseline, Confidence ~ 0.40)
  - INSUFFICIENT_PEER_DATA (N < 5 across all tiers, Confidence <= 0.10, Suppressed)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import numpy as np

from analytics.workflow.workflow_reconstruction import ReconstructedDataset, ReconstructedWorkflow
from backend.models.canonical import (
    CSE,
    Asset,
    AssetCriticality,
    PeerFallbackState,
    PeerGroup,
    Severity,
)


@dataclass
class MetricDistribution:
    median: float
    mad: float
    p25: float
    p75: float
    count: int
    low_confidence: bool = False


@dataclass
class PeerComparison:
    """
    Deterministic result of a peer cohort comparison (FR-060-064).
    Contains full statistical decomposition and fallback provenance.
    """
    peer_group: str
    peer_size: int
    entity_value: float
    peer_median: float
    deviation: float
    confidence: float
    fallback_state: PeerFallbackState
    mad: float = 1.0
    z_score: float = 0.0
    p25: float = 0.0
    p75: float = 0.0
    dimensions: dict[str, str] = field(default_factory=dict)
    dataset_version_id: Optional[UUID] = None
    analysis_run_id: Optional[UUID] = None
    ruleset_version: str = "V1"
    is_suppressed: bool = False
    explanation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "peer_group": self.peer_group,
            "peer_size": self.peer_size,
            "entity_value": round(self.entity_value, 4),
            "peer_median": round(self.peer_median, 4),
            "deviation": round(self.deviation, 4),
            "confidence": round(self.confidence, 4),
            "fallback_state": self.fallback_state.value,
            "mad": round(self.mad, 4),
            "z_score": round(self.z_score, 4),
            "p25": round(self.p25, 4),
            "p75": round(self.p75, 4),
            "dimensions": dict(self.dimensions),
            "dataset_version_id": str(self.dataset_version_id) if self.dataset_version_id else None,
            "analysis_run_id": str(self.analysis_run_id) if self.analysis_run_id else None,
            "ruleset_version": self.ruleset_version,
            "is_suppressed": self.is_suppressed,
            "explanation": self.explanation,
        }


@dataclass
class CSEOperationalMetrics:
    cse_id: UUID
    cse_name: str
    sector: str
    scale: str
    total_alerts: int
    critical_alerts_count: int
    median_critical_closure_duration: float
    p25_critical_closure_duration: float
    median_evidence_count: float
    p25_evidence_count: float
    critical_escalation_ratio: float
    repeat_alert_rate: float
    sla_compliance_rate: float
    operational_profile: str = "STANDARD_OPERATION"


@dataclass
class PeerBenchmarkResult:
    peer_group_id: UUID
    sector: str
    scale: str
    group_size: int
    is_fallback_global: bool
    closure_duration_dist: MetricDistribution
    evidence_count_dist: MetricDistribution
    escalation_ratio_dist: MetricDistribution
    cse_metrics: dict[UUID, CSEOperationalMetrics] = field(default_factory=dict)
    fallback_state: PeerFallbackState = PeerFallbackState.DIRECT
    confidence: float = 0.90
    dimensions: dict[str, str] = field(default_factory=dict)
    dataset_version_id: Optional[UUID] = None
    analysis_run_id: Optional[UUID] = None
    ruleset_version: str = "V1"


@dataclass
class AssetCohortBenchmarkResult:
    cohort_key: str
    asset_class: str
    criticality: str
    environment: str
    operational_profile: str
    cohort_size: int
    closure_duration_dist: MetricDistribution
    evidence_count_dist: MetricDistribution
    member_asset_ids: list[UUID] = field(default_factory=list)
    dataset_version_id: Optional[UUID] = None
    analysis_run_id: Optional[UUID] = None
    ruleset_version: str = "V1"


def compute_median_and_mad(values: list[float], min_size: int = 5) -> MetricDistribution:
    """
    Computes robust median, MAD (Median Absolute Deviation), and percentiles.
    If MAD is near zero (< 1e-4), falls back to sample standard deviation or 1.0.
    """
    if not values:
        return MetricDistribution(median=0.0, mad=1.0, p25=0.0, p75=0.0, count=0, low_confidence=True)

    arr = np.array(values, dtype=float)
    med = float(np.median(arr))
    p25 = float(np.percentile(arr, 25))
    p75 = float(np.percentile(arr, 75))

    abs_deviations = np.abs(arr - med)
    mad = float(np.median(abs_deviations))
    if mad < 1e-4:
        mad = float(np.std(arr)) if len(arr) > 1 and np.std(arr) > 1e-4 else 1.0

    low_conf = len(values) < min_size
    return MetricDistribution(
        median=med,
        mad=mad,
        p25=p25,
        p75=p75,
        count=len(values),
        low_confidence=low_conf,
    )


class PeerBenchmarkEngine:
    """
    Multi-dimensional peer benchmarking engine.
    Constructs statistical cohorts across (asset_class, criticality, environment, operational_profile)
    and (sector, scale, operational_profile), enforcing minimum-N gating (N >= 5) and explicit fallback.
    """
    def __init__(
        self,
        dataset: ReconstructedDataset,
        min_peer_group_size: int = 5,
        ruleset_version: str = "V1",
        analysis_run_id: Optional[UUID] = None,
    ):
        self.dataset = dataset
        self.min_peer_group_size = min_peer_group_size
        self.ruleset_version = ruleset_version
        self.dataset_version_id: UUID = dataset.raw_dataset.dataset_version_id
        self.analysis_run_id: Optional[UUID] = analysis_run_id

        self.cse_metrics: dict[UUID, CSEOperationalMetrics] = {}
        self.peer_benchmarks: dict[str, PeerBenchmarkResult] = {}
        
        # Multi-dimensional asset / workflow cohorts
        self.asset_cohorts: dict[str, AssetCohortBenchmarkResult] = {}
        self.relaxed_asset_cohorts: dict[str, AssetCohortBenchmarkResult] = {}
        
        # Global baseline distributions
        self.global_closure_dist: MetricDistribution = MetricDistribution(0.0, 1.0, 0.0, 0.0, 0, True)
        self.global_evidence_dist: MetricDistribution = MetricDistribution(0.0, 1.0, 0.0, 0.0, 0, True)
        self.global_escalation_dist: MetricDistribution = MetricDistribution(0.0, 1.0, 0.0, 0.0, 0, True)

        self._calculate_all_metrics()

    def _extract_workflow_dimensions(self, w: ReconstructedWorkflow) -> tuple[str, str, str, str]:
        """
        Extracts the 4 canonical peer grouping dimensions:
          1. Asset Class (asset_type)
          2. Criticality
          3. Environment
          4. Operational Profile
        """
        asset = w.asset
        if asset:
            asset_class = (asset.asset_type or "UNKNOWN").upper()
            if hasattr(asset.criticality, "value"):
                crit = str(asset.criticality.value).upper()
            else:
                crit = str(asset.criticality).upper()
            env = (asset.environment or "PRODUCTION").upper()
            op_profile = (asset.expected_monitoring_context or "STANDARD_OPERATION").upper()
        else:
            asset_class = "UNKNOWN"
            crit = w.alert.severity.value.upper() if hasattr(w.alert.severity, "value") else str(w.alert.severity).upper()
            env = "PRODUCTION"
            op_profile = "STANDARD_OPERATION"

        return asset_class, crit, env, op_profile

    def _calculate_all_metrics(self) -> None:
        # 1. Compute per-CSE operational metrics
        for cse in self.dataset.raw_dataset.cse_list:
            wfs = self.dataset.get_workflows_for_cse(cse.cse_id)
            total_alerts = len(wfs)

            crit_wfs = [
                w for w in wfs if w.alert.severity in (Severity.CRITICAL, Severity.HIGH)
            ]
            crit_count = len(crit_wfs)

            # Closure durations for critical/high
            crit_durations = [
                w.closure_duration_seconds
                for w in crit_wfs
                if w.closure_duration_seconds is not None
            ]
            if crit_durations:
                med_dur = float(np.median(crit_durations))
                p25_dur = float(np.percentile(crit_durations, 25))
            else:
                med_dur = 3600.0
                p25_dur = 1800.0

            # Evidence counts
            evidence_counts = [w.evidence_count for w in wfs]
            if evidence_counts:
                med_ev = float(np.median(evidence_counts))
                p25_ev = float(np.percentile(evidence_counts, 25))
            else:
                med_ev = 3.0
                p25_ev = 1.0

            # Critical escalations ratio
            crit_cases = [w for w in crit_wfs if w.case]
            if crit_cases:
                esc_count = sum(1 for w in crit_cases if w.has_escalation)
                esc_ratio = esc_count / len(crit_cases)
            else:
                esc_ratio = 1.0

            # Repeat alert rate
            asset_alert_counts: dict[UUID, int] = {}
            for w in wfs:
                asset_alert_counts[w.alert.asset_id] = asset_alert_counts.get(w.alert.asset_id, 0) + 1
            repeats = sum(1 for cnt in asset_alert_counts.values() if cnt >= 3)
            repeat_rate = repeats / max(len(asset_alert_counts), 1)

            # SLA compliance
            sla_compliant = sum(1 for w in wfs if w.closure is not None)
            sla_compliance = sla_compliant / max(total_alerts, 1)

            op_profile = f"{cse.sector}_{cse.scale}".upper()

            self.cse_metrics[cse.cse_id] = CSEOperationalMetrics(
                cse_id=cse.cse_id,
                cse_name=cse.name,
                sector=cse.sector,
                scale=cse.scale,
                total_alerts=total_alerts,
                critical_alerts_count=crit_count,
                median_critical_closure_duration=med_dur,
                p25_critical_closure_duration=p25_dur,
                median_evidence_count=med_ev,
                p25_evidence_count=p25_ev,
                critical_escalation_ratio=esc_ratio,
                repeat_alert_rate=repeat_rate,
                sla_compliance_rate=sla_compliance,
                operational_profile=op_profile,
            )

        # 2. Build multi-dimensional Asset/Workflow cohorts (4 dimensions)
        raw_asset_groups: dict[str, list[ReconstructedWorkflow]] = {}
        relaxed_asset_groups: dict[str, list[ReconstructedWorkflow]] = {}
        all_workflows = getattr(self.dataset, "workflows", [])

        all_durations = [w.closure_duration_seconds for w in all_workflows if w.closure_duration_seconds is not None]
        all_evidences = [float(w.evidence_count) for w in all_workflows]
        all_escalations = [
            1.0 if w.has_escalation else 0.0
            for w in all_workflows
            if w.alert.severity in (Severity.CRITICAL, Severity.HIGH)
        ]

        self.global_closure_dist = compute_median_and_mad(all_durations, self.min_peer_group_size)
        self.global_evidence_dist = compute_median_and_mad(all_evidences, self.min_peer_group_size)
        self.global_escalation_dist = compute_median_and_mad(all_escalations, self.min_peer_group_size)

        for w in all_workflows:
            ac, crit, env, op = self._extract_workflow_dimensions(w)
            exact_key = f"{ac}:{crit}:{env}:{op}"
            raw_asset_groups.setdefault(exact_key, []).append(w)

            relaxed_key = f"{ac}:{crit}"
            relaxed_asset_groups.setdefault(relaxed_key, []).append(w)

        # Process exact 4D asset cohorts
        for key, w_list in raw_asset_groups.items():
            ac, crit, env, op = key.split(":")
            durs = [w.closure_duration_seconds for w in w_list if w.closure_duration_seconds is not None]
            evs = [float(w.evidence_count) for w in w_list]
            asset_ids = list({w.alert.asset_id for w in w_list})
            self.asset_cohorts[key] = AssetCohortBenchmarkResult(
                cohort_key=key,
                asset_class=ac,
                criticality=crit,
                environment=env,
                operational_profile=op,
                cohort_size=len(asset_ids),
                closure_duration_dist=compute_median_and_mad(durs, self.min_peer_group_size),
                evidence_count_dist=compute_median_and_mad(evs, self.min_peer_group_size),
                member_asset_ids=asset_ids,
                dataset_version_id=self.dataset_version_id,
                analysis_run_id=self.analysis_run_id,
                ruleset_version=self.ruleset_version,
            )

        # Process relaxed asset cohorts (asset_class + criticality)
        for key, w_list in relaxed_asset_groups.items():
            ac, crit = key.split(":")
            durs = [w.closure_duration_seconds for w in w_list if w.closure_duration_seconds is not None]
            evs = [float(w.evidence_count) for w in w_list]
            asset_ids = list({w.alert.asset_id for w in w_list})
            self.relaxed_asset_cohorts[key] = AssetCohortBenchmarkResult(
                cohort_key=key,
                asset_class=ac,
                criticality=crit,
                environment="ANY",
                operational_profile="ANY",
                cohort_size=len(asset_ids),
                closure_duration_dist=compute_median_and_mad(durs, self.min_peer_group_size),
                evidence_count_dist=compute_median_and_mad(evs, self.min_peer_group_size),
                member_asset_ids=asset_ids,
                dataset_version_id=self.dataset_version_id,
                analysis_run_id=self.analysis_run_id,
                ruleset_version=self.ruleset_version,
            )

        # 3. Group by CSE peer definition (Sector + Scale)
        groups: dict[str, list[CSEOperationalMetrics]] = {}
        relaxed_cse_groups: dict[str, list[CSEOperationalMetrics]] = {}
        for metric in self.cse_metrics.values():
            key = f"{metric.sector}_{metric.scale}"
            groups.setdefault(key, []).append(metric)
            relaxed_cse_groups.setdefault(metric.sector, []).append(metric)

        all_metrics = list(self.cse_metrics.values())
        global_cse_durations = [m.median_critical_closure_duration for m in all_metrics]
        global_cse_evidence = [m.median_evidence_count for m in all_metrics]
        global_cse_escalation = [m.critical_escalation_ratio for m in all_metrics]

        global_cse_dur_dist = compute_median_and_mad(global_cse_durations, self.min_peer_group_size)
        global_cse_ev_dist = compute_median_and_mad(global_cse_evidence, self.min_peer_group_size)
        global_cse_esc_dist = compute_median_and_mad(global_cse_escalation, self.min_peer_group_size)

        for cse in self.dataset.raw_dataset.cse_list:
            key = f"{cse.sector}_{cse.scale}"
            peer_members = groups.get(key, [])
            relaxed_members = relaxed_cse_groups.get(cse.sector, [])

            dims = {
                "sector": cse.sector,
                "scale": cse.scale,
                "operational_profile": f"{cse.sector}_{cse.scale}".upper(),
            }

            if len(peer_members) >= self.min_peer_group_size:
                durations = [m.median_critical_closure_duration for m in peer_members]
                evidences = [m.median_evidence_count for m in peer_members]
                escalations = [m.critical_escalation_ratio for m in peer_members]
                conf = min(1.0, 0.85 + 0.15 * min(1.0, (len(peer_members) - 5) / 15.0))

                res = PeerBenchmarkResult(
                    peer_group_id=cse.cse_id,
                    sector=cse.sector,
                    scale=cse.scale,
                    group_size=len(peer_members),
                    is_fallback_global=False,
                    closure_duration_dist=compute_median_and_mad(durations, self.min_peer_group_size),
                    evidence_count_dist=compute_median_and_mad(evidences, self.min_peer_group_size),
                    escalation_ratio_dist=compute_median_and_mad(escalations, self.min_peer_group_size),
                    cse_metrics={m.cse_id: m for m in peer_members},
                    fallback_state=PeerFallbackState.DIRECT,
                    confidence=conf,
                    dimensions=dims,
                    dataset_version_id=self.dataset_version_id,
                    analysis_run_id=self.analysis_run_id,
                    ruleset_version=self.ruleset_version,
                )
            elif len(relaxed_members) >= self.min_peer_group_size:
                durations = [m.median_critical_closure_duration for m in relaxed_members]
                evidences = [m.median_evidence_count for m in relaxed_members]
                escalations = [m.critical_escalation_ratio for m in relaxed_members]
                conf = min(0.75, 0.65 + 0.10 * min(1.0, (len(relaxed_members) - 5) / 15.0))

                res = PeerBenchmarkResult(
                    peer_group_id=cse.cse_id,
                    sector=cse.sector,
                    scale="ANY",
                    group_size=len(relaxed_members),
                    is_fallback_global=False,
                    closure_duration_dist=compute_median_and_mad(durations, self.min_peer_group_size),
                    evidence_count_dist=compute_median_and_mad(evidences, self.min_peer_group_size),
                    escalation_ratio_dist=compute_median_and_mad(escalations, self.min_peer_group_size),
                    cse_metrics={m.cse_id: m for m in relaxed_members},
                    fallback_state=PeerFallbackState.RELAXED_COHORT,
                    confidence=conf,
                    dimensions=dims,
                    dataset_version_id=self.dataset_version_id,
                    analysis_run_id=self.analysis_run_id,
                    ruleset_version=self.ruleset_version,
                )
            elif len(all_metrics) >= self.min_peer_group_size:
                conf = min(0.50, 0.40 + 0.10 * min(1.0, (len(all_metrics) - 5) / 25.0))
                res = PeerBenchmarkResult(
                    peer_group_id=cse.cse_id,
                    sector="GLOBAL",
                    scale="GLOBAL",
                    group_size=len(all_metrics),
                    is_fallback_global=True,
                    closure_duration_dist=global_cse_dur_dist,
                    evidence_count_dist=global_cse_ev_dist,
                    escalation_ratio_dist=global_cse_esc_dist,
                    cse_metrics={m.cse_id: m for m in all_metrics},
                    fallback_state=PeerFallbackState.GLOBAL_FALLBACK,
                    confidence=conf,
                    dimensions=dims,
                    dataset_version_id=self.dataset_version_id,
                    analysis_run_id=self.analysis_run_id,
                    ruleset_version=self.ruleset_version,
                )
            else:
                # Insufficient peer data across entire dataset
                conf = max(0.0, 0.10 * (len(all_metrics) / 5.0))
                res = PeerBenchmarkResult(
                    peer_group_id=cse.cse_id,
                    sector="INSUFFICIENT",
                    scale="INSUFFICIENT",
                    group_size=len(all_metrics),
                    is_fallback_global=True,
                    closure_duration_dist=global_cse_dur_dist,
                    evidence_count_dist=global_cse_ev_dist,
                    escalation_ratio_dist=global_cse_esc_dist,
                    cse_metrics={m.cse_id: m for m in all_metrics},
                    fallback_state=PeerFallbackState.INSUFFICIENT_PEER_DATA,
                    confidence=conf,
                    dimensions=dims,
                    dataset_version_id=self.dataset_version_id,
                    analysis_run_id=self.analysis_run_id,
                    ruleset_version=self.ruleset_version,
                )
            self.peer_benchmarks[str(cse.cse_id)] = res

    def get_benchmark_for_cse(self, cse_id: UUID) -> Optional[PeerBenchmarkResult]:
        return self.peer_benchmarks.get(str(cse_id))

    def compare_metric(
        self,
        entity_value: float,
        asset_class: Optional[str] = None,
        criticality: Optional[str] = None,
        environment: Optional[str] = None,
        operational_profile: Optional[str] = None,
        sector: Optional[str] = None,
        scale: Optional[str] = None,
        metric_name: str = "closure_duration",
    ) -> PeerComparison:
        """
        Compares an entity or asset metric against the 4-tier peer hierarchy.
        Returns a complete PeerComparison object with deviation, robust z-score,
        confidence, and fallback state.
        """
        dims: dict[str, str] = {}
        
        # Check if asset-level comparison requested
        if asset_class or criticality or environment or operational_profile:
            ac = (asset_class or "UNKNOWN").upper()
            crit = (criticality or "MEDIUM").upper()
            env = (environment or "PRODUCTION").upper()
            op = (operational_profile or "STANDARD_OPERATION").upper()

            dims = {
                "asset_class": ac,
                "criticality": crit,
                "environment": env,
                "operational_profile": op,
            }

            exact_key = f"{ac}:{crit}:{env}:{op}"
            relaxed_key = f"{ac}:{crit}"

            # Tier 1: Direct 4D Cohort
            exact_cohort = self.asset_cohorts.get(exact_key)
            if exact_cohort and exact_cohort.cohort_size >= self.min_peer_group_size:
                dist = (
                    exact_cohort.closure_duration_dist
                    if metric_name == "closure_duration"
                    else exact_cohort.evidence_count_dist
                )
                peer_group = exact_key
                peer_size = exact_cohort.cohort_size
                fallback_state = PeerFallbackState.DIRECT
                conf = min(1.0, 0.85 + 0.15 * min(1.0, (peer_size - 5) / 15.0))
                is_suppressed = False

            # Tier 2: Relaxed Cohort (asset_class + criticality)
            elif (
                relaxed_key in self.relaxed_asset_cohorts
                and self.relaxed_asset_cohorts[relaxed_key].cohort_size >= self.min_peer_group_size
            ):
                rel_cohort = self.relaxed_asset_cohorts[relaxed_key]
                dist = (
                    rel_cohort.closure_duration_dist
                    if metric_name == "closure_duration"
                    else rel_cohort.evidence_count_dist
                )
                peer_group = relaxed_key
                peer_size = rel_cohort.cohort_size
                fallback_state = PeerFallbackState.RELAXED_COHORT
                conf = min(0.75, 0.65 + 0.10 * min(1.0, (peer_size - 5) / 15.0))
                is_suppressed = False

            # Tier 3: Global Asset/Workflow Baseline
            elif self.global_closure_dist.count >= self.min_peer_group_size:
                dist = (
                    self.global_closure_dist
                    if metric_name == "closure_duration"
                    else (
                        self.global_evidence_dist
                        if metric_name == "evidence_count"
                        else self.global_escalation_dist
                    )
                )
                peer_group = "GLOBAL_ASSET_POPULATION"
                peer_size = dist.count
                fallback_state = PeerFallbackState.GLOBAL_FALLBACK
                conf = min(0.50, 0.40 + 0.10 * min(1.0, (peer_size - 5) / 25.0))
                is_suppressed = False

            # Tier 4: Insufficient Peer Data
            else:
                dist = (
                    self.global_closure_dist
                    if metric_name == "closure_duration"
                    else self.global_evidence_dist
                )
                peer_group = "INSUFFICIENT_PEER_DATA"
                peer_size = dist.count
                fallback_state = PeerFallbackState.INSUFFICIENT_PEER_DATA
                conf = max(0.0, 0.10 * (peer_size / 5.0))
                is_suppressed = True

        else:
            # CSE-level comparison
            s = sector or "UNKNOWN"
            sc = scale or "UNKNOWN"
            dims = {"sector": s, "scale": sc}

            # Find matching CSE benchmark or cohort
            matching_bm = None
            for bm in self.peer_benchmarks.values():
                if bm.sector == s and bm.scale == sc:
                    matching_bm = bm
                    break

            if matching_bm and matching_bm.fallback_state == PeerFallbackState.DIRECT:
                dist = (
                    matching_bm.closure_duration_dist
                    if metric_name == "closure_duration"
                    else (
                        matching_bm.evidence_count_dist
                        if metric_name == "evidence_count"
                        else matching_bm.escalation_ratio_dist
                    )
                )
                peer_group = f"{s}_{sc}"
                peer_size = matching_bm.group_size
                fallback_state = PeerFallbackState.DIRECT
                conf = matching_bm.confidence
                is_suppressed = False
            elif matching_bm and matching_bm.fallback_state == PeerFallbackState.RELAXED_COHORT:
                dist = (
                    matching_bm.closure_duration_dist
                    if metric_name == "closure_duration"
                    else (
                        matching_bm.evidence_count_dist
                        if metric_name == "evidence_count"
                        else matching_bm.escalation_ratio_dist
                    )
                )
                peer_group = f"{s}_ANY"
                peer_size = matching_bm.group_size
                fallback_state = PeerFallbackState.RELAXED_COHORT
                conf = matching_bm.confidence
                is_suppressed = False
            elif matching_bm and matching_bm.fallback_state == PeerFallbackState.GLOBAL_FALLBACK:
                dist = (
                    matching_bm.closure_duration_dist
                    if metric_name == "closure_duration"
                    else (
                        matching_bm.evidence_count_dist
                        if metric_name == "evidence_count"
                        else matching_bm.escalation_ratio_dist
                    )
                )
                peer_group = "GLOBAL_CSE_POPULATION"
                peer_size = matching_bm.group_size
                fallback_state = PeerFallbackState.GLOBAL_FALLBACK
                conf = matching_bm.confidence
                is_suppressed = False
            else:
                dist = self.global_closure_dist
                peer_group = "INSUFFICIENT_PEER_DATA"
                peer_size = dist.count
                fallback_state = PeerFallbackState.INSUFFICIENT_PEER_DATA
                conf = max(0.0, 0.10 * (peer_size / 5.0))
                is_suppressed = True

        # Statistical calculations
        deviation = entity_value - dist.median
        if abs(deviation) < 1e-6:
            deviation = 0.0
            z_score = 0.0
        else:
            mad_val = max(dist.mad, 1e-4)
            z_score = float(deviation / mad_val)

        if is_suppressed or fallback_state == PeerFallbackState.INSUFFICIENT_PEER_DATA:
            explanation = (
                f"Insufficient peer group data (N={peer_size} < {self.min_peer_group_size}); "
                f"outlier comparisons suppressed to prevent false positive findings."
            )
        else:
            explanation = (
                f"Compared against peer cohort '{peer_group}' (N={peer_size}, state={fallback_state.value}). "
                f"Median={dist.median:.1f}, MAD={dist.mad:.1f}, Deviation={deviation:+.1f}, "
                f"Robust Z={z_score:+.2f}, Confidence={conf:.2f}."
            )

        return PeerComparison(
            peer_group=peer_group,
            peer_size=peer_size,
            entity_value=entity_value,
            peer_median=dist.median,
            deviation=deviation,
            confidence=conf,
            fallback_state=fallback_state,
            mad=dist.mad,
            z_score=z_score,
            p25=dist.p25,
            p75=dist.p75,
            dimensions=dims,
            dataset_version_id=self.dataset_version_id,
            analysis_run_id=self.analysis_run_id,
            ruleset_version=self.ruleset_version,
            is_suppressed=is_suppressed,
            explanation=explanation,
        )

    def compute_peer_deviation_zscore(self, cse_id: UUID, metric_value: float, metric_name: str) -> float:
        bm = self.get_benchmark_for_cse(cse_id)
        if not bm:
            return 0.0

        if metric_name == "closure_duration":
            dist = bm.closure_duration_dist
        elif metric_name == "evidence_count":
            dist = bm.evidence_count_dist
        else:
            dist = bm.escalation_ratio_dist

        if dist.mad < 1e-4:
            return 0.0

        if abs(metric_value - dist.median) < 1e-6:
            return 0.0

        # Robust z-score
        z = (metric_value - dist.median) / dist.mad
        return float(z)

    def build_peer_groups(self) -> list[PeerGroup]:
        """
        Builds versioned PeerGroup domain models suitable for persistence (FR-060, FR-064).
        """
        now = datetime.now(timezone.utc)
        groups: list[PeerGroup] = []

        # 1. CSE Sector-Scale peer groups
        for key, bm in self.peer_benchmarks.items():
            cse_ids = list(bm.cse_metrics.keys())
            pg = PeerGroup(
                peer_group_id=uuid4(),
                definition=f"CSE Cohort {bm.sector}:{bm.scale} (state={bm.fallback_state.value})",
                member_cse_ids=cse_ids,
                dataset_version_id=self.dataset_version_id,
                analysis_run_id=self.analysis_run_id,
                ruleset_version=self.ruleset_version,
                dimensions=bm.dimensions,
                created_at=now,
            )
            groups.append(pg)

        # 2. Asset 4D cohorts
        for key, cohort in self.asset_cohorts.items():
            pg = PeerGroup(
                peer_group_id=uuid4(),
                definition=f"Asset Cohort {key}",
                member_cse_ids=[],
                dataset_version_id=self.dataset_version_id,
                analysis_run_id=self.analysis_run_id,
                ruleset_version=self.ruleset_version,
                dimensions={
                    "asset_class": cohort.asset_class,
                    "criticality": cohort.criticality,
                    "environment": cohort.environment,
                    "operational_profile": cohort.operational_profile,
                },
                created_at=now,
            )
            groups.append(pg)

        return groups
