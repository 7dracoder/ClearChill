#!/usr/bin/env python3
from ultralytics import YOLO

print("Loading YOLOv8n model...")
model = YOLO("/data/models/yolov8n.pt")

print("Exporting to ONNX format...")
model.export(format="onnx")

print("✓ Export complete! Model saved as yolov8n.onnx")
