"""WebSocket connection manager for real-time inventory updates."""
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections and broadcasts messages."""

    def __init__(self) -> None:
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a new WebSocket connection and send the current inventory state."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info("WebSocket client connected. Total: %d", len(self.active_connections))

        # Send current inventory as the first message
        try:
            from fridge_observer.db import get_db
            from fridge_observer.config import get_settings
            import json as _json

            async with get_db() as db:
                cursor = await db.execute(
                    "SELECT id, name, category, quantity, expiry_date, expiry_source, "
                    "added_at, thumbnail, notes FROM food_items ORDER BY added_at DESC"
                )
                rows = await cursor.fetchall()
                items = [dict(row) for row in rows]

            await websocket.send_text(
                _json.dumps({"type": "inventory_update", "payload": items})
            )
        except Exception as exc:
            logger.warning("Failed to send initial inventory state: %s", exc)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info("WebSocket client disconnected. Total: %d", len(self.active_connections))

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to all active connections."""
        text = json.dumps(message)
        disconnected: list[WebSocket] = []
        for connection in self.active_connections:
            try:
                await connection.send_text(text)
            except Exception as exc:
                logger.warning("Failed to send to WebSocket client: %s", exc)
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_inventory_update(self, items: list[dict]) -> None:
        """Broadcast an inventory_update message to all clients."""
        await self.broadcast({"type": "inventory_update", "payload": items})

    async def broadcast_notification(self, level: str, message: str) -> None:
        """Broadcast a notification message to all clients."""
        await self.broadcast({"type": "notification", "payload": {"level": level, "message": message}})

    async def broadcast_temperature_update(self, fridge: float | None, freezer: float | None) -> None:
        """Broadcast a temperature_update message to all clients."""
        await self.broadcast({"type": "temperature_update", "payload": {"fridge": fridge, "freezer": freezer}})


# Global manager instance
manager = ConnectionManager()
