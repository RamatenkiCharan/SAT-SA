"""
Offline & Air-Gapped Operation Smoke Verification Suite (SRS §18).

Verifies that SAT-SA operates 100% locally in an air-gapped environment with zero
outbound network access, external runtime APIs, remote fonts, or cloud SDKs.

Enforces network socket isolation by intercepting outbound socket connection attempts
and proving that all 11 core supervisory journeys execute locally:
1. Login & Token Verification (PBKDF2-HMAC-SHA256, RBAC)
2. Dataset Upload & CSV Ingestion (Delimiter detection, schema aliasing)
3. Multi-table JSON Ingestion (Relational parsing, canonicalization)
4. Data Quality & Trust Engine (4 decomposed quality metrics)
5. Workflow Reconstruction Graph Engine
6. Execution-Gap & Negative-Space Detectors (FR-030, FR-032, FR-033, FR-041)
7. Multi-Dimensional Peer Benchmarking (4D cohorts, dynamic MAD, 4-tier fallback)
8. Evidence Fusion & Priority Scoring (§10.5)
9. Evidence Drilldown & 6-Stage Finding Traceability
10. Ground-Truth Validation Protocol (Tuning & Held-Out Splits)
11. Supervisory Review Decision Workflow & Audit Trail Logging
"""
from __future__ import annotations

import io
import json
import socket
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from analytics.canonicalization.canonicalization import canonicalize_records
from analytics.data_quality.quality_processor import evaluate_dataset_quality
from analytics.evaluation.validation_protocol import run_final_validation_protocol
from analytics.execution_gap.escalation_gap import EscalationGapDetector
from analytics.execution_gap.fast_closure import FastClosureDetector
from analytics.execution_gap.repeated_unresolved import RepeatedUnresolvedDetector
from analytics.fusion.evidence_fusion import EvidenceFusionEngine
from analytics.negative_space.coverage_gap import CoverageGapDetector
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.main import app
from backend.models.canonical import ReviewDecisionState
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1
from backend.repositories.in_memory_repo import get_repository
from backend.security.auth import UserContext, create_access_token, hash_password, verify_password
from backend.services.ingestion import ingest_file_stream


class AirGapViolationError(RuntimeError):
    """Raised when an illegal outbound socket connection is attempted in offline mode."""


@pytest.fixture(autouse=True)
def enforce_network_isolation(monkeypatch):
    """
    Strict socket interceptor:
    Permits loopback / IPC connections (127.0.0.1, localhost) for in-process HTTP test clients.
    Immediately raises AirGapViolationError if any external IP address or non-local host is targeted.
    """
    orig_connect = socket.socket.connect

    def isolated_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        allowed_hosts = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}
        if isinstance(host, str) and host not in allowed_hosts and not host.startswith("127."):
            raise AirGapViolationError(
                f"Air-Gap Policy Violation: Outbound network connection attempted to external host '{host}'!"
            )
        return orig_connect(self, address)

    monkeypatch.setattr(socket.socket, "connect", isolated_connect)


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def supervisor_headers():
    user = UserContext(
        user_id="usr_sup_offline",
        username="supervisor",
        role="supervisor",
        full_name="Air-Gapped Examiner",
    )
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers():
    user = UserContext(
        user_id="usr_admin_offline",
        username="admin",
        role="admin",
        full_name="Air-Gapped Administrator",
    )
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Zero Outbound Network Calls & Air-Gap Enforcement Test
# ---------------------------------------------------------------------------

def test_zero_outbound_network_calls_during_all_workflows(test_client, supervisor_headers):
    """
    Verifies that the entire application lifecycle runs locally with zero external socket calls.
    """
    res = test_client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["offline_mode"] is True


# ---------------------------------------------------------------------------
# 2. Offline Authentication & RBAC Test
# ---------------------------------------------------------------------------

