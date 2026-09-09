---
name: explainability-auditability
description: Design finding rationale, evidence chains, template-only explanation rendering, and provenance/audit tracking for SAT-SA. Use this whenever building or reviewing a finding-detail UI, evidence drill-down, explanation text generation, confidence display, or audit-trail/versioning feature. Trigger for questions like "how should we explain a finding," "should we use an LLM to write the summary," "how do we show confidence," or "what should the audit log capture."
---

# Explainability & Auditability

## The signature feature of the whole project

The system's credibility rests on never saying "AI says risk = 82." Every material finding must be traceable: Finding → Component/detector → Underlying evidence records → Peer/data-quality context → Human decision.

## Explanation rendering rule (non-negotiable)

**Explanation text must be produced by deterministic template substitution over computed values — never by an LLM or any generative text model, local or remote.**

```
Good:  "{n} critical alerts, {m} closed below the peer baseline, {k} lacking escalation records."
       — n, m, k are substituted from real query results. Cannot hallucinate a number.

Bad:   Feeding structured findings to an LLM and asking it to "write a summary."
       — even a "faithful" summarizer can invent a plausible-sounding detail not in the data.
```
This closes a real gap: it's easy to plan a supervisory-evidence system and then, under demo-polish pressure, quietly slot in an LLM narrator "just for readability." Don't. The system's whole pitch is "we don't use AI as the source of truth" — the explanation layer is where that promise is easiest to accidentally break.

## Confidence vs. data quality — keep them visibly separate

Never show a single blended percentage with no way to decompose it. Always show:
- **Finding confidence** (from the fusion formula components — signal strength, peer deviation, persistence, criticality, data uncertainty)
- **Data quality score** (completeness, consistency, coverage, sample sufficiency — see `negative-space-detection` skill for the formula)
- **Supporting signals** (bulleted, with actual numbers)
- **Contradicting signals** (e.g., small sample size) — always show these too, not just supporting evidence

## Evidence chain UI pattern

```
Finding: Potential Critical-Alert Handling Execution Gap
Priority: HIGH
Why flagged:
  • 17 critical alerts in sample
  • 14 closed below contextual duration baseline
  • 11 lack escalation evidence
  • pattern persists across 4 reporting weeks
  • peer deviation: |z| = 3.1
Data quality: 92% (completeness 95%, consistency 98%, coverage 88%, sample sufficiency 91%)
Contradicting evidence: small sample in one subcategory
Recommended action: manual supervisory review
[View source records →]
```
Every number here must come from an actual query on real (or synthetic) data — never typed by hand for a slide.

## Provenance and audit fields (minimum viable set for a prototype)

Every finding should carry: `finding_id`, `dataset_version`, `ruleset_version`, `model_version` (if ML involved), evidence record references, analytical method used (rule/statistic/ML/combination), and review status. Every user action (import, review decision, export) should hit a basic `audit_event` log — who, what, when. Full cryptographic hash-verification and immutable history are production-tier (P2) concerns; a plain versioned table is enough for a demo.

## Review checklist
- [ ] Is any explanation text template-substituted, with zero LLM-generated free text?
- [ ] Is confidence shown as decomposed components, never a bare percentage?
- [ ] Does every finding link to specific source evidence records (not just an aggregate)?
- [ ] Are contradicting signals shown, not just supporting ones?
- [ ] Does every finding record which dataset/ruleset version produced it?
