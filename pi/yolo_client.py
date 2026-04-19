#!/usr/bin/env python3
"""
YOLOv8 ONNX inference client — runs on the Raspberry Pi.

Uses ONNX Runtime for CPU inference. Much faster than Gemini API calls
(~2-5 FPS vs 10-15 seconds per frame) and provides bounding boxes for
precise object tracking across frames.

Advantages over Gemini:
  • 100x faster inference (local CPU vs API round-trip)
  • Bounding boxes enable per-object tracking (not just set difference)
  • No API costs, no rate limits, works offline
  • Can track object movement (hand entering vs leaving fridge)

Disadvantages:
  • Cannot read expiry dates from labels (vision-only, no OCR)
  • Limited to COCO classes (80 categories, not all food-specific)
  • Lower accuracy on packaged goods vs Gemini's multimodal understanding

Best use case: Fast detection + tracking, then optionally call Gemini
on key frames for expiry date reading.
"""

import logging
import os
from typing import Optional
import numpy as np
import cv2

try:
    import onnxruntime as ort
except ImportError:
    ort = None

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "/data/models/yolov8n.onnx")
CONFIDENCE_THRESHOLD = float(os.getenv("YOLO_CONFIDENCE_THRESHOLD", "0.5"))
IOU_THRESHOLD = float(os.getenv("YOLO_IOU_THRESHOLD", "0.5"))  # for tracking across frames
INPUT_SIZE = 640  # YOLOv8 default

# COCO class names (80 classes) — subset relevant to food
COCO_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog",
    "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket", "bottle",
    "wine glass", "cup", "fork", "knife", "spoon", "bowl",
    "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut",
    "cake", "chair", "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop",
    "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

# Map COCO classes to our food categories
COCO_TO_CATEGORY = {
    "banana": "fruits", "apple": "fruits", "orange": "fruits",
    "broccoli": "vegetables", "carrot": "vegetables",
    "sandwich": "packaged_goods", "hot dog": "meat", "pizza": "packaged_goods",
    "donut": "packaged_goods", "cake": "packaged_goods",
    "bottle": "beverages", "wine glass": "beverages", "cup": "beverages",
    "bowl": "packaged_goods", "fork": None, "knife": None, "spoon": None,  # utensils, ignore
}

# Food expiry database (same as gemini_client.py)
FOOD_EXPIRY_DATABASE = {
    "apple": (False, 7), "banana": (False, 5), "orange": (False, 10),
    "broccoli": (False, 5), "carrot": (False, 14),
    "sandwich": (True, None), "hot dog": (False, 2), "pizza": (False, 3),
    "donut": (False, 2), "cake": (False, 5),
    "bottle": (True, None),  # assume packaged beverage
}


# ── ONNX Model Loading ────────────────────────────────────────────────────────

_session: Optional[ort.InferenceSession] = None


def load_model() -> bool:
    """Load YOLOv8 ONNX model. Returns True if successful."""
    global _session
    if _session is not None:
        return True

    if ort is None:
        logger.error("onnxruntime not installed — run: pip install onnxruntime")
        return False

    if not os.path.exists(YOLO_MODEL_PATH):
        logger.error("YOLO model not found at %s", YOLO_MODEL_PATH)
        logger.info("Download YOLOv8n ONNX: https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.onnx")
        return False

    try:
        _session = ort.InferenceSession(
            YOLO_MODEL_PATH,
            providers=["CPUExecutionProvider"],  # Pi 4 doesn't have GPU
        )
        logger.info("YOLOv8 model loaded from %s", YOLO_MODEL_PATH)
        return True
    except Exception as exc:
        logger.error("Failed to load YOLO model: %s", exc)
        return False


# ── Preprocessing ─────────────────────────────────────────────────────────────

def preprocess(image: np.ndarray) -> np.ndarray:
    """
    Preprocess image for YOLOv8 ONNX input.
    Input: BGR image (H, W, 3)
    Output: RGB tensor (1, 3, 640, 640), normalized to [0, 1]
    """
    # Resize to 640x640 (letterbox with padding to preserve aspect ratio)
    h, w = image.shape[:2]
    scale = INPUT_SIZE / max(h, w)
    new_h, new_w = int(h * scale), int(w * scale)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

    # Pad to square
    canvas = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, dtype=np.uint8)
    top = (INPUT_SIZE - new_h) // 2
    left = (INPUT_SIZE - new_w) // 2
    canvas[top:top + new_h, left:left + new_w] = resized

    # Convert BGR → RGB, HWC → CHW, normalize to [0, 1]
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    chw = np.transpose(rgb, (2, 0, 1))  # (3, 640, 640)
    normalized = chw.astype(np.float32) / 255.0
    batched = np.expand_dims(normalized, axis=0)  # (1, 3, 640, 640)

    return batched, scale, (top, left)


