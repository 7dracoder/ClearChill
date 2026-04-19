from __future__ import annotations

"""Recipes REST API — backed by Supabase."""
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from fridge_observer.models import Recipe, RecipeIngredient, ScoredRecipe
from fridge_observer.supabase_client import get_supabase
from fridge_observer.routers.auth_router import get_current_user
from fridge_observer.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/recipes", tags=["recipes"])


def _compute_urgency_score(ingredients, inventory, threshold):
    today = date.today()
    score = 0.0
    matching = []
    inv_by_name = {item["name"].lower(): item for item in inventory}

    for ing in ingredients:
        if ing.get("is_pantry_staple"):
            continue
        inv_item = inv_by_name.get(ing["name"].lower())
        if not inv_item:
            continue
        expiry_str = inv_item.get("expiry_date")
        if not expiry_str:
            continue
        try:
            expiry = date.fromisoformat(expiry_str[:10])
        except (ValueError, TypeError):
            continue
        days = (expiry - today).days
        if days <= 0:
            score += 1.0
            matching.append(ing["name"])
        elif days <= threshold:
            score += (threshold - days) / threshold
            matching.append(ing["name"])

    return score, matching


async def _generate_recipes_with_k2(inventory: list[dict], dietary: str = None, cuisine: str = None, max_prep: int = None) -> list[ScoredRecipe]:
    """Generate recipes dynamically using K2-Think based on inventory."""
    import json as _json
    from fridge_observer.ai_client import k2_chat, ANSWER_SEP
    
    # Build inventory description
    urgent_items = [item for item in inventory if item["days_until_expiry"] is not None and item["days_until_expiry"] <= 3]
    all_items = [item["name"] for item in inventory]
    
    filters_text = []
    if dietary:
        filters_text.append(f"dietary preference: {dietary}")
    if cuisine:
        filters_text.append(f"cuisine: {cuisine}")
    if max_prep:
        filters_text.append(f"max prep time: {max_prep} minutes")
    
    filters_str = ", ".join(filters_text) if filters_text else "no specific filters"
    
    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional chef creating recipes based on available ingredients. "
                "Prioritize using items that are expiring soon. "
                "Always respond with ONLY valid JSON after the separator — no extra text.\n\n"
                f"FORMAT: {ANSWER_SEP}\n{{...}}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Available ingredients: {', '.join(all_items)}\n"
                f"Items expiring soon (use these first): {', '.join([i['name'] for i in urgent_items]) if urgent_items else 'none'}\n"
                f"Filters: {filters_str}\n\n"
                "Generate 5-8 creative recipes using these ingredients. "
                "Each recipe should use at least one available ingredient. "
                "Prioritize recipes that use expiring items.\n\n"
                "Return JSON array with this structure:\n"
                "[\n"
                "  {\n"
                '    "name": "Recipe Name",\n'
                '    "description": "Brief description",\n'
                '    "cuisine": "Cuisine type",\n'
                '    "dietary_tags": ["vegetarian", "gluten-free"],\n'
                '    "prep_minutes": 15,\n'
                '    "ingredients": ["ingredient1", "ingredient2"],\n'
                '    "instructions": "Step 1. Do this. Step 2. Do that."\n'
                "  }\n"
                "]\n\n"
                "Make recipes practical and delicious!"
            ),
        },
    ]
    
    try:
        response = await k2_chat(messages, stream=False)
        
        # Extract JSON
        if ANSWER_SEP in response:
            json_str = response.rsplit(ANSWER_SEP, 1)[1].strip()
        else:
            import re
            match = re.search(r'\[[\s\S]*\]', response)
            json_str = match.group(0) if match else "[]"
        
        # Clean markdown fences
        if "```" in json_str:
            parts = json_str.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("["):
                    json_str = part
                    break
        
        recipes_data = _json.loads(json_str.strip())
        
        if not isinstance(recipes_data, list):
            recipes_data = []
        
        # Convert to ScoredRecipe objects
        scored_recipes = []
        inv_by_name = {item["name"].lower(): item for item in inventory}
        
        for idx, r in enumerate(recipes_data):
            # Calculate urgency score based on which ingredients are used
            score = 0.0
            matching = []
            recipe_ingredients = r.get("ingredients", [])
            
            for ing_name in recipe_ingredients:
                inv_item = inv_by_name.get(ing_name.lower())
                if inv_item and inv_item["days_until_expiry"] is not None:
                    days = inv_item["days_until_expiry"]
                    if days <= 0:
                        score += 1.0
                        matching.append(ing_name)
                    elif days <= 3:
                        score += (3 - days) / 3
                        matching.append(ing_name)
            
            # Create recipe object
            recipe_obj = Recipe(
                id=-(idx + 1),  # Negative IDs for generated recipes
                name=r.get("name", "Unnamed Recipe"),
                description=r.get("description"),
                cuisine=r.get("cuisine"),
                dietary_tags=r.get("dietary_tags", []),
                prep_minutes=r.get("prep_minutes", 30),
                instructions=r.get("instructions", ""),
                image_url=None,
                ingredients=[
                    RecipeIngredient(
                        id=-(idx * 100 + i),
                        recipe_id=-(idx + 1),
                        name=ing,
                        category=None,
                        is_pantry_staple=False,
                    )
                    for i, ing in enumerate(recipe_ingredients)
                ],
                is_favorite=False,
            )
            
            scored_recipes.append(ScoredRecipe(
                recipe=recipe_obj,
                urgency_score=score,
                matching_expiring_items=matching,
            ))
        
        # Sort by urgency score
        scored_recipes.sort(key=lambda x: x.urgency_score, reverse=True)
        return scored_recipes
        
    except Exception as exc:
        logger.error("K2 recipe generation failed: %s", exc)
        return []


