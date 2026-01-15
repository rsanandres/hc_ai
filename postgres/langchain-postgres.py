import os
import sys
import uuid
import asyncio
import json
import urllib.request
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import text
from langchain_postgres import PGVectorStore, PGEngine
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

# Add parent directory to path to import from POC_embeddings/helper.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from POC_embeddings.helper import get_chunk_embedding

# Queue persistence helper
from postgres.queue_storage import (
    init_queue_storage,
    enqueue_chunk_persisted,
    mark_chunk_processed,
    move_chunk_to_dlq,
    get_queue_sizes,
    load_all_queued_chunks,
    log_error,
    get_error_logs,
    get_error_counts,
    clear_error_logs,
)

# Search for .env file (repo root)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(dotenv_path=os.path.join(ROOT_DIR, ".env"))

POSTGRES_USER = os.environ.get("DB_USER")
POSTGRES_PASSWORD = os.environ.get("DB_PASSWORD")
POSTGRES_HOST = os.environ.get("DB_HOST", "localhost")
POSTGRES_PORT = os.environ.get("DB_PORT", "5432")
POSTGRES_DB = os.environ.get("DB_NAME")

RERANKER_SERVICE_URL = os.environ.get("RERANKER_SERVICE_URL", "http://localhost:8001")

TABLE_NAME = "hc_ai_table"
# mxbai-embed-large:latest produces 1024-dimensional embeddings
VECTOR_SIZE = 1024
SCHEMA_NAME = "hc_ai_schema"

# Connection pool / queue configuration
MAX_POOL_SIZE = int(os.getenv("DB_MAX_POOL_SIZE", "10"))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "5"))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))

QUEUE_MAX_SIZE = int(os.getenv("CHUNK_QUEUE_MAX_SIZE", "1000"))
MAX_RETRIES = int(os.getenv("CHUNK_MAX_RETRIES", "5"))
BATCH_SIZE = int(os.getenv("CHUNK_BATCH_SIZE", "20"))
RETRY_BASE_DELAY = float(os.getenv("CHUNK_RETRY_BASE_DELAY", "1.0"))
RETRY_MAX_DELAY = float(os.getenv("CHUNK_RETRY_MAX_DELAY", "60.0"))
QUEUE_PERSIST_PATH = os.getenv("QUEUE_PERSIST_PATH", os.path.join(os.path.dirname(__file__), "queue.db"))

# Error classification keywords
RETRYABLE_KEYWORDS = [
    "too many clients",
    "connection",
    "timeout",
    "deadlock",
    "lock timeout",
    "connection refused",
]

# Global variables for connection pooling
_engine: Optional[AsyncEngine] = None
_pg_engine: Optional[PGEngine] = None
_vector_store: Optional[PGVectorStore] = None
_queue: Optional[asyncio.Queue] = None
_queue_worker_task: Optional[asyncio.Task] = None
_queue_stats = {
    "queued": 0,
    "processed": 0,
    "failed": 0,
    "retries": 0,
}


class CustomEmbeddings(Embeddings):
    """
    Custom LangChain embeddings wrapper that uses get_chunk_embedding from POC_embeddings/main.py.
    This ensures we use the same embedding provider and configuration as process_and_store.
    """
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        embeddings = []
        for text in texts:
            embedding = get_chunk_embedding(text)
            if embedding is None:
                raise ValueError(f"Failed to generate embedding for text: {text[:50]}...")
            embeddings.append(embedding)
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """Embed a single query."""
        embedding = get_chunk_embedding(text)
        if embedding is None:
            raise ValueError(f"Failed to generate embedding for query: {text[:50]}...")
        return embedding


@dataclass
class QueuedChunk:
    chunk_text: str
    chunk_id: str
    metadata: Dict[str, Any]
    retry_count: int = 0
    first_queued_at: float = 0.0

    def __post_init__(self):
        if self.first_queued_at == 0.0:
            self.first_queued_at = time.time()


# ---------------------- Validation & Error Classification ----------------------


def validate_chunk(chunk_text: str, chunk_id: str, metadata: Dict[str, Any]) -> Tuple[bool, str]:
    if not chunk_text or not chunk_text.strip():
        return False, "Empty chunk text"
    try:
        uuid.UUID(chunk_id)
    except Exception:
        return False, "Invalid chunk_id (must be UUID)"
    if not isinstance(metadata, dict):
        return False, "Metadata must be a dict"
    # Basic size guard
    if len(chunk_text) > 20000:  # safeguard to avoid oversized writes
        return False, "Chunk text too large"
    return True, ""