# ── Postprocessing ────────────────────────────────────────────────────────────

def postprocess(output: np.ndarray, scale: float, offset: tuple) -> list[dict]:
    """
    Parse YOLOv8 output and apply NMS.
    
    YOLOv8 output shape: (1, 84, 8400)
      - 84 = 4 bbox coords + 80 class scores
      - 8400 = number of anchor boxes
    
    Returns list of detections:
      [{"class": "apple", "confidence": 0.92, "bbox": [x, y, w, h]}, ...]
    """
    output = output[0]  # (84, 8400)
    predictions = output.T  # (8400, 84)

    # Extract bbox and scores
    boxes = predictions[:, :4]  # (8400, 4) — [cx, cy, w, h]
    scores = predictions[:, 4:]  # (8400, 80) — class scores

    # Get best class for each box
    class_ids = np.argmax(scores, axis=1)
    confidences = np.max(scores, axis=1)

    # Filter by confidence
    mask = confidences > CONFIDENCE_THRESHOLD
    boxes = boxes[mask]
    class_ids = class_ids[mask]
    confidences = confidences[mask]

    if len(boxes) == 0:
        return []

    # Convert [cx, cy, w, h] → [x1, y1, x2, y2]
    x1 = boxes[:, 0] - boxes[:, 2] / 2
    y1 = boxes[:, 1] - boxes[:, 3] / 2
    x2 = boxes[:, 0] + boxes[:, 2] / 2
    y2 = boxes[:, 1] + boxes[:, 3] / 2
    boxes_xyxy = np.stack([x1, y1, x2, y2], axis=1)

    # Apply NMS
    indices = cv2.dnn.NMSBoxes(
        boxes_xyxy.tolist(),
        confidences.tolist(),
        CONFIDENCE_THRESHOLD,
        IOU_THRESHOLD,
    )

    if len(indices) == 0:
        return []

    # Build detection list
    detections = []
    top, left = offset
    for i in indices.flatten():
        class_id = int(class_ids[i])
        class_name = COCO_CLASSES[class_id]
        confidence = float(confidences[i])

        # Unscale bbox back to original image coordinates
        x1_orig = (boxes_xyxy[i, 0] - left) / scale
        y1_orig = (boxes_xyxy[i, 1] - top) / scale
        x2_orig = (boxes_xyxy[i, 2] - left) / scale
        y2_orig = (boxes_xyxy[i, 3] - top) / scale

        bbox = [
            int(x1_orig),
            int(y1_orig),
            int(x2_orig - x1_orig),  # width
            int(y2_orig - y1_orig),  # height
        ]

        detections.append({
            "class": class_name,
            "confidence": round(confidence, 2),
            "bbox": bbox,  # [x, y, w, h]
        })

    return detections


# ── Object Tracking ───────────────────────────────────────────────────────────

def compute_iou(box1: list, box2: list) -> float:
    """Compute IoU between two boxes [x, y, w, h]."""
    x1, y1, w1, h1 = box1
    x2, y2, w2, h2 = box2

    xi1 = max(x1, x2)
    yi1 = max(y1, y2)
    xi2 = min(x1 + w1, x2 + w2)
    yi2 = min(y1 + h1, y2 + h2)

    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    box1_area = w1 * h1
    box2_area = w2 * h2
    union_area = box1_area + box2_area - inter_area

    return inter_area / union_area if union_area > 0 else 0.0


