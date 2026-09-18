"""Regression tests for explicit bootstrap/startup and secret configuration."""
from __future__ import annotations

import hashlib
import hmac

import pytest
from fastapi import HTTPException
from sqlalchemy import text

import backend.security.auth as auth
from backend.main import demo_dataset_seeding_enabled
from backend.repositories.postgres_repo import PostgresRepository, _get_database_url
from backend.services.ruleset_service import RulesetService


def test_postgres_url_requires_an_explicit_secret(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)

    with pytest.raises(RuntimeError, match="POSTGRES_PASSWORD"):
        _get_database_url()


def test_bootstrap_users_are_opt_in_and_complete(monkeypatch):
    monkeypatch.delenv("SAT_SEED_DEMO_USERS", raising=False)
    assert auth.configured_bootstrap_users() == []

    monkeypatch.setenv("SAT_SEED_DEMO_USERS", "true")
    monkeypatch.delenv("SAT_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="SAT_BOOTSTRAP_ADMIN_PASSWORD"):
        auth.configured_bootstrap_users()


def test_durable_repository_does_not_create_demo_users_without_opt_in(tmp_path, monkeypatch):
    monkeypatch.delenv("SAT_SEED_DEMO_USERS", raising=False)
    db_url = f"sqlite:///{(tmp_path / 'no_demo_users.db').as_posix()}"
    repo = PostgresRepository(db_url=db_url)
    try:
        with repo.engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar() == 0
            assert conn.execute(text("SELECT COUNT(*) FROM roles")).scalar() == 3
            assert conn.execute(text("SELECT COUNT(*) FROM rulesets")).scalar() == 1
    finally:
        repo.engine.dispose()


def test_demo_dataset_seeding_requires_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("SAT_SEED_DEMO_DATA", raising=False)
    assert demo_dataset_seeding_enabled() is False
    monkeypatch.setenv("SAT_SEED_DEMO_DATA", "true")
    assert demo_dataset_seeding_enabled() is True


def test_malformed_signed_payload_does_not_echo_parser_details():
    header = auth._b64_encode(b'{"alg":"HS256","typ":"JWT"}')
    payload = auth._b64_encode(b"not-json")
    message = f"{header}.{payload}".encode("utf-8")
    signature = auth._b64_encode(
        hmac.new(auth._SECRET_KEY.encode("utf-8"), message, hashlib.sha256).digest()
    )

    with pytest.raises(HTTPException) as exc_info:
        auth.decode_access_token(f"{header}.{payload}.{signature}")
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Malformed authentication token payload."


def test_ruleset_store_failure_does_not_silently_use_the_baseline():
    class BrokenRepository:
        def get_active_ruleset(self):
            raise OSError("storage unavailable")

    with pytest.raises(RuntimeError, match="ruleset store"):
        RulesetService.get_active_ruleset(repo=BrokenRepository())


def test_invalid_stored_ruleset_is_not_silently_accepted(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'invalid_ruleset.db').as_posix()}"
    repo = PostgresRepository(db_url=db_url)
    try:
        with repo.engine.begin() as conn:
            conn.execute(text("UPDATE rulesets SET weights_json = '{not-json'"))
        with pytest.raises(ValueError, match="Stored active ruleset is invalid"):
            repo.get_active_ruleset()
    finally:
        repo.engine.dispose()
