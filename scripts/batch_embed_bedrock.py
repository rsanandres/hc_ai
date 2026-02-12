#!/usr/bin/env python
"""
Batch Embedding Script for FHIR Patient Data — Amazon Bedrock Titan

Direct Bedrock embedding script that bypasses the HTTP API layer for maximum
throughput. Reads from fhir_raw_files in Postgres, chunks with RecursiveJsonSplitter,
embeds via Bedrock Titan with parallel API calls, and bulk-inserts into hc_ai_table.

Key optimizations over batch_embed_patients.py:
- Direct Bedrock API calls (no FastAPI server needed)
- Parallel embedding (25 concurrent Bedrock calls via ThreadPoolExecutor)
- Bulk DB inserts (50 documents per aadd_documents call)
- Concurrent patient fetching (5 patients via asyncio)

Usage:
    python scripts/batch_embed_bedrock.py [options]

Options:
    --limit N           Only process first N patients
    --batch-size N      Concurrent patients (default: 5)
    --embed-batch N     Parallel Bedrock calls (default: 25)
    --insert-batch N    Documents per DB insert (default: 50)
    --dry-run           Show what would be done without making changes

Environment Variables:
    AWS_REGION              AWS region for Bedrock (default: us-east-1)
    BEDROCK_EMBED_MODEL     Model ID (default: amazon.titan-embed-text-v2:0)
    DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME - Database connection
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple

# ═══════════════════════════════════════════════════════════════════════════════
# PATH & ENV SETUP
# ═══════════════════════════════════════════════════════════════════════════════

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from utils.env_loader import load_env_recursive
load_env_recursive(ROOT_DIR)

# Set embedding provider BEFORE importing helper.py to avoid Ollama connection check
os.environ.setdefault("EMBEDDING_PROVIDER", "bedrock")

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from langchain_postgres import PGVectorStore, PGEngine
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

# Import chunking utilities directly from helper.py to avoid triggering
# api/embeddings/__init__.py which imports FastAPI (not needed for this script)
import importlib.util as _ilu
_helper_path = ROOT_DIR / "api" / "embeddings" / "utils" / "helper.py"
_spec = _ilu.spec_from_file_location("helper", _helper_path)
_helper = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
recursive_json_chunking = _helper.recursive_json_chunking
extract_resource_metadata = _helper.extract_resource_metadata

# ═══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Suppress noisy loggers from imports
# recursive_json_chunking logs ERROR for each resource where RecursiveJsonSplitter
# hits an edge case — the fallback (single chunk) still works, so treat as debug noise
for name in ("api.embeddings.utils.helper", "helper", "langchain_postgres", "botocore", "urllib3"):
    logging.getLogger(name).setLevel(logging.CRITICAL)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
SCHEMA_NAME = os.getenv("HC_AI_SCHEMA", "hc_ai_schema")
TABLE_NAME = "hc_ai_table"
VECTOR_SIZE = 1024

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v2:0")

# Global DB engine
_engine: Optional[AsyncEngine] = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        conn_str = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        _engine = create_async_engine(conn_str, pool_size=10, max_overflow=5, echo=False)
    return _engine


# ═══════════════════════════════════════════════════════════════════════════════
# BEDROCK EMBEDDINGS (BATCHED VIA THREAD POOL)
# ═══════════════════════════════════════════════════════════════════════════════

class BatchBedrockEmbeddings(Embeddings):
    """
    LangChain-compatible embeddings using Amazon Bedrock Titan.
    Parallelizes invoke_model calls using a shared ThreadPoolExecutor.
    """

    def __init__(
        self,
        model_id: str = BEDROCK_MODEL_ID,
        region: str = AWS_REGION,
        max_workers: int = 25,
    ):
        self.model_id = model_id
        self.region = region
        self.max_workers = max_workers
        # Size boto3's HTTP pool to match thread count (avoids "pool is full" warnings)
        boto_config = BotoConfig(max_pool_connections=max_workers + 5)
        self.client = boto3.client("bedrock-runtime", region_name=self.region, config=boto_config)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._call_count = 0
        self._retry_count = 0

    def _embed_single(self, text_input: str) -> List[float]:
        """Embed a single text with retry for throttling."""
        max_retries = 5
        for attempt in range(max_retries):
            try:
                body = json.dumps({"inputText": text_input})
                response = self.client.invoke_model(
                    modelId=self.model_id,
                    body=body,
                    contentType="application/json",
                    accept="application/json",
                )
                result = json.loads(response["body"].read())
                self._call_count += 1
                return result.get("embedding", [])
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code in ("ThrottlingException", "TooManyRequestsException") and attempt < max_retries - 1:
                    delay = min(2 ** attempt, 16)
                    self._retry_count += 1
                    time.sleep(delay)
                    continue
                raise
        return []  # unreachable but satisfies type checker

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed multiple texts in parallel using the shared thread pool."""
        workers = min(self.max_workers, len(texts))
        if workers == 0:
            return []
        return list(self._executor.map(self._embed_single, texts))

    def embed_query(self, text_input: str) -> List[float]:
        """Embed a single query text."""
        return self._embed_single(text_input)

    def test_connection(self) -> bool:
        """Verify Bedrock access with a single test embedding."""
        try:
            result = self._embed_single("connection test")
            if result and len(result) == VECTOR_SIZE:
                return True
            logger.error(f"Unexpected embedding dimension: {len(result)} (expected {VECTOR_SIZE})")
            return False
        except Exception as e:
            logger.error(f"Bedrock connection test failed: {e}")
            return False

    def shutdown(self):
        self._executor.shutdown(wait=False)


