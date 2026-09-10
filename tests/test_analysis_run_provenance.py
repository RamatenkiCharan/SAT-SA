"""
Analysis Run Provenance & End-to-End Lineage Traceability Test Suite.
Verifies:
  1. Complete 6-tier lineage: upload -> dataset -> dataset version -> analysis run -> finding -> evidence references.
  2. Every analysis run records:
     - analysis_run_id
     - dataset_id
     - dataset_version_id
     - schema_version
     - ruleset_version
     - detector version / configuration
     - application version and git commit
     - start time and end time
     - status ("COMPLETED" / "FAILED")
     - error information if failed
  3. Every finding references its parent analysis_run_id and ruleset_version.
  4. Every evidence reference identifies its source canonical record (source_record_ref).
  5. Strict orphan finding prevention: findings not bound to the registering dataset version are rejected.
  6. Provenance persistence in both InMemoryRepository and PostgresRepository.
  7. Finding detail API (GET /api/findings/{id}) and dedicated Provenance API (GET /api/findings/{id}/provenance).
  8. Analytical reproducibility: same dataset version + same ruleset + same detector configuration produces deterministic and equivalent findings.
"""
from __future__ import annotations

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.main import app
from backend.models.canonical import Finding, FindingType, ExpectationBasis, EvidenceRef
from backend.models.provenance import AnalysisRun, FindingProvenanceTrace
from backend.models.ruleset import AnalyticalRuleset
from backend.repositories.in_memory_repo import InMemoryRepository, set_repository
from backend.repositories.postgres_repo import PostgresRepository
from backend.services.ingestion import ingest_file_stream
from backend.services.ruleset_service import RulesetService


@pytest.fixture
def clean_in_memory_repo():
    repo = InMemoryRepository()
    set_repository(repo)
    return repo


@pytest.fixture
def temp_db_path(tmp_path: Path):
    db_file = tmp_path / "satsa_provenance_test.db"
    url = f"sqlite:///{db_file.as_posix()}"
    yield url
    set_repository(InMemoryRepository())


def test_analysis_run_provenance_metadata(clean_in_memory_repo: InMemoryRepository):
    """
    Verifies that running the pipeline generates an AnalysisRun with complete metadata,
    and every finding links to that AnalysisRun and carries source_record_ref in its evidence.
    """
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    ruleset = RulesetService.get_active_ruleset()

    pipeline_res = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=ver_id,
        ruleset=ruleset,
    )

    # 1. Verify AnalysisRun model presence and fields
    run: AnalysisRun = pipeline_res.analysis_run
    assert run is not None
    assert isinstance(run.analysis_run_id, UUID)
    assert run.dataset_version_id == ver_id
    assert run.schema_version == "2.0.0"
    assert run.ruleset_version == ruleset.version
    assert run.status == "COMPLETED"
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.finished_at >= run.started_at
    assert run.error_message is None
    assert run.app_version == "1.0.0"
    assert run.git_commit == "git-rev-satsa-v2"
    assert run.findings_count == len(pipeline_res.findings)
    assert "coverage_gap" in run.detector_config

    # 2. Verify Findings linkage to AnalysisRun
    for f in pipeline_res.findings:
        assert f.analysis_run_id == run.analysis_run_id
        assert f.ruleset_version == ruleset.version
        assert len(f.evidence_refs) > 0
        for ev in f.evidence_refs:
            assert ev.source_record_ref is not None
            assert isinstance(ev.source_record_ref, str)
            assert len(ev.source_record_ref) > 0


def test_orphan_findings_prevented_in_memory(clean_in_memory_repo: InMemoryRepository):
    """
    Verifies that trying to register a dataset version with findings from a different
    dataset_version_id raises a ValueError to prevent orphan/corrupted findings.
    """
    ds_id = uuid4()
    ver_id = uuid4()
    foreign_ver_id = uuid4()

    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    pipeline_res = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=ver_id,
    )

    # Corrupt one finding to have a mismatched dataset_version_id
    corrupted_finding = pipeline_res.findings[0].model_copy(deep=True)
    corrupted_finding.dataset_version_id = foreign_ver_id

    findings_with_orphan = list(pipeline_res.findings) + [corrupted_finding]

    with pytest.raises(ValueError, match="Orphan finding detected"):
        clean_in_memory_repo.register_dataset_version(
            dataset_id=ds_id,
            dataset_name="Orphan Prevention Test",
            source_file_ref="synthetic://test",
            canonical_dataset=pipeline_res.canonical_dataset,
            reconstructed_dataset=pipeline_res.reconstructed_dataset,
            benchmark_engine=pipeline_res.benchmark_engine,
            findings=findings_with_orphan,
            dq_result=pipeline_res.data_quality_result,
            description="Orphan test bundle",
            file_format="synthetic",
            sha256_hash="abc12345",
            accepted_rows=100,
            rejected_rows=0,
            analysis_run=pipeline_res.analysis_run,
        )


