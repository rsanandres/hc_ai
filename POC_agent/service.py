"""FastAPI service for the ReAct agent."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from POC_agent.agent.graph import get_agent
from POC_agent.agent.models import AgentDocument, AgentQueryRequest, AgentQueryResponse
from POC_agent.agent.tools import summarize_tool_results
from POC_agent.guardrails.validators import setup_guard
from POC_agent.pii_masker.factory import create_pii_masker
from POC_retrieval.session.store_dynamodb import build_store_from_env


app = FastAPI()
_pii_masker = create_pii_masker()
_guard = setup_guard()


def _extract_tool_calls(messages: List[Any]) -> List[str]:
    calls: List[str] = []
    for message in messages:
        if isinstance(message, ToolMessage):
            if message.name:
                calls.append(message.name)
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            calls.extend([call.get("name", "") for call in message.tool_calls])
    return [call for call in calls if call]


def _extract_sources(messages: List[Any]) -> List[AgentDocument]:
    sources: List[AgentDocument] = []
    for message in messages:
        if isinstance(message, ToolMessage) and message.name == "search_clinical_notes":
            content = message.content
            data = None
            if isinstance(content, str):
                try:
                    data = json.loads(content)
                except Exception:
                    data = None
            elif isinstance(content, list):
                data = content
            if isinstance(data, list):
                for item in summarize_tool_results(data):
                    sources.append(
                        AgentDocument(
                            doc_id=item.get("id", ""),
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
def query_agent(payload: AgentQueryRequest) -> AgentQueryResponse:
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query is required.")

    masked_query, _ = _pii_masker.mask_pii(payload.query)

    store = build_store_from_env()
    recent = store.get_recent(payload.session_id, limit=10)
    summary = store.get_summary(payload.session_id)

    messages = []
    if summary:
        messages.append(SystemMessage(content=f"Session summary: {summary}"))
    if recent:
        messages.append(SystemMessage(content=f"Recent turns: {json.dumps(recent)}"))
    messages.append(HumanMessage(content=masked_query))

    agent = get_agent()
    max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    result = agent.invoke({"messages": messages}, config={"recursion_limit": max_iterations})

    output_messages = result.get("messages", [])
    response_text = ""
    if output_messages:
        last = output_messages[-1]
        response_text = getattr(last, "content", "") if hasattr(last, "content") else str(last)

    response_text = _guard_output(response_text)
    response_text, _ = _pii_masker.mask_pii(response_text)

    tool_calls = _extract_tool_calls(output_messages)
    sources = _extract_sources(output_messages)

    store.append_turn(payload.session_id, role="user", text=masked_query, meta={"masked": True})
    store.append_turn(payload.session_id, role="assistant", text=response_text, meta={"tool_calls": tool_calls})

    return AgentQueryResponse(
        query=payload.query,
        response=response_text,
        sources=sources,
        tool_calls=tool_calls,
        session_id=payload.session_id,
    )


@app.get("/agent/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/agent/session/{session_id}/clear")
def clear_session(session_id: str) -> Dict[str, str]:
    store = build_store_from_env()
    store.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
