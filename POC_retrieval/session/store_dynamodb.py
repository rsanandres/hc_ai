from __future__ import annotations

import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


def _utc_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _ttl_epoch(ttl_days: Optional[int]) -> Optional[int]:
    if not ttl_days or ttl_days <= 0:
        return None
    return int(time.time() + ttl_days * 86400)


@dataclass
class SessionTurn:
    session_id: str
    turn_ts: str
    role: str
    text: str
    meta: Dict[str, Any]
    patient_id: Optional[str] = None
    ttl: Optional[int] = None


class SessionStore:
    """
    DynamoDB-backed session store for short conversation windows and summaries.
    No external cache; uses last-N query per request.
    """

    def __init__(
        self,
        region_name: str,
        turns_table: str,
        summary_table: str,
        endpoint_url: Optional[str] = None,
        ttl_days: Optional[int] = None,
        max_recent: int = 10,
        auto_create: bool = False,
    ) -> None:
        self.region_name = region_name
        self.turns_table_name = turns_table
        self.summary_table_name = summary_table
        self.ttl_days = ttl_days
        self.max_recent = max_recent
        self.resource = boto3.resource("dynamodb", region_name=region_name, endpoint_url=endpoint_url)
        self.turns_table = self.resource.Table(turns_table)
        self.summary_table = self.resource.Table(summary_table)
        if auto_create:
            self.ensure_tables()

    # ------------------------ table management ------------------------ #

    def ensure_tables(self) -> None:
        """Create tables if missing (PAY_PER_REQUEST) and enable TTL if configured."""
        client = self.resource.meta.client
        self._ensure_table(
            client=client,
            table_name=self.turns_table_name,
            key_schema=[
                {"AttributeName": "session_id", "KeyType": "HASH"},
                {"AttributeName": "turn_ts", "KeyType": "RANGE"},
            ],
            attribute_definitions=[
                {"AttributeName": "session_id", "AttributeType": "S"},
                {"AttributeName": "turn_ts", "AttributeType": "S"},
            ],
            ttl_attribute="ttl" if self.ttl_days and self.ttl_days > 0 else None,
        )
        self._ensure_table(
            client=client,
            table_name=self.summary_table_name,
            key_schema=[
                {"AttributeName": "session_id", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            attribute_definitions=[
                {"AttributeName": "session_id", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
            ],
            ttl_attribute="ttl" if self.ttl_days and self.ttl_days > 0 else None,
        )

    def _ensure_table(
        self,
        client,
        table_name: str,
        key_schema: List[Dict[str, str]],
        attribute_definitions: List[Dict[str, str]],
        ttl_attribute: Optional[str] = None,
    ) -> None:
        try:
            client.describe_table(TableName=table_name)
            exists = True
        except client.exceptions.ResourceNotFoundException:
            exists = False

        if not exists:
            client.create_table(
                TableName=table_name,
                KeySchema=key_schema,
                AttributeDefinitions=attribute_definitions,
                BillingMode="PAY_PER_REQUEST",
            )
            waiter = client.get_waiter("table_exists")
            waiter.wait(TableName=table_name)

        if ttl_attribute:
            try:
                client.update_time_to_live(
                    TableName=table_name,
                    TimeToLiveSpecification={"Enabled": True, "AttributeName": ttl_attribute},
                )
            except ClientError:
                # If TTL already set or not permitted, ignore silently
                pass

    # ------------------------ operations ------------------------ #

    def append_turn(
        self,
        session_id: str,
        role: str,
        text: str,
        meta: Optional[Dict[str, Any]] = None,
        patient_id: Optional[str] = None,
    ) -> SessionTurn:
        turn_ts = _utc_iso()
        ttl = _ttl_epoch(self.ttl_days)
        item: Dict[str, Any] = {
            "session_id": session_id,
            "turn_ts": turn_ts,
            "role": role,
            "text": text,
            "meta": meta or {},
        }
        if patient_id:
            item["patient_id"] = patient_id
        if ttl:
            item["ttl"] = ttl
        self.turns_table.put_item(Item=item)
        return SessionTurn(session_id=session_id, turn_ts=turn_ts, role=role, text=text, meta=item["meta"], patient_id=patient_id, ttl=ttl)

    def get_recent(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        lim = limit or self.max_recent
        resp = self.turns_table.query(
            KeyConditionExpression=Key("session_id").eq(session_id),
            ScanIndexForward=False,  # newest first
            Limit=lim,
        )
        items = resp.get("Items", [])
        # Return newest-first; callers can reverse if they prefer chronological.
        return items

    def update_summary(self, session_id: str, summary: Dict[str, Any], patient_id: Optional[str] = None) -> None:
        ttl = _ttl_epoch(self.ttl_days)
        # Persist under SK=summary
        expr = ["updated_at = :updated_at"]
        values: Dict[str, Any] = {":updated_at": _utc_iso()}
        if patient_id:
            expr.append("patient_id = :patient_id")
            values[":patient_id"] = patient_id
        for key, val in summary.items():
            expr.append(f"{key} = :{key}")
            values[f":{key}"] = val
        if ttl:
            expr.append("ttl = :ttl")
            values[":ttl"] = ttl
        update_expr = "SET " + ", ".join(expr)
        self.summary_table.update_item(
            Key={"session_id": session_id, "sk": "summary"},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=values,
        )

    def get_summary(self, session_id: str) -> Dict[str, Any]:
        resp = self.summary_table.get_item(Key={"session_id": session_id, "sk": "summary"})
        return resp.get("Item", {})

    def set_patient(self, session_id: str, patient_id: str) -> None:
        self.update_summary(session_id=session_id, summary={}, patient_id=patient_id)

    def get_patient(self, session_id: str) -> Optional[str]:
        item = self.get_summary(session_id)
        return item.get("patient_id")

    def clear_session(self, session_id: str) -> None:
        """Delete all turns and summary for a session."""
        # Delete summary
        try:
            self.summary_table.delete_item(Key={"session_id": session_id, "sk": "summary"})
        except ClientError:
            pass
        # Delete turns in batches
        resp = self.turns_table.query(
            KeyConditionExpression=Key("session_id").eq(session_id),
            ProjectionExpression="session_id, turn_ts",
        )
        items = resp.get("Items", [])
        while True:
            with self.turns_table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={"session_id": item["session_id"], "turn_ts": item["turn_ts"]})
            if "LastEvaluatedKey" not in resp:
                break
            resp = self.turns_table.query(
                KeyConditionExpression=Key("session_id").eq(session_id),
                ProjectionExpression="session_id, turn_ts",
                ExclusiveStartKey=resp["LastEvaluatedKey"],
            )
            items = resp.get("Items", [])


def build_store_from_env() -> SessionStore:
    """Factory that builds a SessionStore using environment variables."""
    region = os.getenv("AWS_REGION", "us-east-1")
    turns_table = os.getenv("DDB_TURNS_TABLE", "hcai_session_turns")
    summary_table = os.getenv("DDB_SUMMARY_TABLE", "hcai_session_summary")
    endpoint = os.getenv("DDB_ENDPOINT")
    ttl_days_str = os.getenv("DDB_TTL_DAYS")
    ttl_days = int(ttl_days_str) if ttl_days_str and ttl_days_str.isdigit() else None
    auto_create = os.getenv("DDB_AUTO_CREATE", "false").lower() in {"1", "true", "yes"}
    max_recent = int(os.getenv("SESSION_RECENT_LIMIT", "10"))
    return SessionStore(
        region_name=region,
        turns_table=turns_table,
        summary_table=summary_table,
        endpoint_url=endpoint,
        ttl_days=ttl_days,
        max_recent=max_recent,
        auto_create=auto_create,
    )
