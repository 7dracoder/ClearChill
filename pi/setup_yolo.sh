#!/bin/bash
# Download YOLOv8 model for object detection
cd ~/fridge-observer
source /data/venv/bin/activate

# Install ultralytics if not present
pip install ultralytics opencv-python-headless --quiet

# Download YOLOv8n (nano - fastest, smallest)
python3 << EOF
from ultralytics import YOLO
model = YOLO('yolov8n.pt')  # Downloads automatically
print("YOLOv8 model downloaded!")
EOF

echo "Setup complete!"
