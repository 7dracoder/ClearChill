"""
Google Home voice integration endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
import logging
import os
import httpx

from fridge_observer.auth import get_current_user
from fridge_observer.supabase_client import get_supabase
from fridge_observer.ws_manager import manager

router = APIRouter(prefix="/api/voice", tags=["voice"])
logger = logging.getLogger(__name__)

IFTTT_WEBHOOK_KEY = os.getenv("IFTTT_WEBHOOK_KEY", "")


# ── Models ────────────────────────────────────────────────────────────────

class PendingItem(BaseModel):
    id: int
    item_name: str
    category: str
    confidence: float
    is_packaged: bool
    estimated_expiry_days: Optional[int]
    needs_quantity: bool
    needs_expiry_date: bool
    thumbnail: Optional[str]
    created_at: str


class ConfirmItemRequest(BaseModel):
    pending_item_id: int
    quantity: int
    expiry_date: Optional[str] = None  # ISO format: "2026-04-25"


class GoogleActionsRequest(BaseModel):
    """Google Actions webhook request format"""
    handler: Dict[str, Any]
    intent: Dict[str, Any]
    scene: Dict[str, Any]
    session: Dict[str, Any]
    user: Dict[str, Any]
    home: Dict[str, Any]
    device: Dict[str, Any]


# ── IFTTT Notification ───────────────────────────────────────────────────

async def trigger_ifttt_notification(event: str, values: Dict[str, Any]):
    """
    Trigger IFTTT webhook to make Google Home speak
    
    Args:
        event: IFTTT event name (e.g., "fridge_items_detected")
        values: Dictionary with value1, value2, value3
    """
    if not IFTTT_WEBHOOK_KEY:
        logger.warning("IFTTT_WEBHOOK_KEY not configured - skipping notification")
        return
    
    url = f"https://maker.ifttt.com/trigger/{event}/with/key/{IFTTT_WEBHOOK_KEY}"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=values)
            
            if response.status_code == 200:
                logger.info(f"IFTTT notification sent: {event}")
            else:
                logger.warning(f"IFTTT notification failed: {response.status_code} - {response.text}")
    
    except Exception as e:
        logger.error(f"Failed to send IFTTT notification: {e}")


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.get("/pending-items")
async def get_pending_items(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get all pending items for the current user
    Called by Google Home to fetch items waiting for voice input
    """
    try:
        sb = get_supabase()
        
        # Get pending items that haven't expired
        result = sb.table("pending_items").select("*").eq(
            "user_id", current_user["sub"]
        ).gt(
            "expires_at", datetime.utcnow().isoformat()
        ).order(
            "created_at", desc=False
        ).execute()
        
        items = result.data if result.data else []
        
        # Log voice interaction
        sb.table("voice_interactions").insert({
            "user_id": current_user["sub"],
            "intent": "get_pending_items",
            "query": "What are the pending items?",
            "response": f"Found {len(items)} pending items",
            "success": True
        }).execute()
        
        return {
            "items": items,
            "count": len(items),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    except Exception as e:
        logger.error(f"Error fetching pending items: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/confirm-item")
async def confirm_item(
    request: ConfirmItemRequest,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Confirm a pending item with quantity and optional expiry date
    Called by Google Home after user provides voice input
    """
    try:
        sb = get_supabase()
        
        # Get pending item details
        pending_result = sb.table("pending_items").select("*").eq(
            "id", request.pending_item_id
        ).eq(
            "user_id", current_user["sub"]
        ).single().execute()
        
        if not pending_result.data:
            raise HTTPException(status_code=404, detail="Pending item not found")
        
        pending_item = pending_result.data
        
        # Parse expiry date if provided
        expiry_date = None
        if request.expiry_date:
            try:
                expiry_date = datetime.fromisoformat(request.expiry_date).date()
            except ValueError:
                # Try parsing common date formats
                from dateutil import parser
                expiry_date = parser.parse(request.expiry_date).date()
        
        # If no expiry provided but item is not packaged, estimate it
        if not expiry_date and not pending_item["is_packaged"]:
            if pending_item["estimated_expiry_days"]:
                expiry_date = (datetime.utcnow() + timedelta(days=pending_item["estimated_expiry_days"])).date()
        
        # Add to inventory using the database function
        result = sb.rpc("confirm_pending_item", {
            "p_pending_item_id": request.pending_item_id,
            "p_quantity": request.quantity,
            "p_expiry_date": expiry_date.isoformat() if expiry_date else None
        }).execute()
        
        new_item_id = result.data if result.data else None
        
        # Get the newly added item
        item_result = sb.table("food_items").select("*").eq(
            "id", new_item_id
        ).single().execute()
        
        new_item = item_result.data if item_result.data else {}
        
        # Broadcast WebSocket update
        await manager.broadcast({
            "type": "inventory_updated",
            "action": "item_added",
            "item": new_item,
            "source": "voice"
        })
        
        # Send IFTTT confirmation
        await trigger_ifttt_notification("item_added_to_fridge", {
            "value1": pending_item["item_name"],
            "value2": str(request.quantity),
            "value3": expiry_date.isoformat() if expiry_date else "No expiry"
        })
        
        # Log voice interaction
        sb.table("voice_interactions").insert({
            "user_id": current_user["sub"],
            "intent": "confirm_item",
            "query": f"Add {request.quantity} {pending_item['item_name']}",
            "response": f"Item added to inventory (ID: {new_item_id})",
            "success": True
        }).execute()
        
        logger.info(f"Item confirmed via voice: {pending_item['item_name']} x{request.quantity}")
        
        return {
            "status": "success",
            "item_id": new_item_id,
            "item_name": pending_item["item_name"],
            "quantity": request.quantity,
            "expiry_date": expiry_date.isoformat() if expiry_date else None,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming item: {e}")
        
        # Log failed interaction
        try:
            sb = get_supabase()
            sb.table("voice_interactions").insert({
                "user_id": current_user["sub"],
                "intent": "confirm_item",
                "query": f"Add item {request.pending_item_id}",
                "response": None,
                "success": False,
                "error_message": str(e)
            }).execute()
        except:
            pass
        
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/pending-items/{item_id}")
async def delete_pending_item(
    item_id: int,
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Delete a pending item (user declined or item was misidentified)
    """
    try:
        sb = get_supabase()
        
        # Delete the pending item
        sb.table("pending_items").delete().eq(
            "id", item_id
        ).eq(
            "user_id", current_user["sub"]
        ).execute()
        
        # Broadcast WebSocket update
        await manager.broadcast({
            "type": "pending_item_removed",
            "item_id": item_id
        })
        
        logger.info(f"Pending item deleted: {item_id}")
        
        return {
            "status": "deleted",
            "item_id": item_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    except Exception as e:
        logger.error(f"Error deleting pending item: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def google_actions_webhook(request: Request):
    """
    Google Actions webhook endpoint
    Handles all intents from Google Assistant
    
    This endpoint receives requests from Google Actions when user talks to Google Home
    """
    try:
        body = await request.json()
        logger.info(f"Google Actions webhook received: {body}")
        
        # Extract intent information
        intent_name = body.get("intent", {}).get("name", "")
        parameters = body.get("intent", {}).get("params", {})
        session_id = body.get("session", {}).get("id", "")
        
        # Get user info (you'll need to map Google user ID to your user)
        # For now, we'll use a default user or require authentication
        
        response = {
            "session": {
                "id": session_id,
                "params": {}
            },
            "prompt": {
                "override": False,
                "firstSimple": {
                    "speech": "",
                    "text": ""
                }
            }
        }
        
        # Handle different intents
        if intent_name == "get_pending_items":
            # User asked: "What are the pending items?"
            # TODO: Get user from session, for now return generic response
            response["prompt"]["firstSimple"]["speech"] = "You have 3 pending items: Milk, Eggs, and Chicken. Let's add them. How many Milk?"
            response["prompt"]["firstSimple"]["text"] = "You have 3 pending items. How many Milk?"
        
        elif intent_name == "confirm_item_quantity":
            # User answered: "2 bottles"
            quantity = parameters.get("quantity", 1)
            response["prompt"]["firstSimple"]["speech"] = f"Got it, {quantity}. What's the expiry date for Milk?"
            response["prompt"]["firstSimple"]["text"] = f"Expiry date for Milk?"
        
        elif intent_name == "confirm_item_expiry":
            # User answered: "April 25th"
            date_str = parameters.get("date", "")
            response["prompt"]["firstSimple"]["speech"] = f"Milk added. How many Eggs?"
            response["prompt"]["firstSimple"]["text"] = "How many Eggs?"
        
        else:
            response["prompt"]["firstSimple"]["speech"] = "I didn't understand that. Please try again."
            response["prompt"]["firstSimple"]["text"] = "Please try again."
        
        return response
    
    except Exception as e:
        logger.error(f"Error in Google Actions webhook: {e}")
        return {
            "prompt": {
                "firstSimple": {
                    "speech": "Sorry, I encountered an error. Please try again later.",
                    "text": "Error occurred"
                }
            }
        }


@router.get("/stats")
async def get_voice_stats(
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    Get voice interaction statistics for the current user
    """
    try:
        sb = get_supabase()
        
        # Get total interactions
        total_result = sb.table("voice_interactions").select(
            "id", count="exact"
        ).eq(
            "user_id", current_user["sub"]
        ).execute()
        
        total_interactions = total_result.count if total_result.count else 0
        
        # Get successful interactions
        success_result = sb.table("voice_interactions").select(
            "id", count="exact"
        ).eq(
            "user_id", current_user["sub"]
        ).eq(
            "success", True
        ).execute()
        
        successful_interactions = success_result.count if success_result.count else 0
        
        # Get pending items count
        pending_result = sb.table("pending_items").select(
            "id", count="exact"
        ).eq(
            "user_id", current_user["sub"]
        ).gt(
            "expires_at", datetime.utcnow().isoformat()
        ).execute()
        
        pending_count = pending_result.count if pending_result.count else 0
        
        return {
            "total_interactions": total_interactions,
            "successful_interactions": successful_interactions,
            "success_rate": (successful_interactions / total_interactions * 100) if total_interactions > 0 else 0,
            "pending_items": pending_count,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    
    except Exception as e:
        logger.error(f"Error fetching voice stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
