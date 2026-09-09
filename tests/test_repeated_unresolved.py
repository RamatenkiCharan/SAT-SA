"""
Unit tests for FR-033 Repeated Unresolved Alerts detector.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.execution_gap.repeated_unresolved import RepeatedUnresolvedDetector
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import Action, Alert, AlertStatus, Asset, AssetCriticality, Case, CSE, Severity


def test_repeated_unresolved_alerts_detected():
    ver_id = uuid4()
    cse_id = uuid4()
    asset_id = uuid4()
    rep_id = uuid4()
    now = datetime.now(timezone.utc)

    cse = CSE(
        cse_id=cse_id,
        name="Telecom Core",
        sector="Telecom",
        scale="large",
        reporting_period_id=rep_id,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    asset = Asset(
        asset_id=asset_id,
        cse_id=cse_id,
        criticality=AssetCriticality.CRITICAL,
        asset_type="BGP Router",
        environment="Core",
        dataset_version_id=ver_id,
        ingest_time=now,
    )

    alerts = []
    cases = []
    # 3 repeated alerts in same category over 10 days, NO remediation actions
    for i in range(3):
        alt_id = uuid4()
        c_id = uuid4()
        ev_time = now - timedelta(days=i * 3)

        alerts.append(
            Alert(
                alert_id=alt_id,
                cse_id=cse_id,
                asset_id=asset_id,
                reporting_period_id=rep_id,
                event_time=ev_time,
                severity=Severity.HIGH,
                alert_category="BGP Hijack",
                source="Router Syslog",
                status=AlertStatus.CLOSED,
                dataset_version_id=ver_id,
                ingest_time=now,
            )
        )
        cases.append(
            Case(
                case_id=c_id,
                alert_id=alt_id,
                opened_at=ev_time,
                closed_at=ev_time + timedelta(hours=1),
                severity=Severity.HIGH,
                dataset_version_id=ver_id,
                ingest_time=now,
            )
        )

    canonical_ds = CanonicalDataset(
        dataset_version_id=ver_id,
        cse_list=[cse],
        assets=[asset],
        alerts=alerts,
        cases=cases,
        actions=[],  # No actions!
    )

    reconstructed_ds = ReconstructedDataset(canonical_ds)
    detector = RepeatedUnresolvedDetector(min_occurrences=3, window_days=30)
    signals = detector.detect(reconstructed_ds)

    assert len(signals) == 1
    assert signals[0].alert_count == 3
    assert signals[0].alert_category == "BGP Hijack"
