"""Enhanced retrieval tool for patient records."""

from __future__ import annotations

import os
import re
import uuid
from typing import Any, Dict, Optional

import httpx
from langchain_core.tools import tool


def strip_patient_name_from_query(query: str, patient_id: Optional[str] = None) -> str:
    """Remove patient names from query when patient_id is provided.

    Safeguard: Old embeddings don't contain patient names, so including them
    in semantic search causes mismatches. Use patient_id filter instead.

    Examples:
        "Adam Abbott active conditions" → "active conditions"
        "John Smith's medications" → "medications"
        "Adam Abbott" → "Condition" (fallback when only name provided)
        "what are the patient's conditions" → "what are the patient's conditions" (unchanged)
    """
    if not patient_id or not query:
        return query

    original_query = query.strip()
    words = original_query.split()

    # Pattern 1: Possessive form - "Adam Abbott's conditions" → "conditions"
    possessive_match = re.match(r"^[A-Z][a-z]+\s+[A-Z][a-z]+['\u2019]s?\s+(.+)$", original_query)
    if possessive_match:
        return possessive_match.group(1).strip()

    # Pattern 2: Query is ONLY a name (2 capitalized words, nothing else)
    # "Adam Abbott" → fallback to generic FHIR resource search
    if len(words) == 2:
        first, second = words[0], words[1]
        if (first[0].isupper() and first.isalpha() and len(first) > 1 and
            second[0].isupper() and second.isalpha() and len(second) > 1):
            # Query is just a name - return generic clinical query
            # The patient_id filter will constrain to the right patient
            return "Condition Observation MedicationRequest"

    # Pattern 3: Two capitalized words at start followed by lowercase
    # "Adam Abbott active conditions" → "active conditions"
    if len(words) >= 3:
        first, second, third = words[0], words[1], words[2]
        # Check if first two words look like a name (both capitalized, alphabetic)
        if (first and second and third and
            first[0].isupper() and first.isalpha() and len(first) > 1 and
            second[0].isupper() and second.isalpha() and len(second) > 1 and
            not third[0].isupper()):  # Third word NOT capitalized confirms name pattern
            cleaned = " ".join(words[2:]).strip()
            if cleaned:
                return cleaned

    return original_query

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
    """Get reranker URL with path - unified API endpoint on port 8000."""
    # Prefer explicit reranker URL, fallback to API base (unified API on port 8000)
    api_base = os.getenv("RERANKER_SERVICE_URL") or os.getenv("API_BASE_URL", "http://localhost:8000")
    api_base = api_base.rstrip("/")
    # If caller already included /retrieval, honor it
    if "/retrieval" in api_base:
        if path.startswith("/"):
            return f"{api_base}{path}"
        return f"{api_base}/{path}"
    # Construct path: /retrieval/rerank or /retrieval/rerank/with-context
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
        patient_id: Patient UUID like "f1d2d1e2-4a03-43cb-8f06-f68c90e96cc8" (NOT an ICD-10 code!)
        k_chunks: Number of chunks to return
        include_full_json: Whether to include full document JSON
    """
    from api.agent.tools.argument_validators import validate_patient_id
    
    if patient_id:
        # Validate patient_id format (catches ICD-10/UUID confusion)
        is_valid, error_msg = validate_patient_id(patient_id)
        if not is_valid:
            return RetrievalResponse(
                query=query,
                chunks=[],
                count=0,
                success=False,
                error=error_msg,
            ).model_dump()

        # Strip patient name from query - names don't match old embeddings
        query = strip_patient_name_from_query(query, patient_id)

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
    use_hybrid: bool = True,
) -> Dict[str, Any]:
    """
    Direct retrieval from PostgreSQL with hybrid search and cross-encoder reranking.
    
    Uses BM25 (keyword) + semantic (vector) hybrid search for better coverage,
    then reranks with cross-encoder for final results.
    
    Args:
        query: Search query string
        patient_id: Patient UUID like "f1d2d1e2-4a03-43cb-8f06-f68c90e96cc8" (NOT an ICD-10 code!)
        k_retrieve: Number of candidates to retrieve before reranking
        k_return: Number of results to return after reranking
        use_hybrid: If True, use BM25+semantic hybrid search. If False, semantic only.
    """
    from api.agent.tools.argument_validators import validate_patient_id
    from api.database.postgres import hybrid_search, search_similar_chunks
    
    if patient_id:
        # Validate patient_id format (catches ICD-10/UUID confusion)
        is_valid, error_msg = validate_patient_id(patient_id)
        if not is_valid:
            return RetrievalResponse(
                query=query,
                chunks=[],
                count=0,
                success=False,
                error=error_msg,
            ).model_dump()

        # Strip patient name from query - names don't match old embeddings
        query = strip_patient_name_from_query(query, patient_id)

        filter_metadata = {"patient_id": patient_id}
    else:
        filter_metadata = None

    # Use hybrid search (BM25 + semantic) or semantic-only
    if use_hybrid:
        candidates = await hybrid_search(
            query, 
            k=k_retrieve, 
            filter_metadata=filter_metadata,
            bm25_weight=0.3,
            semantic_weight=0.7,
        )
    else:
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
