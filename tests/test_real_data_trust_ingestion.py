"""
Test Real Data Trust & Multi-Format Ingestion Pipeline (SRS FR-010..FR-015).
Verifies that:
1. Ingestion computes REAL dynamic Data Trust scores across all 4 decomposed components.
2. Incomplete or corrupted CSV/JSON payloads dynamically reduce specific DQ components (not hardcoded 0.88).
3. Low DQ (<0.70) reliably suppresses negative-space coverage gap findings (FR-015 / FR-041).
"""
import io
import json
from uuid import uuid4

from fastapi.testclient import TestClient

from analytics.canonicalization.canonicalization import canonicalize_records
from analytics.data_quality.quality_score import evaluate_dataset_quality
from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.main import app
from backend.models.canonical import FindingType

client = TestClient(app)


def test_real_data_trust_computation_on_clean_data():
    """Clean full dataset must compute high completeness, consistency, coverage, and sample sufficiency."""
    version_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=version_id)
    canonical_ds = canonicalize_records(raw_bundle, dataset_version_id=version_id)

    dq_result = evaluate_dataset_quality(canonical_ds)

    assert dq_result.score > 0.80
    assert dq_result.components.completeness_ratio == 1.0
    assert dq_result.components.consistency_ratio == 1.0
    assert dq_result.components.sample_sufficiency_ratio == 1.0
    # Score is mathematically verified, not a static constant
    expected_score = (
        0.35 * dq_result.components.completeness_ratio
        + 0.25 * dq_result.components.consistency_ratio
        + 0.25 * dq_result.components.coverage_ratio
        + 0.15 * dq_result.components.sample_sufficiency_ratio
    )
    assert abs(dq_result.score - expected_score) < 1e-6


def test_missing_data_degrades_dq_components_dynamically():
    """Removing or corrupting required fields must penalize completeness/consistency and lower total DQ score dynamically."""
    version_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=version_id)

    # Corrupt raw alerts by setting empty categories and orphan asset references
    corrupted_alerts = []
    for a in raw_bundle["alerts"]:
        corrupted_alerts.append(
            {
                "alert_id": a["alert_id"],
                "cse_id": a["cse_id"],
                "asset_id": str(uuid4()),  # Orphan asset reference
                "reporting_period_id": a["reporting_period_id"],
                "event_time": a["event_time"],
                "severity": "MEDIUM",
                "alert_category": "",
                "source": "",
                "status": "CLOSED",
            }
        )
    raw_bundle["alerts"] = corrupted_alerts

    canonical_ds, _, _, findings, dq_res = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=version_id,
    )

    # Completeness and consistency must drop due to missing/corrupted fields
    assert dq_res.components.completeness_ratio < 0.95 or dq_res.components.consistency_ratio < 0.95
    assert dq_res.score < 0.95
    assert dq_res.score != 0.88  # Must NOT be hardcoded


def test_csv_upload_computes_real_dq_and_generates_findings():
    """CSV upload payload must be correctly parsed and computed through Data Trust."""
    # Log in as analyst/supervisor to get bearer token
    login_resp = client.post(
        "/api/auth/login",
        json={"username": "analyst", "password": "sih2026@analyst"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]

    csv_content = """alert_id,cse_id,asset_id,reporting_period_id,event_time,severity,alert_category,source,status
a0000000-0000-0000-0000-000000000001,c0000000-0000-0000-0000-000000000001,b0000000-0000-0000-0000-000000000001,r0000000-0000-0000-0000-000000000001,2026-03-01T10:00:00Z,CRITICAL,Authentication Failure,SIEM,CLOSED
a0000000-0000-0000-0000-000000000002,c0000000-0000-0000-0000-000000000001,b0000000-0000-0000-0000-000000000001,r0000000-0000-0000-0000-000000000001,2026-03-01T10:05:00Z,HIGH,Brute Force,EDR,CLOSED
"""
    files = {"file": ("soc_alerts.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    resp = client.post(
        "/api/datasets/upload",
        files=files,
        headers={"Authorization": f"Bearer {token}"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["row_count"] == 2
    assert "data_quality_score" in data
    assert "data_quality_components" in data
    assert data["data_quality_score"] != 0.88  # Verified dynamic calculation


def test_low_dq_suppresses_negative_space_findings():
    """When Data Trust score is below gate threshold (0.70), negative-space findings must be suppressed (FR-015/FR-041)."""
    version_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=version_id)

    # Intentionally prune alerts to 2 to trigger low sample sufficiency and low coverage
    raw_bundle["alerts"] = raw_bundle["alerts"][:2]

    canonical_ds, _, _, findings, dq_res = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=version_id,
    )

    # Sample sufficiency for 2 alerts with min 30 = 2/30 = 0.0667
    assert dq_res.components.sample_sufficiency_ratio < 0.20
    assert dq_res.score < 0.70

    # Ensure no COVERAGE_GAP findings are emitted because data is insufficiently reliable
    coverage_findings = [f for f in findings if f.finding_type == FindingType.COVERAGE_GAP]
    assert len(coverage_findings) == 0
