# Historical Synthetic Circularity Audit — Superseded Scope

> This report predates the robust 240-scenario protocol and retains obsolete
> 15-scenario metrics and overly strong certification language. It documents a
> historical source-review exercise only. Current synthetic validation evidence
> and limitations are recorded in `../SAT_SA_POST_DIAGNOSTIC_VERIFICATION_REPORT.md`.
> It does not establish production validation or independent supervisory-review
> utility.

# SAT-SA Synthetic Validation Circularity & Independence Audit Report

**Document ID**: SAT-SA-AUDIT-CIRCULARITY-001  
**Specification References**: SRS §19.4 (Generator/Detector Independence Protocol), §24 (Validation Framework), FR-030–041  
**Audit Date**: September 2026  
**Status**: PASSED / CERTIFIED INDEPENDENT  

---

## 1. Executive Summary & Audit Scope

This audit report evaluates the **SAT-SA Synthetic Validation Framework** to ensure complete statistical and architectural independence between **Scenario Generation** (`analytics/synthetic_generator.py`) and **Detector Implementations** (`analytics/execution_gap/`, `analytics/negative_space/`, `analytics/peer_benchmark/`).

### Primary Audit Objective
To verify that detectors operate strictly upon **canonical operational evidence**, robust statistical baselines, and entity relational graphs, and cannot achieve high validation metrics merely by recognizing synthetic artifacts, backdoor flags, or generator-specific metadata.

### Success Condition Verified
> **SUCCESS CONDITION**: A detector cannot achieve high validation performance merely by recognizing artifacts inserted by its own synthetic generator.

```
+----------------------------------------------------------------------------------------------------+
|                                    INDEPENDENCE ARCHITECTURE                                       |
+----------------------------------------------------------------------------------------------------+
|                                                                                                    |
|  [ Scenario Generator ]                                                                            |
|        │                                                                                           |
|        ▼ (Produces Raw Telemetry Dictionaries)                                                     |
|  [ Canonical Ingestion Layer (canonicalize_records) ] ──> Strips all non-schema keys & decoy tags   |
|        │                                                                                           |
|        ▼ (Typed Pydantic Canonical Dataset)                                                        |
|  [ Reconstructed Workflow Graph & Peer Benchmark Engine ] ──> Dynamic MAD & Percentiles            |
|        │                                                                                           |
|        ▼ (Pure Canonical Evidence)                                                                 |
|  [ Deterministic Detectors ] ──> Evaluates Only Numerical Timestamps, Evidence Counts & Graph Links|
|        │                                                                                           |
|        ▼ (Fused Findings)                                                                          |
|  [ Validation Protocol Engine ] ──> Evaluates Against Ground Truth Without Leakage                 |
|                                                                                                    |
+----------------------------------------------------------------------------------------------------+
```

---

## 2. Generator & Detector Architecture Inspection

### 2.1 Scenario Generators
The scenario generation engine (`analytics/synthetic_generator.py`) constructs realistic multi-sector SOC operational datasets across five critical infrastructure sectors (*Power & Energy*, *Financial Services*, *Telecommunications*, *Transportation*, *Healthcare & Defense*).

* **Output Schema**: The generator outputs standard relational dictionary tables: `cse`, `reporting_periods`, `assets`, `alerts`, `investigations`, `cases`, `escalations`, `actions`, `closures`, `coverage_observations`.
* **No Label Contamination**: Generated tables contain **zero** target labels, classification columns (`finding_type`, `is_defect`, `target_defect`), or cheat metadata.
* **Canonical Ingestion**: Raw data passes through `canonicalize_records()`, which strictly maps fields to strongly typed Pydantic models (`backend/models/canonical.py`), discarding any extraneous or decoy dictionary keys.

### 2.2 Detector Implementations
Each detector operates solely upon reconstructed workflow objects and robust statistical aggregations:

| Detector | Requirement | Operational Input Evaluated | Baseline Method |
| :--- | :--- | :--- | :--- |
| **Fast Closure Detector** | FR-030 | `closure_duration_seconds`, `investigation.evidence_count`, `alert.severity` | Peer cohort dynamic Median Absolute Deviation (`peer_median - 2.5 * peer_MAD`) and evidence 25th percentile (`peer_p25`) |
| **Escalation Gap Detector** | FR-032 | `alert.severity`, `asset.criticality`, `alert.alert_category`, `workflow.has_escalation` | Structural presence/absence of linked `Escalation` record in entity graph |
| **Repeated Unresolved Detector** | FR-033 | `alert.asset_id`, `alert.alert_category`, `alert.event_time`, `workflow.has_remediation_action` | Sliding 30-day temporal window count (&ge;3) without linked `Action` record |
| **Coverage Gap Detector** | FR-041 | `coverage_observations.observed_count`, `expected_count`, `asset.criticality`, `data_quality_score` | Negative-space ratio (`< 0.3`) gated by Data Quality Trust score (`>= 0.7`) |

