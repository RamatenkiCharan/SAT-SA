"""
Data Trust and Genuine Data Quality Score Verification Test Suite.
Tests:
1. Dynamic derivation of Data Quality scores from uploaded data (never hardcoded).
2. Distinction between high-quality and low-quality datasets across all 4 components.
3. Regression check ensuring no production code path uses a hardcoded DQ constant (e.g. 0.88 or 0.92).
4. Full upload flow (file validation -> parsing -> schema validation -> canonicalization -> DQ calculation -> persistence -> analysis).
5. Negative-space coverage gap gating by computed DQ score.
6. Traceability of all 4 components (Completeness, Consistency, Coverage, Sample Sufficiency) and diagnostic warnings.
"""
import io
import json
import re
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from analytics.canonicalization.canonicalization import canonicalize_records
from analytics.data_quality.quality_processor import evaluate_dataset_quality
from analytics.data_quality.quality_score import (
    DataQualityComponents,
    DataQualityInputs,
    DataQualityResult,
    compute_data_quality_score,
)
from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.main import app
from backend.models.canonical import AssetCriticality, Severity
from backend.repositories.in_memory_repo import SATRepository, get_repository


def test_formula_weights_authoritative_srs_v2():
    """Formula must be DQ = 0.35*C + 0.25*K + 0.25*V + 0.15*S per SRS v2.0."""
    ver_id = uuid4()
    inputs = DataQualityInputs(
        missing_required_fields=0,
        total_required_fields=100,
        failed_validation_checks=0,
        total_validation_checks=100,
        observed_evidence_records=100,
        expected_evidence_records=100,
        actual_sample_size=30,
    )
    res = compute_data_quality_score(inputs, ver_id)
    assert res.score == pytest.approx(1.0)
    assert res.overall_score == pytest.approx(1.0)
    assert res.completeness_score == pytest.approx(1.0)
    assert res.consistency_score == pytest.approx(1.0)
    assert res.coverage_score == pytest.approx(1.0)
    assert res.sufficiency_score == pytest.approx(1.0)

    # Test single-component degradation according to exact weights
    # C degraded to 0.0 -> score loses 0.35
    inputs_c0 = DataQualityInputs(
        missing_required_fields=100,
        total_required_fields=100,
        failed_validation_checks=0,
        total_validation_checks=100,
        observed_evidence_records=100,
        expected_evidence_records=100,
        actual_sample_size=30,
    )
    res_c0 = compute_data_quality_score(inputs_c0, ver_id)
    assert res_c0.completeness_score == pytest.approx(0.0)
    assert res_c0.score == pytest.approx(0.65)  # 0.25 + 0.25 + 0.15 = 0.65

    # K degraded to 0.0 -> score loses 0.25
    inputs_k0 = DataQualityInputs(
        missing_required_fields=0,
        total_required_fields=100,
        failed_validation_checks=100,
        total_validation_checks=100,
        observed_evidence_records=100,
        expected_evidence_records=100,
        actual_sample_size=30,
    )
    res_k0 = compute_data_quality_score(inputs_k0, ver_id)
    assert res_k0.consistency_score == pytest.approx(0.0)
    assert res_k0.score == pytest.approx(0.75)  # 0.35 + 0.25 + 0.15 = 0.75

    # V degraded to 0.0 -> score loses 0.25
    inputs_v0 = DataQualityInputs(
        missing_required_fields=0,
        total_required_fields=100,
        failed_validation_checks=0,
        total_validation_checks=100,
        observed_evidence_records=0,
        expected_evidence_records=100,
        actual_sample_size=30,
    )
    res_v0 = compute_data_quality_score(inputs_v0, ver_id)
    assert res_v0.coverage_score == pytest.approx(0.0)
    assert res_v0.score == pytest.approx(0.75)  # 0.35 + 0.25 + 0.15 = 0.75

    # S degraded to 0.0 -> score loses 0.15
    inputs_s0 = DataQualityInputs(
        missing_required_fields=0,
        total_required_fields=100,
        failed_validation_checks=0,
        total_validation_checks=100,
        observed_evidence_records=100,
        expected_evidence_records=100,
        actual_sample_size=0,
    )
    res_s0 = compute_data_quality_score(inputs_s0, ver_id)
    assert res_s0.sufficiency_score == pytest.approx(0.0)
    assert res_s0.score == pytest.approx(0.85)  # 0.35 + 0.25 + 0.25 = 0.85


