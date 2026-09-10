"""
Unified Ingestion Pipeline Verification Test Suite.
Tests:
1. CSV and JSON format detection and parsing.
2. Schema mapping with canonical alias resolution.
3. Strict validation: required fields, enum values, invalid date/time strings, duplicate identifiers.
4. Non-silent rejection tracking: accepted_rows, rejected_rows, rejection_reasons.
5. Equivalence: CSV and JSON representing the same data produce equivalent canonical models and DQ scores.
6. End-to-end FastAPI endpoint (/api/datasets/upload) integration for CSV and JSON.
"""
from __future__ import annotations

import csv
import json
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from analytics.data_quality.quality_score import DataQualityResult
from backend.main import app
from backend.models.canonical import AlertStatus, AssetCriticality, Severity
from backend.repositories.in_memory_repo import SATRepository
from backend.services.ingestion import (
    FileFormat,
    IngestionResult,
    IngestionValidationError,
    detect_format,
    ingest_file_stream,
    parse_raw_payload,
)


def test_detect_format_csv_and_json():
    """Format detector correctly detects .csv, .json and sniffs content."""
    csv_bytes = b"alert_id,severity,alert_category,source,status,event_time\n1,HIGH,Auth,SIEM,OPEN,2026-01-01"
    json_bytes = b'[{"alert_id": "1", "severity": "HIGH"}]'
    
    assert detect_format("test.csv", csv_bytes) == FileFormat.CSV
    assert detect_format("test.json", json_bytes) == FileFormat.JSON
    assert detect_format("unlabeled_file", csv_bytes) == FileFormat.CSV
    assert detect_format("unlabeled_file", json_bytes) == FileFormat.JSON

    with pytest.raises(IngestionValidationError, match="Unsupported file format"):
        detect_format("test.exe", b"\x00\x01\x02\x03\x04\x05")


def test_valid_csv_ingestion():
    """Ingesting a valid CSV generates CanonicalDataset, provenance, DQ score, and persistence."""
    repo = SATRepository()
    aid1 = str(uuid4())
    aid2 = str(uuid4())
    csv_text = (
        "alert_id,severity,alert_category,source,status,event_time,asset_id\n"
        f"{aid1},CRITICAL,Unauthorized Access,Firewall,OPEN,2026-01-10T08:00:00Z,{uuid4()}\n"
        f"{aid2},HIGH,Malware Outbreak,EDR,CLOSED,2026-01-10T09:30:00Z,{uuid4()}\n"
    )
    contents = csv_text.encode("utf-8")

    res = ingest_file_stream(
        contents=contents,
        filename="alerts_valid.csv",
        repo=repo,
    )

    assert isinstance(res, IngestionResult)
    assert res.provenance.file_format == "csv"
    assert len(res.provenance.sha256_hash) == 64
    assert res.validation_summary.total_input_rows == 2
    assert res.validation_summary.accepted_rows == 2
    assert res.validation_summary.rejected_rows == 0
    assert len(res.canonical_dataset.alerts) == 2
    assert res.data_quality_result.score > 0.0

    # Verify repository registration
    assert res.dataset_version_id in repo.dataset_versions
    ver_meta = repo.dataset_versions[res.dataset_version_id]
    assert ver_meta.file_format == "csv"
    assert ver_meta.accepted_rows == 2
    assert ver_meta.rejected_rows == 0


