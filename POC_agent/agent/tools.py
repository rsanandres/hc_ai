"""Tool definitions for the ReAct agent."""

from __future__ import annotations

import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional

import requests
from langchain_core.tools import tool

from POC_agent.pii_masker.factory import create_pii_masker
from POC_retrieval.session.store_dynamodb import build_store_from_env


_pii_masker = create_pii_masker()


def _reranker_url() -> str:
    return os.getenv("RERANKER_SERVICE_URL", "http://localhost:8001/rerank")


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
    response = requests.post(_reranker_url(), json=payload, timeout=60)
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
    """Search clinical notes for relevant context."""
    filter_metadata = {"patientId": patient_id} if patient_id else None
    return _call_reranker(query, k_retrieve, k_return, filter_metadata=filter_metadata)


@tool
def get_patient_timeline(patient_id: str, k_return: int = 20) -> Dict[str, Any]:
    """Return a chronological timeline for a patient based on retrieved notes."""
    results = _call_reranker(
        query=f"patient timeline {patient_id}",
        k_retrieve=max(k_return * 3, 30),
        k_return=k_return,
        filter_metadata={"patientId": patient_id},
    )

    def _date_key(item: Dict[str, Any]) -> str:
        metadata = item.get("metadata", {})
        return str(metadata.get("effectiveDate") or metadata.get("lastUpdated") or "")

    sorted_results = sorted(results, key=_date_key)
    return {
        "patient_id": patient_id,
        "events": sorted_results,
    }


@tool
def cross_reference_meds(medication_list: List[str]) -> Dict[str, Any]:
    """Check medication list for basic interaction warnings."""
    meds = {med.strip().lower() for med in medication_list}
    warnings = []
    if "warfarin" in meds and "aspirin" in meds:
        warnings.append("Potential interaction: warfarin with aspirin may increase bleeding risk.")
    if "metformin" in meds and "contrast dye" in meds:
        warnings.append("Potential interaction: metformin with contrast dye may increase lactic acidosis risk.")
    return {"medications": sorted(meds), "warnings": warnings}


@tool
def get_session_context(session_id: str, limit: int = 10) -> Dict[str, Any]:
    """Retrieve session summary and recent turns."""
    store = build_store_from_env()
    recent = store.get_recent(session_id, limit=limit)
    summary = store.get_summary(session_id)
    return {"summary": summary, "recent_turns": recent}


@tool
def calculate(expression: str) -> str:
    """Safely evaluate simple arithmetic expressions."""
    allowed = set("0123456789+-*/(). ")
    if any(ch not in allowed for ch in expression):
        return "Unsupported characters in expression."
    try:
        result = eval(expression, {"__builtins__": {}}, {})
    except Exception:
        return "Unable to evaluate expression."
    return str(result)


@tool
def get_current_date() -> str:
    """Return current date in ISO format."""
    return dt.datetime.utcnow().isoformat()


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
