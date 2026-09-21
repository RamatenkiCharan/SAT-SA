"""
Regression tests for I-04 (migration-based schema authority) and I-06 (durable active version persistence).

Verifies:
  - The migration runner applies SQL files from database/migrations/ in order.
  - Tables are created correctly from migration files (no inline DDL drift).
  - Active dataset version selection persists across simulated restart.
  - Version selection is recorded in the audit log.
  - Memory mode remains process-local (no durable setting).
"""
from __future__ import annotations

from pathlib import Path
import json
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import text

from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.repositories.in_memory_repo import InMemoryRepository, set_repository
from backend.repositories.postgres_repo import PostgresRepository
from database.migrate import run_migrations


@pytest.fixture
def fresh_sqlite_url(tmp_path: Path):
    db_file = tmp_path / "test_migration.db"
    url = f"sqlite:///{db_file.as_posix()}"
    yield url
    set_repository(InMemoryRepository())


@pytest.fixture
def fresh_engine(fresh_sqlite_url: str):
    engine = sa.create_engine(fresh_sqlite_url, connect_args={"check_same_thread": False})
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON;"))
        conn.commit()
    yield engine
    engine.dispose()


# ---------------------------------------------------------------------------
# I-04: Migration runner tests
# ---------------------------------------------------------------------------

class TestMigrationRunner:
    def test_migrations_apply_cleanly_to_fresh_database(self, fresh_engine: sa.engine.Engine):
        """Migrations apply without error to a blank SQLite database."""
        applied = run_migrations(fresh_engine)
        assert len(applied) >= 2  # 001 + 002 at minimum
        assert "001_initial_schema.sql" in applied
        assert "002_app_settings_evidence_messages.sql" in applied

    def test_migrations_are_idempotent(self, fresh_engine: sa.engine.Engine):
        """Running migrations twice applies them only once (tracked in _schema_migrations)."""
        first_run = run_migrations(fresh_engine)
        second_run = run_migrations(fresh_engine)
        assert len(first_run) >= 2
        assert len(second_run) == 0

    def test_migration_creates_all_required_tables(self, fresh_engine: sa.engine.Engine):
        """All tables required by the repository exist after migration."""
        run_migrations(fresh_engine)
        required_tables = [
            "roles", "users", "datasets", "dataset_versions", "cse",
            "reporting_periods", "assets", "alerts", "investigations",
            "cases", "escalations", "actions", "closures",
            "coverage_observations", "rulesets", "analysis_runs",
            "findings", "finding_evidence", "finding_signals",
            "review_decisions", "audit_events", "evidence_messages",
            "app_settings",
        ]
        with fresh_engine.connect() as conn:
            for table_name in required_tables:
                result = conn.execute(
                    text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                ).first()
                assert result is not None, f"Table '{table_name}' was not created by migrations."

    def test_migration_tracking_table_records_filenames(self, fresh_engine: sa.engine.Engine):
        """Applied migration filenames are recorded in _schema_migrations."""
        run_migrations(fresh_engine)
        with fresh_engine.connect() as conn:
            rows = conn.execute(text("SELECT filename FROM _schema_migrations ORDER BY filename")).fetchall()
        filenames = [r[0] for r in rows]
        assert "001_initial_schema.sql" in filenames
        assert "002_app_settings_evidence_messages.sql" in filenames

    def test_postgres_repository_uses_migration_runner(self, fresh_sqlite_url: str):
        """PostgresRepository initialization uses migration runner (no separate inline DDL)."""
        repo = PostgresRepository(db_url=fresh_sqlite_url)
        # If migration runner was used, _schema_migrations table exists
        with repo.engine.connect() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM _schema_migrations")).scalar()
        assert count >= 2
        repo.engine.dispose()


# ---------------------------------------------------------------------------
# I-06: Durable active dataset version selection
# ---------------------------------------------------------------------------

def _create_seeded_repo(db_url: str, seed: int = 42) -> tuple:
    """Creates a PostgresRepository, seeds a dataset, and returns (repo, ds_id, ver_id)."""
    repo = PostgresRepository(db_url=db_url)
    ds_id = uuid4()
    ver_id = uuid4()
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=seed, dataset_version_id=ver_id)
    pipeline_res = run_full_analytical_pipeline(raw_bundle=raw_bundle, dataset_version_id=ver_id)
    repo.register_dataset_version(
        dataset_id=ds_id,
        dataset_name=f"Test Dataset (seed={seed})",
        source_file_ref=f"synthetic://test-seed-{seed}",
        canonical_dataset=pipeline_res.canonical_dataset,
        reconstructed_dataset=pipeline_res.reconstructed_dataset,
        benchmark_engine=pipeline_res.benchmark_engine,
        findings=pipeline_res.findings,
        dq_result=pipeline_res.data_quality_result,
        description=f"Test dataset for seed {seed}",
    )
    return repo, ds_id, ver_id


