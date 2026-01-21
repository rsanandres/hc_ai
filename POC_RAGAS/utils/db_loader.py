"""PostgreSQL helpers for loading chunks and patient IDs."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from langchain_core.documents import Document
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from POC_RAGAS.config import CONFIG, REPO_ROOT


POSTGRES_MODULE_PATH = REPO_ROOT / "postgres" / "langchain-postgres.py"
INGEST_MODULE_PATH = REPO_ROOT / "postgres" / "ingest_fhir_json.py"


@dataclass
class ChunkRow:
    content: str
    metadata: Dict[str, Any]


def _load_module(path: Path, module_name: str):
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _connection_string() -> str:
    if not CONFIG.db_user or not CONFIG.db_password or not CONFIG.db_name:
        raise ValueError("Missing DB_USER, DB_PASSWORD, or DB_NAME in environment.")
    return (
        f"postgresql+asyncpg://{CONFIG.db_user}:{CONFIG.db_password}"
        f"@{CONFIG.db_host}:{CONFIG.db_port}/{CONFIG.db_name}"
    )


def get_engine() -> AsyncEngine:
    return create_async_engine(_connection_string(), echo=False)


def _get_table_info() -> tuple[str, str]:
    module = _load_module(POSTGRES_MODULE_PATH, "langchain_postgres")
    if module is None:
        return "hc_ai_schema", "hc_ai_table"
    schema = getattr(module, "SCHEMA_NAME", "hc_ai_schema")
    table = getattr(module, "TABLE_NAME", "hc_ai_table")
    return schema, table


async def get_total_chunks() -> int:
    schema, table = _get_table_info()
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(f'SELECT COUNT(*) FROM "{schema}"."{table}"')
            )
            return int(result.scalar_one())
    finally:
        await engine.dispose()


async def get_distinct_patient_ids(limit: int = 5000) -> List[str]:
    schema, table = _get_table_info()
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    f"""
                    SELECT DISTINCT (langchain_metadata::jsonb)->>'patientId' AS patient_id
                    FROM "{schema}"."{table}"
                    WHERE (langchain_metadata::jsonb) ? 'patientId'
                      AND (langchain_metadata::jsonb)->>'patientId' IS NOT NULL
                    LIMIT :limit
                    """
                ),
                {"limit": limit},
            )
            ids = [row[0] for row in result.fetchall() if row[0]]
            return sorted(set(ids))
    finally:
        await engine.dispose()


async def load_chunks(
    limit: int = 1000,
    offset: int = 0,
    patient_ids: Optional[Sequence[str]] = None,
) -> List[ChunkRow]:
    schema, table = _get_table_info()
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            if patient_ids:
                result = await conn.execute(
                    text(
                        f"""
                        SELECT content, langchain_metadata
                        FROM "{schema}"."{table}"
                        WHERE langchain_metadata->>'patientId' = ANY(:patient_ids)
                        ORDER BY langchain_metadata->>'patientId'
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    {"patient_ids": list(patient_ids), "limit": limit, "offset": offset},
                )
            else:
                result = await conn.execute(
                    text(
                        f"""
                        SELECT content, langchain_metadata
                        FROM "{schema}"."{table}"
                        LIMIT :limit OFFSET :offset
                        """
                    ),
                    {"limit": limit, "offset": offset},
                )
            rows = []
            for content, metadata in result.fetchall():
                rows.append(ChunkRow(content=content or "", metadata=metadata or {}))
            return rows
    finally:
        await engine.dispose()


async def load_documents(
    limit: int = 1000,
    offset: int = 0,
    patient_ids: Optional[Sequence[str]] = None,
) -> List[Document]:
    rows = await load_chunks(limit=limit, offset=offset, patient_ids=patient_ids)
    return [Document(page_content=row.content, metadata=row.metadata) for row in rows]


async def get_full_fhir_documents(patient_ids: Iterable[str]) -> List[Dict[str, Any]]:
    module = _load_module(INGEST_MODULE_PATH, "ingest_fhir_json")
    if module and hasattr(module, "get_latest_raw_files_by_patient_ids"):
        return await module.get_latest_raw_files_by_patient_ids(list(patient_ids))

    schema = getattr(module, "SCHEMA_NAME", "hc_ai_schema") if module else "hc_ai_schema"
    table = getattr(module, "RAW_TABLE", "fhir_raw_files") if module else "fhir_raw_files"
    engine = get_engine()
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    f"""
                    SELECT patient_id, source_filename, bundle_json
                    FROM "{schema}"."{table}"
                    WHERE patient_id = ANY(:patient_ids)
                    """
                ),
                {"patient_ids": list(patient_ids)},
            )
            documents = []
            for row in result.fetchall():
                documents.append(
                    {
                        "patient_id": row[0],
                        "source_filename": row[1],
                        "bundle_json": row[2],
                    }
                )
            return documents
    finally:
        await engine.dispose()
