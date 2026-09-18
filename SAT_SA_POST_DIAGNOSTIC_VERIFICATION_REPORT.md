# Historical SAT-SA Post-Diagnostic Verification Report — Superseded

> This is a September 2026 verification checkpoint (220 tests). It is retained
> for provenance only and is not current release evidence. The final baseline
> verification completed later with 235 passing tests.

## Executive result

The Windows cleanup failure was not reproducible in the current environment.
Decision Stability Spearman correlation now uses statistical mid-ranks for
equal scores. The requested separate supervisory-utility benchmark is stopped
at the ground-truth independence gate: the repository currently has no
independent supervisory-utility labels separate from generator/detector labels.
Constructing the requested benchmark from those labels would violate the
required no-leakage condition.

## Baseline

| Area | Current state | Verified by |
|---|---|---|
| Backend | FastAPI + local persistence operational | full pytest run |
| Frontend | TypeScript production build available | current lint and production build |
| Tests | 220 passing | `python -m pytest tests -q` |
| CI | backend tests, frontend lint/build, security jobs configured | `.github/workflows/ci.yml` |
| Persistence | migration runner and durable active version | schema/restart tests |
| Security | explicit auth, throttling, bounded upload handling | security regression tests; Bandit; npm audit |
| Analytics | frozen for this phase | source review |
| Detector validation | separate robust synthetic protocol | robust-validation tests |
| Ranking | diagnostic documents unit mismatch | `SUPERVISORY_RANKING_DIAGNOSTIC.md` |
| Review budget | optimizer was not used by published raw Top-K | diagnostic audit |
| Decision Stability | tie correction applied | stability tests |

## Windows test environment

**OBSERVED:** no temporary-directory cleanup error occurred in repeated full
test runs. No workaround was added because the reported failure cannot be
reproduced and hiding cleanup errors would weaken verification.

## Final verification evidence

- `python -m pytest tests -q`: **220 passed** in 18.11 seconds. The only
  runtime notice is pytest-asyncio's configuration deprecation warning.
- Focused stability, robust-validation, security/upload, schema/persistence,
  and offline tests: **32 passed** in 6.74 seconds.
- `npm run lint`: completed with five pre-existing React
  `set-state-in-effect` warnings and no lint failure.
- `npm run build`: completed successfully, including the TypeScript build and
  production bundle.
- `python -m bandit -r backend -ll`: no medium- or high-severity findings.
- `npm audit --audit-level=high`: **0 vulnerabilities**.
- `docker compose config` with non-production placeholder secrets: validated
  successfully. Compose intentionally rejects an unset `POSTGRES_PASSWORD` or
  `SAT_SECRET_KEY`; the local Docker credential-store access warning is an
  environment permission issue and does not change the rendered configuration.
- `git diff --check`: no whitespace errors. The repository reports only
  expected CRLF conversion notices on modified files.

## Spearman tie handling

Equal scores now receive their average one-based rank. UUID order remains only
for deterministic display and selection; it is not part of Spearman. For a
constant score vector, Spearman is mathematically undefined; the result records
`spearman_defined=false` and uses stable value `1.0` only as a non-statistical
sentinel. Tests cover no ties, reverse order, tied groups, and all-equal scores.

## Supervisory-utility evaluation gate

**STOP CONDITION MET — UNVERIFIED:** a new controlled population is feasible,
but the requested supervisory targets require an independently authored target
definition or reviewer labels. Existing `GroundTruthScenario` labels describe
planted detector defects, so reusing them to score review utility would evaluate
the optimizer against detector-generation truth rather than independent
supervisory usefulness. This would contaminate the evaluation claim.

No fusion, detector, optimizer, generator, label, threshold, schema, or
canonical-model change was made.

## Claims

| Claim | Evidence | Result | Limitation |
|---|---|---|---|
| Existing detector protocol runs | robust-validation implementation/tests | verified synthetic behavior | not production validation |
| Stability treats ties correctly | mid-rank tests | verified | measures specified perturbations only |
| Utility benchmark is independent | no independent labels exist | not yet verified | requires externally authored supervisory targets |
| Offline core behavior | existing offline tests | previously verified | scope is tested configuration |

## Decision gate

