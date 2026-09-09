# SAT-SA — Current State

> Update this file when meaningful work completes. Do not leave fake
> placeholder status (PROJECT_CONTEXT §88).

## Current Phase
P0-A — Foundations (in progress)

## Current Sprint Goal
Reliable canonical dataset with quality-score information (P0-A exit
condition per SRS §29 / PROJECT_CONTEXT §38).

## Completed
- Repository scaffold matching SRS §28 structure.
- Canonical Pydantic models for the full evidence graph (`backend/models/canonical.py`):
  CSE, Asset, Alert, Investigation, Case, Escalation, Action, Closure,
  CoverageObservation, PeerGroup, DataQualityScore, Finding — with the
  finding-generation contract check (evidence_refs required, ≥2 independent
  signals, data quality > 0.6) implemented as executable validation, not
  just documentation.
- Initial PostgreSQL schema (`database/migrations/001_initial_schema.sql`)
  covering all §9/§24 entities, dataset versioning/immutability structure,
  a `rulesets` table for versioned weights, `finding_evidence` linkage, and
  audit events.
- Versioned ruleset seed data (`database/seed/rulesets_v1.sql`) pinning the
  §7.2.1 data-quality weights and §10.5 evidence-fusion weights, plus the
  three P0 execution-gap detector configs and the coverage-gap detector
  config — as data, not hardcoded constants.
- Data Quality Score engine (`analytics/data_quality/quality_score.py`)
  implementing the exact §7.2.1 formula as a pure, DB-free function, with
  9 passing unit tests (`tests/test_quality_score.py`) covering normal,
  boundary, low-sample, missing-data, malformed-input (zero-denominator),
  and weight-configurability cases.
- Ingestion service skeleton (`backend/services/ingestion.py`) for
  CSV/JSON only (FR-002), with file-type/size validation and dataset
  versioning as an in-memory result object.
- Minimal FastAPI app (`backend/main.py`) exposing `/api/health` and a
  `/api/datasets` upload endpoint wired to the ingestion skeleton.
- Docker Compose + Dockerfile for local Postgres + backend.

## In Progress
- Nothing actively in progress — this is a clean starting point for the
  next bounded task.

## Blocked
- None.

## Known Risks / Explicit Gaps (do not silently forget these)
- `/api/datasets` does NOT yet persist to Postgres. It returns the parsed
  in-memory result only. The repository layer (`backend/repositories/`) that
  inserts into `dataset_versions`/`cse`/etc. does not exist yet.
- No canonicalization step exists yet (raw parsed rows are not mapped to the
  canonical Pydantic models). This is analytics/canonicalization's job and
  is unbuilt.
- No authentication/RBAC implemented yet (SRS §15.1 hackathon baseline is
  NOT satisfied — do not claim it is in any pitch material until built).
- No detectors (FR-030/032/033/041) implemented yet — only their ruleset
  configs exist as seed data.
- No synthetic data generator yet (§19.1) — nothing to test detectors
  against once they exist.
- Team size/timeline (SRS §33 Assumptions) has not been filled in with real
  numbers — the P0 tier boundary should be re-checked against actual
  capacity before freezing scope.

## Next Milestones
1. Repository layer: wire `dataset_versions`/`cse`/`assets`/... inserts so
   `/api/datasets` actually persists (closes the biggest current gap).
2. Canonicalization step: map raw parsed CSV/JSON rows into the canonical
   Pydantic models with explicit column-mapping config (not silently
   assuming column names match).
3. Data Trust layer wiring: connect `analytics/data_quality` to real
   ingested data (completeness/consistency/coverage counts computed from
   actual rows, not synthetic numbers).
4. Synthetic data generator (§19.1) — required before any detector can be
   validated, and must respect the Generator/Detector Independence
   Protocol (§19.4) from day one, not retrofitted later.

## Latest Verified Commit
Not yet committed to `RamatenkiCharan/SAT-SA` (repo was empty at time of
this scaffold; push instructions are in the top-level README).

## Latest Verified Test Status
`pytest tests/test_quality_score.py` — 9 passed, 0 failed (run locally in
the sandbox that generated this scaffold; re-run yourself after pushing).

## Last Validation Run
None yet — no detectors exist to validate against ground truth.
