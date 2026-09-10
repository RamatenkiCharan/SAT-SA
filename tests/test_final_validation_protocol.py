"""
Automated Tests for the Final SAT-SA Validation Protocol (SRS §19.4, §24).

Validates:
1. Held-Out Ratio: >= 20% of scenarios are held out from detector tuning.
2. 8 Mandatory Scenario Categories:
   - normal behavior
   - fast closure defect
   - escalation gap
   - repeated unresolved behavior
   - coverage gap
   - noisy data
   - missing data
   - non-target anomalies
3. Confusion Matrix Invariants:
   - TP + FN = Total Positives
   - FP + TN = Total Negatives
   - False-Positive Rate = FP / (FP + TN) in [0, 1]
   - Precision = TP / (TP + FP) in [0, 1]
   - Recall = TP / (TP + FN) in [0, 1]
4. Non-Circular Validation: Raw bundle does NOT contain detector findings or target labels.
5. Generalization: Zero degradation on held-out scenarios with frozen ruleset.
6. Persistence: JSON protocol configuration & Markdown report generation.
"""
from __future__ import annotations

import json
import os
import pytest
from uuid import uuid4

from analytics.evaluation.validation_protocol import (
    FinalValidationProtocol,
    run_final_validation_protocol,
)
from analytics.synthetic_generator import (
    SCENARIO_CATEGORIES,
    TUNING_SCENARIO_CONFIGS,
    HELD_OUT_SCENARIO_CONFIGS,
    generate_synthetic_soc_benchmark,
)
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1


def test_scenario_splits_held_out_ratio():
    """Verify that at least 20% of scenarios are held out from tuning."""
    tuning_count = len(TUNING_SCENARIO_CONFIGS)
    held_out_count = len(HELD_OUT_SCENARIO_CONFIGS)
    total_count = tuning_count + held_out_count

    held_out_ratio = (held_out_count / total_count) * 100.0

    assert total_count >= 10, "Scenario catalog must have at least 10 scenarios"
    assert held_out_ratio >= 20.0, f"Held-out ratio {held_out_ratio:.1f}% must be >= 20.0%"
    assert tuning_count == 10
    assert held_out_count == 5
    assert abs(held_out_ratio - 33.33) < 0.1


def test_all_eight_scenario_categories_present():
    """Verify all 8 mandatory scenario categories are covered across both splits."""
    expected_categories = {
        "normal behavior",
        "fast closure defect",
        "escalation gap",
        "repeated unresolved behavior",
        "coverage gap",
        "noisy data",
        "missing data",
        "non-target anomalies",
    }
    assert set(SCENARIO_CATEGORIES) == expected_categories

    # Check Tuning coverage
    tuning_cats = set()
    for cfg in TUNING_SCENARIO_CONFIGS:
        tuning_cats.add(cfg["primary_category"])
        for c in cfg.get("categories", []):
            tuning_cats.add(c)
    assert expected_categories.issubset(tuning_cats), f"Missing in tuning: {expected_categories - tuning_cats}"

    # Check Held-Out coverage
    held_out_cats = set()
    for cfg in HELD_OUT_SCENARIO_CONFIGS:
        held_out_cats.add(cfg["primary_category"])
        for c in cfg.get("categories", []):
            held_out_cats.add(c)
    assert expected_categories.issubset(held_out_cats), f"Missing in held-out: {expected_categories - held_out_cats}"


def test_generator_detector_non_circularity():
    """Ensure generator does NOT inject target labels into raw bundle tables."""
    raw_bundle, scenarios = generate_synthetic_soc_benchmark(seed=42, is_held_out=False)

    # 1. Inspect table names: standard canonical tables only
    expected_tables = {
        "cse",
        "reporting_periods",
        "assets",
        "alerts",
        "investigations",
        "cases",
        "escalations",
        "actions",
        "closures",
        "coverage_observations",
    }
    assert set(raw_bundle.keys()) == expected_tables

    # 2. Inspect alerts and cases: no 'is_defect', 'target_finding', or 'label' fields
    for alt in raw_bundle["alerts"]:
        assert "target_label" not in alt
        assert "is_defect" not in alt
        assert "finding_type" not in alt

    for cs in raw_bundle["cases"]:
        assert "target_label" not in cs
        assert "is_defect" not in cs
        assert "finding_type" not in cs


