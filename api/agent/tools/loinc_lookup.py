"""LOINC lookup tool via Regenstrief Search API."""

from __future__ import annotations

import os
from typing import Any, Dict

import httpx
from langchain_core.tools import tool

from api.agent.tools.schemas import LOINCResponse


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
                return LOINCResponse(
                    success=False,
                    error="code not found",
                    code=code,
                ).model_dump()
            response.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            return LOINCResponse(
                success=False,
                error=str(exc),
                code=code,
            ).model_dump()

    payload = response.json()
    # Response format may vary - handle both array and object responses
    # Response format: {'ResponseSummary': ..., 'Results': [...]}
    results = payload.get("Results", []) if isinstance(payload, dict) else payload
    if not results or not isinstance(results, list):
         return LOINCResponse(
            success=False,
            error="code not found or unexpected format",
            code=code,
        ).model_dump()
        
    data = results[0]
    
    name = data.get("LONG_COMMON_NAME", data.get("COMPONENT", ""))
    if not name:
        # Debugging: if name is missing, return success=False with raw keys to debug
        return LOINCResponse(
            success=False,
            error=f"Schema mismatch. Available keys: {list(data.keys())}",
            code=code,
        ).model_dump()

    return LOINCResponse(
        code=data.get("LOINC_NUM", code),
        name=name,
        component=data.get("COMPONENT", ""),
        system=data.get("SYSTEM", ""),
    ).model_dump()
