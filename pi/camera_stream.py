#!/usr/bin/env python3
"""
USB Camera Stream Server — runs on the Raspberry Pi.

Endpoints:
  GET  /stream   — MJPEG live stream
  GET  /frame    — single JPEG snapshot
  POST /capture  — capture + run Gemini inference locally + POST results to server
  GET  /status   — camera / config status
"""

import os
import sys
import cv2
import httpx
from fastapi import FastAPI, Response
from fastapi.responses import StreamingResponse
import uvicorn
from datetime import datetime
import logging
from dotenv import load_dotenv

# gemini_client.py lives in the same directory
sys.path.insert(0, os.path.dirname(__file__))
from gemini_client import identify_food

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Pi Camera Stream Server")

camera = None

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_TOKEN    = os.getenv("API_TOKEN",    "")


def get_camera():
    global camera
    if camera is None or not camera.isOpened():
        idx = int(os.getenv("WEBCAM_INDEX", "0"))
        camera = cv2.VideoCapture(idx)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        camera.set(cv2.CAP_PROP_FPS, 30)
        logger.info("Camera initialised (index %d)", idx)
    return camera


def generate_frames():
    cam = get_camera()
    while True:
        success, frame = cam.read()
        if not success:
            logger.error("Failed to read frame")
            break
        ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ret:
            continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
               + buf.tobytes() + b"\r\n")


@app.get("/")
async def root():
    return {
        "service": "Pi Camera Stream Server",
        "endpoints": {
            "/stream":  "MJPEG video stream",
            "/frame":   "Single JPEG snapshot",
            "/capture": "Capture + on-device Gemini inference + submit to server",
            "/status":  "Camera / config status",
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/stream")
async def video_stream():
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/frame")
async def get_frame():
    cam = get_camera()
    success, frame = cam.read()
    if not success:
        return Response(content="Failed to capture frame", status_code=500)
    ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ret:
        return Response(content="Failed to encode frame", status_code=500)
    return Response(content=buf.tobytes(), media_type="image/jpeg")


@app.post("/capture")
async def capture_and_infer():
    """
    Grab one frame, run Gemini vision locally on the Pi,
    then POST the structured item list to the server.
    The raw image is never sent over the network.
    """
    if not API_TOKEN:
        return Response(
            content='{"error": "API_TOKEN not configured"}',
            status_code=500, media_type="application/json",
        )

    cam = get_camera()
    success, frame = cam.read()
    if not success:
        return Response(
            content='{"error": "Failed to capture frame"}',
            status_code=500, media_type="application/json",
        )

    ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ret:
        return Response(
            content='{"error": "Failed to encode frame"}',
            status_code=500, media_type="application/json",
        )

    image_bytes = buf.tobytes()
    logger.info("Frame captured (%d bytes) — running Gemini inference…", len(image_bytes))

    # Run inference on the Pi — synchronous call is fine here
    import asyncio
    result = await asyncio.get_event_loop().run_in_executor(
        None, identify_food, image_bytes
    )

    items_added = result  # single-frame: everything detected is treated as added

    if not items_added:
        return {"status": "no_items_detected", "items_added": [], "items_removed": []}

    logger.info("Detected %d item(s) — submitting to server…", len(items_added))

    session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}_stream"
    payload = {
        "session_id": session_id,
        "started_at": datetime.utcnow().isoformat() + "Z",
        "ended_at":   datetime.utcnow().isoformat() + "Z",
        "duration_seconds": 0,
        "frames_captured": 1,
        "items_added": items_added,
        "items_removed": [],
        "low_confidence_items": [],
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{API_BASE_URL}/api/hardware/session-complete",
                json=payload,
                headers={"Authorization": f"Bearer {API_TOKEN}"},
            )

        if resp.is_success:
            result = resp.json()
            logger.info(
                "Submit OK — %d pending item(s) created",
                result.get("pending_items_created", 0),
            )
            return result
        else:
            logger.error("Submit failed: %s %s", resp.status_code, resp.text[:200])
            return Response(
                content=resp.text,
                status_code=resp.status_code,
                media_type="application/json",
            )

    except httpx.TimeoutException:
        return Response(
            content='{"error": "Submit timed out"}',
            status_code=504, media_type="application/json",
        )
    except Exception as exc:
        logger.error("Submit error: %s", exc)
        return Response(
            content=f'{{"error": "{exc}"}}',
            status_code=500, media_type="application/json",
        )


@app.get("/status")
async def camera_status():
    cam = get_camera()
    opened = cam.isOpened()
    status = {
        "camera_opened":        opened,
        "api_base_url":         API_BASE_URL,
        "api_token_configured": bool(API_TOKEN),
        "timestamp":            datetime.now().isoformat(),
    }
    if opened:
        status.update({
            "width":  int(cam.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps":    int(cam.get(cv2.CAP_PROP_FPS)),
        })
    return status


@app.on_event("shutdown")
async def shutdown_event():
    global camera
    if camera is not None:
        camera.release()
        logger.info("Camera released")


if __name__ == "__main__":
    # Port 8001 — port 8000 is the main Fridge Observer API
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
