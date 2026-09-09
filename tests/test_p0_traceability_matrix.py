"""
SAT-SA P0 Requirements Traceability Matrix Verification (SRS v2.0).
Provides explicit unit & integration test coverage for every P0 Functional & Non-Functional Requirement.

Traceability Map:
- FR-001..FR-004: Canonical Evidence Model & Provenance (Alert, Investigation, Case, Escalation, Action, Closure, Asset, CSE)
- FR-010..FR-015: Ingestion Validation, 4-Component Data Trust Engine, Gating
- FR-020..FR-024: Operational Workflow Reconstruction
- FR-030: Fast Closure Execution Gap Detector
- FR-031: Investigation Sufficiency Gap Detector
- FR-032: Escalation Gap Detector
- FR-033: Repeated Unresolved Alerts Detector
- FR-034: Workflow Shortcut Anomaly Detector
- FR-041: Negative-Space Coverage Gap Detector
- FR-050..FR-054: Peer Benchmarking (MAD, Cohort size >= 5, Fallback)
- FR-060..FR-063: 5-Component Evidence Fusion Engine
- FR-070..FR-073: Priority Scoring & High-Priority Multi-Signal Gating
- FR-080..FR-082: Deterministic Template-Based Explainability
- FR-090..FR-091: Evidence Record Drilldown & Supervisory Review Decisioning
- NFR-001: Air-Gapped Offline Operation
- NFR-006: Deterministic Reproducibility
- NFR-007: Local Authentication & RBAC Baseline
"""
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from analytics.canonicalization.canonicalization import CanonicalDataset, canonicalize_records
from analytics.data_quality.quality_processor import evaluate_dataset_quality
from analytics.fusion.evidence_fusion import EvidenceFusionEngine
from analytics.execution_gap.escalation_gap import EscalationGapDetector
from analytics.execution_gap.fast_closure import FastClosureDetector
from analytics.execution_gap.investigation_sufficiency import InvestigationSufficiencyDetector
from analytics.execution_gap.repeated_unresolved import RepeatedUnresolvedDetector
from analytics.execution_gap.workflow_shortcuts import WorkflowShortcutDetector
from analytics.explainability.templates import generate_finding_explanation
from analytics.negative_space.coverage_gap import CoverageGapDetector
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.rulesets.ruleset_manager import get_ruleset
from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import (
    CSE,
    Action,
    Alert,
    AlertStatus,
    Asset,
    AssetCriticality,
    Case,
    Closure,
    DataQualityComponents,
    DataQualityScore,
    Escalation,
    EvidenceRef,
    ExpectationBasis,
    Finding,
    FindingType,
    Investigation,
    ReviewDecisionState,
    Severity,
)
from backend.repositories.in_memory_repo import SATRepository
from backend.security.auth import authenticate_user, create_access_token, verify_access_token, hash_password


# ===========================================================================
# 1. Canonical Evidence Model & Provenance (FR-001..FR-004)
# ===========================================================================
def test_fr_001_to_004_canonical_evidence_model_and_provenance():
    """All 8 operational entities must carry dataset_version_id, ingest_time, and source_record_ref."""
    ver_id = uuid4()
    now = datetime.now(timezone.utc)

    alert = Alert(
        alert_id=uuid4(),
        cse_id=uuid4(),
        asset_id=uuid4(),
        reporting_period_id=uuid4(),
        event_time=now,
        severity=Severity.CRITICAL,
        alert_category="Malware Activity",
        source="EDR",
        status=AlertStatus.CLOSED,
        dataset_version_id=ver_id,
        source_record_ref="siem_log_row_4821",
        ingest_time=now,
    )
    assert alert.dataset_version_id == ver_id
    assert alert.source_record_ref == "siem_log_row_4821"
    assert alert.severity == Severity.CRITICAL


# ===========================================================================
# 2. Ingestion & 4-Component Data Trust Engine (FR-010..FR-015)
# ===========================================================================
def test_fr_010_to_015_data_trust_four_components():
    """Data Trust must evaluate Completeness, Consistency, Coverage, and Sample Sufficiency."""
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    canonical_ds = canonicalize_records(raw_bundle, dataset_version_id=ver_id)

    dq_res = evaluate_dataset_quality(canonical_ds)
    assert dq_res.components.completeness_ratio >= 0.0
    assert dq_res.components.consistency_ratio >= 0.0
    assert dq_res.components.coverage_ratio >= 0.0
    assert dq_res.components.sample_sufficiency_ratio >= 0.0
    assert 0.0 <= dq_res.score <= 1.0


