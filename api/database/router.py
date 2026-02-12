"""FastAPI router for database monitoring endpoints."""

from __future__ import annotations

import importlib.util
from typing import Optional

from fastapi import APIRouter
from pathlib import Path

router = APIRouter()


def _load_postgres_module():
    """Load postgres module dynamically."""
    ROOT_DIR = Path(__file__).resolve().parents[2]
    postgres_file = ROOT_DIR / "api" / "database" / "postgres.py"
    if not postgres_file.exists():
        # Fallback to old location during migration
        postgres_file = ROOT_DIR / "postgres" / "langchain-postgres.py"
        if not postgres_file.exists():
            return None
    
    spec = importlib.util.spec_from_file_location("langchain_postgres", postgres_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@router.get("/stats")
async def db_stats():
    """Return database connection and queue statistics."""
    module = _load_postgres_module()
    if not module:
        return {"error": "Database module not found"}
    try:
        stats = await module.get_connection_stats()
        return stats
    except Exception as e:
        return {"error": str(e)}


@router.get("/queue")
async def db_queue():
    """Return queue stats."""
    module = _load_postgres_module()
    if not module:
        return {"error": "Database module not found"}
    try:
        stats = await module.get_queue_stats()
        return stats
    except Exception as e:
        return {"error": str(e)}


@router.get("/errors")
async def get_error_logs(
    limit: int = 100,
    offset: int = 0,
    file_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    error_type: Optional[str] = None,
):
    """
    Get error logs with optional filtering.
    
    Query parameters:
    - limit: Maximum number of records (default: 100)
    - offset: Pagination offset (default: 0)
    - file_id: Filter by file ID
    - resource_id: Filter by resource ID
    - error_type: Filter by error type (validation, fatal, max_retries, queue_full)
    """
    module = _load_postgres_module()
    if not module:
        return {"error": "Database module not found"}
    try:
        errors = await module.get_error_logs(
            limit=limit,
            offset=offset,
            file_id=file_id,
            resource_id=resource_id,
            error_type=error_type,
        )
        return {
            "errors": errors,
            "limit": limit,
            "offset": offset,
            "count": len(errors)
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/errors/counts")
async def get_error_counts():
    """Get error statistics grouped by type and file/resource."""
    module = _load_postgres_module()
    if not module:
        return {"error": "Database module not found"}
    try:
        counts = await module.get_error_counts()
        return counts
    except Exception as e:
        return {"error": str(e)}


@router.get("/cloudwatch")
async def cloudwatch_metrics():
    """Return CloudWatch metrics for ECS, ALB, and RDS."""
    from api.database.cloudwatch import get_cloudwatch_metrics
    try:
        return get_cloudwatch_metrics()
    except Exception as e:
        return {"error": str(e), "metrics": []}


@router.get("/patients")
async def list_patients():
    """List all unique patients in the vector store with summary info.

    Returns:
        List of patient objects with id, name, chunk_count, and resource_types.
    """
    module = _load_postgres_module()
    if not module:
        return {"error": "Database module not found", "patients": []}
    try:
        patients = await module.list_patients()
        return {"patients": patients, "count": len(patients)}
    except Exception as e:
        return {"error": str(e), "patients": []}
