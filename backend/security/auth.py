"""
Hackathon Security Baseline (SRS §15.1) - Role-Based Access Control (RBAC).
Provides user authentication context, role verification (supervisor, analyst, admin),
and audit user resolution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from fastapi import Header, HTTPException, status


@dataclass(frozen=True)
class UserContext:
    user_id: str
    username: str
    role: str  # supervisor | analyst | admin


_DEFAULT_SUPERVISOR = UserContext(
    user_id="sup_001",
    username="Senior NCIIPC Examiner",
    role="supervisor",
)


def get_current_user(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
) -> UserContext:
    """
    Resolves local security context from headers or falls back to default examiner context.
    Strictly local, offline-ready.
    """
    if x_user_id and x_user_role:
        return UserContext(
            user_id=x_user_id,
            username=x_user_name or f"User_{x_user_id}",
            role=x_user_role.lower(),
        )
    return _DEFAULT_SUPERVISOR


def require_supervisor(user: UserContext) -> None:
    if user.role not in ("supervisor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: This action requires the 'supervisor' or 'admin' role.",
        )
