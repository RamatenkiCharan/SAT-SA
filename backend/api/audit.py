"""
Audit Log API Endpoints.
Retrieves immutable historical log of supervisory examinations, dataset imports, and decisions.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from backend.repositories.in_memory_repo import SATRepository, get_repository
from backend.security.auth import UserContext, require_admin

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("")
def list_audit_events(
    limit: int = 100,
    repo: SATRepository = Depends(get_repository),
    current_user: UserContext = Depends(require_admin),
):
    events = repo.get_audit_events(limit=limit)
    return [
        {
            "audit_event_id": str(e.audit_event_id),
            "user_id": e.user_id,
            "username": e.username,
            "action": e.action,
            "target_type": e.target_type,
            "target_id": e.target_id,
            "occurred_at": e.occurred_at.isoformat(),
            "details": e.details,
        }
        for e in events
    ]
