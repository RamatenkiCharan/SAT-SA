"""Regression tests for authentication failure isolation and bounded uploads."""
from __future__ import annotations

import io

import pytest
from sqlalchemy.exc import OperationalError

from backend.security.auth import AuthenticationBackendError, UserStore
from backend.services import ingestion


class _BrokenDurableRepository:
    """Looks durable to UserStore but fails before it can return a user."""

    def get_user_by_username(self, username: str):
        raise OperationalError("SELECT users", {}, RuntimeError("database unavailable"))


def test_durable_identity_failure_never_falls_back_to_demo_user(monkeypatch):
    """A DB outage must not authenticate the parallel in-memory seed account."""
    monkeypatch.setattr(
        "backend.repositories.in_memory_repo.get_repository",
        lambda: _BrokenDurableRepository(),
    )
    store = UserStore()
    with pytest.raises(AuthenticationBackendError):
        store.authenticate("admin", "Admin@SAT2026!")


def test_streamed_upload_rejects_over_limit_before_parsing(monkeypatch):
    """The byte limit applies to the uploaded stream, not an already-buffered body."""
    monkeypatch.setattr(ingestion, "_MAX_FILE_SIZE_BYTES", 16)
    over_limit = io.BytesIO(b"alert_id,severity\n123,CRITICAL\n")
    with pytest.raises(ingestion.IngestionValidationError, match="exceeds maximum"):
        ingestion.detect_format("alerts.csv", over_limit)


def test_streamed_upload_accepts_near_limit_payload(monkeypatch):
    monkeypatch.setattr(ingestion, "_MAX_FILE_SIZE_BYTES", 128)
    payload = io.BytesIO(b"alert_id,severity\nabc,HIGH\n")
    assert ingestion.detect_format("alerts.csv", payload) == ingestion.FileFormat.CSV
