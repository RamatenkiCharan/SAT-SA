"""
Datasets API Endpoints.
Handles file ingestion, benchmark scenario generation, versioning, and dataset switching.
"""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel

from analytics.synthetic_generator import generate_synthetic_soc_benchmark, run_full_analytical_pipeline
from backend.repositories.in_memory_repo import SATRepository, get_repository
from backend.security.auth import UserContext, require_analyst, require_supervisor
from backend.services.ingestion import IngestionValidationError, ingest_file_stream

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


class LoadDemoRequest(BaseModel):
    scenario_type: str = "critical_infrastructure"  # critical_infrastructure | held_out_test
    dataset_name: Optional[str] = None


class SwitchVersionRequest(BaseModel):
    dataset_version_id: UUID


@router.get("")
def list_datasets(
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst),
):
    return {
        "active_version_id": str(repo.active_dataset_version_id) if repo.active_dataset_version_id else None,
        "datasets": repo.list_datasets(),
    }


@router.post("/load-demo")
def load_demo_dataset(
    req: LoadDemoRequest,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_supervisor),
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

    pipeline_res = run_full_analytical_pipeline(
        raw_bundle=raw_bundle,
        dataset_version_id=version_id,
    )

    ver_meta = repo.register_dataset_version(
        dataset_id=dataset_id,
        dataset_name=ds_name,
        source_file_ref="synthetic://sih-problem-26157-benchmark",
        canonical_dataset=pipeline_res.canonical_dataset,
        reconstructed_dataset=pipeline_res.reconstructed_dataset,
        benchmark_engine=pipeline_res.benchmark_engine,
        findings=pipeline_res.findings,
        dq_result=pipeline_res.data_quality_result,
        description="Comprehensive multi-CSE dataset containing healthy baseline entities, Goodhart's Law execution gaps, and negative-space coverage monitoring anomalies.",
        analysis_run=pipeline_res.analysis_run,
    )

    dq = pipeline_res.data_quality_result
    return {
        "status": "success",
        "dataset_id": str(dataset_id),
        "dataset_version_id": str(version_id),
        "dataset_name": ds_name,
        "row_count": ver_meta.row_count,
        "cse_count": len(pipeline_res.canonical_dataset.cse_list),
        "findings_generated": len(pipeline_res.findings),
        "data_quality_score": dq.score,
        "data_quality_breakdown": {
            "overall_score": round(dq.score * 100, 1),
            "completeness": round(dq.components.completeness_ratio * 100, 1),
            "consistency": round(dq.components.consistency_ratio * 100, 1),
            "coverage": round(dq.components.coverage_ratio * 100, 1),
            "sample_sufficiency": round(dq.components.sample_sufficiency_ratio * 100, 1),
            "warnings": dq.warnings,
        },
    }


@router.post("/upload")
async def upload_dataset_file(
    file: UploadFile,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_supervisor),
):
    """Upload a CSV or JSON dataset file. Requires analyst or higher role."""
    from backend.services.ingestion import parse_raw_payload, IngestionValidationError

    contents = await file.read()
    filename = file.filename or "upload.json"

    try:
        ingest_res = ingest_file_stream(
            contents=contents,
            filename=filename,
            repo=repo,
        )
    except IngestionValidationError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process uploaded file: {str(e)}")

    return ingest_res.to_dict()


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

