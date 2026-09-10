"""
Comprehensive Audit & Snapshot Tests for Explainability Engine (SRS §11, §24, §52).

Verifies:
1. Strict determinism: Running generate_finding_explanation on the same finding always produces the identical output.
2. Non-LLM execution: 100% template substitution without generative models or hallucinations.
3. Type-specific template selection across all detector classes:
   - FAST_CLOSURE
   - ESCALATION_GAP
   - REPEATED_UNRESOLVED_ALERTS
   - COVERAGE_GAP
4. Correct insertion of empirical finding values (metrics, signals, counts, peer stats, DQ ratios).
5. All 6 mandatory explanation dimensions are present:
   - what happened
   - why it was flagged
   - supporting evidence
   - confidence
   - relevant peer context
   - DQ limitation where relevant
6. Strict fidelity: Never claims evidence that does not exist (explicit policy absence / silence reporting).
7. Representative snapshot assertions for all finding types and degraded telemetry states.
"""
from datetime import datetime, timezone
from uuid import UUID, uuid4
import pytest

from analytics.explainability.templates import generate_finding_explanation
from backend.models.canonical import (
    DataQualityComponents,
    DataQualityScore,
    EvidenceRef,
    EvidenceSufficiencyState,
    ExpectationBasis,
    Finding,
    FindingType,
)


