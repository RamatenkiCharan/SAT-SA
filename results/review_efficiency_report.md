# SAT-SA Review-Efficiency Benchmark & Workload Reduction Report

**Evaluation Timestamp:** `2026-09-10T09:38:11.674010+00:00`  
**Ruleset Version:** `V1` (`00000000-0000-0000-0000-000000000001`)  
**Application Version:** `v2.2.0`  
**Methodology:** Generator/Detector Independence Review Efficiency Protocol (SRS §19.4)  

---

## 1. Executive Summary & Efficiency Multiplier

| Metric | Unassisted Baseline | SAT-SA Assisted (Tuning) | SAT-SA Assisted (Held-Out) |
| :--- | :---: | :---: | :---: |
| **Review Target to Inspect** | `200 raw cases` | `6 prioritized findings` | `6 prioritized findings` |
| **Estimated Total Review Time** | `26.67 hrs` | `0.4 hrs` | `0.4 hrs` |
| **Time to 1st Useful Finding** | `229.6 min (expected)` | `4.0 min` | `4.0 min` |
| **Workload Effort Reduction** | `0.0% (Baseline)` | **`98.5%`** | **`98.6%`** |
| **Efficiency Multiplier (Speedup)** | `1.0x` | **`66.7x faster`** | **`70.7x faster`** |
| **Weakness Capture (Recall)** | `100.0% (after all cases)` | **`100.0% (top 6)`** | **`100.0% (top 6)`** |

---

## 2. Split Performance Breakdown

### 2.1 Tuning Split (Controlled Scenarios)
- **Total Raw Telemetry Records:** 628
- **Ground Truth Security Flaws:** 6
- **Precision:** `46.2%` | **Recall:** `100.0%` | **F1 Score:** `0.632`
- **Top-1 Recall:** `16.7%` | **Top-3 Recall:** `50.0%` | **Top-5 Recall:** `83.3%`
- **Headline Yield Summary:** Captured 6 of 6 true weaknesses within top 6 prioritized reviews (0.4 hrs vs 26.67 hrs baseline, 98.5% review effort reduction, 66.7x speedup).

#### Tuning Review Yield Progression:
| Rank | Entity | Finding Type | Priority Score | Useful? | Cumulative TP | Precision@K | Yield % | Assisted Time | Baseline Eq. Time |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | National Power Dispatch Center (NPDC) | `FAST_CLOSURE` | 0.845 | ✅ YES | 1 | 100.0% | 16.7% | 4.0 min | 266.7 min |
| 2 | National Power Dispatch Center (NPDC) | `ESCALATION_GAP` | 0.788 | ✅ YES | 2 | 100.0% | 33.3% | 8.0 min | 533.3 min |
| 3 | National Telecom Core Backbone | `ESCALATION_GAP` | 0.788 | ✅ YES | 3 | 100.0% | 50.0% | 12.0 min | 800.0 min |
| 4 | Metro Rail Transit Command | `FAST_CLOSURE` | 0.745 | ✅ YES | 4 | 100.0% | 66.7% | 16.0 min | 1066.7 min |
| 5 | State Healthcare Exchange | `COVERAGE_GAP` | 0.692 | ✅ YES | 5 | 100.0% | 83.3% | 20.0 min | 1333.3 min |
| 6 | National Power Dispatch Center (NPDC) | `REPEATED_UNRESOLVED_ALERTS` | 0.665 | ✅ YES | 6 | 100.0% | 100.0% | 24.0 min | 1600.0 min |
| 7 | National Power Dispatch Center (NPDC) | `REPEATED_UNRESOLVED_ALERTS` | 0.665 | ⚠️ FP | 6 | 85.7% | 100.0% | 28.0 min | 1600.0 min |
| 8 | Federal Reserve Core Banking | `REPEATED_UNRESOLVED_ALERTS` | 0.665 | ⚠️ FP | 6 | 75.0% | 100.0% | 32.0 min | 1600.0 min |
| 9 | Federal Reserve Core Banking | `REPEATED_UNRESOLVED_ALERTS` | 0.665 | ⚠️ FP | 6 | 66.7% | 100.0% | 36.0 min | 1600.0 min |
| 10 | Federal Reserve Core Banking | `REPEATED_UNRESOLVED_ALERTS` | 0.665 | ⚠️ FP | 6 | 60.0% | 100.0% | 40.0 min | 1600.0 min |
| 11 | Metro Rail Transit Command | `REPEATED_UNRESOLVED_ALERTS` | 0.665 | ⚠️ FP | 6 | 54.5% | 100.0% | 44.0 min | 1600.0 min |
| 12 | National Telecom Core Backbone | `REPEATED_UNRESOLVED_ALERTS` | 0.665 | ⚠️ FP | 6 | 50.0% | 100.0% | 48.0 min | 1600.0 min |
| 13 | State Healthcare Exchange | `REPEATED_UNRESOLVED_ALERTS` | 0.665 | ⚠️ FP | 6 | 46.2% | 100.0% | 52.0 min | 1600.0 min |
| 14 | State Healthcare Exchange | `REPEATED_UNRESOLVED_ALERTS` | 0.665 | ⚠️ FP | 6 | 42.9% | 100.0% | 56.0 min | 1600.0 min |

