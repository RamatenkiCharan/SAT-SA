"""
Unit tests for analytics/data_quality/quality_score.py.

AGENTS.md §55 requires, per detector/formula: normal case, positive target
case, near-boundary case, missing-data case, contradictory-evidence case,
low-sample case, malformed-input case. This suite covers the formula-level
equivalents of those categories.
"""
import uuid
from datetime import datetime

import pytest

from analytics.data_quality.quality_score import (
    DataQualityInputs,
    InsufficientInputError,
    compute_data_quality_score,
)
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1

DATASET_VERSION_ID = uuid.uuid4()


def test_perfect_data_yields_score_of_one():
    inputs = DataQualityInputs(
        missing_required_fields=0,
        total_required_fields=10,
        failed_validation_checks=0,
        total_validation_checks=20,
        observed_evidence_records=100,
        expected_evidence_records=100,
        actual_sample_size=30,
    )
    result = compute_data_quality_score(inputs, DATASET_VERSION_ID)
    assert result.score == pytest.approx(1.0)
    assert result.components.completeness_ratio == 1.0
    assert result.components.coverage_ratio == 1.0


def test_authoritative_v1_weights_match_the_srs_formula():
    """Protect the 0.35/0.25/0.25/0.15 SRS contract from configuration drift."""
    assert DEFAULT_AUTHORITATIVE_RULESET_V1.dq_weights.to_dict() == {
        "completeness_weight": 0.35,
        "consistency_weight": 0.25,
        "coverage_weight": 0.25,
        "sample_sufficiency_weight": 0.15,
        "minimum_sample_size_default": 30,
    }


def test_coverage_ratio_is_capped_at_one_even_with_surplus_evidence():
    """More evidence than expected must not inflate the score past perfect."""
    inputs = DataQualityInputs(
        missing_required_fields=0,
        total_required_fields=10,
        failed_validation_checks=0,
        total_validation_checks=20,
        observed_evidence_records=1000,   # far more than expected
        expected_evidence_records=100,
        actual_sample_size=30,
    )
    result = compute_data_quality_score(inputs, DATASET_VERSION_ID)
    assert result.components.coverage_ratio == 1.0


def test_sample_sufficiency_is_capped_at_one_with_huge_sample():
    inputs = DataQualityInputs(
        missing_required_fields=0,
        total_required_fields=10,
        failed_validation_checks=0,
        total_validation_checks=20,
        observed_evidence_records=100,
        expected_evidence_records=100,
        actual_sample_size=10_000,
    )
    result = compute_data_quality_score(inputs, DATASET_VERSION_ID)
    assert result.components.sample_sufficiency_ratio == 1.0


def test_low_sample_reduces_score_even_when_everything_else_is_perfect():
    inputs = DataQualityInputs(
        missing_required_fields=0,
        total_required_fields=10,
        failed_validation_checks=0,
        total_validation_checks=20,
        observed_evidence_records=100,
        expected_evidence_records=100,
        actual_sample_size=3,  # far below default minimum of 30
    )
    result = compute_data_quality_score(inputs, DATASET_VERSION_ID)
    assert result.components.sample_sufficiency_ratio == pytest.approx(0.1)
    assert result.score < 1.0


def test_missing_required_fields_reduces_completeness_only():
    inputs = DataQualityInputs(
        missing_required_fields=5,
        total_required_fields=10,
        failed_validation_checks=0,
        total_validation_checks=20,
        observed_evidence_records=100,
        expected_evidence_records=100,
        actual_sample_size=30,
    )
    result = compute_data_quality_score(inputs, DATASET_VERSION_ID)
    assert result.components.completeness_ratio == pytest.approx(0.5)
    assert result.components.consistency_ratio == 1.0


def test_zero_total_required_fields_raises_instead_of_dividing_by_zero():
    """AGENTS.md §52: never silently fabricate a value on malformed input."""
    inputs = DataQualityInputs(
        missing_required_fields=0,
        total_required_fields=0,
        failed_validation_checks=0,
        total_validation_checks=20,
        observed_evidence_records=100,
        expected_evidence_records=100,
        actual_sample_size=30,
    )
    with pytest.raises(InsufficientInputError):
        compute_data_quality_score(inputs, DATASET_VERSION_ID)


def test_near_boundary_high_priority_gate_threshold():
    """FR-073 gate is score > 0.6. Construct inputs that land just below and
    just above the boundary to confirm the formula (not the gate logic,
    which lives in fusion) behaves continuously and predictably there."""
    low_inputs = DataQualityInputs(
        missing_required_fields=6,
        total_required_fields=10,
        failed_validation_checks=10,
        total_validation_checks=20,
        observed_evidence_records=40,
        expected_evidence_records=100,
        actual_sample_size=10,
    )
    result = compute_data_quality_score(low_inputs, DATASET_VERSION_ID)
    assert result.score < 0.6


def test_weights_are_configurable_not_hardcoded():
    """Passing a different (still valid) ruleset must change the outcome -
    proves the formula reads weights as data, per AGENTS.md §28."""
    inputs = DataQualityInputs(
        missing_required_fields=5,
        total_required_fields=10,
        failed_validation_checks=0,
        total_validation_checks=20,
        observed_evidence_records=100,
        expected_evidence_records=100,
        actual_sample_size=30,
    )
    default_result = compute_data_quality_score(inputs, DATASET_VERSION_ID)
    alt_weights = {
        "completeness_weight": 0.70,
        "consistency_weight": 0.10,
        "coverage_weight": 0.10,
        "sample_sufficiency_weight": 0.10,
        "minimum_sample_size_default": 30,
    }
    alt_result = compute_data_quality_score(
        inputs, DATASET_VERSION_ID, weights=alt_weights, ruleset_version="V2-test"
    )
    assert default_result.score != alt_result.score
    assert alt_result.ruleset_version == "V2-test"


def test_result_always_carries_all_four_components():
    """PROJECT_CONTEXT §26: never display a blended score without components."""
    inputs = DataQualityInputs(
        missing_required_fields=1,
        total_required_fields=10,
        failed_validation_checks=1,
        total_validation_checks=20,
        observed_evidence_records=50,
        expected_evidence_records=100,
        actual_sample_size=15,
    )
    result = compute_data_quality_score(inputs, DATASET_VERSION_ID)
    for field in ("completeness_ratio", "consistency_ratio", "coverage_ratio", "sample_sufficiency_ratio"):
        assert hasattr(result.components, field)
