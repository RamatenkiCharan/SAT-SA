"""
SAT-SA backend entrypoint.

P0-A scope only: health check + a dataset-upload endpoint wired to the
ingestion service skeleton. Auth/RBAC, findings, peers, analysis-run
endpoints are P0-B/C/D work and are deliberately NOT stubbed here yet -
adding empty placeholder routers now would just be undocumented scope
drift (AGENTS.md §72). Add them in the task that actually implements them.

Run locally:
    uvicorn backend.main:app --reload
"""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, UploadFile

from backend.services.ingestion import IngestionValidationError, ingest_raw_file

app = FastAPI(
    title="SAT-SA API",
    description="Supervisory Analytics Tool for SOC Assessment - P0 prototype API.",
    version="0.1.0-p0a",
)

_UPLOAD_DIR = Path("/tmp/sat-sa-uploads")  # dev-only sandbox path; replace with
_UPLOAD_DIR.mkdir(exist_ok=True)           # a configured, access-controlled dir before demo.


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "offline_mode": True}


@app.post("/api/datasets")
async def create_dataset(file: UploadFile):
    """
    Minimal P0-A upload path: land the file, create a new dataset_version.
    Persistence to Postgres (dataset_versions row insert) is deliberately
    NOT wired yet - this endpoint currently returns the parsed in-memory
    result so the ingestion logic can be exercised end-to-end before the
    repository layer exists. Wiring the DB insert is the next bounded task.
    """
    dest = _UPLOAD_DIR / f"{uuid4()}_{file.filename}"
    contents = await file.read()
    dest.write_bytes(contents)

    try:
        result = ingest_raw_file(
            path=dest,
            dataset_id=uuid4(),       # TODO(P0-A next task): resolve real dataset_id via repository
            next_version_number=1,   # TODO(P0-A next task): compute from DB, not hardcoded
        )
    except IngestionValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "dataset_version_id": str(result.dataset_version.dataset_version_id),
        "row_count": result.row_count,
        "parse_warnings": result.parse_warnings,
        "note": "Row 1-level persistence to Postgres not yet wired - see docs/current-state.md",
    }
