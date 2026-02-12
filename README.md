# Atlas AI - Clinical Intelligence Platform

A full-stack healthcare AI system that lets clinicians query patient records using natural language. Built with a multi-agent RAG architecture, hybrid vector search, and real-time streaming — processing FHIR clinical data across 10 resource types with 20+ specialized medical tools.

## Architecture

```
                                    ┌─────────────────────────────────┐
                                    │         Next.js Frontend        │
                                    │   Chat  ·  Pipeline  ·  Observ  │
                                    └──────────────┬──────────────────┘
                                                   │ SSE Stream
                                    ┌──────────────▼──────────────────┐
                                    │        FastAPI Gateway          │
                                    │   PII Masker  ·  Guardrails    │
                                    └──────────────┬──────────────────┘
                                                   │
                          ┌────────────────────────▼────────────────────────┐
                          │              LangGraph Multi-Agent              │
                          │                                                │
                          │  ┌────────────┐  ┌───────────┐  ┌──────────┐  │
                          │  │ Researcher │→ │ Validator │→ │ Responder│  │
                          │  └─────┬──────┘  └───────────┘  └──────────┘  │
                          │        │                                       │
                          │  ┌─────▼──────────────────────────────────┐   │
                          │  │            20+ Medical Tools           │   │
                          │  │  FDA · ICD-10 · LOINC · RxNorm · GFR  │   │
                          │  │  PubMed · Clinical Trials · WHO Stats │   │
                          │  └────────────────────┬───────────────────┘   │
                          └───────────────────────┼───────────────────────┘
                                                  │
                    ┌─────────────────┬───────────▼──────────┬──────────────┐
                    │                 │                      │              │
             ┌──────▼──────┐  ┌──────▼──────┐  ┌───────────▼──┐  ┌───────▼──────┐
             │  PostgreSQL │  │   Ollama     │  │  Cross-Encoder│  │   DynamoDB   │
             │  + pgvector │  │  qwen2.5:32b │  │   Reranker   │  │  Sessions    │
             │  1024-dim   │  │              │  │  MiniLM-L6   │  │  7-day TTL   │
             └─────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

## Key Features

### Multi-Agent RAG Pipeline
- Three-node LangGraph workflow: Researcher retrieves and reasons, Validator checks safety, Responder synthesizes
- Hybrid search combining BM25 keyword matching (50%) + semantic vector search (50%) with 1024-dim embeddings
- Cross-encoder reranking with MiniLM-L6-v2 for precision
- Auto-detects FHIR resource type from natural language (e.g., "medications" filters to MedicationRequest)

### 20+ Medical Tools
- **Patient data**: Hybrid retrieval search, chronological timeline views
- **Drug safety**: FDA labels, recalls, shortages, adverse event reports (openFDA)
- **Medical coding**: ICD-10 search/validation (NIH), LOINC lookup (Regenstrief), RxNorm resolution
- **Clinical calculators**: eGFR (CKD-EPI 2021), BMI, BSA (Mosteller), creatinine clearance (Cockcroft-Gault)
- **Safety**: Drug interaction checking, dosage validation against FDA labels
- **Research**: PubMed articles, ClinicalTrials.gov, WHO global health statistics

### Real-Time Streaming UI
- Server-Sent Events stream each agent step as it executes
- Pipeline visualization with real wall-clock timing per step
- Expandable step details: documents retrieved, tools invoked, sources cited, relevance scores
- Source cards with score bars, full FHIR metadata, and expand/collapse

### Safety & Privacy
- PII masking on both input and output (patient names, SSNs, dates)
- Guardrails validation layer for response safety checks
- Patient context auto-injection prevents cross-patient data leaks

### Observability Dashboard
- Live service health monitoring with latency tracking
- Database stats, reranker metrics, error counts
- Pipeline step timing driven by real SSE events
- Loading skeletons and graceful degradation when services are down

### Frontend UX
- Mobile-responsive layout with drawer navigation for smaller screens
- Copy button on code blocks, thumbs up/down feedback, regenerate responses
- Chat export to markdown, keyboard shortcuts (Cmd+/)
- Error boundary with toast notifications

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, Material UI, Framer Motion, Recharts |
| Backend | FastAPI, LangGraph, LangChain, Pydantic |
| LLM | Ollama with qwen2.5:32b (runs on 24GB VRAM) |
| Embeddings | mxbai-embed-large (1024 dimensions) |
| Reranker | Cross-encoder MiniLM-L6-v2 |
| Vector DB | PostgreSQL + pgvector (hybrid BM25 + cosine similarity) |
| Sessions | Amazon DynamoDB (7-day TTL) |
| PII | Local regex masker (AWS Comprehend Medical ready) |
| Data Format | HL7 FHIR R4 |
| Data Ingestion | Go parser + Python batch embedder |

## Project Structure

```
hc_ai/
├── api/                          # Unified FastAPI application
│   ├── main.py                   # App entrypoint, mounts all routers
│   ├── agent/                    # Multi-agent system
│   │   ├── multi_agent_graph.py  # LangGraph workflow (researcher -> validator -> responder)
│   │   ├── prompts.yaml          # All agent prompts
│   │   ├── tools/                # 11 tool modules, 20+ functions
│   │   │   ├── retrieval.py      # Hybrid search with auto resource type detection
│   │   │   ├── fda_tools.py      # openFDA drug safety
│   │   │   ├── terminology_tools.py  # ICD-10, RxNorm
│   │   │   ├── loinc_lookup.py   # LOINC lab code validation
│   │   │   ├── calculators.py    # eGFR, BMI, BSA, CrCl
│   │   │   ├── research_tools.py # PubMed, ClinicalTrials.gov, WHO
│   │   │   └── dosage_validator.py   # FDA label dosage checking
│   │   ├── pii_masker/           # Input/output PII protection
│   │   └── guardrails/           # Response safety validation
│   ├── auth/                     # JWT authentication
│   ├── database/                 # PostgreSQL hybrid search implementation
│   ├── embeddings/               # FHIR resource ingestion API
│   ├── retrieval/                # Cross-encoder reranking service
│   └── session/                  # DynamoDB session management
├── frontend/                     # Next.js 16 application
│   └── src/
│       ├── app/page.tsx          # Main chat interface
│       ├── components/
│       │   ├── chat/             # ChatPanel, MessageBubble, MessageList
│       │   ├── workflow/         # Pipeline visualization, SourceCards, PatientSelector
│       │   ├── observability/    # Health monitoring, metrics dashboard
│       │   └── layout/           # Responsive MainLayout
│       ├── hooks/                # useChat, useWorkflow, useObservability
│       └── services/             # API clients, SSE streaming
├── scripts/                      # Batch embedding, database diagnostics, CLI tools
├── data/fhir/                    # FHIR patient bundles (Synthea-generated)
└── POC_*/                        # Proof-of-concept directories (preserved for reference)
```

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL with pgvector extension
- Ollama
- Docker (for DynamoDB Local)

### Backend Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL with pgvector
cd postgres && docker-compose up -d

# Start DynamoDB Local (for sessions)
cd POC_retrieval && docker-compose -f docker-compose-dynamodb.yml up -d

# Pull required models
ollama pull qwen2.5:32b
ollama pull mxbai-embed-large:latest

# Ingest FHIR patient data into vector store
python scripts/batch_embed_patients.py

# Start the API
uvicorn api.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000), select a patient from the sidebar, and ask a clinical question.

### Environment Variables

```bash
# Database
DB_HOST=localhost  DB_PORT=5432  DB_USER=postgres  DB_NAME=postgres

