@echo off
echo ========================================
echo  Fridge Observer System Startup
echo ========================================
echo.

echo [1/4] Starting FastAPI Backend...
start "Backend Server" cmd /k "python -m uvicorn fridge_observer.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 5 /nobreak >nul

echo [2/4] Deploying files to Pi...
scp -O -o BatchMode=yes pi/.env pi/raspberry_pi_sensor.py pi/groq_client.py pi@192.168.0.1:~/fridge-observer/
echo.

echo [3/4] Starting Camera Stream on Pi...
ssh -o BatchMode=yes pi@192.168.0.1 "source /data/venv/bin/activate && cd /data/pi && nohup python3 camera_stream.py > camera.log 2>&1 &"
timeout /t 3 /nobreak >nul

echo [4/4] Starting Sensor Monitor on Pi...
ssh -o BatchMode=yes pi@192.168.0.1 "source /data/venv/bin/activate && cd ~/fridge-observer && nohup python3 raspberry_pi_sensor.py > sensor.log 2>&1 &"
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo  System Started Successfully!
echo ========================================
echo.
echo  Backend:  http://localhost:8000
echo  Monitor:  http://localhost:8000/monitor.html
echo  Camera:   http://192.168.0.1:8001/stream
echo.
echo Press any key to open monitor dashboard...
pause >nul
start http://localhost:8000/monitor.html
