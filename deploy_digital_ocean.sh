#!/bin/bash
# Quick Deploy Script for Digital Ocean
# Run this on your Digital Ocean droplet after initial setup

set -e  # Exit on error

echo "=========================================="
echo "ClearChill - Digital Ocean Deployment"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running as fridge user
if [ "$USER" != "fridge" ]; then
    echo -e "${RED}Error: Please run as 'fridge' user${NC}"
    echo "Switch user: su - fridge"
    exit 1
fi

# Check if in correct directory
if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}Error: Not in ClearChill directory${NC}"
    echo "cd /home/fridge/ClearChill"
    exit 1
fi

echo -e "${BLUE}Step 1: Pulling latest code...${NC}"
git pull origin main

echo -e "${BLUE}Step 2: Activating virtual environment...${NC}"
source .venv/bin/activate

echo -e "${BLUE}Step 3: Installing dependencies...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q

echo -e "${BLUE}Step 4: Checking .env file...${NC}"
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo "Please create .env file with your configuration"
    echo "See .env.example for reference"
    exit 1
fi

# Check required environment variables
source .env
if [ -z "$GEMINI_API_KEY" ]; then
    echo -e "${RED}Warning: GEMINI_API_KEY not set in .env${NC}"
fi
if [ -z "$REPLICATE_API_TOKEN" ]; then
    echo -e "${RED}Warning: REPLICATE_API_TOKEN not set in .env${NC}"
fi
if [ -z "$SECRET_KEY" ]; then
    echo -e "${RED}Error: SECRET_KEY not set in .env${NC}"
    echo "Generate one with: openssl rand -hex 32"
    exit 1
fi

echo -e "${BLUE}Step 5: Initializing database...${NC}"
python -c "from fridge_observer.db import init_db; import asyncio; asyncio.run(init_db())"

echo -e "${BLUE}Step 6: Testing application...${NC}"
python -c "from fridge_observer.main import app; print('✅ Application imports successfully')"

echo -e "${BLUE}Step 7: Restarting service...${NC}"
sudo systemctl restart fridge-observer

echo -e "${BLUE}Step 8: Checking service status...${NC}"
sleep 2
if sudo systemctl is-active --quiet fridge-observer; then
    echo -e "${GREEN}✅ Service is running!${NC}"
else
    echo -e "${RED}❌ Service failed to start${NC}"
    echo "Check logs: sudo journalctl -u fridge-observer -n 50"
    exit 1
fi

echo ""
echo -e "${GREEN}=========================================="
echo "✅ Deployment Complete!"
echo "==========================================${NC}"
echo ""
echo "Your app is now running!"
echo ""
echo "Check status: sudo systemctl status fridge-observer"
echo "View logs:    sudo journalctl -u fridge-observer -f"
echo "Test API:     curl http://localhost:8000/api/health"
echo ""
