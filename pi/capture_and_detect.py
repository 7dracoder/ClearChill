#!/usr/bin/env python3
"""
Capture fridge contents and detect food items using YOLO.
This version captures on demand (no GPIO sensor) for testing.
"""
import cv2
import os
import sys
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

# Import from same directory
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Import YOLO client
import importlib.util
spec = importlib.util.spec_from_file_location("yolo_client", os.path.join(script_dir, "yolo_client.py"))
yolo_client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(yolo_client)
identify_food_multi = yolo_client.identify_food_multi

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://192.168.0.2:8000")
API_TOKEN = os.getenv("API_TOKEN", "")
WEBCAM_INDEX = int(os.getenv("WEBCAM_INDEX", "0"))
CAPTURE_FPS = float(os.getenv("CAPTURE_FPS", "1.0"))
CAPTURE_DURATION = float(os.getenv("CAPTURE_DURATION", "5.0"))

def capture_frames(duration_seconds=5.0, fps=1.0):
    """Capture frames from webcam for specified duration."""
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
            print("Failed to capture frame")
            continue
        
        current_time = time.time() - start_time
        if current_time - last_capture >= frame_interval:
            # Encode frame as JPEG
            _, buffer = cv2.imencode('.jpg', frame)
            frames.append(buffer.tobytes())
            last_capture = current_time
            print(f"  Frame {len(frames)} captured at {current_time:.1f}s")
    
    cap.release()
    print(f"✓ Captured {len(frames)} frames")
    return frames

def send_to_backend(session_id, started_at, ended_at, duration, frames_captured, detection_result):
    """Send detection results to backend."""
    payload = {
        "session_id": session_id,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_seconds": duration,
        "frames_captured": frames_captured,
        "items_added": detection_result.get("items_added", []),
        "items_removed": detection_result.get("items_removed", []),
        "low_confidence_items": []
    }
    
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    print(f"\nSending results to {API_BASE_URL}/api/hardware/session-complete...")
    try:
        resp = requests.post(
            f"{API_BASE_URL}/api/hardware/session-complete",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if resp.status_code == 200:
            print("✓ Backend received data!")
            result = resp.json()
            print(f"  Auto-added: {len(result.get('auto_added', []))}")
            print(f"  Needs expiry input: {len(result.get('needs_expiry_input', []))}")
            print(f"  Removed: {len(result.get('removed', []))}")
            return result
        else:
            print(f"✗ Backend error {resp.status_code}: {resp.text}")
            return None
    except Exception as e:
        print(f"✗ Connection error: {e}")
        return None

def main():
    print("=" * 60)
    print("Fridge Observer - Capture & Detect")
    print("=" * 60)
    
    # Generate session ID
    session_id = f"manual_{int(time.time())}"
    started_at = datetime.utcnow().isoformat() + "Z"
    
    # Capture frames
    print("\n[1/3] Capturing frames...")
    frames = capture_frames(duration_seconds=CAPTURE_DURATION, fps=CAPTURE_FPS)
    
    if not frames:
        print("✗ No frames captured. Exiting.")
        return
    
    ended_at = datetime.utcnow().isoformat() + "Z"
    duration = len(frames) / CAPTURE_FPS
    
    # Run AI detection
    print("\n[2/3] Running YOLO detection...")
    print(f"  Processing {len(frames)} frames...")
    
    try:
        detection_result = identify_food_multi(frames)
        
        items_added = detection_result.get("items_added", [])
        items_removed = detection_result.get("items_removed", [])
        all_items = detection_result.get("all_items", [])
        
        print(f"✓ Detection complete!")
        print(f"  Items added: {len(items_added)}")
        print(f"  Items removed: {len(items_removed)}")
        print(f"  Total detected: {len(all_items)}")
        
        if items_added:
            print("\n  Items added to fridge:")
            for item in items_added:
                expiry_info = ""
                if item.get("expiry_source") == "label":
                    expiry_info = f" (expiry: {item.get('expiry_date')})"
                elif item.get("expiry_source") == "estimated":
                    expiry_info = f" (est. {item.get('estimated_expiry_days')} days)"
                else:
                    expiry_info = " (needs expiry input)"
                print(f"    • {item['name']} ({item['confidence']:.0%}){expiry_info}")
        
        if items_removed:
            print("\n  Items removed from fridge:")
            for item in items_removed:
                print(f"    • {item['name']} ({item['confidence']:.0%})")
        
    except Exception as e:
        print(f"✗ AI detection failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Send to backend
    print("\n[3/3] Sending to backend...")
    result = send_to_backend(
        session_id=session_id,
        started_at=started_at,
        ended_at=ended_at,
        duration=int(duration),
        frames_captured=len(frames),
        detection_result=detection_result
    )
    
    if result:
        print("\n" + "=" * 60)
        print("✓ SUCCESS - Items are now in your web app!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("✗ FAILED - Check backend connection")
        print("=" * 60)

if __name__ == "__main__":
    main()
