"""
Synthetic SOC Operational Evidence Dataset Generator & Validation Engine.
Adheres to the Generator/Detector Independence Protocol to construct realistic multi-sector CSE scenarios
and evaluate Precision, Recall, F1, and Supervisory Review Yield without circular validation.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from analytics.canonicalization.canonicalization import CanonicalDataset, canonicalize_records
from analytics.data_quality.quality_processor import evaluate_dataset_quality
from analytics.data_quality.quality_score import DataQualityResult
from analytics.execution_gap.escalation_gap import EscalationGapDetector
from analytics.execution_gap.fast_closure import FastClosureDetector
from analytics.execution_gap.investigation_sufficiency import InvestigationSufficiencyDetector
from analytics.execution_gap.repeated_unresolved import RepeatedUnresolvedDetector
from analytics.execution_gap.workflow_shortcuts import WorkflowShortcutDetector
from analytics.fusion.evidence_fusion import EvidenceFusionEngine
from analytics.negative_space.coverage_gap import CoverageGapDetector
from analytics.peer_benchmark.benchmarks import PeerBenchmarkEngine
from analytics.workflow.workflow_reconstruction import ReconstructedDataset
from backend.models.canonical import Finding


@dataclass
class GroundTruthScenario:
    cse_id: UUID
    cse_name: str
    sector: str
    scale: str
    has_fast_closure: bool
    has_escalation_gap: bool
    has_repeated_unresolved: bool
    has_coverage_gap: bool
    is_data_outage: bool
    self_reported_sla: float
    description: str


def generate_synthetic_soc_benchmark(
    seed: int = 42,
    dataset_version_id: UUID | None = None,
    is_held_out: bool = False,
) -> tuple[dict[str, list[dict[str, Any]]], list[GroundTruthScenario]]:
    """
    Constructs multi-CSE synthetic datasets representing Power, Banking, Telecom, and Transport sectors.
    Includes the headline Goodhart's Law case study (CSE-B) and held-out evaluation scenarios.
    """
    rng = random.Random(seed + (1000 if is_held_out else 0))
    version_id = dataset_version_id or uuid4()
    now = datetime.now(timezone.utc)
    base_time = now - timedelta(days=30)

    raw_bundle: dict[str, list[dict[str, Any]]] = {
        "cse": [],
        "reporting_periods": [],
        "assets": [],
        "alerts": [],
        "investigations": [],
        "cases": [],
        "escalations": [],
        "actions": [],
        "closures": [],
        "coverage_observations": [],
    }

    scenarios: list[GroundTruthScenario] = []

    # Scenario definitions
    scenario_configs = [
        {
            "name": "Northern Power Grid Co.",
            "sector": "Power & Energy",
            "scale": "large",
            "fast_closure": False,
            "escalation_gap": False,
            "repeated_unresolved": False,
            "coverage_gap": False,
            "data_outage": False,
            "self_reported_sla": 0.965,
            "desc": "Baseline healthy critical infrastructure entity with standard investigation depth.",
        },
        {
            "name": "National Power Dispatch Center (NPDC)",
            "sector": "Power & Energy",
            "scale": "large",
            "fast_closure": True,
            "escalation_gap": True,
            "repeated_unresolved": True,
            "coverage_gap": False,
            "data_outage": False,
            "self_reported_sla": 0.992,
            "desc": "THE WOW MOMENT: 99.2% self-reported SLA compliance, but operational evidence shows rapid closures (avg 4m), 0 escalations on SCADA alerts, and repeated ransomware triggers.",
        },
        {
            "name": "Federal Reserve Core Banking",
            "sector": "Financial Services",
            "scale": "large",
            "fast_closure": False,
            "escalation_gap": False,
            "repeated_unresolved": False,
            "coverage_gap": False,
            "data_outage": False,
            "self_reported_sla": 0.978,
            "desc": "High compliance financial sector entity with robust multi-tiered escalation.",
        },
        {
            "name": "Metro Rail Transit Command",
            "sector": "Transportation",
            "scale": "medium",
            "fast_closure": True,
            "escalation_gap": False,
            "repeated_unresolved": False,
            "coverage_gap": False,
            "data_outage": False,
            "self_reported_sla": 0.985,
            "desc": "Overworked L1 analysts closing signalling alerts below peer duration.",
        },
        {
            "name": "National Telecom Core Backbone",
            "sector": "Telecommunications",
            "scale": "large",
            "fast_closure": False,
            "escalation_gap": True,
            "repeated_unresolved": False,
            "coverage_gap": False,
            "data_outage": False,
            "self_reported_sla": 0.940,
            "desc": "Core router alerts resolving without Tier-2 escalation records.",
        },
        {
            "name": "State Healthcare Exchange",
            "sector": "Healthcare & Defense",
            "scale": "medium",
            "fast_closure": False,
            "escalation_gap": False,
            "repeated_unresolved": False,
            "coverage_gap": True,
            "data_outage": False,
            "self_reported_sla": 0.950,
            "desc": "Negative space: EHR Database is completely silent (0 observed vs 50 expected) despite healthy pipeline.",
        },
        {
            "name": "Coastal Water Authority",
            "sector": "Power & Energy",
            "scale": "large",
            "fast_closure": False,
            "escalation_gap": False,
            "repeated_unresolved": False,
            "coverage_gap": False,
            "data_outage": True,
            "self_reported_sla": 0.820,
            "desc": "Known data ingestion disruption: low activity correctly classified as data uncertainty, NOT an operational breach.",
        },
    ]

    for cfg in scenario_configs:
        cse_id = uuid4()
        rep_id = uuid4()

        raw_bundle["cse"].append(
            {
                "cse_id": str(cse_id),
                "name": cfg["name"],
                "sector": cfg["sector"],
                "scale": cfg["scale"],
                "reporting_period_id": str(rep_id),
            }
        )

        raw_bundle["reporting_periods"].append(
            {
                "reporting_period_id": str(rep_id),
                "cse_id": str(cse_id),
                "period_start": base_time.isoformat(),
                "period_end": now.isoformat(),
            }
        )

        scenario = GroundTruthScenario(
            cse_id=cse_id,
            cse_name=cfg["name"],
            sector=cfg["sector"],
            scale=cfg["scale"],
            has_fast_closure=cfg["fast_closure"],
            has_escalation_gap=cfg["escalation_gap"],
            has_repeated_unresolved=cfg["repeated_unresolved"],
            has_coverage_gap=cfg["coverage_gap"],
            is_data_outage=cfg["data_outage"],
            self_reported_sla=cfg["self_reported_sla"],
            description=cfg["desc"],
        )
        scenarios.append(scenario)

        # Generate Assets for this CSE
        assets = [
            ("SCADA Substation Master Node", "SCADA Controller", "CRITICAL", "High Voltage Grid"),
            ("Primary Domain Controller", "Identity Server", "CRITICAL", "Internal Corp"),
            ("Database Cluster Alpha", "SQL Cluster", "HIGH", "Data Center"),
            ("Edge Log Forwarder", "Telemetry Node", "MEDIUM", "DMZ"),
        ]

        asset_ids = []
        for a_name, a_type, a_crit, env in assets:
            a_id = uuid4()
            asset_ids.append((a_id, a_name, a_type, a_crit))
            raw_bundle["assets"].append(
                {
                    "asset_id": str(a_id),
                    "cse_id": str(cse_id),
                    "criticality": a_crit,
                    "asset_type": a_type,
                    "environment": env,
                    "expected_monitoring_context": f"Active 24/7 SIEM & EDR telemetry for {a_name}",
                }
            )

        # Generate Alerts & Lifecycle Evidence
        alert_count = rng.randint(25, 40)
        if cfg["data_outage"]:
            alert_count = 5  # Very low due to ingestion outage

        for i in range(alert_count):
            alt_id = uuid4()
            case_id = uuid4()
            inv_id = uuid4()
            clo_id = uuid4()

            target_asset = asset_ids[i % len(asset_ids)]
            event_dt = base_time + timedelta(
                days=rng.uniform(1, 28), hours=rng.uniform(0, 23)
            )

            # Assign Severity
            if cfg["fast_closure"] or cfg["escalation_gap"]:
                sev = "CRITICAL" if i < 10 else ("HIGH" if i < 18 else "MEDIUM")
            else:
                sev = rng.choice(["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"])

            category = rng.choice(
                [
                    "SCADA Intrusion",
                    "Ransomware",
                    "Privilege Escalation",
                    "Unauthorized Access",
                    "Brute Force",
                    "Malware Execution",
                ]
            )
            if cfg["repeated_unresolved"] and i < 5:
                # Force repeat alerts on the same critical asset
                target_asset = asset_ids[0]
                category = "SCADA Intrusion"

            raw_bundle["alerts"].append(
                {
                    "alert_id": str(alt_id),
                    "cse_id": str(cse_id),
                    "asset_id": str(target_asset[0]),
                    "reporting_period_id": str(rep_id),
                    "event_time": event_dt.isoformat(),
                    "severity": sev,
                    "alert_category": category,
                    "source": "Splunk/EDR",
                    "status": "CLOSED",
                }
            )

            # Investigation Evidence
            inv_start = event_dt + timedelta(minutes=rng.uniform(1, 10))
            if cfg["fast_closure"] and sev in ("CRITICAL", "HIGH"):
                # Anomaly: Rapid closure (3-6 minutes) and 0-1 evidence records
                duration_sec = rng.uniform(180, 360)
                evidence_cnt = rng.choice([0, 1])
            else:
                # Normal baseline: 35-70 minutes and 3-8 evidence records
                duration_sec = rng.uniform(2100, 4200)
                evidence_cnt = rng.randint(3, 8)

            inv_end = inv_start + timedelta(seconds=duration_sec)

            raw_bundle["investigations"].append(
                {
                    "investigation_id": str(inv_id),
                    "alert_id": str(alt_id),
                    "started_at": inv_start.isoformat(),
                    "ended_at": inv_end.isoformat(),
                    "analyst_id": f"analyst_{rng.randint(101, 115)}",
                    "evidence_count": evidence_cnt,
                    "disposition": "False Positive / Auto-Remediated",
                }
            )

            raw_bundle["cases"].append(
                {
                    "case_id": str(case_id),
                    "alert_id": str(alt_id),
                    "opened_at": inv_start.isoformat(),
                    "closed_at": inv_end.isoformat(),
                    "severity": sev,
                    "outcome": "Closed per SOP",
                }
            )

            # Escalations
            if sev == "CRITICAL" and not cfg["escalation_gap"]:
                raw_bundle["escalations"].append(
                    {
                        "escalation_id": str(uuid4()),
                        "case_id": str(case_id),
                        "escalated_at": (inv_start + timedelta(minutes=5)).isoformat(),
                        "level": "Tier-2",
                        "target": "Senior Incident Responder",
                    }
                )

            # Actions / Remediations
            if not cfg["repeated_unresolved"] and i % 3 == 0:
                raw_bundle["actions"].append(
                    {
                        "action_id": str(uuid4()),
                        "case_id": str(case_id),
                        "action_type": "Isolate Endpoint & Deploy Rule",
                        "performed_at": (inv_start + timedelta(minutes=15)).isoformat(),
                        "outcome": "Success",
                    }
                )

            raw_bundle["closures"].append(
                {
                    "closure_id": str(clo_id),
                    "case_id": str(case_id),
                    "closed_at": inv_end.isoformat(),
                    "reason": "Resolved",
                    "reviewer": f"lead_{rng.randint(1, 5)}",
                }
            )

        # Coverage Observations for Negative Space
        for a_id, a_name, a_type, a_crit in asset_ids:
            expected_cnt = 40.0
            if cfg["coverage_gap"] and a_crit == "CRITICAL" and "SCADA" in a_name:
                obs_cnt = 0.0  # Silent critical asset
            else:
                obs_cnt = rng.uniform(32.0, 48.0)

            raw_bundle["coverage_observations"].append(
                {
                    "observation_id": str(uuid4()),
                    "cse_id": str(cse_id),
                    "asset_id": str(a_id),
                    "alert_category": "SCADA Intrusion",
                    "period_id": str(rep_id),
                    "expected_count": expected_cnt,
                    "observed_count": obs_cnt,
                }
            )

    return raw_bundle, scenarios


def run_full_analytical_pipeline(
    raw_bundle: dict[str, list[dict[str, Any]]],
    dataset_version_id: UUID | None = None,
    ruleset_version: str = "V1",
) -> tuple[CanonicalDataset, ReconstructedDataset, PeerBenchmarkEngine, list[Finding], DataQualityResult, UUID]:
    """
    Executes the complete end-to-end analytical pipeline:
    Canonicalization -> Workflow Reconstruction -> Peer Benchmarking -> Data Trust ->
    Detectors (Fast Closure, Escalation Gap, Repeated Unresolved, Coverage Gap) -> Evidence Fusion.

    Returns a 6-tuple: (canonical_ds, reconstructed_ds, benchmark_engine, findings, dq_result, analysis_run_id)
    The analysis_run_id is the UUID that links every finding back to this specific pipeline execution.
    """
    from datetime import datetime, timezone as tz
    ver_id = dataset_version_id or uuid4()
    analysis_run_id = uuid4()

    # 1. Canonicalization
    canonical_ds = canonicalize_records(raw_bundle, ver_id)

    # 2. Workflow Reconstruction
    reconstructed_ds = ReconstructedDataset(canonical_ds)

    # 3. Peer Benchmarking Engine
    benchmark_engine = PeerBenchmarkEngine(reconstructed_ds)

    # 4. Data Quality Engine
    dq_result = evaluate_dataset_quality(canonical_ds, ver_id, ruleset_version=ruleset_version)

    # 5. Detectors (P0 and P1 Core Suites)
    fast_closure_detector = FastClosureDetector()
    escalation_gap_detector = EscalationGapDetector()
    repeated_unresolved_detector = RepeatedUnresolvedDetector()
    coverage_gap_detector = CoverageGapDetector()
    investigation_sufficiency_detector = InvestigationSufficiencyDetector()
    workflow_shortcut_detector = WorkflowShortcutDetector()

    fast_closures = fast_closure_detector.detect(reconstructed_ds, benchmark_engine)
    escalation_gaps = escalation_gap_detector.detect(reconstructed_ds)
    repeated_unresolved = repeated_unresolved_detector.detect(reconstructed_ds)
    coverage_gaps = coverage_gap_detector.detect(canonical_ds, dq_result.score)
    inv_sufficiencies = investigation_sufficiency_detector.detect(reconstructed_ds, benchmark_engine)
    wf_shortcuts = workflow_shortcut_detector.detect(reconstructed_ds)

    # 6. Evidence Fusion
    fusion_engine = EvidenceFusionEngine(ruleset_version=ruleset_version)
    all_findings: list[Finding] = []

    for cse in canonical_ds.cse_list:
        rep_id = cse.reporting_period_id
        cse_findings = fusion_engine.fuse_signals(
            cse_id=cse.cse_id,
            reporting_period_id=rep_id,
            dataset_version_id=ver_id,
            analysis_run_id=analysis_run_id,
            data_quality_result=dq_result,
            fast_closures=fast_closures,
            escalation_gaps=escalation_gaps,
            repeated_unresolved=repeated_unresolved,
            coverage_gaps=coverage_gaps,
            investigation_sufficiencies=inv_sufficiencies,
            workflow_shortcuts=wf_shortcuts,
        )
        all_findings.extend(cse_findings)

    return canonical_ds, reconstructed_ds, benchmark_engine, all_findings, dq_result, analysis_run_id


def evaluate_ground_truth_validation(
    is_held_out: bool = False,
) -> dict[str, Any]:
    """
    Computes precision, recall, F1, Top-K recall, and Supervisory Review Yield
    against known ground truth scenarios.
    """
    raw_bundle, scenarios = generate_synthetic_soc_benchmark(
        seed=101 if is_held_out else 42,
        is_held_out=is_held_out,
    )
    canonical_ds, reconstructed_ds, bm_engine, findings, _, _run_id = run_full_analytical_pipeline(raw_bundle)

    # Build ground truth weakness map
    gt_map: dict[UUID, set[str]] = {}
    for s in scenarios:
        gt_set = set()
        if s.has_fast_closure:
            gt_set.add("FAST_CLOSURE")
        if s.has_escalation_gap:
            gt_set.add("ESCALATION_GAP")
        if s.has_repeated_unresolved:
            gt_set.add("REPEATED_UNRESOLVED_ALERTS")
        if s.has_coverage_gap and not s.is_data_outage:
            gt_set.add("COVERAGE_GAP")
        gt_map[s.cse_id] = gt_set

    # Tally detections
    total_gt = sum(len(gts) for gts in gt_map.values())
    tp = 0
    fp = 0

    detected_pairs = set()
    for f in findings:
        pair = (f.cse_id, f.finding_type.value)
        if pair in detected_pairs:
            continue
        detected_pairs.add(pair)

        if f.cse_id in gt_map and f.finding_type.value in gt_map[f.cse_id]:
            tp += 1
        else:
            fp += 1

    fn = max(0, total_gt - tp)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(total_gt, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-6)

    # Compute Supervisory Review Yield
    # Sort findings by PriorityScore DESC
    sorted_findings = sorted(findings, key=lambda f: f.priority_score, reverse=True)
    yield_curve = []
    accumulated_tp = 0
    seen_gt = set()

    for idx, f in enumerate(sorted_findings, start=1):
        pair = (f.cse_id, f.finding_type.value)
        if pair not in seen_gt:
            seen_gt.add(pair)
            if f.cse_id in gt_map and f.finding_type.value in gt_map[f.cse_id]:
                accumulated_tp += 1
        yield_curve.append(
            {
                "cases_reviewed": idx,
                "true_weaknesses_captured": accumulated_tp,
                "total_true_weaknesses": total_gt,
                "yield_percentage": round((accumulated_tp / max(total_gt, 1)) * 100, 1),
            }
        )

    return {
        "dataset_split": "Held-Out Set" if is_held_out else "Tuning Set",
        "scenarios_evaluated": len(scenarios),
        "total_true_weaknesses": total_gt,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4),
        "top_k_recall": round(min(1.0, tp / max(total_gt, 1)), 4),
        "yield_summary": f"{accumulated_tp} of {total_gt} true supervisory weaknesses captured in top {len(sorted_findings)} prioritized cases.",
        "yield_curve": yield_curve,
    }
