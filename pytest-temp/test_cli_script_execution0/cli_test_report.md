# SAT-SA Review-Efficiency Benchmark & Workload Reduction Report

**Evaluation Timestamp:** `2026-09-11T08:39:29.051002+00:00`  
**Ruleset Version:** `V1` (`00000000-0000-0000-0000-000000000001`)  
**Application Version:** `v2.2.0`  
**Methodology:** Generator/Detector Independence Review Efficiency Protocol (SRS §19.4)  

---

## 1. Executive Summary & Efficiency Multiplier

| Metric | Unassisted Baseline | SAT-SA Assisted (Tuning) | SAT-SA Assisted (Held-Out) |
| :--- | :---: | :---: | :---: |
| **Review Target to Inspect** | `361 raw cases` | `13 prioritized findings` | `5 prioritized findings` |
| **Estimated Total Review Time** | `48.13 hrs` | `0.87 hrs` | `0.33 hrs` |
| **Time to 1st Useful Finding** | `361.6 min (expected)` | `4.0 min` | `4.0 min` |
| **Workload Effort Reduction** | `0.0% (Baseline)` | **`98.2%`** | **`98.5%`** |
| **Efficiency Multiplier (Speedup)** | `1.0x` | **`55.5x faster`** | **`68.0x faster`** |
| **Weakness Capture (Recall)** | `100.0% (after all cases)` | **`100.0% (top 13)`** | **`100.0% (top 5)`** |

---

## 2. Split Performance Breakdown

### 2.1 Tuning Split (Controlled Scenarios)
- **Total Raw Telemetry Records:** 1123
- **Ground Truth Security Flaws:** 7
- **Precision:** `53.8%` | **Recall:** `100.0%` | **F1 Score:** `0.700`
- **Top-1 Recall:** `14.3%` | **Top-3 Recall:** `42.9%` | **Top-5 Recall:** `71.4%`
- **Headline Yield Summary:** Captured 7 of 7 true weaknesses within top 13 prioritized reviews (0.87 hrs vs 48.13 hrs baseline, 98.2% review effort reduction, 55.5x speedup).

#### Tuning Review Yield Progression:
| Rank | Entity | Finding Type | Priority Score | Useful? | Cumulative TP | Precision@K | Yield % | Assisted Time | Baseline Eq. Time |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | National Power Dispatch Center (NPDC) | `FAST_CLOSURE` | 0.850 | ✅ YES | 1 | 100.0% | 14.3% | 4.0 min | 412.6 min |
| 2 | National Power Dispatch Center (NPDC) | `ESCALATION_GAP` | 0.793 | ✅ YES | 2 | 100.0% | 28.6% | 8.0 min | 825.1 min |
| 3 | National Telecom Core Backbone | `ESCALATION_GAP` | 0.793 | ✅ YES | 3 | 100.0% | 42.9% | 12.0 min | 1237.7 min |
| 4 | Metro Rail Transit Command | `FAST_CLOSURE` | 0.750 | ✅ YES | 4 | 100.0% | 57.1% | 16.0 min | 1650.3 min |
| 5 | State Healthcare Exchange | `COVERAGE_GAP` | 0.697 | ✅ YES | 5 | 100.0% | 71.4% | 20.0 min | 2062.9 min |
| 6 | State Healthcare Exchange | `COVERAGE_GAP` | 0.697 | ⚠️ FP | 5 | 83.3% | 71.4% | 24.0 min | 2062.9 min |
| 7 | State Healthcare Exchange | `COVERAGE_GAP` | 0.697 | ⚠️ FP | 5 | 71.4% | 71.4% | 28.0 min | 2062.9 min |
| 8 | National Power Dispatch Center (NPDC) | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ✅ YES | 6 | 75.0% | 85.7% | 32.0 min | 2475.4 min |
| 9 | National Power Dispatch Center (NPDC) | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 6 | 66.7% | 85.7% | 36.0 min | 2475.4 min |
| 10 | National Power Dispatch Center (NPDC) | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 6 | 60.0% | 85.7% | 40.0 min | 2475.4 min |
| 11 | National Power Dispatch Center (NPDC) | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 6 | 54.5% | 85.7% | 44.0 min | 2475.4 min |
| 12 | National Power Dispatch Center (NPDC) | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 6 | 50.0% | 85.7% | 48.0 min | 2475.4 min |
| 13 | Interstate Oil Pipeline Corp. | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ✅ YES | 7 | 53.8% | 100.0% | 52.0 min | 2888.0 min |

### 2.2 Held-Out Split (Unseen Evaluation Scenarios)
- **Total Raw Telemetry Records:** 530
- **Ground Truth Security Flaws:** 4
- **Precision:** `22.2%` | **Recall:** `100.0%` | **F1 Score:** `0.364`
- **Top-1 Recall:** `25.0%` | **Top-3 Recall:** `75.0%` | **Top-5 Recall:** `100.0%`
- **Headline Yield Summary:** Captured 4 of 4 true weaknesses within top 5 prioritized reviews (0.33 hrs vs 22.67 hrs baseline, 98.5% review effort reduction, 68.0x speedup).

#### Held-Out Review Yield Progression:
| Rank | Entity | Finding Type | Priority Score | Useful? | Cumulative TP | Precision@K | Yield % | Assisted Time | Baseline Eq. Time |
| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | Apex Commercial Bank | `FAST_CLOSURE` | 0.850 | ✅ YES | 1 | 100.0% | 25.0% | 4.0 min | 340.0 min |
| 2 | Apex Commercial Bank | `ESCALATION_GAP` | 0.793 | ✅ YES | 2 | 100.0% | 50.0% | 8.0 min | 680.0 min |
| 3 | Satellite Telecom Uplink Corp | `COVERAGE_GAP` | 0.697 | ✅ YES | 3 | 100.0% | 75.0% | 12.0 min | 1020.0 min |
| 4 | Satellite Telecom Uplink Corp | `COVERAGE_GAP` | 0.697 | ⚠️ FP | 3 | 75.0% | 75.0% | 16.0 min | 1020.0 min |
| 5 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ✅ YES | 4 | 80.0% | 100.0% | 20.0 min | 1360.0 min |
| 6 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 66.7% | 100.0% | 24.0 min | 1360.0 min |
| 7 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 57.1% | 100.0% | 28.0 min | 1360.0 min |
| 8 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 50.0% | 100.0% | 32.0 min | 1360.0 min |
| 9 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 44.4% | 100.0% | 36.0 min | 1360.0 min |
| 10 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 40.0% | 100.0% | 40.0 min | 1360.0 min |
| 11 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 36.4% | 100.0% | 44.0 min | 1360.0 min |
| 12 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 33.3% | 100.0% | 48.0 min | 1360.0 min |
| 13 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 30.8% | 100.0% | 52.0 min | 1360.0 min |
| 14 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 28.6% | 100.0% | 56.0 min | 1360.0 min |
| 15 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 26.7% | 100.0% | 60.0 min | 1360.0 min |
| 16 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 25.0% | 100.0% | 64.0 min | 1360.0 min |
| 17 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 23.5% | 100.0% | 68.0 min | 1360.0 min |
| 18 | Regional Trauma Center Alliance | `REPEATED_UNRESOLVED_ALERTS` | 0.670 | ⚠️ FP | 4 | 22.2% | 100.0% | 72.0 min | 1360.0 min |

---
*Benchmark generated reproducibly via `python scripts/evaluate_review_efficiency.py`.*