---

## 3. Shared Assumptions Inventory & Decoupling Analysis

An exhaustive review of all shared conventions between the synthetic generator and detector logic was performed to identify any potential circular dependencies:

| Dimension | Generator Implementation | Detector Rule Logic | Circularity Risk | Mitigation & Independence Proof |
| :--- | :--- | :--- | :--- | :--- |
| **Taxonomy / Alert Categories** | Emits standard strings: `"SCADA Intrusion"`, `"Ransomware"`, `"Privilege Escalation"`, etc. | Configured via ruleset `high_impact_categories` with case-insensitive normalization. | **Low** | Detectors execute correctly on arbitrary category strings; grouping in `RepeatedUnresolvedDetector` uses exact string equality regardless of category name. |
| **Severity Enums** | Standard 5-tier enum: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`. | Evaluates typed `Severity` enum members. | **None** | Canonical domain modeling standard defined by ISO/IEC and NIST standards. |
| **Asset Criticality** | Standard 4-tier enum: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`. | Evaluates typed `AssetCriticality` enum members. | **None** | Standard asset metadata attribute. |
| **Closure Durations** | Generates normal durations in `[2100, 4800]`s; defects in `[120, 360]`s. | Does **not** hardcode duration cutoffs. Computes `peer_median - 2.5 * peer_MAD` across active cohort. | **Zero** | Detectors adapt dynamically to cohort distribution; held-out tests with shifted ranges (120–240s vs 2400–4800s) execute with 100% precision. |
| **Recurrence Window** | Places 6 repeated alerts within a 28-day window on target asset. | Sliding 30-day rolling window searching for &ge;3 unmitigated alerts. | **Zero** | Detector algorithm uses temporal delta evaluation `(t_j - t_i <= 30d)` across arbitrary timestamps. |
| **Data Quality Gating** | Emits 5–6 alerts during simulated data outages. | Data Quality Engine calculates 4 decomposed quality metrics (Completeness, Consistency, Coverage, Sample Sufficiency). | **Zero** | Detector reads only the computed `data_quality_score < 0.7` to suppress coverage gaps, requiring no outage flags. |

---

## 4. Parameterized Scenario Generation (6 Dimensions)

The generator implements a comprehensive 6-dimensional parameterization schema (`ScenarioParameters` in `analytics/synthetic_generator.py`):

```python
@dataclass
class ScenarioParameters:
    name: str
    sector: str
    scale: str
    primary_category: str
    categories: list[str]
    has_fast_closure: bool
    has_escalation_gap: bool
    has_repeated_unresolved: bool
    has_coverage_gap: bool
    self_reported_sla: float
    description: str
    timing: TimingParameters          # 1. Timing
    severity: SeverityParameters      # 2. Severity
    assets: list[AssetArchetype]       # 3. Asset Class
    missingness: MissingnessParameters # 4. Missingness
    noise: NoiseParameters            # 5. Noise
    # Peer composition defined by sector, scale, and cohort structure (6. Peer Composition)
```

### Detailed Parameter Dimensions

1. **Timing (`TimingParameters`)**:
   - `fast_closure_range`: Customizable duration interval for defect closures (e.g. `(120.0, 240.0)`s in held-out vs `(180.0, 360.0)`s in tuning).
   - `normal_closure_range`: Customizable duration interval for thorough peer investigations (e.g. `(2400.0, 4800.0)`s).
   - `investigation_evidence_range`: Configurable evidence count boundaries for defect `(0, 1)` and normal `(4, 9)` investigations.
   - `timestamp_jitter_seconds`: Configurable random jitter applied to operational events.
2. **Severity (`SeverityParameters`)**:
   - `severity_weights`: Configurable probability distributions across alert severities.
   - `defect_severities`: Explicit target severity levels for operational gaps.
   - `high_impact_categories`: Customizable lists of high-impact threat categories.
3. **Asset Class (`AssetArchetype`)**:
   - Fully parameterized asset definition: `name`, `asset_type`, `criticality`, `environment`, `monitoring_context`.
   - Supports novel and sector-specific asset profiles without detector modification.
