import os
import json
import sqlite3
from typing import Dict, Any, List, Optional
import asyncio


_DB_PATH = os.getenv("QUEUE_PERSIST_PATH", os.path.join(os.path.dirname(__file__), "queue.db"))


def _connect():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


async def init_queue_storage(db_path: str):
    global _DB_PATH
    _DB_PATH = db_path or _DB_PATH
    def _init():
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS queue (
                chunk_id TEXT PRIMARY KEY,
                chunk_text TEXT NOT NULL,
                metadata TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                first_queued_at REAL DEFAULT (strftime('%s','now')),
                last_error TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dlq (
                chunk_id TEXT PRIMARY KEY,
                chunk_text TEXT NOT NULL,
                metadata TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                first_queued_at REAL,
                last_error TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS error_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id TEXT,
                resource_id TEXT,
                chunk_id TEXT,
                chunk_index INTEGER,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                metadata TEXT,
                retry_count INTEGER DEFAULT 0,
                timestamp REAL DEFAULT (strftime('%s','now')),
                source_file TEXT
            );
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_error_log_file_id ON error_log(file_id);
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_error_log_resource_id ON error_log(resource_id);
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_error_log_timestamp ON error_log(timestamp);
            """
        )
        conn.commit()
        conn.close()
    await asyncio.to_thread(_init)


async def enqueue_chunk_persisted(chunk):
    def _save():
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO queue (chunk_id, chunk_text, metadata, retry_count, first_queued_at, last_error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chunk.chunk_id,
                chunk.chunk_text,
                json.dumps(chunk.metadata),
                chunk.retry_count,
                chunk.first_queued_at,
                None,
            ),
        )
        conn.commit()
        conn.close()
    await asyncio.to_thread(_save)


async def dequeue_chunk_persisted():
    def _deq():
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM queue ORDER BY first_queued_at LIMIT 1")
        row = cur.fetchone()
        if row:
            cur.execute("DELETE FROM queue WHERE chunk_id = ?", (row["chunk_id"],))
            conn.commit()
        conn.close()
        if row:
            return dict(row)
        return None
    return await asyncio.to_thread(_deq)


async def load_all_queued_chunks() -> List[Dict[str, Any]]:
    def _load():
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT * FROM queue ORDER BY first_queued_at")
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
    return await asyncio.to_thread(_load)


async def mark_chunk_processed(chunk_id: str):
    def _mark():
        conn = _connect()
        cur = conn.cursor()
        cur.execute("DELETE FROM queue WHERE chunk_id = ?", (chunk_id,))
        conn.commit()
        conn.close()
    await asyncio.to_thread(_mark)


async def move_chunk_to_dlq(chunk, error: str):
    def _move():
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO dlq (chunk_id, chunk_text, metadata, retry_count, first_queued_at, last_error)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                chunk.chunk_id,
                chunk.chunk_text,
                json.dumps(chunk.metadata),
                chunk.retry_count,
                chunk.first_queued_at,
                error,
            ),
        )
        cur.execute("DELETE FROM queue WHERE chunk_id = ?", (chunk.chunk_id,))
        conn.commit()
        conn.close()
    await asyncio.to_thread(_move)


async def get_queue_sizes() -> Dict[str, int]:
    def _sizes():
        conn = _connect()
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM queue")
        q = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM dlq")
        d = cur.fetchone()[0]
        conn.close()
        return {"queued": q, "dlq": d}
    return await asyncio.to_thread(_sizes)


async def log_error(
    file_id: Optional[str],
    resource_id: Optional[str],
    chunk_id: Optional[str],
    chunk_index: Optional[int],
    error_type: str,
    error_message: str,
    metadata: Optional[Dict[str, Any]] = None,
    retry_count: int = 0,
    source_file: Optional[str] = None,
):
    """
    Log an error to the persistent error log.
    
    Args:
        file_id: Identifier for the source file
        resource_id: FHIR resource ID
        chunk_id: Chunk identifier
        chunk_index: Index of chunk in resource
        error_type: Type of error (validation, fatal, max_retries, etc.)
        error_message: Error message
        metadata: Additional metadata dictionary
        retry_count: Number of retries attempted
        source_file: Path to source file
    """
    def _log():
        conn = _connect()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO error_log 
            (file_id, resource_id, chunk_id, chunk_index, error_type, error_message, metadata, retry_count, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                resource_id,
                chunk_id,
                chunk_index,
                error_type,
                error_message,
                json.dumps(metadata) if metadata else None,
                retry_count,
                source_file,
            ),
        )
        conn.commit()
        conn.close()
    await asyncio.to_thread(_log)


async def get_error_logs(
    limit: int = 100,
    offset: int = 0,
    file_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    error_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve error logs with optional filtering.
    
    Args:
        limit: Maximum number of records to return
        offset: Offset for pagination
        file_id: Filter by file ID
        resource_id: Filter by resource ID
        error_type: Filter by error type
    
    Returns:
        List of error log records
    """
    def _get():
        conn = _connect()
        cur = conn.cursor()
        
        query = "SELECT * FROM error_log WHERE 1=1"
        params = []
        
        if file_id:
            query += " AND file_id = ?"
            params.append(file_id)
        if resource_id:
            query += " AND resource_id = ?"
            params.append(resource_id)
        if error_type:
            query += " AND error_type = ?"
            params.append(error_type)
        
        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        
        # Parse JSON metadata
        for row in rows:
            if row.get("metadata"):
                try:
                    row["metadata"] = json.loads(row["metadata"])
                except (ValueError, TypeError, json.JSONDecodeError):
                    pass
        
        conn.close()
        return rows
    return await asyncio.to_thread(_get)


async def get_error_counts() -> Dict[str, Any]:
    """
    Get error statistics grouped by error type and file/resource.
    
    Returns:
        Dictionary with error counts and breakdowns
    """
    def _counts():
        conn = _connect()
        cur = conn.cursor()
        
        # Total count
        cur.execute("SELECT count(*) FROM error_log")
        total = cur.fetchone()[0]
        
        # Count by error type
        cur.execute(
            "SELECT error_type, count(*) as cnt FROM error_log GROUP BY error_type"
        )
        by_type = {row[0]: row[1] for row in cur.fetchall()}
        
        # Count by file_id
        cur.execute(
            "SELECT file_id, count(*) as cnt FROM error_log WHERE file_id IS NOT NULL GROUP BY file_id ORDER BY cnt DESC LIMIT 10"
        )
        by_file = {row[0]: row[1] for row in cur.fetchall()}
        
        # Count by resource_id
        cur.execute(
            "SELECT resource_id, count(*) as cnt FROM error_log WHERE resource_id IS NOT NULL GROUP BY resource_id ORDER BY cnt DESC LIMIT 10"
        )
        by_resource = {row[0]: row[1] for row in cur.fetchall()}
        
        conn.close()
        return {
            "total": total,
            "by_type": by_type,
            "top_files": by_file,
            "top_resources": by_resource,
        }
    return await asyncio.to_thread(_counts)


async def clear_error_logs(older_than_days: Optional[int] = None):
    """
    Clear error logs, optionally only those older than specified days.
    
    Args:
        older_than_days: If specified, only delete logs older than this many days
    """
    def _clear():
        conn = _connect()
        cur = conn.cursor()
        if older_than_days:
            cur.execute(
                "DELETE FROM error_log WHERE timestamp < strftime('%s','now') - ?",
                (older_than_days * 86400,),
            )
        else:
            cur.execute("DELETE FROM error_log")
        conn.commit()
        conn.close()
    await asyncio.to_thread(_clear)
