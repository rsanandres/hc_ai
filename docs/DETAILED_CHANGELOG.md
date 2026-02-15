# Atlas Detailed Changelog

Complete file-level history reconstructed from git commits.

---

## Week 1: Foundation (Jan 9-15, 2026)

### Jan 9 - Initial Commit & Chunking Research
**Commits:** 6

| Action | Files |
|--------|-------|
| A | `README.md` |
| A | `.gitignore`, `FHIR_STRUCTURE.md` |
| A | `POC/main.go`, `POC/main.py`, `POC/requirements.txt` |
| A | `POC/test_chunking_comparison.py`, `POC/README_TEST.md` |
| A | `POC/analyze_fhir_resources.py` |
| A | `chunking.md` - Documentation on chunking strategy |

**Key Decision:** Recursive JSON splitter with min 100 / max 1000 character chunks

---

### Jan 12 - PostgreSQL Setup
**Commits:** 1

| Action | Files |
|--------|-------|
| A | `postgres/docker-compose.yml` |
| A | `postgres/test-langchain-postgres.py` |
| A | `postgres/test.sql` |

---

### Jan 13 - Embeddings Pipeline Complete
**Commits:** 1

| Action | Files |
|--------|-------|
| A | `postgres/langchain-postgres.py` - Main embedding ingestion |
| A | `postgres/old-langchain-postgres.py` - Backup version |
| A | `postgres/check-db.py` |

---

### Jan 14 - Retrieval POC
**Commits:** 4

| Action | Files |
|--------|-------|
| A | `POC_retrieval/` - New retrieval module |
| A | `POC_retrieval/reranker/service.py` - Cross-encoder service |
| A | `POC_retrieval/reranker/cache.py` - Caching layer |
| A | `POC_retrieval/reranker/cross_encoder.py` |
| A | `POC_retrieval/reranker/models.py` |
| A | `postgres/ingest_fhir_json.py` |
| A | `postgres/queue_storage.py` - Failed chunk queue |
| R | `POC/` → `POC_embeddings/` - Renamed directory |

---

### Jan 15 - Reranker Tuning
**Commits:** 1

| Action | Files |
|--------|-------|
| M | `POC_retrieval/reranker/cache.py` |
| M | `POC_retrieval/reranker/service.py` |
| A | `postgres/ingest_fhir_json.py` - Full JSON ingestion |

---

## Week 2: Agent Development (Jan 16-22, 2026)

### Jan 16 - First Agent & Frontend
**Commits:** 4

**Agent POC Created:**
| Action | Files |
|--------|-------|
| A | `POC_agent/` - New agent module |
| A | `POC_agent/agent/graph.py` - LangGraph setup |
| A | `POC_agent/agent/tools.py` - Initial tools |
| A | `POC_agent/guardrails/validators.py` |
| A | `POC_agent/pii_masker/` - PII protection |
| A | `POC_agent/service.py` - FastAPI service |

**Frontend Created:**
| Action | Files |
|--------|-------|
| A | `frontend/` - Next.js application |
| A | `frontend/src/app/page.tsx` |
| A | `frontend/src/components/chat/` - Chat UI |
| A | `frontend/src/components/workflow/` - Pipeline visualization |
| A | `frontend/src/hooks/useChat.ts` |
| A | `frontend/src/services/agentApi.ts` |

**Session Management:**
| Action | Files |
|--------|-------|
| A | `POC_retrieval/session/store_dynamodb.py` |
| A | `POC_retrieval/docker-compose-dynamodb.yml` |

---

### Jan 17 - Agent Integration Testing
**Commits:** 1

| Action | Files |
|--------|-------|
| M | `POC_agent/test_agent_integration.py` |

---

### Jan 19 - Multi-Agent Architecture
**Commits:** 3

**Major Restructure - Tools Modularized:**
| Action | Files |
|--------|-------|
| A | `POC_agent/agent/multi_agent_graph.py` - Multi-agent workflow |
| A | `POC_agent/agent/prompt_loader.py` |
| A | `POC_agent/prompts.yaml` - Centralized prompts |
| R | `POC_agent/agent/tools.py` → `POC_agent/agent/tools/__init__.py` |
| A | `POC_agent/agent/tools/calculators.py` - BMI, GFR, etc. |
| A | `POC_agent/agent/tools/dosage_validator.py` |
| A | `POC_agent/agent/tools/fda_tools.py` - FDA API integration |
| A | `POC_agent/agent/tools/loinc_lookup.py` |
| A | `POC_agent/agent/tools/research_tools.py` - PubMed, etc. |
| A | `POC_agent/agent/tools/retrieval.py` |
| A | `POC_agent/agent/tools/terminology_tools.py` - ICD-10, RxNorm |

