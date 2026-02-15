# Atlas — AWS Migration Analysis

Cross-reference of the Obsidian 3-month project plan, Atlas kanban, AWS Flowchart canvas, and actual codebase state. This document covers what's done, what's left, and a recommended AWS deployment path.

---

## 1. Plan vs Reality — Completion Status

### Month 1: Production RAG Backend — COMPLETE

| Week | Planned | Actual Status |
|------|---------|---------------|
| **Week 1** — Data Ingestion | FastAPI + Go pipeline, semantic chunking | **Done.** Go FHIR parser (`POC_embeddings/main.go`), RecursiveJsonSplitter (823 avg chars, 293 tokens/chunk), `batch_embed_patients.py` with async batching, retry queue, duplicate detection. Tested 4 chunking strategies — recursive JSON won at 6.6s for 76k chunks. |
| **Week 2** — PostgreSQL + pgvector | Hybrid search, HNSW, relational + vector joins | **Done.** `api/database/postgres.py` — 1024-dim embeddings (mxbai-embed-large), hybrid BM25 + semantic at 50/50 weights, metadata filtering by patient_id and resource_type. SQLite dead-letter queue for failed chunks. |
| **Week 3** — Cross-Encoder Reranking | BGE-Reranker, <500ms latency | **Done.** `api/retrieval/cross_encoder.py` — sentence-transformers/all-MiniLM-L6-v2, batch scoring, CUDA auto-detection. Integrated into retrieval pipeline. |
| **Week 4** — Session Memory | Redis → DynamoDB | **Done.** `api/session/store_dynamodb.py` — two DynamoDB tables (`hcai_session_turns`, `hcai_session_summary`), 7-day TTL, last-N retrieval. History injection disabled by default to prevent cross-session pollution. |

**Deviation from plan:** Semantic chunking was explored but recursive JSON chunking was chosen instead (60x faster). Redis was dropped for DynamoDB (cost). BM25 is a custom implementation, not Elasticsearch.

---

### Month 2: Agentic Reasoning & Tooling — MOSTLY COMPLETE

