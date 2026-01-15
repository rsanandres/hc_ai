# helper.py
"""
Helper functions for FHIR data processing including chunking, embeddings, and metadata extraction.
"""

import os
import importlib.util
import json
import logging
import requests
import nltk
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import sklearn for cosine similarity
try:
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import sklearn: {e}. Using fallback chunking method.")
    SKLEARN_AVAILABLE = False
    cosine_similarity = None

# ============================================================================
# EMBEDDING PROVIDER CONFIGURATION
# ============================================================================
# TODO: When migrating to Amazon Bedrock, update EMBEDDING_PROVIDER to "bedrock"
# Supported providers: "ollama" (current, cheaper), "bedrock" (future, production), "nomic" (fallback)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama").lower()

# Ollama Configuration (Current - Cheaper LLM)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large:latest")
USE_OLLAMA = EMBEDDING_PROVIDER == "ollama"

# Nomic API Configuration (Fallback)
NOMIC_API_AVAILABLE = False
if EMBEDDING_PROVIDER == "nomic":
    try:
        from nomic import embed
        NOMIC_API_AVAILABLE = True
    except (ImportError, TypeError) as e:
        logger.warning(f"Could not import nomic API: {e}")

# Amazon Bedrock Configuration (Future Migration)
# TODO: Implement Bedrock embedding support
BEDROCK_REGION = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_EMBED_MODEL", "amazon.titan-embed-text-v1")  # Example model
BEDROCK_AVAILABLE = False
bedrock_runtime = None
if EMBEDDING_PROVIDER == "bedrock":
    try:
        import boto3
        # TODO: Initialize Bedrock client when implementing
        # bedrock_runtime = boto3.client('bedrock-runtime', region_name=BEDROCK_REGION)
        BEDROCK_AVAILABLE = True
        logger.info(f"Bedrock embedding provider configured (not yet implemented)")
    except ImportError as e:
        logger.warning(f"Could not import boto3 for Bedrock: {e}")

# Determine if embeddings are available
EMBEDDINGS_AVAILABLE = USE_OLLAMA or NOMIC_API_AVAILABLE or BEDROCK_AVAILABLE

# Log embedding configuration at startup
logger.info("="*80)
logger.info("EMBEDDING CONFIGURATION")
logger.info("="*80)
logger.info(f"Provider: {EMBEDDING_PROVIDER.upper()}")
if EMBEDDING_PROVIDER == "ollama":
    logger.info(f"  Ollama URL: {OLLAMA_BASE_URL}")
    logger.info(f"  Model: {OLLAMA_MODEL}")
    # Test Ollama connection
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            if OLLAMA_MODEL in model_names:
                logger.info(f"  ✓ Model '{OLLAMA_MODEL}' is available")
            else:
                logger.warning(f"  ⚠ Model '{OLLAMA_MODEL}' not found. Available models: {model_names}")
                logger.warning(f"  You may need to run: ollama pull {OLLAMA_MODEL}")
        else:
            logger.warning(f"  ⚠ Could not connect to Ollama (status {response.status_code})")
    except Exception as e:
        logger.warning(f"  ⚠ Could not connect to Ollama: {e}")
        logger.warning("  Make sure Ollama is running: ollama serve")
elif EMBEDDING_PROVIDER == "bedrock":
    logger.info(f"  Region: {BEDROCK_REGION}")
    logger.info(f"  Model: {BEDROCK_MODEL_ID}")
    logger.warning("  ⚠ Bedrock embeddings not yet implemented")
elif EMBEDDING_PROVIDER == "nomic":
    logger.info("  Using Nomic API for embeddings")
else:
    logger.warning("  ⚠ Unknown embedding provider or no embedding service available")
logger.info("="*80)

# Try to import LangChain text splitters
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter, RecursiveJsonSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import LangChain: {e}. Using fallback chunking method.")
    LANGCHAIN_AVAILABLE = False
    RecursiveCharacterTextSplitter = None
    RecursiveJsonSplitter = None

