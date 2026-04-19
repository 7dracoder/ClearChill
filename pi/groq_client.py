#!/usr/bin/env python3
"""
Groq vision inference client using Llama 3.2 Vision.
Replaces Gemini for food item detection with faster inference.
"""

import os
import json
import base64
import logging
from typing import Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.2-11b-vision-preview")

if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set in .env")

client = Groq(api_key=GROQ_API_KEY)


def _call_groq(image_bytes: bytes) -> list[dict]:
    """
    Call Groq vision API to identify food items in an image.
    Returns list of detected items with metadata.
    """
    # Encode image to base64
    b64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = """You are a food identification assistant for a smart fridge system.
Analyze this image and identify all food items visible.

Return ONLY a JSON array of objects with this exact format:
[
  {
    "name": "Milk",
    "category": "dairy",
    "confidence": 0.95,
    "packaged": true,
    "expiry_date": "2024-04-25",
    "expiry_source": "label",
    "needs_expiry_input": false
  }
]

Categories: fruits, vegetables, dairy, beverages, meat, packaged_goods

Rules:
- Be specific (e.g., "Chicken Breast" not just "Chicken")
- Include brand names if visible
- Only include items you're confident about (>70% confidence)
- For packaged items: try to read expiry date from label
- For fresh produce: set expiry_source to "estimated" and estimate expiry
- Set needs_expiry_input to true if packaged but can't read expiry
- Return empty array [] if no food items visible
"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        
        content = response.choices[0].message.content.strip()
        
        # Extract JSON from response (handle markdown code blocks)
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        items = json.loads(content)
        
        if not isinstance(items, list):
            logger.warning("Groq returned non-list response")
            return []
        
        return items
        
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return []


def _enrich(items: list[dict]) -> list[dict]:
    """
    Enrich detected items with additional metadata and expiry estimates.
    """
    enriched = []
    
    for item in items:
        name = item.get("name", "Unknown")
        category = item.get("category", "packaged_goods")
        confidence = item.get("confidence", 0.5)
        packaged = item.get("packaged", True)
        expiry_date = item.get("expiry_date")
        expiry_source = item.get("expiry_source", "unknown")
        needs_expiry_input = item.get("needs_expiry_input", False)
        
        # Estimate expiry for fresh produce if not provided
        if not expiry_date and not packaged:
            days_until_expiry = {
                "fruits": 5,
                "vegetables": 7,
                "meat": 3,
                "dairy": 7,
            }.get(category, 5)
            
            expiry_date = (datetime.now() + timedelta(days=days_until_expiry)).strftime("%Y-%m-%d")
            expiry_source = "estimated"
            needs_expiry_input = False
        
        enriched.append({
            "name": name,
            "category": category,
            "confidence": confidence,
            "packaged": packaged,
            "expiry_date": expiry_date,
            "expiry_source": expiry_source,
            "needs_expiry_input": needs_expiry_input,
        })
    
    return enriched


def identify_food(image_bytes: bytes) -> list[dict]:
    """
    Single-frame food identification using Groq.
    """
    items = _call_groq(image_bytes)
    return _enrich(items)


def identify_food_multi(frames: list[bytes]) -> dict:
    """
    Multi-frame food identification with change detection.
    
    Strategy:
      - Analyze first frame (before) and last frame (after)
      - Compare to determine items_added and items_removed
    """
    if not frames:
        return {"items_added": [], "items_removed": [], "all_items": []}
    
    # Select key frames
    first_frame = frames[0]
    last_frame = frames[-1]
    
    logger.info(f"Analyzing {len(frames)} frames with Groq (first + last)")
    
    # Analyze both frames
    items_before = identify_food(first_frame)
    items_after = identify_food(last_frame)
    
    # Build name sets for comparison
    names_before = {item["name"].lower() for item in items_before}
    names_after = {item["name"].lower() for item in items_after}
    
    # Determine changes
    added_names = names_after - names_before
    removed_names = names_before - names_after
    
    items_added = [item for item in items_after if item["name"].lower() in added_names]
    items_removed = [item for item in items_before if item["name"].lower() in removed_names]
    
    logger.info(f"Groq detected: {len(items_added)} added, {len(items_removed)} removed")
    
    return {
        "items_added": items_added,
        "items_removed": items_removed,
        "all_items": items_after,
    }
