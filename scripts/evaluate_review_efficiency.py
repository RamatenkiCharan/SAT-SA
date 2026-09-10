#!/usr/bin/env python
"""
Reproducible CLI Evaluation Script for SAT-SA Review Efficiency Benchmark.

Usage:
  python scripts/evaluate_review_efficiency.py
  python scripts/evaluate_review_efficiency.py --output results/review_efficiency_benchmark.json
  python scripts/evaluate_review_efficiency.py --markdown results/review_efficiency_report.md
  python scripts/evaluate_review_efficiency.py --ruleset V1_AUTHORITATIVE
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add workspace root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from analytics.evaluation.review_efficiency import (
    ReviewEfficiencyEvaluator,
    run_review_efficiency_benchmark,
)
from backend.models.ruleset import (
    DEFAULT_AUTHORITATIVE_RULESET_V1,
    AnalyticalRuleset,
)


def format_markdown_report(report_dict: dict) -> str:
    """Generates a standalone Markdown summary report."""
    t_res = report_dict["tuning_split"]
    h_res = report_dict["held_out_split"]
    cross = report_dict["cross_split_summary"]

    md = []
    md.append("# SAT-SA Review-Efficiency Benchmark & Workload Reduction Report")
    md.append("")
    md.append(f"**Evaluation Timestamp:** `{report_dict['evaluation_timestamp']}`  ")
    md.append(f"**Ruleset Version:** `{report_dict['ruleset_version']}` (`{report_dict['ruleset_id']}`)  ")
    md.append(f"**Application Version:** `v{report_dict['app_version']}`  ")
    md.append(f"**Methodology:** {report_dict['methodology']}  ")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 1. Executive Summary & Efficiency Multiplier")
    md.append("")
    md.append("| Metric | Unassisted Baseline | SAT-SA Assisted (Tuning) | SAT-SA Assisted (Held-Out) |")
    md.append("| :--- | :---: | :---: | :---: |")
    md.append(f"| **Review Target to Inspect** | `{t_res['total_raw_cases']} raw cases` | `{t_res['findings_reviewed_for_100pct_recall']} prioritized findings` | `{h_res['findings_reviewed_for_100pct_recall']} prioritized findings` |")
    md.append(f"| **Estimated Total Review Time** | `{t_res['total_baseline_effort_hours']} hrs` | `{t_res['assisted_time_for_100pct_recall_hours']} hrs` | `{h_res['assisted_time_for_100pct_recall_hours']} hrs` |")
    md.append(f"| **Time to 1st Useful Finding** | `{t_res['baseline_expected_minutes_to_first_useful']} min (expected)` | `{t_res['assisted_minutes_to_first_useful']} min` | `{h_res['assisted_minutes_to_first_useful']} min` |")
    md.append(f"| **Workload Effort Reduction** | `0.0% (Baseline)` | **`{t_res['workload_effort_reduction_percentage']}%`** | **`{h_res['workload_effort_reduction_percentage']}%`** |")
    md.append(f"| **Efficiency Multiplier (Speedup)** | `1.0x` | **`{t_res['efficiency_multiplier_speedup']}x faster`** | **`{h_res['efficiency_multiplier_speedup']}x faster`** |")
    md.append(f"| **Weakness Capture (Recall)** | `100.0% (after all cases)` | **`{t_res['recall']*100:.1f}% (top {t_res['findings_reviewed_for_100pct_recall']})`** | **`{h_res['recall']*100:.1f}% (top {h_res['findings_reviewed_for_100pct_recall']})`** |")
    md.append("")
    md.append("---")
    md.append("")
    md.append("## 2. Split Performance Breakdown")
    md.append("")
    md.append("### 2.1 Tuning Split (Controlled Scenarios)")
    md.append(f"- **Total Raw Telemetry Records:** {t_res['total_raw_records']}")
    md.append(f"- **Ground Truth Security Flaws:** {t_res['total_true_weaknesses']}")
    md.append(f"- **Precision:** `{t_res['precision']*100:.1f}%` | **Recall:** `{t_res['recall']*100:.1f}%` | **F1 Score:** `{t_res['f1_score']:.3f}`")
    md.append(f"- **Top-1 Recall:** `{t_res['recall_at_1']*100:.1f}%` | **Top-3 Recall:** `{t_res['recall_at_3']*100:.1f}%` | **Top-5 Recall:** `{t_res['recall_at_5']*100:.1f}%`")
    md.append(f"- **Headline Yield Summary:** {t_res['yield_summary']}")
    md.append("")
    md.append("#### Tuning Review Yield Progression:")
    md.append("| Rank | Entity | Finding Type | Priority Score | Useful? | Cumulative TP | Precision@K | Yield % | Assisted Time | Baseline Eq. Time |")
    md.append("| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for step in t_res["yield_curve"]:
        tp_str = "✅ YES" if step["is_true_positive"] else "⚠️ FP"
        md.append(f"| {step['rank']} | {step['cse_name']} | `{step['finding_type']}` | {step['priority_score']:.3f} | {tp_str} | {step['cumulative_true_positives']} | {step['precision_at_k']*100:.1f}% | {step['yield_percentage']}% | {step['assisted_time_minutes']} min | {step['baseline_equivalent_time_minutes']} min |")
    md.append("")
    md.append("### 2.2 Held-Out Split (Unseen Evaluation Scenarios)")
    md.append(f"- **Total Raw Telemetry Records:** {h_res['total_raw_records']}")
    md.append(f"- **Ground Truth Security Flaws:** {h_res['total_true_weaknesses']}")
    md.append(f"- **Precision:** `{h_res['precision']*100:.1f}%` | **Recall:** `{h_res['recall']*100:.1f}%` | **F1 Score:** `{h_res['f1_score']:.3f}`")
    md.append(f"- **Top-1 Recall:** `{h_res['recall_at_1']*100:.1f}%` | **Top-3 Recall:** `{h_res['recall_at_3']*100:.1f}%` | **Top-5 Recall:** `{h_res['recall_at_5']*100:.1f}%`")
    md.append(f"- **Headline Yield Summary:** {h_res['yield_summary']}")
    md.append("")
    md.append("#### Held-Out Review Yield Progression:")
    md.append("| Rank | Entity | Finding Type | Priority Score | Useful? | Cumulative TP | Precision@K | Yield % | Assisted Time | Baseline Eq. Time |")
    md.append("| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for step in h_res["yield_curve"]:
        tp_str = "✅ YES" if step["is_true_positive"] else "⚠️ FP"
        md.append(f"| {step['rank']} | {step['cse_name']} | `{step['finding_type']}` | {step['priority_score']:.3f} | {tp_str} | {step['cumulative_true_positives']} | {step['precision_at_k']*100:.1f}% | {step['yield_percentage']}% | {step['assisted_time_minutes']} min | {step['baseline_equivalent_time_minutes']} min |")
    md.append("")
    md.append("---")
    md.append("*Benchmark generated reproducibly via `python scripts/evaluate_review_efficiency.py`.*")
    return "\n".join(md)


def main():
    parser = argparse.ArgumentParser(
        description="SAT-SA Review-Efficiency Benchmark & Workload Reduction Evaluation."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="results/review_efficiency_benchmark.json",
        help="Destination path for machine-readable JSON output.",
    )
    parser.add_argument(
        "--markdown",
        "-m",
        type=str,
        default=None,
        help="Optional destination path for formatted Markdown report.",
    )
    parser.add_argument(
        "--ruleset",
        "-r",
        type=str,
        default="V1_AUTHORITATIVE",
        help="Ruleset version to evaluate (default: V1_AUTHORITATIVE).",
    )
    parser.add_argument(
        "--baseline-time",
        type=float,
        default=8.0,
        help="Estimated manual inspection minutes per unindexed case (default: 8.0).",
    )
    parser.add_argument(
        "--assisted-time",
        type=float,
        default=4.0,
        help="Estimated inspection minutes per structured SAT-SA finding (default: 4.0).",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Only output machine-readable JSON to stdout.",
    )

    args = parser.parse_args()

    # Instantiate evaluator
    evaluator = ReviewEfficiencyEvaluator(
        ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1,
        baseline_minutes_per_case=args.baseline_time,
        assisted_minutes_per_finding=args.assisted_time,
    )

    report = evaluator.run_full_benchmark()
    report_dict = report.to_dict()

    # Ensure output directories exist
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report.to_json(indent=2))

    if args.markdown:
        md_path = Path(args.markdown)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(format_markdown_report(report_dict))

    if args.json_only:
        print(report.to_json(indent=2))
        return

    # Print formatted human-readable terminal table
    t_res = report_dict["tuning_split"]
    h_res = report_dict["held_out_split"]

    print("=" * 80)
    print(" SAT-SA REVIEW-EFFICIENCY & WORKLOAD REDUCTION BENCHMARK")
    print(f" Ruleset: {report_dict['ruleset_version']} ({report_dict['ruleset_id']}) | App: v{report_dict['app_version']}")
    print(f" Timestamp: {report_dict['evaluation_timestamp']}")
    print("=" * 80)
    print("")
    print("1. SUMMARY COMPARISON: UNASSISTED BASELINE vs SAT-SA")
    print("-" * 80)
    print(f"{'Metric':<35} | {'Unassisted Baseline':<20} | {'SAT-SA Assisted'}")
    print("-" * 80)
    print(f"{'Cases to Review (100% Capture)':<35} | {t_res['total_raw_cases']:<20} | {t_res['findings_reviewed_for_100pct_recall']} findings")
    print(f"{'Total Review Effort Hours':<35} | {t_res['total_baseline_effort_hours']:<16.2f} hrs | {t_res['assisted_time_for_100pct_recall_hours']:.2f} hrs")
    print(f"{'Time to 1st Useful Finding':<35} | {t_res['baseline_expected_minutes_to_first_useful']:<16.1f} min | {t_res['assisted_minutes_to_first_useful']:.1f} min")
    print(f"{'Workload Effort Reduction':<35} | {'0.0% (Baseline)':<20} | {t_res['workload_effort_reduction_percentage']:.1f}%")
    print(f"{'Efficiency Speedup Multiplier':<35} | {'1.0x':<20} | {t_res['efficiency_multiplier_speedup']:.1f}x FASTER")
    print(f"{'Full Weakness Discovery Recall':<35} | {'100% (after all)':<20} | {t_res['recall']*100:.1f}% (top {t_res['findings_reviewed_for_100pct_recall']} cases)")
    print("-" * 80)
    print("")
    print("2. GENERALIZATION ACROSS TEST SPLITS")
    print("-" * 80)
    print(f"  * Tuning Split Recall:    {t_res['recall']*100:.1f}% (F1: {t_res['f1_score']:.3f}, Top-1: {t_res['recall_at_1']*100:.1f}%, Top-5: {t_res['recall_at_5']*100:.1f}%)")
    print(f"  * Held-Out Split Recall:  {h_res['recall']*100:.1f}% (F1: {h_res['f1_score']:.3f}, Top-1: {h_res['recall_at_1']*100:.1f}%, Top-5: {h_res['recall_at_5']*100:.1f}%)")
    print(f"  * Average Workload Effort Reduction: {report_dict['cross_split_summary']['average_workload_reduction_percentage']}%")
    print(f"  * Average Efficiency Multiplier:    {report_dict['cross_split_summary']['average_efficiency_multiplier_speedup']}x faster")
    print("-" * 80)
    print("")
    print(f"[OK] Machine-readable benchmark saved to: {out_path.resolve()}")
    if args.markdown:
        print(f"[OK] Markdown report saved to: {Path(args.markdown).resolve()}")
    print("=" * 80)


if __name__ == "__main__":
    main()
