"""
Validation & Supervisory Review Yield API Endpoints (SRS §19.4, §24).
Computes empirical metrics against controlled synthetic ground-truth scenarios (tuning and held-out splits).
Includes comprehensive Final Validation Protocol (Confusion Matrix, FPR, 8 Categories) & Review Efficiency Evaluation.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from analytics.evaluation.review_efficiency import (
    ReviewEfficiencyEvaluator,
    run_review_efficiency_benchmark,
)
from analytics.evaluation.validation_protocol import (
    FinalValidationProtocol,
    run_final_validation_protocol,
)
from analytics.synthetic_generator import evaluate_ground_truth_validation
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1
from backend.security.auth import UserContext, require_supervisor

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.get("")
def get_validation_results(
    current_user: UserContext = Depends(require_supervisor),
):
    tuning_results = evaluate_ground_truth_validation(is_held_out=False)
    held_out_results = evaluate_ground_truth_validation(is_held_out=True)
    efficiency_report = run_review_efficiency_benchmark(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    protocol_result = run_final_validation_protocol(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)

    return {
        "status": "success",
        "methodology": "Generator/Detector Independence Protocol (SRS §19.4, §24)",
        "disclosure": "Validated on controlled synthetic multi-sector ground truth scenarios with held-out scenario split (>=20% held-out ratio).",
        "tuning_split": tuning_results,
        "held_out_split": held_out_results,
        "review_efficiency": efficiency_report.to_dict(),
        "final_protocol": protocol_result.to_dict(),
    }


@router.get("/protocol")
def get_final_protocol_results(
    current_user: UserContext = Depends(require_supervisor),
):
    protocol_result = run_final_validation_protocol(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    return protocol_result.to_dict()


@router.get("/review-efficiency")
def get_review_efficiency_results(
    current_user: UserContext = Depends(require_supervisor),
):
    report = run_review_efficiency_benchmark(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    return report.to_dict()

