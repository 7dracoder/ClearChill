from __future__ import annotations

"""FastAPI application entry point — Supabase backend."""
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env file if present (for local development)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Cookie
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

import fridge_observer.config as config_module
from fridge_observer.ws_manager import manager
from fridge_observer.routers import inventory, recipes, notifications, settings
from fridge_observer.routers import ai as ai_router
from fridge_observer.routers import auth_router
from fridge_observer.routers import sustainability as sustainability_router
from fridge_observer.routers import hardware as hardware_router
from fridge_observer.routers import voice as voice_router
from fridge_observer.seed_recipes import seed_recipes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"
COOKIE_NAME = "fridge_session"


def _is_valid_session(token: str | None) -> bool:
    """Check if a Supabase JWT session token is valid — local decode, no network call."""
    if not token:
        return False
    try:
        from jose import jwt as _jwt
        payload = _jwt.decode(
            token,
            key="",
            options={"verify_signature": False, "verify_exp": True, "verify_aud": False},
            algorithms=["HS256"],
        )
        return bool(payload.get("sub"))
    except Exception:
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting BeenChilling (Supabase backend)...")

    # Initialize SQLite database (create tables if they don't exist)
    from fridge_observer.db import init_db
    try:
        await init_db()
        logger.info("Database initialized.")
    except Exception as e:
        logger.warning("Database initialization skipped: %s", e)

    # Load default config
    await config_module.reload()
    logger.info("Configuration loaded.")

    # Seed recipes into Supabase if empty
    await seed_recipes()
    logger.info("Recipes ready.")

    yield
    logger.info("Shutting down BeenChilling.")


app = FastAPI(
    title="BeenChilling",
    description="Smart fridge monitoring system API",
    version="2.0.0",
    lifespan=lifespan,
)

# Configure CORS for production deployment
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in allowed_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router.router)
app.include_router(inventory.router)
app.include_router(recipes.router)
app.include_router(notifications.router)
app.include_router(settings.router)
app.include_router(ai_router.router)
app.include_router(sustainability_router.router)
app.include_router(hardware_router.router)
app.include_router(voice_router.router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except (json.JSONDecodeError, KeyError):
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        logger.warning("WebSocket error: %s", exc)
        manager.disconnect(websocket)


# Static files + page routing
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/")
    async def serve_root(fridge_session: str = Cookie(default=None)):
        if _is_valid_session(fridge_session):
            return FileResponse(str(STATIC_DIR / "index.html"))
        return RedirectResponse(url="/login", status_code=302)

    @app.get("/login")
    async def serve_login(fridge_session: str = Cookie(default=None)):
        if _is_valid_session(fridge_session):
            return RedirectResponse(url="/", status_code=302)
        return FileResponse(str(STATIC_DIR / "login.html"))

    @app.get("/monitor.html")
    async def serve_monitor():
        """Monitoring dashboard - no auth required for easy access"""
        return FileResponse(str(STATIC_DIR / "monitor.html"))

    @app.get("/signup")
    async def serve_signup(fridge_session: str = Cookie(default=None)):
        if _is_valid_session(fridge_session):
            return RedirectResponse(url="/", status_code=302)
        return FileResponse(str(STATIC_DIR / "login.html"))

else:
    @app.get("/")
    async def root():
        return {"message": "BeenChilling API running."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fridge_observer.main:app", host="0.0.0.0", port=8000, reload=False)
