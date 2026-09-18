# Historical SAT-SA Claude-Audit Remediation Report — Superseded

> This is a September 2026 remediation checkpoint (230 tests). It is retained
> for provenance only and is not current release evidence. The final baseline
> verification completed later with 235 passing tests.

## Executive result

This pass verified the repository rather than accepting the prior audit as
truth. Three genuine engineering issues were corrected: implicit PostgreSQL
password fallback, implicit production-like bootstrap users/data, and unsafe
ruleset-store fallbacks/error detail. The frozen detector, fusion, priority,
optimizer, generator, labels, and validation methodology were not changed.

## Audit register

| ID | Original finding | Current state | Action | Evidence | Test | Status |
|---|---|---|---|---|---|---|
| I-01 | Frontend credential bypass | Explicit login; token held only in page memory | Re-verified | `frontend/src/api.ts`, RBAC tests | auth/frontend contract tests | VERIFIED |
| I-02 | Synthetic benchmark quality | Robust 240-scenario protocol exists; results synthetic only | Documented limitations; no metric tuning | robust run output | robust-validation suite | DOCUMENTED |
| I-03 | Stale finding | No reproducible current finding defect | Re-verified | finding persistence/API tests | full suite | NOT REPRODUCED |
| I-04 | Schema drift | Migrations are schema authority | Re-verified | `database/migrate.py` | migration/restart tests | VERIFIED |
| I-05 | Persistence fallback | Invalid persistence mode fails explicitly | Re-verified | repository factory | persistence tests | VERIFIED |
| I-06 | Dataset-selection persistence/audit | Durable and auditable | Re-verified | repository state and audit event path | schema/restart tests | VERIFIED |
| I-07 | Signing key | Production requires `SAT_SECRET_KEY` | Re-verified | `backend/security/auth.py` | auth tests | VERIFIED |
| I-08 | Docker frontend build | Multistage build runs `npm ci` and build | Re-verified | `Dockerfile` | frontend build/config | VERIFIED |
| I-09 | Ranking evaluation | Raw Top-K is not optimizer utility | Preserved diagnostic limitation | ranking diagnostic | robust validation | DOCUMENTED |
| I-10 | CORS | Explicit local origins and limited methods/headers | Re-verified | `backend/main.py` | API tests | VERIFIED |
| I-11 | DB auth failure fallback | Failure becomes unavailable, never demo auth | Re-verified | durable `UserStore` path | security regression | VERIFIED |
| I-12 | Upload memory/error handling | Stream limit and safe client error retained | Re-verified | ingestion/dataset API | upload regression | VERIFIED |
| I-13 | Repository factory | Explicit `sqlite`/`postgres`/`memory`; no unreachable fallback | No aesthetic refactor | `get_repository` | persistence tests | VERIFIED |
| I-14 | Browser token persistence | In-memory token only | Re-verified | frontend API module | frontend auth contract | VERIFIED |
| I-15 | CI | Tests, lint, build, Bandit, npm audit configured | Re-verified | `.github/workflows/ci.yml` | local equivalents | VERIFIED |
| I-16 | Temporary/generated artifacts | Runtime DB/results/cache paths ignored | Classified; no data deleted | `.gitignore`, `git check-ignore` | workspace inspection | VERIFIED |
| I-17 | Database credential hygiene | No runtime DB password fallback; bootstrap passwords env-only | Fixed | PostgreSQL URL/bootstrap code | startup/secret regressions | FIXED |
| I-18 | Startup synchronous initialization | Demo analytics/data load is explicit opt-in only | Fixed | lifespan and seed flags | startup regressions | FIXED |
| I-19 | Docker Compose | Required secrets enforced; config renders with placeholders | Re-verified | `docker-compose.yml` | `docker compose config` | VERIFIED |
| I-20 | Dependency reproducibility | Direct Python pins; Node lockfile/`npm ci`; Docker fixed base tags | Documented transitive-Python lock limitation | manifests/Docker/CI | install/build checks | DOCUMENTED |
| I-21 | Test counts | No current documentation claims an obsolete release count | Corrected current docs/historical labels | current-state/docs banners | full suite | FIXED |
| I-22 | Broad exception/fallback handling | Removed dead silent auth fallback; ruleset store fails explicitly; safe API boundaries retained | Fixed | auth/ruleset modules | focused + full suite | FIXED |
| I-23 | Exception leakage | Signed-token parser and upload/ruleset API errors are client-safe | Fixed/re-verified | auth/datasets/rulesets APIs | malformed-token regression | FIXED |
| I-24 | Generated artifacts | Ignored runtime outputs are not tracked | Classified; no useful artifact deleted | `.gitignore` | workspace inspection | VERIFIED |
| I-25 | Login throttling | Local in-process 5-failure/15-minute throttle remains | Re-verified | auth API | auth tests | VERIFIED |
| I-26 | Frontend quality/CI | Build/type check and lint run in CI | Re-verified | workflow/frontend scripts | current lint/build | VERIFIED |
| I-27 | Asset criticality influence | Correct contextual 15% fusion term; not independently utility-validated | Added controlled characterization tests; no weight change | fusion implementation | criticality tests | DOCUMENTED |
| I-28 | Documentation/instruction residue | Current docs corrected; historical reports marked superseded | Fixed | README/current-state/frontend README | documentation review | FIXED |

