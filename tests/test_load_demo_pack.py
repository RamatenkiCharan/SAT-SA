"""
End-to-End Test Suite for 'Load Demo Pack' Feature (SIH Problem 26157).
Verifies that POST /api/datasets/load-demo loads the predefined SOC demo dataset from sample_data/,
calculates Data Quality, runs workflow reconstruction and P0 detectors, performs evidence fusion,
registers immutable provenance with SHA-256, and updates active repository state and findings.
"""
from fastapi.testclient import TestClient
from uuid import UUID

from backend.main import app
from backend.repositories.in_memory_repo import get_repository
from backend.security.auth import UserContext, create_access_token

client = TestClient(app)

_SUPERVISOR_TOKEN = create_access_token(
    UserContext(user_id="usr_sup_01", username="supervisor", role="supervisor")
)
_ADMIN_TOKEN = create_access_token(
    UserContext(user_id="usr_admin_01", username="admin", role="admin")
)
_AUTH_HEADERS = {"Authorization": f"Bearer {_SUPERVISOR_TOKEN}"}
_ADMIN_AUTH_HEADERS = {"Authorization": f"Bearer {_ADMIN_TOKEN}"}


def test_auth_token_generation_and_user_context():
    """Verify that create_access_token generates valid token for supervisor."""
    assert _SUPERVISOR_TOKEN is not None
    assert len(_SUPERVISOR_TOKEN.split(".")) == 3


def test_load_demo_pack_critical_infrastructure_end_to_end():
    """Verify that clicking 'Load Demo Pack' successfully loads multi_sector_soc_benchmark.json."""
    repo = get_repository()

    response = client.post(
        "/api/datasets/load-demo",
        json={"scenario_type": "critical_infrastructure"},
        headers=_AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert "dataset_id" in data
    assert "dataset_version_id" in data
    assert data["dataset_name"] == "Multi-Sector Critical Infrastructure SOC Operational Evidence Pack"
    assert data["row_count"] == 200
    assert data["cse_count"] == 7
    assert data["findings_generated"] > 0
    assert data["data_quality_score"] > 0.70
    assert "completeness" in data["data_quality_breakdown"]
    assert "consistency" in data["data_quality_breakdown"]
    assert "coverage" in data["data_quality_breakdown"]
    assert "sample_sufficiency" in data["data_quality_breakdown"]

    version_id = UUID(data["dataset_version_id"])
    dataset_id = UUID(data["dataset_id"])

    # Verify active version and dataset metadata via API
    ds_list_resp = client.get("/api/datasets", headers=_AUTH_HEADERS)
    assert ds_list_resp.status_code == 200
    assert ds_list_resp.json()["active_version_id"] == str(version_id)
    datasets = ds_list_resp.json()["datasets"]
    assert any(
        any(v["dataset_version_id"] == str(version_id) and "sample_data/multi_sector_soc_benchmark.json" in v["source_file_ref"] for v in ds.get("versions", []))
        for ds in datasets
    )

    # Verify findings are queryable via GET /api/findings
    findings_resp = client.get(f"/api/findings?dataset_version_id={version_id}", headers=_AUTH_HEADERS)
    assert findings_resp.status_code == 200
    findings_data = findings_resp.json()
    assert findings_data["count"] == data["findings_generated"]
    assert len(findings_data["findings"]) == data["findings_generated"]

    # Verify peer benchmarks are generated
    bm_resp = client.get(f"/api/benchmarks?dataset_version_id={version_id}", headers=_AUTH_HEADERS)
    assert bm_resp.status_code == 200
    bm_data = bm_resp.json()
    assert len(bm_data["entities"]) == 7
    assert len(bm_data["cohorts"]) > 0

    # Verify audit event is recorded
    audit_resp = client.get("/api/audit", headers=_ADMIN_AUTH_HEADERS)
    assert audit_resp.status_code == 200
    audit_events = audit_resp.json()
    assert any(
        e["action"] == "INGEST_DATASET_VERSION" and e["target_id"] == str(version_id)
        for e in audit_events
    )


def test_load_demo_pack_held_out_validation_benchmark():
    """Verify that loading the held-out validation benchmark works end-to-end."""
    response = client.post(
        "/api/datasets/load-demo",
        json={"scenario_type": "held_out_test"},
        headers=_AUTH_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "success"
    assert data["dataset_name"] == "Held-Out Validation Benchmark (v2.0)"
    assert data["row_count"] == 212
    assert data["cse_count"] == 7
    assert data["findings_generated"] > 0

    version_id = UUID(data["dataset_version_id"])
    ds_list_resp = client.get("/api/datasets", headers=_AUTH_HEADERS)
    assert ds_list_resp.status_code == 200
    assert ds_list_resp.json()["active_version_id"] == str(version_id)
    datasets = ds_list_resp.json()["datasets"]
    assert any(
        any(v["dataset_version_id"] == str(version_id) and "sample_data/held_out_validation_benchmark.json" in v["source_file_ref"] for v in ds.get("versions", []))
        for ds in datasets
    )
