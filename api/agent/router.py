"""FastAPI router for agent endpoints."""

from __future__ import annotations

import os
import json
import uuid
import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

try:
    from langgraph.errors import GraphRecursionError
except ImportError:
    # Fallback if langgraph doesn't expose this error
    GraphRecursionError = RecursionError

from api.agent.graph import get_agent
from api.agent.models import AgentDocument, AgentQueryRequest, AgentQueryResponse
from api.agent.guardrails.validators import setup_guard

from api.agent.pii_masker.factory import create_pii_masker
from api.session.store_dynamodb import get_session_store

router = APIRouter()

# Initialize singletons
_pii_masker = create_pii_masker()
_guard = setup_guard()



def _build_sources(source_items: List[Dict[str, Any]]) -> List[AgentDocument]:
    sources: List[AgentDocument] = []
    for item in source_items:
        sources.append(
            AgentDocument(
                doc_id=item.get("doc_id", ""),
                content_preview=item.get("content_preview", ""),
                metadata=item.get("metadata", {}),
            )
        )
    return sources


def _guard_output(text: str) -> str:
    if _guard is None:
        return text
    try:
        result = _guard.validate(text)
        if hasattr(result, "validated_output"):
            return result.validated_output
        if isinstance(result, dict) and "validated_output" in result:
            return str(result["validated_output"])
    except Exception:
        return text
    return text


@router.post("/query", response_model=AgentQueryResponse)
async def query_agent(payload: AgentQueryRequest) -> AgentQueryResponse:
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query is required.")

    request_id = str(uuid.uuid4())
    try:
        masked_query, _ = _pii_masker.mask_pii(payload.query)

        # store = get_session_store() # Already initialized above
        agent = get_agent()
        max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "15"))
        # Set recursion_limit higher than max_iterations to allow for the full loop cycle
        # Each iteration = researcher + validator = 2 steps, plus respond node
        graph_recursion_limit = int(os.getenv("GRAPH_RECURSION_LIMIT", "35"))
        agent_timeout = int(os.getenv("AGENT_TIMEOUT_SECONDS", "300"))  # Default 5 minutes

        state = {
            "query": masked_query,
            "session_id": payload.session_id,
            "patient_id": payload.patient_id,
            "request_id": request_id,  # Add for debugging and isolation
            "k_retrieve": payload.k_retrieve,
            "k_return": payload.k_return,
            "iteration_count": 0,
        }

        # Add timeout handling for agent invocation
        try:
            result = await asyncio.wait_for(
                agent.ainvoke(state, config={"recursion_limit": graph_recursion_limit}),
                timeout=agent_timeout
            )
        except asyncio.TimeoutError:
            error_msg = f"Agent request {request_id} timed out after {agent_timeout} seconds"
            print(f"Error: {error_msg}")
            raise HTTPException(
                status_code=504,
                detail=error_msg
            )

        response_text = result.get("final_response") or result.get("researcher_output", "")

        response_text = _guard_output(response_text)
        response_text, _ = _pii_masker.mask_pii(response_text)

        tool_calls = result.get("tools_called", [])
        sources = _build_sources(result.get("sources", []))

        try:
            store.append_turn(payload.session_id, role="user", text=masked_query, meta={"masked": True})
            store.append_turn(
                payload.session_id,
                role="assistant",
                text=response_text,
                meta={
                    "tool_calls": tool_calls,
                    "sources": [{"doc_id": s.doc_id, "content_preview": s.content_preview, "metadata": s.metadata} for s in sources],
                    "researcher_output": result.get("researcher_output"),
                    "validator_output": result.get("validator_output"),
                    "validation_result": result.get("validation_result"),
                }
            )
        except Exception as store_error:
            # Log store errors but don't fail the request
            print(f"Warning: Failed to store session turn: {store_error}")

        return AgentQueryResponse(
            query=payload.query,
            response=response_text,
            sources=sources,
            tool_calls=tool_calls,
            session_id=payload.session_id,
            validation_result=result.get("validation_result"),
            researcher_output=result.get("researcher_output"),
            validator_output=result.get("validator_output"),
            iteration_count=result.get("iteration_count"),
        )
    except HTTPException:
        # Re-raise HTTP exceptions (like timeout) as-is
        raise
    except GraphRecursionError as e:
        # Agent hit max iterations - return graceful response with what we know
        print(f"Agent hit recursion limit [request_id={request_id}] (graph_recursion_limit={graph_recursion_limit}): {str(e)}")
        return AgentQueryResponse(
            query=payload.query,
            response=f"I was unable to find a complete answer after {max_iterations} attempts. "
                     f"The search may have encountered issues with the query or data availability. "
                     f"Please try rephrasing your question with more specific clinical terms "
                     f"(e.g., 'active conditions' instead of patient name).",
            sources=[],
            tool_calls=[],
            session_id=payload.session_id,
            validation_result="MAX_ITERATIONS",
            researcher_output=None,
            validator_output=f"Reached maximum iterations ({max_iterations}). Could not validate response.",
            iteration_count=max_iterations,
        )
    except Exception as e:
        # Log the full error for debugging with request context
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in agent query [request_id={request_id}]: {type(e).__name__}: {str(e)}")
        print(f"Traceback: {error_details}")

        # Return a 500 with error details instead of crashing
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {type(e).__name__}: {str(e)}"
        )


