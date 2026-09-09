"""
End-to-end integration tests for SAT-SA.
Tests ingestion -> canonicalization -> workflow reconstruction -> quality check -> peer benchmarking -> detectors -> fusion -> review decisions -> audit log.
"""
from uuid import uuid4

from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.models.canonical import ReviewDecisionState
from backend.repositories.in_memory_repo import SATRepository


def test_full_pipeline_end_to_end():
    repo = SATRepository()
    ver_id = uuid4()
    dataset_id = uuid4()

    # 1. Generate multi-sector dataset
    raw_bundle, scenarios = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=ver_id)

    # 2. Run analytical pipeline
    canonical_ds, reconstructed_ds, bm_engine, findings, dq_res = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=ver_id,
    )

    assert len(canonical_ds.cse_list) == 7
    assert len(canonical_ds.alerts) > 50
    assert len(findings) > 0

    # 3. Register dataset version in repository
    ver_meta = repo.register_dataset_version(
        dataset_id=dataset_id,
        dataset_name="E2E Integration Dataset",
        source_file_ref="synthetic://e2e-test",
        canonical_dataset=canonical_ds,
        reconstructed_dataset=reconstructed_ds,
        benchmark_engine=bm_engine,
        findings=findings,
        dq_score=dq_res.score,
    )

    assert ver_meta.dataset_version_id == ver_id
    assert repo.active_dataset_version_id == ver_id

    # 4. Query findings
    all_findings = repo.get_findings(dataset_version_id=ver_id)
    assert len(all_findings) == len(findings)

    # 5. Retrieve evidence drill-down for top finding
    top_finding = all_findings[0]
    evidence_records = repo.get_finding_evidence_records(top_finding.finding_id)
    assert "alerts" in evidence_records
    assert len(evidence_records["alerts"]) > 0

    # 6. Submit a supervisory review decision
    decision_record = repo.record_review_decision(
        finding_id=top_finding.finding_id,
        decision=ReviewDecisionState.CONFIRMED,
        reviewer_id="lead_examiner_01",
        reviewer_name="Senior NCIIPC Examiner",
        notes="Confirmed fast closure execution gap. Scheduled on-site operational review.",
    )

    assert decision_record.decision == ReviewDecisionState.CONFIRMED
    assert top_finding.review_status == ReviewDecisionState.CONFIRMED

    # 7. Verify immutable audit log
    audit_events = repo.get_audit_events()
    assert len(audit_events) >= 2
    assert any(e.action == "SUBMIT_SUPERVISORY_REVIEW_DECISION" for e in audit_events)
    assert any(e.action == "INGEST_DATASET_VERSION" for e in audit_events)
