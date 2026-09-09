"""
Data Quality Processor.
Evaluates canonical datasets to extract empirical DataQualityInputs and compute DataQualityResult.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.data_quality.quality_score import (
    DataQualityInputs,
    DataQualityResult,
    compute_data_quality_score,
)


def evaluate_dataset_quality(
    dataset: CanonicalDataset,
    dataset_version_id: UUID,
    weights: Optional[dict] = None,
    ruleset_version: str = "V1",
) -> DataQualityResult:
    """
    Computes data quality from real canonical records using the §7.2.1 formula.
    """
    total_required = 0
    missing_required = 0

    total_validations = 0
    failed_validations = 0

    # 1. Evaluate CSEs
    for c in dataset.cse_list:
        total_required += 4
        if not c.name:
            missing_required += 1
        if not c.sector:
            missing_required += 1
        if not c.scale:
            missing_required += 1
        if not c.reporting_period_id:
            missing_required += 1

    # 2. Evaluate Assets
    asset_ids = {a.asset_id for a in dataset.assets}
    for a in dataset.assets:
        total_required += 4
        if not a.asset_type:
            missing_required += 1
        if not a.environment:
            missing_required += 1
        if not a.criticality:
            missing_required += 1
        if not a.cse_id:
            missing_required += 1

    # 3. Evaluate Alerts & Validations
    for alert in dataset.alerts:
        total_required += 6
        if not alert.severity:
            missing_required += 1
        if not alert.alert_category:
            missing_required += 1
        if not alert.source:
            missing_required += 1
        if not alert.status:
            missing_required += 1
        if not alert.event_time:
            missing_required += 1
        if not alert.asset_id:
            missing_required += 1

        total_validations += 1
        if alert.asset_id not in asset_ids:
            failed_validations += 1

    # 4. Evaluate Investigations
    alert_ids = {alt.alert_id for alt in dataset.alerts}
    for inv in dataset.investigations:
        total_required += 3
        if not inv.started_at:
            missing_required += 1
        if inv.evidence_count is None:
            missing_required += 1
        if not inv.alert_id:
            missing_required += 1

        total_validations += 2
        if inv.alert_id not in alert_ids:
            failed_validations += 1
        if inv.ended_at and inv.ended_at < inv.started_at:
            failed_validations += 1

    # 5. Evaluate Cases & Closures
    case_ids = {c.case_id for c in dataset.cases}
    case_map = {c.case_id: c for c in dataset.cases}
    for case in dataset.cases:
        total_required += 3
        if not case.opened_at:
            missing_required += 1
        if not case.severity:
            missing_required += 1
        if not case.alert_id:
            missing_required += 1

        total_validations += 2
        if case.alert_id not in alert_ids:
            failed_validations += 1
        if case.closed_at and case.closed_at < case.opened_at:
            failed_validations += 1

    for clo in dataset.closures:
        total_required += 2
        if not clo.closed_at:
            missing_required += 1
        if not clo.reason:
            missing_required += 1

        total_validations += 2
        if clo.case_id not in case_ids:
            failed_validations += 1
        linked_case = case_map.get(clo.case_id)
        if linked_case and clo.closed_at < linked_case.opened_at:
            failed_validations += 1

    # Counts
    total_required = max(total_required, 1)
    total_validations = max(total_validations, 1)

    observed_evidence = (
        len(dataset.alerts)
        + len(dataset.investigations)
        + len(dataset.cases)
        + len(dataset.escalations)
        + len(dataset.actions)
        + len(dataset.closures)
    )

    # Expected count from coverage observations or heuristic
    expected_from_obs = sum(obs.expected_count for obs in dataset.coverage_observations)
    expected_evidence = max(int(expected_from_obs), len(dataset.alerts), 30)

    actual_sample_size = len(dataset.alerts)

    inputs = DataQualityInputs(
        missing_required_fields=missing_required,
        total_required_fields=total_required,
        failed_validation_checks=failed_validations,
        total_validation_checks=total_validations,
        observed_evidence_records=observed_evidence,
        expected_evidence_records=expected_evidence,
        actual_sample_size=actual_sample_size,
    )

    return compute_data_quality_score(
        inputs=inputs,
        dataset_version_id=dataset_version_id,
        weights=weights,
        ruleset_version=ruleset_version,
    )
