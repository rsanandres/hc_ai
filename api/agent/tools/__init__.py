"""Tool definitions for the medical agents."""

from __future__ import annotations

import asyncio
import datetime as dt
import uuid
from typing import Any, Dict, List, Optional

from langchain_core.tools import tool

from api.agent.pii_masker.factory import create_pii_masker
from api.session.store_dynamodb import get_session_store
from api.agent.tools.schemas import (
    CalculationResponse,
    ChunkResult,
    MedicationCheckResponse,
    RetrievalResponse,
    SessionContextResponse,
    TimelineResponse,
)
from api.agent.tools.retrieval import detect_resource_type_from_query
from api.agent.tools.context import get_patient_context

_pii_masker = create_pii_masker()


def _mask_content(text: str) -> str:
    masked, _ = _pii_masker.mask_pii(text)
    return masked


@tool
async def search_clinical_notes(
    query: str,
    k_retrieve: int = 50,
    k_return: int = 10,
    patient_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search clinical notes for relevant context.

    Args:
        query: Search query string
        k_retrieve: Number of candidates to retrieve before reranking
        k_return: Number of results to return after reranking
        patient_id: Patient UUID (auto-injected from context)
    """
    from api.database.postgres import hybrid_search

    # ALWAYS use patient_id from context when available
    context_patient_id = get_patient_context()
    if context_patient_id:
        if patient_id and patient_id != context_patient_id:
            print(f"[CLINICAL_NOTES] Overriding patient_id ({patient_id[:8]}...) with context ({context_patient_id[:8]}...)")
        patient_id = context_patient_id
    elif not patient_id:
        print("[CLINICAL_NOTES] Warning: No patient_id provided and none in context")

    # Auto-detect resource type from query keywords (e.g., "conditions" -> Condition)
    detected_resource_type = detect_resource_type_from_query(query)

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
                error=f"Invalid patient_id format. Must be a UUID (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx), got: {patient_id}",
            ).model_dump()
        filter_metadata: Optional[Dict[str, Any]] = {"patient_id": patient_id}
        if detected_resource_type:
            filter_metadata["resource_type"] = detected_resource_type
            print(f"[CLINICAL_NOTES] Auto-detected resource_type: {detected_resource_type}")
    else:
        filter_metadata = {"resource_type": detected_resource_type} if detected_resource_type else None

    # Direct DB + reranker (no self-referencing HTTP)
    candidates = await hybrid_search(
        query, k=k_retrieve, filter_metadata=filter_metadata,
        bm25_weight=0.5, semantic_weight=0.5,
    )

    if not candidates:
        return RetrievalResponse(query=query, chunks=[], count=0).model_dump()

    # Get or create reranker singleton
    from api.agent.tools.retrieval import _get_reranker
    reranker = _get_reranker()
    scored = await asyncio.to_thread(reranker.rerank_with_scores, query, candidates)
    top_docs = scored[:k_return]

    chunks = [
        ChunkResult(
            id=str(getattr(doc, "id", "")),
            content=_mask_content(doc.page_content),
            score=score,
            metadata=doc.metadata or {},
        )
        for doc, score in top_docs
    ]
    return RetrievalResponse(query=query, chunks=chunks, count=len(chunks)).model_dump()


@tool
async def get_patient_timeline(patient_id: Optional[str] = None, k_return: int = 50) -> Dict[str, Any]:
    """
    Return a chronological timeline for a patient based on retrieved notes.

    Queries database directly to get ALL patient chunks sorted by date.

    Args:
        patient_id: Patient UUID (auto-injected from context)
        k_return: Number of timeline events to return (max 100)
    """
    from api.database.postgres import get_patient_timeline as db_get_timeline

    # ALWAYS use patient_id from context when available
    context_patient_id = get_patient_context()
    if context_patient_id:
        if patient_id and patient_id != context_patient_id:
            print(f"[TIMELINE] Overriding patient_id ({patient_id[:8]}...) with context ({context_patient_id[:8]}...)")
        patient_id = context_patient_id
    elif not patient_id:
        return TimelineResponse(
            patient_id="",
            events=[],
            success=False,
            error="No patient_id provided and none in context",
        ).model_dump()

    # Validate UUID format
    try:
        uuid.UUID(patient_id)
    except (ValueError, TypeError):
        return TimelineResponse(
            patient_id=patient_id,
            events=[],
            success=False,
            error=f"Invalid patient_id format. Must be a UUID (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx), got: {patient_id}",
        ).model_dump()
    
    # Use direct DB query (not vector search) to get all patient chunks
    results = await db_get_timeline(patient_id, k=min(k_return, 100))
    
    return TimelineResponse(
        patient_id=patient_id,
        events=[
            ChunkResult(
                id=str(doc.id) if doc.id else "",
                content=_mask_content(doc.page_content),
                score=0.0,
                metadata=doc.metadata or {},
            )
            for doc in results
        ],
    ).model_dump()


@tool
def cross_reference_meds(medication_list: List[str]) -> Dict[str, Any]:
    """Check medication list for basic interaction warnings."""
    meds = {med.strip().lower() for med in medication_list}
    warnings = []
    if "warfarin" in meds and "aspirin" in meds:
        warnings.append("Potential interaction: warfarin with aspirin may increase bleeding risk.")
    if "metformin" in meds and "contrast dye" in meds:
        warnings.append("Potential interaction: metformin with contrast dye may increase lactic acidosis risk.")
    return MedicationCheckResponse(
        medications=sorted(meds),
        warnings=warnings,
    ).model_dump()


@tool
def get_session_context(session_id: str, limit: int = 10) -> Dict[str, Any]:
    """Retrieve session summary and recent turns."""
    store = get_session_store()
    recent = store.get_recent(session_id, limit=limit)
    summary = store.get_summary(session_id)
    return SessionContextResponse(
        summary=summary,
        recent_turns=recent,
    ).model_dump()


@tool
def calculate(expression: str) -> Dict[str, Any]:
    """Safely evaluate simple arithmetic expressions."""
    allowed = set("0123456789+-*/(). ")
    if any(ch not in allowed for ch in expression):
        return CalculationResponse(
            success=False,
            error="Unsupported characters in expression.",
            result=None,
        ).model_dump()
    try:
        result = eval(expression, {"__builtins__": {}}, {})
    except Exception:
        return CalculationResponse(
            success=False,
            error="Unable to evaluate expression.",
            result=None,
        ).model_dump()
    return CalculationResponse(result=str(result)).model_dump()


@tool
def get_current_date() -> Dict[str, Any]:
    """Return current date in ISO format."""
    return CalculationResponse(result=dt.datetime.utcnow().isoformat()).model_dump()


def summarize_tool_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    summaries = []
    for item in results:
        content = item.get("content", "")
        summaries.append(
            {
                "id": item.get("id", ""),
                "content_preview": content[:200].replace("\n", " "),
                "metadata": item.get("metadata", {}),
            }
        )
    return summaries


from .calculators import (
    calculate_bmi,
    calculate_bsa,
    calculate_creatinine_clearance,
    calculate_gfr,
)
from .dosage_validator import validate_dosage
from .fda_tools import get_drug_recalls, get_drug_shortages, get_faers_events, search_fda_drugs
from .loinc_lookup import lookup_loinc
from .research_tools import get_who_stats, search_clinical_trials, search_pubmed
from .retrieval import retrieve_patient_data, search_patient_records
from .terminology_tools import lookup_rxnorm, search_icd10, validate_icd10_code


__all__ = [
    "calculate",
    "calculate_bmi",
    "calculate_bsa",
    "calculate_creatinine_clearance",
    "calculate_gfr",
    "cross_reference_meds",
    "get_current_date",
    "get_drug_recalls",
    "get_drug_shortages",
    "get_patient_timeline",
    "get_session_context",
    "get_who_stats",
    "lookup_loinc",
    "lookup_rxnorm",
    "search_clinical_notes",
    "search_clinical_trials",
    "search_fda_drugs",
    "search_icd10",
    "search_patient_records",
    "retrieve_patient_data",
    "search_pubmed",
    "summarize_tool_results",
    "validate_icd10_code",
    "validate_dosage",
    "get_faers_events",
]
