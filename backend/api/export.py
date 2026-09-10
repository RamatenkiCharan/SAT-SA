"""
Export API Endpoints.
Generates comprehensive supervisory assessment reports in structured JSON or printable format.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from analytics.explainability.templates import generate_finding_explanation
from backend.repositories.in_memory_repo import SATRepository, get_repository
from backend.security.auth import UserContext, require_supervisor

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/report")
def export_supervisory_report(
    dataset_version_id: Optional[UUID] = None,
    repo: SATRepository = Depends(get_repository),
    current_user: UserContext = Depends(require_supervisor),
):
    ver_id = dataset_version_id or repo.active_dataset_version_id
    if not ver_id:
        raise HTTPException(status_code=400, detail="No active dataset version.")

    findings = repo.get_findings(dataset_version_id=ver_id)
    canonical_ds = repo.canonical_datasets.get(ver_id)
    reconstructed_ds = repo.reconstructed_datasets.get(ver_id)

    if not canonical_ds or not reconstructed_ds:
        raise HTTPException(status_code=404, detail="Dataset version records not found.")

    findings_summary = []
    for f in findings:
        exp = generate_finding_explanation(f)
        cse = reconstructed_ds.cse_by_id.get(f.cse_id)
        findings_summary.append(
            {
                "finding_id": str(f.finding_id),
                "cse_name": cse.name if cse else "Unknown",
                "sector": cse.sector if cse else "Unknown",
                "finding_type": f.finding_type.value,
                "priority_score": round(f.priority_score, 3),
                "priority_label": exp["priority_label"],
                "headline": exp["headline"],
                "recommended_action": exp["recommended_action"],
                "supporting_signals": f.supporting_signals,
                "contradicting_signals": f.contradicting_signals,
                "review_status": f.review_status.value if f.review_status else "PENDING_REVIEW",
                "review_notes": f.review_notes,
            }
        )

    return {
        "report_title": "SAT-SA Supervisory SOC Operational Assessment Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_version_id": str(ver_id),
        "total_critical_sector_entities": len(canonical_ds.cse_list),
        "total_alerts_analyzed": len(canonical_ds.alerts),
        "total_findings": len(findings),
        "high_priority_findings": sum(1 for f in findings if f.priority_score >= 0.75),
        "findings": findings_summary,
    }
