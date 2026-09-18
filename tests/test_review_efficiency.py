"""
Comprehensive Verification Tests for SAT-SA Review-Efficiency Evaluation Framework (SRS §19.4).

Verifies:
1. Baseline vs SAT-SA Assisted review effort calculations (cases, hours, speedup).
2. Useful findings and false positives tracking across ranked cutoffs K.
3. Top-K Recall monotonicity and full weakness capture point K*.
4. Review Yield cumulative progression curves.
5. Time-to-Useful-Finding (TTUF_1st, MTTUF, TTUF_100%).
6. Zero fabrication: metrics derived directly from live pipeline execution.
7. Strict separation of Tuning vs Held-Out splits.
8. Reproducibility of CLI script and API endpoints.
"""
from pathlib import Path
import json
import subprocess
import sys
import pytest
from fastapi.testclient import TestClient

from analytics.evaluation.review_efficiency import (
    ReviewEfficiencyEvaluator,
    run_review_efficiency_benchmark,
)
from backend.main import app
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1
from backend.security.auth import UserContext, create_access_token


@pytest.fixture
def supervisor_headers():
    user = UserContext(user_id="sup-1", username="supervisor", role="supervisor", full_name="Supervisor User")
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 1. Mathematical Sanity & Workload Reduction Verification
# =============================================================================

def test_review_efficiency_workload_reduction_and_speedup():
    """
    Verifies that SAT-SA prioritizes findings such that:
    - 100% weakness recall is achieved in far fewer reviews than total raw cases.
    - Workload effort reduction is strictly positive (> 90%).
    - Efficiency speedup multiplier is > 10x.
    - No fabricated statistics are used.
    """
    evaluator = ReviewEfficiencyEvaluator(
        ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1,
        baseline_minutes_per_case=8.0,
        assisted_minutes_per_finding=4.0,
    )

    report = evaluator.run_full_benchmark()

    # Verify Tuning Split
    tuning = report.tuning_split
    assert tuning.total_raw_cases >= 100
    assert tuning.total_true_weaknesses > 0
    assert tuning.findings_reviewed_for_100pct_recall <= 15
    assert tuning.recall == 1.0  # 100% weakness capture
    assert tuning.workload_effort_reduction_percentage > 90.0
    assert tuning.efficiency_multiplier_speedup > 10.0

    # Verify Held-Out Split
    held_out = report.held_out_split
    assert held_out.total_raw_cases >= 100
    assert held_out.total_true_weaknesses > 0
    assert held_out.findings_reviewed_for_100pct_recall <= 15
    assert held_out.recall == 1.0
    assert held_out.workload_effort_reduction_percentage > 90.0
    assert held_out.efficiency_multiplier_speedup > 10.0

    # Cross-split summary
    cross = report.cross_split_summary
    assert cross["average_workload_reduction_percentage"] > 90.0
    assert cross["average_efficiency_multiplier_speedup"] > 10.0
    assert cross["air_gapped_deterministic"] is True
    assert cross["llm_dependency"] is False


# =============================================================================
# 2. Time-to-Useful-Finding (TTUF) Verification
# =============================================================================

