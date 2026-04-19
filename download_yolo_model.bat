@echo off
echo ============================================================
echo YOLO Model Download and Deploy
echo ============================================================
echo.

echo [1/2] Downloading YOLOv8n model (~6MB)...
echo This may take a minute depending on your internet speed...
echo.

powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.onnx' -OutFile 'yolov8n.onnx' -UseBasicParsing}"

if not exist yolov8n.onnx (
    echo ERROR: Download failed!
    echo.
    echo Please download manually from:
    echo https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.onnx
    echo.
    echo Then run: scp yolov8n.onnx pi@192.168.0.1:/data/models/
    pause
    exit /b 1
)

echo SUCCESS: Model downloaded!
echo.

echo [2/2] Deploying to Raspberry Pi...
scp yolov8n.onnx pi@192.168.0.1:/data/models/

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo SUCCESS! YOLO model installed on Pi
    echo ============================================================
    echo.
    echo You can now run the detection script:
    echo   ssh pi@192.168.0.1
    echo   cd ~/fridge-observer
    echo   source /data/venv/bin/activate
    echo   python3 pi/capture_and_detect.py
    echo.
    del yolov8n.onnx
) else (
    echo.
    echo ERROR: Failed to copy to Pi
    echo The model file is saved as yolov8n.onnx in this directory
    echo You can manually copy it later with:
    echo   scp yolov8n.onnx pi@192.168.0.1:/data/models/
)

echo.
pause
