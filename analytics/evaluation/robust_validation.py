"""
SAT-SA Robust Validation Framework (I-02/I-09).

Replaces the trivially-separable 15-scenario benchmark with a statistically
meaningful evaluation protocol:

- 200+ independently generated scenarios per run
- Overlapping normal/defect distributions (hard negatives)
- Parameter variation across timing, severity, noise, missingness
- Scenario-level held-out evaluation (≥25% held-out ratio)
- Generator/detector independence enforced
- No label leakage
- Bootstrap confidence intervals for all metrics
- Precision, Recall, F1, FPR, Top-1/3/5 ranking metrics
- Threshold sensitivity analysis
- Fusion-weight sensitivity analysis

**Synthetic-Validation Limitation**: All results in this module come from
synthetically generated scenarios.  They measure the detector's ability to
identify known planted defect patterns and MUST NOT be described as
production-grade validation.  Real-world validation requires operational
datasets from live SOC environments.
"""
from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from analytics.synthetic_generator import (
    AssetArchetype,
    GroundTruthScenario,
    MissingnessParameters,
    NoiseParameters,
    ScenarioParameters,
    SeverityParameters,
    TimingParameters,
    build_default_assets,
    generate_parameterized_scenario,
    run_full_analytical_pipeline,
)
from analytics.canonicalization.canonicalization import CanonicalDataset, canonicalize_records
from backend.models.canonical import Finding
from backend.models.ruleset import (
    DEFAULT_AUTHORITATIVE_RULESET_V1,
    AnalyticalRuleset,
)


# ---------------------------------------------------------------------------
# Data classes for results
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceInterval:
    """Bootstrap confidence interval."""
    mean: float
    lower: float
    upper: float
    std: float
    n_bootstrap: int

    def __repr__(self) -> str:
        return f"{self.mean:.4f} [{self.lower:.4f}, {self.upper:.4f}]"


@dataclass
class RobustConfusionMatrix:
    tp: int
    fp: int
    tn: int
    fn: int
    precision: float
    recall: float
    f1_score: float
    fpr: float
    precision_ci: Optional[ConfidenceInterval] = None
    recall_ci: Optional[ConfidenceInterval] = None
    f1_ci: Optional[ConfidenceInterval] = None
    fpr_ci: Optional[ConfidenceInterval] = None


@dataclass
class RankingMetrics:
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    total_findings: int
    total_true_positives: int


@dataclass
class ThresholdSensitivityPoint:
    threshold: float
    precision: float
    recall: float
    f1: float
    fpr: float
    tp: int
    fp: int
    tn: int
    fn: int


@dataclass
class WeightSensitivityPoint:
    weight_name: str
    original_value: float
    perturbed_value: float
    precision: float
    recall: float
    f1: float
    delta_f1: float


