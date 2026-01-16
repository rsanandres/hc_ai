"""Integration test for reranker + ReAct agent + tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, List

import requests
from langchain_core.messages import ToolMessage

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from POC_agent.agent.graph import get_agent


DEFAULT_RERANKER_URL = "http://localhost:8001/rerank"


def test_reranker_service(query: str) -> List[dict]:
    payload = {"query": query, "k_retrieve": 10, "k_return": 5}
    response = requests.post(DEFAULT_RERANKER_URL, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])
    print(f"[RERANKER] Returned {len(results)} documents")
    for idx, doc in enumerate(results, start=1):
        preview = doc.get("content", "")[:120].replace("\n", " ")
        print(f"  {idx}. {doc.get('id')} | {preview}")
    return results


def test_agent_with_tools(query: str) -> Any:
    agent = get_agent()
    result = agent.invoke({"messages": [("user", query)]}, config={"recursion_limit": 10})
    messages = result.get("messages", [])
    tool_calls = [msg.name for msg in messages if isinstance(msg, ToolMessage)]
    print(f"[AGENT] Tool calls: {tool_calls}")
    if messages:
        last = messages[-1]
        print(f"[AGENT] Response: {getattr(last, 'content', str(last))[:500]}")
    return result


def test_full_workflow(query: str) -> None:
    print("\n[WORKFLOW] Testing reranker first...")
    test_reranker_service(query)

    print("\n[WORKFLOW] Testing agent tool usage...")
    test_agent_with_tools(query)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python POC_agent/test_agent_integration.py \"your query here\"")
        return 1
    query = sys.argv[1]
    test_full_workflow(query)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
