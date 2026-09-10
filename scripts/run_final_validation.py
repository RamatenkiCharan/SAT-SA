"""
CLI Runner for the Final SAT-SA Validation Protocol (SRS §19.4, §24).

Executes the final validation protocol across Tuning (10 scenarios) and Held-Out (5 scenarios) splits,
verifies all 8 scenario categories, measures confusion matrix & efficiency metrics, and persists configuration.

Usage:
    python scripts/run_final_validation.py [--output results/final_validation_protocol.json] [--report results/final_validation_report.md]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics.evaluation.validation_protocol import run_final_validation_protocol
from backend.models.ruleset import DEFAULT_AUTHORITATIVE_RULESET_V1


def main():
    parser = argparse.ArgumentParser(
        description="SAT-SA Final Validation Protocol CLI (SRS §19.4)"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default="results/final_validation_protocol.json",
        help="Path to save machine-readable JSON results (default: results/final_validation_protocol.json)",
    )
    parser.add_argument(
        "--report",
        "-r",
        type=str,
        default="results/final_validation_report.md",
        help="Path to save human-readable Markdown report (default: results/final_validation_report.md)",
    )
    args = parser.parse_args()

    print("================================================================================")
    print("           SAT-SA FINAL VALIDATION PROTOCOL RUNNER (SRS §19.4, §24)             ")
    print("================================================================================")
    print("Executing independent evaluation across Tuning and Held-Out scenario splits...")
    print(f"Ruleset: {DEFAULT_AUTHORITATIVE_RULESET_V1.version} ({DEFAULT_AUTHORITATIVE_RULESET_V1.ruleset_id})")
    print()

    result = run_final_validation_protocol(
        ruleset=DEFAULT_AUTHORITATIVE_RULESET_V1,
        output_json_path=args.output,
        output_md_path=args.report,
    )

    t_cm = result.tuning_split.confusion_matrix
    h_cm = result.held_out_split.confusion_matrix

    print("--------------------------------------------------------------------------------")
    print("1. SCENARIO SPLIT DISTRIBUTION & GENERALIZATION")
    print("--------------------------------------------------------------------------------")
    print(f"Total Scenarios Evaluated: {result.tuning_split.total_scenarios + result.held_out_split.total_scenarios}")
    print(f"  - Tuning Split:   {result.tuning_split.total_scenarios} scenarios ({100.0 - result.held_out_ratio_percentage:.1f}%)")
    print(f"  - Held-Out Split: {result.held_out_split.total_scenarios} scenarios ({result.held_out_ratio_percentage:.1f}%) [Req: >= 20%]")
    print(f"Meets Held-Out Ratio: {result.generalization_delta['meets_min_20pct_held_out_requirement']}")
    print(f"Generalization Status: {'PASSED' if result.generalization_delta['generalization_demonstrated'] else 'FAILED'}")
    print()

    print("--------------------------------------------------------------------------------")
    print("2. CONFUSION MATRIX & EMPIRICAL METRICS SUMMARY")
    print("--------------------------------------------------------------------------------")
    print(f"{'Metric':<30} | {'Tuning Set':<15} | {'Held-Out Set':<15} | {'Delta':<10}")
    print("-" * 75)
    print(f"{'True Positives (TP)':<30} | {t_cm.tp:<15} | {h_cm.tp:<15} | {h_cm.tp - t_cm.tp:+d}")
    print(f"{'False Positives (FP)':<30} | {t_cm.fp:<15} | {h_cm.fp:<15} | {h_cm.fp - t_cm.fp:+d}")
    print(f"{'True Negatives (TN)':<30} | {t_cm.tn:<15} | {h_cm.tn:<15} | {h_cm.tn - t_cm.tn:+d}")
    print(f"{'False Negatives (FN)':<30} | {t_cm.fn:<15} | {h_cm.fn:<15} | {h_cm.fn - t_cm.fn:+d}")
    print(f"{'Precision':<30} | {t_cm.precision * 100:.1f}%{'':<10} | {h_cm.precision * 100:.1f}%{'':<10} | {result.generalization_delta['precision_delta'] * 100:+.1f}%")
    print(f"{'Recall (Weakness Discovery)':<30} | {t_cm.recall * 100:.1f}%{'':<10} | {h_cm.recall * 100:.1f}%{'':<10} | {result.generalization_delta['recall_delta'] * 100:+.1f}%")
    print(f"{'F1 Harmonic Score':<30} | {t_cm.f1_score * 100:.1f}%{'':<10} | {h_cm.f1_score * 100:.1f}%{'':<10} | {result.generalization_delta['f1_delta'] * 100:+.1f}%")
    print(f"{'False-Positive Rate (FPR)':<30} | {t_cm.false_positive_rate * 100:.1f}%{'':<10} | {h_cm.false_positive_rate * 100:.1f}%{'':<10} | {result.generalization_delta['fpr_delta'] * 100:+.1f}%")
    print()

    print("--------------------------------------------------------------------------------")
    print("3. MANDATORY SCENARIO CATEGORY AUDIT (SRS Section 19.4)")
    print("--------------------------------------------------------------------------------")
    t_cats = {c.category_name: c for c in result.tuning_split.category_breakdown}
    h_cats = {c.category_name: c for c in result.held_out_split.category_breakdown}
    for cat in result.mandatory_categories_verified:
        tc = t_cats.get(cat)
        hc = h_cats.get(cat)
        t_str = f"TP:{tc.tp} FP:{tc.fp} TN:{tc.tn}" if tc else "N/A"
        h_str = f"TP:{hc.tp} FP:{hc.fp} TN:{hc.tn}" if hc else "N/A"
        print(f"  [OK] {cat:<32} -> Tuning ({t_str}) | Held-Out ({h_str})")
    print()

    print("--------------------------------------------------------------------------------")
    print("4. PERSISTENCE & ARTIFACTS")
    print("--------------------------------------------------------------------------------")
    print(f"  [OK] Machine-Readable JSON: {args.output}")
    print(f"  [OK] Human-Readable Report: {args.report}")
    print("================================================================================")
    print("                      VALIDATION PROTOCOL COMPLETED SUCCESSFULLY                ")
    print("================================================================================")


if __name__ == "__main__":
    main()
