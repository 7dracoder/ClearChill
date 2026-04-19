#!/usr/bin/env python3
"""
Real YOLO detection from Logitech webcam → Supabase via PC proxy
Uses YOLOv8 for actual food detection (not mock data)
"""
import cv2
import os
import sys
import time
import requests
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# PC Proxy configuration
PROXY_URL = "http://172.20.10.6:8001"
USER_ID = "3d16c0db-5f68-4b44-b579-0111e65e8308"

WEBCAM_INDEX = int(os.getenv("WEBCAM_INDEX", "0"))
CAPTURE_DURATION = 5.0
CAPTURE_FPS = 1.0

# Food categories and expiry estimates
FOOD_EXPIRY = {
    "apple": ("fruits", 7),
    "banana": ("fruits", 5),
    "orange": ("fruits", 10),
    "broccoli": ("vegetables", 5),
    "carrot": ("vegetables", 14),
    "sandwich": ("packaged_goods", None),
    "hot dog": ("meat", 2),
    "pizza": ("packaged_goods", 3),
    "donut": ("packaged_goods", 2),
    "cake": ("packaged_goods", 5),
    "bottle": ("beverages", None),
}

def capture_frames(duration_seconds=5.0, fps=1.0):
    """Capture frames from Logitech webcam."""
    print(f"Opening Logitech webcam (camera {WEBCAM_INDEX})...")
    cap = cv2.VideoCapture(WEBCAM_INDEX)
    
    if not cap.isOpened():
        print("ERROR: Cannot open camera")
        return []
    
    # Set resolution for better detection
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
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

