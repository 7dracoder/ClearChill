"""FastAPI application entry point."""
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
    pass  # python-dotenv not installed; rely on real env vars

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from fridge_observer.db import init_db
from fridge_observer.seed_settings import seed_settings
from fridge_observer.seed_recipes import seed_recipes
import fridge_observer.config as config_module
from fridge_observer.ws_manager import manager
from fridge_observer.routers import inventory, recipes, notifications, settings
from fridge_observer.routers import ai as ai_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown tasks."""
    logger.info("Starting Fridge Observer...")

    # Initialize database and schema
    await init_db()
    logger.info("Database initialized.")

    # Seed default settings
    await seed_settings()
    logger.info("Settings seeded.")

    # Seed sample recipes
    await seed_recipes()
    logger.info("Recipes seeded.")

    # Load configuration from DB
    await config_module.reload()
    logger.info("Configuration loaded.")

    yield

    logger.info("Shutting down Fridge Observer.")


app = FastAPI(
    title="Fridge Observer",
    description="Smart fridge monitoring system API",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(inventory.router)
app.include_router(recipes.router)
app.include_router(notifications.router)
app.include_router(settings.router)
app.include_router(ai_router.router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time inventory updates."""
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


# Mount static files (must be after routes to avoid conflicts)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Serve index.html at root
    from fastapi.responses import FileResponse

    @app.get("/")
    async def serve_index():
        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return {"message": "Fridge Observer API is running. Static files not found."}
else:
    @app.get("/")
    async def root():
        return {"message": "Fridge Observer API is running."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("fridge_observer.main:app", host="0.0.0.0", port=8000, reload=False)
