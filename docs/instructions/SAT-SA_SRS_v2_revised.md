# SOFTWARE REQUIREMENTS SPECIFICATION
## SAT-SA — Supervisory Analytics Tool for SOC Assessment
### Smart Evidence-Driven Supervisory Assurance Platform

| Document Attribute | Value |
|---|---|
| Problem Statement ID | 26157 |
| Problem Statement Title | Supervisory Analytics Tool for SOC Assessment (SAT-SA) |
| Primary Stakeholder | National Critical Information Infrastructure Protection Centre (NCIIPC) |
| Document Type | Comprehensive Software Requirements Specification (SRS) |
| Target Deployment | NCIIPC-controlled, fully offline / air-gapped environment |
| Primary Users | Supervisors, assessment analysts/reviewers, administrators, auditors |
| System Nature | Supervisory analytics and decision-support system; not a SOC/SIEM |
| Prototype Data Strategy | Synthetic/controlled datasets until authorized operational data is available |
| **Version** | **2.0 — revised for MVP scoping, formula pinning, and validation-independence discipline** |
| Prepared For | SIH solution design, implementation, validation, demonstration and judging |

> **What changed in v2.0 (summary):** (1) every requirement now carries an explicit build-priority tier so a team or an AI coding agent doesn't try to build all ~95 requirements with equal weight; (2) confidence and data-quality percentages are now defined by actual formulas instead of illustrative numbers; (3) a Generator/Detector Independence Protocol was added to prevent circular validation; (4) security requirements are split into a Hackathon Baseline and a Production Target so prototype effort isn't spent on production-grade controls; (5) resourcing assumptions were added so the roadmap can be sanity-checked against real capacity; (6) the vaguest detector requirements now have pinned statistical definitions; (7) a Requirements Traceability Matrix was added as Appendix C.

---

## 0. Executive Intent

SAT-SA is a supervisory analytics platform designed to help NCIIPC examine the operational evidence produced by Security Operations Centres (SOCs) across Critical Sector Entities (CSEs). Its purpose is not to operate a SOC, detect attacks in real time, or replace expert supervisory judgement. Its purpose is to reduce the amount of manual evidence review required to identify entities, processes, cases and operational patterns that deserve supervisory attention.

The central design principle is **Evidence-to-Assurance**: instead of relying primarily on what a CSE reports about its SOC capability, the platform analyzes what the submitted operational records demonstrate about how the SOC actually behaves. It reconstructs workflows across alerts, investigations, escalations, cases and closures; establishes expected evidence; detects deviations and missing evidence; compares behavior with appropriate peer groups; fuses multiple signals; and produces evidence-backed review priorities.

The two central analytical concepts are **execution gaps** and **negative space**. An execution gap exists when documented or expected controls/processes appear to exist but operational evidence suggests weak, superficial, inconsistent or metric-driven execution. Negative space concerns evidence that should reasonably exist but is missing, unexpectedly sparse, or inconsistent with the known operating context. Neither is treated as an automatic finding of failure: both are hypotheses requiring contextual interpretation and human supervisory review.

**v2.0 addition — scope discipline:** this SRS is deliberately larger than what any team should attempt to fully build for an SIH prototype. Section 3.1 and the Tier columns throughout this document define what must exist for a credible demo (P0), what strengthens the pitch if time allows (P1), and what belongs only in a real deployment (P2). Treat P0 as the actual build target; treat P1/P2 as evidence that the team understands the full problem, not as a to-do list.

---

## 1. Source and Scope Basis

This SRS consolidates the provided SIH Problem Statement 26157 and the accompanying project-design material. The supplied material emphasizes operational evidence, execution gaps, negative-space analysis, peer comparison, explainability, human-in-the-loop review, air-gapped deployment, synthetic validation where real NCIIPC data is unavailable, and measurable reduction in manual review effort.

The source statement explicitly defines the solution as a supervisory analytics capability rather than an operational cybersecurity platform. The SRS therefore treats the following as hard scope boundaries: no SOC replacement, no SIEM replacement, no real-time monitoring, no centralized national monitoring, no continuous telemetry collection, no cloud dependency, no SaaS dependency, and no externally hosted AI dependency.

---

## 2. Problem Definition

### 2.1 Operational Problem
NCIIPC performs supervisory assessments of CSE cyber resilience. Manual review of samples of SOC alerts and case-management records has revealed findings that may not be visible through policies, audits, self-assessments, management reports, KPI dashboards or compliance documentation. As the number of CSEs and the volume of operational records increase, exhaustive manual review becomes expensive and difficult to scale.

### 2.2 The Core Question
The system must answer: given periodic operational evidence from a CSE, which entities, workflows, controls, cases and alert samples deserve supervisory attention, and what evidence supports that recommendation?

### 2.3 Problem in First-Principles Terms
```
DECLARED CAPABILITY  ->  "We investigate and escalate important alerts."
OPERATIONAL EVIDENCE ->  alerts -> investigation -> escalation -> response -> closure
SUPERVISORY ANALYSIS ->  expected behavior vs observed behavior + missing evidence + peer context
OUTPUT               ->  evidence-backed priority for human supervisory review
```

### 2.4 Why Ordinary Dashboards Are Insufficient
A KPI such as "98% of alerts closed within SLA" describes a measurable process outcome but may not establish that investigations were meaningful. Likewise, a very low number of critical alerts can indicate genuinely low activity or a monitoring blind spot. The system must therefore avoid equating low volume, high closure rates or good SLA performance with effective security operations without contextual evidence.

---

## 3. Goals and Success Outcomes

- Scale supervisory analysis across multiple CSEs and time periods.
- Prioritize entities and samples for human review rather than forcing supervisors to inspect everything.
- Detect evidence-backed execution-gap indicators.
- Detect negative-space and potential monitoring-coverage gaps without treating absence as proof of failure.
- Identify anomalous, outlier and suspicious operational patterns.
- Perform context-aware peer comparison and benchmarking.
- Provide entity-level supervisory risk/attention indicators.
- Make every important finding traceable to underlying evidence and analytical reasoning.
- Operate fully offline inside a controlled environment.
- Support reproducible validation against expert-labelled or controlled ground truth.
- Demonstrate measurable review-efficiency improvement.

### 3.1 Build-Priority Tiers *(new in v2.0)*

Every requirement in Sections 7 and 17 carries one of these tags. This is the single most important addition in this revision — without it, every requirement below defaults to equal weight, which is how teams end up with ten shallow features instead of five that actually work.

| Tier | Meaning | Rule of thumb |
|---|---|---|
| **P0 — Demo-critical** | Must exist and work for the core "wow moment" (CSE-B example, §20) to be true and reproducible. | If cutting it breaks the demo story, it's P0. |
| **P1 — Stretch** | Strengthens the pitch and shows depth, but the demo survives without it. | Build only after every P0 item is working end-to-end. |
| **P2 — Production-only** | Correct for a real NCIIPC deployment; out of scope for a prototype timeline. | Mention in the pitch as "designed for, not yet built." |

**Assumed capacity for this tiering** *(state your actual numbers here before freezing scope)*: a team of 4–6 people building over a single SIH cycle (hackathon sprint + a short pre-finals hardening window). If your actual team size or timeline differs materially, re-run the tiering — P0 should always be the largest subset your team can finish and demo reliably with time left for rehearsal, not the largest subset that sounds impressive.

---

## 4. Non-Goals / Explicit Exclusions

- The system is not a Security Operations Centre.
- The system is not a SIEM or replacement for a SIEM.
- The system does not perform real-time network monitoring.
- The system does not continuously collect telemetry from CSEs.
- The system is not a centralized national cyber-monitoring platform.
- The system does not automatically declare a CSE secure/insecure.
- The system does not replace expert supervisory judgement.
- The system does not require raw packet captures, customer information, or sensitive operational data unless justified.
- The system does not rely on cloud-hosted AI models, SaaS services or internet connectivity.
- The system does not use an LLM as the authoritative decision engine, and does not use an LLM to generate free-text explanations that could invent evidence *(clarified in v2.0 — see §12.1)*.

