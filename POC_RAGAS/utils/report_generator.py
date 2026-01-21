"""Generate JSON and Markdown reports for evaluation runs."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List

from tabulate import tabulate

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_json_report(payload: Dict[str, Any], output_path: Path) -> Path:
    _ensure_dir(output_path)
    output_path.write_text(json.dumps(payload, indent=2))
    return output_path


def write_markdown_report(
    summary: Dict[str, Any],
    samples: Iterable[Dict[str, Any]],
    output_path: Path,
) -> Path:
    _ensure_dir(output_path)
    timestamp = summary.get("timestamp") or datetime.utcnow().isoformat()
    metrics = summary.get("metrics", {})

    rows: List[List[Any]] = []
    for metric_name, metric_data in metrics.items():
        if isinstance(metric_data, dict) and "score" in metric_data:
            rows.append([metric_name, metric_data.get("score")])
        elif isinstance(metric_data, dict) and "baseline_score" in metric_data:
            rows.append([metric_name, metric_data.get("baseline_score")])
            rows.append([f"{metric_name}_noisy", metric_data.get("noisy_score")])
            rows.append([f"{metric_name}_degradation", metric_data.get("degradation")])

    table = tabulate(rows, headers=["Metric", "Score"], tablefmt="github")

    sample_lines = []
    for sample in list(samples)[:5]:
        sample_lines.append(f"- Question: {sample.get('question')}")
        sample_lines.append(f"  Answer: {sample.get('answer')}")
        sample_lines.append(f"  Patient: {sample.get('patient_id')}")

    report = f"""# RAGAS Evaluation Report

Timestamp: {timestamp}
Model: {CONFIG.ragas_model}

## Summary Metrics

{table}

## Sample Results (first 5)
{chr(10).join(sample_lines)}
"""
    output_path.write_text(report)
    return output_path
