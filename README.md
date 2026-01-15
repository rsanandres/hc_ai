# HC AI - FHIR Data Processing & Vector Store

A production-ready system for processing FHIR (Fast Healthcare Interoperability Resources) data, generating embeddings, and storing them in a PostgreSQL vector database for semantic search and retrieval.

## 🏗️ Architecture

The system consists of three main components:

1. **Go Parser** (`POC_embeddings/main.go`) - Efficiently parses FHIR Bundle JSON files and extracts resources
2. **Python API** (`POC_embeddings/main.py`) - FastAPI service that accepts FHIR resources and processes them asynchronously
3. **PostgreSQL Vector Store** (`postgres/langchain-postgres.py`) - Stores chunks with 1024-dimensional embeddings using pgvector

### Data Flow

```
FHIR JSON Files → Go Parser → Python API → Chunking → Embedding → PostgreSQL Vector Store
```

## 📋 Prerequisites

- **Go** 1.19+ (for parsing FHIR files)
- **Python** 3.9+ (for API and processing)
- **Docker** & **Docker Compose** (for PostgreSQL with pgvector)
- **Ollama** (for local embeddings) - [Install Ollama](https://ollama.ai)
- **PostgreSQL** with **pgvector** extension (via Docker)

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone <repository-url>
cd hc_ai
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup Environment Variables

Create a `.env` file in the project root:

```bash
# Database Configuration
DB_USER=postgres
DB_PASSWORD=your_password_here
DB_NAME=your_database_name
DB_HOST=localhost
DB_PORT=5432

# Embedding Configuration
EMBEDDING_PROVIDER=ollama  # Options: ollama, nomic, bedrock
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=mxbai-embed-large:latest

# Optional: Database Pool Configuration
DB_MAX_POOL_SIZE=10
DB_MAX_OVERFLOW=5
DB_POOL_TIMEOUT=30

# Optional: Queue Configuration
CHUNK_QUEUE_MAX_SIZE=1000
CHUNK_MAX_RETRIES=5
CHUNK_BATCH_SIZE=20
CHUNK_RETRY_BASE_DELAY=1.0
CHUNK_RETRY_MAX_DELAY=60.0
```

### 4. Start PostgreSQL with pgvector

```bash
cd postgres
docker-compose up -d
```

This starts a PostgreSQL 18 container with pgvector extension on port 5432.

### 5. Pull Ollama Embedding Model

```bash
ollama pull mxbai-embed-large:latest
```

### 6. Start the Python API

```bash
cd POC_embeddings
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### 7. Process FHIR Files

In a separate terminal, run the Go parser:

```bash
cd POC_embeddings
go run main.go
```

This will:
- Scan `../data/fhir/` for JSON files
- Extract FHIR resources from Bundles
- Send each resource to the Python API for processing

## 📡 API Endpoints

### `POST /ingest`

Ingest a FHIR resource for processing.

**Request Body:**
```json
{
  "id": "resource-id",
  "fullUrl": "urn:uuid:...",
  "resourceType": "Observation",
  "content": "Extracted text content from resource",
  "patientId": "patient-123",
  "resourceJson": "{...full FHIR JSON resource...}",
  "sourceFile": "../data/fhir/bundle.json"
}
```

**Response:**
```json
{
  "status": "accepted",
  "id": "resource-id",
  "resourceType": "Observation",
  "contentLength": 1234
}
```

### `GET /health`

Health check endpoint.

### `GET /`

Root endpoint with API information and available endpoints.

### `GET /db/stats`

Get database connection and queue statistics.

**Response:**
```json
{
  "active_connections": 2,
  "max_connections": 500,
  "pool_size": 10,
  "queue_size": 0,
  "queue_stats": {
    "queued": 0,
    "processed": 1234,
    "failed": 0,
    "retries": 5
  }
}
```

### `GET /db/queue`

Get queue statistics (memory queue, persisted queue, DLQ).

### `GET /db/errors`

Get error logs with optional filtering.

**Query Parameters:**
- `limit` (default: 100) - Maximum number of records
- `offset` (default: 0) - Pagination offset
- `file_id` - Filter by file ID
- `resource_id` - Filter by resource ID
- `error_type` - Filter by error type (validation, fatal, max_retries, queue_full)

### `GET /db/errors/counts`

Get error statistics grouped by type and file/resource.

## 🗄️ Database Structure

### Schema: `hc_ai_schema`
### Table: `hc_ai_table`

| Column | Type | Description |
|--------|------|-------------|
| `langchain_id` | UUID | Primary key, unique chunk identifier |
| `content` | TEXT | The chunk text content |
| `embedding` | VECTOR(1024) | 1024-dimensional embedding vector (NOT NULL) |
| `langchain_metadata` | JSON | Metadata including patientId, resourceId, resourceType, etc. |

### Metadata Structure

Each chunk includes rich metadata:
```json
{
  "patientId": "patient-123",
  "resourceId": "resource-456",
  "resourceType": "Observation",
  "fullUrl": "urn:uuid:...",
  "sourceFile": "../data/fhir/bundle.json",
  "chunkId": "resource-456_chunk_0",
  "chunkIndex": 0,
  "totalChunks": 5,
  "chunkSize": 850,
  "effectiveDate": "2024-01-15",
  "status": "final"
}
```

## 🔧 Configuration

### Embedding Providers

The system supports multiple embedding providers:

1. **Ollama** (Default, Local)
   - Set `EMBEDDING_PROVIDER=ollama`
   - Requires Ollama running locally
   - Model: `mxbai-embed-large:latest` (1024 dimensions)

2. **Nomic** (Fallback)
   - Set `EMBEDDING_PROVIDER=nomic`
   - Requires Nomic API key

3. **Amazon Bedrock** (Future)
   - Set `EMBEDDING_PROVIDER=bedrock`
   - Requires AWS credentials
   - Not yet implemented

### Chunking Strategy

The system uses **RecursiveJsonSplitter** when JSON is available, which:
- Preserves FHIR JSON structure
- Creates chunks of 500-1000 characters
- Maintains parent-child relationships

Falls back to **RecursiveCharacterTextSplitter** when JSON is not available.

### Queue & Retry System

- **Queue-based processing** for resilience
- **Automatic retries** with exponential backoff
- **Dead Letter Queue (DLQ)** for failed chunks
- **Persistent queue** stored in SQLite (`postgres/queue.db`)

## 📊 Monitoring & Debugging

### Check Database Status

```bash
# Using the check script
python3 postgres/check-db.py

# Or directly in PostgreSQL
docker exec -it postgres-db psql -U postgres
SET search_path TO hc_ai_schema, public;
SELECT COUNT(*) FROM hc_ai_table;
```

### Verify Embeddings

```bash
# Run SQL queries to verify embeddings
docker exec -it postgres-db psql -U postgres -d your_database_name
```

See `postgres/check_embeddings_simple.sql` for verification queries.

### Check Queue Status

```bash
curl http://localhost:8000/db/queue | python3 -m json.tool
```

### View Error Logs

```bash
curl http://localhost:8000/db/errors?limit=10 | python3 -m json.tool
```

## 📁 Project Structure

```
hc_ai/
├── POC_embeddings/
│   ├── main.py              # FastAPI service
│   ├── main.go              # Go FHIR parser
│   ├── helper.py            # Chunking, embeddings, processing
│   ├── requirements.txt     # Python dependencies
│   └── test_*.py            # Test scripts
├── postgres/
│   ├── docker-compose.yml   # PostgreSQL with pgvector
│   ├── langchain-postgres.py # Vector store implementation
│   ├── queue_storage.py     # Queue persistence
│   ├── check-db.py          # Database diagnostic script
│   └── check_embeddings_simple.sql # Embedding verification queries
├── data/
│   └── fhir/                # FHIR JSON files (place your files here)
├── README.md                # This file
└── .env                     # Environment variables (create this)
```

## 🔍 Key Features

- ✅ **Asynchronous Processing** - FastAPI background tasks for non-blocking ingestion
- ✅ **Resilient Queue System** - Automatic retries with exponential backoff
- ✅ **Rich Metadata** - Comprehensive metadata for filtering and tracing
- ✅ **Multiple Embedding Providers** - Ollama (local), Nomic, Bedrock (future)
- ✅ **Connection Pooling** - Efficient database connection management
- ✅ **Error Tracking** - Comprehensive error logging and monitoring
- ✅ **FHIR-Aware Chunking** - Preserves JSON structure when available

## 🐛 Troubleshooting

### "Model not found" error
```bash
ollama pull mxbai-embed-large:latest
```

### "Connection refused" to database
- Ensure Docker container is running: `docker ps`
- Check environment variables in `.env`
- Verify port 5432 is not in use

### "No embeddings generated"
- Check Ollama is running: `curl http://localhost:11434/api/tags`
- Verify model is available: `ollama list`
- Check logs for embedding errors

### Queue not processing
- Check queue stats: `curl http://localhost:8000/db/queue`
- Review error logs: `curl http://localhost:8000/db/errors`
- Check database connection pool stats

## 📝 License

[Add your license here]

## 🤝 Contributing

[Add contribution guidelines here]