def classify_error(exc: Exception) -> str:
    msg = str(exc).lower()
    for kw in RETRYABLE_KEYWORDS:
        if kw in msg:
            return "retryable"
    if "duplicate key" in msg or "unique constraint" in msg or "conflict" in msg:
        return "duplicate"
    return "fatal"


async def verify_table_exists(engine: AsyncEngine, schema_name: str, table_name: str) -> bool:
    """Check if table exists in the database"""
    async with engine.begin() as conn:
        res = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE  table_schema = :schema_name
                    AND    table_name   = :table_name
                )
            """),
            {"schema_name": schema_name, "table_name": table_name}
        )
        return res.scalar_one()


async def get_table_info(engine: AsyncEngine, schema_name: str, table_name: str):
    """Get table structure information"""
    async with engine.begin() as conn:
        res = await conn.execute(
            text("""
                SELECT 
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable
                FROM information_schema.columns
                WHERE table_schema = :schema_name
                AND table_name = :table_name
                ORDER BY ordinal_position
            """),
            {"schema_name": schema_name, "table_name": table_name}
        )
        return res.fetchall()


# ---------------------- Connection & Queue Monitoring ----------------------


async def get_connection_stats() -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "active_connections": 0,
        "max_connections": 0,
        "pool_size": MAX_POOL_SIZE,
        "pool_overflow": MAX_OVERFLOW,
        "pool_checked_out": 0,
        "pool_checked_in": 0,
        "queue_size": _queue.qsize() if _queue else 0,
        "queue_stats": _queue_stats.copy(),
    }
    if _engine is None:
        return stats
    try:
        async with _engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    SELECT 
                        count(*) as active_connections,
                        (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_connections
                    FROM pg_stat_activity 
                    WHERE datname = current_database()
                    AND state = 'active'
                    """
                )
            )
            row = result.fetchone()
            if row:
                stats["active_connections"] = row[0]
                stats["max_connections"] = row[1]
        if hasattr(_engine, "pool"):
            pool = _engine.pool
            stats["pool_checked_out"] = pool.checkedout()
            stats["pool_checked_in"] = pool.checkedin()
            stats["pool_overflow"] = pool.overflow()
            stats["pool_size"] = pool.size()
    except Exception as e:
        print(f"Error getting connection stats: {e}")
    return stats


async def print_connection_stats():
    stats = await get_connection_stats()
    print("\n" + "=" * 70)
    print("  DATABASE CONNECTION STATISTICS")
    print("=" * 70)
    print(f"  Active Connections: {stats['active_connections']} / {stats['max_connections']}")
    print(f"  Pool Size:          {stats['pool_size']} (max_overflow: {MAX_OVERFLOW})")
    print(f"  Pool Checked Out:   {stats['pool_checked_out']}")
    print(f"  Pool Checked In:    {stats['pool_checked_in']}")
    print(f"  Queue Size:         {stats['queue_size']}")
    print(f"  Queue Stats:        {_queue_stats}")
    print("=" * 70 + "\n")


async def initialize_vector_store() -> PGVectorStore:
    """
    Initialize and return the PostgreSQL vector store.
    Creates schema and table if they don't exist.
    Uses connection pooling for efficiency.
    """
    global _engine, _pg_engine, _vector_store
    
    # Reuse existing connection if available
    if _vector_store is not None:
        return _vector_store
    
    # Validate required environment variables
    required_vars = {
        "DB_USER": POSTGRES_USER,
        "DB_PASSWORD": POSTGRES_PASSWORD,
        "DB_NAME": POSTGRES_DB,
    }
    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Create engine if not exists
    if _engine is None:
        connection_string = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        _engine = create_async_engine(
            connection_string,
            pool_size=MAX_POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_timeout=POOL_TIMEOUT,
            pool_pre_ping=True,
            echo=False,
        )
        _pg_engine = PGEngine.from_engine(engine=_engine)
    
    # Create schema if it doesn't exist
    async with _engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA_NAME}"'))
    
    # Create table if it doesn't exist
    already_exists = await verify_table_exists(_engine, SCHEMA_NAME, TABLE_NAME)
    if not already_exists:
        await _pg_engine.ainit_vectorstore_table(
            table_name=TABLE_NAME,
            vector_size=VECTOR_SIZE,
            schema_name=SCHEMA_NAME,
        )
    
    # Verify table exists
    table_exists = await verify_table_exists(_engine, SCHEMA_NAME, TABLE_NAME)
    if not table_exists:
        raise Exception("Table was not created successfully!")
    
    # Create embeddings instance
    embedding = CustomEmbeddings()
    
    # Create vector store
    _vector_store = await PGVectorStore.create(
        engine=_pg_engine,
        table_name=TABLE_NAME,
        schema_name=SCHEMA_NAME,
        embedding_service=embedding,
    )

    # Initialize queue persistence & worker
    await init_queue_storage(QUEUE_PERSIST_PATH)
    await start_queue_worker()
    
    return _vector_store


