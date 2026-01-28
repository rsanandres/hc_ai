"""Tool definitions for the medical agents."""

from __future__ import annotations

import datetime as dt
import os
import uuid
from typing import Any, Dict, List, Optional

import requests
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
from api.agent.tools.retrieval import _reranker_url

_pii_masker = create_pii_masker()


def _mask_content(text: str) -> str:
    masked, _ = _pii_masker.mask_pii(text)
    return masked


def _call_reranker(
    query: str,
    k_retrieve: int = 50,
    k_return: int = 10,
    filter_metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    payload = {
        "query": query,
        "k_retrieve": k_retrieve,
        "k_return": k_return,
        "filter_metadata": filter_metadata,
    }
    response = requests.post(_reranker_url("rerank"), json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])
    masked_results = []
    for item in results:
        content = item.get("content", "")
        masked_results.append(
            {
                "id": item.get("id", ""),
                "content": _mask_content(content),
                "metadata": item.get("metadata", {}),
            }
        )
    return masked_results


@tool
def search_clinical_notes(
    query: str,
    k_retrieve: int = 50,
    k_return: int = 10,
    patient_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search clinical notes for relevant context.
    
    Args:
        query: Search query string
        k_retrieve: Number of candidates to retrieve before reranking
        k_return: Number of results to return after reranking
        patient_id: Patient UUID in format "f1d2d1e2-4a03-43cb-8f06-f68c90e96cc8" (optional)
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
    results = _call_reranker(query, k_retrieve, k_return, filter_metadata=filter_metadata)
    return RetrievalResponse(
        query=query,
        chunks=[
            ChunkResult(
                id=str(item.get("id", "")),
                content=str(item.get("content", "")),
                score=float(item.get("score", 0.0)),
                metadata=item.get("metadata", {}) or {},
            )
            for item in results
        ],
        count=len(results),
    ).model_dump()


@tool
async def get_patient_timeline(patient_id: str, k_return: int = 50) -> Dict[str, Any]:
    """
    Return a chronological timeline for a patient based on retrieved notes.
    
    Queries database directly to get ALL patient chunks sorted by date.
    
    Args:
        patient_id: Patient UUID in format "f1d2d1e2-4a03-43cb-8f06-f68c90e96cc8" (required)
        k_return: Number of timeline events to return (max 100)
    """
    from api.database.postgres import get_patient_timeline as db_get_timeline
    
    # Validate UUID format
    try:
        uuid.UUID(patient_id)
    except (ValueError, TypeError):
        return TimelineResponse(
            patient_id=patient_id,
            events=[],
            success=False,
            error=f"Invalid patient_id format. Must be a UUID like 'f1d2d1e2-4a03-43cb-8f06-f68c90e96cc8', got: {patient_id}",
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
