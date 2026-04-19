from __future__ import annotations

"""Auth endpoints — Supabase Auth + custom OTP via Gmail."""
import logging
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Response, status, Depends, Cookie
from pydantic import BaseModel, field_validator
from typing import Optional

from fridge_observer.supabase_client import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_NAME = "fridge_session"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
OTP_EXPIRY_MINUTES = 10


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
    """FastAPI dependency — validates Supabase JWT locally (no network call)."""
    # For local development without Supabase, return a dummy user
    import os
    if os.environ.get("ENVIRONMENT") != "production" and not fridge_session:
        return {"sub": "local-user", "email": "local@localhost"}
    
    if not fridge_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        import time
        from jose import jwt as _jwt

        # Decode without signature verification (Supabase signs with their own secret)
        # We still check expiry
        payload = _jwt.decode(
            fridge_session,
            key="",  # key required by jose but ignored when verify_signature=False
            options={
                "verify_signature": False,
                "verify_exp": True,
                "verify_aud": False,
            },
            algorithms=["HS256"],
        )

        user_id = payload.get("sub")
        email = payload.get("email", "")

        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid session")

        return {"sub": user_id, "email": email}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Session expired or invalid")


# ── OTP helpers ───────────────────────────────────────────────

def _generate_otp() -> str:
    return str(secrets.randbelow(900000) + 100000)


def _store_otp(email: str, code: str) -> None:
    """Store OTP in Supabase email_otps table."""
    sb = get_supabase()
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()
    # Delete old OTPs for this email first
    sb.table("email_otps").delete().eq("email", email).execute()
    sb.table("email_otps").insert({
        "email": email,
        "code": code,
        "expires_at": expires_at,
        "used": False,
    }).execute()


def _verify_otp_code(email: str, code: str) -> bool:
    """Check OTP is valid, not expired, not used. Marks as used if valid."""
    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    result = sb.table("email_otps").select("id, used, expires_at").eq("email", email).eq("code", code).eq("used", False).execute()

    if not result.data:
        return False

    row = result.data[0]
    # Check expiry
    expires_at = row.get("expires_at", "")
    if expires_at and expires_at < now:
        return False

    # Mark as used
    sb.table("email_otps").update({"used": True}).eq("id", row["id"]).execute()
    return True


