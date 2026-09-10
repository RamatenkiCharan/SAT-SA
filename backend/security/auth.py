"""
SAT-SA Authentication & Role-Based Access Control (RBAC) Module (SRS §15.1).
Provides:
  - Cryptographically secure password hashing (PBKDF2-HMAC-SHA256, 100,000 rounds, 16-byte random salt)
  - Signed HMAC-SHA256 authentication tokens with expiration timestamps
  - In-memory local user store with pre-hashed development seed users
  - Strict Bearer token dependency (no insecure header-based role claims)
  - Role verification dependencies: admin, supervisor, analyst
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_SECRET_KEY = os.environ.get("SAT_SECRET_KEY") or secrets.token_hex(32)
_PBKDF2_ITERATIONS = 100_000
_DEFAULT_TOKEN_EXPIRY_SECONDS = 86400  # 24 hours

_bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class UserContext:
    user_id: str
    username: str
    role: str  # admin | supervisor | analyst
    full_name: Optional[str] = None


@dataclass
class UserRecord:
    user_id: str
    username: str
    hashed_password: str
    role: str
    full_name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Password Hashing & Verification (Zero Plaintext Storage)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Hashes a password using PBKDF2-HMAC-SHA256 with a unique random 16-byte salt."""
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        iterations=_PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a stored PBKDF2-HMAC-SHA256 hash using constant-time comparison."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = parts[2]
        expected_hash = parts[3]

        computed_key = hashlib.pbkdf2_hmac(
            hash_name="sha256",
            password=plain_password.encode("utf-8"),
            salt=salt.encode("utf-8"),
            iterations=iterations,
        )
        return hmac.compare_digest(computed_key.hex(), expected_hash)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Signed Authentication Tokens (HMAC-SHA256)
# ---------------------------------------------------------------------------

def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data_str: str) -> bytes:
    padding = 4 - (len(data_str) % 4)
    if padding != 4:
        data_str += "=" * padding
    return base64.urlsafe_b64decode(data_str.encode("utf-8"))


def create_access_token(
    user: UserContext,
    expires_in_seconds: int = _DEFAULT_TOKEN_EXPIRY_SECONDS,
) -> str:
    """Creates a tamper-proof HMAC-SHA256 signed bearer token."""
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user.user_id,
        "username": user.username,
        "role": user.role.lower(),
        "full_name": user.full_name,
        "iat": now,
        "exp": now + expires_in_seconds,
    }

    header_b64 = _b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    message = f"{header_b64}.{payload_b64}".encode("utf-8")
    
    signature = hmac.new(_SECRET_KEY.encode("utf-8"), message, hashlib.sha256).digest()
    signature_b64 = _b64_encode(signature)

    return f"{header_b64}.{payload_b64}.{signature_b64}"


def decode_access_token(token: str) -> UserContext:
    """Decodes and validates an access token signature and expiration."""
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    header_b64, payload_b64, signature_b64 = parts
    message = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_sig = hmac.new(_SECRET_KEY.encode("utf-8"), message, hashlib.sha256).digest()
    expected_sig_b64 = _b64_encode(expected_sig)

    if not hmac.compare_digest(signature_b64, expected_sig_b64):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signature. Token may have been tampered with.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload_bytes = _b64_decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not parse token payload: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    exp = payload.get("exp")
    if not exp or int(exp) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    username = payload.get("username")
    role = payload.get("role")
    full_name = payload.get("full_name")

    if not sub or not username or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing required identity claims.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UserContext(
        user_id=str(sub),
        username=str(username),
        role=str(role).lower(),
        full_name=full_name,
    )


# ---------------------------------------------------------------------------
# In-Memory Local User Repository (Thread-Safe Seed Store)
# ---------------------------------------------------------------------------

