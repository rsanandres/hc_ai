"""LangGraph multi-agent workflow: Researcher -> Validator."""

from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional, TypedDict

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph

from api.agent.config import get_llm
try:
    from langgraph.errors import GraphRecursionError
except ImportError:
    # Fallback if langgraph doesn't expose this error
    GraphRecursionError = RecursionError

from api.agent.prompt_loader import (
    get_researcher_prompt,
    get_validator_prompt,
    get_conversational_prompt,
    get_response_prompt
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
from api.agent.tools.context import set_patient_context

# Import session store for automatic history injection
try:
    from api.session.store_dynamodb import get_session_store
    SESSION_STORE_AVAILABLE = True
except ImportError:
    SESSION_STORE_AVAILABLE = False
    get_session_store = None

# Import query classifier
from api.agent.query_classifier import QueryClassifier


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
    # Trajectory tracking for death loop prevention
    search_attempts: List[Dict[str, Any]]  # [{query, patient_id, results_count, iteration}]
    empty_search_count: int  # Count of consecutive empty searches


_RESEARCHER_AGENT: Any = None
_VALIDATOR_AGENT: Any = None
_RESPONSE_AGENT: Any = None


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
    import re
    content = ""
    found = False
    
    for message in reversed(messages):
        if isinstance(message, AIMessage) and getattr(message, "content", ""):
            content = str(message.content)
            found = True
            break
            
    if not found:
        for message in reversed(messages):
            if getattr(message, "content", ""):
                content = str(message.content)
                found = True
                break
                
    if not found and messages:
        last = messages[-1]
        content = getattr(last, "content", "") if hasattr(last, "content") else str(last)

    # Clean internal prompt leakage
    # Remove "VALIDATION TOOLS AVAILABLE" block
    content = re.sub(r'=+\s*VALIDATION TOOLS AVAILABLE\s*=+', '', content, flags=re.IGNORECASE)
    # Remove "OUTPUT FORMAT" block
    content = re.sub(r'=+\s*OUTPUT FORMAT.*=+', '', content, flags=re.IGNORECASE)
    
    return content.strip()


def _get_researcher_agent() -> Any:
    global _RESEARCHER_AGENT
    if _RESEARCHER_AGENT is None:
        llm = get_llm("sonnet")  # Sonnet for reasoning & tool selection
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
        _RESEARCHER_AGENT = create_agent(llm, tools)
    return _RESEARCHER_AGENT

def _get_response_agent() -> Any:
    global _RESPONSE_AGENT
    if _RESPONSE_AGENT is None:
        llm = get_llm("haiku")  # Haiku for synthesis
        _RESPONSE_AGENT = create_agent(llm)
    return _RESPONSE_AGENT

def _get_validator_agent() -> Any:
    global _VALIDATOR_AGENT
    if _VALIDATOR_AGENT is None:
        llm = get_llm("haiku")  # Haiku for validation
        tools = [
            validate_icd10_code,
            lookup_loinc,
            lookup_rxnorm,
            get_current_date,
        ]
        _VALIDATOR_AGENT = create_agent(llm, tools)
    return _VALIDATOR_AGENT


def _clean_response(text: str) -> str:
    """Strip internal details that shouldn't be shown to users."""
    import re
    
    if not text:
        return text
    
    # Remove validation YAML blocks (validation_status: PASS, issues:, etc.)
    text = re.sub(r'\*?\*?[Vv]alidation[_ ][Ss]tatus:?\*?\*?:?\s*\w+', '', text)
    text = re.sub(r'issues:\s*\n\s*-.*?(?=\n\n|\n[A-Z]|\Z)', '', text, flags=re.DOTALL)
    
    # Remove "Final Output Override: None" or similar
    text = re.sub(r'\*?\*?Final Output Override:?\*?\*?:?\s*None\s*', '', text)
    
    # Remove FHIR citation placeholders like [FHIR:Observation/123]
    text = re.sub(r'\[FHIR:\w+/\d+\]', '', text)
    
    # Remove PII masking explanations
    text = re.sub(r'Please note that this response has been scrubbed for PII.*?(?=\n\n|\Z)', '', text, flags=re.DOTALL)
    text = re.sub(r'\[PATIENT\]|\[DATE\]|\[SSN\]|\[PHONE\]|\[EMAIL\]', '', text)
    
    # Clean up multiple blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

def _load_conversation_history(session_id: str, patient_id: Optional[str] = None, limit: int = 10) -> List[Any]:
    """Load recent conversation history from session store and convert to messages.

    Args:
        session_id: The session ID to load history from
        patient_id: If provided, only include turns related to this patient
        limit: Maximum number of turns to retrieve

    Returns:
        List of HumanMessage/AIMessage for injection into agent context
    """
    # Disable history injection to prevent cross-session pollution
    # Set ENABLE_SESSION_HISTORY=true to re-enable
    if not os.getenv("ENABLE_SESSION_HISTORY", "").lower() == "true":
        print("[HISTORY] Session history injection disabled (set ENABLE_SESSION_HISTORY=true to enable)")
        return []

    print(f"[HISTORY] Attempting to load history for session: {session_id}, patient_id: {patient_id}, limit: {limit}")

    if not SESSION_STORE_AVAILABLE:
        print("[HISTORY] WARNING: Session store not available")
        return []
    
    try:
        store = get_session_store()
        # Get more turns than needed since we'll filter
        fetch_limit = limit * 3 if patient_id else limit
        recent_turns = store.get_recent(session_id, limit=fetch_limit)
        print(f"[HISTORY] Retrieved {len(recent_turns)} turns from DynamoDB")
        
        # Filter by patient_id if provided
        if patient_id:
            filtered_turns = [
                turn for turn in recent_turns 
                if turn.get("patient_id") == patient_id or turn.get("patient_id") is None
            ]
            print(f"[HISTORY] Filtered to {len(filtered_turns)} turns for patient: {patient_id}")
        else:
            filtered_turns = recent_turns
        
        # Limit after filtering
        filtered_turns = filtered_turns[:limit]
        
        # Convert turns to messages (oldest first for chronological order)
        # get_recent returns newest first, so we reverse to get chronological
        history_messages: List[Any] = []
        for turn in reversed(filtered_turns):
            role = turn.get("role", "")
            text = turn.get("text", "")
            turn_patient_id = turn.get("patient_id")
            if not text:
                continue
            
            # Add patient context label if patient_id is present
            if turn_patient_id and patient_id and turn_patient_id == patient_id:
                # Add subtle label for context
                labeled_text = f"[Previous message about patient {turn_patient_id[:8]}...]\n{text}"
            else:
                labeled_text = text
            
            if role == "user":
                history_messages.append(HumanMessage(content=labeled_text))
            elif role == "assistant":
                history_messages.append(AIMessage(content=labeled_text))
        
        print(f"[HISTORY] Converted to {len(history_messages)} messages for context")
        if history_messages:
            print(f"[HISTORY] First message preview: {str(history_messages[0].content)[:100]}...")
        return history_messages
    except Exception as e:
        # Log the error so we know what's happening
        print(f"[HISTORY] ERROR loading history: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return []


async def _researcher_node(state: AgentState) -> AgentState:
    max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    patient_id = state.get("patient_id")

    # Set patient context for auto-injection into tool calls
    # This allows tools to get patient_id even if LLM doesn't pass it explicitly
    set_patient_context(patient_id)

    system_prompt = get_researcher_prompt(patient_id)

    # Build messages list with conversation history
    messages = [SystemMessage(content=system_prompt)]

    # Automatically inject conversation history if session_id is available
    session_id = state.get("session_id")
    print(f"[RESEARCHER] Session ID: {session_id}, Patient ID: {patient_id}")
    if session_id:
        history_messages = _load_conversation_history(session_id, patient_id=patient_id, limit=10)
        if history_messages:
            print(f"[RESEARCHER] ✓ Injecting {len(history_messages)} history messages into context")
            messages.extend(history_messages)
        else:
            print(f"[RESEARCHER] ⚠ No history found for session {session_id}")
    else:
        print("[RESEARCHER] ⚠ No session_id provided - skipping history load")
    
    # Add current query
    messages.append(HumanMessage(content=state["query"]))
    
    # Add validator feedback if present (for revision cycles)
    # Use HumanMessage for feedback - more salient than SystemMessage
    if state.get("validator_output"):
        messages.append(HumanMessage(
            content=(
                "⚠️ REVISION REQUIRED ⚠️\n\n"
                "Your previous response was rejected. Fix ONLY these issues:\n\n"
                f"{state['validator_output']}\n\n"
                "Keep everything else the same. Do not rewrite the entire response."
            )
        ))

    # Add greeting instruction if this was a mixed query
    if state.get("should_acknowledge_greeting", False):
        messages.append(SystemMessage(content="IMPORTANT: The user included a greeting (e.g., 'Hello'). Please explicitly acknowledge it warmly at the beginning of your response before addressing the clinical question."))

    # Inject trajectory if in retry mode (death loop prevention)
    search_attempts = state.get("search_attempts", [])
    empty_count = state.get("empty_search_count", 0)
    current_iteration = state.get("iteration_count", 0)
    
    if empty_count > 0:
        failed_queries = [f"  - '{a.get('query', 'unknown')}' → {a.get('results_count', 0)} results"
                          for a in search_attempts[-3:]]
        messages.append(SystemMessage(content=f"""[SYSTEM CONTEXT - Do not echo this in your response]

Previous search attempts returned no useful results:
{chr(10).join(failed_queries)}

ACTION REQUIRED: Try DIFFERENT search terms. Consider:
- Using FHIR resource types: Condition, Observation, MedicationRequest
- Removing specific terms that may not match embeddings
- Broadening the query scope

If you still cannot find data, provide a response stating what you searched for and that no records were found.
DO NOT repeat this system message in your output."""))
    
    # System-wide step limit check (fail gracefully before timeout)
    if current_iteration >= 8:
        messages.append(SystemMessage(content="""[SYSTEM CONTEXT - Do not echo this in your response]

You are approaching the step limit. Provide your best response NOW based on what you have found.
If you found relevant data, summarize it. If nothing was found, state that clearly.
Do NOT make additional tool calls. DO NOT repeat this system message."""))

    agent = _get_researcher_agent()
    
    try:
        result = await agent.ainvoke({"messages": messages}, config={"recursion_limit": max_iterations})
        output_messages = result.get("messages", [])
        response_text = _extract_response_text(output_messages)
    except GraphRecursionError as e:
        print(f"[RESEARCHER] ⚠ Hit internal recursion limit (max_iterations={max_iterations}): {e}")
        # Fallback response to prevent crash
        response_text = (
            f"I encountered a complexity limit after {max_iterations} internal steps while researching this. "
            "I am returning what I have found so far, but it may be incomplete."
        )
        # We don't have new messages if it crashed, so we just use empty list
        output_messages = []


    # Extract sources from tool outputs FIRST (before we check for empty response)
    new_sources = _extract_sources(output_messages)
    all_sources = state.get("sources", []) + new_sources
    tools_called = (state.get("tools_called") or []) + _extract_tool_calls(output_messages)

    # Validate non-empty response and detect echo bugs
    echo_indicators = [
        "RETRY MODE",
        "PREVIOUS FAILED QUERIES",
        "SYSTEM CONTEXT",
        "Do not echo this",
        "ACTION REQUIRED: Try DIFFERENT"
    ]
    is_echo_response = any(indicator in response_text for indicator in echo_indicators)

    if not response_text or len(response_text.strip()) < 20 or is_echo_response:
        # Check if we have any sources we can report on
        if new_sources:
            response_text = (
                f"Based on my search, I found {len(new_sources)} relevant records. "
                "However, I was unable to fully synthesize a response. "
                "Please try rephrasing your question for more specific results."
            )
        else:
            response_text = (
                "I searched the patient records but was unable to generate a complete response. "
                "Please try rephrasing your question or providing more specific clinical terms."
            )
    
    # Track search attempts for trajectory (death loop prevention)
    # We need to match AIMessage tool_calls with their corresponding ToolMessage results
    search_attempts = list(state.get("search_attempts", []))  # Make a copy to avoid mutation
    found_results_this_iteration = False
    
    # First, build a map of tool_call_id -> result_count from ToolMessages
    tool_results: Dict[str, int] = {}
    for message in output_messages:
        if isinstance(message, ToolMessage):
            tool_call_id = getattr(message, "tool_call_id", None)
            if tool_call_id:
                try:
                    content_str = str(message.content)
                    data = json.loads(content_str)
                    if isinstance(data, dict):
                        # Count chunks from the response
                        chunks = data.get("chunks", [])
                        count = data.get("count", len(chunks) if isinstance(chunks, list) else 0)
                        tool_results[tool_call_id] = count
                        if count > 0:
                            found_results_this_iteration = True
                except (json.JSONDecodeError, Exception):
                    tool_results[tool_call_id] = 0
    
    # Now match tool_calls to their results
    for message in output_messages:
        if isinstance(message, AIMessage) and getattr(message, "tool_calls", None):
            for call in message.tool_calls:
                if call.get("name") == "search_patient_records":
                    args = call.get("args", {})
                    call_id = call.get("id", "")
                    result_count = tool_results.get(call_id, 0)
                    
                    current_attempt = {
                        "query": args.get("query", "unknown"),
                        "patient_id": args.get("patient_id", "unknown"),
                        "results_count": result_count,
                        "iteration": state.get("iteration_count", 0) + 1
                    }
                    search_attempts.append(current_attempt)
                    print(f"[TRAJECTORY] Tracked search: '{args.get('query', 'unknown')}' → {result_count} results")
                    
                    if result_count > 0:
                        found_results_this_iteration = True
    
    # Track empty searches - only increment if NO searches returned results this iteration
    empty_count = state.get("empty_search_count", 0)
    if not found_results_this_iteration and len(tool_results) > 0:
        # Only count as empty if we actually made searches but got nothing
        empty_count += 1
        print(f"[TRAJECTORY] Empty search count: {empty_count}")
    elif found_results_this_iteration:
        empty_count = 0  # Reset on success
        print("[TRAJECTORY] Found results! Resetting empty count to 0")
    
    return {
        **state,
        "researcher_output": response_text,
        "iteration_count": state.get("iteration_count", 0) + 1,
        "tools_called": tools_called,
        "sources": all_sources,
        "search_attempts": search_attempts,
        "empty_search_count": empty_count,
    }

def _extract_sources(messages: List[Any]) -> List[Dict[str, Any]]:
    """Extract source documents from ToolMessages."""
    sources: List[Dict[str, Any]] = []
    for message in messages:
        if isinstance(message, ToolMessage):
            try:
                # content can be string or list of content blocks
                content_str = str(message.content)
                data = json.loads(content_str)
                
                # Check for standard "chunks" format
                if isinstance(data, dict) and "chunks" in data and isinstance(data["chunks"], list):
                    for chunk in data["chunks"]:
                        if isinstance(chunk, dict):
                            source_entry: Dict[str, Any] = {
                                "doc_id": chunk.get("id", ""),
                                "content_preview": chunk.get("content", "") or chunk.get("text", ""),
                                "metadata": chunk.get("metadata", {}),
                            }
                            # Include relevance score if available
                            if "score" in chunk and chunk["score"] is not None:
                                source_entry["score"] = float(chunk["score"])
                            sources.append(source_entry)
            except json.JSONDecodeError:
                continue
            except Exception:
                continue
    return sources

async def _validator_node(state: AgentState) -> AgentState:
    """Validate researcher output with strictness tiers and structured parsing."""
    from api.agent.output_schemas import parse_validator_output
    from api.agent.guardrails.validators import validate_output

    # Calculate strictness tier in Python (more reliable than LLM)
    current_iter = state.get("iteration_count", 0)
    max_iter = int(os.getenv("AGENT_MAX_ITERATIONS", "15"))
    remaining = max_iter - current_iter

    # Balanced tier distribution: ~1/3 strict, ~1/3 relaxed, ~1/3 emergency
    if remaining > 5:
        strictness_tier = "TIER_STRICT"
    elif remaining > 2:
        strictness_tier = "TIER_RELAXED"
    else:
        strictness_tier = "TIER_EMERGENCY"

    # Run Guardrails AI validation first (if enabled)
    researcher_output = state.get("researcher_output", "")
    guardrails_valid, guardrails_error = validate_output(researcher_output)

    if not guardrails_valid:
        # Auto-fail with guardrails error
        return {
            **state,
            "validator_output": f"Guardrails validation failed:\n{guardrails_error}",
            "validation_result": "FAIL",
            "tools_called": state.get("tools_called") or [],
            "sources": state.get("sources", []),
        }

    # Fast-path: Detect incomplete/fallback responses and avoid wasting validation cycles
    _INCOMPLETE_MARKERS = [
        "unable to generate a complete response",
        "unable to generate complete response",
        "could not find any",
        "no results found",
        "please try rephrasing",
        "please rephrase your question",
    ]
    researcher_lower = researcher_output.lower()
    is_incomplete = any(marker in researcher_lower for marker in _INCOMPLETE_MARKERS)

    if is_incomplete and strictness_tier != "TIER_STRICT":
        # Don't waste tool calls validating an empty response - just pass it through
        # User deserves to know we couldn't find data rather than looping forever
        return {
            **state,
            "validator_output": "Response indicates no data found. Passing to user (not harmful).",
            "validation_result": "PASS",
            "tools_called": state.get("tools_called") or [],
            "sources": state.get("sources", []),
        }

    # Inject strictness tier into prompt
    patient_id = state.get("patient_id") or "N/A"
    system_prompt = get_validator_prompt().format(
        strictness_tier=strictness_tier,
        patient_id=patient_id
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Validate the response below.\n\n"
                f"STRICTNESS TIER: {strictness_tier}\n"
                f"REMAINING ATTEMPTS: {remaining}\n\n"
                f"User query:\n{state.get('query', '')}\n\n"
                f"Researcher response:\n{researcher_output}"
            )
        ),
    ]

    agent = _get_validator_agent()
    result = await agent.ainvoke({"messages": messages}, config={"recursion_limit": max_iter})
    output_messages = result.get("messages", [])
    response_text = _extract_response_text(output_messages)

    tools_called = (state.get("tools_called") or []) + _extract_tool_calls(output_messages)
    
    # Use structured parsing with fallback
    parsed = parse_validator_output(response_text)
    validation_result = parsed.validation_status
    
    # Handle final_output_override if provided
    final_output = response_text
    if parsed.final_output_override:
        final_output = f"{response_text}\n\n---\nCORRECTED OUTPUT:\n{parsed.final_output_override}"
        # If override is provided in TIER_EMERGENCY, auto-pass
        if strictness_tier == "TIER_EMERGENCY":
            validation_result = "PASS"

    return {
        **state,
        "validator_output": final_output,
        "validation_result": validation_result,
        "tools_called": tools_called,
        "sources": state.get("sources", []),
    }


