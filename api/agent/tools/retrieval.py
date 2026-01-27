"""Enhanced retrieval tool for patient records."""

from __future__ import annotations

import os
import uuid
from typing import Any, Dict, Optional

import httpx
from langchain_core.tools import tool

from api.database.postgres import search_similar_chunks
from api.retrieval.cross_encoder import Reranker
from api.agent.tools.schemas import ChunkResult, RetrievalResponse


_RERANKER_INSTANCE: Optional[Reranker] = None


def _get_reranker() -> Reranker:
    global _RERANKER_INSTANCE
    if _RERANKER_INSTANCE is None:
        model = os.getenv("RERANKER_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        device = os.getenv("RERANKER_DEVICE", "auto")
        _RERANKER_INSTANCE = Reranker(model_name=model, device=device)
    return _RERANKER_INSTANCE


def _reranker_url(path: str) -> str:
    # Prefer explicit reranker URL, fallback to API base
    api_base = os.getenv("RERANKER_SERVICE_URL") or os.getenv("API_BASE_URL", "http://localhost:8000")
    api_base = api_base.rstrip("/")
    # If caller already included /retrieval, honor it
    if "/retrieval" in api_base:
        if path.startswith("/"):
            return f"{api_base}{path}"
        return f"{api_base}/{path}"
    if path.startswith("/"):
        return f"{api_base}/retrieval{path}"
    return f"{api_base}/retrieval/{path}"


@tool
async def search_patient_records(
    query: str,
    patient_id: Optional[str] = None,
    k_chunks: int = 10,
    include_full_json: bool = False,
) -> Dict[str, Any]:
    """
    Call reranker service for chunks, optionally fetch full JSON context.
    
    Args:
        query: Search query string
        patient_id: Patient UUID in format "f1d2d1e2-4a03-43cb-8f06-f68c90e96cc8" (required for patient-specific searches)
        k_chunks: Number of chunks to return
        include_full_json: Whether to include full document JSON
    """
    if patient_id:
        # Validate UUID format
        try:
            uuid.UUID(patient_id)
        except (ValueError, TypeError):
            return RetrievalResponse(
                query=query,
                chunks=[],
                count=0,
                success=False,
                error=f"Invalid patient_id format. Must be a UUID like 'f1d2d1e2-4a03-43cb-8f06-f68c90e96cc8', got: {patient_id}",
            ).model_dump()
        payload = {
            "query": query,
            "k_retrieve": max(k_chunks * 4, 20),
            "k_return": k_chunks,
        }
        payload["filter_metadata"] = {"patient_id": patient_id}
    else:
        payload = {
            "query": query,
            "k_retrieve": max(k_chunks * 4, 20),
            "k_return": k_chunks,
        }
    if include_full_json:
        payload["include_full_json"] = True
    path = "/rerank/with-context" if include_full_json else "/rerank"
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(_reranker_url(path), json=payload)
        response.raise_for_status()
        data = response.json()

    if include_full_json:
        response = RetrievalResponse(
            query=data.get("query", query),
            chunks=[
                ChunkResult(
                    id=str(item.get("id", "")),
                    content=str(item.get("content", "")),
                    score=float(item.get("score", 0.0)),
                    metadata=item.get("metadata", {}) or {},
                )
                for item in data.get("chunks", [])
            ],
            count=len(data.get("chunks", [])),
        ).model_dump()
        response["full_documents"] = data.get("full_documents", [])
        return response
    return RetrievalResponse(
        query=data.get("query", query),
        chunks=[
            ChunkResult(
                id=str(item.get("id", "")),
                content=str(item.get("content", "")),
                score=float(item.get("score", 0.0)),
                metadata=item.get("metadata", {}) or {},
            )
            for item in data.get("results", [])
        ],
        count=len(data.get("results", [])),
    ).model_dump()


@tool
async def retrieve_patient_data(
    query: str,
    patient_id: Optional[str] = None,
    k_retrieve: int = 50,
    k_return: int = 10,
) -> Dict[str, Any]:
    """
    Direct retrieval from PostgreSQL with cross-encoder reranking. No HTTP.
    
    Args:
        query: Search query string
        patient_id: Patient UUID in format "f1d2d1e2-4a03-43cb-8f06-f68c90e96cc8" (required for patient-specific searches)
        k_retrieve: Number of candidates to retrieve before reranking
        k_return: Number of results to return after reranking
    """
    if patient_id:
        # Validate UUID format
        try:
            uuid.UUID(patient_id)
        except (ValueError, TypeError):
            return RetrievalResponse(
                query=query,
                chunks=[],
                count=0,
                success=False,
                error=f"Invalid patient_id format. Must be a UUID like 'f1d2d1e2-4a03-43cb-8f06-f68c90e96cc8', got: {patient_id}",
            ).model_dump()
        filter_metadata = {"patient_id": patient_id}
    else:
        filter_metadata = None
    candidates = await search_similar_chunks(query, k=k_retrieve, filter_metadata=filter_metadata)
    if not candidates:
        return RetrievalResponse(query=query, chunks=[], count=0).model_dump()

    reranker = _get_reranker()
    scored = reranker.rerank_with_scores(query, candidates)
    top_docs = scored[:k_return]
    chunks = [
        ChunkResult(
            id=str(getattr(doc, "id", "")),
            content=doc.page_content,
            score=score,
            metadata=doc.metadata or {},
        )
        for doc, score in top_docs
    ]
    return RetrievalResponse(query=query, chunks=chunks, count=len(chunks)).model_dump()
