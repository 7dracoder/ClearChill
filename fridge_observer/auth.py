"""Authentication utilities — password hashing and JWT tokens."""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

# ── Config ────────────────────────────────────────────────────
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7   # 7 days
REMEMBER_ME_EXPIRE_MINUTES  = 60 * 24 * 30  # 30 days
COOKIE_NAME = "fridge_session"


# ── Password helpers ──────────────────────────────────────────

def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── JWT helpers ───────────────────────────────────────────────

def create_access_token(user_id: int, email: str, remember_me: bool = False) -> str:
    expire_minutes = REMEMBER_ME_EXPIRE_MINUTES if remember_me else ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT. Returns payload dict or None."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


# ── FastAPI dependency ────────────────────────────────────────

from fastapi import Cookie, HTTPException, status


def get_current_user(fridge_session: Optional[str] = Cookie(default=None)) -> dict:
    """FastAPI dependency — returns the current user payload or raises 401."""
    if not fridge_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    payload = decode_token(fridge_session)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )
    return payload


def get_optional_user(fridge_session: Optional[str] = Cookie(default=None)) -> Optional[dict]:
    """FastAPI dependency — returns user payload or None (no error)."""
    if not fridge_session:
        return None
    return decode_token(fridge_session)