@dataclass
class RobustValidationResult:
    """Full result of the robust validation protocol."""
    protocol_version: str = "2.0-robust"
    total_scenarios: int = 0
    tuning_scenarios: int = 0
    held_out_scenarios: int = 0
    held_out_ratio: float = 0.0

    # Per-split metrics
    tuning_metrics: Optional[RobustConfusionMatrix] = None
    held_out_metrics: Optional[RobustConfusionMatrix] = None

    # Ranking
    tuning_ranking: Optional[RankingMetrics] = None
    held_out_ranking: Optional[RankingMetrics] = None

    # Sensitivity
    threshold_sensitivity: list[ThresholdSensitivityPoint] = field(default_factory=list)
    weight_sensitivity: list[WeightSensitivityPoint] = field(default_factory=list)

    # Category breakdown
    category_metrics: dict[str, RobustConfusionMatrix] = field(default_factory=dict)

    # Hard negative analysis
    hard_negative_count: int = 0
    hard_negative_fp_count: int = 0
    hard_negative_tn_count: int = 0

    # Disclosure
    limitation_notice: str = (
        "SYNTHETIC VALIDATION ONLY: These results measure detector performance "
        "against planted synthetic defect patterns. They do NOT constitute "
        "production validation. Real-world effectiveness requires evaluation "
        "on operational SOC datasets with independent ground truth."
    )

    def to_dict(self) -> dict[str, Any]:
        """Serializes result for JSON export."""
        d: dict[str, Any] = {
            "protocol_version": self.protocol_version,
            "limitation_notice": self.limitation_notice,
            "total_scenarios": self.total_scenarios,
            "tuning_scenarios": self.tuning_scenarios,
            "held_out_scenarios": self.held_out_scenarios,
            "held_out_ratio": round(self.held_out_ratio, 4),
            "hard_negative_count": self.hard_negative_count,
            "hard_negative_fp_count": self.hard_negative_fp_count,
            "hard_negative_tn_count": self.hard_negative_tn_count,
        }
        for split_name, metrics, ranking in [
            ("tuning", self.tuning_metrics, self.tuning_ranking),
            ("held_out", self.held_out_metrics, self.held_out_ranking),
        ]:
            if metrics:
                d[f"{split_name}_metrics"] = {
                    "tp": metrics.tp, "fp": metrics.fp,
                    "tn": metrics.tn, "fn": metrics.fn,
                    "precision": round(metrics.precision, 4),
                    "recall": round(metrics.recall, 4),
                    "f1_score": round(metrics.f1_score, 4),
                    "fpr": round(metrics.fpr, 4),
                }
                if metrics.precision_ci:
                    d[f"{split_name}_metrics"]["precision_ci"] = str(metrics.precision_ci)
                if metrics.recall_ci:
                    d[f"{split_name}_metrics"]["recall_ci"] = str(metrics.recall_ci)
            if ranking:
                d[f"{split_name}_ranking"] = {
                    "recall_at_1": round(ranking.recall_at_1, 4),
                    "recall_at_3": round(ranking.recall_at_3, 4),
                    "recall_at_5": round(ranking.recall_at_5, 4),
                }
        if self.threshold_sensitivity:
            d["threshold_sensitivity"] = [
                {"threshold": round(p.threshold, 2), "precision": round(p.precision, 4),
                 "recall": round(p.recall, 4), "f1": round(p.f1, 4), "fpr": round(p.fpr, 4)}
                for p in self.threshold_sensitivity
            ]
        if self.weight_sensitivity:
            d["weight_sensitivity"] = [
                {"weight": p.weight_name, "original": round(p.original_value, 4),
                 "perturbed": round(p.perturbed_value, 4), "f1": round(p.f1, 4),
                 "delta_f1": round(p.delta_f1, 4)}
                for p in self.weight_sensitivity
            ]
        return d


# ---------------------------------------------------------------------------
# Scenario generation with overlapping distributions
# ---------------------------------------------------------------------------

# Sectors for generation
_SECTORS = [
    "Power & Energy", "Financial Services", "Transportation",
    "Telecommunications", "Healthcare & Defense",
]
_SCALES = ["small", "medium", "large"]

_DEFECT_TYPES = [
    ("fast_closure", "fast closure defect"),
    ("escalation_gap", "escalation gap"),
    ("repeated_unresolved", "repeated unresolved behavior"),
    ("coverage_gap", "coverage gap"),
]