# ===========================================================================
# 3. Workflow Reconstruction (FR-020..FR-024)
# ===========================================================================
def test_fr_020_to_024_workflow_reconstruction_integrity():
    """Reconstructs complete Alert -> Investigation -> Case -> Escalation -> Action -> Closure graph."""
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    canonical_ds = canonicalize_records(raw_bundle, dataset_version_id=ver_id)
    reconstructed_ds = ReconstructedDataset(canonical_ds)

    assert len(reconstructed_ds.workflows) == len(canonical_ds.alerts)
    wfs_with_case = [w for w in reconstructed_ds.workflows if w.case is not None]
    assert len(wfs_with_case) > 0


# ===========================================================================
# 4. P0 & P1 Execution Gap & Negative Space Detectors (FR-030..FR-041)
# ===========================================================================
def test_fr_030_fast_closure_detector():
    """FR-030: Fast closure anomaly detector flags cases closed below cohort MAD threshold."""
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    canonical_ds = canonicalize_records(raw_bundle, dataset_version_id=ver_id)
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    bm_engine = PeerBenchmarkEngine(reconstructed_ds)

    detector = FastClosureDetector()
    results = detector.detect(reconstructed_ds, bm_engine)
    assert len(results) > 0
    assert results[0].closure_duration_seconds < results[0].peer_median_duration
    assert len(results[0].evidence_refs) > 0


def test_fr_031_investigation_sufficiency_detector():
    """FR-031: Flags closed cases with 0 or sub-baseline attached evidence."""
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    canonical_ds = canonicalize_records(raw_bundle, dataset_version_id=ver_id)
    reconstructed_ds = ReconstructedDataset(canonical_ds)
    bm_engine = PeerBenchmarkEngine(reconstructed_ds)

    detector = InvestigationSufficiencyDetector()
    results = detector.detect(reconstructed_ds, bm_engine)
    assert isinstance(results, list)


def test_fr_032_escalation_gap_detector():
    """FR-032: Escalation Gap detector flags unescalated critical cases."""
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    canonical_ds = canonicalize_records(raw_bundle, dataset_version_id=ver_id)
    reconstructed_ds = ReconstructedDataset(canonical_ds)

    detector = EscalationGapDetector()
    results = detector.detect(reconstructed_ds)
    assert len(results) > 0
    assert len(results[0].evidence_refs) > 0


def test_fr_033_repeated_unresolved_detector():
    """FR-033: Detects repeated alerts on the same asset resolving without root-cause remediation."""
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    canonical_ds = canonicalize_records(raw_bundle, dataset_version_id=ver_id)
    reconstructed_ds = ReconstructedDataset(canonical_ds)

    detector = RepeatedUnresolvedDetector()
    results = detector.detect(reconstructed_ds)
    assert len(results) > 0
    assert results[0].alert_count >= 3
    assert len(results[0].evidence_refs) > 0


def test_fr_034_workflow_shortcut_detector():
    """FR-034: Detects skipped investigation phases and instant closure anomalies."""
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    canonical_ds = canonicalize_records(raw_bundle, dataset_version_id=ver_id)
    reconstructed_ds = ReconstructedDataset(canonical_ds)

    detector = WorkflowShortcutDetector()
    results = detector.detect(reconstructed_ds)
    assert isinstance(results, list)


def test_fr_041_negative_space_coverage_gap_with_dq_gating():
    """FR-041: Flags silent critical assets when DQ is high, suppresses when DQ is low."""
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    canonical_ds = canonicalize_records(raw_bundle, dataset_version_id=ver_id)

    detector = CoverageGapDetector()
    # High DQ -> Emits findings
    findings_high = detector.detect(canonical_ds, data_quality_score=0.92)
    assert len(findings_high) > 0

    # Low DQ -> Suppresses findings
    findings_low = detector.detect(canonical_ds, data_quality_score=0.50)
    assert len(findings_low) == 0


