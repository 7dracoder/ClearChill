#!/usr/bin/env python3
"""Check what users exist in Supabase"""
import requests

SUPABASE_URL = "https://tgigfxzozdauhdrovlfe.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRnaWdmeHpvemRhdWhkcm92bGZlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjQ3NzkzNywiZXhwIjoyMDkyMDUzOTM3fQ.GduId4RUDrCGI5hsYUCekGSidQ9zmKJW2YYjWnQ2pd8"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

# Check auth.users table
print("Checking Supabase auth.users...")
print("=" * 60)

# Try to get user info from food_items to see what user_id we have
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/food_items?select=user_id&limit=1",
    headers=headers
)

if resp.status_code == 200:
    items = resp.json()
    if items:
        user_id = items[0].get('user_id')
        print(f"Found user_id in food_items: {user_id}")
        print("\nThis is the user account you need to log in with.")
        print("If you don't know the email/password for this account,")
        print("you'll need to create a new account and update the Pi script")
        print("with the new user_id.")
    else:
        print("No items found in food_items table")
else:
    print(f"Error: {resp.status_code} - {resp.text}")
