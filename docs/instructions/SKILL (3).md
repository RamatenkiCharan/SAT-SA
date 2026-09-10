---
name: analytics-validation
description: Design synthetic ground-truth datasets and validate SAT-SA's detection engines without circular validation. Use this whenever generating synthetic/test data for SAT-SA, computing precision/recall/top-K/review-yield metrics, preparing a validation package for a demo or judges, or reviewing whether reported benchmark numbers are trustworthy. Trigger for questions like "how do we prove this works without real NCIIPC data," "what metrics should we report," or "is our test data too easy."
---

# Analytics Validation

## The trap this skill exists to prevent: circular validation

If the synthetic-data generator injects "execution gap" using the exact same threshold expression the detector checks for (`closure_time < X minutes` on both sides), your precision/recall numbers measure whether your code can invert its own arithmetic — not whether the methodology finds real supervisory weaknesses. This is the most common way a technically-correct-looking validation number turns out to be worthless under judge questioning.

## Generator/Detector Independence Protocol (apply every time)

1. **Separate ownership.** The person who writes the synthetic-scenario generator should not be the same person tuning detector thresholds — or should work from a written scenario spec that doesn't expose the detector's exact formula.
2. **Parameter decorrelation.** Express injected anomalies through realistic process simulation (e.g., "this analyst is overloaded, so closure durations are drawn from a different, plausible distribution") rather than copying the detector's threshold expression directly into the generator.
3. **Held-out scenario families.** At least 20% of ground-truth scenarios must be built *after* thresholds are frozen, using parameter ranges not used during tuning, run exactly once before reporting final numbers.
4. **Report both numbers separately.** Tuning-set performance AND held-out performance. A large gap between them is itself a finding worth disclosing — don't hide it.
5. **Disclose the limitation honestly.** "Validated on controlled synthetic data with held-out scenario testing, not on real NCIIPC data" is the correct, defensible framing — don't overclaim.

## Ground-truth scenario checklist

Build at minimum these scenario types with explicit labels:

| Scenario | Ground truth | Expected detection |
|---|---|---|
| Normal operation | No weakness | Low priority / no finding |
| Rapid critical closures | Execution gap | Fast-closure signal |
| Critical alerts without escalation | Execution gap | Escalation-gap signal |
| Repeated alerts, no remediation | Execution gap | Recurrence signal |
| Critical assets, weak evidence coverage | Potential negative space | Coverage signal |
| Missing category, adequate source coverage | Potential negative space | Absence signal |
| Low activity from a known data outage | No operational conclusion | Data-quality warning (NOT a security finding) |
| Strong KPI + weak underlying evidence | Execution gap | KPI-outcome divergence |

## Metrics to compute and report — never invent these numbers

- Precision, recall, F1 on controlled ground truth (tuning set AND held-out set, separately).
- Top-K recall: fraction of expert-important cases captured in the top-K review recommendations.
- **Review-efficiency / Supervisory Review Yield**: e.g., "30 prioritized cases reviewed captured 13 of 15 meaningful findings, vs. 100 cases needed without prioritization." This is the headline demo number — build and test it early, not last.
- Explanation coverage: % of findings with a complete, traceable evidence chain (should be 100%).
- Reproducibility: same dataset/version → same output across repeated runs.

## Review checklist before presenting any validation result
- [ ] Are the generator and detector logic independently authored/parameterized?
- [ ] Is there a held-out scenario split evaluated exactly once, separate from the tuning set?
- [ ] Are tuning-set and held-out numbers reported separately, not blended?
- [ ] Is every reported number the output of an actual test run (never a placeholder or hand-typed estimate)?
- [ ] Does the disclosure explicitly say "controlled synthetic data," not implying production validation?
