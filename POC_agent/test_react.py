"""Minimal import test for agent package."""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from utils.env_loader import load_env_recursive
load_env_recursive(ROOT_DIR)
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from POC_agent.agent.graph import get_agent


def main() -> int:
    _ = get_agent()
    print("ReAct agent import OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
