"""
SAT-SA Backend Application Entrypoint.
Wires REST routers, CORS middleware, offline air-gapped readiness, pre-seeds demo benchmark data,
and serves the React SPA frontend.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.api.audit import router as audit_router
from backend.api.auth import router as auth_router
from backend.api.benchmarks import router as benchmarks_router
from backend.api.datasets import router as datasets_router
from backend.api.export import router as export_router
from backend.api.findings import router as findings_router
from backend.api.reviews import router as reviews_router
from backend.api.rulesets import router as rulesets_router
from backend.api.validation import router as validation_router
from backend.repositories.in_memory_repo import get_repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Pre-seed baseline multi-sector critical infrastructure demo pack
    repo = get_repository()
    if not repo.datasets:
        dataset_id = uuid4()
        version_id = uuid4()
        raw_bundle, _ = generate_synthetic_soc_benchmark(seed=42, dataset_version_id=version_id)
        canonical_ds, reconstructed_ds, bm_engine, findings, dq_res, analysis_run_id = run_full_analytical_pipeline(
            raw_bundle=raw_bundle,
            dataset_version_id=version_id,
        )
        repo.register_dataset_version(
            dataset_id=dataset_id,
            dataset_name="Multi-Sector Critical Infrastructure SOC Operational Evidence Pack (Default)",
            source_file_ref="synthetic://sih-problem-26157-default",
            canonical_dataset=canonical_ds,
            reconstructed_dataset=reconstructed_ds,
            benchmark_engine=bm_engine,
            findings=findings,
            dq_score=round(dq_res.score, 4),
            description="Pre-seeded multi-sector CSE operational evidence bundle featuring National Power Dispatch Center (NPDC) Goodhart's Law case study.",
            analysis_run_id=analysis_run_id,
            ruleset_version="V1",
        )
    yield



app = FastAPI(
    title="SAT-SA Supervisory Analytics API",
    description="Supervisory Analytics Tool for SOC Assessment (SIH Problem 26157) - NCIIPC Operational Evidence Examiner.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local web interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(auth_router)
app.include_router(datasets_router)
app.include_router(findings_router)
app.include_router(reviews_router)
app.include_router(benchmarks_router)
app.include_router(validation_router)
app.include_router(audit_router)
app.include_router(export_router)
app.include_router(rulesets_router)


@app.get("/api/health")
def health() -> dict:
    repo = get_repository()
    return {
        "status": "ok",
        "service": "SAT-SA Supervisory Analytics Engine",
        "offline_mode": True,
        "active_version_id": str(repo.active_dataset_version_id) if repo.active_dataset_version_id else None,
        "datasets_count": len(repo.datasets),
        "audit_events_count": len(repo.audit_events),
    }


# Mount Static Frontend (if built)
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
