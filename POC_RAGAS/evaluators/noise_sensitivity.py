"""Noise sensitivity evaluation using RAGAS faithfulness metric."""

from __future__ import annotations

import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG
from POC_RAGAS.evaluators.faithfulness import evaluate_faithfulness


def _inject_noise(
    samples: List[Dict[str, Any]],
    noise_pool: Sequence[str],
    noise_ratio: float,
    seed: int,
) -> List[Dict[str, Any]]:
    rng = random.Random(seed)
    noisy_samples: List[Dict[str, Any]] = []
    for sample in samples:
        contexts = list(sample.get("contexts", []))
        if not contexts:
            noisy_samples.append(sample)
            continue
        num_noise = max(1, int(len(contexts) * noise_ratio))
        noise_docs = rng.sample(list(noise_pool), k=min(num_noise, len(noise_pool)))
        noisy_samples.append(
            {
                **sample,
                "contexts": contexts + noise_docs,
            }
        )
    return noisy_samples


def evaluate_noise_sensitivity(
    samples: List[Dict[str, Any]],
    noise_pool: Sequence[str],
) -> Dict[str, Any]:
    baseline = evaluate_faithfulness(samples)
    noisy_samples = _inject_noise(
        samples=samples,
        noise_pool=noise_pool,
        noise_ratio=CONFIG.noise_ratio,
        seed=CONFIG.noise_seed,
    )
    noisy = evaluate_faithfulness(noisy_samples)
    degradation = float(baseline["score"]) - float(noisy["score"])
    return {
        "baseline_score": float(baseline["score"]),
        "noisy_score": float(noisy["score"]),
        "degradation": degradation,
        "baseline_raw": baseline["raw"],
        "noisy_raw": noisy["raw"],
    }
