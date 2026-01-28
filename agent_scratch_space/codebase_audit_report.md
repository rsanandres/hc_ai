# Codebase Verification Audit Report

**Date:** 2026-01-27  
**Scope:** Full codebase verification (no code changes)  
**Focus:** Code consistency, import health, dead code detection

---

## Executive Summary

| Category | Severity | Count |
|----------|----------|-------|
| Duplicate Functions | ⚠️ Medium | 11 |
| Potentially Unused Functions | 🔵 Low | 74 |
| Root-level Orphaned Files | 🔵 Low | 3 |
| Deprecated Folder Files | 📋 Info | 99 |

---

## 1. Code Consistency Findings

### 1.1 Duplicate Function Names (Action Required)

These functions are defined in multiple files with the same name, which may indicate code duplication:

| Function | Files | Severity |
|----------|-------|----------|
| `_reranker_url` | `api/agent/tools/__init__.py`, `api/agent/tools/retrieval.py` | ⚠️ High |
| `get_patient_timeline` | `api/database/postgres.py`, `api/agent/tools/__init__.py` | ⚠️ High |
| `validate_icd10_code` | `api/agent/tools/terminology_tools.py`, `api/agent/tools/argument_validators.py` | ⚠️ Medium |
| `_get_reranker` | `api/agent/tools/retrieval.py`, `api/retrieval/router.py` | ⚠️ Medium |
| `_load_postgres_module` | `api/database/router.py`, `api/retrieval/router.py` | 🔵 Low |
| `get_error_counts` | `api/database/postgres.py`, `api/database/queue_storage.py`, `api/database/router.py` | 🔵 Low |
| `get_error_logs` | `api/database/postgres.py`, `api/database/queue_storage.py`, `api/database/router.py` | 🔵 Low |
| `health` | `api/main.py`, `api/agent/router.py` | 🔵 Low (different routers) |
| `root` | `api/main.py`, `api/embeddings/router.py` | 🔵 Low (different routers) |

**Recommendations:**
1. Consolidate `_reranker_url` into a shared utility module
2. The `get_patient_timeline` in `tools/__init__.py` should call the database version, not duplicate logic
3. `validate_icd10_code` should have one canonical implementation

---

### 1.2 Naming Convention Issues

| Pattern | Location | Issue |
|---------|----------|-------|
| Mixed case | `patientId` vs `patient_id` | Database uses camelCase, Python uses snake_case |
| Inconsistent prefixes | `_get_reranker` vs `_reranker_url` | Some helpers use `_get_` prefix, some don't |

---

## 2. Import Health Findings

### 2.1 Import Status
✅ **No circular imports detected**  
✅ **No syntax errors in any Python files**  
⚠️ **Some potentially unused imports** (requires runtime verification)

### 2.2 Cross-Module Dependencies

```
api/agent/tools/__init__.py
├── api.database.postgres (get_patient_timeline)
├── api.session.store_dynamodb (SessionStore)
└── api.agent.pii_masker.factory

api/agent/multi_agent_graph.py
├── api.agent.config
├── api.agent.prompt_loader
├── api.agent.tools (all 10+ tools)
└── api.session.store_dynamodb

api/agent/router.py
├── api.agent.multi_agent_graph
├── api.agent.guardrails.validators
└── 16 total imports
```

---

## 3. Dead Code Findings

### 3.1 Potentially Unused Functions (74 total)

Many are **false positives** (tools called dynamically by LLM). Key genuinely unused:

| Function | Location | Notes |
|----------|----------|-------|
| `ping` | `api/agent/mcp/client.py` | MCP module entirely unused |
| `shutdown_all` | `api/agent/mcp/manager.py` | MCP module entirely unused |
| `build_mcp_tools_for_agent` | `api/agent/mcp/tool_adapter.py` | MCP module entirely unused |
| `detect_pii` | All 3 pii_masker files | Method defined but never called |
| `reload_prompts` | `api/agent/prompt_loader.py` | Defined but never invoked |
| `classify_query` | `api/agent/query_classifier.py` | Standalone function never called |
| `query_agent_stream` | `api/agent/router.py` | Streaming endpoint not used by frontend |

### 3.2 Unused Modules

| Module | Path | Status |
|--------|------|--------|
| MCP (Model Context Protocol) | `api/agent/mcp/` | 5 files, entirely unused |
| PII detection methods | `api/agent/pii_masker/*.py` | `detect_pii` never called |

