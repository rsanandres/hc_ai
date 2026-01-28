import sys
import os
from pathlib import Path
import boto3

# Add root to sys.path
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.env_loader import load_env_recursive
from api.session.store_dynamodb import get_session_store, SessionStore

def test_connection():
    print("Loading environment...")
    load_env_recursive(ROOT_DIR)
    
    endpoint = os.getenv("DDB_ENDPOINT", "http://localhost:8001")
    region = os.getenv("AWS_REGION", "us-east-1")
    print(f"DDB_ENDPOINT: {endpoint}")
    print(f"AWS_REGION: {region}")
    
    print("\nInitializing SessionStore...")
    try:
        # We use build_store_from_env to avoid caching if we run this multiple times in same process context (unlikely here but good practice)
        # Actually get_session_store is fine
        store = get_session_store()
        print(f"Store initialized. Tables: {store.turns_table_name}, {store.summary_table_name}")
        
        print("\nChecking tables...")
        try:
            store.ensure_tables()
            print("✅ ensure_tables() completed")
        except Exception as e:
            print(f"❌ ensure_tables() failed: {e}")
            import traceback
            traceback.print_exc()
            return

        print("\nTesting write...")
        try:
            store.update_summary("test_debug_session", {"name": "test_session"}, user_id="debug_user")
            print("✅ update_summary() completed")
        except Exception as e:
            print(f"❌ update_summary() failed: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_connection()
