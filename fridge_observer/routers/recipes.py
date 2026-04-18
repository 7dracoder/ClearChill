"""Recipes REST API router."""
import json
import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from fridge_observer.db import get_db
from fridge_observer.models import Recipe, RecipeIngredient, ScoredRecipe
from fridge_observer.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recipes", tags=["recipes"])


def _compute_urgency_score(
    ingredients: list[dict],
    inventory: list[dict],
    threshold: int,
) -> tuple[float, list[str]]:
    """Compute the Expiry Urgency Score for a recipe given current inventory."""
    today = date.today()
    score = 0.0
    matching_expiring: list[str] = []

    # Build inventory lookup by name (case-insensitive)
    inv_by_name: dict[str, dict] = {}
    for item in inventory:
        inv_by_name[item["name"].lower()] = item

    for ing in ingredients:
        if ing.get("is_pantry_staple"):
            continue
        ing_name = ing["name"].lower()
        inv_item = inv_by_name.get(ing_name)
        if inv_item is None:
            continue

        expiry_str = inv_item.get("expiry_date")
        if not expiry_str:
            continue

        try:
            expiry = date.fromisoformat(expiry_str)
        except (ValueError, TypeError):
            continue

        days_remaining = (expiry - today).days
        if days_remaining <= 0:
            score += 1.0
            matching_expiring.append(ing["name"])
        elif days_remaining <= threshold:
            score += (threshold - days_remaining) / threshold
            matching_expiring.append(ing["name"])

    return score, matching_expiring


