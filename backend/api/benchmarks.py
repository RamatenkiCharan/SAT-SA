"""
Peer Benchmarks API Endpoints.
Provides peer cohort distributions, robust MAD baselines, and cross-CSE operational metric comparisons.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from backend.repositories.in_memory_repo import SATRepository, get_repository

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


@router.get("")
def get_benchmarks(
    dataset_version_id: Optional[UUID] = None,
    repo: SATRepository = Depends(get_repository),
):
    ver_id = dataset_version_id or repo.active_dataset_version_id
    if not ver_id or ver_id not in repo.benchmark_engines:
        return {"cohorts": [], "entities": []}

    engine = repo.benchmark_engines[ver_id]
    
    entities = []
    for m in engine.cse_metrics.values():
        entities.append(
            {
                "cse_id": str(m.cse_id),
                "cse_name": m.cse_name,
                "sector": m.sector,
                "scale": m.scale,
                "total_alerts": m.total_alerts,
                "critical_alerts_count": m.critical_alerts_count,
                "median_critical_closure_minutes": round(m.median_critical_closure_duration / 60, 1),
                "median_evidence_count": round(m.median_evidence_count, 1),
                "critical_escalation_ratio": round(m.critical_escalation_ratio * 100, 1),
                "repeat_alert_rate": round(m.repeat_alert_rate * 100, 1),
                "self_reported_sla_compliance": round(m.sla_compliance_rate * 100, 1),
            }
        )

    cohorts = []
    for key, bm in engine.peer_benchmarks.items():
        cohorts.append(
            {
                "peer_id": key,
                "sector": bm.sector,
                "scale": bm.scale,
                "group_size": bm.group_size,
                "is_fallback_global": bm.is_fallback_global,
                "closure_duration": {
                    "median_minutes": round(bm.closure_duration_dist.median / 60, 1),
                    "mad_minutes": round(bm.closure_duration_dist.mad / 60, 1),
                    "p25_minutes": round(bm.closure_duration_dist.p25 / 60, 1),
                    "p75_minutes": round(bm.closure_duration_dist.p75 / 60, 1),
                },
                "evidence_count": {
                    "median": round(bm.evidence_count_dist.median, 1),
                    "mad": round(bm.evidence_count_dist.mad, 1),
                    "p25": round(bm.evidence_count_dist.p25, 1),
                    "p75": round(bm.evidence_count_dist.p75, 1),
                },
                "escalation_ratio": {
                    "median_percent": round(bm.escalation_ratio_dist.median * 100, 1),
                    "mad_percent": round(bm.escalation_ratio_dist.mad * 100, 1),
                },
            }
        )

    return {
        "dataset_version_id": str(ver_id),
        "entities": entities,
        "cohorts": cohorts,
    }


@router.get("/cse/{cse_id}")
def get_cse_benchmark_detail(
    cse_id: UUID,
    dataset_version_id: Optional[UUID] = None,
    repo: SATRepository = Depends(get_repository),
):
    ver_id = dataset_version_id or repo.active_dataset_version_id
    if not ver_id or ver_id not in repo.benchmark_engines:
        raise HTTPException(status_code=404, detail="Benchmark data not available.")

    engine = repo.benchmark_engines[ver_id]
    metric = engine.cse_metrics.get(cse_id)
    bm = engine.get_benchmark_for_cse(cse_id)

    if not metric or not bm:
        raise HTTPException(status_code=404, detail="CSE benchmark metrics not found.")

    dur_z = engine.compute_peer_deviation_zscore(cse_id, metric.median_critical_closure_duration, "closure_duration")
    ev_z = engine.compute_peer_deviation_zscore(cse_id, metric.median_evidence_count, "evidence_count")

    return {
        "cse_id": str(cse_id),
        "cse_name": metric.cse_name,
        "sector": metric.sector,
        "metrics": {
            "total_alerts": metric.total_alerts,
            "median_closure_minutes": round(metric.median_critical_closure_duration / 60, 1),
            "median_evidence_count": round(metric.median_evidence_count, 1),
            "critical_escalation_ratio": round(metric.critical_escalation_ratio * 100, 1),
            "self_reported_sla": round(metric.sla_compliance_rate * 100, 1),
        },
        "peer_cohort": {
            "sector": bm.sector,
            "scale": bm.scale,
            "size": bm.group_size,
            "peer_median_closure_minutes": round(bm.closure_duration_dist.median / 60, 1),
            "peer_mad_closure_minutes": round(bm.closure_duration_dist.mad / 60, 1),
            "peer_median_evidence": round(bm.evidence_count_dist.median, 1),
        },
        "robust_deviations": {
            "closure_duration_zscore": round(dur_z, 2),
            "evidence_count_zscore": round(ev_z, 2),
        },
    }