def test_two_datasets_with_different_quality_receive_different_dq_scores():
    """Requirement 11: Two datasets with materially different quality receive different DQ results."""
    ver_a = uuid4()
    ver_b = uuid4()

    cse_id_a = str(uuid4())
    rep_id_a = str(uuid4())
    asset_id_a = str(uuid4())

    # Dataset A: High quality dataset (complete metadata, valid links, 40 alerts)
    raw_bundle_high = {
        "cse": [
            {
                "cse_id": cse_id_a,
                "name": "High Quality Power Corp",
                "sector": "Power & Energy",
                "scale": "large",
                "reporting_period_id": rep_id_a,
            }
        ],
        "reporting_periods": [
            {
                "reporting_period_id": rep_id_a,
                "cse_id": cse_id_a,
                "period_start": "2026-01-01T00:00:00Z",
                "period_end": "2026-01-31T23:59:59Z",
            }
        ],
        "assets": [
            {
                "asset_id": asset_id_a,
                "cse_id": cse_id_a,
                "criticality": "CRITICAL",
                "asset_type": "SCADA Server",
                "environment": "Production",
            }
        ],
        "alerts": [
            {
                "alert_id": str(uuid4()),
                "cse_id": cse_id_a,
                "asset_id": asset_id_a,
                "reporting_period_id": rep_id_a,
                "event_time": f"2026-01-{(i%28)+1:02d}T10:00:00Z",
                "severity": "HIGH",
                "alert_category": "Unauthorized Access",
                "source": "Splunk",
                "status": "CLOSED",
            }
            for i in range(40)
        ],
        "coverage_observations": [
            {
                "observation_id": str(uuid4()),
                "cse_id": cse_id_a,
                "asset_id": asset_id_a,
                "expected_count": 40.0,
                "observed_count": 40.0,
                "period_id": rep_id_a,
            }
        ],
    }

    # Dataset B: Low quality / degraded dataset (missing required fields, broken asset IDs, tiny sample)
    cse_id_b = str(uuid4())
    rep_id_b = str(uuid4())
    raw_bundle_low = {
        "cse": [
            {
                "cse_id": cse_id_b,
                "name": "",  # Missing name
                "sector": "",  # Missing sector
                "scale": "small",
                "reporting_period_id": rep_id_b,
            }
        ],
        "reporting_periods": [],  # Missing reporting periods
        "assets": [],  # Missing assets
        "alerts": [
            {
                "alert_id": str(uuid4()),
                "cse_id": cse_id_b,
                "asset_id": str(uuid4()),  # Orphaned asset reference!
                "reporting_period_id": rep_id_b,
                "event_time": "",  # Missing event time
                "severity": "",  # Missing severity
                "alert_category": "",  # Missing category
                "source": "",  # Missing source
                "status": "",  # Missing status
            },
            {
                "alert_id": str(uuid4()),
                "cse_id": cse_id_b,
                "asset_id": str(uuid4()),  # Orphaned asset reference!
                "reporting_period_id": rep_id_b,
                "event_time": "2026-01-02T10:00:00Z",
                "severity": "LOW",
                "alert_category": "Test",
                "source": "Manual",
                "status": "OPEN",
            },
        ],
        "coverage_observations": [
            {
                "observation_id": str(uuid4()),
                "cse_id": cse_id_b,
                "asset_id": None,
                "expected_count": 100.0,
                "observed_count": 2.0,
                "period_id": rep_id_b,
            }
        ],
    }

    canonical_high = canonicalize_records(raw_bundle_high, ver_a)
    canonical_low = canonicalize_records(raw_bundle_low, ver_b)

    dq_high = evaluate_dataset_quality(canonical_high, ver_a)
    dq_low = evaluate_dataset_quality(canonical_low, ver_b)

    # Scores must be derived and materially different
    assert dq_high.score != dq_low.score
    assert dq_high.score > 0.90
    assert dq_low.score < 0.60
    assert dq_high.completeness_score > dq_low.completeness_score
    assert dq_high.consistency_score > dq_low.consistency_score
    assert dq_high.sufficiency_score > dq_low.sufficiency_score
    assert len(dq_low.warnings) > 0
    assert any("Missing" in w for w in dq_low.warnings)
    assert any("validation" in w.lower() for w in dq_low.warnings)
    assert any("sample size" in w.lower() for w in dq_low.warnings)