def _generate_scenario_configs(
    rng: random.Random,
    n_total: int = 240,
    held_out_ratio: float = 0.3,
    hard_negative_ratio: float = 0.15,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[bool]]:
    """
    Generate n_total scenario configs with controlled defect/normal ratios
    and hard negatives (near-threshold scenarios that look defective but aren't,
    or look normal but are).

    Returns (tuning_configs, held_out_configs, is_hard_negative_flags).
    """
    all_configs: list[dict[str, Any]] = []
    hard_negative_flags: list[bool] = []

    n_normal = int(n_total * 0.35)
    n_defect = int(n_total * 0.35)
    n_hard_neg = int(n_total * hard_negative_ratio)
    n_multi = n_total - n_normal - n_defect - n_hard_neg  # compound scenarios

    # 1. Clean normal scenarios
    for i in range(n_normal):
        sector = rng.choice(_SECTORS)
        scale = rng.choice(_SCALES)
        normal_lo = rng.uniform(1800, 3000)
        normal_hi = normal_lo + rng.uniform(1000, 3000)
        evidence_lo = rng.randint(3, 6)
        evidence_hi = evidence_lo + rng.randint(2, 5)
        sla = rng.uniform(0.92, 0.99)

        cfg = {
            "name": f"Normal-{sector[:3]}-{i:03d}",
            "sector": sector,
            "scale": scale,
            "primary_category": "normal behavior",
            "categories": ["normal behavior"],
            "fast_closure": False,
            "escalation_gap": False,
            "repeated_unresolved": False,
            "coverage_gap": False,
            "data_outage": False,
            "noisy_data": rng.random() < 0.15,  # some noise in normals
            "non_target_anomaly": rng.random() < 0.1,
            "self_reported_sla": round(sla, 3),
            "desc": f"Normal behavior scenario {i}",
            "timing": TimingParameters(
                normal_closure_range=(normal_lo, normal_hi),
                investigation_evidence_range_normal=(evidence_lo, evidence_hi),
            ),
        }
        if cfg["noisy_data"]:
            cfg["noise"] = NoiseParameters(is_noisy=True, noisy_alert_count_range=(30, 60))
        if cfg["non_target_anomaly"]:
            cfg["noise"] = NoiseParameters(is_maintenance_anomaly=True)
        all_configs.append(cfg)
        hard_negative_flags.append(False)

    # 2. Clear defect scenarios (single or compound)
    for i in range(n_defect):
        sector = rng.choice(_SECTORS)
        scale = rng.choice(_SCALES)
        sla = rng.uniform(0.90, 0.995)

        # Pick 1-2 random defects
        n_defects = rng.choices([1, 2], weights=[0.6, 0.4])[0]
        chosen = rng.sample(_DEFECT_TYPES, min(n_defects, len(_DEFECT_TYPES)))

        cats = []
        flags = {"fast_closure": False, "escalation_gap": False,
                 "repeated_unresolved": False, "coverage_gap": False}
        for flag_key, cat_name in chosen:
            flags[flag_key] = True
            cats.append(cat_name)

        fast_lo = rng.uniform(60, 300)
        fast_hi = fast_lo + rng.uniform(60, 200)

        cfg = {
            "name": f"Defect-{sector[:3]}-{i:03d}",
            "sector": sector,
            "scale": scale,
            "primary_category": cats[0],
            "categories": cats,
            "fast_closure": flags["fast_closure"],
            "escalation_gap": flags["escalation_gap"],
            "repeated_unresolved": flags["repeated_unresolved"],
            "coverage_gap": flags["coverage_gap"],
            "data_outage": False,
            "noisy_data": rng.random() < 0.2,
            "non_target_anomaly": False,
            "self_reported_sla": round(sla, 3),
            "desc": f"Defect scenario {i}: {', '.join(cats)}",
            "timing": TimingParameters(
                fast_closure_range=(fast_lo, fast_hi),
                investigation_evidence_range_defect=(0, 1),
            ),
        }
        if cfg["noisy_data"]:
            cfg["noise"] = NoiseParameters(is_noisy=True, noisy_alert_count_range=(25, 50))
        all_configs.append(cfg)
        hard_negative_flags.append(False)

    # 3. Hard negatives — scenarios at decision boundary
    for i in range(n_hard_neg):
        sector = rng.choice(_SECTORS)
        scale = rng.choice(_SCALES)
        is_actually_defective = rng.random() < 0.5

        if is_actually_defective:
            # Mild defect — borderline fast closures that are only slightly below normal
            close_lo = rng.uniform(800, 1500)  # borderline — between clear defect and normal
            close_hi = close_lo + rng.uniform(300, 800)
            evidence_lo = rng.randint(1, 3)  # borderline evidence
            evidence_hi = evidence_lo + rng.randint(1, 3)
            cfg = {
                "name": f"HardNeg-Mild-{i:03d}",
                "sector": sector,
                "scale": scale,
                "primary_category": "fast closure defect",
                "categories": ["fast closure defect"],
                "fast_closure": True,
                "escalation_gap": False,
                "repeated_unresolved": False,
                "coverage_gap": False,
                "data_outage": False,
                "noisy_data": rng.random() < 0.3,
                "non_target_anomaly": False,
                "self_reported_sla": round(rng.uniform(0.93, 0.98), 3),
                "desc": f"Hard negative (mild defect with borderline timing) {i}",
                "timing": TimingParameters(
                    fast_closure_range=(close_lo, close_hi),
                    investigation_evidence_range_defect=(evidence_lo, evidence_hi),
                ),
            }
        else:
            # Looks suspicious but is actually clean — fast legitimate operations
            close_lo = rng.uniform(600, 1200)
            close_hi = close_lo + rng.uniform(500, 1200)
            evidence_lo = rng.randint(3, 5)
            evidence_hi = evidence_lo + rng.randint(2, 4)
            cfg = {
                "name": f"HardNeg-Clean-{i:03d}",
                "sector": sector,
                "scale": scale,
                "primary_category": "normal behavior",
                "categories": ["normal behavior"],
                "fast_closure": False,
                "escalation_gap": False,
                "repeated_unresolved": False,
                "coverage_gap": False,
                "data_outage": False,
                "noisy_data": True,  # high noise makes it look suspicious
                "non_target_anomaly": rng.random() < 0.4,
                "self_reported_sla": round(rng.uniform(0.88, 0.95), 3),
                "desc": f"Hard negative (clean but suspicious-looking) {i}",
                "timing": TimingParameters(
                    normal_closure_range=(close_lo, close_hi),
                    investigation_evidence_range_normal=(evidence_lo, evidence_hi),
                ),
                "noise": NoiseParameters(is_noisy=True, noisy_alert_count_range=(40, 70)),
            }

        all_configs.append(cfg)
        hard_negative_flags.append(True)

    # 4. Data quality / missing data / compound challenge scenarios
    for i in range(n_multi):
        sector = rng.choice(_SECTORS)
        scale = rng.choice(_SCALES)
        is_outage = rng.random() < 0.5
        cfg = {
            "name": f"Challenge-{sector[:3]}-{i:03d}",
            "sector": sector,
            "scale": scale,
            "primary_category": "missing data" if is_outage else "noisy data",
            "categories": ["missing data"] if is_outage else ["noisy data"],
            "fast_closure": False,
            "escalation_gap": False,
            "repeated_unresolved": False,
            "coverage_gap": False,
            "data_outage": is_outage,
            "noisy_data": not is_outage,
            "non_target_anomaly": rng.random() < 0.3,
            "self_reported_sla": round(rng.uniform(0.80, 0.95), 3),
            "desc": f"Challenge scenario {i}: data quality / noise",
        }
        if is_outage:
            cfg["missingness"] = MissingnessParameters(
                is_data_outage=True,
                data_outage_alert_count=rng.randint(3, 10),
            )
        else:
            cfg["noise"] = NoiseParameters(
                is_noisy=True,
                noisy_alert_count_range=(rng.randint(40, 60), rng.randint(65, 90)),
            )
        all_configs.append(cfg)
        hard_negative_flags.append(False)

    # Shuffle deterministically
    combined = list(zip(all_configs, hard_negative_flags))
    rng.shuffle(combined)
    all_configs, hard_negative_flags = zip(*combined)
    all_configs = list(all_configs)
    hard_negative_flags = list(hard_negative_flags)

    # Split into tuning / held-out
    n_held_out = int(len(all_configs) * held_out_ratio)
    tuning_configs = all_configs[n_held_out:]
    held_out_configs = all_configs[:n_held_out]

    return tuning_configs, held_out_configs, hard_negative_flags


