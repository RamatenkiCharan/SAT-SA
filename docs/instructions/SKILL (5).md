---
name: architecture-review
description: Review SAT-SA's layered architecture, technology stack choices, build sequencing, and security-scope discipline. Use this whenever choosing or reviewing a tech stack, evaluating whether an architecture is overengineered for a prototype timeline, sequencing a roadmap, or deciding what infrastructure (databases, queues, ML frameworks, deployment tooling) is actually justified. Trigger for questions like "should we use X technology," "is this architecture too complex," or "what order should we build things in."
---

# Architecture Review for SAT-SA

## Governing principle: engineering depth ≠ infrastructure inflation

The technical depth of this project lives in the analytics methodology (evidence modeling, execution-gap/negative-space reasoning, peer-aware statistics, evidence fusion, explainability) — not in the infrastructure stack. A team that reaches for Kubernetes + Kafka + Neo4j + Elasticsearch + Spark + a GPU cluster for a prototype has optimized for looking impressive, not for shipping a working, defensible demo.

## Layered architecture (target shape)

```
Presentation      React + TypeScript dashboard / findings / evidence drill-down
Application       FastAPI | RBAC | workflow | review | audit
Intelligence      Execution Gap | Negative Space | Peer Benchmark | Evidence Fusion
Evidence/Analytics canonical model | workflow reconstruction | stats | (P1/P2) ML
Data Trust        completeness | consistency | coverage checks
Data              PostgreSQL, versioned datasets
Infrastructure    Local server/VM, no Internet
```

## Recommended stack and why (don't substitute without a measured reason)

| Layer | Choice | Reason |
|---|---|---|
| Frontend | React + TypeScript | Mature, supports drill-down/interactive dashboards |
| Backend | Python + FastAPI | Strong data/ML ecosystem, clean API layer |
| Database | PostgreSQL | Relational evidence model fits naturally, auditable, no distributed infra needed |
| Processing | Polars/Pandas | Sufficient for prototype scale |
| Stats | NumPy/SciPy | Transparent, auditable calculations |
| ML (P1 only) | scikit-learn | Offline, open-source, interpretable enough to explain |
| Viz | Apache ECharts / Plotly | Interactive charts without vendor lock-in |
| Deployment | Docker Compose | Reproducible locally; bare-metal must also work (air-gapped requirement) |

**Escalate beyond this stack only when a measured bottleneck proves it's needed** — e.g., don't add a queue until you've actually measured ingestion throughput failing.

## Security scope discipline

Split every security requirement into two explicit buckets before estimating effort:
- **Hackathon Baseline (build now):** local auth, RBAC as a role column enforced at the API layer, a basic audit-log table, strict upload validation, zero outbound network calls (verify this explicitly, don't just assume it).
- **Production Target (describe, don't build):** full RBAC with dedicated auditor role, encryption at rest, TLS, hash-verified model/ruleset packages, offline dependency-pinning strategy.

Building the Production Target list for a prototype is a scope trap — it directly competes with time needed for the analytics engines that are the actual differentiator.

## Build sequencing rule

**Do not start P1 work until every P0 exit condition is met and rehearsed as a live, reproducible demo.** Recommended order: canonical model + ingestion + data trust → 2–3 core execution-gap/negative-space detectors with pinned formulas → peer grouping → evidence fusion + priority ranking → evidence-chain UI → validation (independence-protocol-tested numbers). Everything else is P1/P2.

## Review checklist
- [ ] Is every infrastructure choice justified by a measured need, not by how it sounds in a pitch?
- [ ] Is the analytics/evidence layer clearly the most detailed part of the architecture, not the infra layer?
- [ ] Is security explicitly split into baseline-vs-production, with only baseline in the current sprint?
- [ ] Does the build sequence put P0 detectors and the evidence-chain UI ahead of governance/audit/scale features?
- [ ] Has "no internet dependency" been actually tested, not just asserted in a diagram?
