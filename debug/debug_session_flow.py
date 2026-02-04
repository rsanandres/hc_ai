#!/usr/bin/env python3
"""Debug script to verify session flow end-to-end.

This script tests:
1. DynamoDB connection (via Docker)
2. Session creation
3. Turn appending
4. Turn retrieval
5. History loading (as used by the agent)

Usage:
    python debug/debug_session_flow.py
"""
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set environment variables for local DynamoDB
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("DDB_ENDPOINT", "http://localhost:8001")

def test_session_flow():
    print("=" * 60)
    print("Session Flow Debug Script")
    print("=" * 60)
    
    # Step 1: Import and connect
    print("\n[1] Connecting to DynamoDB...")
    try:
        from api.session.store_dynamodb import get_session_store
        store = get_session_store()
        endpoint = store.resource.meta.client.meta.endpoint_url
        print(f"    ✓ Connected to: {endpoint}")
    except Exception as e:
        print(f"    ✗ Failed to connect: {e}")
        print("\n    Make sure DynamoDB is running in Docker:")
        print("    docker ps | grep dynamodb")
        return

    test_session_id = "debug-test-session-001"
    
    # Step 2: Create test session
    print(f"\n[2] Creating test session: {test_session_id}")
    try:
        store.update_summary(
            session_id=test_session_id, 
            summary={"name": "Debug Test Session"},
            user_id="debug_user"
        )
        print("    ✓ Session created")
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        return

    # Step 3: Append user turn
    print("\n[3] Appending user turn...")
    try:
        store.append_turn(
            session_id=test_session_id,
            role="user",
            text="Hello, this is a test message from the debug script.",
            meta={"source": "debug_script"},
            patient_id="test-patient-001"  # Add patient_id for filtering test
        )
        print("    ✓ User turn appended (with patient_id)")
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        return

    # Step 4: Append assistant turn
    print("\n[4] Appending assistant turn...")
    try:
        store.append_turn(
            session_id=test_session_id,
            role="assistant",
            text="Hello! I'm the assistant. How can I help you today?",
            meta={"tool_calls": [], "sources": []},
            patient_id="test-patient-001"  # Same patient_id
        )
        print("    ✓ Assistant turn appended (with patient_id)")
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        return

    # Step 5: Retrieve turns
    print("\n[5] Retrieving recent turns...")
    try:
        turns = store.get_recent(test_session_id, limit=10)
        print(f"    ✓ Found {len(turns)} turns:")
        for i, turn in enumerate(turns):
            role = turn.get('role', 'unknown')
            text = turn.get('text', '')[:50]
            ts = turn.get('turn_ts', 'N/A')
            print(f"      [{i+1}] {role}: {text}... (ts: {ts[:19]})")
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        return

    # Step 6: Test agent history loading (with patient filter)
    print("\n[6] Testing agent history loading (with patient_id filter)...")
    try:
        from api.agent.multi_agent_graph import _load_conversation_history
        history = _load_conversation_history(test_session_id, patient_id="test-patient-001", limit=10)
        print(f"    ✓ Loaded {len(history)} messages for agent context")
        for i, msg in enumerate(history):
            content = str(msg.content)[:50]
            msg_type = type(msg).__name__
            print(f"      [{i+1}] {msg_type}: {content}...")
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        import traceback
        traceback.print_exc()

    # Step 7: Cleanup
    print("\n[7] Cleaning up test session...")
    try:
        store.clear_session(test_session_id)
        print("    ✓ Test session deleted")
    except Exception as e:
        print(f"    ⚠ Cleanup failed (non-critical): {e}")

    print("\n" + "=" * 60)
    print("Debug complete!")
    print("=" * 60)


def list_all_sessions():
    """List all sessions in DynamoDB (useful for debugging)."""
    print("\n" + "=" * 60)
    print("Listing All Sessions")
    print("=" * 60)
    
    try:
        from api.session.store_dynamodb import get_session_store
        store = get_session_store()
        
        # Scan summary table
        resp = store.summary_table.scan()
        items = resp.get("Items", [])
        
        print(f"\nTotal items in summary table: {len(items)}")
        
        user_sessions = {}
        for item in items:
            if item.get("sk") == "summary":
                uid = item.get("user_id", "UNKNOWN")
                if uid not in user_sessions:
                    user_sessions[uid] = []
                user_sessions[uid].append({
                    "session_id": item.get("session_id"),
                    "name": item.get("name", "Unnamed"),
                    "last_activity": item.get("last_activity", "N/A")
                })
        
        print("\nSessions by User:")
        for uid, sessions in user_sessions.items():
            print(f"\n  User: {uid} ({len(sessions)} sessions)")
            for sess in sessions[:5]:  # Show max 5 per user
                sid = sess['session_id'][:8] if sess.get('session_id') else 'N/A'
                name = (sess.get('name') or 'Unnamed')[:30]
                print(f"    - {sid}... : {name}")
                
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Debug session flow")
    parser.add_argument("--list", action="store_true", help="List all sessions")
    args = parser.parse_args()
    
    if args.list:
        list_all_sessions()
    else:
        test_session_flow()
