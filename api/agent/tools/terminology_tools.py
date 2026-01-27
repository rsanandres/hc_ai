"""Tools for medical terminology lookups (ICD-10, RxNorm)."""

from __future__ import annotations

import os
from typing import Any, Dict, List

import httpx
from langchain_core.tools import tool

from api.agent.tools.schemas import TerminologyResponse
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
        return TerminologyResponse(
            success=False,
            error="term is required",
            results=[],
            count=0,
        ).model_dump()
    url = f"{_ICD10_BASE_URL}/search"
    data = await _http_get(url, {"sf": "code,name", "terms": term, "maxList": max_results})
    if "error" in data:
        return TerminologyResponse(
            success=False,
            error=str(data.get("error")),
            results=[],
            count=0,
        ).model_dump()
    results: List[Dict[str, str]] = []
    try:
        # API response format: [count, [codes], null, [[code, name], ...]]
        # data[0] = count
        # data[1] = array of codes
        # data[2] = null (not used)
        # data[3] = array of [code, name] pairs
        if not isinstance(data, list) or len(data) < 4:
            return TerminologyResponse(
                success=False,
                error="unexpected ICD-10 response format",
                results=[],
                count=0,
            ).model_dump()
        
        # Use data[3] which contains [code, name] pairs
        code_name_pairs = data[3] if data[3] else []
        for pair in code_name_pairs:
            if isinstance(pair, list) and len(pair) >= 2:
                results.append({"code": pair[0], "name": pair[1]})
    except Exception as exc:  # noqa: BLE001
        return TerminologyResponse(
            success=False,
            error=f"unexpected ICD-10 response: {exc}",
            results=[],
            count=0,
        ).model_dump()
    return TerminologyResponse(results=results, count=len(results)).model_dump()


@tool
async def validate_icd10_code(code: str) -> Dict[str, Any]:
    """Validate whether an ICD-10-CM code exists by searching for exact code match."""
    if not code.strip():
        return TerminologyResponse(
            success=False,
            error="code is required",
            results=[],
            count=0,
        ).model_dump()
    
    # Use the search endpoint with the exact code
    url = f"{_ICD10_BASE_URL}/search"
    data = await _http_get(url, {"sf": "code,name", "terms": code, "maxList": 10})
    
    if "error" in data:
        return TerminologyResponse(
            success=False,
            error=str(data.get("error")),
            results=[],
            count=0,
        ).model_dump()
    
    # Parse response: [count, [codes], null, [[code, name], ...]]
    try:
        if not isinstance(data, list) or len(data) < 4:
            return TerminologyResponse(
                results=[{"valid": False, "code": code}],
                count=1,
            ).model_dump()
        
        code_name_pairs = data[3] if data[3] else []
        for pair in code_name_pairs:
            if isinstance(pair, list) and len(pair) >= 2:
                found_code = pair[0]
                if found_code.lower() == code.lower():
                    return TerminologyResponse(
                        results=[{"valid": True, "code": found_code, "name": pair[1]}],
                        count=1,
                    ).model_dump()
    except Exception:  # noqa: BLE001
        pass
    
    return TerminologyResponse(results=[{"valid": False, "code": code}], count=1).model_dump()


@tool
async def lookup_rxnorm(drug_name: str) -> Dict[str, Any]:
    """Lookup RxNorm RxCUI by drug name."""
    if not drug_name.strip():
        return TerminologyResponse(
            success=False,
            error="drug_name is required",
            results=[],
            count=0,
        ).model_dump()
    url = f"{_RXNORM_BASE_URL}/rxcui.json"
    data = await _http_get(url, {"name": drug_name})
    if "error" in data:
        return TerminologyResponse(
            success=False,
            error=str(data.get("error")),
            results=[],
            count=0,
        ).model_dump()
    rxcui_list = data.get("idGroup", {}).get("rxnormId", [])
    results = [{"rxcui": rxcui} for rxcui in rxcui_list]
    return TerminologyResponse(results=results, count=len(results)).model_dump()



ß