# ---------------------------------------------------------------------------
# Evaluation engine
# ---------------------------------------------------------------------------

DETECTOR_TYPES = ["FAST_CLOSURE", "ESCALATION_GAP", "REPEATED_UNRESOLVED_ALERTS", "COVERAGE_GAP"]


def _build_ground_truth_map(scenarios: list[GroundTruthScenario]) -> dict[UUID, set[str]]:
    gt_map: dict[UUID, set[str]] = {}
    for s in scenarios:
        gt: set[str] = set()
        if s.has_fast_closure:
            gt.add("FAST_CLOSURE")
        if s.has_escalation_gap:
            gt.add("ESCALATION_GAP")
        if s.has_repeated_unresolved:
            gt.add("REPEATED_UNRESOLVED_ALERTS")
        if s.has_coverage_gap and not s.is_data_outage:
            gt.add("COVERAGE_GAP")
        gt_map[s.cse_id] = gt
    return gt_map


def _compute_confusion(
    scenarios: list[GroundTruthScenario],
    findings: list[Finding],
    priority_threshold: float = 0.0,
) -> tuple[int, int, int, int]:
    gt_map = _build_ground_truth_map(scenarios)
    detected_pairs: set[tuple[UUID, str]] = set()
    for f in findings:
        if f.priority_score >= priority_threshold:
            detected_pairs.add((f.cse_id, f.finding_type.value))

    tp, fp, tn, fn = 0, 0, 0, 0
    for s in scenarios:
        expected = gt_map.get(s.cse_id, set())
        for det in DETECTOR_TYPES:
            is_gt = det in expected
            is_det = (s.cse_id, det) in detected_pairs
            if is_gt and is_det:
                tp += 1
            elif not is_gt and is_det:
                fp += 1
            elif not is_gt and not is_det:
                tn += 1
            else:
                fn += 1
    return tp, fp, tn, fn


