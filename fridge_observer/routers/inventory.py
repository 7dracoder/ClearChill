"""Inventory REST API router."""
import json
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from fridge_observer.db import get_db
from fridge_observer.models import FoodItem, FoodItemCreate, FoodItemUpdate
from fridge_observer.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inventory", tags=["inventory"])


async def _get_all_items_raw(db) -> list[dict]:
    """Fetch all inventory items as raw dicts."""
    cursor = await db.execute(
        "SELECT id, name, category, quantity, expiry_date, expiry_source, added_at, thumbnail, notes "
        "FROM food_items ORDER BY added_at DESC"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def _broadcast_inventory_update(db) -> None:
    """Broadcast current inventory to all WebSocket clients."""
    try:
        from fridge_observer.ws_manager import manager
        items = await _get_all_items_raw(db)
        await manager.broadcast_inventory_update(items)
    except Exception as exc:
        logger.warning("Failed to broadcast inventory update: %s", exc)


def _row_to_food_item(row: dict, threshold: int = 3) -> FoodItem:
    """Convert a DB row dict to a FoodItem model."""
    expiry_date = None
    if row.get("expiry_date"):
        try:
            expiry_date = date.fromisoformat(row["expiry_date"])
        except (ValueError, TypeError):
            pass

    added_at = row.get("added_at")
    if isinstance(added_at, str):
        try:
            added_at = datetime.fromisoformat(added_at)
        except (ValueError, TypeError):
            added_at = datetime.now()

    return FoodItem.with_threshold(
        {
            "id": row["id"],
            "name": row["name"],
            "category": row["category"],
            "quantity": row["quantity"],
            "expiry_date": expiry_date,
            "expiry_source": row.get("expiry_source", "estimated"),
            "added_at": added_at,
            "thumbnail": row.get("thumbnail"),
            "notes": row.get("notes"),
        },
        threshold,
    )


@router.get("", response_model=list[FoodItem])
async def get_inventory(
    category: Optional[str] = Query(None),
    sort_by: Optional[str] = Query(None, pattern="^(expiry_date|added_at|name|quantity)$"),
    sort_dir: Optional[str] = Query("asc", pattern="^(asc|desc)$"),
    expiry_before: Optional[date] = Query(None),
    expiry_after: Optional[date] = Query(None),
):
    """Get all inventory items with optional filtering and sorting."""
    settings = get_settings()

    query = (
        "SELECT id, name, category, quantity, expiry_date, expiry_source, added_at, thumbnail, notes "
        "FROM food_items WHERE 1=1"
    )
    params: list = []

    if category:
        query += " AND category = ?"
        params.append(category)

    if expiry_before:
        query += " AND expiry_date IS NOT NULL AND expiry_date <= ?"
        params.append(expiry_before.isoformat())

    if expiry_after:
        query += " AND expiry_date IS NOT NULL AND expiry_date >= ?"
        params.append(expiry_after.isoformat())

    # Sorting
    sort_column = sort_by or "added_at"
    direction = "DESC" if sort_dir == "desc" else "ASC"
    query += f" ORDER BY {sort_column} {direction}"

    async with get_db() as db:
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()

    items = []
    for row in rows:
        row_dict = dict(row)
        cat = row_dict.get("category", "packaged_goods")
        threshold = settings.get_spoilage_threshold(cat)
        items.append(_row_to_food_item(row_dict, threshold))

    return items


@router.post("", response_model=FoodItem, status_code=201)
async def create_inventory_item(item: FoodItemCreate):
    """Add a new item to the inventory."""
    settings = get_settings()

    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO food_items (name, category, quantity, expiry_date, expiry_source, notes)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                item.name,
                item.category.value,
                item.quantity,
                item.expiry_date.isoformat() if item.expiry_date else None,
                item.expiry_source,
                item.notes,
            ),
        )
        item_id = cursor.lastrowid
        await db.execute(
            """INSERT INTO activity_log (item_id, item_name, action, source)
               VALUES (?, ?, 'added', 'manual')""",
            (item_id, item.name),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT id, name, category, quantity, expiry_date, expiry_source, added_at, thumbnail, notes "
            "FROM food_items WHERE id = ?",
            (item_id,),
        )
        row = await cursor.fetchone()
        await _broadcast_inventory_update(db)

    threshold = settings.get_spoilage_threshold(item.category.value)
    return _row_to_food_item(dict(row), threshold)


@router.patch("/{item_id}", response_model=FoodItem)
async def update_inventory_item(item_id: int, patch: FoodItemUpdate):
    """Update an existing inventory item."""
    settings = get_settings()

    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, category, quantity, expiry_date, expiry_source, added_at, thumbnail, notes "
            "FROM food_items WHERE id = ?",
            (item_id,),
        )
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Item not found")

        existing_dict = dict(existing)
        updates: list[str] = []
        params: list = []

        if patch.name is not None:
            updates.append("name = ?")
            params.append(patch.name)
        if patch.quantity is not None:
            updates.append("quantity = ?")
            params.append(patch.quantity)
        if patch.expiry_date is not None:
            updates.append("expiry_date = ?")
            params.append(patch.expiry_date.isoformat())
        if patch.expiry_source is not None:
            updates.append("expiry_source = ?")
            params.append(patch.expiry_source)
        if patch.notes is not None:
            updates.append("notes = ?")
            params.append(patch.notes)

        if updates:
            params.append(item_id)
            await db.execute(
                f"UPDATE food_items SET {', '.join(updates)} WHERE id = ?",
                params,
            )
            await db.execute(
                """INSERT INTO activity_log (item_id, item_name, action, source)
                   VALUES (?, ?, 'updated', 'manual')""",
                (item_id, patch.name or existing_dict["name"]),
            )
            await db.commit()

        cursor = await db.execute(
            "SELECT id, name, category, quantity, expiry_date, expiry_source, added_at, thumbnail, notes "
            "FROM food_items WHERE id = ?",
            (item_id,),
        )
        row = await cursor.fetchone()
        await _broadcast_inventory_update(db)

    row_dict = dict(row)
    threshold = settings.get_spoilage_threshold(row_dict.get("category", "packaged_goods"))
    return _row_to_food_item(row_dict, threshold)


@router.delete("/{item_id}", status_code=204)
async def delete_inventory_item(item_id: int):
    """Remove an item from the inventory."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name FROM food_items WHERE id = ?", (item_id,)
        )
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Item not found")

        item_name = existing["name"]
        await db.execute("DELETE FROM food_items WHERE id = ?", (item_id,))
        await db.execute(
            """INSERT INTO activity_log (item_id, item_name, action, source)
               VALUES (?, ?, 'removed', 'manual')""",
            (item_id, item_name),
        )
        await db.commit()
        await _broadcast_inventory_update(db)
