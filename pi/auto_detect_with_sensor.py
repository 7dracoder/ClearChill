#!/usr/bin/env python3
"""
Automatic fridge detection with light sensor
Monitors door state and triggers detection when door opens/closes
"""
import cv2
import os
import time
import requests
import lgpio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Configuration
PROXY_URL = "http://172.20.10.6:8001"
USER_ID = "3d16c0db-5f68-4b44-b579-0111e65e8308"
WEBCAM_INDEX = int(os.getenv("WEBCAM_INDEX", "0"))
BCM_PIN = 17  # GPIO pin 11 (BOARD) = BCM 17
BRIGHTNESS_THRESHOLD = float(os.getenv("BRIGHTNESS_THRESHOLD", "80.0"))
SCAN_INTERVAL = 4.0   # seconds between scans while door is open
DOOR_DEBOUNCE = 2.0  # door must stay open/closed this long before acting

# Food categories and expiry - ALL items that belong in a fridge
FOOD_EXPIRY = {
    # Fruits
    "apple": ("fruits", 7), "banana": ("fruits", 5), "orange": ("fruits", 10),
    "strawberry": ("fruits", 3), "grape": ("fruits", 5), "blueberry": ("fruits", 5),
    "lemon": ("fruits", 14), "lime": ("fruits", 14), "watermelon": ("fruits", 7),
    "pear": ("fruits", 7), "peach": ("fruits", 5), "plum": ("fruits", 5),
    "mango": ("fruits", 5), "pineapple": ("fruits", 5), "kiwi": ("fruits", 7),
    "cherry": ("fruits", 3), "raspberry": ("fruits", 2), "blackberry": ("fruits", 2),
    "melon": ("fruits", 7), "cantaloupe": ("fruits", 5), "grapefruit": ("fruits", 14),
    "avocado": ("fruits", 5), "pomegranate": ("fruits", 7), "papaya": ("fruits", 5),
    # Vegetables
    "broccoli": ("vegetables", 5), "carrot": ("vegetables", 14), "lettuce": ("vegetables", 5),
    "tomato": ("vegetables", 7), "cucumber": ("vegetables", 7), "pepper": ("vegetables", 7),
    "celery": ("vegetables", 7), "spinach": ("vegetables", 3), "cabbage": ("vegetables", 14),
    "onion": ("vegetables", 14), "garlic": ("vegetables", 14), "potato": ("vegetables", 14),
    "corn": ("vegetables", 3), "peas": ("vegetables", 3), "beans": ("vegetables", 5),
    "mushroom": ("vegetables", 5), "zucchini": ("vegetables", 5), "eggplant": ("vegetables", 5),
    "cauliflower": ("vegetables", 7), "asparagus": ("vegetables", 3), "kale": ("vegetables", 5),
    # Dairy
    "milk": ("dairy", 7), "cheese": ("dairy", 14), "yogurt": ("dairy", 14),
    "butter": ("dairy", 30), "cream": ("dairy", 7), "egg": ("dairy", 21),
    "sour cream": ("dairy", 14), "cottage cheese": ("dairy", 7), "mozzarella": ("dairy", 14),
    "cheddar": ("dairy", 21), "parmesan": ("dairy", 30), "ice cream": ("dairy", 60),
    # Meat
    "chicken": ("meat", 2), "beef": ("meat", 3), "pork": ("meat", 3),
    "fish": ("meat", 1), "salmon": ("meat", 1), "ham": ("meat", 5),
    "bacon": ("meat", 7), "sausage": ("meat", 3), "turkey": ("meat", 2),
    "lamb": ("meat", 3), "steak": ("meat", 3), "shrimp": ("meat", 2),
    "tuna": ("meat", 2), "crab": ("meat", 2),
    # Beverages
    "juice": ("beverages", 7), "water": ("beverages", 30), "soda": ("beverages", 90),
    "beer": ("beverages", 90), "wine": ("beverages", 365), "cola": ("beverages", 90),
    "lemonade": ("beverages", 7), "tea": ("beverages", 7),
    "energy drink": ("beverages", 90), "sports drink": ("beverages", 90),
    "can": ("beverages", 90), "bottle": ("beverages", 30), "drink": ("beverages", 7),
    # Packaged & Leftovers
    "pizza": ("packaged_goods", 3), "leftover": ("packaged_goods", 3),
    "sandwich": ("packaged_goods", 2), "sauce": ("packaged_goods", 30),
    "chocolate": ("packaged_goods", 90), "candy": ("packaged_goods", 90),
    "dessert": ("packaged_goods", 3), "cake": ("packaged_goods", 5),
    "pie": ("packaged_goods", 3), "cookie": ("packaged_goods", 7),
    "bread": ("packaged_goods", 7), "pasta": ("packaged_goods", 3),
    "rice": ("packaged_goods", 3), "salad": ("packaged_goods", 2),
    "soup": ("packaged_goods", 3), "dip": ("packaged_goods", 7),
    "hummus": ("packaged_goods", 7), "food": ("packaged_goods", 3),
    "meal": ("packaged_goods", 3), "snack": ("packaged_goods", 7),
}

