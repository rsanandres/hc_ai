"""API runner for agent endpoint."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG


async def run_api_query(
    query: str,
    session_id: str,
    patient_id: Optional[str] = None,
    k_retrieve: Optional[int] = None,
    k_return: Optional[int] = None,
) -> Dict[str, Any]:
    payload = {
        "query": query,
        "session_id": session_id,
        "patient_id": patient_id,
        "k_retrieve": k_retrieve,
        "k_return": k_return,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(CONFIG.agent_api_url, json=payload)
        response.raise_for_status()
        data = response.json()
    return {
        "query": data.get("query", query),
        "response": data.get("response", ""),
        "sources": data.get("sources", []),
        "tool_calls": data.get("tool_calls", []),
        "validation_result": data.get("validation_result"),
        "raw": data,
    }
