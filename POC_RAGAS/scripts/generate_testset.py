"""CLI to generate a synthetic testset."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG
from POC_RAGAS.generators.synthetic_testset import TestsetConfig, generate_synthetic_testset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a RAGAS synthetic testset.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(CONFIG.testset_dir) / "synthetic_testset.json",
        help="Output path for generated testset JSON.",
    )
    parser.add_argument("--size", type=int, default=CONFIG.test_set_size, help="Number of test questions.")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    config = TestsetConfig(
        test_size=args.size,
        simple_ratio=CONFIG.question_distribution_simple,
        multihop_ratio=CONFIG.question_distribution_multihop,
        conditional_ratio=CONFIG.question_distribution_conditional,
    )
    await generate_synthetic_testset(output_path=args.output, config=config)
    print(f"Generated testset: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
