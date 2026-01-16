# POC Agent Service

This service hosts a LangGraph ReAct agent for healthcare RAG.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Ensure the reranker service is running:
   ```bash
   uvicorn POC_retrieval.reranker.service:app --reload --port 8001
   ```

3. Configure environment variables (repo root `.env`):
   ```
   LLM_PROVIDER=ollama
   LLM_MODEL=chevalblanc/claude-3-haiku:latest
   OLLAMA_BASE_URL=http://localhost:11434
   PII_MASKER_PROVIDER=local
   ```

## Run the Agent Service

```bash
uvicorn POC_agent.service:app --reload --port 8002
```

## Query Endpoint

`POST /agent/query`

Body:
```json
{
  "query": "What medications is the patient taking for diabetes?",
  "session_id": "demo-session",
  "patient_id": "patient-123"
}
```

## Tests

Integration test (requires reranker running):
```bash
python POC_agent/test_agent_integration.py "diabetes medications"
```

Unit tests:
```bash
python POC_agent/test_agent.py
```