# Download NLTK data if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)


def semantic_chunking(text: str, threshold: float = 0.7):
    """
    Perform semantic chunking on text using sentence embeddings.
    Falls back to simple sentence-based chunking if embeddings are unavailable.
    
    Args:
        text: Input text to chunk
        threshold: Similarity threshold for chunking (default: 0.7, only used with embeddings)
    
    Returns:
        List of text chunks
    """
    if not text or len(text.strip()) == 0:
        logger.warning("Empty text provided to semantic_chunking")
        return []
    
    # 1. Split into sentences
    try:
        sentences = nltk.sent_tokenize(text)
    except Exception as e:
        logger.error(f"Error tokenizing sentences: {e}")
        # Fallback: split by periods
        sentences = [s.strip() + '.' for s in text.split('.') if s.strip()]
    
    if len(sentences) < 2:
        return [text] if text.strip() else []

    # 2. If embeddings are not available, use simple sentence-based chunking
    if not EMBEDDINGS_AVAILABLE:
        logger.info("Using fallback sentence-based chunking (embeddings not available)")
        # Simple chunking: group sentences into chunks of ~3-5 sentences
        chunks = []
        chunk_size = 3
        for i in range(0, len(sentences), chunk_size):
            chunk = " ".join(sentences[i:i+chunk_size])
            chunks.append(chunk)
        return chunks

    # 3. Embed sentences using Ollama or Nomic API
    try:
        embeddings = get_embeddings(sentences)
        if not embeddings:
            # Fallback: return sentences as chunks
            return sentences
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        # Fallback: return sentences as chunks
        return sentences

    # 4. Calculate similarities and break into chunks
    chunks = []
    current_chunk = [sentences[0]]
    
    try:
        for i in range(len(sentences) - 1):
            if i >= len(embeddings) or (i + 1) >= len(embeddings):
                # If embedding failed for some sentences, add remaining to current chunk
                current_chunk.extend(sentences[i+1:])
                break
                
            vec_a = np.array(embeddings[i]).reshape(1, -1)
            vec_b = np.array(embeddings[i+1]).reshape(1, -1)
            
            if SKLEARN_AVAILABLE:
                similarity = cosine_similarity(vec_a, vec_b)[0][0]
            else:
                # Manual cosine similarity calculation
                similarity = np.dot(vec_a[0], vec_b[0]) / (np.linalg.norm(vec_a[0]) * np.linalg.norm(vec_b[0]))
            
            if similarity < threshold:
                # Semantic Break!
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentences[i+1]]
            else:
                current_chunk.append(sentences[i+1])
                
        chunks.append(" ".join(current_chunk))
    except Exception as e:
        logger.error(f"Error during chunking: {e}")
        # Fallback: return sentences as chunks
        return sentences
    
    return chunks


