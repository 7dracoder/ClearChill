"""Auth endpoints — powered by Supabase Auth."""
import logging
import os
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Response, status, Depends, Cookie
from pydantic import BaseModel, field_validator
from typing import Optional

from fridge_observer.supabase_client import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "fridge_session"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")


# ── Models ────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: str
    display_name: str
    password: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, v):
        if not EMAIL_RE.match(v.strip()):
            raise ValueError("Invalid email address")
        return v.strip().lower()

    @field_validator("display_name")
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if len(v) < 2: raise ValueError("Name must be at least 2 characters")
        if len(v) > 60: raise ValueError("Name must be 60 characters or fewer")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8: raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v):
        return v.strip().lower()


class VerifyOTPRequest(BaseModel):
    email: str
    code: str

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v):
        return v.strip().lower()

    @field_validator("code")
    @classmethod
    def clean_code(cls, v):
        return v.strip()


class ResendOTPRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v):
        return v.strip().lower()


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    created_at: str


# ── Cookie helper ─────────────────────────────────────────────

def _set_session_cookie(response: Response, access_token: str, remember_me: bool = False) -> None:
    max_age = (30 * 24 * 60 * 60) if remember_me else (7 * 24 * 60 * 60)
    response.set_cookie(
        key=COOKIE_NAME,
        value=access_token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )


def get_current_user(fridge_session: Optional[str] = Cookie(default=None)) -> dict:
    """FastAPI dependency — validates Supabase JWT and returns user."""
    if not fridge_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        sb = get_supabase()
        user_response = sb.auth.get_user(fridge_session)
        if not user_response or not user_response.user:
            raise HTTPException(status_code=401, detail="Session expired")
        return {"sub": user_response.user.id, "email": user_response.user.email}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Session expired or invalid")


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/signup", status_code=201)
async def signup(body: SignupRequest):
    """
    Create account via Supabase Auth.
    Supabase sends the OTP email automatically.
    """
    try:
        sb = get_supabase()
        result = sb.auth.sign_up({
            "email": body.email,
            "password": body.password,
            "options": {
                "data": {"display_name": body.display_name},
                "email_redirect_to": None,
            }
        })

        if result.user is None:
            raise HTTPException(status_code=400, detail="Signup failed. Please try again.")

        logger.info("New user signed up: %s", body.email)
        return {
            "email": body.email,
            "display_name": body.display_name,
            "message": "Account created. Please check your email for a 6-digit verification code.",
            "requires_verification": True,
        }

    except HTTPException:
        raise
    except Exception as exc:
        err_msg = str(exc).lower()
        if "already registered" in err_msg or "already exists" in err_msg:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        logger.error("Signup error: %s", exc)
        raise HTTPException(status_code=400, detail="Signup failed. Please try again.")


@router.post("/verify-otp", response_model=UserResponse)
async def verify_otp(body: VerifyOTPRequest, response: Response):
    """Verify the OTP code sent by Supabase. On success, sets session cookie."""
    try:
        sb = get_supabase()
        result = sb.auth.verify_otp({
            "email": body.email,
            "token": body.code,
            "type": "email",
        })

        if not result.session or not result.user:
            raise HTTPException(status_code=400, detail="Invalid or expired code. Please request a new one.")

        # Get display name from user metadata
        display_name = (
            result.user.user_metadata.get("display_name")
            or result.user.email.split("@")[0]
        )

        _set_session_cookie(response, result.session.access_token)
        logger.info("User verified: %s", body.email)

        return UserResponse(
            id=result.user.id,
            email=result.user.email,
            display_name=display_name,
            created_at=str(result.user.created_at),
        )

    except HTTPException:
        raise
    except Exception as exc:
        err_msg = str(exc).lower()
        if "invalid" in err_msg or "expired" in err_msg or "otp" in err_msg:
            raise HTTPException(status_code=400, detail="Invalid or expired code. Please request a new one.")
        logger.error("OTP verify error: %s", exc)
        raise HTTPException(status_code=400, detail="Verification failed. Please try again.")


@router.post("/resend-otp", status_code=200)
async def resend_otp(body: ResendOTPRequest):
    """Resend OTP via Supabase."""
    try:
        sb = get_supabase()
        sb.auth.resend({"type": "signup", "email": body.email})
        return {"message": "A new verification code has been sent to your email."}
    except Exception as exc:
        err_msg = str(exc).lower()
        if "rate" in err_msg or "limit" in err_msg:
            raise HTTPException(status_code=429, detail="Please wait before requesting a new code.")
        return {"message": "If that email is registered, a new code has been sent."}


@router.post("/login", response_model=UserResponse)
async def login(body: LoginRequest, response: Response):
    """Sign in with email + password via Supabase Auth."""
    try:
        sb = get_supabase()
        result = sb.auth.sign_in_with_password({
            "email": body.email,
            "password": body.password,
        })

        if not result.session or not result.user:
            raise HTTPException(status_code=401, detail="Incorrect email or password")

        display_name = (
            result.user.user_metadata.get("display_name")
            or result.user.email.split("@")[0]
        )

        _set_session_cookie(response, result.session.access_token, body.remember_me)
        logger.info("User logged in: %s", body.email)

        return UserResponse(
            id=result.user.id,
            email=result.user.email,
            display_name=display_name,
            created_at=str(result.user.created_at),
        )

    except HTTPException:
        raise
    except Exception as exc:
        err_msg = str(exc).lower()
        if "email not confirmed" in err_msg or "not confirmed" in err_msg:
            raise HTTPException(
                status_code=403,
                detail="Please verify your email before signing in.",
                headers={"X-Requires-Verification": "true"},
            )
        if "invalid" in err_msg or "credentials" in err_msg or "password" in err_msg:
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        logger.error("Login error: %s", exc)
        raise HTTPException(status_code=401, detail="Incorrect email or password")


@router.post("/logout", status_code=204)
async def logout(response: Response):
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    try:
        sb = get_supabase()
        user_response = sb.auth.get_user()
        # Get profile from profiles table
        profile = sb.table("profiles").select("display_name, created_at").eq("id", current_user["sub"]).single().execute()
        display_name = profile.data.get("display_name", current_user["email"].split("@")[0]) if profile.data else current_user["email"].split("@")[0]
        created_at = profile.data.get("created_at", "") if profile.data else ""

        return UserResponse(
            id=current_user["sub"],
            email=current_user["email"],
            display_name=display_name,
            created_at=str(created_at),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Me endpoint error: %s", exc)
        return UserResponse(
            id=current_user["sub"],
            email=current_user["email"],
            display_name=current_user["email"].split("@")[0],
            created_at="",
        )
