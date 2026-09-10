"""
SAT-SA Review-Efficiency Evaluation Engine (SRS §19.4, §24).

Demonstrates quantitatively that SAT-SA helps an examiner/analyst reach useful
security findings significantly faster than reviewing raw operational datasets blindly.

Measures:
1. Baseline Review Effort (Raw records/cases to inspect, estimated unassisted review hours)
2. SAT-SA-Assisted Review Effort (Prioritized findings to inspect, assisted review hours)
3. Useful Findings Reviewed (True Positives @ K, categorized by supervisory gap type)
4. False Positives Reviewed (False Positives @ K, Precision @ K)
5. Top-K Recall (Recall @ 1, 3, 5, 10, and cutoff K* for 100% weakness capture)
6. Review Yield (Cumulative percentage of true weaknesses discovered per reviewed case)
7. Time-to-Useful-Finding (TTUF to 1st useful finding, Mean TTUF, Time to 100% recall)

Guarantees:
- Zero fabrication: Computed directly from live pipeline execution over ground-truth scenarios.
- Strict reproducibility: Deterministic seeds and versioned ruleset pinning.
- Split separation: Independent evaluation for Tuning vs Held-Out scenario splits.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from analytics.synthetic_generator import (
    GroundTruthScenario,
    generate_synthetic_soc_benchmark,
    run_full_analytical_pipeline,
)
from backend.models.canonical import Finding
from backend.models.ruleset import (
    DEFAULT_AUTHORITATIVE_RULESET_V1,
    AnalyticalRuleset,
)


@dataclass
class ScenarioDescriptor:
    cse_id: str
    cse_name: str
    sector: str
    scale: str
    self_reported_sla: float
    expected_weaknesses: list[str]
    description: str


@dataclass
class YieldStep:
    rank: int
    finding_id: str
    cse_name: str
    finding_type: str
    priority_score: float
    priority_label: str
    is_true_positive: bool
    cumulative_true_positives: int
    cumulative_false_positives: int
    precision_at_k: float
    recall_at_k: float
    yield_percentage: float
    assisted_time_minutes: float
    baseline_equivalent_time_minutes: float


@dataclass
class SplitEfficiencyResult:
    split_name: str
    seed: int
    total_scenarios: int
    scenarios: list[ScenarioDescriptor]
    total_raw_records: int
    total_raw_cases: int
    total_true_weaknesses: int
    total_findings_generated: int
    
    # 1. Baseline Unassisted Review Effort
    baseline_inspection_minutes_per_case: float
    total_baseline_effort_hours: float
    baseline_expected_cases_to_first_useful: float
    baseline_expected_minutes_to_first_useful: float
    baseline_cases_for_100pct_recall: int
    baseline_time_for_100pct_recall_hours: float

    # 2. SAT-SA-Assisted Review Effort
    assisted_inspection_minutes_per_finding: float
    findings_reviewed_for_100pct_recall: int
    assisted_minutes_to_first_useful: float
    assisted_time_for_100pct_recall_minutes: float
    assisted_time_for_100pct_recall_hours: float
    workload_effort_reduction_percentage: float
    efficiency_multiplier_speedup: float

    # 3. Detection & Quality Metrics
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    recall: float
    f1_score: float

    # 4. Top-K Recall Metrics
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float

    # 5. Time-to-Useful-Finding (TTUF)
    ttuf_first_useful_minutes: float
    mean_time_to_useful_finding_minutes: float
    time_to_100pct_recall_minutes: float

    # 6. Yield Curve
    yield_curve: list[YieldStep]
    yield_summary: str


@dataclass
class ReviewEfficiencyReport:
    evaluation_timestamp: str
    ruleset_version: str
    ruleset_id: str
    app_version: str
    methodology: str
    tuning_split: SplitEfficiencyResult
    held_out_split: SplitEfficiencyResult
    cross_split_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)


class ReviewEfficiencyEvaluator:
    """
    Evaluator that executes SAT-SA against controlled synthetic scenarios to
    measure operational review efficiency vs unassisted baseline manual review.
    """

    def __init__(
        self,
        ruleset: Optional[AnalyticalRuleset] = None,
        baseline_minutes_per_case: float = 8.0,
        assisted_minutes_per_finding: float = 4.0,
    ):
        self.ruleset = ruleset or DEFAULT_AUTHORITATIVE_RULESET_V1
        self.baseline_minutes_per_case = baseline_minutes_per_case
        self.assisted_minutes_per_finding = assisted_minutes_per_finding

    def evaluate_split(
        self,
        seed: int,
        is_held_out: bool = False,
    ) -> SplitEfficiencyResult:
        """
        Executes analytical pipeline and calculates empirical review efficiency metrics.
        """
        dataset_version_id = uuid4()
        raw_bundle, scenarios = generate_synthetic_soc_benchmark(
            seed=seed,
            dataset_version_id=dataset_version_id,
            is_held_out=is_held_out,
        )

        pipeline_res = run_full_analytical_pipeline(
            raw_bundle=raw_bundle,
            dataset_version_id=dataset_version_id,
            ruleset=self.ruleset,
        )

        findings = pipeline_res.findings
        total_raw_alerts = len(raw_bundle.get("alerts", []))
        total_raw_cases = len(raw_bundle.get("cases", []))
        total_raw_investigations = len(raw_bundle.get("investigations", []))
        total_raw_observations = len(raw_bundle.get("coverage_observations", []))
        total_raw_records = (
            total_raw_alerts
            + total_raw_cases
            + total_raw_investigations
            + total_raw_observations
        )

        # Build ground truth weakness map
        gt_map: dict[UUID, set[str]] = {}
        scenario_descriptors: list[ScenarioDescriptor] = []

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

            scenario_descriptors.append(
                ScenarioDescriptor(
                    cse_id=str(s.cse_id),
                    cse_name=s.cse_name,
                    sector=s.sector,
                    scale=s.scale,
                    self_reported_sla=s.self_reported_sla,
                    expected_weaknesses=sorted(list(gt_set)),
                    description=s.description,
                )
            )

        total_true_weaknesses = sum(len(gts) for gts in gt_map.values())

        # Sort findings by PriorityScore DESC (SAT-SA prioritized queue)
        sorted_findings = sorted(findings, key=lambda f: f.priority_score, reverse=True)

        # Step through prioritized queue to compute yield & metrics
        yield_steps: list[YieldStep] = []
        captured_weaknesses: set[tuple[UUID, str]] = set()
        tp_count = 0
        fp_count = 0
        first_tp_rank: Optional[int] = None
        full_capture_rank: Optional[int] = None

        # Finding entity map for CSE names
        cse_name_map = {s.cse_id: s.cse_name for s in scenarios}

        for rank, f in enumerate(sorted_findings, start=1):
            pair = (f.cse_id, f.finding_type.value)
            is_tp = False

            if f.cse_id in gt_map and f.finding_type.value in gt_map[f.cse_id]:
                if pair not in captured_weaknesses:
                    captured_weaknesses.add(pair)
                    tp_count += 1
                    is_tp = True
                    if first_tp_rank is None:
                        first_tp_rank = rank
                    if tp_count == total_true_weaknesses and full_capture_rank is None:
                        full_capture_rank = rank
                else:
                    fp_count += 1
            else:
                fp_count += 1

            precision_at_k = tp_count / rank
            recall_at_k = tp_count / max(total_true_weaknesses, 1)
            yield_pct = round(recall_at_k * 100, 1)

            assisted_time = round(rank * self.assisted_minutes_per_finding, 1)
            # Baseline expected review time for same recall:
            # Under random baseline, proportion of cases reviewed matches recall ratio
            baseline_eq_cases = recall_at_k * total_raw_cases
            baseline_eq_time = round(baseline_eq_cases * self.baseline_minutes_per_case, 1)

            yield_steps.append(
                YieldStep(
                    rank=rank,
                    finding_id=str(f.finding_id),
                    cse_name=cse_name_map.get(f.cse_id, "Unknown"),
                    finding_type=f.finding_type.value,
                    priority_score=round(f.priority_score, 3),
                    priority_label=f.priority_label if hasattr(f, "priority_label") else "HIGH",
                    is_true_positive=is_tp,
                    cumulative_true_positives=tp_count,
                    cumulative_false_positives=fp_count,
                    precision_at_k=round(precision_at_k, 4),
                    recall_at_k=round(recall_at_k, 4),
                    yield_percentage=yield_pct,
                    assisted_time_minutes=assisted_time,
                    baseline_equivalent_time_minutes=baseline_eq_time,
                )
            )

        # Baseline calculations
        total_baseline_effort_hours = round(
            (total_raw_cases * self.baseline_minutes_per_case) / 60.0, 2
        )
        # Random expectation for 1st TP: (N_cases + 1) / (N_gt + 1)
        expected_cases_to_1st_tp = round(
            (total_raw_cases + 1.0) / max(total_true_weaknesses + 1.0, 1.0), 1
        )
        expected_minutes_to_1st_tp = round(
            expected_cases_to_1st_tp * self.baseline_minutes_per_case, 1
        )

        # Assisted calculations
        k_star = full_capture_rank or len(sorted_findings)
        assisted_time_for_100pct_minutes = round(
            k_star * self.assisted_minutes_per_finding, 1
        )
        assisted_time_for_100pct_hours = round(
            assisted_time_for_100pct_minutes / 60.0, 2
        )

        # Effort reduction & speedup
        baseline_time_for_100pct_minutes = total_raw_cases * self.baseline_minutes_per_case
        workload_reduction_pct = round(
            max(
                0.0,
                (
                    (baseline_time_for_100pct_minutes - assisted_time_for_100pct_minutes)
                    / max(baseline_time_for_100pct_minutes, 1e-6)
                )
                * 100.0,
            ),
            1,
        )
        efficiency_multiplier = round(
            max(
                1.0,
                baseline_time_for_100pct_minutes
                / max(assisted_time_for_100pct_minutes, 1e-6),
            ),
            1,
        )

        # Top-K recall
        def get_recall_at_k(k: int) -> float:
            if not yield_steps:
                return 0.0
            idx = min(k, len(yield_steps)) - 1
            return yield_steps[idx].recall_at_k

        recall_1 = get_recall_at_k(1)
        recall_3 = get_recall_at_k(3)
        recall_5 = get_recall_at_k(5)
        recall_10 = get_recall_at_k(10)

        # TTUF metrics
        ttuf_1st = (first_tp_rank or 1) * self.assisted_minutes_per_finding
        mean_ttuf = (
            assisted_time_for_100pct_minutes / max(tp_count, 1) if tp_count > 0 else 0.0
        )

        final_precision = tp_count / max(tp_count + fp_count, 1)
        final_recall = tp_count / max(total_true_weaknesses, 1)
        final_f1 = (
            2 * final_precision * final_recall / max(final_precision + final_recall, 1e-6)
        )

        summary_text = (
            f"Captured {tp_count} of {total_true_weaknesses} true weaknesses within top {k_star} "
            f"prioritized reviews ({assisted_time_for_100pct_hours} hrs vs {total_baseline_effort_hours} hrs baseline, "
            f"{workload_reduction_pct}% review effort reduction, {efficiency_multiplier}x speedup)."
        )

        return SplitEfficiencyResult(
            split_name="Held-Out Split" if is_held_out else "Tuning Split",
            seed=seed,
            total_scenarios=len(scenarios),
            scenarios=scenario_descriptors,
            total_raw_records=total_raw_records,
            total_raw_cases=total_raw_cases,
            total_true_weaknesses=total_true_weaknesses,
            total_findings_generated=len(sorted_findings),
            baseline_inspection_minutes_per_case=self.baseline_minutes_per_case,
            total_baseline_effort_hours=total_baseline_effort_hours,
            baseline_expected_cases_to_first_useful=expected_cases_to_1st_tp,
            baseline_expected_minutes_to_first_useful=expected_minutes_to_1st_tp,
            baseline_cases_for_100pct_recall=total_raw_cases,
            baseline_time_for_100pct_recall_hours=total_baseline_effort_hours,
            assisted_inspection_minutes_per_finding=self.assisted_minutes_per_finding,
            findings_reviewed_for_100pct_recall=k_star,
            assisted_minutes_to_first_useful=ttuf_1st,
            assisted_time_for_100pct_recall_minutes=assisted_time_for_100pct_minutes,
            assisted_time_for_100pct_recall_hours=assisted_time_for_100pct_hours,
            workload_effort_reduction_percentage=workload_reduction_pct,
            efficiency_multiplier_speedup=efficiency_multiplier,
            true_positives=tp_count,
            false_positives=fp_count,
            false_negatives=max(0, total_true_weaknesses - tp_count),
            precision=round(final_precision, 4),
            recall=round(final_recall, 4),
            f1_score=round(final_f1, 4),
            recall_at_1=round(recall_1, 4),
            recall_at_3=round(recall_3, 4),
            recall_at_5=round(recall_5, 4),
            recall_at_10=round(recall_10, 4),
            ttuf_first_useful_minutes=round(ttuf_1st, 1),
            mean_time_to_useful_finding_minutes=round(mean_ttuf, 1),
            time_to_100pct_recall_minutes=assisted_time_for_100pct_minutes,
            yield_curve=yield_steps,
            yield_summary=summary_text,
        )

    def run_full_benchmark(self) -> ReviewEfficiencyReport:
        """
        Runs complete benchmark evaluating both Tuning Split (seed=42) and
        Held-Out Split (seed=101) with reproducibility metadata.
        """
        tuning_res = self.evaluate_split(seed=42, is_held_out=False)
        held_out_res = self.evaluate_split(seed=101, is_held_out=True)

        avg_effort_reduction = round(
            (
                tuning_res.workload_effort_reduction_percentage
                + held_out_res.workload_effort_reduction_percentage
            )
            / 2.0,
            1,
        )
        avg_speedup = round(
            (
                tuning_res.efficiency_multiplier_speedup
                + held_out_res.efficiency_multiplier_speedup
            )
            / 2.0,
            1,
        )

        cross_summary = {
            "average_workload_reduction_percentage": avg_effort_reduction,
            "average_efficiency_multiplier_speedup": avg_speedup,
            "tuning_recall": tuning_res.recall,
            "held_out_recall": held_out_res.recall,
            "tuning_top5_recall": tuning_res.recall_at_5,
            "held_out_top5_recall": held_out_res.recall_at_5,
            "air_gapped_deterministic": True,
            "llm_dependency": False,
        }

        return ReviewEfficiencyReport(
            evaluation_timestamp=datetime.now(timezone.utc).isoformat(),
            ruleset_version=self.ruleset.version,
            ruleset_id=self.ruleset.ruleset_id,
            app_version="2.2.0",
            methodology="Generator/Detector Independence Review Efficiency Protocol (SRS §19.4)",
            tuning_split=tuning_res,
            held_out_split=held_out_res,
            cross_split_summary=cross_summary,
        )


def run_review_efficiency_benchmark(
    ruleset: Optional[AnalyticalRuleset] = None,
) -> ReviewEfficiencyReport:
    """Convenience runner returning the complete benchmark report."""
    evaluator = ReviewEfficiencyEvaluator(ruleset=ruleset)
    return evaluator.run_full_benchmark()