FRIDGE_KEYWORDS = [
    'milk', 'cheese', 'yogurt', 'butter', 'cream', 'egg', 'dairy', 'ice cream',
    'sour cream', 'cottage cheese', 'mozzarella', 'cheddar', 'parmesan',
    'meat', 'chicken', 'beef', 'pork', 'fish', 'salmon', 'bacon', 'ham',
    'turkey', 'lamb', 'steak', 'sausage', 'shrimp', 'tuna', 'crab', 'seafood',
    'fruit', 'apple', 'banana', 'orange', 'strawberry', 'grape', 'berry',
    'lemon', 'lime', 'watermelon', 'pear', 'peach', 'plum', 'mango',
    'pineapple', 'kiwi', 'cherry', 'raspberry', 'blackberry', 'melon',
    'cantaloupe', 'grapefruit', 'avocado', 'pomegranate', 'papaya',
    'vegetable', 'lettuce', 'tomato', 'cucumber', 'carrot', 'broccoli', 'pepper',
    'celery', 'spinach', 'cabbage', 'onion', 'garlic', 'potato', 'corn',
    'peas', 'beans', 'mushroom', 'zucchini', 'eggplant', 'cauliflower',
    'asparagus', 'kale', 'veggie',
    'juice', 'beverage', 'drink', 'soda', 'water', 'beer', 'wine', 'cola',
    'lemonade', 'tea', 'can', 'bottle', 'energy drink', 'sports drink',
    'pizza', 'leftover', 'sandwich', 'sauce', 'chocolate', 'candy', 'dessert',
    'cake', 'pie', 'cookie', 'bread', 'pasta', 'rice', 'salad',
    'soup', 'dip', 'hummus', 'condiment', 'dressing', 'mayonnaise', 'ketchup',
    'mustard', 'container', 'tupperware', 'food', 'meal', 'snack',
]


# ── GPIO helpers ──────────────────────────────────────────────────────────────

def measure_brightness_ms(chip, timeout_ms=500.0):
    """RC timing: lower = brighter = door open."""
    try:
        lgpio.gpio_claim_output(chip, BCM_PIN, 0)
        time.sleep(0.05)
        lgpio.gpio_free(chip, BCM_PIN)

        lgpio.gpio_claim_input(chip, BCM_PIN, lgpio.SET_PULL_NONE)
        t_start = time.time()
        deadline = t_start + timeout_ms / 1000.0

        while lgpio.gpio_read(chip, BCM_PIN) == 0:
            if time.time() > deadline:
                lgpio.gpio_free(chip, BCM_PIN)
                return timeout_ms

        elapsed = (time.time() - t_start) * 1000.0
        lgpio.gpio_free(chip, BCM_PIN)
        return elapsed
    except Exception as e:
        # Try to free pin before returning
        try:
            lgpio.gpio_free(chip, BCM_PIN)
        except Exception:
            pass
        return timeout_ms


# ── Camera ────────────────────────────────────────────────────────────────────

def open_camera():
    """Open camera and keep it open — returns cap object or None."""
    cap = cv2.VideoCapture(WEBCAM_INDEX)
    if not cap.isOpened():
        print("  ⚠ Cannot open webcam")
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    # Warm up — discard first few frames
    for _ in range(3):
        cap.read()
    print("  📷 Camera opened")
    return cap

def capture_frame(cap):
    """Grab a frame from an already-open camera."""
    if cap is None or not cap.isOpened():
        return None
    ret, frame = cap.read()
    return frame if ret else None


# ── Detection ─────────────────────────────────────────────────────────────────

def detect_with_imagga_via_proxy(frame):
    import base64
    _, buffer = cv2.imencode('.jpg', frame)
    payload = {"image": base64.b64encode(buffer.tobytes()).decode()}

    try:
        resp = requests.post(f"{PROXY_URL}/proxy/imagga", json=payload, timeout=30)
        if resp.status_code != 200:
            print(f"  ⚠ Imagga error {resp.status_code}: {resp.text[:80]}")
            return []

        tags = resp.json().get('result', {}).get('tags', [])
        detected = []
        for tag in tags[:20]:
            tag_name = tag.get('tag', {}).get('en', '').lower()
            confidence = tag.get('confidence', 0) / 100.0
            if any(kw in tag_name for kw in FRIDGE_KEYWORDS) and confidence > 0.25:
                detected.append({"name": tag_name, "confidence": confidence})

        items = []
        for det in detected[:5]:
            name = det["name"]
            category, expiry_days = FOOD_EXPIRY.get(name, ("packaged_goods", 7))
            items.append({
                "name": name.title(),
                "category": category,
                "confidence": det["confidence"],
                "expiry_days": expiry_days,
            })
        return items

    except Exception as e:
        print(f"  ⚠ Detection error: {e}")
        return []


