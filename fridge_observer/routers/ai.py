"""AI endpoints — K2-Think reasoning and Gemini vision."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from fridge_observer.db import get_db
from fridge_observer.ai_client import (
    k2_ask,
    k2_suggest_recipes,
    k2_storage_tip,
    k2_chat_stream,
    gemini_identify_food,
    build_inventory_context,
    K2_MODEL,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/ai", tags=["ai"])


# ── Request / Response models ─────────────────────────────────

class AskRequest(BaseModel):
    question: str
    preferences: Optional[str] = None


class StorageTipRequest(BaseModel):
    item_name: str
    category: str


class IdentifyResponse(BaseModel):
    items: list[dict]
    raw: str
    error: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────

async def _get_inventory() -> list[dict]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, name, category, quantity, expiry_date FROM food_items ORDER BY expiry_date ASC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/ask")
async def ask_ai(body: AskRequest):
    """
    General-purpose AI Q&A with inventory context.
    Streams the K2-Think response as Server-Sent Events.
    """
    inventory = await _get_inventory()

    async def generate():
        try:
            from fridge_observer.ai_client import k2_ask, build_inventory_context
            from fridge_observer.ai_client import k2_chat_stream
            context = build_inventory_context(inventory)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful smart fridge assistant. You have access to the user's "
                        "current fridge inventory and can answer questions about food, recipes, "
                        "storage, nutrition, and reducing food waste. Be concise and helpful. "
                        "Format your response in plain text — no markdown headers, just clean readable text."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{context}\n\nUser question: {body.question}",
                },
            ]
            async for token in k2_chat_stream(messages):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("K2 ask error: %s", exc)
            yield f"data: Sorry, I couldn't process that request. ({exc})\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/suggest-recipes")
async def suggest_recipes(body: AskRequest):
    """
    Ask K2 to suggest recipes based on current inventory, prioritising expiring items.
    Streams the response as Server-Sent Events.
    """
    inventory = await _get_inventory()

    async def generate():
        try:
            from fridge_observer.ai_client import k2_chat_stream, build_inventory_context
            context = build_inventory_context(inventory)
            pref_str = f"\nUser preferences: {body.preferences}" if body.preferences else ""
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful culinary assistant for a smart fridge app. "
                        "Your goal is to help users reduce food waste by suggesting recipes "
                        "that use ingredients that are expiring soon. "
                        "Be concise, practical, and enthusiastic about cooking. "
                        "Format your response clearly with recipe names as titles, "
                        "followed by a brief description and key steps. No markdown symbols."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{context}{pref_str}\n\n"
                        "Please suggest 3 recipes I can make with these ingredients, "
                        "prioritising items that expire soonest. "
                        "For each recipe, briefly explain what to do and which expiring items it uses."
                    ),
                },
            ]
            async for token in k2_chat_stream(messages):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("K2 suggest-recipes error: %s", exc)
            yield f"data: Sorry, I couldn't generate recipe suggestions. ({exc})\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/storage-tip")
async def get_storage_tip(body: StorageTipRequest):
    """Get a storage tip for a specific food item from K2."""
    try:
        tip = await k2_storage_tip(body.item_name, body.category)
        return {"tip": tip, "item_name": body.item_name}
    except Exception as exc:
        logger.error("K2 storage-tip error: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}")


@router.post("/identify", response_model=IdentifyResponse)
async def identify_food(file: UploadFile = File(...)):
    """
    Identify food items in an uploaded image using Gemini vision.
    Accepts JPEG or PNG images from the webcam.
    """
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP images are supported.")

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Image too large (max 10MB).")

    result = await gemini_identify_food(image_bytes, mime_type=file.content_type or "image/jpeg")
    return IdentifyResponse(
        items=result.get("items", []),
        raw=result.get("raw", ""),
        error=result.get("error"),
    )


@router.get("/inventory-summary")
async def inventory_summary():
    """
    Ask K2 to analyse the current inventory and provide a smart summary:
    what's expiring, what to use first, and any waste-reduction tips.
    Streams as SSE.
    """
    inventory = await _get_inventory()

    async def generate():
        try:
            from fridge_observer.ai_client import k2_chat_stream, build_inventory_context
            context = build_inventory_context(inventory)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a smart fridge assistant helping users reduce food waste. "
                        "Analyse the inventory and give a brief, friendly summary. "
                        "Highlight what needs to be used soon, suggest priorities, "
                        "and give one practical tip. Keep it under 150 words. No markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": f"{context}\n\nGive me a quick summary of my fridge situation.",
                },
            ]
            async for token in k2_chat_stream(messages):
                yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("K2 inventory-summary error: %s", exc)
            yield f"data: Unable to generate summary. ({exc})\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