async def store_chunk(
    chunk_text: str,
    chunk_id: str,
    metadata: Dict[str, Any]
) -> bool:
    """
    Store a single chunk in the PostgreSQL vector store.
    
    Args:
        chunk_text: The text content of the chunk
        chunk_id: Unique identifier for the chunk
        metadata: Dictionary of metadata to store with the chunk
    
    Returns:
        True if successful, False otherwise
    """
    try:
        vector_store = await initialize_vector_store()
        
        # Create a Document with the chunk
        doc = Document(
            id=chunk_id,
            page_content=chunk_text,
            metadata=metadata
        )
        
        # Add document to vector store
        await vector_store.aadd_documents([doc])
        
        return True
    except Exception as e:
        print(f"Error storing chunk {chunk_id}: {e}")
        return False


async def store_chunks_batch(
    chunks: List[Dict[str, Any]]
) -> int:
    """
    Store multiple chunks in a batch operation.
    
    Args:
        chunks: List of dictionaries, each containing:
            - 'text': chunk text content
            - 'id': chunk ID
            - 'metadata': metadata dictionary
    
    Returns:
        Number of successfully stored chunks
    """
    try:
        vector_store = await initialize_vector_store()
        
        documents = []
        for chunk in chunks:
            doc = Document(
                id=chunk['id'],
                page_content=chunk['text'],
                metadata=chunk.get('metadata', {})
            )
            documents.append(doc)
        
        if documents:
            await vector_store.aadd_documents(documents)
        
        return len(documents)
    except Exception as e:
        print(f"Error storing chunks batch: {e}")
        return 0


async def search_similar_chunks(
    query: str,
    k: int = 5,
    filter_metadata: Optional[Dict[str, Any]] = None
) -> List[Document]:
    """
    Search for similar chunks using semantic similarity.
    
    Args:
        query: Search query text
        k: Number of results to return
        filter_metadata: Optional metadata filters
    
    Returns:
        List of similar Document objects
    """
    try:
        vector_store = await initialize_vector_store()
        
        # Perform similarity search
        results = await vector_store.asimilarity_search(
            query=query,
            k=k,
            filter=filter_metadata
        )
        
        return results
    except Exception as e:
        print(f"Error searching chunks: {e}")
        return []


async def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Post JSON to the reranker service using standard library."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return await asyncio.to_thread(_send_request, request)


def _send_request(request: urllib.request.Request) -> Dict[str, Any]:
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw)


async def retrieve_and_rerank(
    query: str,
    k_retrieve: int = 50,
    k_return: int = 10,
    filter_metadata: Optional[Dict[str, Any]] = None,
) -> List[Document]:
    """
    Retrieve and rerank documents by calling the local reranker service.
    """
    payload = {
        "query": query,
        "k_retrieve": k_retrieve,
        "k_return": k_return,
        "filter_metadata": filter_metadata,
    }
    result = await _post_json(f"{RERANKER_SERVICE_URL}/rerank", payload)
    docs: List[Document] = []
    for item in result.get("results", []):
        docs.append(
            Document(
                id=item.get("id"),
                page_content=item.get("content", ""),
                metadata=item.get("metadata", {}) or {},
            )
        )
    return docs


async def close_connections():
    """Close database connections and cleanup."""
    global _engine, _vector_store
    if _engine:
        await _engine.dispose()
        _engine = None
        _vector_store = None


# ---------------------- Queue Worker & Storage ----------------------


