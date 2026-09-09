"""
Local Authentication API Endpoints (SRS §15.1 Hackathon Baseline).
Provides offline login, token issuance, and user context endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from backend.security.auth import (
    UserContext,
    authenticate_user,
    create_access_token,
    get_current_user,
    require_admin,
    require_analyst_or_above,
    _LOCAL_USERS_DB,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    display_name: str
    role: str


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password. Seeded accounts: supervisor/sih2026@supervisor, analyst/sih2026@analyst, admin/sih2026@admin.",
        )
    token = create_access_token(user)
    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
    )


@router.get("/me")
def get_me(user: UserContext = Depends(get_current_user)):
    return {
        "user_id": user.user_id,
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
    }


@router.get("/users")
def list_users(admin: UserContext = Depends(require_admin)):
    return [
        {
            "user_id": u["user_id"],
            "username": u["username"],
            "display_name": u["display_name"],
            "role": u["role"],
        }
        for u in _LOCAL_USERS_DB.values()
    ]
