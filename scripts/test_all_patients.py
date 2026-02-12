#!/usr/bin/env python3
"""
Comprehensive test script for all patients and example prompts.
Outputs results to a markdown report.

Usage:
    python scripts/test_all_patients.py
    python scripts/test_all_patients.py --output results/test_report.md
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

# Test configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
TIMEOUT_SECONDS = 180  # 3 minutes per query (32B model is slow)

# All test patients from ReferencePanel.tsx
PATIENTS = [
    {
        "name": "Danial Larson",
        "id": "5e81d5b2-af01-4367-9b2e-0cdf479094a4",
        "age": 65,
        "expected_conditions": ["Recurrent rectal polyp", "sinusitis", "Polyp of colon"],
        "description": "Older male with multiple chronic conditions.",
    },
    {
        "name": "Ron Zieme",
        "id": "d8d9460b-4cb6-47f9-a94f-9e58390204b2",
        "age": 86,
        "expected_conditions": ["Hypertension", "Fibromyalgia", "Osteoporosis"],
        "description": "Elderly female with complex history including MI and heart disease.",
    },
    {
        "name": "Doug Christiansen",
        "id": "0beb6802-3353-4144-8ae3-97176bce86c3",
        "age": 24,
        "expected_conditions": ["sinusitis"],
        "description": "Young adult with chronic sinus issues.",
    },
    {
        "name": "Jamie Hegmann",
        "id": "6a4168a1-2cfd-4269-8139-8a4a663adfe7",
        "age": 71,
        "expected_conditions": ["Coronary Heart Disease", "Myocardial Infarction"],
        "description": "Female patient with significant cardiac history.",
    },
    {
        "name": "Carlo Herzog",
        "id": "7f7ad77a-5dd5-4df0-ba36-f4f1e4b6d368",
        "age": 23,
        "expected_conditions": ["asthma", "rhinitis", "allergy"],
        "description": "Young male with multiple allergies and asthma.",
    },
    {
        "name": "Adam Abbott",
        "id": "53fcaff1-eb44-4257-819b-50b47f311edf",
        "age": 31,
        "expected_conditions": ["Pregnancy", "Normal pregnancy"],
        "description": "Young female with active pregnancy.",
    },
    {
        "name": "Alva Abbott",
        "id": "f883318e-9a81-4f77-9cff-5318a00b777f",
        "age": 67,
        "expected_conditions": ["Prediabetes", "diabetes"],
        "description": "Older male managing prediabetes.",
    },
    {
        "name": "Amaya Abbott",
        "id": "4b7098a8-13b8-4916-a379-6ae2c8a70a8a",
        "age": 69,
        "expected_conditions": ["Hypertension", "sinusitis", "Concussion"],
        "description": "Older male with hypertension and history of head injury.",
    },
]

# Standard prompts from ReferencePanel.tsx
PROMPTS = [
    "What are the patient's active conditions?",
    "Summarize the patient's medication history.",
    "Show me the timeline of recent encounters.",
    "Does the patient have any known allergies?",
]

# Known hallucination patterns to check for
HALLUCINATION_PATTERNS = [
    "Type 2 Diabetes",
    "E11.9",
    "Hypertension 38341003",  # Wrong SNOMED for hypertension
    "I10",  # ICD-10 for hypertension when not expected
    "[CONDITION_NAME]",  # Placeholder leak
    "[CODE]",  # Placeholder leak
]


class TestResult:
    """Holds result of a single test."""

    def __init__(
        self,
        patient_name: str,
        patient_id: str,
        prompt: str,
        response: str,
        sources: List[Dict],
        tool_calls: List[str],
        iteration_count: int,
        duration_seconds: float,
        error: Optional[str] = None,
    ):
        self.patient_name = patient_name
        self.patient_id = patient_id
        self.prompt = prompt
        self.response = response
        self.sources = sources
        self.tool_calls = tool_calls
        self.iteration_count = iteration_count
        self.duration_seconds = duration_seconds
        self.error = error

        # Computed fields
        self.has_response = bool(response and len(response) > 10)
        self.hallucinations = self._check_hallucinations()
        self.passed = self._evaluate_pass()

    def _check_hallucinations(self) -> List[str]:
        """Check for known hallucination patterns."""
        found = []
        response_lower = self.response.lower()
        for pattern in HALLUCINATION_PATTERNS:
            if pattern.lower() in response_lower:
                found.append(pattern)
        return found

    def _evaluate_pass(self) -> bool:
        """Determine if test passed."""
        if self.error:
            return False
        if not self.has_response:
            return False
        if self.hallucinations:
            return False
        return True


async def query_agent(
    patient_id: str,
    query: str,
    session_id: str,
) -> Dict[str, Any]:
    """Send a query to the agent API."""
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        response = await client.post(
            f"{API_BASE_URL}/agent/query",
            json={
                "query": query,
                "patient_id": patient_id,
                "session_id": session_id,
            },
        )
        response.raise_for_status()
        return response.json()


async def run_single_test(
    patient: Dict[str, Any],
    prompt: str,
    test_num: int,
    total_tests: int,
) -> TestResult:
    """Run a single test case."""
    patient_name = patient["name"]
    patient_id = patient["id"]
    session_id = f"test-{patient_id[:8]}-{datetime.now().strftime('%H%M%S')}"

    print(f"  [{test_num}/{total_tests}] {patient_name}: {prompt[:50]}...", end=" ", flush=True)

    start_time = datetime.now()
    try:
        result = await query_agent(patient_id, prompt, session_id)
        duration = (datetime.now() - start_time).total_seconds()

        test_result = TestResult(
            patient_name=patient_name,
            patient_id=patient_id,
            prompt=prompt,
            response=result.get("response", ""),
            sources=result.get("sources", []),
            tool_calls=result.get("tool_calls", []),
            iteration_count=result.get("iteration_count", 0),
            duration_seconds=duration,
        )

        status = "✓ PASS" if test_result.passed else "✗ FAIL"
        if test_result.hallucinations:
            status += f" (hallucination: {test_result.hallucinations[0]})"
        print(f"{status} ({duration:.1f}s)")

        return test_result

    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        print(f"✗ ERROR: {e}")
        return TestResult(
            patient_name=patient_name,
            patient_id=patient_id,
            prompt=prompt,
            response="",
            sources=[],
            tool_calls=[],
            iteration_count=0,
            duration_seconds=duration,
            error=str(e),
        )


async def run_all_tests() -> List[TestResult]:
    """Run all test cases."""
    results = []
    total_tests = len(PATIENTS) * len(PROMPTS)
    test_num = 0

    print(f"\n{'='*60}")
    print(f"Running {total_tests} tests ({len(PATIENTS)} patients × {len(PROMPTS)} prompts)")
    print(f"{'='*60}\n")

    for patient in PATIENTS:
        print(f"\n📋 Patient: {patient['name']} ({patient['age']} yrs)")
        print(f"   ID: {patient['id']}")
        print(f"   Expected: {', '.join(patient['expected_conditions'][:3])}")
        print()

        for prompt in PROMPTS:
            test_num += 1
            result = await run_single_test(patient, prompt, test_num, total_tests)
            results.append(result)

            # Small delay between requests to avoid overwhelming the server
            await asyncio.sleep(1)

    return results


def generate_markdown_report(results: List[TestResult], output_path: str) -> str:
    """Generate a markdown report from test results."""

    # Calculate summary stats
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed
    hallucinations = sum(1 for r in results if r.hallucinations)
    errors = sum(1 for r in results if r.error)
    avg_duration = sum(r.duration_seconds for r in results) / total if total > 0 else 0

    # Build markdown
    lines = [
        "# HC AI Agent Test Report",
        "",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total Tests | {total} |",
        f"| ✓ Passed | {passed} ({100*passed/total:.1f}%) |",
        f"| ✗ Failed | {failed} ({100*failed/total:.1f}%) |",
        f"| Hallucinations | {hallucinations} |",
        f"| Errors | {errors} |",
        f"| Avg Duration | {avg_duration:.1f}s |",
        "",
        "---",
        "",
    ]

    # Group results by patient
    patients_seen = []
    for result in results:
        if result.patient_name not in patients_seen:
            patients_seen.append(result.patient_name)

    for patient_name in patients_seen:
        patient_results = [r for r in results if r.patient_name == patient_name]
        patient_passed = sum(1 for r in patient_results if r.passed)
        patient_total = len(patient_results)

        lines.append(f"## {patient_name}")
        lines.append("")
        lines.append(f"**Patient ID:** `{patient_results[0].patient_id}`")
        lines.append(f"**Results:** {patient_passed}/{patient_total} passed")
        lines.append("")

        for result in patient_results:
            status_icon = "✓" if result.passed else "✗"
            lines.append(f"### {status_icon} {result.prompt}")
            lines.append("")

            if result.error:
                lines.append(f"**Error:** {result.error}")
                lines.append("")
            else:
                # Response preview (first 500 chars)
                response_preview = result.response[:500]
                if len(result.response) > 500:
                    response_preview += "..."

                lines.append("**Response:**")
                lines.append("```")
                lines.append(response_preview)
                lines.append("```")
                lines.append("")

                lines.append(f"**Tool Calls:** {', '.join(result.tool_calls) if result.tool_calls else 'None'}")
                lines.append(f"**Duration:** {result.duration_seconds:.1f}s")
                lines.append(f"**Iterations:** {result.iteration_count}")

                if result.hallucinations:
                    lines.append(f"**⚠️ Hallucinations Detected:** {', '.join(result.hallucinations)}")

                if result.sources:
                    lines.append(f"**Sources:** {len(result.sources)} chunks retrieved")

                lines.append("")

        lines.append("---")
        lines.append("")

    # Write report
    report_content = "\n".join(lines)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

    with open(output_path, "w") as f:
        f.write(report_content)

    return report_content


async def check_server_health() -> bool:
    """Check if the API server is running."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{API_BASE_URL}/health")
            return response.status_code == 200
    except Exception:
        return False