@pytest.fixture
def high_dq_fixture():
    ver_id = uuid4()
    return DataQualityScore(
        dataset_version_id=ver_id,
        score=0.92,
        components=DataQualityComponents(
            completeness_ratio=0.95,
            consistency_ratio=0.98,
            coverage_ratio=0.88,
            sample_sufficiency_ratio=0.90,
        ),
        ruleset_version="V1",
        computed_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def degraded_dq_fixture():
    ver_id = uuid4()
    return DataQualityScore(
        dataset_version_id=ver_id,
        score=0.42,
        components=DataQualityComponents(
            completeness_ratio=0.40,
            consistency_ratio=0.45,
            coverage_ratio=0.35,
            sample_sufficiency_ratio=0.30,
        ),
        ruleset_version="V1",
        computed_at=datetime.now(timezone.utc),
    )


# =============================================================================
# 1. Strict Determinism Verification (Success Condition)
# =============================================================================

def test_explainability_strict_determinism(high_dq_fixture):
    """
    SUCCESS CONDITION: Running generate_finding_explanation on the same finding twice
    (and across 50 iterations) produces bit-identical explanation outputs.
    """
    now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    fixed_id = UUID("11111111-1111-1111-1111-111111111111")
    cse_id = UUID("22222222-2222-2222-2222-222222222222")

    finding = Finding(
        finding_id=fixed_id,
        cse_id=cse_id,
        reporting_period_id=UUID("33333333-3333-3333-3333-333333333333"),
        finding_type=FindingType.FAST_CLOSURE,
        priority_score=0.88,
        priority_components={
            "signal_strength": 0.85,
            "peer_deviation": 0.90,
            "persistence": 0.75,
            "asset_criticality": 1.0,
            "data_uncertainty": 0.08,
        },
        evidentiary_confidence=0.95,
        data_quality_status=high_dq_fixture,
        evidence_state=EvidenceSufficiencyState.SUPPORTED,
        expectation_basis=ExpectationBasis.STATISTICAL_BASELINE,
        expected_behavior="Expected ~45.0 min median duration",
        observed_behavior="Observed 18 critical cases closed in median 3.2 min",
        supporting_signals=[
            "18 critical alerts closed rapidly",
            "Peer deviation |z| = 3.2 relative to sector cohort",
        ],
        contradicting_signals=[],
        evidence_refs=[
            EvidenceRef(entity_type="alert", entity_id=uuid4(), source_record_ref="ALT-001"),
            EvidenceRef(entity_type="case", entity_id=uuid4(), source_record_ref="CASE-001"),
        ],
        peer_context="Sector median triage time: 45.0 min (MAD: 12.5, Cohort N: 8)",
        temporal_context="Observed persistent rapid closure across 3 consecutive shifts",
        analytical_method="Peer MAD Outlier Detection",
        ruleset_version="V1",
        dataset_version_id=high_dq_fixture.dataset_version_id,
        analysis_run_id=UUID("44444444-4444-4444-4444-444444444444"),
        created_at=now,
    )

    baseline_exp = generate_finding_explanation(finding)

    for _ in range(50):
        test_exp = generate_finding_explanation(finding)
        assert test_exp == baseline_exp


# =============================================================================
# 2. Snapshot Test: Fast Closure Execution Gap (FR-030)
# =============================================================================

def test_snapshot_fast_closure_explanation(high_dq_fixture):
    """
    Verifies that Fast Closure findings generate the correct snapshot structure
    with actual empirical numbers inserted into all 6 core explanation dimensions.
    """
    finding = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.FAST_CLOSURE,
        priority_score=0.84,
        priority_components={
            "signal_strength": 0.8,
            "peer_deviation": 0.9,
            "persistence": 0.7,
            "asset_criticality": 1.0,
            "data_uncertainty": 0.08,
        },
        evidentiary_confidence=0.92,
        data_quality_status=high_dq_fixture,
        evidence_state=EvidenceSufficiencyState.SUPPORTED,
        expectation_basis=ExpectationBasis.STATISTICAL_BASELINE,
        expected_behavior="Expected ~50.0 min median duration",
        observed_behavior="Observed 14 critical cases closed in median 3.5 min",
        supporting_signals=[
            "14 critical alerts closed rapidly",
            "Peer deviation |z| = 2.9 relative to sector cohort",
        ],
        contradicting_signals=[],
        evidence_refs=[
            EvidenceRef(entity_type="alert", entity_id=uuid4()),
            EvidenceRef(entity_type="case", entity_id=uuid4()),
        ],
        peer_context="Power Sector Median: 50.0 min (MAD: 14.0 min, N=7 peers)",
        temporal_context="Recurrent across 30-day reporting window",
        analytical_method="Peer MAD Outlier Detection",
        ruleset_version="V1",
        dataset_version_id=high_dq_fixture.dataset_version_id,
        analysis_run_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    exp = generate_finding_explanation(finding)

    # 1. Headline & Priority
    assert exp["priority_label"] == "HIGH"
    assert "Rapid-Closure" in exp["title"]
    assert "Critical incidents closed significantly faster" in exp["headline"]

    # 2. What Happened (Empirical Values Inserted)
    assert "14 critical cases closed in median 3.5 min" in exp["what_happened"]

    # 3. Why It Was Flagged
    assert "Fast Closure Detector (FR-030)" in exp["why_flagged"]
    assert "Goodhart's Law" in exp["why_flagged"]

    # 4. Supporting Evidence Summary
    assert "2 concrete alert and case records attached" in exp["supporting_evidence_summary"]
    assert "2 corroborating signals" in exp["supporting_evidence_summary"]

    # 5. Confidence Summary
    assert "Confidence: 92.0% [State: SUPPORTED]" in exp["confidence_summary"]

    # 6. Relevant Peer Context
    assert "Power Sector Median: 50.0 min" in exp["peer_context_summary"]

    # 7. DQ Limitation
    assert "Data quality is high (92.0%)" in exp["data_quality_limitation"]


# =============================================================================
# 3. Snapshot Test: Escalation Gap (FR-032) & Policy Absence
# =============================================================================

def test_snapshot_escalation_gap_explanation(high_dq_fixture):
    """
    Verifies that Escalation Gap findings explicitly assert policy absence
    and never claim escalation records exist when none do.
    """
    finding = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.ESCALATION_GAP,
        priority_score=0.81,
        priority_components={
            "signal_strength": 0.8,
            "peer_deviation": 0.7,
            "persistence": 0.8,
            "asset_criticality": 1.0,
            "data_uncertainty": 0.08,
        },
        evidentiary_confidence=0.90,
        data_quality_status=high_dq_fixture,
        evidence_state=EvidenceSufficiencyState.SUPPORTED,
        expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
        expected_behavior="Mandatory Tier-2/Tier-3 escalation for all Severity=CRITICAL alerts on SCADA assets",
        observed_behavior="0 of 12 critical SCADA alerts escalated to Tier 2 / IR leadership",
        supporting_signals=[
            "12 critical alerts closed without escalation record",
            "Target assets: SCADA EMS Energy Management Server",
        ],
        contradicting_signals=[],
        evidence_refs=[
            EvidenceRef(entity_type="alert", entity_id=uuid4()),
            EvidenceRef(entity_type="case", entity_id=uuid4()),
        ],
        peer_context="Supervisory compliance standard for critical infrastructure",
        temporal_context="Continuous absence over reporting period",
        analytical_method="Execution Gap State Graph",
        ruleset_version="V1",
        dataset_version_id=high_dq_fixture.dataset_version_id,
        analysis_run_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    exp = generate_finding_explanation(finding)

    assert exp["priority_label"] == "HIGH"
    assert "Critical Incident Escalation Gap" in exp["title"]
    assert "0 of 12 critical SCADA alerts escalated" in exp["what_happened"]
    assert "Escalation Gap Detector (FR-032)" in exp["why_flagged"]
    assert "Policy absence confirmed: 0 escalation handoffs logged" in exp["supporting_evidence_summary"]
    assert "Review SOC escalation procedures" in exp["recommended_action"]


# =============================================================================
# 4. Snapshot Test: Repeated Unresolved Threat Recurrence (FR-033)
# =============================================================================

def test_snapshot_repeated_unresolved_explanation(high_dq_fixture):
    """
    Verifies explanation structure for Repeated Unresolved Alerts.
    """
    finding = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.REPEATED_UNRESOLVED_ALERTS,
        priority_score=0.76,
        priority_components={
            "signal_strength": 0.7,
            "peer_deviation": 0.6,
            "persistence": 0.9,
            "asset_criticality": 1.0,
            "data_uncertainty": 0.08,
        },
        evidentiary_confidence=0.88,
        data_quality_status=high_dq_fixture,
        evidence_state=EvidenceSufficiencyState.SUPPORTED,
        expectation_basis=ExpectationBasis.STATISTICAL_BASELINE,
        expected_behavior="Remediation ticket deployment after >= 2 recurring alert triggers on critical assets",
        observed_behavior="Observed 9 identical SCADA brute-force alerts on Asset-101 within 5 days without engineering action",
        supporting_signals=[
            "9 recurrent alert firings",
            "Zero Action entity records attached to Case-501",
        ],
        contradicting_signals=[],
        evidence_refs=[
            EvidenceRef(entity_type="alert", entity_id=uuid4()),
            EvidenceRef(entity_type="case", entity_id=uuid4()),
        ],
        peer_context="Entity recurrence index 3.4x higher than Banking sector cohort median",
        temporal_context="Clustered in 5-day window",
        analytical_method="Temporal Recurrence Clustering",
        ruleset_version="V1",
        dataset_version_id=high_dq_fixture.dataset_version_id,
        analysis_run_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    exp = generate_finding_explanation(finding)

    assert exp["priority_label"] == "HIGH"
    assert "Unresolved Threat Recurrence" in exp["title"]
    assert "9 identical SCADA brute-force alerts on Asset-101" in exp["what_happened"]
    assert "Repeated Unresolved Alerts Detector (FR-033)" in exp["why_flagged"]
    assert "Request engineering ticket logs" in exp["recommended_action"]


# =============================================================================
# 5. Snapshot Test: Negative Space Coverage Gap (FR-041) with High DQ
# =============================================================================

def test_snapshot_coverage_gap_high_dq_explanation(high_dq_fixture):
    """
    Verifies negative-space coverage gap explanation when data quality is verified healthy.
    """
    finding = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.COVERAGE_GAP,
        priority_score=0.79,
        priority_components={
            "signal_strength": 0.8,
            "peer_deviation": 0.8,
            "persistence": 0.6,
            "asset_criticality": 1.0,
            "data_uncertainty": 0.08,
        },
        evidentiary_confidence=0.85,
        data_quality_status=high_dq_fixture,
        evidence_state=EvidenceSufficiencyState.SUPPORTED,
        expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
        expected_behavior="Expected ~40.0 telemetry events per month based on critical SCADA asset class",
        observed_behavior="Observed 0 telemetry events from Core Transmission RTU over 30 days",
        supporting_signals=[
            "Total silence on Tier-1 SCADA asset",
            "Telemetry ingestion pipeline health verified at 92.0% DQ score",
        ],
        contradicting_signals=[],
        evidence_refs=[
            EvidenceRef(entity_type="coverage_observation", entity_id=uuid4()),
        ],
        peer_context="Peer SCADA assets averaged 42.4 events/month",
        temporal_context="Silence persisted throughout 30-day reporting period",
        analytical_method="Negative-Space Observation Baseline",
        ruleset_version="V1",
        dataset_version_id=high_dq_fixture.dataset_version_id,
        analysis_run_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    exp = generate_finding_explanation(finding)

    assert exp["priority_label"] == "HIGH"
    assert "Negative-Space Monitoring Coverage Gap" in exp["title"]
    assert "Core Transmission RTU over 30 days" in exp["what_happened"]
    assert "Negative-Space Coverage Gap Detector (FR-041)" in exp["why_flagged"]
    assert "unmonitored blind spot" in exp["why_flagged"]
    assert "Perform sensor reachability and log forwarding audit" in exp["recommended_action"]


# =============================================================================
# 6. Degraded Data Quality: NOT_ASSESSABLE State
# =============================================================================

def test_snapshot_degraded_dq_not_assessable(degraded_dq_fixture):
    """
    Verifies that when data quality is degraded (DQ < 60%), negative-space findings
    render the NOT_ASSESSABLE guidance rather than false security accusations.
    """
    finding = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.COVERAGE_GAP,
        priority_score=0.35,
        priority_components={
            "signal_strength": 0.3,
            "peer_deviation": 0.0,
            "persistence": 0.2,
            "asset_criticality": 1.0,
            "data_uncertainty": 0.58,
        },
        evidentiary_confidence=0.20,
        data_quality_status=degraded_dq_fixture,
        evidence_state=EvidenceSufficiencyState.NOT_ASSESSABLE,
        expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
        expected_behavior="Expected regular sensor events",
        observed_behavior="Zero telemetry observed during active ingestion pipeline outage",
        supporting_signals=[],
        contradicting_signals=["Data quality failure: Ingestion dropouts detected"],
        evidence_refs=[],
        peer_context="Peer comparison suspended due to low DQ",
        temporal_context="Reporting window compromised",
        analytical_method="Negative-Space Observation Baseline",
        ruleset_version="V1",
        dataset_version_id=degraded_dq_fixture.dataset_version_id,
        analysis_run_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    exp = generate_finding_explanation(finding)

    assert exp["priority_label"] == "LOW"
    assert exp["evidence_state"] == "NOT_ASSESSABLE"
    assert "Data quality is degraded (42.0% < 60.0% threshold)" in exp["data_quality_limitation"]
    assert "Confidence: 20.0% [State: NOT_ASSESSABLE]" in exp["confidence_summary"]
    assert "Do not initiate disciplinary or operational compliance actions" in exp["recommended_action"]


# =============================================================================
# 7. Sparse Telemetry: INSUFFICIENT_EVIDENCE State
# =============================================================================

def test_snapshot_sparse_sample_insufficient_evidence(high_dq_fixture):
    """
    Verifies that sparse telemetry samples render INSUFFICIENT_EVIDENCE state
    and supervisory guidance to collect additional reporting cycles.
    """
    finding = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.FAST_CLOSURE,
        priority_score=0.45,
        priority_components={
            "signal_strength": 0.3,
            "peer_deviation": 0.4,
            "persistence": 0.1,
            "asset_criticality": 0.5,
            "data_uncertainty": 0.08,
        },
        evidentiary_confidence=0.35,
        data_quality_status=high_dq_fixture,
        evidence_state=EvidenceSufficiencyState.INSUFFICIENT_EVIDENCE,
        expectation_basis=ExpectationBasis.STATISTICAL_BASELINE,
        expected_behavior="Expected regular case triage",
        observed_behavior="Observed 1 case closed quickly in small sample of 2 total cases",
        supporting_signals=["1 rapid closure"],
        contradicting_signals=["Sparse sample size (N=2)"],
        evidence_refs=[],
        peer_context="Sample size insufficient for reliable peer z-score",
        temporal_context="Single observation",
        analytical_method="Peer MAD Outlier Detection",
        ruleset_version="V1",
        dataset_version_id=high_dq_fixture.dataset_version_id,
        analysis_run_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    exp = generate_finding_explanation(finding)

    assert exp["priority_label"] == "LOW"
    assert exp["evidence_state"] == "INSUFFICIENT_EVIDENCE"
    assert "Confidence: 35.0% [State: INSUFFICIENT_EVIDENCE]" in exp["confidence_summary"]
    assert "Collect additional reporting periods of telemetry" in exp["recommended_action"]


# =============================================================================
# 8. Never Claim Evidence That Does Not Exist (Absence Fidelity)
# =============================================================================

def test_never_claims_nonexistent_evidence(high_dq_fixture):
    """
    Verifies that when evidence_refs is empty, the explanation explicitly states
    zero records/absence rather than claiming positive evidence was discovered.
    """
    # Test for Escalation Gap with 0 evidence refs
    f_esc = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.ESCALATION_GAP,
        priority_score=0.70,
        priority_components={"signal_strength": 0.7, "peer_deviation": 0.5, "persistence": 0.7, "asset_criticality": 1.0, "data_uncertainty": 0.08},
        evidentiary_confidence=0.85,
        data_quality_status=high_dq_fixture,
        evidence_state=EvidenceSufficiencyState.SUPPORTED,
        expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
        expected_behavior="Mandatory escalation",
        observed_behavior="No escalation logged",
        supporting_signals=[],
        contradicting_signals=[],
        evidence_refs=[],
        peer_context="Compliance standard",
        temporal_context="Active period",
        analytical_method="Execution Gap",
        ruleset_version="V1",
        dataset_version_id=high_dq_fixture.dataset_version_id,
        analysis_run_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )
    exp_esc = generate_finding_explanation(f_esc)
    assert "Zero escalation records exist" in exp_esc["supporting_evidence_summary"]

    # Test for Fast Closure with 0 evidence refs
    f_fast = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.FAST_CLOSURE,
        priority_score=0.70,
        priority_components={"signal_strength": 0.7, "peer_deviation": 0.5, "persistence": 0.7, "asset_criticality": 1.0, "data_uncertainty": 0.08},
        evidentiary_confidence=0.85,
        data_quality_status=high_dq_fixture,
        evidence_state=EvidenceSufficiencyState.SUPPORTED,
        expectation_basis=ExpectationBasis.STATISTICAL_BASELINE,
        expected_behavior="Expected baseline",
        observed_behavior="Fast closures without investigation",
        supporting_signals=[],
        contradicting_signals=[],
        evidence_refs=[],
        peer_context="Peer MAD",
        temporal_context="Active period",
        analytical_method="Execution Gap",
        ruleset_version="V1",
        dataset_version_id=high_dq_fixture.dataset_version_id,
        analysis_run_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )
    exp_fast = generate_finding_explanation(f_fast)
    assert "Zero attached investigation notes" in exp_fast["supporting_evidence_summary"]