# LLM & Embeddings
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:32b
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_PROVIDER=ollama
OLLAMA_EMBED_MODEL=mxbai-embed-large:latest

# Sessions
DDB_ENDPOINT=http://localhost:8001

# Agent configuration
AGENT_GRAPH_TYPE=simple        # simple (fast) or complex (with validator loop)
AGENT_RECURSION_LIMIT=50
AGENT_TIMEOUT_SECONDS=300

# Optional
DEBUG_HALLUCINATION=true       # Trace source attribution through the pipeline
PII_MASKER_PROVIDER=local      # local (default) or aws (for Comprehend Medical)
```

## Example Queries

With a patient selected:

```
"What are the patient's active conditions?"
"Summarize the patient's medication history"
"Does the patient have any known allergies?"
"What are the patient's recent lab results?"
"Show me the timeline of clinical events"
"When was the patient's last encounter?"
```

The agent can also access external medical resources:

```
"Calculate the patient's eGFR from their latest creatinine"
"Are there any FDA recalls for the patient's medications?"
"Search PubMed for recent treatments for the patient's conditions"
```

## FHIR Resource Types

The system indexes and retrieves 10 FHIR R4 resource types:

| Resource Type | Example Queries |
|--------------|----------------|
| Condition | Active diagnoses, problem list |
| Observation | Lab results, vital signs, blood pressure |
| MedicationRequest | Current prescriptions, medication history |
| Encounter | Visits, admissions, appointment history |
| Procedure | Surgeries, diagnostic procedures |
| Immunization | Vaccine records |
| DiagnosticReport | Lab and imaging reports |
| Patient | Demographics |
| Organization | Healthcare facilities |
| Medication | Drug reference data |

## Testing

```bash
# Backend agent tests
python -m pytest api/agent/test_*.py

# Frontend build & lint
cd frontend && npm run build && npm run lint
```

## Data Attribution

Patient data generated by [Synthea](https://synthea.mitre.org/downloads), an open-source synthetic patient generator. All patient records are fictional — no real patient data is used.

## License

MIT
