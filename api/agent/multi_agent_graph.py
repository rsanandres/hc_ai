"""LangGraph multi-agent workflow: Researcher -> Validator."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph

from api.agent.config import get_llm
from api.agent.prompt_loader import (
    get_researcher_prompt,
    get_validator_prompt,
    get_conversational_prompt
)
from api.agent.tools import (
    calculate,
    cross_reference_meds,
    get_current_date,
    get_patient_timeline,
    get_session_context,
    lookup_loinc,
    lookup_rxnorm,
    search_clinical_notes,
    search_icd10,
    search_patient_records,
    validate_icd10_code,
)

# Import session store for automatic history injection
try:
    from api.session.store_dynamodb import get_session_store
    SESSION_STORE_AVAILABLE = True
except ImportError:
    SESSION_STORE_AVAILABLE = False
    get_session_store = None

# Import query classifier
from api.agent.query_classifier import QueryClassifier, QueryType


class AgentState(TypedDict, total=False):
    query: str
    session_id: str
    patient_id: Optional[str]
    # Query classification
    query_type: str  # "conversational" | "medical" | "mixed" | "unclear"
    classification_confidence: float
    classification_method: str
    should_acknowledge_greeting: bool
    # Agent outputs
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


def _extract_response_text(messages: List[Any]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and getattr(message, "content", ""):
            return str(message.content)
    for message in reversed(messages):
        if getattr(message, "content", ""):
            return str(message.content)
    if messages:
        last = messages[-1]
        return getattr(last, "content", "") if hasattr(last, "content") else str(last)
    return ""


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
            search_icd10,
            calculate,
            get_current_date,
        ]
        _RESEARCHER_AGENT = create_react_agent(llm, tools)
    return _RESEARCHER_AGENT


def _get_validator_agent() -> Any:
    global _VALIDATOR_AGENT
    if _VALIDATOR_AGENT is None:
        llm = get_llm()
        tools = [
            validate_icd10_code,
            lookup_loinc,
            lookup_rxnorm,
            get_current_date,
        ]
        _VALIDATOR_AGENT = create_react_agent(llm, tools)
    return _VALIDATOR_AGENT


def _load_conversation_history(session_id: str, limit: int = 10) -> List[Any]:
    """Load recent conversation history from session store and convert to messages."""
    if not SESSION_STORE_AVAILABLE:
        return []
    
    try:
        store = get_session_store()
        recent_turns = store.get_recent(session_id, limit=limit)
        
        # Convert turns to messages (oldest first for chronological order)
        # get_recent returns newest first, so we reverse to get chronological
        history_messages: List[Any] = []
        for turn in reversed(recent_turns):
            role = turn.get("role", "")
            text = turn.get("text", "")
            if not text:
                continue
            
            if role == "user":
                history_messages.append(HumanMessage(content=text))
            elif role == "assistant":
                history_messages.append(AIMessage(content=text))
        
        return history_messages
    except Exception:
        # If session store is not available or fails, continue without history
        return []


async def _researcher_node(state: AgentState) -> AgentState:
    max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    system_prompt = get_researcher_prompt(state.get("patient_id"))
    
    # Build messages list with conversation history
    messages = [SystemMessage(content=system_prompt)]
    
    # Automatically inject conversation history if session_id is available
    session_id = state.get("session_id")
    if session_id:
        history_messages = _load_conversation_history(session_id, limit=10)
        if history_messages:
            messages.extend(history_messages)
    
    # Add current query
    messages.append(HumanMessage(content=state["query"]))
    
    # Add validator feedback if present (for revision cycles)
    if state.get("validator_output"):
        messages.append(SystemMessage(content=f"Validator feedback:\n{state['validator_output']}"))

    # Add greeting instruction if this was a mixed query
    if state.get("should_acknowledge_greeting", False):
        messages.append(SystemMessage(content="IMPORTANT: The user included a greeting (e.g., 'Hello'). Please explicitly acknowledge it warmly at the beginning of your response before addressing the clinical question."))

    agent = _get_researcher_agent()
    result = await agent.ainvoke({"messages": messages}, config={"recursion_limit": max_iterations})
    output_messages = result.get("messages", [])
    response_text = _extract_response_text(output_messages)

    tools_called = (state.get("tools_called") or []) + _extract_tool_calls(output_messages)
    return {
        **state,
        "researcher_output": response_text,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "tools_called": tools_called,
        "sources": state.get("sources", []),
    }


async def _validator_node(state: AgentState) -> AgentState:
    # CALCULATE REMAINING ATTEMPTS
    current_iter = state.get("iteration_count", 0)
    max_iter = int(os.getenv("AGENT_MAX_ITERATIONS", "5"))
    remaining = max_iter - current_iter

    # INJECT INTO PROMPT
    system_prompt = get_validator_prompt().format(
        remaining_attempts=remaining
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                "Validate the response below. If the researcher response is empty, "
                "evaluate safety based on the user query alone.\n\n"
                f"User query:\n{state.get('query', '')}\n\n"
                f"Researcher response:\n{state.get('researcher_output', '')}"
            )
        ),
    ]

    agent = _get_validator_agent()
    result = await agent.ainvoke({"messages": messages}, config={"recursion_limit": max_iterations})
    output_messages = result.get("messages", [])
    response_text = _extract_response_text(output_messages)

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


def _classify_node(state: AgentState) -> dict:
    """Classify the user query to route to appropriate path."""
    query = state.get("query", "")
    session_id = state.get("session_id", "")
    
    # Get session context if available
    context = {}
    if SESSION_STORE_AVAILABLE and get_session_store:
        try:
            store = get_session_store()
            # Basic context from metadata (could be expanded)
            summary = store.get_summary(session_id)
            context["last_query_type"] = summary.get("last_query_type")
        except Exception:
            pass
            
    # Classify query
    classifier = QueryClassifier()
    result = classifier.classify(query, session_context=context)
    
    # Update session metadata with query type (async side effect)
    if SESSION_STORE_AVAILABLE and get_session_store:
        try:
            store = get_session_store()
            store.update_summary(session_id, {"last_query_type": result.query_type.value})
        except Exception:
            pass
            
    return {
        **state,
        "query_type": result.query_type.value,
        "classification_confidence": result.confidence,
        "classification_method": result.method,
        "should_acknowledge_greeting": result.should_acknowledge_greeting
    }


async def _conversational_responder_node(state: AgentState) -> dict:
    """Handle purely conversational queries without RAG."""
    query = state.get("query", "")
    
    system_prompt = get_conversational_prompt()
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=query)
    ]
    
    llm = get_llm()
    try:
        response_msg = await llm.ainvoke(messages)
        response = str(response_msg.content)
    except Exception as e:
        # Fallback if LLM fails
        response = f"I apologize, but I'm having trouble generating a response right now. (Error: {str(e)})"

    return {
        **state,
        "final_response": response,
        "researcher_output": response,  # Populate for API consistency
        "validation_result": "PASS"     # Skip validation
    }


def _route_after_classification(state: AgentState) -> str:
    """Route based on query classification."""
    query_type = state.get("query_type", "medical")
    
    if query_type == "conversational":
        return "conversational_responder"
    # Both "medical" and "mixed" go to researcher
    # "unclear" defaults to researcher (medical path) via classifier logic
    return "researcher"


def _route_after_validation(state: AgentState) -> str:
    validation_result = state.get("validation_result", "NEEDS_REVISION")
    query_type = state.get("query_type", "medical")
    
    # Conversational queries skip validation (already handled, but safety check)
    if query_type == "conversational":
        return "respond"
        
    if validation_result in {"PASS", "FAIL"}:
        return "respond"
    
    # Strict limit on iterations
    max_revisions = int(os.getenv("AGENT_MAX_ITERATIONS", "3"))
    if state.get("iteration_count", 0) >= max_revisions:
        return "respond"
        
    return "researcher"


def create_multi_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("classify_query", _classify_node)
    graph.add_node("conversational_responder", _conversational_responder_node)
    graph.add_node("researcher", _researcher_node)
    graph.add_node("validator", _validator_node)
    graph.add_node("respond", _respond_node)

    graph.set_entry_point("classify_query")
    graph.add_conditional_edges("classify_query", _route_after_classification)
    
    graph.add_edge("conversational_responder", END)
    
    graph.add_edge("researcher", "validator")
    graph.add_conditional_edges("validator", _route_after_validation)
    graph.add_edge("respond", END)
    return graph.compile()