### 3.3 Tools Registered but May Be Unused by Agent

These are in `_get_researcher_agent()` tool list but may not be called:
- `cross_reference_meds`
- `get_session_context`
- `calculate`
- Most FDA/research tools

---

## 4. File Organization Findings

### 4.1 Root-level Files That Should Be Moved

| File | Current Location | Recommended Location |
|------|------------------|---------------------|
| `test.py` | `/` | `debug/` or `scripts/` |
| `upload_data.py` | `/` | `scripts/` |
| `test_multi_agent_prompts.py` | `/` | `debug/` |

### 4.2 Deprecated Folders (Do Not Touch)

| Folder | Python Files | Status |
|--------|--------------|--------|
| `POC_agent/` | 53 | Deprecated |
| `POC_RAGAS/` | 25 | Deprecated |
| `POC_retrieval/` | 9 | Deprecated |
| `POC_embeddings/` | 5 | Deprecated |
| `postgres/` | 7 | Deprecated |
| **Total** | **99** | Keep for reference |

---

## 5. Frontend Integration Status

### 5.1 API Connection Points (Already Connected)

The frontend in `frontend/src/services/agentApi.ts` connects to:

| Endpoint | Purpose | Status |
|----------|---------|--------|
| `/agent/query` | Main query endpoint | ✅ Connected |
| `/agent/health` | Health check | ✅ Connected |
| `/session/{id}` | Session CRUD | ✅ Connected |
| `/session/list` | List user sessions | ✅ Connected |
| `/session/create` | Create session | ✅ Connected |
| `/retrieval/rerank/*` | Reranker endpoints | ✅ Connected |

### 5.2 Frontend Notes

- Uses `NEXT_PUBLIC_API_URL` env var (defaults to `http://localhost:8000`)
- Types in `src/types/index.ts` reference `POC_agent` in comments - should update to `api/`
- Streaming endpoint `query_agent_stream` exists in backend but not used by frontend

---

## 6. Module Statistics

### 6.1 File Counts by Module

| Module | Python Files | Lines (approx) |
|--------|-------------|----------------|
| `api/agent/` | 31 | ~2,900 |
| `api/database/` | 5 | ~1,200 |
| `api/embeddings/` | 5 | ~1,000 |
| `api/retrieval/` | 5 | ~500 |
| `api/session/` | 4 | ~700 |
| `scripts/` | 7 | ~600 |
| `debug/` | 6 | ~400 |

### 6.2 Largest Files

| File | Lines | Notes |
|------|-------|-------|
| `api/database/postgres.py` | 1006 | Vector store, BM25, queue |
| `api/embeddings/utils/helper.py` | 906 | Chunking, embeddings |
| `api/session/store_dynamodb.py` | 555 | DynamoDB session store |
| `api/agent/multi_agent_graph.py` | 469 | LangGraph workflow |
| `api/agent/query_classifier.py` | 340 | Query classification |

---

## 7. Actionable Items Summary

### High Priority (Code Consistency)
1. [ ] Consolidate `_reranker_url` into shared utility
2. [ ] Fix `get_patient_timeline` duplication (tool should call database function)
3. [ ] Consolidate `validate_icd10_code` implementations

### Medium Priority (Dead Code)
4. [ ] Evaluate if MCP module (`api/agent/mcp/`) is needed
5. [ ] Implement or remove `detect_pii` methods
6. [ ] Consider adding `query_agent_stream` to frontend

### Low Priority (Organization)
7. [ ] Move root-level test files to appropriate folders
8. [ ] Update frontend type comments to reference `api/` instead of `POC_agent/`

---

## 8. Appendix: Scripts Folder Status

| Script | Purpose | Imports from api/ |
|--------|---------|-------------------|
| `agent_debug_cli.py` | Debug CLI for agent | ✅ Yes |
| `visualize_graph.py` | Graph visualization | ✅ Yes |
| `chat_cli.py` | Chat interface | ❌ No |
| `check_db.py` | Database checks | ❌ No |
| `check_embeddings.py` | Embedding checks | ❌ No |
| `ingest_fhir_json.py` | Data ingestion | ❌ No |
| `test_postgres.py` | Postgres tests | ❌ No |

---

*Report generated: 2026-01-27 14:25 PST*