def _metrics_from_confusion(tp: int, fp: int, tn: int, fn: int) -> tuple[float, float, float, float]:
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    fpr = fp / max(fp + tn, 1)
    return precision, recall, f1, fpr


def _bootstrap_ci(
    scenarios: list[GroundTruthScenario],
    findings: list[Finding],
    n_bootstrap: int = 200,
    confidence: float = 0.95,
    rng_seed: int = 42,
) -> tuple[ConfidenceInterval, ConfidenceInterval, ConfidenceInterval, ConfidenceInterval]:
    """Bootstrap confidence intervals for precision, recall, F1, FPR."""
    rng = random.Random(rng_seed)
    precisions, recalls, f1s, fprs = [], [], [], []

    for _ in range(n_bootstrap):
        sample = rng.choices(scenarios, k=len(scenarios))
        # Filter findings to only those related to sampled scenarios
        sampled_cse_ids = {s.cse_id for s in sample}
        sampled_findings = [f for f in findings if f.cse_id in sampled_cse_ids]
        tp, fp, tn, fn = _compute_confusion(sample, sampled_findings)
        p, r, f1, fpr = _metrics_from_confusion(tp, fp, tn, fn)
        precisions.append(p)
        recalls.append(r)
        f1s.append(f1)
        fprs.append(fpr)

    alpha = (1 - confidence) / 2

    def _ci(values: list[float]) -> ConfidenceInterval:
        values.sort()
        n = len(values)
        lo_idx = max(0, int(n * alpha))
        hi_idx = min(n - 1, int(n * (1 - alpha)))
        return ConfidenceInterval(
            mean=round(statistics.mean(values), 4),
            lower=round(values[lo_idx], 4),
            upper=round(values[hi_idx], 4),
            std=round(statistics.stdev(values) if len(values) > 1 else 0.0, 4),
            n_bootstrap=n_bootstrap,
        )

    return _ci(precisions), _ci(recalls), _ci(f1s), _ci(fprs)


def _compute_ranking_metrics(
    scenarios: list[GroundTruthScenario],
    findings: list[Finding],
) -> RankingMetrics:
    gt_map = _build_ground_truth_map(scenarios)
    total_tp = sum(len(v) for v in gt_map.values())

    sorted_findings = sorted(findings, key=lambda f: f.priority_score, reverse=True)
    seen: set[tuple[UUID, str]] = set()
    cumulative_tp = 0

    def _recall_at(k: int) -> float:
        ct = 0
        s: set[tuple[UUID, str]] = set()
        for f in sorted_findings[:k]:
            pair = (f.cse_id, f.finding_type.value)
            if pair not in s:
                s.add(pair)
                if f.cse_id in gt_map and f.finding_type.value in gt_map[f.cse_id]:
                    ct += 1
        return ct / max(total_tp, 1)

    return RankingMetrics(
        recall_at_1=round(_recall_at(1), 4),
        recall_at_3=round(_recall_at(3), 4),
        recall_at_5=round(_recall_at(5), 4),
        total_findings=len(sorted_findings),
        total_true_positives=total_tp,
    )


