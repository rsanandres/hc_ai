#!/usr/bin/env python3
"""Enhanced Terminal CLI for debugging the agent with verbose output.

This CLI displays intermediate agent steps (Researcher → Validator),
tool calls, validation status, and LangSmith trace URLs.
"""

from __future__ import annotations

import sys
import uuid
import json
from pathlib import Path
from typing import Optional

import requests

# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    # Agent role colors
    RESEARCHER = "\033[96m"  # Cyan
    VALIDATOR = "\033[95m"   # Magenta
    RESPONSE = "\033[92m"    # Green
    LANGSMITH = "\033[94m"   # Blue
    
    # Status colors
    PASS = "\033[92m"        # Green
    NEEDS_REVISION = "\033[93m"  # Yellow
    FAIL = "\033[91m"        # Red
    
    # UI colors
    PROMPT = "\033[97m"      # White
    INFO = "\033[90m"        # Gray
    WARNING = "\033[93m"     # Yellow
    ERROR = "\033[91m"       # Red
    HEADER = "\033[96m"      # Cyan
    CYAN = "\033[96m"        # Cyan
    YELLOW = "\033[93m"      # Yellow


ROOT_DIR = Path(__file__).resolve().parents[1]  # Go up 1 level from scripts/ to project root
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.env_loader import load_env_recursive

load_env_recursive(ROOT_DIR)

# Default service URL - unified API on port 8000
DEFAULT_AGENT_URL = "http://localhost:8000/agent/query"


