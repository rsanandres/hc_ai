# main.py
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
import nltk
#nltk.download('punkt_tab')
import numpy as np
import logging

# Configure logging first
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

# Configuration for embeddings
import os
import requests
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large:latest")
USE_OLLAMA = os.getenv("USE_OLLAMA", "true").lower() == "true"

# Try to import nomic API (fallback if Ollama not used)
NOMIC_API_AVAILABLE = False
if not USE_OLLAMA:
    try:
        from nomic import embed
        NOMIC_API_AVAILABLE = True
    except (ImportError, TypeError) as e:
        logger.warning(f"Could not import nomic API: {e}")

# Determine if embeddings are available
EMBEDDINGS_AVAILABLE = USE_OLLAMA or NOMIC_API_AVAILABLE

# Log embedding configuration at startup
if USE_OLLAMA:
    logger.info(f"Using Ollama for embeddings: {OLLAMA_BASE_URL} with model '{OLLAMA_MODEL}'")
    # Test Ollama connection
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            if OLLAMA_MODEL in model_names:
                logger.info(f"✓ Ollama model '{OLLAMA_MODEL}' is available")
            else:
                logger.warning(f"⚠ Ollama model '{OLLAMA_MODEL}' not found. Available models: {model_names}")
                logger.warning(f"  You may need to run: ollama pull {OLLAMA_MODEL}")
        else:
            logger.warning(f"⚠ Could not connect to Ollama (status {response.status_code})")
    except Exception as e:
        logger.warning(f"⚠ Could not connect to Ollama: {e}")
        logger.warning("  Make sure Ollama is running: ollama serve")
elif NOMIC_API_AVAILABLE:
    logger.info("Using Nomic API for embeddings")
else:
    logger.warning("No embedding service available - will use fallback chunking")

# Try to import LangChain text splitters
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Could not import LangChain: {e}. Using fallback chunking method.")
    LANGCHAIN_AVAILABLE = False
    RecursiveCharacterTextSplitter = None

# Download NLTK data if not already present
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

app = FastAPI()

class ClinicalNote(BaseModel):
    id: str
    fullUrl: str = Field(default="", alias="fullUrl")
    resourceType: str
    content: str = Field(min_length=1)  # Ensure content is not empty
    patientId: str = Field(default="unknown", alias="patientId")

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

@app.post("/ingest")
async def ingest_note(note: ClinicalNote, background_tasks: BackgroundTasks):
    """
    Ingest a clinical note for processing.
    
    Validates the note and queues it for background processing.
    """
    # Validate content is not empty
    if not note.content or len(note.content.strip()) == 0:
        raise HTTPException(
            status_code=400, 
            detail=f"Content cannot be empty for resource {note.id}"
        )
    
    # Offload the heavy embedding/chunking to a background task
    background_tasks.add_task(process_and_store, note)
    logger.info(f"Accepted note: {note.id} ({note.resourceType})")
    return {
        "status": "accepted", 
        "id": note.id,
        "resourceType": note.resourceType,
        "contentLength": len(note.content)
    }

def get_embeddings(texts: list) -> list:
    """
    Get embeddings for a list of texts using Ollama or Nomic API.
    
    Args:
        texts: List of text strings to embed
    
    Returns:
        List of embedding vectors
    """
    if not EMBEDDINGS_AVAILABLE:
        return None
    
    if USE_OLLAMA:
        # Use Ollama API
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
    else:
        # Use Nomic API
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


def get_chunk_embedding(chunk_text: str):
    """Get embedding for a single chunk."""
    if not EMBEDDINGS_AVAILABLE:
        return None
    
    embeddings = get_embeddings([chunk_text])
    return embeddings[0] if embeddings and len(embeddings) > 0 else None

def process_and_store(note: ClinicalNote):
    """
    Process and store a clinical note with parent-child chunking.
    
    Uses hybrid LangChain + semantic chunking approach.
    """
    try:
        logger.info(f"\n{'='*80}")
        logger.info(f"Processing Resource: {note.id}")
        logger.info(f"  Resource Type: {note.resourceType}")
        logger.info(f"  Patient ID: {note.patientId}")
        logger.info(f"  Content Length: {len(note.content)} chars")
        logger.info(f"{'='*80}")
        
        # Use parent-child chunking
        chunk_hierarchy = parent_child_chunking(
            note.content,
            parent_chunk_size=2000,
            child_chunk_size=500,
            parent_overlap=200,
            child_overlap=50,
            use_semantic_for_children=True,
            semantic_threshold=0.7
        )
        
        if not chunk_hierarchy:
            logger.warning(f"No chunks created for {note.id}")
            return
        
        # Separate parents and children
        parents = [c for c in chunk_hierarchy if c["chunk_type"] == "parent"]
        children = [c for c in chunk_hierarchy if c["chunk_type"] == "child"]
        
        logger.info(f"\nCreated {len(parents)} parent chunks and {len(children)} child chunks\n")
        
        # Display and process each chunk
        for chunk in chunk_hierarchy:
            chunk_id = chunk["chunk_id"]
            chunk_text = chunk["text"]
            chunk_type = chunk["chunk_type"]
            
            # Get embedding
            embedding = get_chunk_embedding(chunk_text)
            if embedding:
                embedding_info = f"Embedding: {len(embedding)} dimensions"
            else:
                embedding_info = "Embedding: Not available"
            
            # Build metadata with parent-child info
            metadata = {
                "patientId": note.patientId,
                "resourceId": note.id,
                "resourceType": note.resourceType,
                "fullUrl": note.fullUrl,
                "chunkId": f"{note.id}_{chunk_id}",
                "chunkType": chunk_type,
                "parentId": f"{note.id}_{chunk['parent_id']}" if chunk.get("parent_id") else None,
                "childIds": [f"{note.id}_{cid}" for cid in chunk.get("child_ids", [])],
                "chunkSize": chunk["chunk_size"],
                "chunkIndex": chunk["chunk_index"]
            }
            
            # Display chunk details
            logger.info(f"\n{'═'*80}")
            logger.info(f"{chunk_type.upper()} CHUNK: {chunk_id}")
            logger.info(f"{'═'*80}")
            logger.info(f"Chunk ID:      {note.id}_{chunk_id}")
            logger.info(f"Chunk Type:    {chunk_type}")
            if chunk.get("parent_id"):
                logger.info(f"Parent ID:     {note.id}_{chunk['parent_id']}")
            if chunk.get("child_ids"):
                logger.info(f"Child IDs:     {[f'{note.id}_{cid}' for cid in chunk['child_ids']]}")
            logger.info(f"Patient ID:    {note.patientId}")
            logger.info(f"Resource ID:   {note.id}")
            logger.info(f"Resource Type: {note.resourceType}")
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
            
            # Here you would save chunks to a Vector DB (e.g., Pinecone or Weaviate)
            # Example:
            # vector_db.upsert(
            #     id=f"{note.id}_{chunk_id}",
            #     values=embedding if embedding else None,
            #     metadata=metadata
            # )
        
        logger.info(f"\n✓ Completed processing {note.id}")
        logger.info(f"  - {len(parents)} parent chunks")
        logger.info(f"  - {len(children)} child chunks")
        logger.info(f"{'='*80}\n")
        
    except Exception as e:
        logger.error(f"Error processing note {note.id}: {e}", exc_info=True)

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "FHIR Data Processing API",
        "endpoints": {
            "ingest": "/ingest (POST)",
            "health": "/health (GET)"
        }
    }