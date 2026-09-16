"""
Tests for Evidence Inspection -> Send Message Audit Trail functionality.
Ensures that sending a message during evidence inspection creates a persistent,
immutable server-side audit event (EVIDENCE_MESSAGE_SENT) with the correct actor,
evidence context, finding ID, and metadata, while negative cases (422/404) do NOT
create false positive audit records.
"""

from uuid import uuid4
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.security.auth import UserContext, create_access_token


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def admin_headers():
    user = UserContext(user_id="usr_admin_01", username="admin", role="admin", full_name="System Administrator")
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def supervisor_headers():
    user = UserContext(user_id="usr_sup_01", username="supervisor", role="supervisor", full_name="Supervisory Examiner")
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def analyst_headers():
    user = UserContext(user_id="usr_anl_01", username="analyst", role="analyst", full_name="SOC Analyst")
    token = create_access_token(user)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module", autouse=True)
def seed_test_data(client: TestClient, supervisor_headers: dict[str, str]):
    """Pre-seeds demo benchmark data so finding routes have records."""
    resp = client.post(
        "/api/datasets/load-demo",
        json={"scenario_type": "critical_infrastructure"},
        headers=supervisor_headers,
    )
    assert resp.status_code == 200, f"Failed to seed demo data: {resp.text}"


def test_send_evidence_message_success_creates_audit_event(client, supervisor_headers, admin_headers):
    """
    Test that a supervisory user sending a message on an evidence record:
    1. Returns 200 OK with message metadata.
    2. Persists the message record.
    3. Generates a server-side EVIDENCE_MESSAGE_SENT audit event with full context.
    """
    # 1. Fetch available findings
    findings_resp = client.get("/api/findings", headers=supervisor_headers)
    assert findings_resp.status_code == 200
    data = findings_resp.json()
    findings = data.get("findings", [])
    assert len(findings) > 0, "Expected at least one finding in seeded dataset"
    target_finding = findings[0]
    finding_id = target_finding["finding_id"]
    evidence_id = "ev_auth_spk_01"
    if target_finding.get("evidence_references"):
        evidence_id = target_finding["evidence_references"][0].get("source_record_ref") or "ev_auth_spk_01"

    # 2. Send evidence inquiry message
    msg_payload = {
        "message": "Please clarify anomalous authentication spike noted in canonical evidence window.",
        "evidence_id": evidence_id,
        "recipient_role": "analyst",
    }
    send_resp = client.post(f"/api/findings/{finding_id}/messages", json=msg_payload, headers=supervisor_headers)
    assert send_resp.status_code == 200
    msg_res = send_resp.json()
    assert msg_res["status"] == "success"
    assert msg_res["finding_id"] == finding_id
    assert msg_res["evidence_id"] == evidence_id
    assert msg_res["sender"] == "supervisor"
    assert msg_res["role"] == "supervisor"
    assert msg_res["message"] == msg_payload["message"]
    assert "message_id" in msg_res
    assert "sent_at" in msg_res

    # 3. Verify message can be retrieved via GET endpoint
    get_msgs_resp = client.get(f"/api/findings/{finding_id}/messages", headers=supervisor_headers)
    assert get_msgs_resp.status_code == 200
    messages = get_msgs_resp.json()
    assert any(m["message_id"] == msg_res["message_id"] for m in messages)

    # 4. Verify EVIDENCE_MESSAGE_SENT audit record in /api/audit
    audit_resp = client.get("/api/audit", headers=admin_headers)
    assert audit_resp.status_code == 200
    audit_events = audit_resp.json()
    matching_events = [
        e for e in audit_events
        if e.get("action") == "EVIDENCE_MESSAGE_SENT"
        and (
            e.get("target_id") in (evidence_id, finding_id)
            or e.get("details", {}).get("message_id") == msg_res["message_id"]
        )
    ]
    assert len(matching_events) >= 1, "Expected at least one EVIDENCE_MESSAGE_SENT audit event"
    event = matching_events[0]
    assert event["user_id"] == "usr_sup_01"
    assert event["details"]["finding_id"] == finding_id
    assert event["details"]["evidence_id"] == evidence_id
    assert event["details"]["recipient"] == "analyst"
    assert event["details"]["role"] == "supervisor"
    assert event["details"]["user_name"] == "supervisor"


def test_send_evidence_message_negative_empty_payload_no_audit(client, supervisor_headers, admin_headers):
    """
    Test that invalid / empty messages fail validation with 422
    and DO NOT produce false positive audit entries.
    """
    findings_resp = client.get("/api/findings", headers=supervisor_headers)
    assert findings_resp.status_code == 200
    target_finding = findings_resp.json()["findings"][0]
    finding_id = target_finding["finding_id"]

    # Baseline audit event count
    audit_resp_before = client.get("/api/audit", headers=admin_headers)
    assert audit_resp_before.status_code == 200
    count_before = len([e for e in audit_resp_before.json() if e.get("action") == "EVIDENCE_MESSAGE_SENT"])

    # Attempt to send empty / whitespace message
    invalid_payload = {
        "message": "   ",
        "evidence_id": "ev_01",
        "recipient_role": "analyst",
    }
    resp = client.post(f"/api/findings/{finding_id}/messages", json=invalid_payload, headers=supervisor_headers)
    assert resp.status_code in (400, 422)

    # Verify no new audit event was created
    audit_resp_after = client.get("/api/audit", headers=admin_headers)
    count_after = len([e for e in audit_resp_after.json() if e.get("action") == "EVIDENCE_MESSAGE_SENT"])
    assert count_after == count_before, "No audit event should be logged on 422 validation failure"