def _threshold_sensitivity(
    scenarios: list[GroundTruthScenario],
    findings: list[Finding],
) -> list[ThresholdSensitivityPoint]:
    """Compute metrics at different priority score thresholds."""
    thresholds = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    points = []
    for t in thresholds:
        tp, fp, tn, fn = _compute_confusion(scenarios, findings, priority_threshold=t)
        p, r, f1, fpr = _metrics_from_confusion(tp, fp, tn, fn)
        points.append(ThresholdSensitivityPoint(
            threshold=t, precision=round(p, 4), recall=round(r, 4),
            f1=round(f1, 4), fpr=round(fpr, 4), tp=tp, fp=fp, tn=tn, fn=fn,
        ))
    return points


def _run_pipeline_for_scenarios(
    configs: list[dict[str, Any]],
    seed: int,
    ruleset: AnalyticalRuleset,
) -> tuple[list[GroundTruthScenario], list[Finding], dict[str, list[dict[str, Any]]]]:
    """
    Runs the full analytical pipeline on a list of scenario configs.
    Returns scenarios, findings, and the combined raw bundle.
    """
    rng = random.Random(seed)
    now = datetime.now(timezone.utc)
    base_time = now - timedelta(days=90)
    ver_id = uuid4()

    # Merge all scenario bundles into a combined raw bundle
    combined_bundle: dict[str, list[dict[str, Any]]] = {
        "cse": [], "reporting_periods": [], "assets": [], "alerts": [],
        "investigations": [], "cases": [], "escalations": [], "actions": [],
        "closures": [], "coverage_observations": [],
    }
    all_scenarios: list[GroundTruthScenario] = []

    for cfg in configs:
        scenario_bundle, gt_scenario = generate_parameterized_scenario(
            cfg=cfg, rng=rng, base_time=base_time, now=now,
        )
        for key in combined_bundle:
            combined_bundle[key].extend(scenario_bundle.get(key, []))
        all_scenarios.append(gt_scenario)

    pipeline_res = run_full_analytical_pipeline(
        raw_bundle=combined_bundle,
        ruleset=ruleset,
        dataset_version_id=ver_id,
    )
    return all_scenarios, pipeline_res.findings, combined_bundle


# ---------------------------------------------------------------------------
# Main validation runner
# ---------------------------------------------------------------------------

