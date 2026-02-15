# Atlas Project History

## Overview
6-week development history of the Atlas medical platform (formerly HC AI), reconstructed from git commits, Obsidian daily notes, Claude Code memory, and AWS deployment logs. Covers the full journey from first commit to production deployment.

---

## Week 1: Foundation (Jan 9-15, 2026)

### Jan 9 - Project Kickoff
- **Initial commit** - Project created
- **FHIR structure analysis** - Explored FHIR resource formats
- **Chunking strategy research** - Tested different chunking methods
- **Final chunking decision**: Recursive JSON splitter, min 100 / max 1000 chars
- **Embedding details** - Initial embedding configuration

### Jan 12 - Database Setup
- **PostgreSQL + pgvector implementation**
- Initial LangChain integration for vector operations

### Jan 13 - Embeddings Pipeline
- **Embeddings to DB finished** - Full pipeline working
- FHIR data successfully embedded and stored

### Jan 14 - Retrieval POC
- **POC_retrieval** - First retrieval proof of concept
- Cross-encoder reranking exploration
- README documentation
- Continued DB embedding while developing

### Jan 15 - Reranker Integration
- **Adjusted reranker** configuration
- **Ingested full JSON to DB** - Complete FHIR bundles stored

---

## Week 2: Agent Development (Jan 16-22, 2026)

### Jan 16 - First Agent
- **First run through on an agent** - Basic agent working
- **Frontend first try** - Initial React/Next.js setup
- Optimizations to agent logic

### Jan 17 - Continued Development
- Various agent improvements

### Jan 19 - Multi-Agent Architecture
- **Multi-agent implementation** - Researcher + Validator + Responder pattern
- **Tools implementation** - Medical domain tools (FDA, LOINC, etc.)
- Test fixes and refinements

### Jan 20 - Prompt Engineering
- **Clarified prompts** - First major prompt revision
- Improved agent instructions

### Jan 21-22 - RAGAS Evaluation
- **RAGAS implementation** - Evaluation framework setup
- Iterative improvements to RAGAS testing
- "Needs a lot more work" - ongoing evaluation challenges

---

## Week 3: Integration & Polish (Jan 25-31, 2026)

### Jan 25 - Testing
- **Fixed tests** - Test suite stabilization

### Jan 26 - API Consolidation
- **Consolidated API** - Unified FastAPI application
- **DB movement** - Database restructuring
- **Frontend and chatbot changes** - UI improvements

### Jan 27 - RAG Feature Complete
- **Finished RAG feature** - Core retrieval working
- **Layout and frontend integration** - UI polish
- **Prompting changes** - Continued prompt refinement

### Jan 28 - Working Prototype
- **Working prototype** achieved
- Prepared for RAGAS evaluation

### Jan 29 - RAGAS Testing
- Added RAGAS documentation
- Pre-evaluation preparation

### Jan 31 - Global Implementation Prep
- Prepared for broader deployment

---

## Week 4: Production Readiness (Feb 2-3, 2026)

### Feb 2 - Final RAG & AWS Prep
- **RAGAS testing** - Comprehensive evaluation
- **RAGAS improvements** - Based on test results
- **Final RAG before AWS** - Production-ready state

### Feb 3 - Cleanup
- Deleted api.log and other cleanup

---

## Week 5: Major Fixes & Optimization (Feb 4, 2026)

### Feb 4 - Extensive Improvements (Single Day - Many Commits)

#### Morning: Core Fixes
1. **CLAUDE.md added** - Project documentation for AI assistance
2. **Patient name prefixing** - Embedded content prefixed with patient names for better semantic search

#### Patient ID Auto-Injection
3. **Patient selection UI** - Frontend patient picker
4. **Auto-inject patient_id** - Tools receive patient_id from context automatically
5. **Context module** (`context.py`) - Thread-safe patient_id storage via contextvars

