# Hardware Setup Guide

## Components

| Component | Model | Purpose |
|---|---|---|
| Single-board computer | Raspberry Pi 4 (4GB+ recommended) | Runs all software |
| Camera | Logitech C920 or similar USB webcam | Captures fridge contents |
| Sensor | SenseCAP Indicator D1 | Temperature, humidity, light (door detection) |
| Voice | Amazon Echo Dot (3rd gen or later) | Voice alerts via Alexa |
| Mounting | Strong magnets or adhesive mount | Attaches camera to fridge side |

---

## Camera Placement

The Logitech webcam mounts on the **side of the fridge**, pointing inward and slightly downward so it can see items being placed on shelves when the door opens.

**Tips:**
- Use a magnetic mount or strong adhesive strip rated for the camera weight
- Angle the camera so it captures the full shelf area visible when the door is open
- Ensure the USB cable has enough slack for the door to open fully
- Test the field of view before permanent mounting — open the door and check the webcam feed

---

## SenseCAP D1 Setup

The SenseCAP Indicator D1 connects to your home WiFi and publishes sensor readings via MQTT.

### 1. Flash the firmware

The D1 needs custom firmware to publish to a local MQTT broker. Use the SenseCAP firmware tool or flash via USB with the provided firmware image.

### 2. Configure WiFi and MQTT

In the SenseCAP configuration portal:
- **WiFi SSID**: your home network
- **WiFi Password**: your network password
- **MQTT Broker**: `<raspberry-pi-ip>` (e.g. `192.168.1.100`)
- **MQTT Port**: `1883`
- **MQTT Topics**:
  - Temperature → `fridge/sensor/temperature`
  - Humidity → `fridge/sensor/humidity`
  - Light → `fridge/sensor/light`

### 3. Sensor placement

- Place the D1 **inside the fridge** near the top shelf
- The light sensor detects the fridge interior light turning on (door open)
- The temperature sensor monitors fridge temperature
- Ensure the D1 has WiFi signal inside the fridge (most modern fridges allow this)

### 4. Light threshold calibration

The default light threshold for door detection is **50 lux**. Adjust in `fridge_observer/sensor_service.py` if needed:

```python
LIGHT_THRESHOLD_LUX = 50  # lux — above this = door open
```

---

## Raspberry Pi Wiring

The Pi connects to:
- **Logitech Webcam** — USB port
- **Home WiFi** — for SenseCAP D1 MQTT and web app access
- **Power** — standard USB-C power supply (5V 3A minimum)

No GPIO wiring is required — all sensors communicate over WiFi/MQTT.

---

## Network Setup

All devices must be on the **same WiFi network**:

```
Home WiFi Router
├── Raspberry Pi (static IP recommended, e.g. 192.168.1.100)
├── SenseCAP D1 (connects to Pi's MQTT broker)
├── Amazon Echo Dot (connects to Alexa cloud)
└── Your phone/laptop (accesses web app at http://192.168.1.100:8000)
```

**Recommended:** Assign a static IP to the Raspberry Pi via your router's DHCP settings so the web app URL never changes.
