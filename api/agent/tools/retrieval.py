"""Enhanced retrieval tool for patient records."""

from __future__ import annotations

import os
import re
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


# Keyword-to-resource-type mapping for automatic query intent detection
RESOURCE_TYPE_KEYWORDS = {
    "Condition": [
        "condition", "conditions", "diagnosis", "diagnoses", "diagnosed",
        "disease", "diseases", "problem", "problems", "illness", "illnesses",
        "disorder", "disorders", "ailment", "ailments", "sickness",
    ],
    "Observation": [
        "observation", "observations", "lab", "labs", "laboratory",
        "test", "tests", "result", "results", "measurement", "measurements",
        "vital", "vitals", "blood pressure", "heart rate", "temperature",
        "weight", "height", "bmi", "glucose", "cholesterol", "hemoglobin",
    ],
    "MedicationRequest": [
        "medication", "medications", "medicine", "medicines", "drug", "drugs",
        "prescription", "prescriptions", "prescribed", "rx", "pharma",
    ],
    "Procedure": [
        "procedure", "procedures", "surgery", "surgeries", "surgical",
        "operation", "operations", "intervention", "interventions",
    ],
    "Immunization": [
        "immunization", "immunizations", "vaccine", "vaccines", "vaccination",
        "vaccinations", "immunized", "vaccinated", "shot", "shots",
    ],
    "Encounter": [
        "encounter", "encounters", "visit", "visits", "appointment",
        "appointments", "admission", "admissions", "hospitalization",
    ],
    "DiagnosticReport": [
        "report", "reports", "diagnostic", "diagnostics", "imaging",
        "radiology", "xray", "x-ray", "mri", "ct scan", "ultrasound",
    ],
    "AllergyIntolerance": [
        "allergy", "allergies", "allergic", "intolerance", "intolerances",
        "allergen", "allergens", "hypersensitivity", "anaphylaxis",
    ],
}


def detect_resource_type_from_query(query: str) -> Optional[str]:
    """
    Detect FHIR resource type from keywords in the query.

    Args:
        query: User's search query

    Returns:
        FHIR resource type string if detected, None otherwise
    """
    if not query:
        return None

    query_lower = query.lower()

    # Check each resource type's keywords
    for resource_type, keywords in RESOURCE_TYPE_KEYWORDS.items():
        for keyword in keywords:
            # Match whole words to avoid partial matches
            # e.g., "medication" shouldn't match in "premedication"
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, query_lower):
                return resource_type

    return None


