"""LLM configuration for the ReAct agent."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_aws import ChatBedrock
import sys

# Add utils to path for env_loader
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
from utils.env_loader import load_env_recursive

load_env_recursive(ROOT_DIR)

from langchain_ollama import ChatOllama


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value and value.isdigit():
        return int(value)
    return default


def get_llm() -> Any:
    """Return a configured LLM client based on environment variables."""

    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    max_tokens = _int_env("LLM_MAX_TOKENS", 2048)

    if provider == "bedrock":
        model_name = os.getenv("LLM_MODEL", "haiku").lower()
        if model_name == "sonnet":
            model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        else:
            model_id = "anthropic.claude-3-5-haiku-20241022-v2:0"

        return ChatBedrock(
            model_id=model_id,
            model_kwargs={
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        )

    model = os.getenv("LLM_MODEL", "chevalblanc/claude-3-haiku:latest")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    num_ctx = _int_env("LLM_NUM_CTX", 4096)

    return ChatOllama(
        model=model,
        base_url=base_url,
        temperature=temperature,
        num_ctx=num_ctx,
    )