---

## 5. Stakeholders and Personas

| Persona | Primary Need | Key Actions | Tier |
|---|---|---|---|
| Supervisory Examiner | Rapidly identify what deserves attention | Review findings, inspect evidence, accept/reject/escalate findings | P0 |
| Assessment Analyst | Investigate patterns and prepare assessment material | Filter, drill down, compare peers, export reports | P0 |
| System Administrator | Operate the platform safely in an air-gapped environment | Manage users, configurations, models, rules and deployments | P1 |
| Auditor | Verify traceability and governance | Inspect audit logs, model/ruleset versions, evidence provenance | P2 |
| Domain Expert | Validate analytical signals | Label controlled data, review findings, tune expectations/thresholds | P0 (needed for validation, §19) |
| Development/Validation Team | Prove technical performance | Run test datasets, benchmarks, regression tests and validation experiments | P0 |

---

## 6. Major Use Cases

| ID | Use Case | Description | Tier |
|---|---|---|---|
| UC-01 | Import periodic CSE operational data | Supervisor uploads CSV/JSON/database export or invokes an approved local API ingestion path. | P0 |
| UC-02 | Validate data quality | System checks completeness, duplicates, timestamps, referential integrity, field validity and coverage. | P0 |
| UC-03 | Reconstruct operational workflows | System links alerts to investigations, cases, escalations, actions and closures where identifiers permit. | P0 |
| UC-04 | Detect execution gaps | System identifies suspicious workflow shortcuts, unusually fast closures, missing escalation, repetitive investigation evidence and unresolved recurrence. | P0 (subset — see §7.4 tiers) |
| UC-05 | Detect negative space | System identifies expected-but-missing evidence using asset inventory, peer context, historical baselines and data-quality checks. | P0 (subset — see §7.5 tiers) |
| UC-06 | Benchmark peers | System compares CSE behavior against contextually similar entities rather than a universal threshold. | P0 |
| UC-07 | Prioritize manual review | System ranks entities, processes and alert/case samples by supervisory attention priority. | P0 |
| UC-08 | Explain a finding | Supervisor opens a finding and sees evidence, calculations, peer context, data quality, supporting and contradicting signals. | P0 |
| UC-09 | Record supervisory decision | Reviewer marks finding as confirmed, false positive, needs investigation or insufficient evidence. | P1 |
| UC-10 | Generate assessment report | System produces an auditable report with findings, evidence references, methodology and limitations. | P1 |

---

## 7. Functional Requirements

Each requirement now carries a **Tier** (see §3.1). Read the tier before the requirement text — it tells you whether to build it this week or mention it in the pitch deck.

### 7.1 Data Ingestion

| ID | Requirement | Tier |
|---|---|---|
| FR-001 | Multi-source ingestion — ingest structured data from multiple CSEs and multiple reporting periods. | P0 |
| FR-002 | Supported formats — support CSV and JSON as baseline formats; DB exports/APIs only if trivially available. | P0 (CSV/JSON only); P2 (live API/DB export) |
| FR-003 | Bulk ingestion — allow multiple files/datasets to be uploaded and associated with a CSE, period and dataset version. | P0 |
| FR-004 | Schema mapping — map source-specific columns to a canonical SAT-SA data model without modifying source evidence. | P0 |
| FR-005 | Data provenance — store source file identifier, import time, dataset version, source period and transformation version. | P0 |
| FR-006 | Duplicate protection — detect duplicate records and avoid double-counting unless explicitly configured. | P1 |
| FR-007 | Incremental processing — permit new reporting periods to be analyzed without destroying prior-period evidence. | P1 |

### 7.2 Data Trust / Quality Layer

| ID | Requirement | Tier |
|---|---|---|
| FR-010 | Completeness analysis — calculate missingness for required and optional fields. | P0 |
| FR-011 | Consistency checks — validate timestamps, severity values, status transitions, foreign-key relationships and categorical domains. | P0 |
| FR-012 | Coverage analysis — estimate evidence coverage for critical assets, alert classes, investigation records and escalation records when the relevant data exists. | P0 |
| FR-013 | **Data quality score** — produce a transparent data-quality assessment that affects finding confidence, computed as (see formula, §7.2.1). | P0 |
| FR-014 | Quality-aware inference — prevent a missing-data condition from being interpreted as a genuine operational absence without sufficient evidence. | P0 |
| FR-015 | Quality warnings — show supervisors when a conclusion may be weakened by incomplete or unreliable source data. | P0 |

**7.2.1 Data Quality Score — pinned formula *(new in v2.0; was previously an unspecified "92%")***

```
DataQualityScore(dataset) =
    0.35 · CompletenessRatio        (1 − missing_required_fields / total_required_fields)
  + 0.25 · ConsistencyRatio         (1 − failed_validation_checks / total_validation_checks)
  + 0.25 · CoverageRatio            (observed_evidence_records / expected_evidence_records, capped at 1.0)
  + 0.15 · SampleSufficiencyRatio   (min(1.0, actual_sample_size / minimum_sample_size))

Weights are configuration, not constants — store in the rulesets table (§24) and version them.
Minimum sample size default: 30 records per evidence category per reporting period (tune during validation).
Report the score AND its four components in the UI — never the blended number alone.
```

### 7.3 Canonical Evidence Model

| ID | Requirement | Tier |
|---|---|---|
| FR-020 | Entity model — represent CSEs, assets, alerts, cases, investigations, escalations, dispositions and closures as linked entities. | P0 |
| FR-021 | Workflow reconstruction — construct event sequences using available IDs, timestamps and relationships. | P0 |
| FR-022 | Evidence graph — maintain traceable relationships from supervisory finding to source records. | P0 |
| FR-023 | Temporal modeling — preserve event ordering and calculate durations and transition intervals. | P0 |
| FR-024 | Evidence provenance — every finding must retain references to the records and analytical components that produced it. | P0 |

### 7.4 Execution Gap Analytics

| ID | Requirement | Tier |
|---|---|---|
| FR-030 | **Fast closure detection** — pinned formula, §7.4.1. | P0 |
| FR-031 | Investigation sufficiency indicators — detect cases with minimal, repetitive or template-like investigation evidence where data supports such analysis. | P1 |
| FR-032 | **Escalation gap detection** — pinned formula, §7.4.1. | P0 |
| FR-033 | **Repeated unresolved alerts** — pinned formula, §7.4.1. | P0 |
| FR-034 | Workflow shortcut detection — identify suspiciously compressed or skipped workflow transitions. | P1 |
| FR-035 | Metric-quality analysis — identify cases where KPI performance may be inconsistent with deeper operational evidence. | P1 (this is the "CSE-B" demo moment — build if any P1 budget exists at all) |
| FR-036 | Persistence analysis — distinguish one-off anomalies from repeated patterns across periods. | P1 |

**7.4.1 P0 Execution-Gap Detectors — pinned formulas *(new in v2.0; replaces vague "contextually appropriate baselines")***

```
Let peer_median(x) and peer_MAD(x) be computed over the CSE's peer group (§7.7) for metric x,
with a minimum peer-group size of 5 (below this, fall back to the global population and flag
low-confidence).

FR-030 Fast closure:
  flag if  severity = CRITICAL/HIGH
       AND closure_duration < peer_median(closure_duration) − 2.5 · peer_MAD(closure_duration)
       AND evidence_count(investigation) < peer_p25(evidence_count)

FR-032 Escalation gap:
  flag if  severity = CRITICAL
       AND escalation_expected(asset_criticality, alert_category) = TRUE   [see FR-042 expectation model]
       AND no escalation record exists for the case

FR-033 Repeated unresolved alerts:
  flag if  count(alerts on same asset_id, same alert_category) >= 3
       AND within a 30-day rolling window
       AND no remediation action record links to any of those alerts

All three write their contributing record IDs into finding_evidence (§24) — no detector may
produce a finding without at least one linked evidence record.
```