async def _get_inventory(db) -> list[dict]:
    """Fetch all inventory items."""
    cursor = await db.execute(
        "SELECT id, name, category, quantity, expiry_date FROM food_items"
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def _get_recipe_with_ingredients(db, recipe_id: int) -> Optional[dict]:
    """Fetch a recipe with its ingredients."""
    cursor = await db.execute(
        "SELECT id, name, description, cuisine, dietary_tags, prep_minutes, instructions, image_url "
        "FROM recipes WHERE id = ?",
        (recipe_id,),
    )
    row = await cursor.fetchone()
    if not row:
        return None

    recipe = dict(row)
    recipe["dietary_tags"] = json.loads(recipe.get("dietary_tags") or "[]")

    cursor = await db.execute(
        "SELECT id, recipe_id, name, category, is_pantry_staple FROM recipe_ingredients WHERE recipe_id = ?",
        (recipe_id,),
    )
    ing_rows = await cursor.fetchall()
    recipe["ingredients"] = [dict(r) for r in ing_rows]

    # Check if favorited
    cursor = await db.execute(
        "SELECT recipe_id FROM recipe_favorites WHERE recipe_id = ?", (recipe_id,)
    )
    fav = await cursor.fetchone()
    recipe["is_favorite"] = fav is not None

    return recipe


def _is_feasible(ingredients: list[dict], inventory: list[dict]) -> bool:
    """Check if all non-staple ingredients are in inventory."""
    inv_names = {item["name"].lower() for item in inventory}
    for ing in ingredients:
        if ing.get("is_pantry_staple"):
            continue
        if ing["name"].lower() not in inv_names:
            return False
    return True


@router.get("", response_model=list[ScoredRecipe])
async def get_recipes(
    dietary: Optional[str] = Query(None),
    cuisine: Optional[str] = Query(None),
    max_prep_minutes: Optional[int] = Query(None),
    favorites_only: bool = Query(False),
):
    """Get recipes scored by expiry urgency, with optional filters."""
    settings = get_settings()
    # Use a general threshold (average or fruits threshold as default)
    threshold = settings.spoilage_threshold_fruits

    async with get_db() as db:
        query = (
            "SELECT id, name, description, cuisine, dietary_tags, prep_minutes, instructions, image_url "
            "FROM recipes WHERE 1=1"
        )
        params: list = []

        if cuisine:
            query += " AND LOWER(cuisine) = LOWER(?)"
            params.append(cuisine)

        if max_prep_minutes is not None:
            query += " AND prep_minutes <= ?"
            params.append(max_prep_minutes)

        if favorites_only:
            query += " AND id IN (SELECT recipe_id FROM recipe_favorites)"

        cursor = await db.execute(query, params)
        recipe_rows = await cursor.fetchall()

        inventory = await _get_inventory(db)

        # Get all favorites
        cursor = await db.execute("SELECT recipe_id FROM recipe_favorites")
        fav_rows = await cursor.fetchall()
        fav_ids = {row["recipe_id"] for row in fav_rows}

        scored_recipes: list[ScoredRecipe] = []
        for recipe_row in recipe_rows:
            recipe_dict = dict(recipe_row)
            recipe_dict["dietary_tags"] = json.loads(recipe_dict.get("dietary_tags") or "[]")

            # Apply dietary filter
            if dietary:
                tags = [t.lower() for t in recipe_dict["dietary_tags"]]
                if dietary.lower() not in tags:
                    continue

            # Get ingredients
            cursor = await db.execute(
                "SELECT id, recipe_id, name, category, is_pantry_staple FROM recipe_ingredients WHERE recipe_id = ?",
                (recipe_dict["id"],),
            )
            ing_rows = await cursor.fetchall()
            ingredients = [dict(r) for r in ing_rows]
            recipe_dict["ingredients"] = ingredients
            recipe_dict["is_favorite"] = recipe_dict["id"] in fav_ids

            # Only show feasible recipes
            if not _is_feasible(ingredients, inventory):
                # Still include but with score 0 if no matching items
                pass

            score, matching = _compute_urgency_score(ingredients, inventory, threshold)

            recipe_obj = Recipe(
                id=recipe_dict["id"],
                name=recipe_dict["name"],
                description=recipe_dict.get("description"),
                cuisine=recipe_dict.get("cuisine"),
                dietary_tags=recipe_dict["dietary_tags"],
                prep_minutes=recipe_dict.get("prep_minutes"),
                instructions=recipe_dict["instructions"],
                image_url=recipe_dict.get("image_url"),
                ingredients=[
                    RecipeIngredient(
                        id=i["id"],
                        recipe_id=i["recipe_id"],
                        name=i["name"],
                        category=i.get("category"),
                        is_pantry_staple=bool(i.get("is_pantry_staple", 0)),
                    )
                    for i in ingredients
                ],
                is_favorite=recipe_dict["is_favorite"],
            )

            scored_recipes.append(
                ScoredRecipe(
                    recipe=recipe_obj,
                    urgency_score=score,
                    matching_expiring_items=matching,
                )
            )

    # Sort by urgency score descending
    scored_recipes.sort(key=lambda x: x.urgency_score, reverse=True)
    return scored_recipes


@router.post("/{recipe_id}/favorite", status_code=201)
async def add_favorite(recipe_id: int):
    """Add a recipe to favorites."""
    async with get_db() as db:
        cursor = await db.execute("SELECT id FROM recipes WHERE id = ?", (recipe_id,))
        if not await cursor.fetchone():
            raise HTTPException(status_code=404, detail="Recipe not found")

        await db.execute(
            "INSERT OR IGNORE INTO recipe_favorites (recipe_id) VALUES (?)",
            (recipe_id,),
        )
        await db.commit()
    return {"status": "favorited", "recipe_id": recipe_id}


@router.delete("/{recipe_id}/favorite", status_code=204)
async def remove_favorite(recipe_id: int):
    """Remove a recipe from favorites."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM recipe_favorites WHERE recipe_id = ?", (recipe_id,)
        )
        await db.commit()


@router.post("/{recipe_id}/made-this", status_code=200)
async def made_this(recipe_id: int):
    """Mark a recipe as made and remove non-staple ingredients from inventory."""
    async with get_db() as db:
        cursor = await db.execute("SELECT id, name FROM recipes WHERE id = ?", (recipe_id,))
        recipe_row = await cursor.fetchone()
        if not recipe_row:
            raise HTTPException(status_code=404, detail="Recipe not found")

        cursor = await db.execute(
            "SELECT id, name, category, is_pantry_staple FROM recipe_ingredients WHERE recipe_id = ?",
            (recipe_id,),
        )
        ingredients = [dict(r) for r in await cursor.fetchall()]

        removed_items: list[str] = []
        for ing in ingredients:
            if ing.get("is_pantry_staple"):
                continue

            # Find matching inventory item
            cursor = await db.execute(
                "SELECT id, name FROM food_items WHERE LOWER(name) = LOWER(?) LIMIT 1",
                (ing["name"],),
            )
            inv_item = await cursor.fetchone()
            if inv_item:
                await db.execute("DELETE FROM food_items WHERE id = ?", (inv_item["id"],))
                await db.execute(
                    """INSERT INTO activity_log (item_id, item_name, action, source)
                       VALUES (?, ?, 'removed', 'manual')""",
                    (inv_item["id"], inv_item["name"]),
                )
                removed_items.append(inv_item["name"])

        await db.commit()

        # Broadcast updated inventory
        try:
            from fridge_observer.ws_manager import manager
            cursor = await db.execute(
                "SELECT id, name, category, quantity, expiry_date, expiry_source, added_at, thumbnail, notes "
                "FROM food_items ORDER BY added_at DESC"
            )
            rows = await cursor.fetchall()
            items = [dict(row) for row in rows]
            await manager.broadcast_inventory_update(items)
        except Exception as exc:
            logger.warning("Failed to broadcast after made-this: %s", exc)

    return {"status": "ok", "removed_items": removed_items}
