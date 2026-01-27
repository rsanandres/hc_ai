"""Validate environment variables for API configuration."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv


_TABLE_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")


def _check_table_name(name: str) -> Tuple[bool, str]:
    if not name:
        return False, "empty"
    if len(name) < 3 or len(name) > 255:
        return False, f"invalid length ({len(name)})"
    if not _TABLE_NAME_RE.match(name):
        return False, "invalid characters (allowed: a-z A-Z 0-9 _ . -)"
    return True, "ok"


def main() -> int:
    # Load .env file from project root (hc_ai/.env)
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    env_file = project_root / ".env"
    
    if env_file.exists():
        load_dotenv(env_file, override=False)
        print(f"Loaded .env from: {env_file}")
    else:
        print(f"Warning: .env file not found at {env_file}")
    
    issues: List[str] = []

    ddb_endpoint = os.getenv("DDB_ENDPOINT", "")
    turns_table = os.getenv("DDB_TURNS_TABLE", "")
    summary_table = os.getenv("DDB_SUMMARY_TABLE", "")
    reranker_url = os.getenv("RERANKER_SERVICE_URL", "")

    if ddb_endpoint:
        if "8000" in ddb_endpoint:
            issues.append(
                f"DDB_ENDPOINT points to port 8000 ({ddb_endpoint}). "
                "Expected DynamoDB Local on port 8001."
            )
    else:
        issues.append("DDB_ENDPOINT is not set (expected http://localhost:8001)")

    ok, msg = _check_table_name(turns_table)
    if not ok:
        issues.append(f"DDB_TURNS_TABLE invalid: {msg} ({turns_table!r})")

    ok, msg = _check_table_name(summary_table)
    if not ok:
        issues.append(f"DDB_SUMMARY_TABLE invalid: {msg} ({summary_table!r})")

    if reranker_url:
        if reranker_url.startswith("http://localhost:8001"):
            issues.append(
                "RERANKER_SERVICE_URL points to port 8001; "
                "expected unified API on http://localhost:8000/retrieval"
            )
        if "/retrieval" not in reranker_url and "/rerank" in reranker_url:
            issues.append(
                "RERANKER_SERVICE_URL should use /retrieval/rerank on unified API"
            )
    else:
        issues.append(
            "RERANKER_SERVICE_URL not set; "
            "expected http://localhost:8000/retrieval"
        )

    if issues:
        print("Environment issues detected:")
        for item in issues:
            print(f"- {item}")
        print("\nSuggested values:")
        print("DDB_ENDPOINT=http://localhost:8001")
        print("DDB_TURNS_TABLE=hcai_session_turns")
        print("DDB_SUMMARY_TABLE=hcai_session_summary")
        print("RERANKER_SERVICE_URL=http://localhost:8000/retrieval")
        return 1

    print("Environment looks good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