1. Remaining reproducible engineering issue fixed: **yes, tie handling**.
2. Full suite green: **yes, 220 passed**.
3. Spearman tie handling statistically appropriate: **yes, with explicit undefined handling**.
4. New supervisory-utility benchmark independent: **not yet constructible without independent ground truth**.
5. Review unit well-defined: **implementation candidate is CSE × period × finding type; supervisory usefulness labels remain undefined**.
6. Optimizer useful coverage: **unverified independently**.
7. Baseline comparison: **not run; would be meaningless without independent targets**.
8. Frozen analytical components changed: **no**.
9. Existing validation regression: **none observed**.
10. Safe claim: controlled synthetic detector behavior and implementation-level verification.
11. Required qualification: no production effectiveness, real-world SOC performance, or independent utility claim.
12. Final UI/demo hardening: **not yet; obtain independent utility target definitions first**.

## Existing detector validation

The existing robust synthetic detector protocol was preserved. Its generator,
held-out detector labels, thresholds, fusion formula, weights, and optimizer
were not changed in this phase. The complete suite and focused robust-validation
tests pass. This establishes implementation continuity only; it does not make a
production or real-SOC effectiveness claim.

## New supervisory-utility evaluation

**Not run by design.** The proposed review unit is supportable as
`CSE × reporting period × finding type`, with duplicate findings collapsed to a
single unit. However, no independently authored label identifies which review
units are *supervisor-useful*. The only available ground truth records planted
detector conditions. Using it to score review yield, coverage, or optimizer
selection would leak generator intent into the result.

An independent evaluation can begin only after a domain owner supplies a
versioned supervisory-target rubric and independently labels a new evaluation
population (or authorizes a documented external review process). It must remain
separate from detector tuning and the existing held-out detector benchmark.

## Baseline comparisons and review-budget results

Random, priority-only, diversity-only, and optimizer comparisons were not
reported because their proposed outcome, useful supervisory coverage, has no
independent denominator. The ranking diagnostic remains available as an
implementation diagnostic: on its detector-target population, raw Top-1/3/5
and optimizer K=5 each cover 1/39, 3/39, and 5/39 unique detector targets.
Those numbers are not review-utility results and must not be presented as such.

## Negative controls and provenance

No new negative-control population was generated. Doing so without the missing
independent utility rubric would create labels by construction and fail the
same independence requirement. The diagnostic script records its fixed seed,
ruleset, population, and metric definitions; its output is explicitly a
synthetic implementation diagnostic, not production validation.

## Security, offline behavior, and frontend/API

The security regression tests confirm that a database lookup failure cannot
fall back to demo credentials, and that upload format checking rejects an
over-limit streamed upload. Authentication remains explicit and throttled;
upload errors are client-safe. Offline behavior, persistence migration, and
durable active-version tests are included in the focused verification set.

No new UI or API surface was added because no valid supervisory-utility result
exists to expose. The frontend still builds successfully. Core analytics were
verified under the tested offline configuration without external LLM or cloud
inference dependencies; this is not a claim of universal offline behavior.

## Regression results and remaining limitations

There were no assertion failures, skipped tests, or temporary-directory cleanup
failures in the final 220-test run. The remaining non-failing notices are the
pytest-asyncio future-default deprecation and five existing frontend
`set-state-in-effect` lint warnings.

The material limitation is independent supervisory-utility ground truth. Until
that exists, SAT-SA must not claim ranking superiority, real-world SOC review
coverage, production/NCIIPC effectiveness, fairness, absence of systemic bias,
or production-scale reliability.

## Claim-to-evidence matrix

| Claim | Evidence | Test | Result | Limitation |
|---|---|---|---|---|
| Temporary cleanup issue is fixed/reproducible | repeated Windows suite execution | full pytest | no cleanup error observed | no prior failing handle was available to isolate |
| Tie handling is statistically appropriate | average-rank Spearman implementation | focused stability tests | partial/all-tie behavior covered; undefined state explicit | only measures configured perturbations |
| Detector behavior remained intact | frozen analytical implementation plus regression suite | robust/full pytest | no regression observed | synthetic only |
| Security controls operate in tested paths | auth and upload regression cases | focused security tests | pass | not a penetration test |
| Frontend release build works | TypeScript/Vite build | lint + build | pass; five warnings | warning cleanup deferred |
| Dependency/static checks found no high-risk issue | Bandit and npm audit | security commands | no Bandit medium/high findings; 0 npm audit vulnerabilities | point-in-time/tool-limited |
| Review utility is independently validated | independent targets | not available | **not established** | requires externally authored labels |

## Recommended next engineering phase

Obtain and version a human-approved supervisory-utility rubric and an
independently labeled evaluation dataset. Then run the planned controlled
review-budget comparison without altering the frozen detector benchmark. Final
UI/demo/presentation hardening should follow that evidence, not substitute for
it.
