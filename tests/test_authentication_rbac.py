"""
Authentication & Role-Based Access Control (RBAC) Test Suite.
Tests:
1. Successful authentication and token issuance for admin, supervisor, and analyst roles.
2. Rejection of invalid passwords with HTTP 401.
3. Rejection of unknown usernames with HTTP 401.
4. Rejection of missing, malformed, tampered, and expired Bearer tokens on protected endpoints.
5. Inability to spoof identity or escalate privileges using X-User-Role headers.
6. Strict role hierarchy enforcement (supervisor/admin actions vs analyst restrictions).
7. Password hashing verification (zero plaintext storage).
"""
from __future__ import annotations

import base64
import json
import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.canonical import ReviewDecisionState
from backend.repositories.in_memory_repo import SATRepository, get_repository
from backend.security.auth import (
    UserContext,
    create_access_token,
    get_user_store,
    hash_password,
    verify_password,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_successful_login_all_roles(client: TestClient):
    """Test successful authentication for all supported roles."""
    roles_and_passwords = [
        ("admin", "Admin@SAT2026!", "admin"),
        ("supervisor", "Supervisor@SAT2026!", "supervisor"),
        ("analyst", "Analyst@SAT2026!", "analyst"),
    ]

    for username, password, expected_role in roles_and_passwords:
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        assert resp.status_code == 200, f"Login failed for {username}: {resp.text}"
        data = resp.json()
        assert data["status"] == "success"
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == username
        assert data["user"]["role"] == expected_role
        assert "password" not in data["user"]


def test_invalid_password_returns_401(client: TestClient):
    """Wrong password returns HTTP 401 Unauthorized."""
    resp = client.post("/api/auth/login", json={"username": "supervisor", "password": "WrongPassword123!"})
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.json()["detail"]


def test_unknown_user_returns_401(client: TestClient):
    """Unknown username returns HTTP 401 Unauthorized."""
    resp = client.post("/api/auth/login", json={"username": "non_existent_user", "password": "AnyPassword!"})
    assert resp.status_code == 401
    assert "Invalid username or password" in resp.json()["detail"]


def test_missing_token_returns_401(client: TestClient):
    """Protected endpoints require Bearer token; omitting it returns HTTP 401."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert "Missing authentication token" in resp.json()["detail"]


def test_tampered_token_rejected(client: TestClient):
    """Modifying token payload or signature fails validation with HTTP 401."""
    # 1. Login to get a valid token
    resp = client.post("/api/auth/login", json={"username": "analyst", "password": "Analyst@SAT2026!"})
    valid_token = resp.json()["access_token"]
    header_b64, payload_b64, sig_b64 = valid_token.split(".")

    # 2. Tamper with payload to elevate role to 'admin'
    payload_json = json.loads(base64.urlsafe_b64decode(payload_b64 + "==").decode("utf-8"))
    payload_json["role"] = "admin"
    tampered_payload_b64 = base64.urlsafe_b64encode(json.dumps(payload_json).encode("utf-8")).decode("utf-8").rstrip("=")
    tampered_token = f"{header_b64}.{tampered_payload_b64}.{sig_b64}"

    # 3. Request with tampered token
    tampered_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
    assert tampered_resp.status_code == 401
    assert "Invalid token signature" in tampered_resp.json()["detail"]


def test_expired_token_rejected(client: TestClient):
    """An expired token returns HTTP 401."""
    user = UserContext(user_id="u1", username="test_exp", role="analyst")
    # Token expired 10 seconds ago
    expired_token = create_access_token(user, expires_in_seconds=-10)

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_x_user_role_header_spoofing_fails(client: TestClient):
    """
    CRITICAL SUCCESS CONDITION:
    Sending X-User-Role: admin headers CANNOT bypass authentication or grant admin access.
    """
    # 1. Unauthenticated request claiming X-User-Role: admin -> 401 (not bypassed!)
    resp_unauth = client.post(
        "/api/reviews",
        json={"finding_id": str(uuid4()), "decision": "CONFIRMED", "notes": "Spoofed attempt"},
        headers={"X-User-Role": "admin", "X-User-Name": "Hacker", "X-User-Id": "hack_01"},
    )
    assert resp_unauth.status_code == 401
    assert "Missing authentication token" in resp_unauth.json()["detail"]

    # 2. Authenticated as 'analyst' with token, but sending X-User-Role: admin -> 403 Forbidden!
    login_resp = client.post("/api/auth/login", json={"username": "analyst", "password": "Analyst@SAT2026!"})
    analyst_token = login_resp.json()["access_token"]

    resp_analyst_spoof = client.post(
        "/api/reviews",
        json={"finding_id": str(uuid4()), "decision": "CONFIRMED", "notes": "Analyst role spoof"},
        headers={
            "Authorization": f"Bearer {analyst_token}",
            "X-User-Role": "admin",
            "X-User-Id": "admin_root",
        },
    )
    # Analyst cannot submit supervisory review decisions even if claiming X-User-Role: admin
    assert resp_analyst_spoof.status_code == 403
    assert "Forbidden: Insufficient privileges" in resp_analyst_spoof.json()["detail"]


def test_role_hierarchy_permissions(client: TestClient):
    """Supervisor can submit review decisions; Analyst is forbidden."""
    # 1. Login as supervisor
    sup_login = client.post("/api/auth/login", json={"username": "supervisor", "password": "Supervisor@SAT2026!"})
    sup_token = sup_login.json()["access_token"]
    sup_headers = {"Authorization": f"Bearer {sup_token}"}

    # Load demo dataset so real findings exist
    demo_resp = client.post("/api/datasets/load-demo", json={"scenario_type": "critical_infrastructure"}, headers=sup_headers)
    assert demo_resp.status_code == 200

    repo = get_repository()
    all_findings = repo.get_findings()
    assert len(all_findings) > 0
    finding_id = str(all_findings[0].finding_id)

    # 2. Supervisor submits review -> 200 OK
    resp_sup = client.post(
        "/api/reviews",
        json={"finding_id": finding_id, "decision": "CONFIRMED", "notes": "Authorized review"},
        headers=sup_headers,
    )
    assert resp_sup.status_code == 200
    assert resp_sup.json()["status"] == "success"
    assert resp_sup.json()["decision"] == "CONFIRMED"

    # 3. Analyst attempts review on same finding -> 403 Forbidden
    analyst_login = client.post("/api/auth/login", json={"username": "analyst", "password": "Analyst@SAT2026!"})
    analyst_token = analyst_login.json()["access_token"]

    resp_analyst = client.post(
        "/api/reviews",
        json={"finding_id": finding_id, "decision": "CONFIRMED", "notes": "Unauthorized attempt"},
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert resp_analyst.status_code == 403
    assert "Forbidden: Insufficient privileges" in resp_analyst.json()["detail"]


def test_auth_me_endpoint_returns_identity(client: TestClient):
    """GET /api/auth/me returns identity claims extracted from signed token."""
    login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "Admin@SAT2026!"})
    token = login_resp.json()["access_token"]

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    me = resp.json()
    assert me["username"] == "admin"
    assert me["role"] == "admin"
    assert me["full_name"] == "NCIIPC Lead Administrator"


def test_passwords_never_stored_in_plaintext():
    """Verify passwords in UserStore are hashed with salted PBKDF2-HMAC-SHA256."""
    store = get_user_store()
    for user_rec in store.list_users():
        # Password must not contain plaintext password
        assert "Admin@SAT2026!" not in user_rec.hashed_password
        assert "Supervisor@SAT2026!" not in user_rec.hashed_password
        assert "Analyst@SAT2026!" not in user_rec.hashed_password

        # Must follow pbkdf2_sha256 format
        assert user_rec.hashed_password.startswith("pbkdf2_sha256$100000$")
        parts = user_rec.hashed_password.split("$")
        assert len(parts) == 4
        salt = parts[2]
        hash_val = parts[3]
        assert len(salt) == 32  # 16-byte hex
        assert len(hash_val) == 64  # SHA-256 32-byte hex
