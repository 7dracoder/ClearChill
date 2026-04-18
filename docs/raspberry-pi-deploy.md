# Raspberry Pi Deployment Guide

This guide covers deploying Fridge Observer on a Raspberry Pi 4 running Raspberry Pi OS (64-bit).

---

## 1. Initial Pi Setup

```bash
# Update the system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11+ and pip
sudo apt install -y python3 python3-pip python3-venv git

# Install Mosquitto MQTT broker
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Install nginx
sudo apt install -y nginx
```

---

## 2. Clone the Repository

```bash
cd /home/pi
git clone https://github.com/your-username/fridge-observer.git
cd fridge-observer
```

---

## 3. Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 4. Environment Variables

```bash
cp .env.example .env
nano .env
```

Fill in your API keys:

```env
K2_API_KEY=your-k2-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here
FRIDGE_DB_PATH=/home/pi/fridge-observer/fridge.db
HOST=0.0.0.0
PORT=8000
```

---

## 5. Test the Server

```bash
source .venv/bin/activate
python -m fridge_observer.main
```

Open `http://<pi-ip>:8000` on your phone or laptop. If it works, stop the server (`Ctrl+C`) and proceed to systemd setup.

---

## 6. systemd Services

Copy the service files and enable them:

```bash
sudo cp systemd/fridge-api.service /etc/systemd/system/
sudo cp systemd/fridge-sensor.service /etc/systemd/system/
sudo cp systemd/fridge-vision.service /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable fridge-api fridge-sensor fridge-vision
sudo systemctl start fridge-api fridge-sensor fridge-vision
```

Check status:

```bash
sudo systemctl status fridge-api
sudo journalctl -u fridge-api -f   # live logs
```

---

## 7. nginx Reverse Proxy

```bash
sudo cp nginx/fridge-observer.conf /etc/nginx/sites-available/fridge-observer
sudo ln -s /etc/nginx/sites-available/fridge-observer /etc/nginx/sites-enabled/
sudo nginx -t   # test config
sudo systemctl reload nginx
```

The app is now accessible at `http://<pi-ip>` (port 80, no port number needed).

---

## 8. Find Your Pi's IP Address

```bash
hostname -I
```

Or check your router's connected devices list. The web app will be at `http://<that-ip>`.

**Tip:** Set a static IP in your router's DHCP settings so the address never changes.

---

## 9. Auto-start on Boot

All services are already enabled via systemd. They will start automatically when the Pi boots.

To verify:

```bash
sudo reboot
# After reboot:
sudo systemctl status fridge-api fridge-sensor fridge-vision
```

---

## 10. Updating the App

```bash
cd /home/pi/fridge-observer
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart fridge-api fridge-sensor fridge-vision
```

---

## Troubleshooting

| Issue | Solution |
|---|---|
| Web app not loading | Check `sudo systemctl status fridge-api` and `sudo journalctl -u fridge-api` |
| No sensor data | Check Mosquitto: `mosquitto_sub -t 'fridge/#' -v` |
| Camera not detected | Run `ls /dev/video*` — webcam should appear as `/dev/video0` |
| Database errors | Delete `fridge.db` and restart — it will be recreated |
| Port 8000 in use | Change `PORT=8001` in `.env` and update nginx config |
