#!/usr/bin/env python3
"""

Raspberry Pi Fridge Observer — Hardware Integration Script


Light sensing uses an RC timing circuit:

  - Photoresistor + capacitor wired to a single GPIO pin (BOARD pin 7 by default)

  - GPIO is driven LOW to discharge the capacitor, then switched to INPUT

  - Time for the pin to go HIGH = charge time through the photoresistor

  - Shorter charge time  →  lower resistance  →  brighter light  →  door open

  - Longer charge time   →  higher resistance →  darker          →  door closed


Capture strategy (per hardware.txt):

  - Frames are collected into RAM while the door is OPEN

  - When the door CLOSES, Gemini analyses key frames locally on the Pi

  - Detections are aggregated across frames for higher confidence

  - Only the JSON result is sent to the server — images never leave the Pi
"""

import os
import time
import logging

import requests

import cv2

# Set RPI_LGPIO_CHIP before importing RPi.GPIO (Pi 4 uses gpiochip4)

os.environ.setdefault("RPI_LGPIO_CHIP", "4")

import lgpio  # Use lgpio directly instead of RPi.GPIO wrapper
from datetime import datetime

from dotenv import load_dotenv


load_dotenv()


# ── Logging ───────────────────────────────────────────────────────────────────


logging.basicConfig(

    level=logging.INFO,

    format="%(asctime)s %(levelname)s: %(message)s",

    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


# ── Import inference client based on config ───────────────────────────────────

# Options: "groq" (default), "gemini", "yolo", "hybrid"


INFERENCE_MODE = os.getenv("INFERENCE_MODE", "groq").lower()


if INFERENCE_MODE == "yolo":

    from yolo_client import identify_food_multi

    logger.info("Using YOLO ONNX inference (fast, local, bbox tracking)")

elif INFERENCE_MODE == "hybrid":

    from hybrid_client import identify_food_multi

    logger.info("Using hybrid inference (YOLO + Groq for expiry dates)")

elif INFERENCE_MODE == "gemini":

    from gemini_client import identify_food_multi

    logger.info("Using Gemini API inference (slow, accurate, reads labels)")

else:

    from groq_client import identify_food_multi

    logger.info("Using Groq API inference (fast, accurate vision model)")


# ── Configuration (all overridable via .env) ──────────────────────────────────


API_BASE_URL     = os.getenv("API_BASE_URL",     "http://localhost:8000")

API_TOKEN        = os.getenv("API_TOKEN",        "")

WEBCAM_INDEX     = int(os.getenv("WEBCAM_INDEX",     "0"))

CAPTURE_FPS      = float(os.getenv("CAPTURE_FPS",     "1.0"))   # frames per second while door open

CAPTURE_COOLDOWN = float(os.getenv("CAPTURE_COOLDOWN", "30.0")) # min seconds between sessions

STATUS_INTERVAL  = float(os.getenv("STATUS_INTERVAL",  "300.0"))


# RC timing light sensor — BOARD numbering

SENSOR_PIN     = int(os.getenv("LIGHT_SENSOR_PIN", "11"))  # physical pin 11 = GPIO17

BCM_PIN        = 17  # BOARD pin 11 = BCM GPIO 17

BRIGHTNESS_THRESHOLD = float(os.getenv("BRIGHTNESS_THRESHOLD", "80.0"))  # ms — calibrated value


# ── GPIO setup ────────────────────────────────────────────────────────────────

_gpio_chip = lgpio.gpiochip_open(4)  # Pi 4 main GPIO bank


# ── State ─────────────────────────────────────────────────────────────────────


door_was_open     = False

last_session_time = 0.0



# ── Light sensing ─────────────────────────────────────────────────────────────


def measure_brightness_ms() -> float:
    """

    Discharge the capacitor then measure how long it takes to recharge

    through the photoresistor.  Returns charge time in milliseconds.


    Low value  = dark   (door closed)

    High value = bright (door open)
    """

    # Free the pin first in case it's still claimed from a previous run

    try:

        lgpio.gpio_free(_gpio_chip, BCM_PIN)

    except:
        pass
    

    # Discharge: claim as output, drive LOW

    lgpio.gpio_claim_output(_gpio_chip, BCM_PIN, 0)

    time.sleep(0.05)


    # Switch to input and time the recharge

    lgpio.gpio_free(_gpio_chip, BCM_PIN)

    lgpio.gpio_claim_input(_gpio_chip, BCM_PIN, lgpio.SET_PULL_NONE)

    t_start = time.time()

    timeout = t_start + 0.5  # 500 ms safety cap


    while lgpio.gpio_read(_gpio_chip, BCM_PIN) == 0:

        if time.time() > timeout:

            lgpio.gpio_free(_gpio_chip, BCM_PIN)

            return 500.0


    elapsed = (time.time() - t_start) * 1000.0

    lgpio.gpio_free(_gpio_chip, BCM_PIN)
    return elapsed



def is_door_open(brightness_ms: float) -> bool:

    return brightness_ms > BRIGHTNESS_THRESHOLD  # High value = bright = door open



# ── API helpers ───────────────────────────────────────────────────────────────


def _auth_headers() -> dict:

    return {"Authorization": f"Bearer {API_TOKEN}"}



def send_door_event(event_type: str, brightness_ms: float) -> None:

    try:

        resp = requests.post(

            f"{API_BASE_URL}/api/hardware/door-event",

            json={

                "event": event_type,

                "timestamp": datetime.utcnow().isoformat() + "Z",

                "light_level": darkness_ms,

            },

            headers=_auth_headers(),

            timeout=5,
        )

        if resp.ok:

            logger.info("✓ Door event sent: %s", event_type)

        else:

            logger.warning("✗ Door event rejected: %s", resp.status_code)

    except Exception as exc:

        logger.error("✗ Error sending door event: %s", exc)



def send_session_complete(payload: dict) -> None:
    """

    POST aggregated detection results to the server.

    Images are never sent — only the JSON item list.
    """

    try:

        resp = requests.post(

            f"{API_BASE_URL}/api/hardware/session-complete",

            json=payload,

            headers=_auth_headers(),

            timeout=10,
        )

        if resp.ok:

            result = resp.json()
            logger.info(

                "✓ Session complete — %d pending item(s) created",

                result.get("pending_items_created", 0),
            )

            for item in result.get("auto_added", []):

                logger.info("    • %s — expires %s", item["name"], item.get("expiry_date", "?"))

            for item in result.get("needs_expiry_input", []):

                logger.info("    • %s (needs expiry date)", item["name"])

        else:

            logger.error("✗ Session submit failed: %s — %s", resp.status_code, resp.text[:200])

    except requests.Timeout:

        logger.error("✗ Session submit timed out")

    except Exception as exc:

        logger.error("✗ Session submit error: %s", exc)



def send_status_update(darkness_ms: float) -> None:

    try:

        resp = requests.post(

            f"{API_BASE_URL}/api/hardware/status",

            json={

                "light_level": darkness_ms,

                "last_capture": (
                    datetime.fromtimestamp(last_session_time).isoformat()

                    if last_session_time > 0 else None

                ),

                "status": "online",

                "timestamp": datetime.utcnow().isoformat() + "Z",

            },

            headers=_auth_headers(),

            timeout=5,
        )

        if resp.ok:

            logger.info("✓ Status update sent")

        else:

            logger.warning("✗ Status update rejected: %s", resp.status_code)

    except Exception as exc:

        logger.error("✗ Error sending status: %s", exc)



# ── Capture session ───────────────────────────────────────────────────────────


def run_capture_session() -> None:
    """

    Collect frames into RAM while the door is open.

    When the door closes, run Gemini on key frames, aggregate results,

    and POST the JSON summary to the server.

    Images are held in RAM only and deleted after processing.
    """

    global last_session_time


    now = time.time()

    if now - last_session_time < CAPTURE_COOLDOWN:

        remaining = CAPTURE_COOLDOWN - (now - last_session_time)

        logger.info("⏳ Session cooldown — %.0f s remaining", remaining)
        return


    session_id = f"sess_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    started_at = datetime.utcnow()


    logger.info("📸 Session started: %s", session_id
)
    logger.info("   Opening camera (index %d)…", WEBCAM_INDEX)


    cam = cv2.VideoCapture(WEBCAM_INDEX)

    if not cam.isOpened():

        logger.error("✗ Could not open webcam")
        return


    cam.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)

    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    time.sleep(0.5)  # let auto-exposure settle


    # ── Collect frames while door is open ─────────────────────

    frames: list[bytes] = []

    frame_interval = 1.0 / CAPTURE_FPS


    try:

        while True:

            brightness_ms = measure_brightness_ms()

            if not is_door_open(brightness_ms):

                break  # door closed — stop capturing


            ret, frame = cam.read()

            if ret and frame is not None:

                ret2, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

                if ret2:

                    frames.append(buf.tobytes())

                    logger.info("   Frame %d captured", len(frames))


            time.sleep(frame_interval)


    finally:
        cam.release()

        logger.info("   Camera released")


    ended_at = datetime.utcnow()

    duration = (ended_at - started_at).total_seconds()


    logger.info("   Door closed — %d frame(s) captured in %.1f s", len(frames), duration)


    if not frames:

        logger.info("   No frames captured, skipping inference")
        return


    # ── Run Gemini inference on key frames (in RAM) ───────────

    logger.info("   Running Gemini inference on key frames…")

    result = identify_food_multi(frames)


    # ── Free frame memory immediately ─────────────────────────

    frame_count = len(frames)
    frames.clear()

    logger.info("   Frame memory cleared")


    items_added   = result["items_added"]

    items_removed = result["items_removed"]

    all_items     = result["all_items"]


    if not all_items:

        logger.info("   No items detected above confidence threshold")

        last_session_time = now
        return

    logger.info(

        "   %d item(s) added, %d item(s) removed",

        len(items_added), len(items_removed),
    )

    for item in items_added:

        logger.info("    + %s (%.0f%% confident, expiry: %s)",

                    item["name"], item["confidence"] * 100,

                    item.get("expiry_date") or f"~{item.get('estimated_expiry_days')}d" or "ask user")

    for item in items_removed:

        logger.info("    - %s", item["name"])


    # ── Send aggregated results to server ─────────────────────

    payload = {

        "session_id": session_id,

        "started_at": started_at.isoformat() + "Z",

        "ended_at": ended_at.isoformat() + "Z",

        "duration_seconds": int(duration),

        "frames_captured": frame_count,

        "items_added": items_added,

        "items_removed": items_removed,

        "low_confidence_items": [],  # already filtered by CONFIDENCE_THRESHOLD

    }


    send_session_complete(payload)

    last_session_time = now



