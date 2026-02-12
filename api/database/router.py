"""FastAPI router for database monitoring endpoints."""

from __future__ import annotations

import importlib.util
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pathlib import Path

from slowapi import Limiter
from slowapi.util import get_remote_address

from api.auth.dependencies import get_current_user

limiter = Limiter(key_func=get_remote_address)

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
@limiter.limit("30/minute")
async def db_stats(request: Request):
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
@limiter.limit("30/minute")
async def db_queue(request: Request):
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
@limiter.limit("30/minute")
async def get_error_logs(
    request: Request,
    limit: int = 100,
    offset: int = 0,
    file_id: Optional[str] = None,
    resource_id: Optional[str] = None,
    error_type: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
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
@limiter.limit("30/minute")
async def get_error_counts(request: Request, current_user: dict = Depends(get_current_user)):
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
@limiter.limit("30/minute")
async def cloudwatch_metrics(request: Request):
    """Return CloudWatch metrics for ECS, ALB, and RDS."""
    from api.database.cloudwatch import get_cloudwatch_metrics
    try:
        return get_cloudwatch_metrics()
    except Exception as e:
        return {"error": str(e), "metrics": []}


@router.get("/patients")
@limiter.limit("30/minute")
async def list_patients(request: Request):
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
