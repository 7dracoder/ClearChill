"""AI client for K2-Think (reasoning) and Gemini (vision) APIs."""
import base64
import json
import logging
import os
from typing import AsyncIterator

import httpx

logger = logging.getLogger(__name__)

# Keys are loaded from environment variables (see .env.example)
K2_API_KEY = os.environ.get("K2_API_KEY", "")
K2_BASE_URL = "https://api.k2think.ai/v1"
K2_MODEL = "MBZUAI-IFM/K2-Think-v2"

# Gemini — used for image understanding (food identification from webcam frames)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-pro"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


# ── K2-Think ─────────────────────────────────────────────────

async def k2_chat(messages: list[dict], stream: bool = False) -> str:
    """Send a chat request to K2-Think and return the full response text."""
    payload = {
        "model": K2_MODEL,
        "messages": messages,
        "stream": stream,
    }
    headers = {
        "Authorization": f"Bearer {K2_API_KEY}",
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        if stream:
            full_text = ""
            async with client.stream(
                "POST",
                f"{K2_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_text += content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
            return full_text
        else:
            response = await client.post(
                f"{K2_BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]


async def k2_chat_stream(messages: list[dict]) -> AsyncIterator[str]:
    """Stream K2-Think response tokens as an async generator."""
    payload = {
        "model": K2_MODEL,
        "messages": messages,
        "stream": True,
    }
    headers = {
        "Authorization": f"Bearer {K2_API_KEY}",
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream(
            "POST",
            f"{K2_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


# ── Gemini Vision ─────────────────────────────────────────────

async def gemini_identify_food(image_bytes: bytes, mime_type: str = "image/jpeg") -> dict:
    """
    Send an image to Gemini and get back a structured list of identified food items.
    Returns: {"items": [{"name": str, "category": str, "confidence": float}], "raw": str}
    """
    if not GEMINI_API_KEY:
        return {"items": [], "raw": "Gemini API key not configured.", "error": "no_api_key"}

    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """You are a food identification assistant for a smart fridge system.
Analyze this image and identify all food items visible.

For each food item, provide:
- name: common name of the item (e.g. "milk", "apple", "cheddar cheese")
- category: one of [fruits, vegetables, dairy, beverages, meat, packaged_goods]
- confidence: a float between 0.0 and 1.0

Respond ONLY with valid JSON in this exact format:
{
  "items": [
    {"name": "milk", "category": "dairy", "confidence": 0.95},
    {"name": "apple", "category": "fruits", "confidence": 0.88}
  ]
}

If no food items are visible, return {"items": []}.
Do not include any explanation outside the JSON."""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type,
                            "data": image_b64,
                        }
                    },
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
        },
    }

    url = f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
        return {"items": parsed.get("items", []), "raw": text}
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning("Failed to parse Gemini response: %s", exc)
        return {"items": [], "raw": str(data), "error": str(exc)}


# ── Inventory-aware prompts ───────────────────────────────────

def build_inventory_context(inventory: list[dict]) -> str:
    """Build a concise inventory summary string for AI prompts."""
    if not inventory:
        return "The fridge is currently empty."

    lines = ["Current fridge inventory:"]
    for item in inventory:
        expiry = item.get("expiry_date")
        expiry_str = f", expires {expiry}" if expiry else ""
        lines.append(f"  - {item['name']} ({item['category']}, qty: {item.get('quantity', 1)}{expiry_str})")
    return "\n".join(lines)


async def k2_suggest_recipes(inventory: list[dict], preferences: str = "") -> str:
    """Ask K2 to suggest recipes based on current inventory, prioritising expiring items."""
    context = build_inventory_context(inventory)
    pref_str = f"\nUser preferences: {preferences}" if preferences else ""

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful culinary assistant for a smart fridge app. "
                "Your goal is to help users reduce food waste by suggesting recipes "
                "that use ingredients that are expiring soon. "
                "Be concise, practical, and enthusiastic about cooking."
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
    return await k2_chat(messages, stream=True)


async def k2_storage_tip(item_name: str, category: str) -> str:
    """Ask K2 for a storage tip for a specific food item."""
    messages = [
        {
            "role": "system",
            "content": "You are a food storage expert. Give concise, practical storage tips in 1-2 sentences.",
        },
        {
            "role": "user",
            "content": f"How should I store {item_name} ({category}) to maximise its shelf life?",
        },
    ]
    return await k2_chat(messages, stream=True)


async def k2_ask(question: str, inventory: list[dict]) -> str:
    """General-purpose Q&A with inventory context using K2."""
    context = build_inventory_context(inventory)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful smart fridge assistant. You have access to the user's "
                "current fridge inventory and can answer questions about food, recipes, "
                "storage, nutrition, and reducing food waste. Be concise and helpful."
            ),
        },
        {
            "role": "user",
            "content": f"{context}\n\nUser question: {question}",
        },
    ]
    return await k2_chat(messages, stream=True)