class TestDurableActiveVersion:
    def test_active_version_persists_across_restart(self, fresh_sqlite_url: str):
        """
        Select version A → restart → A remains active.
        Select version B → restart → B remains active.
        """
        # Create repo with two versions
        repo1, ds_id_a, ver_id_a = _create_seeded_repo(fresh_sqlite_url, seed=42)

        # Register a second version
        ver_id_b = uuid4()
        raw_bundle_b, _ = generate_synthetic_soc_benchmark(seed=99, dataset_version_id=ver_id_b)
        pipeline_b = run_full_analytical_pipeline(raw_bundle=raw_bundle_b, dataset_version_id=ver_id_b)
        repo1.register_dataset_version(
            dataset_id=ds_id_a,
            dataset_name="Test Dataset (seed=42)",
            source_file_ref="synthetic://test-seed-99",
            canonical_dataset=pipeline_b.canonical_dataset,
            reconstructed_dataset=pipeline_b.reconstructed_dataset,
            benchmark_engine=pipeline_b.benchmark_engine,
            findings=pipeline_b.findings,
            dq_result=pipeline_b.data_quality_result,
            description="Second version",
        )

        # Active is now ver_id_b (latest registered)
        assert repo1.active_dataset_version_id == ver_id_b

        # Switch to version A
        repo1.set_active_dataset_version(ver_id_a, "usr_sup_01", "supervisor")
        assert repo1.active_dataset_version_id == ver_id_a

        # Simulate restart
        repo1.engine.dispose()
        del repo1

        repo2 = PostgresRepository(db_url=fresh_sqlite_url)
        assert repo2.active_dataset_version_id == ver_id_a, \
            "Active version A did not persist after restart"

        # Switch to B and restart again
        repo2.set_active_dataset_version(ver_id_b, "usr_sup_01", "supervisor")
        repo2.engine.dispose()
        del repo2

        repo3 = PostgresRepository(db_url=fresh_sqlite_url)
        assert repo3.active_dataset_version_id == ver_id_b, \
            "Active version B did not persist after restart"

        # Verify audit log contains both SET_ACTIVE events
        audit_events = repo3.get_audit_events(limit=100)
        switch_events = [e for e in audit_events if e.action == "SET_ACTIVE_DATASET_VERSION"]
        assert len(switch_events) >= 2
        repo3.engine.dispose()

    def test_active_version_persists_on_register(self, fresh_sqlite_url: str):
        """When register_dataset_version sets active version, it is also persisted."""
        repo1, _, ver_id = _create_seeded_repo(fresh_sqlite_url, seed=42)
        assert repo1.active_dataset_version_id == ver_id

        # Verify it's in app_settings
        stored = repo1._load_setting("active_dataset_version_id")
        assert stored == str(ver_id)

        # Restart and confirm
        repo1.engine.dispose()
        del repo1
        repo2 = PostgresRepository(db_url=fresh_sqlite_url)
        assert repo2.active_dataset_version_id == ver_id
        repo2.engine.dispose()

def test_memory_mode_active_version_is_not_durable():
    """InMemoryRepository active version is process-local and expected to reset."""
    repo = InMemoryRepository()
    assert repo.active_dataset_version_id is None
    # Memory repo doesn't have _persist_setting or app_settings
    assert not hasattr(repo, '_persist_setting')


def test_legacy_bundled_v1_weights_are_reconciled_on_durable_restart(fresh_sqlite_url: str):
    """The known pre-SRS bundled V1 values are corrected without touching other rulesets."""
    repo = PostgresRepository(db_url=fresh_sqlite_url)
    legacy = repo.get_active_ruleset().to_dict()
    legacy["dq_weights"].update({
        "completeness_weight": 0.30,
        "consistency_weight": 0.25,
        "coverage_weight": 0.25,
        "sample_sufficiency_weight": 0.20,
    })
    with repo.engine.begin() as conn:
        conn.execute(
            text("UPDATE rulesets SET weights_json = :weights WHERE ruleset_id = :ruleset_id"),
            {"weights": json.dumps(legacy), "ruleset_id": str(repo.get_active_ruleset().ruleset_id)},
        )
    repo.engine.dispose()

    restarted = PostgresRepository(db_url=fresh_sqlite_url)
    assert restarted.get_active_ruleset().dq_weights.completeness_weight == 0.35
    assert restarted.get_active_ruleset().dq_weights.sample_sufficiency_weight == 0.15
    restarted.engine.dispose()
