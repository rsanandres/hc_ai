"""Pydantic models for the ReAct agent service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentQueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    patient_id: Optional[str] = None
    k_retrieve: Optional[int] = Field(default=None, ge=1, le=200)
    k_return: Optional[int] = Field(default=None, ge=1, le=50)


class AgentDocument(BaseModel):
    doc_id: str
    content_preview: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentQueryResponse(BaseModel):
    query: str
    response: str
    sources: List[AgentDocument] = Field(default_factory=list)
    tool_calls: List[str] = Field(default_factory=list)
    session_id: str
