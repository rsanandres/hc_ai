"""Test synthetic testset generation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG
from POC_RAGAS.generators.synthetic_testset import TestsetConfig, generate_synthetic_testset


@pytest.mark.asyncio
async def test_generate_synthetic_testset():
    if not CONFIG.openai_api_key:
        pytest.skip("OPENAI_API_KEY not configured.")

    output_path = Path(CONFIG.testset_dir) / "testset_smoke.json"
    config = TestsetConfig(
        test_size=min(10, CONFIG.test_set_size),
        simple_ratio=CONFIG.question_distribution_simple,
        multihop_ratio=CONFIG.question_distribution_multihop,
        conditional_ratio=CONFIG.question_distribution_conditional,
    )

    await generate_synthetic_testset(output_path=output_path, config=config)
    assert output_path.exists(), "Synthetic testset was not created."

    data = output_path.read_text().strip()
    assert data, "Synthetic testset file is empty."
