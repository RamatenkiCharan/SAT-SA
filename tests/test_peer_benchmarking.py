"""
Comprehensive Unit and Integration Tests for SAT-SA v2.0 Peer-Group & Benchmarking Engine (FR-060-064).

Test Matrix:
  1. Peer size >= 5 (Direct cohort match, high confidence >= 0.85, verified median and deviation)
  2. Peer size < 5 (Multi-tier fallback: RELAXED_COHORT, GLOBAL_FALLBACK, INSUFFICIENT_PEER_DATA)
  3. Exact median case (Entity value == peer median -> deviation == 0.0, z_score == 0.0)
  4. Extreme deviation case (Massive outlier -> robust z-score computed accurately without overflow)
  5. Missing peer data (Empty cohort -> INSUFFICIENT_PEER_DATA, suppression of false positive findings)
  6. 4-Dimension peer cohorting verification: asset_class, criticality, environment, operational_profile
  7. Versioned peer membership persistence with analysis_run_id and dataset_version_id
"""
from datetime import datetime, timezone
from uuid import UUID, uuid4

import numpy as np
import pytest

from analytics.canonicalization.canonicalization import CanonicalDataset
from analytics.execution_gap.fast_closure import FastClosureDetector
from analytics.peer_benchmark.benchmarks import (
    AssetCohortBenchmarkResult,
    CSEOperationalMetrics,
    MetricDistribution,
    PeerBenchmarkEngine,
    PeerBenchmarkResult,
    PeerComparison,
    compute_median_and_mad,
)
from analytics.workflow.workflow_reconstruction import ReconstructedDataset, ReconstructedWorkflow
from backend.models.canonical import (
    CSE,
    Alert,
    AlertStatus,
    Asset,
    AssetCriticality,
    Case,
    Closure,
    Investigation,
    PeerFallbackState,
    PeerGroup,
    Severity,
)
from backend.repositories.in_memory_repo import InMemoryRepository


# ---------------------------------------------------------------------------
# Helpers for deterministic synthetic test fixtures
# ---------------------------------------------------------------------------

def _make_mock_workflow(
    cse_id: UUID,
    dataset_version_id: UUID,
    asset_class: str = "SERVER",
    criticality: AssetCriticality = AssetCriticality.CRITICAL,
    environment: str = "PRODUCTION",
    operational_profile: str = "24X7_MISSION_CRITICAL",
    severity: Severity = Severity.CRITICAL,
    closure_duration_seconds: float = 3600.0,
    evidence_count: int = 5,
) -> ReconstructedWorkflow:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    asset_id = uuid4()
    alert_id = uuid4()
    case_id = uuid4()
    closure_id = uuid4()
    inv_id = uuid4()

    asset = Asset(
        asset_id=asset_id,
        cse_id=cse_id,
        criticality=criticality,
        asset_type=asset_class,
        environment=environment,
        expected_monitoring_context=operational_profile,
        dataset_version_id=dataset_version_id,
        ingest_time=now,
    )

    alert = Alert(
        alert_id=alert_id,
        cse_id=cse_id,
        asset_id=asset_id,
        reporting_period_id=uuid4(),
        event_time=now,
        severity=severity,
        alert_category="malware",
        source="EDR",
        status=AlertStatus.CLOSED,
        dataset_version_id=dataset_version_id,
        ingest_time=now,
    )

    case = Case(
        case_id=case_id,
        alert_id=alert_id,
        opened_at=now,
        closed_at=datetime.fromtimestamp(now.timestamp() + closure_duration_seconds, tz=timezone.utc),
        severity=severity,
        outcome="RESOLVED",
        dataset_version_id=dataset_version_id,
        ingest_time=now,
    )

    closure = Closure(
        closure_id=closure_id,
        case_id=case_id,
        closed_at=datetime.fromtimestamp(now.timestamp() + closure_duration_seconds, tz=timezone.utc),
        reason="RESOLVED",
        reviewer="Analyst_1",
        dataset_version_id=dataset_version_id,
        ingest_time=now,
    )

    inv = Investigation(
        investigation_id=inv_id,
        alert_id=alert_id,
        started_at=now,
        ended_at=datetime.fromtimestamp(now.timestamp() + 300, tz=timezone.utc),
        analyst_id="Analyst_1",
        evidence_count=evidence_count,
        disposition="BENIGN",
        dataset_version_id=dataset_version_id,
        ingest_time=now,
    )

    rw = ReconstructedWorkflow(
        alert=alert,
        asset=asset,
        cse=None,
        investigation=inv,
        case=case,
        escalations=[],
        actions=[],
        closure=closure,
    )
    return rw


