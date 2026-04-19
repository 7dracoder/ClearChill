#!/usr/bin/env python3
"""Simple capture and send - no sensor, just camera + AI + send to backend"""
import cv2
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://192.168.0.2:8000")
API_TOKEN = os.getenv("API_TOKEN", "")

print("Capturing from camera...")
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("ERROR: Cannot open camera")
    exit(1)

# Capture 5 frames
frames = []
for i in range(5):
    ret, frame = cap.read()
    if ret:
        frames.append(frame)
        print(f"Frame {i+1} captured")
cap.release()

print(f"\nCaptured {len(frames)} frames")
print("Processing with Groq AI...")

# Use gemini_client to process
from gemini_client import identify_food_multi

# Convert frames to bytes
frame_bytes = []
for frame in frames:
    _, buffer = cv2.imencode('.jpg', frame)
    frame_bytes.append(buffer.tobytes())

result = identify_food_multi(frame_bytes)

print(f"\nDetected {len(result['items_added'])} items:")
for item in result['items_added']:
    print(f"  - {item['name']} ({item['confidence']:.2f})")

# Send to backend
print("\nSending to backend...")
payload = {
    "session_id": f"manual_{int(os.times().elapsed * 1000)}",
    "started_at": "2024-01-01T00:00:00Z",
    "ended_at": "2024-01-01T00:00:05Z",
    "duration_seconds": 5,
    "frames_captured": len(frames),
    "items_added": result['items_added'],
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
    print(resp.json())
except Exception as e:
    print(f"Error: {e}")

print("\nDone! Check your web app inventory.")
