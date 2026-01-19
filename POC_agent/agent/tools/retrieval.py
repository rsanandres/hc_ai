"""Enhanced retrieval tool for patient records."""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import httpx
from langchain_core.tools import tool


def _reranker_url(path: str) -> str:
    base = os.getenv("RERANKER_SERVICE_URL", "http://localhost:8001/rerank")
    if base.endswith("/rerank"):
        base = base[: -len("/rerank")]
    return f"{base}{path}"


@tool
async def search_patient_records(
    query: str,
    patient_id: Optional[str] = None,
    k_chunks: int = 10,
    include_full_json: bool = False,
) -> Dict[str, Any]:
    """
    Call reranker service for chunks, optionally fetch full JSON context.
    """
    payload = {
        "query": query,
        "k_retrieve": max(k_chunks * 4, 20),
        "k_return": k_chunks,
        "filter_metadata": {"patientId": patient_id} if patient_id else None,
    }
    if include_full_json:
        payload["include_full_json"] = True
    path = "/rerank/with-context" if include_full_json else "/rerank"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(_reranker_url(path), json=payload)
        response.raise_for_status()
        data = response.json()

    if include_full_json:
        return {
            "query": data.get("query", query),
            "chunks": data.get("chunks", []),
            "full_documents": data.get("full_documents", []),
        }
    return {"query": data.get("query", query), "chunks": data.get("results", [])}
