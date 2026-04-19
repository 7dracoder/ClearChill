#!/usr/bin/env python3
"""
Gemini Vision client — runs on the Raspberry Pi.

Calls the Gemini API directly from the Pi so AI inference happens
before anything is sent to the server. Images never leave the Pi —
only the structured JSON item list is forwarded.

Expiry priority (highest → lowest):
  1. AI reads the date directly from the label in the image  → use it, no user input needed
  2. Item is fresh/unpackaged with a known shelf life        → use estimated days
  3. Item is packaged but date is not visible in the image   → ask user

In/out detection:
  Compare first-frame detections vs last-frame detections.
  Present in last but not first  → item was PUT IN
  Present in first but not last  → item was TAKEN OUT

Public API:
  identify_food(image_bytes)        — single frame
  identify_food_multi(frames_list)  — full session with in/out tracking
"""

import base64
import json
import logging
import os
import time
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Minimum averaged confidence across key frames to include an item in results.
# Items below this are silently dropped — not added, not queued for user input.
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))

# ── Food expiry database ──────────────────────────────────────────────────────
# (False, days) = fresh item, auto-estimate expiry
# (True,  None) = packaged item, expiry date must come from label or user

FOOD_EXPIRY_DATABASE: dict[str, tuple[bool, Optional[int]]] = {
    # Fruits
    "apple": (False, 7), "banana": (False, 5), "orange": (False, 10),
    "strawberry": (False, 3), "strawberries": (False, 3),
    "grape": (False, 5), "grapes": (False, 5),
    "watermelon": (False, 7), "melon": (False, 7),
    "pear": (False, 7), "peach": (False, 5), "plum": (False, 5),
    "cherry": (False, 3), "cherries": (False, 3),
    "blueberry": (False, 5), "blueberries": (False, 5),
    "raspberry": (False, 2), "raspberries": (False, 2),
    "mango": (False, 5), "pineapple": (False, 5), "kiwi": (False, 7),
    "lemon": (False, 14), "lime": (False, 14),
    # Vegetables
    "lettuce": (False, 5), "carrot": (False, 14), "carrots": (False, 14),
    "tomato": (False, 7), "tomatoes": (False, 7), "cucumber": (False, 7),
    "broccoli": (False, 5), "spinach": (False, 3),
    "bell pepper": (False, 7), "pepper": (False, 7),
    "onion": (False, 30), "onions": (False, 30),
    "garlic": (False, 30), "potato": (False, 30), "potatoes": (False, 30),
    "celery": (False, 7), "cabbage": (False, 14), "cauliflower": (False, 7),
    "zucchini": (False, 5), "eggplant": (False, 7),
    "mushroom": (False, 5), "mushrooms": (False, 5), "avocado": (False, 5),
    # Dairy
    "milk": (True, None), "yogurt": (True, None), "cheese": (True, None),
    "cheddar": (True, None), "mozzarella": (True, None),
    "butter": (False, 30), "cream": (True, None), "sour cream": (True, None),
    # Meat
    "chicken": (False, 2), "beef": (False, 3), "pork": (False, 3),
    "fish": (False, 1), "salmon": (False, 1), "tuna": (False, 1),
    "shrimp": (False, 1), "turkey": (False, 2),
    "bacon": (True, None), "sausage": (True, None), "ham": (True, None),
    # Beverages
    "juice": (True, None), "orange juice": (True, None),
    "apple juice": (True, None), "soda": (True, None),
    "water": (True, None), "beer": (True, None), "wine": (False, 365),
    # Packaged
    "bread": (True, None), "eggs": (True, None), "egg": (True, None),
    "tofu": (True, None), "hummus": (True, None), "salsa": (True, None),
    "ketchup": (True, None), "mayonnaise": (True, None), "mustard": (True, None),
    # Leftovers
    "leftover": (False, 3), "cooked rice": (False, 3),
    "cooked pasta": (False, 3), "soup": (False, 3), "pizza": (False, 3),
    "cooked chicken": (False, 3), "cooked beef": (False, 3),
}

CATEGORY_DEFAULTS: dict[str, tuple[bool, Optional[int]]] = {
    "fruits": (False, 7), "vegetables": (False, 7),
    "dairy": (True, None), "meat": (False, 2),
    "beverages": (True, None), "packaged_goods": (True, None),
}


def classify_item(name: str, category: str) -> tuple[bool, Optional[int]]:
    """Return (needs_user_expiry_input, estimated_days)."""
    key = name.lower().strip()
    if key in FOOD_EXPIRY_DATABASE:
        return FOOD_EXPIRY_DATABASE[key]
    for food_name, val in FOOD_EXPIRY_DATABASE.items():
        if food_name in key or key in food_name:
            return val
    if category in CATEGORY_DEFAULTS:
        return CATEGORY_DEFAULTS[category]
    return (True, None)


# ── Gemini prompt ─────────────────────────────────────────────────────────────
#
# Key design decisions baked into the prompt:
#   • Gemini tries to read the expiry date from the label first
#   • Only reports items it is ≥75% confident about
#   • Returns expiry_date as ISO string if visible, null otherwise
#   • Returns expiry_source: "label" | "estimated" | "unknown"
#   • Does NOT guess expiry for packaged items — that's our job