**MCP Integration Attempted:**
| Action | Files |
|--------|-------|
| A | `POC_agent/mcp/` - Model Context Protocol |
| A | `POC_agent/mcp/client.py` |
| A | `POC_agent/mcp/servers.py` |

**Tests Added:**
| Action | Files |
|--------|-------|
| A | `POC_agent/tests/test_custom_tools.py` |
| A | `POC_agent/tests/test_e2e_flow.py` |
| A | `POC_agent/tests/test_mcp_connections.py` |

---

### Jan 20 - Prompt Clarification
**Commits:** 1

| Action | Files |
|--------|-------|
| M | `POC_agent/agent/prompt_loader.py` |
| M | `POC_agent/prompts.yaml` |

---

### Jan 21-22 - RAGAS Evaluation Framework
**Commits:** 3

| Action | Files |
|--------|-------|
| A | `POC_RAGAS/` - Evaluation framework |
| A | `POC_RAGAS/evaluators/faithfulness.py` |
| A | `POC_RAGAS/evaluators/relevancy.py` |
| A | `POC_RAGAS/evaluators/noise_sensitivity.py` |
| A | `POC_RAGAS/generators/synthetic_testset.py` |
| A | `POC_RAGAS/runners/agent_runner.py` |
| A | `POC_RAGAS/runners/api_runner.py` |
| A | `POC_RAGAS/scripts/run_evaluation.py` |
| A | `POC_RAGAS/scripts/run_evaluation_batch.py` |
| A | `POC_RAGAS/utils/checkpoint.py` |
| A | `POC_RAGAS/utils/service_manager.py` |

---

## Week 3: Integration (Jan 25-31, 2026)

### Jan 25 - Test Suite
**Commits:** 1

| Action | Files |
|--------|-------|
| A | `POC_agent/tests/test_tool_accuracy.py` |
| A | `POC_agent/tests/test_tool_functionality.py` |
| A | `POC_agent/tests/test_prompt_configuration.py` |
| A | `POC_agent/tests/utils/` - Test utilities |

---

### Jan 26 - API Consolidation (Major Refactor)
**Commits:** 3

**Unified API Created:**
| Action | Files |
|--------|-------|
| A | `api/` - New unified API directory |
| A | `api/main.py` - Single FastAPI app |
| A | `api/agent/` - Agent module |
| A | `api/agent/multi_agent_graph.py` |
| A | `api/agent/prompts.yaml` |
| A | `api/agent/tools/` - All tools |
| A | `api/database/postgres.py` |
| A | `api/embeddings/router.py` |
| A | `api/retrieval/router.py` |
| A | `api/session/router.py` |
| A | `api/session/store_dynamodb.py` |

**CLI Tools:**
| Action | Files |
|--------|-------|
| A | `scripts/agent_debug_cli.py` |
| A | `scripts/chat_cli.py` |

**Database Scripts:**
| Action | Files |
|--------|-------|
| A | `db/postgres/docker-compose.yml` |
| A | `db/dynamodb/docker-compose.yml` |
| A | `scripts/check_db.py` |

**Frontend Updates:**
| Action | Files |
|--------|-------|
| A | `frontend/src/components/session/SessionSidebar.tsx` |
| A | `frontend/src/hooks/useSessions.ts` |
| A | `frontend/src/hooks/useUser.ts` |
| A | `frontend/src/services/embeddingsApi.ts` |

---

### Jan 27 - RAG Feature Complete
**Commits:** 4

**Prompting & Validation:**
| Action | Files |
|--------|-------|
| A | `api/agent/output_schemas.py` |
| A | `api/agent/tools/argument_validators.py` |
| A | `api/database/bm25_search.py` - BM25 keyword search |
| M | `api/agent/prompts.yaml` - Major prompt updates |
| M | `api/agent/guardrails/validators.py` |

**Frontend Streaming:**
| Action | Files |
|--------|-------|
| A | `frontend/src/services/streamAgent.ts` - SSE streaming |
| A | `frontend/src/components/chat/ThinkingPanel.tsx` |
| A | `frontend/src/components/workflow/ReferencePanel.tsx` |
| A | `frontend/src/hooks/useDebugMode.tsx` |
| M | `frontend/src/components/chat/ChatPanel.tsx` |

