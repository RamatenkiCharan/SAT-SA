"""
Validation & Supervisory Review Yield API Endpoints (SRS §19.4, §24).
Computes empirical metrics against controlled synthetic ground-truth scenarios (tuning and held-out splits).
Includes comprehensive Robust Validation Protocol (Confusion Matrix, FPR, Thresholds, Hard Negatives) & Review Efficiency Evaluation.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from analytics.evaluation.review_efficiency import (
    ReviewEfficiencyEvaluator,
    run_review_efficiency_benchmark,
)
from analytics.evaluation.robust_validation import RobustValidationEngine
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1
from backend.security.auth import UserContext, require_supervisor

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.get("")
def get_validation_results(
    current_user: UserContext = Depends(require_supervisor),
):
    efficiency_report = run_review_efficiency_benchmark(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    
    engine = RobustValidationEngine(n_scenarios=100, n_bootstrap=50, ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    protocol_result = engine.run(seed=42)

    return {
        "status": "success",
        "methodology": "Robust Validation Protocol (I-02/I-09)",
        "disclosure": protocol_result.limitation_notice,
        "review_efficiency": efficiency_report.to_dict(),
        "final_protocol": protocol_result.to_dict(),
    }


@router.get("/protocol")
def get_final_protocol_results(
    current_user: UserContext = Depends(require_supervisor),
):
    engine = RobustValidationEngine(n_scenarios=240, n_bootstrap=200, ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    protocol_result = engine.run(seed=42)
    return protocol_result.to_dict()


@router.get("/review-efficiency")
def get_review_efficiency_results(
    current_user: UserContext = Depends(require_supervisor),
):
    report = run_review_efficiency_benchmark(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    return report.to_dict()