def test_valid_json_ingestion_array_and_bundle():
    """Ingesting valid JSON array of objects and multi-entity bundles."""
    repo = SATRepository()
    aid1 = str(uuid4())
    aid2 = str(uuid4())

    # 1. Array of alert objects
    json_array = [
        {
            "alert_id": aid1,
            "severity": "CRITICAL",
            "alert_category": "Brute Force",
            "source": "AuthLog",
            "status": "OPEN",
            "event_time": "2026-01-12T14:00:00Z",
        },
        {
            "alert_id": aid2,
            "severity": "MEDIUM",
            "alert_category": "Port Scan",
            "source": "NIDS",
            "status": "CLOSED",
            "event_time": "2026-01-12T15:00:00Z",
        },
    ]
    contents_arr = json.dumps(json_array).encode("utf-8")

    res_arr = ingest_file_stream(
        contents=contents_arr,
        filename="alerts_array.json",
        repo=repo,
    )
    assert res_arr.validation_summary.accepted_rows == 2
    assert res_arr.validation_summary.rejected_rows == 0
    assert len(res_arr.canonical_dataset.alerts) == 2

    # 2. Multi-entity bundle
    cse_id = str(uuid4())
    rep_id = str(uuid4())
    asset_id = str(uuid4())
    json_bundle = {
        "cse": [
            {
                "cse_id": cse_id,
                "name": "State Grid Operator",
                "sector": "Power & Energy",
                "scale": "large",
                "reporting_period_id": rep_id,
            }
        ],
        "assets": [
            {
                "asset_id": asset_id,
                "cse_id": cse_id,
                "criticality": "CRITICAL",
                "asset_type": "Control Master",
                "environment": "Production",
            }
        ],
        "alerts": [
            {
                "alert_id": str(uuid4()),
                "cse_id": cse_id,
                "asset_id": asset_id,
                "reporting_period_id": rep_id,
                "severity": "HIGH",
                "alert_category": "SCADA Telemetry Dropout",
                "source": "Telemetry",
                "status": "OPEN",
                "event_time": "2026-01-14T10:00:00Z",
            }
        ],
    }
    contents_bundle = json.dumps(json_bundle).encode("utf-8")

    res_bundle = ingest_file_stream(
        contents=contents_bundle,
        filename="full_bundle.json",
        repo=repo,
    )
    assert len(res_bundle.canonical_dataset.cse_list) == 1
    assert len(res_bundle.canonical_dataset.assets) == 1
    assert len(res_bundle.canonical_dataset.alerts) == 1
    assert res_bundle.canonical_dataset.cse_list[0].name == "State Grid Operator"


def test_malformed_csv_and_json_handling():
    """Malformed CSV (headerless) and malformed JSON syntax are rejected with IngestionValidationError."""
    # Malformed JSON
    bad_json = b"{'key': 'value' invalid syntax"
    with pytest.raises(IngestionValidationError, match="Malformed JSON"):
        ingest_file_stream(bad_json, "broken.json")

    # JSON with top-level primitive
    primitive_json = b"42"
    with pytest.raises(IngestionValidationError, match="Top-level JSON must be an object or array"):
        ingest_file_stream(primitive_json, "primitive.json")

    # Headerless CSV
    empty_csv = b""
    with pytest.raises(IngestionValidationError, match="CSV has no header row"):
        ingest_file_stream(empty_csv, "empty.csv")


def test_schema_mapping_and_unknown_columns():
    """Field aliases are mapped correctly and unknown columns are captured in warnings."""
    # CSV with aliased field names: 'id' -> alert_id, 'sev' -> severity, 'type' -> alert_category, 'state' -> status
    csv_aliased = (
        "id,sev,type,source,state,time,custom_vendor_score,debug_note\n"
        f"{uuid4()},CRITICAL,Ransomware,EDR,OPEN,2026-01-15T00:00:00Z,99.5,ReviewImmediately\n"
    )
    res = ingest_file_stream(csv_aliased.encode("utf-8"), "aliased.csv")
    assert res.validation_summary.accepted_rows == 1
    alert = res.canonical_dataset.alerts[0]
    assert alert.severity == Severity.CRITICAL
    assert alert.alert_category == "Ransomware"
    assert alert.status == AlertStatus.OPEN

    # Check unknown columns warning
    assert any("custom_vendor_score" in w for w in res.validation_summary.warnings)
    assert any("debug_note" in w for w in res.validation_summary.warnings)


