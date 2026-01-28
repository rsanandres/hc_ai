import os
import boto3
from api.session.store_dynamodb import get_session_store
from boto3.dynamodb.conditions import Key

# Set env vars
os.environ["AWS_REGION"] = "us-east-1"
os.environ["DDB_ENDPOINT"] = "http://localhost:8001"

def cleanup_sessions(user_id: str, limit: int = 20):
    print(f"Cleaning up sessions for {user_id}. Maintaining max {limit}...")
    
    try:
        store = get_session_store()
        table = store.summary_table
        
        # 1. Fetch all sessions
        print("Fetching sessions...")
        sessions = []
        start_key = None
        
        while True:
            kwargs = {
                "IndexName": "user_id-index",
                "KeyConditionExpression": Key("user_id").eq(user_id),
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
                
            resp = table.query(**kwargs)
            sessions.extend(resp.get("Items", []))
            
            start_key = resp.get("LastEvaluatedKey")
            if not start_key:
                break
                
        print(f"Found {len(sessions)} total sessions.")
        
        if len(sessions) <= limit:
            print("Session count is within limit. No action needed.")
            return

        # 2. Sort by last_activity descending (newest first)
        # Handle cases where last_activity might be missing
        sessions.sort(key=lambda x: x.get('last_activity', ''), reverse=True)
        
        # 3. Identify sessions to delete (all after the first 'limit' items)
        sessions_to_delete = sessions[limit:]
        print(f"Deleting {len(sessions_to_delete)} old sessions...")
        
        # 4. Delete them
        count = 0
        for session in sessions_to_delete:
            pk = session['session_id']
            sk = session['sk']
            
            # Delete summary
            table.delete_item(Key={'session_id': pk, 'sk': sk})
            
            # Also clean up turns table? 
            # The store.clear_session method does this, but importing it might be tricky if we want to batch this.
            # For now, let's just delete the summary so it disappears from the UI. 
            # Ideally we should use store.clear_session(pk) but that fetches first.
            # Let's use the store's clear_session to be thorough, even if slower.
            
            store.clear_session(pk)
            
            count += 1
            if count % 5 == 0:
                print(f"Deleted {count}/{len(sessions_to_delete)}...")
                
        print(f"Cleanup complete! Deleted {count} sessions. {limit} sessions remain.")

    except Exception as e:
        print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    cleanup_sessions("raph", 0)
