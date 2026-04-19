#!/usr/bin/env python3
"""
Simple proxy server - Pi sends data here, PC forwards to Supabase
Run this on your PC: python supabase_proxy.py
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests
import uvicorn

app = FastAPI()

SUPABASE_URL = "https://tgigfxzozdauhdrovlfe.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRnaWdmeHpvemRhdWhkcm92bGZlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjQ3NzkzNywiZXhwIjoyMDkyMDUzOTM3fQ.GduId4RUDrCGI5hsYUCekGSidQ9zmKJW2YYjWnQ2pd8"

@app.post("/proxy/imagga")
async def proxy_imagga(request: Request):
    """Proxy image recognition requests from Pi to Imagga"""
    import base64
    
    data = await request.json()
    image_b64 = data.get("image")
    
    if not image_b64:
        return JSONResponse(content={"error": "No image provided"}, status_code=400)
    
    # Decode image
    image_bytes = base64.b64decode(image_b64)
    
    IMAGGA_API_KEY = "acc_1295516e145383e"
    IMAGGA_API_SECRET = "4381b8e24fec3008a6e73abe449d7f69"
    
    try:
        files = {'image': ('image.jpg', image_bytes, 'image/jpeg')}
        resp = requests.post(
            "https://api.imagga.com/v2/tags",
            auth=(IMAGGA_API_KEY, IMAGGA_API_SECRET),
            files=files,
            timeout=30
        )
        
        if resp.status_code == 200:
            return JSONResponse(content=resp.json())
        else:
            return JSONResponse(content={"error": resp.text}, status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/proxy/food_items")
async def proxy_food_items(request: Request):
    """Proxy requests from Pi to Supabase"""
    data = await request.json()
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/food_items",
            json=data,
            headers=headers,
            timeout=10
        )
        return JSONResponse(content=resp.json() if resp.status_code in (200, 201) else {"error": resp.text}, status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/health")
async def health():
    return {"status": "ok", "proxy": "supabase"}

if __name__ == "__main__":
    print("=" * 60)
    print("Supabase Proxy Server")
    print("=" * 60)
    print("\nListening on http://0.0.0.0:8001")
    print("Pi will send data here, PC forwards to Supabase\n")
    uvicorn.run(app, host="0.0.0.0", port=8001)
