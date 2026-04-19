#!/usr/bin/env python3
"""
Update the USER_ID in pi/auto_detect_with_sensor.py

Usage:
  python update_user_id.py <new-user-id>

Example:
  python update_user_id.py a1b2c3d4-5678-90ab-cdef-1234567890ab
"""
import sys
import re

if len(sys.argv) != 2:
    print("Usage: python update_user_id.py <new-user-id>")
    print("\nExample:")
    print("  python update_user_id.py a1b2c3d4-5678-90ab-cdef-1234567890ab")
    print("\nTo get your user_id:")
    print("  1. Log in to https://clearchill.onrender.com")
    print("  2. Run: python get_my_user_id.py")
    sys.exit(1)

new_user_id = sys.argv[1].strip()

# Validate UUID format
uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
if not re.match(uuid_pattern, new_user_id, re.IGNORECASE):
    print(f"❌ Invalid user_id format: {new_user_id}")
    print("   Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
    sys.exit(1)

# Read the file
file_path = "pi/auto_detect_with_sensor.py"
try:
    with open(file_path, 'r') as f:
        content = f.read()
except FileNotFoundError:
    print(f"❌ File not found: {file_path}")
    sys.exit(1)

# Find and replace USER_ID
old_pattern = r'USER_ID = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"'
new_line = f'USER_ID = "{new_user_id}"'

if not re.search(old_pattern, content, re.IGNORECASE):
    print("❌ Could not find USER_ID line in file")
    sys.exit(1)

# Get old user_id for display
old_match = re.search(old_pattern, content, re.IGNORECASE)
old_user_id = old_match.group(0).split('"')[1] if old_match else "unknown"

# Replace
new_content = re.sub(old_pattern, new_line, content, flags=re.IGNORECASE)

# Write back
with open(file_path, 'w') as f:
    f.write(new_content)

print("=" * 60)
print("✅ USER_ID Updated Successfully!")
print("=" * 60)
print(f"Old: {old_user_id}")
print(f"New: {new_user_id}")
print("\nNext steps:")
print("1. Copy to Pi:")
print(f"   scp {file_path} pi@172.20.10.5:~/")
print("\n2. On Pi, restart detection:")
print("   python3 auto_detect_with_sensor.py")
print("\n3. Test by opening fridge door!")
print("=" * 60)
