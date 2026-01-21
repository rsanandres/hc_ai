"""Pytest configuration for RAGAS evaluations."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture(scope="session")
def ragas_min_thresholds():
    return {
        "faithfulness": float(os.getenv("RAGAS_MIN_FAITHFULNESS", "0.0")),
        "relevancy": float(os.getenv("RAGAS_MIN_RELEVANCY", "0.0")),
        "noise_degradation": float(os.getenv("RAGAS_MAX_NOISE_DEGRADATION", "1.0")),
    }