def recursive_json_chunking(
    json_text: str,
    max_chunk_size: int = 1000,
    min_chunk_size: int = 500
):
    """
    Chunk JSON text using RecursiveJsonSplitter.
    
    Args:
        json_text: JSON string to chunk
        max_chunk_size: Maximum size of chunks
        min_chunk_size: Minimum size of chunks
    
    Returns:
        List of chunk dictionaries
    """
    if not json_text or len(json_text.strip()) == 0:
        logger.warning("Empty JSON text provided to recursive_json_chunking")
        return []
    
    if not LANGCHAIN_AVAILABLE or RecursiveJsonSplitter is None:
        logger.warning("RecursiveJsonSplitter not available, falling back to simple text splitting")
        # Fallback: simple splitting
        chunks = []
        for i in range(0, len(json_text), max_chunk_size):
            chunk_text = json_text[i:i+max_chunk_size]
            if chunk_text.strip():
                chunks.append({
                    "chunk_id": f"chunk_{i // max_chunk_size}",
                    "chunk_type": "chunk",
                    "text": chunk_text,
                    "chunk_size": len(chunk_text),
                    "chunk_index": i // max_chunk_size
                })
        return chunks
    
    try:
        # Create RecursiveJsonSplitter
        json_splitter = RecursiveJsonSplitter(
            max_chunk_size=max_chunk_size,
            min_chunk_size=min_chunk_size
        )
        
        # Split the JSON
        split_chunks = json_splitter.split_text(json_text)
        
        # Convert to our chunk format
        chunks = []
        for i, chunk in enumerate(split_chunks):
            # Handle different return types from RecursiveJsonSplitter
            if hasattr(chunk, 'page_content'):
                chunk_text = str(chunk.page_content)
            elif isinstance(chunk, str):
                chunk_text = chunk
            elif isinstance(chunk, dict):
                chunk_text = json.dumps(chunk, ensure_ascii=False)
            else:
                chunk_text = str(chunk)
            
            if chunk_text.strip():
                chunks.append({
                    "chunk_id": f"chunk_{i}",
                    "chunk_type": "chunk",
                    "text": chunk_text,
                    "chunk_size": len(chunk_text),
                    "chunk_index": i
                })
        
        return chunks
    except Exception as e:
        logger.error(f"Error in recursive_json_chunking: {e}")
        # Fallback: return as single chunk
        return [{
            "chunk_id": "chunk_0",
            "chunk_type": "chunk",
            "text": json_text,
            "chunk_size": len(json_text),
            "chunk_index": 0
        }]


def parent_child_chunking(
    text: str,
    parent_chunk_size: int = 2000,
    child_chunk_size: int = 500,
    parent_overlap: int = 200,
    child_overlap: int = 50,
    use_semantic_for_children: bool = True,
    semantic_threshold: float = 0.7
):
    """
    Hybrid parent-child chunking using LangChain for splitting and semantic similarity for children.
    
    Creates larger parent chunks for context and smaller child chunks for precise retrieval.
    Uses LangChain's RecursiveCharacterTextSplitter for parent chunks, and semantic chunking
    (if available) or LangChain for child chunks.
    
    Args:
        text: Input text to chunk
        parent_chunk_size: Size of parent chunks (larger, for context)
        child_chunk_size: Size of child chunks (smaller, for precise retrieval)
        parent_overlap: Overlap between parent chunks
        child_overlap: Overlap between child chunks
        use_semantic_for_children: Whether to use semantic chunking for children (if available)
        semantic_threshold: Threshold for semantic similarity (if using semantic chunking)
    
    Returns:
        List of chunk dictionaries with parent-child relationships
    """
    if not text or len(text.strip()) == 0:
        logger.warning("Empty text provided to parent_child_chunking")
        return []
    
    # Step 1: Create parent chunks using LangChain (or fallback)
    if LANGCHAIN_AVAILABLE:
        parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=parent_chunk_size,
            chunk_overlap=parent_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len
        )
        parent_chunks = parent_splitter.split_text(text)
    else:
        # Fallback: simple splitting
        logger.info("LangChain not available, using fallback for parent chunks")
        parent_chunks = [text[i:i+parent_chunk_size] for i in range(0, len(text), parent_chunk_size - parent_overlap)]
    
    all_chunks = []
    parent_id_counter = 0
    
    # Step 2: For each parent, create child chunks
    for parent_idx, parent_text in enumerate(parent_chunks):
        parent_id = f"parent_{parent_idx}"
        parent_id_counter += 1
        
        # Create child chunks from parent
        if use_semantic_for_children and EMBEDDINGS_AVAILABLE:
            # Use semantic chunking for children
            child_chunks = semantic_chunking(parent_text, threshold=semantic_threshold)
            # If semantic chunks are too large, split them further
            refined_child_chunks = []
            for child in child_chunks:
                if len(child) > child_chunk_size:
                    # Split large semantic chunks using LangChain or simple splitting
                    if LANGCHAIN_AVAILABLE:
                        child_splitter = RecursiveCharacterTextSplitter(
                            chunk_size=child_chunk_size,
                            chunk_overlap=child_overlap,
                            separators=["\n", ". ", " ", ""],
                            length_function=len
                        )
                        refined_child_chunks.extend(child_splitter.split_text(child))
                    else:
                        # Simple split
                        refined_child_chunks.extend([
                            child[i:i+child_chunk_size] 
                            for i in range(0, len(child), child_chunk_size - child_overlap)
                        ])
                else:
                    refined_child_chunks.append(child)
            child_chunks = refined_child_chunks if refined_child_chunks else [parent_text]
        elif LANGCHAIN_AVAILABLE:
            # Use LangChain for child chunks
            child_splitter = RecursiveCharacterTextSplitter(
                chunk_size=child_chunk_size,
                chunk_overlap=child_overlap,
                separators=["\n", ". ", " ", ""],
                length_function=len
            )
            child_chunks = child_splitter.split_text(parent_text)
        else:
            # Fallback: simple splitting
            child_chunks = [
                parent_text[i:i+child_chunk_size] 
                for i in range(0, len(parent_text), child_chunk_size - child_overlap)
            ]
        
        # If no children created, create at least one
        if not child_chunks:
            child_chunks = [parent_text]
        
        # Create parent chunk object
        parent_chunk = {
            "chunk_id": parent_id,
            "chunk_type": "parent",
            "text": parent_text,
            "parent_id": None,  # Parents have no parent
            "child_ids": [f"{parent_id}_child_{i}" for i in range(len(child_chunks))],
            "chunk_size": len(parent_text),
            "chunk_index": parent_idx
        }
        all_chunks.append(parent_chunk)
        
        # Create child chunk objects
        for i, child_text in enumerate(child_chunks):
            child_id = f"{parent_id}_child_{i}"
            child_chunk = {
                "chunk_id": child_id,
                "chunk_type": "child",
                "text": child_text,
                "parent_id": parent_id,  # Link to parent
                "child_ids": [],  # Children have no children
                "chunk_size": len(child_text),
                "chunk_index": i,
                "parent_text": parent_text  # Include parent text for context
            }
            all_chunks.append(child_chunk)
    
    return all_chunks