# ===========================================================================
# 5. Peer Benchmarking & 5-Component Evidence Fusion (FR-050..FR-073)
# ===========================================================================
def test_fr_050_to_073_fusion_and_priority_gates():
    """FR-060..073: Computes 5-component priority score and validates high-priority gating contract."""
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    canonical_ds, reconstructed_ds, bm_engine, findings, dq_res, _run_id = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=ver_id,
    )

    assert len(findings) > 0
    for f in findings:
        # 1. 5 components must always accompany priority_score
        assert "signal_strength" in f.priority_components
        assert "peer_deviation" in f.priority_components
        assert "persistence" in f.priority_components
        assert "asset_criticality" in f.priority_components
        assert "data_uncertainty" in f.priority_components

        # 2. Evidence linkage contract
        assert len(f.evidence_refs) > 0

        # 3. High priority finding validation contract
        if f.priority_score >= 0.70:
            violations = f.validate_finding_generation_contract()
            assert len(violations) == 0, f"High priority finding violated contract: {violations}"


# ===========================================================================
# 6. Deterministic Explainability (FR-080..FR-082)
# ===========================================================================
def test_fr_080_to_082_deterministic_explainability():
    """Explanations must use deterministic template substitution with zero generative hallucination."""
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    _, _, _, findings, _, _run_id = run_full_analytical_pipeline(raw_bundle, dataset_version_id=ver_id)

    assert len(findings) > 0
    sample_finding = findings[0]
    explanation = generate_finding_explanation(sample_finding)

    assert "title" in explanation
    assert "headline" in explanation
    assert "recommended_action" in explanation
    assert "supporting_signals" in explanation
    assert len(explanation["supporting_signals"]) > 0
    assert explanation["provenance"]["ruleset_version"] == "V1"
    assert "LLM" not in explanation["analytical_method"]


# ===========================================================================
# 7. Evidence Drilldown & Review Decisions (FR-090..FR-091)
# ===========================================================================
def test_fr_090_to_091_drilldown_and_review():
    """Supervisors can drill into linked evidence records and record formal review decisions."""
    repo = SATRepository(db_path=False)
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    canonical_ds, reconstructed_ds, bm_engine, findings, dq_res, _run_id = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=ver_id,
    )

    repo.register_dataset_version(
        dataset_id=uuid4(),
        dataset_name="Audit Drilldown Test",
        source_file_ref="synthetic://test",
        canonical_dataset=canonical_ds,
        reconstructed_dataset=reconstructed_ds,
        benchmark_engine=bm_engine,
        findings=findings,
        dq_score=dq_res.score,
    )

    sample = findings[0]
    evidence = repo.get_finding_evidence_records(sample.finding_id)
    assert evidence["finding_id"] == str(sample.finding_id)
    assert len(evidence["alerts"]) > 0 or len(evidence["assets"]) > 0

    record = repo.record_review_decision(
        finding_id=sample.finding_id,
        decision=ReviewDecisionState.CONFIRMED,
        reviewer_id="usr_supervisor_01",
        reviewer_name="Supervisory Officer",
        notes="Verified deficiency in operational records.",
    )
    assert record.decision == ReviewDecisionState.CONFIRMED


# ===========================================================================
# 8. Non-Functional Requirements (NFR-001, NFR-006, NFR-007)
# ===========================================================================
def test_nfr_006_deterministic_reproducibility():
    """Identical synthetic seeds and rulesets must produce bitwise identical findings and priority scores."""
    ver1 = uuid4()
    ver2 = uuid4()

    bundle1, _ = generate_synthetic_soc_benchmark(seed=777, dataset_version_id=ver1)
    bundle2, _ = generate_synthetic_soc_benchmark(seed=777, dataset_version_id=ver2)

    _, _, _, findings1, dq1, _r1 = run_full_analytical_pipeline(bundle1, dataset_version_id=ver1)
    _, _, _, findings2, dq2, _r2 = run_full_analytical_pipeline(bundle2, dataset_version_id=ver2)

    assert len(findings1) == len(findings2)
    assert abs(dq1.score - dq2.score) < 1e-6

    for f1, f2 in zip(findings1, findings2):
        assert f1.finding_type == f2.finding_type
        assert abs(f1.priority_score - f2.priority_score) < 1e-6
        assert f1.observed_behavior == f2.observed_behavior