# ── Main loop ─────────────────────────────────────────────────────────────────


def main() -> None:

    global door_was_open


    print("=" * 60)

    print("  Fridge Observer — Hardware Monitor")

    print("=" * 60)

    print(f"  API           : {API_BASE_URL}")

    print(f"  Sensor pin    : BOARD {SENSOR_PIN}")

    print(f"  Brightness threshold: {BRIGHTNESS_THRESHOLD} ms")

    print(f"  Webcam index  : {WEBCAM_INDEX}")

    print(f"  Capture FPS   : {CAPTURE_FPS}")

    print(f"  Cooldown      : {CAPTURE_COOLDOWN} s")

    print(f"  AI inference  : {INFERENCE_MODE.upper()} (on-device, runs on door close)")

    print("=" * 60)

    print("  Monitoring started — press Ctrl+C to stop")
    print()


    last_status_time = 0.0


    try:

        while True:
            brightness_ms = measure_brightness_ms()
            door_open   = is_door_open(brightness_ms)


            if door_open and not door_was_open:

                # Door just opened — notify server, start session

                logger.info("🚪 Door OPENED  (darkness: %.2f ms)",brightness_ms)
                send_door_event("door_opened", brightness_ms)
                door_was_open = True
                run_capture_session()  # blocrs until door closes, then processes

                door_was_open = False

            elif not door_open and door_was_open:

                # Shouldn't normally reach here (run_capture_session handles close)
                # but handles edge case where door closed before session started
                logger.info("🚪 Door CLOSED  (brightness: %.2f ms)", brightness_ms)
                send_door_event("door_closed", brightness_ms)
                door_was_open = False


            now = time.time()

            if now - last_status_time >= STATUS_INTERVAL:
                send_status_update(brightness_ms)

                last_status_time = now


            time.sleep(0.1)


    except KeyboardInterrupt:

        print("\n⏹  Stopping monitor…")

    finally:

        lgpio.gpiochip_close(_gpio_chip)

        logger.info("✓ GPIO cleaned up")

        logger.info("✓ Monitor stopped")



if __name__ == "__main__":
    main()

