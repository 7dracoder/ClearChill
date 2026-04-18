# 🧊 Fridge Observer

A retrofit smart fridge monitoring system that reduces food waste — without buying a new fridge.

Mount a camera on the side of your fridge, connect a sensor, and get a real-time web app that tracks what's inside, warns you before things expire, and suggests recipes using what you have.

---

## ✨ Features

- **Automatic inventory tracking** — camera detects items going in and out when the fridge door opens
- **Expiry date tracking** — auto-estimates shelf life by category; prompts manual entry for packaged goods
- **Recipe suggestions** — ranked by an Expiry Urgency Score (uses items expiring soonest first)
- **Real-time web app** — WebSocket-powered, updates instantly on any device on your home WiFi
- **AI assistant** — powered by K2-Think for smart Q&A, recipe ideas, and storage tips
- **Gemini Vision** — identify food items from photos
- **Temperature monitoring** — alerts when fridge/freezer goes above safe thresholds
- **Shopping list integration** — auto-adds depleted items via webhook
- **Echo Dot / Alexa** — voice alerts and "what's in my fridge?" queries
- **Zero-waste streak** — gamified weekly waste tracking

---

## 🛠 Hardware

| Component | Purpose |
|---|---|
| Raspberry Pi 4 | Central processing unit, runs everything |
| Logitech Webcam | USB camera mounted on fridge side via magnet |
| SenseCAP D1 | Temperature, humidity, and light sensor (door detection) |
| Amazon Echo Dot | Voice alerts via Alexa |

---

## 🏗 Architecture

```
Raspberry Pi (home WiFi)
├── FastAPI server          :8000  — REST API + WebSocket + static files
├── Alexa skill endpoint    :5000  — Flask + ASK SDK
├── Mosquitto MQTT broker   :1883  — receives SenseCAP D1 sensor data
├── Sensor service                 — door events + temperature monitoring
├── Vision processor               — webcam capture + food identification
└── SQLite database                — fridge.db (WAL mode)
```

Browser connects to `http://<pi-ip>:8000` over local WiFi. WebSocket pushes live inventory updates.

---

## 🚀 Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/your-username/fridge-observer.git
cd fridge-observer
```

### 2. Create a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** Requires Python 3.11+. Tested on Python 3.13 and 3.14.

### 4. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```env
K2_API_KEY=your-k2-api-key-here
GEMINI_API_KEY=your-gemini-api-key-here
```

- **K2-Think API** — get your key at [k2think.ai](https://k2think.ai) (powers the AI assistant)
- **Gemini API** — get your key at [Google AI Studio](https://aistudio.google.com) (powers image food identification)

### 5. Run the server

```bash
python -m fridge_observer.main
```

Open **http://localhost:8000** in your browser.

The database (`fridge.db`) and all tables are created automatically on first run. Sample recipes are seeded automatically.

---

## 📁 Project Structure

```
fridge-observer/
├── fridge_observer/           # Python backend package
│   ├── main.py                # FastAPI app entry point
│   ├── db.py                  # SQLite async database layer
│   ├── models.py              # Pydantic data models
│   ├── config.py              # Settings loaded from DB
│   ├── ai_client.py           # K2-Think + Gemini API clients
│   ├── ws_manager.py          # WebSocket connection manager
│   ├── schema.sql             # Database schema (8 tables)
│   ├── seed_settings.py       # Default settings seed
│   ├── seed_recipes.py        # Sample recipe seed data (17 recipes)
│   └── routers/
│       ├── inventory.py       # GET/POST/PATCH/DELETE /api/inventory
│       ├── recipes.py         # /api/recipes + favorites + made-this
│       ├── notifications.py   # Activity log, waste report, streak
│       ├── settings.py        # /api/settings
│       └── ai.py              # /api/ai/* (K2 + Gemini endpoints)
│
├── static/                    # Frontend (vanilla HTML/CSS/JS)
│   ├── index.html             # Single-page app shell
│   ├── css/
│   │   ├── main.css           # Design system, CSS variables, typography
│   │   ├── layout.css         # Sidebar + mobile tab bar
│   │   ├── components.css     # Reusable UI components
│   │   ├── inventory.css      # Inventory dashboard styles
│   │   ├── recipes.css        # Recipe section styles
│   │   ├── notifications.css  # Activity log + waste report styles
│   │   ├── settings.css       # Settings page styles
│   │   └── ai-assistant.css   # AI chat panel styles
│   └── js/
│       ├── app.js             # App entry point, navigation, WebSocket wiring
│       ├── ws-client.js       # WebSocket client with exponential backoff
│       ├── inventory.js       # Inventory dashboard logic
│       ├── recipes.js         # Recipe section logic
│       ├── notifications.js   # Notifications + history logic
│       ├── settings.js        # Settings form logic
│       └── ai-assistant.js    # AI chat panel (K2 streaming + Gemini vision)
│
├── tests/                     # Test suite
│   └── __init__.py
│
├── docs/                      # Documentation
│   ├── hardware-setup.md      # Hardware wiring and sensor setup
│   ├── raspberry-pi-deploy.md # Deploying to Raspberry Pi
│   └── alexa-skill-setup.md   # Setting up the Alexa skill
│
├── systemd/                   # systemd service files (Raspberry Pi)
├── nginx/                     # nginx reverse proxy config
│
├── .env.example               # Environment variable template
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 🌐 API Reference