**MCP Removed:**
| Action | Files |
|--------|-------|
| D | `api/agent/mcp/` - Removed MCP (not needed) |

---

### Jan 28 - Working Prototype
**Commits:** 2

**Documentation:**
| Action | Files |
|--------|-------|
| A | `frontend/public/technical_documentation.md` |
| A | `frontend/public/*_diagram_*.png` - Architecture diagrams |
| A | `frontend/src/app/docs/page.tsx` - Docs page |
| A | `frontend/src/components/workflow/DocumentationPanel.tsx` |

**Bug Fixes:**
| Action | Files |
|--------|-------|
| M | `api/database/postgres.py` |
| M | `api/retrieval/router.py` |
| A | `scripts/migrate_metadata_to_snake_case.py` |

---

### Jan 29-31 - RAGAS Testing & Prep
**Commits:** 4

| Action | Files |
|--------|-------|
| A | `POC_RAGAS/scripts/score_batch_results.py` |
| A | `POC_RAGAS/scripts/generate_patient_tests.py` |
| A | `agent_scratch_space/` - Debug scripts |
| A | `scripts/run_patient_evaluation.sh` |
| A | `scripts/evaluate_clinical_batch.sh` |

---

## Week 4: Production Prep (Feb 2-3, 2026)

### Feb 2 - Final Testing
**Commits:** 3

**RAGAS Improvements:**
| Action | Files |
|--------|-------|
| A | `agent_scratch_space/run_comprehensive_eval.py` |
| A | `agent_scratch_space/golden_truths_report.md` |
| A | `agent_scratch_space/quick_ragas_score.py` |
| M | `api/agent/prompts.yaml` |
| M | `api/database/bm25_search.py` |

**Debug Tools:**
| Action | Files |
|--------|-------|
| A | `agent_scratch_space/debug_retrieval.py` |
| A | `agent_scratch_space/verify_agent_tool_use.py` |

---

### Feb 3 - Cleanup
**Commits:** 1

| Action | Files |
|--------|-------|
| D | `api.log` |

---

## Week 5: Major Fixes (Feb 4, 2026)

### Feb 4 - Extensive Improvements
**Commits:** 14+

**Authentication System:**
| Action | Files |
|--------|-------|
| A | `api/auth/` - JWT authentication |
| A | `api/auth/router.py` |
| A | `api/auth/security.py` |
| A | `api/auth/models.py` |
| A | `api/auth/email.py` |
| A | `api/database/migrations/001_create_auth_tables.sql` |
| A | `frontend/src/components/auth/LoginForm.tsx` |
| A | `frontend/src/components/auth/RegisterForm.tsx` |
| A | `frontend/src/components/ProtectedRoute.tsx` |

**Patient Auto-Injection:**
| Action | Files |
|--------|-------|
| A | `api/agent/tools/context.py` - Thread-safe patient context |
| M | `api/agent/tools/retrieval.py` - Auto-inject patient_id |
| M | `api/agent/tools/__init__.py` |
| M | `api/agent/multi_agent_graph.py` |

**Search Fixes:**
| Action | Files |
|--------|-------|
| M | `api/database/postgres.py` - SQL-level patient filtering |

**Prompt Engineering:**
| Action | Files |
|--------|-------|
| M | `api/agent/prompts.yaml` - Query decomposition, dates |
| A | `CLAUDE.md` - Project documentation |
| A | `scripts/batch_embed_patients.py` - Patient name prefixing |

**Frontend Polish:**
| Action | Files |
|--------|-------|
| M | `frontend/src/components/workflow/ReferencePanel.tsx` |
| M | `frontend/src/app/page.tsx` |
| M | `frontend/src/hooks/useChat.ts` |
| M | `frontend/src/components/chat/ChatInput.tsx` |

---

## Week 6: The Travel Sprint (Feb 9, 2026)

### Feb 9 - Frontend Overhaul, Containerization & Repo Cleanup
**Commits:** 5

**Frontend UX Overhaul (12 improvements):**
| Action | Files |
|--------|-------|
| M | `frontend/src/app/page.tsx` - SSE-driven pipeline timing |
| M | `frontend/src/hooks/useChat.ts` - Real step transitions |
| M | `frontend/src/hooks/useWorkflow.ts` - `activateStep()` with `Date.now()` |
| M | `frontend/src/components/workflow/PipelineStep.tsx` - Source scores |
| M | `frontend/src/services/streamAgent.ts` - Streaming improvements |

