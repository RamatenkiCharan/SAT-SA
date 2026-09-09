"""
Hackathon Security Baseline (SRS §15.1) - Local Authentication & Role-Based Access Control (RBAC).
Provides cryptographically verified local token generation, password hashing, and role checks
(supervisor, analyst, admin) for 100% air-gapped, offline operation.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

# Secret key for local signing (air-gapped static secret)
_LOCAL_HMAC_SECRET = b"sat_sa_nciipc_air_gapped_offline_secret_key_2026"
_TOKEN_VALIDITY_SECONDS = 86400 * 7  # 7 days

security_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class UserContext:
    user_id: str
    username: str
    display_name: str
    role: str  # "supervisor" | "analyst" | "admin"


# In-memory local user store with pre-hashed passwords (PBKDF2-HMAC-SHA256)
def hash_password(password: str, salt: bytes = b"sat_sa_salt_2026") -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000).hex()


def verify_password(password: str, hashed: str) -> bool:
    input_hash = hash_password(password)
    return hmac.compare_digest(hashed, input_hash)


_hash_password = hash_password


_LOCAL_USERS_DB: dict[str, dict] = {
    "supervisor": {
        "user_id": "usr_sup_001",
        "username": "supervisor",
        "display_name": "Senior NCIIPC Supervisory Examiner",
        "password_hash": hash_password("sih2026@supervisor"),
        "role": "supervisor",
    },
    "analyst": {
        "user_id": "usr_ana_001",
        "username": "analyst",
        "display_name": "Lead Assessment Analyst",
        "password_hash": hash_password("sih2026@analyst"),
        "role": "analyst",
    },
    "admin": {
        "user_id": "usr_adm_001",
        "username": "admin",
        "display_name": "System Security Administrator",
        "password_hash": hash_password("sih2026@admin"),
        "role": "admin",
    },
}


def authenticate_user(username: str, password: str) -> Optional[UserContext]:
    user_data = _LOCAL_USERS_DB.get(username.lower())
    if not user_data:
        return None
    input_hash = _hash_password(password)
    if not hmac.compare_digest(user_data["password_hash"], input_hash):
        return None
    return UserContext(
        user_id=user_data["user_id"],
        username=user_data["username"],
        display_name=user_data["display_name"],
        role=user_data["role"],
    )


def create_access_token(user: UserContext | dict) -> str:
    """Generates an HMAC-signed local token with timestamp and role claims."""
    if isinstance(user, UserContext):
        payload = {
            "sub": user.user_id,
            "username": user.username,
            "name": user.display_name,
            "role": user.role,
            "exp": int(time.time()) + _TOKEN_VALIDITY_SECONDS,
        }
    else:
        payload = dict(user)
        if "exp" not in payload:
            payload["exp"] = int(time.time()) + _TOKEN_VALIDITY_SECONDS
    payload_bytes = json.dumps(payload).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("utf-8").rstrip("=")
    signature = hmac.new(_LOCAL_HMAC_SECRET, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_access_token(token: str) -> Optional[UserContext]:
    """Validates token signature and expiration."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        payload_b64, signature = parts
        expected_sig = hmac.new(_LOCAL_HMAC_SECRET, payload_b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        # Fix base64 padding
        padded_b64 = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_b64).decode("utf-8"))

        if payload.get("exp", 0) < time.time():
            return None

        return UserContext(
            user_id=payload["sub"],
            username=payload["username"],
            display_name=payload.get("name", payload["username"]),
            role=payload["role"],
        )
    except Exception:
        return None


def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
) -> UserContext:
    """
    Resolves local security context from Bearer token.
    Falls back to default supervisor for unauthenticated local browser sessions.
    """
    if auth_header and auth_header.credentials:
        user = verify_access_token(auth_header.credentials)
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        )

    # Fallback to local default supervisor if running in local standalone mode
    return UserContext(
        user_id="usr_sup_001",
        username="supervisor",
        display_name="Senior NCIIPC Supervisory Examiner",
        role="supervisor",
    )


def require_supervisor(user: UserContext = Depends(get_current_user)) -> UserContext:
    if user.role not in ("supervisor", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: This supervisory action requires 'supervisor' or 'admin' role privileges.",
        )
    return user


def require_admin(user: UserContext = Depends(get_current_user)) -> UserContext:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Administrative privileges required.",
        )
    return user
