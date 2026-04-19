#!/usr/bin/env python3
"""Quick test - capture and send dummy data to verify the pipeline works"""
import cv2
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://192.168.0.2:8000")
API_TOKEN = os.getenv("API_TOKEN", "")

print("Testing camera...")
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("ERROR: Cannot open camera")
    exit(1)

ret, frame = cap.read()
cap.release()

if ret:
    print(f"✓ Camera works! Captured {frame.shape}")
else:
    print("✗ Failed to capture")
    exit(1)

# Send test data
print("\nSending test detection to backend...")
print(f"Using API: {API_BASE_URL}")
print(f"Token: {API_TOKEN[:50]}..." if API_TOKEN else "No token!")

payload = {
    "session_id": "test_123",
    "started_at": "2024-01-01T00:00:00Z",
    "ended_at": "2024-01-01T00:00:05Z",
    "duration_seconds": 5,
    "frames_captured": 1,
    "items_added": [
        {
            "name": "Test Item",
            "confidence": 0.95,
            "category": "packaged_goods",
            "needs_expiry_input": True,
            "expiry_source": "unknown",
            "expiry_date": None
        }
    ],
    "items_removed": [],
    "low_confidence_items": []
}

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

try:
    resp = requests.post(
        f"{API_BASE_URL}/api/hardware/session-complete",
        json=payload,
        headers=headers,
        timeout=10
    )
    print(f"Response: {resp.status_code}")
    if resp.status_code == 200:
        print("✓ Backend received data!")
        print(resp.json())
    else:
        print(f"✗ Error: {resp.text}")
except Exception as e:
    print(f"✗ Connection error: {e}")

print("\nTest complete!")