def test_orphan_findings_prevented_postgres(temp_db_path: str):
    """
    Verifies that PostgresRepository also rejects orphan findings with mismatched dataset_version_id.
    """
    repo = PostgresRepository(db_url=temp_db_path)
    ds_id = uuid4()
    ver_id = uuid4()
    foreign_ver_id = uuid4()

    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    pipeline_res = run_full_analytical_pipeline(raw_bundle=raw_bundle, dataset_version_id=ver_id)

    corrupted_finding = pipeline_res.findings[0].model_copy(deep=True)
    corrupted_finding.dataset_version_id = foreign_ver_id

    findings_with_orphan = list(pipeline_res.findings) + [corrupted_finding]

    with pytest.raises(ValueError, match="Orphan finding detected"):
        repo.register_dataset_version(
            dataset_id=ds_id,
            dataset_name="Postgres Orphan Prevention Test",
            source_file_ref="synthetic://test",
            canonical_dataset=pipeline_res.canonical_dataset,
            reconstructed_dataset=pipeline_res.reconstructed_dataset,
            benchmark_engine=pipeline_res.benchmark_engine,
            findings=findings_with_orphan,
            dq_result=pipeline_res.data_quality_result,
            description="Postgres orphan test",
            file_format="synthetic",
            sha256_hash="postgres12345",
            accepted_rows=100,
            rejected_rows=0,
            analysis_run=pipeline_res.analysis_run,
        )


def test_provenance_persistence_and_retrieval(temp_db_path: str):
    """
    Verifies that AnalysisRun and FindingProvenanceTrace persist across database reboots
    and can be queried via get_analysis_run and get_finding_provenance.
    """
    repo = PostgresRepository(db_url=temp_db_path)
    set_repository(repo)

    ds_id = uuid4()
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    pipeline_res = run_full_analytical_pipeline(raw_bundle=raw_bundle, dataset_version_id=ver_id)

    ver_meta = repo.register_dataset_version(
        dataset_id=ds_id,
        dataset_name="Provenance Persistence Pack",
        source_file_ref="synthetic://benchmark-pack",
        canonical_dataset=pipeline_res.canonical_dataset,
        reconstructed_dataset=pipeline_res.reconstructed_dataset,
        benchmark_engine=pipeline_res.benchmark_engine,
        findings=pipeline_res.findings,
        dq_result=pipeline_res.data_quality_result,
        description="Provenance persistence test",
        file_format="synthetic",
        sha256_hash="sha256_deadbeef",
        accepted_rows=500,
        rejected_rows=0,
        analysis_run=pipeline_res.analysis_run,
    )

    run_id = pipeline_res.analysis_run.analysis_run_id

    # Query AnalysisRun from repository
    retrieved_run = repo.get_analysis_run(run_id)
    assert retrieved_run is not None
    assert retrieved_run.analysis_run_id == run_id
    assert retrieved_run.dataset_id == ds_id
    assert retrieved_run.dataset_version_id == pipeline_res.canonical_dataset.dataset_version_id
    assert retrieved_run.status == "COMPLETED"
    assert retrieved_run.ruleset_version == pipeline_res.analysis_run.ruleset_version

    # Pick a finding and query its complete provenance trace
    sample_finding = pipeline_res.findings[0]
    trace: FindingProvenanceTrace = repo.get_finding_provenance(sample_finding.finding_id)
    assert trace is not None
    assert trace.finding_id == sample_finding.finding_id
    assert trace.finding_type == sample_finding.finding_type.value
    assert trace.dataset_id == ds_id
    assert trace.dataset_name == "Provenance Persistence Pack"
    assert trace.dataset_version_id == pipeline_res.canonical_dataset.dataset_version_id
    assert trace.source_file_ref == "synthetic://benchmark-pack"
    assert trace.sha256_hash == "sha256_deadbeef"
    assert trace.analysis_run_id == run_id
    assert trace.schema_version == "2.0.0"
    assert trace.ruleset_version == pipeline_res.analysis_run.ruleset_version
    assert trace.status == "COMPLETED"
    assert len(trace.evidence_refs) == len(sample_finding.evidence_refs)
    assert trace.evidence_refs[0].source_record_ref is not None

    # Restart repository instance against same database
    restarted_repo = PostgresRepository(db_url=temp_db_path)
    restarted_run = restarted_repo.get_analysis_run(run_id)
    assert restarted_run is not None
    assert restarted_run.analysis_run_id == run_id

    restarted_trace = restarted_repo.get_finding_provenance(sample_finding.finding_id)
    assert restarted_trace is not None
    assert restarted_trace.dataset_name == "Provenance Persistence Pack"
    assert restarted_trace.sha256_hash == "sha256_deadbeef"


