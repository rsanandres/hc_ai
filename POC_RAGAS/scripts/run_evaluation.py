"""CLI to run RAGAS evaluation."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG
from POC_RAGAS.evaluators.faithfulness import evaluate_faithfulness
from POC_RAGAS.evaluators.noise_sensitivity import evaluate_noise_sensitivity
from POC_RAGAS.evaluators.relevancy import evaluate_relevancy
from POC_RAGAS.runners.agent_runner import run_agent_query
from POC_RAGAS.runners.api_runner import run_api_query
from POC_RAGAS.utils.db_loader import get_distinct_patient_ids, get_full_fhir_documents
from POC_RAGAS.utils.report_generator import write_json_report, write_markdown_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation.")
    parser.add_argument(
        "--testset",
        type=Path,
        default=Path(CONFIG.testset_dir) / "synthetic_testset.json",
        help="Path to testset JSON.",
    )
    parser.add_argument(
        "--mode",
        choices=["direct", "api", "both"],
        default="both",
        help="Run direct agent, API, or both.",
    )
    parser.add_argument(
        "--patient-mode",
        choices=["with", "without", "both"],
        default="both",
        help="Use patient_id filter or not.",
    )
    return parser.parse_args()


def _extract_questions(testset_path: Path) -> List[Dict[str, Any]]:
    data = json.loads(testset_path.read_text())
    if isinstance(data, dict) and "data" in data:
        data = data["data"]
    if not isinstance(data, list):
        raise ValueError("Testset JSON format not recognized.")
    return data


async def _build_samples(query: str, result: Dict[str, Any], patient_id: str | None):
    contexts = []
    for source in result.get("sources", []):
        if isinstance(source, dict):
            contexts.append(source.get("content_preview") or source.get("content") or "")
        else:
            contexts.append(str(source))
    if CONFIG.include_full_json and patient_id:
        full_docs = await get_full_fhir_documents([patient_id])
        for doc in full_docs:
            bundle = doc.get("bundle_json")
            if bundle:
                contexts.append(json.dumps(bundle)[:2000])
    contexts = [ctx for ctx in contexts if ctx]
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


async def main() -> int:
    args = parse_args()
    testset = _extract_questions(args.testset)
    patient_ids = await get_distinct_patient_ids(limit=100)
    patient_id = patient_ids[0] if patient_ids else None

    samples: List[Dict[str, Any]] = []
    for item in testset:
        question = item.get("question") or item.get("query") or item.get("prompt")
        if not question:
            continue
        modes = []
        if args.mode in {"direct", "both"}:
            modes.append("direct")
        if args.mode in {"api", "both"}:
            modes.append("api")

        for mode in modes:
            if mode == "direct":
                result = await run_agent_query(
                    query=question,
                    session_id=f"ragas-direct-{mode}",
                    patient_id=patient_id if args.patient_mode != "without" else None,
                )
            else:
                result = await run_api_query(
                    query=question,
                    session_id=f"ragas-api-{mode}",
                    patient_id=patient_id if args.patient_mode != "without" else None,
                )
            samples.extend(await _build_samples(question, result, patient_id))

    if not samples:
        raise RuntimeError("No samples available for evaluation.")

    faith = evaluate_faithfulness(samples)
    relevancy = evaluate_relevancy(samples)
    noise = evaluate_noise_sensitivity(samples, [s["contexts"][0] for s in samples])

    summary = {
        "run_id": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        "timestamp": datetime.utcnow().isoformat(),
        "config": {
            "mode": args.mode,
            "patient_mode": args.patient_mode,
            "testset": str(args.testset),
        },
        "metrics": {
            "faithfulness": {"score": faith["score"]},
            "relevancy": {"score": relevancy["score"]},
            "noise_sensitivity": {
                "baseline_score": noise["baseline_score"],
                "noisy_score": noise["noisy_score"],
                "degradation": noise["degradation"],
            },
        },
    }

    results_path = Path(CONFIG.results_dir) / "results.json"
    report_path = Path(CONFIG.results_dir) / "report.md"
    write_json_report(summary, results_path)
    write_markdown_report(summary, samples, report_path)

    print(f"Saved results to {results_path}")
    print(f"Saved report to {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
