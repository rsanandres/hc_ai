"""Direct agent invocation runner."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from utils.env_loader import load_env_recursive

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_agent.agent.graph import get_agent
from POC_RAGAS.config import REPO_ROOT


load_env_recursive(REPO_ROOT)


async def run_agent_query(
    query: str,
    session_id: str,
    patient_id: Optional[str] = None,
    k_retrieve: Optional[int] = None,
    k_return: Optional[int] = None,
) -> Dict[str, Any]:
    agent = get_agent()
    max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    state = {
        "query": query,
        "session_id": session_id,
        "patient_id": patient_id,
        "k_retrieve": k_retrieve,
        "k_return": k_return,
        "iteration_count": 0,
    }
    result = await agent.ainvoke(state, config={"recursion_limit": max_iterations})
    response_text = result.get("final_response") or result.get("researcher_output", "")
    return {
        "query": query,
        "response": response_text,
        "sources": result.get("sources", []),
        "tool_calls": result.get("tools_called", []),
        "validation_result": result.get("validation_result"),
        "raw": result,
    }