PROMPT = """\
You are a food identification assistant for a smart fridge system.
Analyse this image and identify all food items visible.

RULES — follow these exactly:
1. Only report items you are at least 75% confident about. Skip anything uncertain.
2. For each item, try to read any visible expiry / best-before / use-by date from the label.
3. If you can read the date clearly, include it as expiry_date in ISO format (YYYY-MM-DD).
4. If the item is fresh produce (fruit, vegetable, unpackaged meat/fish), set expiry_source to "estimated" and omit expiry_date — the system will estimate it.
5. If the item is packaged and you cannot read the date, set expiry_source to "unknown" and omit expiry_date — the user will be asked.
6. Never guess an expiry date for packaged goods — only report what you can actually read.

For each item provide:
- name: specific common name (e.g. "whole milk", "granny smith apple", "cheddar cheese")
- category: one of [fruits, vegetables, dairy, beverages, meat, packaged_goods]
- confidence: float 0.75–1.0 (only include items you are this confident about)
- expiry_date: ISO date string if readable from label, otherwise omit this field
- expiry_source: "label" if you read it, "estimated" if fresh produce, "unknown" if packaged and not readable

Respond ONLY with valid JSON:
{
  "items": [
    {"name": "whole milk", "category": "dairy", "confidence": 0.95, "expiry_date": "2026-04-28", "expiry_source": "label"},
    {"name": "apple",      "category": "fruits", "confidence": 0.92, "expiry_source": "estimated"},
    {"name": "yogurt",     "category": "dairy",  "confidence": 0.88, "expiry_source": "unknown"}
  ]
}
If no food is visible return {"items": []}.
No explanation outside the JSON."""


# ── Gemini API call ───────────────────────────────────────────────────────────

