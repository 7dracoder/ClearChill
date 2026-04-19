#!/usr/bin/env python3
"""
Simple food detection script - MOCK VERSION for testing pipeline
Uses dummy detections until YOLO model is properly installed
"""
import cv2
import os
import sys
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "https://clearchill.onrender.com")
API_TOKEN = os.getenv("API_TOKEN", "")
WEBCAM_INDEX = int(os.getenv("WEBCAM_INDEX", "0"))
CAPTURE_DURATION = 5.0
CAPTURE_FPS = 1.0

# Mock food items for testing
MOCK_ITEMS = [
    {"name": "Apple", "category": "fruits", "confidence": 0.92, "expiry_source": "estimated", "estimated_expiry_days": 7, "needs_expiry_input": False},
    {"name": "Milk", "category": "dairy", "confidence": 0.88, "expiry_source": "unknown", "estimated_expiry_days": None, "needs_expiry_input": True},
    {"name": "Banana", "category": "fruits", "confidence": 0.95, "expiry_source": "estimated", "estimated_expiry_days": 5, "needs_expiry_input": False},
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
    time.sleep(1)  # Simulate processing time
    
    return {
        "items_added": MOCK_ITEMS,
        "items_removed": [],
        "all_items": MOCK_ITEMS
    }

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
    print("Fridge Observer - Simple Detection (MOCK MODE)")
    print("=" * 60)
    print("\nNOTE: Using mock detection for testing.")
    print("Install YOLO model for real food detection.\n")
    
    session_id = f"mock_{int(time.time())}"
    started_at = datetime.utcnow().isoformat() + "Z"
    
    # Capture frames
    print("[1/3] Capturing frames...")
    frames = capture_frames(duration_seconds=CAPTURE_DURATION, fps=CAPTURE_FPS)
    
    if not frames:
        print("✗ No frames captured. Exiting.")
        return
    
    ended_at = datetime.utcnow().isoformat() + "Z"
    duration = len(frames) / CAPTURE_FPS
    
    # Mock detection
    print("\n[2/3] Running detection...")
    detection_result = mock_detection(frames)
    
    items_added = detection_result.get("items_added", [])
    print(f"✓ Detection complete! Found {len(items_added)} items:")
    for item in items_added:
        expiry_info = ""
        if item.get("expiry_source") == "estimated":
            expiry_info = f" (est. {item.get('estimated_expiry_days')} days)"
        else:
            expiry_info = " (needs expiry input)"
        print(f"    • {item['name']} ({item['confidence']:.0%}){expiry_info}")
    
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
        print("\nCheck your web app to see the detected items.")
        print("Items needing expiry input will be queued for user input.")
    else:
        print("\n" + "=" * 60)
        print("✗ FAILED - Check backend connection")
        print("=" * 60)

if __name__ == "__main__":
    main()
