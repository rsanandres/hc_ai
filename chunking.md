# FHIR Data Chunking Architecture

## Overview

This document explains the chunking strategy and architecture for processing FHIR (Fast Healthcare Interoperability Resources) data. The system uses a two-stage pipeline: a Go program (`main.go`) that extracts and sends FHIR resources, and a Python FastAPI service (`main.py`) that chunks the data using LangChain's `RecursiveJsonSplitter`.

## Architecture

### Two-Stage Pipeline

```
FHIR JSON Files → main.go (Go) → FastAPI (Python) → Chunked Data
```

1. **Go Stage (`main.go`)**: Reads FHIR Bundle JSON files, extracts individual resources, and sends them to the Python API
2. **Python Stage (`main.py`)**: Receives resources, chunks them using `RecursiveJsonSplitter`, and prepares them for vector database storage

## Chunking Strategy

### RecursiveJsonSplitter

The system uses LangChain's `RecursiveJsonSplitter` to chunk FHIR resources while preserving JSON structure. This is crucial for healthcare data where maintaining the hierarchical structure of JSON is important for context and relationships.

#### Configuration

- **Max Chunk Size**: 1000 characters
- **Min Chunk Size**: 500 characters

These parameters ensure:
- Chunks are large enough to contain meaningful context
- Chunks are small enough for efficient embedding and retrieval
- JSON structure is preserved (no broken JSON objects)

#### How RecursiveJsonSplitter Works

1. **JSON Structure Preservation**: The splitter intelligently splits JSON by navigating the structure, ensuring each chunk remains valid JSON
2. **Size Constraints**: Attempts to create chunks between min and max sizes, but prioritizes JSON validity over strict size limits
3. **Hierarchical Splitting**: Recursively splits nested JSON objects, arrays, and properties while maintaining relationships

#### Fallback Strategy

If `RecursiveJsonSplitter` is unavailable or if JSON is not provided:
- Falls back to `RecursiveCharacterTextSplitter` with similar size constraints
- Final fallback: Simple character-based splitting

## Data Flow

### Step 1: Go Program (`main.go`)

The Go program processes FHIR Bundle files:

```go
1. Reads FHIR Bundle JSON file
2. Parses the bundle structure
3. Extracts Patient ID from Patient resource
4. For each resource in the bundle:
   a. Extracts meaningful text content
   b. Serializes the original resource JSON
   c. Sends to Python API with:
      - Resource ID
      - Resource Type
      - Extracted content (text)
      - Original JSON (for chunking)
      - Patient ID
      - Source file path
```

**Key Functions:**
- `processFile(filePath)`: Main processing function
- `extractPatientID(entries)`: Finds Patient resource and extracts ID
- `extractContent(resource, resourceType)`: Extracts human-readable text from FHIR resource
- `sendToPipeline(data)`: Sends data to Python FastAPI endpoint

### Step 2: Python FastAPI Service (`main.py`)

The Python service receives resources and chunks them:

```python
1. Receives ClinicalNote via POST /ingest
2. Validates the note
3. Chunks the resource:
   a. If JSON available: Uses RecursiveJsonSplitter
   b. If JSON not available: Uses RecursiveCharacterTextSplitter
   c. Creates chunk dictionaries with metadata
4. For each chunk:
   a. Extracts metadata from resource JSON
   b. Creates embedding (if available)
   c. Builds complete metadata dictionary
   d. Logs chunk information
```

**Key Functions:**
- `recursive_json_chunking(json_text, max_chunk_size, min_chunk_size)`: Chunks JSON using RecursiveJsonSplitter
- `extract_resource_metadata(resource_json)`: Extracts date, status, and lastUpdated from FHIR JSON
- `process_and_store(note)`: Main processing function that orchestrates chunking
- `get_chunk_embedding(chunk_text)`: Generates embeddings for chunks

## Metadata Structure

Each chunk includes comprehensive metadata for filtering, searching, and context:

### Core Identifiers
- **`patientId`**: Patient identifier (extracted from Patient resource)
- **`resourceId`**: Unique identifier for the FHIR resource
- **`resourceType`**: Type of FHIR resource (Patient, Condition, Observation, etc.)
- **`fullUrl`**: FHIR fullUrl reference identifier
- **`sourceFile`**: Path to the original FHIR Bundle file

### Chunk Identifiers
- **`chunkId`**: Unique identifier for the chunk (format: `{resourceId}_{chunk_id}`)
- **`chunkIndex`**: Position of this chunk within the resource (0-based)
- **`totalChunks`**: Total number of chunks created from this resource

### Chunk Properties
- **`chunkSize`**: Size of the chunk in characters

### Extracted Metadata (if available)
- **`effectiveDate`**: When the data was recorded (extracted from various date fields depending on resource type)
- **`status`**: Status of the resource (e.g., "active", "completed")
- **`lastUpdated`**: Last update timestamp from the resource's meta field

### Date Field Extraction

