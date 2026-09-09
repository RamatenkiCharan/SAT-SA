"""
Unit tests for FR-032 Escalation Gap execution-gap detector.
"""
from datetime import datetime, timezone
from uuid import uuid4

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.execution_gap.escalation_gap import EscalationGapDetector
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import Alert, AlertStatus, Asset, AssetCriticality, Case, CSE, Escalation, Severity


def test_escalation_gap_detects_unresolved_critical_alert():
    ver_id = uuid4()
    cse_id = uuid4()
    asset_id = uuid4()
    rep_id = uuid4()
    now = datetime.now(timezone.utc)

    cse = CSE(
        cse_id=cse_id,
        name="Test Bank",
        sector="Financial",
        scale="large",
        reporting_period_id=rep_id,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    asset = Asset(
        asset_id=asset_id,
        cse_id=cse_id,
        criticality=AssetCriticality.CRITICAL,
        asset_type="Core Ledger",
        environment="Prod",
        dataset_version_id=ver_id,
        ingest_time=now,
    )

    alt_id = uuid4()
    case_id = uuid4()

    alert = Alert(
        alert_id=alt_id,
        cse_id=cse_id,
        asset_id=asset_id,
        reporting_period_id=rep_id,
        event_time=now,
        severity=Severity.CRITICAL,
        alert_category="Ransomware",
        source="EDR",
        status=AlertStatus.CLOSED,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    case = Case(
        case_id=case_id,
        alert_id=alt_id,
        opened_at=now,
        closed_at=now,
        severity=Severity.CRITICAL,
        dataset_version_id=ver_id,
        ingest_time=now,
    )

    canonical_ds = CanonicalDataset(
        dataset_version_id=ver_id,
        cse_list=[cse],
        assets=[asset],
        alerts=[alert],
        cases=[case],
        escalations=[],  # Missing escalation!
    )

    reconstructed_ds = ReconstructedDataset(canonical_ds)
    detector = EscalationGapDetector()
    signals = detector.detect(reconstructed_ds)

    assert len(signals) == 1
    assert signals[0].workflow.alert.alert_id == alt_id
    assert signals[0].severity == Severity.CRITICAL


def test_escalation_gap_ignores_escalated_case():
    ver_id = uuid4()
    cse_id = uuid4()
    asset_id = uuid4()
    rep_id = uuid4()
    now = datetime.now(timezone.utc)

    cse = CSE(
        cse_id=cse_id,
        name="Test Bank",
        sector="Financial",
        scale="large",
        reporting_period_id=rep_id,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    asset = Asset(
        asset_id=asset_id,
        cse_id=cse_id,
        criticality=AssetCriticality.CRITICAL,
        asset_type="Core Ledger",
        environment="Prod",
        dataset_version_id=ver_id,
        ingest_time=now,
    )

    alt_id = uuid4()
    case_id = uuid4()
    esc_id = uuid4()

    alert = Alert(
        alert_id=alt_id,
        cse_id=cse_id,
        asset_id=asset_id,
        reporting_period_id=rep_id,
        event_time=now,
        severity=Severity.CRITICAL,
        alert_category="Ransomware",
        source="EDR",
        status=AlertStatus.CLOSED,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    case = Case(
        case_id=case_id,
        alert_id=alt_id,
        opened_at=now,
        closed_at=now,
        severity=Severity.CRITICAL,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    escalation = Escalation(
        escalation_id=esc_id,
        case_id=case_id,
        escalated_at=now,
        level="Tier 2",
        target="Senior IR Lead",
        dataset_version_id=ver_id,
        ingest_time=now,
    )

    canonical_ds = CanonicalDataset(
        dataset_version_id=ver_id,
        cse_list=[cse],
        assets=[asset],
        alerts=[alert],
        cases=[case],
        escalations=[escalation],
    )

    reconstructed_ds = ReconstructedDataset(canonical_ds)
    detector = EscalationGapDetector()
    signals = detector.detect(reconstructed_ds)

    assert len(signals) == 0
