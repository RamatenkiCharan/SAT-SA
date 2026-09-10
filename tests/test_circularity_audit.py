"""
Automated Circularity Audit & Detector Independence Regression Tests.
Source of Truth: SRS §19.4 (Generator/Detector Independence Protocol), §24 (Validation).

Verifies:
1. Detector Invariance: Adding arbitrary generator metadata, decoy flags, or synthetic tags
   to raw operational records does NOT alter detector outputs or finding scores.
2. Direct Canonical Execution: Detectors operate purely on handcrafted canonical telemetry
   without requiring synthetic generator structures.
3. Parameterized Scenario Engine: Supports arbitrary parameter matrices across all 6 dimensions:
   timing, severity, asset class, peer composition, missingness, noise.
4. Unseen Held-Out Combinations: Held-out suite (>= 20%) utilizes novel combinations of asset classes,
   timing ranges, and noise profiles not present in the tuning set.
5. Statistical Robustness & Perturbation Stability: Dynamic peer MAD and percentile calculations
   generalize stably across randomized timing and volume perturbations without threshold brittleness.
"""
from __future__ import annotations

import copy
import random
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from analytics.canonicalization.canonicalization import (
    CanonicalDataset,
    canonicalize_records,
)
from analytics.data_quality.quality_processor import evaluate_dataset_quality
from analytics.execution_gap.escalation_gap import EscalationGapDetector
from analytics.execution_gap.fast_closure import FastClosureDetector
from analytics.execution_gap.repeated_unresolved import RepeatedUnresolvedDetector
from analytics.negative_space.coverage_gap import CoverageGapDetector
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.synthetic_generator import (
    HELD_OUT_SCENARIO_CONFIGS,
    TUNING_SCENARIO_CONFIGS,
    AssetArchetype,
    MissingnessParameters,
    NoiseParameters,
    ScenarioParameters,
    SeverityParameters,
    TimingParameters,
    generate_parameterized_scenario,
    generate_synthetic_soc_benchmark,
    run_full_analytical_pipeline,
)
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import (
    CSE,
    Alert,
    AlertStatus,
    Asset,
    AssetCriticality,
    Case,
    Closure,
    CoverageObservation,
    Escalation,
    Investigation,
    Severity,
)
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1


def test_detectors_ignore_generator_metadata_and_decoy_tags():
    """
    Circularity Invariance Test:
    Injects decoy labels and generator-specific mock metadata into raw telemetry.
    Proves detectors ignore non-canonical fields and produce identical results.
    """
    raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, is_held_out=False)
    clean_bundle = copy.deepcopy(raw_bundle)

    # Injected tainted bundle with misleading decoy tags
    tainted_bundle = copy.deepcopy(raw_bundle)

    for alt in tainted_bundle["alerts"]:
        alt["_generator_tag"] = "DECOY_FAST_CLOSURE_FLAG"
        alt["is_defect"] = False
        alt["ground_truth_category"] = "DO_NOT_FLAG"
        alt["synthetic_metadata"] = {"cheat_code": "override_detector"}

    for cs in tainted_bundle["cases"]:
        cs["_case_label"] = "CLEAN_CASE_IGNORE"
        cs["target_defect"] = None

    for inv in tainted_bundle["investigations"]:
        inv["generator_hint"] = "substandard_evidence"

    for cov in tainted_bundle["coverage_observations"]:
        cov["is_silent_gap"] = True
        cov["decoy_score"] = 99.9

    # Execute pipeline on both bundles
    clean_res = run_full_analytical_pipeline(clean_bundle)
    tainted_res = run_full_analytical_pipeline(tainted_bundle)

    # Assert exact finding count and identical finding attributes
    assert len(clean_res.findings) == len(tainted_res.findings)

    clean_findings = sorted(clean_res.findings, key=lambda f: (f.finding_type.value, f.priority_score))
    tainted_findings = sorted(tainted_res.findings, key=lambda f: (f.finding_type.value, f.priority_score))

    for cf, tf in zip(clean_findings, tainted_findings):
        assert cf.finding_type == tf.finding_type
        assert abs(cf.priority_score - tf.priority_score) < 1e-5
        assert cf.priority_components == tf.priority_components
        assert cf.observed_behavior == tf.observed_behavior
        assert cf.expected_behavior == tf.expected_behavior
        assert len(cf.evidence_refs) == len(tf.evidence_refs)


