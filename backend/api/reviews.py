"""
Reviews API Endpoints.
Handles human examiner / supervisor decision recording and audit tracking.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.models.canonical import ReviewDecisionState
from backend.repositories.in_memory_repo import SATRepository, get_repository
from backend.security.auth import UserContext, require_supervisor

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


class ReviewSubmissionRequest(BaseModel):
    finding_id: UUID
    decision: ReviewDecisionState
    notes: Optional[str] = None


@router.post("")
def submit_review_decision(
    req: ReviewSubmissionRequest,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_supervisor),
):
    finding = repo.get_finding_by_id(req.finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found.")

    decision_record = repo.record_review_decision(
        finding_id=req.finding_id,
        decision=req.decision,
        reviewer_id=user.user_id,
        reviewer_name=user.username,
        notes=req.notes,
    )

    return {
        "status": "success",
        "review_decision_id": str(decision_record.review_decision_id),
        "finding_id": str(req.finding_id),
        "decision": decision_record.decision.value,
        "reviewer_name": decision_record.reviewer_name,
        "decided_at": decision_record.decided_at.isoformat(),
        "notes": decision_record.notes,
    }


@router.get("")
def list_review_decisions(repo: SATRepository = Depends(get_repository)):
    return [
        {
            "review_decision_id": str(r.review_decision_id),
            "finding_id": str(r.finding_id),
            "decision": r.decision.value,
            "reviewer_id": r.reviewer_id,
            "reviewer_name": r.reviewer_name,
            "decided_at": r.decided_at.isoformat(),
            "notes": r.notes,
        }
        for r in reversed(repo.review_decisions)
    ]