**README Rewrite:**
| Action | Files |
|--------|-------|
| M | `README.md` - Full project scope, recommended prompts |

**Repo Cleanup for Public Visibility:**
| Action | Files |
|--------|-------|
| D | Various internal dev files |
| A | `LICENSE` - MIT license |

**Containerization & CI:**
| Action | Files |
|--------|-------|
| A | `Dockerfile` - Backend container |
| A | `.github/workflows/ci.yml` - Lint + build checks |

---

## Week 7: AWS Migration (Feb 10-13, 2026)

### Feb 10 - AWS Migration Analysis & Initial Deployment
**Commits:** 1

| Action | Files |
|--------|-------|
| A | `docs/aws-migration-analysis.md` - Cost-optimized architecture plan |

**Infrastructure work (not in git):**
- RDS PostgreSQL 16 deployed (db.t4g.medium, 50 GB → 100 GB gp3)
- Bedrock Titan embedding: 83,098 patients in first run
- EC2 t3.medium for embedding (same VPC, direct Bedrock calls)
- Secrets Manager configured (`hcai/prod`, 5 keys)
- Security group lockdown (ECS→RDS only)

---

### Feb 11 - Production Config & Bedrock Integration
**Commits:** 5

**Production Deployment Config:**
| Action | Files |
|--------|-------|
| A | `api/agent/config.py` - Bedrock model IDs (Sonnet + Haiku) |
| M | `api/agent/multi_agent_graph.py` - `get_llm()` with model tiers |
| M | `api/main.py` - Production environment detection |

**Frontend Persona Data:**
| Action | Files |
|--------|-------|
| A | `frontend/public/data/patients.json` - 91,094 patients (static) |
| A | `frontend/src/data/featured-patients.ts` - 9 featured patients |

**Embedding Cost Documentation:**
| Action | Files |
|--------|-------|
| M | `docs/aws-migration-analysis.md` - Updated cost estimates |

**Production Fixes (v5):**
| Action | Files |
|--------|-------|
| M | `api/database/postgres.py` - SSL context for asyncpg (non-localhost) |
| M | `api/session/router.py` - Stub DynamoDB endpoints (200 when disabled) |

**Static Patient Directory:**
| Action | Files |
|--------|-------|
| M | `frontend/src/components/PatientSelector.tsx` - Load from static JSON |
| M | `api/database/router.py` - Removed expensive `/db/patients` scan |

---

### Feb 12 - CI/CD, Observability & Security Hardening
**Commits:** 10

**Connection Pool Consolidation:**
| Action | Files |
|--------|-------|
| M | `api/auth/router.py` - Share engine with database module |
| M | `api/database/postgres.py` - Single connection pool |

**Maintenance Mode:**
| Action | Files |
|--------|-------|
| A | `frontend/src/components/MaintenanceBanner.tsx` - Auto-detect downtime |
| M | `frontend/src/hooks/useChat.ts` - Health check integration |

**Agent Performance:**
| Action | Files |
|--------|-------|
| M | `api/agent/config.py` - Bedrock timeout (60s read, 10s connect, 2 retries) |
| M | `api/agent/multi_agent_graph.py` - Max iterations 10, step limit warning at 8 |
| M | `api/agent/multi_agent_graph.py` - Sonnet for researcher, Haiku for others |

**SSE Keepalive:**
| Action | Files |
|--------|-------|
| M | `api/agent/router.py` - Keepalive pings every 15s via asyncio.Queue |

**CI/CD Pipeline:**
| Action | Files |
|--------|-------|
| A | `.github/workflows/deploy.yml` - GitHub Actions → ECR → ECS |
| M | `.github/workflows/ci.yml` - Fixed lint errors |

**CloudWatch Observability:**
| Action | Files |
|--------|-------|
| A | `api/database/cloudwatch.py` - CloudWatch metrics API |
| A | `infra/cloudwatch-dashboard.json` - Dashboard definition |
| M | `api/database/router.py` - `/db/cloudwatch` endpoint |
| M | `frontend/src/components/workflow/ObservabilityPanel.tsx` - Sparklines |

**Security Hardening:**
| Action | Files |
|--------|-------|
| M | `api/database/postgres.py` - Parameterized queries (SQL injection fix) |
| M | `api/agent/router.py` - Auth required on admin endpoints |
| M | `api/auth/router.py` - Rate limiting |