async def main():
    parser = argparse.ArgumentParser(description="Test all patients with example prompts")
    parser.add_argument(
        "--output", "-o",
        default="test_results/agent_test_report.md",
        help="Output path for markdown report",
    )
    parser.add_argument(
        "--patient", "-p",
        help="Test only a specific patient (by name, partial match)",
    )
    parser.add_argument(
        "--prompt", "-q",
        type=int,
        help="Test only a specific prompt (1-4)",
    )
    args = parser.parse_args()

    # Check server health
    print("Checking API server health...")
    if not await check_server_health():
        print(f"ERROR: API server not responding at {API_BASE_URL}")
        print("Start the server with: uvicorn api.main:app --reload --port 8000")
        sys.exit(1)
    print(f"✓ API server healthy at {API_BASE_URL}")

    # Filter patients/prompts if specified
    global PATIENTS, PROMPTS
    if args.patient:
        PATIENTS = [p for p in PATIENTS if args.patient.lower() in p["name"].lower()]
        if not PATIENTS:
            print(f"ERROR: No patient matching '{args.patient}'")
            sys.exit(1)

    if args.prompt:
        if 1 <= args.prompt <= len(PROMPTS):
            PROMPTS = [PROMPTS[args.prompt - 1]]
        else:
            print(f"ERROR: Prompt number must be 1-{len(PROMPTS)}")
            sys.exit(1)

    # Run tests
    results = await run_all_tests()

    # Generate report
    print(f"\n{'='*60}")
    print("Generating report...")
    generate_markdown_report(results, args.output)
    print(f"✓ Report saved to: {args.output}")

    # Print summary
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"FINAL RESULTS: {passed}/{total} tests passed ({100*passed/total:.1f}%)")
    print(f"{'='*60}\n")

    # Exit with error code if any tests failed
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(main())