#### Search Fixes
6. **SQL-level patient filtering** - Fixed critical bug where semantic search wasn't filtering by patient
   - Problem: Danial Larsen's 2 conditions buried among 5000+ global results
   - Solution: SQL WHERE clause with patient_id before semantic ranking
   - Result: Accuracy improved from 0.513 to 0.83

#### Agent Robustness
7. **LangGraph recursion limits** - Unified AGENT_MAX_ITERATIONS=15
8. **Echo bug prevention** - Detect when researcher echoes system messages
9. **Empty query handling** - Graceful errors instead of 422s

#### Prompt Engineering (Research-Backed)
10. **Query decomposition** - Broad questions trigger multiple tool calls
11. **Date extraction** - Explicit instructions for FHIR date fields
12. **Response Synthesizer** - New agent for user-friendly output formatting
13. **Validator focus shift** - Accuracy over formatting

#### Frontend Polish
14. **Removed prompt dialog** - Streamlined patient selection
15. **Reorganized ReferencePanel** - Patient first, then prompts
16. **Visual indicators** - Selected patient shown in chat header

#### Evening: Hallucination Debugging (This Session)
17. **Identified example contamination** - LLM copying prompt examples as real data
18. **Removed all medical examples** - Replaced with placeholders
19. **Session history disabled** - Prevent cross-session pollution
20. **Model upgrade** - Changed from llama3.1:8b to qwen2.5:32b
21. **Debug logging** - Added DEBUG_HALLUCINATION flag

---

## Week 6: The Travel Sprint (Feb 5-9, 2026)

