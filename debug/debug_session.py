import requests
import json
import sys

BASE_URL = "http://localhost:8000"
SESSION_CREATE_URL = f"{BASE_URL}/session/create"

payload = {
    "user_id": "test_debug_user",
    "name": "Debug Session",
    "description": "Created for testing",
    "tags": ["debug"]
}

print(f"Testing POST {SESSION_CREATE_URL}...")
print("-" * 50)

try:
    headers = {'Content-Type': 'application/json'}
    response = requests.post(SESSION_CREATE_URL, json=payload, headers=headers, timeout=10)
    
    status = "✅ OK" if response.status_code == 200 else f"❌ {response.status_code}"
    print(f"Status: {status}")
    print(f"Response: {response.text}")
    
    if response.status_code != 200:
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error: {str(e)}")
    sys.exit(1)
