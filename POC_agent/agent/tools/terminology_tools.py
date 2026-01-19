"""Tools for medical terminology lookups (ICD-10, RxNorm)."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import httpx
from langchain_core.tools import tool

_ICD10_BASE_URL = os.getenv("ICD10_API_URL", "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3")
_RXNORM_BASE_URL = os.getenv("RXNORM_API_URL", "https://rxnav.nlm.nih.gov/REST")


async def _http_get(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": f"request failed: {exc}"}


@tool
async def search_icd10(term: str, max_results: int = 10) -> Dict[str, Any]:
    """Search ICD-10-CM codes by term."""
    if not term.strip():
        return {"error": "term is required", "results": [], "count": 0}
    url = f"{_ICD10_BASE_URL}/search"
    data = await _http_get(url, {"sf": "code,name", "terms": term, "maxList": max_results})
    if "error" in data:
        return {"error": data["error"], "results": [], "count": 0}
    results: List[Dict[str, str]] = []
    try:
        codes = data[1]
        names = data[2]
        for code, name in zip(codes, names):
            results.append({"code": code, "name": name})
    except Exception as exc:  # noqa: BLE001
        return {"error": f"unexpected ICD-10 response: {exc}", "results": [], "count": 0}
    return {"results": results, "count": len(results)}


@tool
async def validate_icd10_code(code: str) -> Dict[str, Any]:
    """Validate whether an ICD-10-CM code exists."""
    if not code.strip():
        return {"valid": False, "error": "code is required"}
    data = await search_icd10.ainvoke({"term": code, "max_results": 5})
    if "error" in data:
        return {"valid": False, "error": data["error"]}
    for item in data.get("results", []):
        if item.get("code", "").lower() == code.lower():
            return {"valid": True, "code": item.get("code", ""), "name": item.get("name", "")}
    return {"valid": False, "code": code}


@tool
async def lookup_rxnorm(drug_name: str) -> Dict[str, Any]:
    """Lookup RxNorm RxCUI by drug name."""
    if not drug_name.strip():
        return {"error": "drug_name is required", "results": [], "count": 0}
    url = f"{_RXNORM_BASE_URL}/rxcui.json"
    data = await _http_get(url, {"name": drug_name})
    if "error" in data:
        return {"error": data["error"], "results": [], "count": 0}
    rxcui_list = data.get("idGroup", {}).get("rxnormId", [])
    results = [{"rxcui": rxcui} for rxcui in rxcui_list]
    return {"results": results, "count": len(results)}


@tool
async def get_drug_interactions(rxcui: str) -> Dict[str, Any]:
    """Get RxNorm interaction data for a specific RxCUI."""
    if not rxcui.strip():
        return {"error": "rxcui is required", "results": [], "count": 0}
    url = f"{_RXNORM_BASE_URL}/interaction/list.json"
    data = await _http_get(url, {"rxcuis": rxcui})
    if "error" in data:
        return {"error": data["error"], "results": [], "count": 0}
    interactions = []
    for group in data.get("fullInteractionTypeGroup", []):
        for interaction_type in group.get("fullInteractionType", []):
            for pair in interaction_type.get("interactionPair", []):
                interactions.append(
                    {
                        "description": pair.get("description", ""),
                        "severity": pair.get("severity", ""),
                        "interaction_concept": [
                            concept.get("minConceptItem", {}).get("name", "")
                            for concept in pair.get("interactionConcept", [])
                        ],
                    }
                )
    return {"results": interactions, "count": len(interactions)}
