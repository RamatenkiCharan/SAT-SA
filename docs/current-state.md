# SAT-SA — Current Engineering State

## Scope

SAT-SA is a supervisory analytics prototype for reviewing periodic SOC
operational evidence. It is not a SIEM, SOC, SOAR, EDR/XDR, real-time monitor,
or autonomous auditor. Findings are evidence-backed review signals for a human
supervisor, not declarations of operational failure.

## Implemented baseline

- CSV/JSON ingestion, canonical evidence, workflow reconstruction, provenance,
  versioned datasets, and durable SQLite/PostgreSQL persistence.
- Data Trust gating, execution-gap signals, negative-space coverage signals,
  peer benchmarking, deterministic explainability, evidence fusion, review
  prioritization, and review-budget selection.
- Explicit authentication/RBAC, login throttling, bounded uploads, safe
  client-facing errors, audit events, and migration-based schema authority.
- A React/TypeScript frontend with explicit sign-in and no persisted browser
  bearer token.

## Validation and verification

The robust synthetic protocol has 240 scenarios: 168 tuning, 72 held-out, and
36 hard negatives. Its latest held-out detector result is 36 TP, 1 FP, 248 TN,
and 3 FN: precision 97.30%, recall 92.31%, F1 94.74%, and FPR 0.40%. Bootstrap
intervals are emitted by the protocol. These are synthetic detector results,
not production, real-SOC, or supervisory-review-utility validation.

The last full baseline verification completed with 235 passing backend tests.
The focused validation/API contract tests passed 25 tests; the frontend
type-check and production build passed, and lint now completes without React
effect warnings. Run the commands below for the current count after any
subsequent change.

Raw finding Top-K measures detector-target coverage. They do not evaluate
`ReviewBudgetOptimizer` utility. A separate utility benchmark is intentionally
blocked until independently authored supervisory labels are available; reusing
planted detector labels would leak generator truth.

## Operational configuration

PostgreSQL requires `DATABASE_URL` or `POSTGRES_PASSWORD`; there is no
hardcoded database password. A durable production startup applies migrations,
roles, and the baseline ruleset but does not create known demo users or synthetic
datasets. Test/demo users and synthetic data require explicit opt-in environment
variables documented in `.env.example` and the root README.

## Verification commands

- `python -m pytest tests -q`
- `python scripts/run_robust_validation.py --output results/robust_validation.json`
- `cd frontend; npm run lint; npm run build; npm audit --audit-level=high`
- `python -m bandit -r backend -ll`

See `SAT_SA_POST_DIAGNOSTIC_VERIFICATION_REPORT.md` for historical
post-diagnostic provenance and `SUPERVISORY_RANKING_DIAGNOSTIC.md` for the
current diagnostic limitations.
