# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HC AI is a medical AI platform for processing FHIR (Fast Healthcare Interoperability Resources) data with RAG-based retrieval, multi-agent reasoning, and a full-stack chat interface.

## Common Commands

### Backend
```bash
# Start unified API (port 8000)
python api/main.py
uvicorn api.main:app --reload --port 8000

# Run tests
python -m pytest api/agent/test_*.py
python -m pytest scripts/test_*.py
```

### Frontend
```bash
cd frontend
npm install          # Install dependencies
npm run dev          # Development server (port 3000)
npm run build        # Production build
npm run lint         # Run ESLint
```

### Infrastructure
```bash
# PostgreSQL with pgvector
cd postgres && docker-compose up -d

# DynamoDB Local (for sessions)
cd POC_retrieval && docker-compose -f docker-compose-dynamodb.yml up -d

# Ollama (for LLM/embeddings)
ollama serve
ollama pull mxbai-embed-large:latest
ollama pull llama3.1:8b
```

### Data Ingestion
```bash
# Batch embed FHIR patient data
python scripts/batch_embed_patients.py

# Go FHIR parser (in POC_embeddings/)
go run main.go
```

### Utility Scripts
```bash
python scripts/check_db.py           # Database diagnostics
python scripts/chat_cli.py           # Chat CLI interface
python scripts/agent_debug_cli.py    # Agent debugging
```

## Architecture

### Unified FastAPI Application (`api/main.py`)
All services are mounted as routers under a single FastAPI app:
- `/auth/*` → `api/auth/router.py` - JWT authentication, email verification
- `/agent/*` → `api/agent/router.py` - LangGraph-based multi-agent queries
- `/embeddings/*` → `api/embeddings/router.py` - FHIR resource ingestion
- `/retrieval/*` → `api/retrieval/router.py` - Cross-encoder reranking
- `/session/*` → `api/session/router.py` - DynamoDB session management
- `/db/*` → `api/database/router.py` - Database stats and queue monitoring

### Agent System (`api/agent/`)
LangGraph-based multi-agent with three nodes:
1. **Researcher**: Retrieves from vector store, uses medical tools (FDA, LOINC, terminology)
2. **Validator**: Safety checks via Guardrails, PII masking
3. **Responder**: Generates final response

Key files:
- `multi_agent_graph.py` - Agent graph definition
- `tools/retrieval.py` - Vector store retrieval tool
- `tools/terminology_tools.py`, `fda_tools.py`, `loinc_lookup.py` - Medical domain tools
- `pii_masker/` - Input/output PII protection
- `prompts.yaml` - Agent prompts

### Data Pipeline
```
FHIR JSON → Go Parser → FastAPI /ingest → RecursiveJsonSplitter → Ollama Embedding → PostgreSQL pgvector
```

Chunking preserves JSON structure (500-1000 chars) with rich metadata (patientId, resourceType, dates).

### Frontend (`frontend/`)
Next.js 16 with React 19:
- `src/app/page.tsx` - Main chat interface
- `src/components/chat/` - ChatPanel, MessageList, ChatInput
- `src/components/workflow/` - Agent processing visualization
- `src/hooks/useChat.ts` - Chat state management
- `src/services/agentApi.ts`, `streamAgent.ts` - API clients with streaming

### Database
- **PostgreSQL + pgvector**: Vector store (1024-dim embeddings) - schema `hc_ai_schema`, table `hc_ai_table`
- **DynamoDB Local**: Session turns and summaries (7-day TTL)
- **SQLite**: Queue persistence for failed chunks

## Key Environment Variables

```bash
# Database
DB_HOST=localhost DB_PORT=5432 DB_USER=postgres DB_NAME=postgres

# LLM/Embeddings
LLM_PROVIDER=ollama LLM_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_PROVIDER=ollama OLLAMA_EMBED_MODEL=mxbai-embed-large:latest

# DynamoDB
DDB_ENDPOINT=http://localhost:8001

# Agent
AGENT_GRAPH_TYPE=complex  # or 'simple'
```

## POC Directories

Legacy implementations preserved for reference:
- `POC_embeddings/` - Original embedding service with Go parser
- `POC_agent/` - Original agent implementation
- `POC_retrieval/` - Retrieval/reranking POC with DynamoDB setup
- `POC_RAGAS/` - RAGAS evaluation framework
