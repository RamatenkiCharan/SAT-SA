---
name: negative-space-detection
description: Reason about missing/absent operational evidence and monitoring coverage gaps for SAT-SA without conflating absence-of-evidence with evidence-of-failure. Use this whenever building, reviewing, or explaining negative-space detection, coverage-gap logic, telemetry blind-spot analysis, or any feature that has to decide what to conclude from missing data. Trigger for questions like "what does it mean if there's no data for X," "how do we detect monitoring blind spots," or "is low alert volume a problem."
---

# Negative Space Detection

## The core danger this skill guards against

"There were only 3 critical alerts from the most important environment" sounds good until you realize it might mean **"we can't see what's happening"** rather than **"it's secure."** Negative-space detection is not simple missing-value detection — it's reasoning about the absence of evidence that should reasonably exist given the operating context.

## The mandatory ordering rule (this is the whole skill in one sentence)

**Never let a data-pipeline failure masquerade as a security finding.** Always check data quality *before* interpreting absence. If low coverage is explained by a known data-quality problem, raise a data-quality warning — not a negative-space finding.

```
No/low evidence
      ↓
Was telemetry expected? (asset criticality, peer baseline)
      ↓
Was data collection actually working for this source? (DataQualityScore)
      ↓
   IF DataQualityScore <= 0.7 for the relevant source:
        → raise a DATA-QUALITY WARNING, not a negative-space finding. STOP HERE.
      ↓
   ELSE:
        → ONLY THEN is a negative-space hypothesis appropriate.
```

## Pinned formulas

```
ExpectedEvidenceCount(asset) ≈ peer_median(alerts_per_asset | same criticality_tier, same sector)

CoverageRatio(asset) = observed_alerts(asset) / max(ExpectedEvidenceCount(asset), 1)

Coverage-gap flag condition:
  flag if  asset_criticality_tier IN {CRITICAL, HIGH}
       AND CoverageRatio(asset) < 0.3
       AND DataQualityScore(source feeding this asset) > 0.7
```

## Always present alternative explanations alongside a negative-space finding

Never phrase the output as an accusation. Present it as a hypothesis with named alternatives:
```
1. genuine low activity
2. monitoring coverage gap
3. incomplete data submission
4. asset classification mismatch
```
Recommended action is always "manual supervisory review," never a conclusion of insecurity.

## Data Quality Score (feeds the gating rule above)

```
DataQualityScore =
    0.35 · CompletenessRatio    (1 − missing_required_fields / total_required_fields)
  + 0.25 · ConsistencyRatio     (1 − failed_validation_checks / total_validation_checks)
  + 0.25 · CoverageRatio        (observed_evidence_records / expected_evidence_records, capped at 1.0)
  + 0.15 · SampleSufficiencyRatio (min(1.0, actual_sample_size / minimum_sample_size))

Minimum sample size default: 30 records per evidence category per reporting period.
```
Show all four components in the UI — never the blended score alone.

## Review checklist for any negative-space feature
- [ ] Does the code check data quality/coverage of the *source* before raising a finding about the *entity*?
- [ ] Is the output phrased as a hypothesis ("potential monitoring blind spot") rather than a conclusion?
- [ ] Are alternative explanations shown alongside the finding?
- [ ] Is the expected-evidence baseline peer-relative, not a fixed universal number?
- [ ] Does context (historical baseline, known outages, reporting-period completeness) get checked before concluding "missing"?
