"""
Authentication & Session Management API Endpoints (SRS §15.1).
Handles:
  - User login & credential verification
  - Signed Bearer token issuance
  - Current session inspection (/api/auth/me)
  - User roster queries for administrators
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.security.auth import (
    UserContext,
    AuthenticationBackendError,
    UserStore,
    create_access_token,
    get_current_user,
    get_user_store,
    require_admin,
    require_supervisor,
)

router = APIRouter(prefix="/api/auth", tags=["authentication"])
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_MAX_ATTEMPTS = 5
_login_attempts: dict[str, deque[float]] = defaultdict(deque)
_login_attempts_lock = threading.Lock()


def _check_login_rate_limit(client_key: str) -> None:
    now = time.monotonic()
    with _login_attempts_lock:
        attempts = _login_attempts[client_key]
        while attempts and now - attempts[0] >= _LOGIN_WINDOW_SECONDS:
            attempts.popleft()
        if len(attempts) >= _LOGIN_MAX_ATTEMPTS:
            raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")


def _record_failed_login(client_key: str) -> None:
    with _login_attempts_lock:
        _login_attempts[client_key].append(time.monotonic())


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, description="Registered username (e.g. admin, supervisor, analyst)")
    password: str = Field(..., min_length=1, description="Plaintext password for verification")


class UserProfileResponse(BaseModel):
    user_id: str
    username: str
    role: str
    full_name: Optional[str] = None


class LoginResponse(BaseModel):
    status: str = "success"
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600
    user: UserProfileResponse


@router.post("/login", response_model=LoginResponse)
def login(
    req: LoginRequest,
    request: Request,
    user_store: UserStore = Depends(get_user_store),
):
    """
    Authenticates user credentials and issues a signed Bearer token.
    Rejects unknown users and invalid passwords with HTTP 401 Unauthorized.
    """
    client_key = request.client.host if request.client else "unknown"
    _check_login_rate_limit(client_key)
    try:
        user_ctx = user_store.authenticate(req.username, req.password)
    except AuthenticationBackendError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable.",
        )
    if not user_ctx:
        _record_failed_login(client_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user_ctx)
    return LoginResponse(
        status="success",
        access_token=token,
        token_type="bearer",
        expires_in=3600,
        user=UserProfileResponse(
            user_id=user_ctx.user_id,
            username=user_ctx.username,
            role=user_ctx.role,
            full_name=user_ctx.full_name,
        ),
    )


@router.get("/me", response_model=UserProfileResponse)
def get_authenticated_user_profile(
    current_user: UserContext = Depends(get_current_user),
):
    """Returns the authenticated identity claims extracted from the verified Bearer token."""
    return UserProfileResponse(
        user_id=current_user.user_id,
        username=current_user.username,
        role=current_user.role,
        full_name=current_user.full_name,
    )


@router.get("/users")
def list_system_users(
    user_store: UserStore = Depends(get_user_store),
    current_user: UserContext = Depends(require_admin),
):
    """Lists registered users and assigned roles (requires admin role)."""
    return [
        {
            "user_id": u.user_id,
            "username": u.username,
            "role": u.role,
            "full_name": u.full_name,
            "created_at": u.created_at.isoformat(),
        }
        for u in user_store.list_users()
    ]