def get_embeddings(texts: list) -> list:
    """
    Get embeddings for a list of texts using the configured embedding provider.
    
    EMBEDDING PROVIDER SWITCH POINT:
    - Current: Ollama (cheaper LLM)
    - Future: Amazon Bedrock (production)
    
    To switch providers, set EMBEDDING_PROVIDER environment variable:
    - "ollama" (default, current)
    - "bedrock" (future)
    - "nomic" (fallback)
    
    Args:
        texts: List of text strings to embed
    
    Returns:
        List of embedding vectors, or None if embedding fails
    """
    if not EMBEDDINGS_AVAILABLE:
        return None
    
    # ========================================================================
    # EMBEDDING PROVIDER ROUTING
    # ========================================================================
    if EMBEDDING_PROVIDER == "ollama":
        return _get_embeddings_ollama(texts)
    elif EMBEDDING_PROVIDER == "nomic":
        return _get_embeddings_nomic(texts)
    elif EMBEDDING_PROVIDER == "bedrock":
        return _get_embeddings_bedrock(texts)
    else:
        logger.error(f"Unknown embedding provider: {EMBEDDING_PROVIDER}")
        return None


def _get_embeddings_ollama(texts: list) -> list:
    """
    Get embeddings using Ollama API (Current - Cheaper LLM).
    
    TODO: When migrating to Bedrock, this function can be kept
    as a fallback option or removed if no longer needed.
    """
    try:
        embeddings = []
        # Ollama can handle batch requests, but we'll do one at a time for reliability
        for text in texts:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/api/embeddings",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": text
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            if "embedding" in result:
                embeddings.append(result["embedding"])
            else:
                logger.warning(f"Unexpected response format from Ollama: {result}")
                return None
        
        return embeddings
    except requests.exceptions.RequestException as e:
        logger.error(f"Error calling Ollama API: {e}")
        return None


