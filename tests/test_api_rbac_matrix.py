"""
API-Level Role-Based Access Control (RBAC) Matrix Test Suite.
Verifies:
1. Public endpoints (accessible without credentials).
2. Authenticated endpoints (accessible to analyst, supervisor, admin; 401 if unauthenticated).
3. Supervisor/Admin endpoints (accessible to supervisor and admin; 403 for analyst, 401 if unauthenticated).
4. Admin-Only endpoints (accessible to admin only; 403 for supervisor and analyst, 401 if unauthenticated).
5. Immunity against header/parameter spoofing (X-User-Role cannot bypass auth or escalate privileges).
"""
from __future__ import annotations

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.repositories.in_memory_repo import get_repository


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_tokens(client: TestClient):
    """Obtains authentic signed Bearer tokens for each role."""
    roles = {
        "admin": ("admin", "Admin@SAT2026!"),
        "supervisor": ("supervisor", "Supervisor@SAT2026!"),
        "analyst": ("analyst", "Analyst@SAT2026!"),
    }
    tokens = {}
    for role, (user, pwd) in roles.items():
        resp = client.post("/api/auth/login", json={"username": user, "password": pwd})
        assert resp.status_code == 200, f"Login failed for {role}: {resp.text}"
        tokens[role] = resp.json()["access_token"]
    return tokens


@pytest.fixture(scope="module", autouse=True)
def seed_benchmark_data(client: TestClient, auth_tokens: dict[str, str]):
    """Pre-seeds demo benchmark data so finding and dataset routes have records."""
    headers = {"Authorization": f"Bearer {auth_tokens['supervisor']}"}
    resp = client.post("/api/datasets/load-demo", json={"scenario_type": "critical_infrastructure"}, headers=headers)
    assert resp.status_code == 200


# ===========================================================================
# 1. Public Endpoints
# ===========================================================================

