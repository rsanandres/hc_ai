# POC_RAGAS Evaluation Suite

This folder contains RAGAS-based evaluation tooling for the medical RAG agent.

## What it covers
- Synthetic test generation from embedded FHIR chunks
- Hallucination evaluation:
  - Faithfulness
  - Response relevancy
  - Noise sensitivity
- Runs against both direct agent invocation and the API endpoint
- Outputs JSON + Markdown reports

## Prerequisites
- PostgreSQL with pgvector running and populated (first 2000 files embedded)
- Ollama running for embeddings (if used by the system)
- Reranker service running on `:8001`
- Agent service running on `:8002`
- `OPENAI_API_KEY` available for RAGAS metrics and test generation

## Install

```bash
pip install -r POC_RAGAS/requirements.txt
```

## Service startup

```bash
# PostgreSQL (if using docker-compose)
cd postgres && docker-compose up -d

# Ollama
ollama serve

# Reranker service
uvicorn POC_retrieval.reranker.service:app --port 8001

# Agent service
uvicorn POC_agent.service:app --port 8002
```

## Health checks

```bash
python POC_RAGAS/scripts/check_services.py
```

## Generate a synthetic testset

```bash
python POC_RAGAS/scripts/generate_testset.py --size 120
```

Output: `POC_RAGAS/data/testsets/synthetic_testset.json`

## Run evaluation (CLI)

```bash
python POC_RAGAS/scripts/run_evaluation.py --mode both --patient-mode both
```

Outputs:
- `POC_RAGAS/data/results/results.json`
- `POC_RAGAS/data/results/report.md`

## Run evaluation (Pytest)

```bash
pytest POC_RAGAS/tests -v
```

### Optional thresholds
Set environment variables to enforce minimum scores:
```bash
export RAGAS_MIN_FAITHFULNESS=0.7
export RAGAS_MIN_RELEVANCY=0.7
export RAGAS_MAX_NOISE_DEGRADATION=0.2
```

## Configuration

Environment variables used (all optional unless noted):
- `OPENAI_API_KEY` (required for metrics and test generation)
- `RAGAS_MODEL` (default: `gpt-4`)
- `RAGAS_TEST_SET_SIZE` (default: `120`)
- `RAGAS_Q_SIMPLE`, `RAGAS_Q_MULTI`, `RAGAS_Q_COND`
- `RAGAS_NOISE_RATIO` (default: `0.25`)
- `RAGAS_NOISE_SEED` (default: `42`)
- `RAGAS_INCLUDE_FULL_JSON` (default: `true`)
- `AGENT_API_URL` (default: `http://localhost:8002/agent/query`)
- `RERANKER_SERVICE_URL` (default: `http://localhost:8001`)

Database settings (required for DB access):
- `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_HOST`, `DB_PORT`