async def _respond_node(state: AgentState) -> AgentState:
    """Synthesize the researched information into a user-friendly response."""
    max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    system_prompt = get_response_prompt() or get_conversational_prompt()

    # Get the research findings
    researcher_output = state.get("researcher_output", "")
    user_query = state.get("query", "")

    # DEBUG: Log what we're sending to the Response Synthesizer
    debug_hallucination = os.getenv("DEBUG_HALLUCINATION", "").lower() == "true"
    if debug_hallucination:
        print("\n[DEBUG:RESPOND] ========== RESPONSE SYNTHESIZER INPUT ==========")
        print(f"[DEBUG:RESPOND] User query: {user_query}")
        print(f"[DEBUG:RESPOND] Researcher output (first 1000 chars):\n{researcher_output[:1000]}")
        print("[DEBUG:RESPOND] ================================================\n")
    
    # Build messages for response synthesis - only include what user needs to see
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"User's question: {user_query}\n\n"
                f"Research findings:\n{researcher_output}\n\n"
                "Synthesize these findings into a clear, conversational response for the user."
            )
        ),
    ]
    
    # Use response agent to synthesize
    agent = _get_response_agent()
    result = await agent.ainvoke({"messages": messages}, config={"recursion_limit": max_iterations})
    output_messages = result.get("messages", [])
    final_response = _extract_response_text(output_messages)
    
    # Fallback to researcher output if synthesis fails
    if not final_response or len(final_response.strip()) < 10:
        final_response = researcher_output

    # Clean up any internal details that leaked through
    final_response = _clean_response(final_response)

    # DEBUG: Log the final synthesized response
    if debug_hallucination:
        print("\n[DEBUG:RESPOND] ========== FINAL RESPONSE OUTPUT ==========")
        print(f"[DEBUG:RESPOND] Final response:\n{final_response}")
        print("[DEBUG:RESPOND] ===========================================\n")

        # HALLUCINATION CHECK: Look for known example data in response
        example_hallucinations = [
            ("Type 2 Diabetes", "E11.9"),
            ("Hypertension", "38341003"),
            ("Metformin", "examples"),
            ("Lisinopril", "examples"),
        ]
        for condition, code in example_hallucinations:
            if condition in final_response and code not in researcher_output:
                print(f"[DEBUG:HALLUCINATION] WARNING: '{condition}' in response but '{code}' not in researcher output!")
                print("[DEBUG:HALLUCINATION] This may be a hallucination from prompt examples!")

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
    
    llm = get_llm("haiku")  # Haiku for conversational
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
    """Route based on validation result.
    
    - PASS: Go to respond (good answer)
    - FAIL/NEEDS_REVISION: Retry with researcher (up to max iterations)
    - Max iterations: Force respond even if not perfect
    """
    validation_result = state.get("validation_result", "NEEDS_REVISION")
    iteration_count = state.get("iteration_count", 0)
    max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "10"))
    
    # Conversational queries skip validation (safety check)
    if state.get("query_type") == "conversational":
        return "respond"
    
    # PASS = validated answer, go to respond
    if validation_result == "PASS":
        return "respond"
    
    # Hit max iterations, force respond with whatever we have
    if iteration_count >= max_iterations:
        return "respond"
    
    # FAIL or NEEDS_REVISION = retry with researcher
    # Researcher will receive validator_output as feedback (lines 177-187)
    return "researcher"