## Security and persistence

Production PostgreSQL now requires `DATABASE_URL` or `POSTGRES_PASSWORD`; no
known fallback password remains in runtime code. Durable startup seeds roles and
the authoritative ruleset only. Creating demo accounts requires an explicit
operator flag plus all three bootstrap-password variables. Synthetic demo data
also requires explicit opt-in. The known `Admin@SAT2026!`-style values remain
only as isolated test fixtures, not runtime defaults or frontend content.

Authentication is explicit; authorization is backend-enforced; database lookup
failures fail closed; login throttling, restrictive CORS, bounded upload checks,
and safe boundary errors remain in place. Migration scripts remain the sole
schema source and durable active dataset selection remains auditable.

## Startup, exceptions, and criticality

Startup now has deterministic, bounded behavior: repository initialization,
migrations, required reference data, and state load. It runs the analytical demo
pipeline only when `SAT_SEED_DEMO_DATA=true`. Invalid stored rulesets no longer
silently become the V1 baseline; an operator receives a safe API failure and
the internal exception is logged. Legacy dead methods that swallowed database
errors and returned demo users were removed.

Asset criticality is a documented contextual component with weight 0.15. Equal
evidence changes by exactly 0.1125 between CRITICAL and LOW assets. Strong
low-criticality evidence still outranks weak critical-asset evidence. Removing
the term equalizes otherwise identical inputs; increasing the term has the
expected bounded effect. This characterizes implementation behavior, not
independent supervisory-ranking utility.

## Validation and claims

The 240-scenario robust synthetic protocol ran unchanged: 168 tuning scenarios,
72 held-out scenarios, and 36 hard negatives. Held-out detector performance was
36 TP, 1 FP, 248 TN, 3 FN: precision 97.30%, recall 92.31%, F1 94.74%, FPR
0.40%; bootstrap intervals are 90.00–100.00% precision and 82.05–100.00%
recall. Raw finding recall@1/3/5 is 2.56%/7.69%/12.82% over its 39
detector-target denominator. These are synthetic detector measurements, not
production validation or review-budget utility.

The independent supervisory-utility benchmark remains blocked correctly: the
repository contains no independently authored supervisory labels. Reusing
planted detector truth would be leakage, so no fabricated baseline comparison
or optimizer superiority claim was added.

## Claim-to-evidence audit

| Claim | Implementation evidence | Test evidence | Validation type | Limitation |
|---|---|---|---|---|
| SAT-SA detects specified execution-gap signals | deterministic detector modules | focused detector/full suite | synthetic implementation | not real SOC validation |
| SAT-SA evaluates data-trust-gated negative space | coverage detector plus trust gating | data-trust/coverage tests | synthetic implementation | absence is still a review hypothesis |
| SAT-SA reconstructs workflows and preserves provenance | canonical/repository models | persistence/provenance tests | implementation | source data remains synthetic in validation |
| SAT-SA prioritizes supervisory attention | versioned fusion and explanations | fusion/criticality tests | implementation | priority is not security risk or utility proof |
| SAT-SA selects a bounded review queue | ReviewBudgetOptimizer | review-budget tests | implementation | independently useful coverage unverified |
| Core analytics run locally without external LLM/cloud inference | local Python/SQLite/Postgres deployment design | offline tests | tested offline configuration | target-network policy still needs deployment verification |
| SAT-SA has synthetic detector validation | robust protocol | robust/full suite | synthetic held-out | no production/general SOC claim |

## Verification results

- Focused remediation suite: **26 passed**.
- Complete Python suite: **230 passed** in 18.28 seconds.
- Offline/security/startup focus: **20 passed**.
- Frontend type-check/production build: passed.
- Frontend lint: passed with five existing `react(set-state-in-effect)` warnings.
- Bandit: no medium/high findings.
- npm audit: **0 vulnerabilities**.
- Docker Compose: valid when non-production required-secret placeholders are
  provided. The workstation Docker credential-store permission warning is
  environmental and did not alter rendered configuration.

## Remaining limitations and decision gate

The five frontend effect warnings and pytest-asyncio future-default warning are
non-failing hardening items. Python transitive dependencies are not hash-locked;
direct dependencies are exact-pinned and Node uses `package-lock.json` with
`npm ci`. Independent supervisory-utility labels, real operational data,
production-scale resilience, fairness, and universal ranking superiority remain
unproven.

1. Genuine remaining audit defects fixed: **yes, for the verified items**.
2. Deferred hardening: frontend effect-warning cleanup and stronger Python
   transitive lock/hashes.
3. Not defects: repository factory and documented asset criticality term.
4. Frozen analytical components changed: **no**.
5. Validation metric regression: **no**.
6. Backend suite green: **yes, 230 passed**.
7. Frontend build/type-check green: **yes**.
8. Frontend lint green: **yes, warnings only**.
9. Security checks green: **yes**.
10. Docker configuration valid: **yes, with required secrets supplied**.
11. Repository clean: **no** — the intentional, uncommitted remediation and
    prior verification artifacts are present and ready for review/commit.
12. Claims synchronized with implementation: **yes, after this pass**.
13. Critical engineering defect open: **no verified P0/P1 defect**.
14. Engineering baseline freeze: **yes, subject to reviewing and committing the
    intentional working-tree changes; do not claim independent supervisory
    utility or real-world validation.**
