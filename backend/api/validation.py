"""
Validation & Supervisory Review Yield API Endpoints.
Computes empirical metrics against controlled synthetic ground-truth scenarios (tuning and held-out splits).
"""
from __future__ import annotations

from fastapi import APIRouter
from analytics.synthetic_generator import evaluate_ground_truth_validation

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.get("")
def get_validation_results():
    tuning_results = evaluate_ground_truth_validation(is_held_out=False)
    held_out_results = evaluate_ground_truth_validation(is_held_out=True)

    return {
        "status": "success",
        "methodology": "Generator/Detector Independence Protocol (§19.4)",
        "disclosure": "Validated on controlled synthetic multi-sector ground truth scenarios with held-out scenario split.",
        "tuning_split": tuning_results,
        "held_out_split": held_out_results,
    }
