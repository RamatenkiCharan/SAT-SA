# SAT-SA — Smart India Hackathon (SIH) Pitch & Live Demo Guide
**Problem Statement ID: 26157**  
**Stakeholder: National Critical Information Infrastructure Protection Centre (NCIIPC)**

> This guide demonstrates SAT-SA using controlled synthetic evidence. No
> authorized NCIIPC production dataset was available for validation. Current
> detector metrics are synthetic-only; independent supervisory-review utility
> and real-world ranking superiority remain unvalidated.

---

## 1. The Core Pitch Story (The "Goodhart's Law" Insight)

> **"Don't ask whether a SOC says it works. Analyze the empirical evidence of how it actually operates."**

### Analogy:
- **SOC** = Doctor treating the patient (fights active cyber threats).
- **SAT-SA** = Chief Medical Examiner assessing the hospital's treatment system (evaluates whether the defense process is actually effective).

### The Critical Problem in Critical Sector Entities (CSEs):
When a SOC is audited using conventional KPI dashboards (e.g. *98.4% SLA Compliance*), management sees all "Green". But under the pressure of SLA metrics, analysts may engage in **Goodhart's Law Metric Gaming**:
- Closing critical SCADA alerts in under 4 minutes with 0 evidence artifacts.
- Never escalating high-severity intrusion attempts to senior engineers.
- Closing repeated ransomware triggers on core banking servers as "false positive" without executing any remediation.
- Missing telemetry from critical controllers because no alarms are firing (silent failure vs benign environment).

**SAT-SA solves this by reconstructing operational workflows and applying deterministic supervisory analytics.**

---

## 2. The 3-Minute Live Demo Script

| Time | Screen / View | Action on Screen | What to Say to the Judges |
|---|---|---|---|
| **0:00 - 0:45** | **Overview Tab** | Point to the **National Power Dispatch Center (NPDC)** card. | *"In this controlled synthetic scenario, NPDC reports a 99.2% SLA compliance. SAT-SA then reconstructs the supplied operational evidence to surface potential execution-gap signals for human review."* |
| **0:45 - 1:30** | **Findings Triage & Evidence Drill-Down** | Click into the **FR-030 Fast Closure finding on NPDC**. Open the Evidence Timeline. | *"This synthetic evidence lifecycle shows a critical SCADA alert acknowledged at 02:00 and closed at 02:04 with no forensic artifacts. Compared with the scenario's peer baseline, the pattern is an evidence-backed review signal, not a conclusion about a real SOC."* |
| **1:30 - 2:00** | **Negative Space Tab** | Open the **Negative Space Matrix**. Point out the Critical SCADA Controller. | *"This scenario contains no telemetry for a critical asset. SAT-SA checks Data Trust first; when the tested data is sufficiently trustworthy, it surfaces a potential monitoring blind spot for review rather than treating missing evidence as proof of failure."* |
| **2:00 - 2:30** | **Human-in-the-Loop & Auditability** | Click **Review Action**, select **Confirmed Operational Gap**, add notes, then switch to **Audit Trail**. | *"The human supervisor remains the final authority. SAT-SA records the review decision in its audit trail. The core analytics were verified under the tested offline configuration without external LLM/cloud inference, and explanations are deterministic templates over evidence."* |
| **2:30 - 3:00** | **Validation Tab** | Open the **Current Held-Out Synthetic Detector Validation** view. | *"Under the Generator/Detector Independence Protocol, the current controlled synthetic benchmark has 240 scenarios: 168 tuning, 72 held-out, and 36 hard negatives. Held-out detector results are 97.30% precision, 92.31% recall, 94.74% F1, and 0.40% FPR. This is synthetic detector validation, not real-world SOC or review-utility validation."* |

---

## 3. Top 10 Judge Trap Questions & Flawless Defenses

### Q1: "Is this just another SIEM or SOAR platform?"
> **Defense:** *"No. A SIEM/SOAR asks: 'Is something malicious happening on the network right now?' SAT-SA is a supervisory analytics layer that asks: 'Is the SOC's detection, investigation, and escalation process itself functioning effectively?' We consume telemetry-about-the-process, not raw packet captures."*

### Q2: "Why didn't you use an LLM (like GPT-4 or Claude) to generate the findings?"
> **Defense:** *"SAT-SA is designed for offline/air-gapped deployment. Its core analytics were verified under the tested offline configuration without external LLM/cloud inference. Generative AI can invent facts and change conclusions between runs, so SAT-SA uses robust statistics (Median/MAD) and deterministic template substitution over computed numbers."*

### Q3: "How do you distinguish a true blind spot from a broken log shipper?"
> **Defense:** *"Through our Data Trust & Quality Engine (§7.2.1). Before raising a negative-space coverage gap, we calculate a 4-part Data Quality score (Completeness, Consistency, Coverage, Sample Sufficiency). If Data Quality is $\le 0.70$, we flag a data pipeline outage (FR-015). We ONLY flag an operational blind spot when Data Quality is $> 0.70$."*