def test_detectors_work_on_handcrafted_canonical_telemetry():
    """
    Pure Canonical Verification:
    Constructs canonical telemetry directly without calling synthetic generators.
    Proves all 4 detectors operate purely on schema mechanics.
    """
    version_id = uuid4()
    now = datetime.now(timezone.utc)
    cse_id = uuid4()
    rep_id = uuid4()

    # 1. Manually construct CSE & Asset
    cse = CSE(
        cse_id=cse_id,
        name="Manual Airgap Test Grid",
        sector="Power & Energy",
        scale="large",
        reporting_period_id=rep_id,
        dataset_version_id=version_id,
        source_record_ref="manual:cse:1",
        ingest_time=now,
    )

    asset = Asset(
        asset_id=uuid4(),
        cse_id=cse_id,
        criticality=AssetCriticality.CRITICAL,
        asset_type="SCADA Controller",
        environment="PRODUCTION",
        expected_monitoring_context="High Voltage Grid SCADA Master",
        dataset_version_id=version_id,
        source_record_ref="manual:asset:1",
        ingest_time=now,
    )

    # 2. Handcraft Fast Closure: 10 alerts in peer cohort, 1 rapid closure (120s, 0 evidence)
    alerts = []
    cases = []
    investigations = []
    closures = []

    for i in range(10):
        alt_id = uuid4()
        case_id = uuid4()
        inv_id = uuid4()
        clo_id = uuid4()

        event_time = now - timedelta(days=20 - i)
        is_rapid = (i == 0)

        # Baseline: 3600s duration, 5 evidence items. Anomaly: 120s duration, 0 evidence items.
        dur_sec = 120.0 if is_rapid else 3600.0
        ev_cnt = 0 if is_rapid else 5

        alerts.append(
            Alert(
                alert_id=alt_id,
                cse_id=cse_id,
                asset_id=asset.asset_id,
                reporting_period_id=rep_id,
                event_time=event_time,
                severity=Severity.CRITICAL,
                alert_category="SCADA Intrusion",
                source="Splunk",
                status=AlertStatus.CLOSED,
                dataset_version_id=version_id,
                source_record_ref=f"manual:alt:{i}",
                ingest_time=now,
            )
        )

        cases.append(
            Case(
                case_id=case_id,
                alert_id=alt_id,
                opened_at=event_time + timedelta(minutes=1),
                closed_at=event_time + timedelta(minutes=1, seconds=dur_sec),
                severity=Severity.CRITICAL,
                outcome="Resolved",
                dataset_version_id=version_id,
                source_record_ref=f"manual:case:{i}",
                ingest_time=now,
            )
        )

        investigations.append(
            Investigation(
                investigation_id=inv_id,
                alert_id=alt_id,
                started_at=event_time + timedelta(minutes=1),
                ended_at=event_time + timedelta(minutes=1, seconds=dur_sec),
                analyst_id=f"analyst_{i}",
                evidence_count=ev_cnt,
                disposition="Closed",
                dataset_version_id=version_id,
                source_record_ref=f"manual:inv:{i}",
                ingest_time=now,
            )
        )

        closures.append(
            Closure(
                closure_id=clo_id,
                case_id=case_id,
                closed_at=event_time + timedelta(minutes=1, seconds=dur_sec),
                reason="Resolved",
                reviewer="lead_1",
                dataset_version_id=version_id,
                source_record_ref=f"manual:clo:{i}",
                ingest_time=now,
            )
        )

    canonical_ds = CanonicalDataset(
        dataset_version_id=version_id,
        cse_list=[cse],
        assets=[asset],
        alerts=alerts,
        investigations=investigations,
        cases=cases,
        escalations=[],
        actions=[],
        closures=closures,
        coverage_observations=[
            CoverageObservation(
                observation_id=uuid4(),
                cse_id=cse_id,
                asset_id=asset.asset_id,
                alert_category="SCADA Intrusion",
                period_id=rep_id,
                expected_count=40.0,
                observed_count=0.0,  # Coverage gap
                dataset_version_id=version_id,
                source_record_ref="manual:cov:1",
                ingest_time=now,
            )
        ],
    )

    reconstructed_ds = ReconstructedDataset(canonical_ds)
    bm_engine = PeerBenchmarkEngine(reconstructed_ds)

    # Test Detectors
    fast_det = FastClosureDetector(config=DEFAULT_AUTHORITATIVE_RULESET_V1.detector_config.fast_closure)
    esc_det = EscalationGapDetector(config=DEFAULT_AUTHORITATIVE_RULESET_V1.detector_config.escalation_gap)
    rep_det = RepeatedUnresolvedDetector(config=DEFAULT_AUTHORITATIVE_RULESET_V1.detector_config.repeated_unresolved)
    cov_det = CoverageGapDetector(config=DEFAULT_AUTHORITATIVE_RULESET_V1.detector_config.coverage_gap)

    fast_signals = fast_det.detect(reconstructed_ds, bm_engine)
    esc_signals = esc_det.detect(reconstructed_ds)
    rep_signals = rep_det.detect(reconstructed_ds)
    cov_signals = cov_det.detect(canonical_ds, data_quality_score=0.95)

    # Fast closure flags exactly the 1 rapid workflow
    assert len(fast_signals) == 1
    assert fast_signals[0].closure_duration_seconds == 120.0

    # Escalation gap flags all 10 critical alerts since no escalations exist
    assert len(esc_signals) == 10

    # Repeated unresolved flags recurrence (10 alerts on same asset without action)
    assert len(rep_signals) == 1
    assert rep_signals[0].alert_count == 10

    # Coverage gap flags the silent observation
    assert len(cov_signals) == 1
    assert cov_signals[0].observed_count == 0.0


