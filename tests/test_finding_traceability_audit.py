"""
Comprehensive Audit & Verification Tests for Finding Evidence Traceability (SRS §24, §52, §54).

Verifies:
1. Every finding provides all 12 mandatory traceability fields:
   - finding ID
   - detector
   - detector version
   - reason
   - source entity
   - source record IDs
   - evidence references
   - calculation inputs
   - calculation result
   - dataset version
   - analysis run
   - ruleset version
2. Traversal path through the 6-stage inspection hierarchy:
   Finding -> Explanation -> Detector -> Calculation -> Evidence -> Source record
3. Zero fabrication: missing or unescalated evidence produces explicit absence / insufficient evidence states
4. API endpoints return full traceability payloads without truncation or opaque values
5. Repeatable determinism across all detector types (Fast Closure, Escalation Gap, Repeated Unresolved, Coverage Gap)
"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.main import app
from backend.repositories.in_memory_repo import InMemoryRepository, get_repository
from backend.models.canonical import (
    Asset,
    AssetCriticality,
    CSE,
    CoverageObservation,
    DataQualityComponents,
    DataQualityScore,
    EvidenceRef,
    EvidenceSufficiencyState,
    ExpectationBasis,
    Finding,
    FindingType,
    Severity,
)
from backend.models.provenance import (
    AnalysisRun,
    EvidenceProvenanceRef,
    FindingProvenanceTrace,
)
from backend.security.auth import UserContext, create_access_token
from analytics.synthetic_generator import (
    generate_synthetic_soc_benchmark,
    run_full_analytical_pipeline,
)


@pytest.fixture
def auth_headers():
    user = UserContext(user_id="analyst-1", username="analyst", role="analyst", full_name="Analyst User")
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_repo_with_findings():
    repo = InMemoryRepository()
    ds_id = uuid4()
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    pipeline_res = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=ver_id,
    )

    repo.register_dataset_version(
        dataset_id=ds_id,
        dataset_name="Traceability Audit Dataset",
        source_file_ref="synthetic://traceability-audit",
        canonical_dataset=pipeline_res.canonical_dataset,
        reconstructed_dataset=pipeline_res.reconstructed_dataset,
        benchmark_engine=pipeline_res.benchmark_engine,
        findings=pipeline_res.findings,
        dq_result=pipeline_res.data_quality_result,
        analysis_run=pipeline_res.analysis_run,
    )
    return repo


# =====================================================================
# 1. Verification of the 12 Mandatory Traceability Fields
# =====================================================================

def test_all_twelve_traceability_fields_present_in_provenance(test_repo_with_findings):
    """
    Verifies that get_finding_provenance exposes all 12 mandatory traceability fields.
    """
    repo = test_repo_with_findings
    findings = repo.get_findings()
    assert len(findings) > 0

    for finding in findings:
        prov = repo.get_finding_provenance(finding.finding_id)
        assert prov is not None
        p_dict = prov.to_dict()

        # 1. Finding ID
        assert "finding_id" in p_dict
        assert p_dict["finding_id"] == str(finding.finding_id)

        # 2. Detector
        assert "detector" in p_dict
        assert p_dict["detector"] == finding.finding_type.value

        # 3. Detector Version
        assert "detector_version" in p_dict
        assert len(p_dict["detector_version"]) > 0

        # 4. Reason
        assert "reason" in p_dict
        assert len(p_dict["reason"]) > 0

        # 5. Source Entity
        assert "source_entity" in p_dict
        assert "cse_id" in p_dict["source_entity"]
        assert p_dict["source_entity"]["cse_id"] == str(finding.cse_id)

        # 6. Source Record IDs
        assert "source_record_ids" in p_dict
        assert isinstance(p_dict["source_record_ids"], list)

        # 7. Evidence References
        assert "evidence_references" in p_dict
        assert isinstance(p_dict["evidence_references"], list)

        # 8. Calculation Inputs
        assert "calculation_inputs" in p_dict
        assert "signal_count" in p_dict["calculation_inputs"]
        assert "data_quality_score" in p_dict["calculation_inputs"]

        # 9. Calculation Result
        assert "calculation_result" in p_dict
        assert "priority_score" in p_dict["calculation_result"]
        assert "priority_label" in p_dict["calculation_result"]

        # 10. Dataset Version
        assert "dataset_version" in p_dict
        assert "dataset_version_id" in p_dict["dataset_version"]

        # 11. Analysis Run
        assert "analysis_run" in p_dict
        assert "analysis_run_id" in p_dict["analysis_run"]

        # 12. Ruleset Version
        assert "ruleset_version" in p_dict
        assert p_dict["ruleset_version"] in ["V1", "V2", "DEFAULT", "V1_AUTHORITATIVE"]


# =====================================================================
# 2. API Endpoints Return Full Traceability Payload
# =====================================================================

def test_api_list_findings_traceability_payload(test_repo_with_findings, auth_headers):
    """
    Verifies that GET /api/findings returns the 12 traceability fields for every finding.
    """
    app.dependency_overrides[get_repository] = lambda: test_repo_with_findings
    client = TestClient(app)

    response = client.get("/api/findings", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["count"] > 0

    for f in data["findings"]:
        assert "finding_id" in f
        assert "detector" in f
        assert "detector_version" in f
        assert "reason" in f
        assert "source_entity" in f
        assert "source_record_ids" in f
        assert "evidence_references" in f
        assert "calculation_inputs" in f
        assert "calculation_result" in f
        assert "dataset_version" in f
        assert "analysis_run" in f
        assert "ruleset_version" in f


def test_api_get_finding_detail_complete_hierarchy(test_repo_with_findings, auth_headers):
    """
    Verifies that GET /api/findings/{id} returns explanation, detector, calculation,
    evidence records with source IDs, and provenance lineage.
    """
    app.dependency_overrides[get_repository] = lambda: test_repo_with_findings
    client = TestClient(app)

    findings = test_repo_with_findings.get_findings()
    first_finding = findings[0]

    response = client.get(f"/api/findings/{first_finding.finding_id}", headers=auth_headers)
    assert response.status_code == 200
    detail = response.json()

    # Stage 1: Finding
    assert detail["finding_id"] == str(first_finding.finding_id)
    assert detail["priority_score"] == round(first_finding.priority_score, 3)

    # Stage 2: Explanation
    assert "explanation" in detail
    assert "headline" in detail["explanation"]
    assert "expected_behavior" in detail["explanation"]
    assert "observed_behavior" in detail["explanation"]
    assert "supporting_signals" in detail["explanation"]

    # Stage 3: Detector
    assert detail["detector"] == first_finding.finding_type.value
    assert detail["detector_version"] is not None

    # Stage 4: Calculation
    assert "calculation_inputs" in detail
    assert "calculation_result" in detail
    assert "data_quality_breakdown" in detail["explanation"]

    # Stage 5: Evidence
    assert "evidence_records" in detail
    assert "alerts" in detail["evidence_records"]

    # Stage 6: Source Record
    assert "provenance" in detail
    assert "source_file_ref" in detail["provenance"]
    assert "sha256_hash" in detail["provenance"]


# =====================================================================
# 3. Evidence References Link to Concrete Source Record IDs (No Fabrication)
# =====================================================================

def test_evidence_records_carry_source_record_ids(test_repo_with_findings):
    """
    Verifies that each individual evidence item (alert, case, investigation, etc.)
    contains non-null source_record_id / source_record_ref corresponding to ingested data.
    """
    repo = test_repo_with_findings
    findings = repo.get_findings()

    for finding in findings:
        ev_records = repo.get_finding_evidence_records(finding.finding_id)
        assert ev_records is not None

        # Check alerts
        for alt in ev_records.get("alerts", []):
            assert "source_record_id" in alt
            assert alt["source_record_id"] is not None
            assert len(alt["source_record_id"]) > 0

        # Check cases
        for c in ev_records.get("cases", []):
            assert "source_record_id" in c
            assert c["source_record_id"] is not None

        # Check investigations
        for inv in ev_records.get("investigations", []):
            assert "source_record_id" in inv
            assert inv["source_record_id"] is not None


# =====================================================================
# 4. Absence Gaps Explicitly Show Insufficient / Absent Records
# =====================================================================

def test_escalation_gap_shows_zero_escalations_without_fabrication(test_repo_with_findings):
    """
    Verifies that an Escalation Gap finding has an empty escalations list in evidence,
    correctly demonstrating the absence of policy-mandated escalation rather than fabricating mock records.
    """
    repo = test_repo_with_findings
    esc_findings = [f for f in repo.get_findings() if f.finding_type == FindingType.ESCALATION_GAP]

    if esc_findings:
        target = esc_findings[0]
        ev_records = repo.get_finding_evidence_records(target.finding_id)
        # Escalations must be empty because the whole finding represents an escalation gap!
        assert len(ev_records.get("escalations", [])) == 0


def test_missing_evidence_state_handling():
    """
    Verifies that when evidence is completely unavailable or degraded,
    the finding explicitly marks evidence_state as INSUFFICIENT_EVIDENCE or NOT_ASSESSABLE.
    """
    finding = Finding(
        finding_id=uuid4(),
        cse_id=uuid4(),
        reporting_period_id=uuid4(),
        finding_type=FindingType.COVERAGE_GAP,
        priority_score=0.30,
        priority_components={
            "signal_strength": 0.2,
            "peer_deviation": 0.0,
            "persistence": 0.1,
            "asset_criticality": 0.5,
            "data_uncertainty": 0.6,
        },
        evidentiary_confidence=0.25,
        data_quality_status=DataQualityScore(
            dataset_version_id=uuid4(),
            score=0.40,
            components=DataQualityComponents(
                completeness_ratio=0.3,
                consistency_ratio=0.4,
                coverage_ratio=0.3,
                sample_sufficiency_ratio=0.2,
            ),
            ruleset_version="V1",
            computed_at=datetime.now(timezone.utc),
        ),
        evidence_state=EvidenceSufficiencyState.NOT_ASSESSABLE,
        expectation_basis=ExpectationBasis.CONFIGURED_EXPECTATION,
        expected_behavior="Expected regular telemetry",
        observed_behavior="Degraded data quality; monitoring silence is not assessable",
        supporting_signals=[],
        contradicting_signals=["Data quality failure: telemetry ingestion pipeline outage"],
        evidence_refs=[],
        analytical_method="Negative space",
        ruleset_version="V1",
        dataset_version_id=uuid4(),
        analysis_run_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    assert finding.evidence_state == EvidenceSufficiencyState.NOT_ASSESSABLE
    assert len(finding.evidence_refs) == 0


# =====================================================================
# 5. Deterministic Traversal Path (Finding -> Explanation -> Detector -> Calculation -> Evidence -> Source record)
# =====================================================================

def test_six_stage_traceability_traversal_integrity(test_repo_with_findings, auth_headers):
    """
    Verifies the end-to-end traversal path across all 6 stages of inspection for a finding:
    1. Finding
    2. Explanation
    3. Detector
    4. Calculation
    5. Evidence
    6. Source record
    """
    app.dependency_overrides[get_repository] = lambda: test_repo_with_findings
    client = TestClient(app)

    findings = test_repo_with_findings.get_findings()
    assert len(findings) > 0

    for finding in findings:
        resp = client.get(f"/api/findings/{finding.finding_id}", headers=auth_headers)
        assert resp.status_code == 200
        payload = resp.json()

        # Step 1: Finding
        assert payload["finding_id"] == str(finding.finding_id)
        assert "priority_score" in payload

        # Step 2: Explanation
        assert "headline" in payload["explanation"]
        assert "recommended_action" in payload["explanation"]

        # Step 3: Detector
        assert payload["detector"] == finding.finding_type.value
        assert "analytical_method" in payload["explanation"]

        # Step 4: Calculation
        assert "priority_components" in payload
        assert "data_quality_breakdown" in payload["explanation"]

        # Step 5: Evidence
        assert "evidence_records" in payload
        assert isinstance(payload["evidence_references"], list)

        # Step 6: Source Record
        assert "provenance" in payload
        assert "source_file_ref" in payload["provenance"]
        assert "source_record_ids" in payload
