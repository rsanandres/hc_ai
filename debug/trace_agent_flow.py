"""Trace agent execution step-by-step with timing."""

from __future__ import annotations

import argparse
import asyncio
import time
import sys
from pathlib import Path
from typing import Any, Dict

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from api.agent.multi_agent_graph import (
    _classify_node,
    _conversational_responder_node,
    _researcher_node,
    _validator_node,
    _respond_node,
)


def _now() -> float:
    return time.perf_counter()


async def _run_step(name: str, coro, timeout: int) -> Any:
    start = _now()
    try:
        result = await asyncio.wait_for(coro, timeout=timeout)
        elapsed = _now() - start
        print(f"OK   {name} ({elapsed:.2f}s)")
        return result
    except asyncio.TimeoutError:
        elapsed = _now() - start
        print(f"TIME {name} ({elapsed:.2f}s) timed out after {timeout}s")
        raise


async def main() -> int:
    parser = argparse.ArgumentParser(description="Trace agent flow step-by-step")
    parser.add_argument("--query", required=True, help="User query")
    parser.add_argument("--session-id", default="debug-session", help="Session ID")
    parser.add_argument("--patient-id", default=None, help="Patient ID")
    parser.add_argument("--timeout", type=int, default=180, help="Per-step timeout (s)")
    args = parser.parse_args()

    state: Dict[str, Any] = {
        "query": args.query,
        "session_id": args.session_id,
        "patient_id": args.patient_id,
        "iteration_count": 0,
        "tools_called": [],
        "sources": [],
    }

    print("Tracing agent flow...")
    print(f"query: {args.query!r}")
    print(f"session_id: {args.session_id!r}")
    print(f"patient_id: {args.patient_id!r}")
    print(f"timeout: {args.timeout}s\n")

    # classify (sync)
    start = _now()
    state.update(_classify_node(state))
    print(f"OK   classify_query ({_now() - start:.2f}s)")

    if state.get("query_type") == "conversational":
        state = await _run_step("conversational_responder", _conversational_responder_node(state), args.timeout)
    else:
        state = await _run_step("researcher", _researcher_node(state), args.timeout)
        state = await _run_step("validator", _validator_node(state), args.timeout)
        start = _now()
        state.update(_respond_node(state))
        print(f"OK   respond ({_now() - start:.2f}s)")

    print("\nResult summary:")
    print(f"- validation_result: {state.get('validation_result')}")
    print(f"- tools_called: {state.get('tools_called')}")
    print(f"- iteration_count: {state.get('iteration_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
