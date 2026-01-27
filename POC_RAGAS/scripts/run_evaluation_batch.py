"""CLI to run RAGAS evaluation in batches of 5 questions."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
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
from POC_RAGAS.utils.checkpoint import load_latest_checkpoint, load_checkpoint_from_path, save_checkpoint
from POC_RAGAS.utils.db_loader import get_distinct_patient_ids, get_full_fhir_documents
from POC_RAGAS.utils.report_generator import write_json_report, write_markdown_report
from POC_RAGAS.utils.service_manager import ensure_service_running


BATCH_SIZE = 5


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAGAS evaluation in batches of 5 questions.")
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
        "--batch-start",
        type=int,
        default=None,
        help="Start from this batch number (0-based). If not specified, resumes from last checkpoint.",
    )
    parser.add_argument(
        "--batch-count",
        type=int,
        default=None,
        help="Number of batches to run. If not specified, runs until all questions are processed.",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="Path to specific checkpoint file to resume from (e.g., checkpoint_first35_questions.json).",
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


def _get_batch_range(total_questions: int, batch_num: int) -> tuple[int, int]:
    """Get the start and end indices for a batch."""
    start = batch_num * BATCH_SIZE
    end = min(start + BATCH_SIZE, total_questions)
    return start, end


async def main() -> int:
    args = parse_args()
    testset = _extract_questions(args.testset)
    total_questions = len(testset)
    
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
    
    # Determine modes to run
    modes = []
    if args.mode in {"direct", "both"}:
        modes.append("direct")
    if args.mode in {"api", "both"}:
        modes.append("api")
    
    # Initialize samples and failed lists
    samples: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []
    completed_combinations: set[tuple[int, str]] = set()
    
    # Determine starting batch
    start_batch = 0
    checkpoint_loaded = False
    
    if args.batch_start is not None:
        start_batch = args.batch_start
        print(f"Starting from batch {start_batch} (questions {start_batch * BATCH_SIZE}-{min((start_batch + 1) * BATCH_SIZE, total_questions) - 1})")
        # Mark all questions before this batch as completed (skip them)
        for q_idx in range(start_batch * BATCH_SIZE):
            for mode in modes:
                completed_combinations.add((q_idx, mode))
    elif args.checkpoint:
        # Load from specific checkpoint file
        checkpoint_path = Path(args.checkpoint)
        print(f"Loading checkpoint from: {checkpoint_path}")
        checkpoint = load_checkpoint_from_path(checkpoint_path)
        if checkpoint:
            checkpoint_config = checkpoint.get("config", {})
            # Use checkpoint's testset if available, otherwise use current testset
            checkpoint_testset = checkpoint_config.get("testset", "")
            if checkpoint_testset and checkpoint_testset != str(args.testset):
                print(f"Warning: Checkpoint testset ({checkpoint_testset}) differs from current ({args.testset})")
                print("  Continuing anyway - samples will be loaded from checkpoint")
            
            samples = checkpoint.get("samples", [])
            failed = checkpoint.get("failed", [])
            
            # Determine which batch we're on
            # Find highest question index from failed list
            max_processed_idx = -1
            if failed:
                max_failed_idx = max(f.get("question_index", -1) for f in failed)
                max_processed_idx = max(max_processed_idx, max_failed_idx)
            
            # Estimate completed questions from samples
            # In 'both' mode, each question produces 2 samples (one per mode)
            # In single mode, each question produces 1 sample
            samples_per_question = len(modes)
            estimated_completed_questions = len(samples) // samples_per_question if samples_per_question > 0 else 0
            max_processed_idx = max(max_processed_idx, estimated_completed_questions - 1)
            
            # Check if checkpoint has a note about which questions were processed
            progress_note = checkpoint.get("progress", {}).get("note", "")
            if "first" in progress_note.lower() and "questions" in progress_note.lower():
                # Try to extract number from note like "first 35 questions"
                match = re.search(r'first\s+(\d+)\s+questions', progress_note.lower())
                if match:
                    num_questions = int(match.group(1))
                    max_processed_idx = max(max_processed_idx, num_questions - 1)
            
            # Start from the batch after the last processed question
            start_batch = (max_processed_idx + 1 + BATCH_SIZE - 1) // BATCH_SIZE
            
            # Reconstruct completed_combinations from failed list
            # Mark all questions that have been processed (either succeeded or failed)
            for f in failed:
                q_idx = f.get("question_index", -1)
                if q_idx >= 0:
                    mode = f.get("mode", "")
                    if mode in modes:
                        completed_combinations.add((q_idx, mode))
            
            # Mark all questions up to max_processed_idx as completed for all modes
            # This ensures we skip questions that were already processed
            for q_idx in range(max_processed_idx + 1):
                for mode in modes:
                    completed_combinations.add((q_idx, mode))
            
            checkpoint_loaded = True
            print(f"✓ Loaded checkpoint: {checkpoint_path.name}")
            print(f"  Run ID: {checkpoint.get('run_id', 'unknown')}")
            print(f"  Samples: {len(samples)}")
            print(f"  Failed: {len(failed)}")
            print(f"  Estimated starting batch: {start_batch}")
        else:
            print(f"✗ Could not load checkpoint from {checkpoint_path}")
            print("  Starting fresh")
    else:
        # Try to load latest checkpoint
        checkpoint = load_latest_checkpoint()
        if checkpoint:
            checkpoint_config = checkpoint.get("config", {})
            if checkpoint_config.get("testset") == str(args.testset):
                samples = checkpoint.get("samples", [])
                failed = checkpoint.get("failed", [])
                # Determine which batch we're on based on completed combinations
                # Find highest question index from failed list
                if failed:
                    max_failed_idx = max(f.get("question_index", 0) for f in failed)
                    # Estimate batch from completed samples count
                    # Each question in 'both' mode produces 2 samples
                    estimated_completed = len(samples) // len(modes) if modes else 0
                    start_batch = max(0, (estimated_completed + max_failed_idx) // BATCH_SIZE)
                else:
                    estimated_completed = len(samples) // len(modes) if modes else 0
                    start_batch = estimated_completed // BATCH_SIZE
                
                checkpoint_loaded = True
                print(f"Resuming from latest checkpoint: batch {start_batch}")
                print(f"  Loaded {len(samples)} samples, {len(failed)} failed queries")
                # Reconstruct completed_combinations from samples and failed
                # This is approximate - we'll skip questions that are clearly done
                for q_idx in range(start_batch * BATCH_SIZE):
                    for mode in modes:
                        completed_combinations.add((q_idx, mode))
            else:
                print("Checkpoint testset doesn't match, starting fresh")
    
    # Calculate total batches
    total_batches = (total_questions + BATCH_SIZE - 1) // BATCH_SIZE
    batches_to_run = args.batch_count if args.batch_count is not None else total_batches - start_batch
    
    print(f"\n{'='*60}")
    print(f"Batch Evaluation Configuration:")
    print(f"  Total questions: {total_questions}")
    print(f"  Batch size: {BATCH_SIZE}")
    print(f"  Total batches: {total_batches}")
    print(f"  Starting batch: {start_batch}")
    print(f"  Batches to run: {batches_to_run}")
    print(f"  Modes: {', '.join(modes)}")
    print(f"{'='*60}\n")
    
    config_dict = {
        "mode": args.mode,
        "patient_mode": args.patient_mode,
        "testset": str(args.testset),
    }
    
    # Process batches
    for batch_num in range(start_batch, start_batch + batches_to_run):
        batch_start, batch_end = _get_batch_range(total_questions, batch_num)
        
        if batch_start >= total_questions:
            print(f"\nAll questions processed!")
            break
        
        print(f"\n{'='*60}")
        print(f"Processing Batch {batch_num + 1}/{total_batches}")
        print(f"  Questions {batch_start}-{batch_end - 1} ({batch_end - batch_start} questions)")
        print(f"{'='*60}")
        
        batch_samples = []
        batch_failed = []
        
        for question_idx in range(batch_start, batch_end):
            item = testset[question_idx]
            question = item.get("question") or item.get("query") or item.get("prompt") or item.get("user_input")
            if not question:
                continue

            for mode in modes:
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
                    
                    if result.get("error"):
                        error_msg = result.get("error", "")
                        batch_failed.append({
                            "question_index": question_idx,
                            "question": question,
                            "mode": mode,
                            "error": error_msg,
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                        print(f"  ✗ [{question_idx+1}/{total_questions}] {mode}: {error_msg[:80]}")
                        
                        # If API service is down, save checkpoint and exit
                        if mode == "api" and ("ConnectError" in error_msg or "not running" in error_msg.lower()):
                            print("\n" + "="*60)
                            print("ALERT: Agent API service is down!")
                            print("="*60)
                            print(f"Progress saved to checkpoint before exit.")
                            print(f"Completed: {len(samples)} samples")
                            print(f"Failed: {len(failed)} queries")
                            print(f"Last batch: {batch_num}")
                            print(f"Last question: {question_idx}")
                            print("\nTo resume:")
                            print(f"  1. Start unified API service: uvicorn api.main:app --port 8000")
                            print(f"  2. Run: python POC_RAGAS/scripts/run_evaluation_batch.py --batch-start {batch_num}")
                            print("="*60)
                            
                            # Save checkpoint before exiting
                            checkpoint_path = save_checkpoint(
                                run_id=run_id,
                                config=config_dict,
                                samples=samples,
                                failed=failed + batch_failed,
                                total_questions=total_questions,
                                completed_questions=len(samples),
                            )
                            print(f"\nCheckpoint saved: {checkpoint_path}")
                            return 1
                    else:
                        new_samples = await _build_samples(question, result, patient_id)
                        batch_samples.extend(new_samples)
                        completed_combinations.add(combination)
                        print(f"  ✓ [{question_idx+1}/{total_questions}] {mode}: {question[:60]}...")
                except Exception as e:
                    batch_failed.append({
                        "question_index": question_idx,
                        "question": question,
                        "mode": mode,
                        "error": f"{type(e).__name__}: {str(e)}",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    print(f"  ✗ [{question_idx+1}/{total_questions}] {mode}: Exception - {type(e).__name__}")
        
        # Add batch results to main lists
        samples.extend(batch_samples)
        failed.extend(batch_failed)
        
        # Save checkpoint after each batch
        checkpoint_path = save_checkpoint(
            run_id=run_id,
            config=config_dict,
            samples=samples,
            failed=failed,
            total_questions=total_questions,
            completed_questions=len(samples),
        )
        
        print(f"\nBatch {batch_num + 1} complete!")
        print(f"  Batch samples: {len(batch_samples)}")
        print(f"  Batch failed: {len(batch_failed)}")
        print(f"  Total samples: {len(samples)}")
        print(f"  Total failed: {len(failed)}")
        print(f"  Checkpoint saved: {checkpoint_path.name}")
    
    # Final evaluation and reporting
    if not samples:
        print("\nNo samples to evaluate!")
        return 1
    
    print(f"\n{'='*60}")
    print("Running RAGAS evaluations...")
    print(f"{'='*60}")
    
    faithfulness_scores = await evaluate_faithfulness(samples)
    relevancy_scores = await evaluate_relevancy(samples)
    noise_sensitivity_scores = await evaluate_noise_sensitivity(samples)
    
    # Combine scores
    for i, sample in enumerate(samples):
        sample["faithfulness"] = faithfulness_scores[i] if i < len(faithfulness_scores) else None
        sample["relevancy"] = relevancy_scores[i] if i < len(relevancy_scores) else None
        sample["noise_sensitivity"] = noise_sensitivity_scores[i] if i < len(noise_sensitivity_scores) else None
    
    # Generate summary
    summary = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat(),
        "total_samples": len(samples),
        "total_failed": len(failed),
        "metrics": {
            "faithfulness": {
                "mean": sum(s["faithfulness"] for s in samples if s.get("faithfulness") is not None) / len([s for s in samples if s.get("faithfulness") is not None]) if samples else 0,
                "scores": faithfulness_scores,
            },
            "relevancy": {
                "mean": sum(s["relevancy"] for s in samples if s.get("relevancy") is not None) / len([s for s in samples if s.get("relevancy") is not None]) if samples else 0,
                "scores": relevancy_scores,
            },
            "noise_sensitivity": {
                "mean": sum(s["noise_sensitivity"] for s in samples if s.get("noise_sensitivity") is not None) / len([s for s in samples if s.get("noise_sensitivity") is not None]) if samples else 0,
                "scores": noise_sensitivity_scores,
            },
        },
        "progress": {
            "total_questions": total_questions,
            "completed_questions": len(samples),
            "failed_questions": len(failed),
        },
        "failed": failed,
    }
    
    # Save results
    CONFIG.results_dir.mkdir(parents=True, exist_ok=True)
    results_path = CONFIG.results_dir / f"results_{run_id}.json"
    report_path = CONFIG.results_dir / f"report_{run_id}.md"
    
    write_json_report(summary, samples, results_path)
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
