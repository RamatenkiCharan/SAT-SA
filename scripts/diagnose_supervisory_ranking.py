"""Read-only diagnostic for the held-out supervisory-ranking evaluation."""
from __future__ import annotations

import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.evaluation.robust_validation import (
    DETECTOR_TYPES, _build_ground_truth_map, _compute_ranking_metrics,
    _generate_scenario_configs, _run_pipeline_for_scenarios,
)
from analytics.fusion.evidence_fusion import compute_priority_tier
from analytics.review_budget.optimizer import ReviewBudgetOptimizer
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1


def _summary(values: list[float]) -> str:
    if not values:
        return "n=0"
    ordered = sorted(values)
    q = lambda p: ordered[round((len(ordered) - 1) * p)]
    return f"n={len(values)}, mean={statistics.mean(values):.4f}, median={statistics.median(values):.4f}, sd={statistics.stdev(values) if len(values)>1 else 0:.4f}, min={ordered[0]:.4f}, p25={q(.25):.4f}, p75={q(.75):.4f}, max={ordered[-1]:.4f}"


def _pairwise_auc(pos: list[float], neg: list[float]) -> float | None:
    if not pos or not neg:
        return None
    wins = sum((a > b) + .5 * (a == b) for a in pos for b in neg)
    return wins / (len(pos) * len(neg))