def test_ollama_connection(test_text: str = "ping") -> dict:
    """
    Quick connectivity check against the configured Ollama endpoint/model.
    
    Returns a dictionary with:
    - base_url / model used
    - tags_status: HTTP status for /api/tags (if reached)
    - available_models: list of models (if retrieved)
    - embed_status: HTTP status for /api/embeddings (if reached)
    - embed_dimensions: length of returned embedding (if successful)
    - errors: any connection/HTTP errors encountered
    """
    result: dict = {
        "base_url": OLLAMA_BASE_URL,
        "model": OLLAMA_MODEL,
        "tags_status": None,
        "available_models": None,
        "embed_status": None,
        "embed_dimensions": None,
        "errors": [],
        "ok": False,
    }
    
    # Check /api/tags
    try:
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        result["tags_status"] = resp.status_code
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            result["available_models"] = [m.get("name", "") for m in models]
    except Exception as e:
        result["errors"].append(f"tags_error: {e}")
    
    # Try a simple embedding call
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/embeddings",
            json={"model": OLLAMA_MODEL, "prompt": test_text},
            timeout=10,
        )
        result["embed_status"] = resp.status_code
        if resp.status_code == 200:
            payload = resp.json()
            if "embedding" in payload:
                result["embed_dimensions"] = len(payload["embedding"])
                result["ok"] = True
            else:
                result["errors"].append("embed_error: missing 'embedding' key in response")
        else:
            result["errors"].append(f"embed_error: status {resp.status_code}, body={resp.text}")
    except Exception as e:
        result["errors"].append(f"embed_error: {e}")
    
    return result


def _get_embeddings_nomic(texts: list) -> list:
    """
    Get embeddings using Nomic API (Fallback).
    """
    try:
        output = embed.text(
            texts=texts,
            model='nomic-embed-text-v1.5',
            task_type='search_document'
        )
        return output['embeddings'] if output.get('embeddings') else None
    except Exception as e:
        logger.error(f"Error calling Nomic API: {e}")
        return None


def _get_embeddings_bedrock(texts: list) -> list:
    """
    Get embeddings using Amazon Bedrock (Future - Production).
    
    TODO: Implement Bedrock embedding calls
    TODO: Handle Bedrock-specific error cases
    TODO: Implement batching if Bedrock supports it
    
    Expected Bedrock API format:
    - Model: amazon.titan-embed-text-v1 or similar
    - Input: text strings
    - Output: embedding vectors
    
    Reference: https://docs.aws.amazon.com/bedrock/latest/userguide/embeddings.html
    """
    # TODO: Implement Bedrock embedding
    logger.error("Bedrock embeddings not yet implemented")
    return None
    # Example implementation structure (uncomment and implement when ready):
    # try:
    #     embeddings = []
    #     for text in texts:
    #         body = json.dumps({"inputText": text})
    #         response = bedrock_runtime.invoke_model(
    #             modelId=BEDROCK_MODEL_ID,
    #             body=body,
    #             contentType="application/json",
    #             accept="application/json"
    #         )
    #         result = json.loads(response['body'].read())
    #         embeddings.append(result['embedding'])
    #     return embeddings
    # except Exception as e:
    #     logger.error(f"Error calling Bedrock API: {e}")
    #     return None


def get_chunk_embedding(chunk_text: str):
    """Get embedding for a single chunk."""
    if not EMBEDDINGS_AVAILABLE:
        return None
    
    embeddings = get_embeddings([chunk_text])
    return embeddings[0] if embeddings and len(embeddings) > 0 else None