def test_regression_no_hardcoded_dq_score_in_production_code():
    """Requirement 12: Regression test proving no production code path uses a hardcoded DQ score."""
    root_dir = Path(__file__).resolve().parent.parent
    production_dirs = [root_dir / "backend", root_dir / "analytics"]

    # Patterns indicating hardcoded DQ scores in assignment context
    suspicious_patterns = [
        re.compile(r"dq_score\s*=\s*0\.88"),
        re.compile(r"dq_score\s*=\s*0\.92"),
        re.compile(r"data_quality_score\s*=\s*0\.88"),
        re.compile(r"data_quality_score\s*=\s*0\.92"),
    ]

    violations = []
    for p_dir in production_dirs:
        for py_file in p_dir.rglob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            for idx, line in enumerate(content.splitlines(), start=1):
                # Ignore comment-only lines
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("*"):
                    continue
                for pat in suspicious_patterns:
                    if pat.search(line):
                        violations.append(f"{py_file.name}:{idx} -> {line.strip()}")

    assert not violations, f"Found hardcoded DQ score assignments in production code: {violations}"


def test_upload_flow_executes_dynamic_dq_derivation():
    """Requirement 8 & 9: Full upload flow executes and returns computed DQ score and breakdown."""
    client = TestClient(app)

    # Authenticate as supervisor
    login_resp = client.post("/api/auth/login", json={"username": "supervisor", "password": "Supervisor@SAT2026!"})
    assert login_resp.status_code == 200
    auth_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    # 1. Upload high quality JSON file
    high_json = {
        "cse": [
            {
                "cse_id": str(uuid4()),
                "name": "Metro Transit",
                "sector": "Transportation",
                "scale": "medium",
                "reporting_period_id": str(uuid4()),
            }
        ],
        "alerts": [
            {
                "alert_id": str(uuid4()),
                "severity": "CRITICAL",
                "alert_category": "Signalling Failure",
                "source": "Syslog",
                "status": "CLOSED",
                "event_time": "2026-01-15T12:00:00Z",
                "asset_id": str(uuid4()),
            }
            for _ in range(35)
        ],
    }

    response_high = client.post(
        "/api/datasets/upload",
        files={"file": ("high_quality.json", json.dumps(high_json).encode("utf-8"), "application/json")},
        headers=auth_headers,
    )
    assert response_high.status_code == 200
    data_high = response_high.json()

    assert data_high["status"] == "success"
    assert "data_quality_score" in data_high
    assert "data_quality_breakdown" in data_high
    dq_score_high = data_high["data_quality_score"]
    assert dq_score_high != 0.88, "DQ score was hardcoded to 0.88!"

    # 2. Upload degraded JSON file with small sample size and missing entity metadata
    degraded_json = {
        "alerts": [
            {
                "alert_id": str(uuid4()),
                "severity": "LOW",
                "alert_category": "Unknown",
                "source": "Manual",
                "status": "OPEN",
                "event_time": "2026-01-02T10:00:00Z",
            }
            for _ in range(3)
        ]
    }

    response_low = client.post(
        "/api/datasets/upload",
        files={"file": ("degraded.json", json.dumps(degraded_json).encode("utf-8"), "application/json")},
        headers=auth_headers,
    )
    assert response_low.status_code == 200
    data_low = response_low.json()

    dq_score_low = data_low["data_quality_score"]
    assert dq_score_low != 0.88, "DQ score was hardcoded to 0.88!"
    assert dq_score_high > dq_score_low, "High quality dataset did not score higher than degraded dataset!"

    # 3. Upload CSV file
    csv_content = "alert_id,severity,alert_category,source,status,event_time,asset_id\n"
    for i in range(32):
        csv_content += f"{uuid4()},HIGH,Auth Failure,SIEM,CLOSED,2026-01-10T00:00:00Z,{uuid4()}\n"

    response_csv = client.post(
        "/api/datasets/upload",
        files={"file": ("alerts.csv", csv_content.encode("utf-8"), "text/csv")},
        headers=auth_headers,
    )
    assert response_csv.status_code == 200
    data_csv = response_csv.json()
    assert data_csv["status"] == "success"
    assert data_csv["row_count"] == 32
    assert data_csv["data_quality_score"] > 0.70

    # 4. Verify list_datasets returns genuine DQ score and breakdown
    list_resp = client.get("/api/datasets", headers=auth_headers)
    assert list_resp.status_code == 200
    all_datasets = list_resp.json()["datasets"]
    assert len(all_datasets) >= 1
    for ds in all_datasets:
        for ver in ds["versions"]:
            assert ver["data_quality_score"] is not None
            assert 0.0 <= ver["data_quality_score"] <= 1.0


