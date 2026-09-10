"""
Peer Benchmarks API Endpoints.
Provides multi-dimensional peer cohort distributions, robust MAD baselines,
cross-CSE operational metric comparisons, and deterministic minimum-N aware comparison results.
"""
from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from backend.repositories.in_memory_repo import SATRepository, get_repository
from backend.security.auth import UserContext, require_analyst

router = APIRouter(prefix="/api/benchmarks", tags=["benchmarks"])


class PeerCompareRequest(BaseModel):
    entity_value: float = Field(..., description="Observed numeric metric value for comparison.")
    metric_name: str = Field("closure_duration", description="Metric name: closure_duration | evidence_count | escalation_ratio.")
    asset_class: Optional[str] = Field(None, description="Asset class/type e.g. SERVER, DATABASE, WORKSTATION.")
    criticality: Optional[str] = Field(None, description="Criticality: CRITICAL | HIGH | MEDIUM | LOW.")
    environment: Optional[str] = Field(None, description="Environment: PRODUCTION | STAGING | DEVELOPMENT | CORP.")
    operational_profile: Optional[str] = Field(None, description="Operational profile or expected context.")
    sector: Optional[str] = Field(None, description="Entity sector.")
    scale: Optional[str] = Field(None, description="Entity scale.")
    dataset_version_id: Optional[UUID] = None


@router.get("")
def get_benchmarks(
    dataset_version_id: Optional[UUID] = None,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst),
):
    ver_id = dataset_version_id or repo.active_dataset_version_id
    if not ver_id or ver_id not in repo.benchmark_engines:
        return {"cohorts": [], "entities": [], "asset_cohorts": []}

    engine = repo.benchmark_engines[ver_id]

    entities = []
    for m in engine.cse_metrics.values():
        entities.append(
            {
                "cse_id": str(m.cse_id),
                "cse_name": m.cse_name,
                "sector": m.sector,
                "scale": m.scale,
                "operational_profile": m.operational_profile,
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
                "fallback_state": bm.fallback_state.value,
                "confidence": round(bm.confidence, 4),
                "dimensions": bm.dimensions,
                "ruleset_version": bm.ruleset_version,
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

    asset_cohorts = []
    for key, ac in engine.asset_cohorts.items():
        asset_cohorts.append(
            {
                "cohort_key": ac.cohort_key,
                "asset_class": ac.asset_class,
                "criticality": ac.criticality,
                "environment": ac.environment,
                "operational_profile": ac.operational_profile,
                "cohort_size": ac.cohort_size,
                "closure_duration": {
                    "median_minutes": round(ac.closure_duration_dist.median / 60, 1),
                    "mad_minutes": round(ac.closure_duration_dist.mad / 60, 1),
                    "p25_minutes": round(ac.closure_duration_dist.p25 / 60, 1),
                    "p75_minutes": round(ac.closure_duration_dist.p75 / 60, 1),
                },
                "evidence_count": {
                    "median": round(ac.evidence_count_dist.median, 1),
                    "mad": round(ac.evidence_count_dist.mad, 1),
                    "p25": round(ac.evidence_count_dist.p25, 1),
                    "p75": round(ac.evidence_count_dist.p75, 1),
                },
            }
        )

    return {
        "dataset_version_id": str(ver_id),
        "entities": entities,
        "cohorts": cohorts,
        "asset_cohorts": asset_cohorts,
    }


@router.get("/cse/{cse_id}")
def get_cse_benchmark_detail(
    cse_id: UUID,
    dataset_version_id: Optional[UUID] = None,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst),
):
    ver_id = dataset_version_id or repo.active_dataset_version_id
    if not ver_id or ver_id not in repo.benchmark_engines:
        raise HTTPException(status_code=404, detail="Benchmark data not available.")

    engine = repo.benchmark_engines[ver_id]
    metric = engine.cse_metrics.get(cse_id)
    bm = engine.get_benchmark_for_cse(cse_id)

    if not metric or not bm:
        raise HTTPException(status_code=404, detail="CSE benchmark metrics not found.")

    dur_comp = engine.compare_metric(
        entity_value=metric.median_critical_closure_duration,
        sector=metric.sector,
        scale=metric.scale,
        operational_profile=metric.operational_profile,
        metric_name="closure_duration",
    )
    ev_comp = engine.compare_metric(
        entity_value=metric.median_evidence_count,
        sector=metric.sector,
        scale=metric.scale,
        operational_profile=metric.operational_profile,
        metric_name="evidence_count",
    )

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
            "operational_profile": metric.operational_profile,
        },
        "peer_cohort": {
            "sector": bm.sector,
            "scale": bm.scale,
            "size": bm.group_size,
            "fallback_state": bm.fallback_state.value,
            "confidence": round(bm.confidence, 4),
            "peer_median_closure_minutes": round(bm.closure_duration_dist.median / 60, 1),
            "peer_mad_closure_minutes": round(bm.closure_duration_dist.mad / 60, 1),
            "peer_median_evidence": round(bm.evidence_count_dist.median, 1),
        },
        "robust_deviations": {
            "closure_duration": dur_comp.to_dict(),
            "evidence_count": ev_comp.to_dict(),
            "closure_duration_zscore": round(dur_comp.z_score, 2),
            "evidence_count_zscore": round(ev_comp.z_score, 2),
        },
    }


@router.post("/compare")
def compare_peer_metric(
    req: PeerCompareRequest,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst),
):
    ver_id = req.dataset_version_id or repo.active_dataset_version_id
    if not ver_id or ver_id not in repo.benchmark_engines:
        raise HTTPException(status_code=404, detail="Benchmark engine not available for version.")

    engine = repo.benchmark_engines[ver_id]
    comp = engine.compare_metric(
        entity_value=req.entity_value,
        asset_class=req.asset_class,
        criticality=req.criticality,
        environment=req.environment,
        operational_profile=req.operational_profile,
        sector=req.sector,
        scale=req.scale,
        metric_name=req.metric_name,
    )
    return comp.to_dict()