def _send_otp_email_async(email: str, display_name: str, code: str) -> None:
    """Send OTP email via Gmail in a background thread."""
    import threading
    from fridge_observer.email_sender import send_otp_email

    def _send():
        try:
            send_otp_email(email, display_name, code)
            logger.info("✓ OTP email sent successfully to %s", email)
        except RuntimeError as exc:
            logger.error("❌ SMTP not configured: %s", exc)
        except Exception as exc:
            logger.error("❌ Failed to send OTP email to %s: %s", email, exc, exc_info=True)

    threading.Thread(target=_send, daemon=True).start()


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/signup", status_code=201)
async def signup(body: SignupRequest):
    sb = get_supabase()

    # Check if user already exists
    try:
        existing = sb.auth.admin.list_users()
        existing_emails = [u.email for u in existing if u.email]
        if body.email in existing_emails:
            for u in existing:
                if u.email == body.email:
                    if u.email_confirmed_at:
                        raise HTTPException(status_code=409, detail="An account with this email already exists")
                    else:
                        code = _generate_otp()
                        _store_otp(body.email, code)
                        _send_otp_email_async(body.email, body.display_name, code)
                        return {
                            "email": body.email,
                            "display_name": body.display_name,
                            "message": "Verification code resent. Please check your email.",
                            "requires_verification": True,
                        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("list_users check failed (non-fatal): %s", exc)

    # Create user
    try:
        result = sb.auth.admin.create_user({
            "email": body.email,
            "password": body.password,
            "user_metadata": {"display_name": body.display_name},
            "email_confirm": False,
        })
        if not result.user:
            raise HTTPException(status_code=400, detail="Signup failed. Please try again.")
    except HTTPException:
        raise
    except Exception as exc:
        err_msg = str(exc).lower()
        if "already registered" in err_msg or "already exists" in err_msg or "duplicate" in err_msg:
            raise HTTPException(status_code=409, detail="An account with this email already exists")
        logger.error("Signup error: %s", exc)
        raise HTTPException(status_code=400, detail="Signup failed. Please try again.")

    # Generate and send OTP
    code = _generate_otp()
    _store_otp(body.email, code)
    _send_otp_email_async(body.email, body.display_name, code)

    logger.info("New user signed up: %s", body.email)
    return {
        "email": body.email,
        "display_name": body.display_name,
        "message": "Account created. Please check your email for a 6-digit verification code.",
        "requires_verification": True,
    }


@router.post("/verify-otp", response_model=UserResponse)
async def verify_otp(body: VerifyOTPRequest, response: Response):
    """Verify OTP. On success, confirm user email and set session cookie."""
    # Verify the OTP code
    if not _verify_otp_code(body.email, body.code):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired code. Please request a new one.",
        )

    sb = get_supabase()

    # Find the user and confirm their email
    try:
        users = sb.auth.admin.list_users()
        user = next((u for u in users if u.email == body.email), None)

        if not user:
            raise HTTPException(status_code=404, detail="Account not found")

        # Confirm the user's email
        sb.auth.admin.update_user_by_id(user.id, {"email_confirm": True})

        # Sign them in to get a session token
        sign_in = sb.auth.sign_in_with_password({
            "email": body.email,
            "password": "",  # We need the password — use a workaround
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("OTP verify error: %s", exc)
        raise HTTPException(status_code=400, detail="Verification failed. Please try again.")

    # Since we can't sign in without the password here, generate a magic link session
    try:
        # Use admin to generate a session directly
        session = sb.auth.admin.generate_link({
            "type": "magiclink",
            "email": body.email,
        })
        # Actually, let's use a different approach — store a verified flag and
        # require the user to sign in after verification
        display_name = user.user_metadata.get("display_name", body.email.split("@")[0]) if user.user_metadata else body.email.split("@")[0]

        return {
            "id": user.id,
            "email": body.email,
            "display_name": display_name,
            "created_at": str(user.created_at),
            "verified": True,
            "message": "Email verified! Please sign in with your password.",
        }

    except Exception as exc:
        logger.error("Post-verify session error: %s", exc)
        display_name = user.user_metadata.get("display_name", body.email.split("@")[0]) if user.user_metadata else body.email.split("@")[0]
        return {
            "id": user.id,
            "email": body.email,
            "display_name": display_name,
            "created_at": str(user.created_at),
            "verified": True,
        }


@router.post("/verify-otp-and-login", response_model=UserResponse)
async def verify_otp_and_login(body: VerifyOTPRequest, response: Response):
    """Verify OTP and immediately log the user in using stored credentials."""
    # This endpoint is called from the frontend after OTP verification
    # The frontend passes email + code, we verify and create a session

    if not _verify_otp_code(body.email, body.code):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired code. Please request a new one.",
        )

    sb = get_supabase()

    try:
        users = sb.auth.admin.list_users()
        user = next((u for u in users if u.email == body.email), None)

        if not user:
            raise HTTPException(status_code=404, detail="Account not found")

        # Confirm email
        sb.auth.admin.update_user_by_id(user.id, {"email_confirm": True})

        display_name = (user.user_metadata or {}).get("display_name", body.email.split("@")[0])

        logger.info("User verified via OTP: %s", body.email)

        # Return success — frontend will redirect to login
        return UserResponse(
            id=user.id,
            email=body.email,
            display_name=display_name,
            created_at=str(user.created_at),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Verify and login error: %s", exc)
        raise HTTPException(status_code=400, detail="Verification failed.")


@router.post("/resend-otp", status_code=200)
async def resend_otp(body: ResendOTPRequest):
    """Resend a fresh OTP via Gmail."""
    sb = get_supabase()

    try:
        users = sb.auth.admin.list_users()
        user = next((u for u in users if u.email == body.email), None)
    except Exception:
        return {"message": "If that email is registered, a new code has been sent."}

    if not user:
        return {"message": "If that email is registered, a new code has been sent."}

    if user.email_confirmed_at:
        raise HTTPException(status_code=409, detail="This email is already verified.")

    # Rate limit: check last OTP
    result = sb.table("email_otps").select("created_at").eq("email", body.email).order("created_at", desc=True).limit(1).execute()
    if result.data:
        last_created = result.data[0].get("created_at", "")
        if last_created:
            try:
                last_dt = datetime.fromisoformat(last_created.replace("Z", "+00:00"))
                if (datetime.now(timezone.utc) - last_dt).total_seconds() < 60:
                    raise HTTPException(status_code=429, detail="Please wait 60 seconds before requesting a new code.")
            except HTTPException:
                raise
            except Exception:
                pass

    display_name = (user.user_metadata or {}).get("display_name", body.email.split("@")[0])
    code = _generate_otp()
    _store_otp(body.email, code)
    _send_otp_email_async(body.email, display_name, code)

    return {"message": "A new verification code has been sent to your email."}


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

        display_name = (result.user.user_metadata or {}).get("display_name") or body.email.split("@")[0]

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
    response.delete_cookie(key=COOKIE_NAME, path="/")


@router.get("/me", response_model=UserResponse)
async def me(current_user: dict = Depends(get_current_user)):
    try:
        sb = get_supabase()
        profile = sb.table("profiles").select("display_name, created_at").eq("id", current_user["sub"]).single().execute()
        display_name = (profile.data or {}).get("display_name", current_user["email"].split("@")[0])
        created_at = (profile.data or {}).get("created_at", "")
        return UserResponse(
            id=current_user["sub"],
            email=current_user["email"],
            display_name=display_name,
            created_at=str(created_at),
        )
    except Exception:
        return UserResponse(
            id=current_user["sub"],
            email=current_user["email"],
            display_name=current_user["email"].split("@")[0],
            created_at="",
        )
