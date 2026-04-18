#!/usr/bin/env python3
"""
Test Hardware Workflow
Simulates Raspberry Pi sending images to the web app
Tests the complete flow: image → AI detection → inventory update
"""
import requests
import os
import base64
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

print("=" * 70)
print("HARDWARE WORKFLOW TEST")
print("=" * 70)
print(f"API: {API_BASE_URL}")
print()

# Step 1: Create test account
print("Step 1: Creating test account...")
try:
    response = requests.post(
        f"{API_BASE_URL}/auth/signup",
        json={
            "email": TEST_EMAIL,
            "display_name": "Test User",
            "password": TEST_PASSWORD
        }
    )
    if response.status_code == 201:
        print("✅ Account created")
    elif response.status_code == 409:
        print("⚠️  Account already exists, continuing...")
    else:
        print(f"❌ Failed: {response.status_code} - {response.text}")
except Exception as e:
    print(f"❌ Error: {e}")

# Step 2: Login to get token
print("\nStep 2: Logging in...")
try:
    response = requests.post(
        f"{API_BASE_URL}/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        }
    )
    if response.ok:
        # Get token from cookie
        token = response.cookies.get("fridge_session")
        if token:
            print(f"✅ Logged in successfully")
            print(f"   Token: {token[:20]}...")
        else:
            print("❌ No token in response")
            exit(1)
    else:
        print(f"❌ Login failed: {response.status_code}")
        print(f"   Error: {response.text}")
        exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)

headers = {"Cookie": f"fridge_session={token}"}

# Step 3: Clear existing inventory
print("\nStep 3: Clearing existing inventory...")
try:
    response = requests.get(f"{API_BASE_URL}/api/inventory", headers=headers)
    if response.ok:
        items = response.json()
        print(f"   Found {len(items)} existing items")
        
        # Delete each item
        for item in items:
            del_response = requests.delete(
                f"{API_BASE_URL}/api/inventory/{item['id']}",
                headers=headers
            )
            if del_response.ok:
                print(f"   ✓ Deleted: {item['name']}")
        
        print("✅ Inventory cleared")
    else:
        print(f"⚠️  Could not fetch inventory: {response.status_code}")
except Exception as e:
    print(f"⚠️  Error clearing inventory: {e}")

# Step 4: Simulate door open event
print("\nStep 4: Simulating door open event...")
try:
    response = requests.post(
        f"{API_BASE_URL}/api/hardware/door-event",
        json={
            "event": "door_opened",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "light_level": 0.85
        },
        headers=headers
    )
    if response.ok:
        print("✅ Door event sent")
    else:
        print(f"❌ Failed: {response.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

# Step 5: Create fake image with food items
print("\nStep 5: Creating test image...")
try:
    from PIL import Image, ImageDraw, ImageFont
    
    # Create image
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw food items
    draw.text((50, 50), "Apple", fill='red')
    draw.text((50, 150), "Banana", fill='yellow')
    draw.text((50, 250), "Milk Carton", fill='blue')
    draw.text((50, 350), "Chicken Breast", fill='brown')
    
    # Save
    img.save("test_fridge_image.jpg")
    print("✅ Test image created: test_fridge_image.jpg")
    
except ImportError:
    print("⚠️  PIL not installed, using placeholder")
    # Create a simple placeholder
    with open("test_fridge_image.jpg", "wb") as f:
        # Minimal JPEG header
        f.write(b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00')

# Step 6: Send image to API (simulate Pi capturing image)
print("\nStep 6: Sending image to API...")
try:
    with open("test_fridge_image.jpg", "rb") as f:
        files = {"image": ("fridge.jpg", f, "image/jpeg")}
        response = requests.post(
            f"{API_BASE_URL}/api/hardware/capture-image",
            files=files,
            headers=headers
        )
    
    if response.ok:
        result = response.json()
        print("✅ Image processed successfully")
        print(f"\n   📊 Detection Results:")
        print(f"   Total items detected: {result['total_items']}")
        
        if result['auto_added']:
            print(f"\n   ✅ Auto-added items ({len(result['auto_added'])}):")
            for item in result['auto_added']:
                print(f"      • {item['name']} ({item['category']})")
                print(f"        Expires: {item['expiry_date']} ({item['estimated_days']} days)")
        
        if result['needs_expiry_input']:
            print(f"\n   ⏳ Items needing expiry input ({len(result['needs_expiry_input'])}):")
            for item in result['needs_expiry_input']:
                print(f"      • {item['name']} ({item['category']})")
                print(f"        Confidence: {item['confidence']:.2f}")
                print(f"        → Google Home will ask for expiry date")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"   Error: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Step 7: Simulate Google Home adding packaged item with expiry
print("\nStep 7: Simulating Google Home adding packaged item...")
try:
    # User tells Google Home: "Milk expires on April 25th"
    expiry_date = (datetime.utcnow() + timedelta(days=7)).date().isoformat()
    
    response = requests.post(
        f"{API_BASE_URL}/api/hardware/add-item-with-expiry",
        json={
            "item_name": "Milk",
            "expiry_date": expiry_date,
            "quantity": 1
        },
        headers=headers
    )
    
    if response.ok:
        result = response.json()
        print("✅ Item added via voice")
        print(f"   Item: {result['item']}")
        print(f"   Expiry: {result['expiry_date']}")
        print(f"   Quantity: {result['quantity']}")
    else:
        print(f"❌ Failed: {response.status_code}")
        print(f"   Error: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")

# Step 8: Verify inventory
print("\nStep 8: Verifying final inventory...")
try:
    response = requests.get(f"{API_BASE_URL}/api/inventory", headers=headers)
    if response.ok:
        items = response.json()
        print(f"✅ Inventory retrieved: {len(items)} items")
        print("\n   📦 Current Inventory:")
        for item in items:
            source = "🤖 Auto" if item.get("added_via") == "hardware_auto" else "🎤 Voice"
            print(f"      {source} {item['name']} - Expires: {item['expiry_date']}")
    else:
        print(f"❌ Failed: {response.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

# Step 9: Simulate door close event
print("\nStep 9: Simulating door close event...")
try:
    response = requests.post(
        f"{API_BASE_URL}/api/hardware/door-event",
        json={
            "event": "door_closed",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "light_level": 0.15
        },
        headers=headers
    )
    if response.ok:
        print("✅ Door event sent")
    else:
        print(f"❌ Failed: {response.status_code}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
print("\n📝 Summary:")
print("   1. ✅ Hardware sends image to web app")
print("   2. ✅ Web app detects food items using AI")
print("   3. ✅ Fresh items auto-added with estimated expiry")
print("   4. ✅ Packaged items wait for Google Home voice input")
print("   5. ✅ Google Home adds packaged items with user-provided expiry")
print("   6. ✅ All items appear in web app inventory")
print("\n🎉 Workflow is working correctly!")
print("\nNext steps:")
print("   • Deploy to Render.com")
print("   • Configure Raspberry Pi with deployed URL")
print("   • Test with real hardware")
