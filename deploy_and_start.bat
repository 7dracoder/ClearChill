@echo off
echo ========================================
echo  Deploying to Pi and Starting System
echo ========================================
echo.

echo [1/5] Stopping old processes on Pi...
ssh -o BatchMode=yes pi@192.168.0.1 "pkill -9 python3 2>/dev/null; sleep 1"

echo [2/5] Deploying files to Pi...
scp -O -o BatchMode=yes pi/.env pi/raspberry_pi_sensor.py pi/groq_client.py pi@192.168.0.1:~/fridge-observer/

echo [3/5] Testing script syntax...
ssh -o BatchMode=yes pi@192.168.0.1 "source /data/venv/bin/activate && cd ~/fridge-observer && python3 -m py_compile raspberry_pi_sensor.py"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Script has syntax errors!
    pause
    exit /b 1
)

echo [4/5] Starting sensor on Pi...
ssh -o BatchMode=yes pi@192.168.0.1 "source /data/venv/bin/activate && cd ~/fridge-observer && nohup python3 raspberry_pi_sensor.py > sensor.log 2>&1 &"
timeout /t 3 /nobreak >nul

echo [5/5] Checking status...
ssh -o BatchMode=yes pi@192.168.0.1 "pgrep -f raspberry_pi_sensor && echo 'Sensor running!' || echo 'Sensor NOT running'"
ssh -o BatchMode=yes pi@192.168.0.1 "tail -15 ~/fridge-observer/sensor.log"

echo.
echo ========================================
echo  Deployment Complete
echo ========================================
echo.
echo Check the log above for any errors.
echo The door is currently OPEN - close it to trigger capture.
echo.
pause