The system intelligently extracts dates based on resource type:
- `effectiveDateTime` (Observations, DiagnosticReports)
- `effectivePeriod.start` (Encounters)
- `date` (Immunizations)
- `onsetDateTime` (Conditions)
- `performedDateTime` (Procedures)
- `authoredOn` (MedicationRequests)
- `birthDate` (Patients)

## Example Metadata

```json
{
  "patientId": "03e6006e-b8a0-49a5-9e97-8c08f2f66752",
  "resourceId": "a1adaf74-aeee-47a2-b096-247728c87cc2",
  "resourceType": "Observation",
  "fullUrl": "urn:uuid:a1adaf74-aeee-47a2-b096-247728c87cc2",
  "sourceFile": "../data/fhir/Abbott509_Aaron203_44.json",
  "chunkId": "a1adaf74-aeee-47a2-b096-247728c87cc2_chunk_0",
  "chunkIndex": 0,
  "totalChunks": 2,
  "chunkSize": 850,
  "effectiveDate": "2024-01-15T10:30:00Z",
  "status": "final",
  "lastUpdated": "2024-01-20T14:22:00Z"
}
```

## Why This Approach?

### 1. JSON Structure Preservation
FHIR resources have complex nested structures with relationships between resources. `RecursiveJsonSplitter` maintains this structure, ensuring chunks contain complete, valid JSON objects rather than arbitrary text splits.

### 2. Rich Metadata
Comprehensive metadata enables:
- **Filtering**: By patient, resource type, date, status
- **Tracing**: Back to original source files
- **Context**: Understanding chunk position within resource
- **Temporal Queries**: Filtering by date ranges

### 3. Two-Stage Processing
- **Go**: Efficient file parsing and resource extraction
- **Python**: Rich ecosystem for NLP, chunking, and embeddings
- **Separation**: Each tool used for its strengths

## API Endpoints

### POST `/ingest`
Accepts a `ClinicalNote` object and processes it asynchronously.

**Request Body:**
```json
{
  "id": "resource-id",
  "fullUrl": "urn:uuid:...",
  "resourceType": "Observation",
  "content": "Extracted text content",
  "patientId": "patient-id",
  "resourceJson": "{...full JSON resource...}",
  "sourceFile": "../data/fhir/file.json"
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

### GET `/health`
Health check endpoint.

### GET `/`
Root endpoint with API information.

## Configuration

### Environment Variables
- `OLLAMA_BASE_URL`: Base URL for Ollama embeddings (default: `http://localhost:11434`)
- `OLLAMA_EMBED_MODEL`: Ollama embedding model (default: `mxbai-embed-large:latest`)
- `USE_OLLAMA`: Whether to use Ollama for embeddings (default: `true`)

### Chunking Parameters
Currently hardcoded in `process_and_store()`:
- `max_chunk_size = 1000`
- `min_chunk_size = 500`

These can be made configurable via environment variables or API parameters if needed.

## Error Handling

### Go Program
- Logs errors for unreadable files
- Skips resources with missing or invalid data
- Continues processing even if individual resources fail

### Python Service
- Validates incoming data (non-empty content required)
- Falls back to alternative chunking methods if primary fails
- Logs all errors with full stack traces
- Returns appropriate HTTP status codes

## Future Enhancements

Potential improvements:
1. **Configurable Chunk Sizes**: Make min/max chunk sizes configurable
2. **Batch Processing**: Process multiple resources in a single request
3. **Vector DB Integration**: Direct integration with Pinecone, Weaviate, etc.
4. **Chunk Relationships**: Track relationships between chunks from related resources
5. **Custom Chunking Strategies**: Resource-type-specific chunking parameters
6. **Progress Tracking**: Track processing progress for large batches

## Dependencies

### Go
- Standard library only (no external dependencies)

### Python
- `fastapi`: Web framework
- `langchain-text-splitters`: RecursiveJsonSplitter
- `langchain`: Text splitters
- `nltk`: Sentence tokenization (fallback)
- `numpy`: Numerical operations
- `sklearn`: Cosine similarity (for semantic chunking fallback)
- `requests`: HTTP client for Ollama/Nomic API
- `pydantic`: Data validation

## Running the System

1. **Start Python FastAPI Server:**
   ```bash
   cd POC_embeddings
   python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
   ```

2. **Run Go Program:**
   ```bash
   cd POC_embeddings
   go run main.go
   ```

The Go program will process the specified FHIR file and send resources to the Python API for chunking.

## Summary

This chunking architecture provides:
- ✅ **Structured Chunking**: Preserves JSON structure using RecursiveJsonSplitter
- ✅ **Rich Metadata**: Comprehensive metadata for filtering and context
- ✅ **Scalable Design**: Two-stage pipeline optimized for each language's strengths
- ✅ **Robust Error Handling**: Graceful fallbacks and comprehensive logging
- ✅ **FHIR-Aware**: Understands FHIR resource structure and extracts relevant metadata

The system is designed to process FHIR Bundle files efficiently while maintaining data integrity and providing rich metadata for downstream vector database operations.
