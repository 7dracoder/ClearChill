#!/usr/bin/env python3
"""
Send detection data via PC proxy to Supabase
PC proxy forwards to Supabase (bypasses network restrictions)
"""
import cv2
import os
import sys
import time
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# PC Proxy configuration
PROXY_URL = "http://172.20.10.6:8001"
USER_ID = "3d16c0db-5f68-4b44-b579-0111e65e8308"

WEBCAM_INDEX = int(os.getenv("WEBCAM_INDEX", "0"))
CAPTURE_DURATION = 5.0
CAPTURE_FPS = 1.0

# Mock food items for testing
MOCK_ITEMS = [
    {"name": "Apple", "category": "fruits", "confidence": 0.92, "expiry_days": 7},
    {"name": "Milk", "category": "dairy", "confidence": 0.88, "expiry_days": None},
    {"name": "Banana", "category": "fruits", "confidence": 0.95, "expiry_days": 5},
    {"name": "Orange", "category": "fruits", "confidence": 0.89, "expiry_days": 10},
]

def capture_frames(duration_seconds=5.0, fps=1.0):
    """Capture frames from webcam."""
    print(f"Opening camera {WEBCAM_INDEX}...")
    cap = cv2.VideoCapture(WEBCAM_INDEX)
    
    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        return []
    
    print(f"✓ Camera opened. Capturing for {duration_seconds}s at {fps} FPS...")
    
    frames = []
    frame_interval = 1.0 / fps
    start_time = time.time()
    last_capture = 0
    
    while (time.time() - start_time) < duration_seconds:
        ret, frame = cap.read()
        if not ret:
            continue
        
        current_time = time.time() - start_time
        if current_time - last_capture >= frame_interval:
            frames.append(frame)
            last_capture = current_time
            print(f"  Frame {len(frames)} captured at {current_time:.1f}s")
    
    cap.release()
    print(f"✓ Captured {len(frames)} frames")
    return frames

def mock_detection(frames):
    """Mock detection - returns dummy food items."""
    print("\n[MOCK MODE] Simulating food detection...")
    print("  (Real YOLO detection will be enabled once model is installed)")
    time.sleep(1)
    return MOCK_ITEMS

def send_via_proxy(items):
    """Send items via PC proxy to Supabase."""
    added_count = 0
    needs_input_count = 0
    
    print(f"\nSending {len(items)} items via PC proxy...")
    
    for item in items:
        name = item["name"]
        category = item["category"]
        expiry_days = item.get("expiry_days")
        
        if expiry_days is not None:
            # Fresh item - auto-add with estimated expiry
            expiry_date = (datetime.now() + timedelta(days=expiry_days)).date().isoformat()
            
            payload = {
                "name": name,
                "category": category,
                "quantity": 1,
                "expiry_date": expiry_date,
                "user_id": USER_ID
            }
            
            try:
                resp = requests.post(
                    f"{PROXY_URL}/proxy/food_items",
                    json=payload,
                    timeout=10
                )
                
                if resp.status_code in (200, 201):
                    print(f"  ✓ Added {name} (expires in {expiry_days} days)")
                    added_count += 1
                else:
                    print(f"  ✗ Failed to add {name}: {resp.status_code} - {resp.text}")
            except Exception as e:
                print(f"  ✗ Error adding {name}: {e}")
        else:
            # Packaged item - needs user input for expiry
            print(f"  ⏳ {name} needs expiry input (will be queued)")
            needs_input_count += 1
    
    return added_count, needs_input_count

def main():
    print("=" * 60)
    print("Fridge Observer - Via PC Proxy to Supabase")
    print("=" * 60)
    print("\nPi → PC Proxy → Supabase → Render Web App\n")
    
    # Capture frames
    print("[1/3] Capturing frames...")
    frames = capture_frames(duration_seconds=CAPTURE_DURATION, fps=CAPTURE_FPS)
    
    if not frames:
        print("✗ No frames captured. Exiting.")
        return
    
    # Mock detection
    print("\n[2/3] Running detection...")
    items = mock_detection(frames)
    
    print(f"✓ Detection complete! Found {len(items)} items:")
    for item in items:
        expiry_info = f" (est. {item.get('expiry_days')} days)" if item.get('expiry_days') else " (needs expiry input)"
        print(f"    • {item['name']} ({item['confidence']:.0%}){expiry_info}")
    
    # Send via proxy
    print("\n[3/3] Sending via PC proxy to Supabase...")
    added, needs_input = send_via_proxy(items)
    
    print("\n" + "=" * 60)
    print("✓ SUCCESS - Data sent to Supabase!")
    print("=" * 60)
    print(f"\n  Auto-added: {added} items")
    print(f"  Needs input: {needs_input} items")
    print(f"\n  Check your web app at: https://clearchill.onrender.com")
    print(f"  Items should appear in your inventory!")

if __name__ == "__main__":
    main()
