"""
Hardware integration endpoints for Raspberry Pi sensor
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
import logging

from fridge_observer.auth import get_current_user

router = APIRouter(prefix="/api/hardware", tags=["hardware"])
logger = logging.getLogger(__name__)


# ── Food Classification & Expiry Estimation ───────────────────

# Comprehensive food expiry database
FOOD_EXPIRY_DATABASE = {
    # Fruits (fresh, not packaged)
    "apple": (False, 7),
    "banana": (False, 5),
    "orange": (False, 10),
    "strawberry": (False, 3),
    "strawberries": (False, 3),
    "grape": (False, 5),
    "grapes": (False, 5),
    "watermelon": (False, 7),
    "melon": (False, 7),
    "pear": (False, 7),
    "peach": (False, 5),
    "plum": (False, 5),
    "cherry": (False, 3),
    "cherries": (False, 3),
    "blueberry": (False, 5),
    "blueberries": (False, 5),
    "raspberry": (False, 2),
    "raspberries": (False, 2),
    "mango": (False, 5),
    "pineapple": (False, 5),
    "kiwi": (False, 7),
    "lemon": (False, 14),
    "lime": (False, 14),
    
    # Vegetables (fresh, not packaged)
    "lettuce": (False, 5),
    "carrot": (False, 14),
    "carrots": (False, 14),
    "tomato": (False, 7),
    "tomatoes": (False, 7),
    "cucumber": (False, 7),
    "broccoli": (False, 5),
    "spinach": (False, 3),
    "bell pepper": (False, 7),
    "pepper": (False, 7),
    "onion": (False, 30),
    "onions": (False, 30),
    "garlic": (False, 30),
    "potato": (False, 30),
    "potatoes": (False, 30),
    "celery": (False, 7),
    "cabbage": (False, 14),
    "cauliflower": (False, 7),
    "zucchini": (False, 5),
    "eggplant": (False, 7),
    "mushroom": (False, 5),
    "mushrooms": (False, 5),
    "avocado": (False, 5),
    
    # Dairy (mostly packaged)
    "milk": (True, None),  # Packaged - needs user input
    "yogurt": (True, None),
    "cheese": (True, None),
    "cheddar": (True, None),
    "mozzarella": (True, None),
    "butter": (False, 30),  # Usually doesn't have expiry printed
    "cream": (True, None),
    "sour cream": (True, None),
    
    # Meat (fresh, short shelf life)
    "chicken": (False, 2),
    "beef": (False, 3),
    "pork": (False, 3),
    "fish": (False, 1),
    "salmon": (False, 1),
    "tuna": (False, 1),
    "shrimp": (False, 1),
    "turkey": (False, 2),
    "bacon": (True, None),  # Usually packaged with date
    "sausage": (True, None),
    "ham": (True, None),
    
    # Beverages (mostly packaged)
    "juice": (True, None),
    "orange juice": (True, None),
    "apple juice": (True, None),
    "soda": (True, None),
    "water": (True, None),
    "beer": (True, None),
    "wine": (False, 365),  # Wine lasts long
    
    # Packaged goods
    "bread": (True, None),
    "eggs": (True, None),
    "egg": (True, None),
    "tofu": (True, None),
    "hummus": (True, None),
    "salsa": (True, None),
    "ketchup": (True, None),
    "mayonnaise": (True, None),
    "mustard": (True, None),
    
    # Leftovers (cooked food)
    "leftover": (False, 3),
    "cooked rice": (False, 3),
    "cooked pasta": (False, 3),
    "soup": (False, 3),
    "pizza": (False, 3),
    "cooked chicken": (False, 3),
    "cooked beef": (False, 3),
}

# Category-based defaults
CATEGORY_DEFAULTS = {
    "fruits": (False, 7),
    "vegetables": (False, 7),
    "dairy": (True, None),
    "meat": (False, 2),
    "beverages": (True, None),
    "packaged_goods": (True, None),
}


def _classify_item(name: str, category: str) -> Tuple[bool, Optional[int]]:
    """
    Classify if item is packaged and estimate expiry days.
    
    Returns:
        (is_packaged, expiry_days)
        - is_packaged: True if needs user input for expiry
        - expiry_days: Days until expiry (None if packaged)
    """
    name_lower = name.lower().strip()
    
    # Check exact match in database
    if name_lower in FOOD_EXPIRY_DATABASE:
        return FOOD_EXPIRY_DATABASE[name_lower]
    
    # Check partial matches (e.g., "green apple" matches "apple")
    for food_name, (is_packaged, days) in FOOD_EXPIRY_DATABASE.items():
        if food_name in name_lower or name_lower in food_name:
            return (is_packaged, days)
    
    # Fall back to category default
    if category in CATEGORY_DEFAULTS:
        return CATEGORY_DEFAULTS[category]
    
    # Ultimate fallback: assume packaged
    logger.warning(f"Unknown food item: {name} ({category}), assuming packaged")
    return (True, None)


class DoorEvent(BaseModel):
    event: str  # "door_opened" or "door_closed"
    timestamp: str
    light_level: Optional[float] = None


class HardwareStatus(BaseModel):
    light_level: float
    last_capture: Optional[str] = None
    status: str  # "online", "offline", "error"
    timestamp: str


class DetectedItem(BaseModel):
    name: str
    confidence: float
    category: Optional[str] = None


class ItemWithUserInput(BaseModel):
    item_name: str
    quantity: int  # REQUIRED - Google Home asks for this
    expiry_date: Optional[str] = None  # ISO format: "2026-04-25" - only for packaged items
    category: Optional[str] = None
    estimated_expiry_days: Optional[int] = None  # For fresh items


class ExpiryDateInput(BaseModel):
    item_name: str
    quantity: int
    expiry_date: str  # ISO format: "2026-04-25"


class SessionItem(BaseModel):
    name: str
    category: str
    confidence: float
    needs_expiry_input: bool
    expiry_source: Optional[str] = "unknown"   # "label" | "estimated" | "unknown"
    expiry_date: Optional[str] = None           # ISO date if read from label
    estimated_expiry_days: Optional[int] = None


class SessionComplete(BaseModel):
    session_id: str
    started_at: str
    ended_at: str
    duration_seconds: int
    frames_captured: int
    items_added: List[SessionItem]
    items_removed: Optional[List[SessionItem]] = []
    low_confidence_items: Optional[List] = []


@router.post("/session-complete")
async def receive_session_complete(
    session: SessionComplete,
    current_user: dict = Depends(get_current_user)
):
    """
    Receive a completed capture session from the Raspberry Pi.
    The Pi has already run Gemini inference locally — this endpoint
    only handles persistence and WebSocket broadcast.
    No image data is received here.
    """
    from datetime import datetime, timedelta
    from fridge_observer.supabase_client import get_supabase
    from fridge_observer.ws_manager import manager

    logger.info(
        "Session %s: %d item(s) detected, %d frame(s), %.1f s",
        session.session_id,
        len(session.items_added),
        session.frames_captured,
        session.duration_seconds,
    )

    sb = get_supabase()
    added_items   = []
    needs_expiry  = []
    removed_items = []

    # ── Process items added to fridge ─────────────────────────
    for item in session.items_added:
        if item.expiry_source == "label" and item.expiry_date:
            # Best case: Gemini read the date directly off the label
            try:
                sb.table("food_items").insert({
                    "name":        item.name,
                    "category":    item.category,
                    "quantity":    1,
                    "expiry_date": item.expiry_date,
                    "user_id":     current_user["sub"],
                    "added_via":   "hardware_label",
                }).execute()
                added_items.append({
                    "name":        item.name,
                    "category":    item.category,
                    "expiry_date": item.expiry_date,
                    "expiry_source": "label",
                })
                logger.info("Auto-added %s (label date: %s)", item.name, item.expiry_date)
            except Exception as exc:
                logger.error("Failed to insert %s: %s", item.name, exc)

        elif not item.needs_expiry_input and item.estimated_expiry_days is not None:
            # Fresh produce — use estimated shelf life
            expiry_date = datetime.utcnow() + timedelta(days=item.estimated_expiry_days)
            try:
                sb.table("food_items").insert({
                    "name":        item.name,
                    "category":    item.category,
                    "quantity":    1,
                    "expiry_date": expiry_date.date().isoformat(),
                    "user_id":     current_user["sub"],
                    "added_via":   "hardware_auto",
                }).execute()
                added_items.append({
                    "name":        item.name,
                    "category":    item.category,
                    "expiry_date": expiry_date.date().isoformat(),
                    "expiry_source": "estimated",
                    "estimated_days": item.estimated_expiry_days,
                })
                logger.info("Auto-added %s (estimated expiry: %s)", item.name, expiry_date.date())
            except Exception as exc:
                logger.error("Failed to insert %s: %s", item.name, exc)

        else:
            # Packaged item, date not visible — queue for user input
            needs_expiry.append({
                "name":     item.name,
                "category": item.category,
                "confidence": item.confidence,
            })
            logger.info("Queued for expiry input: %s", item.name)

    # ── Process items removed from fridge ─────────────────────
    for item in (session.items_removed or []):
        try:
            # Mark as removed in inventory (soft delete — set quantity to 0 or delete)
            result = sb.table("food_items").select("id").eq(
                "name", item.name
            ).eq("user_id", current_user["sub"]).order(
                "created_at", desc=True
            ).limit(1).execute()

            if result.data:
                item_id = result.data[0]["id"]
                sb.table("food_items").delete().eq("id", item_id).execute()
                removed_items.append({"name": item.name, "category": item.category})
                logger.info("Removed %s from inventory", item.name)
            else:
                logger.info("Removal: %s not found in inventory (may not have been tracked)", item.name)
        except Exception as exc:
            logger.error("Failed to remove %s: %s", item.name, exc)

    # Broadcast real-time update to web UI
    if added_items or needs_expiry or removed_items:
        await manager.broadcast({
            "type":   "inventory_updated",
            "action": "session_complete",
            "session_id":         session.session_id,
            "auto_added":         added_items,
            "needs_expiry_input": needs_expiry,
            "removed":            removed_items,
            "source": "hardware_session",
        })

    return {
        "status":                "processed",
        "session_id":            session.session_id,
        "pending_items_created": len(needs_expiry),
        "auto_added":            added_items,
        "needs_expiry_input":    needs_expiry,
        "removed":               removed_items,
        "timestamp":             datetime.utcnow().isoformat() + "Z",
    }


@router.post("/door-event")
async def receive_door_event(
    event: DoorEvent,
    current_user: dict = Depends(get_current_user)
):
    """
    Receive door open/close events from Raspberry Pi
    """
    logger.info(f"Door event: {event.event} at {event.timestamp} (light: {event.light_level})")
    
    # Store event in database (optional - for analytics)
    # You can add a door_events table to track usage patterns
    
    return {
        "status": "received",
        "event": event.event,
        "timestamp": event.timestamp
    }


@router.post("/capture-image")
async def receive_captured_image(
    image: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Receive captured fridge image from Raspberry Pi
    Process with AI to detect food items
    Determine if packaged (needs expiry input) or fresh (auto-estimate)
    """
    try:
        # Read image data
        image_data = await image.read()
        logger.info(f"Received image: {len(image_data)} bytes")
        
        # Process image with Gemini AI vision
        from fridge_observer.ai_client import gemini_identify_food
        from datetime import datetime, timedelta
        
        vision_result = await gemini_identify_food(image_data, mime_type=image.content_type or "image/jpeg")
        
        if vision_result.get("error"):
            logger.warning(f"Vision API error: {vision_result.get('error')}")
            # Fall back to empty list if vision fails
            raw_items = []
        else:
            raw_items = vision_result.get("items", [])
        
        logger.info(f"Gemini detected {len(raw_items)} items")
        
        # Enhance detected items with packaging detection and expiry estimates
        detected_items = []
        for item in raw_items:
            name = item.get("name", "Unknown")
            category = item.get("category", "packaged_goods")
            confidence = item.get("confidence", 0.5)
            
            # Determine if packaged and get expiry estimate
            is_packaged, expiry_days = _classify_item(name, category)
            
            detected_items.append({
                "name": name.title(),
                "confidence": confidence,
                "category": category,
                "is_packaged": is_packaged,
                "needs_expiry_input": is_packaged,
                "estimated_expiry_days": expiry_days if not is_packaged else None
            })
        
        # ALL items need user input for quantity AND expiry (for packaged items)
        # Google Home will ask:
        # 1. For ALL items: "What's the quantity?"
        # 2. For packaged items only: "What's the expiry date?"
        
        needs_user_input = []
        for item in detected_items:
            needs_user_input.append({
                "name": item["name"],
                "category": item["category"],
                "confidence": item["confidence"],
                "needs_quantity": True,  # Always ask for quantity
                "needs_expiry": item["needs_expiry_input"],  # Only packaged items
                "estimated_expiry_days": item["estimated_expiry_days"]
            })
        
        logger.info(f"Detected {len(detected_items)} items - ALL need quantity input, {len([i for i in detected_items if i['needs_expiry_input']])} also need expiry")
        
        return {
            "status": "processed",
            "total_items": len(detected_items),
            "needs_user_input": needs_user_input,  # Google Home will ask for quantity + expiry
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/status")
async def receive_hardware_status(
    status: HardwareStatus,
    current_user: dict = Depends(get_current_user)
):
    """
    Receive hardware status updates from Raspberry Pi
    """
    logger.info(f"Hardware status: {status.status} (light: {status.light_level})")
    
    # Store status in database or cache for monitoring dashboard
    
    return {
        "status": "received",
        "timestamp": status.timestamp
    }


@router.get("/status")
async def get_hardware_status(
    current_user: dict = Depends(get_current_user)
):
    """
    Get current hardware status (for web app dashboard)
    """
    # TODO: Retrieve latest status from database/cache
    
    return {
        "status": "online",
        "light_level": 0.75,
        "last_capture": "2026-04-18T14:30:00Z",
        "last_update": datetime.utcnow().isoformat() + "Z"
    }


@router.post("/add-item-with-expiry")
async def add_item_with_expiry(
    expiry_input: ExpiryDateInput,
    current_user: dict = Depends(get_current_user)
):
    """
    Add item to inventory with expiry date (called by Google Home after user provides date)
    """
    try:
        from datetime import datetime
        from fridge_observer.supabase_client import get_supabase
        from fridge_observer.ws_manager import manager
        
        # Parse expiry date
        expiry_date = datetime.fromisoformat(expiry_input.expiry_date)
        
        logger.info(f"Adding {expiry_input.item_name} with expiry {expiry_date.date()}")
        
        # Determine category based on item name
        category = _guess_category(expiry_input.item_name)
        
        # Add to Supabase inventory
        sb = get_supabase()
        result = sb.table("food_items").insert({
            "name": expiry_input.item_name,
            "category": category,
            "quantity": expiry_input.quantity,
            "expiry_date": expiry_date.date().isoformat(),
            "user_id": current_user["sub"],
            "added_via": "hardware_voice"
        }).execute()
        
        item_id = result.data[0]["id"] if result.data else None
        
        # Send WebSocket notification for real-time UI update
        await manager.broadcast({
            "type": "inventory_updated",
            "action": "item_added",
            "item": {
                "id": item_id,
                "name": expiry_input.item_name,
                "category": category,
                "quantity": expiry_input.quantity,
                "expiry_date": expiry_date.date().isoformat()
            },
            "source": "hardware_voice"
        })
        
        return {
            "status": "added",
            "item": expiry_input.item_name,
            "expiry_date": expiry_input.expiry_date,
            "quantity": expiry_input.quantity,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
    except Exception as e:
        logger.error(f"Error adding item with expiry: {e}")
        raise HTTPException(status_code=400, detail=str(e))


def _guess_category(item_name: str) -> str:
    """
    Guess the category of a food item based on its name.
    """
    name_lower = item_name.lower().strip()
    
    # Fruits
    fruits = ["apple", "banana", "orange", "strawberry", "grape", "watermelon", 
              "melon", "pear", "peach", "plum", "cherry", "blueberry", "raspberry",
              "mango", "pineapple", "kiwi", "lemon", "lime"]
    if any(fruit in name_lower for fruit in fruits):
        return "fruits"
    
    # Vegetables
    vegetables = ["lettuce", "carrot", "tomato", "cucumber", "broccoli", "spinach",
                  "pepper", "onion", "garlic", "potato", "celery", "cabbage",
                  "cauliflower", "zucchini", "eggplant", "mushroom", "avocado"]
    if any(veg in name_lower for veg in vegetables):
        return "vegetables"
    
    # Dairy
    dairy = ["milk", "yogurt", "cheese", "cheddar", "mozzarella", "butter", 
             "cream", "sour cream"]
    if any(d in name_lower for d in dairy):
        return "dairy"
    
    # Meat
    meat = ["chicken", "beef", "pork", "fish", "salmon", "tuna", "shrimp",
            "turkey", "bacon", "sausage", "ham"]
    if any(m in name_lower for m in meat):
        return "meat"
    
    # Beverages
    beverages = ["juice", "soda", "water", "beer", "wine", "milk"]
    if any(bev in name_lower for bev in beverages):
        return "beverages"
    
    # Default to packaged goods
    return "packaged_goods"


# ── New Session-Based Endpoints ──────────────────────────────────────────

class CaptureSessionComplete(BaseModel):
    session_id: str
    started_at: str
    ended_at: str
    duration_seconds: Optional[int] = None
    frames_captured: int
    items_added: List[Dict[str, Any]]
    items_removed: List[Dict[str, Any]] = []
    low_confidence_items: List[Dict[str, Any]] = []


@router.post("/session-complete")
async def receive_session_complete(
    session: CaptureSessionComplete,
    current_user: dict = Depends(get_current_user)
):
    """
    Receive complete capture session results from Raspberry Pi
    
    This is called when the door closes and Raspberry Pi has finished processing all frames.
    It includes all detected items with their confidence scores.
    
    Flow:
    1. Store capture session metadata
    2. Classify each detected item (packaged vs fresh)
    3. Store as pending items (waiting for voice input)
    4. Trigger Google Home notification via IFTTT
    5. Return summary
    """
    try:
        from fridge_observer.supabase_client import get_supabase
        from fridge_observer.ws_manager import manager
        import os
        import httpx
        
        sb = get_supabase()
        logger.info(f"Received session complete: {session.session_id} with {len(session.items_added)} items")
        
        # Store capture session
        session_data = {
            "user_id": current_user["sub"],
            "session_id": session.session_id,
            "started_at": session.started_at,
            "ended_at": session.ended_at,
            "duration_seconds": session.duration_seconds,
            "frames_captured": session.frames_captured,
            "items_detected": len(session.items_added) + len(session.items_removed),
            "items_added": len(session.items_added),
            "items_removed": len(session.items_removed),
            "status": "completed"
        }
        
        sb.table("capture_sessions").insert(session_data).execute()
        
        # Process each detected item
        pending_items = []
        
        for item in session.items_added:
            name = item.get("name", "Unknown")
            category = item.get("category", "packaged_goods")
            confidence = item.get("confidence", 0.5)
            
            # Classify item
            is_packaged, expiry_days = _classify_item(name, category)
            
            # Store as pending item
            pending_data = {
                "user_id": current_user["sub"],
                "session_id": session.session_id,
                "item_name": name,
                "category": category,
                "confidence": confidence,
                "is_packaged": is_packaged,
                "estimated_expiry_days": expiry_days,
                "needs_quantity": True,  # Always ask for quantity
                "needs_expiry_date": is_packaged,  # Only ask expiry for packaged items
                "thumbnail": item.get("thumbnail")
            }
            
            result = sb.table("pending_items").insert(pending_data).execute()
            if result.data:
                pending_items.append(result.data[0])
        
        # Broadcast WebSocket update
        await manager.broadcast({
            "type": "pending_items_added",
            "count": len(pending_items),
            "items": pending_items,
            "session_id": session.session_id
        })
        
        # Trigger Google Home notification via IFTTT
        ifttt_key = os.getenv("IFTTT_WEBHOOK_KEY")
        if ifttt_key and len(pending_items) > 0:
            try:
                item_names = ", ".join([item["item_name"] for item in pending_items[:3]])
                if len(pending_items) > 3:
                    item_names += f" and {len(pending_items) - 3} more"
                
                webhook_url = f"https://maker.ifttt.com/trigger/fridge_items_detected/with/key/{ifttt_key}"
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(webhook_url, json={
                        "value1": str(len(pending_items)),
                        "value2": item_names,
                        "value3": datetime.utcnow().isoformat()
                    })
                
                logger.info(f"IFTTT notification sent for {len(pending_items)} items")
            except Exception as e:
                logger.warning(f"Failed to send IFTTT notification: {e}")
        
        return {
            "status": "success",
            "session_id": session.session_id,
            "pending_items_created": len(pending_items),
            "items_removed": len(session.items_removed),
            "low_confidence_items": len(session.low_confidence_items),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    except Exception as e:
        logger.error(f"Error processing session complete: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sensor-status")
async def get_sensor_status():
    """
    Get real-time sensor status for monitoring dashboard.
    This endpoint doesn't require authentication for easy polling.
    """
    import subprocess
    import json
    
    try:
        # Try to read the latest sensor log from Pi
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=2", 
             "pi@192.168.0.1", "tail -50 ~/fridge-observer/sensor.log 2>/dev/null || echo 'no log'"],
            capture_output=True,
            text=True,
            timeout=3
        )
        
        log_lines = result.stdout.strip().split('\n')
        
        # Parse log to extract status
        door_open = False
        capturing = False
        processing = False
        frame_count = 0
        light_level = None
        last_event = None
        items_detected = 0
        
        for line in reversed(log_lines[-20:]):  # Check last 20 lines
            if "Door OPENED" in line:
                door_open = True
                if "darkness:" in line:
                    try:
                        light_level = float(line.split("darkness:")[1].split("ms")[0].strip())
                    except:
                        pass
            elif "Door closed" in line or "Door CLOSED" in line:
                door_open = False
            elif "Frame" in line and "captured" in line:
                capturing = True
                try:
                    frame_count = int(line.split("Frame")[1].split("captured")[0].strip())
                except:
                    pass
            elif "Running" in line and "inference" in line:
                processing = True
                capturing = False
            elif "detected:" in line:
                try:
                    items_detected = int(line.split("detected:")[1].split("added")[0].strip())
                except:
                    pass
        
        return {
            "door_open": door_open,
            "capturing": capturing,
            "processing": processing,
            "frame_count": frame_count,
            "light_level": light_level,
            "items_detected": items_detected,
            "last_event": datetime.utcnow().isoformat() + "Z",
            "ai_model": "Groq Llama 3.2",
            "status": "online"
        }
    
    except Exception as e:
        logger.error(f"Error getting sensor status: {e}")
        return {
            "door_open": False,
            "capturing": False,
            "processing": False,
            "frame_count": 0,
            "light_level": None,
            "items_detected": 0,
            "last_event": None,
            "ai_model": "Unknown",
            "status": "offline"
        }