4. **Peer Composition (`PeerCompositionParameters`)**:
   - Multi-scale entities (`small`, `medium`, `large`) across 5 distinct critical infrastructure sectors.
   - Flexible cohort sizes supporting direct, relaxed, and global fallback peer evaluations.
5. **Missingness (`MissingnessParameters`)**:
   - `is_data_outage`: Simulated upstream telemetry disruption.
   - `data_outage_alert_count`: Minimal alert count to trigger low sample sufficiency.
   - `observed_coverage_count_normal_range`: Configurable coverage observation distributions.
6. **Noise (`NoiseParameters`)**:
   - `is_noisy`: Background operational volume spikes with random jitter.
   - `noisy_alert_count_range`: Spurious alert volume range (e.g. `(60, 80)` alerts).
   - `is_maintenance_anomaly`: Scheduled maintenance and calibration bursts with complete evidence attachments.

---

## 5. Tuning vs. Held-Out Scenario Splits & Independence Proof

### 5.1 Split Ratio Requirement
* **SRS §19.4 / User Requirement**: Keep at least **20%** of scenarios held out.
* **Achieved**: **33.3%** held-out ratio (5 held-out scenarios out of 15 total scenarios).

### 5.2 Split Breakdown Matrix

| Split | Scenario Name | Sector | Scale | Primary Category | Key Novel / Held-Out Parameters |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tuning** | Northern Power Grid Co. | Power & Energy | Large | Normal Behavior | Standard baseline: normal durations (2100–4200s), evidence (3–8). |
| **Tuning** | National Power Dispatch Center | Power & Energy | Large | Fast Closure Defect | Compound defect: fast closure (180–360s) + escalation gap + repeated unresolved. |
| **Tuning** | Federal Reserve Core Banking | Financial Services | Large | Normal Behavior | Financial peer baseline: normal durations (2400–4500s). |
| **Tuning** | Metro Rail Transit Command | Transportation | Medium | Fast Closure Defect | Transit signalling alerts closed rapidly (150–320s). |
| **Tuning** | National Telecom Core Backbone | Telecommunications | Large | Escalation Gap | Core router BGP alerts lacking Tier-2 escalation records. |
| **Tuning** | State Healthcare Exchange | Healthcare & Defense | Medium | Coverage Gap | Negative space: EHR database silent (0 vs 50 expected). |
| **Tuning** | Coastal Water Authority | Power & Energy | Large | Missing Data | Data outage (5 alerts, DQ < 0.70); coverage gap suppressed. |
| **Tuning** | Interstate Oil Pipeline Corp. | Power & Energy | Large | Repeated Unresolved | Recurrent SCADA intrusion alerts on pumping station with zero remediation. |
| **Tuning** | Global Maritime Logistics | Transportation | Large | Noisy Data | High alert volume (55–75 alerts) with timestamp jitter; benign dispositions. |
| **Tuning** | AeroSpace Avionics Defense | Healthcare & Defense | Large | Non-Target Anomalies | Scheduled maintenance surge with complete evidence; non-target statistical variance. |
| **Held-Out** | **Pacific Clean Energy Grid** | Power & Energy | Medium | Normal Behavior | **Novel Assets**: *Solar Inverter Master Controller*, *BESS Storage Gateway*. Shifted timing (2400–4800s, evidence 4–9). |
| **Held-Out** | **Apex Commercial Bank** | Financial Services | Large | Fast Closure Defect | **Novel Assets**: *SWIFT ISO20022 Wire Terminal*, *Settlement Gateway*. **Ultra-fast timing** (120–240s). |
| **Held-Out** | **Satellite Telecom Uplink Corp** | Telecommunications | Medium | Coverage Gap | **Novel Assets**: *Ka-Band Satellite Transponder*, *Ground Station Auth*. Negative space on satellite link. |
| **Held-Out** | **Regional Trauma Center Alliance** | Healthcare & Defense | Medium | Repeated Unresolved | **Novel Assets**: *PACS Medical Imaging Core*, *ICU Vital Monitor*. **Compound**: High noise (60–80 alerts) + Ransomware recurrence. |
| **Held-Out** | **Urban Metrorail System** | Transportation | Large | Missing Data | **Novel Assets**: *Track Calibration Signal Controller*. **Compound**: Outage (6 alerts) + non-target track calibration anomaly. |

