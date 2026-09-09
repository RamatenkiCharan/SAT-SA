"""
Datasets API Endpoints.
Handles file ingestion, benchmark scenario generation, versioning, and dataset switching.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.repositories.in_memory_repo import SATRepository, get_repository
from backend.security.auth import UserContext, get_current_user, require_analyst_or_above, require_supervisor

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


class LoadDemoRequest(BaseModel):
    scenario_type: str = "critical_infrastructure"  # critical_infrastructure | held_out_test
    dataset_name: Optional[str] = None


class SwitchVersionRequest(BaseModel):
    dataset_version_id: UUID


@router.get("")
def list_datasets(
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(get_current_user),
):
    """List all loaded dataset versions. Requires authentication."""
    return {
        "active_version_id": str(repo.active_dataset_version_id) if repo.active_dataset_version_id else None,
        "datasets": repo.list_datasets(),
    }


@router.post("/load-demo")
def load_demo_dataset(
    req: LoadDemoRequest,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst_or_above),
):
    """Load a synthetic benchmark dataset. Requires analyst or higher role."""
    is_held_out = req.scenario_type == "held_out_test"
    dataset_id = uuid4()
    version_id = uuid4()
    ds_name = req.dataset_name or (
        "Held-Out Validation Benchmark (v2.0)" if is_held_out else "Multi-Sector Critical Infrastructure SOC Operational Evidence Pack"
    )

    raw_bundle, scenarios = generate_synthetic_soc_benchmark(
        seed=101 if is_held_out else 42,
        dataset_version_id=version_id,
        is_held_out=is_held_out,
    )

    canonical_ds, reconstructed_ds, bm_engine, findings, dq_res, analysis_run_id = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=version_id,
    )

    ver_meta = repo.register_dataset_version(
        dataset_id=dataset_id,
        dataset_name=ds_name,
        source_file_ref="synthetic://sih-problem-26157-benchmark",
        canonical_dataset=canonical_ds,
        reconstructed_dataset=reconstructed_ds,
        benchmark_engine=bm_engine,
        findings=findings,
        dq_score=round(dq_res.score, 4),
        description="Comprehensive multi-CSE dataset containing healthy baseline entities, Goodhart's Law execution gaps, and negative-space coverage monitoring anomalies.",
        analysis_run_id=analysis_run_id,
        ruleset_version="V1",
    )

    return {
        "status": "success",
        "dataset_id": str(dataset_id),
        "dataset_version_id": str(version_id),
        "dataset_name": ds_name,
        "row_count": ver_meta.row_count,
        "cse_count": len(canonical_ds.cse_list),
        "findings_generated": len(findings),
        "data_quality_score": round(dq_res.score, 4),
        "data_quality_components": {
            "completeness": round(dq_res.components.completeness_ratio, 4),
            "consistency": round(dq_res.components.consistency_ratio, 4),
            "coverage": round(dq_res.components.coverage_ratio, 4),
            "sample_sufficiency": round(dq_res.components.sample_sufficiency_ratio, 4),
        },
    }


@router.post("/upload")
async def upload_dataset_file(
    file: UploadFile,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst_or_above),
):
    """Upload a CSV or JSON dataset file. Requires analyst or higher role."""
    from backend.services.ingestion import parse_raw_payload, IngestionValidationError

    contents = await file.read()
    filename = file.filename or "upload.json"

    try:
        raw_bundle, warnings = parse_raw_payload(contents, filename)
    except IngestionValidationError as e:
        raise HTTPException(status_code=400, detail=f"Ingestion validation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse uploaded file: {str(e)}")

    dataset_id = uuid4()
    version_id = uuid4()

    canonical_ds, reconstructed_ds, bm_engine, findings, dq_res, analysis_run_id = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=version_id,
    )

    ver_meta = repo.register_dataset_version(
        dataset_id=dataset_id,
        dataset_name=f"Upload: {filename}",
        source_file_ref=filename,
        canonical_dataset=canonical_ds,
        reconstructed_dataset=reconstructed_ds,
        benchmark_engine=bm_engine,
        findings=findings,
        dq_score=round(dq_res.score, 4),
        description=f"User-submitted SOC operational evidence package ({filename})",
        analysis_run_id=analysis_run_id,
        ruleset_version="V1",
    )

    return {
        "status": "success",
        "dataset_id": str(dataset_id),
        "dataset_version_id": str(version_id),
        "row_count": ver_meta.row_count,
        "findings_generated": len(findings),
        "data_quality_score": round(dq_res.score, 4),
        "data_quality_components": {
            "completeness": round(dq_res.components.completeness_ratio, 4),
            "consistency": round(dq_res.components.consistency_ratio, 4),
            "coverage": round(dq_res.components.coverage_ratio, 4),
            "sample_sufficiency": round(dq_res.components.sample_sufficiency_ratio, 4),
        },
        "parse_warnings": warnings,
    }


@router.post("/switch-version")
def switch_active_version(
    req: SwitchVersionRequest,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_supervisor),
):
    """Switch the active dataset version. Requires supervisor or admin role."""
    if req.dataset_version_id not in repo.dataset_versions:
        raise HTTPException(status_code=404, detail="Dataset version not found.")
    repo.active_dataset_version_id = req.dataset_version_id
    return {"status": "success", "active_version_id": str(req.dataset_version_id)}
