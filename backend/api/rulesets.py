"""
Rulesets API Endpoints (SRS §24 / §52).
Exposes versioned configurations of Data Quality weights, Fusion weights, and Detector thresholds.
Supports auditable configuration management and reproducible provenance across analysis runs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from analytics.rulesets.ruleset_manager import (
    RulesetRecord,
    get_ruleset,
    list_rulesets,
    register_ruleset,
)
from backend.repositories.in_memory_repo import SATRepository, get_repository
from backend.security.auth import UserContext, require_admin

router = APIRouter(prefix="/api/rulesets", tags=["rulesets"])


class CreateRulesetRequest(BaseModel):
    ruleset_version: str = Field(..., description="Unique version tag, e.g., 'V2'")
    name: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Detailed scope of ruleset")
    data_quality_weights: dict[str, float]
    fusion_weights: dict[str, Any]
    detector_thresholds: dict[str, Any]


@router.get("")
def get_all_rulesets() -> dict[str, Any]:
    """Lists all available versioned rulesets."""
    records = list_rulesets()
    return {
        "count": len(records),
        "rulesets": [r.to_dict() for r in records],
    }


@router.get("/{version}")
def get_ruleset_by_version(version: str) -> dict[str, Any]:
    """Retrieves specific versioned ruleset by version string (e.g., 'V1')."""
    record = get_ruleset(version)
    if not record or record.ruleset_version.upper() != version.upper():
        raise HTTPException(status_code=404, detail=f"Ruleset version '{version}' not found.")
    return record.to_dict()


@router.post("", dependencies=[Depends(require_admin)])
def create_versioned_ruleset(
    req: CreateRulesetRequest,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_admin),
) -> dict[str, Any]:
    """Registers a new immutable ruleset version (Admin only)."""
    existing = get_ruleset(req.ruleset_version)
    if existing and existing.ruleset_version.upper() == req.ruleset_version.upper():
        raise HTTPException(
            status_code=400,
            detail=f"Ruleset version '{req.ruleset_version}' already exists and is immutable.",
        )

    record = RulesetRecord(
        ruleset_id=uuid4(),
        ruleset_version=req.ruleset_version.upper(),
        name=req.name,
        description=req.description,
        created_at=datetime.now(timezone.utc),
        data_quality_weights=req.data_quality_weights,
        fusion_weights=req.fusion_weights,
        detector_thresholds=req.detector_thresholds,
    )
    register_ruleset(record)

    repo.record_audit_event(
        user_id=user.user_id,
        username=user.username,
        action="REGISTER_VERSIONED_RULESET",
        target_type="ruleset",
        target_id=str(record.ruleset_id),
        details={
            "ruleset_version": record.ruleset_version,
            "name": record.name,
        },
    )

    return {
        "status": "success",
        "ruleset": record.to_dict(),
    }
