#!/usr/bin/env python3
"""Terminal CLI for chatting with the agent through the FastAPI service."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path
from typing import Optional

import requests

ROOT_DIR = Path(__file__).resolve().parents[1]  # Go up 1 level from scripts/ to project root
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.env_loader import load_env_recursive

load_env_recursive(ROOT_DIR)

# Default service URL - unified API on port 8000
DEFAULT_AGENT_URL = "http://localhost:8000/agent/query"


def format_response(response_data: dict) -> str:
    """Format the agent response for display."""
    lines = []
    
    # Main response
    response_text = response_data.get("response", "")
    if response_text:
        lines.append("=" * 70)
        lines.append("AGENT RESPONSE:")
        lines.append("=" * 70)
        lines.append(response_text)
        lines.append("")
    
    # Tool calls
    tool_calls = response_data.get("tool_calls", [])
    if tool_calls:
        lines.append(f"Tools used: {', '.join(tool_calls)}")
        lines.append("")
    
    # Sources
    sources = response_data.get("sources", [])
    if sources:
        lines.append(f"Sources ({len(sources)}):")
        for idx, source in enumerate(sources, 1):
            doc_id = source.get("doc_id", "unknown")
            preview = source.get("content_preview", "")[:100]
            lines.append(f"  {idx}. {doc_id}: {preview}...")
        lines.append("")
    
    # Validation info (if available)
    validation_result = response_data.get("validation_result")
    if validation_result:
        lines.append(f"Validation: {validation_result}")
    
    return "\n".join(lines)


def query_agent(
    query: str,
    session_id: str,
    agent_url: str = DEFAULT_AGENT_URL,
    patient_id: Optional[str] = None,
) -> dict:
    """Send a query to the agent service."""
    payload = {
        "query": query,
        "session_id": session_id,
    }
    if patient_id:
        payload["patient_id"] = patient_id
    
    try:
        response = requests.post(agent_url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to agent service at {agent_url}")
        print("Make sure the service is running: uvicorn api.main:app --reload --port 8000")
        sys.exit(1)
    except requests.exceptions.HTTPError:
        print(f"Error: HTTP {response.status_code}: {response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {type(e).__name__}: {str(e)}")
        sys.exit(1)


def main() -> int:
    """Main CLI loop."""
    # Get session ID
    if len(sys.argv) > 1:
        session_id = sys.argv[1]
        print(f"Using session ID: {session_id}")
    else:
        session_id = str(uuid.uuid4())
        print(f"Starting new session: {session_id}")
        print("(To continue an existing session, pass the session ID as an argument)")
    
    print("\n" + "=" * 70)
    print("Agent Chat CLI")
    print("=" * 70)
    print("Type your questions below. Type 'exit', 'quit', or 'q' to exit.")
    print("Type 'clear' to clear the session history.")
    print("=" * 70 + "\n")
    
    agent_url = DEFAULT_AGENT_URL
    
    # Check if service is available
    try:
        if "/agent/query" in agent_url:
            health_url = agent_url.replace("/agent/query", "/agent/health")
        else:
            api_base = agent_url.replace("/agent", "").rstrip("/")
            health_url = f"{api_base}/agent/health"
        response = requests.get(health_url, timeout=5)
        if response.status_code == 200:
            print("✓ Connected to agent service\n")
        else:
            print("⚠ Warning: Agent service health check failed\n")
    except Exception:
        print("⚠ Warning: Could not verify agent service connection\n")
    
    # Main chat loop
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            # Handle special commands
            if user_input.lower() in ("exit", "quit", "q"):
                print("\nGoodbye!")
                break
            
            if user_input.lower() == "clear":
                try:
                    # Use session endpoint
                    api_base = agent_url.replace("/agent/query", "").replace("/agent", "")
                    clear_url = f"{api_base}/session/{session_id}"
                    response = requests.delete(clear_url, timeout=10)
                    if response.status_code == 200:
                        print("✓ Session cleared\n")
                    else:
                        print(f"⚠ Failed to clear session: {response.status_code}\n")
                except Exception as e:
                    print(f"⚠ Error clearing session: {e}\n")
                continue
            
            # Send query to agent
            print("\n[Thinking...]")
            response_data = query_agent(user_input, session_id, agent_url)
            
            # Display response
            print("\n" + format_response(response_data))
            print("-" * 70 + "\n")
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'exit' to quit or continue chatting.")
        except EOFError:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"\nError: {type(e).__name__}: {str(e)}\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
