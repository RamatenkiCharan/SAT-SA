"""
Interactive End-to-End Live Verification Script for SAT-SA Evidence Message Audit Log
"""
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_verification():
    print("--- 1. Health Check ---")
    h_res = requests.get(f"{BASE_URL}/api/health")
    assert h_res.status_code == 200, f"Health check failed: {h_res.text}"
    print("[PASS] Health check OK:", h_res.json())

    print("\n--- 2. Authenticate as Admin ---")
    auth_res = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "Admin@SAT2026!"}
    )
    assert auth_res.status_code == 200, f"Login failed: {auth_res.text}"
    admin_token = auth_res.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("[PASS] Admin authenticated successfully.")

    print("\n--- 3. Seed Benchmark Dataset ---")
    load_res = requests.post(
        f"{BASE_URL}/api/datasets/load-demo",
        json={"scenario_type": "critical_infrastructure"},
        headers=admin_headers
    )
    assert load_res.status_code == 200, f"Failed to seed demo data: {load_res.text}"
    print("[PASS] Benchmark dataset seeded.")

    print("\n--- 4. Retrieve Findings & Canonical Evidence ---")
    f_res = requests.get(f"{BASE_URL}/api/findings", headers=admin_headers)
    assert f_res.status_code == 200
    findings = f_res.json().get("findings", [])
    assert len(findings) > 0, "No findings found"
    target_f = findings[0]
    finding_id = target_f["finding_id"]
    evidence_id = target_f["evidence_references"][0]["source_record_ref"] if target_f.get("evidence_references") else "ev_sec_001"
    print(f"[PASS] Selected Finding ID: {finding_id}, Evidence ID: {evidence_id}")

    print("\n--- 5. Capture Baseline Audit Count ---")
    audit_pre = requests.get(f"{BASE_URL}/api/audit", headers=admin_headers).json()
    msg_audit_pre_count = len([e for e in audit_pre if e.get("action") == "EVIDENCE_MESSAGE_SENT"])
    print(f"Pre-send EVIDENCE_MESSAGE_SENT count: {msg_audit_pre_count}")

    print("\n--- 6. Dispatch Evidence Message via POST /api/findings/{id}/messages ---")
    msg_body = {
        "message": "Supervisory directive: Review correlated authentication anomalies in evidence window.",
        "evidence_id": evidence_id,
        "recipient_role": "analyst"
    }
    send_res = requests.post(
        f"{BASE_URL}/api/findings/{finding_id}/messages",
        json=msg_body,
        headers=admin_headers
    )
    assert send_res.status_code == 200, f"Send message failed: {send_res.text}"
    msg_data = send_res.json()
    print("[PASS] Send message response:", msg_data)
    message_id = msg_data["message_id"]

    print("\n--- 7. Fetch Finding Messages Thread ---")
    thread_res = requests.get(f"{BASE_URL}/api/findings/{finding_id}/messages", headers=admin_headers)
    assert thread_res.status_code == 200
    thread = thread_res.json()
    matching_thread_msgs = [m for m in thread if m["message_id"] == message_id]
    assert len(matching_thread_msgs) == 1, "Sent message not found in thread"
    print("[PASS] Message thread verified:", matching_thread_msgs[0])

    print("\n--- 8. Verify Immutable Audit Log Recording ---")
    audit_post = requests.get(f"{BASE_URL}/api/audit", headers=admin_headers).json()
    matching_audit = [
        e for e in audit_post
        if e.get("action") == "EVIDENCE_MESSAGE_SENT" and e.get("details", {}).get("message_id") == message_id
    ]
    assert len(matching_audit) == 1, "EVIDENCE_MESSAGE_SENT audit record not found"
    audit_entry = matching_audit[0]
    print("[PASS] Real Audit Record Verified:")
    print(f"  - Action: {audit_entry['action']}")
    print(f"  - User ID: {audit_entry['user_id']}")
    print(f"  - Username: {audit_entry['username']}")
    print(f"  - Target ID: {audit_entry['target_id']}")
    print(f"  - Timestamp: {audit_entry['occurred_at']}")
    print(f"  - Details: {audit_entry['details']}")

    print("\n--- 9. Negative Test: Empty Message ---")
    bad_res = requests.post(
        f"{BASE_URL}/api/findings/{finding_id}/messages",
        json={"message": "   ", "evidence_id": evidence_id},
        headers=admin_headers
    )
    assert bad_res.status_code == 422, f"Expected 422, got {bad_res.status_code}"
    print("[PASS] Empty message rejected with 422 Unprocessable Entity.")

    print("\n--- 10. Verify Negative Test Did NOT Generate False Audit Record ---")
    audit_after_bad = requests.get(f"{BASE_URL}/api/audit", headers=admin_headers).json()
    msg_audit_post_count = len([e for e in audit_after_bad if e.get("action") == "EVIDENCE_MESSAGE_SENT"])
    assert msg_audit_post_count == msg_audit_pre_count + 1, "False positive audit record was created!"
    print("[PASS] Zero false-positive audit entries generated.")

    print("\n========================================================")
    print("ALL LIVE END-TO-END VERIFICATION CHECKS PASSED 100%!")
    print("========================================================")

if __name__ == "__main__":
    run_verification()
