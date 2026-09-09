"""
Unit tests for Investigation Sufficiency Execution-Gap Detector (FR-031).
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.execution_gap.investigation_sufficiency import InvestigationSufficiencyDetector
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import Alert, AlertStatus, CSE, Investigation, Severity


def test_investigation_sufficiency_flags_zero_evidence():
    v_id = uuid4()
    p_id = uuid4()
    cse_id = uuid4()
    now = datetime.now(timezone.utc)

    cse = CSE(
        dataset_version_id=v_id,
        ingest_time=now,
        cse_id=cse_id,
        name="Power Corp Alpha",
        sector="Power & Energy",
        scale="large",
        reporting_period_id=p_id,
    )

    alert = Alert(
        dataset_version_id=v_id,
        ingest_time=now,
        alert_id=uuid4(),
        cse_id=cse_id,
        asset_id=uuid4(),
        reporting_period_id=p_id,
        event_time=now,
        severity=Severity.CRITICAL,
        alert_category="SCADA_ANOMALY",
        source="SIEM_CORE",
        status=AlertStatus.CLOSED,
    )

    # Investigation with 0 evidence and 10s duration
    inv = Investigation(
        dataset_version_id=v_id,
        ingest_time=now,
        investigation_id=uuid4(),
        alert_id=alert.alert_id,
        started_at=now,
        ended_at=now + timedelta(seconds=10),
        analyst_id="ANALYST_01",
        evidence_count=0,
        disposition="FALSE_POSITIVE",
    )

    canonical_ds = CanonicalDataset(
        dataset_version_id=v_id,
        cse_list=[cse],
        reporting_periods=[],
        assets=[],
        alerts=[alert],
        investigations=[inv],
        cases=[],
        escalations=[],
        actions=[],
        closures=[],
        coverage_observations=[],
    )

    reconstructed_ds = ReconstructedDataset(canonical_ds)
    bm_engine = PeerBenchmarkEngine(reconstructed_ds)
    detector = InvestigationSufficiencyDetector(min_required_evidence=1, min_investigation_duration_seconds=60.0)

    signals = detector.detect(reconstructed_ds, bm_engine)
    assert len(signals) == 1
    assert signals[0].cse_id == cse_id
    assert signals[0].evidence_count == 0