def _assess_query_complexity(state: AgentState) -> str:
    """Assess if query is simple or complex to route to appropriate graph.
    
    Simple queries: Factual lookups, single-patient queries, basic information retrieval
    Complex queries: Multi-step analysis, cross-referencing, validation required
    
    Returns:
        "simple" -> route to single-agent graph (researcher -> respond)
        "complex" -> route to multi-agent graph (researcher -> validator -> respond)
    """
    query = state.get("query", "").lower()
    
    # Complexity indicators
    complex_keywords = [
        "compare", "analyze", "cross-reference", "validate",
        "verify", "check for conflicts", "review", "assess",
        "multiple", "all patients", "trend", "pattern",
        "icd", "loinc", "rxnorm", "diagnosis", "differential"
    ]
    
    # Simple indicators
    simple_keywords = [
        "what is", "when was", "show me", "get", "list",
        "find", "lookup", "search", "retrieve"
    ]
    
    # Check for complex indicators
    complexity_score = sum(1 for keyword in complex_keywords if keyword in query)
    simplicity_score = sum(1 for keyword in simple_keywords if keyword in query)
    
    # Query length as a factor (longer queries tend to be more complex)
    word_count = len(query.split())
    
    # Decision logic
    if complexity_score >= 2:  # Multiple complex keywords
        return "complex"
    elif complexity_score == 1 and simplicity_score == 0 and word_count > 10:
        return "complex"
    elif simplicity_score > 0 and complexity_score == 0 and word_count <= 15:
        return "simple"
    else:
        # Default to complex for safety (validation is better than missing issues)
        return "complex"