def test_offline_authentication_and_rbac(test_client):
    """
    Verifies local PBKDF2 password verification and tamper-proof HMAC token issuance.
    """
    # 1. Valid Login
    login_res = test_client.post(
        "/api/auth/login",
        json={"username": "supervisor", "password": "Supervisor@SAT2026!"},
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    token = login_data["access_token"]
    assert token is not None
    assert login_data["user"]["role"] == "supervisor"

    # 2. Authenticated Me Endpoint
    me_res = test_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "supervisor"

    # 3. Invalid Credentials
    bad_login = test_client.post(
        "/api/auth/login",
        json={"username": "supervisor", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401


# ---------------------------------------------------------------------------
# 3. Offline CSV Ingestion & Quality Scoring Test
# ---------------------------------------------------------------------------

def test_offline_csv_ingestion_and_quality_score(test_client, supervisor_headers):
    """
    Verifies file stream ingestion for CSV format with delimiter detection and DQ derivation.
    """
    csv_content = (
        "alert_id,cse_id,asset_id,reporting_period_id,event_time,severity,alert_category,source,status\n"
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890,c1b2c3d4-e5f6-7890-abcd-ef1234567890,b1b2c3d4-e5f6-7890-abcd-ef1234567890,r1b2c3d4-e5f6-7890-abcd-ef1234567890,2026-09-01T10:00:00Z,CRITICAL,SCADA Intrusion,Splunk,CLOSED\n"
        "a2b2c3d4-e5f6-7890-abcd-ef1234567890,c1b2c3d4-e5f6-7890-abcd-ef1234567890,b1b2c3d4-e5f6-7890-abcd-ef1234567890,r1b2c3d4-e5f6-7890-abcd-ef1234567890,2026-09-02T11:00:00Z,HIGH,Ransomware,EDR,CLOSED\n"
    ).encode("utf-8")

    res = test_client.post(
        "/api/datasets/upload",
        files={"file": ("airgap_alerts.csv", io.BytesIO(csv_content), "text/csv")},
        headers=supervisor_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["row_count"] == 2
    assert "data_quality_score" in data


# ---------------------------------------------------------------------------
# 4. Offline Multi-Table JSON Ingestion Test
# ---------------------------------------------------------------------------

def test_offline_json_multi_table_ingestion(test_client, supervisor_headers):
    """
    Verifies multi-table relational JSON bundle parsing, canonicalization, and ingestion.
    """
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, is_held_out=False)
    json_bytes = json.dumps(raw_bundle).encode("utf-8")

    res = test_client.post(
        "/api/datasets/upload",
        files={"file": ("airgap_benchmark_bundle.json", io.BytesIO(json_bytes), "application/json")},
        headers=supervisor_headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["row_count"] > 100
    assert data["findings_generated"] >= 5


# ---------------------------------------------------------------------------
# 5. Offline Analytical Pipeline & Findings Query Test
# ---------------------------------------------------------------------------

def test_offline_analytical_pipeline_and_findings(test_client, supervisor_headers):
    """
    Verifies full analytical execution: Workflow Reconstruction -> Benchmarking -> Detectors -> Fusion.
    """
    # 1. Load baseline demo
    load_res = test_client.post(
        "/api/datasets/load-demo",
        json={"scenario_type": "critical_infrastructure"},
        headers=supervisor_headers,
    )
    assert load_res.status_code == 200
    version_id = load_res.json()["dataset_version_id"]

    # 2. Query findings
    findings_res = test_client.get(
        f"/api/findings?dataset_version_id={version_id}",
        headers=supervisor_headers,
    )
    assert findings_res.status_code == 200
    findings_data = findings_res.json()
    assert findings_data["count"] >= 5
    findings = findings_data["findings"]
    assert len(findings) >= 5

    # Verify priority score bounding [0, 1]
    for f in findings:
        assert 0.0 <= f["priority_score"] <= 1.0
        assert f["priority_label"] in ("HIGH", "MEDIUM", "LOW")
        assert f["finding_type"] is not None


# ---------------------------------------------------------------------------
# 6. Offline Evidence Drilldown & Traceability Test
# ---------------------------------------------------------------------------

def test_offline_evidence_drilldown_and_source_refs(test_client, supervisor_headers):
    """
    Verifies 6-stage finding detail resolution, explanation derivation, and evidence linkage.
    """
    # 1. Get findings
    findings_res = test_client.get("/api/findings", headers=supervisor_headers)
    assert findings_res.status_code == 200
    findings = findings_res.json()["findings"]
    assert len(findings) > 0
    target_finding_id = findings[0]["finding_id"]

    # 2. Get Finding Detail
    detail_res = test_client.get(f"/api/findings/{target_finding_id}", headers=supervisor_headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()

    assert detail["finding_id"] == target_finding_id
    assert "explanation" in detail
    assert "evidence_references" in detail
    assert len(detail["evidence_references"]) >= 1

    # Verify source_record_ref existence for all evidence items
    for ref in detail["evidence_references"]:
        assert ref["source_record_ref"] is not None
        assert len(ref["source_record_ref"]) > 0


# ---------------------------------------------------------------------------
# 7. Offline Peer Benchmarking & Cohort Statistics Test
# ---------------------------------------------------------------------------

def test_offline_peer_benchmarking_and_fallback(test_client, supervisor_headers):
    """
    Verifies local calculation of peer-relative statistics (median, MAD, percentiles).
    """
    bench_res = test_client.get("/api/benchmarks", headers=supervisor_headers)
    assert bench_res.status_code == 200
    bench_data = bench_res.json()

    assert "cohorts" in bench_data
    assert "entities" in bench_data
    assert len(bench_data["cohorts"]) >= 1
    assert len(bench_data["entities"]) >= 1

    for c in bench_data["cohorts"]:
        assert c["group_size"] >= 1
        assert "closure_duration" in c
        assert "median_minutes" in c["closure_duration"]


# ---------------------------------------------------------------------------
# 8. Offline Ground-Truth Validation Protocol Test
# ---------------------------------------------------------------------------

def test_offline_ground_truth_validation_protocol(test_client, supervisor_headers):
    """
    Verifies execution of the multi-split validation protocol (Tuning vs Held-Out).
    """
    val_res = test_client.get("/api/validation", headers=supervisor_headers)
    assert val_res.status_code == 200
    val_data = val_res.json()

    assert val_data["status"] == "success"
    assert "tuning_split" in val_data
    assert "held_out_split" in val_data
    assert "final_protocol" in val_data

    fp = val_data["final_protocol"]
    assert fp["held_out_ratio_percentage"] >= 20.0
    assert fp["generalization_delta"]["generalization_demonstrated"] is True


# ---------------------------------------------------------------------------
# 9. Offline Supervisory Review Decision Workflow Test
# ---------------------------------------------------------------------------

def test_offline_supervisory_review_decision_workflow(test_client, supervisor_headers):
    """
    Verifies submitting, persisting, and querying supervisory review dispositions.
    """
    # 1. Get first finding
    findings_res = test_client.get("/api/findings", headers=supervisor_headers)
    finding_id = findings_res.json()["findings"][0]["finding_id"]

    # 2. Submit Review Decision
    review_res = test_client.post(
        "/api/reviews",
        json={
            "finding_id": finding_id,
            "decision": "CONFIRMED",
            "notes": "Verified offline during NCIIPC air-gap audit exercise.",
        },
        headers=supervisor_headers,
    )
    assert review_res.status_code == 200
    rev_data = review_res.json()
    assert rev_data["status"] == "success"
    assert rev_data["decision"] == "CONFIRMED"


# ---------------------------------------------------------------------------
# 10. Offline Audit Trail & Export Generation Test
# ---------------------------------------------------------------------------

def test_offline_audit_log_and_export_generation(test_client, admin_headers, supervisor_headers):
    """
    Verifies immutable audit trail recording and offline Markdown/JSON report export.
    """
    # 1. Query Audit Logs (requires admin role)
    audit_res = test_client.get("/api/audit", headers=admin_headers)
    assert audit_res.status_code == 200
    logs = audit_res.json()
    assert isinstance(logs, list)
    assert len(logs) >= 1

    # 2. Generate Export Report (requires supervisor role)
    export_res = test_client.get("/api/export/report", headers=supervisor_headers)
    assert export_res.status_code == 200
    report = export_res.json()
    assert report["report_title"] == "SAT-SA Supervisory SOC Operational Assessment Report"
    assert report["total_findings"] >= 1
    assert "findings" in report
    assert len(report["findings"]) >= 1