### Feb 5 - Model Upgrade & Last Local Push
- Major work done the day before — agent cleanup nearly complete
- **Model upgrade**: Upgraded from llama3.1:8b to qwen2.5:32b (hosted remotely via Tailscale)
  - "Did wonders" — hallucination issues dramatically reduced
  - 32B model can distinguish few-shot examples from real data (8B couldn't)
- Frontend detection and cleanup work
- Almost ready to start the AWS migration

### Feb 6-8 - Break
- No project work

### Feb 9 - Productive Travel Day
- Traveling but productive — Claude Code + SSH made remote work possible
- **Frontend UX overhaul** — 12 improvements in one commit:
  - Real pipeline timing (replaced fake 400ms timer with SSE event-driven transitions)
  - Source scores propagated to frontend
  - Multiple UI polish items
- **README rewrite** — Full project scope and recommended prompts
- **Repo cleanup** — Removed internal dev files, polished for public visibility
- **MIT license** added
- **Containerization** — Dockerfile + CI pipeline (GitHub Actions) for AWS deployment
- **5 commits** in a single travel day

---

## Week 7: AWS Migration — "Learning by Doing" (Feb 10-13, 2026)

> _Goal: This is a portfolio project. The point is learning AWS by doing it, not just shipping._

### Feb 10 - The Great Migration Begins

This was the most infrastructure-intensive day of the project. Everything that could go wrong did, and each fix uncovered the next problem.

#### The RDS Storage Crisis
- **Problem**: After embedding 83,098 patients, the 50 GB RDS instance ran out of storage
- **Symptom**: Database entered `storage-full` recovery mode — completely unresponsive
- **Diagnosis**: Used AWS CLI to identify the storage-full state
- **Fix**: Expanded storage from 50 GB to 100 GB gp3
- **Lesson learned**: RDS storage can only increase, never decrease. Each increase requires a 6-hour cooldown.
- **Cost impact**: +$4/mo

#### Bedrock Embedding Campaign
- Ran `batch_embed_bedrock.py` on a t3.medium EC2 instance in the same VPC
- Used ThreadPoolExecutor(25) for parallel Bedrock Titan calls, bypassing the FastAPI HTTP layer
- **First run**: 83,098 patients embedded (~$21 Bedrock cost)
- **Second run**: +19,620 patients (after storage expansion)
- **Stopped at 102,718 / 132,842** (77% coverage) — Bedrock cost hit ~$36 total
- **Decision**: 77% coverage is sufficient for portfolio demo. Raw data preserved for future embedding.
- **Known compromise**: EC2 was missing `langchain-text-splitters` — fell back to blind 1000-char splits instead of RecursiveJsonSplitter. Affects all embeddings but is consistent and functional.

#### Security Lockdown
- Added ECS → RDS security group rule (only ECS tasks can reach the database)
- Deleted stale port 8000 listener on ALB
- Added HTTP → HTTPS redirect on port 80
- Terminated EC2 embedding instance after embedding stopped
- Cleaned up old SageMaker domain and EFS resources

#### Backend Production Fixes (v5 deployed)
- **Session 500s**: DynamoDB not deployed in prod → stubbed endpoints to return 200s when `ENABLE_SESSION_HISTORY=false`
- **RDS SSL rejection**: asyncpg connections to RDS require SSL context — added automatic SSL for non-localhost connections
- **Password sync**: Discovered Secrets Manager and RDS master password were out of sync — corrected both

#### The Connection Leak Incident
- **Symptom**: RDS CPU spiking to 80-85%, 30 active connections
- **Root cause**: `/db/patients` endpoint was scanning 132K JSONB rows every time a user loaded the patient list. Combined with auth router creating a separate connection pool (pool_size=5+10) on top of the database pool (10+5).
- **Fix**: Replaced API call with a static `patients.json` file (91,094 patients) served from Vercel CDN. Search box in frontend.
- **Result**: CPU dropped from 85% → 15%, connections cleared after ECS restart
- Also replaced featured patient "Ron Zieme" (0 chunks, useless for demo) with "Hailee Kovacek" (375 chunks)

#### AWS Migration Analysis
- Wrote comprehensive `docs/aws-migration-analysis.md` with cost-optimized architecture
- Target: ~$85-95/mo for the full stack

### Feb 11 - Production Hardening

#### Morning: Deployment Configuration
- **Bedrock model integration** — Configured `api/agent/config.py` with inference profile IDs:
  - Researcher: Claude 3.5 Sonnet (`us.anthropic.claude-3-5-sonnet-20241022-v2:0`)
  - Responder/Validator: Claude 3.5 Haiku (`us.anthropic.claude-3-5-haiku-20241022-v1:0`)
- **Frontend persona data files** — Static data for Vercel build
- **Embedding cost documentation** — Updated estimates after stopping at 77%

#### Afternoon: More Production Fixes
- **RDS SSL fix** deployed (SSL context for asyncpg)
- **Session endpoint stubs** — Graceful degradation without DynamoDB
- **Static patient directory** live — replaced expensive DB query with CDN-served JSON

#### Meanwhile: Job Search & Side Projects
- Major resume overhaul with 4 job-search-focused variants (Applied AI, Infrastructure, Forward Deployed, Full-Stack)
- Created application timeline (Feb 12 → Apr 30)
- Significant work on Ayle (Godot game project) — 10 improvements, 24 files, 871 insertions

### Feb 12 - CI/CD, Observability & Security

This day was about making the deployment pipeline reliable and the system observable.

#### Connection Pool Consolidation
- **Problem**: Auth router was creating its own SQLAlchemy engine, doubling connection count
- **Fix**: Consolidated auth + database into a single shared connection pool
- Deployed as backend v6

#### Maintenance Mode
- Added auto-detect maintenance banner for frontend during ECS deployments
- Frontend detects unhealthy backend and shows a user-friendly message

#### Agent Performance Tuning
- **Bedrock timeout**: `botocore.Config(read_timeout=60, connect_timeout=10, retries=2)`
- **Iteration limits**: Reduced max iterations from 15 to 10 (Sonnet converges faster)
- **Model split**: Sonnet for Researcher (needs reasoning), Haiku for everything else (fast synthesis)
- Step limit warning at iteration 8

#### ALB Idle Timeout Crisis
- **Problem**: ALB was closing SSE connections after 60 seconds — Sonnet queries take longer
- **Fix**: Increased ALB idle timeout to 300s. Added SSE keepalive pings (`: keepalive\n\n` every 15s via asyncio.Queue).

#### CI/CD Pipeline
- **GitHub Actions → ECR → ECS**: Automatic deployment on push to main
- CI runs lint + type checks; Deploy Backend builds Docker image, pushes to ECR, updates ECS service
- Fixed lint errors across backend and frontend to get CI green

#### CloudWatch Observability
- Created CloudWatch dashboard (`infra/cloudwatch-dashboard.json`)
- Wired metrics into frontend ObservabilityPanel — ECS, ALB, RDS, Bedrock, Billing sparklines
- `api/database/cloudwatch.py` → `/db/cloudwatch` endpoint

#### Security Hardening
- SQL injection fixes (parameterized all dynamic queries)
- Rate limiting on auth endpoints
- Auth required on admin endpoints (`/db/*`, `/agent/reload-prompts`)

#### Featured Patients
- Selected 9 data-rich example patients with diverse medical histories
- Shared `featured-patients.ts` data file between WelcomeScreen and PatientSelector

### Feb 13 - Frontend Polish, IVFFlat Battles & DB Migration Planning

#### Morning: Frontend Completion
- **WelcomeScreen onboarding flow** — Full-page intro with project description
- **6-step UI tour** (`OnboardingTour.tsx`) — Walks new users through patient selector, chat, pipeline, observability panel
  - Includes "A Note on Performance" step (honest about cold starts and Bedrock latency)
- **Debug mode on by default** — Transparency is a feature, not a debug tool
- **Auto-open side panel** on small screens (chat wasn't visible on mobile)
- **Pipeline visualization fixes** — Correct model names (Sonnet/Haiku, not Ollama), proper step transitions, cleaned null details
- **LangSmith removal** — Stripped all frontend LangSmith integration (6 files, -170 lines). Not needed with CloudWatch.

#### Backports from atlas_mcp (formerly hc_ai_mcp)
- Timeline `ORDER BY` fix (dates were unsorted)
- Reranker score propagation to frontend
- Metadata key whitelist (cleaned noisy fields from display)

#### The IVFFlat Saga

The vector index became the final boss of the deployment.

**Background**: 7.7M embedding vectors (1024 dimensions) in PostgreSQL. Without an index, every query does a sequential scan — reading all 7.7M rows. An IVFFlat index groups vectors into clusters ("lists") so queries only scan a fraction.

**Attempt 1** (100 GB storage, 2 GB maintenance_work_mem):
- Failed immediately: PostgreSQL needs `maintenance_work_mem` ≥ 2075 MB for this dataset
- Error: insufficient memory for the number of centroids

**Attempt 2** (100 GB storage, 3 GB maintenance_work_mem):
- Ran for a while, then: **disk full**
- IVFFlat build writes ~31 GB index file + ~30 GB temp sort files
- 100 GB wasn't even close

**Attempt 3** (150 GB storage, 3 GB maintenance_work_mem, lists=2775):
- Ran for 3 hours 28 minutes before manual kill
- Phase 1 (k-means centroids): 2.5 hours, disk flat at 61 GB — all in RAM
- Phase 2 (writing vectors to lists): Disk growth exploded
  - 3h 00m: 88 GB
  - 3h 10m: 97 GB
  - 3h 15m: 101 GB (12 GB free)
  - 3h 20m: 105 GB (5 GB free on EBS, dropping fast)
- **Killed** to prevent storage-full catastrophe
- After kill: instantly back to 61 GB (PostgreSQL rollback is clean)

**Key insight**: `pg_database_size()` doesn't see the uncommitted index file. EBS fills ~30 GB faster than Postgres reports. You have to monitor EBS directly.

**Another key insight**: RDS has a 6-hour cooldown between storage modifications. You can't emergency-expand during a build. You have to plan ahead.

**Decision**: Expand to 250 GB (comfortable headroom), rebuild with `lists=512` (faster build, same index size, fine for portfolio — scans ~4.5% per query instead of 100%). Then migrate to a fresh smaller instance (120 GB, t4g.small) to avoid permanently bloated storage.

#### Probes Update
- Changed `SET ivfflat.probes = 53` → `SET ivfflat.probes = 23` in `postgres.py`
- probes = sqrt(lists): sqrt(512) ≈ 23
- Deployed via CI/CD

#### Current State (End of Feb 13)
- Storage expansion to 250 GB queued (waiting for 6-hour cooldown)
- IVFFlat build planned with lists=512
- DB migration to smaller instance planned (dump/restore via temp EC2)
- ECS at 0 tasks (scaled down during index work)
- Frontend fully polished and deployed on Vercel

---

## Hurdles & How They Were Overcome

### 1. The Hallucination Crisis (Feb 4)
**Problem**: The LLM was copying example medical data from prompt templates into responses — reporting conditions the patient didn't have.
**Root cause**: `prompts.yaml` contained real medical data as examples (Type 2 Diabetes E11.9, Hypertension 38341003). The 8B model couldn't distinguish examples from real retrieval results.
**Fix**: Three-pronged — (1) replaced all examples with placeholders like `[CONDITION_NAME]`, (2) upgraded from llama3.1:8b to qwen2.5:32b, (3) added anti-hallucination instructions to Response Synthesizer.
**Lesson**: Small models (8B) cannot distinguish few-shot examples from real data. Use 32B+ for complex medical prompts, or never put realistic data in your prompts.

### 2. Patient Data Buried in Noise (Feb 4)
**Problem**: Searching for Danial Larsen's conditions returned 5000+ results from all patients. His 2 Condition chunks were buried among thousands of Observations.
**Fix**: SQL-level patient_id filtering before semantic search. Also added auto resource type detection (keywords like "conditions" → filter to Condition resources).
**Impact**: Accuracy jumped from 0.513 to 0.83.

### 3. RDS Storage Death Spiral (Feb 10-13)
**Problem**: RDS storage can only increase, never decrease. Each expansion has a 6-hour cooldown. Started at 50 GB.
**Timeline**: 50 GB (full) → 100 GB (index attempt, full) → 150 GB (index attempt, nearly full) → 250 GB (planned)
**Lesson**: For vector databases, estimate peak disk usage (data + index + WAL + sort files) before choosing storage. IVFFlat needs ~2x the final index size during build.

### 4. The Connection Leak (Feb 10)
**Problem**: 30 active DB connections, 80% CPU on a db.t4g.medium.
**Root cause**: Two separate SQLAlchemy engines (auth + database routers), and a patient list endpoint scanning 132K JSONB rows on every page load.
**Fix**: (1) Replaced API call with static JSON served from CDN, (2) consolidated into a single connection pool.

### 5. ALB Killing SSE Streams (Feb 12)
**Problem**: AWS ALB has a 60-second idle timeout by default. Sonnet needs more than 60s to reason through complex medical queries. SSE streams were dying mid-response.
**Fix**: Increased ALB idle timeout to 300s. Added backend keepalive pings every 15s via asyncio.Queue so the connection is never "idle."

### 6. Text Splitting Regression (Feb 10)
**Problem**: EC2 embedding instance was missing `langchain-text-splitters`. The script fell back to blind `json_text[i:i+1000]` character splits — cutting mid-JSON, mid-word.
**Impact**: All 132K patients (both embedding runs) have suboptimal chunks.
**Decision**: Not re-embedding. The data is at least consistent, retrieval quality is acceptable for portfolio, and re-embedding would cost another ~$36.

### 7. Bedrock Cost Surprise (Feb 10-11)
**Problem**: Bedrock Titan embedding has no batch API — one `invoke_model` call per text chunk. At 7.7M chunks, costs add up fast.
**Spent**: ~$36 total ($21 first run + $15 second run)
**Decision**: Stopped at 77% coverage (102,718 of 132,842 patients). Sufficient for demo purposes.

### 8. The IVFFlat Final Boss (Feb 13)
**Problem**: 3 failed index build attempts over 6+ hours of wall-clock time.
**Key learnings**: (1) IVFFlat build has invisible disk overhead not reported by `pg_database_size()`, (2) the write phase grows disk exponentially, (3) RDS cooldown prevents emergency expansion, (4) lists count doesn't change index size — only build speed and query scan percentage.
**Solution**: Plan for 250 GB (100 GB headroom), use lists=512 (faster build), then migrate to a fresh 120 GB instance after.

---

## Key Milestones

| Date | Milestone |
|------|-----------|
| Jan 9 | Project started — first commit |
| Jan 13 | Embeddings pipeline complete |
| Jan 16 | First working agent + frontend |
| Jan 19 | Multi-agent architecture (Researcher/Validator/Responder) |
| Jan 27 | RAG feature complete |
| Jan 28 | Working prototype |
| Feb 2 | Production-ready locally (final RAGAS tests) |
| Feb 4 | Hallucination crisis identified and fixed, model upgrade to 32B |
| Feb 5 | Agent cleanup complete, ready for AWS |
| Feb 9 | Frontend UX overhaul, containerization, CI pipeline, MIT license |
| Feb 10 | RDS deployed, 83K patients embedded, first storage crisis |
| Feb 11 | Bedrock models configured, production fixes deployed (v5) |
| Feb 12 | CI/CD pipeline, CloudWatch observability, security hardening |
| Feb 13 | Frontend polish complete, IVFFlat index work begins |

---

## Architecture Evolution

### Phase 1: POC (Week 1)
```
FHIR JSON → Chunker → Embeddings → PostgreSQL pgvector
```

### Phase 2: Basic Agent (Week 2)
```
User Query → Single Agent → Response
```

### Phase 3: Multi-Agent (Week 2-3)
```
User Query → Researcher → Validator → Responder → Response
```

### Phase 4: Production Local (Week 4-5)
```
Frontend → Patient Selection → Auto-Injection → Multi-Agent Graph → Streaming Response
(Ollama qwen2.5:32b, local PostgreSQL)
```

### Phase 5: AWS Production (Week 6-7)
```
Vercel Frontend → ALB → ECS Fargate → Bedrock Claude 3.5 → RDS PostgreSQL pgvector
                                    ↓
                     Secrets Manager, CloudWatch, GitHub Actions CI/CD
```

---

## Technology Decisions & Rationale

| Decision | Chosen | Alternatives Considered | Why |
|----------|--------|------------------------|-----|
| Vector DB | PostgreSQL + pgvector | Pinecone, Weaviate, Qdrant | Already needed Postgres for raw FHIR storage; avoid extra service |
| Embedding model (local) | mxbai-embed-large (1024d) | all-MiniLM-L6-v2 | Better performance on medical text at the cost of larger vectors |
| Embedding model (prod) | Bedrock Titan v2 (1024d) | OpenAI ada-002, Cohere | AWS-native, no API key management, same dims |
| LLM (local) | qwen2.5:32b via Ollama | llama3.1:8b, mixtral:8x7b | Best instruction-following for medical prompts on consumer GPU |
| LLM (prod) | Claude 3.5 Sonnet + Haiku | GPT-4, Claude 3 Opus | Cost-optimized: Sonnet for reasoning, Haiku for synthesis |
| Frontend | Next.js 16 + React 19 | Remix, SvelteKit | Most familiar, strong SSE support, Vercel deployment |
| Hosting | ECS Fargate + ALB | EC2, Lambda, App Runner | Right-sized for always-on API with streaming SSE |
| Frontend hosting | Vercel | Amplify, S3+CloudFront | Free tier, instant deploys, better DX than Amplify |
| Index type | IVFFlat | HNSW | HNSW needs ~41 GB maintenance_work_mem — impossible on t4g.medium |
| Search strategy | Hybrid (BM25 + semantic) | Pure semantic | FHIR data is structured — BM25 catches exact resourceType/code matches |

---

## Cost Evolution

| Phase | Monthly Cost | Notes |
|-------|-------------|-------|
| Local dev (Jan-Feb 4) | $0 | Ollama on local GPU, local Postgres |
| AWS initial (Feb 10) | ~$95 | t4g.medium + 50GB + ECS + ALB |
| AWS peak (Feb 10-13) | ~$115 | t4g.medium + 150GB + embedding EC2 |
| AWS target (post-migration) | ~$75 | t4g.small + 120GB (fresh instance) |

One-time costs:
- Bedrock Titan embedding: ~$36 (102K patients)
- EC2 embedding instance: ~$2 (t3.medium, ~48 hours)

---

## Lessons Learned

### Agent & LLM
1. **Small models hallucinate from examples** — 8B models copy prompt examples as real data. Use 32B+ or never put realistic data in prompts.
2. **SQL-level filtering required** — Post-hoc Python filtering misses sparse patient data. Filter at the database level.
3. **Session history can pollute** — Old hallucinated responses leak into new sessions and compound the problem.
4. **Validator can harm** — With small models, validation loops cause more problems than they solve. Switched to simple mode (Researcher → Responder only).
5. **Hybrid search matters for structured data** — Pure semantic search buries exact matches. BM25 catches FHIR resourceType and code fields.

### AWS & Infrastructure
6. **RDS storage only goes up** — Plan generously. You can't shrink it, and there's a 6-hour cooldown between expansions.
7. **IVFFlat build needs 2x headroom** — The build process uses ~30 GB of invisible EBS space beyond what `pg_database_size()` reports.
8. **ALB idle timeout kills long SSE** — Default 60s is too short for LLM reasoning. Increase to 300s and add keepalive pings.
9. **Connection pooling matters** — Two separate engines doubled connection count. Consolidate everything into one pool.
10. **Static files beat API calls** — Serving 91K patient records from CDN JSON is infinitely faster and more reliable than scanning a database table.
11. **HNSW is a luxury** — At 7.7M vectors with 1024 dims, HNSW needs ~41 GB maintenance_work_mem. IVFFlat is the practical choice for constrained instances.
12. **Estimate embedding costs before starting** — Bedrock Titan has no batch API. At 7.7M chunks, costs add up to ~$36 even with a cheap model.

### Process
13. **Claude Code + SSH = travel-compatible development** — Shipped 5 commits from a travel day.
14. **CI/CD saves sanity** — Once the pipeline exists, every push deploys automatically. The overhead of setting it up pays for itself immediately.
15. **Transparency is a feature** — Debug mode on by default, performance disclaimers in the tour, real metrics in the UI. Honest about limitations.

---

## Files by Development Phase

### Core Infrastructure
- `api/database/postgres.py` — Vector store, hybrid search, IVFFlat probes
- `api/embeddings/` — FHIR embedding pipeline
- `api/retrieval/` — Cross-encoder reranking

### Agent System
- `api/agent/multi_agent_graph.py` — LangGraph workflow
- `api/agent/prompts.yaml` — All agent prompts
- `api/agent/config.py` — Bedrock model configuration
- `api/agent/tools/` — Medical domain tools
- `api/agent/tools/context.py` — Patient context auto-injection

### Frontend
- `frontend/src/app/page.tsx` — Main chat interface
- `frontend/src/hooks/useChat.ts` — Chat state management
- `frontend/src/components/OnboardingTour.tsx` — 6-step tutorial
- `frontend/src/components/WelcomeScreen.tsx` — Onboarding flow
- `frontend/src/components/workflow/` — Pipeline visualization

### Infrastructure
- `.github/workflows/` — CI/CD (lint, build, deploy)
- `Dockerfile` — Backend containerization
- `infra/cloudwatch-dashboard.json` — AWS monitoring
- `api/database/cloudwatch.py` — CloudWatch metrics API

### Evaluation
- `POC_RAGAS/` — RAGAS evaluation framework
- `scripts/batch_embed_bedrock.py` — Bedrock embedding script

### Documentation
- `docs/PROJECT_HISTORY.md` — This file
- `docs/DETAILED_CHANGELOG.md` — File-level git history
- `docs/aws-migration-analysis.md` — Cost analysis
- `CLAUDE.md` — Project onboarding for AI assistance