def test_parameterized_scenario_generation_all_six_dimensions():
    """
    Parametric Generator Verification:
    Tests generation across all 6 dimensions: timing, severity, asset class, peer composition, missingness, noise.
    """
    now = datetime.now(timezone.utc)
    base_time = now - timedelta(days=30)
    rng = random.Random(777)

    params = ScenarioParameters(
        name="Quantum Research Cloud Grid",
        sector="Healthcare & Defense",
        scale="medium",
        primary_category="fast closure defect",
        categories=["fast closure defect", "noisy data"],
        has_fast_closure=True,
        has_escalation_gap=False,
        has_repeated_unresolved=False,
        has_coverage_gap=False,
        self_reported_sla=0.975,
        description="Custom parametric stress test entity.",
        timing=TimingParameters(
            fast_closure_range=(45.0, 110.0),  # Ultra fast closures
            normal_closure_range=(3600.0, 7200.0),
            investigation_evidence_range_defect=(0, 0),
            investigation_evidence_range_normal=(5, 12),
        ),
        severity=SeverityParameters(
            defect_severities=["CRITICAL", "HIGH"],
        ),
        assets=[
            AssetArchetype("Quantum Random Engine", "SCADA Controller", "CRITICAL", "Secure Lab", "Active Quantum Telemetry"),
            AssetArchetype("Cryo-Cooling Telemetry Hub", "Telemetry Node", "HIGH", "Cryo Bay", "Thermal Monitoring"),
        ],
        missingness=MissingnessParameters(
            is_data_outage=False,
            expected_coverage_count=50.0,
            observed_coverage_count_normal_range=(45.0, 50.0),
        ),
        noise=NoiseParameters(
            is_noisy=True,
            noisy_alert_count_range=(65, 85),
        ),
    )

    bundle, gt = generate_parameterized_scenario(params, rng, base_time, now)

    assert gt.cse_name == "Quantum Research Cloud Grid"
    assert len(bundle["assets"]) == 2
    assert len(bundle["alerts"]) >= 65
    assert len(bundle["investigations"]) == len(bundle["alerts"])
    assert len(bundle["cases"]) == len(bundle["alerts"])
    assert len(bundle["coverage_observations"]) == 2

    # Execute pipeline over single custom scenario
    pipeline_res = run_full_analytical_pipeline(bundle)
    assert len(pipeline_res.canonical_dataset.alerts) >= 65
    assert len(pipeline_res.findings) >= 1

    # Verify that fast closure was detected with ultra-fast duration
    fast_findings = [f for f in pipeline_res.findings if f.finding_type.value == "FAST_CLOSURE"]
    assert len(fast_findings) == 1
    assert fast_findings[0].priority_score >= 0.70
    assert "fast closure" in fast_findings[0].observed_behavior.lower()