| Week | Planned | Actual Status |
|------|---------|---------------|
| **Week 1** — Agentic Reasoning (LangGraph) | ReAct loop, tool selection, stopping conditions | **Done.** `api/agent/multi_agent_graph.py` — LangGraph DAG with query classification, researcher, validator, responder nodes. Death-loop prevention, search trajectory tracking. Simple mode (2 nodes) and complex mode (3 nodes, 15 max iterations). |
| **Week 2** — Tool Use & Function Calling | JSON schemas, FHIR/HL7 APIs | **Done.** 24 tools across 6 categories: patient retrieval, terminology (ICD-10, LOINC, RxNorm), FDA drug safety (recalls, shortages, FAERS), clinical calculators (eGFR, BMI, BSA, creatinine clearance, dosage validation, drug interactions), research (PubMed, ClinicalTrials.gov, WHO). |
| **Week 3** — Multi-Agent Orchestration | Supervisor → Researcher + Validator | **Done.** Classification node routes to medical vs conversational path. Researcher uses tools, optional Validator checks codes. Response synthesizer formats output. |
| **Week 4** — MCP Server | Python/Go MCP server for IDE integration | **Done.** Separate repo [`atlas_mcp`](https://github.com/rsanandres/atlas_mcp) — FastMCP server with 15 tools (agent, retrieval, session, embeddings), stdio + streamable-http transport, works with Claude Desktop and Cursor. Already supports `LLM_PROVIDER=bedrock`. |

**Deviation from plan:** MCP was built as a separate companion repo rather than embedded in hc_ai. The agent system is significantly more sophisticated than planned — 24 tools vs the original "a few tools," auto-resource detection, patient context auto-injection, PII masking on input/output. CrewAI was dropped for LangGraph (correct call).

---

### Month 3: Enterprise Infra & Evaluation — PARTIALLY COMPLETE

| Week | Planned | Actual Status |
|------|---------|---------------|
| **Week 1** — RAGAS Evaluation | Automated evaluation harness | **Done (POC).** `POC_RAGAS/` has synthetic test generation, faithfulness/relevancy/noise-sensitivity metrics. Uses OpenAI for metric computation. Not integrated into CI. |
| **Week 2** — AWS Cloud Infra (CDK/Terraform) | ECS, OpenSearch, Bedrock, IAM, VPC endpoints | **NOT DONE.** No CDK, Terraform, CloudFormation, or any IaC. Docker compose for local only. |
| **Week 3** — Observability | LangSmith or CloudWatch dashboard | **Partial.** LangSmith trace integration exists (optional). Frontend observability panel shows health, DB stats, queue metrics. No CloudWatch. |
| **Week 4** — CI/CD & Production Rollout | GitHub Actions + eval suite | **NOT DONE.** No `.github/workflows/`. No automated testing in CI. |

---

### Summary Scorecard

| Area | Status | Effort Remaining |
|------|--------|-----------------|
| Data ingestion | Complete | — |
| Vector store + hybrid search | Complete | — |
| Cross-encoder reranking | Complete | — |
| Session memory (DynamoDB) | Complete | — |
| LangGraph multi-agent | Complete | — |
| 24 medical tools | Complete | — |
| Frontend (Next.js streaming) | Complete | — |
| PII masking (local) | Complete | — |
| Auth (JWT) | Complete | — |
| RAGAS evaluation | POC done | Integrate into CI |
| LangSmith observability | Partial | Add CloudWatch |
| MCP server | **Complete** | Done in [atlas_mcp](https://github.com/rsanandres/atlas_mcp) — 15 tools, stdio + HTTP transport |
| AWS infrastructure (IaC) | Not started | **Primary gap** |
| CI/CD pipeline | Not started | **Required for AWS** |

---

## 2. AWS Architecture — Canvas Analysis

Your Obsidian `AWS Flowchart.canvas` specifies this target architecture:

```
User → Website Chatbot
         ↓
    ALB / API Gateway
         ↓
    App Runner or EC2 (VPC)
         ↓
    ┌─────────────────────────────┐
    │  Researcher Agent (Haiku)   │←→ Tools (FDA, ICD-10, etc.)
    │          ↕                  │
    │  Validator Agent (Haiku)    │
    └─────────────────────────────┘
         ↓                ↓
    RDS PostgreSQL    Amazon Titan
    (pgvector)        (Embeddings)
         ↓
    DynamoDB          S3 (optional)
         ↓
    CloudWatch        Secret Store
         ↓
    Terraform (IaC)
```

---

## 3. Recommended AWS Migration Path

### What Changes vs Local

| Component | Local (Current) | AWS (Target) | Migration Complexity |
|-----------|----------------|--------------|---------------------|
| **LLM** | Ollama (qwen2.5:32b on 4090) | **Amazon Bedrock** (Claude Haiku / Sonnet) | Medium — swap `ChatOllama` for `ChatBedrock` in `models.py` |
| **Embeddings** | Ollama (mxbai-embed-large) | **Amazon Titan Embeddings v2** | Medium — swap embedding provider, re-embed all data (dim change: 1024→1024 or 1536) |
| **PostgreSQL** | Local Docker | **RDS PostgreSQL 16** + pgvector | Low — connection string change, enable pgvector extension |
| **DynamoDB** | DynamoDB Local (port 8001) | **DynamoDB** (native) | Low — remove `endpoint_url` override, IAM auth |
| **Compute** | `uvicorn` on localhost | **ECS Fargate** or **App Runner** | Medium — Dockerfile + task definition |
| **Frontend** | `npm run dev` on :3000 | **Amplify** or **S3 + CloudFront** | Low — `next build && next export` or SSR on Amplify |
| **Reranker** | Local sentence-transformers | **SageMaker Endpoint** or keep in-container | Medium — either deploy model or bundle in container |
| **PII Masking** | Local regex | **AWS Comprehend Medical** | Low — already scaffolded in `pii_masker/`, flip env var |
| **Secrets** | `.env` file | **Secrets Manager** / **Parameter Store** | Low |
| **Monitoring** | LangSmith + health checks | **CloudWatch** + LangSmith | Low — add CloudWatch log driver |

### What Does NOT Change

- LangGraph agent architecture (framework-agnostic)
- All 24 tools (they call external APIs, not local services)
- Frontend React components
- Session management logic (DynamoDB client stays the same)
- Hybrid search SQL (pgvector SQL is identical on RDS)
- RAGAS evaluation suite

---

## 4. Recommended Approach: Phased Migration

### Phase 1: Containerize & CI/CD (1 week)

**Why first:** You can't deploy what you can't build reproducibly.

1. **Multi-stage Dockerfile** for the FastAPI backend
   - Stage 1: Python dependencies + model downloads
   - Stage 2: Slim runtime image
   - Include reranker model in container (avoids SageMaker cost)

2. **Frontend Dockerfile** (or Amplify config)
   - Next.js production build
   - Environment variable injection for API URL

3. **GitHub Actions pipeline**
   - On PR: lint + `pytest api/agent/test_*.py`
   - On merge to main: build Docker image → push to ECR
   - Optional: run RAGAS eval suite as gate

4. **docker-compose.prod.yml** for local testing of the full stack

### Phase 2: Core AWS Infrastructure (1-2 weeks)

**Use Terraform** (your canvas says Terraform, and it's more portable than CDK).

```
Module layout:
terraform/
├── main.tf
├── variables.tf
├── outputs.tf
├── modules/
│   ├── networking/     # VPC, subnets, security groups
│   ├── database/       # RDS PostgreSQL + pgvector
│   ├── dynamodb/       # Session tables
│   ├── compute/        # ECS Fargate or App Runner
│   ├── frontend/       # Amplify or S3+CloudFront
│   └── monitoring/     # CloudWatch dashboards, alarms
```

**Networking:**
- VPC with public + private subnets across 2 AZs
- RDS in private subnet (no public access)
- ECS/App Runner in private subnet with ALB in public subnet
- VPC endpoints for Bedrock, DynamoDB, S3, Secrets Manager (keeps traffic off internet — HIPAA requirement per your plan)

**Database:**
- RDS PostgreSQL 16, `db.t4g.medium` (2 vCPU, 4GB RAM — sufficient for pgvector with your data size)
- Enable pgvector extension post-creation
- Automated backups, 7-day retention
- Run `batch_embed_patients.py` one-time to populate (or pg_dump/pg_restore from local)

**DynamoDB:**
- Two tables: `hcai_session_turns`, `hcai_session_summary`
- On-demand pricing (pennies at your scale)
- TTL enabled (7 days, already configured in code)

### Phase 3: Swap LLM & Embeddings to Bedrock (1 week)

This is the most impactful change. Your code already abstracts the LLM provider.

**LLM swap** (`api/agent/models.py`):
```python
# Current
from langchain_ollama import ChatOllama
llm = ChatOllama(model="qwen2.5:32b", base_url=OLLAMA_BASE_URL)

# AWS
from langchain_aws import ChatBedrock
llm = ChatBedrock(
    model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
    region_name="us-west-2",
    model_kwargs={"temperature": 0.1, "max_tokens": 4096}
)
```

**Embedding swap** (`api/embeddings/` + `api/database/postgres.py`):
```python
# Current
from langchain_ollama import OllamaEmbeddings
embeddings = OllamaEmbeddings(model="mxbai-embed-large:latest")

# AWS
from langchain_aws import BedrockEmbeddings
embeddings = BedrockEmbeddings(
    model_id="amazon.titan-embed-text-v2:0",
    region_name="us-west-2"
)
```

**Critical decision — embedding dimensions:**
- Current: mxbai-embed-large = 1024 dimensions
- Titan Embed v2 = 1024 dimensions (configurable, max 1536)
- If you keep 1024, you can potentially migrate existing vectors without re-embedding
- If you change dimensions, you must re-embed all data and update the pgvector column

**Recommendation:** Use Titan at 1024 dimensions to match current schema. Re-embed anyway since the model change means vectors aren't compatible, but at least the schema stays the same.

**Model choice for agents:**
| Use Case | Recommended Model | Cost (per 1M tokens) |
|----------|------------------|---------------------|
| Researcher agent | Claude 3.5 Haiku | ~$0.25 input / $1.25 output |
| Validator agent | Claude 3.5 Haiku | Same |
| Response synthesizer | Claude 3.5 Sonnet | ~$3 input / $15 output |
| Embeddings | Titan Embed v2 | ~$0.02 |

Your canvas says "Claude Haiku" for both agents — Haiku is the right call for cost. Consider Sonnet for the response synthesizer if quality matters more than latency on the final answer.

### Phase 4: Compute Deployment (1 week)

**Recommendation: ECS Fargate** over App Runner.

| Factor | ECS Fargate | App Runner |
|--------|-------------|------------|
| VPC integration | Full (private subnets, VPC endpoints) | Limited (VPC connector needed) |
| Task sizing | Flexible (0.25–16 vCPU, up to 120GB) | Fixed tiers |
| Secrets | Native Secrets Manager integration | Basic |
| Health checks | ALB target group health checks | Built-in |
| Cost | Pay per vCPU-second | Pay per vCPU-second |
| HIPAA | BAA-eligible | BAA-eligible |

**Task definition:**
- Backend: 1 vCPU, 4GB RAM (includes reranker model in memory)
- Frontend: 0.5 vCPU, 1GB RAM (or use Amplify instead)
- ALB with HTTPS (ACM certificate)
- Auto-scaling: 1-3 tasks based on CPU

**Alternative for frontend:** AWS Amplify handles Next.js natively (SSR, ISR, static). Simpler than running a container. Point your domain at Amplify, set `NEXT_PUBLIC_API_URL` to the ALB endpoint.

### Phase 5: Security & Compliance (ongoing)

- **IAM:** Least-privilege roles for ECS tasks (Bedrock invoke, RDS connect, DynamoDB read/write, Secrets Manager read)
- **PII Masking:** Flip `PII_MASKER_PROVIDER=comprehend_medical` — already scaffolded in `api/agent/pii_masker/`
- **Secrets Manager:** Move all env vars (DB creds, JWT secret, API keys)
- **VPC Endpoints:** Bedrock, DynamoDB, S3, Secrets Manager — ensures data never traverses public internet
- **Encryption:** RDS encryption at rest (default), DynamoDB encryption at rest (default), ALB TLS termination
- **Audit:** CloudTrail for API call logging

---

## 5. Cost Estimate (Monthly)

| Service | Spec | Est. Cost |
|---------|------|-----------|
| RDS PostgreSQL | db.t4g.medium, 50GB gp3 | ~$35 |
| ECS Fargate (backend) | 1 vCPU, 4GB, always-on | ~$55 |
| ECS Fargate or Amplify (frontend) | 0.5 vCPU, 1GB or Amplify free tier | ~$15-25 |
| DynamoDB | On-demand, low traffic | ~$1-5 |
| Bedrock (Claude Haiku) | ~50k queries/mo estimate | ~$15-30 |
| Bedrock (Titan Embeddings) | One-time re-embed + queries | ~$36 actual (see note) |
| ALB | 1 ALB, low traffic | ~$20 |
| CloudWatch | Basic metrics + logs | ~$5-10 |
| Secrets Manager | 5-10 secrets | ~$3 |
| ECR | Container storage | ~$1 |
| NAT Gateway | Required for private subnet internet | ~$35 |
| **Total** | | **~$185-225/mo** |

> **Embedding cost note (2026-02-11):** Titan Embed v2 one-time cost was ~$36 for embedding ~102,718 of 132,842 patients (77%). Embedding was stopped early to cap upfront costs. The remaining ~30K patients can be embedded later if more complete coverage is desired — all raw FHIR data remains in `fhir_raw_files`.

**Cost reduction options:**
- Use Fargate Spot for non-critical workloads (up to 70% savings)
- Schedule scale-to-zero at night if it's a portfolio project
- Skip NAT Gateway by using VPC endpoints exclusively (saves $35/mo)
- Use Amplify free tier for frontend (saves $15-25/mo)

---

## 6. What to Skip or Deprioritize

| Item | Recommendation | Reason |
|------|---------------|--------|
| **MCP Server** | **Done** — see [atlas_mcp](https://github.com/rsanandres/atlas_mcp). Separate repo with FastMCP server (stdio + streamable-http), 15 tools, LangGraph agent, hybrid search, reranker, session management. Works with Claude Desktop and Cursor. Already supports Bedrock via `LLM_PROVIDER=bedrock`. |
| **OpenSearch** | Skip | Your pgvector hybrid search already works. OpenSearch adds cost and complexity for marginal gain at your data scale. |
| **SageMaker for reranker** | Skip | Bundle reranker in container. SageMaker endpoint adds $50+/mo for a model that runs in <500ms on CPU. |
| **Complex graph mode** | Deprioritize | Simple mode is more reliable. Enable complex mode as a feature flag for demos. |
| **CSV ingestion** | Skip | FHIR JSON is the standard. CSV adds scope without portfolio value. |
| **Production Comprehend Medical** | Optional | Nice for HIPAA story, but local regex masker works. Flip the switch if you want to demo it. |

---

## 7. Recommended Order of Operations

```
1. Dockerfile + docker-compose.prod.yml     (can test locally)
2. GitHub Actions CI pipeline               (lint + test on PR)
3. Terraform: VPC + RDS + DynamoDB          (data layer first)
4. Migrate data: pg_dump → RDS              (or re-embed)
5. Swap LLM/embeddings to Bedrock           (code changes in models.py)
6. Terraform: ECS Fargate + ALB             (deploy backend)
7. Frontend: Amplify or ECS                 (deploy frontend)
8. Secrets Manager + IAM lockdown           (security pass)
9. CloudWatch dashboards + alarms           (observability)
10. GitHub Actions CD: ECR push → ECS deploy (automated deploys)
```

Steps 1-2 are prerequisites that also make your repo look production-ready to recruiters. Steps 3-7 are the actual migration. Steps 8-10 are polish.

---

## 8. Code Changes Required — Detailed Dual-Mode Specifications

Goal: every file should work in both local (Ollama + Docker) and AWS (Bedrock + RDS) mode, controlled entirely by environment variables. No code forks, no `if aws:` branches scattered around — just provider abstractions that already exist being made complete.

---

### File 1: `api/agent/config.py` — LLM Provider

**Current state:** Already has dual-mode support. `get_llm()` reads `LLM_PROVIDER` and returns either `ChatOllama` or `ChatBedrock`. Bedrock branch maps `"sonnet"` and `"haiku"` model names to full model IDs.

```python
# Current code (lines 31-64) — ALREADY WORKS for both modes
def get_llm() -> Any:
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    max_tokens = _int_env("LLM_MAX_TOKENS", 2048)

    if provider == "bedrock":
        model_name = os.getenv("LLM_MODEL", "haiku").lower()
        if model_name == "sonnet":
            model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        else:
            model_id = "anthropic.claude-3-5-haiku-20241022-v2:0"
        return ChatBedrock(
            model_id=model_id,
            model_kwargs={"temperature": temperature, "max_tokens": max_tokens},
        )

    # Default: Ollama
    model = os.getenv("LLM_MODEL", "chevalblanc/claude-3-haiku:latest")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    return ChatOllama(model=model, base_url=base_url, ...)
```

**What to change:** Nothing for basic functionality. Optional improvements:
- Add `AWS_REGION` support to `ChatBedrock` (currently uses boto3 default)
- Update default Ollama model from `chevalblanc/claude-3-haiku:latest` to `qwen2.5:32b` to match what you actually run
- Add Bedrock region param: `region_name=os.getenv("AWS_REGION", "us-east-1")`

**Local env:** `LLM_PROVIDER=ollama`, `LLM_MODEL=qwen2.5:32b`
**AWS env:** `LLM_PROVIDER=bedrock`, `LLM_MODEL=haiku`

---

### File 2: `api/embeddings/utils/helper.py` — Embedding Provider

**Current state:** Already has full tri-mode support (lines 40-75). Reads `EMBEDDING_PROVIDER` env var and routes to `_get_embeddings_ollama()`, `_get_embeddings_nomic()`, or `_get_embeddings_bedrock()`. The Bedrock implementation (lines 568-625) already uses `boto3.client("bedrock-runtime")`, calls `invoke_model()` with Titan's `{"inputText": "..."}` format, and extracts the `"embedding"` key.

```python
# Current code — ALREADY WORKS for both modes
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama").lower()

# Bedrock init (lines 63-72)
if EMBEDDING_PROVIDER == "bedrock":
    import boto3
    bedrock_runtime = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

# Provider routing (lines 450-460)
def get_embeddings(texts: list) -> list:
    if EMBEDDING_PROVIDER == "ollama":
        return _get_embeddings_ollama(texts)
    elif EMBEDDING_PROVIDER == "bedrock":
        return _get_embeddings_bedrock(texts)
    ...

# Bedrock implementation (lines 568-625)
def _get_embeddings_bedrock(texts: list) -> list:
    for text in texts:
        body = json.dumps({"inputText": text})
        response = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID, body=body, ...
        )
        result = json.loads(response["body"].read())
        embedding = result.get("embedding", [])
        embeddings.append(embedding)
    return embeddings
```

**What to change:** Nothing — this file is already fully dual-mode. The Bedrock path, Titan model ID, and dimension handling are all implemented.

**Local env:** `EMBEDDING_PROVIDER=ollama`, `OLLAMA_EMBED_MODEL=mxbai-embed-large:latest`
**AWS env:** `EMBEDDING_PROVIDER=bedrock`, `BEDROCK_EMBED_MODEL=amazon.titan-embed-text-v2:0`

**Critical note on re-embedding:** When switching from Ollama mxbai to Titan, you MUST re-embed all data. Even though both produce 1024-dim vectors, the vector spaces are incompatible. Run `batch_embed_patients.py` with `EMBEDDING_PROVIDER=bedrock` against the new RDS instance.

---

### File 3: `api/database/postgres.py` — Vector Store Connection

**Current state:** Reads connection params from env vars (lines 48-52). Builds the async connection string at line 281. Schema, table name, vector size are all constants at the top.

```python
# Current code (lines 48-59)
POSTGRES_USER = os.environ.get("DB_USER")
POSTGRES_PASSWORD = os.environ.get("DB_PASSWORD")
POSTGRES_HOST = os.environ.get("DB_HOST", "localhost")
POSTGRES_PORT = os.environ.get("DB_PORT", "5432")
POSTGRES_DB = os.environ.get("DB_NAME")

TABLE_NAME = "hc_ai_table"
VECTOR_SIZE = 1024
SCHEMA_NAME = "hc_ai_schema"

# Connection string (line 281)
connection_string = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
```

**What to change:** Nothing in the code — it's already fully parameterized. Just set the env vars.

**Local env:**
```
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=postgres
```

**AWS env:**
```
DB_HOST=hcai-db.xxxxxxxxxxxx.us-east-1.rds.amazonaws.com
DB_PORT=5432
DB_USER=hcai_admin
DB_PASSWORD=<from-secrets-manager>
DB_NAME=hcai
```

**RDS setup note:** After creating the RDS instance, you must enable pgvector:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```
The `initialize_vector_store()` function (line 257) handles creating the schema and table automatically.

**Optional improvement for AWS:** Add SSL mode for RDS connections. Currently the connection string doesn't enforce SSL. For production:
```python
# Add to connection string for RDS
if os.getenv("DB_SSL_MODE"):
    connection_string += f"?ssl={os.getenv('DB_SSL_MODE', 'require')}"
```

---

### File 4: `api/session/store_dynamodb.py` — Session Store

**Current state:** Already fully dual-mode (lines 107-118). When `endpoint_url` is set, it uses dummy credentials for DynamoDB Local. When `endpoint_url` is `None`, it uses the default AWS credential chain (IAM role, env vars, etc).

```python
# Current code (lines 107-118) — ALREADY WORKS for both modes
if endpoint_url:
    # Local DynamoDB - use dummy credentials
    self.resource = boto3.resource(
        "dynamodb", region_name=region_name,
        endpoint_url=endpoint_url,
        aws_access_key_id="dummy",
        aws_secret_access_key="dummy",
    )
else:
    # Real AWS - use default credential chain
    self.resource = boto3.resource("dynamodb", region_name=region_name)
```

The factory `build_store_from_env()` (line 536) reads `DDB_ENDPOINT` defaulting to `http://localhost:8001`.

**What to change:** For AWS, just unset or remove `DDB_ENDPOINT` from env. The code already handles this — when no endpoint URL is provided, it connects to real DynamoDB via IAM.

**Local env:**
```
DDB_ENDPOINT=http://localhost:8001
DDB_TURNS_TABLE=hcai_session_turns
DDB_SUMMARY_TABLE=hcai_session_summary
DDB_TTL_DAYS=7
DDB_AUTO_CREATE=true
```

**AWS env:**
```
# DDB_ENDPOINT is NOT SET — triggers real AWS path
AWS_REGION=us-east-1
DDB_TURNS_TABLE=hcai_session_turns
DDB_SUMMARY_TABLE=hcai_session_summary
DDB_TTL_DAYS=7
DDB_AUTO_CREATE=true
```

**No code changes needed.** The ECS task role just needs `dynamodb:*` on these two tables.

---

### File 5: `api/agent/pii_masker/` — PII Masking (3 files)

**Current state:** Already fully dual-mode with a factory pattern.

`factory.py` (full file, 17 lines):
```python
def create_pii_masker() -> PIIMaskerInterface:
    provider = os.getenv("PII_MASKER_PROVIDER", "local").lower()
    if provider in {"aws", "comprehend"}:
        return AWSComprehendMedicalMasker()
    return LocalPIIMasker()
```

`aws_masker.py` (full file, 42 lines) — already implemented:
```python
class AWSComprehendMedicalMasker(PIIMaskerInterface):
    def __init__(self) -> None:
        region = os.getenv("AWS_REGION", "us-east-1")
        self._client = boto3.client("comprehendmedical", region_name=region)

    def mask_pii(self, text: str) -> Tuple[str, Dict]:
        response = self._client.detect_phi(Text=text)
        # ... replaces PHI entities with [TYPE] placeholders
```

`local_masker.py` — regex-based fallback for EMAIL, PHONE, SSN, DATE patterns.

**What to change:** Nothing — flip the env var.

**Local env:** `PII_MASKER_PROVIDER=local`
**AWS env:** `PII_MASKER_PROVIDER=aws`

**IAM note:** ECS task role needs `comprehendmedical:DetectPHI` permission.

---

### File 6: `api/main.py` — Startup Diagnostics

**Current state:** `_startup_diagnostics()` (lines 51-85) hard-codes localhost URLs for health checks:
```python
requests.get("http://localhost:8000/agent/health", timeout=2)
requests.get("http://localhost:8000/retrieval/rerank/health", timeout=2)
requests.get("http://localhost:8001", timeout=2)  # DynamoDB Local
```

These will fail silently on AWS (they're wrapped in try/except), but they're noise in logs.

**What to change:** Make diagnostics environment-aware. The checks should use the same URLs the app is actually configured to use, or skip external checks on AWS where services are managed.

```python
# Suggested change
def _startup_diagnostics() -> None:
    ddb_endpoint = os.getenv("DDB_ENDPOINT")  # None on AWS
    is_local = ddb_endpoint is not None

    if is_local:
        # Only run localhost checks in local dev
        # ... existing checks ...
    else:
        # AWS: verify Bedrock access, RDS connectivity
        print(f"Running in AWS mode (region: {os.getenv('AWS_REGION', 'us-east-1')})")
```

**Local env:** No change
**AWS env:** Absence of `DDB_ENDPOINT` signals AWS mode

---

### File 7: `frontend/.env.local` → `frontend/.env.production`

**Current state:** `.env.local` only has LangSmith config:
```
NEXT_PUBLIC_LANGSMITH_API_KEY=lsv2_pt_...
NEXT_PUBLIC_LANGSMITH_API_URL=https://api.smith.langchain.com
```

The API URL defaults to `http://localhost:8000` throughout the frontend (hardcoded fallback in `axiosInstance.ts:6`, `agentApi.ts:5`, `streamAgent.ts:5`, `useChat.ts:158`).

**What to change:** Create `.env.production` with the ALB/API Gateway URL. The code already reads `NEXT_PUBLIC_API_URL` — it just needs to be set.

**Local env (`.env.local`):**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_LANGSMITH_API_KEY=lsv2_pt_...
NEXT_PUBLIC_LANGSMITH_API_URL=https://api.smith.langchain.com
```

**AWS env (`.env.production`):**
```
NEXT_PUBLIC_API_URL=https://api.vectorhealth.app
NEXT_PUBLIC_LANGSMITH_API_KEY=lsv2_pt_...
NEXT_PUBLIC_LANGSMITH_API_URL=https://api.smith.langchain.com
```

If using Amplify, set `NEXT_PUBLIC_API_URL` in the Amplify environment variables console. If using ECS, bake it into the Docker build or pass at runtime.

---

### Summary: What's Already Done vs What Needs Work

| File | Local Mode | AWS Mode | Code Change Needed? |
|------|-----------|----------|-------------------|
| `api/agent/config.py` | `LLM_PROVIDER=ollama` | `LLM_PROVIDER=bedrock` | **No** — already implemented |
| `api/embeddings/utils/helper.py` | `EMBEDDING_PROVIDER=ollama` | `EMBEDDING_PROVIDER=bedrock` | **No** — Bedrock path fully coded |
| `api/database/postgres.py` | `DB_HOST=localhost` | `DB_HOST=<rds-endpoint>` | **No** — parameterized via env vars |
| `api/session/store_dynamodb.py` | `DDB_ENDPOINT=http://localhost:8001` | `DDB_ENDPOINT` unset | **No** — already has conditional logic |
| `api/agent/pii_masker/factory.py` | `PII_MASKER_PROVIDER=local` | `PII_MASKER_PROVIDER=aws` | **No** — factory + AWS masker exist |
| `api/main.py` | Checks localhost | Should skip local checks | **Yes** — minor: make diagnostics env-aware |
| `frontend/.env.production` | `localhost:8000` | `https://api.vectorhealth.app` | **Yes** — create the file (1 line) |

**Bottom line:** 5 of 7 files need zero code changes — just different env vars. Only `api/main.py` needs a minor tweak to the startup diagnostics, and the frontend needs a `.env.production` file created. Your abstractions are already built for dual-mode.

---

## 9. Cost Optimization — Chosen Architecture

After reviewing the production-grade architecture in Sections 2 and 5, a cost-optimized variant was chosen for initial deployment. This keeps all the same AWS services but drops the enterprise networking layer that drives up cost without adding value for a portfolio/demo workload.

### Original vs Chosen Architecture

| Component | Original (Production-Grade) | Chosen (Cost-Optimized) |
|-----------|---------------------------|------------------------|
| **VPC networking** | Private subnets, NAT Gateway, VPC endpoints | Default VPC, public subnets |
| **RDS instance** | db.t4g.medium (2 vCPU, 4GB) | db.t4g.micro (2 vCPU, 1GB) |
| **RDS availability** | Multi-AZ | Single-AZ |
| **ECS backend** | 1 vCPU, 4GB | 0.5 vCPU, 1GB (or scale-to-zero) |
| **Frontend** | ECS Fargate (0.5 vCPU, 1GB) | Amplify free tier |
| **ALB** | ALB in private subnet | ALB in public subnet |
| **DynamoDB** | On-demand | On-demand (unchanged) |
| **Bedrock** | Claude Haiku + Titan Embeddings | Claude Haiku + Titan Embeddings (unchanged) |
| **Secrets Manager** | Same | Same (unchanged) |
| **CloudWatch** | Same | Same (unchanged) |

### What Was Dropped and Why

| Dropped Item | Monthly Savings | Trade-off |
|-------------|----------------|-----------|
| **NAT Gateway** | ~$35 | Services in public subnets reach the internet directly. No data-processing charges. |
| **VPC endpoints** | ~$8-15 | Not needed without private subnets. Services use public AWS endpoints over the internet. |
| **Multi-AZ RDS** | ~$15 | Single point of failure for the database. Acceptable for a demo — no SLA to meet. |
| **db.t4g.medium → micro** | ~$20 | 1GB RAM is sufficient for low-traffic pgvector queries. Can scale up later if needed. |
| **Private subnets** | $0 (indirect) | Simplifies networking. Security groups still restrict access. No compliance requirement. |
| **ECS frontend task** | ~$15-25 | Amplify free tier handles Next.js SSR. Eliminates a whole Fargate task. |

### Revised Monthly Cost Estimate (Updated 2026-02-14 with actuals)

| Service | Spec | Est. Cost |
|---------|------|-----------|
| RDS PostgreSQL | db.t4g.small, single-AZ, 250GB gp3 | ~$46 |
| ECS Fargate (backend) | 0.5 vCPU, 2GB, always-on | ~$15 |
| Vercel (frontend) | Free tier (SSR) | ~$0 |
| Bedrock (Claude Haiku) | Query-time inference only | ~$1-2 |
| ALB | 1 ALB, low traffic | ~$16 |
| VPC | Public subnets only, no NAT | ~$3 |
| CloudWatch | Basic metrics + logs | ~$2-3 |
| Secrets Manager | 5 secrets | ~$1 |
| ECR | Container storage | ~$1 |
| **Total (recurring)** | | **~$85-87/mo** |

**One-time costs (February 2026):**

| Item | Cost | Notes |
|------|------|-------|
| Bedrock Titan Embeddings | ~$36 | 102,718 patients embedded (77% of 132,842) |
| Temp EC2 instances | ~$5 | Embedding + migration work |
| RDS t4g.medium time | ~$10 | Temporarily scaled up for IVFFlat index build |
| **Total one-time** | **~$51** | |

> **Why 250GB RDS storage?** IVFFlat index build for 7.7M vectors (1024-dim) peaks at ~161GB disk usage during construction. RDS storage can only increase, never decrease. The migration to a smaller instance was attempted via pg_dump/pg_restore but abandoned — pg_restore replays `CREATE INDEX` DDL, requiring the same peak disk on the target. The extra storage cost (~$10/mo over 120GB) was accepted as the pragmatic choice.

**Savings: ~$100-140/mo compared to the original estimate ($185-225/mo).**

### Production Upgrade Path

This is a deliberate choice for portfolio/demo deployment. The production path is fully documented in Sections 2-5 above. To upgrade for HIPAA or production use, add back:

1. **Private subnets + NAT Gateway** — move ECS tasks and RDS into private subnets, route outbound traffic through NAT
2. **Multi-AZ RDS** — enable in the RDS console or Terraform for automatic failover
3. **VPC endpoints** — add gateway endpoints for S3/DynamoDB and interface endpoints for Bedrock, Secrets Manager, ECR
4. **Larger RDS instance** — scale to db.t4g.medium or db.t4g.large based on query load
5. **WAF on ALB** — add AWS WAF rules for OWASP top 10 protection

All application code remains identical — the upgrade is purely infrastructure configuration.