def test_send_evidence_message_negative_nonexistent_finding(client, supervisor_headers, admin_headers):
    """
    Test that attempting to send a message on a non-existent finding returns 404
    and does not create a false success audit entry.
    """
    audit_resp_before = client.get("/api/audit", headers=admin_headers)
    count_before = len([e for e in audit_resp_before.json() if e.get("action") == "EVIDENCE_MESSAGE_SENT"])

    missing_finding_id = str(uuid4())
    payload = {
        "message": "Querying missing finding",
        "evidence_id": "ev_nonexistent",
        "recipient_role": "analyst",
    }
    resp = client.post(f"/api/findings/{missing_finding_id}/messages", json=payload, headers=supervisor_headers)
    assert resp.status_code == 404

    audit_resp_after = client.get("/api/audit", headers=admin_headers)
    count_after = len([e for e in audit_resp_after.json() if e.get("action") == "EVIDENCE_MESSAGE_SENT"])
    assert count_after == count_before, "No audit event should be logged on 404 finding not found"


def test_send_evidence_message_actor_attribution_different_roles(client, analyst_headers, admin_headers):
    """
    Test that an Analyst sending a message correctly records their authentic user_id and role.
    """
    findings_resp = client.get("/api/findings", headers=analyst_headers)
    assert findings_resp.status_code == 200
    target_finding = findings_resp.json()["findings"][0]
    finding_id = target_finding["finding_id"]

    msg_payload = {
        "message": "Analyst escalation note regarding peer variance.",
        "evidence_id": "ev_sec_01",
        "recipient_role": "supervisor",
    }
    send_resp = client.post(f"/api/findings/{finding_id}/messages", json=msg_payload, headers=analyst_headers)
    assert send_resp.status_code == 200
    msg_res = send_resp.json()

    audit_resp = client.get("/api/audit", headers=admin_headers)
    assert audit_resp.status_code == 200
    events = [e for e in audit_resp.json() if e.get("details", {}).get("message_id") == msg_res["message_id"]]
    assert len(events) == 1
    ev = events[0]
    assert ev["user_id"] == "usr_anl_01"
    assert ev["details"]["role"] == "analyst"
    assert ev["details"]["user_name"] == "analyst"


def test_unauthenticated_evidence_message_rejected(client):
    """
    Test that unauthenticated requests to send evidence messages return 401 Unauthorized.
    """
    fake_finding_id = str(uuid4())
    payload = {
        "message": "Unauthenticated inquiry attempt",
        "evidence_id": "ev_01",
    }
    resp = client.post(f"/api/findings/{fake_finding_id}/messages", json=payload)
    assert resp.status_code == 401


def test_evidence_traceability_across_different_evidence_ids(client, supervisor_headers, admin_headers):
    """
    Test that sending messages on two distinct evidence records produces two distinct
    audit events, each referencing its respective evidence ID accurately.
    """
    findings_resp = client.get("/api/findings", headers=supervisor_headers)
    assert findings_resp.status_code == 200
    target_finding = findings_resp.json()["findings"][0]
    finding_id = target_finding["finding_id"]

    # Send on Evidence A
    msg_a = client.post(
        f"/api/findings/{finding_id}/messages",
        json={"message": "Inquiry on Evidence Alpha", "evidence_id": "ev_alpha_999"},
        headers=supervisor_headers,
    )
    assert msg_a.status_code == 200
    rec_a = msg_a.json()

    # Send on Evidence B
    msg_b = client.post(
        f"/api/findings/{finding_id}/messages",
        json={"message": "Inquiry on Evidence Beta", "evidence_id": "ev_beta_888"},
        headers=supervisor_headers,
    )
    assert msg_b.status_code == 200
    rec_b = msg_b.json()

    # Verify audit log contains both events with correct distinct evidence targets
    audit_resp = client.get("/api/audit", headers=admin_headers)
    events = audit_resp.json()
    event_a = next(e for e in events if e.get("details", {}).get("message_id") == rec_a["message_id"])
    event_b = next(e for e in events if e.get("details", {}).get("message_id") == rec_b["message_id"])

    assert event_a["details"]["evidence_id"] == "ev_alpha_999"
    assert event_b["details"]["evidence_id"] == "ev_beta_888"
    assert event_a["details"]["evidence_id"] != event_b["details"]["evidence_id"]
