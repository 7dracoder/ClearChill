@echo off
echo ========================================
echo  Quick Camera Test - YOLO Detection
echo ========================================
echo.

echo [1/3] Setting up YOLO on Pi...
ssh pi@192.168.0.1 "cd ~/fridge-observer && bash setup_yolo.sh"

echo.
echo [2/3] Capturing and detecting...
ssh pi@192.168.0.1 "source /data/venv/bin/activate && cd ~/fridge-observer && python3 yolo_capture.py"

echo.
echo [3/3] Done!
echo Check your web app at http://192.168.0.2:8000
echo.
pause
