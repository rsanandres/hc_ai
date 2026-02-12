import os
from api.session.store_dynamodb import get_session_store
from boto3.dynamodb.conditions import Key

# Set env vars
os.environ["AWS_REGION"] = "us-east-1"
os.environ["DDB_ENDPOINT"] = "http://localhost:8001"

def migrate_user(old_uid: str, new_uid: str):
    print(f"Starting migration from {old_uid} to {new_uid}...")
    
    try:
        store = get_session_store()
        table = store.summary_table
        
        # 1. Find all sessions for old user
        print("Finding sessions...")
        sessions = []
        start_key = None
        
        while True:
            kwargs = {
                "IndexName": "user_id-index",
                "KeyConditionExpression": Key("user_id").eq(old_uid),
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
                
            resp = table.query(**kwargs)
            sessions.extend(resp.get("Items", []))
            
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break
                
        print(f"Found {len(sessions)} sessions to migrate.")
        
        if not sessions:
            print("No sessions found. Exiting.")
            return

        # 2. Update each session
        count = 0
        # Note: batch_writer doesn't support update_item, only put_item and delete_item.
        # Since we want to update only one field and batch_writer is for put/delete,
        # we will iterate and update individually. It's 36 items, so it's fast enough.
        
        for session in sessions:
            pk = session['session_id']
            sk = session['sk']
            
            table.update_item(
                Key={'session_id': pk, 'sk': sk},
                UpdateExpression="SET user_id = :new_uid",
                ExpressionAttributeValues={':new_uid': new_uid}
            )
            count += 1
            if count % 10 == 0:
                print(f"Migrated {count}/{len(sessions)}...")
                
        print(f"Migration complete! {count} sessions transferred to '{new_uid}'.")

    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate_user("178eb255", "raph")
