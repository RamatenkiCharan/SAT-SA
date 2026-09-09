"""
Unit tests for FR-041 Coverage Gap negative-space detector.
"""
from datetime import datetime, timezone
from uuid import uuid4

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.negative_space.coverage_gap import CoverageGapDetector
from backend.models.canonical import Asset, AssetCriticality, CoverageObservation, CSE


def test_coverage_gap_flags_silent_critical_asset_when_dq_high():
    ver_id = uuid4()
    cse_id = uuid4()
    asset_id = uuid4()
    rep_id = uuid4()
    now = datetime.now(timezone.utc)

    cse = CSE(
        cse_id=cse_id,
        name="State Health Exchange",
        sector="Healthcare",
        scale="medium",
        reporting_period_id=rep_id,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    asset = Asset(
        asset_id=asset_id,
        cse_id=cse_id,
        criticality=AssetCriticality.CRITICAL,
        asset_type="EHR Database",
        environment="Prod",
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    obs = CoverageObservation(
        observation_id=uuid4(),
        cse_id=cse_id,
        asset_id=asset_id,
        alert_category="Data Exfiltration",
        period_id=rep_id,
        expected_count=50.0,
        observed_count=0.0,  # Silent
        dataset_version_id=ver_id,
        ingest_time=now,
    )

    canonical_ds = CanonicalDataset(
        dataset_version_id=ver_id,
        cse_list=[cse],
        assets=[asset],
        coverage_observations=[obs],
    )

    detector = CoverageGapDetector()
    # When DataQualityScore is healthy (0.92 > 0.7), coverage gap SHOULD flag
    signals = detector.detect(canonical_ds, data_quality_score=0.92)
    assert len(signals) == 1
    assert signals[0].coverage_ratio == 0.0
    assert signals[0].asset_criticality == AssetCriticality.CRITICAL


def test_coverage_gap_safely_ignored_when_dq_low():
    ver_id = uuid4()
    cse_id = uuid4()
    asset_id = uuid4()
    rep_id = uuid4()
    now = datetime.now(timezone.utc)

    cse = CSE(
        cse_id=cse_id,
        name="Outage Entity",
        sector="Energy",
        scale="large",
        reporting_period_id=rep_id,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    asset = Asset(
        asset_id=asset_id,
        cse_id=cse_id,
        criticality=AssetCriticality.CRITICAL,
        asset_type="Transformer Controller",
        environment="Grid",
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    obs = CoverageObservation(
        observation_id=uuid4(),
        cse_id=cse_id,
        asset_id=asset_id,
        alert_category="Outage",
        period_id=rep_id,
        expected_count=50.0,
        observed_count=0.0,
        dataset_version_id=ver_id,
        ingest_time=now,
    )

    canonical_ds = CanonicalDataset(
        dataset_version_id=ver_id,
        cse_list=[cse],
        assets=[asset],
        coverage_observations=[obs],
    )

    detector = CoverageGapDetector()
    # When DataQualityScore is low (0.45 < 0.7), coverage gap MUST NOT raise an operational conclusion
    signals = detector.detect(canonical_ds, data_quality_score=0.45)
    assert len(signals) == 0