### 2.2 Held-Out Split (Unseen Evaluation Scenarios)
- **Total Raw Telemetry Records:** 664
- **Ground Truth Security Flaws:** 6
- **Precision:** `60.0%` | **Recall:** `100.0%` | **F1 Score:** `0.750`
- **Top-1 Recall:** `16.7%` | **Top-3 Recall:** `50.0%` | **Top-5 Recall:** `83.3%`
- **Headline Yield Summary:** Captured 6 of 6 true weaknesses within top 6 prioritized reviews (0.4 hrs vs 28.27 hrs baseline, 98.6% review effort reduction, 70.7x speedup).

#### Held-Out Review Yield Progression:
| Rank | Entity | Finding Type | Priority Score | Useful? | Cumulative TP | Precision@K | Yield % | Assisted Time | Baseline Eq. Time |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | National Power Dispatch Center (NPDC) | `FAST_CLOSURE` | 0.846 | ✅ YES | 1 | 100.0% | 16.7% | 4.0 min | 282.7 min |
| 2 | National Power Dispatch Center (NPDC) | `ESCALATION_GAP` | 0.789 | ✅ YES | 2 | 100.0% | 33.3% | 8.0 min | 565.3 min |
| 3 | National Telecom Core Backbone | `ESCALATION_GAP` | 0.789 | ✅ YES | 3 | 100.0% | 50.0% | 12.0 min | 848.0 min |
| 4 | Metro Rail Transit Command | `FAST_CLOSURE` | 0.746 | ✅ YES | 4 | 100.0% | 66.7% | 16.0 min | 1130.7 min |
| 5 | State Healthcare Exchange | `COVERAGE_GAP` | 0.693 | ✅ YES | 5 | 100.0% | 83.3% | 20.0 min | 1413.3 min |
| 6 | National Power Dispatch Center (NPDC) | `REPEATED_UNRESOLVED_ALERTS` | 0.666 | ✅ YES | 6 | 100.0% | 100.0% | 24.0 min | 1696.0 min |
| 7 | National Power Dispatch Center (NPDC) | `REPEATED_UNRESOLVED_ALERTS` | 0.666 | ⚠️ FP | 6 | 85.7% | 100.0% | 28.0 min | 1696.0 min |
| 8 | Metro Rail Transit Command | `REPEATED_UNRESOLVED_ALERTS` | 0.666 | ⚠️ FP | 6 | 75.0% | 100.0% | 32.0 min | 1696.0 min |
| 9 | National Telecom Core Backbone | `REPEATED_UNRESOLVED_ALERTS` | 0.666 | ⚠️ FP | 6 | 66.7% | 100.0% | 36.0 min | 1696.0 min |
| 10 | National Telecom Core Backbone | `REPEATED_UNRESOLVED_ALERTS` | 0.666 | ⚠️ FP | 6 | 60.0% | 100.0% | 40.0 min | 1696.0 min |
| 11 | State Healthcare Exchange | `REPEATED_UNRESOLVED_ALERTS` | 0.666 | ⚠️ FP | 6 | 54.5% | 100.0% | 44.0 min | 1696.0 min |

---
*Benchmark generated reproducibly via `python scripts/evaluate_review_efficiency.py`.*