from api.database.postgres import search_similar_chunks
from api.retrieval.cross_encoder import Reranker
from api.agent.tools.schemas import ChunkResult, RetrievalResponse
from api.agent.tools.context import get_patient_context


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
        patient_id: Patient UUID (NOT an ICD-10 code!) - use the patient_id from context
        k_chunks: Number of chunks to return (default: 10)
        include_full_json: Whether to include full document JSON
    """
    from api.agent.tools.argument_validators import validate_patient_id

    # ALWAYS use patient_id from context when available - this prevents LLM from
    # hallucinating wrong patient IDs. The context is set from the frontend selection.
    context_patient_id = get_patient_context()
    if context_patient_id:
        if patient_id and patient_id != context_patient_id:
            print(f"[RETRIEVAL] Overriding LLM patient_id ({patient_id[:8]}...) with context ({context_patient_id[:8]}...)")
        patient_id = context_patient_id
    elif not patient_id:
        print("[RETRIEVAL] Warning: No patient_id provided and none in context")

    # Store original query before any modifications
    original_query = query

    # Handle empty query - return helpful error instead of 422
    if not query or not query.strip():
        return RetrievalResponse(
            query="",
            original_query=original_query,
            chunks=[],
            count=0,
            success=False,
            error="Query cannot be empty. Please provide a search term like 'Condition', 'Observation', or 'MedicationRequest'.",
        ).model_dump()

    if patient_id:
        # Validate patient_id format (catches ICD-10/UUID confusion)
        is_valid, error_msg = validate_patient_id(patient_id)
        if not is_valid:
            return RetrievalResponse(
                query=query,
                original_query=original_query,
                chunks=[],
                count=0,
                success=False,
                error=error_msg,
            ).model_dump()

        # Strip patient name from query - names don't match old embeddings
        cleaned_query = strip_patient_name_from_query(query, patient_id)

        # If query becomes empty after stripping, use a generic FHIR resource query
        if not cleaned_query or not cleaned_query.strip():
            cleaned_query = "Condition Observation MedicationRequest"

        # Auto-detect resource type from query keywords
        detected_resource_type = detect_resource_type_from_query(original_query)

        payload = {
            "query": cleaned_query,
            "k_retrieve": max(k_chunks * 4, 20),
            "k_return": k_chunks,
        }
        filter_metadata = {"patient_id": patient_id}
        if detected_resource_type:
            filter_metadata["resource_type"] = detected_resource_type
        payload["filter_metadata"] = filter_metadata
    else:
        cleaned_query = query
        # Auto-detect resource type from query keywords
        detected_resource_type = detect_resource_type_from_query(query)

        payload = {
            "query": cleaned_query,
            "k_retrieve": max(k_chunks * 4, 20),
            "k_return": k_chunks,
        }
        if detected_resource_type:
            payload["filter_metadata"] = {"resource_type": detected_resource_type}
    if include_full_json:
        payload["include_full_json"] = True
    path = "/rerank/with-context" if include_full_json else "/rerank"
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(_reranker_url(path), json=payload)
        response.raise_for_status()
        data = response.json()

    if include_full_json:
        response = RetrievalResponse(
            query=cleaned_query,
            original_query=original_query if original_query != cleaned_query else None,
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
        query=cleaned_query,
        original_query=original_query if original_query != cleaned_query else None,
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
        patient_id: Patient UUID (NOT an ICD-10 code!) - use the patient_id from context
        k_retrieve: Number of candidates to retrieve before reranking
        k_return: Number of results to return after reranking
        use_hybrid: If True, use BM25+semantic hybrid search. If False, semantic only.
    """
    from api.agent.tools.argument_validators import validate_patient_id
    from api.database.postgres import hybrid_search

    # ALWAYS use patient_id from context when available - this prevents LLM from
    # hallucinating wrong patient IDs. The context is set from the frontend selection.
    context_patient_id = get_patient_context()
    if context_patient_id:
        if patient_id and patient_id != context_patient_id:
            print(f"[RETRIEVAL] Overriding LLM patient_id ({patient_id[:8]}...) with context ({context_patient_id[:8]}...)")
        patient_id = context_patient_id
    elif not patient_id:
        print("[RETRIEVAL] Warning: No patient_id provided and none in context")

    # Store original query before any modifications
    original_query = query

    # Handle empty query - return helpful error instead of crashing
    if not query or not query.strip():
        return RetrievalResponse(
            query="",
            original_query=original_query,
            chunks=[],
            count=0,
            success=False,
            error="Query cannot be empty. Please provide a search term like 'Condition', 'Observation', or 'MedicationRequest'.",
        ).model_dump()

    if patient_id:
        # Validate patient_id format (catches ICD-10/UUID confusion)
        is_valid, error_msg = validate_patient_id(patient_id)
        if not is_valid:
            return RetrievalResponse(
                query=query,
                original_query=original_query,
                chunks=[],
                count=0,
                success=False,
                error=error_msg,
            ).model_dump()

        # Strip patient name from query - names don't match old embeddings
        cleaned_query = strip_patient_name_from_query(query, patient_id)

        # If query becomes empty after stripping, use a generic FHIR resource query
        if not cleaned_query or not cleaned_query.strip():
            cleaned_query = "Condition Observation MedicationRequest"

        # Auto-detect resource type from query keywords
        detected_resource_type = detect_resource_type_from_query(original_query)

        filter_metadata = {"patient_id": patient_id}
        if detected_resource_type:
            filter_metadata["resource_type"] = detected_resource_type
    else:
        cleaned_query = query
        # Auto-detect resource type from query keywords
        detected_resource_type = detect_resource_type_from_query(query)
        filter_metadata = {"resource_type": detected_resource_type} if detected_resource_type else None

    # Use hybrid search (BM25 + semantic) or semantic-only
    if use_hybrid:
        candidates = await hybrid_search(
            cleaned_query,
            k=k_retrieve,
            filter_metadata=filter_metadata,
            bm25_weight=0.5,
            semantic_weight=0.5,
        )
    else:
        candidates = await search_similar_chunks(cleaned_query, k=k_retrieve, filter_metadata=filter_metadata)

    if not candidates:
        return RetrievalResponse(
            query=cleaned_query,
            original_query=original_query if original_query != cleaned_query else None,
            chunks=[],
            count=0
        ).model_dump()

    reranker = _get_reranker()
    scored = reranker.rerank_with_scores(cleaned_query, candidates)
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
    return RetrievalResponse(
        query=cleaned_query,
        original_query=original_query if original_query != cleaned_query else None,
        chunks=chunks,
        count=len(chunks)
    ).model_dump()
