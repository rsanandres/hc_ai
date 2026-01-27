"""DynamoDB Local diagnostics."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import boto3

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from api.session.store_dynamodb import build_store_from_env


def _build_resource():
    endpoint = os.getenv("DDB_ENDPOINT", "http://localhost:8001")
    region = os.getenv("AWS_REGION", "us-east-1")
    if endpoint:
        return boto3.resource(
            "dynamodb",
            region_name=region,
            endpoint_url=endpoint,
            aws_access_key_id="dummy",
            aws_secret_access_key="dummy",
        )
    return boto3.resource("dynamodb", region_name=region)


def main() -> int:
    endpoint = os.getenv("DDB_ENDPOINT", "http://localhost:8001")
    turns_table = os.getenv("DDB_TURNS_TABLE", "hcai_session_turns")
    summary_table = os.getenv("DDB_SUMMARY_TABLE", "hcai_session_summary")
    auto_create = os.getenv("DDB_AUTO_CREATE", "false").lower() in {"1", "true", "yes"}

    print("DynamoDB diagnostics")
    print(f"- endpoint: {endpoint}")
    print(f"- turns_table: {turns_table}")
    print(f"- summary_table: {summary_table}")
    print(f"- auto_create: {auto_create}")

    try:
        resource = _build_resource()
        client = resource.meta.client
        tables = client.list_tables().get("TableNames", [])
        print(f"- tables: {tables}")
    except Exception as exc:
        print(f"FAIL  connection error: {exc}")
        return 1

    if auto_create:
        try:
            build_store_from_env()
            print("OK    auto_create: ensured tables")
        except Exception as exc:
            print(f"FAIL  auto_create error: {exc}")
            return 1

    for name in (turns_table, summary_table):
        try:
            client.describe_table(TableName=name)
            print(f"OK    describe_table: {name}")
        except Exception as exc:
            print(f"FAIL  describe_table: {name} ({exc})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
