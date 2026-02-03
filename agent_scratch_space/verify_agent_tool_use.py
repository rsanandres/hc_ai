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

TEST_CASES = [
    {
        "category": "Calculators",
        "prompt": "Calculate the BMI for a patient weighing 70kg and 175cm tall.",
        "expected_tool": "calculate_bmi",
        "alt_tool": "calculate" # It might use math
    },
    {
        "category": "Calculators",
        "prompt": "Calculate eGFR for a 50 year old male with creatinine 1.0.",
        "expected_tool": "calculate_gfr",
        "alt_tool": "calculate"
    },
    {
        "category": "FDA Tools",
        "prompt": "Find the FDA drug label for Ibuprofen.",
        "expected_tool": "search_fda_drugs"
    },
    {
        "category": "FDA Tools",
        "prompt": "Are there any current drug shortages for Amoxicillin?",
        "expected_tool": "get_drug_shortages"
    },
    {
        "category": "Terminology",
        "prompt": "Is 'E11.9' a valid ICD-10 code?",
        "expected_tool": "validate_icd10_code" # In Validator
    },
    {
        "category": "Terminology",
        "prompt": "What is the LOINC code 4548-4?",
        "expected_tool": "lookup_loinc" # In Validator
    },
    {
        "category": "Research",
        "prompt": "Search PubMed for recent articles on Ozempic.",
        "expected_tool": "search_pubmed"
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
            "session_id": "test-session-verify-" + datetime.now().strftime("%H%M%S"),
            "patient_id": "f1d2d1e2-4a03-43cb-8f06-f68c90e96cc8" # Dummy valid UUID
        }
        
        try:
            # Run agent
            # Using simple query type logic might route to different graphs, 
            # so we let the classifier decide or default to complex if we set env var.
            # But we test as configured.
            response = await agent.ainvoke(state)
            
            tools_called = response.get("tools_called", [])
            final_response = response.get("final_response", "")
            
            success = case["expected_tool"] in tools_called
            alt_success = case.get("alt_tool") and case.get("alt_tool") in tools_called
            
            status = "✅ PASS" if success else ("⚠️ ALT PASS" if alt_success else "❌ FAIL")
            
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
    print("AGENT TOOL VERIFICATION SUMMARY")
    print("="*50)
    for res in results:
        print(f"[{res['status']}] Expected: {res['expected']} | Called: {res['calls']}")

if __name__ == "__main__":
    asyncio.run(run_tests())
