"""Test agent tools in isolation."""

from __future__ import annotations

import argparse
import asyncio
import time
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import os

from api.agent.tools import (
    calculate,
    cross_reference_meds,
    get_current_date,
    get_patient_timeline,
    get_session_context,
    lookup_loinc,
    lookup_rxnorm,
    search_clinical_notes,
    search_icd10,
    search_patient_records,
    retrieve_patient_data,
    validate_icd10_code,
)


def _timed(name: str, func: Callable[[], Any]) -> Tuple[str, Any, float, Exception | None]:
    start = time.perf_counter()
    try:
        result = func()
        return name, result, time.perf_counter() - start, None
    except Exception as exc:  # noqa: BLE001
        return name, None, time.perf_counter() - start, exc


async def _timed_async(name: str, coro, timeout: int) -> Tuple[str, Any, float, Exception | None]:
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        return name, result, time.perf_counter() - start, None
    except Exception as exc:  # noqa: BLE001
        return name, None, time.perf_counter() - start, exc


TOOLS = {
    "calculate": calculate,
    "cross_reference_meds": cross_reference_meds,
    "get_current_date": get_current_date,
    "get_patient_timeline": get_patient_timeline,
    "get_session_context": get_session_context,
    "lookup_loinc": lookup_loinc,
    "lookup_rxnorm": lookup_rxnorm,
    "search_clinical_notes": search_clinical_notes,
    "search_icd10": search_icd10,
    "search_patient_records": search_patient_records,
    "retrieve_patient_data": retrieve_patient_data,
    "validate_icd10_code": validate_icd10_code,
}

