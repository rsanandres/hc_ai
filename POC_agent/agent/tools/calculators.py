"""Medical calculator tools."""

from __future__ import annotations

import math
from typing import Dict, Optional, Union

from langchain_core.tools import tool


def _egfr_stage(gfr: float) -> str:
    if gfr >= 90:
        return "G1"
    if gfr >= 60:
        return "G2"
    if gfr >= 45:
        return "G3a"
    if gfr >= 30:
        return "G3b"
    if gfr >= 15:
        return "G4"
    return "G5"


@tool
def calculate_gfr(
    age: int,
    sex: str,
    creatinine: float,
) -> Dict[str, Union[float, str]]:
    """Calculate eGFR using CKD-EPI 2021 equation (no race adjustment)."""
    sex_lower = sex.strip().lower()
    if sex_lower not in {"male", "female"}:
        raise ValueError("sex must be 'male' or 'female'.")
    if age <= 0 or creatinine <= 0:
        raise ValueError("age and creatinine must be positive.")

    k = 0.7 if sex_lower == "female" else 0.9
    alpha = -0.241 if sex_lower == "female" else -0.302
    min_ratio = min(creatinine / k, 1) ** alpha
    max_ratio = max(creatinine / k, 1) ** -1.200
    sex_factor = 1.012 if sex_lower == "female" else 1.0
    gfr = 142 * min_ratio * max_ratio * (0.9938 ** age) * sex_factor

    return {
        "gfr": round(gfr, 1),
        "stage": _egfr_stage(gfr),
        "input_race": race,
    }


@tool
def calculate_bmi(weight_kg: float, height_cm: float) -> Dict[str, Union[float, str]]:
    """Calculate body mass index and category."""
    if weight_kg <= 0 or height_cm <= 0:
        raise ValueError("weight_kg and height_cm must be positive.")
    height_m = height_cm / 100.0
    bmi = weight_kg / (height_m ** 2)
    if bmi < 18.5:
        category = "Underweight"
    elif bmi < 25:
        category = "Normal"
    elif bmi < 30:
        category = "Overweight"
    else:
        category = "Obese"
    return {"bmi": round(bmi, 1), "category": category}


@tool
def calculate_bsa(weight_kg: float, height_cm: float) -> Dict[str, float]:
    """Calculate body surface area using Mosteller formula."""
    if weight_kg <= 0 or height_cm <= 0:
        raise ValueError("weight_kg and height_cm must be positive.")
    bsa = math.sqrt((height_cm * weight_kg) / 3600.0)
    return {"bsa": round(bsa, 3)}


@tool
def calculate_creatinine_clearance(
    age: int,
    weight_kg: float,
    sex: str,
    creatinine: float,
) -> Dict[str, float]:
    """Calculate creatinine clearance using Cockcroft-Gault formula."""
    sex_lower = sex.strip().lower()
    if sex_lower not in {"male", "female"}:
        raise ValueError("sex must be 'male' or 'female'.")
    if age <= 0 or weight_kg <= 0 or creatinine <= 0:
        raise ValueError("age, weight_kg, and creatinine must be positive.")

    base = ((140 - age) * weight_kg) / (72 * creatinine)
    if sex_lower == "female":
        base *= 0.85
    return {"creatinine_clearance": round(base, 1)}
