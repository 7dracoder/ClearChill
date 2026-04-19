#!/usr/bin/env python3
"""Remove duplicate items from Supabase"""
import requests
from collections import defaultdict

SUPABASE_URL = "https://tgigfxzozdauhdrovlfe.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRnaWdmeHpvemRhdWhkcm92bGZlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjQ3NzkzNywiZXhwIjoyMDkyMDUzOTM3fQ.GduId4RUDrCGI5hsYUCekGSidQ9zmKJW2YYjWnQ2pd8"
USER_ID = "3d16c0db-5f68-4b44-b579-0111e65e8308"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

# Get all items
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/food_items?user_id=eq.{USER_ID}",
    headers=headers
)

if resp.status_code == 200:
    items = resp.json()
    
    # Group by name
    by_name = defaultdict(list)
    for item in items:
        by_name[item['name']].append(item)
    
    print("Found items:")
    for name, item_list in by_name.items():
        print(f"  {name}: {len(item_list)} copies")
    
    # Keep only one of each, delete the rest
    print("\nCleaning up duplicates...")
    for name, item_list in by_name.items():
        if len(item_list) > 1:
            # Keep the first one, delete the rest
            for item in item_list[1:]:
                resp = requests.delete(
                    f"{SUPABASE_URL}/rest/v1/food_items?id=eq.{item['id']}",
                    headers=headers
                )
                if resp.status_code in (200, 204):
                    print(f"  ✓ Deleted duplicate {name} (ID: {item['id']})")
    
    print("\nDone! Checking final state...")
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/food_items?user_id=eq.{USER_ID}",
        headers=headers
    )
    items = resp.json()
    print(f"\nFinal count: {len(items)} unique items")
    for item in items:
        print(f"  • {item['name']} - {item['category']}")
