"""
Ingest full FHIR bundle JSON files into Postgres, separate from embeddings.

Defaults:
- Uses DB_* environment variables (DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME)
- Schema: hc_ai_schema
- Tables:
    - fhir_raw_files: stores JSONB bundle per file with versioning
    - fhir_raw_ingest_log: tracks ingest attempts

Behavior:
- Scans data/fhir/*.json (configurable) sorted by filename.
- Limits to first 10,000 files by default (configurable).
- Extracts patientId like POC_embeddings/main.go|main.py: Patient resource id, else Patient fullUrl, else "unknown".
- Computes content hash; if identical hash already exists for patient+filename, skips new version.
- Otherwise inserts with next version for that patientId.
- Provides helpers to fetch raw files by patient or patient+filename for POC retrieval.
"""

import argparse
import asyncio
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Load .env from repo root (one level up from scripts/ folder)
ROOT_DIR = Path(__file__).resolve().parents[1]  # Go up 1 level from scripts/ to project root
import sys
sys.path.insert(0, str(ROOT_DIR))
from utils.env_loader import load_env_recursive
load_env_recursive(ROOT_DIR)

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")

SCHEMA_NAME = os.getenv("HC_AI_SCHEMA", "hc_ai_schema")
RAW_TABLE = os.getenv("HC_AI_RAW_TABLE", "fhir_raw_files")
LOG_TABLE = os.getenv("HC_AI_RAW_LOG_TABLE", "fhir_raw_ingest_log")

DEFAULT_DATA_DIR = ROOT_DIR / "data" / "fhir"
DEFAULT_MAX_FILES = 10_000  # per requirement: first 10,000 files ordered by filename

_engine: Optional[AsyncEngine] = None


# ------------------------------- Engine & Schema ------------------------------- #

def _require_env():
    missing = [name for name, val in [("DB_USER", DB_USER), ("DB_PASSWORD", DB_PASSWORD), ("DB_NAME", DB_NAME)] if not val]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _require_env()
        conn_str = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        _engine = create_async_engine(conn_str, echo=False)
    return _engine