# ═══════════════════════════════════════════════════════════════════════════════
# PATIENT DISCOVERY (reused SQL from batch_embed_patients.py)
# ═══════════════════════════════════════════════════════════════════════════════

async def get_embedded_patients() -> Set[str]:
    """Get patient IDs that already have embeddings."""
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text(f'''
            SELECT DISTINCT langchain_metadata->>'patient_id'
            FROM "{SCHEMA_NAME}".{TABLE_NAME}
            WHERE langchain_metadata->>'patient_id' IS NOT NULL
        '''))
        return {row[0] for row in result.fetchall()}


async def get_all_fhir_patients() -> List[str]:
    """Get all patient IDs from fhir_raw_files."""
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text(f'''
            SELECT DISTINCT patient_id
            FROM "{SCHEMA_NAME}".fhir_raw_files
            ORDER BY patient_id
        '''))
        return [row[0] for row in result.fetchall()]


async def get_patients_needing_embedding() -> List[str]:
    """Get patient IDs that have FHIR data but no embeddings yet."""
    embedded = await get_embedded_patients()
    all_patients = await get_all_fhir_patients()
    return [p for p in all_patients if p not in embedded]


async def get_patient_fhir_data(patient_id: str) -> List[Dict[str, Any]]:
    """Fetch the latest FHIR bundle for a patient."""
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text(f'''
            SELECT source_filename, bundle_json
            FROM "{SCHEMA_NAME}".fhir_raw_files
            WHERE patient_id = :patient_id
            ORDER BY version DESC
            LIMIT 1
        '''), {"patient_id": patient_id})
        rows = result.fetchall()
        return [{"filename": r[0], "bundle": r[1]} for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# RESOURCE PROCESSING
# ═══════════════════════════════════════════════════════════════════════════════

def process_patient_resources(
    patient_id: str,
    source_filename: str,
    bundle: Dict[str, Any],
) -> List[Document]:
    """
    Process a patient's FHIR bundle into Document objects ready for embedding.

    Chunks each resource with RecursiveJsonSplitter and builds metadata
    matching the format used by process_and_store() in helper.py.
    """
    documents = []

    if not isinstance(bundle, dict):
        return documents

    entries = bundle.get("entry", [])

    for entry in entries:
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType", "")
        resource_id = resource.get("id", entry.get("fullUrl", ""))

        if not resource_type:
            continue

        # Serialize resource to JSON for chunking (same as process_and_store)
        resource_json = json.dumps(resource, ensure_ascii=False)

        if not resource_json or len(resource_json.strip()) < 10:
            continue

        # Chunk using RecursiveJsonSplitter (same params as process_and_store)
        chunks = recursive_json_chunking(
            resource_json,
            max_chunk_size=1000,
            min_chunk_size=500,
        )

        if not chunks:
            continue

        # Extract date/status metadata from the resource
        resource_metadata = extract_resource_metadata(resource_json)
        total_chunks = len(chunks)

        for chunk in chunks:
            chunk_uuid = str(uuid.uuid4())

            # Build metadata matching existing schema (snake_case)
            metadata = {
                "patient_id": patient_id,
                "resource_id": resource_id,
                "resource_type": resource_type,
                "full_url": entry.get("fullUrl", ""),
                "source_file": source_filename,
                "chunk_id": f"{resource_id}_{chunk['chunk_id']}",
                "chunk_index": chunk["chunk_index"],
                "total_chunks": total_chunks,
                "chunk_size": chunk["chunk_size"],
            }

            if "effectiveDate" in resource_metadata:
                metadata["effective_date"] = resource_metadata["effectiveDate"]
            if "status" in resource_metadata:
                metadata["status"] = resource_metadata["status"]
            if "lastUpdated" in resource_metadata:
                metadata["last_updated"] = resource_metadata["lastUpdated"]

            doc = Document(
                id=chunk_uuid,
                page_content=chunk["text"],
                metadata=metadata,
            )
            documents.append(doc)

    return documents


# ═══════════════════════════════════════════════════════════════════════════════
# VECTOR STORE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

async def init_vector_store(embeddings: BatchBedrockEmbeddings) -> PGVectorStore:
    """Initialize PGVectorStore with the given embeddings service."""
    engine = get_engine()
    pg_engine = PGEngine.from_engine(engine=engine)

    # Ensure schema exists
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA_NAME}"'))

    # Check if table exists
    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = :schema AND table_name = :table
            )
        """), {"schema": SCHEMA_NAME, "table": TABLE_NAME})
        exists = result.scalar_one()

    if not exists:
        await pg_engine.ainit_vectorstore_table(
            table_name=TABLE_NAME,
            vector_size=VECTOR_SIZE,
            schema_name=SCHEMA_NAME,
        )

    vector_store = await PGVectorStore.create(
        engine=pg_engine,
        table_name=TABLE_NAME,
        schema_name=SCHEMA_NAME,
        embedding_service=embeddings,
    )

    return vector_store


# ═══════════════════════════════════════════════════════════════════════════════
# BATCH PROCESSING
# ═══════════════════════════════════════════════════════════════════════════════

async def embed_patient(
    patient_id: str,
    vector_store: PGVectorStore,
    insert_batch_size: int = 50,
    dry_run: bool = False,
) -> Tuple[bool, int, str]:
    """
    Fetch, chunk, embed, and store one patient's FHIR data.

    Returns: (success, chunk_count, error_message)
    """
    try:
        fhir_data = await get_patient_fhir_data(patient_id)
        if not fhir_data:
            return False, 0, "No FHIR data found"

        all_docs: List[Document] = []
        for data in fhir_data:
            bundle = data["bundle"]
            filename = data["filename"]
            docs = process_patient_resources(patient_id, filename, bundle)
            all_docs.extend(docs)

        if not all_docs:
            return True, 0, "No chunks generated"

        if dry_run:
            return True, len(all_docs), ""

        # Insert in batches (aadd_documents calls embed_documents internally)
        stored = 0
        for i in range(0, len(all_docs), insert_batch_size):
            batch = all_docs[i : i + insert_batch_size]
            await vector_store.aadd_documents(batch)
            stored += len(batch)

        return True, stored, ""

    except Exception as e:
        return False, 0, str(e)


async def run_batch(
    batch_size: int = 5,
    embed_batch_size: int = 25,
    insert_batch_size: int = 50,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Run the full batch embedding pipeline."""

    start_time = time.time()

    # ── Discover patients ────────────────────────────────────────────────
    logger.info("Discovering patients needing embedding...")
    patients = await get_patients_needing_embedding()

    total_needing = len(patients)

    if limit:
        patients = patients[:limit]

    total_patients = len(patients)
    total_in_db = len(await get_all_fhir_patients())
    already_done = total_in_db - total_needing
    logger.info(f"Total patients in DB: {total_in_db}")
    logger.info(f"Already embedded:     {already_done}")
    logger.info(f"Needing embedding:    {total_needing}")
    if limit:
        logger.info(f"Processing (--limit): {total_patients}")

    if total_patients == 0:
        return {"status": "complete", "message": "All patients already embedded"}

    # ── Initialize embeddings & vector store ─────────────────────────────
    embeddings = BatchBedrockEmbeddings(max_workers=embed_batch_size)
    vector_store = None

    if not dry_run:
        logger.info(f"Testing Bedrock connection ({BEDROCK_MODEL_ID}, {AWS_REGION})...")
        if not embeddings.test_connection():
            return {"status": "error", "message": "Bedrock connection failed — check AWS credentials"}
        logger.info(f"Bedrock OK ({VECTOR_SIZE}D embeddings)")

        logger.info("Initializing vector store...")
        vector_store = await init_vector_store(embeddings)
        logger.info("Vector store ready")

    # ── Stats ────────────────────────────────────────────────────────────
    stats: Dict[str, Any] = {
        "total_patients": total_patients,
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "total_chunks": 0,
        "errors": [],
    }

    # ── Process in groups ────────────────────────────────────────────────
    semaphore = asyncio.Semaphore(batch_size)

    async def process_one(patient_id: str) -> Tuple[str, bool, int, str]:
        async with semaphore:
            success, chunks, error = await embed_patient(
                patient_id, vector_store, insert_batch_size, dry_run
            )
            return patient_id, success, chunks, error

    # Process in reporting groups (report progress every N patients)
    group_size = max(batch_size * 4, 20)

    for i in range(0, len(patients), group_size):
        group = patients[i : i + group_size]

        # Progress header
        elapsed = time.time() - start_time
        if stats["processed"] > 0:
            rate = stats["processed"] / elapsed
            remaining = (total_patients - stats["processed"]) / rate
            eta = str(timedelta(seconds=int(remaining)))
        else:
            eta = "calculating..."

        logger.info(
            f"\n{'═'*60}\n"
            f"Progress: {stats['processed']}/{total_patients} | "
            f"Chunks: {stats['total_chunks']} | ETA: {eta}\n"
            f"{'═'*60}"
        )

        # Launch concurrent tasks for this group
        tasks = [process_one(pid) for pid in group]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            stats["processed"] += 1

            if isinstance(result, BaseException):
                stats["failed"] += 1
                stats["errors"].append({"patient_id": "unknown", "error": str(result)})
                logger.error(f"  ✗ Exception: {result}")
                continue

            patient_id, success, chunks, error = result
            if success:
                stats["successful"] += 1
                stats["total_chunks"] += chunks
                if chunks > 0:
                    logger.info(f"  ✓ {patient_id[:8]}...: {chunks} chunks")
                elif not dry_run:
                    logger.info(f"  - {patient_id[:8]}...: 0 chunks (empty bundle)")
            else:
                stats["failed"] += 1
                stats["errors"].append({"patient_id": patient_id, "error": error})
                logger.error(f"  ✗ {patient_id[:8]}...: {error}")

    # ── Final stats ──────────────────────────────────────────────────────
    total_time = time.time() - start_time
    stats["total_time_seconds"] = total_time
    stats["rate_patients_per_second"] = stats["processed"] / total_time if total_time > 0 else 0
    stats["bedrock_api_calls"] = embeddings._call_count
    stats["bedrock_retries"] = embeddings._retry_count

    embeddings.shutdown()

    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Batch embed FHIR patient data using Amazon Bedrock Titan",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only process first N patients",
    )
    parser.add_argument(
        "--batch-size", type=int, default=5,
        help="Concurrent patients (default: 5)",
    )
    parser.add_argument(
        "--embed-batch", type=int, default=25,
        help="Parallel Bedrock calls (default: 25)",
    )
    parser.add_argument(
        "--insert-batch", type=int, default=50,
        help="Documents per DB insert (default: 50)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be done without making changes",
    )
    return parser.parse_args()


