#!/usr/bin/env python3
"""Check what's in Supabase food_items table"""
import requests

SUPABASE_URL = "https://tgigfxzozdauhdrovlfe.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRnaWdmeHpvemRhdWhkcm92bGZlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjQ3NzkzNywiZXhwIjoyMDkyMDUzOTM3fQ.GduId4RUDrCGI5hsYUCekGSidQ9zmKJW2YYjWnQ2pd8"
USER_ID = "3d16c0db-5f68-4b44-b579-0111e65e8308"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

# Get ALL items first
print("Checking ALL items in food_items table:")
print("=" * 60)
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/food_items?limit=20",
    headers=headers
)

if resp.status_code == 200:
    items = resp.json()
    print(f"Total items: {len(items)}")
    if items:
        for item in items:
            print(f"  • {item['name']} - {item['category']} - user: {item.get('user_id', 'N/A')[:8]}...")
            print(f"    ID: {item.get('id')}, Quantity: {item.get('quantity')}, Expires: {item.get('expiry_date')}")
    else:
        print("  No items found in entire table!")
else:
    print(f"Error: {resp.status_code} - {resp.text}")

# Get items for specific user
print(f"\nItems for user {USER_ID[:8]}...:")
print("=" * 60)
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/food_items?user_id=eq.{USER_ID}&limit=10",
    headers=headers
)

if resp.status_code == 200:
    items = resp.json()
    if items:
        for item in items:
            print(f"  • {item['name']} - {item['category']} - expires: {item.get('expiry_date')}")
            print(f"    ID: {item.get('id')}, Quantity: {item.get('quantity')}")
    else:
        print("  No items found for this user!")
else:
    print(f"Error: {resp.status_code} - {resp.text}")