class RobustValidationEngine:
    """
    Executes a statistically meaningful validation protocol with 200+ scenarios,
    hard negatives, bootstrap confidence intervals, and sensitivity analysis.
    """

    def __init__(
        self,
        n_scenarios: int = 240,
        held_out_ratio: float = 0.3,
        hard_negative_ratio: float = 0.15,
        n_bootstrap: int = 200,
        ruleset: Optional[AnalyticalRuleset] = None,
    ):
        self.n_scenarios = n_scenarios
        self.held_out_ratio = held_out_ratio
        self.hard_negative_ratio = hard_negative_ratio
        self.n_bootstrap = n_bootstrap
        self.ruleset = ruleset or DEFAULT_AUTHORITATIVE_RULESET_V1

    def run(self, seed: int = 42) -> RobustValidationResult:
        """
        Execute the full robust validation protocol.

        Returns a RobustValidationResult with all metrics, confidence intervals,
        and sensitivity analyses.
        """
        rng = random.Random(seed)

        # 1. Generate scenario configurations
        tuning_cfgs, held_out_cfgs, hard_neg_flags = _generate_scenario_configs(
            rng=rng,
            n_total=self.n_scenarios,
            held_out_ratio=self.held_out_ratio,
            hard_negative_ratio=self.hard_negative_ratio,
        )

        # 2. Run pipeline on tuning set
        tuning_scenarios, tuning_findings, _ = _run_pipeline_for_scenarios(
            tuning_cfgs, seed=seed + 1000, ruleset=self.ruleset,
        )

        # 3. Run pipeline on held-out set (different seed — no information leakage)
        held_out_scenarios, held_out_findings, held_out_bundle = _run_pipeline_for_scenarios(
            held_out_cfgs, seed=seed + 2000, ruleset=self.ruleset,
        )

        # 4. Compute metrics
        def _build_split_metrics(
            scenarios: list[GroundTruthScenario],
            findings: list[Finding],
        ) -> RobustConfusionMatrix:
            tp, fp, tn, fn = _compute_confusion(scenarios, findings)
            p, r, f1, fpr = _metrics_from_confusion(tp, fp, tn, fn)
            p_ci, r_ci, f1_ci, fpr_ci = _bootstrap_ci(
                scenarios, findings, n_bootstrap=self.n_bootstrap, rng_seed=seed,
            )
            return RobustConfusionMatrix(
                tp=tp, fp=fp, tn=tn, fn=fn,
                precision=round(p, 4), recall=round(r, 4),
                f1_score=round(f1, 4), fpr=round(fpr, 4),
                precision_ci=p_ci, recall_ci=r_ci,
                f1_ci=f1_ci, fpr_ci=fpr_ci,
            )

        tuning_metrics = _build_split_metrics(tuning_scenarios, tuning_findings)
        held_out_metrics = _build_split_metrics(held_out_scenarios, held_out_findings)

        # 5. Ranking metrics
        tuning_ranking = _compute_ranking_metrics(tuning_scenarios, tuning_findings)
        held_out_ranking = _compute_ranking_metrics(held_out_scenarios, held_out_findings)

        # 6. Threshold sensitivity on held-out
        threshold_sens = _threshold_sensitivity(held_out_scenarios, held_out_findings)

        # 7. Hard negative analysis
        hard_neg_scenarios_in_held_out = [
            s for s, is_hn in zip(
                tuning_scenarios + held_out_scenarios,
                hard_neg_flags[:len(tuning_scenarios)] + hard_neg_flags[len(tuning_scenarios):],
            ) if is_hn
        ]
        all_findings = tuning_findings + held_out_findings
        hn_fp = 0
        hn_tn = 0
        if hard_neg_scenarios_in_held_out:
            tp_hn, fp_hn, tn_hn, fn_hn = _compute_confusion(
                hard_neg_scenarios_in_held_out, all_findings,
            )
            hn_fp = fp_hn
            hn_tn = tn_hn

        # 8. Weight sensitivity (perturb each fusion weight ±20%)
        weight_sens: list[WeightSensitivityPoint] = []
        base_tp, base_fp, base_tn, base_fn = _compute_confusion(
            held_out_scenarios, held_out_findings,
        )
        _, _, base_f1, _ = _metrics_from_confusion(base_tp, base_fp, base_tn, base_fn)

        from dataclasses import replace

        weights_to_perturb = [
            "signal_strength_weight",
            "peer_deviation_weight",
            "persistence_weight",
            "asset_criticality_weight",
            "data_uncertainty_weight",
        ]

        for w_name in weights_to_perturb:
            orig_val = getattr(self.ruleset.fusion_weights, w_name)
            for multiplier in [0.8, 1.2]:
                pert_val = orig_val * multiplier
                new_fw = replace(self.ruleset.fusion_weights, **{w_name: pert_val})
                new_ruleset = replace(self.ruleset, fusion_weights=new_fw)

                # Re-run pipeline on the same bundle
                pert_res = run_full_analytical_pipeline(
                    raw_bundle=held_out_bundle,
                    ruleset=new_ruleset,
                    dataset_version_id=uuid4(),
                )

                ptp, pfp, ptn, pfn = _compute_confusion(held_out_scenarios, pert_res.findings)
                p_prec, p_rec, p_f1, _ = _metrics_from_confusion(ptp, pfp, ptn, pfn)

                weight_sens.append(WeightSensitivityPoint(
                    weight_name=w_name,
                    original_value=orig_val,
                    perturbed_value=pert_val,
                    precision=p_prec,
                    recall=p_rec,
                    f1=p_f1,
                    delta_f1=p_f1 - base_f1,
                ))

        result = RobustValidationResult(
            total_scenarios=len(tuning_cfgs) + len(held_out_cfgs),
            tuning_scenarios=len(tuning_cfgs),
            held_out_scenarios=len(held_out_cfgs),
            held_out_ratio=round(len(held_out_cfgs) / max(len(tuning_cfgs) + len(held_out_cfgs), 1), 4),
            tuning_metrics=tuning_metrics,
            held_out_metrics=held_out_metrics,
            tuning_ranking=tuning_ranking,
            held_out_ranking=held_out_ranking,
            threshold_sensitivity=threshold_sens,
            weight_sensitivity=weight_sens,
            hard_negative_count=sum(hard_neg_flags),
            hard_negative_fp_count=hn_fp,
            hard_negative_tn_count=hn_tn,
        )

        return result
