"""FastAPI router for retrieval/reranking endpoints."""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import APIRouter
from langchain_core.documents import Document

from api.database.postgres import hybrid_search
from api.retrieval.cache import InMemoryCache, build_cache_key
from api.retrieval.cross_encoder import Reranker
from api.retrieval.models import (
    BatchRerankRequest,
    BatchRerankResponse,
    DocumentResponse,
    RerankRequest,
    RerankResponse,
    RerankWithContextRequest,
    RerankWithContextResponse,
    FullDocumentResponse,
    StatsResponse,
)

# Add project root to path so we can import from postgres/ (not a package)
_ROOT_DIR = Path(__file__).resolve().parents[2]
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

router = APIRouter()

# Configuration
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
RERANKER_DEVICE = os.getenv("RERANKER_DEVICE", "auto")
DEFAULT_K_RETRIEVE = int(os.getenv("RERANKER_K_RETRIEVE", "50"))
DEFAULT_K_RETURN = int(os.getenv("RERANKER_K_RETURN", "10"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))
CACHE_MAX_SIZE = int(os.getenv("CACHE_MAX_SIZE", "10000"))

_reranker: Optional[Reranker] = None
_cache: Optional[InMemoryCache] = None


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



def _document_id(doc: Document, fallback_index: int) -> str:
    doc_id = getattr(doc, "id", None)
    if doc_id:
        return str(doc_id)
    meta = doc.metadata or {}
    for key in ("chunk_id", "resource_id", "id"):
        if key in meta:
            return str(meta[key])
    content_hash = hashlib.sha256(doc.page_content.encode("utf-8")).hexdigest()
    return f"content:{fallback_index}:{content_hash}"


def _to_response(doc: Document, doc_id: str, score: float = 0.0) -> DocumentResponse:
    return DocumentResponse(
        id=doc_id,
        content=doc.page_content,
        metadata=doc.metadata or {},
        score=score,
    )


async def _rerank_single(request: RerankRequest) -> RerankResponse:
    query = request.query
    k_retrieve = request.k_retrieve or DEFAULT_K_RETRIEVE
    k_return = request.k_return or DEFAULT_K_RETURN

    # ENFORCED: Always use Hybrid Search (BM25 + Semantic)
    # This ensures exact matches for ICD-10 codes, dates, and names are found
    # even if semantic similarity is low.
    candidates: List[Document] = await hybrid_search(
        query=query,
        k=k_retrieve,
        filter_metadata=request.filter_metadata,
        bm25_weight=0.5,     # Balanced for FHIR keyword matching (resourceType, codes)
        semantic_weight=0.5, # Equal semantic understanding
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
            results = [_to_response(doc, doc_id, cached_map[doc_id]) for _idx, doc, doc_id in top_docs]
            return RerankResponse(query=query, results=results)

    reranker = _get_reranker()
    # Run synchronous cross-encoder inference in a thread pool to avoid
    # blocking the event loop (which deadlocks self-referencing HTTP calls)
    scored_docs = await asyncio.to_thread(reranker.rerank_with_scores, query, candidates)
    doc_id_map = {id(doc): doc_id for doc, doc_id in candidate_pairs}
    scored_pairs: List[Tuple[str, float]] = []
    for doc, score in scored_docs:
        doc_id = doc_id_map.get(id(doc), "")
        if doc_id:
            scored_pairs.append((doc_id, score))
    cache.set(cache_key, scored_pairs)

    top_docs = scored_docs[:k_return]
    results = [_to_response(doc, doc_id_map.get(id(doc), _document_id(doc, idx)), score) for idx, (doc, score) in enumerate(top_docs)]
    return RerankResponse(query=query, results=results)


async def _fetch_full_documents(patient_ids: List[str]) -> List[FullDocumentResponse]:
    if not patient_ids:
        return []
    from postgres.ingest_fhir_json import get_latest_raw_files_by_patient_ids
    raw_files = await get_latest_raw_files_by_patient_ids(patient_ids)
    documents: List[FullDocumentResponse] = []
    for item in raw_files:
        documents.append(
            FullDocumentResponse(
                patient_id=item.get("patient_id", ""),
                source_filename=item.get("source_filename", ""),
                bundle_json=item.get("bundle_json", {}),
            )
        )
    return documents


@router.post("/rerank", response_model=RerankResponse)
async def rerank(request: RerankRequest) -> RerankResponse:
    return await _rerank_single(request)


@router.post("/rerank/with-context", response_model=RerankWithContextResponse)
async def rerank_with_context(request: RerankWithContextRequest) -> RerankWithContextResponse:
    reranked = await _rerank_single(request)
    patient_ids = []
    for item in reranked.results:
        metadata = item.metadata or {}
        patient_id = metadata.get("patient_id")
        if patient_id:
            patient_ids.append(str(patient_id))
    full_documents = []
    if request.include_full_json:
        full_documents = await _fetch_full_documents(sorted(set(patient_ids)))
    return RerankWithContextResponse(query=reranked.query, chunks=reranked.results, full_documents=full_documents)


@router.post("/rerank/batch", response_model=BatchRerankResponse)
async def rerank_batch(request: BatchRerankRequest) -> BatchRerankResponse:
    tasks = [_rerank_single(item) for item in request.items]
    results = await asyncio.gather(*tasks)
    return BatchRerankResponse(items=results)


@router.get("/rerank/health")
async def rerank_health() -> Dict[str, str]:
    reranker = _get_reranker()
    return {"status": "healthy", "model": reranker.model_name, "device": reranker.device}


@router.get("/rerank/stats", response_model=StatsResponse)
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