@router.post("/query/stream")
async def query_agent_stream(payload: AgentQueryRequest):
    """Stream agent execution progress using Server-Sent Events."""
    
    async def event_generator():
        result = None
        request_id = str(uuid.uuid4())
        # print(f"[STREAM {request_id}] === Generator function CALLED ===")
        try:
            # print(f"[STREAM {request_id}] About to yield first event...")
            yield f"data: {json.dumps({'type': 'start', 'message': 'Starting agent...'})}\n\n"
            # print(f"[STREAM {request_id}] First event yielded")
            
            
            masked_query, _ = _pii_masker.mask_pii(payload.query)
            
            # store = get_session_store() # Already initialized above
            agent = get_agent()
            max_iterations = int(os.getenv("AGENT_MAX_ITERATIONS", "15"))
            # Set recursion_limit higher than max_iterations to allow for the full loop cycle
            # Each iteration = researcher + validator = 2 steps, plus respond node
            graph_recursion_limit = int(os.getenv("GRAPH_RECURSION_LIMIT", "35"))
            agent_timeout = int(os.getenv("AGENT_TIMEOUT_SECONDS", "300"))  # Default 5 minutes

            state = {
                "query": masked_query,
                "session_id": payload.session_id,
                "patient_id": payload.patient_id,
                "request_id": request_id, # Add for debugging and isolation
                "k_retrieve": payload.k_retrieve,
                "k_return": payload.k_return,
                "iteration_count": 0,
            }

            yield f"data: {json.dumps({'type': 'status', 'message': '🔍 Starting agent...'})}\n\n"

            # Track state accumulation for final result
            accumulated_state = {}
            start_time = asyncio.get_event_loop().time()
            event_count = 0

            # print(f"[STREAM {request_id}] Starting astream_events loop...")

            # Use astream_events for real-time streaming (removed version parameter for compatibility)
            try:
                async for event in agent.astream_events(
                    state,
                    config={"recursion_limit": graph_recursion_limit}
                ):
                    event_count += 1
                    # print(f"[STREAM {request_id}] Event {event_count}: {event.get('event')} - {event.get('name', 'unknown')}")
                    
                    # Check timeout manually during streaming
                    if asyncio.get_event_loop().time() - start_time > agent_timeout:
                        error_msg = f"Agent request {request_id} timed out after {agent_timeout} seconds"
                        print(f"Error: {error_msg}")
                        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                        return
                    
                    event_type = event.get("event")
                    event_name = event.get("name", "")
                    event_data = event.get("data", {})
                    
                    # Handle different LangGraph events
                    if event_type == "on_chain_start":
                        # Node starting (researcher, validator, respond, etc.)
                        # print(f"[STREAM {request_id}] Chain starting: {event_name}")
                        if "researcher" in event_name.lower():
                            yield f"data: {json.dumps({'type': 'status', 'message': '🔬 Researcher investigating...'})}\n\n"
                        elif "validator" in event_name.lower():
                            yield f"data: {json.dumps({'type': 'status', 'message': '✓ Validator checking...'})}\n\n"
                        elif "respond" in event_name.lower():
                            yield f"data: {json.dumps({'type': 'status', 'message': '📝 Synthesizing response...'})}\n\n"
                    
                    elif event_type == "on_tool_start":
                        # Tool being called
                        tool_name = event_name or event_data.get("name", "unknown_tool")
                        tool_input = event_data.get("input", {})
                        # print(f"[STREAM {request_id}] Tool starting: {tool_name}")
                        yield f"data: {json.dumps({'type': 'tool', 'tool': tool_name, 'input': tool_input})}\n\n"
                        yield f"data: {json.dumps({'type': 'status', 'message': f'🛠️ Using {tool_name}...'})}\n\n"
                    
                    elif event_type == "on_tool_end":
                        # Tool completed - emit the result
                        tool_name = event_name or "unknown_tool"
                        tool_output = event_data.get("output", "")
                        # print(f"[STREAM {request_id}] Tool ended: {tool_name}, output length: {len(str(tool_output))}")
                        
                        # Truncate large outputs for display (max 1000 chars)
                        output_str = str(tool_output) if tool_output else ""
                        if len(output_str) > 1000:
                            output_preview = output_str[:1000] + f"... [truncated, {len(output_str)} total chars]"
                        else:
                            output_preview = output_str
                        
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'output': output_preview})}\n\n"
                    
                    elif event_type == "on_chain_end":
                        # Node completed - capture outputs
                        # print(f"[STREAM {request_id}] Chain ended: {event_name}")
                        output = event_data.get("output", {})
                        
                        # Update accumulated state
                        if isinstance(output, dict):
                            accumulated_state.update(output)
                            # print(f"[STREAM {request_id}] Accumulated state keys: {list(accumulated_state.keys())}")
                            
                            # Get current iteration
                            iteration_count = output.get("iteration_count", accumulated_state.get("iteration_count", 1))
                            
                            # Emit intermediate outputs with iteration number for debug mode
                            # Only emit if this is the actual node (not wrapper chains like LangGraph)
                            if "researcher_output" in output and output["researcher_output"] and "researcher" in event_name.lower():
                                yield f"data: {json.dumps({'type': 'researcher_output', 'output': output['researcher_output'], 'iteration': iteration_count, 'search_attempts': output.get('search_attempts', []), 'empty_search_count': output.get('empty_search_count', 0)})}\n\n"
                            
                            if "validator_output" in output and output["validator_output"] and "validator" in event_name.lower():
                                validation_result = output.get("validation_result", "")
                                yield f"data: {json.dumps({'type': 'validator_output', 'output': output['validator_output'], 'result': validation_result, 'iteration': iteration_count})}\n\n"
                            
                            if "final_response" in output and output["final_response"] and "respond" in event_name.lower():
                                yield f"data: {json.dumps({'type': 'response_output', 'output': output['final_response'], 'iteration': iteration_count})}\n\n"
                
                # print(f"[STREAM {request_id}] astream_events loop completed. Total events: {event_count}")
                
                # After streaming completes, use accumulated state as result
                result = accumulated_state
                
            except GraphRecursionError as e:
                # Agent hit max iterations - return graceful response with what we have
                current_iter = accumulated_state.get("iteration_count", max_iterations)
                print(f"[STREAM {request_id}] Agent hit recursion limit (graph_recursion_limit={graph_recursion_limit}): {str(e)}")
                yield f"data: {json.dumps({'type': 'max_iterations', 'message': f'Reached maximum iterations ({current_iter})', 'iteration_count': current_iter})}\n\n"

                # Return a helpful response instead of an error
                graceful_response = (
                    f"I was unable to find a complete answer after {current_iter} attempts. "
                    f"The search may have encountered issues with the query or data availability. "
                    f"Please try rephrasing your question with more specific clinical terms."
                )
                # Use 'complete' type for consistency with normal flow (frontend handles 'complete', not 'final')
                yield f"data: {json.dumps({'type': 'complete', 'response': graceful_response, 'validation_result': 'MAX_ITERATIONS', 'sources': [], 'tool_calls': [], 'iteration_count': current_iter})}\n\n"
                return
            except Exception as e:
                import traceback
                error_msg = f"Error in astream_events: {type(e).__name__}: {str(e)}"
                error_trace = traceback.format_exc()
                print(f"[STREAM {request_id}] {error_msg}")
                print(f"[STREAM {request_id}] Traceback: {error_trace}")
                yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                return
            
            # print(f"[STREAM {request_id}] Preparing final response...")
            yield f"data: {json.dumps({'type': 'status', 'message': '✓ Agent processing complete'})}\n\n"
            
            response_text = result.get("final_response") or result.get("researcher_output", "")
            response_text = _guard_output(response_text)
            response_text, _ = _pii_masker.mask_pii(response_text)
            
            tool_calls = result.get("tools_called", [])
            sources = _build_sources(result.get("sources", []))
            
            # Store in session
            try:
                store.append_turn(payload.session_id, role="user", text=masked_query, meta={"masked": True})
                store.append_turn(
                    payload.session_id,
                    role="assistant",
                    text=response_text,
                    meta={
                        "tool_calls": tool_calls,
                        "sources": [{"doc_id": s.doc_id, "content_preview": s.content_preview, "metadata": s.metadata} for s in sources],
                        "researcher_output": result.get("researcher_output"),
                        "validator_output": result.get("validator_output"),
                        "validation_result": result.get("validation_result"),
                    }
                )
            except Exception as store_error:
                print(f"Warning: Failed to store session turn: {store_error}")
            
            # Send final response
            final_data = {
                "type": "complete",
                "response": response_text,
                "researcher_output": result.get("researcher_output"),
                "validator_output": result.get("validator_output"),
                "validation_result": result.get("validation_result"),
                "tool_calls": tool_calls,
                "sources": [{"doc_id": s.doc_id, "content_preview": s.content_preview} for s in sources],
                "iteration_count": result.get("iteration_count"),
            }
            yield f"data: {json.dumps(final_data)}\n\n"
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = f"Error in streaming agent query [request_id={request_id}]: {type(e).__name__}: {str(e)}"
            print(error_msg)
            print(f"Traceback: {error_details}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}
