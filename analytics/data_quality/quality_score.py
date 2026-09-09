"""
Data Quality Score - pinned formula, SRS v2.0 §7.2.1.

    DataQualityScore(dataset) =
        0.35 * CompletenessRatio
      + 0.25 * ConsistencyRatio
      + 0.25 * CoverageRatio        (capped at 1.0)
      + 0.15 * SampleSufficiencyRatio

Hard rules this module MUST respect (do not "simplify" these away):
  - Weights are read from the `rulesets` table (data_quality_score / V1), never
    hardcoded here as bare literals. A default is provided ONLY as a fallback
    for local unit tests that don't have a DB connection.
  - The score is NEVER returned alone. Every caller gets the four components
    back too (PROJECT_CONTEXT §26 explainability contract / SRS §7.2.1
    "Report the score AND its four components in the UI - never the blended
    number alone").
  - CoverageRatio is capped at 1.0 - having MORE evidence than expected must
    never inflate the score past perfect.
  - SampleSufficiencyRatio uses min(1.0, actual/minimum) - never let a huge
    sample count push this above 1.0 either.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

# Fallback only - production code must load this from the `rulesets` table
# (ruleset_name='data_quality_score', version='V1') via a repository, so a
# weight change is a data migration, not a code deploy (AGENTS.md §28).
_FALLBACK_WEIGHTS = {
    "completeness_weight": 0.35,
    "consistency_weight": 0.25,
    "coverage_weight": 0.25,
    "sample_sufficiency_weight": 0.15,
    "minimum_sample_size_default": 30,
}


@dataclass(frozen=True)
class DataQualityInputs:
    """Raw counts a caller must supply. No inference happens here - this
    module only applies the pinned formula to numbers the Data Trust layer
    (FR-010/011/012) has already computed."""
    missing_required_fields: int
    total_required_fields: int
    failed_validation_checks: int
    total_validation_checks: int
    observed_evidence_records: int
    expected_evidence_records: int
    actual_sample_size: int


@dataclass(frozen=True)
class DataQualityComponents:
    completeness_ratio: float
    consistency_ratio: float
    coverage_ratio: float
    sample_sufficiency_ratio: float


@dataclass(frozen=True)
class DataQualityResult:
    dataset_version_id: UUID
    score: float
    components: DataQualityComponents
    ruleset_version: str
    computed_at: datetime


class InsufficientInputError(ValueError):
    """Raised when a required denominator is zero/undefined - we refuse to
    silently divide by zero and refuse to silently assume a perfect score.
    Per AGENTS.md §52 (Error Handling): fail explicitly, never fabricate."""


def _safe_ratio(numerator: float, denominator: float, *, cap_at_one: bool) -> float:
    if denominator <= 0:
        raise InsufficientInputError(
            f"Cannot compute ratio: denominator is {denominator} (numerator={numerator})."
        )
    ratio = numerator / denominator
    if cap_at_one:
        ratio = min(ratio, 1.0)
    return max(ratio, 0.0)


def compute_data_quality_score(
    inputs: DataQualityInputs,
    dataset_version_id: UUID,
    weights: dict | None = None,
    ruleset_version: str = "V1",
) -> DataQualityResult:
    """
    Pure function. No DB access, no side effects - callers pass in weights
    loaded from the rulesets table so this stays independently unit-testable
    (AGENTS.md §55 analytics test requirement) and reproducible (§30).
    """
    w = weights or _FALLBACK_WEIGHTS

    completeness_ratio = _safe_ratio(
        inputs.total_required_fields - inputs.missing_required_fields,
        inputs.total_required_fields,
        cap_at_one=True,
    )
    consistency_ratio = _safe_ratio(
        inputs.total_validation_checks - inputs.failed_validation_checks,
        inputs.total_validation_checks,
        cap_at_one=True,
    )
    coverage_ratio = _safe_ratio(
        inputs.observed_evidence_records,
        max(inputs.expected_evidence_records, 1),
        cap_at_one=True,
    )
    min_sample = w.get("minimum_sample_size_default", 30)
    sample_sufficiency_ratio = min(1.0, inputs.actual_sample_size / max(min_sample, 1))

    score = (
        w["completeness_weight"] * completeness_ratio
        + w["consistency_weight"] * consistency_ratio
        + w["coverage_weight"] * coverage_ratio
        + w["sample_sufficiency_weight"] * sample_sufficiency_ratio
    )
    # Clamp for floating-point drift only - the weighted sum of four ratios
    # each in [0,1] with weights summing to 1.0 is mathematically in [0,1].
    score = max(0.0, min(1.0, score))

    return DataQualityResult(
        dataset_version_id=dataset_version_id,
        score=score,
        components=DataQualityComponents(
            completeness_ratio=completeness_ratio,
            consistency_ratio=consistency_ratio,
            coverage_ratio=coverage_ratio,
            sample_sufficiency_ratio=sample_sufficiency_ratio,
        ),
        ruleset_version=ruleset_version,
        computed_at=datetime.now(timezone.utc),
    )
