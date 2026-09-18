"""
Analytical Rulesets API Endpoints.
Allows supervisory inspection, auditing, registration, and activation of versioned rulesets.
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.models.ruleset import AnalyticalRuleset
from backend.repositories.in_memory_repo import SATRepository, get_repository
from backend.security.auth import UserContext, require_analyst, require_supervisor
from backend.services.ruleset_service import RulesetService

router = APIRouter(prefix="/api/rulesets", tags=["rulesets"])
logger = logging.getLogger("satsa.api.rulesets")


class RegisterRulesetRequest(BaseModel):
    ruleset_id: Optional[str] = None
    version: str
    name: str
    is_active: bool = False
    effective_timestamp: Optional[str] = None
    author: str = "SAT-SA Supervisory Team"
    rationale: str = "Configured supervisory parameters"
    dq_weights: dict[str, Any]
    fusion_weights: dict[str, Any]
    thresholds: Optional[dict[str, Any]] = None
    detector_config: Optional[dict[str, Any]] = None


@router.get("")
def list_rulesets(
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst),
):
    """Lists all versioned analytical rulesets."""
    rulesets = RulesetService.list_rulesets(repo=repo)
    active = RulesetService.get_active_ruleset(repo=repo)
    return {
        "active_version": active.version,
        "count": len(rulesets),
        "rulesets": [r.to_dict() for r in rulesets],
    }


@router.get("/active")
def get_active_ruleset(
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst),
):
    """Retrieves the active analytical ruleset bundle."""
    active = RulesetService.get_active_ruleset(repo=repo)
    return active.to_dict()


@router.get("/{version}")
def get_ruleset_by_version(
    version: str,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_analyst),
):
    """Retrieves a specific versioned analytical ruleset."""
    try:
        ruleset = RulesetService.get_ruleset_by_version(version, repo=repo)
        return ruleset.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("")
def register_ruleset(
    req: RegisterRulesetRequest,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_supervisor),
):
    """Registers a new versioned ruleset (supervisor or admin only)."""
    try:
        ruleset = AnalyticalRuleset.from_dict(req.model_dump())
        registered = RulesetService.register_ruleset(ruleset, set_active=req.is_active, repo=repo)
        return {
            "status": "success",
            "message": f"Ruleset version '{registered.version}' registered successfully.",
            "ruleset": registered.to_dict(),
        }
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid ruleset configuration.")
    except Exception as exc:
        logger.exception("Ruleset registration failed.")
        raise HTTPException(status_code=500, detail="Unable to register ruleset.") from exc


@router.post("/{version}/activate")
def activate_ruleset(
    version: str,
    repo: SATRepository = Depends(get_repository),
    user: UserContext = Depends(require_supervisor),
):
    """Activates a specific versioned ruleset (supervisor or admin only)."""
    try:
        activated = RulesetService.activate_ruleset(version, repo=repo)
        return {
            "status": "success",
            "message": f"Ruleset version '{version}' is now active.",
            "active_ruleset": activated.to_dict(),
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as exc:
        logger.exception("Ruleset activation failed.")
        raise HTTPException(status_code=500, detail="Unable to activate ruleset.") from exc
