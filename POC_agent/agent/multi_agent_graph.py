"""LangGraph multi-agent workflow: Researcher -> Validator."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, TypedDict

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph

from POC_agent.agent.config import get_llm
from POC_agent.agent.prompt_loader import get_researcher_prompt, get_validator_prompt
from POC_agent.agent.tools import (
    calculate,
    calculate_bmi,
    calculate_bsa,
    calculate_creatinine_clearance,
    calculate_gfr,
    cross_reference_meds,
    get_drug_interactions,
    get_drug_recalls,
    get_drug_shortages,
    get_current_date,
    get_patient_timeline,
    get_session_context,
    get_faers_events,
    get_who_stats,
    lookup_loinc,
    lookup_rxnorm,
    search_clinical_notes,
    search_clinical_trials,
    search_fda_drugs,
    search_icd10,
    search_patient_records,
    search_pubmed,
    validate_icd10_code,
    validate_dosage,
)


class AgentState(TypedDict, total=False):
    query: str
    session_id: str
    patient_id: Optional[str]
    researcher_output: str
    validator_output: str
    validation_result: str
    final_response: str
    iteration_count: int
    tools_called: List[str]
    sources: List[Dict[str, Any]]


_RESEARCHER_AGENT: Any = None
_VALIDATOR_AGENT: Any = None


def _extract_tool_calls(messages: List[Any]) -> List[str]:
    calls: List[str] = []
    for message in messages:
        if isinstance(message, ToolMessage):
            if message.name:
                calls.append(message.name)
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            calls.extend([call.get("name", "") for call in message.tool_calls])
    return [call for call in calls if call]


def _get_researcher_agent() -> Any:
    global _RESEARCHER_AGENT
    if _RESEARCHER_AGENT is None:
        llm = get_llm()
        tools = [
            search_patient_records,
            search_clinical_notes,
            get_patient_timeline,
            cross_reference_meds,
            get_session_context,
            calculate,
            calculate_bmi,
            calculate_bsa,
            calculate_creatinine_clearance,
            calculate_gfr,
            get_current_date,
            search_pubmed,
            search_clinical_trials,
            search_icd10,
            search_fda_drugs,
            get_drug_recalls,
            get_drug_shortages,
            get_drug_interactions,
        ]
        _RESEARCHER_AGENT = create_agent(llm, tools, system_prompt="You are a medical researcher.")
    return _RESEARCHER_AGENT


def _get_validator_agent() -> Any:
    global _VALIDATOR_AGENT
    if _VALIDATOR_AGENT is None:
        llm = get_llm()
        tools = [
            validate_dosage,
            lookup_loinc,
            validate_icd10_code,
            lookup_rxnorm,
            get_who_stats,
            get_faers_events,
            get_drug_recalls,
            cross_reference_meds,
            get_current_date,
        ]
        _VALIDATOR_AGENT = create_agent(llm, tools, system_prompt="You are a medical validator.")
    return _VALIDATOR_AGENT


def _researcher_node(state: AgentState) -> AgentState:
    max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    system_prompt = get_researcher_prompt(state.get("patient_id"))
    messages = [SystemMessage(content=system_prompt), HumanMessage(content=state["query"])]
    if state.get("validator_output"):
        messages.append(SystemMessage(content=f"Validator feedback:\n{state['validator_output']}"))

    agent = _get_researcher_agent()
    result = agent.invoke({"messages": messages}, config={"recursion_limit": max_iterations})
    output_messages = result.get("messages", [])
    response_text = ""
    if output_messages:
        last = output_messages[-1]
        response_text = getattr(last, "content", "") if hasattr(last, "content") else str(last)

    tools_called = (state.get("tools_called") or []) + _extract_tool_calls(output_messages)
    return {
        **state,
        "researcher_output": response_text,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "tools_called": tools_called,
        "sources": state.get("sources", []),
    }


def _validator_node(state: AgentState) -> AgentState:
    max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    system_prompt = get_validator_prompt()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Researcher response:\n{state.get('researcher_output', '')}"),
    ]

    agent = _get_validator_agent()
    result = agent.invoke({"messages": messages}, config={"recursion_limit": max_iterations})
    output_messages = result.get("messages", [])
    response_text = ""
    if output_messages:
        last = output_messages[-1]
        response_text = getattr(last, "content", "") if hasattr(last, "content") else str(last)

    tools_called = (state.get("tools_called") or []) + _extract_tool_calls(output_messages)
    validation_result = "NEEDS_REVISION"
    for line in response_text.splitlines():
        if line.strip().startswith("VALIDATION_STATUS"):
            validation_result = line.split(":", 1)[-1].strip()
            break

    return {
        **state,
        "validator_output": response_text,
        "validation_result": validation_result,
        "tools_called": tools_called,
        "sources": state.get("sources", []),
    }


def _respond_node(state: AgentState) -> AgentState:
    validation_result = state.get("validation_result", "NEEDS_REVISION")
    if validation_result == "PASS":
        final_response = state.get("researcher_output", "")
    else:
        final_response = f"{state.get('validator_output', '')}\n\nRESEARCHER_RESPONSE:\n{state.get('researcher_output', '')}"
    return {**state, "final_response": final_response}


def _route_after_validation(state: AgentState) -> str:
    validation_result = state.get("validation_result", "NEEDS_REVISION")
    if validation_result in {"PASS", "FAIL"}:
        return "respond"
    if state.get("iteration_count", 0) >= 2:
        return "respond"
    return "researcher"


def create_multi_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("researcher", _researcher_node)
    graph.add_node("validator", _validator_node)
    graph.add_node("respond", _respond_node)

    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "validator")
    graph.add_conditional_edges("validator", _route_after_validation)
    graph.add_edge("respond", END)
    return graph.compile()
