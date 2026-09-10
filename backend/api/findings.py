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
from backend.security.auth import UserContext, require_analyst

router = APIRouter(prefix="/api/findings", tags=["findings"])


@router.get("")
def list_findings(
    sector: Optional[str] = Query(None),
    finding_type: Optional[str] = Query(None),
    cse_id: Optional[UUID] = Query(None),
    min_priority: Optional[float] = Query(None),
    dataset_version_id: Optional[UUID] = Query(None),
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst),
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
        source_rec_ids = [r.source_record_ref for r in f.evidence_refs if r.source_record_ref]
        ev_refs = [
            {
                "entity_type": r.entity_type,
                "entity_id": str(r.entity_id),
                "source_record_ref": r.source_record_ref,
            }
            for r in f.evidence_refs
        ]
        
        result.append(
            {
                "finding_id": str(f.finding_id),
                "cse_id": str(f.cse_id),
                "cse_name": cse.name if cse else "Unknown Entity",
                "sector": cse.sector if cse else "Unknown Sector",
                "finding_type": f.finding_type.value,
                "detector": f.finding_type.value,
                "detector_version": f.model_version or "1.0.0",
                "reason": f.observed_behavior or explanation.get("headline", ""),
                "source_entity": {
                    "cse_id": str(f.cse_id),
                    "cse_name": cse.name if cse else "Unknown Entity",
                    "sector": cse.sector if cse else "Unknown Sector",
                },
                "source_record_ids": source_rec_ids,
                "evidence_references": ev_refs,
                "calculation_inputs": {
                    "signal_count": len(f.supporting_signals),
                    "priority_components": f.priority_components,
                    "data_quality_score": f.data_quality_status.score if f.data_quality_status else 1.0,
                    "evidence_state": f.evidence_state.value if f.evidence_state else "SUPPORTED",
                    "peer_context": f.peer_context,
                    "temporal_context": f.temporal_context,
                },
                "calculation_result": {
                    "priority_score": round(f.priority_score, 4),
                    "priority_label": explanation["priority_label"],
                    "evidentiary_confidence": round(f.evidentiary_confidence, 4),
                    "components": f.priority_components,
                },
                "dataset_version": {
                    "dataset_version_id": str(f.dataset_version_id),
                },
                "analysis_run": {
                    "analysis_run_id": str(f.analysis_run_id),
                    "ruleset_version": f.ruleset_version,
                },
                "ruleset_version": f.ruleset_version or "V1",
                "priority_score": round(f.priority_score, 3),
                "priority_label": explanation["priority_label"],
                "evidentiary_confidence": round(f.evidentiary_confidence * 100, 1),
                "data_quality_score": round(f.data_quality_status.score * 100, 1),
                "evidence_state": f.evidence_state.value if f.evidence_state else "SUPPORTED",
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
    user: UserContext = Depends(require_analyst),
):
    finding = repo.get_finding_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    explanation = generate_finding_explanation(finding)
    evidence_records = repo.get_finding_evidence_records(finding_id)
    provenance_trace = repo.get_finding_provenance(finding_id)
    provenance_dict = provenance_trace.to_dict() if provenance_trace else explanation.get("provenance", {})

    source_rec_ids = [r.source_record_ref for r in finding.evidence_refs if r.source_record_ref]
    ev_refs = [
        {
            "entity_type": r.entity_type,
            "entity_id": str(r.entity_id),
            "source_record_ref": r.source_record_ref,
        }
        for r in finding.evidence_refs
    ]

    return {
        "finding_id": str(finding.finding_id),
        "cse_id": str(finding.cse_id),
        "cse_name": evidence_records.get("cse_name", "Unknown"),
        "sector": evidence_records.get("sector", "Unknown"),
        "finding_type": finding.finding_type.value,
        "detector": finding.finding_type.value,
        "detector_version": finding.model_version or "1.0.0",
        "reason": finding.observed_behavior or explanation.get("headline", ""),
        "source_entity": {
            "cse_id": str(finding.cse_id),
            "cse_name": evidence_records.get("cse_name", "Unknown"),
            "sector": evidence_records.get("sector", "Unknown"),
        },
        "source_record_ids": source_rec_ids,
        "evidence_references": ev_refs,
        "calculation_inputs": {
            "signal_count": len(finding.supporting_signals),
            "priority_components": finding.priority_components,
            "data_quality_score": finding.data_quality_status.score if finding.data_quality_status else 1.0,
            "evidence_state": finding.evidence_state.value if finding.evidence_state else "SUPPORTED",
            "peer_context": finding.peer_context,
            "temporal_context": finding.temporal_context,
        },
        "calculation_result": {
            "priority_score": round(finding.priority_score, 4),
            "priority_label": explanation["priority_label"],
            "evidentiary_confidence": round(finding.evidentiary_confidence, 4),
            "components": finding.priority_components,
        },
        "dataset_version": {
            "dataset_version_id": str(finding.dataset_version_id),
        },
        "analysis_run": {
            "analysis_run_id": str(finding.analysis_run_id),
            "ruleset_version": finding.ruleset_version,
        },
        "ruleset_version": finding.ruleset_version or "V1",
        "priority_score": round(finding.priority_score, 3),
        "priority_label": explanation["priority_label"],
        "evidentiary_confidence": round(finding.evidentiary_confidence * 100, 1),
        "data_quality_score": round(finding.data_quality_status.score * 100, 1),
        "evidence_state": finding.evidence_state.value if finding.evidence_state else "SUPPORTED",
        "priority_components": finding.priority_components,
        "explanation": explanation,
        "evidence_records": evidence_records,
        "provenance": provenance_dict,
        "review_status": finding.review_status.value if finding.review_status else None,
        "review_notes": finding.review_notes,
        "created_at": finding.created_at.isoformat(),
    }


@router.get("/{finding_id}/provenance")
def get_finding_provenance_endpoint(
    finding_id: UUID,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst),
):
    provenance = repo.get_finding_provenance(finding_id)
    if not provenance:
        raise HTTPException(status_code=404, detail="Finding provenance trace not found.")
    return provenance.to_dict()


@router.get("/{finding_id}/evidence")
def get_finding_evidence(
    finding_id: UUID,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst),
):
    records = repo.get_finding_evidence_records(finding_id)
    if not records:
        raise HTTPException(status_code=404, detail="Finding evidence not found.")
    return records

