"""FastAPI router for agent endpoints."""

from __future__ import annotations

import os
import json
import uuid
import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth.dependencies import get_current_user

limiter = Limiter(key_func=get_remote_address)

try:
    from langgraph.errors import GraphRecursionError
except ImportError:
    # Fallback if langgraph doesn't expose this error
    GraphRecursionError = RecursionError

from api.agent.graph import get_agent
from api.agent.models import AgentDocument, AgentQueryRequest, AgentQueryResponse
from api.agent.guardrails.validators import setup_guard

from api.agent.pii_masker.factory import create_pii_masker

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
                score=item.get("score"),
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
@limiter.limit("10/minute")
async def query_agent(request: Request, payload: AgentQueryRequest) -> AgentQueryResponse:
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="Query is required.")

    request_id = str(uuid.uuid4())
    try:
        masked_query, _ = _pii_masker.mask_pii(payload.query)

        # store = get_session_store() # Already initialized above
        agent = get_agent()
        recursion_limit = int(os.getenv("AGENT_RECURSION_LIMIT", "50"))
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
                agent.ainvoke(state, config={"recursion_limit": recursion_limit}),
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

        # Session store disabled (DynamoDB deferred)
        # try:
        #     store.append_turn(payload.session_id, role="user", text=masked_query, meta={"masked": True})
        #     store.append_turn(
        #         payload.session_id,
        #         role="assistant",
        #         text=response_text,
        #         meta={
        #             "tool_calls": tool_calls,
        #             "sources": [{"doc_id": s.doc_id, "content_preview": s.content_preview, "metadata": s.metadata} for s in sources],
        #             "researcher_output": result.get("researcher_output"),
        #             "validator_output": result.get("validator_output"),
        #             "validation_result": result.get("validation_result"),
        #         }
        #     )
        # except Exception as store_error:
        #     print(f"Warning: Failed to store session turn: {store_error}")

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
        print(f"Agent hit recursion limit [request_id={request_id}] (recursion_limit={recursion_limit}): {str(e)}")
        return AgentQueryResponse(
            query=payload.query,
            response="I was unable to find a complete answer due to processing limits. "
                     "The search may have encountered issues with the query or data availability. "
                     "Please try rephrasing your question with more specific clinical terms.",
            sources=[],
            tool_calls=[],
            session_id=payload.session_id,
            validation_result="MAX_ITERATIONS",
            researcher_output=None,
            validator_output=f"Reached recursion limit ({recursion_limit}). Could not complete response.",
            iteration_count=recursion_limit,
        )
    except Exception as e:
        # Log the full error for debugging with request context
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in agent query [request_id={request_id}]: {type(e).__name__}: {str(e)}")
        print(f"Traceback: {error_details}")

        # Return generic error — details stay server-side
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@router.post("/query/stream")
@limiter.limit("10/minute")
async def query_agent_stream(request: Request, payload: AgentQueryRequest):
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
            recursion_limit = int(os.getenv("AGENT_RECURSION_LIMIT", "50"))
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

            # Use astream_events for real-time streaming
            # Keepalive: yield SSE comments to prevent ALB idle timeout during long Bedrock calls
            KEEPALIVE_INTERVAL = 15  # seconds
            event_queue: asyncio.Queue = asyncio.Queue()
            stream_done = False

            async def _stream_events():
                """Consume astream_events and push to queue."""
                nonlocal stream_done
                try:
                    async for ev in agent.astream_events(
                        state,
                        config={"recursion_limit": recursion_limit}
                    ):
                        await event_queue.put(ev)
                except GraphRecursionError as e:
                    await event_queue.put(("__recursion_error__", e))
                except Exception as e:
                    await event_queue.put(("__error__", e))
                finally:
                    stream_done = True
                    await event_queue.put(None)  # sentinel

            stream_task = asyncio.create_task(_stream_events())

            try:
                while True:
                    try:
                        event = await asyncio.wait_for(event_queue.get(), timeout=KEEPALIVE_INTERVAL)
                    except asyncio.TimeoutError:
                        # No event in 15s — send SSE comment keepalive
                        yield ": keepalive\n\n"
                        continue

                    if event is None:
                        break  # stream done

                    # Handle errors forwarded from stream task
                    if isinstance(event, tuple) and len(event) == 2:
                        tag, exc = event
                        if tag == "__recursion_error__":
                            raise GraphRecursionError(str(exc))
                        elif tag == "__error__":
                            raise exc

                    event_count += 1

                    # Check timeout manually during streaming
                    if asyncio.get_event_loop().time() - start_time > agent_timeout:
                        error_msg = f"Agent request {request_id} timed out after {agent_timeout} seconds"
                        print(f"Error: {error_msg}")
                        stream_task.cancel()
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

                # Stream finished — clean up task
                await stream_task

                # After streaming completes, use accumulated state as result
                result = accumulated_state

            except GraphRecursionError as e:
                # Agent hit recursion limit - return graceful response with what we have
                current_iter = accumulated_state.get("iteration_count", 0)
                print(f"[STREAM {request_id}] Agent hit recursion limit (recursion_limit={recursion_limit}): {str(e)}")
                yield f"data: {json.dumps({'type': 'max_iterations', 'message': 'Reached recursion limit', 'iteration_count': current_iter})}\n\n"

                # Check if we have partial results
                if accumulated_state.get("researcher_output"):
                    graceful_response = f"Here is what I found (processing was limited):\n\n{accumulated_state['researcher_output']}"
                else:
                    graceful_response = (
                        "I was unable to find a complete answer due to processing limits. "
                        "Please try rephrasing your question with more specific clinical terms."
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
            
            # Session store disabled (DynamoDB deferred)
            # try:
            #     store.append_turn(payload.session_id, role="user", text=masked_query, meta={"masked": True})
            #     store.append_turn(
            #         payload.session_id,
            #         role="assistant",
            #         text=response_text,
            #         meta={
            #             "tool_calls": tool_calls,
            #             "sources": [{"doc_id": s.doc_id, "content_preview": s.content_preview, "metadata": s.metadata} for s in sources],
            #             "researcher_output": result.get("researcher_output"),
            #             "validator_output": result.get("validator_output"),
            #             "validation_result": result.get("validation_result"),
            #         }
            #     )
            # except Exception as store_error:
            #     print(f"Warning: Failed to store session turn: {store_error}")
            
            # Send final response
            final_data = {
                "type": "complete",
                "response": response_text,
                "researcher_output": result.get("researcher_output"),
                "validator_output": result.get("validator_output"),
                "validation_result": result.get("validation_result"),
                "tool_calls": tool_calls,
                "sources": [{"doc_id": s.doc_id, "content_preview": s.content_preview, "metadata": s.metadata, "score": s.score} for s in sources],
                "iteration_count": result.get("iteration_count"),
            }
            yield f"data: {json.dumps(final_data)}\n\n"
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            error_msg = f"Error in streaming agent query [request_id={request_id}]: {type(e).__name__}: {str(e)}"
            print(error_msg)
            print(f"Traceback: {error_details}")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Internal server error'})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.post("/reload-prompts")
async def reload_prompts(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Reload prompts from YAML file without restarting server.

    Useful for development when prompts.yaml has been updated.
    Also clears any cached agents to ensure new prompts are used.
    """
    from api.agent.prompt_loader import reload_prompts as _reload_prompts, get_metadata
    from api.agent import multi_agent_graph

    # Reload prompts from file
    _reload_prompts()

    # Clear cached agents so they pick up new prompts
    multi_agent_graph._RESEARCHER_AGENT = None
    multi_agent_graph._VALIDATOR_AGENT = None
    multi_agent_graph._RESPONSE_AGENT = None

    # Get metadata for confirmation
    metadata = get_metadata()

    return {
        "status": "ok",
        "message": "Prompts reloaded and agent caches cleared",
        "metadata": metadata
    }
