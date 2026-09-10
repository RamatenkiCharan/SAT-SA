---
name: requirements-analysis
description: Scope, tier, and validate requirements for SAT-SA (Supervisory Analytics Tool for SOC Assessment, SIH 26157) or any similarly-shaped government/supervisory-analytics SRS. Use this whenever the user is drafting, reviewing, prioritizing, or freezing requirements/FRs/NFRs/use-cases/acceptance-criteria for SAT-SA, whenever a requirements list has grown large and needs P0/P1/P2 tiering, whenever scope-vs-timeline mismatch is suspected, or whenever a traceability matrix, acceptance criteria set, or "what should we actually build first" question comes up. Trigger even if the user just says "review this SRS" or "is this feasible" without naming tiering explicitly.
---

# Requirements Analysis for SAT-SA

Core failure mode this skill exists to prevent: a large, well-written requirements document where every requirement is tagged "Must," which guarantees a team builds ten things shallowly instead of five things that work. This is the single most common way SIH-style projects fail their own demo.

## When to use this
- Reviewing or drafting an SRS, feature list, or backlog for SAT-SA or an evidence-driven supervisory/assessment tool.
- Someone asks "is this buildable in the time we have."
- A requirements document has no visible prioritization (everything "Must" / "Shall").
- Preparing acceptance criteria or a traceability matrix before a build sprint.

## The tiering method (P0 / P1 / P2)

Apply this to every functional requirement (FR), non-functional requirement (NFR), and use case (UC):

| Tier | Meaning | Test |
|---|---|---|
| P0 — Demo-critical | Must exist and work for the core "wow moment" to be true and reproducible | If cutting it breaks the demo story, it's P0 |
| P1 — Stretch | Strengthens the pitch; demo survives without it | Build only after every P0 works end-to-end |
| P2 — Production-only | Correct for real deployment; out of scope for a prototype timeline | Mention in the pitch as "designed for, not yet built" |

**Rule:** P0 should be the largest subset your actual team/timeline can finish AND rehearse, not the largest subset that sounds impressive. Always get team size and time budget stated explicitly before freezing tiers — untiered scope and unstated capacity are the same failure wearing different clothes.

## Red flags to catch in any SAT-SA-style SRS

1. **Every requirement is "Must."** No prioritization = no real prioritization decision was made. Demand a tier on every line.
2. **Formulas described conceptually but never pinned.** "Relative to contextually appropriate baselines" is not implementable — someone will build a different system than someone else reading the same sentence. Convert to an actual statistic (median/MAD, explicit thresholds, explicit constants) before coding starts.
3. **Security/governance NFRs at production-grade sitting next to "avoid infra bloat" language.** These are in direct tension. Split security into a Hackathon Baseline (local auth, basic RBAC, basic audit log) vs. a Production Target (encryption at rest, TLS, hash-verified model packages, full auditor role) — don't let the second list eat sprint time meant for the analytics core.
4. **No resourcing/timeline assumptions.** A roadmap with phases and exit conditions but no team-size/hours estimate can't be sanity-checked. Add it before trusting the roadmap.
5. **No traceability.** If you can't answer "which test proves FR-030 works," you don't actually know if it's done. Build a matrix: Requirement → Component → Use Case → Ground-truth scenario → Test level.
6. **Validation numbers with no defined methodology.** If precision/recall/confidence percentages are illustrative examples rather than the output of an actual formula and actual test run, flag it — see the `analytics-validation` skill for the independence protocol this needs.

## Acceptance criteria pattern

Write acceptance criteria as testable, tier-tagged statements, not aspirations:
- Bad: "The system should detect execution gaps."
- Good: "**(P0)** The system flags a case as a fast-closure execution gap when `closure_duration < peer_median − 2.5·peer_MAD AND evidence_count < peer_p25`, with the contributing record IDs attached to the finding."

## Traceability matrix template

```
| Requirement ID | Component/Engine | Use Case | Ground-Truth Scenario | Test Level | Tier |
```
Populate this for the P0 tier first — that's the subset that actually needs to be provably done before a demo.

## Deliverable checklist before "requirements frozen"
- [ ] Every FR/NFR/UC has a tier.
- [ ] Team size and time budget stated.
- [ ] P0 formulas are pinned (concrete statistics, not adjectives).
- [ ] Security requirements split into baseline vs. production target.
- [ ] Traceability matrix exists for at least the P0 tier.
- [ ] No requirement claims a benchmark number that hasn't been produced by an actual test run.
