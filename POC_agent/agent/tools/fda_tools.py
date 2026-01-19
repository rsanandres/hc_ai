"""Tools for openFDA endpoints."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx
from langchain_core.tools import tool

_OPENFDA_BASE_URL = os.getenv("OPENFDA_BASE_URL", "https://api.fda.gov")
_OPENFDA_API_KEY = os.getenv("OPENFDA_API_KEY")


async def _openfda_get(path: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if _OPENFDA_API_KEY and "api_key" not in params:
        params["api_key"] = _OPENFDA_API_KEY
    url = f"{_OPENFDA_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            return {"error": f"openFDA request failed: {exc}"}


@tool
async def search_fda_drugs(drug_name: str, limit: int = 5) -> Dict[str, Any]:
    """Search openFDA drug labels by generic or brand name."""
    if not drug_name.strip():
        return {"error": "drug_name is required", "results": [], "count": 0}
    query = f'(openfda.generic_name:"{drug_name}" OR openfda.brand_name:"{drug_name}")'
    data = await _openfda_get("/drug/label.json", {"search": query, "limit": limit})
    if "error" in data:
        return {"error": data["error"], "results": [], "count": 0}
    results = data.get("results", [])
    return {"results": results, "count": len(results)}


@tool
async def get_drug_recalls(drug_name: str, limit: int = 5) -> Dict[str, Any]:
    """Return recent FDA drug recalls by name."""
    if not drug_name.strip():
        return {"error": "drug_name is required", "results": [], "count": 0}
    query = f'(openfda.generic_name:"{drug_name}" OR openfda.brand_name:"{drug_name}")'
    data = await _openfda_get("/drug/enforcement.json", {"search": query, "limit": limit})
    if "error" in data:
        return {"error": data["error"], "results": [], "count": 0}
    recalls = []
    for item in data.get("results", []):
        recalls.append(
            {
                "reason": item.get("reason_for_recall", ""),
                "status": item.get("status", ""),
                "classification": item.get("classification", ""),
                "recall_initiation_date": item.get("recall_initiation_date", ""),
            }
        )
    return {"results": recalls, "count": len(recalls)}


@tool
async def get_drug_shortages(drug_name: str, limit: int = 5) -> Dict[str, Any]:
    """Return current FDA drug shortages by name."""
    if not drug_name.strip():
        return {"error": "drug_name is required", "results": [], "count": 0}
    query = f'(openfda.generic_name:"{drug_name}" OR openfda.brand_name:"{drug_name}")'
    data = await _openfda_get("/drug/shortages.json", {"search": query, "limit": limit})
    if "error" in data:
        return {"error": data["error"], "results": [], "count": 0}
    shortages = []
    for item in data.get("results", []):
        shortages.append(
            {
                "status": item.get("status", ""),
                "availability": item.get("availability", ""),
                "reason": item.get("reason", ""),
                "updated": item.get("updated", ""),
            }
        )
    return {"results": shortages, "count": len(shortages)}


@tool
async def get_faers_events(drug_name: str, limit: int = 5) -> Dict[str, Any]:
    """Return adverse event summaries for a drug from FAERS."""
    if not drug_name.strip():
        return {"error": "drug_name is required", "results": [], "count": 0}
    query = f'patient.drug.medicinalproduct:"{drug_name}"'
    data = await _openfda_get("/drug/event.json", {"search": query, "limit": limit})
    if "error" in data:
        return {"error": data["error"], "results": [], "count": 0}
    events = []
    for item in data.get("results", []):
        reactions = item.get("patient", {}).get("reaction", [])
        events.append(
            {
                "safetyreportid": item.get("safetyreportid", ""),
                "receivedate": item.get("receivedate", ""),
                "reactions": [r.get("reactionmeddrapt", "") for r in reactions],
            }
        )
    return {"results": events, "count": len(events)}