def track_objects(
    first_frame_detections: list[dict],
    last_frame_detections: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    Track objects across first and last frames using IoU matching.
    
    Returns (items_added, items_removed):
      items_added   — objects in last frame with no match in first (new items)
      items_removed — objects in first frame with no match in last (taken out)
    """
    # Match last frame objects to first frame using IoU
    matched_last = set()
    matched_first = set()

    for i, det_last in enumerate(last_frame_detections):
        best_iou = 0.0
        best_j = -1
        for j, det_first in enumerate(first_frame_detections):
            if det_last["class"] != det_first["class"]:
                continue  # only match same class
            iou = compute_iou(det_last["bbox"], det_first["bbox"])
            if iou > best_iou:
                best_iou = iou
                best_j = j

        if best_iou > IOU_THRESHOLD:
            matched_last.add(i)
            matched_first.add(best_j)

    # Unmatched objects in last frame = added
    items_added = [
        last_frame_detections[i]
        for i in range(len(last_frame_detections))
        if i not in matched_last
    ]

    # Unmatched objects in first frame = removed
    items_removed = [
        first_frame_detections[i]
        for i in range(len(first_frame_detections))
        if i not in matched_first
    ]

    return items_added, items_removed


# ── Enrichment ────────────────────────────────────────────────────────────────

def enrich_detection(det: dict) -> dict:
    """Add category and expiry info to a YOLO detection."""
    class_name = det["class"]
    category = COCO_TO_CATEGORY.get(class_name, "packaged_goods")

    if category is None:
        # Utensil or non-food item — skip
        return None

    needs_input, est_days = FOOD_EXPIRY_DATABASE.get(class_name, (True, None))

    return {
        "name": class_name.title(),
        "category": category,
        "confidence": det["confidence"],
        "bbox": det["bbox"],
        "expiry_source": "estimated" if not needs_input else "unknown",
        "expiry_date": None,
        "estimated_expiry_days": est_days if not needs_input else None,
        "needs_expiry_input": needs_input,
    }


# ── Public API ────────────────────────────────────────────────────────────────

def identify_food(image_bytes: bytes) -> list[dict]:
    """
    Run YOLOv8 inference on a single frame.
    Returns enriched detection list (same schema as gemini_client).
    """
    if not load_model():
        return []

    # Decode image
    nparr = np.frombuffer(image_bytes, np.uint8)
    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if image is None:
        logger.error("Failed to decode image")
        return []

    # Preprocess
    input_tensor, scale, offset = preprocess(image)

    # Inference
    outputs = _session.run(None, {_session.get_inputs()[0].name: input_tensor})

    # Postprocess
    detections = postprocess(outputs[0], scale, offset)

    # Enrich and filter
    enriched = [enrich_detection(det) for det in detections]
    enriched = [e for e in enriched if e is not None]

    return enriched


def identify_food_multi(frames: list[bytes]) -> dict:
    """
    Run YOLOv8 on first and last frames, track objects using IoU.
    
    Returns:
      {
        "items_added": [...],
        "items_removed": [...],
        "all_items": [...],
      }
    """
    if not load_model():
        return {"items_added": [], "items_removed": [], "all_items": []}

    if not frames:
        return {"items_added": [], "items_removed": [], "all_items": []}

    # Decode first and last frames
    first_image = cv2.imdecode(np.frombuffer(frames[0], np.uint8), cv2.IMREAD_COLOR)
    last_image = cv2.imdecode(np.frombuffer(frames[-1], np.uint8), cv2.IMREAD_COLOR)

    if first_image is None or last_image is None:
        logger.error("Failed to decode frames")
        return {"items_added": [], "items_removed": [], "all_items": []}

    # Run inference on both frames
    first_input, first_scale, first_offset = preprocess(first_image)
    last_input, last_scale, last_offset = preprocess(last_image)

    first_outputs = _session.run(None, {_session.get_inputs()[0].name: first_input})
    last_outputs = _session.run(None, {_session.get_inputs()[0].name: last_input})

    first_detections = postprocess(first_outputs[0], first_scale, first_offset)
    last_detections = postprocess(last_outputs[0], last_scale, last_offset)

    logger.info("First frame: %d detections, Last frame: %d detections",
                len(first_detections), len(last_detections))

    # Track objects using IoU
    added_raw, removed_raw = track_objects(first_detections, last_detections)

    # Enrich
    items_added = [enrich_detection(det) for det in added_raw]
    items_added = [e for e in items_added if e is not None]

    items_removed = [enrich_detection(det) for det in removed_raw]
    items_removed = [e for e in items_removed if e is not None]

    # All items = union of first and last frame (deduplicated by tracking)
    all_items = items_added + items_removed

    logger.info("Tracked: %d added, %d removed", len(items_added), len(items_removed))

    return {
        "items_added": items_added,
        "items_removed": items_removed,
        "all_items": all_items,
    }
