"""Guardrails AI setup for validating agent output."""

from __future__ import annotations

import os
from typing import Optional


def setup_guard() -> Optional[object]:
    """Initialize Guardrails validators if enabled."""

    if os.getenv("GUARDRAILS_ENABLED", "true").lower() not in {"1", "true", "yes"}:
        return None

    try:
        from guardrails import Guard
        from guardrails.hub import DetectHallucination, DetectPII
    except Exception:
        return None

    guard = Guard().use(
        DetectPII(threshold=0.5),
        DetectHallucination(threshold=0.5),
    )
    return guard
