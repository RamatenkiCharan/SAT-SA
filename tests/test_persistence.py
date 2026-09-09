"""
Test SQLite Durable Persistence and State Rehydration.
Verifies that datasets, canonical entities, findings, review decisions, and audit events
persist into SQLite and are accurately rehydrated upon repository re-initialization (SRS §7.2 / §24).
"""
import tempfile
from pathlib import Path
from uuid import uuid4

from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.models.canonical import ReviewDecisionState
from backend.repositories.in_memory_repo import SATRepository


def test_sqlite_persistence_and_rehydration():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_sat_sa.db"

        # 1. Initialize repo and register dataset
        repo1 = SATRepository(db_path=str(db_path))
        version_id = uuid4()
        dataset_id = uuid4()

        raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=version_id)
        canonical_ds, reconstructed_ds, bm_engine, findings, dq_res = run_full_analytical_pipeline(
            raw_bundle=raw_bundle,
            dataset_version_id=version_id,
        )

        repo1.register_dataset_version(
            dataset_id=dataset_id,
            dataset_name="Persistence Test Dataset",
            source_file_ref="synthetic://test-persistence",
            canonical_dataset=canonical_ds,
            reconstructed_dataset=reconstructed_ds,
            benchmark_engine=bm_engine,
            findings=findings,
            dq_score=round(dq_res.score, 4),
            description="Testing state retention across restarts.",
        )

        assert len(repo1.datasets) == 1
        assert len(repo1.findings_by_id) == len(findings)

        # Record a review decision
        sample_finding = findings[0]
        repo1.record_review_decision(
            finding_id=sample_finding.finding_id,
            decision=ReviewDecisionState.CONFIRMED,
            reviewer_id="usr_supervisor_01",
            reviewer_name="Supervisory Officer Sharma",
            notes="Confirmed execution anomaly during audit.",
        )

        # 2. Simulate process restart by creating a new repository pointing to the same SQLite DB
        repo2 = SATRepository(db_path=str(db_path))

        assert len(repo2.datasets) == 1
        assert dataset_id in repo2.datasets
        assert len(repo2.dataset_versions) == 1
        assert version_id in repo2.dataset_versions

        # Verify findings rehydrated
        assert len(repo2.findings_by_id) == len(findings)
        rehydrated_finding = repo2.get_finding_by_id(sample_finding.finding_id)
        assert rehydrated_finding is not None
        assert rehydrated_finding.review_status == ReviewDecisionState.CONFIRMED
        assert rehydrated_finding.review_notes == "Confirmed execution anomaly during audit."

        # Verify evidence drill-down works on rehydrated dataset
        evidence = repo2.get_finding_evidence_records(sample_finding.finding_id)
        assert evidence is not None
        assert "alerts" in evidence
        assert "cse_name" in evidence

        # Verify audit events persisted
        assert len(repo2.audit_events) >= 2
