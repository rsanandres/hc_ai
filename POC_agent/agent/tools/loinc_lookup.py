"""LOINC lookup tool via FHIR API."""

from __future__ import annotations

from typing import Any, Dict

import httpx
from langchain_core.tools import tool


LOINC_BASE_URL = "https://fhir.loinc.org"


def _extract_parameters(payload: Dict[str, Any]) -> Dict[str, Any]:
    params = {}
    for item in payload.get("parameter", []):
        name = item.get("name")
        if not name:
            continue
        if "valueString" in item:
            params[name] = item["valueString"]
        elif "valueCode" in item:
            params[name] = item["valueCode"]
        elif "valueUri" in item:
            params[name] = item["valueUri"]
    return params


@tool
async def lookup_loinc(code: str) -> Dict[str, Any]:
    """Validate LOINC code and return basic metadata."""
    url = f"{LOINC_BASE_URL}/CodeSystem/$lookup"
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            response = await client.get(url, params={"code": code})
            if response.status_code == 404:
                return {"valid": False, "code": code}
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return {"valid": False, "code": code, "error": str(exc)}

    payload = response.json()
    data = _extract_parameters(payload)
    return {
        "valid": True,
        "code": code,
        "long_name": data.get("display", ""),
        "component": data.get("component", ""),
        "system": data.get("system", ""),
        "method": data.get("method", ""),
    }