async def start_queue_worker():
    """Start the background queue worker and load persisted items."""
    global _queue, _queue_worker_task
    if _queue is None:
        _queue = asyncio.Queue(maxsize=QUEUE_MAX_SIZE)
    # Load persisted queued items
    queued = await load_all_queued_chunks()
    for qc in queued:
        try:
            meta = qc.get("metadata")
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            await _queue.put(
                QueuedChunk(
                    chunk_text=qc.get("chunk_text", ""),
                    chunk_id=qc.get("chunk_id", str(uuid.uuid4())),
                    metadata=meta or {},
                    retry_count=qc.get("retry_count", 0),
                    first_queued_at=qc.get("first_queued_at", 0.0),
                )
            )
        except asyncio.QueueFull:
            break
    if _queue_worker_task is None or _queue_worker_task.done():
        _queue_worker_task = asyncio.create_task(queue_worker())


async def queue_worker():
    """Background worker that retries queued chunks with exponential backoff."""
    while True:
        try:
            queued_chunk: QueuedChunk = await _queue.get()
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(0.5)
            continue

        delay = min(RETRY_BASE_DELAY * (2 ** queued_chunk.retry_count), RETRY_MAX_DELAY)
        if queued_chunk.retry_count > 0:
            await asyncio.sleep(delay)

        try:
            success = await store_chunk_direct(
                chunk_text=queued_chunk.chunk_text,
                chunk_id=queued_chunk.chunk_id,
                metadata=queued_chunk.metadata,
            )
            if success:
                _queue_stats["processed"] += 1
                await mark_chunk_processed(queued_chunk.chunk_id)
            else:
                raise Exception("Unknown failure during store_chunk_direct")
        except Exception as e:
            classification = classify_error(e)
            if classification == "retryable" and queued_chunk.retry_count < MAX_RETRIES:
                queued_chunk.retry_count += 1
                _queue_stats["retries"] += 1
                try:
                    await enqueue_chunk_persisted(queued_chunk)
                    await _queue.put(queued_chunk)
                except asyncio.QueueFull:
                    _queue_stats["failed"] += 1
                    # Log queue full error
                    await log_error(
                        file_id=queued_chunk.metadata.get("sourceFile"),
                        resource_id=queued_chunk.metadata.get("resourceId"),
                        chunk_id=queued_chunk.chunk_id,
                        chunk_index=queued_chunk.metadata.get("chunkIndex"),
                        error_type="queue_full",
                        error_message=f"Queue full after {queued_chunk.retry_count} retries: {str(e)}",
                        metadata=queued_chunk.metadata,
                        retry_count=queued_chunk.retry_count,
                        source_file=queued_chunk.metadata.get("sourceFile"),
                    )
            else:
                _queue_stats["failed"] += 1
                await move_chunk_to_dlq(queued_chunk, str(e))
                # Log max retries or fatal error
                error_type = "max_retries" if queued_chunk.retry_count >= MAX_RETRIES else "fatal"
                await log_error(
                    file_id=queued_chunk.metadata.get("sourceFile"),
                    resource_id=queued_chunk.metadata.get("resourceId"),
                    chunk_id=queued_chunk.chunk_id,
                    chunk_index=queued_chunk.metadata.get("chunkIndex"),
                    error_type=error_type,
                    error_message=str(e),
                    metadata=queued_chunk.metadata,
                    retry_count=queued_chunk.retry_count,
                    source_file=queued_chunk.metadata.get("sourceFile"),
                )
        finally:
            _queue.task_done()


# ---------------------- Storage Helpers ----------------------


async def store_chunk_direct(
    chunk_text: str,
    chunk_id: str,
    metadata: Dict[str, Any],
) -> bool:
    """Store a single chunk directly (no queue)."""
    is_valid, msg = validate_chunk(chunk_text, chunk_id, metadata)
    if not is_valid:
        # Log validation error
        await log_error(
            file_id=metadata.get("sourceFile"),
            resource_id=metadata.get("resourceId"),
            chunk_id=chunk_id,
            chunk_index=metadata.get("chunkIndex"),
            error_type="validation",
            error_message=msg,
            metadata=metadata,
            source_file=metadata.get("sourceFile"),
        )
        raise ValueError(msg)

    vector_store = await initialize_vector_store()

    doc = Document(
        id=chunk_id,
        page_content=chunk_text,
        metadata=metadata,
    )

    await vector_store.aadd_documents([doc])
    return True


