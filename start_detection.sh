#!/bin/bash
# Start detection system with proper logging

echo "============================================================"
echo "Starting Fridge Detection System"
echo "============================================================"
echo ""
echo "User ID: 3d16c0db-5f68-4b44-b579-0111e65e8308"
echo "Proxy: http://172.20.10.6:8001"
echo ""

# Kill any existing instances
echo "Stopping existing instances..."
pkill -f auto_detect_with_sensor
sleep 2

# Start fresh
echo "Starting detection..."
python3 ~/auto_detect_with_sensor.py 2>&1 | tee detection.log