# ── Supabase ──────────────────────────────────────────────────────────────────

def send_to_supabase(items, already_sent):
    added = 0
    for item in items:
        key = item["name"].lower()
        if key in already_sent:
            continue

        expiry_days = item.get("expiry_days") or 7   # default 7 days if None
        expiry_date = (datetime.now() + timedelta(days=expiry_days)).date().isoformat()

        payload = {
            "name": item["name"],
            "category": item["category"],
            "quantity": 1,
            "expiry_date": expiry_date,
            "user_id": USER_ID,
        }
        try:
            resp = requests.post(f"{PROXY_URL}/proxy/food_items", json=payload, timeout=10)
            if resp.status_code in (200, 201):
                print(f"  ✓ Added {item['name']} (expires {expiry_date})")
                already_sent.add(key)
                added += 1
            else:
                print(f"  ✗ Failed to add {item['name']}: {resp.status_code} {resp.text[:60]}")
        except Exception as e:
            print(f"  ✗ Error adding {item['name']}: {e}")

    return added, already_sent


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Fridge Observer - Automatic Detection")
    print("=" * 60)
    print(f"GPIO BCM pin : {BCM_PIN}  (BOARD pin 11)")
    print(f"Threshold    : {BRIGHTNESS_THRESHOLD} ms")
    print(f"Proxy        : {PROXY_URL}")
    print(f"User ID      : {USER_ID[:8]}...")
    print("\nMonitoring door... Press Ctrl+C to stop\n")

    chip = lgpio.gpiochip_open(4)

    door_was_open = False
    detected_items = set()
    sent_items = set()
    last_scan_time = 0
    cap = None               # camera kept open while door is open
    last_open_time = 0
    last_close_time = 0

    try:
        while True:
            brightness = measure_brightness_ms(chip)
            door_open = brightness < BRIGHTNESS_THRESHOLD
            now = time.time()

            # ── Door just opened ──────────────────────────────────────
            if door_open and not door_was_open:
                # Debounce: ignore flicker if closed less than 1s ago
                if now - last_close_time < 1.0:
                    time.sleep(0.3)
                    continue

                last_open_time = now
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔓 Door OPENED ({brightness:.1f} ms)")
                detected_items.clear()
                sent_items.clear()
                last_scan_time = 0
                door_was_open = True

                # Open camera once and keep it open for the session
                if cap is not None:
                    cap.release()
                cap = open_camera()

            # ── Door still open — scan periodically ───────────────────
            elif door_open and door_was_open:
                if now - last_scan_time >= SCAN_INTERVAL:
                    last_scan_time = now
                    print(f"  📷 Scanning... ({len(sent_items)} sent so far)")

                    # Re-open camera if it died
                    if cap is None or not cap.isOpened():
                        print("  ⚠ Camera lost, reopening...")
                        cap = open_camera()

                    frame = capture_frame(cap)
                    if frame is not None:
                        items = detect_with_imagga_via_proxy(frame)
                        if items:
                            new_items = [i for i in items if i['name'].lower() not in detected_items]
                            for i in new_items:
                                detected_items.add(i['name'].lower())
                            if new_items:
                                print(f"  🔍 Detected:")
                                for i in new_items:
                                    print(f"     • {i['name']} ({i['confidence']:.0%})")
                                added, sent_items = send_to_supabase(new_items, sent_items)
                                if added:
                                    print(f"  ✅ {added} item(s) saved to Supabase!")
                            else:
                                print("  (no new items this scan)")
                        else:
                            print("  (nothing fridge-related detected)")
                    else:
                        print("  ⚠ Frame capture failed")

            # ── Door just closed ──────────────────────────────────────
            elif not door_open and door_was_open:
                # Debounce: only close if door has been open for at least 0.5s
                if now - last_open_time < 0.5:
                    time.sleep(0.3)
                    continue

                last_close_time = now
                print(f"[{datetime.now().strftime('%H:%M:%S')}] 🔒 Door CLOSED ({brightness:.1f} ms)")
                print(f"  Session: {len(sent_items)} unique item(s) sent\n")
                door_was_open = False
                detected_items.clear()
                sent_items.clear()

                # Release camera
                if cap is not None:
                    cap.release()
                    cap = None

            time.sleep(0.3)

    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        if cap is not None:
            cap.release()
        lgpio.gpiochip_close(chip)
        print("GPIO closed. Bye!")


if __name__ == "__main__":
    main()
