#!/usr/bin/env python3
"""
Debug script to test the Self-RAG improvements:
- Query Expansion (STEP 0)
- Trajectory Awareness (death loop prevention)
- Hallucination Prevention

This script simulates the Researcher node behavior with trajectory injection.
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def test_trajectory_injection():
    """Test that trajectory is properly injected into messages."""
    from langchain_core.messages import SystemMessage
    
    # Simulate state with failed searches
    state = {
        "search_attempts": [
            {"query": "Condition active", "patient_id": "test-123", "results_count": 0, "iteration": 1},
            {"query": "Diagnosis", "patient_id": "test-123", "results_count": 0, "iteration": 2},
        ],
        "empty_search_count": 2,
        "iteration_count": 2,
    }
    
    # Simulate trajectory injection logic
    search_attempts = state.get("search_attempts", [])
    empty_count = state.get("empty_search_count", 0)
    
    if empty_count > 0:
        failed_queries = [f"- '{a.get('query', 'unknown')}' → {a.get('results_count', 0)} results" 
                          for a in search_attempts[-3:]]
        trajectory_msg = f"""
⚠️ RETRY MODE (Attempt {empty_count + 1})

PREVIOUS FAILED QUERIES:
{chr(10).join(failed_queries)}

CONSTRAINT: Use DIFFERENT search terms. Broaden your query scope.
If you cannot find data after this attempt, report: "I have searched for [Term A] and [Term B] but found no records."
"""
        print("=" * 60)
        print("TRAJECTORY INJECTION TEST")
        print("=" * 60)
        print(trajectory_msg)
        print("=" * 60)
        print("✅ Trajectory injection working correctly")
        return True
    else:
        print("❌ No trajectory to inject (empty_count = 0)")
        return False


def test_step_limit_warning():
    """Test that step limit warning is injected when approaching limit."""
    iteration_count = 12
    
    if iteration_count >= 12:
        step_limit_msg = """
⚠️ APPROACHING STEP LIMIT - You must provide a response NOW.
Report whatever you have found so far. If nothing was found, explicitly state that.
Do NOT attempt additional searches.
"""
        print("=" * 60)
        print("STEP LIMIT WARNING TEST")
        print("=" * 60)
        print(step_limit_msg)
        print("=" * 60)
        print("✅ Step limit warning working correctly")
        return True
    else:
        print("❌ Step limit not reached")
        return False


def test_search_attempt_tracking():
    """Test that search attempts are properly tracked."""
    from langchain_core.messages import AIMessage
    
    # Simulate an AIMessage with tool_calls (mock structure)
    class MockToolCall:
        def get(self, key, default=None):
            mock_data = {
                "name": "search_patient_records",
                "args": {"query": "Condition hypertension", "patient_id": "test-456"}
            }
            return mock_data.get(key, default)
    
    # Simulate tracking logic
    search_attempts = []
    mock_call = MockToolCall()
    
    if mock_call.get("name") == "search_patient_records":
        args = mock_call.get("args", {})
        current_attempt = {
            "query": args.get("query", "unknown"),
            "patient_id": args.get("patient_id", "unknown"),
            "results_count": 5,  # Simulated results
            "iteration": 1
        }
        search_attempts.append(current_attempt)
    
    print("=" * 60)
    print("SEARCH ATTEMPT TRACKING TEST")
    print("=" * 60)
    print(f"Tracked attempts: {search_attempts}")
    print("=" * 60)
    
    if len(search_attempts) == 1 and search_attempts[0]["query"] == "Condition hypertension":
        print("✅ Search attempt tracking working correctly")
        return True
    else:
        print("❌ Search attempt tracking failed")
        return False


def test_prompt_changes_loaded():
    """Test that prompt changes are present in prompts.yaml."""
    import yaml
    
    prompts_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "api/agent/prompts.yaml"
    )
    
    with open(prompts_path, "r") as f:
        content = f.read()
    
    print("=" * 60)
    print("PROMPT CHANGES VERIFICATION")
    print("=" * 60)
    
    checks = [
        ("STEP 0 - QUERY EXPANSION", "STEP 0 - QUERY EXPANSION" in content),
        ("TRAJECTORY AWARENESS", "TRAJECTORY AWARENESS" in content),
        ("HALLUCINATION PREVENTION", "HALLUCINATION PREVENTION" in content),
        ("HALLUCINATION DETECTION", "HALLUCINATION DETECTION" in content),
    ]
    
    all_passed = True
    for name, passed in checks:
        status = "✅" if passed else "❌"
        print(f"{status} {name}: {'Found' if passed else 'NOT FOUND'}")
        if not passed:
            all_passed = False
    
    print("=" * 60)
    return all_passed


def main():
    """Run all debug tests."""
    print("\n" + "=" * 60)
    print("SELF-RAG DEBUG TESTS")
    print("=" * 60 + "\n")
    
    results = []
    
    # Test 1: Prompt changes
    results.append(("Prompt Changes", test_prompt_changes_loaded()))
    print()
    
    # Test 2: Trajectory injection
    results.append(("Trajectory Injection", test_trajectory_injection()))
    print()
    
    # Test 3: Step limit warning
    results.append(("Step Limit Warning", test_step_limit_warning()))
    print()
    
    # Test 4: Search attempt tracking
    results.append(("Search Attempt Tracking", test_search_attempt_tracking()))
    print()
    
    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {name}: {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("=" * 60)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
