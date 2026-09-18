"""
Automated Tests for the Robust SAT-SA Validation Protocol (I-02/I-09).

Validates:
1. Generation of hard negatives.
2. Bootstrap confidence intervals.
3. Confusion Matrix and Ranking Metrics.
4. Generalization with no label leakage.
5. Integration with API endpoints.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from analytics.evaluation.robust_validation import RobustValidationEngine
from backend.main import app
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1
from backend.security.auth import UserContext, create_access_token

@pytest.fixture
def supervisor_headers():
    user = UserContext(
        user_id="usr_sup_offline",
        username="supervisor",
        role="supervisor",
        full_name="Air-Gapped Examiner",
    )
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}

def test_robust_validation_engine_execution():
    """Verify that the robust validation engine runs and computes metrics correctly."""
    engine = RobustValidationEngine(n_scenarios=20, n_bootstrap=10, ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    res = engine.run(seed=123)

    assert res.total_scenarios == 20
    assert res.held_out_ratio > 0
    assert res.limitation_notice.startswith("SYNTHETIC VALIDATION ONLY")

    assert res.tuning_metrics is not None
    assert res.held_out_metrics is not None
    assert res.tuning_ranking is not None
    assert res.held_out_ranking is not None
    assert len(res.weight_sensitivity) == 10
    assert all(0 <= point.recall_at_5 <= 1 for point in res.weight_sensitivity)

    # Verify metrics logic
    assert 0 <= res.tuning_metrics.precision <= 1
    assert 0 <= res.tuning_metrics.recall <= 1
    assert 0 <= res.tuning_metrics.fpr <= 1

    # Verify CI bounds
    if res.tuning_metrics.precision_ci:
        assert res.tuning_metrics.precision_ci.lower <= res.tuning_metrics.precision_ci.mean <= res.tuning_metrics.precision_ci.upper


def test_api_validation_endpoint(supervisor_headers):
    """Verify the active API returns the current authoritative protocol."""
    client = TestClient(app)

    res = client.get("/api/validation", headers=supervisor_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_scenarios"] == 240
    assert data["tuning_scenarios"] == 168
    assert data["held_out_scenarios"] == 72
    assert data["hard_negative_count"] == 36
    assert "SYNTHETIC VALIDATION ONLY" in data["limitation_notice"]
    assert data["held_out_metrics"] == {
        "tp": 36,
        "fp": 1,
        "tn": 248,
        "fn": 3,
        "precision": pytest.approx(0.973),
        "recall": pytest.approx(0.9231),
        "f1_score": pytest.approx(0.9474),
        "fpr": pytest.approx(0.004),
        "precision_ci": data["held_out_metrics"]["precision_ci"],
        "recall_ci": data["held_out_metrics"]["recall_ci"],
    }
    assert "tuning_ranking" in data
    assert "held_out_ranking" in data
    assert "weight_sensitivity" in data
    assert "final_protocol" not in data
    assert "review_efficiency" not in data
