"""
Unit and Integration Tests for Versioned Analytical Rulesets.
Proves that:
  - Ruleset V1 produces 100% deterministic results with authoritative SRS v2.0 parameters.
  - Modifying / creating ruleset V2 produces intentionally distinct analytical outcomes.
  - Historical findings retain their generating ruleset version across active ruleset changes (Success Condition).
  - Explicit and safe fallback behavior when database or version is unavailable.
  - REST API endpoints for ruleset management respect RBAC authorization.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from analytics.data_quality.quality_processor import evaluate_dataset_quality
from analytics.data_quality.quality_score import DataQualityInputs, compute_data_quality_score
from analytics.fusion.evidence_fusion import (
    EvidenceFusionEngine,
    FusionInputs,
    calculate_priority_components,
)
from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.main import app
from backend.models.canonical import Finding
from backend.models.ruleset import (
    DEFAULT_AUTHORITATIVE_RULESET_V1,
    AnalyticalRuleset,
    CoverageGapConfig,
    DataQualityWeights,
    DetectorConfig,
    EscalationGapConfig,
    FastClosureConfig,
    FusionWeights,
    PriorityThresholds,
    RepeatedUnresolvedConfig,
)
from backend.repositories.in_memory_repo import InMemoryRepository, set_repository
from backend.services.ruleset_service import RulesetService


@pytest.fixture(autouse=True)
def reset_in_memory_repo():
    """Ensure clean in-memory repository before and after each test."""
    repo = InMemoryRepository()
    set_repository(repo)
    yield repo
    set_repository(InMemoryRepository())


def test_ruleset_v1_authoritative_determinism():
    """Proves that default ruleset V1 produces deterministic results matching SRS v2.0."""
    ruleset_v1 = RulesetService.get_fallback_ruleset()
    assert ruleset_v1.version == "V1"

    # 1. Test DQ calculation with authoritative weights
    inputs = DataQualityInputs(
        missing_required_fields=0,
        total_required_fields=100,
        failed_validation_checks=0,
        total_validation_checks=100,
        observed_evidence_records=100,
        expected_evidence_records=100,
        actual_sample_size=100,
    )
    dq_res = compute_data_quality_score(
        inputs=inputs,
        dataset_version_id=uuid4(),
        ruleset=ruleset_v1,
    )
    assert dq_res.score == 1.0
    assert dq_res.ruleset_version == "V1"
    assert dq_res.components.completeness_ratio == 1.0
    assert dq_res.components.consistency_ratio == 1.0
    assert dq_res.components.coverage_ratio == 1.0
    assert dq_res.components.sample_sufficiency_ratio == 1.0

    # 2. Test Priority calculation with authoritative fusion weights
    fusion_inputs = FusionInputs(
        signal_count=3,
        max_peer_zscore=3.0,
        persistence_ratio=1.0,
        asset_criticality_tier="CRITICAL",
        data_quality_score=1.0,
    )
    score, comps = calculate_priority_components(fusion_inputs, ruleset=ruleset_v1)
    # 0.30(1.0) + 0.25(1.0) + 0.20(1.0) + 0.15(1.0) + (-0.10)(0.0) = 0.90
    assert round(score, 4) == 0.9000
    assert comps["signal_strength"] == 1.0
    assert comps["peer_deviation"] == 1.0
    assert comps["persistence"] == 1.0
    assert comps["asset_criticality"] == 1.0
    assert comps["data_uncertainty"] == 0.0


def test_changing_ruleset_produces_intentionally_different_results():
    """Proves that creating and applying an alternate ruleset produces distinct scores and thresholds."""
    # Define experimental ruleset V2 with different weight distribution
    ruleset_v2 = AnalyticalRuleset(
        ruleset_id=uuid4(),
        version="V2-EXPERIMENTAL",
        name="Experimental High-Asset-Criticality Ruleset",
        is_active=False,
        effective_timestamp=datetime.now(timezone.utc),
        author="Security Architecture Group",
        rationale="Amplifies asset criticality weighting to 0.40 and reduces peer deviation weighting.",
        dq_weights=DataQualityWeights(
            completeness_weight=0.50,
            consistency_weight=0.20,
            coverage_weight=0.20,
            sample_sufficiency_weight=0.10,
            minimum_sample_size_default=15,
        ),
        fusion_weights=FusionWeights(
            signal_strength_weight=0.20,
            peer_deviation_weight=0.10,
            persistence_weight=0.10,
            asset_criticality_weight=0.40,
            data_uncertainty_weight=-0.20,
            signal_strength_cap=2,
            peer_deviation_zscore_cap=2.0,
        ),
        thresholds=PriorityThresholds(
            high_priority_min_independent_signals=1,
            high_priority_min_data_quality=0.5,
        ),
        detector_config=DetectorConfig(
            fast_closure=FastClosureConfig(mad_multiplier=1.8, investigation_evidence_percentile=30),
            escalation_gap=EscalationGapConfig(applies_to_severity=["CRITICAL", "HIGH"]),
            repeated_unresolved=RepeatedUnresolvedConfig(min_occurrences=2, window_days=14),
            coverage_gap=CoverageGapConfig(coverage_ratio_threshold=0.5, min_data_quality_to_flag=0.5),
        ),
    )

    # 1. Compare DQ scores between V1 and V2 on partial completeness dataset
    inputs = DataQualityInputs(
        missing_required_fields=20,  # 80% completeness
        total_required_fields=100,
        failed_validation_checks=0,  # 100% consistency
        total_validation_checks=100,
        observed_evidence_records=100,  # 100% coverage
        expected_evidence_records=100,
        actual_sample_size=100,  # 100% sufficiency
    )
    dq_v1 = compute_data_quality_score(inputs, uuid4(), ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    dq_v2 = compute_data_quality_score(inputs, uuid4(), ruleset=ruleset_v2)

    # V1: 0.30(0.8) + 0.25(1.0) + 0.25(1.0) + 0.20(1.0) = 0.24 + 0.25 + 0.25 + 0.20 = 0.94
    assert round(dq_v1.score, 4) == 0.9400
    # V2: 0.50(0.8) + 0.20(1.0) + 0.20(1.0) + 0.10(1.0) = 0.40 + 0.20 + 0.20 + 0.10 = 0.90
    assert round(dq_v2.score, 4) == 0.9000
    assert dq_v1.score != dq_v2.score
    assert dq_v1.ruleset_version == "V1"
    assert dq_v2.ruleset_version == "V2-EXPERIMENTAL"

    # 2. Compare Fusion priority scores between V1 and V2
    fusion_inputs = FusionInputs(
        signal_count=2,
        max_peer_zscore=1.5,
        persistence_ratio=0.5,
        asset_criticality_tier="CRITICAL",  # 1.0
        data_quality_score=0.90,            # uncertainty = 0.10
    )
    score_v1, _ = calculate_priority_components(fusion_inputs, ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1)
    score_v2, _ = calculate_priority_components(fusion_inputs, ruleset=ruleset_v2)

    assert score_v1 != score_v2
    # Under V2 with 0.40 asset criticality weight, score for critical asset is noticeably higher
    assert score_v2 > score_v1


def test_historical_findings_retain_generating_ruleset_version():
    """
    SUCCESS CONDITION TEST:
    Proves that a historical finding generated under ruleset V1 remains permanently stamped
    with ruleset_version='V1' and reproducible even after activating ruleset V2.
    """
    repo = InMemoryRepository()
    set_repository(repo)

    # 1. Ingest dataset under active ruleset V1
    ds_id = uuid4()
    ver_v1_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_v1_id)
    pipeline_v1 = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=ver_v1_id,
        ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1,
    )

    repo.register_dataset_version(
        dataset_id=ds_id,
        dataset_name="V1 Baseline Evaluation",
        source_file_ref="synthetic://benchmark-v1",
        canonical_dataset=pipeline_v1.canonical_dataset,
        reconstructed_dataset=pipeline_v1.reconstructed_dataset,
        benchmark_engine=pipeline_v1.benchmark_engine,
        findings=pipeline_v1.findings,
        dq_result=pipeline_v1.data_quality_result,
    )

    findings_v1 = repo.get_findings(dataset_version_id=ver_v1_id)
    assert len(findings_v1) > 0
    for f in findings_v1:
        assert f.ruleset_version == "V1"

    original_finding_0 = findings_v1[0]
    original_score = original_finding_0.priority_score
    original_comps = dict(original_finding_0.priority_components)
    original_id = original_finding_0.finding_id

    # 2. Register and activate new Ruleset V2
    ruleset_v2 = AnalyticalRuleset(
        ruleset_id=uuid4(),
        version="V2-NCIIPC-2027",
        name="Next Gen Supervisory Ruleset",
        is_active=True,
        effective_timestamp=datetime.now(timezone.utc),
        author="NCIIPC",
        rationale="Upgraded weighting schema",
        fusion_weights=FusionWeights(signal_strength_weight=0.50, peer_deviation_weight=0.10),
    )
    repo.register_ruleset(ruleset_v2, set_active=True)

    assert repo.get_active_ruleset().version == "V2-NCIIPC-2027"

    # 3. Ingest new dataset under active ruleset V2
    ver_v2_id = uuid4()
    raw_bundle_v2, _ = generate_synthetic_soc_benchmark(seed=101, dataset_version_id=ver_v2_id)
    pipeline_v2 = run_full_analytical_pipeline(
        raw_bundle=raw_bundle_v2,
        dataset_version_id=ver_v2_id,
        ruleset=ruleset_v2,
    )
    repo.register_dataset_version(
        dataset_id=ds_id,
        dataset_name="V2 Upgraded Evaluation",
        source_file_ref="synthetic://benchmark-v2",
        canonical_dataset=pipeline_v2.canonical_dataset,
        reconstructed_dataset=pipeline_v2.reconstructed_dataset,
        benchmark_engine=pipeline_v2.benchmark_engine,
        findings=pipeline_v2.findings,
        dq_result=pipeline_v2.data_quality_result,
    )


    # 4. Verify historical finding from V1 is unchanged and retains ruleset_version='V1'
    historical_finding = repo.get_finding_by_id(original_id)
    assert historical_finding is not None
    assert historical_finding.ruleset_version == "V1"
    assert historical_finding.priority_score == original_score
    assert historical_finding.priority_components == original_comps

    # 5. Verify new findings under V2 have ruleset_version='V2-NCIIPC-2027'
    findings_v2 = repo.get_findings(dataset_version_id=ver_v2_id)
    assert len(findings_v2) > 0
    for f in findings_v2:
        assert f.ruleset_version == "V2-NCIIPC-2027"


def test_safe_fallback_behavior():
    """Proves that requesting a missing ruleset version or empty repository falls back safely."""
    # When no repository is provided, active ruleset is V1
    fallback = RulesetService.get_active_ruleset(repo=None)
    assert fallback.version == "V1"
    assert fallback.dq_weights.completeness_weight == 0.30

    # Non-existent version raises explicit ValueError
    with pytest.raises(ValueError, match="not found"):
        RulesetService.get_ruleset_by_version("NON-EXISTENT-V99", repo=None)


def test_ruleset_api_endpoints_and_rbac():
    """Tests /api/rulesets REST endpoints under Analyst and Supervisor roles."""
    client = TestClient(app)

    # 1. Login as Analyst
    login_analyst = client.post("/api/auth/login", json={"username": "analyst", "password": "Analyst@SAT2026!"})
    assert login_analyst.status_code == 200
    analyst_headers = {"Authorization": f"Bearer {login_analyst.json()['access_token']}"}

    # 2. Login as Supervisor
    login_sup = client.post("/api/auth/login", json={"username": "supervisor", "password": "Supervisor@SAT2026!"})
    assert login_sup.status_code == 200
    sup_headers = {"Authorization": f"Bearer {login_sup.json()['access_token']}"}

    # 3. GET /api/rulesets is accessible to Analyst
    list_resp = client.get("/api/rulesets", headers=analyst_headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["active_version"] == "V1"
    assert data["count"] >= 1

    # 4. GET /api/rulesets/active is accessible to Analyst
    active_resp = client.get("/api/rulesets/active", headers=analyst_headers)
    assert active_resp.status_code == 200
    active_data = active_resp.json()
    assert active_data["version"] == "V1"
    assert active_data["dq_weights"]["completeness_weight"] == 0.30

    # 5. POST /api/rulesets by Analyst -> 403 Forbidden
    new_ruleset_payload = {
        "version": "V2-API-TEST",
        "name": "API Configured Ruleset",
        "is_active": False,
        "author": "Supervisor Examiner",
        "rationale": "Testing API ruleset management",
        "dq_weights": {
            "completeness_weight": 0.40,
            "consistency_weight": 0.20,
            "coverage_weight": 0.20,
            "sample_sufficiency_weight": 0.20,
            "minimum_sample_size_default": 25,
        },
        "fusion_weights": {
            "signal_strength_weight": 0.35,
            "peer_deviation_weight": 0.25,
            "persistence_weight": 0.15,
            "asset_criticality_weight": 0.15,
            "data_uncertainty_weight": -0.10,
            "signal_strength_cap": 3,
            "peer_deviation_zscore_cap": 3.0,
            "high_priority_min_independent_signals": 2,
            "high_priority_min_data_quality": 0.6,
        },
    }
    forbidden_resp = client.post("/api/rulesets", headers=analyst_headers, json=new_ruleset_payload)
    assert forbidden_resp.status_code == 403

    # 6. POST /api/rulesets by Supervisor -> 200 OK
    create_resp = client.post("/api/rulesets", headers=sup_headers, json=new_ruleset_payload)
    assert create_resp.status_code == 200
    assert create_resp.json()["status"] == "success"

    # 7. GET /api/rulesets/V2-API-TEST -> 200 OK
    get_v2_resp = client.get("/api/rulesets/V2-API-TEST", headers=analyst_headers)
    assert get_v2_resp.status_code == 200
    assert get_v2_resp.json()["version"] == "V2-API-TEST"

    # 8. POST /api/rulesets/V2-API-TEST/activate by Supervisor -> 200 OK
    activate_resp = client.post("/api/rulesets/V2-API-TEST/activate", headers=sup_headers)
    assert activate_resp.status_code == 200
    assert activate_resp.json()["status"] == "success"

    # Verify active ruleset is now V2-API-TEST
    check_active_resp = client.get("/api/rulesets/active", headers=analyst_headers)
    assert check_active_resp.status_code == 200
    assert check_active_resp.json()["version"] == "V2-API-TEST"