# =============================================================================
# 9. Completeness of All 6 Mandatory Dimensions
# =============================================================================

def test_all_six_required_dimensions_present_across_all_findings(high_dq_fixture):
    """
    Verifies that all 6 required explanation dimensions are present, non-empty,
    and properly populated across all 4 finding types.
    """
    types = [
        FindingType.FAST_CLOSURE,
        FindingType.ESCALATION_GAP,
        FindingType.REPEATED_UNRESOLVED_ALERTS,
        FindingType.COVERAGE_GAP,
    ]

    for ft in types:
        f = Finding(
            finding_id=uuid4(),
            cse_id=uuid4(),
            reporting_period_id=uuid4(),
            finding_type=ft,
            priority_score=0.80,
            priority_components={"signal_strength": 0.8, "peer_deviation": 0.7, "persistence": 0.8, "asset_criticality": 1.0, "data_uncertainty": 0.08},
            evidentiary_confidence=0.90,
            data_quality_status=high_dq_fixture,
            evidence_state=EvidenceSufficiencyState.SUPPORTED,
            expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
            expected_behavior="Expected supervisory standard",
            observed_behavior=f"Observed behavior for {ft.value}",
            supporting_signals=[f"Signal 1 for {ft.value}", f"Signal 2 for {ft.value}"],
            contradicting_signals=[],
            evidence_refs=[EvidenceRef(entity_type="alert", entity_id=uuid4())],
            peer_context="Sector benchmark context",
            temporal_context="Active period",
            analytical_method="Supervisory Analytics",
            ruleset_version="V1",
            dataset_version_id=high_dq_fixture.dataset_version_id,
            analysis_run_id=uuid4(),
            created_at=datetime.now(timezone.utc),
        )

        exp = generate_finding_explanation(f)

        # 1. What happened
        assert "what_happened" in exp and len(exp["what_happened"]) > 0
        # 2. Why it was flagged
        assert "why_flagged" in exp and len(exp["why_flagged"]) > 0
        # 3. Supporting evidence
        assert "supporting_evidence_summary" in exp and len(exp["supporting_evidence_summary"]) > 0
        # 4. Confidence
        assert "confidence_summary" in exp and len(exp["confidence_summary"]) > 0
        # 5. Relevant peer context
        assert "peer_context_summary" in exp and len(exp["peer_context_summary"]) > 0
        # 6. DQ limitation
        assert "data_quality_limitation" in exp and len(exp["data_quality_limitation"]) > 0
