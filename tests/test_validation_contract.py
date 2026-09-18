"""Regression checks for the active validation API/UI contract."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.api import validation
from backend.main import app
from backend.security.auth import UserContext, create_access_token


def _supervisor_headers() -> dict[str, str]:
    token = create_access_token(
        UserContext(
            user_id="validation_contract_supervisor",
            username="supervisor",
            role="supervisor",
            full_name="Validation Contract Supervisor",
        )
    )
    return {"Authorization": f"Bearer {token}"}


def test_active_validation_api_has_no_legacy_protocol_route():
    client = TestClient(app)
    response = client.get("/api/validation/protocol", headers=_supervisor_headers())
    assert response.status_code == 404


def test_validation_view_consumes_current_protocol_and_has_no_metric_fallbacks():
    source = (
        Path(__file__).resolve().parents[1]
        / "frontend"
        / "src"
        / "components"
        / "ValidationView.tsx"
    ).read_text(encoding="utf-8")

    assert "data.total_scenarios" in source
    assert "data.tuning_metrics.recall" in source
    assert "data.held_out_metrics.recall" in source
    assert "data.final_protocol" not in source
    assert "data.review_efficiency" not in source
    assert "92.31% RECALL" not in source
    assert "240 scenarios" not in source


def test_validation_view_clears_results_and_shows_a_generic_retrieval_error():
    source = (
        Path(__file__).resolve().parents[1]
        / "frontend"
        / "src"
        / "components"
        / "ValidationView.tsx"
    ).read_text(encoding="utf-8")

    assert "setData(null);" in source
    assert "Validation results are unavailable." in source
    assert "role=\"alert\"" in source


def test_validation_api_failure_does_not_expose_internal_error(monkeypatch):
    def fail_protocol():
        raise RuntimeError("internal validation implementation detail")

    monkeypatch.setattr(validation, "_run_current_validation_protocol", fail_protocol)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/validation", headers=_supervisor_headers())

    assert response.status_code == 500
    assert "internal validation implementation detail" not in response.text


def test_validation_client_rejects_malformed_protocol_responses():
    source = (
        Path(__file__).resolve().parents[1] / "frontend" / "src" / "api.ts"
    ).read_text(encoding="utf-8")

    assert "isValidationProtocolResponse" in source
    assert "Validation API returned an invalid protocol response." in source
