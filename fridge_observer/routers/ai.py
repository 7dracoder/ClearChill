from __future__ import annotations

"""AI endpoints — K2-Think reasoning and Gemini vision."""
import logging
from typing import Optional

import httpx
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

ANSWER_SEP = "---ANSWER---"

def _extract_answer(text: str) -> str:
    """Extract the answer after ---ANSWER--- separator, or return cleaned full text."""
    if ANSWER_SEP in text:
        # Use the LAST occurrence — K2 sometimes repeats the separator in its reasoning
        return text.rsplit(ANSWER_SEP, 1)[1].strip()
    # Fallback: return the last non-empty paragraph (most likely the actual answer)
    paragraphs = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    if paragraphs:
        return paragraphs[-1]
    return text.strip()


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
    from fridge_observer.supabase_client import get_supabase
    sb = get_supabase()
    # Get all items (no user filtering for local dev)
    result = sb.table("food_items").select("id, name, category, quantity, expiry_date").order("expiry_date").execute()
    return result.data or []


# ── Endpoints ─────────────────────────────────────────────────

@router.post("/ask")
async def ask_ai(body: AskRequest):
    """
    General-purpose AI Q&A with inventory context.
    Collects the full K2 response, strips reasoning, then streams the clean answer.
    """
    # Check if K2 API key is configured
    from fridge_observer.ai_client import K2_API_KEY
    if not K2_API_KEY or K2_API_KEY == "":
        raise HTTPException(
            status_code=503,
            detail="AI assistant is not configured. Please set K2_API_KEY in your .env file."
        )
    
    inventory = await _get_inventory()

    async def generate():
        try:
            from fridge_observer.ai_client import k2_chat, build_inventory_context
            context = build_inventory_context(inventory)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a helpful smart fridge assistant with access to the user's fridge inventory. "
                        "Answer questions about food, recipes, storage, and reducing waste. "
                        "Be friendly and concise. Plain text only — no markdown.\n\n"
                        "FORMAT: Write your final answer after the separator '---ANSWER---'. "
                        "Example:\n---ANSWER---\nHello! How can I help you today?"
                    ),
                },
                {
                    "role": "user",
                    "content": f"{context}\n\n{body.question}",
                },
            ]
            full_response = await k2_chat(messages, stream=False)
            # Extract answer after separator if present
            answer = _extract_answer(full_response)
            # Stream it word by word for a natural feel
            words = answer.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except httpx.HTTPStatusError as exc:
            logger.error("K2 API HTTP error: %s - %s", exc.response.status_code, exc.response.text)
            if exc.response.status_code == 401:
                yield f"data: AI assistant authentication failed. Please check your K2_API_KEY.\n\n"
            elif exc.response.status_code == 429:
                yield f"data: AI assistant is busy. Please try again in a moment.\n\n"
            else:
                yield f"data: AI assistant encountered an error. Please try again later.\n\n"
            yield "data: [DONE]\n\n"
        except httpx.TimeoutException:
            logger.error("K2 API timeout")
            yield f"data: AI assistant timed out. Please try again.\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("K2 ask error: %s", exc, exc_info=True)
            yield f"data: Sorry, I couldn't process that request. Error: {str(exc)[:100]}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/suggest-recipes")
async def suggest_recipes(body: AskRequest):
    """Ask K2 to suggest recipes based on current inventory."""
    # Check if K2 API key is configured
    from fridge_observer.ai_client import K2_API_KEY
    if not K2_API_KEY or K2_API_KEY == "":
        raise HTTPException(
            status_code=503,
            detail="AI assistant is not configured. Please set K2_API_KEY in your .env file."
        )
    
    inventory = await _get_inventory()

    async def generate():
        try:
            from fridge_observer.ai_client import k2_chat, build_inventory_context
            context = build_inventory_context(inventory)
            pref_str = f"\nUser preferences: {body.preferences}" if body.preferences else ""
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a culinary assistant for a smart fridge app. "
                        "Suggest recipes that use ingredients expiring soonest. "
                        "Be concise and practical. Plain text only.\n\n"
                        f"FORMAT: Write your final answer after '{ANSWER_SEP}'. "
                        f"Example:\n{ANSWER_SEP}\n1. Pasta Primavera — uses your zucchini..."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"{context}{pref_str}\n\n"
                        "Suggest 3 recipes using ingredients that expire soonest. "
                        "For each, give the name, what expiring items it uses, and 2-3 key steps."
                    ),
                },
            ]
            full_response = await k2_chat(messages, stream=False)
            answer = _extract_answer(full_response)
            words = answer.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except httpx.HTTPStatusError as exc:
            logger.error("K2 API HTTP error: %s", exc)
            if exc.response.status_code == 401:
                yield f"data: AI authentication failed. Please check your K2_API_KEY.\n\n"
            else:
                yield f"data: AI assistant error. Please try again later.\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("K2 suggest-recipes error: %s", exc, exc_info=True)
            yield f"data: Sorry, I couldn't generate recipe suggestions.\n\n"
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

    if result.get("error") == "rate_limit":
        raise HTTPException(status_code=429, detail=result.get("message", "Rate limit reached. Try again shortly."))
    if result.get("error") in ("auth_error", "bad_request"):
        raise HTTPException(status_code=502, detail=result.get("message", "Gemini API error."))

    return IdentifyResponse(
        items=result.get("items", []),
        raw=result.get("raw", ""),
        error=result.get("error"),
    )