def test_duplicate_identifiers_detection():
    """Duplicate alert identifiers within the same file are detected and rejected."""
    dup_id = str(uuid4())
    csv_dups = (
        "alert_id,severity,alert_category,source,status,event_time\n"
        f"{dup_id},HIGH,Auth,SIEM,OPEN,2026-01-01T00:00:00Z\n"
        f"{dup_id},LOW,Auth,SIEM,CLOSED,2026-01-01T01:00:00Z\n"
        f"{uuid4()},CRITICAL,Malware,EDR,OPEN,2026-01-01T02:00:00Z\n"
    )
    res = ingest_file_stream(csv_dups.encode("utf-8"), "duplicates.csv")
    assert res.validation_summary.total_input_rows == 3
    assert res.validation_summary.accepted_rows == 2
    assert res.validation_summary.rejected_rows == 1
    assert any(f"Duplicate alert identifier: '{dup_id}'" in r for r in res.validation_summary.rejection_reasons)


def test_invalid_dates_and_enum_types_rejection():
    """Invalid date strings and unsupported enum types are rejected with explicit reasons."""
    csv_invalid = (
        "alert_id,severity,alert_category,source,status,event_time\n"
        f"{uuid4()},SUPER_CRITICAL,Auth,SIEM,OPEN,2026-01-01T00:00:00Z\n"  # Invalid severity enum
        f"{uuid4()},HIGH,Auth,SIEM,UNKNOWN_STATUS,2026-01-01T00:00:00Z\n"    # Invalid status enum
        f"{uuid4()},HIGH,Auth,SIEM,OPEN,not-a-real-date\n"                  # Invalid date
        f"{uuid4()},MEDIUM,Malware,EDR,OPEN,2026-01-01T12:00:00Z\n"         # Valid row
    )
    res = ingest_file_stream(csv_invalid.encode("utf-8"), "invalid_types.csv")
    assert res.validation_summary.total_input_rows == 4
    assert res.validation_summary.accepted_rows == 1
    assert res.validation_summary.rejected_rows == 3

    reasons = " ".join(res.validation_summary.rejection_reasons)
    assert "Invalid severity 'SUPER_CRITICAL'" in reasons
    assert "Invalid status 'UNKNOWN_STATUS'" in reasons
    assert "Invalid date/time format" in reasons


def test_equivalent_csv_and_json_datasets_yield_identical_results():
    """Requirement: CSV and JSON representing the exact same data produce equivalent canonical records and DQ scores."""
    aid1 = str(uuid4())
    aid2 = str(uuid4())
    aid3 = str(uuid4())

    common_data = [
        {
            "alert_id": aid1,
            "severity": "CRITICAL",
            "alert_category": "Privilege Escalation",
            "source": "Active Directory",
            "status": "OPEN",
            "event_time": "2026-01-20T10:00:00Z",
        },
        {
            "alert_id": aid2,
            "severity": "HIGH",
            "alert_category": "Data Exfiltration",
            "source": "DLP Gateway",
            "status": "INVESTIGATING",
            "event_time": "2026-01-20T11:00:00Z",
        },
        {
            "alert_id": aid3,
            "severity": "MEDIUM",
            "alert_category": "Suspicious Login",
            "source": "Okta",
            "status": "CLOSED",
            "event_time": "2026-01-20T12:00:00Z",
        },
    ]

    # JSON representation
    json_bytes = json.dumps(common_data).encode("utf-8")
    res_json = ingest_file_stream(json_bytes, "shared.json")

    # CSV representation
    csv_lines = [
        "alert_id,severity,alert_category,source,status,event_time",
        *[
            f"{row['alert_id']},{row['severity']},{row['alert_category']},{row['source']},{row['status']},{row['event_time']}"
            for row in common_data
        ],
    ]
    csv_bytes = "\n".join(csv_lines).encode("utf-8")
    res_csv = ingest_file_stream(csv_bytes, "shared.csv")

    # Verify equivalent canonical datasets
    assert len(res_json.canonical_dataset.alerts) == len(res_csv.canonical_dataset.alerts) == 3
    for i in range(3):
        a_json = res_json.canonical_dataset.alerts[i]
        a_csv = res_csv.canonical_dataset.alerts[i]
        assert a_json.alert_id == a_csv.alert_id
        assert a_json.severity == a_csv.severity
        assert a_json.alert_category == a_csv.alert_category
        assert a_json.source == a_csv.source
        assert a_json.status == a_csv.status

    # Verify equivalent Data Quality score and components
    dq_j = res_json.data_quality_result
    dq_c = res_csv.data_quality_result
    assert dq_j.score == pytest.approx(dq_c.score, abs=1e-5)
    assert dq_j.completeness_score == pytest.approx(dq_c.completeness_score, abs=1e-5)
    assert dq_j.consistency_score == pytest.approx(dq_c.consistency_score, abs=1e-5)
    assert dq_j.sufficiency_score == pytest.approx(dq_c.sufficiency_score, abs=1e-5)


