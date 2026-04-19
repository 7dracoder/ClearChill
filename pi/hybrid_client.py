#!/usr/bin/env python3
"""
Hybrid inference client — best of both worlds.

Strategy:
  1. Use YOLOv8 ONNX for fast object detection + tracking (2-5 FPS)
  2. For items that need expiry dates, call Gemini on a single key frame
  3. Merge results: YOLO's bounding boxes + Gemini's expiry reading

Advantages:
  • Fast local inference for detection + in/out tracking
  • Precise per-object tracking using bounding boxes
  • Expiry date reading from labels (Gemini's strength)
  • Minimal API calls (only for packaged items, only once per session)

Use case: Production-ready system with best speed + accuracy.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv

# Import both clients
try:
    from yolo_client import identify_food_multi as yolo_identify_multi, load_model as yolo_load
except ImportError:
    yolo_identify_multi = None
    yolo_load = None

try:
    from gemini_client import _call_gemini, _enrich
except ImportError:
    _call_gemini = None
    _enrich = None

load_dotenv()

logger = logging.getLogger(__name__)

USE_HYBRID = os.getenv("USE_HYBRID_INFERENCE", "true").lower() == "true"


def identify_food_multi(frames: list[bytes]) -> dict:
    """
    Hybrid multi-frame inference.
    
    Flow:
      1. Run YOLO on first + last frames → get items_added/removed with bboxes
      2. For items_added that need expiry input, run Gemini on middle frame
      3. Merge: YOLO's tracking + Gemini's expiry dates
    
    Returns same schema as gemini_client.identify_food_multi().
    """
    if not USE_HYBRID or yolo_identify_multi is None:
        # Fall back to pure Gemini
        logger.info("Hybrid mode disabled or YOLO unavailable — using Gemini only")
        from gemini_client import identify_food_multi as gemini_multi
        return gemini_multi(frames)

    if not frames:
        return {"items_added": [], "items_removed": [], "all_items": []}

    # ── Step 1: YOLO for fast detection + tracking ───────────────────────────
    logger.info("Running YOLO inference for object tracking…")
    yolo_result = yolo_identify_multi(frames)

    items_added = yolo_result["items_added"]
    items_removed = yolo_result["items_removed"]

    if not items_added:
        # Nothing added — no need for Gemini
        logger.info("No items added — skipping Gemini")
        return yolo_result

    # ── Step 2: Identify packaged items that need expiry reading ─────────────
    needs_expiry_reading = [
        item for item in items_added
        if item.get("needs_expiry_input") and item.get("expiry_source") == "unknown"
    ]

    if not needs_expiry_reading:
        # All items are fresh produce with estimated expiry — done
        logger.info("All added items have estimated expiry — skipping Gemini")
        return yolo_result

    # ── Step 3: Call Gemini on middle frame to read expiry dates ─────────────
    logger.info("Calling Gemini to read expiry dates for %d packaged item(s)…",
                len(needs_expiry_reading))

    if _call_gemini is None:
        logger.warning("Gemini client not available — cannot read expiry dates")
        return yolo_result

    middle_frame = frames[len(frames) // 2]
    gemini_raw = _call_gemini(middle_frame)

    if not gemini_raw:
        logger.warning("Gemini returned no results")
        return yolo_result

    # ── Step 4: Merge Gemini's expiry info into YOLO's detections ────────────
    # Build lookup: item name → expiry info from Gemini
    gemini_lookup = {}
    for g_item in gemini_raw:
        name = g_item.get("name", "").lower().strip()
        expiry_date = g_item.get("expiry_date")
        expiry_source = g_item.get("expiry_source", "unknown")
        if expiry_date and expiry_source == "label":
            gemini_lookup[name] = expiry_date

    # Update items_added with Gemini's expiry dates
    for item in items_added:
        name_key = item["name"].lower().strip()
        if name_key in gemini_lookup:
            item["expiry_date"] = gemini_lookup[name_key]
            item["expiry_source"] = "label"
            item["needs_expiry_input"] = False
            logger.info("Merged expiry date for %s: %s", item["name"], item["expiry_date"])

    logger.info("Hybrid inference complete: %d added, %d removed",
                len(items_added), len(items_removed))

    return {
        "items_added": items_added,
        "items_removed": items_removed,
        "all_items": yolo_result["all_items"],
    }


# ── Single-frame API (for camera_stream.py /capture endpoint) ────────────────

def identify_food(image_bytes: bytes) -> list[dict]:
    """
    Single-frame inference. Uses YOLO if available, else Gemini.
    """
    if USE_HYBRID and yolo_load is not None:
        from yolo_client import identify_food as yolo_identify
        return yolo_identify(image_bytes)
    else:
        from gemini_client import identify_food as gemini_identify
        return gemini_identify(image_bytes)