async def _get_real_patient_ids(limit: int = 5) -> List[str]:
    """Query database for actual patient IDs that have data, verified to have chunks."""
    try:
        # Get database connection info
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_name = os.getenv("DB_NAME")
        schema_name = os.getenv("DB_SCHEMA", "hc_ai_schema")
        table_name = os.getenv("DB_TABLE", "hc_ai_table")
        
        if not all([db_user, db_password, db_name]):
            return []
        
        connection_string = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        engine = create_async_engine(connection_string, pool_pre_ping=True)
        
        async with engine.begin() as conn:
            # Get patient IDs that have at least a few chunks (verified to have data)
            result = await conn.execute(
                text(
                    f"""
                    SELECT 
                        (langchain_metadata::jsonb)->>'patientId' AS patient_id,
                        COUNT(*) as chunk_count
                    FROM "{schema_name}"."{table_name}"
                    WHERE (langchain_metadata::jsonb)->>'patientId' IS NOT NULL
                      AND (langchain_metadata::jsonb)->>'patientId' != ''
                    GROUP BY (langchain_metadata::jsonb)->>'patientId'
                    HAVING COUNT(*) >= 5
                    ORDER BY chunk_count DESC
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            rows = result.fetchall()
            ids = [row[0] for row in rows if row[0]]
            if ids:
                print(f"Found {len(ids)} patient IDs with chunks:")
                for i, (pid, count) in enumerate(rows[:5], 1):
                    print(f"  {i}. {pid} ({count} chunks)")
        await engine.dispose()
        return ids
    except Exception as e:
        print(f"Warning: Could not fetch patient IDs from database: {e}")
        import traceback
        traceback.print_exc()
        return []


TOOL_TESTS: Dict[str, List[Tuple[str, Dict[str, Any], bool]]] = {
    "calc": [
        ("calculate", {"expression": "2 + 2"}, False),
        ("get_current_date", {}, False),
    ],
    "retrieval": [
        ("search_patient_records", {"query": "", "k_chunks": 3, "include_full_json": False, "patient_id": None}, True),
        ("retrieve_patient_data", {"query": "", "k_retrieve": 20, "k_return": 5, "patient_id": None}, True),
        ("search_clinical_notes", {"query": "", "k_retrieve": 10, "k_return": 3, "patient_id": None}, False),
        ("get_patient_timeline", {"patient_id": "f0000d346-2e09-428f-b37b-b9d5182e313f", "k_return": 5}, False),
        ("cross_reference_meds", {"medication_list": ["metformin", "lisinopril"]}, False),
    ],
    "terminology": [
        ("search_icd10", {"term": "diabetes", "max_results": 5}, True),
        ("validate_icd10_code", {"code": "E11.9"}, True), #diabetes
        ("lookup_rxnorm", {"drug_name": "metformin"}, True),
        ("lookup_loinc", {"code": "2345-7"}, True),
    ],
    "session": [
        ("get_session_context", {"session_id": "debug-session", "limit": 3}, False),
    ],
}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Test agent tools")
    parser.add_argument("--query", default="diabetes", help="Query to use for tools")
    parser.add_argument("--patient-id", default=None, help="Patient ID")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout for async tools")
    parser.add_argument(
        "--category",
        choices=["all", "calc", "retrieval", "fda", "research", "terminology", "session"],
        default="all",
        help="Tool category to test",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed output")
    args = parser.parse_args()

    # Get real patient IDs from database for retrieval tests
    real_patient_ids = await _get_real_patient_ids(limit=10)
    if real_patient_ids:
        print(f"Found {len(real_patient_ids)} patient IDs in database")
        # Use first few for different tests
        test_patient_ids = real_patient_ids[:4] if len(real_patient_ids) >= 4 else real_patient_ids * 4
    else:
        print("Warning: No patient IDs found in database, using placeholder IDs")
        test_patient_ids = ["placeholder-1", "placeholder-2", "placeholder-3", "placeholder-4"]

    tests: List[Tuple[str, Any, float, Exception | None, dict]] = []

    categories = TOOL_TESTS.keys() if args.category == "all" else [args.category]

    patient_id_idx = 0
    for category in categories:
        for tool_name, payload, is_async in TOOL_TESTS[category]:
            tool = TOOLS[tool_name]
            request = dict(payload)
            if "query" in request:
                request["query"] = args.query
            if "patient_id" in request:
                # Use CLI arg if provided, otherwise use real patient ID from database
                if args.patient_id is not None:
                    request["patient_id"] = args.patient_id
                elif request.get("patient_id") is None and real_patient_ids:
                    # Replace None with real patient ID
                    request["patient_id"] = test_patient_ids[patient_id_idx % len(test_patient_ids)]
                    patient_id_idx += 1
            if is_async:
                name, result, elapsed, error = await _timed_async(
                    tool_name,
                    tool.ainvoke(request),
                    args.timeout,
                )
                tests.append((name, result, elapsed, error, request))
            else:
                name, result, elapsed, error = _timed(
                    tool_name,
                    lambda t=tool, r=request: t.invoke(r),
                )
                tests.append((name, result, elapsed, error, request))

    failed = 0
    for name, result, elapsed, error, request in tests:
        if error:
            failed += 1
            print(f"FAIL {name} ({elapsed:.2f}s): {error}")
            if args.verbose:
                print(f"  Request: {request}")
                if hasattr(error, "__traceback__"):
                    import traceback
                    print(f"  Traceback:\n{''.join(traceback.format_exception(type(error), error, error.__traceback__))}")
        else:
            size = None
            if isinstance(result, dict):
                # Handle Pydantic response schemas - check multiple possible fields
                if "chunks" in result:
                    size = len(result.get("chunks", []))
                elif "results" in result:
                    size = len(result.get("results", []))
                elif "events" in result:
                    size = len(result.get("events", []))
                elif "medications" in result:
                    size = len(result.get("medications", []))
                elif "warnings" in result:
                    size = len(result.get("warnings", []))
                elif "count" in result:
                    size = result.get("count", 0)
                elif "recent_turns" in result:
                    size = len(result.get("recent_turns", []))
                else:
                    # Fallback: try to find any list field
                    for key, value in result.items():
                        if isinstance(value, list):
                            size = len(value)
                            break
                
                # Show success/error status for debugging
                if result.get("success") is False:
                    print(f"OK   {name} ({elapsed:.2f}s) size={size} error={result.get('error', 'unknown')}")
                else:
                    print(f"OK   {name} ({elapsed:.2f}s) size={size}")
                
                # Verbose output
                if args.verbose:
                    print(f"  Request: {request}")
                    if "chunks" in result and result["chunks"]:
                        chunks = result["chunks"]
                        print(f"  Chunks ({len(chunks)}):")
                        for i, chunk in enumerate(chunks[:3], 1):  # Show first 3
                            if isinstance(chunk, dict):
                                content_preview = str(chunk.get("content", chunk.get("text", "")))[:100]
                                metadata = chunk.get("metadata", {})
                                print(f"    {i}. {content_preview}...")
                                if metadata:
                                    print(f"       metadata: {list(metadata.keys())}")
                            else:
                                print(f"    {i}. {str(chunk)[:100]}...")
                        if len(chunks) > 3:
                            print(f"    ... and {len(chunks) - 3} more")
                    elif "results" in result and result["results"]:
                        results_list = result["results"]
                        print(f"  Results ({len(results_list)}):")
                        for i, item in enumerate(results_list[:3], 1):  # Show first 3
                            print(f"    {i}. {str(item)[:150]}...")
                        if len(results_list) > 3:
                            print(f"    ... and {len(results_list) - 3} more")
                    elif "events" in result and result["events"]:
                        events = result["events"]
                        print(f"  Events ({len(events)}):")
                        for i, event in enumerate(events[:3], 1):
                            print(f"    {i}. {str(event)[:150]}...")
                        if len(events) > 3:
                            print(f"    ... and {len(events) - 3} more")
                    elif "medications" in result and result["medications"]:
                        meds = result["medications"]
                        print(f"  Medications ({len(meds)}):")
                        for i, med in enumerate(meds[:3], 1):
                            print(f"    {i}. {str(med)[:150]}...")
                        if len(meds) > 3:
                            print(f"    ... and {len(meds) - 3} more")
                    elif "warnings" in result and result["warnings"]:
                        warnings = result["warnings"]
                        print(f"  Warnings ({len(warnings)}):")
                        for i, warning in enumerate(warnings[:3], 1):
                            print(f"    {i}. {str(warning)[:150]}...")
                        if len(warnings) > 3:
                            print(f"    ... and {len(warnings) - 3} more")
                    elif result.get("success") is False:
                        print(f"  Error: {result.get('error', 'unknown')}")
                    else:
                        # Show key fields from result
                        key_fields = {k: v for k, v in result.items() if k not in ["success", "chunks", "results", "events", "medications", "warnings", "count", "recent_turns"]}
                        if key_fields:
                            print(f"  Response fields: {list(key_fields.keys())}")
                            for key, value in list(key_fields.items())[:5]:  # Show first 5 fields
                                value_str = str(value)
                                if len(value_str) > 100:
                                    value_str = value_str[:100] + "..."
                                print(f"    {key}: {value_str}")
            else:
                print(f"OK   {name} ({elapsed:.2f}s) result={type(result).__name__}")
                if args.verbose:
                    print(f"  Request: {request}")
                    result_str = str(result)
                    if len(result_str) > 200:
                        result_str = result_str[:200] + "..."
                    print(f"  Response: {result_str}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
