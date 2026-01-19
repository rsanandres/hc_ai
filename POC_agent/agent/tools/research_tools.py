"""Tools for literature and research lookups."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import httpx
from langchain_core.tools import tool

_NCBI_BASE_URL = os.getenv("NCBI_API_URL", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils")
_NCBI_API_KEY = os.getenv("NCBI_API_KEY")
_CLINICAL_TRIALS_URL = os.getenv("CLINICAL_TRIALS_API_URL", "https://clinicaltrials.gov/api/v2/studies")
_WHO_GHO_URL = os.getenv("WHO_GHO_API_URL", "https://ghoapi.azureedge.net/api")


async def _get_json(url: str, params: Dict[str, Any]) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": f"request failed: {exc}"}


@tool
async def search_pubmed(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search PubMed articles and return summaries."""
    if not query.strip():
        return {"error": "query is required", "results": [], "count": 0}
    params = {"db": "pubmed", "term": query, "retmode": "json", "retmax": max_results}
    if _NCBI_API_KEY:
        params["api_key"] = _NCBI_API_KEY
    esearch = await _get_json(f"{_NCBI_BASE_URL}/esearch.fcgi", params)
    if "error" in esearch:
        return {"error": esearch["error"], "results": [], "count": 0}
    ids = esearch.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return {"results": [], "count": 0}
    summary_params = {"db": "pubmed", "id": ",".join(ids), "retmode": "json"}
    if _NCBI_API_KEY:
        summary_params["api_key"] = _NCBI_API_KEY
    esummary = await _get_json(f"{_NCBI_BASE_URL}/esummary.fcgi", summary_params)
    if "error" in esummary:
        return {"error": esummary["error"], "results": [], "count": 0}
    results = []
    for uid in ids:
        item = esummary.get("result", {}).get(uid, {})
        results.append(
            {
                "uid": uid,
                "title": item.get("title", ""),
                "source": item.get("source", ""),
                "pubdate": item.get("pubdate", ""),
            }
        )
    return {"results": results, "count": len(results)}


@tool
async def search_clinical_trials(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Search ClinicalTrials.gov for studies matching a query."""
    if not query.strip():
        return {"error": "query is required", "results": [], "count": 0}
    params = {"query.term": query, "pageSize": max_results}
    data = await _get_json(_CLINICAL_TRIALS_URL, params)
    if "error" in data:
        return {"error": data["error"], "results": [], "count": 0}
    results: List[Dict[str, Any]] = []
    for study in data.get("studies", []):
        protocol = study.get("protocolSection", {})
        identification = protocol.get("identificationModule", {})
        status = protocol.get("statusModule", {})
        results.append(
            {
                "nct_id": identification.get("nctId", ""),
                "title": identification.get("briefTitle", ""),
                "overall_status": status.get("overallStatus", ""),
            }
        )
    return {"results": results, "count": len(results)}


@tool
async def get_who_stats(indicator_name: str, max_results: int = 5) -> Dict[str, Any]:
    """Search WHO GHO indicators by name."""
    if not indicator_name.strip():
        return {"error": "indicator_name is required", "results": [], "count": 0}
    url = f"{_WHO_GHO_URL}/Indicator"
    params = {"$filter": f"contains(IndicatorName,'{indicator_name}')", "$top": max_results}
    data = await _get_json(url, params)
    if "error" in data:
        return {"error": data["error"], "results": [], "count": 0}
    results = []
    for item in data.get("value", []):
        results.append(
            {
                "code": item.get("IndicatorCode", ""),
                "name": item.get("IndicatorName", ""),
                "source": item.get("Source", ""),
            }
        )
    return {"results": results, "count": len(results)}
