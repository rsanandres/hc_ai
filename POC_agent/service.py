"""FastAPI service for the ReAct agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from POC_agent.agent.graph import get_agent
from POC_agent.agent.models import AgentDocument, AgentQueryRequest, AgentQueryResponse
from POC_agent.guardrails.validators import setup_guard
from POC_agent.mcp.langsmith_config import configure_langsmith_tracing
from POC_agent.pii_masker.factory import create_pii_masker
from POC_retrieval.session.store_dynamodb import build_store_from_env

import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
from utils.env_loader import load_env_recursive

load_env_recursive(ROOT_DIR)

app = FastAPI()
_pii_masker = create_pii_masker()
_guard = setup_guard()
try:
    configure_langsmith_tracing()
except Exception:
    # Tracing is optional in local/dev environments.
    pass


def _build_sources(source_items: List[Dict[str, Any]]) -> List[AgentDocument]:
    sources: List[AgentDocument] = []
    for item in source_items:
        sources.append(
            AgentDocument(
                doc_id=item.get("doc_id", ""),
                content_preview=item.get("content_preview", ""),
                metadata=item.get("metadata", {}),
            )
        )
    return sources


def _guard_output(text: str) -> str:
    if _guard is None:
        return text
    try:
        result = _guard.validate(text)
        if hasattr(result, "validated_output"):
            return result.validated_output
        if isinstance(result, dict) and "validated_output" in result:
            return str(result["validated_output"])
    except Exception:
        return text
    return text


@app.post("/agent/query", response_model=AgentQueryResponse)
async def query_agent(payload: AgentQueryRequest) -> AgentQueryResponse:
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query is required.")

    masked_query, _ = _pii_masker.mask_pii(payload.query)

    store = build_store_from_env()
    agent = get_agent()
    max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    state = {
        "query": masked_query,
        "session_id": payload.session_id,
        "patient_id": payload.patient_id,
        "k_retrieve": payload.k_retrieve,
        "k_return": payload.k_return,
        "iteration_count": 0,
    }
    result = await agent.ainvoke(state, config={"recursion_limit": max_iterations})

    response_text = result.get("final_response") or result.get("researcher_output", "")

    response_text = _guard_output(response_text)
    response_text, _ = _pii_masker.mask_pii(response_text)

    tool_calls = result.get("tools_called", [])
    sources = _build_sources(result.get("sources", []))

    store.append_turn(payload.session_id, role="user", text=masked_query, meta={"masked": True})
    store.append_turn(payload.session_id, role="assistant", text=response_text, meta={"tool_calls": tool_calls})

    return AgentQueryResponse(
        query=payload.query,
        response=response_text,
        sources=sources,
        tool_calls=tool_calls,
        session_id=payload.session_id,
        validation_result=result.get("validation_result"),
        researcher_output=result.get("researcher_output"),
        validator_output=result.get("validator_output"),
    )


@app.get("/agent/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/session/{session_id}/clear")
def clear_session(session_id: str) -> Dict[str, str]:
    store = build_store_from_env()
    store.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