def extract_resource_metadata(resource_json: str) -> dict:
    """
    Extract common metadata fields from FHIR resource JSON.
    
    Extracts:
    - effectiveDate/date: When the data was recorded (varies by resource type)
    - status: Status of the resource (varies by resource type)
    - lastUpdated: Last update timestamp from meta field
    
    Returns:
        Dictionary with extracted metadata fields (may be empty if extraction fails)
    """
    metadata = {}
    if not resource_json or not resource_json.strip():
        return metadata
    
    try:
        resource = json.loads(resource_json)
        
        # Extract effective date (varies by resource type)
        if "effectiveDateTime" in resource:
            metadata["effectiveDate"] = resource["effectiveDateTime"]
        elif "effectivePeriod" in resource and isinstance(resource["effectivePeriod"], dict):
            if "start" in resource["effectivePeriod"]:
                metadata["effectiveDate"] = resource["effectivePeriod"]["start"]
        elif "date" in resource:
            metadata["effectiveDate"] = resource["date"]
        elif "onsetDateTime" in resource:
            metadata["effectiveDate"] = resource["onsetDateTime"]
        elif "performedDateTime" in resource:
            metadata["effectiveDate"] = resource["performedDateTime"]
        elif "authoredOn" in resource:
            metadata["effectiveDate"] = resource["authoredOn"]
        elif "birthDate" in resource:
            metadata["effectiveDate"] = resource["birthDate"]
        
        # Extract status if available (varies by resource type)
        if "status" in resource:
            metadata["status"] = resource["status"]
        elif "clinicalStatus" in resource:
            metadata["status"] = resource["clinicalStatus"]
        
        # Extract lastUpdated from meta field
        if "meta" in resource and isinstance(resource["meta"], dict):
            if "lastUpdated" in resource["meta"]:
                metadata["lastUpdated"] = resource["meta"]["lastUpdated"]
            
    except Exception as e:
        logger.debug(f"Could not extract metadata from JSON: {e}")
    
    return metadata


