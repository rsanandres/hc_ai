"""
End-to-end test of Researcher -> Validator agent flow.
Enable with: ENABLE_AGENT_E2E_TESTS=true
"""

from __future__ import annotations

import argparse
import asyncio
import os
from typing import Optional

import pytest

from POC_agent.agent.multi_agent_graph import create_multi_agent_graph


pytestmark = pytest.mark.skipif(
    os.getenv("ENABLE_AGENT_E2E_TESTS", "false").lower() not in {"1", "true", "yes"},
    reason="E2E tests disabled (set ENABLE_AGENT_E2E_TESTS=true)",
)


PREDEFINED_QUERIES = {
    "medication_check": {
        "query": "Patient John Doe (ID: patient-123) is on metformin 500mg twice daily. "
        "He has a GFR of 45. Is this dosage appropriate?",
        "patient_id": "patient-123",
    },
    "drug_interaction": {
        "query": "Can a patient safely take warfarin and aspirin together? "
        "Check for any FDA recalls or adverse events.",
        "patient_id": None,
    },
    "diagnosis_lookup": {
        "query": "What is the ICD-10 code for Type 2 Diabetes Mellitus with chronic kidney disease stage 3?",
        "patient_id": None,
    },
    "patient_timeline": {
        "query": "Show me the clinical timeline for patient-456 including all conditions and medications.",
        "patient_id": "patient-456",
    },
    "clinical_calculation": {
        "query": "Calculate the GFR for a 65-year-old male with creatinine 1.8 mg/dL. "
        "Also calculate BMI if weight is 85kg and height is 175cm.",
        "patient_id": None,
    },
}


DEFAULT_QUERY = "medication_check"


class TestE2EAgentFlow:
    """Test the full Researcher -> Validator pipeline."""

    @pytest.fixture
    def graph(self):
        return create_multi_agent_graph()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("query_name", PREDEFINED_QUERIES.keys())
    async def test_predefined_queries(self, graph, query_name):
        test_case = PREDEFINED_QUERIES[query_name]
        initial_state = {
            "query": test_case["query"],
            "session_id": f"test-{query_name}",
            "patient_id": test_case["patient_id"],
            "iteration_count": 0,
        }
        result = await graph.ainvoke(initial_state)
        assert result.get("final_response")
        assert result.get("validation_result") in ["PASS", "NEEDS_REVISION", "FAIL"]
        assert result.get("iteration_count", 0) <= 3

    @pytest.mark.asyncio
    async def test_validator_catches_bad_dosage(self, graph):
        dangerous_query = (
            "Patient has a GFR of 15 (severe kidney disease). "
            "Is metformin 2000mg twice daily appropriate?"
        )
        initial_state = {
            "query": dangerous_query,
            "session_id": "test-dangerous-dose",
            "patient_id": None,
            "iteration_count": 0,
        }
        result = await graph.ainvoke(initial_state)
        assert result.get("validation_result") in ["NEEDS_REVISION", "FAIL"]
        final_response = (result.get("final_response") or "").lower()
        assert "renal" in final_response or "kidney" in final_response


async def run_single_query(query: str, patient_id: Optional[str] = None):
    graph = create_multi_agent_graph()
    initial_state = {
        "query": query,
        "session_id": "cli-test",
        "patient_id": patient_id,
        "iteration_count": 0,
    }
    result = await graph.ainvoke(initial_state)
    return result


def main():
    parser = argparse.ArgumentParser(description="Test the two-agent healthcare system")
    parser.add_argument("--query", "-q", type=str, help="Custom query to run (or use predefined name)")
    parser.add_argument("--patient-id", "-p", type=str, default=None, help="Optional patient ID for filtering")
    parser.add_argument("--list-predefined", "-l", action="store_true", help="List all predefined test queries")
    args = parser.parse_args()

    if args.list_predefined:
        for name, data in PREDEFINED_QUERIES.items():
            print(f"{name}: {data['query'][:80]}...")
        return

    if args.query and args.query in PREDEFINED_QUERIES:
        test_case = PREDEFINED_QUERIES[args.query]
        query = test_case["query"]
        patient_id = args.patient_id or test_case["patient_id"]
    elif args.query:
        query = args.query
        patient_id = args.patient_id
    else:
        test_case = PREDEFINED_QUERIES[DEFAULT_QUERY]
        query = test_case["query"]
        patient_id = test_case["patient_id"]

    result = asyncio.run(run_single_query(query, patient_id))
    print(result)


if __name__ == "__main__":
    main()
