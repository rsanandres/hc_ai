"""FastAPI router for embeddings endpoints."""

from __future__ import annotations

import logging
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from api.embeddings.models import ClinicalNote
from api.embeddings.utils.helper import process_and_store
from api.auth.dependencies import get_current_user

router = APIRouter()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@router.post("/ingest")
async def ingest_note(note: ClinicalNote, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
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


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "FHIR Data Processing API - Embeddings Service",
        "endpoints": {
            "ingest": "/embeddings/ingest (POST)",
            "health": "/embeddings/health (GET)",
        },
    }
