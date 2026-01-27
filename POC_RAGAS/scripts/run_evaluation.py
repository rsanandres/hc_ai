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
from POC_RAGAS.utils.checkpoint import load_latest_checkpoint, save_checkpoint, should_checkpoint
from POC_RAGAS.utils.db_loader import get_distinct_patient_ids, get_full_fhir_documents
from POC_RAGAS.utils.report_generator import write_json_report, write_markdown_report
from POC_RAGAS.utils.service_manager import ensure_service_running


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
    parser.add_argument(
        "--start-from",
        type=int,
        default=None,
        help="Start evaluation from this question index (0-based). Clears checkpoint and starts fresh.",
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
    
    # Pre-flight: Check agent API service health (if using API mode)
    if args.mode in {"api", "both"}:
        print("Checking agent API service health...")
        if not await ensure_service_running():
            print("ERROR: Agent API service is not running.")
            print("Please start it manually: uvicorn api.main:app --port 8000")
            return 1
        print("Agent API service is ready")
    
    patient_ids = await get_distinct_patient_ids(limit=100)
    patient_id = patient_ids[0] if patient_ids else None

    # Generate run_id for this evaluation
    run_id = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    
    # Determine modes to run (needed early for checkpoint resume)
    modes = []
    if args.mode in {"direct", "both"}:
        modes.append("direct")
    if args.mode in {"api", "both"}:
        modes.append("api")
    
    # Handle --start-from argument
    start_from_index = args.start_from
    samples: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    completed_combinations: set[tuple[int, str]] = set()
    
    if start_from_index is not None:
        if start_from_index < 0 or start_from_index >= len(testset):
            print(f"ERROR: --start-from must be between 0 and {len(testset) - 1}")
            return 1
        print(f"Starting fresh from question {start_from_index} (clearing checkpoint)")
        # Mark all questions before start_from as completed (skip them)
        for q_idx in range(start_from_index):
            for mode in modes:
                completed_combinations.add((q_idx, mode))
        print(f"Skipping questions 0-{start_from_index - 1}, starting from question {start_from_index}")
    else:
        # Try to load checkpoint
        checkpoint = load_latest_checkpoint()
        if checkpoint:
            # Validate checkpoint matches current config
            checkpoint_config = checkpoint.get("config", {})
            if checkpoint_config.get("testset") != str(args.testset):
                print(f"Warning: Checkpoint testset ({checkpoint_config.get('testset')}) differs from current ({args.testset})")
            
            # Load existing samples and failed queries
            samples = checkpoint.get("samples", [])
            failed = checkpoint.get("failed", [])
            
            # Track completed combinations from samples count
            # Since we process sequentially (question 0 direct, question 0 api, question 1 direct, etc.)
            # we can estimate which questions have been fully completed
            checkpoint_progress = checkpoint.get("progress", {})
            completed_count = checkpoint_progress.get("completed_questions", 0)
            
            # Estimate completed questions based on samples count
            # This works because we process in order: Q0-direct, Q0-api, Q1-direct, Q1-api, etc.
            total_modes = 2 if args.mode == "both" else 1
            estimated_completed_questions = completed_count // total_modes if total_modes > 0 else 0
            
            # Mark all questions up to estimated_completed as done (for both modes)
            for q_idx in range(estimated_completed_questions):
                for mode in modes:
                    completed_combinations.add((q_idx, mode))
            
            print(f"Resumed from checkpoint: {checkpoint.get('run_id', 'unknown')}")
            print(f"  Progress: {completed_count} samples completed")
            print(f"  Failed queries: {len(failed)}")
            print(f"  Estimated completed questions: {estimated_completed_questions}/{len(testset)}")
            print(f"  Resuming from question {estimated_completed_questions + 1}")
        else:
            print("Starting new evaluation run")

    # Process questions
    total_questions = len(testset)
    for question_idx, item in enumerate(testset):
        question = item.get("question") or item.get("query") or item.get("prompt") or item.get("user_input")
        if not question:
            continue

        for mode in modes:
            # Check if this combination was already completed
            combination = (question_idx, mode)
            if combination in completed_combinations:
                continue

            try:
                if mode == "direct":
                    result = await run_agent_query(
                        query=question,
                        session_id=f"ragas-{run_id}-direct",
                        patient_id=patient_id if args.patient_mode != "without" else None,
                    )
                else:
                    result = await run_api_query(
                        query=question,
                        session_id=f"ragas-{run_id}-api",
                        patient_id=patient_id if args.patient_mode != "without" else None,
                    )
                
                # Check for errors in result
                if result.get("error"):
                    error_msg = result.get("error", "")
                    failed.append({
                        "question_index": question_idx,
                        "question": question,
                        "mode": mode,
                        "error": error_msg,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    print(f"Failed [{question_idx+1}/{total_questions}] {mode}: {error_msg[:100]}")
                    
                    # If API service is down, save checkpoint and exit
                    if mode == "api" and ("ConnectError" in error_msg or "not running" in error_msg.lower()):
                        print("\n" + "="*60)
                        print("ALERT: Agent API service is down!")
                        print("="*60)
                        print(f"Progress saved to checkpoint before exit.")
                        print(f"Completed: {len(samples)} samples")
                        print(f"Failed: {len(failed)} queries")
                        print(f"Last successful question: {question_idx}")
                        print("\nTo resume:")
                        print(f"  1. Start unified API service: uvicorn api.main:app --port 8000")
                        print(f"  2. Run: python POC_RAGAS/scripts/run_evaluation.py --start-from {question_idx + 1}")
                        print("="*60)
                        
                        # Save checkpoint before exiting
                        config_dict = {
                            "mode": args.mode,
                            "patient_mode": args.patient_mode,
                            "testset": str(args.testset),
                        }
                        checkpoint_path = save_checkpoint(
                            run_id=run_id,
                            config=config_dict,
                            samples=samples,
                            failed=failed,
                            total_questions=total_questions,
                            completed_questions=len(samples),
                        )
                        print(f"\nCheckpoint saved: {checkpoint_path}")
                        return 1
                else:
                    new_samples = await _build_samples(question, result, patient_id)
                    samples.extend(new_samples)
                    completed_combinations.add(combination)
                    print(f"Completed [{question_idx+1}/{total_questions}] {mode}: {question[:60]}...")
            except Exception as e:
                failed.append({
                    "question_index": question_idx,
                    "question": question,
                    "mode": mode,
                    "error": f"{type(e).__name__}: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat(),
                })
                print(f"Exception [{question_idx+1}/{total_questions}] {mode}: {type(e).__name__} - {str(e)[:100]}")

            # Save checkpoint every N questions
            completed_count = len(samples)
            if should_checkpoint(completed_count, CONFIG.checkpoint_interval):
                config_dict = {
                    "mode": args.mode,
                    "patient_mode": args.patient_mode,
                    "testset": str(args.testset),
                }
                checkpoint_path = save_checkpoint(
                    run_id=run_id,
                    config=config_dict,
                    samples=samples,
                    failed=failed,
                    total_questions=total_questions,
                    completed_questions=completed_count,
                )
                print(f"Checkpoint saved: {checkpoint_path} ({completed_count} samples)")

    if not samples:
        raise RuntimeError("No samples available for evaluation.")

    # Evaluate metrics
    faith = evaluate_faithfulness(samples)
    relevancy = evaluate_relevancy(samples)
    noise = evaluate_noise_sensitivity(samples, [s["contexts"][0] for s in samples])

    summary = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat(),
        "config": {
            "mode": args.mode,
            "patient_mode": args.patient_mode,
            "testset": str(args.testset),
        },
        "progress": {
            "total_questions": total_questions,
            "completed_questions": len(samples),
            "failed_questions": len(failed),
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
        "failed": failed,
    }

    results_path = Path(CONFIG.results_dir) / "results.json"
    report_path = Path(CONFIG.results_dir) / "report.md"
    write_json_report(summary, results_path)
    write_markdown_report(summary, samples, report_path)

    print(f"\nEvaluation complete!")
    print(f"  Completed: {len(samples)} samples")
    print(f"  Failed: {len(failed)} queries")
    print(f"  Saved results to {results_path}")
    print(f"  Saved report to {report_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        raise SystemExit(1)