async def main():
    args = parse_args()

    print("\n" + "═" * 70)
    print("  FHIR Batch Embedding — Bedrock Titan")
    print("═" * 70)
    print(f"  Started:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Database:      {DB_NAME}@{DB_HOST}:{DB_PORT}")
    print(f"  Bedrock:       {BEDROCK_MODEL_ID} ({AWS_REGION})")
    print(f"  Concurrency:   {args.batch_size} patients, {args.embed_batch} embed workers")
    print(f"  Insert batch:  {args.insert_batch} docs/batch")
    if args.dry_run:
        print("  Mode:          DRY RUN")
    if args.limit:
        print(f"  Limit:         {args.limit} patients")
    print("═" * 70 + "\n")

    try:
        stats = await run_batch(
            batch_size=args.batch_size,
            embed_batch_size=args.embed_batch,
            insert_batch_size=args.insert_batch,
            limit=args.limit,
            dry_run=args.dry_run,
        )
    finally:
        # Clean up DB connections
        engine = get_engine()
        await engine.dispose()

    # Print summary
    print("\n" + "═" * 70)
    print("  EMBEDDING COMPLETE")
    print("═" * 70)

    if stats.get("message"):
        print(f"  {stats['message']}")
    else:
        print(f"  Patients processed: {stats.get('processed', 0)}")
        print(f"  Successful:         {stats.get('successful', 0)}")
        print(f"  Failed:             {stats.get('failed', 0)}")
        print(f"  Total chunks:       {stats.get('total_chunks', 0)}")
        print(f"  Bedrock API calls:  {stats.get('bedrock_api_calls', 0)}")
        if stats.get("bedrock_retries", 0) > 0:
            print(f"  Bedrock retries:    {stats['bedrock_retries']}")
        print(f"  Total time:         {stats.get('total_time_seconds', 0):.1f}s")
        rate = stats.get("rate_patients_per_second", 0)
        print(f"  Rate:               {rate:.2f} patients/sec")
        if rate > 0:
            remaining = stats.get("total_patients", 0) - stats.get("processed", 0)
            if remaining > 0:
                est = timedelta(seconds=int(remaining / rate))
                print(f"  Est. remaining:     {est} for {remaining} more patients")

        if stats.get("errors"):
            print(f"\n  Errors ({len(stats['errors'])} total):")
            for err in stats["errors"][:10]:
                pid = err["patient_id"]
                msg = err["error"][:80]
                print(f"    - {pid[:20]}...: {msg}")

    print("═" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
