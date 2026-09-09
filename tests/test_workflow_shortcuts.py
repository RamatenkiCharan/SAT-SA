"""
Unit tests for Workflow Shortcuts Detector (FR-034).
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.execution_gap.workflow_shortcuts import WorkflowShortcutDetector
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import Alert, AlertStatus, Case, Closure, CSE, Severity


def test_workflow_shortcut_detects_skipped_investigation():
    v_id = uuid4()
    p_id = uuid4()
    cse_id = uuid4()
    case_id = uuid4()
    now = datetime.now(timezone.utc)

    cse = CSE(
        dataset_version_id=v_id,
        ingest_time=now,
        cse_id=cse_id,
        name="Transit Authority",
        sector="Transportation",
        scale="medium",
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
        alert_category="SIGNALING_UNAUTHORIZED_ACCESS",
        source="EDR_CORP",
        status=AlertStatus.CLOSED,
    )

    case = Case(
        dataset_version_id=v_id,
        ingest_time=now,
        case_id=case_id,
        alert_id=alert.alert_id,
        opened_at=now,
        severity=Severity.CRITICAL,
    )

    closure = Closure(
        dataset_version_id=v_id,
        ingest_time=now,
        closure_id=uuid4(),
        case_id=case_id,
        closed_at=now + timedelta(minutes=2),
        reason="Auto-dismissed",
    )

    canonical_ds = CanonicalDataset(
        dataset_version_id=v_id,
        cse_list=[cse],
        reporting_periods=[],
        assets=[],
        alerts=[alert],
        investigations=[],  # Skipped completely
        cases=[case],
        escalations=[],
        actions=[],
        closures=[closure],
        coverage_observations=[],
    )

    reconstructed_ds = ReconstructedDataset(canonical_ds)
    detector = WorkflowShortcutDetector()

    signals = detector.detect(reconstructed_ds)
    assert len(signals) == 1
    assert signals[0].shortcut_type == "SKIPPED_INVESTIGATION"
    assert signals[0].cse_id == cse_id
