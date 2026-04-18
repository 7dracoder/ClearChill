# ClearChill

A smart fridge management system that uses AI to automatically track your food inventory and reduce waste.

## What It Does

ClearChill monitors your fridge using a Raspberry Pi with a camera and light sensor. When you open the door, it captures an image, identifies the food items using AI, and updates your inventory automatically. Most items get expiry dates estimated automatically, so you always know what needs to be used soon.

## Features

- Automatic food detection using Google Gemini Vision AI
- Smart expiry date estimation for fresh produce
- Real-time inventory updates via WebSocket
- Web dashboard to view your inventory from anywhere
- Raspberry Pi hardware integration with door sensor and camera
- AI-generated sustainability insights and blueprints
- Optional voice input for packaged items

## Tech Stack

**Backend**: FastAPI, Python 3.11, Supabase (auth + database)
**Frontend**: HTML, CSS, JavaScript
**AI**: Google Gemini Vision, Replicate
**Hardware**: Raspberry Pi 4, OpenCV, GPIO sensors
**Deployment**: Digital Ocean (all-in-one)

## Quick Start

### 1. Clone and Install

```bash
git clone https://github.com/7dracoder/ClearChill.git
cd ClearChill
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and add your API keys:

```bash
cp .env.example .env
nano .env
```

Required:
- `SUPABASE_URL` and `SUPABASE_KEY` - Get from [Supabase](https://supabase.com)
- `GEMINI_API_KEY` - Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
- `REPLICATE_API_TOKEN` - Get from [Replicate](https://replicate.com)
- `SECRET_KEY` - Generate with: `openssl rand -hex 32`

### 3. Run Locally

```bash
python -m uvicorn fridge_observer.main:app --reload
```

Open http://localhost:8000

## Deployment

Deploy everything **FREE** using Render.com in 10 minutes:

```bash
# Follow the deployment guide
cat DEPLOY.md
```

**Cost**: FREE (Render.com free tier + Supabase free tier)

**Note**: Free tier sleeps after 15 min inactivity. First request takes ~30 seconds to wake up.

## Hardware Setup

You'll need:
- Raspberry Pi 4
- USB webcam (1080p recommended)
- Photoresistor and 10µF capacitor for door detection
- Protoboard and jumper wires

Total cost: $70-110. Setup takes about 30 minutes.

See `RASPBERRY_PI_SETUP.md` for detailed instructions.

## How It Works

**Complete Workflow:**

1. **You open your fridge door**
2. **Raspberry Pi detects door opening** (light sensor)
3. **Pi captures image** (webcam after 2 seconds)
4. **Pi sends image to web app** (via WiFi)
5. **Web app detects food items** (Gemini AI Vision)
6. **Web app determines item type**:
   - **Fresh items** (fruits, vegetables, meat) → Auto-estimates expiry date → Adds to inventory
   - **Packaged items** (milk, yogurt, etc.) → Waits for expiry date
7. **For packaged items**: Google Home asks "When does the milk expire?"
8. **You respond**: "April 25th"
9. **Google Home sends expiry to web app** → Adds to inventory
10. **Web app updates in real-time** (WebSocket)

**Time**: 5-6 seconds from door open to seeing items in your app

**All detection happens in the web app, not on the Pi!**

## Testing Hardware Integration

Test the complete workflow locally:

```bash
# Start the server
python -m uvicorn fridge_observer.main:app --reload

# In another terminal, run the test
python test_hardware_workflow.py
```

This simulates:
- Pi sending images
- AI detecting food items
- Auto-adding fresh items
- Google Home adding packaged items
- Real-time inventory updates

## Documentation

- `DEPLOY.md` - Free deployment guide for Render.com
- `RASPBERRY_PI_CONFIG.md` - Hardware setup and WiFi configuration
- `.env.example` - Environment variables reference

## License

MIT License - see LICENSE file

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
