---
name: security-data-modeling
description: Design and review the canonical evidence data model, database schema, and entity relationships for SAT-SA (alerts, investigations, cases, escalations, closures, assets, peer groups, findings). Use this whenever designing or reviewing an ERD, database schema, table list, data provenance/versioning strategy, or peer-grouping schema for SAT-SA or any similar security-operational-evidence platform. Trigger for questions like "what tables do we need," "how should alerts relate to cases," or "how do we version datasets."
---

# Security Data Modeling for SAT-SA

## Why this layer is the actual technical depth of the project

A weak implementation stores flat rows (`alert_id, severity, status`). The intended implementation reconstructs **relationships** so the system can reason about workflows, not isolated records. This is what makes execution-gap and negative-space detection possible at all — you cannot ask "was this escalated?" from a table that doesn't link alerts to escalations.

## Canonical entity model

```
CSE
 ├── Asset (criticality, type, environment)
 ├── Alert (timestamp, severity, source, asset_id, status)
 │    ├── Investigation (start/end, analyst, evidence_count, disposition)
 │    ├── Case (opened/closed, severity, outcome)
 │    │    ├── Escalation (timestamp, level, target)
 │    │    ├── Action (type, timestamp, outcome)
 │    │    └── Closure (timestamp, reason, reviewer)
 │    └── recurrence / related alerts
 └── Reporting Period
```

## Core table list (PostgreSQL — don't reach for Neo4j for a prototype)

```
cse · asset · alert · case · investigation · escalation · disposition · closure
analyst/team · peer_group · peer_membership · telemetry_coverage
finding · finding_evidence · finding_signals · review_decision
dataset · dataset_version · ruleset · model_version · analysis_run
audit_event
```

Relational storage is sufficient. A graph database only earns its cost once you've measured a real bottleneck querying multi-hop workflow chains (e.g., "every critical alert where investigation → escalation → response is broken") — don't add graph infrastructure preemptively.

## Non-negotiable modeling rules

1. **Never overwrite source evidence.** Raw imported records are immutable once ingested; a `dataset_version` is frozen at import time. Corrections happen as new versions, not edits in place.
2. **Every derived record cites its dataset_version.** Analytical outputs (findings, features) must reference exactly which version of the data produced them — this is what makes results reproducible.
3. **Separate declared/self-reported fields from observed/derived fields.** Don't let a CSE's self-reported status field silently become the system's "ground truth" — operational timestamps and linked records are the ground truth.
4. **Model peer grouping as first-class data**, not a runtime-only computation: `peer_group` + `peer_membership` tables, with the grouping attributes (sector, scale, asset count, alert volume) stored so a benchmark comparison can be audited later. Minimum peer group size: 5 — below that, fall back to global population and mark the comparison low-confidence.
5. **Model coverage/telemetry expectations explicitly.** A `telemetry_coverage` table (asset/category, expected count, observed count, period) is what makes negative-space reasoning possible — don't infer "expected" ad hoc inside application code with no persisted record of what was expected and why.
6. **Findings must carry evidence references, not just a score.** `finding_evidence` links a `finding_id` to the specific source record IDs that produced it. A finding with no linked evidence records should be treated as a bug, not a valid state.

## Schema review checklist
- [ ] Can I trace any finding back to the exact source rows that produced it?
- [ ] Is dataset versioning immutable (no in-place edits to imported data)?
- [ ] Does the schema distinguish self-reported/declarative fields from observed/derived fields?
- [ ] Is peer-group membership persisted, not just computed at query time?
- [ ] Is there a table that records *expected* evidence (for negative-space checks), separate from *observed* evidence?
- [ ] Are foreign keys and referential integrity enforced between alert → investigation → case → escalation → closure?