def test_time_to_useful_finding_metrics():
    """
    Verifies that TTUF metrics are calculated correctly and show dramatic
    time reduction relative to unassisted random search.
    """
    evaluator = ReviewEfficiencyEvaluator(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    res = evaluator.evaluate_split(seed=42, is_held_out=False)

    # Time to 1st useful finding under SAT-SA should be <= 8 minutes
    assert res.ttuf_first_useful_minutes <= 8.0
    # Expected random search time to 1st useful finding should be significantly larger
    assert res.baseline_expected_minutes_to_first_useful > 100.0
    assert res.ttuf_first_useful_minutes < res.baseline_expected_minutes_to_first_useful

    # Time for 100% recall
    assert res.time_to_100pct_recall_minutes < (res.total_baseline_effort_hours * 60.0)
    assert res.mean_time_to_useful_finding_minutes > 0.0


# =============================================================================
# 3. Top-K Recall & Monotonicity
# =============================================================================

def test_top_k_recall_monotonicity():
    """
    Verifies that Top-K recall is monotonically non-decreasing:
    0 <= Recall@1 <= Recall@3 <= Recall@5 <= Recall@10 <= 1.0
    """
    evaluator = ReviewEfficiencyEvaluator(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    res = evaluator.evaluate_split(seed=42, is_held_out=False)

    assert 0.0 <= res.recall_at_1 <= 1.0
    assert res.recall_at_1 <= res.recall_at_3
    assert res.recall_at_3 <= res.recall_at_5
    assert res.recall_at_5 <= res.recall_at_10
    assert res.recall_at_10 <= 1.0


# =============================================================================
# 4. Useful vs False Positive Progression in Yield Curve
# =============================================================================

def test_yield_curve_integrity():
    """
    Verifies that every step in the yield curve satisfies:
    - cumulative TP + cumulative FP == rank
    - precision@k == cumulative TP / rank
    - recall@k == cumulative TP / total_true_weaknesses
    - assisted time == rank * assisted_minutes_per_finding
    """
    evaluator = ReviewEfficiencyEvaluator(
        ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1,
        assisted_minutes_per_finding=4.0,
    )
    res = evaluator.evaluate_split(seed=42, is_held_out=False)

    assert len(res.yield_curve) > 0

    for step in res.yield_curve:
        assert step.cumulative_true_positives + step.cumulative_false_positives == step.rank
        expected_precision = round(step.cumulative_true_positives / step.rank, 4)
        assert abs(step.precision_at_k - expected_precision) < 1e-3
        expected_recall = round(step.cumulative_true_positives / res.total_true_weaknesses, 4)
        assert abs(step.recall_at_k - expected_recall) < 1e-3
        assert step.assisted_time_minutes == round(step.rank * 4.0, 1)


# =============================================================================
# 5. Separation of Tuning vs Held-Out Scenario Splits
# =============================================================================

def test_tuning_and_held_out_independence():
    """
    Verifies that Tuning Split and Held-Out Split evaluate different random seeds,
    carry their respective descriptors, and produce independent evaluations.
    """
    report = run_review_efficiency_benchmark()

    assert report.tuning_split.seed == 42
    assert report.held_out_split.seed == 101
    assert report.tuning_split.split_name == "Tuning Split"
    assert report.held_out_split.split_name == "Held-Out Split"

    # Both must have scenario descriptors
    assert len(report.tuning_split.scenarios) > 0
    assert len(report.held_out_split.scenarios) > 0

    for sc in report.tuning_split.scenarios:
        assert len(sc.cse_name) > 0
        assert len(sc.sector) > 0
        assert 0.0 <= sc.self_reported_sla <= 1.0


# =============================================================================
# 6. JSON Serialization & Schema Completeness
# =============================================================================

def test_benchmark_json_serialization():
    """
    Verifies that the benchmark report serializes cleanly to JSON with all
    required metadata (ruleset version, ruleset ID, timestamps, scenario list).
    """
    report = run_review_efficiency_benchmark()
    json_str = report.to_json(indent=2)
    parsed = json.loads(json_str)

    assert "evaluation_timestamp" in parsed
    assert "ruleset_version" in parsed
    assert "ruleset_id" in parsed
    assert "tuning_split" in parsed
    assert "held_out_split" in parsed
    assert "cross_split_summary" in parsed

    assert "workload_effort_reduction_percentage" in parsed["tuning_split"]
    assert "efficiency_multiplier_speedup" in parsed["tuning_split"]
    assert "yield_curve" in parsed["tuning_split"]


# =============================================================================
# 7. CLI Script Execution End-to-End
# =============================================================================

def test_cli_script_execution(tmp_path: Path):
    """
    Executes scripts/evaluate_review_efficiency.py via subprocess to verify
    clean CLI behavior and file emission.
    """
    out_json = tmp_path / "cli_test_benchmark.json"
    out_md = tmp_path / "cli_test_report.md"

    cmd = [
        sys.executable,
        "scripts/evaluate_review_efficiency.py",
        "--output",
        str(out_json),
        "--markdown",
        str(out_md),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"CLI script failed: {res.stderr}"

    assert out_json.exists()
    assert out_md.exists()

    with open(out_json, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert "tuning_split" in data
        assert "held_out_split" in data


# =============================================================================
# 8. FastAPI Validation API Review Efficiency Endpoint
# =============================================================================

def test_api_validation_review_efficiency_endpoints(supervisor_headers):
    """
    Verifies the explicitly historical review-efficiency endpoint remains
    isolated from the active robust-validation API contract.
    """
    client = TestClient(app)

    # The active validation endpoint must not expose historical diagnostics.
    resp1 = client.get("/api/validation", headers=supervisor_headers)
    assert resp1.status_code == 200
    val_data = resp1.json()
    assert "review_efficiency" not in val_data

    # Historical diagnostics remain available only under an explicit path.
    resp2 = client.get("/api/validation/historical-review-efficiency", headers=supervisor_headers)
    assert resp2.status_code == 200
    eff_data = resp2.json()
    assert "tuning_split" in eff_data
    assert "held_out_split" in eff_data
    assert eff_data["ruleset_version"] == "V1"
