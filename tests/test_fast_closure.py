"""
Unit tests for FR-030 Fast Closure execution-gap detector.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.execution_gap.fast_closure import FastClosureDetector
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import Alert, AlertStatus, Asset, AssetCriticality, Case, Closure, CSE, Investigation, Severity


def test_fast_closure_detects_anomaly():
    ver_id = uuid4()
    cse_id = uuid4()
    asset_id = uuid4()
    rep_id = uuid4()
    now = datetime.now(timezone.utc)

    cse = CSE(
        cse_id=cse_id,
        name="Test Power Entity",
        sector="Power",
        scale="large",
        reporting_period_id=rep_id,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    asset = Asset(
        asset_id=asset_id,
        cse_id=cse_id,
        criticality=AssetCriticality.CRITICAL,
        asset_type="SCADA",
        environment="Grid",
        dataset_version_id=ver_id,
        ingest_time=now,
    )

    alerts = []
    cases = []
    closures = []
    investigations = []

    # Normal baseline alerts (45 minutes, 5 evidence items)
    for i in range(10):
        alt_id = uuid4()
        c_id = uuid4()
        start = now - timedelta(hours=i + 5)
        end = start + timedelta(minutes=45)
        
        alerts.append(
            Alert(
                alert_id=alt_id,
                cse_id=cse_id,
                asset_id=asset_id,
                reporting_period_id=rep_id,
                event_time=start,
                severity=Severity.HIGH,
                alert_category="Auth",
                source="SIEM",
                status=AlertStatus.CLOSED,
                dataset_version_id=ver_id,
                ingest_time=now,
            )
        )
        cases.append(
            Case(
                case_id=c_id,
                alert_id=alt_id,
                opened_at=start,
                closed_at=end,
                severity=Severity.HIGH,
                dataset_version_id=ver_id,
                ingest_time=now,
            )
        )
        closures.append(
            Closure(
                closure_id=uuid4(),
                case_id=c_id,
                closed_at=end,
                reason="Resolved",
                dataset_version_id=ver_id,
                ingest_time=now,
            )
        )
        investigations.append(
            Investigation(
                investigation_id=uuid4(),
                alert_id=alt_id,
                started_at=start,
                ended_at=end,
                evidence_count=5,
                dataset_version_id=ver_id,
                ingest_time=now,
            )
        )

    # Injected rapid closure anomaly (2 minutes, 0 evidence)
    alt_anom = uuid4()
    c_anom = uuid4()
    start_anom = now - timedelta(hours=1)
    end_anom = start_anom + timedelta(minutes=2)

    alerts.append(
        Alert(
            alert_id=alt_anom,
            cse_id=cse_id,
            asset_id=asset_id,
            reporting_period_id=rep_id,
            event_time=start_anom,
            severity=Severity.CRITICAL,
            alert_category="Intrusion",
            source="EDR",
            status=AlertStatus.CLOSED,
            dataset_version_id=ver_id,
            ingest_time=now,
        )
    )
    cases.append(
        Case(
            case_id=c_anom,
            alert_id=alt_anom,
            opened_at=start_anom,
            closed_at=end_anom,
            severity=Severity.CRITICAL,
            dataset_version_id=ver_id,
            ingest_time=now,
        )
    )
    closures.append(
        Closure(
            closure_id=uuid4(),
            case_id=c_anom,
            closed_at=end_anom,
            reason="Quick Close",
            dataset_version_id=ver_id,
            ingest_time=now,
        )
    )
    investigations.append(
        Investigation(
            investigation_id=uuid4(),
            alert_id=alt_anom,
            started_at=start_anom,
            ended_at=end_anom,
            evidence_count=0,
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
        closures=closures,
        investigations=investigations,
    )

    reconstructed_ds = ReconstructedDataset(canonical_ds)
    bm_engine = PeerBenchmarkEngine(reconstructed_ds)
    detector = FastClosureDetector(mad_multiplier=2.0)

    signals = detector.detect(reconstructed_ds, bm_engine)
    assert len(signals) >= 1
    assert any(s.workflow.alert.alert_id == alt_anom for s in signals)
    assert signals[0].evidence_refs[0].entity_type == "alert"
