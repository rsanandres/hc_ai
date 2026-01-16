"""FastAPI service for retrieval + cross-encoder reranking."""

from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import os
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.documents import Document

from .cache import InMemoryCache, build_cache_key
from .cross_encoder import Reranker
from .models import (
    BatchRerankRequest,
    BatchRerankResponse,
    DocumentResponse,
    RerankRequest,
    RerankResponse,
    SessionSummaryUpdate,
    SessionTurnRequest,
    SessionTurnResponse,
    StatsResponse,
)
from session.store_dynamodb import SessionStore


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

RERANKER_MODEL = os.getenv("RERANKER_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
RERANKER_DEVICE = os.getenv("RERANKER_DEVICE", "auto")
DEFAULT_K_RETRIEVE = int(os.getenv("RERANKER_K_RETRIEVE", "50"))
DEFAULT_K_RETURN = int(os.getenv("RERANKER_K_RETURN", "10"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "10000"))
SESSION_RECENT_LIMIT = int(os.getenv("SESSION_RECENT_LIMIT", "10"))

DDB_REGION = os.getenv("AWS_REGION", "us-east-1")
DDB_TURNS_TABLE = os.getenv("DDB_TURNS_TABLE", "hcai_session_turns")
DDB_SUMMARY_TABLE = os.getenv("DDB_SUMMARY_TABLE", "hcai_session_summary")
DDB_ENDPOINT = os.getenv("DDB_ENDPOINT")
DDB_TTL_DAYS = os.getenv("DDB_TTL_DAYS")
DDB_AUTO_CREATE = os.getenv("DDB_AUTO_CREATE", "false").lower() in {"1", "true", "yes"}


app = FastAPI()

_reranker: Optional[Reranker] = None
_cache: Optional[InMemoryCache] = None
_session_store: Optional[SessionStore] = None


def _get_reranker() -> Reranker:
    global _reranker
    if _reranker is None:
        _reranker = Reranker(model_name=RERANKER_MODEL, device=RERANKER_DEVICE)
    return _reranker


def _get_cache() -> InMemoryCache:
    global _cache
    if _cache is None:
        _cache = InMemoryCache(ttl_seconds=CACHE_TTL, max_size=CACHE_MAX_SIZE)
    return _cache


def _get_session_store() -> SessionStore:
    global _session_store
    if _session_store is None:
        ttl_days_int: Optional[int] = None
        if DDB_TTL_DAYS and DDB_TTL_DAYS.isdigit():
            ttl_days_int = int(DDB_TTL_DAYS)
        _session_store = SessionStore(
            region_name=DDB_REGION,
            turns_table=DDB_TURNS_TABLE,
            summary_table=DDB_SUMMARY_TABLE,
            endpoint_url=DDB_ENDPOINT,
            ttl_days=ttl_days_int,
            max_recent=SESSION_RECENT_LIMIT,
            auto_create=DDB_AUTO_CREATE,
        )
    return _session_store


def _load_postgres_module():
    postgres_dir = os.path.join(ROOT_DIR, "postgres")
    postgres_file = os.path.join(postgres_dir, "langchain-postgres.py")
    if not os.path.exists(postgres_file):
        return None
    spec = importlib.util.spec_from_file_location("langchain_postgres", postgres_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _document_id(doc: Document, fallback_index: int) -> str:
    doc_id = getattr(doc, "id", None)
    if doc_id:
        return str(doc_id)
    meta = doc.metadata or {}
    for key in ("chunkId", "resourceId", "id"):
        if key in meta:
            return str(meta[key])
    content_hash = hashlib.sha256(doc.page_content.encode("utf-8")).hexdigest()
    return f"content:{fallback_index}:{content_hash}"


def _to_response(doc: Document, doc_id: str) -> DocumentResponse:
    return DocumentResponse(
        id=doc_id,
        content=doc.page_content,
        metadata=doc.metadata or {},
    )


async def _rerank_single(request: RerankRequest) -> RerankResponse:
    module = _load_postgres_module()
    if not module:
        raise HTTPException(status_code=500, detail="postgres/langchain-postgres.py not found")

    query = request.query
    k_retrieve = request.k_retrieve or DEFAULT_K_RETRIEVE
    k_return = request.k_return or DEFAULT_K_RETURN

    candidates: List[Document] = await module.search_similar_chunks(
        query=query,
        k=k_retrieve,
        filter_metadata=request.filter_metadata,
    )

    if not candidates:
        return RerankResponse(query=query, results=[])

    candidate_pairs = [(doc, _document_id(doc, idx)) for idx, doc in enumerate(candidates)]
    doc_ids = [doc_id for _doc, doc_id in candidate_pairs]
    cache_key = build_cache_key(query, doc_ids)
    cache = _get_cache()
    cached = cache.get(cache_key)

    if cached:
        cached_map = {doc_id: score for doc_id, score in cached}
        if all(doc_id in cached_map for doc_id in doc_ids):
            scored = [(idx, doc, doc_id) for idx, (doc, doc_id) in enumerate(candidate_pairs)]
            scored.sort(key=lambda item: (-cached_map[item[2]], item[0]))
            top_docs = scored[:k_return]
            results = [_to_response(doc, doc_id) for _idx, doc, doc_id in top_docs]
            return RerankResponse(query=query, results=results)

    reranker = _get_reranker()
    scored_docs = reranker.rerank_with_scores(query, candidates)
    doc_id_map = {id(doc): doc_id for doc, doc_id in candidate_pairs}
    scored_pairs: List[Tuple[str, float]] = []
    for doc, score in scored_docs:
        doc_id = doc_id_map.get(id(doc), "")
        if doc_id:
            scored_pairs.append((doc_id, score))
    cache.set(cache_key, scored_pairs)

    top_docs = scored_docs[:k_return]
    results = [_to_response(doc, doc_id_map.get(id(doc), _document_id(doc, idx))) for idx, (doc, _score) in enumerate(top_docs)]
    return RerankResponse(query=query, results=results)


@app.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest) -> RerankResponse:
    return await _rerank_single(request)


@app.post("/rerank/batch", response_model=BatchRerankResponse)
async def rerank_batch(request: BatchRerankRequest) -> BatchRerankResponse:
    tasks = [_rerank_single(item) for item in request.items]
    results = await asyncio.gather(*tasks)
    return BatchRerankResponse(items=results)


@app.get("/rerank/health")
async def rerank_health() -> Dict[str, str]:
    reranker = _get_reranker()
    return {"status": "healthy", "model": reranker.model_name, "device": reranker.device}


@app.get("/rerank/stats", response_model=StatsResponse)
async def rerank_stats() -> StatsResponse:
    reranker = _get_reranker()
    cache = _get_cache()
    stats = cache.stats()
    return StatsResponse(
        model_name=reranker.model_name,
        device=reranker.device,
        cache_hits=stats["hits"],
        cache_misses=stats["misses"],
        cache_size=stats["size"],
    )


# ---------------- Session memory endpoints (DynamoDB) ---------------- #


@app.post("/session/turn", response_model=SessionTurnResponse)
def append_session_turn(payload: SessionTurnRequest) -> SessionTurnResponse:
    store = _get_session_store()
    store.append_turn(
        session_id=payload.session_id,
        role=payload.role,
        text=payload.text,
        meta=payload.meta,
        patient_id=payload.patient_id,
    )
    recent = store.get_recent(payload.session_id, limit=payload.return_limit or SESSION_RECENT_LIMIT)
    summary = store.get_summary(payload.session_id)
    return SessionTurnResponse(session_id=payload.session_id, recent_turns=recent, summary=summary)


@app.get("/session/{session_id}", response_model=SessionTurnResponse)
def get_session_state(session_id: str, limit: int = SESSION_RECENT_LIMIT) -> SessionTurnResponse:
    store = _get_session_store()
    recent = store.get_recent(session_id, limit=limit)
    summary = store.get_summary(session_id)
    return SessionTurnResponse(session_id=session_id, recent_turns=recent, summary=summary)


@app.post("/session/summary")
def update_session_summary(payload: SessionSummaryUpdate) -> Dict[str, Any]:
    store = _get_session_store()
    store.update_summary(session_id=payload.session_id, summary=payload.summary, patient_id=payload.patient_id)
    summary = store.get_summary(payload.session_id)
    return {"session_id": payload.session_id, "summary": summary}


@app.delete("/session/{session_id}")
def clear_session(session_id: str) -> Dict[str, str]:
    store = _get_session_store()
    store.clear_session(session_id)
    return {"status": "cleared", "session_id": session_id}
