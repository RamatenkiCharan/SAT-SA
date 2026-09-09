"""
Peer Benchmarking Engine.
Calculates peer-relative robust statistics (median, MAD, robust z-scores) for CSE operational metrics.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

import numpy as np

from analytics.workflow.workflow_reconstruction import ReconstructedDataset, ReconstructedWorkflow
from backend.models.canonical import CSE, PeerGroup, Severity


@dataclass
class MetricDistribution:
    median: float
    mad: float
    p25: float
    p75: float
    count: int
    low_confidence: bool = False


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


def compute_median_and_mad(values: list[float], min_size: int = 5) -> MetricDistribution:
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
    def __init__(self, dataset: ReconstructedDataset, min_peer_group_size: int = 5):
        self.dataset = dataset
        self.min_peer_group_size = min_peer_group_size
        self.cse_metrics: dict[UUID, CSEOperationalMetrics] = {}
        self.peer_benchmarks: dict[str, PeerBenchmarkResult] = {}
        self._calculate_all_metrics()

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

            # High-level self-reported / superficial SLA compliance (e.g. closed within KPI SLA)
            sla_compliant = sum(1 for w in wfs if w.closure is not None)
            sla_compliance = sla_compliant / max(total_alerts, 1)

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
            )

        # 2. Group by peer definition (Sector + Scale)
        groups: dict[str, list[CSEOperationalMetrics]] = {}
        for metric in self.cse_metrics.values():
            key = f"{metric.sector}_{metric.scale}"
            groups.setdefault(key, []).append(metric)

        # All CSE metrics across global population
        all_metrics = list(self.cse_metrics.values())
        global_durations = [m.median_critical_closure_duration for m in all_metrics]
        global_evidence = [m.median_evidence_count for m in all_metrics]
        global_escalation = [m.critical_escalation_ratio for m in all_metrics]

        global_dur_dist = compute_median_and_mad(global_durations, self.min_peer_group_size)
        global_ev_dist = compute_median_and_mad(global_evidence, self.min_peer_group_size)
        global_esc_dist = compute_median_and_mad(global_escalation, self.min_peer_group_size)

        for cse in self.dataset.raw_dataset.cse_list:
            key = f"{cse.sector}_{cse.scale}"
            peer_members = groups.get(key, [])
            
            if len(peer_members) >= self.min_peer_group_size:
                durations = [m.median_critical_closure_duration for m in peer_members]
                evidences = [m.median_evidence_count for m in peer_members]
                escalations = [m.critical_escalation_ratio for m in peer_members]
                
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
                )
            else:
                # Fallback to global
                res = PeerBenchmarkResult(
                    peer_group_id=cse.cse_id,
                    sector=cse.sector,
                    scale=cse.scale,
                    group_size=len(all_metrics),
                    is_fallback_global=True,
                    closure_duration_dist=global_dur_dist,
                    evidence_count_dist=global_ev_dist,
                    escalation_ratio_dist=global_esc_dist,
                    cse_metrics={m.cse_id: m for m in all_metrics},
                )
            self.peer_benchmarks[str(cse.cse_id)] = res

    def get_benchmark_for_cse(self, cse_id: UUID) -> Optional[PeerBenchmarkResult]:
        return self.peer_benchmarks.get(str(cse_id))

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
        
        # Robust z-score
        z = (metric_value - dist.median) / dist.mad
        return float(z)
