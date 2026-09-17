# SAT-SA — Supervisory Analytics Tool for SOC Assessment

**Smart India Hackathon (SIH) Problem Statement 26157**  
*Prototype for NCIIPC (National Critical Information Infrastructure Protection Centre)*

---

## 🎯 What is SAT-SA?

> **"Don't ask whether a SOC says it works. Analyze the evidence of how it actually operates."**

```
SOC        = Doctor treating the patient        -> Fights active cyber threats
SAT-SA     = Examiner assessing the hospital     -> Evaluates whether the defense system
             treatment system                      is actually effective
```

SAT-SA is **not** a SIEM, SOAR, EDR/XDR, or real-time monitoring platform. It is an **air-gapped supervisory intelligence engine** that analyzes the operational evidence a Security Operations Center (SOC) produces (alerts, investigations, cases, escalations, remediation actions, closures) to identify:

1. **Execution Gaps (Goodhart's Law Metric Gaming)**: When a documented process exists and KPI metrics look healthy (e.g. 99% SLA compliance), but underlying evidence shows rapid superficial closures (e.g., median 3-4 minutes on critical alerts), missing escalation records, and recurring unresolved alerts on critical infrastructure.
2. **Negative Space (Monitoring Blind Spots)**: Evidence that *should* exist under expected operating conditions but doesn't (e.g., zero telemetry from a critical SCADA controller), safely gated by Data Trust scores to distinguish true blind spots from data ingestion outages.

---

## 🏗️ Architecture & Core Components

```
┌────────────────────────────────────────────────────────────────────────┐
│                   React + TypeScript Command Center                    │
│   (Overview / Reality Check • Findings Triage • Peer Benchmarks •      │
│    Negative Space Map • Review Yield Suite • Audit Trail)              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ REST API & Proxy
┌───────────────────────────────────▼────────────────────────────────────┐
│                        FastAPI Backend Layer                           │
│   (Datasets • Findings • Evidence Drill-Down • Reviews • Audit Logs)   │
├────────────────────────────────────────────────────────────────────────┤
│                     Supervisory Analytics Engines                      │
│   • Canonicalization & Workflow Reconstruction                         │
│   • Data Quality & Trust Engine (§7.2.1 4-ratio formula)               │
│   • Peer Benchmarking Engine (Median, MAD, & robust z-scores)          │
│   • Deterministic P0 Detectors:                                        │
│       - FR-030 Fast Closure Detector                                   │
│       - FR-032 Escalation Gap Detector                                 │
│       - FR-033 Repeated Unresolved Alerts Detector                     │
│       - FR-041 Coverage Gap Negative-Space Detector                    │
│   • Evidence Fusion & Priority Scoring (§10.5 5-component formula)     │
│   • Deterministic Template Explainability Engine (100% Non-LLM)        │
│   • Generator/Detector Independence Protocol Validation Suite (§19.4)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│         Thread-Safe Immutable Repository & PostgreSQL Schema           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start & Running Locally

### Option 1: One-Click Unified Runner (Recommended)
Runs the unified FastAPI backend serving the complete React dashboard on `http://127.0.0.1:8000`:
```bash
python run_app.py
```
*(On Windows, you can also double-click `start.bat` or run `.\start.ps1`)*

The local runner uses durable SQLite by default. Set `SAT_PERSISTENCE_MODE=postgres`
only when `DATABASE_URL` is configured; set it to `memory` only for disposable tests.
For Docker, copy `.env.example` to `.env` and replace both placeholders before starting.

### Option 2: Full Development Mode (Hot Reload)

```bash
# 1. Install Backend Dependencies & Start API
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# 2. Install Frontend Dependencies & Start Dev Server
cd frontend
npm install
npm run dev
```

Visit **`http://127.0.0.1:5173`** in your browser.

---

## 🧪 Testing & Empirical Validation

Run all unit tests and end-to-end integration tests:
```bash
python -m pytest tests/ -v
```

### Validation limitations

The bundled validation data is synthetic and must not be presented as production
performance. Its current scenario distributions are intentionally controlled and
too separable to make the headline precision/recall figures meaningful. Use the
review-yield and Top-K measures as diagnostic outputs, not claims of field accuracy,
until an overlapping held-out benchmark has been completed.

---

## 🛡️ Hackathon Security Baseline (SRS §15.1)
- **100% Offline & Air-Gapped**: Zero outbound network requests.
- **Deterministic Explainability**: Rationale rendered strictly via template substitution over empirical values—no generative text hallucinations.
- **Provenance & Auditability**: Every dataset import and human examiner disposition is recorded in an immutable audit log.