def test_held_out_scenarios_use_unseen_parameter_combinations():
    """
    Independence & Held-Out Composition Test:
    Verifies held-out set represents >= 20% of catalog and uses distinct, unseen parameter combinations.
    """
    total_scenarios = len(TUNING_SCENARIO_CONFIGS) + len(HELD_OUT_SCENARIO_CONFIGS)
    held_out_ratio = (len(HELD_OUT_SCENARIO_CONFIGS) / total_scenarios) * 100.0

    assert held_out_ratio >= 20.0
    assert len(HELD_OUT_SCENARIO_CONFIGS) == 5
    assert len(TUNING_SCENARIO_CONFIGS) == 10

    # Extract asset names in tuning vs held-out
    tuning_asset_names = set()
    for cfg in TUNING_SCENARIO_CONFIGS:
        assets = cfg.get("assets") or []
        for a in assets:
            tuning_asset_names.add(a.name)

    held_out_novel_assets = set()
    for cfg in HELD_OUT_SCENARIO_CONFIGS:
        assets = cfg.get("assets") or []
        for a in assets:
            held_out_novel_assets.add(a.name)

    # Verify held-out set introduces novel asset names
    assert len(held_out_novel_assets) >= 10
    novel_unseen = held_out_novel_assets - tuning_asset_names
    assert len(novel_unseen) >= 8
    assert "Solar Inverter Master Controller" in novel_unseen
    assert "SWIFT ISO20022 Wire Terminal" in novel_unseen
    assert "Ka-Band Satellite Transponder" in novel_unseen
    assert "PACS Medical Imaging Core" in novel_unseen


def test_circularity_resilience_randomized_perturbations():
    """
    Perturbation Stability Test:
    Applies diverse random seeds to ensure detection accuracy is resilient to statistical noise.
    """
    for test_seed in [10, 42, 99, 101, 2024]:
        raw_bundle, scenarios = generate_synthetic_soc_benchmark(seed=test_seed, is_held_out=True)
        pipeline_res = run_full_analytical_pipeline(raw_bundle)

        # Build expected weaknesses
        gt_weakness_count = sum(
            1 for s in scenarios if s.has_fast_closure or s.has_escalation_gap or s.has_repeated_unresolved or (s.has_coverage_gap and not s.is_data_outage)
        )

        detected_types = {f.finding_type.value for f in pipeline_res.findings}

        # Held-out scenario bundle contains fast closure, escalation gap, coverage gap, repeated unresolved
        assert "FAST_CLOSURE" in detected_types
        assert "ESCALATION_GAP" in detected_types
        assert "COVERAGE_GAP" in detected_types
        assert "REPEATED_UNRESOLVED_ALERTS" in detected_types
        assert len(pipeline_res.findings) >= gt_weakness_count


