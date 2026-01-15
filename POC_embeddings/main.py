# main.py
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
import logging

# Import helper functions from helper.py
from helper import process_and_store
import os
import importlib.util

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class ClinicalNote(BaseModel):
    id: str
    fullUrl: str = Field(default="", alias="fullUrl")
    resourceType: str
    content: str = Field(min_length=1)  # Ensure content is not empty
    patientId: str = Field(default="unknown", alias="patientId")
    resourceJson: str = Field(default="", alias="resourceJson")  # Optional: original JSON for RecursiveJsonSplitter
    sourceFile: str = Field(default="", alias="sourceFile")  # Source file path


@app.post("/ingest")
async def ingest_note(note: ClinicalNote, background_tasks: BackgroundTasks):
    """
    Ingest a clinical note for processing.
    
    Validates the note and queues it for background processing.
    """
    # Validate content is not empty
    if not note.content or len(note.content.strip()) == 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Content cannot be empty for resource {note.id}"
        )
    
    # Offload the heavy embedding/chunking to a background task
    background_tasks.add_task(process_and_store, note)
    logger.info(f"Accepted note: {note.id} ({note.resourceType})")
    return {
        "status": "accepted", 
        "id": note.id,
        "resourceType": note.resourceType,
        "contentLength": len(note.content)
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "FHIR Data Processing API",
        "endpoints": {
            "ingest": "/ingest (POST)",
            "health": "/health (GET)",
            "db_stats": "/db/stats (GET)",
            "db_queue": "/db/queue (GET)",
            "db_errors": "/db/errors (GET)",
            "db_errors_counts": "/db/errors/counts (GET)"
        }
    }


def _load_postgres_module():
    postgres_dir = os.path.join(os.path.dirname(__file__), '..', 'postgres')
    postgres_file = os.path.join(postgres_dir, 'langchain-postgres.py')
    if os.path.exists(postgres_file):
        spec = importlib.util.spec_from_file_location("langchain_postgres", postgres_file)
        langchain_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(langchain_module)
        return langchain_module
    return None


@app.get("/db/stats")
async def db_stats():
    """Return database connection and queue statistics."""
    module = _load_postgres_module()
    if not module:
        return {"error": "postgres/langchain-postgres.py not found"}
    try:
        stats = await module.get_connection_stats()
        return stats
    except Exception as e:
        return {"error": str(e)}


@app.get("/db/queue")
async def db_queue():
    """Return queue stats."""
    module = _load_postgres_module()
    if not module:
        return {"error": "postgres/langchain-postgres.py not found"}
    try:
        stats = await module.get_queue_stats()
        return stats
    except Exception as e:
        return {"error": str(e)}


@app.get("/db/errors")
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
        return {"error": "postgres/langchain-postgres.py not found"}
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


@app.get("/db/errors/counts")
async def get_error_counts():
    """Get error statistics grouped by type and file/resource."""
    module = _load_postgres_module()
    if not module:
        return {"error": "postgres/langchain-postgres.py not found"}
    try:
        counts = await module.get_error_counts()
        return counts
    except Exception as e:
        return {"error": str(e)}