@router.get("", response_model=list[ScoredRecipe])
async def get_recipes(
    dietary: Optional[str] = Query(None),
    cuisine: Optional[str] = Query(None),
    max_prep_minutes: Optional[int] = Query(None),
    favorites_only: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """Generate recipes dynamically using K2-Think based on fridge inventory."""
    settings = get_settings()
    threshold = settings.spoilage_threshold_fruits
    sb = get_supabase()

    # Get inventory with expiry dates
    inv_result = sb.table("food_items").select("name, category, expiry_date").eq("user_id", current_user["sub"]).execute()
    inventory = inv_result.data or []

    if not inventory:
        return []

    # Sort inventory by expiry date (most urgent first)
    today = date.today()
    inventory_with_urgency = []
    for item in inventory:
        days_until_expiry = None
        if item.get("expiry_date"):
            try:
                expiry = date.fromisoformat(item["expiry_date"][:10])
                days_until_expiry = (expiry - today).days
            except Exception:
                pass
        inventory_with_urgency.append({
            "name": item["name"],
            "category": item.get("category", ""),
            "days_until_expiry": days_until_expiry,
        })
    
    # Sort by urgency (expired/expiring soon first)
    inventory_with_urgency.sort(key=lambda x: (x["days_until_expiry"] is None, x["days_until_expiry"] if x["days_until_expiry"] is not None else 999))

    # Generate recipes using K2-Think
    recipes = await _generate_recipes_with_k2(inventory_with_urgency, dietary, cuisine, max_prep_minutes)
    
    return recipes


@router.post("/{recipe_id}/favorite", status_code=201)
async def add_favorite(recipe_id: int, current_user: dict = Depends(get_current_user)):
    sb = get_supabase()
    sb.table("recipe_favorites").upsert({"user_id": current_user["sub"], "recipe_id": recipe_id}).execute()
    return {"status": "favorited", "recipe_id": recipe_id}


@router.delete("/{recipe_id}/favorite", status_code=204)
async def remove_favorite(recipe_id: int, current_user: dict = Depends(get_current_user)):
    sb = get_supabase()
    sb.table("recipe_favorites").delete().eq("user_id", current_user["sub"]).eq("recipe_id", recipe_id).execute()


@router.post("/{recipe_id}/made-this", status_code=200)
async def made_this(recipe_id: int, current_user: dict = Depends(get_current_user)):
    sb = get_supabase()

    recipe = sb.table("recipes").select("id, name").eq("id", recipe_id).single().execute()
    if not recipe.data:
        raise HTTPException(status_code=404, detail="Recipe not found")

    ingredients = sb.table("recipe_ingredients").select("*").eq("recipe_id", recipe_id).execute()
    removed = []

    for ing in (ingredients.data or []):
        if ing.get("is_pantry_staple"):
            continue
        item = sb.table("food_items").select("id, name").eq("user_id", current_user["sub"]).ilike("name", ing["name"]).limit(1).execute()
        if item.data:
            item_row = item.data[0]
            sb.table("food_items").delete().eq("id", item_row["id"]).execute()
            sb.table("activity_log").insert({
                "user_id": current_user["sub"],
                "item_id": item_row["id"],
                "item_name": item_row["name"],
                "action": "removed",
                "source": "manual",
            }).execute()
            removed.append(item_row["name"])

    # Broadcast update
    try:
        from fridge_observer.ws_manager import manager
        inv = sb.table("food_items").select("*").eq("user_id", current_user["sub"]).execute()
        await manager.broadcast_inventory_update(inv.data or [])
    except Exception as exc:
        logger.warning("Broadcast failed: %s", exc)

    return {"status": "ok", "removed_items": removed}


@router.get("/{recipe_id}/detail")
async def get_recipe_detail(recipe_id: int, current_user: dict = Depends(get_current_user)):
    """
    Get full recipe detail. For generated recipes (negative IDs), regenerate with K2.
    For stored recipes, fetch from database and enhance with K2.
    """
    sb = get_supabase()

    # Check if this is a generated recipe (negative ID)
    if recipe_id < 0:
        # Regenerate the recipe list and find this one
        inv_result = sb.table("food_items").select("name, category, expiry_date").eq("user_id", current_user["sub"]).execute()
        inventory = inv_result.data or []
        
        if not inventory:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        # Prepare inventory with urgency
        today = date.today()
        inventory_with_urgency = []
        for item in inventory:
            days_until_expiry = None
            if item.get("expiry_date"):
                try:
                    expiry = date.fromisoformat(item["expiry_date"][:10])
                    days_until_expiry = (expiry - today).days
                except Exception:
                    pass
            inventory_with_urgency.append({
                "name": item["name"],
                "category": item.get("category", ""),
                "days_until_expiry": days_until_expiry,
            })
        
        inventory_with_urgency.sort(key=lambda x: (x["days_until_expiry"] is None, x["days_until_expiry"] if x["days_until_expiry"] is not None else 999))
        
        # Generate recipes
        recipes = await _generate_recipes_with_k2(inventory_with_urgency)
        
        # Find the requested recipe by ID
        recipe_idx = abs(recipe_id) - 1
        if recipe_idx >= len(recipes):
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        scored_recipe = recipes[recipe_idx]
        r = scored_recipe.recipe
        
        # Generate full details with K2
        full_recipe = await _generate_full_recipe_with_k2(
            name=r.name,
            description=r.description or "",
            cuisine=r.cuisine or "",
            prep_minutes=r.prep_minutes,
            ingredients=[{"name": ing.name, "category": ing.category, "is_pantry_staple": ing.is_pantry_staple} for ing in r.ingredients],
            raw_instructions=r.instructions,
        )
        
        # Mark which ingredients are in fridge
        inv_map = {item["name"].lower(): item for item in inventory}
        enriched_ingredients = []
        for ing in r.ingredients:
            inv_item = inv_map.get(ing.name.lower())
            days = None
            if inv_item and inv_item.get("expiry_date"):
                try:
                    expiry = date.fromisoformat(inv_item["expiry_date"][:10])
                    days = (expiry - today).days
                except Exception:
                    pass
            
            status = "ok"
            if days is not None:
                if days <= 0:
                    status = "expired"
                elif days <= 3:
                    status = "warning"
            
            enriched_ingredients.append({
                "name": ing.name,
                "category": ing.category,
                "is_pantry_staple": ing.is_pantry_staple,
                "in_fridge": inv_item is not None,
                "expiry_status": status if inv_item else None,
            })
        
        return {
            "id": recipe_id,
            "name": r.name,
            "description": r.description,
            "cuisine": r.cuisine,
            "dietary_tags": r.dietary_tags,
            "prep_minutes": r.prep_minutes,
            "servings": full_recipe.get("servings", 2),
            "ingredients": enriched_ingredients,
            "quantities": full_recipe.get("quantities", {}),
            "steps": full_recipe.get("steps", []),
            "tips": full_recipe.get("tips", ""),
            "image_url": r.image_url,
        }

    # Original stored recipe logic
    recipe = sb.table("recipes").select("*, recipe_ingredients(*)").eq("id", recipe_id).single().execute()
    if not recipe.data:
        raise HTTPException(status_code=404, detail="Recipe not found")

    r = recipe.data
    tags = r.get("dietary_tags") or []
    if isinstance(tags, str):
        import json as _json
        try: tags = _json.loads(tags)
        except: tags = []

    ingredients = r.get("recipe_ingredients") or []

    # Check which ingredients are expiring in user's fridge
    inv = sb.table("food_items").select("name, expiry_date").eq("user_id", current_user["sub"]).execute()
    inv_map = {}
    today = date.today()
    for i in (inv.data or []):
        days = None
        if i.get("expiry_date"):
            try:
                days = (date.fromisoformat(i["expiry_date"][:10]) - today).days
            except Exception:
                pass
        status = "ok"
        if days is not None:
            if days <= 0:
                status = "expired"
            elif days <= 3:
                status = "warning"
        inv_map[i["name"].lower()] = {"expiry_status": status}

    # Mark ingredients with expiry info
    enriched_ingredients = []
    for ing in ingredients:
        inv_item = inv_map.get(ing["name"].lower())
        enriched_ingredients.append({
            "name": ing["name"],
            "category": ing.get("category"),
            "is_pantry_staple": bool(ing.get("is_pantry_staple", False)),
            "in_fridge": inv_item is not None,
            "expiry_status": inv_item.get("expiry_status") if inv_item else None,
        })

    # Use K2 to generate the full structured recipe
    full_recipe = await _generate_full_recipe_with_k2(
        name=r["name"],
        description=r.get("description", ""),
        cuisine=r.get("cuisine", ""),
        prep_minutes=r.get("prep_minutes"),
        ingredients=enriched_ingredients,
        raw_instructions=r.get("instructions", ""),
    )

    return {
        "id": r["id"],
        "name": r["name"],
        "description": r.get("description"),
        "cuisine": r.get("cuisine"),
        "dietary_tags": tags,
        "prep_minutes": r.get("prep_minutes"),
        "servings": full_recipe.get("servings", 2),
        "ingredients": enriched_ingredients,
        "quantities": full_recipe.get("quantities", {}),
        "steps": full_recipe.get("steps", []),
        "tips": full_recipe.get("tips", ""),
        "image_url": r.get("image_url"),
    }


async def _generate_full_recipe_with_k2(
    name: str,
    description: str,
    cuisine: str,
    prep_minutes: int | None,
    ingredients: list[dict],
    raw_instructions: str,
) -> dict:
    """
    Use K2-Think to generate a complete structured recipe with quantities and steps.
    Returns: {servings, quantities: {name: qty}, steps: [str], tips: str}
    """
    import json as _json
    from fridge_observer.ai_client import k2_chat, ANSWER_SEP

    ing_names = [i["name"] for i in ingredients]
    prep_str = f"{prep_minutes} minutes" if prep_minutes else "quick"

    messages = [
        {
            "role": "system",
            "content": (
                "You are a professional chef. Generate complete, accurate recipe details. "
                "Always respond with ONLY valid JSON after the separator — no extra text.\n\n"
                f"FORMAT: {ANSWER_SEP}\n{{...}}"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Recipe: {name}\n"
                f"Cuisine: {cuisine or 'International'}\n"
                f"Description: {description or name}\n"
                f"Prep time: {prep_str}\n"
                f"Ingredients available: {', '.join(ing_names)}\n\n"
                "Generate a complete recipe JSON with this exact structure:\n"
                "{\n"
                '  "servings": 2,\n'
                '  "quantities": {\n'
                '    "ingredient name": "amount + unit (e.g. 200g, 2 cups, 3 tbsp)"\n'
                "  },\n"
                '  "steps": [\n'
                '    "Step description with specific temperatures, times, and techniques",\n'
                '    "Next step..."\n'
                "  ],\n"
                '  "tips": "One practical cooking tip for this recipe"\n'
                "}\n\n"
                "Make quantities realistic for 2 servings. Steps should be clear and specific."
            ),
        },
    ]

    try:
        response = await k2_chat(messages, stream=False)

        # Extract JSON after separator
        if ANSWER_SEP in response:
            json_str = response.rsplit(ANSWER_SEP, 1)[1].strip()
        else:
            # Try to find JSON block
            import re
            match = re.search(r'\{[\s\S]*\}', response)
            json_str = match.group(0) if match else "{}"

        # Clean markdown fences
        if "```" in json_str:
            parts = json_str.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    json_str = part
                    break

        result = _json.loads(json_str.strip())

        # Validate structure
        if not isinstance(result.get("steps"), list):
            result["steps"] = _parse_instructions(raw_instructions)
        if not isinstance(result.get("quantities"), dict):
            result["quantities"] = {}
        if not result.get("servings"):
            result["servings"] = 2

        return result

    except Exception as exc:
        logger.warning("K2 recipe generation failed: %s", exc)
        # Fallback to parsed instructions
        return {
            "servings": 2,
            "quantities": {},
            "steps": _parse_instructions(raw_instructions),
            "tips": "",
        }


def _parse_instructions(raw: str) -> list[str]:
    """Parse numbered instructions into a list of steps."""
    import re
    steps = re.split(r'\d+\.\s+', raw)
    steps = [s.strip() for s in steps if s.strip()]
    if not steps and raw:
        steps = [s.strip() for s in raw.split('.') if s.strip()]
    return steps or [raw]
