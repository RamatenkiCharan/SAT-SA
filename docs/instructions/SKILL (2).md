---
name: supervisory-signal-engine
description: Implement or review SAT-SA's execution-gap detectors, peer-benchmarking logic, and evidence-fusion/priority-scoring formulas. Use this whenever writing or reviewing statistical/rule-based detection logic, thresholds, peer comparison code, or the fusion score that combines multiple signals into a supervisory priority. Trigger for questions like "how should we detect fast closures," "what threshold should we use," "how do we combine multiple signals into one score," or any code touching execution-gap or priority-ranking logic.
---

# Supervisory Signal Engine (Execution Gaps + Fusion)

## Governing principle
Deterministic rules and statistics come first; ML is an addition, never the authority. A supervisor needs auditability — "AI says risk = 82" is not an acceptable output. Every detector must produce a result someone can recompute by hand from the same data.

## Peer-aware statistics (use everywhere — never a universal threshold)

A universal threshold across all CSEs is unsafe: 10,000 alerts/month at one CSE and 500/month at another aren't directly comparable. Always compute peer-relative statistics:

```
peer_median(x), peer_MAD(x)   — computed over the CSE's peer group for metric x
Minimum peer-group size: 5.
Below 5: fall back to the global population and mark the comparison low-confidence.
```

## Pinned P0 detector formulas — use these exact patterns, don't leave them as prose

**Fast closure (execution gap):**
```
flag if  severity IN {CRITICAL, HIGH}
     AND closure_duration < peer_median(closure_duration) − 2.5 · peer_MAD(closure_duration)
     AND evidence_count(investigation) < peer_p25(evidence_count)
```

**Escalation gap (execution gap):**
```
flag if  severity = CRITICAL
     AND escalation_expected(asset_criticality, alert_category) = TRUE
     AND no escalation record exists for the case
```

**Repeated unresolved alerts (execution gap):**
```
flag if  count(alerts on same asset_id, same alert_category) >= 3
     AND within a 30-day rolling window
     AND no remediation action record links to any of those alerts
```

**Every detector must write its contributing record IDs to `finding_evidence`.** A detector that can't cite the records that triggered it is broken, not lenient.

## Evidence fusion / priority score — pinned formula

```
PriorityScore(finding) =
    0.30 · SignalStrength      (# independent detectors that fired, normalized 0–1, capped at 3)
  + 0.25 · PeerDeviation       (|z-score| vs peer distribution, capped at 3.0, normalized 0–1)
  + 0.20 · Persistence         (fraction of recent periods showing the same signal)
  + 0.15 · AssetCriticality    (normalized criticality tier)
  - 0.10 · DataUncertainty     (1 − DataQualityScore of the contributing source)
```

Rules that go with this formula:
- Weights are **versioned configuration**, not hardcoded constants — store them in a `ruleset` table so you can trace which weights produced a historical finding.
- Never surface a "high priority" finding from a single detector. Threshold: require ≥ 2 independent contributing signals AND `DataQualityScore > 0.6`.
- **Always show the components in the UI, not just the blended score.** A number nobody can decompose is exactly the "AI confidence: 93%" anti-pattern this whole project exists to avoid.

## Common pitfalls to catch in review
- A "confidence" or "risk" percentage with no defined formula behind it — this is cosmetic and undermines the entire evidence-based pitch. Demand the formula.
- Using a single global threshold instead of peer-relative statistics.
- A "high priority" finding backed by exactly one weak signal.
- Detector logic that doesn't record which records triggered it (breaks explainability downstream).
- Reusing the exact same threshold expression in both the synthetic-data generator and the detector — see the `analytics-validation` skill; this makes your validation numbers circular.
- Letting ML replace rules for the P0 core. Isolation Forest / robust z-scores are fine as **P1 additions**, not required for the demo-critical detectors above.
