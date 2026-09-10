"""
Comprehensive tests for Data Trust downstream inference control.
Verifies that Data Quality strictly governs:
  1. Negative-space inference (low DQ blocks false blind spot conclusions).
  2. Absence-based confidence scaling (low coverage/completeness reduces confidence in missing-record hypotheses).
  3. Review prioritization (low DQ or insufficient evidence caps priority).
  4. Non-hallucination of missing evidence (missing source records do not become positive security findings).
  5. Explicit inference states (SUPPORTED, WEAKLY_SUPPORTED, INSUFFICIENT_EVIDENCE, NOT_ASSESSABLE).
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.data_quality.quality_score import (
    DataQualityComponents as RawDataQualityComponents,
    DataQualityInputs,
    DataQualityResult,
    compute_data_quality_score,
)
from analytics.explainability.templates import generate_finding_explanation
from analytics.execution_gap.escalation_gap import EscalationGapSignal
from analytics.execution_gap.fast_closure import FastClosureSignal
from analytics.execution_gap.repeated_unresolved import RepeatedUnresolvedSignal
from analytics.fusion.evidence_fusion import (
    EvidenceFusionEngine,
    determine_evidence_sufficiency_state,
)
from analytics.negative_space.coverage_gap import CoverageGapDetector, CoverageGapSignal
from analytics.workflow.workflow_reconstruction import ReconstructedDataset, ReconstructedWorkflow
from backend.models.canonical import (
    Alert,
    AlertStatus,
    Asset,
    AssetCriticality,
    Case,
    Closure,
    CoverageObservation,
    CSE,
    DataQualityComponents,
    DataQualityScore,
    EvidenceRef,
    EvidenceSufficiencyState,
    ExpectationBasis,
    Finding,
    FindingType,
    Investigation,
    ReportingPeriod,
    Severity,
)


def _make_sample_dq_result(
    score: float,
    completeness: float = 1.0,
    consistency: float = 1.0,
    coverage: float = 1.0,
    sample_sufficiency: float = 1.0,
    ver_id=None,
) -> DataQualityResult:
    v_id = ver_id or uuid4()
    return DataQualityResult(
        dataset_version_id=v_id,
        score=score,
        components=RawDataQualityComponents(
            completeness_ratio=completeness,
            consistency_ratio=consistency,
            coverage_ratio=coverage,
            sample_sufficiency_ratio=sample_sufficiency,
        ),
        ruleset_version="V1",
        computed_at=datetime.now(timezone.utc),
        warnings=[],
    )


def test_high_dq_true_coverage_gap():
    """High DQ (0.90) + true silence on critical asset -> SUPPORTED finding with high confidence and priority."""
    ver_id = uuid4()
    cse_id = uuid4()
    asset_id = uuid4()
    rep_id = uuid4()
    now = datetime.now(timezone.utc)

    cse = CSE(
        cse_id=cse_id,
        name="Nuclear Control Center",
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
        asset_type="SCADA Safety System",
        environment="Grid",
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    obs = CoverageObservation(
        observation_id=uuid4(),
        cse_id=cse_id,
        asset_id=asset_id,
        alert_category="Safety Bypass",
        period_id=rep_id,
        expected_count=60.0,
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

    detector = CoverageGapDetector(min_data_quality_to_flag=0.70)
    signals = detector.detect(canonical_ds, data_quality_score=0.90)
    assert len(signals) == 1
    assert signals[0].assessment_state == EvidenceSufficiencyState.SUPPORTED

    dq_res = _make_sample_dq_result(score=0.90, completeness=0.95, consistency=0.95, coverage=0.90, sample_sufficiency=1.0)
    engine = EvidenceFusionEngine()
    findings = engine.fuse_signals(
        cse_id=cse_id,
        reporting_period_id=rep_id,
        dataset_version_id=ver_id,
        analysis_run_id=uuid4(),
        data_quality_result=dq_res,
        fast_closures=[],
        escalation_gaps=[],
        repeated_unresolved=[],
        coverage_gaps=signals,
    )

    assert len(findings) == 1
    f = findings[0]
    assert f.finding_type == FindingType.COVERAGE_GAP
    assert f.evidence_state == EvidenceSufficiencyState.SUPPORTED
    assert f.evidentiary_confidence >= 0.75
    # Contract validation succeeds
    assert len(f.validate_finding_generation_contract()) == 0


def test_low_dq_apparent_coverage_gap():
    """Low DQ (0.45) + apparent silence -> Suppressed by detector, preventing false positive security finding."""
    ver_id = uuid4()
    cse_id = uuid4()
    asset_id = uuid4()
    rep_id = uuid4()
    now = datetime.now(timezone.utc)

    cse = CSE(
        cse_id=cse_id,
        name="Outage Substation",
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
        asset_type="Telemetry Controller",
        environment="Grid",
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    obs = CoverageObservation(
        observation_id=uuid4(),
        cse_id=cse_id,
        asset_id=asset_id,
        alert_category="Grid Monitoring",
        period_id=rep_id,
        expected_count=60.0,
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

    detector = CoverageGapDetector(min_data_quality_to_flag=0.70)
    # Low DQ score (0.45 < 0.70)
    signals = detector.detect(canonical_ds, data_quality_score=0.45)
    # Detector MUST NOT emit signals during data outage
    assert len(signals) == 0


def test_missing_critical_source_escalation_gap_not_assessable():
    """When critical escalation data is missing due to low completeness/coverage, state is NOT_ASSESSABLE and confidence is heavily penalized."""
    cse_id = uuid4()
    rep_id = uuid4()
    ver_id = uuid4()
    now = datetime.now(timezone.utc)

    alert = Alert(
        alert_id=uuid4(),
        cse_id=cse_id,
        asset_id=uuid4(),
        reporting_period_id=rep_id,
        event_time=now,
        severity=Severity.CRITICAL,
        alert_category="Ransomware",
        source="EDR",
        status=AlertStatus.CLOSED,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    wf = ReconstructedWorkflow(alert=alert)
    sig = EscalationGapSignal(
        cse_id=cse_id,
        workflow=wf,
        severity=Severity.CRITICAL,
        asset_criticality=AssetCriticality.CRITICAL,
        alert_category="Ransomware",
        evidence_refs=[EvidenceRef(entity_type="alert", entity_id=alert.alert_id)],
    )

    # Degraded completeness (0.40) & low overall DQ (0.48) representing missing source table
    dq_res = _make_sample_dq_result(score=0.48, completeness=0.40, consistency=0.60, coverage=0.45, sample_sufficiency=0.8)

    engine = EvidenceFusionEngine()
    findings = engine.fuse_signals(
        cse_id=cse_id,
        reporting_period_id=rep_id,
        dataset_version_id=ver_id,
        analysis_run_id=uuid4(),
        data_quality_result=dq_res,
        fast_closures=[],
        escalation_gaps=[sig],
        repeated_unresolved=[],
        coverage_gaps=[],
    )

    assert len(findings) == 1
    f = findings[0]
    assert f.evidence_state == EvidenceSufficiencyState.NOT_ASSESSABLE
    # Priority score is capped at low tier (<= 0.30)
    assert f.priority_score <= 0.30
    assert f.evidentiary_confidence <= 0.30
    # Contradicting signals document data trust failure
    assert any("Data trust failure" in s for s in f.contradicting_signals)
    # Cannot be persisted as High priority
    violations = f.validate_finding_generation_contract()
    assert any("NOT_ASSESSABLE" in v for v in violations)


def test_sparse_sample_yields_insufficient_evidence():
    """When sample sufficiency is very low (e.g. 0.15, N < 5), state is INSUFFICIENT_EVIDENCE."""
    cse_id = uuid4()
    rep_id = uuid4()
    ver_id = uuid4()
    now = datetime.now(timezone.utc)

    alert = Alert(
        alert_id=uuid4(),
        cse_id=cse_id,
        asset_id=uuid4(),
        reporting_period_id=rep_id,
        event_time=now,
        severity=Severity.CRITICAL,
        alert_category="Triage",
        source="SIEM",
        status=AlertStatus.CLOSED,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    inv = Investigation(
        investigation_id=uuid4(),
        alert_id=alert.alert_id,
        started_at=now,
        ended_at=now + timedelta(seconds=120),
        evidence_count=1,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    wf = ReconstructedWorkflow(alert=alert, investigation=inv)

    sig = FastClosureSignal(
        cse_id=cse_id,
        workflow=wf,
        closure_duration_seconds=120.0,
        evidence_count=1,
        peer_median_duration=1800.0,
        peer_mad_duration=400.0,
        threshold_duration=800.0,
        peer_p25_evidence=4.0,
        z_score=4.2,
        evidence_refs=[EvidenceRef(entity_type="alert", entity_id=alert.alert_id)],
    )

    # Sparse sample sufficiency (0.15)
    dq_res = _make_sample_dq_result(score=0.72, completeness=0.95, consistency=0.95, coverage=0.90, sample_sufficiency=0.15)

    engine = EvidenceFusionEngine()
    findings = engine.fuse_signals(
        cse_id=cse_id,
        reporting_period_id=rep_id,
        dataset_version_id=ver_id,
        analysis_run_id=uuid4(),
        data_quality_result=dq_res,
        fast_closures=[sig],
        escalation_gaps=[],
        repeated_unresolved=[],
        coverage_gaps=[],
    )

    assert len(findings) == 1
    f = findings[0]
    assert f.evidence_state == EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE
    assert f.priority_score <= 0.45


def test_low_coverage_reduces_absence_based_confidence():
    """Lower coverage mathematically reduces confidence in absence-based findings."""
    cse_id = uuid4()
    rep_id = uuid4()
    ver_id = uuid4()
    now = datetime.now(timezone.utc)

    alert = Alert(
        alert_id=uuid4(),
        cse_id=cse_id,
        asset_id=uuid4(),
        reporting_period_id=rep_id,
        event_time=now,
        severity=Severity.CRITICAL,
        alert_category="Ransomware",
        source="EDR",
        status=AlertStatus.CLOSED,
        dataset_version_id=ver_id,
        ingest_time=now,
    )
    wf = ReconstructedWorkflow(alert=alert)
    sig = EscalationGapSignal(
        cse_id=cse_id,
        workflow=wf,
        severity=Severity.CRITICAL,
        asset_criticality=AssetCriticality.CRITICAL,
        alert_category="Ransomware",
        evidence_refs=[EvidenceRef(entity_type="alert", entity_id=alert.alert_id)],
    )

    # Dataset A: High coverage (1.0)
    dq_high_cov = _make_sample_dq_result(score=0.88, completeness=0.90, consistency=0.90, coverage=1.0, sample_sufficiency=0.85)
    # Dataset B: Low coverage (0.55)
    dq_low_cov = _make_sample_dq_result(score=0.72, completeness=0.90, consistency=0.90, coverage=0.55, sample_sufficiency=0.85)

    engine = EvidenceFusionEngine()
    findings_high = engine.fuse_signals(
        cse_id=cse_id,
        reporting_period_id=rep_id,
        dataset_version_id=ver_id,
        analysis_run_id=uuid4(),
        data_quality_result=dq_high_cov,
        fast_closures=[],
        escalation_gaps=[sig],
        repeated_unresolved=[],
        coverage_gaps=[],
    )
    findings_low = engine.fuse_signals(
        cse_id=cse_id,
        reporting_period_id=rep_id,
        dataset_version_id=ver_id,
        analysis_run_id=uuid4(),
        data_quality_result=dq_low_cov,
        fast_closures=[],
        escalation_gaps=[sig],
        repeated_unresolved=[],
        coverage_gaps=[],
    )

    conf_high = findings_high[0].evidentiary_confidence
    conf_low = findings_low[0].evidentiary_confidence

    assert conf_high > conf_low
    assert findings_high[0].evidence_state == EvidenceSufficiencyState.SUPPORTED
    assert findings_low[0].evidence_state == EvidenceSufficiencyState.WEAKLY_SUPPORTED


def test_explainability_template_renders_explicit_state_and_guidance():
    """Explainability template includes evidence_state and outputs targeted guidance for non-assessable states."""
    f = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.ESCALATION_GAP,
        priority_score=0.25,
        priority_components={"signal_strength": 0.5, "peer_deviation": 0.5, "persistence": 0.5, "asset_criticality": 1.0, "data_uncertainty": 0.6},
        evidentiary_confidence=0.20,
        data_quality_status=DataQualityScore(
            dataset_version_id=uuid4(),
            score=0.40,
            components=DataQualityComponents(completeness_ratio=0.3, consistency_ratio=0.4, coverage_ratio=0.4, sample_sufficiency_ratio=0.5),
            ruleset_version="V1",
            computed_at=datetime.now(timezone.utc),
        ),
        evidence_state=EvidenceSufficiencyState.NOT_ASSESSABLE,
        expectation_basis=ExpectationBasis.HARD_REQUIREMENT,
        expected_behavior="Expected escalation record",
        observed_behavior="No escalation record found",
        supporting_signals=["Signal 1", "Signal 2"],
        contradicting_signals=["Data trust failure: telemetry outage"],
        evidence_refs=[EvidenceRef(entity_type="alert", entity_id=uuid4())],
        analytical_method="Policy conformance evaluation",
        ruleset_version="V1",
        dataset_version_id=uuid4(),
        analysis_run_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    explanation = generate_finding_explanation(f)
    assert explanation["evidence_state"] == "NOT_ASSESSABLE"
    assert "Do not initiate disciplinary" in explanation["recommended_action"]
    assert "log ingestion pipelines" in explanation["recommended_action"]