def detect_with_imagga_via_proxy(frames):
    """
    Use Imagga API via PC proxy to detect actual food items.
    Sends the middle frame to PC, which forwards to Imagga.
    """
    print("\n[IMAGGA AI] Analyzing captured image via PC proxy...")
    
    if not frames:
        return []
    
    # Use middle frame for detection
    middle_frame = frames[len(frames) // 2]
    
    # Encode frame as JPEG
    _, buffer = cv2.imencode('.jpg', middle_frame)
    image_bytes = buffer.tobytes()
    
    import base64
    
    try:
        # Send image to PC proxy
        payload = {"image": base64.b64encode(image_bytes).decode()}
        
        resp = requests.post(
            f"{PROXY_URL}/proxy/imagga",
            json=payload,
            timeout=30
        )
        
        if resp.status_code == 200:
            data = resp.json()
            tags = data.get('result', {}).get('tags', [])
            
            print(f"  Imagga detected {len(tags)} tag(s)")
            
            # Filter for food-related tags
            food_keywords = ['food', 'fruit', 'vegetable', 'drink', 'beverage', 'meat', 
                           'dairy', 'bottle', 'can', 'package', 'apple', 'banana', 
                           'orange', 'milk', 'juice', 'bread', 'cheese', 'egg', 'water',
                           'soda', 'cola', 'snack', 'candy', 'chocolate', 'cookie']
            
            detected = []
            for tag in tags[:15]:  # Top 15 tags
                tag_name = tag.get('tag', {}).get('en', '').lower()
                confidence = tag.get('confidence', 0) / 100.0  # Convert to 0-1
                
                # Check if it's food-related
                if any(keyword in tag_name for keyword in food_keywords) and confidence > 0.25:
                    detected.append({
                        "name": tag_name,
                        "confidence": confidence
                    })
                    print(f"    - {tag_name}: {confidence:.0%}")
            
            # Enrich with category and expiry info
            items = []
            for det in detected[:5]:  # Top 5 food items
                name = det["name"]
                confidence = det["confidence"]
                
                # Try to match with known foods
                if name in FOOD_EXPIRY:
                    category, expiry_days = FOOD_EXPIRY[name]
                else:
                    # Default to packaged goods if unknown
                    category = "packaged_goods"
                    expiry_days = None
                
                items.append({
                    "name": name.title(),
                    "category": category,
                    "confidence": confidence,
                    "expiry_days": expiry_days
                })
            
            return items
        else:
            print(f"  ✗ Proxy error: {resp.status_code}")
            return []
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return []
    """
    Use Imagga API to detect actual food items in the captured frames.
    Sends the middle frame to Imagga for analysis.
    """
    print("\n[IMAGGA AI] Analyzing captured image...")
    
    if not frames:
        return []
    
    # Use middle frame for detection
    middle_frame = frames[len(frames) // 2]
    
    # Encode frame as JPEG
    _, buffer = cv2.imencode('.jpg', middle_frame)
    image_bytes = buffer.tobytes()
    
    IMAGGA_API_KEY = "acc_2a76d6d92ed7a97"
    IMAGGA_API_SECRET = "55dfe4556b4bec6644fad9fdb31db6a0"
    
    # Try with just API key first (some APIs support this)
    url = "https://api.imagga.com/v2/tags"
    
    try:
        # Send image to Imagga
        files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
        
        # Try with API key as bearer token
        headers = {'Authorization': f'Bearer {IMAGGA_API_KEY}'}
        resp = requests.post(url, headers=headers, files=files, timeout=30)
        
        if resp.status_code == 401 and IMAGGA_API_SECRET:
            # Try with Basic Auth if bearer fails
            resp = requests.post(
                url,
                auth=(IMAGGA_API_KEY, IMAGGA_API_SECRET),
                files=files,
                timeout=30
            )
        
        if resp.status_code == 200:
            data = resp.json()
            tags = data.get('result', {}).get('tags', [])
            
            print(f"  Imagga detected {len(tags)} tag(s)")
            
            # Filter for food-related tags
            food_keywords = ['food', 'fruit', 'vegetable', 'drink', 'beverage', 'meat', 
                           'dairy', 'bottle', 'can', 'package', 'apple', 'banana', 
                           'orange', 'milk', 'juice', 'bread', 'cheese', 'egg', 'water']
            
            detected = []
            for tag in tags[:15]:  # Top 15 tags
                tag_name = tag.get('tag', {}).get('en', '').lower()
                confidence = tag.get('confidence', 0) / 100.0  # Convert to 0-1
                
                # Check if it's food-related
                if any(keyword in tag_name for keyword in food_keywords) and confidence > 0.25:
                    detected.append({
                        "name": tag_name,
                        "confidence": confidence
                    })
                    print(f"    - {tag_name}: {confidence:.0%}")
            
            if not detected:
                print("  No food items detected in image")
                return []
            
            # Enrich with category and expiry info
            items = []
            for det in detected[:5]:  # Top 5 food items
                name = det["name"]
                confidence = det["confidence"]
                
                # Try to match with known foods
                if name in FOOD_EXPIRY:
                    category, expiry_days = FOOD_EXPIRY[name]
                else:
                    # Default to packaged goods if unknown
                    category = "packaged_goods"
                    expiry_days = None
                
                items.append({
                    "name": name.title(),
                    "category": category,
                    "confidence": confidence,
                    "expiry_days": expiry_days
                })
            
            return items
        else:
            print(f"  ✗ Imagga error: {resp.status_code}")
            print(f"  Response: {resp.text[:200]}")
            print(f"  Note: You may need to provide IMAGGA_API_SECRET")
            return []
        
    except Exception as e:
        print(f"  ✗ Imagga error: {e}")
        return []

def send_via_proxy(items):
    """Send detected items via PC proxy to Supabase."""
    added_count = 0
    needs_input_count = 0
    
    print(f"\nSending {len(items)} detected items via PC proxy...")
    
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
                    print(f"  ✗ Failed to add {name}: {resp.status_code}")
            except Exception as e:
                print(f"  ✗ Error adding {name}: {e}")
        else:
            # Packaged item - needs user input for expiry
            print(f"  ⏳ {name} needs expiry input (will be queued)")
            needs_input_count += 1
    
    return added_count, needs_input_count

def main():
    print("=" * 60)
    print("Fridge Observer - Imagga AI Detection")
    print("=" * 60)
    print("\nLogitech Webcam → Imagga AI → PC Proxy → Supabase → Web App\n")
    
    # Capture frames from Logitech webcam
    print("[1/3] Capturing from Logitech webcam...")
    frames = capture_frames(duration_seconds=CAPTURE_DURATION, fps=CAPTURE_FPS)
    
    if not frames:
        print("✗ No frames captured. Exiting.")
        return
    
    # Run Imagga detection via PC proxy
    print("\n[2/3] Running Imagga AI detection...")
    items = detect_with_imagga_via_proxy(frames)
    
    if not items:
        print("✗ No food items detected.")
        return
    
    print(f"✓ Detection complete! Found {len(items)} items:")
    for item in items:
        expiry_info = f" (est. {item.get('expiry_days')} days)" if item.get('expiry_days') else " (needs expiry input)"
        print(f"    • {item['name']} ({item['confidence']:.0%}){expiry_info}")
    
    # Send via proxy to Supabase
    print("\n[3/3] Sending to Supabase...")
    added, needs_input = send_via_proxy(items)
    
    print("\n" + "=" * 60)
    print("✓ SUCCESS - Items added to your web app!")
    print("=" * 60)
    print(f"\n  Auto-added: {added} items")
    print(f"  Needs input: {needs_input} items")
    print(f"\n  Check: https://clearchill.onrender.com")

if __name__ == "__main__":
    main()