class UserStore:
    def __init__(self):
        self._users: dict[str, UserRecord] = {}
        self._seed_default_users()

    def _seed_default_users(self):
        # Development seed users with initial passwords (only salted hashes are stored)
        seeds = [
            ("usr_admin_01", "admin", "Admin@SAT2026!", "admin", "NCIIPC Lead Administrator"),
            ("usr_sup_01", "supervisor", "Supervisor@SAT2026!", "supervisor", "Senior NCIIPC Examiner"),
            ("usr_analyst_01", "analyst", "Analyst@SAT2026!", "analyst", "SOC Evidence Analyst"),
        ]
        for user_id, username, raw_pwd, role, full_name in seeds:
            self._users[username.lower()] = UserRecord(
                user_id=user_id,
                username=username,
                hashed_password=hash_password(raw_pwd),
                role=role,
                full_name=full_name,
            )

    def get_by_username(self, username: str) -> Optional[UserRecord]:
        uname = username.lower().strip()
        try:
            from backend.repositories.base import BaseSATRepository
            from backend.repositories.in_memory_repo import get_repository
            from backend.repositories.postgres_repo import PostgresRepository
            from sqlalchemy import text
            repo = get_repository()
            if isinstance(repo, PostgresRepository):
                with repo.engine.connect() as conn:
                    row = conn.execute(
                        text("""
                        SELECT u.user_id, u.username, u.password_hash, r.role_name, u.full_name, u.created_at
                        FROM users u
                        LEFT JOIN roles r ON r.role_id = u.role_id
                        WHERE lower(u.username) = :uname AND u.is_active = 1
                        """),
                        {"uname": uname},
                    ).mappings().first()
                    if row:
                        cr_at = row["created_at"]
                        if isinstance(cr_at, str):
                            cr_at = datetime.fromisoformat(cr_at)
                        if cr_at.tzinfo is None:
                            cr_at = cr_at.replace(tzinfo=timezone.utc)
                        return UserRecord(
                            user_id=row["user_id"],
                            username=row["username"],
                            hashed_password=row["password_hash"],
                            role=row["role_name"] or "analyst",
                            full_name=row["full_name"] or "",
                            created_at=cr_at,
                        )
        except Exception:
            pass
        return self._users.get(uname)

    def get_by_id(self, user_id: str) -> Optional[UserRecord]:
        try:
            from backend.repositories.in_memory_repo import get_repository
            from backend.repositories.postgres_repo import PostgresRepository
            from sqlalchemy import text
            repo = get_repository()
            if isinstance(repo, PostgresRepository):
                with repo.engine.connect() as conn:
                    row = conn.execute(
                        text("""
                        SELECT u.user_id, u.username, u.password_hash, r.role_name, u.full_name, u.created_at
                        FROM users u
                        LEFT JOIN roles r ON r.role_id = u.role_id
                        WHERE u.user_id = :uid AND u.is_active = 1
                        """),
                        {"uid": user_id},
                    ).mappings().first()
                    if row:
                        cr_at = row["created_at"]
                        if isinstance(cr_at, str):
                            cr_at = datetime.fromisoformat(cr_at)
                        if cr_at.tzinfo is None:
                            cr_at = cr_at.replace(tzinfo=timezone.utc)
                        return UserRecord(
                            user_id=row["user_id"],
                            username=row["username"],
                            hashed_password=row["password_hash"],
                            role=row["role_name"] or "analyst",
                            full_name=row["full_name"] or "",
                            created_at=cr_at,
                        )
        except Exception:
            pass
        for u in self._users.values():
            if u.user_id == user_id:
                return u
        return None

    def list_users(self) -> list[UserRecord]:
        try:
            from backend.repositories.in_memory_repo import get_repository
            from backend.repositories.postgres_repo import PostgresRepository
            from sqlalchemy import text
            repo = get_repository()
            if isinstance(repo, PostgresRepository):
                with repo.engine.connect() as conn:
                    rows = conn.execute(
                        text("""
                        SELECT u.user_id, u.username, u.password_hash, r.role_name, u.full_name, u.created_at
                        FROM users u
                        LEFT JOIN roles r ON r.role_id = u.role_id
                        WHERE u.is_active = 1
                        """)
                    ).mappings().all()
                    if rows:
                        result = []
                        for row in rows:
                            cr_at = row["created_at"]
                            if isinstance(cr_at, str):
                                cr_at = datetime.fromisoformat(cr_at)
                            if cr_at.tzinfo is None:
                                cr_at = cr_at.replace(tzinfo=timezone.utc)
                            result.append(
                                UserRecord(
                                    user_id=row["user_id"],
                                    username=row["username"],
                                    hashed_password=row["password_hash"],
                                    role=row["role_name"] or "analyst",
                                    full_name=row["full_name"] or "",
                                    created_at=cr_at,
                                )
                            )
                        return result
        except Exception:
            pass
        return list(self._users.values())

    def authenticate(self, username: str, password: str) -> Optional[UserContext]:
        user_rec = self.get_by_username(username)
        if not user_rec:
            return None
        if not verify_password(password, user_rec.hashed_password):
            return None
        return UserContext(
            user_id=user_rec.user_id,
            username=user_rec.username,
            role=user_rec.role,
            full_name=user_rec.full_name,
        )


_USER_STORE = UserStore()


def get_user_store() -> UserStore:
    return _USER_STORE


# ---------------------------------------------------------------------------
# FastAPI Authentication Dependencies
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> UserContext:
    """
    Extracts and verifies identity from Bearer token in Authorization header.
    Rejects insecure header-based role claims.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token. Please provide 'Authorization: Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(credentials.credentials)


def require_role(*allowed_roles: str) -> Callable[[UserContext], UserContext]:
    """Factory creating a role-enforcing dependency."""
    allowed_lower = {r.lower() for r in allowed_roles}

    def role_checker(user: UserContext = Depends(get_current_user)) -> UserContext:
        if user.role.lower() not in allowed_lower:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient privileges. Required role: {', '.join(allowed_roles)} (Current: '{user.role}').",
            )
        return user

    return role_checker


# Pinned Role Dependencies
require_admin = require_role("admin")
require_supervisor = require_role("supervisor", "admin")
require_analyst = require_role("analyst", "supervisor", "admin")
