"""
Unit tests for Report Export APIs.
"""
from uuid import uuid4

from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.api.export import export_supervisory_html_report, export_supervisory_report
from backend.repositories.in_memory_repo import get_repository


def test_export_supervisory_report_json_and_html():
    repo = get_repository()
    dataset_id = uuid4()
    version_id = uuid4()

    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=version_id)
    canonical_ds, reconstructed_ds, bm_engine, findings, dq_res, _run_id = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=version_id,
    )

    repo.register_dataset_version(
        dataset_id=dataset_id,
        dataset_name="Test Export Dataset",
        source_file_ref="synthetic://test",
        canonical_dataset=canonical_ds,
        reconstructed_dataset=reconstructed_ds,
        benchmark_engine=bm_engine,
        findings=findings,
        dq_score=dq_res.score,
        description="Test export dataset description",
    )

    # 1. Test JSON Export
    json_report = export_supervisory_report(dataset_version_id=version_id, repo=repo)
    assert json_report["report_title"] == "SAT-SA Supervisory SOC Operational Assessment Report"
    assert json_report["total_critical_sector_entities"] > 0
    assert len(json_report["findings"]) > 0

    # 2. Test HTML Export
    html_resp = export_supervisory_html_report(dataset_version_id=version_id, repo=repo)
    assert html_resp.status_code == 200
    assert b"NCIIPC OPERATIONAL AUDIT DOSSIER" in html_resp.body
    assert b"SAT-SA SOC Supervisory Analytics Assessment Report" in html_resp.body
