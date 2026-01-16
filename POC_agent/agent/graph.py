"""LangGraph ReAct agent definition."""

from __future__ import annotations

import os
from typing import Any

from langchain.agents import create_agent

from POC_agent.agent.config import get_llm
from POC_agent.agent.tools import (
    calculate,
    cross_reference_meds,
    get_current_date,
    get_patient_timeline,
    get_session_context,
    search_clinical_notes,
)


_AGENT: Any = None


def get_agent() -> Any:
    global _AGENT
    if _AGENT is not None:
        return _AGENT

    llm = get_llm()
    tools = [
        search_clinical_notes,
        get_patient_timeline,
        cross_reference_meds,
        get_session_context,
        calculate,
        get_current_date,
    ]
    system_prompt = os.getenv(
        "AGENT_SYSTEM_PROMPT",
        (
            "You are a medical assistant. Use tools to retrieve facts, cite sources, "
            "and express uncertainty when appropriate. Do not invent medical facts."
        ),
    )
    _AGENT = create_agent(llm, tools, system_prompt=system_prompt)
    return _AGENT