def test_final_validation_protocol_execution():
    """Execute validation protocol and verify confusion matrix math and generalization."""
    protocol = FinalValidationProtocol(ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    result = protocol.run_validation(
        output_json_path="results/test_protocol.json",
        output_md_path="results/test_report.md",
    )

    assert result.protocol_version == "2.0.0"
    assert result.held_out_ratio_percentage >= 20.0
    assert result.generalization_delta["generalization_demonstrated"] is True

    # 1. Tuning Confusion Matrix
    t_cm = result.tuning_split.confusion_matrix
    assert t_cm.tp + t_cm.fn == t_cm.total_positives
    assert t_cm.fp + t_cm.tn == t_cm.total_negatives
    assert 0.0 <= t_cm.false_positive_rate <= 1.0
    assert 0.0 <= t_cm.precision <= 1.0
    assert 0.0 <= t_cm.recall <= 1.0
    assert t_cm.recall >= 0.85
    assert t_cm.false_positive_rate <= 0.15

    # 2. Held-Out Confusion Matrix
    h_cm = result.held_out_split.confusion_matrix
    assert h_cm.tp + h_cm.fn == h_cm.total_positives
    assert h_cm.fp + h_cm.tn == h_cm.total_negatives
    assert 0.0 <= h_cm.false_positive_rate <= 1.0
    assert 0.0 <= h_cm.precision <= 1.0
    assert 0.0 <= h_cm.recall <= 1.0
    assert h_cm.recall >= 0.85, f"Held-out recall {h_cm.recall} must be >= 0.85"
    assert h_cm.false_positive_rate <= 0.15, f"Held-out FPR {h_cm.false_positive_rate} must be <= 0.15"

    # 3. Category Breakdown verification
    assert len(result.tuning_split.category_breakdown) == 8
    assert len(result.held_out_split.category_breakdown) == 8

    # 4. Clean up test artifacts
    if os.path.exists("results/test_protocol.json"):
        os.remove("results/test_protocol.json")
    if os.path.exists("results/test_report.md"):
        os.remove("results/test_report.md")


def test_validation_persistence_and_reproducibility():
    """Verify saved protocol configuration matches runtime output deterministically."""
    out_json = "results/final_validation_protocol.json"
    out_md = "results/final_validation_report.md"

    res = run_final_validation_protocol(
        ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1,
        output_json_path=out_json,
        output_md_path=out_md,
    )

    assert os.path.exists(out_json)
    assert os.path.exists(out_md)

    with open(out_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["protocol_version"] == "2.0.0"
    assert data["ruleset_version"] == "V1"
    assert data["tuning_split"]["total_scenarios"] == 10
    assert data["held_out_split"]["total_scenarios"] == 5
    assert data["generalization_delta"]["generalization_demonstrated"] is True


from fastapi.testclient import TestClient
from backend.main import app
from backend.security.auth import UserContext, create_access_token


@pytest.fixture
def supervisor_headers():
    user = UserContext(user_id="sup-1", username="supervisor", role="supervisor", full_name="Supervisor User")
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


def test_api_validation_endpoint(supervisor_headers):
    """Verify /api/validation and /api/validation/protocol endpoints."""
    client = TestClient(app)
    
    # 1. Main validation endpoint
    res = client.get("/api/validation", headers=supervisor_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "tuning_split" in data
    assert "held_out_split" in data
    assert "final_protocol" in data
    assert data["final_protocol"]["held_out_ratio_percentage"] >= 20.0

    # 2. Protocol sub-endpoint
    res_proto = client.get("/api/validation/protocol", headers=supervisor_headers)
    assert res_proto.status_code == 200
    proto_data = res_proto.json()
    assert proto_data["protocol_version"] == "2.0.0"
    assert proto_data["generalization_delta"]["generalization_demonstrated"] is True

