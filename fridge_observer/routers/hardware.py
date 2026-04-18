"""
Hardware integration endpoints for Raspberry Pi sensor
"""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List, Tuple
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


class ExpiryDateInput(BaseModel):
    item_name: str
    expiry_date: str  # ISO format: "2026-04-25"
    quantity: Optional[int] = 1


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
        
        # Separate items that need user input vs auto-add
        needs_expiry = [item for item in detected_items if item["needs_expiry_input"]]
        auto_add = [item for item in detected_items if not item["needs_expiry_input"]]
        
        # Auto-add items with estimated expiry to inventory
        from fridge_observer.supabase_client import get_supabase
        from fridge_observer.ws_manager import manager
        
        sb = get_supabase()
        added_items = []
        
        for item in auto_add:
            expiry_date = datetime.utcnow() + timedelta(days=item["estimated_expiry_days"])
            
            # Insert into Supabase inventory
            result = sb.table("food_items").insert({
                "name": item["name"],
                "category": item["category"],
                "quantity": 1,
                "expiry_date": expiry_date.date().isoformat(),
                "user_id": current_user["sub"],
                "added_via": "hardware_auto"
            }).execute()
            
            added_items.append({
                "name": item["name"],
                "category": item["category"],
                "expiry_date": expiry_date.date().isoformat(),
                "estimated_days": item["estimated_expiry_days"]
            })
            
            logger.info(f"Auto-added {item['name']} with expiry {expiry_date.date()}")
        
        # Send WebSocket notification for real-time UI update
        if added_items:
            await manager.broadcast({
                "type": "inventory_updated",
                "action": "items_added",
                "items": added_items,
                "source": "hardware_auto"
            })
        
        logger.info(f"Detected {len(detected_items)} items: {len(needs_expiry)} need expiry input, {len(auto_add)} auto-added")
        
        return {
            "status": "processed",
            "total_items": len(detected_items),
            "needs_expiry_input": needs_expiry,  # Google Home will ask for these
            "auto_added": added_items,  # Already added to inventory
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
