"""Load and manage agent prompts from external YAML file."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

import yaml

PROMPTS_FILE = Path(__file__).resolve().parents[1] / "prompts.yaml"

_prompts_cache: Optional[Dict[str, object]] = None


def load_prompts(reload: bool = False) -> Dict[str, object]:
    """Load prompts from YAML file with caching."""
    global _prompts_cache
    if _prompts_cache is not None and not reload:
        return _prompts_cache

    prompts_path = Path(os.getenv("AGENT_PROMPTS_FILE", str(PROMPTS_FILE)))
    with prompts_path.open("r", encoding="utf-8") as handle:
        _prompts_cache = yaml.safe_load(handle) or {}
    return _prompts_cache


def get_researcher_prompt(patient_id: Optional[str] = None) -> str:
    """Get researcher system prompt, optionally with patient context."""
    prompts = load_prompts()
    base = str(prompts.get("researcher", {}).get("system_prompt", "")).strip()

    fragments = prompts.get("fragments", {})
    base += "\n\n" + str(fragments.get("safety_reminder", "")).strip()
    base += "\n\n" + str(fragments.get("citation_format", "")).strip()

    if patient_id:
        context = str(fragments.get("patient_context", "")).format(patient_id=patient_id)
        base += "\n\n" + context.strip()

    return base.strip()


def get_validator_prompt() -> str:
    """Get validator system prompt."""
    prompts = load_prompts()
    base = str(prompts.get("validator", {}).get("system_prompt", "")).strip()
    fragments = prompts.get("fragments", {})
    base += "\n\n" + str(fragments.get("safety_reminder", "")).strip()
    return base.strip()


def reload_prompts() -> Dict[str, object]:
    """Force reload prompts from file (useful for hot-reloading in dev)."""
    return load_prompts(reload=True)