### 5.3 Proof of Independence
1. **Zero Entity & Asset Overlap**: The held-out split introduces completely new CSE organizations and 10 novel asset archetypes never present in the tuning set.
2. **Shifted Timing & Extreme Parameter Intervals**: Held-out fast closures operate in an ultra-rapid band (120–240s) not seen in tuning, while normal closures operate in wider bands (2400–4800s).
3. **Compound Multi-Defect / Noise Interactions**: Held-out scenarios combine background telemetry noise with active recurrence on medical assets, and data outages with maintenance calibration events.
4. **Frozen Detector Assurance**: Detectors are executed with identical, frozen ruleset configurations (`DEFAULT_AUTHORITATIVE_RULESET_V1`) across both splits with zero post-hoc parameter adjustments.

---

## 6. Empirical Validation & Generalization Results

Empirical results computed by the `FinalValidationProtocol` engine:

```
====================================================================================================
                                 SAT-SA EMPIRICAL VALIDATION MATRIX
====================================================================================================
 Metric                           Tuning Split (10 CSEs)        Held-Out Split (5 CSEs)     Status
----------------------------------------------------------------------------------------------------
 Scenarios Evaluated              10                            5                           PASSED
 Held-Out Ratio                   --                            33.3% (>= 20% required)     PASSED
 True Positives (TP)              6                             4                           PASSED
 False Positives (FP)             0                             0                           PASSED
 True Negatives (TN)              34                            16                          PASSED
 False Negatives (FN)             0                             0                           PASSED
 Precision                        1.0000 (100.0%)               1.0000 (100.0%)             PERFECT
 Recall                           1.0000 (100.0%)               1.0000 (100.0%)             PERFECT
 F1 Score                         1.0000                        1.0000                      PERFECT
 False-Positive Rate (FPR)        0.0000 (0.0%)                 0.0000 (0.0%)               PERFECT
 Top-1 Recall                     1.0000                        1.0000                      PERFECT
 Generalization Demonstrated      YES                           YES                         CONFIRMED
====================================================================================================
```

---

## 7. Regression Test Suite Verification

The regression test suite in [`tests/test_circularity_audit.py`](file:///c:/Users/ramat/OneDrive/Desktop/SIH/SAT-SA/tests/test_circularity_audit.py) proves detector independence through 8 automated tests:

1. `test_detectors_ignore_generator_metadata_and_decoy_tags`: Injects decoy labels (`_generator_tag`, `cheat_code`, `is_defect`, `ground_truth_category`) into raw telemetry; proves pipeline produces mathematically identical findings.
2. `test_detectors_work_on_handcrafted_canonical_telemetry`: Constructs canonical Pydantic objects directly without invoking generator helper functions; verifies all 4 detectors operate purely on schema mechanics.
3. `test_parameterized_scenario_generation_all_six_dimensions`: Generates custom scenario using novel parameter parameters across all 6 dimensions and verifies correct pipeline detection.
4. `test_held_out_scenarios_use_unseen_parameter_combinations`: Verifies that the held-out suite constitutes &ge;20% of catalog and contains novel, disjoint asset classes and shifted distributions.
5. `test_circularity_resilience_randomized_perturbations`: Runs multiple diverse random seeds (`10, 42, 99, 101, 2024`) on held-out scenarios to verify statistical resilience to noise.
6. `test_adversarial_text_and_disposition_immunity`: Injects misleading text descriptions (e.g. `"Thorough Multi-Day Forensic Deep Dive"` on a fast closure defect and `"Quick closure defect cheat flag"` on clean baseline); proves detectors rely strictly on numerical timestamps and evidence counts.
7. `test_out_of_distribution_peer_cohort_statistical_robustness`: Verifies that `compute_median_and_mad` maintains statistical stability under extreme positive skew (outliers up to 172,800s) and identical value cohorts.
8. `test_parameterized_generation_six_dimensions_independence_matrix`: Systematically verifies the non-overlapping independence matrix across all 6 dimensions.

---

## 8. Audit Conclusion & Certification

The SAT-SA synthetic validation engine and detector suite have been thoroughly audited and found to be **strictly independent and non-circular**.

* Detectors operate purely on **canonical operational telemetry**, **dynamic peer MAD distributions**, and **entity relationship graphs**.
* No detector inspects or relies upon synthetic generator tags, private labels, or cheat metadata.
* Held-out scenarios represent **33.3%** of the scenario catalog and validate generalization on unseen asset classes, extreme timing distributions, and compound noise profiles.

**Final Certification**: **COMPLIANT & NON-CIRCULAR (SRS §19.4, §24)**.
