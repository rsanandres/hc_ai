"""LOINC lookup tool via Regenstrief Search API."""

from __future__ import annotations

import os
from typing import Any, Dict

import httpx
from langchain_core.tools import tool


LOINC_BASE_URL = "https://loinc.regenstrief.org"


@tool
async def lookup_loinc(code: str) -> Dict[str, Any]:
    """Validate LOINC code and return basic metadata."""
    url = f"{LOINC_BASE_URL}/searchapi/loincs"
    
    # Get credentials from environment
    username = os.getenv("LOINC_USERNAME")
    password = os.getenv("LOINC_PASSWORD")
    
    # Set up basic auth if credentials are available
    auth = None
    if username and password:
        auth = (username, password)
    
    async with httpx.AsyncClient(timeout=20, auth=auth) as client:
        try:
            response = await client.get(url, params={"query": code})
            if response.status_code == 404:
                return {"valid": False, "code": code}
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return {"valid": False, "code": code, "error": str(exc)}

    payload = response.json()
    # Response format may vary - handle both array and object responses
    if isinstance(payload, list):
        if not payload:
            return {"valid": False, "code": code, "error": "code not found"}
        # Use first result if multiple found
        data = payload[0]
    else:
        data = payload
    
    return {
        "valid": True,
        "code": data.get("LOINC_NUM", code),
        "long_name": data.get("LONG_COMMON_NAME", data.get("COMPONENT", "")),
        "component": data.get("COMPONENT", ""),
        "system": data.get("SYSTEM", ""),
        "method": data.get("METHOD", ""),
    }
