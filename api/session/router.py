"""FastAPI router for session management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

import os

from api.session.models import (
    SessionSummaryUpdate,
    SessionTurnRequest,
    SessionTurnResponse,
    SessionCreateRequest,
    SessionUpdateRequest,
    SessionMetadata,
    SessionListResponse,
    SessionCountResponse,
)

router = APIRouter()

SESSION_RECENT_LIMIT = int(os.getenv("SESSION_RECENT_LIMIT", "10"))
MAX_SESSIONS_PER_USER = int(os.getenv("MAX_SESSIONS_PER_USER", "20"))

def _sessions_enabled() -> bool:
    return os.getenv("ENABLE_SESSION_HISTORY", "true").lower() == "true"


def _get_session_store():
    from api.session.store_dynamodb import get_session_store
    return get_session_store()


@router.post("/turn", response_model=SessionTurnResponse)
def append_session_turn(payload: SessionTurnRequest) -> SessionTurnResponse:
    if not _sessions_enabled():
        return SessionTurnResponse(session_id=payload.session_id, recent_turns=[], summary={})

    store = _get_session_store()
    store.append_turn(
        session_id=payload.session_id,
        role=payload.role,
        text=payload.text,
        meta=payload.meta,
        patient_id=payload.patient_id,
    )
    
    # Auto-name session if it's the first user message
    summary = store.get_summary(payload.session_id)
    if payload.role == "user" and (not summary.get("name") or summary.get("name") == "New Session"):
        # Simple naming: First 50 chars of message
        new_name = payload.text[:50] + "..." if len(payload.text) > 50 else payload.text
        store.update_summary(session_id=payload.session_id, summary={"name": new_name})
        
    recent = store.get_recent(payload.session_id, limit=payload.return_limit or SESSION_RECENT_LIMIT)
    summary = store.get_summary(payload.session_id) # Refresh summary with new name
    return SessionTurnResponse(session_id=payload.session_id, recent_turns=recent, summary=summary)





@router.post("/summary")
def update_session_summary(payload: SessionSummaryUpdate) -> Dict[str, Any]:
    store = _get_session_store()
    store.update_summary(session_id=payload.session_id, summary=payload.summary, patient_id=payload.patient_id)
    summary = store.get_summary(payload.session_id)
    return {"session_id": payload.session_id, "summary": summary}


@router.delete("/{session_id}")
def clear_session(session_id: str) -> Dict[str, str]:
    store = _get_session_store()
    store.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}


@router.get("/list", response_model=SessionListResponse)
def list_sessions(user_id: str) -> SessionListResponse:
    """List all sessions for a user."""
    if not _sessions_enabled():
        return SessionListResponse(sessions=[], count=0)

    store = _get_session_store()
    sessions_data = store.list_sessions_by_user(user_id)
    
    sessions: List[SessionMetadata] = []
    for item in sessions_data:
        session_id = item.get("session_id", "")
        first_preview = store.get_first_message_preview(session_id)
        
        # Count messages
        recent = store.get_recent(session_id, limit=1000)  # Get all to count
        message_count = len([t for t in recent if t.get("role") == "user"])
        
        sessions.append(
            SessionMetadata(
                session_id=session_id,
                user_id=item.get("user_id", user_id),
                name=item.get("name"),
                description=item.get("description"),
                tags=item.get("tags", []),
                created_at=item.get("created_at", item.get("updated_at", datetime.utcnow().isoformat() + "Z")),
                last_activity=item.get("last_activity", item.get("updated_at", datetime.utcnow().isoformat() + "Z")),
                message_count=message_count,
                first_message_preview=first_preview,
            )
        )
    
    return SessionListResponse(sessions=sessions, count=len(sessions))


@router.get("/count", response_model=SessionCountResponse)
def get_session_count(user_id: str) -> SessionCountResponse:
    """Get session count for a user."""
    if not _sessions_enabled():
        return SessionCountResponse(user_id=user_id, count=0, max_allowed=MAX_SESSIONS_PER_USER)

    store = _get_session_store()
    count = store.get_session_count(user_id)
    MAX_SESSIONS = int(os.getenv("MAX_SESSIONS_PER_USER", "50"))
    return SessionCountResponse(user_id=user_id, count=count, max_allowed=MAX_SESSIONS)


@router.post("/create", response_model=SessionMetadata)
def create_session(payload: SessionCreateRequest) -> SessionMetadata:
    """Create a new session."""
    if not _sessions_enabled():
        now = datetime.utcnow().isoformat() + "Z"
        return SessionMetadata(
            session_id=str(uuid.uuid4()),
            user_id=payload.user_id,
            name=payload.name,
            tags=payload.tags or [],
            created_at=now,
            last_activity=now,
            message_count=0,
        )

    store = _get_session_store()
    user_id = payload.user_id  # Use user_id from payload

    # Check session limit
    count = store.get_session_count(user_id)
    MAX_SESSIONS = int(os.getenv("MAX_SESSIONS_PER_USER", "50"))
    if count >= MAX_SESSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Session limit reached",
                "code": "SESSION_LIMIT_EXCEEDED",
                "max_sessions": MAX_SESSIONS,
            }
        )
    
    # Generate new session_id
    session_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat() + "Z"
    
    # Create summary with metadata
    summary: Dict[str, Any] = {
        "name": payload.name,
        "description": payload.description,
        "tags": payload.tags or [],
        "created_at": now,
        "last_activity": now,
    }
    
    store.update_summary(
        session_id=session_id,
        summary=summary,
        user_id=payload.user_id,
    )
    
    return SessionMetadata(
        session_id=session_id,
        user_id=payload.user_id,
        name=payload.name,
        description=payload.description,
        tags=payload.tags or [],
        created_at=now,
        last_activity=now,
        message_count=0,
        first_message_preview=None,
    )


@router.get("/{session_id}/metadata", response_model=SessionMetadata)
def get_session_metadata(session_id: str) -> SessionMetadata:
    """Get session metadata."""
    store = _get_session_store()
    summary = store.get_summary(session_id)
    
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")
    
    first_preview = store.get_first_message_preview(session_id)
    recent = store.get_recent(session_id, limit=1000)
    message_count = len([t for t in recent if t.get("role") == "user"])
    
    return SessionMetadata(
        session_id=session_id,
        user_id=summary.get("user_id", ""),
        name=summary.get("name"),
        description=summary.get("description"),
        tags=summary.get("tags", []),
        created_at=summary.get("created_at", summary.get("updated_at", datetime.utcnow().isoformat() + "Z")),
        last_activity=summary.get("last_activity", summary.get("updated_at", datetime.utcnow().isoformat() + "Z")),
        message_count=message_count,
        first_message_preview=first_preview,
    )


@router.put("/{session_id}/metadata", response_model=SessionMetadata)
def update_session_metadata(session_id: str, payload: SessionUpdateRequest) -> SessionMetadata:
    """Update session metadata."""
    store = _get_session_store()
    summary = store.get_summary(session_id)
    
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Update only provided fields
    updated_summary = summary.copy()
    if payload.name is not None:
        updated_summary["name"] = payload.name
    if payload.description is not None:
        updated_summary["description"] = payload.description
    if payload.tags is not None:
        updated_summary["tags"] = payload.tags
    
    updated_summary["last_activity"] = datetime.utcnow().isoformat() + "Z"
    
    # Remove keys that shouldn't be updated or are primary keys
    # Also remove user_id/patient_id as they are passed explicitly to update_summary
    # Remove updated_at/ttl as they are handled automatically by update_summary and cause overlapping path errors
    for key in ["session_id", "sk", "user_id", "patient_id", "created_at", "updated_at", "ttl"]:
        updated_summary.pop(key, None)
    
    store.update_summary(
        session_id=session_id,
        summary=updated_summary,
        user_id=summary.get("user_id"),
        patient_id=summary.get("patient_id"),
    )
    
    # Return updated metadata
    return get_session_metadata(session_id)


@router.get("/{session_id}", response_model=SessionTurnResponse)
def get_session_state(
    session_id: str,
    limit: int = SESSION_RECENT_LIMIT,
) -> SessionTurnResponse:
    """Get session messages."""
    if not _sessions_enabled():
        return SessionTurnResponse(session_id=session_id, recent_turns=[], summary={})

    store = _get_session_store()

    recent = store.get_recent(session_id, limit=limit)
    summary = store.get_summary(session_id)
    return SessionTurnResponse(session_id=session_id, recent_turns=recent, summary=summary)