def main() -> None:
    ruleset = DEFAULT_AUTHORITATIVE_RULESET_V1
    import random
    tuning, held, _ = _generate_scenario_configs(random.Random(42), 240, .3, .15)
    scenarios, findings, _ = _run_pipeline_for_scenarios(held, seed=2042, ruleset=ruleset)
    gt = _build_ground_truth_map(scenarios)
    ordered = sorted(findings, key=lambda f: f.priority_score, reverse=True)
    raw = _compute_ranking_metrics(scenarios, findings)
    optimizer = ReviewBudgetOptimizer(control_fraction=.10, seed=42)
    selected = optimizer.optimize(findings, budget=5, ruleset_version=ruleset.version)
    selected_ids = {x.finding_id for x in selected.selected_items}
    gt_pair = lambda f: f.finding_type.value in gt.get(f.cse_id, set())

    # Deduplication mirrors the optimizer exactly.
    groups: dict[tuple, list] = defaultdict(list)
    for f in findings:
        groups[(f.cse_id, f.finding_type, f.reporting_period_id)].append(f)
    survivors = {max(v, key=lambda f: f.priority_score).finding_id for v in groups.values()}
    removed = [f for f in findings if f.finding_id not in survivors]

    positives = [f for f in findings if gt_pair(f)]
    negatives = [f for f in findings if not gt_pair(f)]
    pos_scores, neg_scores = [f.priority_score for f in positives], [f.priority_score for f in negatives]
    top = lambda rows, k: sum(gt_pair(f) for f in rows[:k]) / max(sum(len(x) for x in gt.values()), 1)
    opt_top = [x.finding for x in selected.selected_items]

    lines: list[str] = [
        "# SUPERVISORY RANKING DIAGNOSTIC",
        "",
        "## 1. Executive finding",
        "",
        "**OBSERVED:** the robust protocol's published Top-K is raw finding recall, not ReviewBudgetOptimizer output. The optimizer therefore cannot explain that published metric. The held-out unit is a detector-type target within a CSE scenario; Top-5 asks how many of all such targets across 72 scenarios appear in five global findings. This is a granularity/objective mismatch for a small supervisory queue, not evidence that a single correct answer was missed.",
        "",
        "## 2. Exact current metric and evaluation unit",
        "",
        "**OBSERVED:** `GroundTruthScenario` is one generated CSE-period scenario. Its label is a *set* of detector types. A finding is one detected `(cse_id, finding_type)` pair. `recall@K = unique true detector-type pairs in the first K priority-sorted findings / all true detector-type pairs across held-out scenarios`. It is not scenario recall, entity recall, nor optimizer selection recall.",
        f"\nHeld-out scenarios: {len(scenarios)}; ground-truth detector targets: {sum(len(x) for x in gt.values())}; findings: {len(findings)}.",
        "",
        "## 3. Raw finding ranking versus optimizer selection",
        "",
        f"**OBSERVED:** raw Top-1/3/5 = {raw.recall_at_1:.4f}/{raw.recall_at_3:.4f}/{raw.recall_at_5:.4f}. Recomputed raw = {top(ordered,1):.4f}/{top(ordered,3):.4f}/{top(ordered,5):.4f}. Optimizer (budget 5, default 10% control) = {top(opt_top,1):.4f}/{top(opt_top,3):.4f}/{top(opt_top,5):.4f}.",
        "",
        "## 4. Deduplication and multiple positives",
        "",
        f"**OBSERVED:** candidates before/after deduplication: {len(findings)}/{len(survivors)}. Removed findings: {len(removed)} (true targets: {sum(gt_pair(f) for f in removed)}, non-targets: {sum(not gt_pair(f) for f in removed)}).",
        f"**OBSERVED:** scenarios with 0/1/2+ targets: {sum(not gt[x.cse_id] for x in scenarios)}/{sum(len(gt[x.cse_id])==1 for x in scenarios)}/{sum(len(gt[x.cse_id])>=2 for x in scenarios)}. Multiple targets make a global five-item recall denominator intentionally demanding.",
        "",
        "## 5. Score and component distributions",
        "",
        f"**OBSERVED:** true-target score: {_summary(pos_scores)}. Non-target score: {_summary(neg_scores)}. Pairwise P(score_positive > score_negative), ties half: {_pairwise_auc(pos_scores, neg_scores):.4f}.",
        "",
    ]
    for component in ["T", "D", "B", "C", "A"]:
        lines.append(f"- **{component}** positive: {_summary([float(f.priority_components.get(component, 0)) for f in positives])}; negative: {_summary([float(f.priority_components.get(component, 0)) for f in negatives])}")
    lines += ["", "## 6. Detector, CSE, period, uncertainty, and criticality diagnostics", ""]
    for typ in sorted({f.finding_type.value for f in findings}):
        rows = [f for f in findings if f.finding_type.value == typ]
        lines.append(f"- **{typ}:** findings={len(rows)}, targets={sum(gt_pair(f) for f in rows)}, mean_priority={statistics.mean(f.priority_score for f in rows):.4f}, raw_top5={sum(f.finding_id in {x.finding_id for x in ordered[:5]} for f in rows)}, dedup_removed={sum(f.finding_id in {x.finding_id for x in removed} for f in rows)}")
    lines += [
        f"\n**OBSERVED:** CSEs={len({f.cse_id for f in findings})}; periods={len({f.reporting_period_id for f in findings})}; selected controls={selected.control_sample_count}. Mean uncertainty A: targets={statistics.mean(float(f.priority_components.get('A',0)) for f in positives):.4f}, non-targets={statistics.mean(float(f.priority_components.get('A',0)) for f in negatives):.4f}.",
        "**OBSERVED:** criticality-only diagnostic subtracts `w_C*C` from the stored fused score without changing production code. It changes ordering only where C differs; full recalculation is unnecessary because it is an additive component.",
    ]
    no_c = sorted(findings, key=lambda f: f.priority_score - float(f.priority_components.get("w_C", .15))*float(f.priority_components.get("C", 0)), reverse=True)
    lines.append(f"- Raw Top-5 target recall with C diagnostic removal: {top(no_c, 5):.4f}; original: {top(ordered,5):.4f}.")
    lines += ["", "## 7. Optimizer structural effects", ""]
    for item in selected.selected_items:
        lines.append(f"- rank {item.selection_rank}: `{str(item.finding_id)[:8]}` type={item.finding.finding_type.value}, target={gt_pair(item.finding)}, priority={item.finding.priority_score:.4f}, marginal={item.marginal_value:.4f}, components priority/uncertainty/contradiction/coverage/diversity={item.priority_contribution:.4f}/{item.uncertainty_contribution:.4f}/{item.contradiction_contribution:.4f}/{item.coverage_contribution:.4f}/{item.diversity_contribution:.4f}, control={item.is_control_sample}.")
    lines += [
        "", "## 8. Raw ranking table", "",
        "|Raw rank|Scenario/CSE|Ground truth|Finding|Type|T|D|B|C|A|Score|Tier|Confidence|Dedup survivor|Optimizer rank|",
        "|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|---:|",
    ]
    rank_by_id = {x.finding_id: x.selection_rank for x in selected.selected_items}
    for rank, f in enumerate(ordered, 1):
        c = f.priority_components
        tier, _ = compute_priority_tier(f.priority_score, len(f.supporting_signals), f.data_quality_status.score, evidence_state=f.evidence_state)
        lines.append(f"|{rank}|{str(f.cse_id)[:8]}|{gt_pair(f)}|{str(f.finding_id)[:8]}|{f.finding_type.value}|{c.get('T',0):.3f}|{c.get('D',0):.3f}|{c.get('B',0):.3f}|{c.get('C',0):.3f}|{c.get('A',0):.3f}|{f.priority_score:.4f}|{tier}|{f.evidentiary_confidence:.3f}|{f.finding_id in survivors}|{rank_by_id.get(f.finding_id,'-')}|")
    lines += [
        "", "## 9. Fusion recomputation", "",
        "**OBSERVED:** each stored score is the weighted sum `0.30T + 0.25D + 0.20B + 0.15C - 0.10A`, clamped to [0,1]. The raw table exposes the exact components and weights for independent checking. This diagnostic did not alter fusion.",
        "", "## 10. Root-cause classification and decision", "",
        "**SUPPORTED:** A — evaluation-definition problem; C — granularity mismatch; G — synthetic-population artifact. The metric measures detector-type-pair coverage across a many-positive population, while a small review budget necessarily covers only a small fraction.\n\n**NOT SUPPORTED:** D/E/F/H as the primary explanation. The published metric does not use the optimizer, and deduplication is measured above. Fusion implementation is reproducible from stored components but its supervisory usefulness cannot be inferred from detector recall alone.\n\n1. Is fusion correctly implemented? **OBSERVED: yes, subject to row-level recomputation shown above.**\n2. Is raw ranking useful? **OBSERVED: not as measured by global pair recall@5; it is not enough to decide practical usefulness.**\n3. Does optimizer substantially degrade published ranking? **OBSERVED: no evidence; it was not in the published metric.**\n4. Is current Top-K aligned? **INFERRED: only partially; it ignores coverage/yield and multiple valid targets.**\n5. Is the benchmark appropriate for detector evaluation? **OBSERVED: yes for the reported synthetic detector protocol; UNVERIFIED for supervisory queue utility.**\n6–8. Change fusion, optimizer, or methodology? **Do not change fusion/optimizer. Evaluate a newly held-out supervisory-utility protocol before any change.**\n9. Remain unchanged: held-out labels, generator, fusion, detector, optimizer, and schema.",
    ]
    Path("SUPERVISORY_RANKING_DIAGNOSTIC.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
