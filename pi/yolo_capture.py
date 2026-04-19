#!/usr/bin/env python3
"""Capture with camera, detect with YOLO, send to backend"""
import cv2
import requests
import os
from ultralytics import YOLO
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://192.168.0.2:8000")

print("Loading YOLO model...")
model = YOLO('yolov8n.pt')

print("Capturing from camera...")
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("ERROR: Cannot open camera")
    exit(1)

ret, frame = cap.read()
cap.release()

if not ret:
    print("ERROR: Failed to capture frame")
    exit(1)

print("Running YOLO detection...")
results = model(frame, verbose=False)

# Extract detected objects
items_added = []
for r in results:
    for box in r.boxes:
        cls = int(box.cls[0])
        conf = float(box.conf[0])
        name = model.names[cls]
        
        # Filter for food-related items (confidence > 0.5)
        if conf > 0.5:
            items_added.append({
                "name": name.title(),
                "confidence": round(conf, 2),
                "category": "packaged_goods",
                "needs_expiry_input": True,
                "expiry_source": "unknown",
                "expiry_date": None,
                "estimated_expiry_days": None
            })

print(f"\nDetected {len(items_added)} items:")
for item in items_added:
    print(f"  - {item['name']} ({item['confidence']})")

if len(items_added) == 0:
    print("\nNo items detected. Try pointing camera at objects.")
    exit(0)

# Send to backend
print("\nSending to backend...")
payload = {
    "session_id": f"yolo_{int(os.times().elapsed * 1000)}",
    "started_at": "2024-01-01T00:00:00Z",
    "ended_at": "2024-01-01T00:00:05Z",
    "duration_seconds": 1,
    "frames_captured": 1,
    "items_added": items_added,
    "items_removed": [],
    "low_confidence_items": []
}

try:
    resp = requests.post(
        f"{API_BASE_URL}/api/hardware/session-complete",
        json=payload,
        timeout=10
    )
    print(f"Response: {resp.status_code}")
    if resp.status_code == 200:
        print("✓ Items sent to web app!")
        print(resp.json())
    else:
        print(f"Error: {resp.text}")
except Exception as e:
    print(f"Error: {e}")

print("\nDone! Check your web app inventory.")
