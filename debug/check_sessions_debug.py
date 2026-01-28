import os
import boto3
from api.session.store_dynamodb import get_session_store
from boto3.dynamodb.conditions import Key

# Set env vars
os.environ["AWS_REGION"] = "us-east-1"
os.environ["DDB_ENDPOINT"] = "http://localhost:8001"

def check_sessions():
    store = get_session_store()
    table = store.summary_table
    
    for uid in ["raph", "178eb255"]:
        print(f"Checking sessions for '{uid}'...")
        resp = table.query(
            IndexName="user_id-index",
            KeyConditionExpression=Key("user_id").eq(uid)
        )
        items = resp.get("Items", [])
        print(f"User '{uid}' has {len(items)} sessions.")

if __name__ == "__main__":
    check_sessions()