def test_adversarial_text_and_disposition_immunity():
    """
    Adversarial Text Payload & Disposition Immunity Test:
    Verifies that detectors evaluate strictly numerical telemetry timestamps,
    evidence counts, and entity graph linkages—completely ignoring deceptive
    human-readable text strings or misleading disposition labels.
    """
    version_id = uuid4()
    now = datetime.now(timezone.utc)
    cse_id = uuid4()
    rep_id = uuid4()

    cse = CSE(
        cse_id=cse_id,
        name="Adversarial Text Grid",
        sector="Power & Energy",
        scale="large",
        reporting_period_id=rep_id,
        dataset_version_id=version_id,
        source_record_ref="adv:cse:1",
        ingest_time=now,
    )

    asset = Asset(
        asset_id=uuid4(),
        cse_id=cse_id,
        criticality=AssetCriticality.CRITICAL,
        asset_type="SCADA Controller",
        environment="PRODUCTION",
        expected_monitoring_context="High Voltage Grid SCADA Master",
        dataset_version_id=version_id,
        source_record_ref="adv:asset:1",
        ingest_time=now,
    )

    alerts = []
    cases = []
    investigations = []
    closures = []

    # 10 workflows: 9 baseline, 1 fast closure defect disguised with deceptive text
    for i in range(10):
        alt_id = uuid4()
        case_id = uuid4()
        inv_id = uuid4()
        clo_id = uuid4()

        event_time = now - timedelta(days=20 - i)
        is_defect = (i == 0)

        dur_sec = 60.0 if is_defect else 3600.0
        ev_cnt = 0 if is_defect else 6

        # Deceptive text injected:
        # For the rapid closure defect: inject "Thorough Multi-Day Forensic Deep Dive with Full Tier 3 Escalation Approval"
        # For baseline clean workflows: inject "Quick closure defect cheat flag"
        disp_text = (
            "Thorough Multi-Day Forensic Deep Dive with Full Tier 3 Escalation Approval"
            if is_defect
            else "Quick closure defect cheat flag"
        )
        outcome_text = (
            "Exhaustive Root Cause Remediated"
            if is_defect
            else "Potential Fast Closure Defect"
        )

        alerts.append(
            Alert(
                alert_id=alt_id,
                cse_id=cse_id,
                asset_id=asset.asset_id,
                reporting_period_id=rep_id,
                event_time=event_time,
                severity=Severity.CRITICAL,
                alert_category="SCADA Intrusion",
                source="Splunk",
                status=AlertStatus.CLOSED,
                dataset_version_id=version_id,
                source_record_ref=f"adv:alt:{i}",
                ingest_time=now,
            )
        )

        cases.append(
            Case(
                case_id=case_id,
                alert_id=alt_id,
                opened_at=event_time + timedelta(minutes=1),
                closed_at=event_time + timedelta(minutes=1, seconds=dur_sec),
                severity=Severity.CRITICAL,
                outcome=outcome_text,
                dataset_version_id=version_id,
                source_record_ref=f"adv:case:{i}",
                ingest_time=now,
            )
        )

        investigations.append(
            Investigation(
                investigation_id=inv_id,
                alert_id=alt_id,
                started_at=event_time + timedelta(minutes=1),
                ended_at=event_time + timedelta(minutes=1, seconds=dur_sec),
                analyst_id=f"analyst_{i}",
                evidence_count=ev_cnt,
                disposition=disp_text,
                dataset_version_id=version_id,
                source_record_ref=f"adv:inv:{i}",
                ingest_time=now,
            )
        )

        closures.append(
            Closure(
                closure_id=clo_id,
                case_id=case_id,
                closed_at=event_time + timedelta(minutes=1, seconds=dur_sec),
                reason=outcome_text,
                reviewer="lead_1",
                dataset_version_id=version_id,
                source_record_ref=f"adv:clo:{i}",
                ingest_time=now,
            )
        )

    canonical_ds = CanonicalDataset(
        dataset_version_id=version_id,
        cse_list=[cse],
        assets=[asset],
        alerts=alerts,
        investigations=investigations,
        cases=cases,
        escalations=[],
        actions=[],
        closures=closures,
        coverage_observations=[],
    )

    reconstructed_ds = ReconstructedDataset(canonical_ds)
    bm_engine = PeerBenchmarkEngine(reconstructed_ds)

    fast_det = FastClosureDetector(config=DEFAULT_AUTHORITATIVE_RULESET_V1.detector_config.fast_closure)
    fast_signals = fast_det.detect(reconstructed_ds, bm_engine)

    # Assert: Exactly the 1 rapid workflow is flagged despite having "Thorough Multi-Day" disposition!
    assert len(fast_signals) == 1
    assert fast_signals[0].closure_duration_seconds == 60.0
    assert fast_signals[0].evidence_count == 0