def _call_gemini(image_bytes: bytes, mime_type: str = "image/jpeg") -> list[dict]:
    """
    Single synchronous Gemini call. Returns raw item list.
    Retries up to 3 times on rate limit / timeout.
    """
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set")
        return []

    payload = {
        "contents": [{
            "parts": [
                {"text": PROMPT},
                {"inline_data": {
                    "mime_type": mime_type,
                    "data": base64.b64encode(image_bytes).decode(),
                }},
            ]
        }],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
    }
    url = f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"

    for attempt in range(3):
        try:
            resp = httpx.post(url, json=payload, timeout=30.0)
        except httpx.TimeoutException:
            logger.warning("Gemini timeout (attempt %d/3)", attempt + 1)
            time.sleep(5)
            continue

        if resp.status_code == 429:
            wait = (attempt + 1) * 10
            logger.warning("Gemini rate limit — retrying in %ds", wait)
            time.sleep(wait)
            continue
        if resp.status_code in (400, 403):
            logger.error("Gemini error %s: %s", resp.status_code, resp.text[:200])
            return []

        resp.raise_for_status()

        try:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text).get("items", [])
        except (KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.error("Failed to parse Gemini response: %s", exc)
            return []

    logger.error("Gemini failed after 3 attempts")
    return []


# ── Enrichment ────────────────────────────────────────────────────────────────

def _enrich(raw_items: list[dict]) -> list[dict]:
    """
    Resolve expiry for each item using this priority:
      1. Gemini read the date from the label  → use it directly
      2. Fresh produce (expiry_source=estimated) → use our shelf-life DB
      3. Packaged, date not visible            → needs_expiry_input = True

    Also drops items below CONFIDENCE_THRESHOLD.
    """
    result = []
    for item in raw_items:
        conf = float(item.get("confidence", 0.0))
        if conf < CONFIDENCE_THRESHOLD:
            logger.debug("Dropping low-confidence item: %s (%.2f)", item.get("name"), conf)
            continue

        name          = item.get("name", "Unknown").strip()
        category      = item.get("category", "packaged_goods")
        expiry_source = item.get("expiry_source", "unknown")
        expiry_date   = item.get("expiry_date")   # ISO string or None

        if expiry_source == "label" and expiry_date:
            # Best case: AI read the date off the packaging
            result.append({
                "name":                  name.title(),
                "category":              category,
                "confidence":            round(conf, 2),
                "expiry_source":         "label",
                "expiry_date":           expiry_date,       # exact date from label
                "estimated_expiry_days": None,
                "needs_expiry_input":    False,
            })

        elif expiry_source == "estimated":
            # Fresh produce — use our shelf-life database
            _, est_days = classify_item(name, category)
            result.append({
                "name":                  name.title(),
                "category":              category,
                "confidence":            round(conf, 2),
                "expiry_source":         "estimated",
                "expiry_date":           None,
                "estimated_expiry_days": est_days,
                "needs_expiry_input":    False,
            })

        else:
            # Packaged item, date not readable — ask the user
            result.append({
                "name":                  name.title(),
                "category":              category,
                "confidence":            round(conf, 2),
                "expiry_source":         "unknown",
                "expiry_date":           None,
                "estimated_expiry_days": None,
                "needs_expiry_input":    True,
            })

    return result


# ── In/out detection ──────────────────────────────────────────────────────────

def _item_keys(items: list[dict]) -> set[str]:
    """Normalised name set for set-difference comparisons."""
    return {item.get("name", "").lower().strip() for item in items}


def _detect_movement(
    first_frame_items: list[dict],
    last_frame_items: list[dict],
    all_items: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Compare first and last frame detections to determine direction of movement.

    Returns (items_added, items_removed):
      items_added   — present in last frame but NOT in first  → put into fridge
      items_removed — present in first frame but NOT in last  → taken out of fridge

    Items that appear in both frames are treated as already-present inventory
    and are excluded from both lists (no change).

    all_items is used to look up the full enriched dict for each name.
    """
    first_keys = _item_keys(first_frame_items)
    last_keys  = _item_keys(last_frame_items)

    added_keys   = last_keys - first_keys
    removed_keys = first_keys - last_keys

    # Build lookup from enriched aggregated results
    lookup = {item["name"].lower().strip(): item for item in all_items}

    items_added   = [lookup[k] for k in added_keys   if k in lookup]
    items_removed = [lookup[k] for k in removed_keys if k in lookup]

    return items_added, items_removed


# ── Public API ────────────────────────────────────────────────────────────────

def identify_food(image_bytes: bytes, mime_type: str = "image/jpeg") -> list[dict]:
    """
    Analyse a single frame. Returns enriched item list.
    """
    raw = _call_gemini(image_bytes, mime_type)
    return _enrich(raw)


def identify_food_multi(
    frames: list[bytes],
    mime_type: str = "image/jpeg",
) -> dict:
    """
    Analyse a full door-open session.

    Strategy:
      1. Call Gemini on first, middle, and last frames
      2. Aggregate confidence scores across frames
      3. Enrich with expiry data (label > estimated > ask user)
      4. Compare first vs last frame to determine in/out direction

    Returns a dict:
      {
        "items_added":   [...],   # new items put into fridge
        "items_removed": [...],   # items taken out of fridge
        "all_items":     [...],   # everything detected (for debugging)
      }
    """
    if not frames:
        return {"items_added": [], "items_removed": [], "all_items": []}

    n = len(frames)
    # Always analyse first and last; add middle if session was long enough
    key_indices = sorted({0, n // 2, n - 1})
    key_frames  = [frames[i] for i in key_indices]

    logger.info("Analysing %d key frame(s) from %d total", len(key_frames), n)

    # Raw detections per key frame (needed for in/out comparison)
    per_frame_raw: list[list[dict]] = []

    # Aggregation across all key frames
    aggregated: dict[str, dict] = {}  # name_lower → {name, category, confidences, expiry fields}

    for i, frame_bytes in enumerate(key_frames):
        raw = _call_gemini(frame_bytes, mime_type)
        per_frame_raw.append(raw)
        logger.info("  Key frame %d/%d: %d item(s)", i + 1, len(key_frames), len(raw))

        for item in raw:
            name          = item.get("name", "Unknown").strip()
            key           = name.lower()
            category      = item.get("category", "packaged_goods")
            conf          = float(item.get("confidence", 0.0))
            expiry_source = item.get("expiry_source", "unknown")
            expiry_date   = item.get("expiry_date")

            if key not in aggregated:
                aggregated[key] = {
                    "name":          name,
                    "category":      category,
                    "confidences":   [],
                    # Keep the best expiry info seen across frames
                    "expiry_source": expiry_source,
                    "expiry_date":   expiry_date,
                }
            else:
                # Upgrade expiry source if a later frame has better info
                existing = aggregated[key]
                priority = {"label": 2, "estimated": 1, "unknown": 0}
                if priority.get(expiry_source, 0) > priority.get(existing["expiry_source"], 0):
                    existing["expiry_source"] = expiry_source
                    existing["expiry_date"]   = expiry_date

            aggregated[key]["confidences"].append(conf)

    if not aggregated:
        return {"items_added": [], "items_removed": [], "all_items": []}

    # Build averaged raw list and enrich
    raw_averaged = []
    for data in aggregated.values():
        avg_conf = sum(data["confidences"]) / len(data["confidences"])
        raw_averaged.append({
            "name":          data["name"],
            "category":      data["category"],
            "confidence":    round(avg_conf, 2),
            "expiry_source": data["expiry_source"],
            "expiry_date":   data["expiry_date"],
        })

    all_items = _enrich(raw_averaged)
    all_items.sort(key=lambda x: x["confidence"], reverse=True)

    # In/out detection using first vs last key frame
    first_raw = per_frame_raw[0]  if per_frame_raw else []
    last_raw  = per_frame_raw[-1] if per_frame_raw else []

    items_added, items_removed = _detect_movement(first_raw, last_raw, all_items)

    logger.info(
        "Session result: %d added, %d removed, %d total detected",
        len(items_added), len(items_removed), len(all_items),
    )

    return {
        "items_added":   items_added,
        "items_removed": items_removed,
        "all_items":     all_items,
    }