def _build_test_reconstructed_dataset(
    workflows: list[ReconstructedWorkflow],
    cses: list[CSE],
    version_id: UUID,
) -> ReconstructedDataset:
    alerts = [w.alert for w in workflows]
    assets = [w.asset for w in workflows if w.asset is not None]
    cases = [w.case for w in workflows if w.case is not None]
    closures = [w.closure for w in workflows if w.closure is not None]
    investigations = [w.investigation for w in workflows if w.investigation is not None]

    canonical = CanonicalDataset(
        dataset_version_id=version_id,
        cse_list=cses,
        reporting_periods=[],
        assets=assets,
        alerts=alerts,
        investigations=investigations,
        cases=cases,
        escalations=[],
        actions=[],
        closures=closures,
        coverage_observations=[],
    )

    return ReconstructedDataset(canonical)


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

class TestPeerBenchmarkingV2:

    def test_compute_median_and_mad_basic(self):
        """Tests basic robust median and MAD calculations with sample gating."""
        # 5 items: [100, 200, 300, 400, 500] -> median=300, deviations=[200, 100, 0, 100, 200] -> MAD=100
        dist = compute_median_and_mad([100.0, 200.0, 300.0, 400.0, 500.0], min_size=5)
        assert dist.count == 5
        assert dist.median == 300.0
        assert dist.mad == 100.0
        assert not dist.low_confidence

        # Small sample < 5 items -> marked low_confidence
        dist_small = compute_median_and_mad([10.0, 20.0, 30.0], min_size=5)
        assert dist_small.count == 3
        assert dist_small.median == 20.0
        assert dist_small.low_confidence is True

        # Empty values
        dist_empty = compute_median_and_mad([], min_size=5)
        assert dist_empty.count == 0
        assert dist_empty.median == 0.0
        assert dist_empty.low_confidence is True

    def test_peer_size_ge_5_direct_cohort(self):
        """
        Requirement 2 & 4:
        When peer size >= 5 on all 4 dimensions, compare_metric must return:
        - fallback_state == DIRECT
        - confidence >= 0.85
        - exact peer median, deviation, and robust z-score
        """
        version_id = uuid4()
        cse_id = uuid4()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cse = CSE(
            cse_id=cse_id,
            name="Bank_Alpha",
            sector="Financial",
            scale="Large",
            reporting_period_id=uuid4(),
            dataset_version_id=version_id,
            ingest_time=now,
        )

        # Create 6 workflows with exact 4-dimension tuple (SERVER, CRITICAL, PRODUCTION, 24X7_MISSION_CRITICAL)
        # Durations: [2000, 3000, 4000, 5000, 6000, 7000] -> Median = 4500.0
        durations = [2000.0, 3000.0, 4000.0, 5000.0, 6000.0, 7000.0]
        wfs = [
            _make_mock_workflow(
                cse_id=cse_id,
                dataset_version_id=version_id,
                asset_class="SERVER",
                criticality=AssetCriticality.CRITICAL,
                environment="PRODUCTION",
                operational_profile="24X7_MISSION_CRITICAL",
                closure_duration_seconds=dur,
            )
            for dur in durations
        ]

        dataset = _build_test_reconstructed_dataset(wfs, [cse], version_id)
        engine = PeerBenchmarkEngine(dataset, min_peer_group_size=5)

        # Compare an entity value of 3000.0
        comparison = engine.compare_metric(
            entity_value=3000.0,
            asset_class="SERVER",
            criticality="CRITICAL",
            environment="PRODUCTION",
            operational_profile="24X7_MISSION_CRITICAL",
            metric_name="closure_duration",
        )

        assert comparison.fallback_state == PeerFallbackState.DIRECT
        assert comparison.peer_size == 6
        assert comparison.confidence >= 0.85
        assert comparison.peer_median == 4500.0
        assert comparison.deviation == -1500.0  # 3000 - 4500
        assert comparison.z_score < 0  # negative robust z-score
        assert not comparison.is_suppressed
        assert "SERVER:CRITICAL:PRODUCTION:24X7_MISSION_CRITICAL" in comparison.peer_group

    def test_peer_size_lt_5_fallback_hierarchy(self):
        """
        Requirement 3:
        When direct 4D cohort has N < 5:
        1. Falls back to RELAXED_COHORT (asset_class + criticality) if relaxed N >= 5
        2. Falls back to GLOBAL_FALLBACK if relaxed N < 5 but global N >= 5
        3. Falls back to INSUFFICIENT_PEER_DATA if global N < 5
        """
        version_id = uuid4()
        cse_id = uuid4()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cse = CSE(
            cse_id=cse_id,
            name="Alpha_Energy",
            sector="Energy",
            scale="Medium",
            reporting_period_id=uuid4(),
            dataset_version_id=version_id,
            ingest_time=now,
        )

        # 2 workflows in STAGING, 4 workflows in PRODUCTION for (DATABASE, HIGH)
        # Total (DATABASE, HIGH) = 6 workflows (N >= 5)
        wfs_staging = [
            _make_mock_workflow(
                cse_id=cse_id,
                dataset_version_id=version_id,
                asset_class="DATABASE",
                criticality=AssetCriticality.HIGH,
                environment="STAGING",
                operational_profile="DEV_TEST",
                closure_duration_seconds=1200.0,
            )
            for _ in range(2)
        ]
        wfs_prod = [
            _make_mock_workflow(
                cse_id=cse_id,
                dataset_version_id=version_id,
                asset_class="DATABASE",
                criticality=AssetCriticality.HIGH,
                environment="PRODUCTION",
                operational_profile="24X7_MISSION_CRITICAL",
                closure_duration_seconds=3600.0,
            )
            for _ in range(4)
        ]

        dataset = _build_test_reconstructed_dataset(wfs_staging + wfs_prod, [cse], version_id)
        engine = PeerBenchmarkEngine(dataset, min_peer_group_size=5)

        # Querying STAGING: direct size is 2 (< 5), relaxed (DATABASE:HIGH) size is 6 (>= 5)
        comp_relaxed = engine.compare_metric(
            entity_value=1500.0,
            asset_class="DATABASE",
            criticality="HIGH",
            environment="STAGING",
            operational_profile="DEV_TEST",
            metric_name="closure_duration",
        )

        assert comp_relaxed.fallback_state == PeerFallbackState.RELAXED_COHORT
        assert comp_relaxed.peer_size == 6
        assert 0.65 <= comp_relaxed.confidence <= 0.75
        assert comp_relaxed.peer_group == "DATABASE:HIGH"
        assert not comp_relaxed.is_suppressed

        # Querying rare asset class (FIREWALL) where only 1 item exists:
        # Relaxed size = 1 (< 5), Global size = 7 (>= 5) -> GLOBAL_FALLBACK
        wf_firewall = _make_mock_workflow(
            cse_id=cse_id,
            dataset_version_id=version_id,
            asset_class="FIREWALL",
            criticality=AssetCriticality.MEDIUM,
            environment="PRODUCTION",
            operational_profile="STANDARD",
            closure_duration_seconds=500.0,
        )
        dataset_global = _build_test_reconstructed_dataset(wfs_staging + wfs_prod + [wf_firewall], [cse], version_id)
        engine_global = PeerBenchmarkEngine(dataset_global, min_peer_group_size=5)

        comp_global = engine_global.compare_metric(
            entity_value=500.0,
            asset_class="FIREWALL",
            criticality="MEDIUM",
            environment="PRODUCTION",
            operational_profile="STANDARD",
            metric_name="closure_duration",
        )

        assert comp_global.fallback_state == PeerFallbackState.GLOBAL_FALLBACK
        assert comp_global.peer_size == 7
        assert 0.40 <= comp_global.confidence <= 0.50
        assert not comp_global.is_suppressed

    def test_exact_median_case(self):
        """
        Requirement 7:
        When entity value is exactly equal to the peer cohort median:
        - deviation must be 0.0
        - robust z_score must be 0.0
        """
        version_id = uuid4()
        cse_id = uuid4()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cse = CSE(
            cse_id=cse_id,
            name="Telecom_Beta",
            sector="Telecom",
            scale="Large",
            reporting_period_id=uuid4(),
            dataset_version_id=version_id,
            ingest_time=now,
        )

        # 5 workflows with durations [1000, 2000, 3000, 4000, 5000] -> Median = 3000.0
        durations = [1000.0, 2000.0, 3000.0, 4000.0, 5000.0]
        wfs = [
            _make_mock_workflow(
                cse_id=cse_id,
                dataset_version_id=version_id,
                asset_class="WORKSTATION",
                criticality=AssetCriticality.LOW,
                environment="CORP",
                operational_profile="STANDARD_OFFICE",
                closure_duration_seconds=dur,
            )
            for dur in durations
        ]

        dataset = _build_test_reconstructed_dataset(wfs, [cse], version_id)
        engine = PeerBenchmarkEngine(dataset, min_peer_group_size=5)

        comparison = engine.compare_metric(
            entity_value=3000.0,
            asset_class="WORKSTATION",
            criticality="LOW",
            environment="CORP",
            operational_profile="STANDARD_OFFICE",
            metric_name="closure_duration",
        )

        assert comparison.peer_median == 3000.0
        assert comparison.deviation == 0.0
        assert comparison.z_score == 0.0

    def test_extreme_deviation_case(self):
        """
        Requirement 7:
        Tests extreme outlier entity values:
        - Extreme high value (e.g. 1,000,000s) -> high positive z-score without overflow or NaN
        - Extreme low value (e.g. 1.0s) -> high negative z-score
        """
        version_id = uuid4()
        cse_id = uuid4()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cse = CSE(
            cse_id=cse_id,
            name="Gov_Gamma",
            sector="Government",
            scale="Large",
            reporting_period_id=uuid4(),
            dataset_version_id=version_id,
            ingest_time=now,
        )

        # 5 workflows with median 3600, MAD 600
        durations = [3000.0, 3300.0, 3600.0, 3900.0, 4200.0]
        wfs = [
            _make_mock_workflow(
                cse_id=cse_id,
                dataset_version_id=version_id,
                closure_duration_seconds=dur,
            )
            for dur in durations
        ]

        dataset = _build_test_reconstructed_dataset(wfs, [cse], version_id)
        engine = PeerBenchmarkEngine(dataset, min_peer_group_size=5)

        # Extreme positive deviation (1,000,000 seconds)
        comp_high = engine.compare_metric(
            entity_value=1000000.0,
            asset_class="SERVER",
            criticality="CRITICAL",
            environment="PRODUCTION",
            operational_profile="24X7_MISSION_CRITICAL",
            metric_name="closure_duration",
        )

        assert not np.isnan(comp_high.z_score)
        assert not np.isinf(comp_high.z_score)
        assert comp_high.z_score > 1000.0
        assert comp_high.deviation == 1000000.0 - 3600.0

        # Extreme negative deviation (0.01 seconds)
        comp_low = engine.compare_metric(
            entity_value=0.01,
            asset_class="SERVER",
            criticality="CRITICAL",
            environment="PRODUCTION",
            operational_profile="24X7_MISSION_CRITICAL",
            metric_name="closure_duration",
        )

        assert not np.isnan(comp_low.z_score)
        assert comp_low.z_score < -5.0
        assert comp_low.deviation < -3500.0

    def test_missing_peer_data_and_false_finding_suppression(self):
        """
        Requirements 3 & 5:
        When peer data is missing or total sample size < 5:
        - comparison returns INSUFFICIENT_PEER_DATA
        - confidence <= 0.10
        - is_suppressed == True
        - FastClosureDetector strictly suppresses false positive findings
        """
        version_id = uuid4()
        cse_id = uuid4()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cse = CSE(
            cse_id=cse_id,
            name="Sparse_CSE",
            sector="Financial",
            scale="Small",
            reporting_period_id=uuid4(),
            dataset_version_id=version_id,
            ingest_time=now,
        )

        # Only 2 workflows total in entire dataset
        wfs = [
            _make_mock_workflow(
                cse_id=cse_id,
                dataset_version_id=version_id,
                closure_duration_seconds=10.0,  # Rapid closure
                evidence_count=1,               # Substandard evidence
            ),
            _make_mock_workflow(
                cse_id=cse_id,
                dataset_version_id=version_id,
                closure_duration_seconds=20.0,
                evidence_count=1,
            ),
        ]

        dataset = _build_test_reconstructed_dataset(wfs, [cse], version_id)
        engine = PeerBenchmarkEngine(dataset, min_peer_group_size=5)

        comp = engine.compare_metric(
            entity_value=10.0,
            asset_class="SERVER",
            criticality="CRITICAL",
            environment="PRODUCTION",
            operational_profile="24X7_MISSION_CRITICAL",
            metric_name="closure_duration",
        )

        assert comp.fallback_state == PeerFallbackState.INSUFFICIENT_PEER_DATA
        assert comp.confidence <= 0.10
        assert comp.is_suppressed is True

        # Run FastClosureDetector on this sparse dataset
        detector = FastClosureDetector(min_peer_group_size=5)
        signals = detector.detect(dataset, engine)

        # CRITICAL ASSERTION: Zero false positive fast closure signals generated from insufficient peer sample!
        assert len(signals) == 0

    def test_four_peer_grouping_dimensions_verified(self):
        """
        Requirement 1:
        Verifies all 4 peer grouping dimensions:
        - asset_class
        - criticality
        - environment
        - operational_profile
        """
        version_id = uuid4()
        cse_id = uuid4()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        cse = CSE(
            cse_id=cse_id,
            name="Bank_4D",
            sector="Financial",
            scale="Large",
            reporting_period_id=uuid4(),
            dataset_version_id=version_id,
            ingest_time=now,
        )

        # Create 5 workflows each for 2 distinct 4D cohorts:
        # Cohort A: (SERVER, CRITICAL, PRODUCTION, 24X7_MISSION_CRITICAL) -> median = 5000.0
        cohort_a_wfs = [
            _make_mock_workflow(
                cse_id=cse_id,
                dataset_version_id=version_id,
                asset_class="SERVER",
                criticality=AssetCriticality.CRITICAL,
                environment="PRODUCTION",
                operational_profile="24X7_MISSION_CRITICAL",
                closure_duration_seconds=5000.0,
            )
            for _ in range(5)
        ]

        # Cohort B: (WORKSTATION, LOW, CORP, STANDARD_OFFICE) -> median = 1000.0
        cohort_b_wfs = [
            _make_mock_workflow(
                cse_id=cse_id,
                dataset_version_id=version_id,
                asset_class="WORKSTATION",
                criticality=AssetCriticality.LOW,
                environment="CORP",
                operational_profile="STANDARD_OFFICE",
                closure_duration_seconds=1000.0,
            )
            for _ in range(5)
        ]

        dataset = _build_test_reconstructed_dataset(cohort_a_wfs + cohort_b_wfs, [cse], version_id)
        engine = PeerBenchmarkEngine(dataset, min_peer_group_size=5)

        # Verify Cohort A
        comp_a = engine.compare_metric(
            entity_value=5000.0,
            asset_class="SERVER",
            criticality="CRITICAL",
            environment="PRODUCTION",
            operational_profile="24X7_MISSION_CRITICAL",
            metric_name="closure_duration",
        )
        assert comp_a.peer_group == "SERVER:CRITICAL:PRODUCTION:24X7_MISSION_CRITICAL"
        assert comp_a.peer_median == 5000.0
        assert comp_a.dimensions == {
            "asset_class": "SERVER",
            "criticality": "CRITICAL",
            "environment": "PRODUCTION",
            "operational_profile": "24X7_MISSION_CRITICAL",
        }

        # Verify Cohort B
        comp_b = engine.compare_metric(
            entity_value=1000.0,
            asset_class="WORKSTATION",
            criticality="LOW",
            environment="CORP",
            operational_profile="STANDARD_OFFICE",
            metric_name="closure_duration",
        )
        assert comp_b.peer_group == "WORKSTATION:LOW:CORP:STANDARD_OFFICE"
        assert comp_b.peer_median == 1000.0
        assert comp_b.dimensions == {
            "asset_class": "WORKSTATION",
            "criticality": "LOW",
            "environment": "CORP",
            "operational_profile": "STANDARD_OFFICE",
        }

    def test_peer_membership_versioning_and_persistence(self):
        """
        Requirement 6:
        Verifies that peer membership domain objects carry dataset_version_id, analysis_run_id,
        ruleset_version, and are persisted in the repository.
        """
        version_id = uuid4()
        analysis_run_id = uuid4()
        cse_id = uuid4()
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        cse = CSE(
            cse_id=cse_id,
            name="Entity_Persist",
            sector="Healthcare",
            scale="Medium",
            reporting_period_id=uuid4(),
            dataset_version_id=version_id,
            ingest_time=now,
        )

        wfs = [
            _make_mock_workflow(
                cse_id=cse_id,
                dataset_version_id=version_id,
                closure_duration_seconds=3600.0,
            )
            for _ in range(5)
        ]

        dataset = _build_test_reconstructed_dataset(wfs, [cse], version_id)
        engine = PeerBenchmarkEngine(
            dataset=dataset,
            min_peer_group_size=5,
            ruleset_version="V1",
            analysis_run_id=analysis_run_id,
        )

        peer_groups = engine.build_peer_groups()
        assert len(peer_groups) > 0

        for pg in peer_groups:
            assert isinstance(pg, PeerGroup)
            assert pg.dataset_version_id == version_id
            assert pg.analysis_run_id == analysis_run_id
            assert pg.ruleset_version == "V1"
            assert pg.created_at is not None
            assert isinstance(pg.dimensions, dict)

        # Test repository persistence & retrieval
        repo = InMemoryRepository()
        repo.persist_peer_groups(version_id, peer_groups)

        retrieved = repo.get_peer_groups(version_id)
        assert len(retrieved) == len(peer_groups)
        assert retrieved[0].dataset_version_id == version_id
        assert retrieved[0].analysis_run_id == analysis_run_id
