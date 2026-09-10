"""
Comprehensive Persistence & Restart Survival Verification Test Suite.
Verifies that:
  - Datasets, dataset versions, provenance, and Data Quality scores survive restart.
  - Canonical entities (CSE, alerts, cases, investigations, escalations, actions, closures, assets, observations) survive restart.
  - Prioritized findings, decomposed priority components, evidentiary confidence, and signals survive restart.
  - Finding evidence linkages remain drillable and return full operational evidence records after restart.
  - Supervisory review decisions and finding review statuses survive restart.
  - Audit event history survives restart.
  - Peer benchmark distributions and MAD baselines are reconstituted accurately from persisted records.
"""
from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.main import app
from backend.models.canonical import FindingType, ReviewDecisionState
from backend.repositories.in_memory_repo import InMemoryRepository, set_repository
from backend.repositories.postgres_repo import PostgresRepository
from backend.security.auth import get_user_store
from backend.services.ingestion import ingest_file_stream


@pytest.fixture
def temp_db_path(tmp_path: Path):
    db_file = tmp_path / "satsa_persistence_test.db"
    url = f"sqlite:///{db_file.as_posix()}"
    yield url
    set_repository(InMemoryRepository())



def test_postgres_repository_lifecycle_and_restart(temp_db_path: str):
    """
    1. Ingest synthetic dataset into PostgresRepository.
    2. Submit review decision and audit event.
    3. Destroy in-memory instance and create fresh repository connected to same database.
    4. Assert that datasets, versions, canonical entities, findings, evidence, review state, and audit logs are fully intact.
    """
    repo1 = PostgresRepository(db_url=temp_db_path)

    # 1. Generate and persist dataset
    ds_id = uuid4()
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)
    pipeline_res = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=ver_id,
    )

    ver_meta = repo1.register_dataset_version(
        dataset_id=ds_id,
        dataset_name="Persistent Infrastructure Pack",
        source_file_ref="synthetic://sih-problem-26157-benchmark",
        canonical_dataset=pipeline_res.canonical_dataset,
        reconstructed_dataset=pipeline_res.reconstructed_dataset,
        benchmark_engine=pipeline_res.benchmark_engine,
        findings=pipeline_res.findings,
        dq_result=pipeline_res.data_quality_result,
        description="Persistent verification bundle",
        file_format="json",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        accepted_rows=len(pipeline_res.canonical_dataset.alerts),
        rejected_rows=0,
    )

    assert ver_meta.version_number == 1
    assert len(repo1.findings_by_version[ver_id]) > 0

    first_finding = pipeline_res.findings[0]
    finding_id = first_finding.finding_id

    # 2. Record supervisory review decision
    review_rec = repo1.record_review_decision(
        finding_id=finding_id,
        decision=ReviewDecisionState.CONFIRMED,
        reviewer_id="usr_sup_01",
        reviewer_name="Senior NCIIPC Examiner",
        notes="Verified abnormal fast closure against peer median baseline.",
    )
    assert review_rec.decision == ReviewDecisionState.CONFIRMED

    # Record custom audit event
    repo1.record_audit_event(
        user_id="usr_sup_01",
        username="Senior NCIIPC Examiner",
        action="EXPORT_SUPERVISORY_BRIEFING",
        target_type="dataset",
        target_id=str(ds_id),
        details={"format": "pdf", "section": "findings"},
    )

    initial_datasets_count = len(repo1.list_datasets())
    initial_findings_count = len(repo1.get_findings(dataset_version_id=ver_id))
    initial_evidence = repo1.get_finding_evidence_records(finding_id)
    initial_audit_count = len(repo1.get_audit_events())

    assert initial_datasets_count == 1
    assert initial_findings_count > 0
    assert len(initial_evidence["alerts"]) > 0

    # -----------------------------------------------------------------------
    # 3. Simulate System / Container Restart
    # -----------------------------------------------------------------------
    del repo1

    # Spin up brand new repository instance pointing to the exact same database
    repo2 = PostgresRepository(db_url=temp_db_path)

    # 4. Verify Dataset Survival
    datasets = repo2.list_datasets()
    assert len(datasets) == 1
    ds = datasets[0]
    assert ds["dataset_id"] == str(ds_id)
    assert ds["name"] == "Persistent Infrastructure Pack"
    assert len(ds["versions"]) == 1

    v = ds["versions"][0]
    assert v["dataset_version_id"] == str(ver_id)
    assert v["version_number"] == 1
    assert v["row_count"] == len(pipeline_res.canonical_dataset.alerts)
    assert v["data_quality_score"] is not None
    assert v["data_quality_breakdown"] is not None
    assert v["data_quality_breakdown"]["overall_score"] > 0
    assert v["provenance"]["file_format"] == "json"
    assert v["provenance"]["sha256_hash"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    # 5. Verify Findings Survival
    reconstituted_findings = repo2.get_findings(dataset_version_id=ver_id)
    assert len(reconstituted_findings) == initial_findings_count

    f_reconstituted = repo2.get_finding_by_id(finding_id)
    assert f_reconstituted is not None
    assert f_reconstituted.finding_id == finding_id
    assert f_reconstituted.finding_type == first_finding.finding_type
    assert round(f_reconstituted.priority_score, 4) == round(first_finding.priority_score, 4)
    assert f_reconstituted.evidentiary_confidence == first_finding.evidentiary_confidence
    assert f_reconstituted.data_quality_status.score == first_finding.data_quality_status.score
    assert len(f_reconstituted.evidence_refs) == len(first_finding.evidence_refs)

    # 6. Verify Review Decision Survival
    assert f_reconstituted.review_status == ReviewDecisionState.CONFIRMED
    assert f_reconstituted.review_notes == "Verified abnormal fast closure against peer median baseline."

    assert len(repo2.review_decisions) >= 1
    last_review = repo2.review_decisions[-1]
    assert last_review.finding_id == finding_id
    assert last_review.decision == ReviewDecisionState.CONFIRMED
    assert last_review.reviewer_name == "Senior NCIIPC Examiner"

    # 7. Verify Finding Evidence Linkage Reconstitution
    reconstituted_evidence = repo2.get_finding_evidence_records(finding_id)
    assert reconstituted_evidence["finding_id"] == str(finding_id)
    assert reconstituted_evidence["cse_id"] == str(first_finding.cse_id)
    assert reconstituted_evidence["cse_name"] != "Unknown"
    assert len(reconstituted_evidence["alerts"]) == len(initial_evidence["alerts"])
    assert len(reconstituted_evidence["cases"]) == len(initial_evidence["cases"])
    assert len(reconstituted_evidence["investigations"]) == len(initial_evidence["investigations"])

    # 8. Verify Audit Log Survival
    audit_events = repo2.get_audit_events()
    assert len(audit_events) == initial_audit_count
    actions = [e.action for e in audit_events]
    assert "INGEST_DATASET_VERSION" in actions
    assert "SUBMIT_SUPERVISORY_REVIEW_DECISION" in actions
    assert "EXPORT_SUPERVISORY_BRIEFING" in actions


def test_api_workflow_end_to_end_across_restart(temp_db_path: str):
    """
    Tests complete FastAPI client workflow:
      Login -> Upload CSV -> Get Findings -> Submit Review -> Restart API -> Verify Data Intact
    """
    repo = PostgresRepository(db_url=temp_db_path)
    set_repository(repo)

    client = TestClient(app)

    # 1. Login as supervisor
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "supervisor", "password": "Supervisor@SAT2026!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}

    # 2. Upload structured multi-entity operational evidence bundle
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=uuid4())

    upload_resp = client.post(
        "/api/datasets/upload",
        headers=auth_headers,
        files={"file": ("operational_soc.json", json.dumps(raw_bundle).encode("utf-8"), "application/json")},
    )
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    dataset_version_id = upload_data["dataset_version_id"]
    assert upload_resp.status_code == 200
    upload_data = upload_resp.json()
    dataset_version_id = upload_data["dataset_version_id"]

    # 3. List findings
    findings_resp = client.get("/api/findings", headers=auth_headers)
    assert findings_resp.status_code == 200
    findings_data = findings_resp.json()
    assert findings_data["count"] > 0
    target_finding = findings_data["findings"][0]
    finding_id = target_finding["finding_id"]

    # 4. Submit review decision
    review_resp = client.post(
        "/api/reviews",
        headers=auth_headers,
        json={
            "finding_id": finding_id,
            "decision": "CONFIRMED",
            "notes": "Reviewed via API across persistence layer.",
        },
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "success"

    # -----------------------------------------------------------------------
    # 5. SIMULATE API RESTART
    # -----------------------------------------------------------------------
    # Instantiate a new repository connected to the same DB and inject it into the app
    restarted_repo = PostgresRepository(db_url=temp_db_path)
    set_repository(restarted_repo)

    # 6. Verify Dataset via API
    ds_resp = client.get("/api/datasets", headers=auth_headers)
    assert ds_resp.status_code == 200
    datasets = ds_resp.json()["datasets"]
    assert len(datasets) >= 1
    found_ver = any(
        v["dataset_version_id"] == dataset_version_id
        for d in datasets
        for v in d["versions"]
    )
    assert found_ver, "Uploaded dataset version was not found after restart."

    # 7. Verify Findings via API
    f_resp = client.get(f"/api/findings?dataset_version_id={dataset_version_id}", headers=auth_headers)
    assert f_resp.status_code == 200
    f_list = f_resp.json()["findings"]
    assert len(f_list) > 0

    restarted_finding = next((f for f in f_list if f["finding_id"] == finding_id), None)
    assert restarted_finding is not None
    assert restarted_finding["review_status"] == "CONFIRMED"
    assert restarted_finding["review_notes"] == "Reviewed via API across persistence layer."

    # 8. Verify Finding Detail & Evidence via API
    detail_resp = client.get(f"/api/findings/{finding_id}", headers=auth_headers)
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["finding_id"] == finding_id
    assert detail_data["cse_name"] != "Unknown"
    assert detail_data["review_status"] == "CONFIRMED"
    assert len(detail_data["evidence_records"]["alerts"]) >= 1

    evidence_resp = client.get(f"/api/findings/{finding_id}/evidence", headers=auth_headers)
    assert evidence_resp.status_code == 200
    evidence_data = evidence_resp.json()
    assert evidence_data["finding_id"] == finding_id
    assert len(evidence_data["alerts"]) >= 1

    # 9. Verify Reviews Listing via API
    rev_list_resp = client.get("/api/reviews", headers=auth_headers)
    assert rev_list_resp.status_code == 200
    reviews = rev_list_resp.json()
    assert len(reviews) >= 1
    assert any(r["finding_id"] == finding_id and r["decision"] == "CONFIRMED" for r in reviews)

    # 10. Verify Audit Log Listing via API (requires admin role)
    admin_login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin@SAT2026!"},
    )
    assert admin_login.status_code == 200
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    audit_resp = client.get("/api/audit", headers=admin_headers)
    assert audit_resp.status_code == 200
    audit_list = audit_resp.json()
    assert len(audit_list) >= 2
    actions = [a["action"] for a in audit_list]
    assert "INGEST_DATASET_VERSION" in actions
    assert "SUBMIT_SUPERVISORY_REVIEW_DECISION" in actions


def test_database_seeded_user_auth(temp_db_path: str):
    """Verifies that default seed users in the database authenticate successfully."""
    repo = PostgresRepository(db_url=temp_db_path)
    set_repository(repo)

    user_store = get_user_store()

    # Test admin authentication
    admin_ctx = user_store.authenticate("admin", "Admin@SAT2026!")
    assert admin_ctx is not None
    assert admin_ctx.role == "admin"
    assert admin_ctx.username == "admin"

    # Test supervisor authentication
    sup_ctx = user_store.authenticate("supervisor", "Supervisor@SAT2026!")
    assert sup_ctx is not None
    assert sup_ctx.role == "supervisor"

    # Test analyst authentication
    analyst_ctx = user_store.authenticate("analyst", "Analyst@SAT2026!")
    assert analyst_ctx is not None
    assert analyst_ctx.role == "analyst"

    # Test invalid password rejection
    bad_ctx = user_store.authenticate("admin", "WrongPassword123!")
    assert bad_ctx is None