async def store_chunk(
    chunk_text: str,
    chunk_id: str,
    metadata: Dict[str, Any],
    use_queue: bool = True,
) -> bool:
    """
    Store a single chunk with optional queueing on retryable errors.
    """
    try:
        return await store_chunk_direct(chunk_text, chunk_id, metadata)
    except Exception as e:
        classification = classify_error(e)
        if classification == "duplicate":
            # Treat duplicates as success
            return True
        if use_queue and classification == "retryable":
            try:
                q_item = QueuedChunk(chunk_text=chunk_text, chunk_id=chunk_id, metadata=metadata)
                await enqueue_chunk_persisted(q_item)
                await start_queue_worker()
                await _queue.put(q_item)
                _queue_stats["queued"] += 1
                return False  # queued for later
            except asyncio.QueueFull:
                _queue_stats["failed"] += 1
                # Log queue full error
                await log_error(
                    file_id=metadata.get("sourceFile"),
                    resource_id=metadata.get("resourceId"),
                    chunk_id=chunk_id,
                    chunk_index=metadata.get("chunkIndex"),
                    error_type="queue_full",
                    error_message=f"Queue full, cannot queue chunk: {str(e)}",
                    metadata=metadata,
                    source_file=metadata.get("sourceFile"),
                )
                return False
        # Log fatal or non-retryable errors
        await log_error(
            file_id=metadata.get("sourceFile"),
            resource_id=metadata.get("resourceId"),
            chunk_id=chunk_id,
            chunk_index=metadata.get("chunkIndex"),
            error_type="fatal",
            error_message=str(e),
            metadata=metadata,
            source_file=metadata.get("sourceFile"),
        )
        raise


async def store_chunks_batch(chunks: List[Dict[str, Any]]) -> int:
    """
    Store multiple chunks; fall back to individual queueing on failure.
    """
    stored = 0
    for chunk in chunks:
        chunk_text = chunk.get("text")
        chunk_id = chunk.get("id") or str(uuid.uuid4())
        metadata = chunk.get("metadata", {})
        try:
            success = await store_chunk(chunk_text, chunk_id, metadata, use_queue=True)
            if success:
                stored += 1
        except Exception:
            # best effort: queue handled in store_chunk
            continue
    return stored


# ---------------------- Monitoring APIs ----------------------


async def get_error_logs(
    limit: int = 100,
    offset: int = 0,
    file_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    error_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get error logs with optional filtering.
    
    Args:
        limit: Maximum number of records to return
        offset: Offset for pagination
        file_id: Filter by file ID
        resource_id: Filter by resource ID
        error_type: Filter by error type
    
    Returns:
        List of error log records
    """
    from postgres.queue_storage import get_error_logs as _get_error_logs
    return await _get_error_logs(limit, offset, file_id, resource_id, error_type)


async def get_error_counts() -> Dict[str, Any]:
    """
    Get error statistics grouped by error type and file/resource.
    
    Returns:
        Dictionary with error counts and breakdowns
    """
    from postgres.queue_storage import get_error_counts as _get_error_counts
    return await _get_error_counts()


async def get_queue_stats() -> Dict[str, Any]:
    queue_sizes = await get_queue_sizes()
    return {
        "memory_queue_size": _queue.qsize() if _queue else 0,
        "persisted_queue_size": queue_sizes.get("queued", 0),
        "dlq_size": queue_sizes.get("dlq", 0),
        "stats": _queue_stats.copy(),
    }


# For testing/standalone use
async def main():
    """Test function for standalone execution."""
    print_section("PostgreSQL Vector Store Initialization")
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Database: {POSTGRES_DB} @ {POSTGRES_HOST}:{POSTGRES_PORT}")
    print(f"  Schema: {SCHEMA_NAME}")
    print(f"  Table: {TABLE_NAME}")
    
    try:
        vector_store = await initialize_vector_store()
        print("✓ Vector store initialized successfully")
        
        # Test: Store a sample chunk
        test_chunk_id = str(uuid.uuid4())
        test_metadata = {
            "test": True,
            "timestamp": datetime.now().isoformat()
        }
        
        success = await store_chunk(
            chunk_text="This is a test chunk",
            chunk_id=test_chunk_id,
            metadata=test_metadata
        )
        
        if success:
            print("✓ Test chunk stored successfully")
        else:
            print("✗ Failed to store test chunk")
        
        # Test: Search
        results = await search_similar_chunks("test chunk", k=1)
        print(f"✓ Search test returned {len(results)} results")
        
    except Exception as e:
        print(f"✗ Error: {e}")
    finally:
        await close_connections()
    
    print(f"  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
