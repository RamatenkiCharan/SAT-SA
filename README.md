# SAT-SA — Supervisory Analytics Tool for SOC Assessment

SIH Problem Statement 26157. Prototype for NCIIPC: analyzes SOC operational
evidence (alerts, investigations, cases, escalations, closures) to surface
potential execution gaps and negative-space (coverage) signals for human
supervisory review. It is not a SIEM, SOAR, or SOC replacement — see
`PROJECT_CONTEXT.md` §8/§9 for the full boundary.

This is the **P0-A (Foundations)** scaffold only. See `docs/current-state.md`
for exactly what is and isn't built yet — don't assume more exists than is
listed there.

## What's here right now

```
backend/          FastAPI app, canonical Pydantic models, ingestion skeleton
analytics/        data_quality (implemented) + empty module dirs for the
                   remaining P0-B engines (execution_gap, negative_space,
                   peer_benchmark, fusion, explainability) — not yet built
database/         Postgres schema (001_initial_schema.sql) + versioned
                   ruleset seed data
datasets/         empty — generator/scenarios/schemas not yet built
tests/            unit tests for the data-quality-score formula
docs/             current-state.md — the actual source of truth on progress
```

## Local setup

Requires Python 3.12+ and Docker (for Postgres).

```bash
# 1. Start Postgres (and the backend container, though it has almost no
#    wired endpoints yet)
docker compose up -d db

# 2. Apply the schema + seed data manually for now (no migration runner
#    wired yet - psql directly against the container)
docker exec -i $(docker compose ps -q db) psql -U satsa -d satsa < database/migrations/001_initial_schema.sql
docker exec -i $(docker compose ps -q db) psql -U satsa -d satsa < database/seed/rulesets_v1.sql

# 3. Python deps + run the API locally (outside Docker, for iteration speed)
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload

# 4. Run tests
pytest tests/ -v
```

Offline verification (SRS §16/§31): the backend has zero outbound network
calls in its current code. Re-verify this explicitly after every dependency
change — don't assume it stays true.

## Pushing this scaffold into your GitHub repo

This scaffold was generated outside your repository. To publish it:

```bash
cd /path/to/this/scaffold
git init
git remote add origin https://github.com/RamatenkiCharan/SAT-SA.git
git add .
git commit -m "feat: P0-A foundations - canonical model, schema, data quality engine, ingestion skeleton"
git branch -M main
git push -u origin main
```

If the remote already has commits by the time you push (e.g. a teammate
pushed something), pull/rebase first — don't force-push over teammate work
(AGENTS.md §60 Git Safety).

## Source of truth

If anything in this README conflicts with `SAT-SA_SRS_v2_revised.md`, the SRS
wins (see that document's own source-of-truth hierarchy, §35 in
PROJECT_CONTEXT.md). This scaffold implements P0-A only — see
`docs/current-state.md` for the honest list of what's still missing before
P0-B (core detectors) can start.
