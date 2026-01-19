"""Dosage validation tool using openFDA labels."""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional

import httpx
from langchain_core.tools import tool

OPENFDA_URL = os.getenv("OPENFDA_LABEL_URL", "https://api.fda.gov/drug/label.json")


def _parse_dose_values(text: str) -> List[Dict[str, Any]]:
    pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g)\b", re.IGNORECASE)
    values: List[Dict[str, Any]] = []
    for match in pattern.finditer(text):
        values.append({"value": float(match.group(1)), "unit": match.group(2).lower()})
    return values


def _normalize_unit(unit: str) -> str:
    unit = unit.strip().lower()
    if unit in {"mcg", "ug"}:
        return "mcg"
    if unit in {"g", "gram", "grams"}:
        return "g"
    return "mg"


def _dose_in_unit(value: float, unit: str, target_unit: str) -> Optional[float]:
    unit = _normalize_unit(unit)
    target_unit = _normalize_unit(target_unit)
    if unit == target_unit:
        return value
    if unit == "g" and target_unit == "mg":
        return value * 1000
    if unit == "mg" and target_unit == "g":
        return value / 1000
    if unit == "mcg" and target_unit == "mg":
        return value / 1000
    if unit == "mg" and target_unit == "mcg":
        return value * 1000
    return None


@tool
async def validate_dosage(
    drug_name: str,
    dose_amount: float,
    dose_unit: str,
    frequency: str,
    patient_weight_kg: Optional[float] = None,
    patient_gfr: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Validate dosage using openFDA labels.
    Returns dict with validity, warnings, and label excerpt.
    """
    if dose_amount <= 0:
        return {"valid": False, "warning": "dose_amount must be positive"}

    if patient_gfr is not None and patient_gfr < 30:
        return {
            "valid": False,
            "warning": "Renal impairment detected (GFR < 30). Dose adjustment required.",
            "frequency": frequency,
        }

    query = f'(openfda.generic_name:"{drug_name}" OR openfda.brand_name:"{drug_name}")'
    params = {"search": query, "limit": 1}
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            response = await client.get(OPENFDA_URL, params=params)
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:  # noqa: BLE001
            return {
                "valid": False,
                "warning": f"openFDA request failed: {exc}",
                "frequency": frequency,
            }

    results = payload.get("results", [])
    if not results:
        return {
            "valid": False,
            "warning": "No openFDA label found for drug.",
            "frequency": frequency,
        }

    label = results[0]
    dosage_sections = label.get("dosage_and_administration", [])
    dosage_text = " ".join(dosage_sections) if isinstance(dosage_sections, list) else str(dosage_sections)
    dose_values = _parse_dose_values(dosage_text)

    normalized_unit = _normalize_unit(dose_unit)
    converted_values = []
    for item in dose_values:
        converted = _dose_in_unit(item["value"], item["unit"], normalized_unit)
        if converted is not None:
            converted_values.append(converted)

    valid = None
    warning = ""
    if converted_values:
        min_dose = min(converted_values)
        max_dose = max(converted_values)
        valid = min_dose <= dose_amount <= max_dose
        if not valid:
            warning = f"Dose outside label range ({min_dose}-{max_dose} {normalized_unit})."
    else:
        valid = True
        warning = "Unable to parse label dose range; manual review recommended."

    return {
        "valid": valid,
        "warning": warning,
        "frequency": frequency,
        "label_excerpt": dosage_text[:500],
        "patient_weight_kg": patient_weight_kg,
    }