@router.get("/inventory-summary")
async def inventory_summary():
    """Ask K2 to analyse the current inventory and provide a smart summary."""
    # Check if K2 API key is configured
    from fridge_observer.ai_client import K2_API_KEY
    if not K2_API_KEY or K2_API_KEY == "":
        raise HTTPException(
            status_code=503,
            detail="AI assistant is not configured. Please set K2_API_KEY in your .env file."
        )
    
    inventory = await _get_inventory()

    async def generate():
        try:
            from fridge_observer.ai_client import k2_chat, build_inventory_context
            context = build_inventory_context(inventory)
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are a smart fridge assistant. Give a brief, friendly fridge summary. "
                        "Highlight what needs to be used soon and give one practical tip. "
                        "Under 100 words. Plain text only.\n\n"
                        f"FORMAT: Write your final answer after '{ANSWER_SEP}'.\n{ANSWER_SEP}\n[your answer]"
                    ),
                },
                {
                    "role": "user",
                    "content": f"{context}\n\nGive me a quick summary of my fridge situation.",
                },
            ]
            full_response = await k2_chat(messages, stream=False)
            answer = _extract_answer(full_response)
            words = answer.split(" ")
            for i, word in enumerate(words):
                chunk = word + (" " if i < len(words) - 1 else "")
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except httpx.HTTPStatusError as exc:
            logger.error("K2 API HTTP error: %s", exc)
            if exc.response.status_code == 401:
                yield f"data: AI authentication failed. Please check your K2_API_KEY.\n\n"
            else:
                yield f"data: AI assistant error. Please try again later.\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:
            logger.error("K2 inventory-summary error: %s", exc, exc_info=True)
            yield f"data: Unable to generate summary.\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Image generation endpoints ────────────────────────────────

@router.get("/recipe-image")
async def get_recipe_image(name: str, cuisine: str = ""):
    """Generate a recipe food photo using FLUX.1-schnell."""
    from fridge_observer.image_gen import generate_recipe_image, image_to_data_url
    from fastapi.responses import Response

    image_bytes = await generate_recipe_image(name, cuisine)
    if image_bytes:
        return Response(content=image_bytes, media_type="image/jpeg")

    # Return SVG placeholder if generation fails
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="#EBF3EE" rx="16"/>
  <text x="256" y="240" text-anchor="middle" font-family="Inter,sans-serif" font-size="64">🍽️</text>
  <text x="256" y="300" text-anchor="middle" font-family="Inter,sans-serif" font-size="18" fill="#4A7C59">{name[:30]}</text>
</svg>"""
    return Response(content=svg.encode(), media_type="image/svg+xml")


@router.get("/food-image")
async def get_food_image(name: str, category: str = ""):
    """Generate a food item image using FLUX.1-schnell."""
    from fridge_observer.image_gen import generate_food_item_image
    from fastapi.responses import Response

    image_bytes = await generate_food_item_image(name, category)
    if image_bytes:
        return Response(content=image_bytes, media_type="image/jpeg")

    cat_emoji = {"fruits": "🍎", "vegetables": "🥦", "dairy": "🧀", "beverages": "🥤", "meat": "🥩", "packaged_goods": "📦"}.get(category, "🍽️")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect width="256" height="256" fill="#F4F3EF" rx="12"/>
  <text x="128" y="140" text-anchor="middle" font-family="Inter,sans-serif" font-size="80">{cat_emoji}</text>
  <text x="128" y="200" text-anchor="middle" font-family="Inter,sans-serif" font-size="14" fill="#6B6860">{name[:20]}</text>
</svg>"""
    return Response(content=svg.encode(), media_type="image/svg+xml")
