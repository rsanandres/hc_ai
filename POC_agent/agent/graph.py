"""LangGraph multi-agent definition."""

from __future__ import annotations

from typing import Any

from POC_agent.agent.multi_agent_graph import create_multi_agent_graph

_GRAPH: Any = None


def get_agent() -> Any:
    """Return the compiled multi-agent graph."""
    global _GRAPH
    if _GRAPH is not None:
        return _GRAPH

    _GRAPH = create_multi_agent_graph()
    return _GRAPH


def get_graph() -> Any:
    return get_agent()
