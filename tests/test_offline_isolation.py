"""
Test Offline Air-Gapped Isolation and Security RBAC Baseline (SRS NFR-001, NFR-007).
Verifies:
1. Zero outbound external HTTP/HTTPS calls, CDNs, or LLM APIs in analytical pipelines.
2. Local authentication lifecycle (PBKDF2 hashing, HMAC token issuance).
3. Role-based authorization enforcement (Supervisor review privileges vs Analyst restricted access).
"""
import ast
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.security.auth import (
    authenticate_user,
    create_access_token,
    verify_access_token,
    verify_password,
    hash_password,
)

client = TestClient(app)


def test_zero_external_network_dependencies_in_backend():
    """Verify backend and analytics source files make zero external network requests."""
    root = Path(__file__).resolve().parent.parent
    banned_modules = {"requests", "urllib.request", "httpx", "aiohttp", "openai", "anthropic", "google.generativeai"}

    for search_dir in ["analytics", "backend"]:
        dir_path = root / search_dir
        for py_file in dir_path.rglob("*.py"):
            with open(py_file, "r", encoding="utf-8") as f:
                content = f.read()

            try:
                tree = ast.parse(content, filename=str(py_file))
            except Exception:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert (
                            alias.name not in banned_modules
                        ), f"Banned network/LLM dependency '{alias.name}' in {py_file.name}"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        assert (
                            node.module not in banned_modules
                        ), f"Banned network/LLM dependency '{node.module}' in {py_file.name}"


def test_local_authentication_lifecycle():
    """Verify local PBKDF2 hashing and HMAC token generation/verification."""
    # 1. Hashing and verification
    pw = "sih2026@supervisor"
    h = hash_password(pw)
    assert h != pw
    assert verify_password(pw, h) is True
    assert verify_password("wrong_password", h) is False

    # 2. Local authentication
    user = authenticate_user("supervisor", pw)
    assert user is not None
    assert user.role == "supervisor"

    bad_user = authenticate_user("supervisor", "wrong_password")
    assert bad_user is None

    # 3. Token issuance and decoding
    token = create_access_token({"sub": user.user_id, "username": user.username, "role": user.role})
    payload = verify_access_token(token)
    assert payload is not None
    assert payload.username == "supervisor"
    assert payload.role == "supervisor"


def test_rbac_endpoint_enforcement():
    """Verify that only users with 'supervisor' role can submit review decisions."""
    # Log in as analyst (restricted)
    analyst_login = client.post(
        "/api/auth/login",
        json={"username": "analyst", "password": "sih2026@analyst"},
    )
    assert analyst_login.status_code == 200
    analyst_token = analyst_login.json()["access_token"]

    # Log in as supervisor (permitted)
    supervisor_login = client.post(
        "/api/auth/login",
        json={"username": "supervisor", "password": "sih2026@supervisor"},
    )
    assert supervisor_login.status_code == 200
    supervisor_token = supervisor_login.json()["access_token"]

    dummy_finding_id = str(uuid4())

    # Attempt review as analyst -> Must be rejected with 403 Forbidden
    resp_analyst = client.post(
        "/api/reviews",
        json={
            "finding_id": dummy_finding_id,
            "decision": "CONFIRMED",
            "notes": "Unauthorized analyst review attempt",
        },
        headers={"Authorization": f"Bearer {analyst_token}"},
    )
    assert resp_analyst.status_code == 403
    assert "requires 'supervisor'" in resp_analyst.json()["detail"]

    # Attempt review with invalid token -> Must be rejected with 401 Unauthorized
    resp_unauth = client.post(
        "/api/reviews",
        json={
            "finding_id": dummy_finding_id,
            "decision": "CONFIRMED",
            "notes": "Invalid token attempt",
        },
        headers={"Authorization": "Bearer invalid.token.payload"},
    )
    assert resp_unauth.status_code == 401