def test_out_of_distribution_peer_cohort_statistical_robustness():
    """
    Out-of-Distribution Peer Cohort Statistical Robustness Test:
    Verifies that dynamic peer MAD and percentile calculations remain robust
    against extreme outliers and skewed baseline cohorts.
    """
    from analytics.peer_benchmark.benchmarks import compute_median_and_mad

    # 1. Heavily skewed distribution with extreme high-duration outliers
    durations = [1800.0, 2000.0, 2100.0, 2200.0, 2300.0, 2400.0, 2500.0, 86400.0, 172800.0]
    dist = compute_median_and_mad(durations, min_size=5)

    assert dist.count == 9
    assert dist.median == 2300.0  # Median is impervious to 86400s and 172800s outliers
    assert dist.mad > 0.0
    assert dist.p25 == 2100.0
    assert dist.low_confidence is False

    # 2. Identical values distribution (MAD near zero fallback protection)
    uniform_durations = [3600.0, 3600.0, 3600.0, 3600.0, 3600.0, 3600.0]
    dist_uniform = compute_median_and_mad(uniform_durations, min_size=5)

    assert dist_uniform.median == 3600.0
    # Fallback to standard deviation or minimum floor (>= 1.0) to prevent divide-by-zero
    assert dist_uniform.mad >= 1.0


def test_parameterized_generation_six_dimensions_independence_matrix():
    """
    Systematic 6-Dimensional Independence Matrix Verification:
    Verifies that held-out scenarios instantiate distinct, independent parameter values
    across all 6 required dimensions (timing, severity, asset class, peer composition, missingness, noise).
    """
    # 1. Dimension: Timing
    tuning_fast_ranges = [cfg.get("timing").fast_closure_range for cfg in TUNING_SCENARIO_CONFIGS if cfg.get("timing") and hasattr(cfg.get("timing"), "fast_closure_range")]
    held_out_fast_ranges = [cfg.get("timing").fast_closure_range for cfg in HELD_OUT_SCENARIO_CONFIGS if cfg.get("timing") and hasattr(cfg.get("timing"), "fast_closure_range")]
    assert (120.0, 240.0) in held_out_fast_ranges
    assert (120.0, 240.0) not in tuning_fast_ranges

    # 2. Dimension: Asset Class
    tuning_asset_classes = {a.name for cfg in TUNING_SCENARIO_CONFIGS for a in cfg.get("assets", [])}
    held_out_asset_classes = {a.name for cfg in HELD_OUT_SCENARIO_CONFIGS for a in cfg.get("assets", [])}
    assert "Solar Inverter Master Controller" in held_out_asset_classes
    assert "Solar Inverter Master Controller" not in tuning_asset_classes

    # 3. Dimension: Noise
    held_out_noise_cats = [cfg.get("noise").maintenance_category for cfg in HELD_OUT_SCENARIO_CONFIGS if cfg.get("noise") and hasattr(cfg.get("noise"), "maintenance_category")]
    assert "Track Calibration & Signal Diagnostics" in held_out_noise_cats

    # 4. Dimension: Missingness
    held_out_outages = [cfg.get("missingness").is_data_outage for cfg in HELD_OUT_SCENARIO_CONFIGS if cfg.get("missingness")]
    assert True in held_out_outages

    # 5. Dimension: Severity
    held_out_slas = [cfg.get("self_reported_sla") for cfg in HELD_OUT_SCENARIO_CONFIGS]
    assert min(held_out_slas) == 0.810  # Low SLA for data outage in Urban Metrorail

    # 6. Dimension: Peer Composition
    held_out_sectors = {cfg.get("sector") for cfg in HELD_OUT_SCENARIO_CONFIGS}
    assert {"Power & Energy", "Financial Services", "Telecommunications", "Healthcare & Defense", "Transportation"} == held_out_sectors