def test_finding_detail_and_provenance_api_endpoints(clean_in_memory_repo: InMemoryRepository):
    """
    Verifies that:
      - GET /api/findings/{id} includes the provenance field.
      - GET /api/findings/{id}/provenance returns the full 6-tier provenance trace.
    """
    client = TestClient(app)
    # Login as supervisor to have upload and demo load privilege
    login_res = client.post("/api/auth/login", json={"username": "supervisor", "password": "Supervisor@SAT2026!"})
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Load demo dataset benchmark
    demo_res = client.post(
        "/api/datasets/load-demo",
        headers=headers,
        json={"scenario_type": "critical_infrastructure", "dataset_name": "API Provenance Test Benchmark"},
    )
    assert demo_res.status_code == 200, f"Load demo failed: {demo_res.text}"
    demo_data = demo_res.json()
    version_id = demo_data["dataset_version_id"]

    # Retrieve finding list
    findings_res = client.get(f"/api/findings?dataset_version_id={version_id}", headers=headers)
    assert findings_res.status_code == 200
    findings_list = findings_res.json()["findings"]
    assert len(findings_list) > 0

    first_finding_id = findings_list[0]["finding_id"]

    # 1. Test GET /api/findings/{id}
    detail_res = client.get(f"/api/findings/{first_finding_id}", headers=headers)
    assert detail_res.status_code == 200
    detail_json = detail_res.json()
    assert "provenance" in detail_json
    prov = detail_json["provenance"]
    assert prov is not None
    assert prov["dataset_name"] == "API Provenance Test Benchmark"
    assert prov["dataset_version_id"] == version_id
    assert prov["schema_version"] == "2.0.0"
    assert prov["ruleset_version"] is not None
    assert prov["status"] == "COMPLETED"
    assert len(prov["evidence_refs"]) > 0
    assert "source_record_ref" in prov["evidence_refs"][0]

    # 2. Test GET /api/findings/{id}/provenance
    prov_res = client.get(f"/api/findings/{first_finding_id}/provenance", headers=headers)
    assert prov_res.status_code == 200
    prov_json = prov_res.json()
    assert prov_json["finding_id"] == first_finding_id
    assert prov_json["dataset_version_id"] == version_id
    assert prov_json["schema_version"] == "2.0.0"
    assert prov_json["detector_config"] is not None
    assert prov_json["source_file_ref"] is not None


def test_analytical_reproducibility_contract():
    """
    Reproducibility Test:
    Same dataset version + same ruleset + same detector configuration
    MUST produce equivalent findings.
    """
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=1337, dataset_version_id=ver_id)
    ruleset = RulesetService.get_active_ruleset()

    # Run 1
    res1 = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=ver_id,
        ruleset=ruleset,
    )

    # Run 2 with identical inputs
    res2 = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=ver_id,
        ruleset=ruleset,
    )

    # Assert analytical reproducibility
    dq1 = res1.data_quality_result.score
    dq2 = res2.data_quality_result.score
    assert dq1 == pytest.approx(dq2, rel=1e-9)
    assert res1.data_quality_result.components.completeness_ratio == pytest.approx(res2.data_quality_result.components.completeness_ratio, rel=1e-9)
    assert res1.data_quality_result.components.consistency_ratio == pytest.approx(res2.data_quality_result.components.consistency_ratio, rel=1e-9)
    assert res1.data_quality_result.components.coverage_ratio == pytest.approx(res2.data_quality_result.components.coverage_ratio, rel=1e-9)
    assert res1.data_quality_result.components.sample_sufficiency_ratio == pytest.approx(res2.data_quality_result.components.sample_sufficiency_ratio, rel=1e-9)

    assert len(res1.findings) == len(res2.findings)

    # Sort findings by finding_type and cse_id for deterministic comparison
    f_list1 = sorted(res1.findings, key=lambda f: (f.finding_type.value, str(f.cse_id)))
    f_list2 = sorted(res2.findings, key=lambda f: (f.finding_type.value, str(f.cse_id)))

    for f1, f2 in zip(f_list1, f_list2):
        assert f1.finding_type == f2.finding_type
        assert f1.cse_id == f2.cse_id
        assert f1.ruleset_version == f2.ruleset_version
        assert f1.priority_score == pytest.approx(f2.priority_score, rel=1e-9)
        assert f1.evidentiary_confidence == pytest.approx(f2.evidentiary_confidence, rel=1e-9)
        for k in f1.priority_components:
            assert f1.priority_components[k] == pytest.approx(f2.priority_components[k], rel=1e-9)
        assert len(f1.evidence_refs) == len(f2.evidence_refs)
        for ev1, ev2 in zip(f1.evidence_refs, f2.evidence_refs):
            assert ev1.source_record_ref == ev2.source_record_ref
            assert ev1.entity_type == ev2.entity_type
            assert ev1.entity_id == ev2.entity_id
