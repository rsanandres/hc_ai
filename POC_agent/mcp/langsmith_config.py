"""LangSmith tracing configuration."""

from __future__ import annotations

import os


def configure_langsmith_tracing() -> None:
    """Ensure LangSmith tracing environment variables are set."""
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGSMITH_PROJECT", "hc-ai-agents")
    if os.getenv("LANGSMITH_API_KEY") is None:
        raise RuntimeError("LANGSMITH_API_KEY is required for LangSmith tracing.")