def test_negative_space_coverage_gap_gated_by_actual_dq_score():
    """Requirement 10: Negative-space logic is gated by the actual computed DQ score."""
    cse_id = uuid4()
    rep_id = uuid4()
    asset_id = uuid4()
    obs_id = uuid4()

    # Scenario with silent critical asset
    raw_bundle_silent = {
        "cse": [
            {
                "cse_id": str(cse_id),
                "name": "State Water SCADA",
                "sector": "Power & Energy",
                "scale": "large",
                "reporting_period_id": str(rep_id),
            }
        ],
        "reporting_periods": [
            {
                "reporting_period_id": str(rep_id),
                "cse_id": str(cse_id),
                "period_start": "2026-01-01T00:00:00Z",
                "period_end": "2026-01-31T23:59:59Z",
            }
        ],
        "assets": [
            {
                "asset_id": str(asset_id),
                "cse_id": str(cse_id),
                "criticality": "CRITICAL",
                "asset_type": "SCADA Master",
                "environment": "Grid",
            }
        ],
        "alerts": [
            {
                "alert_id": str(uuid4()),
                "cse_id": str(cse_id),
                "asset_id": str(asset_id),
                "reporting_period_id": str(rep_id),
                "event_time": f"2026-01-{(i%28)+1:02d}T12:00:00Z",
                "severity": "HIGH",
                "alert_category": "Telemetry Check",
                "source": "Syslog",
                "status": "CLOSED",
            }
            for i in range(35)
        ],
        "coverage_observations": [
            {
                "observation_id": str(obs_id),
                "cse_id": str(cse_id),
                "asset_id": str(asset_id),
                "alert_category": "SCADA Intrusion",
                "expected_count": 50.0,
                "observed_count": 0.0,  # Silent asset
                "period_id": str(rep_id),
            }
        ],
    }

    # Run with healthy data quality -> coverage gap MUST be flagged
    pipe_healthy = run_full_analytical_pipeline(raw_bundle_silent)
    assert pipe_healthy.data_quality_result.score >= 0.70
    cov_findings_healthy = [f for f in pipe_healthy.findings if f.finding_type.value == "COVERAGE_GAP"]
    assert len(cov_findings_healthy) >= 1

    # Now create an outage / degraded dataset where DQ drops below 0.70
    raw_bundle_outage = {
        "cse": [
            {
                "cse_id": str(cse_id),
                "name": "State Water SCADA",
                "sector": "Power & Energy",
                "scale": "large",
                "reporting_period_id": str(rep_id),
            }
        ],
        "reporting_periods": [],  # Missing
        "assets": [
            {
                "asset_id": str(asset_id),
                "cse_id": str(cse_id),
                "criticality": "CRITICAL",
                "asset_type": "SCADA Master",
                "environment": "Grid",
            }
        ],
        "alerts": [
            {
                "alert_id": str(uuid4()),
                "cse_id": str(cse_id),
                "asset_id": str(uuid4()),  # Unmapped
                "reporting_period_id": str(rep_id),
                "event_time": "",
                "severity": "",
                "alert_category": "",
                "source": "",
                "status": "",
            }
        ],
        "coverage_observations": [
            {
                "observation_id": str(obs_id),
                "cse_id": str(cse_id),
                "asset_id": str(asset_id),
                "alert_category": "SCADA Intrusion",
                "expected_count": 50.0,
                "observed_count": 0.0,
                "period_id": str(rep_id),
            }
        ],
    }

    pipe_outage = run_full_analytical_pipeline(raw_bundle_outage)
    assert pipe_outage.data_quality_result.score < 0.70
    cov_findings_outage = [f for f in pipe_outage.findings if f.finding_type.value == "COVERAGE_GAP"]
    assert len(cov_findings_outage) == 0, "Coverage gap should NOT be raised when DQ is degraded (<0.70)!"