The full interactive API docs are available at **http://localhost:8000/docs** when the server is running.

### Inventory
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/inventory` | List all items (supports filter/sort query params) |
| POST | `/api/inventory` | Add a new item |
| PATCH | `/api/inventory/{id}` | Update an item |
| DELETE | `/api/inventory/{id}` | Remove an item |

### Recipes
| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/recipes` | Get recipes ranked by expiry urgency |
| POST | `/api/recipes/{id}/favorite` | Favorite a recipe |
| DELETE | `/api/recipes/{id}/favorite` | Unfavorite a recipe |
| POST | `/api/recipes/{id}/made-this` | Mark as made, remove ingredients |

### AI
| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ai/ask` | General Q&A with inventory context (SSE stream) |
| POST | `/api/ai/suggest-recipes` | AI recipe suggestions (SSE stream) |
| POST | `/api/ai/storage-tip` | Storage tip for a food item |
| POST | `/api/ai/identify` | Identify food from image (Gemini Vision) |
| GET | `/api/ai/inventory-summary` | Smart fridge analysis (SSE stream) |

### WebSocket
Connect to `ws://localhost:8000/ws` for real-time inventory updates.

Message types pushed from server:
- `inventory_update` — full inventory state after any change
- `notification` — spoilage alerts, temperature warnings
- `temperature_update` — live sensor readings

---

## 🎨 Design System

| Token | Value | Usage |
|---|---|---|
| `--color-bg` | `#FAFAF8` | Page background |
| `--color-accent` | `#4A7C59` | Sage green, primary actions |
| `--color-ok` | `#3D9970` | Fresh items |
| `--color-warning` | `#E8A838` | Expiring soon |
| `--color-expired` | `#D94F3D` | Expired items |

Fonts: **Inter** (UI) + **JetBrains Mono** (timestamps, temperatures)

---

## 🔧 Development

### Running tests

```bash
pytest tests/
```

### Environment variables

| Variable | Required | Description |
|---|---|---|
| `K2_API_KEY` | Yes (for AI) | K2-Think API key |
| `GEMINI_API_KEY` | Yes (for vision) | Google Gemini API key |
| `FRIDGE_DB_PATH` | No | SQLite DB path (default: `fridge.db`) |
| `HOST` | No | Server host (default: `0.0.0.0`) |
| `PORT` | No | Server port (default: `8000`) |

---

## 🍓 Raspberry Pi Deployment

See [docs/raspberry-pi-deploy.md](docs/raspberry-pi-deploy.md) for full instructions including:
- Setting up the Python environment
- Configuring systemd services for auto-start
- Setting up nginx as a reverse proxy
- Connecting the SenseCAP D1 via MQTT

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgements

- [K2-Think](https://k2think.ai) — reasoning AI model
- [Google Gemini](https://deepmind.google/technologies/gemini/) — vision model for food identification
- [FastAPI](https://fastapi.tiangolo.com) — async Python web framework
- [SenseCAP](https://www.seeedstudio.com/SenseCAP-Indicator-D1-p-5643.html) — IoT sensor platform