def create_simple_graph():
    """Create a simple single-agent graph: researcher -> respond.
    
    Used for straightforward queries that don't require validation.
    """
    graph = StateGraph(AgentState)
    graph.add_node("researcher", _researcher_node)
    graph.add_node("respond", _respond_node)

    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "respond")
    graph.add_edge("respond", END)
    return graph.compile()


def create_complex_graph():
    """Create the full multi-agent graph: researcher -> validator -> respond.
    
    Used for complex queries requiring validation and iterative refinement.
    """
    graph = StateGraph(AgentState)
    graph.add_node("researcher", _researcher_node)
    graph.add_node("validator", _validator_node)
    graph.add_node("respond", _respond_node)

    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "validator")
    graph.add_conditional_edges("validator", _route_after_validation)
    graph.add_edge("respond", END)
    return graph.compile()


def create_multi_agent_graph():
    """Create the main graph with configurable complexity.
    
    Uses AGENT_GRAPH_TYPE environment variable to determine graph type:
    - "simple": researcher → respond (fast, no validation)
    - "complex": researcher → validator → respond (validated, iterative refinement)
    
    Defaults to "simple" if not specified.
    """
    graph_type = os.getenv("AGENT_GRAPH_TYPE", "simple").lower()
    
    if graph_type == "complex":
        print("[GRAPH] Creating complex multi-agent graph (researcher → validator → respond)")
        return create_complex_graph()
    else:
        print("[GRAPH] Creating simple single-agent graph (researcher → respond)")
        return create_simple_graph()