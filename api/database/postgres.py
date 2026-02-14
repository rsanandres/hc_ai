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

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy import text, event
from langchain_postgres import PGVectorStore, PGEngine
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

# Add parent directory to path to import from api/embeddings/utils/helper.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
try:
    from api.embeddings.utils.helper import get_chunk_embedding
except ImportError:
    # Fallback to old location during migration
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
    get_error_logs,  # noqa: F401 (re-exported for dynamic module access)
    get_error_counts,  # noqa: F401 (re-exported for dynamic module access)
)

# Search for .env file (repo root)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
import sys
sys.path.insert(0, ROOT_DIR)
from utils.env_loader import load_env_recursive
load_env_recursive(ROOT_DIR)

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


def get_engine() -> AsyncEngine:
    """Get or create the shared async engine. Use this instead of creating separate engines."""
    global _engine
    if _engine is None:
        connection_string = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        connect_args = {}
        if POSTGRES_HOST not in ("localhost", "127.0.0.1"):
            import ssl as _ssl
            rds_ca_path = os.path.join(os.path.dirname(__file__), "..", "..", "rds-combined-ca-bundle.pem")
            if os.path.exists(rds_ca_path):
                ssl_ctx = _ssl.create_default_context(cafile=rds_ca_path)
            elif os.path.exists("/app/rds-combined-ca-bundle.pem"):
                ssl_ctx = _ssl.create_default_context(cafile="/app/rds-combined-ca-bundle.pem")
            else:
                # Fallback: verify server cert with system CA store
                ssl_ctx = _ssl.create_default_context()
            connect_args["ssl"] = ssl_ctx
        _engine = create_async_engine(
            connection_string,
            pool_size=MAX_POOL_SIZE,
            max_overflow=MAX_OVERFLOW,
            pool_timeout=POOL_TIMEOUT,
            pool_pre_ping=True,
            echo=False,
            connect_args=connect_args,
        )

        # Set IVFFlat probes on every new connection for optimal index recall.
        # probes = sqrt(lists) where lists = 512 → probes ≈ 23
        @event.listens_for(_engine.sync_engine, "connect")
        def set_ivfflat_probes(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("SET ivfflat.probes = 23")
            cursor.close()

    return _engine


class CustomEmbeddings(Embeddings):
    """
    Custom LangChain embeddings wrapper that uses get_chunk_embedding from api.embeddings.utils.helper.
    This ensures we use the same embedding provider and configuration as process_and_store.
    """
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of documents."""
        embeddings = []
        for txt in texts:
            embedding = get_chunk_embedding(txt)
            if embedding is None:
                raise ValueError(f"Failed to generate embedding for text: {txt[:50]}...")
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
    
    # Create engine if not exists (reuses shared engine)
    if _engine is None:
        _engine = get_engine()
    if _pg_engine is None:
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


async def search_similar_chunks(
    query: str,
    k: int = 5,
    filter_metadata: Optional[Dict[str, Any]] = None
) -> List[Document]:
    """
    Search for similar chunks using semantic similarity with SQL-level filtering.

    Args:
        query: Search query text
        k: Number of results to return
        filter_metadata: Optional metadata filters (filters on JSON metadata column)

    Returns:
        List of similar Document objects
    """
    try:
        # If we have a patient_id filter, use SQL-level filtering for accuracy
        # This ensures we search WITHIN the patient's documents, not across all
        if filter_metadata and filter_metadata.get("patient_id"):
            return await _search_similar_with_sql_filter(query, k, filter_metadata)

        # For non-patient-specific searches, use the standard vector store
        vector_store = await initialize_vector_store()

        if filter_metadata:
            # Other filters - retrieve more and filter in Python
            retrieve_k = max(k * 20, 100)
        else:
            retrieve_k = k

        # Perform similarity search
        results = await vector_store.asimilarity_search(
            query=query,
            k=retrieve_k,
        )

        # Filter results in Python if filter_metadata is provided
        if filter_metadata and results:
            filtered_results = []
            for doc in results:
                doc_metadata = doc.metadata or {}
                matches = True
                for key, value in filter_metadata.items():
                    doc_value = doc_metadata.get(key)
                    if doc_value != value:
                        matches = False
                        break
                if matches:
                    filtered_results.append(doc)
            return filtered_results[:k]

        return results[:k]
    except Exception as e:
        print(f"Error searching chunks: {e}")
        return []


async def _search_similar_with_sql_filter(
    query: str,
    k: int,
    filter_metadata: Dict[str, Any]
) -> List[Document]:
    """
    Perform semantic similarity search with SQL-level metadata filtering.

    This is more accurate than post-filtering because it searches WITHIN
    the filtered set rather than filtering after retrieval.
    """
    global _engine

    if _engine is None:
        await initialize_vector_store()

    if not _engine:
        return []

    # Get the query embedding
    query_embedding = get_chunk_embedding(query)
    if not query_embedding:
        print(f"Warning: Could not get embedding for query: {query[:50]}...")
        return []

    # Convert embedding to PostgreSQL array format
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    # Build SQL query with pgvector similarity and metadata filter
    # Using cosine distance operator <=> for similarity
    # Build WHERE clause with metadata filters
    where_clauses = []
    params: Dict[str, Any] = {"k": k}

    ALLOWED_METADATA_KEYS = {"patient_id", "resource_type", "effective_date", "encounter_id", "status"}
    for key, value in filter_metadata.items():
        if key not in ALLOWED_METADATA_KEYS:
            continue
        param_name = f"meta_{key}"
        where_clauses.append(f"langchain_metadata->>'{key}' = :{param_name}")
        params[param_name] = value

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Use raw SQL with the embedding directly interpolated (safe since we generate it)
    sql = f"""
        SELECT
            langchain_id,
            content,
            langchain_metadata,
            1 - (embedding <=> '{embedding_str}'::vector) as similarity
        FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
        WHERE {where_sql}
        ORDER BY embedding <=> '{embedding_str}'::vector
        LIMIT :k
    """

    try:
        async with _engine.begin() as conn:
            result = await conn.execute(text(sql), params)
            rows = result.fetchall()

        documents = []
        for row in rows:
            doc_id, content, metadata, similarity = row
            # Parse metadata if it's a string
            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            doc = Document(
                page_content=content,
                metadata=metadata or {},
                id=str(doc_id)
            )
            doc.metadata["_similarity_score"] = float(similarity) if similarity else 0.0
            documents.append(doc)

        return documents
    except Exception as e:
        print(f"Error in SQL similarity search: {e}")
        # Fallback to the old method
        return await _search_similar_fallback(query, k, filter_metadata)


async def _search_similar_fallback(
    query: str,
    k: int,
    filter_metadata: Dict[str, Any]
) -> List[Document]:
    """
    Fallback similarity search using vector store with post-filtering.
    Used when SQL-level filtering fails.
    """
    try:
        vector_store = await initialize_vector_store()
        # Retrieve a large pool and filter
        retrieve_k = min(max(k * 100, 1000), 5000)

        results = await vector_store.asimilarity_search(
            query=query,
            k=retrieve_k,
        )

        filtered_results = []
        for doc in results:
            doc_metadata = doc.metadata or {}
            matches = True
            for key, value in filter_metadata.items():
                if doc_metadata.get(key) != value:
                    matches = False
                    break
            if matches:
                filtered_results.append(doc)

        if len(filtered_results) < k:
            print(f"Warning: Fallback search found {len(filtered_results)}/{k} results (patient_id={filter_metadata.get('patient_id', 'N/A')})")

        return filtered_results[:k]
    except Exception as e:
        print(f"Error in fallback similarity search: {e}")
        return []


async def hybrid_search(
    query: str,
    k: int = 10,
    filter_metadata: Optional[Dict[str, Any]] = None,
    bm25_weight: float = 0.5,
    semantic_weight: float = 0.5,
    bm25_k: int = 50,
    semantic_k: int = 50,
) -> List[Document]:
    """
    Hybrid search combining BM25 (keyword) and semantic (vector) search.

    This approach ensures both exact keyword matches (like ICD-10 codes, resourceType)
    and semantically similar content are retrieved.

    Args:
        query: Search query text
        k: Number of final results to return
        filter_metadata: Optional metadata filters (e.g., {"patient_id": "..."})
        bm25_weight: Weight for BM25 scores (default 0.5)
        semantic_weight: Weight for semantic scores (default 0.5)
        bm25_k: Number of BM25 candidates to retrieve
        semantic_k: Number of semantic candidates to retrieve
        
    Returns:
        List of Document objects sorted by combined score
    """
    import asyncio
    from api.database.bm25_search import bm25_search
    
    # Run both searches in parallel
    bm25_task = asyncio.create_task(
        bm25_search(query, k=bm25_k, filter_metadata=filter_metadata)
    )
    semantic_task = asyncio.create_task(
        search_similar_chunks(query, k=semantic_k, filter_metadata=filter_metadata)
    )
    
    bm25_results, semantic_results = await asyncio.gather(bm25_task, semantic_task)
    
    # Create a dict to merge results by document ID
    merged: Dict[str, Dict[str, Any]] = {}
    
    # Process BM25 results
    if bm25_results:
        # Normalize BM25 scores to 0-1 range
        max_bm25 = max(
            (doc.metadata.get("_bm25_score", 0) for doc in bm25_results),
            default=1.0
        )
        max_bm25 = max_bm25 if max_bm25 > 0 else 1.0
        
        for doc in bm25_results:
            doc_id = str(doc.id) if doc.id else doc.page_content[:50]
            bm25_score = doc.metadata.get("_bm25_score", 0) / max_bm25
            merged[doc_id] = {
                "doc": doc,
                "bm25_score": bm25_score,
                "semantic_score": 0.0,
            }
    
    # Process semantic results (they don't have scores by default, so use rank)
    for rank, doc in enumerate(semantic_results):
        doc_id = str(doc.id) if doc.id else doc.page_content[:50]
        # Convert rank to score (higher rank = lower score, normalize to 0-1)
        semantic_score = 1.0 - (rank / max(len(semantic_results), 1))
        
        if doc_id in merged:
            merged[doc_id]["semantic_score"] = semantic_score
        else:
            merged[doc_id] = {
                "doc": doc,
                "bm25_score": 0.0,
                "semantic_score": semantic_score,
            }
    
    # Calculate combined scores and sort
    scored_results = []
    for doc_id, data in merged.items():
        combined_score = (
            bm25_weight * data["bm25_score"] +
            semantic_weight * data["semantic_score"]
        )
        # Add combined score to metadata for debugging
        doc = data["doc"]
        doc.metadata["_hybrid_score"] = combined_score
        doc.metadata["_bm25_component"] = data["bm25_score"]
        doc.metadata["_semantic_component"] = data["semantic_score"]
        scored_results.append((combined_score, doc))
    
    # Sort by combined score descending
    scored_results.sort(key=lambda x: x[0], reverse=True)
    
    return [doc for _, doc in scored_results[:k]]


async def get_patient_timeline(
    patient_id: str,
    k: int = 50,
    resource_types: Optional[List[str]] = None,
) -> List[Document]:
    """
    Get patient timeline by directly querying all chunks for a patient ID.
    
    Unlike vector search, this filters at the database level to ensure
    ALL patient chunks are considered, sorted by effectiveDate.
    
    Args:
        patient_id: UUID of the patient
        k: Maximum number of results to return
        resource_types: Optional filter for specific FHIR resource types
        
    Returns:
        List of Documents sorted by effectiveDate (newest first)
    """
    if _engine is None:
        await initialize_vector_store()
    
    if not _engine:
        return []
    
    # Build query with direct patient filter
    params: Dict[str, Any] = {"patient_id": patient_id, "k": k}
    
    base_sql = f"""
        SELECT 
            langchain_id,
            content,
            langchain_metadata
        FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
        WHERE langchain_metadata->>'patient_id' = :patient_id
    """
    
    # Add resource type filter if specified (parameterized to prevent SQL injection)
    if resource_types:
        base_sql += " AND langchain_metadata->>'resource_type' = ANY(:resource_types)"
        params["resource_types"] = resource_types
    
    # Sort by effectiveDate descending (newest first)
    base_sql += """
        ORDER BY langchain_metadata->>'effective_date' DESC NULLS LAST
        LIMIT :k
    """
    
    try:
        async with _engine.begin() as conn:
            result = await conn.execute(text(base_sql), params)
            rows = result.fetchall()
            
            documents = []
            for row in rows:
                if hasattr(row, '_mapping'):
                    langchain_id = row._mapping['langchain_id']
                    content = row._mapping['content']
                    metadata = row._mapping['langchain_metadata'] or {}
                else:
                    langchain_id, content, metadata = row
                    
                doc = Document(
                    id=str(langchain_id),
                    page_content=content or "",
                    metadata=metadata if isinstance(metadata, dict) else {},
                )
                documents.append(doc)
                
            return documents
            
    except Exception as e:
        print(f"Patient timeline query error: {e}")
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
    with urllib.request.urlopen(request, timeout=120) as response:
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
                        chunk_index=queued_chunk.metadata.get("chunk_index"),
                        error_type="queue_full",
                        error_message=f"Queue full after {queued_chunk.retry_count} retries: {str(e)}",
                        metadata=queued_chunk.metadata,
                        retry_count=queued_chunk.retry_count,
                        source_file=queued_chunk.metadata.get("source_file"),
                    )
            else:
                _queue_stats["failed"] += 1
                await move_chunk_to_dlq(queued_chunk, str(e))
                # Log max retries or fatal error
                error_type = "max_retries" if queued_chunk.retry_count >= MAX_RETRIES else "fatal"
                await log_error(
                    file_id=queued_chunk.metadata.get("source_file"),
                    resource_id=queued_chunk.metadata.get("resource_id"),
                    chunk_id=queued_chunk.chunk_id,
                    chunk_index=queued_chunk.metadata.get("chunk_index"),
                    error_type=error_type,
                    error_message=str(e),
                    metadata=queued_chunk.metadata,
                    retry_count=queued_chunk.retry_count,
                    source_file=queued_chunk.metadata.get("source_file"),
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
            file_id=metadata.get("source_file"),
            resource_id=metadata.get("resource_id"),
            chunk_id=chunk_id,
            chunk_index=metadata.get("chunk_index"),
            error_type="validation",
            error_message=msg,
            metadata=metadata,
            source_file=metadata.get("source_file"),
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
                    file_id=metadata.get("source_file"),
                    resource_id=metadata.get("resource_id"),
                    chunk_id=chunk_id,
                    chunk_index=metadata.get("chunk_index"),
                    error_type="queue_full",
                    error_message=f"Queue full, cannot queue chunk: {str(e)}",
                    metadata=metadata,
                    source_file=metadata.get("source_file"),
                )
                return False
        # Log fatal or non-retryable errors
        await log_error(
            file_id=metadata.get("source_file"),
            resource_id=metadata.get("resource_id"),
            chunk_id=chunk_id,
            chunk_index=metadata.get("chunk_index"),
            error_type="fatal",
            error_message=str(e),
            metadata=metadata,
            source_file=metadata.get("source_file"),
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


async def get_queue_stats() -> Dict[str, Any]:
    queue_sizes = await get_queue_sizes()
    return {
        "memory_queue_size": _queue.qsize() if _queue else 0,
        "persisted_queue_size": queue_sizes.get("queued", 0),
        "dlq_size": queue_sizes.get("dlq", 0),
        "stats": _queue_stats.copy(),
    }


async def list_patients(limit: int = 100) -> List[Dict[str, Any]]:
    """
    List all unique patients in the vector store with summary info.

    Returns a list of patient objects with:
    - id: patient UUID
    - name: extracted from source_file metadata (format: LastName_FirstName_N.json)
    - chunk_count: number of chunks for this patient
    - resource_types: list of FHIR resource types for this patient
    """
    global _engine

    if _engine is None:
        await initialize_vector_store()

    if not _engine:
        return []

    try:
        async with _engine.begin() as conn:
            # Get patient IDs, counts, and source_file for name extraction
            result = await conn.execute(text(f"""
                SELECT
                    langchain_metadata->>'patient_id' as patient_id,
                    COUNT(*) as chunk_count,
                    MIN(langchain_metadata->>'source_file') as source_file
                FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
                WHERE langchain_metadata->>'patient_id' IS NOT NULL
                GROUP BY langchain_metadata->>'patient_id'
                ORDER BY chunk_count DESC
                LIMIT :limit
            """), {"limit": limit})
            patient_rows = result.fetchall()

            if not patient_rows:
                return []

            # Get resource types for these patients (use snake_case field name)
            patient_ids = [row[0] for row in patient_rows]
            result = await conn.execute(text(f"""
                SELECT
                    langchain_metadata->>'patient_id' as patient_id,
                    array_agg(DISTINCT langchain_metadata->>'resource_type') as resource_types
                FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
                WHERE langchain_metadata->>'patient_id' = ANY(:patient_ids)
                GROUP BY langchain_metadata->>'patient_id'
            """), {"patient_ids": patient_ids})
            resource_type_rows = {row[0]: row[1] for row in result.fetchall()}

        patients = []
        for patient_id, chunk_count, source_file in patient_rows:
            resource_types = resource_type_rows.get(patient_id, [])
            # Filter out None from resource_types
            resource_types = [rt for rt in (resource_types or []) if rt]

            # Extract patient name from source_file (format: LastName_FirstName_N.json)
            name = "Unknown Patient"
            if source_file:
                try:
                    # Remove path prefix and .json suffix
                    filename = source_file.split("/")[-1].replace(".json", "")
                    # Split by underscore: LastName_FirstName_Number
                    parts = filename.split("_")
                    if len(parts) >= 2:
                        # Remove numeric suffix from last name (e.g., Adams180 -> Adams)
                        last_name = ''.join(c for c in parts[0] if not c.isdigit())
                        # Remove numeric suffix from first name (e.g., Katelin961 -> Katelin)
                        first_name = ''.join(c for c in parts[1] if not c.isdigit())
                        if first_name and last_name:
                            name = f"{first_name} {last_name}"
                except Exception:
                    pass

            patients.append({
                "id": patient_id,
                "name": name,
                "chunk_count": chunk_count,
                "resource_types": resource_types,
            })

        return patients
    except Exception as e:
        print(f"Error listing patients: {e}")
        import traceback
        traceback.print_exc()
        return []


# For testing/standalone use
async def main():
    """Test function for standalone execution."""
    print_section("PostgreSQL Vector Store Initialization")
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Database: {POSTGRES_DB} @ {POSTGRES_HOST}:{POSTGRES_PORT}")
    print(f"  Schema: {SCHEMA_NAME}")
    print(f"  Table: {TABLE_NAME}")
    
    try:
        await initialize_vector_store()
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
