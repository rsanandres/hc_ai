"""Evaluate hallucination metrics for agent responses."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG
from POC_RAGAS.evaluators.faithfulness import evaluate_faithfulness
from POC_RAGAS.evaluators.noise_sensitivity import evaluate_noise_sensitivity
from POC_RAGAS.evaluators.relevancy import evaluate_relevancy
from POC_RAGAS.runners.agent_runner import run_agent_query
from POC_RAGAS.runners.api_runner import run_api_query
from POC_RAGAS.utils.db_loader import (
    get_distinct_patient_ids,
    get_full_fhir_documents,
    load_documents,
)


async def _check_api_health() -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(CONFIG.agent_api_url.replace("/agent/query", "/agent/health"))
            return resp.status_code == 200
    except Exception:
        return False


def _extract_contexts(sources: List[Dict[str, Any]]) -> List[str]:
    contexts = []
    for item in sources:
        if isinstance(item, dict):
            contexts.append(item.get("content_preview") or item.get("content") or "")
        else:
            contexts.append(str(item))
    return [ctx for ctx in contexts if ctx]


async def _build_samples(
    query: str,
    result: Dict[str, Any],
    patient_id: str,
) -> List[Dict[str, Any]]:
    contexts = _extract_contexts(result.get("sources", []))
    if CONFIG.include_full_json:
        full_docs = await get_full_fhir_documents([patient_id])
        for doc in full_docs:
            bundle = doc.get("bundle_json")
            if bundle:
                contexts.append(json.dumps(bundle)[:2000])

    if not contexts:
        return []

    return [
        {
            "question": query,
            "answer": result.get("response", ""),
            "contexts": contexts,
            "patient_id": patient_id,
        }
    ]


@pytest.mark.asyncio
async def test_hallucination_metrics(ragas_min_thresholds):
    if not CONFIG.openai_api_key:
        pytest.skip("OPENAI_API_KEY not configured.")

    if not await _check_api_health():
        pytest.skip("Agent API is not reachable. Start services before running this test.")

    patient_ids = await get_distinct_patient_ids(limit=50)
    if not patient_ids:
        pytest.skip("No patient IDs found in embeddings table.")
    patient_id = patient_ids[0]

    query = "What is the patient's birth date?"
    direct_result = await run_agent_query(query=query, session_id="ragas-direct", patient_id=patient_id)
    api_result = await run_api_query(query=query, session_id="ragas-api", patient_id=patient_id)

    samples = []
    samples.extend(await _build_samples(query, direct_result, patient_id))
    samples.extend(await _build_samples(query, api_result, patient_id))
    if not samples:
        pytest.skip("No contexts found for evaluation.")

    faith = evaluate_faithfulness(samples)
    relevancy = evaluate_relevancy(samples)

    noise_docs = await load_documents(limit=50)
    noise_pool = [doc.page_content for doc in noise_docs]
    noise = evaluate_noise_sensitivity(samples, noise_pool)

    assert 0.0 <= faith["score"] <= 1.0
    assert 0.0 <= relevancy["score"] <= 1.0
    assert 0.0 <= noise["baseline_score"] <= 1.0

    assert faith["score"] >= ragas_min_thresholds["faithfulness"]
    assert relevancy["score"] >= ragas_min_thresholds["relevancy"]
    assert noise["degradation"] <= ragas_min_thresholds["noise_degradation"]