### 7.5 Negative Space Analytics

| ID | Requirement | Tier |
|---|---|---|
| FR-040 | Expected evidence model — pinned in §7.5.1. | P0 |
| FR-041 | **Coverage gap detection** — pinned formula, §7.5.1. | P0 |
| FR-042 | Context-aware absence — consider environment size, asset criticality, historical baseline, peer behavior and data quality before raising a negative-space signal. | P0 |
| FR-043 | Uncertainty handling — represent negative-space results as potential blind spots rather than definitive failures. | P0 |
| FR-044 | Alternative explanations — display plausible non-failure explanations where available, such as data-source gaps or operational changes. | P1 |

**7.5.1 Expected Evidence Model & Coverage Gap — pinned definition *(new in v2.0)***

```
ExpectedEvidenceCount(asset) = f(asset_criticality_tier, historical_baseline, peer_median_alert_rate)
  — for the prototype, use the simplest defensible version:
    expected = peer_median(alerts_per_asset | same criticality_tier, same sector)

CoverageRatio(asset) = observed_alerts(asset) / max(expected, 1)

FR-041 flag condition:
  flag if  asset_criticality_tier IN {CRITICAL, HIGH}
       AND CoverageRatio(asset) < 0.3
       AND DataQualityScore(source feeding this asset) > 0.7   [i.e., low coverage is NOT explained
                                                                  by a known data-quality problem]

If DataQualityScore <= 0.7 for the relevant source, do not raise a negative-space finding —
raise a data-quality warning instead (FR-015). This ordering is the single most important rule
in the whole negative-space engine: never let a data pipeline failure masquerade as a security finding.
```

### 7.6 Behavioral / Temporal Analytics

