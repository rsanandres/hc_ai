"""Basic health checks for local services."""

from __future__ import annotations

import socket
import sys
from dataclasses import dataclass
from typing import Callable, Optional

import requests


@dataclass
class ServiceCheck:
    name: str
    check: Callable[[], bool]
    hint: Optional[str] = None


def _http_ok(url: str, timeout: int = 3) -> bool:
    try:
        resp = requests.get(url, timeout=timeout)
        return resp.status_code < 500
    except requests.RequestException:
        return False


def _http_any(url: str, timeout: int = 3) -> bool:
    try:
        requests.get(url, timeout=timeout)
        return True
    except requests.RequestException:
        return False


def _port_open(host: str, port: int, timeout: int = 2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def main() -> int:
    checks = [
        ServiceCheck(
            name="FastAPI /agent/health",
            check=lambda: _http_ok("http://localhost:8000/agent/health"),
            hint="Start with: uvicorn api.main:app --reload --port 8000",
        ),
        ServiceCheck(
            name="FastAPI /retrieval/rerank/health",
            check=lambda: _http_ok("http://localhost:8000/retrieval/rerank/health"),
            hint="Ensure retrieval router is loaded in api.main",
        ),
        ServiceCheck(
            name="DynamoDB Local (port 8001)",
            check=lambda: _http_any("http://localhost:8001"),
            hint="Start via db/dynamodb/docker-compose.yml",
        ),
        ServiceCheck(
            name="Postgres (port 5432)",
            check=lambda: _port_open("localhost", 5432),
            hint="Start via db/postgres/docker-compose.yml",
        ),
        ServiceCheck(
            name="Ollama /api/tags",
            check=lambda: _http_ok("http://localhost:11434/api/tags"),
            hint="Start Ollama: ollama serve",
        ),
    ]

    failures = 0
    for item in checks:
        ok = item.check()
        status = "OK" if ok else "FAIL"
        print(f"{status:4}  {item.name}")
        if not ok and item.hint:
            print(f"      hint: {item.hint}")
            failures += 1

    if failures:
        print(f"\n{failures} service(s) failed")
        return 1
    print("\nAll services reachable")
    return 0


if __name__ == "__main__":
    sys.exit(main())
