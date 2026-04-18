"""Settings REST API router."""
import logging
from typing import Any

from fastapi import APIRouter

from fridge_observer.db import get_db
import fridge_observer.config as config_module

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
async def get_settings():
    """Get all current settings."""
    async with get_db() as db:
        cursor = await db.execute("SELECT key, value FROM settings ORDER BY key")
        rows = await cursor.fetchall()

    return {row["key"]: row["value"] for row in rows}


@router.patch("")
async def update_settings(updates: dict[str, Any]):
    """Update one or more settings values."""
    async with get_db() as db:
        for key, value in updates.items():
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
        await db.commit()

    # Reload config after saving
    await config_module.reload()

    # Return updated settings
    async with get_db() as db:
        cursor = await db.execute("SELECT key, value FROM settings ORDER BY key")
        rows = await cursor.fetchall()

    return {row["key"]: row["value"] for row in rows}