| ID | Requirement | Tier |
|---|---|---|
| FR-050 | Time-series analysis — analyze operational behavior across multiple periods. | P1 |
| FR-051 | Distribution analysis — analyze severity, closure duration, escalation rates, investigation depth and recurrence distributions. | P0 (needed to compute peer_median/MAD above) |
| FR-052 | Change-point detection — detect material changes in operational behavior between periods. | P2 |
| FR-053 | Sequence analysis — identify unusual workflow sequences and repeated operational patterns. | P2 |
| FR-054 | Outlier analysis — identify statistical outliers while retaining context and sample-size information. | P0 (this is what FR-030/032/033 already use — don't build a separate generic version, just expose the same primitives) |

### 7.7 Peer Benchmarking

| ID | Requirement | Tier |
|---|---|---|
| FR-060 | Peer grouping — group CSEs using relevant contextual features such as sector, scale, asset count, alert volume and SOC operating characteristics. | P0 |
| FR-061 | Peer comparison — compare behavior against appropriate peer distributions rather than universal thresholds. | P0 |
| FR-062 | Robust benchmarking — use robust statistics and a **minimum peer-group size of 5** *(pinned in v2.0 — was previously unspecified)*; below this, fall back to global population and mark the comparison low-confidence. | P0 |
| FR-063 | Peer explanation — show why an entity differs from its peer group and the uncertainty of the comparison. | P0 |

### 7.8 Evidence Fusion and Prioritization

| ID | Requirement | Tier |
|---|---|---|
| FR-070 | Multi-signal fusion — combine rule-based, statistical, temporal, peer and data-quality signals into a supervisory attention score. Formula in §10.5. | P0 |
| FR-071 | Separate evidence confidence — distinguish analytical/finding confidence (§7.2.1-style formula) from model confidence and from source-data quality. Never merge these into one number without showing components. | P0 |
| FR-072 | Priority ranking — rank entities, controls/processes and individual samples for review. | P0 |
| FR-073 | Evidence thresholding — do not produce high-priority findings from weak evidence alone (minimum: 2 independent contributing signals, sample size >= minimum from §7.2.1). | P0 |
| FR-074 | Contradicting evidence — display signals that reduce confidence or offer an alternative explanation. | P1 |
| FR-075 | **Review-efficiency metric** — measure how many expert-identified important samples are captured within a chosen review budget. This is your headline demo number — build and test it early, not last. | P0 |

### 7.9 Explainability and Auditability

| ID | Requirement | Tier |
|---|---|---|
| FR-080 | Finding rationale — every material finding shall state why it was generated. | P0 |
| FR-081 | Evidence references — allow drill-down to underlying records and aggregated evidence. | P0 |
| FR-082 | Method trace — show whether a finding came from deterministic rules, statistical analysis, ML, peer comparison or a combination. | P0 |
| FR-083 | Version traceability — record model version, ruleset version, schema version and dataset version. | P1 |
| FR-084 | Human decision — allow supervisors to record review outcomes and comments. | P1 |
| FR-085 | Immutable history — preserve the historical state of reviewed findings and decisions for audit purposes. | P2 |

**12.1 Explanation rendering — clarified in v2.0:** finding rationale text (FR-080) MUST be produced by deterministic template substitution over computed values (e.g., `"{n} critical alerts, {m} closed below baseline"` with n/m substituted from real query results) — **not** by an LLM or any generative text model, local or remote. This closes a loophole left open by the original document, which discussed an "optional local model" for narrative polish elsewhere but never explicitly forbade it inside the SRS. Templates cannot hallucinate a number that didn't come from a query; a language model can.

### 7.10 Reporting

| ID | Requirement | Tier |
|---|---|---|
| FR-090 | Dashboard — provide entity-level, trend-level and finding-level supervisory dashboards. | P0 |
| FR-091 | Drill-down — allow navigation from a high-level finding to the exact evidence supporting it. | P0 |
| FR-092 | Reports — generate supervisory reports with methodology, findings, evidence, confidence and limitations. | P1 |
| FR-093 | Export — support controlled export to common report formats such as PDF and structured JSON/CSV where appropriate. | P1 |
| FR-094 | Reproducibility — allow a report to be regenerated from the same dataset and analysis version. | P1 |

---

## 8. High-Level System Architecture

The architecture is deliberately layered. The analytical core, rather than the UI or an AI chatbot, is the primary innovation. The system is designed for a local NCIIPC-controlled environment.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         SAT-SA SUPERVISORY PLATFORM                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  Presentation Layer            React + TypeScript dashboard/findings/evidence│
├─────────────────────────────────────────────────────────────────────────────┤
│  Application & Governance      FastAPI | RBAC | workflow | review | audit   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Supervisory Intelligence      Execution Gap | Negative Space | Peer | Fusion│
├─────────────────────────────────────────────────────────────────────────────┤
│  Evidence / Analytics Layer    canonical model | workflow | stats | ML       │
├─────────────────────────────────────────────────────────────────────────────┤
│  Data Trust Layer              completeness | consistency | coverage        │
├─────────────────────────────────────────────────────────────────────────────┤
│  Data Layer                    PostgreSQL | versioned datasets              │
├─────────────────────────────────────────────────────────────────────────────┤
│  Local Infrastructure          NCIIPC-controlled server/VM | no Internet    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 8.1 Component Responsibilities

| Component | Responsibility | Design Principle | Tier |
|---|---|---|---|
| Ingestion Service | Import and version source data | Never overwrite source evidence | P0 |
| Data Trust Engine | Assess data quality and coverage | Absence is not automatically failure | P0 |
| Canonical Evidence Store | Normalize and relate operational records | Evidence-first model | P0 |
| Workflow Reconstruction | Build alert→investigation→escalation→closure sequences | Temporal and referential integrity | P0 |
| Execution Gap Engine | Detect operational execution anomalies | Context + evidence | P0 |
| Negative Space Engine | Detect expected-but-missing evidence | Coverage + uncertainty | P0 |
| Temporal Engine | Find persistent changes and sequences | Behavior over time | P2 |
| Peer Engine | Contextual benchmark | Comparable entities only | P0 |
| Evidence Fusion Engine | Combine signals | Transparent scoring | P0 |
| Priority Engine | Rank review targets | Optimize reviewer attention | P0 |
| Explainability Service | Generate evidence-backed explanations | No unsupported claims, template-only text | P0 |
| Review Service | Capture human decisions | Human remains decision authority | P1 |
| Reporting Service | Generate reproducible reports | Versioned outputs | P1 |
| Audit Service | Track actions/configuration | Tamper-evident provenance | P2 |

---

## 9. Canonical Data Model

The canonical model is the foundation of the project. A weak implementation would simply load arbitrary CSV columns and run an ML model. The intended implementation reconstructs operational evidence and relationships.

```
CSE
 ├── Asset
 │    └── Criticality / environment / expected monitoring coverage
 ├── Alert
 │    ├── Investigation
 │    ├── Case
 │    │    ├── Escalation
 │    │    ├── Response actions
 │    │    └── Closure / disposition
 │    └── recurrence / related alerts
 └── Reporting Period
```

| Entity | Representative Fields | Purpose |
|---|---|---|
| CSE | cse_id, sector, scale, reporting_period | Entity context and peer grouping |
| Asset | asset_id, criticality, type, environment | Expected evidence and coverage reasoning |
| Alert | alert_id, timestamp, severity, source, asset_id, status | Primary operational event |
| Investigation | investigation_id, alert_id, start/end, analyst, evidence_count, disposition | Investigation behavior |
| Case | case_id, alert_id, opened/closed, severity, outcome | Case lifecycle |
| Escalation | escalation_id, case_id, timestamp, level, target | Escalation evidence |
| Action | action_id, case_id, type, timestamp, outcome | Response/remediation evidence |
| Closure | closure_id, case_id, timestamp, reason, reviewer | Closure quality and speed |
| TelemetryCoverage | asset/category, expected, observed, period | Negative-space/coverage reasoning |
| Finding | finding_id, type, score, confidence, evidence_refs | Supervisory output |
| ReviewDecision | finding_id, decision, reviewer, timestamp, notes | Human validation loop |

---

## 10. Supervisory Analytics Methodology

### 10.1 Evidence-to-Assurance Pipeline
```
SOURCE DATA → DATA TRUST/QUALITY → CANONICALIZATION → WORKFLOW RECONSTRUCTION
  → EXPECTED BEHAVIOR MODEL
      ├── EXECUTION GAP ANALYSIS
      ├── NEGATIVE SPACE ANALYSIS
      ├── TEMPORAL/BEHAVIORAL ANALYSIS (P1/P2)
      └── PEER BENCHMARKING
  → EVIDENCE FUSION → SUPERVISORY PRIORITY RANKING → EVIDENCE-BACKED FINDING
  → HUMAN REVIEW → VALIDATION/FEEDBACK
```

### 10.2 Execution Gap Model
Execution-gap detection compares an expected operational behavior with observed evidence. The expectation may come from explicitly configured supervisory criteria, domain rules, historical behavior, or a peer baseline. See §7.4.1 for the pinned P0 formulas (fast closure, escalation gap, repeated unresolved alerts).

- **Premature closure** — severe alert closes substantially faster than an appropriate baseline and lacks supporting investigation evidence.
- **Missing escalation** — event severity/context suggests escalation should be expected but no corresponding evidence exists.
- **Repetitive investigation** *(P1)* — many cases show unusually similar investigation structure with little case-specific evidence.
- **Repeated unresolved alert** — the same asset repeatedly generates materially similar alerts without visible remediation evidence.
- **Metric-outcome divergence** *(P1)* — strong SLA/KPI results coexist with weak investigation, escalation or remediation evidence.

### 10.3 Negative Space Model
Negative-space analytics is not simple missing-value detection. It is reasoning about the absence of expected operational evidence. The system must first establish whether the relevant evidence source is itself sufficiently complete before interpreting absence (see §7.5.1's ordering rule — data-quality gate before negative-space flag).

```
Expected Evidence → Data Availability/Trust → Observed Evidence → Coverage Gap
  → Context + Peer Baseline + Historical Baseline → Potential Negative-Space Signal
  → Human Supervisory Review
```

### 10.4 Peer Benchmarking
Universal thresholds are unsafe because CSEs differ in scale, asset count, alert volume, sector and SOC operating model. Peer benchmarking should therefore use contextually similar groups and robust statistics (minimum group size 5, §7.7).

```
CSE A: 10,000 alerts/month
CSE B:    500 alerts/month   => raw counts are not directly comparable.

Prefer normalized measures and peer distributions:
closure time | escalation rate | recurrence rate | investigation depth | coverage ratio
```

### 10.5 Evidence Fusion — pinned formula *(concretized in v2.0)*

The original document described fusion only conceptually ("weighted evidence signals + persistence + peer deviation..."). Pinned version for the prototype:

```
PriorityScore(finding) =
    0.30 · SignalStrength      (number of independent detectors that fired, normalized 0–1, capped at 3 signals)
  + 0.25 · PeerDeviation       (|z-score| vs peer distribution, capped at 3.0, normalized 0–1)
  + 0.20 · Persistence         (fraction of recent reporting periods showing the same signal)
  + 0.15 · AssetCriticality    (normalized criticality tier of the affected asset)
  - 0.10 · DataUncertainty     (1 − DataQualityScore for the contributing source, §7.2.1)

FR-073 threshold: do not surface as "high priority" unless SignalStrength implies >= 2
independent detectors AND DataQualityScore(contributing source) > 0.6.

All five components must be shown in the UI alongside the blended score — never the
blended score alone. This is a direct fix to the confidence-formula gap flagged in the
prior review: the platform must not display a percentage that no one can recompute.
```

Weights and thresholds must be versioned configuration (rulesets table, §24), not hidden constants.

---

## 11. AI / ML Role

AI is an augmentation layer, not the foundation of trust. The system should first establish deterministic evidence relationships and transparent statistical signals. ML is then used where it provides measurable value over rules and classical statistics.

### 11.1 Appropriate AI Roles (P1/P2 — not required for P0 demo)
- Unsupervised anomaly detection for multidimensional operational behavior.
- Sequence modeling or clustering to identify recurring workflow patterns.
- Representation learning for similar operational cases where structured features are insufficient.
- Outlier detection across peer-normalized feature spaces.
- Optional supervised ranking/classification after enough validated labels exist.
- Assisted discovery of previously unknown patterns for expert review.

**v2.0 note:** the P0 detectors in §7.4.1/§7.5.1 are deliberately deterministic/statistical, not ML. Do not let ML be a P0 dependency — a robust z-score/MAD detector that works beats an Isolation Forest you didn't have time to validate.

### 11.2 AI Roles That Should Be Avoided
- Using an external LLM API to decide whether a CSE is compliant.
- Allowing generated natural-language explanations to invent evidence (see §12.1 — template-only rendering).
- Treating model confidence as equivalent to evidentiary confidence.
- Training a black-box model on synthetic artifacts and presenting its output as production truth.

### 11.3 Recommended AI Architecture (P1/P2)
```
Structured Features (temporal, workflow, severity/closure, recurrence, coverage, peer-normalized)
  → Baselines/Rules + ML Anomaly Model → Evidence Fusion → Review Prioritization
```
For an SIH prototype, scikit-learn methods such as Isolation Forest, robust distance/outlier methods and interpretable classifiers are sufficient starting points, and are P1 — the P0 detectors do not require them. More complex sequence models should only be introduced if experiments show a clear improvement over the P0 baseline.

---

## 12. Explainability Model

A supervisory system must be defensible. The target output is not "AI says high risk." The target output is a structured finding whose reasoning can be inspected.

```
Finding: Potential Critical-Alert Handling Execution Gap
Priority: HIGH
Why flagged:
  • 17 critical alerts in sample
  • 14 closed below contextual duration baseline
  • 11 lack escalation evidence
  • 9 contain minimal investigation evidence
  • pattern persists across 4 reporting weeks
  • behavior is materially different from peer distribution
Data quality: 92%   [now traceable to §7.2.1's four components — never a bare number]
Contradicting evidence: small sample for one subcategory
Recommended action: manual supervisory review
```

The exact numbers above are illustrative UI content only; the implementation must calculate actual values from the dataset using the formulas in §7.2.1, §7.4.1, §7.5.1 and §10.5. Every production/demo claim must be generated from reproducible experiments — never typed in by hand for a slide.

See §12.1 (under §7.9) for the template-only rendering rule.

---

## 13. End-to-End Operational Workflow

1. Supervisor authenticates locally.
2. Supervisor creates or selects a CSE and reporting period.
3. Supervisor uploads a source dataset.
4. System fingerprints and versions the source package.
5. Data Trust Layer validates schema, completeness, duplicates, timestamps and relationships.
6. System displays data-quality and coverage warnings before analysis.
7. Canonicalization maps source records into the evidence model.
8. Workflow reconstruction links alerts, investigations, cases, escalations, actions and closures.
9. Analytical engines execute deterministic, statistical and optional ML analyses.
10. Peer engine establishes appropriate comparison context.
11. Evidence Fusion Engine combines signals and uncertainty.
12. Priority engine ranks entities, processes and samples.
13. Supervisor opens a finding and drills into evidence.
14. Supervisor records a decision and optional explanation. *(P1)*
15. System preserves audit trail and produces a report. *(P1/P2)*
16. Validation subsystem aggregates reviewer decisions for future threshold/model evaluation. *(P2)*

---

## 14. User Interface Requirements

| Screen | Required Information | Primary Interaction | Tier |
|---|---|---|---|
| Home / Assessment Overview | CSEs, periods, attention priorities, data quality | Select assessment | P0 |
| Data Intake | Files, schemas, validation status, provenance | Upload/map/validate | P0 |
| Data Trust | Missingness, duplicates, coverage, warnings | Inspect quality | P0 |
| Supervisory Overview | Top findings, entity priorities, trends | Filter/drill | P0 |
| Entity Profile | Behavior, peer comparison, findings, trends | Inspect CSE | P0 |
| Finding Detail | Rationale, evidence, drivers, contradictions | Review evidence | P0 |
| Case/Alert Evidence | Underlying records and workflow timeline | Inspect source evidence | P0 |
| Peer Benchmark | Peer group, normalized metrics, distribution | Compare | P0 |
| Review Queue | Prioritized samples | Mark review status | P1 |
| Reports | Generated reports and versions | Export/view | P1 |
| Administration | Users, roles, rules, thresholds, model versions | Manage | P2 |
| Audit Trail | User actions, configuration and finding history | Audit | P2 |

---

## 15. Security Architecture *(split into two tiers in v2.0 — was previously one undifferentiated list)*

The platform processes sensitive cybersecurity operational data, so its target production posture must assume the application is a high-value local asset. **However, building the full list below for a prototype demo is a scope trap** — it competes directly for time against the analytics engines that are the actual differentiator. Build the Hackathon Baseline; document the Production Target as a roadmap item.

### 15.1 Hackathon Security Baseline (P0)
- Local authentication (single mechanism, e.g. hashed-password + session token).
- Role-based access control as a simple role column/table (supervisor, analyst, admin) — enforce at the API layer.
- Basic audit log table: who did what, when (imports, finding reviews, exports).
- Strict file validation on upload (file type, size limit, malformed-CSV handling).
- No outbound network calls anywhere in the codebase (verify with a dependency/network audit before the demo).

### 15.2 Production Target (P2 — describe, don't build)
- Full RBAC with a dedicated auditor role and least-privilege DB roles.
- Encryption at rest with platform-managed keys.
- TLS for local service-to-service communication.
- Path traversal / malicious archive / oversized-file protections beyond basic validation.
- Model/ruleset integrity verification using cryptographic hashes.
- Dependency pinning and an offline package repository strategy for controlled updates.
- Controlled export with user attribution and report versioning.

---

## 16. Air-Gapped / Offline Deployment Requirements

```
NCIIPC CONTROLLED ENVIRONMENT
  ├── Frontend server
  ├── Backend/API
  ├── PostgreSQL
  ├── Local analytics/ML runtime
  ├── Local report generator
  └── Local model/ruleset registry

NO INTERNET · NO CLOUD AI API · NO SaaS · NO EXTERNAL DATABASE · NO REMOTE MODEL INFERENCE
```

- All inference must execute locally. **(P0 — verify, don't just assert)**
- All dependencies must be installable from approved offline media/repository. **(P1)**
- Model updates must be imported through controlled, integrity-checked packages. **(P2)**
- The application must continue to operate when DNS/internet access is unavailable. **(P0 — test this explicitly before the demo)**
- Outbound network connections should be denied by default. **(P0)**

---

## 17. Non-Functional Requirements

| ID | Requirement | Target / Principle | Tier |
|---|---|---|---|
| NFR-001 | Offline operation | 100% core functionality without Internet | P0 |
| NFR-002 | Explainability | 100% material findings have evidence references and rationale | P0 |
| NFR-003 | Auditability | Versioned dataset, ruleset, model and finding history | P2 |
| NFR-004 | Scalability | Support large multi-CSE datasets; benchmark actual tested limits | P1 (benchmark at whatever size you actually test — don't extrapolate) |
| NFR-005 | Performance | Document ingestion/analysis latency for defined dataset sizes | P1 |
| NFR-006 | Reliability | Repeatable analysis should produce consistent outputs for fixed versions | P0 |
| NFR-007 | Security | RBAC, secure parsing, local authentication and audit logs | P0 (Hackathon Baseline, §15.1 only) |
| NFR-008 | Maintainability | Modular analytics engines and versioned configuration | P1 |
| NFR-009 | Portability | Deployable on controlled Linux/VM infrastructure | P1 |
| NFR-010 | Usability | Supervisor can move from finding to source evidence with minimal navigation | P0 |
| NFR-011 | Data integrity | Source evidence remains immutable/versioned | P1 |
| NFR-012 | Model governance | No untracked model or threshold changes | P2 |
| NFR-013 | Accessibility | Readable dashboards, keyboard-friendly controls and clear severity semantics | P1 |

---

## 18. Recommended Technology Stack

Technology selection is intentionally conservative. The project should not use Kubernetes, Kafka, Spark, large GPU clusters or paid AI APIs unless measured workload requirements justify them. Engineering depth should come from the supervisory analytics methodology rather than unnecessary infrastructure complexity.

| Layer | Recommended Technology | Reason |
|---|---|---|
| Frontend | React + TypeScript | Mature, maintainable dashboard architecture |
| Backend | Python + FastAPI | Strong data/ML ecosystem and clear API layer |
| Database | PostgreSQL | Reliable relational evidence model and auditability |
| Data Processing | Polars / Pandas | Efficient structured-data processing |
| Statistics | NumPy / SciPy | Transparent statistical analysis |
| ML | scikit-learn; optional XGBoost | Offline, open-source, reproducible (P1 only) |
| Visualization | Apache ECharts | Interactive dashboards and distributions |
| Reports | ReportLab / HTML templates | Local report generation (P1) |
| Packaging | Docker Compose for prototype | Reproducible local deployment |
| Testing | pytest + API/UI test framework | Automated validation |

---

## 19. Validation and Evaluation Strategy

The problem statement requires validation against findings derived from expert manual review. Because real NCIIPC CSE data may not be available to a student team, the prototype must clearly distinguish controlled validation from production validation.

### 19.1 Controlled Synthetic Dataset
- Generate multiple synthetic CSEs with different scale, asset criticality and alert volumes.
- Create realistic alert→investigation→case→escalation→closure relationships.
- Inject known supervisory patterns with explicit ground truth.
- Generate normal behavior distributions and realistic noise.
- Inject missing-data conditions separately from genuine negative-space conditions.
- Create peer groups with different operational baselines.

### 19.2 Ground-Truth Scenarios

| Scenario | Ground Truth | Expected Detection |
|---|---|---|
| Normal operation | No supervisory weakness | Low priority / no finding |
| Rapid critical closures | Execution gap | Fast-closure signal |
| Critical alerts without escalation | Execution gap | Escalation-gap signal |
| Repeated alerts without remediation | Execution gap | Recurrence/remediation signal |
| Template-like investigations | Potential execution gap | Repetition signal |
| Critical assets with weak evidence coverage | Potential negative space | Coverage signal |
| Missing alert category with adequate source coverage | Potential negative space | Absence signal |
| Low activity explained by data outage | No operational conclusion | Data-quality warning |
| Metric gaming | Execution gap | KPI-outcome divergence |

### 19.3 Quantitative Metrics
- Precision, recall and F1 for controlled ground-truth findings.
- False-positive rate.
- Top-K recall: fraction of expert-important cases captured in the top K review recommendations.
- Mean reciprocal rank or equivalent ranking metric for prioritized review lists.
- Supervisory Review Yield: meaningful findings per unit of review effort.
- Review reduction: fraction of records/cases avoided while retaining a target proportion of important cases.
- Explanation coverage: percentage of findings with complete evidence traces.
- Reproducibility: consistency across repeated runs with fixed versions.

The prototype must never invent benchmark numbers. All reported performance figures must be produced by the actual test runs and include dataset description, scenario composition and limitations.

### 19.4 Generator/Detector Independence Protocol *(new in v2.0 — closes the circularity gap)*

**The problem:** if the synthetic-data generator injects "execution gap" by literally applying the same threshold the detector checks for (e.g., both use `closure_time < X minutes`), your precision/recall numbers measure whether your code can invert its own arithmetic — not whether the methodology finds real supervisory weaknesses. This was flagged as a risk (§21) but never operationalized as a rule. It is now a hard requirement:

1. **Separate ownership.** The person/sub-team who writes the synthetic-scenario generator must not be the same person who tunes detector thresholds, or must do so from a written scenario spec that does not expose the detector's exact formula.
2. **Parameter decorrelation.** The generator should express anomalies through realistic process simulation (e.g., "this analyst closes tickets fast because they're overloaded, drawing durations from a different, plausible distribution") rather than directly copying the detector's threshold expression.
3. **Held-out scenario families.** At least 20% of ground-truth scenarios must be constructed *after* thresholds are frozen, using parameter ranges not used during threshold tuning, and run exactly once before reporting final numbers.
4. **Report both numbers.** Show precision/recall on (a) the tuning set and (b) the held-out set separately. A large gap between them is itself a finding worth disclosing, not hiding.
5. **Never claim more than this earns you.** The honest framing for judges: "on controlled synthetic data with held-out scenario validation, not on real NCIIPC data" — exactly as §31's Q&A already states, but now backed by an actual procedure instead of only a disclosure sentence.

---

## 20. Demonstration Design

The strongest demonstration should expose a situation where conventional KPI reporting appears healthy but the operational evidence creates a legitimate supervisory question.

```
Dashboard view:
CSE-B — SLA compliance: 99%
Looks healthy.

SAT-SA supervisory attention: HIGH

Click →
  critical alerts closed unusually fast
  + missing escalation evidence
  + low investigation evidence
  + repeated alerts on same assets
  + peer deviation
  + persistence across periods
  - data quality caveat

Recommendation: Prioritize these 20 cases for human review.
```

This is not a claim that CSE-B is insecure. It demonstrates the value of the platform: converting large volumes of operational evidence into a defensible, prioritized supervisory question. **Build §7.4.1's FR-030/FR-032/FR-033 and §7.8's FR-070/FR-075 first — everything else in this document exists to support this one moment.**

---

## 21. Risk Register and Mitigations

| Risk | Severity | Why It Matters | Mitigation |
|---|---|---|---|
| No real NCIIPC data | High | Cannot claim production validity | Controlled synthetic data + transparent limitation + expert-labelled validation framework |
| Missing data interpreted as failure | High | Negative-space false positives | Data Trust Layer + coverage model + uncertainty + human review (see §7.5.1 gating order) |
| Peer groups unfair | High | Different CSE environments | Contextual grouping + normalization + minimum sample size (§7.7) |
| Black-box AI | High | Poor supervisory defensibility | Rules/statistics first + interpretable ML + evidence traces |
| LLM hallucination | High | Unsupported conclusions | No external LLM; template-only rendering (§12.1); structured evidence is authoritative |
| Synthetic data too clean | Medium | Inflated results | Noise injection, realistic distributions, and the Independence Protocol (§19.4) |
| Overfitting to injected scenarios | Medium | Weak generalization | Held-out scenario families (§19.4), unseen-pattern tests |
| Overengineering | Medium | Delivery risk | Tier system (§3.1) — build P0 only, first |
| Data privacy exposure | High | Sensitive SOC data | Local deployment, RBAC baseline, minimization, secure storage |
| Model drift | Medium | Behavior changes over time | Versioning (P2), periodic recalibration and human validation |
| Metric gaming misinterpretation | Medium | False accusations | Phrase outputs as supervisory signals, not verdicts |
| Poor evidence linkage | High | Loss of trust | Evidence graph and immutable provenance |
| **Scope-vs-timeline mismatch** *(new in v2.0)* | **High** | ~95 requirements at equal priority guarantees shallow coverage | Tier system (§3.1); freeze P0 list before writing any code |
| **Confidence numbers without formulas** *(new in v2.0)* | **High** | Undermines the core "evidence, not AI theater" pitch | Pinned formulas §7.2.1, §10.5 — never display a percentage that can't be recomputed |

---

## 22. Acceptance Criteria

1. A user can import a valid multi-CSE structured dataset entirely offline. **(P0)**
2. The system produces a data-quality/coverage assessment before supervisory analytics are trusted. **(P0)**
3. Alerts, investigations, cases, escalations and closures can be reconstructed when source relationships permit. **(P0)**
4. The prototype detects the defined controlled execution-gap scenarios with measurable performance. **(P0)**
5. The prototype detects controlled negative-space scenarios while distinguishing them from source-data outages. **(P0)**
6. Peer comparisons are context-aware and expose the peer population used. **(P0)**
7. Every high-priority finding contains evidence references and a human-readable rationale. **(P0)**
8. Every finding records dataset/ruleset/model versions. **(P1)**
9. Supervisors can mark findings as confirmed, false positive, needs investigation or insufficient evidence. **(P1)**
10. The system provides a prioritized review queue. **(P0)**
11. The system can generate a reproducible report from a fixed dataset/version. **(P1)**
12. No core functionality requires Internet, cloud, SaaS or external AI APIs. **(P0)**
13. The team can demonstrate a review-efficiency metric on controlled ground truth, including the held-out split from §19.4. **(P0 — this is the number the whole pitch rests on)**
14. The application does not claim to replace SOC operations or supervisory judgement. **(P0)**

---

## 23. Logical API Surface

| Endpoint | Method | Purpose | Tier |
|---|---|---|---|
| /api/auth/login | POST | Local authentication | P0 |
| /api/datasets | POST | Create/import dataset | P0 |
| /api/datasets/{id}/validate | POST | Run data trust checks | P0 |
| /api/datasets/{id}/analysis | POST | Run analysis pipeline | P0 |
| /api/cse | GET | List CSEs | P0 |
| /api/cse/{id}/overview | GET | Entity-level supervisory view | P0 |
| /api/findings | GET | List/filter findings | P0 |
| /api/findings/{id} | GET | Finding detail and evidence | P0 |
| /api/findings/{id}/review | POST | Record supervisory decision | P1 |
| /api/peers/{id} | GET | Peer comparison | P0 |
| /api/reports | POST | Generate report | P1 |
| /api/audit | GET | Audit history | P2 |
| /api/config/rules | GET/PUT | Versioned rules configuration | P1 |
| /api/config/models | GET | Model metadata/version | P2 |

---

## 24. Database / Persistence Design

```
users · roles · cse · reporting_periods · datasets · dataset_versions · assets · alerts
investigations · cases · escalations · actions · closures · coverage_observations
peer_groups · peer_memberships · analytical_features · findings · finding_evidence
finding_signals · review_decisions · rulesets · model_versions · analysis_runs
reports · audit_events
```

Source records and derived analytical records should be logically separated. A dataset version must be immutable after ingestion. Analytical outputs reference the dataset version from which they were computed. The `rulesets` table stores the weights from §7.2.1 and §10.5 as versioned rows, not hardcoded constants.

---

## 25. Model and Rules Governance *(P1/P2 — Hackathon Baseline can defer most of this)*

- Every model has a unique version, training-data description, feature schema, training configuration and evaluation record. **(P2)**
- Every ruleset has a version, author, effective date, rationale and change history. **(P1 — minimally, a version number and a date is enough for the prototype)**
- A model/ruleset cannot silently change the meaning of a historical finding. **(P2)**
- Offline model updates are imported as signed or hash-verified packages. **(P2)**
- Model performance is evaluated on held-out scenarios before activation. **(P0 — this is §19.4, just phrased as governance)**
- Human review outcomes are stored as validation data but are not automatically used for retraining. **(P1)**
- Threshold changes require explicit approval and versioning. **(P2)**

---

## 26. Test Strategy

| Test Level | Examples | Tier |
|---|---|---|
| Unit | Feature calculations, duration logic, peer normalization, evidence linkage | P0 |
| Integration | Ingestion→validation→canonicalization→analytics | P0 |
| API | Authentication, dataset lifecycle, findings, review, reporting | P0 |
| UI | Upload, filtering, drill-down, review workflow | P1 |
| Data Quality | Missing fields, duplicates, malformed timestamps, inconsistent IDs | P0 |
| Security | RBAC, upload abuse, path traversal, authorization, audit logging | P1 (Hackathon Baseline scope only) |
| Model | Precision/recall, calibration, holdout scenarios, reproducibility | P0 |
| Performance | Large-file ingestion, multi-CSE analysis, concurrent users | P1 |
| Offline | No-network operation and dependency verification | P0 |
| Regression | Fixed datasets produce stable outputs across releases | P1 |
| Explainability | Every finding has valid evidence references and reproducible calculations | P0 |

---

## 27. Performance Benchmark Plan

The team must define and publish actual tested limits rather than claiming generic scalability. Benchmark using at least three dataset sizes and record hardware, processing time, peak memory and database size. These are benchmark categories, not claimed capabilities — final numbers must come from actual experiments.

| Benchmark | Example Test Size | Measure | Tier |
|---|---|---|---|
| Small | 100k records | Import time, analysis time, memory | P0 |
| Medium | 1M records | Import time, analysis time, memory | P1 |
| Large | 5M+ records | Import time, analysis time, memory, degradation | P2 |
| Multi-CSE | 10–50 synthetic CSEs | Peer analytics and cross-entity processing | P0 |

---

## 28. Recommended Software Repository Structure

```
sat-sa/
├── frontend/
│   ├── src/pages/
│   ├── src/components/
│   ├── src/features/findings/
│   └── src/features/evidence/
├── backend/
│   ├── api/
│   ├── services/
│   ├── models/
│   ├── repositories/
│   └── security/
├── analytics/
│   ├── data_quality/
│   ├── canonicalization/
│   ├── workflow/
│   ├── execution_gap/
│   ├── negative_space/
│   ├── temporal/
│   ├── peer_benchmark/
│   ├── fusion/
│   └── explainability/
├── ml/
│   ├── features/
│   ├── training/
│   ├── evaluation/
│   └── models/
├── database/
│   ├── migrations/
│   └── seed/
├── datasets/
│   ├── generator/
│   ├── scenarios/
│   └── schemas/
├── reports/
├── tests/
├── docs/
├── deployment/
└── README.md
```

---

## 29. Implementation Roadmap *(re-sequenced around Tiers in v2.0)*

| Phase | Build | Exit Condition | Tier |
|---|---|---|---|
| P0-A — Foundations | Canonical model, schemas, ingestion, data trust layer | Reliable canonical dataset with quality scores | P0 |
| P0-B — Core Detectors | FR-030, FR-032, FR-033, FR-041 (pinned formulas), peer grouping | Controlled scenarios detected on synthetic data | P0 |
| P0-C — Fusion & Priority | Evidence fusion (§10.5), review-efficiency metric (FR-075) | Review queue produces a defensible ranked list | P0 |
| P0-D — Evidence UI | Finding detail, drill-down, peer benchmark screen | End-to-end demo works, reproducibly | P0 |
| P0-E — Validation | Independence Protocol (§19.4), held-out metrics | Real, disclosed precision/recall/top-K numbers | P0 |
| P1-A — Depth | Remaining P1 detectors (FR-031, FR-034–036), review workflow, reports | Stronger pitch, not required for baseline demo | P1 |
| P1-B — Hardening | Hackathon security baseline verification, offline-mode test | Confirmed no network dependency | P1 |
| P2 — Production Vision | Full RBAC/audit/governance, ML layer, scale benchmarking | Described in pitch as roadmap, not built | P2 |

**Do not start P1 work until every P0 exit condition is met and rehearsed as a live demo.** This single sequencing rule is the practical fix for the scope-vs-timeline risk in §21.

---

## 30. Competitive Positioning and Differentiation

The project should not claim that SOC maturity assessment is a new category. Existing maturity frameworks and assessment practices already exist. The defensible distinction is the operational-evidence layer.

| Approach | Primary Question | Operational Evidence | Execution Gaps | Negative Space | Human Supervisory Focus |
|---|---|---|---|---|---|
| Questionnaire / self-assessment | What does the organization report? | Limited | Limited | Limited | Yes |
| SOC maturity assessment | How mature is the capability? | Some | Not exact focus | Not exact focus | Yes |
| SIEM/SOC platform | What security events are occurring? | Yes | Not primary | Not primary | Operational |
| Manual supervisory review | What does evidence reveal? | Yes | Yes | Yes | Yes |
| SAT-SA | Where does operational evidence warrant supervisory attention? | Yes | Core | Core | Core |

The innovation is therefore not "AI + dashboard." It is the combination of evidence reconstruction, expected-vs-observed reasoning, negative-space analysis, peer-aware context, evidence fusion, review prioritization and auditable human decision support in an air-gapped supervisory environment — **provided the P0 tier above is actually built and validated with the independence protocol, not merely described.**

---

## 31. Likely Judge Questions and Defensible Answers

**Q: Isn't this just SOC maturity assessment?**
A: No. Maturity assessment asks how capable/mature a SOC is, often using structured assessment evidence. SAT-SA focuses on operational evidence produced by the SOC and helps supervisors discover execution gaps and missing evidence that may not appear in self-assessment or KPI reporting.

**Q: Isn't this just a dashboard?**
A: No. The dashboard is the presentation layer. The core is a supervisory evidence engine that reconstructs workflows, detects deviations, performs negative-space reasoning, benchmarks peers and provides traceable evidence.

**Q: Why AI?**
A: AI is used only where it adds measurable value for pattern discovery and anomaly detection (P1/P2). The P0 core is deterministic rules and statistics because supervisory findings must be explainable and reproducible.

**Q: How can you validate without real NCIIPC data?**
A: We cannot claim production validation without authorized data. We use controlled synthetic datasets with explicit ground truth, a held-out validation split built independently of the detector thresholds (§19.4), and we report the limitation plainly.

**Q: Does no alert mean no problem?**
A: No. The system explicitly treats missing evidence as a hypothesis. It checks source coverage, context, peer behavior and historical baselines — and gates on data quality first — before raising a negative-space signal.

**Q: Can AI decide that a CSE is failing?**
A: No. The system recommends supervisory attention. The final assessment remains with the human examiner.

**Q: Why not use an LLM?**
A: An LLM is not necessary for the core analytical problem and creates offline, reproducibility and hallucination risks. Structured analytics plus template-based explanation (§12.1) are more appropriate.

**Q: What is the measurable benefit?**
A: The primary benefit is review efficiency: capture a high proportion of expert-important cases within a substantially smaller manual review set, measured on both a tuning set and a held-out set (§19.4).

**Q: Why doesn't your demo include X, Y, Z from the full architecture diagram?**
A: *(new in v2.0)* Because we deliberately tiered the scope (§3.1): what you're seeing is the P0 core that the full vision is built around. The rest is a roadmap, not a gap we didn't notice.

---

## 32. SIH Evaluation Deliverables

| Deliverable | Required Content | Tier |
|---|---|---|
| Source Code | Reproducible repository with setup and offline execution | P0 |
| README | Prerequisites, installation, dataset format, run commands, demo flow | P0 |
| Architecture Document | Two-page executive architecture aligned with this SRS | P0 |
| Demo Video | Maximum two minutes; evidence-to-assurance story and measurable result | P0 |
| Technical Presentation | Maximum five slides; problem, insight, architecture, results, impact | P0 |
| Validation Package | Dataset generator, scenario definitions, ground truth and benchmark outputs (tuning + held-out) | P0 |
| Technical Documentation | Data model, analytics methodology, model governance, security and limitations | P1 |

---

## 33. Assumptions

- Periodic structured operational submissions are available.
- At least some source records contain timestamps and identifiers sufficient to reconstruct relationships.
- Asset inventory may be incomplete; the system must represent this uncertainty.
- CSEs may have different schemas; canonicalization is required.
- Real production data may be unavailable during SIH development.
- Synthetic data can be generated with realistic temporal and relational structure for prototype validation.
- The deployment environment can provide a local server/VM and controlled software installation.
- **Team size and timeline** *(new in v2.0 — fill in with real numbers)*: __ people, __ weeks/hours of build time. The Tier assignments in §3.1 assume a 4–6 person team on a single SIH cycle; re-tier if this doesn't match reality.

---

## 34. Open Questions for Requirements Freeze

- Exact CSE submission schema and mandatory fields.
- Authoritative definitions of expected escalation by severity/context.
- Authoritative asset criticality taxonomy.
- Approved peer-group attributes and benchmarking policy.
- Retention period for operational evidence and audit records.
- Approved local identity/authentication mechanism.
- Required report template and classification markings.
- Authorized validation dataset and expert review protocol.
- Hardware envelope for offline deployment.

---

## 35. Definition of Done

The SIH prototype is considered technically complete when a reviewer can start from a controlled dataset, validate its trustworthiness, reconstruct operational workflows, observe multiple supervisory signals, inspect why a finding was generated, trace it to source evidence, compare it with peers, prioritize a human review set, record the review decision, reproduce the result, and run the entire workflow without Internet or external AI APIs — **using only the P0 tier of this document.** P1/P2 items strengthen the story but are not required for "done."

---

## 36. Final Engineering Principle

Do not build a system that says: "AI thinks this SOC is risky." Build a system that says: "Here is what the operational evidence shows, here is what would normally be expected, here is what differs, here is what is missing, here is the peer and temporal context, here is the uncertainty, and here are the specific records a human supervisor should review first."

This principle should govern architecture, analytics, AI usage, UI design, validation, security, documentation and the SIH presentation. The strongest competitive identity is Evidence-to-Assurance, not AI branding — and in v2.0, it is backed by pinned formulas and an independence-tested validation number, not just a narrative.

---

## Appendix A — Glossary

| Term | Meaning in SAT-SA |
|---|---|
| SOC | Security Operations Centre; operational function responsible for detecting/investigating/responding to cyber events. |
| NCIIPC | National Critical Information Infrastructure Protection Centre; supervisory stakeholder in this problem. |
| CSE | Critical Sector Entity being assessed. |
| Supervisory Analytics | Analysis used by an oversight function to decide where human assessment effort should be directed. |
| Execution Gap | Difference between expected/documented operational behavior and observed evidence of actual execution. |
| Negative Space | Potentially meaningful absence or unexpected sparsity of evidence that should exist under an expected operating context. |
| Data Trust | Assessment of whether available data is sufficiently complete, consistent and representative for a conclusion. |
| Peer Benchmark | Comparison with contextually similar entities rather than a universal threshold. |
| Evidence Fusion | Combining multiple analytical signals, uncertainty and context into a transparent review-priority assessment. |
| Supervisory Priority | Relative recommendation for where a human examiner should focus attention. |
| Finding Confidence | Confidence that the evidence supports the stated supervisory signal — now computed via §7.2.1/§10.5, not asserted. |
| Model Confidence | Confidence produced by an ML model; not equivalent to evidentiary confidence. |
| Air-Gapped | Network environment intentionally isolated from external networks/Internet. |
| **Tier (P0/P1/P2)** | *New in v2.0.* Build-priority classification defined in §3.1; the mechanism used throughout this document to separate "must work for the demo" from "belongs in the pitch as future work." |

## Appendix B — Revision History

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-09-08 | Initial comprehensive SIH SRS baseline derived from Problem Statement 26157 and supplied project design material. |
| 2.0 | 2026-09-08 | Added P0/P1/P2 build-priority tiers to all FR/NFR/UC tables; pinned formulas for data-quality score, three P0 execution-gap detectors, negative-space coverage gap, and evidence fusion/priority score; added Generator/Detector Independence Protocol (§19.4) to prevent circular validation; split Security Architecture into Hackathon Baseline vs. Production Target; added team-size/timeline assumption placeholder; clarified template-only explanation rendering (no LLM text generation, §12.1); added Requirements Traceability Matrix (Appendix C); re-sequenced roadmap around tiers. |

## Appendix C — Requirements Traceability Matrix *(new in v2.0)*

Maps the P0 core only — the subset that must actually get built and demoed. Extend this table as P1 items are pulled into scope.

| Requirement | Engine/Component | Use Case | Ground-Truth Scenario (§19.2) | Test Level |
|---|---|---|---|---|
| FR-010–015 (Data Trust) | Data Trust Engine | UC-02 | "Low activity explained by data outage" | Data Quality, Unit |
| FR-020–024 (Canonical Model) | Canonical Evidence Store, Workflow Reconstruction | UC-03 | — (foundation for all scenarios) | Integration |
| FR-030 (Fast closure) | Execution Gap Engine | UC-04 | "Rapid critical closures" | Unit, Model |
| FR-032 (Escalation gap) | Execution Gap Engine | UC-04 | "Critical alerts without escalation" | Unit, Model |
| FR-033 (Repeated unresolved) | Execution Gap Engine | UC-04 | "Repeated alerts without remediation" | Unit, Model |
| FR-041 (Coverage gap) | Negative Space Engine | UC-05 | "Critical assets with weak evidence coverage" | Unit, Model |
| FR-060–063 (Peer Benchmark) | Peer Engine | UC-06 | All scenarios (peer context required) | Unit, Model |
| FR-070–075 (Fusion/Priority) | Evidence Fusion Engine, Priority Engine | UC-07 | All scenarios | Model, Integration |
| FR-080–082 (Explainability) | Explainability Service | UC-08 | All scenarios | Explainability |
| §19.4 (Independence Protocol) | Validation subsystem / dataset generator | — | Held-out scenario families | Model, Regression |

