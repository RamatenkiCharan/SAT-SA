"""
Review-Budget Optimizer API (Innovation Phase 4).
Provides endpoints for supervisory review sample selection.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from analytics.review_budget.optimizer import ReviewBudgetOptimizer
from backend.repositories.in_memory_repo import SATRepository, get_repository
from backend.security.auth import UserContext, require_supervisor

router = APIRouter(prefix="/api/review-budget", tags=["review-budget"])


class ReviewBudgetRequest(BaseModel):
    budget: int = Field(10, ge=0, le=500, description="Maximum number of cases for supervisory review.")
    dataset_version_id: Optional[str] = None
    control_fraction: float = Field(0.10, ge=0.0, le=0.5, description="Fraction of budget reserved for control sample.")
    seed: int = Field(42, description="Deterministic seed for reproducible control selection.")


@router.post("/optimize")
def optimize_review_budget(
    req: ReviewBudgetRequest,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_supervisor),
):
    # Resolve dataset version
    ver_id = req.dataset_version_id or (str(repo.active_dataset_version_id) if repo.active_dataset_version_id else None)
    if not ver_id:
        raise HTTPException(status_code=404, detail="No active dataset version. Load a dataset first.")

    # Retrieve findings for the active version
    version_uuid = UUID(ver_id)
    findings = repo.get_findings(dataset_version_id=version_uuid)
    if not findings and findings is not None:
        findings = []

    # Resolve analysis run and ruleset metadata
    analysis_run_id = None
    ruleset_version = None
    for ds_meta in repo.datasets.values():
        for v in ds_meta.get("versions", []):
            if str(v.get("version_id")) == ver_id:
                analysis_run_id = v.get("analysis_run_id")
                ruleset_version = v.get("ruleset_version")
                break

    optimizer = ReviewBudgetOptimizer(
        control_fraction=req.control_fraction,
        seed=req.seed,
    )

    report = optimizer.optimize(
        candidates=findings,
        budget=req.budget,
        dataset_version_id=version_uuid,
        analysis_run_id=analysis_run_id,
        ruleset_version=ruleset_version,
    )

    # Audit trail
    repo.record_audit_event(
        user_id=user.user_id,
        username=user.username,
        action="REVIEW_BUDGET_OPTIMIZATION",
        target_type="review_budget",
        target_id=ver_id,
        details={
            "budget": req.budget,
            "candidate_count": report.candidate_count,
            "selected_count": report.selected_count,
            "dataset_version_id": ver_id,
            "seed": req.seed,
        },
    )

    return report.to_dict()
