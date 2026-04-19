#!/usr/bin/env python3
"""
Get your user_id from the web app after logging in.

INSTRUCTIONS:
1. Go to https://clearchill.onrender.com
2. Log in or create a new account
3. Open browser DevTools (F12)
4. Go to Console tab
5. Type: document.cookie
6. Copy the "fridge_session" cookie value
7. Paste it below when prompted
"""
import sys

def decode_jwt(token):
    """Decode JWT without verification"""
    try:
        import base64
        import json
        
        # JWT format: header.payload.signature
        parts = token.split('.')
        if len(parts) != 3:
            return None
        
        # Decode payload (add padding if needed)
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
    except Exception as e:
        print(f"Error decoding token: {e}")
        return None

print("=" * 60)
print("Get Your User ID")
print("=" * 60)
print("\nINSTRUCTIONS:")
print("1. Go to https://clearchill.onrender.com")
print("2. Log in or create a new account")
print("3. Open browser DevTools (F12)")
print("4. Go to Application tab > Cookies")
print("5. Find 'fridge_session' cookie")
print("6. Copy its value")
print("7. Paste it here\n")

token = input("Paste your fridge_session cookie value: ").strip()

if not token:
    print("No token provided!")
    sys.exit(1)

payload = decode_jwt(token)
if payload:
    user_id = payload.get('sub')
    email = payload.get('email')
    
    print("\n" + "=" * 60)
    print("YOUR USER INFO:")
    print("=" * 60)
    print(f"User ID: {user_id}")
    print(f"Email: {email}")
    print("\nUpdate pi/auto_detect_with_sensor.py:")
    print(f'USER_ID = "{user_id}"')
    print("=" * 60)
else:
    print("Failed to decode token. Make sure you copied the full value.")