### Q4: "How do you avoid comparing small SOCs with giant enterprise SOCs?"
> **Defense:** *"We implement Context-Aware Peer Grouping (§7.7). Entities are clustered by sector, asset count, and operational scale. All anomaly thresholds use robust peer-relative metrics ($\text{Median}$ and $\text{MAD}$) with a minimum cohort size of 5, rather than static hardcoded thresholds."*

### Q5: "Is your synthetic validation circular (i.e. did you hardcode tests to find what you injected)?"
> **Defense:** *"No. We strictly adhere to the Generator/Detector Independence Protocol (§19.4). The generator creates varied operational workflows with realistic noise, and we evaluate our detectors against an isolated, held-out test split (different seeds, different entity topologies) that was never used during detector tuning."*

### Q6: "What is your Evidence Fusion formula?"
> **Defense:** *"We use the pinned 5-component formula (§10.5):*
> $$\text{Priority} = 0.30 \times S_{\text{signal}} + 0.25 \times S_{\text{peer}} + 0.20 \times S_{\text{persistence}} + 0.15 \times S_{\text{criticality}} - 0.10 \times U_{\text{data}}$$
> *Every component is decomposed in the UI so the supervisor knows exactly why a score was assigned."*

### Q7: "Can a user upload custom operational data?"
> **Defense:** *"Yes. In the Dataset Manager tab, users can upload standard JSON or CSV packages containing alerts, investigations, cases, and closures. SAT-SA automatically canonicalizes the records, validates data quality, and reconstructs the lifecycle graphs."*

### Q8: "What if a CSE has a small sample size?"
> **Defense:** *"Our Sample Sufficiency ratio drops if the record count is below 30. This increases Data Uncertainty ($U_{\text{data}}$), which penalizes the Priority Score and adds a prominent 'Low Confidence / Small Sample' warning in the finding explanation."*

### Q9: "How does SAT-SA save time for NCIIPC examiners?"
> **Defense:** *"SAT-SA implements deterministic budget-constrained review selection to help supervisors inspect a limited queue. Independent supervisory-utility ground truth is not yet available, so we do not claim proven real-world review-yield or ranking superiority."*

### Q10: "Can this deploy in a real air-gapped NCIIPC bunker tomorrow?"
> **Defense:** *"SAT-SA is designed for local/offline deployment and is containerized with Docker Compose. Its tested core analytics use local PostgreSQL/SQLite options and no external LLM/cloud inference. Target-environment deployment and network policy still require operational verification."*

---

## 4. 7-Slide Hackathon Pitch Deck Structure

1. **Slide 1: Title & Hook**
   - Title: SAT-SA — Supervisory Analytics Tool for SOC Assessment
   - Subtitle: Evidence-Driven Assurance for National Critical Information Infrastructure (Problem 26157)
   - Hook: *"Don't ask whether a SOC says it works. Analyze the evidence of how it actually operates."*

2. **Slide 2: The Hidden Problem (Goodhart's Law in SOCs)**
   - The illusion of Green KPI dashboards vs reality of metric gaming (rapid superficial closures, suppressed escalations).
   - The scaling bottleneck of NCIIPC manual evidence audits.

3. **Slide 3: The SAT-SA Solution Architecture**
   - Canonical Evidence Model $\rightarrow$ Data Trust Engine $\rightarrow$ Workflow Reconstruction $\rightarrow$ Execution Gap & Negative Space Engines $\rightarrow$ Evidence Fusion.

4. **Slide 4: Core Innovations**
   - 4-Part Data Quality Gating (§7.2.1).
   - Robust Peer Benchmarking (Median / MAD / Robust Z).
   - Deterministic template explainability over evidence, without external LLM/cloud inference in the tested configuration.

5. **Slide 5: Live Demonstration ("The NPDC Reality Check")**
   - Side-by-side contrast of 99.2% SLA vs 4-min closure on SCADA alert.
   - Evidence drill-down timeline & Negative Space Matrix.

6. **Slide 6: Controlled Synthetic Validation & Limitations**
   - Current held-out synthetic detector scorecard: 97.30% precision, 92.31% recall, 94.74% F1, 0.40% FPR (72 held-out of 240 scenarios; 36 hard negatives).
   - State clearly: no authorized NCIIPC production dataset and no independently authored supervisory-utility ground truth.

7. **Slide 7: Deployment & Impact**
   - Designed for offline/air-gapped deployment; core analytics verified in the tested offline configuration without external LLM/cloud inference.
   - Demonstrated on controlled synthetic evidence; target-environment deployment and real-world effectiveness remain future validation work.
