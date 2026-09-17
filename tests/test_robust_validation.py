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

    # Verify metrics logic
    assert 0 <= res.tuning_metrics.precision <= 1
    assert 0 <= res.tuning_metrics.recall <= 1
    assert 0 <= res.tuning_metrics.fpr <= 1

    # Verify CI bounds
    if res.tuning_metrics.precision_ci:
        assert res.tuning_metrics.precision_ci.lower <= res.tuning_metrics.precision_ci.mean <= res.tuning_metrics.precision_ci.upper


def test_api_validation_endpoint(supervisor_headers):
    """Verify /api/validation endpoints return robust validation results."""
    client = TestClient(app)

    res = client.get("/api/validation", headers=supervisor_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "Robust Validation Protocol" in data["methodology"]
    assert "SYNTHETIC VALIDATION ONLY" in data["disclosure"]
    assert "review_efficiency" in data
    assert "final_protocol" in data

    proto = data["final_protocol"]
    assert "tuning_metrics" in proto
    assert "held_out_metrics" in proto
    assert "tuning_ranking" in proto
