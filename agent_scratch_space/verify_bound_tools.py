import asyncio
import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from api.agent.graph import get_agent

# Only testing tools confirmed to be in _get_researcher_agent
TEST_CASES = [
    {
        "category": "Retrieval",
        "prompt": "Search patient records for 'hypertension' history.",
        "expected_tool": "search_patient_records"
    },
    {
        "category": "Retrieval",
        "prompt": "Find 'chest pain' in the clinical notes.",
        "expected_tool": "search_clinical_notes"
    },
    {
        "category": "Timeline",
        "prompt": "Get the complete timeline of events for this patient.",
        "expected_tool": "get_patient_timeline"
    },
    {
        "category": "Medication Safety",
        "prompt": "Check for interactions between Warfarin and Aspirin.",
        "expected_tool": "cross_reference_meds"
    },
    {
        "category": "Terminology",
        "prompt": "Search for the ICD-10 code for 'Type 2 Diabetes'.",
        "expected_tool": "search_icd10"
    },
    {
        "category": "Calculation",
        "prompt": "Calculate 150 divided by 3.",
        "expected_tool": "calculate"
    },
    {
        "category": "Utility",
        "prompt": "What is the current date?",
        "expected_tool": "get_current_date"
    }
]

async def run_tests():
    print("Initializing Agent...")
    agent = get_agent()
    
    results = []
    
    for case in TEST_CASES:
        print(f"\n--- Testing {case['category']}: '{case['prompt']}' ---")
        state = {
            "query": case["prompt"],
            "session_id": "test-session-bound-" + datetime.now().strftime("%H%M%S"),
            "patient_id": "f1d2d1e2-4a03-43cb-8f06-f68c90e96cc8" # Dummy valid UUID
        }
        
        try:
            # Run agent
            response = await agent.ainvoke(state)
            
            tools_called = response.get("tools_called", [])
            final_response = response.get("final_response", "")
            
            success = case["expected_tool"] in tools_called
            
            status = "✅ PASS" if success else "❌ FAIL"
            
            print(f"Result: {status}")
            print(f"Tools Called: {tools_called}")
            print(f"Response Preview: {final_response[:100]}...")
            
            results.append({
                "prompt": case["prompt"],
                "expected": case["expected_tool"],
                "calls": tools_called,
                "status": status,
                "response": final_response
            })
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results.append({
                "prompt": case["prompt"],
                "expected": case["expected_tool"],
                "calls": [],
                "status": "ERROR",
                "response": str(e)
            })

    # Summary
    print("\n" + "="*50)
    print("BOUND TOOL VERIFICATION SUMMARY")
    print("="*50)
    passed = 0
    for res in results:
        if res['status'] == "✅ PASS":
            passed += 1
        print(f"[{res['status']}] Expected: {res['expected']} | Called: {res['calls']}")
    
    print(f"\nTotal: {passed}/{len(results)} Passed")

if __name__ == "__main__":
    asyncio.run(run_tests())
