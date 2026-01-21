"""Faithfulness evaluation using RAGAS."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, List

from datasets import Dataset
from langchain_openai import ChatOpenAI
from ragas import evaluate
from ragas.metrics import faithfulness

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG


def _coerce_score(value: Any) -> float:
    if isinstance(value, list):
        numeric = [v for v in value if isinstance(v, (int, float))]
        return float(sum(numeric) / len(numeric)) if numeric else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _build_llm():
    if not CONFIG.openai_api_key:
        raise ValueError("OPENAI_API_KEY is required for faithfulness evaluation.")
    return ChatOpenAI(model=CONFIG.ragas_model, api_key=CONFIG.openai_api_key)


def evaluate_faithfulness(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    dataset = Dataset.from_list(samples)
    llm = _build_llm()
    result = evaluate(dataset, metrics=[faithfulness], llm=llm)
    return {
        "score": _coerce_score(result["faithfulness"]),
        "raw": result,
    }