**Featured Patients:**
| Action | Files |
|--------|-------|
| M | `frontend/src/data/featured-patients.ts` - 9 data-rich patients |
| M | `frontend/src/components/WelcomeScreen.tsx` - Featured patient cards |

---

### Feb 13 - Frontend Polish, IVFFlat & Index Planning
**Commits:** 9

**Onboarding System:**
| Action | Files |
|--------|-------|
| A | `frontend/src/components/WelcomeScreen.tsx` - Full-page onboarding |
| A | `frontend/src/components/OnboardingTour.tsx` - 6-step UI tour |

**Frontend Fixes:**
| Action | Files |
|--------|-------|
| M | `frontend/src/app/page.tsx` - Debug mode default true, auto-open side panel |
| M | `frontend/src/components/workflow/PipelineStep.tsx` - Correct model names |
| M | `frontend/src/components/workflow/PipelineVisualization.tsx` - Step transitions |

**LangSmith Removal:**
| Action | Files |
|--------|-------|
| D | `frontend/src/components/workflow/LangSmithPanel.tsx` |
| D | `frontend/src/hooks/useLangSmith.ts` |
| M | `frontend/src/app/page.tsx` - Removed LangSmith integration |
| M | 4 other files - Stripped LangSmith references (-170 lines total) |

**Backports from atlas_mcp (formerly hc_ai_mcp):**
| Action | Files |
|--------|-------|
| M | `api/agent/tools/retrieval.py` - Timeline ORDER BY fix |
| M | `api/agent/router.py` - Reranker score propagation |
| M | `api/agent/multi_agent_graph.py` - Metadata key whitelist |

**IVFFlat Index Work:**
| Action | Files |
|--------|-------|
| M | `api/database/postgres.py` - `SET ivfflat.probes = 53` (then updated to 23) |

**Lint Fix:**
| Action | Files |
|--------|-------|
| M | `frontend/src/components/OnboardingTour.tsx` - Initialize from prop, not effect |

---

## File Statistics

### Most Modified Files (Top 15)
1. `api/agent/prompts.yaml` — 15+ modifications
2. `api/agent/multi_agent_graph.py` — 15+ modifications
3. `frontend/src/hooks/useChat.ts` — 12+ modifications
4. `frontend/src/app/page.tsx` — 12+ modifications
5. `api/agent/router.py` — 10+ modifications
6. `api/database/postgres.py` — 10+ modifications
7. `api/agent/tools/retrieval.py` — 8+ modifications
8. `frontend/src/components/chat/ChatPanel.tsx` — 7+ modifications
9. `frontend/src/services/streamAgent.ts` — 6+ modifications
10. `api/agent/config.py` — 5+ modifications
11. `api/auth/router.py` — 4+ modifications
12. `api/database/router.py` — 4+ modifications
13. `frontend/src/components/workflow/PipelineStep.tsx` — 4+ modifications
14. `frontend/src/data/featured-patients.ts` — 3+ modifications
15. `api/main.py` — 3+ modifications

### Files Added by Category
- **Agent System:** ~55 files
- **Frontend:** ~55 files
- **Database:** ~18 files
- **Testing/RAGAS:** ~40 files
- **Scripts/Utils:** ~32 files
- **Infrastructure:** ~8 files (CI/CD, Docker, CloudWatch)
- **Documentation:** ~12 files

### Files Deleted
- `api/agent/mcp/` — MCP integration removed (not needed)
- `POC_embeddings/*.log` — Log files cleaned up
- `api.log` — Log file removed
- `AWSCLIV2.pkg` — Accidentally committed, removed
- `frontend/src/components/workflow/LangSmithPanel.tsx` — Replaced by CloudWatch
- `frontend/src/hooks/useLangSmith.ts` — Removed with LangSmith

### Total Commits
- **73 commits** across 6 weeks (Jan 9 – Feb 13, 2026)
- Week 1: 10 commits (foundation)
- Week 2: 10 commits (agent development)
- Week 3: 11 commits (integration)
- Week 4: 5 commits (production prep)
- Week 5: 14 commits (major fixes — single day Feb 4)
- Week 6-7: 23 commits (AWS migration + frontend polish)

---

## Legend
- **A** = Added
- **M** = Modified
- **D** = Deleted
- **R** = Renamed