async def process_and_store(note):
    """
    Process and store a clinical note with RecursiveJsonSplitter chunking.
    
    Uses RecursiveJsonSplitter with max_chunk_size=1000 and min_chunk_size=500.
    
    Args:
        note: ClinicalNote object with resource data
    """
    try:
        logger.info(f"\n{'='*80}")
        logger.info(f"Processing Resource: {note.id}")
        logger.info(f"  Resource Type: {note.resourceType}")
        logger.info(f"  Patient ID: {note.patientId}")
        logger.info(f"  Content Length: {len(note.content)} chars")
        logger.info(f"{'='*80}")
        
        # Use RecursiveJsonSplitter if JSON is available, otherwise use RecursiveCharacterTextSplitter
        if note.resourceJson and note.resourceJson.strip():
            logger.info(f"  Using RecursiveJsonSplitter on JSON resource")
            json_to_chunk = note.resourceJson
            chunk_hierarchy = recursive_json_chunking(
                json_to_chunk,
                max_chunk_size=1000,
                min_chunk_size=500
            )
        else:
            logger.warning(f"  No JSON resource provided, using RecursiveCharacterTextSplitter on content")
            # Fallback to RecursiveCharacterTextSplitter when JSON is not available
            if LANGCHAIN_AVAILABLE and RecursiveCharacterTextSplitter:
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=100,
                    separators=["\n\n", "\n", ". ", " ", ""],
                    length_function=len
                )
                split_chunks = text_splitter.split_text(note.content)
                chunk_hierarchy = []
                for i, chunk_text in enumerate(split_chunks):
                    if chunk_text.strip():
                        chunk_hierarchy.append({
                            "chunk_id": f"chunk_{i}",
                            "chunk_type": "chunk",
                            "text": chunk_text,
                            "chunk_size": len(chunk_text),
                            "chunk_index": i
                        })
            else:
                # Final fallback: simple splitting
                chunk_hierarchy = []
                for i in range(0, len(note.content), 1000):
                    chunk_text = note.content[i:i+1000]
                    if chunk_text.strip():
                        chunk_hierarchy.append({
                            "chunk_id": f"chunk_{i // 1000}",
                            "chunk_type": "chunk",
                            "text": chunk_text,
                            "chunk_size": len(chunk_text),
                            "chunk_index": i // 1000
                        })
        
        if not chunk_hierarchy:
            logger.warning(f"No chunks created for {note.id}")
            return
        
        chunking_method = "RecursiveJsonSplitter" if (note.resourceJson and note.resourceJson.strip()) else "RecursiveCharacterTextSplitter"
        logger.info(f"\nCreated {len(chunk_hierarchy)} chunks using {chunking_method}\n")
        
        # Extract metadata from resource JSON if available
        resource_metadata = extract_resource_metadata(note.resourceJson) if note.resourceJson else {}
        total_chunks = len(chunk_hierarchy)
        
        # Display and process each chunk
        for chunk in chunk_hierarchy:
            chunk_id = chunk["chunk_id"]
            chunk_text = chunk["text"]
            chunk_type = chunk["chunk_type"]
            
            # ============================================================================
            # EMBEDDING GENERATION
            # ============================================================================
            # This is where embeddings are generated for each chunk.
            # The embedding provider is determined by EMBEDDING_PROVIDER env var.
            # Current: Ollama (cheaper LLM)
            # Future: Amazon Bedrock (set EMBEDDING_PROVIDER=bedrock)
            # ============================================================================
            embedding = get_chunk_embedding(chunk_text)
            if embedding:
                embedding_info = f"Embedding: {len(embedding)} dimensions"
            else:
                embedding_info = "Embedding: Not available"
            
            # Build metadata
            metadata = {
                # Core identifiers
                "patientId": note.patientId,
                "resourceId": note.id,
                "resourceType": note.resourceType,
                "fullUrl": note.fullUrl,
                "sourceFile": note.sourceFile,
                
                # Chunk identifiers
                "chunkId": f"{note.id}_{chunk_id}",
                "chunkIndex": chunk["chunk_index"],
                "totalChunks": total_chunks,
                
                # Chunk properties
                "chunkSize": chunk["chunk_size"],
            }
            
            # Add extracted metadata from resource JSON if available
            if "effectiveDate" in resource_metadata:
                metadata["effectiveDate"] = resource_metadata["effectiveDate"]
            if "status" in resource_metadata:
                metadata["status"] = resource_metadata["status"]
            if "lastUpdated" in resource_metadata:
                metadata["lastUpdated"] = resource_metadata["lastUpdated"]
            
            # Display chunk details
            logger.info(f"\n{'═'*80}")
            logger.info(f"CHUNK: {chunk_id}")
            logger.info(f"{'═'*80}")
            logger.info(f"Chunk ID:      {note.id}_{chunk_id}")
            logger.info(f"Patient ID:    {note.patientId}")
            logger.info(f"Resource ID:   {note.id}")
            logger.info(f"Resource Type: {note.resourceType}")
            logger.info(f"Source File:   {note.sourceFile}")
            logger.info(f"Chunk Index:   {chunk['chunk_index']} of {total_chunks}")
            if "effectiveDate" in metadata:
                logger.info(f"Effective Date: {metadata['effectiveDate']}")
            if "status" in metadata:
                logger.info(f"Status:         {metadata['status']}")
            if "lastUpdated" in metadata:
                logger.info(f"Last Updated:   {metadata['lastUpdated']}")
            logger.info(f"{embedding_info}")
            logger.info(f"Metadata:      {metadata}")
            logger.info(f"\n{'─'*80}")
            logger.info(f"CHUNK TEXT ({len(chunk_text)} characters):")
            logger.info(f"{'─'*80}")
            
            if chunk_text and chunk_text.strip():
                print(f"\n>>> {chunk_type.upper()} CHUNK TEXT START >>>")
                print(chunk_text)
                print(f">>> {chunk_type.upper()} CHUNK TEXT END >>>\n")
                logger.info("")
                logger.info(chunk_text)
                logger.info("")
            else:
                logger.warning("  [EMPTY OR WHITESPACE-ONLY CHUNK TEXT]")
            
            logger.info(f"{'─'*80}")
            logger.info(f"{'═'*80}")
            
            # Store chunk in PostgreSQL vector store
            try:
                import os
                import importlib.util
                import uuid  
                
                # Load langchain-postgres module
                postgres_dir = os.path.join(os.path.dirname(__file__), '..', 'postgres')
                postgres_file = os.path.join(postgres_dir, 'langchain-postgres.py')
                
                if os.path.exists(postgres_file):
                    spec = importlib.util.spec_from_file_location("langchain_postgres", postgres_file)
                    langchain_module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(langchain_module)
                    
                    # Generate a proper UUID for the chunk ID (required by PostgreSQL)
                    chunk_uuid = str(uuid.uuid4())
                    
                    # Validate chunk before attempting to store
                    is_valid, validation_msg = langchain_module.validate_chunk(chunk_text, chunk_uuid, metadata)
                    if not is_valid:
                        # Log validation error
                        await langchain_module.log_error(
                            file_id=note.sourceFile,
                            resource_id=note.id,
                            chunk_id=chunk_uuid,
                            chunk_index=chunk["chunk_index"],
                            error_type="validation",
                            error_message=validation_msg,
                            metadata=metadata,
                            source_file=note.sourceFile,
                        )
                        logger.warning(f"⚠ Skipping invalid chunk {chunk_id}: {validation_msg}")
                        continue
                    
                    # Store the original chunk identifier in metadata (already there as chunkId)
                    success = await langchain_module.store_chunk(
                        chunk_text=chunk_text,
                        chunk_id=chunk_uuid,  # Use UUID instead of concatenated string
                        metadata=metadata,  # chunkId is already in metadata
                        use_queue=True,
                    )
                    
                    if success:
                        logger.info(f"✓ Stored chunk {chunk_uuid} (original: {note.id}_{chunk_id}) in PostgreSQL vector store")
                    else:
                        # Could be queued for retry
                        logger.warning(f"⚠ Chunk {chunk_uuid} not stored immediately (may be queued for retry)")
                else:
                    logger.warning(f"PostgreSQL vector store module not found at {postgres_file}")
            except ImportError as e:
                logger.warning(f"Could not import PostgreSQL vector store functions: {e}")
                logger.info("  Chunk will not be stored in vector database")
            except Exception as e:
                logger.error(f"Error storing chunk in PostgreSQL: {e}", exc_info=True)
                # Log the error
                try:
                    import os
                    import importlib.util
                    import uuid
                    postgres_dir = os.path.join(os.path.dirname(__file__), '..', 'postgres')
                    postgres_file = os.path.join(postgres_dir, 'langchain-postgres.py')
                    if os.path.exists(postgres_file):
                        spec = importlib.util.spec_from_file_location("langchain_postgres", postgres_file)
                        langchain_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(langchain_module)
                        chunk_uuid = str(uuid.uuid4())
                        await langchain_module.log_error(
                            file_id=note.sourceFile,
                            resource_id=note.id,
                            chunk_id=chunk_uuid,
                            chunk_index=chunk["chunk_index"],
                            error_type="fatal",
                            error_message=str(e),
                            metadata=metadata,
                            source_file=note.sourceFile,
                        )
                except Exception:
                    pass  # Don't fail on error logging failure
        
        logger.info(f"\n✓ Completed processing {note.id}")
        logger.info(f"  - {len(chunk_hierarchy)} chunks")
        logger.info(f"{'='*80}\n")
        
    except Exception as e:
        logger.error(f"Error processing note {note.id}: {e}", exc_info=True)
