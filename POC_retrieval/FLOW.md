# Retrieval + Reranking Flow

## Overview
This folder contains the retrieval pipeline that pulls candidate chunks from the
pgvector store and reranks them with a cross-encoder before returning results
to the LLM caller.

## Flow of Events
1. **Query Input**
   - Input: natural language query and optional metadata filters.
2. **Vector Search**
   - `postgres/langchain-postgres.py::search_similar_chunks()` retrieves top K
     candidate documents from `hc_ai_schema.hc_ai_table` using embeddings.
3. **Cross-Encoder Rerank**
   - `POC_retrieval/reranker/cross_encoder.py` scores query–document pairs.
   - Results are sorted by score and trimmed to top N.
4. **Return to LLM**
   - The reranked documents (content + metadata + id) are returned to the caller.

## Configuration (Repo Root .env)
The reranker reads `.env` from the repo root:
`/Users/raph/.cursor/worktrees/hc_ai/plp/.env`

Key variables:
- `RERANKER_MODEL` (default: `sentence-transformers/ms-marco-MiniLM-L-6-v2`)
- `RERANKER_DEVICE` (`auto`, `cpu`, `cuda`)
- `RERANKER_K_RETRIEVE` (default: 50)
- `RERANKER_K_RETURN` (default: 10)
- `CACHE_TTL` (default: 3600)
- `CACHE_MAX_SIZE` (default: 10000)
- `RERANKER_SERVICE_URL` (default: `http://localhost:8001`)

## Inputs / Outputs
**Input**: query string, optional metadata filters, `k_retrieve`, `k_return`  
**Output**: list of reranked documents with `id`, `content`, and `metadata`

## Notes
- In-memory cache reduces repeated scoring for identical query–doc sets.
- This retrieval pipeline is separate from ingestion (`POC_embeddings/`) and should not
  interfere with the running ingestion processes.
