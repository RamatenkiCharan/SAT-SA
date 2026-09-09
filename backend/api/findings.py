"""
Findings API Endpoints.
Retrieves prioritized supervisory findings, decomposed metrics, and clickable evidence records.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from analytics.explainability.templates import generate_finding_explanation
from backend.repositories.in_memory_repo import SATRepository, get_repository

router = APIRouter(prefix="/api/findings", tags=["findings"])


@router.get("")
def list_findings(
    sector: Optional[str] = Query(None),
    finding_type: Optional[str] = Query(None),
    cse_id: Optional[UUID] = Query(None),
    min_priority: Optional[float] = Query(None),
    dataset_version_id: Optional[UUID] = Query(None),
    repo: SATRepository = Depends(get_repository),
):
    findings = repo.get_findings(
        dataset_version_id=dataset_version_id,
        sector=sector,
        finding_type=finding_type,
        cse_id=cse_id,
        min_priority=min_priority,
    )

    ver_id = dataset_version_id or repo.active_dataset_version_id
    reconstructed_ds = repo.reconstructed_datasets.get(ver_id) if ver_id else None

    result = []
    for f in findings:
        explanation = generate_finding_explanation(f)
        cse = reconstructed_ds.cse_by_id.get(f.cse_id) if reconstructed_ds else None
        
        result.append(
            {
                "finding_id": str(f.finding_id),
                "cse_id": str(f.cse_id),
                "cse_name": cse.name if cse else "Unknown Entity",
                "sector": cse.sector if cse else "Unknown Sector",
                "finding_type": f.finding_type.value,
                "priority_score": round(f.priority_score, 3),
                "priority_label": explanation["priority_label"],
                "evidentiary_confidence": round(f.evidentiary_confidence * 100, 1),
                "data_quality_score": round(f.data_quality_status.score * 100, 1),
                "title": explanation["title"],
                "headline": explanation["headline"],
                "expected_behavior": f.expected_behavior,
                "observed_behavior": f.observed_behavior,
                "supporting_signals": f.supporting_signals,
                "contradicting_signals": f.contradicting_signals,
                "priority_components": f.priority_components,
                "data_quality_breakdown": explanation["data_quality_breakdown"],
                "recommended_action": explanation["recommended_action"],
                "evidence_record_count": len(f.evidence_refs),
                "review_status": f.review_status.value if f.review_status else None,
                "review_notes": f.review_notes,
                "created_at": f.created_at.isoformat(),
            }
        )

    return {
        "count": len(result),
        "dataset_version_id": str(ver_id) if ver_id else None,
        "findings": result,
    }


@router.get("/{finding_id}")
def get_finding_detail(
    finding_id: UUID,
    repo: SATRepository = Depends(get_repository),
):
    finding = repo.get_finding_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    explanation = generate_finding_explanation(finding)
    evidence_records = repo.get_finding_evidence_records(finding_id)

    return {
        "finding_id": str(finding.finding_id),
        "cse_id": str(finding.cse_id),
        "cse_name": evidence_records.get("cse_name", "Unknown"),
        "sector": evidence_records.get("sector", "Unknown"),
        "finding_type": finding.finding_type.value,
        "priority_score": round(finding.priority_score, 3),
        "priority_label": explanation["priority_label"],
        "evidentiary_confidence": round(finding.evidentiary_confidence * 100, 1),
        "data_quality_score": round(finding.data_quality_status.score * 100, 1),
        "explanation": explanation,
        "evidence_records": evidence_records,
        "review_status": finding.review_status.value if finding.review_status else None,
        "review_notes": finding.review_notes,
        "created_at": finding.created_at.isoformat(),
    }


@router.get("/{finding_id}/evidence")
def get_finding_evidence(
    finding_id: UUID,
    repo: SATRepository = Depends(get_repository),
):
    records = repo.get_finding_evidence_records(finding_id)
    if not records:
        raise HTTPException(status_code=404, detail="Finding evidence not found.")
    return records