class AgentDebugCLI:
    """Enhanced CLI for agent debugging with verbose output."""
    
    def __init__(self, session_id: Optional[str] = None, agent_url: str = DEFAULT_AGENT_URL):
        self.session_id = session_id or str(uuid.uuid4())
        self.agent_url = agent_url
        self.patient_id: Optional[str] = None
        self.verbose = True  # Show intermediate steps by default
        self.show_langsmith = False  # Hidden by default (frontend doesn't show this)
        self.last_response: Optional[dict] = None  # Store last response for saving
        
    def print_header(self) -> None:
        """Print CLI header."""
        print(f"\n{Colors.HEADER}{'═' * 70}")
        print("  Agent Debug CLI - Enhanced Terminal Interface")
        print(f"{'═' * 70}{Colors.RESET}")
        print(f"{Colors.INFO}Session: {self.session_id}{Colors.RESET}")
        print(f"{Colors.INFO}Verbose mode: {'ON' if self.verbose else 'OFF'}{Colors.RESET}")
        print()
        self._print_help()
        print(f"{Colors.HEADER}{'═' * 70}{Colors.RESET}\n")
    
    def _print_help(self) -> None:
        """Print help text."""
        print(f"{Colors.DIM}Commands:")
        print("  /verbose    - Toggle verbose mode (show Researcher/Validator output)")
        print("  /langsmith  - Toggle LangSmith trace URL display (hidden by default)")
        print("  /history    - Show recent session history")
        print("  /patient <id> - Set patient ID for queries")
        print("  /clear      - Clear session history")
        print("  /help       - Show this help")
        print("  /save       - Save last response to file")
        print(f"  /exit       - Exit CLI{Colors.RESET}")
    
    def check_health(self) -> bool:
        """Check if agent service is available."""
        try:
            # Extract base URL and construct health endpoint
            if "/agent/query" in self.agent_url:
                health_url = self.agent_url.replace("/agent/query", "/agent/health")
            else:
                api_base = self.agent_url.replace("/agent", "").rstrip("/")
                health_url = f"{api_base}/agent/health"
            response = requests.get(health_url, timeout=5)
            if response.status_code == 200:
                print(f"{Colors.PASS}✓ Connected to agent service{Colors.RESET}\n")
                return True
            else:
                print(f"{Colors.WARNING}⚠ Agent service health check failed{Colors.RESET}\n")
                return False
        except Exception as e:
            print(f"{Colors.ERROR}✗ Could not connect to agent service: {e}{Colors.RESET}\n")
            return False
    
    def format_validation_status(self, status: Optional[str]) -> str:
        """Format validation status with color."""
        if not status:
            return f"{Colors.DIM}N/A{Colors.RESET}"
        
        status = status.upper()
        if status == "PASS":
            return f"{Colors.PASS}{Colors.BOLD}PASS{Colors.RESET}"
        elif status == "NEEDS_REVISION":
            return f"{Colors.NEEDS_REVISION}{Colors.BOLD}NEEDS_REVISION{Colors.RESET}"
        elif status == "FAIL":
            return f"{Colors.FAIL}{Colors.BOLD}FAIL{Colors.RESET}"
        return f"{Colors.DIM}{status}{Colors.RESET}"
    
    def format_researcher_output(self, output: Optional[str]) -> str:
        """Format Researcher agent output."""
        if not output:
            return ""
        
        lines = [
            f"{Colors.RESEARCHER}{Colors.BOLD}┌─ RESEARCHER OUTPUT ─────────────────────────────────────────────┐{Colors.RESET}",
            f"{Colors.RESEARCHER}│{Colors.RESET}",
        ]
        
        # Word wrap and indent the output
        for line in output.split('\n'):
            wrapped = self._wrap_text(line, width=66)
            for w in wrapped:
                lines.append(f"{Colors.RESEARCHER}│{Colors.RESET} {w}")
        
        lines.append(f"{Colors.RESEARCHER}│{Colors.RESET}")
        lines.append(f"{Colors.RESEARCHER}{Colors.BOLD}└──────────────────────────────────────────────────────────────────┘{Colors.RESET}")
        
        return '\n'.join(lines)
    
    def format_validator_output(self, output: Optional[str], status: Optional[str]) -> str:
        """Format Validator agent output."""
        if not output:
            return ""
        
        status_display = self.format_validation_status(status)
        
        lines = [
            f"{Colors.VALIDATOR}{Colors.BOLD}┌─ VALIDATOR OUTPUT ─────────────────────────────────────────────┐{Colors.RESET}",
            f"{Colors.VALIDATOR}│{Colors.RESET} Status: {status_display}",
            f"{Colors.VALIDATOR}│{Colors.RESET}",
        ]
        
        # Word wrap and indent the output
        for line in output.split('\n'):
            wrapped = self._wrap_text(line, width=66)
            for w in wrapped:
                lines.append(f"{Colors.VALIDATOR}│{Colors.RESET} {w}")
        
        lines.append(f"{Colors.VALIDATOR}│{Colors.RESET}")
        lines.append(f"{Colors.VALIDATOR}{Colors.BOLD}└──────────────────────────────────────────────────────────────────┘{Colors.RESET}")
        
        return '\n'.join(lines)
    
    def format_final_response(self, response: str) -> str:
        """Format final response."""
        lines = [
            f"{Colors.RESPONSE}{Colors.BOLD}┌─ FINAL RESPONSE ────────────────────────────────────────────────┐{Colors.RESET}",
            f"{Colors.RESPONSE}│{Colors.RESET}",
        ]
        
        for line in response.split('\n'):
            wrapped = self._wrap_text(line, width=66)
            for w in wrapped:
                lines.append(f"{Colors.RESPONSE}│{Colors.RESET} {w}")
        
        lines.append(f"{Colors.RESPONSE}│{Colors.RESET}")
        lines.append(f"{Colors.RESPONSE}{Colors.BOLD}└──────────────────────────────────────────────────────────────────┘{Colors.RESET}")
        
        return '\n'.join(lines)
    
    def _wrap_text(self, text: str, width: int = 66) -> list:
        """Wrap text to specified width."""
        if not text:
            return [""]
        if len(text) <= width:
            return [text]
        
        words = text.split(' ')
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line) + len(word) + 1 <= width:
                current_line += (" " if current_line else "") + word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return lines if lines else [""]
    
    def format_tool_calls(self, tool_calls: list) -> str:
        """Format tool calls."""
        if not tool_calls:
            return ""
        
        unique_tools = list(dict.fromkeys(tool_calls))  # Remove duplicates, preserve order
        return f"{Colors.INFO}🔧 Tools used: {', '.join(unique_tools)}{Colors.RESET}"
    
    def format_sources(self, sources: list) -> str:
        """Format sources."""
        if not sources:
            return ""
        
        lines = [f"{Colors.INFO}📚 Sources ({len(sources)}):{Colors.RESET}"]
        for idx, source in enumerate(sources[:5], 1):  # Show first 5
            doc_id = source.get("doc_id", "unknown")[:40]
            preview = source.get("content_preview", "")[:60].replace('\n', ' ')
            lines.append(f"{Colors.DIM}   {idx}. {doc_id}: {preview}...{Colors.RESET}")
        
        if len(sources) > 5:
            lines.append(f"{Colors.DIM}   ... and {len(sources) - 5} more{Colors.RESET}")
        
        return '\n'.join(lines)
    
    def format_langsmith_url(self, url: Optional[str]) -> str:
        """Format LangSmith trace URL."""
        if not url or not self.show_langsmith:
            return ""
        return f"{Colors.LANGSMITH}🔗 LangSmith Trace: {url}{Colors.RESET}"
    
    def query_agent(self, query: str) -> Optional[dict]:
        """Send a query to the agent service using streaming."""
        payload = {
            "query": query,
            "session_id": self.session_id,
        }
        if self.patient_id:
            payload["patient_id"] = self.patient_id
        
        try:
            # Use streaming endpoint
            response = requests.post(
                f"{self.agent_url}/stream",
                json=payload,
                timeout=300,
                stream=True
            )
            response.raise_for_status()
            
            result_data = None
            current_status = ""
            
            # Process Server-Sent Events
            for line in response.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                
                try:
                    data = json.loads(line[6:])  # Strip "data: " prefix
                    event_type = data.get("type")
                    
                    if event_type == "status":
                        # Show status update
                        msg = data.get("message", "")
                        if msg != current_status:
                            print(f"\r{Colors.CYAN}{msg}{Colors.RESET}", end="", flush=True)
                            current_status = msg
                    
                    elif event_type == "tool":
                        # Show tool call
                        tool = data.get("tool", "")
                        print(f"\r{Colors.YELLOW}🔧 Tool: {tool}{Colors.RESET}" + " " * 20)
                    
                    elif event_type == "complete":
                        # Clear status line and store result
                        print(f"\r{' ' * 80}\r", end="")
                        result_data = data
                        break
                    
                    elif event_type == "error":
                        print(f"\r{Colors.ERROR}Error: {data.get('message')}{Colors.RESET}")
                        return None
                
                except json.JSONDecodeError:
                    continue
            
            return result_data
            
        except requests.exceptions.ConnectionError:
            print(f"{Colors.ERROR}Error: Could not connect to agent service at {self.agent_url}")
            print(f"Make sure the service is running: uvicorn api.main:app --reload --port 8000{Colors.RESET}")
            return None
        except requests.exceptions.HTTPError:
            print(f"{Colors.ERROR}Error: HTTP {response.status_code}: {response.text}{Colors.RESET}")
            return None
        except Exception as e:
            print(f"{Colors.ERROR}Error: {type(e).__name__}: {str(e)}{Colors.RESET}")
            return None
    
    def display_response(self, response_data: dict) -> None:
        """Display the agent response with all intermediate steps."""
        print()
        
        # Show intermediate steps if verbose mode
        if self.verbose:
            researcher_output = response_data.get("researcher_output")
            if researcher_output:
                print(self.format_researcher_output(researcher_output))
                print()
            
            validator_output = response_data.get("validator_output")
            validation_status = response_data.get("validation_result")
            if validator_output:
                print(self.format_validator_output(validator_output, validation_status))
                print()
        
        # Always show final response
        final_response = response_data.get("response", "")
        if final_response:
            print(self.format_final_response(final_response))
            print()
        
        # Show tool calls
        tool_calls = response_data.get("tool_calls", [])
        if tool_calls:
            print(self.format_tool_calls(tool_calls))
        
        # Show retrieval results (Sources)
        sources = response_data.get("sources", [])
        if sources:
            print(self.format_sources(sources))
        
        # Show LangSmith URL
        langsmith_url = response_data.get("langsmith_run_url")
        if langsmith_url:
            print(self.format_langsmith_url(langsmith_url))
        
        print(f"\n{Colors.DIM}{'─' * 70}{Colors.RESET}\n")
    
    def get_session_history(self) -> None:
        """Fetch and display session history from DynamoDB."""
        try:
            # Use the session store directly
            from api.session.store_dynamodb import build_store_from_env
            store = build_store_from_env()
            turns = store.get_recent(self.session_id, limit=10)
            
            if not turns:
                print(f"{Colors.INFO}No conversation history for this session.{Colors.RESET}")
                return
            
            print(f"\n{Colors.HEADER}Session History (last {len(turns)} turns):{Colors.RESET}")
            print(f"{Colors.DIM}{'─' * 70}{Colors.RESET}")
            
            for turn in reversed(turns):  # Show oldest first
                role = turn.get("role", "unknown")
                text = turn.get("text", "")[:150]
                ts = turn.get("turn_ts", "")[:19]  # Trim to datetime
                
                if role == "user":
                    print(f"{Colors.PROMPT}[{ts}] You: {text}...{Colors.RESET}")
                else:
                    print(f"{Colors.RESPONSE}[{ts}] Agent: {text}...{Colors.RESET}")
            
            print(f"{Colors.DIM}{'─' * 70}{Colors.RESET}\n")
            
        except Exception as e:
            print(f"{Colors.ERROR}Error fetching history: {e}{Colors.RESET}")
    
    def clear_session(self) -> None:
        """Clear the current session."""
        try:
            # Use unified API session endpoint
            api_base = self.agent_url.replace("/agent/query", "").replace("/agent", "")
            clear_url = f"{api_base}/session/{self.session_id}"
            response = requests.delete(clear_url, timeout=10)
            if response.status_code == 200:
                print(f"{Colors.PASS}✓ Session cleared{Colors.RESET}\n")
            else:
                print(f"{Colors.WARNING}⚠ Failed to clear session: {response.status_code}{Colors.RESET}\n")
        except Exception as e:
            print(f"{Colors.ERROR}Error clearing session: {e}{Colors.RESET}\n")
    
    def save_response(self) -> None:
        """Save the last response to a file."""
        if not self.last_response:
            print(f"{Colors.WARNING}No response to save.{Colors.RESET}\n")
            return
            
        try:
            timestamp = self.last_response.get("timestamp", str(uuid.uuid4()))
            filename = f"agent_response_{timestamp}.json"
            
            # Create debug_output directory if not exists
            output_dir = ROOT_DIR / "debug_output"
            output_dir.mkdir(exist_ok=True)
            
            filepath = output_dir / filename
            with open(filepath, "w") as f:
                json.dump(self.last_response, f, indent=2)
            
            print(f"{Colors.PASS}✓ Response saved to {filepath}{Colors.RESET}\n")
        except Exception as e:
            print(f"{Colors.ERROR}Error saving response: {e}{Colors.RESET}\n")

    def handle_command(self, command: str) -> bool:
        """Handle CLI commands. Returns True if should continue, False to exit."""
        cmd = command.lower().strip()
        
        if cmd in ("/exit", "/quit", "/q"):
            print(f"\n{Colors.INFO}Goodbye!{Colors.RESET}")
            return False
        
        elif cmd == "/verbose":
            self.verbose = not self.verbose
            status = "ON" if self.verbose else "OFF"
            print(f"{Colors.INFO}Verbose mode: {status}{Colors.RESET}\n")
        
        elif cmd == "/langsmith":
            self.show_langsmith = not self.show_langsmith
            status = "ON" if self.show_langsmith else "OFF"
            print(f"{Colors.INFO}LangSmith URLs: {status}{Colors.RESET}\n")
        
        elif cmd == "/history":
            self.get_session_history()
        
        elif cmd == "/save":
            self.save_response()
            
        elif cmd == "/clear":
            self.clear_session()
        
        elif cmd == "/help":
            self._print_help()
            print()
        
        elif cmd.startswith("/patient "):
            patient_id = command[9:].strip()
            if patient_id:
                self.patient_id = patient_id
                print(f"{Colors.INFO}Patient ID set to: {patient_id}{Colors.RESET}\n")
            else:
                print(f"{Colors.WARNING}Usage: /patient <patient_id>{Colors.RESET}\n")
        
        elif cmd.startswith("/"):
            print(f"{Colors.WARNING}Unknown command: {cmd}. Type /help for available commands.{Colors.RESET}\n")
        
        else:
            # Not a command, it's a query
            return self.process_query(command)
        
        return True
    
    def process_query(self, query: str) -> bool:
        """Process a user query."""
        print(f"\n{Colors.INFO}[Thinking...]{Colors.RESET}")
        
        response_data = self.query_agent(query)
        if response_data:
            self.last_response = response_data  # Store for saving
            self.display_response(response_data)
        
        return True
    
    def run(self) -> int:
        """Main CLI loop."""
        self.print_header()
        self.check_health()
        
        while True:
            try:
                user_input = input(f"{Colors.PROMPT}You: {Colors.RESET}").strip()
                
                if not user_input:
                    continue
                
                if not self.handle_command(user_input):
                    break
                    
            except KeyboardInterrupt:
                print(f"\n\n{Colors.INFO}Interrupted. Type /exit to quit.{Colors.RESET}")
            except EOFError:
                print(f"\n\n{Colors.INFO}Goodbye!{Colors.RESET}")
                break
            except Exception as e:
                print(f"\n{Colors.ERROR}Error: {type(e).__name__}: {str(e)}{Colors.RESET}\n")
        
        return 0


def main() -> int:
    """Main entry point."""
    session_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    cli = AgentDebugCLI(session_id=session_id)
    return cli.run()


if __name__ == "__main__":
    sys.exit(main())