def test_public_health_endpoint(client: TestClient):
    """GET /api/health is public and requires no credentials."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_public_auth_login_endpoint(client: TestClient):
    """POST /api/auth/login is public."""
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@SAT2026!"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "success"


# ===========================================================================
# 2. Authenticated Endpoints (analyst, supervisor, admin)
# ===========================================================================

@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/me",
        "/api/datasets",
        "/api/findings",
        "/api/reviews",
        "/api/benchmarks",
    ],
)
def test_authenticated_endpoints_require_token(client: TestClient, path: str):
    """Unauthenticated requests to authenticated endpoints return 401."""
    resp = client.get(path)
    assert resp.status_code == 401
    assert "Missing authentication token" in resp.json()["detail"]


@pytest.mark.parametrize(
    "path",
    [
        "/api/auth/me",
        "/api/datasets",
        "/api/findings",
        "/api/reviews",
        "/api/benchmarks",
    ],
)
def test_authenticated_endpoints_accessible_to_all_roles(
    client: TestClient, auth_tokens: dict[str, str], path: str
):
    """Analyst, supervisor, and admin can all access general authenticated endpoints."""
    for role in ["analyst", "supervisor", "admin"]:
        headers = {"Authorization": f"Bearer {auth_tokens[role]}"}
        resp = client.get(path, headers=headers)
        assert resp.status_code == 200, f"Role {role} failed on {path}: {resp.text}"


# ===========================================================================
# 3. Supervisor / Admin Endpoints (supervisor, admin only)
# ===========================================================================

def test_supervisor_review_submission_rbac(client: TestClient, auth_tokens: dict[str, str]):
    """POST /api/reviews: unauthenticated -> 401, analyst -> 403, supervisor -> 200, admin -> 200."""
    repo = get_repository()
    all_findings = repo.get_findings()
    finding_id = str(all_findings[0].finding_id) if all_findings else str(uuid4())
    payload = {"finding_id": finding_id, "decision": "CONFIRMED", "notes": "RBAC verification"}

    # 1. Unauthenticated -> 401
    resp_unauth = client.post("/api/reviews", json=payload)
    assert resp_unauth.status_code == 401

    # 2. Analyst -> 403 Forbidden
    resp_analyst = client.post(
        "/api/reviews",
        json=payload,
        headers={"Authorization": f"Bearer {auth_tokens['analyst']}"},
    )
    assert resp_analyst.status_code == 403
    assert "Forbidden" in resp_analyst.json()["detail"]

    # 3. Supervisor -> 200 OK
    resp_sup = client.post(
        "/api/reviews",
        json=payload,
        headers={"Authorization": f"Bearer {auth_tokens['supervisor']}"},
    )
    assert resp_sup.status_code == 200

    # 4. Admin -> 200 OK
    resp_admin = client.post(
        "/api/reviews",
        json=payload,
        headers={"Authorization": f"Bearer {auth_tokens['admin']}"},
    )
    assert resp_admin.status_code == 200


def test_supervisor_dataset_upload_rbac(client: TestClient, auth_tokens: dict[str, str]):
    """POST /api/datasets/upload: unauthenticated -> 401, analyst -> 403, supervisor -> 200."""
    csv_bytes = b"alert_id,severity,alert_category,source,status,event_time\n1,HIGH,Auth,SIEM,OPEN,2026-01-01T00:00:00Z"
    files = {"file": ("rbac_upload.csv", csv_bytes, "text/csv")}

    # 1. Unauthenticated -> 401
    resp_unauth = client.post("/api/datasets/upload", files=files)
    assert resp_unauth.status_code == 401

    # 2. Analyst -> 403 Forbidden
    resp_analyst = client.post(
        "/api/datasets/upload",
        files={"file": ("rbac_upload.csv", csv_bytes, "text/csv")},
        headers={"Authorization": f"Bearer {auth_tokens['analyst']}"},
    )
    assert resp_analyst.status_code == 403

    # 3. Supervisor -> 200 OK
    resp_sup = client.post(
        "/api/datasets/upload",
        files={"file": ("rbac_upload.csv", csv_bytes, "text/csv")},
        headers={"Authorization": f"Bearer {auth_tokens['supervisor']}"},
    )
    assert resp_sup.status_code == 200


def test_supervisor_validation_endpoint_rbac(client: TestClient, auth_tokens: dict[str, str]):
    """GET /api/validation: unauthenticated -> 401, analyst -> 403, supervisor -> 200, admin -> 200."""
    # 1. Unauthenticated -> 401
    assert client.get("/api/validation").status_code == 401

    # 2. Analyst -> 403 Forbidden
    resp_analyst = client.get("/api/validation", headers={"Authorization": f"Bearer {auth_tokens['analyst']}"})
    assert resp_analyst.status_code == 403

    # 3. Supervisor -> 200 OK
    resp_sup = client.get("/api/validation", headers={"Authorization": f"Bearer {auth_tokens['supervisor']}"})
    assert resp_sup.status_code == 200

    # 4. Admin -> 200 OK
    resp_admin = client.get("/api/validation", headers={"Authorization": f"Bearer {auth_tokens['admin']}"})
    assert resp_admin.status_code == 200


def test_supervisor_export_report_rbac(client: TestClient, auth_tokens: dict[str, str]):
    """GET /api/export/report: unauthenticated -> 401, analyst -> 403, supervisor -> 200, admin -> 200."""
    # 1. Unauthenticated -> 401
    assert client.get("/api/export/report").status_code == 401

    # 2. Analyst -> 403 Forbidden
    resp_analyst = client.get("/api/export/report", headers={"Authorization": f"Bearer {auth_tokens['analyst']}"})
    assert resp_analyst.status_code == 403

    # 3. Supervisor -> 200 OK
    resp_sup = client.get("/api/export/report", headers={"Authorization": f"Bearer {auth_tokens['supervisor']}"})
    assert resp_sup.status_code == 200

    # 4. Admin -> 200 OK
    resp_admin = client.get("/api/export/report", headers={"Authorization": f"Bearer {auth_tokens['admin']}"})
    assert resp_admin.status_code == 200


# ===========================================================================
# 4. Supervisor-Level Endpoints (supervisor + admin)
# ===========================================================================

def test_audit_endpoint_rbac(client: TestClient, auth_tokens: dict[str, str]):
    """GET /api/audit: unauthenticated -> 401, analyst -> 403, supervisor -> 200, admin -> 200."""
    # 1. Unauthenticated -> 401
    assert client.get("/api/audit").status_code == 401

    # 2. Analyst -> 403 Forbidden
    resp_analyst = client.get("/api/audit", headers={"Authorization": f"Bearer {auth_tokens['analyst']}"})
    assert resp_analyst.status_code == 403

    # 3. Supervisor -> 200 OK (supervisor can inspect audit ledger)
    resp_sup = client.get("/api/audit", headers={"Authorization": f"Bearer {auth_tokens['supervisor']}"})
    assert resp_sup.status_code == 200
    assert isinstance(resp_sup.json(), list)

    # 4. Admin -> 200 OK
    resp_admin = client.get("/api/audit", headers={"Authorization": f"Bearer {auth_tokens['admin']}"})
    assert resp_admin.status_code == 200
    assert isinstance(resp_admin.json(), list)


def test_admin_only_user_roster_rbac(client: TestClient, auth_tokens: dict[str, str]):
    """GET /api/auth/users: unauthenticated -> 401, analyst -> 403, supervisor -> 403, admin -> 200."""
    # 1. Unauthenticated -> 401
    assert client.get("/api/auth/users").status_code == 401

    # 2. Analyst -> 403 Forbidden
    resp_analyst = client.get("/api/auth/users", headers={"Authorization": f"Bearer {auth_tokens['analyst']}"})
    assert resp_analyst.status_code == 403

    # 3. Supervisor -> 403 Forbidden
    resp_sup = client.get("/api/auth/users", headers={"Authorization": f"Bearer {auth_tokens['supervisor']}"})
    assert resp_sup.status_code == 403

    # 4. Admin -> 200 OK
    resp_admin = client.get("/api/auth/users", headers={"Authorization": f"Bearer {auth_tokens['admin']}"})
    assert resp_admin.status_code == 200
    assert len(resp_admin.json()) >= 3


# ===========================================================================
# 5. Header / Parameter Spoofing Resistance
# ===========================================================================

def test_header_spoofing_cannot_bypass_rbac_or_escalate_roles(client: TestClient, auth_tokens: dict[str, str]):
    """
    Sending X-User-Role: admin or role headers cannot bypass auth or escalate privileges.
    Uses /api/auth/users (admin-only) to verify spoofing resistance.
    """
    # 1. Unauthenticated claiming X-User-Role: admin -> 401
    resp = client.get("/api/auth/users", headers={"X-User-Role": "admin", "X-User-Id": "root"})
    assert resp.status_code == 401

    # 2. Analyst claiming X-User-Role: admin on admin-only route -> 403
    resp_analyst = client.get(
        "/api/auth/users",
        headers={
            "Authorization": f"Bearer {auth_tokens['analyst']}",
            "X-User-Role": "admin",
            "X-User-Id": "root",
        },
    )
    assert resp_analyst.status_code == 403

    # 3. Supervisor claiming X-User-Role: admin on admin-only route -> 403
    resp_sup = client.get(
        "/api/auth/users",
        headers={
            "Authorization": f"Bearer {auth_tokens['supervisor']}",
            "X-User-Role": "admin",
        },
    )
    assert resp_sup.status_code == 403

