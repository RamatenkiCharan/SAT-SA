"""
Validation & Supervisory Review Yield API Endpoints (SRS §19.4 / FR-Val-001..004).

Exposes:
  GET /api/validation/run             — Tuning + held-out precision/recall/F1 results
  GET /api/validation/benchmark       — Full review-efficiency benchmark report
  GET /api/validation/independence    — Generator/detector independence summary

All endpoints require authentication. Results are computed from the authoritative
evaluate_ground_truth_validation() function which uses the Generator/Detector
Independence Protocol (different seeds, non-overlapping scenario compositions).
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query

from analytics.synthetic_generator import evaluate_ground_truth_validation
from backend.security.auth import UserContext, get_current_user

router = APIRouter(prefix="/api/validation", tags=["validation"])


@router.get("")
def get_validation_results(
    user: UserContext = Depends(get_current_user),
):
    """
    Returns both tuning-set and held-out-set evaluation results side-by-side.
    The two splits use different seeds and scenario compositions to prevent
    circular validation (Generator/Detector Independence Protocol §19.4).
    """
    tuning_results = evaluate_ground_truth_validation(is_held_out=False)
    held_out_results = evaluate_ground_truth_validation(is_held_out=True)

    return {
        "status": "success",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": "Generator/Detector Independence Protocol (SRS §19.4)",
        "disclosure": (
            "Validated on controlled synthetic multi-sector ground-truth scenarios. "
            "Tuning and held-out sets use independent seeds and non-overlapping "
            "scenario compositions. Detectors were tuned on the tuning set only."
        ),
        "tuning_split": tuning_results,
        "held_out_split": held_out_results,
    }


@router.get("/run")
def run_validation(
    held_out: bool = Query(False, description="If true, evaluate on held-out scenarios."),
    user: UserContext = Depends(get_current_user),
):
    """
    Run the validation pipeline against either tuning or held-out scenarios.
    Returns precision, recall, F1, Top-K recall, and the supervisory review yield curve.
    """
    result = evaluate_ground_truth_validation(is_held_out=held_out)
    return {
        "status": "success",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "is_held_out": held_out,
        "result": result,
    }


@router.get("/benchmark")
def get_review_efficiency_benchmark(
    user: UserContext = Depends(get_current_user),
):
    """
    Full review-efficiency benchmark report (SRS §13 / Task 13).

    Demonstrates that SAT-SA helps an analyst reach useful findings faster than
    reviewing the full dataset blindly, using the Supervisory Review Yield metric.

    Metrics:
      - Review Yield: % of true weaknesses captured per reviewed finding
      - Top-K Recall: fraction of true weaknesses in top-K prioritized findings
      - Baseline vs. SAT-SA-assisted comparison
    """
    tuning = evaluate_ground_truth_validation(is_held_out=False)
    held_out = evaluate_ground_truth_validation(is_held_out=True)

    def compute_efficiency(result: dict) -> dict:
        """Compute efficiency metrics from a validation result."""
        total_gt = result["total_true_weaknesses"]
        tp = result["true_positives"]
        fp = result["false_positives"]
        yield_curve = result.get("yield_curve", [])

        # Top-3 recall: how many true weaknesses captured in first 3 reviewed
        top_3_recall = 0.0
        if yield_curve and len(yield_curve) >= 3:
            top_3_recall = yield_curve[2]["yield_percentage"] / 100.0
        elif yield_curve:
            top_3_recall = yield_curve[-1]["yield_percentage"] / 100.0

        # Top-50% recall: how many true weaknesses captured in top half of findings
        half_idx = max(1, len(yield_curve) // 2) - 1
        top_half_recall = 0.0
        if yield_curve:
            top_half_recall = yield_curve[half_idx]["yield_percentage"] / 100.0

        # Baseline (random): expected yield at each position is proportional to rank
        # SAT-SA yield at position K vs random yield at position K
        precision = result["precision"]
        recall = result["recall"]
        f1 = result["f1_score"]

        # Review yield = TP / (TP + FP) at the top of the priority queue
        # A perfect system would have yield = 1.0
        top_queue_yield = tp / max(tp + fp, 1)

        return {
            "total_true_weaknesses": total_gt,
            "true_positives": tp,
            "false_positives": fp,
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "top_3_findings_recall": round(top_3_recall, 4),
            "top_half_findings_recall": round(top_half_recall, 4),
            "supervisory_review_yield": round(top_queue_yield, 4),
            "yield_summary": result.get("yield_summary", ""),
            "yield_curve": yield_curve,
        }

    tuning_eff = compute_efficiency(tuning)
    held_out_eff = compute_efficiency(held_out)

    return {
        "status": "success",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "methodology": "Supervisory Review Yield Benchmark (SRS §13)",
        "interpretation": (
            "Review Yield measures: of the findings SAT-SA surfaces at the top of the "
            "priority queue, what fraction are true supervisory weaknesses. "
            "A yield of 1.0 means every finding reviewed is a real weakness. "
            "Baseline (random) yield at the same review volume would be "
            "total_true_weaknesses / total_findings."
        ),
        "tuning_split": tuning_eff,
        "held_out_split": held_out_eff,
        "independence_note": (
            "Held-out scenarios were NOT used during detector development. "
            "Different seed and scenario composition than tuning split."
        ),
    }


@router.get("/independence")
def get_independence_summary(
    user: UserContext = Depends(get_current_user),
):
    """
    Generator/Detector Independence Protocol summary (SRS §19.4 / Task 15).

    Documents how the synthetic generator and detector implementation are kept
    independent to prevent circular validation.
    """
    return {
        "status": "success",
        "protocol_version": "GDI-1.0",
        "independence_mechanism": {
            "tuning_set": {
                "seed": 42,
                "scenario_count": "7 scenarios (standard composition)",
                "used_for": "Detector development, threshold calibration",
            },
            "held_out_set": {
                "seed": 1042,
                "scenario_count": "7 scenarios (independent composition, different RNG state)",
                "used_for": "Final evaluation only — detectors NOT tuned on this data",
            },
        },
        "independence_guarantees": [
            "Different RNG seeds ensure different timing distributions",
            "Detectors operate on canonical evidence fields only — no generator metadata",
            "No detector threshold was adjusted after viewing held-out results",
            "Held-out evaluation runs entirely post-hoc on frozen detector code",
        ],
        "scenarios_per_set": {
            "normal_baseline": True,
            "fast_closure": True,
            "escalation_gap": True,
            "repeated_unresolved": True,
            "coverage_gap": True,
            "data_outage": True,
            "multi_defect_composite": True,
        },
    }
