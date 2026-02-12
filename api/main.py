"""Main FastAPI application with all routers."""

from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI

import sys
import requests

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from utils.env_loader import load_env_recursive
from api.shared.middleware import setup_cors, setup_logging

# Load environment variables
load_env_recursive(ROOT_DIR)

# Create FastAPI app
app = FastAPI(
    title="HC AI Unified API",
    description="Unified API for agent, embeddings, retrieval, session, and database services",
    version="1.0.0",
)

# Setup CORS
setup_cors(app)
setup_logging(app)

# Import routers
from api.agent import router as agent_router
from api.embeddings import router as embeddings_router
from api.retrieval import router as retrieval_router
from api.session import router as session_router
from api.database import router as database_router
from api.auth.router import router as auth_router  # NEW

# Mount routers
app.include_router(auth_router, prefix="/auth", tags=["authentication"])  # NEW - mount first for /docs
app.include_router(agent_router, prefix="/agent", tags=["agent"])
app.include_router(embeddings_router, prefix="/embeddings", tags=["embeddings"])
app.include_router(retrieval_router, prefix="/retrieval", tags=["retrieval"])
app.include_router(session_router, prefix="/session", tags=["session"])
app.include_router(database_router, prefix="/db", tags=["database"])


def _startup_diagnostics() -> None:
    ddb_endpoint = os.getenv("DDB_ENDPOINT", "http://localhost:8001")
    ddb_summary = os.getenv("DDB_SUMMARY_TABLE", "")
    reranker_url = os.getenv("RERANKER_SERVICE_URL", "http://localhost:8000/retrieval")

    if "localhost:8000" in ddb_endpoint:
        print(
            "Warning: DDB_ENDPOINT points to port 8000. "
            "DynamoDB Local should run on port 8001."
        )
    if ddb_summary and " " in ddb_summary:
        print(
            f"Warning: DDB_SUMMARY_TABLE contains spaces ({ddb_summary!r}). "
            "DynamoDB table names must not include spaces."
        )
    if reranker_url.startswith("http://localhost:8001"):
        print(
            "Warning: RERANKER_SERVICE_URL points to port 8001. "
            "Unified API reranker is on port 8000 under /retrieval."
        )

    # Best-effort connectivity checks (non-fatal)
    try:
        resp = requests.get("http://localhost:8000/agent/health", timeout=2)
        if resp.status_code >= 500:
            print("Warning: /agent/health returned server error")
    except requests.RequestException:
        print("Warning: /agent/health not reachable")

    try:
        resp = requests.get("http://localhost:8000/retrieval/rerank/health", timeout=2)
        if resp.status_code >= 500:
            print("Warning: /retrieval/rerank/health returned server error")
    except requests.RequestException:
        print("Warning: /retrieval/rerank/health not reachable")

    try:
        requests.get("http://localhost:8001", timeout=2)
    except requests.RequestException:
        print("Warning: DynamoDB Local not reachable on port 8001")


@app.on_event("startup")
async def _on_startup() -> None:
    _startup_diagnostics()


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "HC AI Unified API",
        "version": "1.0.0",
        "endpoints": {
            "auth": "/auth/*",  # NEW
            "agent": "/agent/*",
            "embeddings": "/embeddings/*",
            "retrieval": "/retrieval/*",
            "session": "/session/*",
            "database": "/db/*",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
