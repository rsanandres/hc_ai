import os
import boto3
from api.session.store_dynamodb import get_session_store

# Set env vars to match local dev if needed
os.environ["AWS_REGION"] = "us-east-1"
os.environ["DDB_ENDPOINT"] = "http://localhost:8001"

try:
    store = get_session_store()
    print(f"Connected to DynamoDB at {store.resource.meta.client.meta.endpoint_url}")
    
    # 1. Scan Summary Table
    print("\nScanning Summary Table...")
    resp = store.summary_table.scan()
    items = resp.get("Items", [])
    print(f"Total items in summary table: {len(items)}")
    
    user_counts = {}
    for item in items:
        if item.get("sk") == "summary":
            uid = item.get("user_id", "UNKNOWN")
            user_counts[uid] = user_counts.get(uid, 0) + 1
            
    print("\nSession counts by User ID:")
    for uid, count in user_counts.items():
        print(f"  - {uid}: {count}")

except Exception as e:
    print(f"Error: {e}")