def test_fastapi_upload_endpoint_e2e():
    """End-to-end HTTP upload endpoint tests via TestClient."""
    client = TestClient(app)

    # Authenticate as supervisor
    login_resp = client.post("/api/auth/login", json={"username": "supervisor", "password": "Supervisor@SAT2026!"})
    assert login_resp.status_code == 200
    auth_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # 1. Successful CSV upload
    aid1 = str(uuid4())
    csv_content = (
        "alert_id,severity,alert_category,source,status,event_time\n"
        f"{aid1},CRITICAL,DDoS Attack,FlowMonitor,OPEN,2026-01-22T08:00:00Z\n"
        f"{uuid4()},HIGH,Ransomware,EDR,CLOSED,2026-01-22T09:00:00Z\n"
    )
    resp_csv = client.post(
        "/api/datasets/upload",
        files={"file": ("endpoint_test.csv", csv_content.encode("utf-8"), "text/csv")},
        headers=auth_headers,
    )
    assert resp_csv.status_code == 200
    data_csv = resp_csv.json()
    assert data_csv["status"] == "success"
    assert data_csv["provenance"]["filename"] == "endpoint_test.csv"
    assert data_csv["provenance"]["file_format"] == "csv"
    assert data_csv["validation_summary"]["accepted_rows"] == 2
    assert data_csv["validation_summary"]["rejected_rows"] == 0
    assert data_csv["row_count"] == 2
    assert "data_quality_score" in data_csv
    assert "data_quality_breakdown" in data_csv

    # 2. Upload with partial rejections (2 valid rows, 1 invalid row)
    csv_partial = (
        "alert_id,severity,alert_category,source,status,event_time\n"
        f"{uuid4()},HIGH,Auth,SIEM,OPEN,2026-01-22T10:00:00Z\n"
        f"{uuid4()},INVALID_SEV,Auth,SIEM,OPEN,2026-01-22T11:00:00Z\n"
        f"{uuid4()},LOW,Auth,SIEM,CLOSED,2026-01-22T12:00:00Z\n"
    )
    resp_partial = client.post(
        "/api/datasets/upload",
        files={"file": ("partial.csv", csv_partial.encode("utf-8"), "text/csv")},
        headers=auth_headers,
    )
    assert resp_partial.status_code == 200
    data_partial = resp_partial.json()
    assert data_partial["validation_summary"]["total_input_rows"] == 3
    assert data_partial["validation_summary"]["accepted_rows"] == 2
    assert data_partial["validation_summary"]["rejected_rows"] == 1
    assert len(data_partial["validation_summary"]["rejection_reasons"]) == 1

    # 3. Upload where all rows fail validation -> returns 400 Bad Request
    csv_all_bad = (
        "alert_id,severity,alert_category,source,status,event_time\n"
        f"{uuid4()},BAD_SEV1,Auth,SIEM,OPEN,2026-01-22T10:00:00Z\n"
        f"{uuid4()},BAD_SEV2,Auth,SIEM,OPEN,2026-01-22T11:00:00Z\n"
    )
    resp_bad = client.post(
        "/api/datasets/upload",
        files={"file": ("all_bad.csv", csv_all_bad.encode("utf-8"), "text/csv")},
        headers=auth_headers,
    )
    assert resp_bad.status_code == 400
    assert "Validation error" in resp_bad.json()["detail"]

