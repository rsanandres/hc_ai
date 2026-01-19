"""Shared pytest fixtures."""

from __future__ import annotations

import asyncio
from pathlib import Path

from dotenv import load_dotenv
import pytest_asyncio
import sys

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))
from utils.env_loader import load_env_recursive
load_env_recursive(ROOT_DIR)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
