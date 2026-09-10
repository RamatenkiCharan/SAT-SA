"""
Strict Authentication & RBAC Tests (FIX 2 — anonymous fallback removed).

Verifies that after removing the anonymous supervisor fallback:
1. Unauthenticated requests to protected endpoints receive HTTP 401.
2. Analyst token cannot access supervisor-only endpoints (403).
3. Analyst token CAN access analyst-accessible endpoints (200).
4. Supervisor token can access all supervisor endpoints.
5. Admin token can access admin-only endpoints.
6. X-User-Role header manipulation is ignored (does not grant roles).
"""
from __future__ import annotations

import io
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app, raise_server_exceptions=False)


def _get_token(username: str, password: str) -> str:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Unauthenticated requests must return 401 (not 200 with supervisor data)
# ---------------------------------------------------------------------------

def test_unauthenticated_datasets_returns_401():
    """GET /api/datasets without token must return 401, not 200."""
    resp = client.get("/api/datasets")
    assert resp.status_code == 401, f"Expected 401 but got {resp.status_code}: {resp.text}"


def test_unauthenticated_findings_returns_401():
    """GET /api/findings without token must return 401."""
    resp = client.get("/api/findings")
    assert resp.status_code == 401, f"Expected 401 but got {resp.status_code}: {resp.text}"


def test_unauthenticated_validation_returns_401():
    """GET /api/validation without token must return 401."""
    resp = client.get("/api/validation")
    assert resp.status_code == 401, f"Expected 401 but got {resp.status_code}: {resp.text}"


def test_unauthenticated_reviews_post_returns_401():
    """POST /api/reviews without token must return 401."""
    resp = client.post(
        "/api/reviews",
        json={"finding_id": str(uuid4()), "decision": "CONFIRMED", "notes": "test"},
    )
    assert resp.status_code == 401, f"Expected 401 but got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# 2. X-User-Role header must NOT grant admin/supervisor access
# ---------------------------------------------------------------------------

def test_x_user_role_header_does_not_grant_access():
    """
    X-User-Role: admin header must NOT substitute for a real Bearer token.
    The old anonymous fallback accepted this pattern; the fix removes it.
    """
    resp = client.get("/api/datasets", headers={"X-User-Role": "admin"})
    assert resp.status_code == 401, (
        f"X-User-Role header should not grant access but got {resp.status_code}"
    )


def test_x_user_role_supervisor_does_not_grant_access():
    """X-User-Role: supervisor must be rejected without a real token."""
    resp = client.get("/api/findings", headers={"X-User-Role": "supervisor"})
    assert resp.status_code == 401, (
        f"X-User-Role header should not grant access but got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# 3. Invalid token returns 401
# ---------------------------------------------------------------------------

def test_tampered_token_returns_401():
    """A malformed / tampered Bearer token must return 401."""
    resp = client.get("/api/datasets", headers={"Authorization": "Bearer tampered.garbage.token"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 4. Analyst can access GET endpoints but not supervisor actions
# ---------------------------------------------------------------------------

def test_analyst_can_list_findings():
    """Analyst token must successfully GET /api/findings (200)."""
    token = _get_token("analyst", "sih2026@analyst")
    resp = client.get("/api/findings", headers=_auth(token))
    assert resp.status_code == 200


def test_analyst_can_list_datasets():
    """Analyst token must successfully GET /api/datasets (200)."""
    token = _get_token("analyst", "sih2026@analyst")
    resp = client.get("/api/datasets", headers=_auth(token))
    assert resp.status_code == 200


def test_analyst_cannot_submit_review():
    """Analyst cannot POST to /api/reviews (supervisor action) — must return 403."""
    token = _get_token("analyst", "sih2026@analyst")
    resp = client.post(
        "/api/reviews",
        json={"finding_id": str(uuid4()), "decision": "CONFIRMED", "notes": "analyst attempt"},
        headers=_auth(token),
    )
    assert resp.status_code == 403, f"Analyst review should be 403 but got {resp.status_code}"


def test_analyst_cannot_switch_active_version():
    """Analyst cannot POST /api/datasets/switch-version (supervisor action)."""
    token = _get_token("analyst", "sih2026@analyst")
    resp = client.post(
        "/api/datasets/switch-version",
        json={"dataset_version_id": str(uuid4())},
        headers=_auth(token),
    )
    assert resp.status_code == 403, (
        f"Analyst switch-version should be 403 but got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# 5. Supervisor can access supervisor endpoints
# ---------------------------------------------------------------------------

def test_supervisor_can_list_datasets():
    """Supervisor token must successfully GET /api/datasets."""
    token = _get_token("supervisor", "sih2026@supervisor")
    resp = client.get("/api/datasets", headers=_auth(token))
    assert resp.status_code == 200


def test_supervisor_can_access_validation():
    """Supervisor token must successfully GET /api/validation."""
    token = _get_token("supervisor", "sih2026@supervisor")
    resp = client.get("/api/validation", headers=_auth(token))
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 6. Admin can access admin-only /api/auth/users endpoint
# ---------------------------------------------------------------------------

def test_admin_can_list_users():
    """Admin token must successfully GET /api/auth/users."""
    token = _get_token("admin", "sih2026@admin")
    resp = client.get("/api/auth/users", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    usernames = {u["username"] for u in data}
    assert "supervisor" in usernames
    assert "analyst" in usernames
    assert "admin" in usernames


def test_analyst_cannot_list_users():
    """Analyst cannot access admin-only /api/auth/users — must return 403."""
    token = _get_token("analyst", "sih2026@analyst")
    resp = client.get("/api/auth/users", headers=_auth(token))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# 7. /api/health is public (no auth required)
# ---------------------------------------------------------------------------

def test_health_endpoint_is_public():
    """GET /api/health must return 200 without any token."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
