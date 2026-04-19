#!/usr/bin/env python3
"""
Try to find the email for user_id 3d16c0db-5f68-4b44-b579-0111e65e8308
"""
import requests

SUPABASE_URL = "https://tgigfxzozdauhdrovlfe.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRnaWdmeHpvemRhdWhkcm92bGZlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3NjQ3NzkzNywiZXhwIjoyMDkyMDUzOTM3fQ.GduId4RUDrCGI5hsYUCekGSidQ9zmKJW2YYjWnQ2pd8"
USER_ID = "3d16c0db-5f68-4b44-b579-0111e65e8308"

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
}

print("=" * 60)
print("Searching for user email...")
print("=" * 60)

# Try to query user_profiles table
print("\n1. Checking user_profiles table...")
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/user_profiles?user_id=eq.{USER_ID}",
    headers=headers
)

if resp.status_code == 200:
    profiles = resp.json()
    if profiles:
        print(f"   Found profile: {profiles[0]}")
    else:
        print("   No profile found")
else:
    print(f"   Error: {resp.status_code}")

# Try to query settings table
print("\n2. Checking settings table...")
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/settings?user_id=eq.{USER_ID}",
    headers=headers
)

if resp.status_code == 200:
    settings = resp.json()
    if settings:
        print(f"   Found settings: {settings[0]}")
    else:
        print("   No settings found")
else:
    print(f"   Error: {resp.status_code}")

# Try to query activity_log table
print("\n3. Checking activity_log table...")
resp = requests.get(
    f"{SUPABASE_URL}/rest/v1/activity_log?user_id=eq.{USER_ID}&limit=1",
    headers=headers
)

if resp.status_code == 200:
    logs = resp.json()
    if logs:
        print(f"   Found activity: {logs[0]}")
    else:
        print("   No activity found")
else:
    print(f"   Error: {resp.status_code}")

print("\n" + "=" * 60)
print("RECOMMENDATION:")
print("=" * 60)
print("Since we can't directly access auth.users table,")
print("the easiest solution is to:")
print("\n1. Create a NEW account at https://clearchill.onrender.com")
print("2. Get your new user_id using: python get_my_user_id.py")
print("3. Update pi/auto_detect_with_sensor.py with your new user_id")
print("4. All future detections will appear in your account!")
print("=" * 60)