async def ensure_tables(engine: AsyncEngine):
    """Create schema and tables if they do not exist."""
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA_NAME}"'))

        await conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS "{SCHEMA_NAME}"."{RAW_TABLE}" (
                    patient_id      TEXT        NOT NULL,
                    source_filename TEXT        NOT NULL,
                    file_path       TEXT        NOT NULL,
                    file_hash       TEXT        NOT NULL,
                    bundle_json     JSONB       NOT NULL,
                    version         INTEGER     NOT NULL,
                    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (patient_id, version)
                );
                """
            )
        )
        await conn.execute(
            text(
                f"""
                CREATE UNIQUE INDEX IF NOT EXISTS "idx_{RAW_TABLE}_uniq"
                ON "{SCHEMA_NAME}"."{RAW_TABLE}" (patient_id, source_filename, file_hash);
                """
            )
        )
        await conn.execute(
            text(
                f"""
                CREATE INDEX IF NOT EXISTS "idx_{RAW_TABLE}_patient"
                ON "{SCHEMA_NAME}"."{RAW_TABLE}" (patient_id);
                """
            )
        )

        await conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS "{SCHEMA_NAME}"."{LOG_TABLE}" (
                    id              BIGSERIAL   PRIMARY KEY,
                    patient_id      TEXT,
                    source_filename TEXT,
                    file_path       TEXT,
                    file_hash       TEXT,
                    version         INTEGER,
                    status          TEXT        NOT NULL,
                    message         TEXT,
                    ingested_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
        )
        await conn.execute(
            text(
                f"""
                CREATE INDEX IF NOT EXISTS "idx_{LOG_TABLE}_patient"
                ON "{SCHEMA_NAME}"."{LOG_TABLE}" (patient_id);
                """
            )
        )


# ------------------------------- Helpers ------------------------------- #

def compute_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_patient_id(bundle: Dict[str, Any]) -> str:
    """Match logic from POC_embeddings main.go/main.py."""
    entries = bundle.get("entry") or []
    for entry in entries:
        resource = entry.get("resource") or {}
        if resource.get("resourceType") == "Patient":
            rid = resource.get("id")
            if rid:
                return str(rid)
            full_url = entry.get("fullUrl")
            if full_url:
                return str(full_url)
    return "unknown"


def load_bundle(path: Path) -> Tuple[Dict[str, Any], str]:
    data = path.read_bytes()
    bundle = json.loads(data)
    return bundle, compute_hash(data)


async def get_existing_version(conn, patient_id: str, filename: str, file_hash: str) -> Optional[int]:
    res = await conn.execute(
        text(
            f"""
            SELECT version
            FROM "{SCHEMA_NAME}"."{RAW_TABLE}"
            WHERE patient_id = :patient_id
              AND source_filename = :filename
              AND file_hash = :file_hash
            LIMIT 1
            """
        ),
        {"patient_id": patient_id, "filename": filename, "file_hash": file_hash},
    )
    row = res.fetchone()
    return row[0] if row else None


async def next_version_for_patient(conn, patient_id: str) -> int:
    res = await conn.execute(
        text(
            f"""
            SELECT COALESCE(MAX(version), 0) + 1
            FROM "{SCHEMA_NAME}"."{RAW_TABLE}"
            WHERE patient_id = :patient_id
            """
        ),
        {"patient_id": patient_id},
    )
    return res.scalar_one()


async def insert_raw_file(
    conn,
    patient_id: str,
    filename: str,
    file_path: str,
    file_hash: str,
    bundle_json: Dict[str, Any],
    version: int,
):
    await conn.execute(
        text(
            f"""
            INSERT INTO "{SCHEMA_NAME}"."{RAW_TABLE}"
                (patient_id, source_filename, file_path, file_hash, bundle_json, version)
            VALUES
                (:patient_id, :filename, :file_path, :file_hash, CAST(:bundle_json AS jsonb), :version)
            """
        ),
        {
            "patient_id": patient_id,
            "filename": filename,
            "file_path": file_path,
            "file_hash": file_hash,
            "bundle_json": json.dumps(bundle_json),
            "version": version,
        },
    )


async def log_ingest(conn, patient_id: str, filename: str, file_path: str, file_hash: str, status: str, version: Optional[int], message: str = ""):
    await conn.execute(
        text(
            f"""
            INSERT INTO "{SCHEMA_NAME}"."{LOG_TABLE}"
                (patient_id, source_filename, file_path, file_hash, version, status, message)
            VALUES
                (:patient_id, :filename, :file_path, :file_hash, :version, :status, :message)
            """
        ),
        {
            "patient_id": patient_id,
            "filename": filename,
            "file_path": file_path,
            "file_hash": file_hash,
            "version": version,
            "status": status,
            "message": message[:2000],
        },
    )


# ------------------------------- Ingest Logic ------------------------------- #

async def process_file(conn, path: Path, dry_run: bool = False) -> Tuple[str, str, str]:
    bundle, file_hash = load_bundle(path)
    patient_id = extract_patient_id(bundle)
    filename = path.name
    existing_version = await get_existing_version(conn, patient_id, filename, file_hash)

    if existing_version is not None:
        await log_ingest(conn, patient_id, filename, str(path), file_hash, status="skipped-identical", version=existing_version, message="Identical content already stored")
        return patient_id, filename, "skipped"

    version = await next_version_for_patient(conn, patient_id)
    if not dry_run:
        await insert_raw_file(conn, patient_id, filename, str(path), file_hash, bundle, version)
        await log_ingest(conn, patient_id, filename, str(path), file_hash, status="ingested", version=version)
    return patient_id, filename, "ingested"


async def ingest_dir(data_dir: Path, max_files: int, dry_run: bool = False) -> Dict[str, int]:
    engine = get_engine()
    await ensure_tables(engine)

    files = sorted(data_dir.glob("*.json"))
    selected = files[:max_files] if max_files is not None else files

    stats = {"total": len(selected), "ingested": 0, "skipped": 0, "failed": 0}

    for path in selected:
        try:
            async with engine.begin() as conn:
                _, filename, status = await process_file(conn, path, dry_run=dry_run)
                stats[status] = stats.get(status, 0) + 1
        except Exception as exc:  # noqa: BLE001
            stats["failed"] += 1
            try:
                async with engine.begin() as conn:
                    await log_ingest(conn, patient_id="unknown", filename=path.name, file_path=str(path), file_hash="", status="failed", version=None, message=str(exc))
            except Exception as log_exc:  # noqa: BLE001
                print(f"[LOG-ERROR] {path.name}: {log_exc}")
            print(f"[ERROR] {path.name}: {exc}")
    return stats


# ------------------------------- Retrieval Helpers ------------------------------- #

async def get_raw_files_by_patient(patient_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    """Fetch raw bundles for a patient, newest versions first."""
    engine = get_engine()
    await ensure_tables(engine)
    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                f"""
                SELECT source_filename, file_path, file_hash, version, ingested_at, bundle_json
                FROM "{SCHEMA_NAME}"."{RAW_TABLE}"
                WHERE patient_id = :patient_id
                ORDER BY version DESC
                LIMIT :limit OFFSET :offset
                """
            ),
            {"patient_id": patient_id, "limit": limit, "offset": offset},
        )
        rows = res.fetchall()
        return [
            {
                "patient_id": patient_id,
                "source_filename": r[0],
                "file_path": r[1],
                "file_hash": r[2],
                "version": r[3],
                "ingested_at": r[4],
                "bundle_json": r[5],
            }
            for r in rows
        ]


async def get_raw_file(patient_id: str, filename: str) -> Optional[Dict[str, Any]]:
    """Fetch latest version of a specific file for a patient."""
    engine = get_engine()
    await ensure_tables(engine)
    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                f"""
                SELECT source_filename, file_path, file_hash, version, ingested_at, bundle_json
                FROM "{SCHEMA_NAME}"."{RAW_TABLE}"
                WHERE patient_id = :patient_id
                  AND source_filename = :filename
                ORDER BY version DESC
                LIMIT 1
                """
            ),
            {"patient_id": patient_id, "filename": filename},
        )
        row = res.fetchone()
        if not row:
            return None
        return {
            "patient_id": patient_id,
            "source_filename": row[0],
            "file_path": row[1],
            "file_hash": row[2],
            "version": row[3],
            "ingested_at": row[4],
            "bundle_json": row[5],
        }


async def get_raw_files_by_patients(patient_ids: List[str], limit_per_patient: int = 50) -> List[Dict[str, Any]]:
    """Fetch raw bundles for multiple patients, newest versions first."""
    if not patient_ids:
        return []
    engine = get_engine()
    await ensure_tables(engine)
    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                f"""
                SELECT patient_id, source_filename, file_path, file_hash, version, ingested_at, bundle_json
                FROM "{SCHEMA_NAME}"."{RAW_TABLE}"
                WHERE patient_id = ANY(:patient_ids)
                ORDER BY patient_id, version DESC
                """
            ),
            {"patient_ids": patient_ids},
        )
        rows = res.fetchall()
        results = [
            {
                "patient_id": r[0],
                "source_filename": r[1],
                "file_path": r[2],
                "file_hash": r[3],
                "version": r[4],
                "ingested_at": r[5],
                "bundle_json": r[6],
            }
            for r in rows
        ]
    if limit_per_patient is None:
        return results
    trimmed: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}
    for item in results:
        pid = item["patient_id"]
        counts[pid] = counts.get(pid, 0) + 1
        if counts[pid] <= limit_per_patient:
            trimmed.append(item)
    return trimmed


async def get_latest_raw_files_by_patient_ids(patient_ids: List[str]) -> List[Dict[str, Any]]:
    """Fetch latest raw bundle per patient_id."""
    if not patient_ids:
        return []
    engine = get_engine()
    await ensure_tables(engine)
    async with engine.begin() as conn:
        res = await conn.execute(
            text(
                f"""
                SELECT DISTINCT ON (patient_id)
                    patient_id,
                    source_filename,
                    file_path,
                    file_hash,
                    version,
                    ingested_at,
                    bundle_json
                FROM "{SCHEMA_NAME}"."{RAW_TABLE}"
                WHERE patient_id = ANY(:patient_ids)
                ORDER BY patient_id, version DESC
                """
            ),
            {"patient_ids": patient_ids},
        )
        rows = res.fetchall()
        return [
            {
                "patient_id": r[0],
                "source_filename": r[1],
                "file_path": r[2],
                "file_hash": r[3],
                "version": r[4],
                "ingested_at": r[5],
                "bundle_json": r[6],
            }
            for r in rows
        ]


# ------------------------------- CLI ------------------------------- #

def parse_args():
    parser = argparse.ArgumentParser(description="Ingest FHIR bundle JSON files into Postgres (separate from embeddings).")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR, help="Directory containing *.json bundle files (default: data/fhir)")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES, help="Maximum files to process, ordered by filename (default: 10000)")
    parser.add_argument("--no-limit", action="store_true", help="Process all files (overrides --max-files)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and hash only; no DB writes")
    return parser.parse_args()


async def main():
    args = parse_args()
    data_dir = args.data_dir
    max_files = None if args.no_limit else args.max_files

    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    started = datetime.utcnow()
    print(f"Starting ingest from {data_dir} (max_files={max_files}, dry_run={args.dry_run}) at {started.isoformat()}Z")
    stats = await ingest_dir(data_dir, max_files=max_files, dry_run=args.dry_run)
    finished = datetime.utcnow()
    print(f"Finished at {finished.isoformat()}Z | duration={(finished - started).total_seconds():.1f}s")
    print(f"Stats: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
