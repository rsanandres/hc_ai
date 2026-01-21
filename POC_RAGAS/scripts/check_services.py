"""Health checks for required services."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG
from POC_RAGAS.utils.db_loader import get_total_chunks


async def check_http(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            return response.status_code == 200
    except Exception:
        return False


async def main() -> int:
    agent_health = await check_http(CONFIG.agent_api_url.replace("/agent/query", "/agent/health"))
    reranker_health = await check_http(f"{CONFIG.reranker_url}/rerank/health")

    db_ok = False
    try:
        count = await get_total_chunks()
        db_ok = count > 0
    except Exception:
        count = 0

    print(f"Agent API health: {'OK' if agent_health else 'FAILED'}")
    print(f"Reranker health: {'OK' if reranker_health else 'FAILED'}")
    print(f"Postgres embeddings: {'OK' if db_ok else 'FAILED'} (rows: {count})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
