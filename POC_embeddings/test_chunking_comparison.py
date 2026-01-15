#!/usr/bin/env python3
"""
Test script to compare semantic chunking vs parent-child chunking
on 1000 patient files.
"""

import json
import os
import time
import gc
import sys
from pathlib import Path
from typing import Dict, List
import logging
from collections import defaultdict

# Import chunking functions from main.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import semantic_chunking, parent_child_chunking

# Import LangChain splitters
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter, RecursiveJsonSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    RecursiveCharacterTextSplitter = None
    RecursiveJsonSplitter = None

# Import LangChain experimental semantic chunker
try:
    from langchain_experimental.text_splitter import SemanticChunker
    from langchain_core.embeddings import Embeddings
    SEMANTIC_CHUNKER_AVAILABLE = True
except ImportError:
    SEMANTIC_CHUNKER_AVAILABLE = False
    SemanticChunker = None
    Embeddings = None

# Create Ollama embeddings wrapper for LangChain
if SEMANTIC_CHUNKER_AVAILABLE and Embeddings:
    import requests
    
    class OllamaEmbeddings(Embeddings):
        """LangChain-compatible embeddings wrapper for Ollama."""
        
        def __init__(self, base_url=None, model=None):
            self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            self.model = model or os.getenv("OLLAMA_EMBED_MODEL", "mxbai-embed-large:latest")
        
        def embed_documents(self, texts):
            """Embed a list of documents."""
            embeddings = []
            for text in texts:
                try:
                    response = requests.post(
                        f"{self.base_url}/api/embeddings",
                        json={"model": self.model, "prompt": text},
                        timeout=30
                    )
                    response.raise_for_status()
                    result = response.json()
                    if "embedding" in result:
                        embeddings.append(result["embedding"])
                    else:
                        # Fallback: return zero vector
                        embeddings.append([0.0] * 768)
                except Exception as e:
                    logging.warning(f"Error getting embedding: {e}")
                    # Fallback: return zero vector
                    embeddings.append([0.0] * 768)
            return embeddings
        
        def embed_query(self, text):
            """Embed a single query."""
            return self.embed_documents([text])[0]
    
    # Initialize Ollama embeddings
    try:
        ollama_embeddings = OllamaEmbeddings()
        # Test connection
        test_embed = ollama_embeddings.embed_query("test")
        OLLAMA_EMBEDDINGS_AVAILABLE = len(test_embed) > 0
    except Exception as e:
        logging.warning(f"Could not initialize Ollama embeddings: {e}")
        OLLAMA_EMBEDDINGS_AVAILABLE = False
        ollama_embeddings = None
else:
    OLLAMA_EMBEDDINGS_AVAILABLE = False
    ollama_embeddings = None

# Import tokenizer for token counting
try:
    import tiktoken
    TOKENIZER_AVAILABLE = True
    # Use cl100k_base encoding (used by GPT-3.5, GPT-4, and many embedding models)
    tokenizer = tiktoken.get_encoding("cl100k_base")
except ImportError:
    TOKENIZER_AVAILABLE = False
    tokenizer = None

def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken."""
    if not text or not TOKENIZER_AVAILABLE:
        # Fallback: approximate tokens as words (rough estimate: 1 token ≈ 0.75 words)
        return len(text.split()) if text else 0
    return len(tokenizer.encode(text))


def clear_caches():
    """
    Clear all caches between test runs for fair comparison.
    This includes Python garbage collection and memory cleanup.
    """
    logger.info("Clearing caches between tests...")
    
    # Force multiple rounds of garbage collection to ensure everything is collected
    collected = 0
    for round_num in range(3):
        round_collected = gc.collect()
        collected += round_collected
        if round_num == 0:
            logger.info(f"  Round {round_num + 1}: Collected {round_collected} objects")
    
    logger.info(f"  Total garbage collected: {collected} objects")
    
    # Small delay to ensure cleanup completes and system resources are freed
    # This helps ensure memory is actually released and not just marked for collection
    time.sleep(1.0)
    
    logger.info("  ✓ Cache clearing complete - ready for next test")

def extract_patient_id(resources: List[Dict]) -> str:
    """Extract patient ID from resources (Python version)."""
    for resource in resources:
        resource_obj = resource.get("resource", {})
        if resource_obj.get("resourceType") == "Patient":
            patient_id = resource_obj.get("id", "")
            if patient_id:
                return patient_id
            # Fallback to fullUrl
            return resource.get("fullUrl", "unknown")
    return "unknown"


def extract_content_from_resource_python(resource: Dict) -> str:
    """Extract meaningful content from a resource (Python version of Go extractContent)."""
    import re
    
    resource_obj = resource.get("resource", {})
    resource_type = resource_obj.get("resourceType", "")
    parts = []
    
    # Try to get text.div first (if available)
    if "text" in resource_obj:
        text_obj = resource_obj["text"]
        if isinstance(text_obj, dict) and "div" in text_obj:
            div = text_obj["div"]
            if div:
                # Clean HTML tags
                div = re.sub(r'<[^>]+>', ' ', div)
                div = re.sub(r'\s+', ' ', div).strip()
                if div:
                    return div
    
    # Build content based on resource type
    if resource_type == "Patient":
        parts.append("Patient Information:")
        if "name" in resource_obj and isinstance(resource_obj["name"], list) and len(resource_obj["name"]) > 0:
            name_obj = resource_obj["name"][0]
            if isinstance(name_obj, dict):
                if "family" in name_obj:
                    parts.append(f"Name: {name_obj['family']}")
                if "given" in name_obj and isinstance(name_obj["given"], list) and len(name_obj["given"]) > 0:
                    parts.append(name_obj["given"][0])
        if "gender" in resource_obj:
            parts.append(f"Gender: {resource_obj['gender']}")
        if "birthDate" in resource_obj:
            parts.append(f"Date of Birth: {resource_obj['birthDate']}")
    
    elif resource_type == "Condition":
        parts.append("Medical Condition:")
        if "code" in resource_obj:
            code_obj = resource_obj["code"]
            if isinstance(code_obj, dict):
                if "text" in code_obj:
                    parts.append(code_obj["text"])
                elif "coding" in code_obj and isinstance(code_obj["coding"], list) and len(code_obj["coding"]) > 0:
                    coding_obj = code_obj["coding"][0]
                    if isinstance(coding_obj, dict) and "display" in coding_obj:
                        parts.append(coding_obj["display"])
        if "clinicalStatus" in resource_obj:
            parts.append(f"Status: {resource_obj['clinicalStatus']}")
        if "onsetDateTime" in resource_obj:
            parts.append(f"Onset: {resource_obj['onsetDateTime']}")
    
    elif resource_type == "Observation":
        parts.append("Clinical Observation:")
        if "code" in resource_obj:
            code_obj = resource_obj["code"]
            if isinstance(code_obj, dict):
                if "text" in code_obj:
                    parts.append(code_obj["text"])
                elif "coding" in code_obj and isinstance(code_obj["coding"], list) and len(code_obj["coding"]) > 0:
                    coding_obj = code_obj["coding"][0]
                    if isinstance(coding_obj, dict) and "display" in coding_obj:
                        parts.append(coding_obj["display"])
        if "valueQuantity" in resource_obj:
            value_qty = resource_obj["valueQuantity"]
            if isinstance(value_qty, dict):
                value = value_qty.get("value")
                unit = value_qty.get("unit", "")
                if value is not None:
                    if unit:
                        parts.append(f"Value: {value:.2f} {unit}")
                    else:
                        parts.append(f"Value: {value:.2f}")
        if "effectiveDateTime" in resource_obj:
            parts.append(f"Date: {resource_obj['effectiveDateTime']}")
    
    elif resource_type == "Encounter":
        parts.append("Healthcare Encounter:")
        if "type" in resource_obj and isinstance(resource_obj["type"], list) and len(resource_obj["type"]) > 0:
            type_obj = resource_obj["type"][0]
            if isinstance(type_obj, dict):
                if "text" in type_obj:
                    parts.append(type_obj["text"])
                elif "coding" in type_obj and isinstance(type_obj["coding"], list) and len(type_obj["coding"]) > 0:
                    coding_obj = type_obj["coding"][0]
                    if isinstance(coding_obj, dict) and "display" in coding_obj:
                        parts.append(coding_obj["display"])
        if "period" in resource_obj:
            period = resource_obj["period"]
            if isinstance(period, dict) and "start" in period:
                parts.append(f"Start: {period['start']}")
        if "reason" in resource_obj:
            reason = resource_obj["reason"]
            if isinstance(reason, dict) and "coding" in reason and isinstance(reason["coding"], list) and len(reason["coding"]) > 0:
                coding_obj = reason["coding"][0]
                if isinstance(coding_obj, dict) and "display" in coding_obj:
                    parts.append(f"Reason: {coding_obj['display']}")
    
    elif resource_type in ["MedicationRequest", "Medication", "Immunization", "DiagnosticReport", "Procedure", "Organization"]:
        # Simplified extraction for other types
        parts.append(f"{resource_type}:")
        if "code" in resource_obj:
            code_obj = resource_obj["code"]
            if isinstance(code_obj, dict):
                if "text" in code_obj:
                    parts.append(code_obj["text"])
                elif "coding" in code_obj and isinstance(code_obj["coding"], list) and len(code_obj["coding"]) > 0:
                    coding_obj = code_obj["coding"][0]
                    if isinstance(coding_obj, dict) and "display" in coding_obj:
                        parts.append(coding_obj["display"])
        if "name" in resource_obj and isinstance(resource_obj["name"], str):
            parts.append(resource_obj["name"])
    
    if len(parts) == 0:
        return ""
    
    return " ".join(parts)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_fhir_bundle(file_path: str) -> Dict:
    """Load and parse a FHIR bundle JSON file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {file_path}: {e}")
        return None


def extract_resources_from_bundle(bundle: Dict) -> List[Dict]:
    """Extract all resources from a FHIR bundle."""
    if not bundle or bundle.get("resourceType") != "Bundle":
        return []
    
    resources = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource:
            resources.append({
                "id": resource.get("id", ""),
                "fullUrl": entry.get("fullUrl", ""),
                "resourceType": resource.get("resourceType", ""),
                "resource": resource
            })
    
    return resources


def extract_content_from_resource(resource: Dict) -> str:
    """Extract meaningful content from a resource."""
    return extract_content_from_resource_python(resource)


def process_file_semantic_only(file_path: str) -> Dict:
    """Process a file using semantic chunking only."""
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "total_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_chunk_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0
    }
    
    start_time = time.time()
    
    for resource in resources:
        content = extract_content_from_resource(resource)
        if not content:
            continue
        
        chunks = semantic_chunking(content)
        if chunks:
            chunk_sizes = [len(c) for c in chunks]
            chunk_tokens = [count_tokens(c) for c in chunks]
            stats["total_chunks"] += len(chunks)
            stats["total_chunk_chars"] += sum(chunk_sizes)
            stats["total_chunk_tokens"] += sum(chunk_tokens)
            stats["min_chunk_size"] = min(stats["min_chunk_size"], min(chunk_sizes))
            stats["max_chunk_size"] = max(stats["max_chunk_size"], max(chunk_sizes))
            stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], min(chunk_tokens))
            stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], max(chunk_tokens))
            stats["chunks_per_resource"].append({
                "resource_type": resource["resourceType"],
                "chunk_count": len(chunks),
                "avg_chunk_size": sum(chunk_sizes) / len(chunks) if chunks else 0,
                "avg_chunk_tokens": sum(chunk_tokens) / len(chunks) if chunks else 0
            })
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def process_file_parent_child(file_path: str) -> Dict:
    """Process a file using parent-child chunking."""
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "parent_chunks": 0,
        "child_chunks": 0,
        "total_chunk_chars": 0,
        "parent_chunk_chars": 0,
        "child_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "parent_chunk_tokens": 0,
        "child_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_parent_size": 0,
        "avg_child_size": 0,
        "avg_chunk_tokens": 0,
        "avg_parent_tokens": 0,
        "avg_child_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0
    }
    
    start_time = time.time()
    
    for resource in resources:
        content = extract_content_from_resource(resource)
        if not content:
            continue
        
        chunk_hierarchy = parent_child_chunking(
            content,
            parent_chunk_size=2000,
            child_chunk_size=500,
            parent_overlap=200,
            child_overlap=50,
            use_semantic_for_children=True,
            semantic_threshold=0.85
        )
        
        if chunk_hierarchy:
            parents = [c for c in chunk_hierarchy if c["chunk_type"] == "parent"]
            children = [c for c in chunk_hierarchy if c["chunk_type"] == "child"]
            
            parent_sizes = [p["chunk_size"] for p in parents]
            child_sizes = [c["chunk_size"] for c in children]
            parent_tokens = [count_tokens(p["text"]) for p in parents]
            child_tokens = [count_tokens(c["text"]) for c in children]
            all_sizes = parent_sizes + child_sizes
            all_tokens = parent_tokens + child_tokens
            
            stats["total_chunks"] += len(chunk_hierarchy)
            stats["parent_chunks"] += len(parents)
            stats["child_chunks"] += len(children)
            stats["total_chunk_chars"] += sum(all_sizes)
            stats["parent_chunk_chars"] += sum(parent_sizes)
            stats["child_chunk_chars"] += sum(child_sizes)
            stats["total_chunk_tokens"] += sum(all_tokens)
            stats["parent_chunk_tokens"] += sum(parent_tokens)
            stats["child_chunk_tokens"] += sum(child_tokens)
            
            if all_sizes:
                stats["min_chunk_size"] = min(stats["min_chunk_size"], min(all_sizes))
                stats["max_chunk_size"] = max(stats["max_chunk_size"], max(all_sizes))
            if all_tokens:
                stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], min(all_tokens))
                stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], max(all_tokens))
            
            stats["chunks_per_resource"].append({
                "resource_type": resource["resourceType"],
                "total_chunks": len(chunk_hierarchy),
                "parent_chunks": len(parents),
                "child_chunks": len(children),
                "avg_parent_size": sum(parent_sizes) / len(parents) if parents else 0,
                "avg_child_size": sum(child_sizes) / len(children) if children else 0,
                "avg_parent_tokens": sum(parent_tokens) / len(parents) if parents else 0,
                "avg_child_tokens": sum(child_tokens) / len(children) if children else 0
            })
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    if stats["parent_chunks"] > 0:
        stats["avg_parent_size"] = stats["parent_chunk_chars"] / stats["parent_chunks"]
        stats["avg_parent_tokens"] = stats["parent_chunk_tokens"] / stats["parent_chunks"]
    if stats["child_chunks"] > 0:
        stats["avg_child_size"] = stats["child_chunk_chars"] / stats["child_chunks"]
        stats["avg_child_tokens"] = stats["child_chunk_tokens"] / stats["child_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def process_file_recursive_chunking(file_path: str) -> Dict:
    """Process a file using LangChain's RecursiveCharacterTextSplitter."""
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "total_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_chunk_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0
    }
    
    if not LANGCHAIN_AVAILABLE:
        logger.warning("LangChain not available for recursive chunking")
        return stats
    
    start_time = time.time()
    
    # Create recursive splitter
    recursive_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len
    )
    
    for resource in resources:
        content = extract_content_from_resource(resource)
        if not content:
            continue
        
        chunks = recursive_splitter.split_text(content)
        
        if chunks:
            chunk_sizes = [len(c) for c in chunks]
            chunk_tokens = [count_tokens(c) for c in chunks]
            stats["total_chunks"] += len(chunks)
            stats["total_chunk_chars"] += sum(chunk_sizes)
            stats["total_chunk_tokens"] += sum(chunk_tokens)
            stats["min_chunk_size"] = min(stats["min_chunk_size"], min(chunk_sizes))
            stats["max_chunk_size"] = max(stats["max_chunk_size"], max(chunk_sizes))
            stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], min(chunk_tokens))
            stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], max(chunk_tokens))
            stats["chunks_per_resource"].append({
                "resource_type": resource["resourceType"],
                "chunk_count": len(chunks),
                "avg_chunk_size": sum(chunk_sizes) / len(chunks) if chunks else 0,
                "avg_chunk_tokens": sum(chunk_tokens) / len(chunks) if chunks else 0
            })
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def process_file_hierarchical_chunking(file_path: str) -> Dict:
    """Process a file using hierarchical document chunking with LangChain."""
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "level_1_chunks": 0,  # Largest chunks
        "level_2_chunks": 0,  # Medium chunks
        "level_3_chunks": 0,  # Smallest chunks
        "total_chunk_chars": 0,
        "level_1_chars": 0,
        "level_2_chars": 0,
        "level_3_chars": 0,
        "total_chunk_tokens": 0,
        "level_1_tokens": 0,
        "level_2_tokens": 0,
        "level_3_tokens": 0,
        "avg_chunk_size": 0,
        "avg_level_1_size": 0,
        "avg_level_2_size": 0,
        "avg_level_3_size": 0,
        "avg_chunk_tokens": 0,
        "avg_level_1_tokens": 0,
        "avg_level_2_tokens": 0,
        "avg_level_3_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0
    }
    
    if not LANGCHAIN_AVAILABLE:
        logger.warning("LangChain not available for hierarchical chunking")
        return stats
    
    start_time = time.time()
    
    # Create hierarchical splitters (3 levels)
    level_1_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len
    )
    
    level_2_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        separators=["\n", ". ", " ", ""],
        length_function=len
    )
    
    level_3_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=[". ", " ", ""],
        length_function=len
    )
    
    for resource in resources:
        content = extract_content_from_resource(resource)
        if not content:
            continue
        
        # Level 1: Largest chunks
        level_1_chunks = level_1_splitter.split_text(content)
        
        # Level 2: Split level 1 chunks further (only if large enough)
        level_2_chunks = []
        for l1_chunk in level_1_chunks:
            if len(l1_chunk) > 1000:  # Only split if larger than level 2 target size
                level_2_chunks.extend(level_2_splitter.split_text(l1_chunk))
            # If too small, don't create a level 2 chunk
        
        # Level 3: Split level 2 chunks further (only if large enough)
        level_3_chunks = []
        for l2_chunk in level_2_chunks:
            if len(l2_chunk) > 500:  # Only split if larger than level 3 target size
                level_3_chunks.extend(level_3_splitter.split_text(l2_chunk))
            # If too small, don't create a level 3 chunk
        
        # Collect all chunks and sizes
        all_chunks = level_1_chunks + level_2_chunks + level_3_chunks
        level_1_sizes = [len(c) for c in level_1_chunks]
        level_2_sizes = [len(c) for c in level_2_chunks]
        level_3_sizes = [len(c) for c in level_3_chunks]
        level_1_tokens = [count_tokens(c) for c in level_1_chunks]
        level_2_tokens = [count_tokens(c) for c in level_2_chunks]
        level_3_tokens = [count_tokens(c) for c in level_3_chunks]
        all_sizes = level_1_sizes + level_2_sizes + level_3_sizes
        all_tokens = level_1_tokens + level_2_tokens + level_3_tokens
        
        if all_sizes:
            stats["total_chunks"] += len(all_chunks)
            stats["level_1_chunks"] += len(level_1_chunks)
            stats["level_2_chunks"] += len(level_2_chunks)
            stats["level_3_chunks"] += len(level_3_chunks)
            stats["total_chunk_chars"] += sum(all_sizes)
            stats["level_1_chars"] += sum(level_1_sizes)
            stats["level_2_chars"] += sum(level_2_sizes)
            stats["level_3_chars"] += sum(level_3_sizes)
            stats["total_chunk_tokens"] += sum(all_tokens)
            stats["level_1_tokens"] += sum(level_1_tokens)
            stats["level_2_tokens"] += sum(level_2_tokens)
            stats["level_3_tokens"] += sum(level_3_tokens)
            stats["min_chunk_size"] = min(stats["min_chunk_size"], min(all_sizes))
            stats["max_chunk_size"] = max(stats["max_chunk_size"], max(all_sizes))
            stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], min(all_tokens))
            stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], max(all_tokens))
            
            stats["chunks_per_resource"].append({
                "resource_type": resource["resourceType"],
                "total_chunks": len(all_chunks),
                "level_1_chunks": len(level_1_chunks),
                "level_2_chunks": len(level_2_chunks),
                "level_3_chunks": len(level_3_chunks),
                "avg_level_1_size": sum(level_1_sizes) / len(level_1_sizes) if level_1_sizes else 0,
                "avg_level_2_size": sum(level_2_sizes) / len(level_2_sizes) if level_2_sizes else 0,
                "avg_level_3_size": sum(level_3_sizes) / len(level_3_sizes) if level_3_sizes else 0,
                "avg_level_1_tokens": sum(level_1_tokens) / len(level_1_tokens) if level_1_tokens else 0,
                "avg_level_2_tokens": sum(level_2_tokens) / len(level_2_tokens) if level_2_tokens else 0,
                "avg_level_3_tokens": sum(level_3_tokens) / len(level_3_tokens) if level_3_tokens else 0
            })
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    if stats["level_1_chunks"] > 0:
        stats["avg_level_1_size"] = stats["level_1_chars"] / stats["level_1_chunks"]
        stats["avg_level_1_tokens"] = stats["level_1_tokens"] / stats["level_1_chunks"]
    if stats["level_2_chunks"] > 0:
        stats["avg_level_2_size"] = stats["level_2_chars"] / stats["level_2_chunks"]
        stats["avg_level_2_tokens"] = stats["level_2_tokens"] / stats["level_2_chunks"]
    if stats["level_3_chunks"] > 0:
        stats["avg_level_3_size"] = stats["level_3_chars"] / stats["level_3_chunks"]
        stats["avg_level_3_tokens"] = stats["level_3_tokens"] / stats["level_3_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def process_file_langchain_semantic_chunking(file_path: str) -> Dict:
    """Process a file using LangChain's SemanticChunker."""
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "total_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_chunk_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0
    }
    
    if not SEMANTIC_CHUNKER_AVAILABLE or not OLLAMA_EMBEDDINGS_AVAILABLE:
        logger.warning("LangChain SemanticChunker or Ollama embeddings not available")
        return stats
    
    start_time = time.time()
    
    # Create semantic chunker with Ollama embeddings
    try:
        semantic_splitter = SemanticChunker(
            embeddings=ollama_embeddings,
            breakpoint_threshold_type="percentile",  # or "standard_deviation", "interquartile"
            breakpoint_threshold_amount=75  # percentile threshold
        )
    except Exception as e:
        logger.warning(f"Could not create SemanticChunker: {e}")
        return stats
    
    for resource in resources:
        content = extract_content_from_resource(resource)
        if not content:
            continue
        
        try:
            # SemanticChunker.create_documents returns Document objects
            documents = semantic_splitter.create_documents([content])
            chunks = [doc.page_content for doc in documents]
        except Exception as e:
            logger.debug(f"Semantic chunking failed for resource {resource.get('id', 'unknown')}: {e}")
            # Fallback: use simple sentence splitting
            import nltk
            try:
                sentences = nltk.sent_tokenize(content)
                chunks = [" ".join(sentences[i:i+3]) for i in range(0, len(sentences), 3)]
            except:
                chunks = [content]
        
        if chunks:
            chunk_sizes = [len(c) for c in chunks]
            chunk_tokens = [count_tokens(c) for c in chunks]
            stats["total_chunks"] += len(chunks)
            stats["total_chunk_chars"] += sum(chunk_sizes)
            stats["total_chunk_tokens"] += sum(chunk_tokens)
            stats["min_chunk_size"] = min(stats["min_chunk_size"], min(chunk_sizes))
            stats["max_chunk_size"] = max(stats["max_chunk_size"], max(chunk_sizes))
            stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], min(chunk_tokens))
            stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], max(chunk_tokens))
            stats["chunks_per_resource"].append({
                "resource_type": resource["resourceType"],
                "chunk_count": len(chunks),
                "avg_chunk_size": sum(chunk_sizes) / len(chunks) if chunks else 0,
                "avg_chunk_tokens": sum(chunk_tokens) / len(chunks) if chunks else 0
            })
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def process_file_parent_child_recursive_children(file_path: str) -> Dict:
    """Process a file using parent-child chunking with recursive chunking for children."""
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "parent_chunks": 0,
        "child_chunks": 0,
        "total_chunk_chars": 0,
        "parent_chunk_chars": 0,
        "child_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "parent_chunk_tokens": 0,
        "child_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_parent_size": 0,
        "avg_child_size": 0,
        "avg_chunk_tokens": 0,
        "avg_parent_tokens": 0,
        "avg_child_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0
    }
    
    if not LANGCHAIN_AVAILABLE:
        logger.warning("LangChain not available for parent-child with recursive children")
        return stats
    
    start_time = time.time()
    
    # Create parent splitter
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len
    )
    
    # Create child splitter (recursive)
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n", ". ", " ", ""],
        length_function=len
    )
    
    for resource in resources:
        content = extract_content_from_resource(resource)
        if not content:
            continue
        
        # Create parent chunks
        parent_chunks = parent_splitter.split_text(content)
        
        # For each parent, create child chunks using recursive splitting
        all_parents = []
        all_children = []
        
        for parent_text in parent_chunks:
            parent_id = f"parent_{len(all_parents)}"
            all_parents.append(parent_text)
            
            # Create children using recursive splitting
            child_chunks = child_splitter.split_text(parent_text)
            all_children.extend(child_chunks)
        
        if all_parents or all_children:
            parent_sizes = [len(p) for p in all_parents]
            child_sizes = [len(c) for c in all_children]
            parent_tokens = [count_tokens(p) for p in all_parents]
            child_tokens = [count_tokens(c) for c in all_children]
            all_sizes = parent_sizes + child_sizes
            all_tokens = parent_tokens + child_tokens
            
            stats["total_chunks"] += len(all_parents) + len(all_children)
            stats["parent_chunks"] += len(all_parents)
            stats["child_chunks"] += len(all_children)
            stats["total_chunk_chars"] += sum(all_sizes)
            stats["parent_chunk_chars"] += sum(parent_sizes)
            stats["child_chunk_chars"] += sum(child_sizes)
            stats["total_chunk_tokens"] += sum(all_tokens)
            stats["parent_chunk_tokens"] += sum(parent_tokens)
            stats["child_chunk_tokens"] += sum(child_tokens)
            
            if all_sizes:
                stats["min_chunk_size"] = min(stats["min_chunk_size"], min(all_sizes))
                stats["max_chunk_size"] = max(stats["max_chunk_size"], max(all_sizes))
            if all_tokens:
                stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], min(all_tokens))
                stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], max(all_tokens))
            
            stats["chunks_per_resource"].append({
                "resource_type": resource["resourceType"],
                "total_chunks": len(all_parents) + len(all_children),
                "parent_chunks": len(all_parents),
                "child_chunks": len(all_children),
                "avg_parent_size": sum(parent_sizes) / len(all_parents) if all_parents else 0,
                "avg_child_size": sum(child_sizes) / len(all_children) if all_children else 0,
                "avg_parent_tokens": sum(parent_tokens) / len(all_parents) if all_parents else 0,
                "avg_child_tokens": sum(child_tokens) / len(all_children) if all_children else 0
            })
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    if stats["parent_chunks"] > 0:
        stats["avg_parent_size"] = stats["parent_chunk_chars"] / stats["parent_chunks"]
        stats["avg_parent_tokens"] = stats["parent_chunk_tokens"] / stats["parent_chunks"]
    if stats["child_chunks"] > 0:
        stats["avg_child_size"] = stats["child_chunk_chars"] / stats["child_chunks"]
        stats["avg_child_tokens"] = stats["child_chunk_tokens"] / stats["child_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def process_file_parent_child_hierarchical_children(file_path: str) -> Dict:
    """Process a file using parent-child chunking with hierarchical chunking for children."""
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "parent_chunks": 0,
        "child_chunks": 0,
        "child_level_2_chunks": 0,
        "child_level_3_chunks": 0,
        "total_chunk_chars": 0,
        "parent_chunk_chars": 0,
        "child_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "parent_chunk_tokens": 0,
        "child_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_parent_size": 0,
        "avg_child_size": 0,
        "avg_chunk_tokens": 0,
        "avg_parent_tokens": 0,
        "avg_child_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0
    }
    
    if not LANGCHAIN_AVAILABLE:
        logger.warning("LangChain not available for parent-child with hierarchical children")
        return stats
    
    start_time = time.time()
    
    # Create parent splitter
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len
    )
    
    # Create hierarchical child splitters
    child_level_2_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        separators=["\n", ". ", " ", ""],
        length_function=len
    )
    
    child_level_3_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=[". ", " ", ""],
        length_function=len
    )
    
    for resource in resources:
        content = extract_content_from_resource(resource)
        if not content:
            continue
        
        # Create parent chunks
        parent_chunks = parent_splitter.split_text(content)
        
        # For each parent, create hierarchical children
        all_parents = []
        all_children = []
        
        for parent_text in parent_chunks:
            all_parents.append(parent_text)
            
            # Level 2: Split parent into medium chunks
            level_2_chunks = child_level_2_splitter.split_text(parent_text)
            
            # Level 3: Split level 2 chunks into small chunks
            level_3_chunks = []
            for l2_chunk in level_2_chunks:
                level_3_chunks.extend(child_level_3_splitter.split_text(l2_chunk))
            
            # All children are level 2 + level 3
            all_children.extend(level_2_chunks)
            all_children.extend(level_3_chunks)
        
        if all_parents or all_children:
            parent_sizes = [len(p) for p in all_parents]
            child_sizes = [len(c) for c in all_children]
            parent_tokens = [count_tokens(p) for p in all_parents]
            child_tokens = [count_tokens(c) for c in all_children]
            all_sizes = parent_sizes + child_sizes
            all_tokens = parent_tokens + child_tokens
            
            stats["total_chunks"] += len(all_parents) + len(all_children)
            stats["parent_chunks"] += len(all_parents)
            stats["child_chunks"] += len(all_children)
            stats["total_chunk_chars"] += sum(all_sizes)
            stats["parent_chunk_chars"] += sum(parent_sizes)
            stats["child_chunk_chars"] += sum(child_sizes)
            stats["total_chunk_tokens"] += sum(all_tokens)
            stats["parent_chunk_tokens"] += sum(parent_tokens)
            stats["child_chunk_tokens"] += sum(child_tokens)
            
            if all_sizes:
                stats["min_chunk_size"] = min(stats["min_chunk_size"], min(all_sizes))
                stats["max_chunk_size"] = max(stats["max_chunk_size"], max(all_sizes))
            if all_tokens:
                stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], min(all_tokens))
                stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], max(all_tokens))
            
            stats["chunks_per_resource"].append({
                "resource_type": resource["resourceType"],
                "total_chunks": len(all_parents) + len(all_children),
                "parent_chunks": len(all_parents),
                "child_chunks": len(all_children),
                "avg_parent_size": sum(parent_sizes) / len(all_parents) if all_parents else 0,
                "avg_child_size": sum(child_sizes) / len(all_children) if all_children else 0,
                "avg_parent_tokens": sum(parent_tokens) / len(all_parents) if all_parents else 0,
                "avg_child_tokens": sum(child_tokens) / len(all_children) if all_children else 0
            })
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    if stats["parent_chunks"] > 0:
        stats["avg_parent_size"] = stats["parent_chunk_chars"] / stats["parent_chunks"]
        stats["avg_parent_tokens"] = stats["parent_chunk_tokens"] / stats["parent_chunks"]
    if stats["child_chunks"] > 0:
        stats["avg_child_size"] = stats["child_chunk_chars"] / stats["child_chunks"]
        stats["avg_child_tokens"] = stats["child_chunk_tokens"] / stats["child_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def process_file_recursive_json(file_path: str, max_chunk_size: int = 1000, min_chunk_size: int = 100) -> Dict:
    """Process a file using LangChain's RecursiveJsonSplitter with configurable chunk sizes."""
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "total_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_chunk_tokens": 0,
        "median_chunk_tokens": 0,  # Add median calculation
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0,
        "all_chunk_tokens": []  # Store all token counts for median calculation
    }
    
    if not LANGCHAIN_AVAILABLE or RecursiveJsonSplitter is None:
        logger.warning("LangChain RecursiveJsonSplitter not available")
        return stats
    
    start_time = time.time()
    
    # Create JSON splitter with configurable sizes
    json_splitter = RecursiveJsonSplitter(
        max_chunk_size=max_chunk_size,
        min_chunk_size=min_chunk_size
    )
    
    for resource in resources:
        # RecursiveJsonSplitter works on JSON strings, so use the original resource JSON
        # This is better than extracted text since it preserves JSON structure
        try:
            resource_obj = resource.get("resource", {})
            if not resource_obj:
                continue
            
            # Convert resource to JSON string for splitting
            resource_json = json.dumps(resource_obj, ensure_ascii=False)
            
            # Only split if JSON is large enough
            if len(resource_json) < json_splitter.min_chunk_size:
                chunks = [resource_json]
            else:
                try:
                    chunks = json_splitter.split_text(resource_json)
                except (IndexError, ValueError, KeyError) as split_error:
                    # If splitting fails internally, log and use the whole JSON as one chunk
                    logger.debug(f"JSON splitter failed for resource {resource.get('id', 'unknown')}: {split_error}")
                    chunks = [resource_json]
            
            # Convert chunks back to strings (handle Document objects if returned)
            chunk_strings = []
            for chunk in chunks:
                # Check if it's a Document object (has page_content attribute)
                if hasattr(chunk, 'page_content'):
                    chunk_strings.append(str(chunk.page_content))
                elif isinstance(chunk, str):
                    chunk_strings.append(chunk)
                elif isinstance(chunk, dict):
                    chunk_strings.append(json.dumps(chunk, ensure_ascii=False))
                else:
                    chunk_strings.append(str(chunk))
            chunks = chunk_strings
            
        except Exception as e:
            logger.warning(f"Could not use JSON splitter for resource {resource.get('id', 'unknown')}: {e}")
            # Skip this resource if JSON splitting fails
            continue
        
        if chunks:
            chunk_sizes = [len(c) for c in chunks]
            chunk_tokens = [count_tokens(c) for c in chunks]
            stats["total_chunks"] += len(chunks)
            stats["total_chunk_chars"] += sum(chunk_sizes)
            stats["total_chunk_tokens"] += sum(chunk_tokens)
            stats["all_chunk_tokens"].extend(chunk_tokens)  # Store for median calculation
            stats["min_chunk_size"] = min(stats["min_chunk_size"], min(chunk_sizes))
            stats["max_chunk_size"] = max(stats["max_chunk_size"], max(chunk_sizes))
            stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], min(chunk_tokens))
            stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], max(chunk_tokens))
            stats["chunks_per_resource"].append({
                "resource_type": resource["resourceType"],
                "chunk_count": len(chunks),
                "avg_chunk_size": sum(chunk_sizes) / len(chunks) if chunks else 0,
                "avg_chunk_tokens": sum(chunk_tokens) / len(chunks) if chunks else 0
            })
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
        # Calculate median tokens
        sorted_tokens = sorted(stats["all_chunk_tokens"])
        n = len(sorted_tokens)
        if n % 2 == 0:
            stats["median_chunk_tokens"] = (sorted_tokens[n//2 - 1] + sorted_tokens[n//2]) / 2
        else:
            stats["median_chunk_tokens"] = sorted_tokens[n//2]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
        stats["median_chunk_tokens"] = 0
    
    # Remove all_chunk_tokens from final stats to save space
    del stats["all_chunk_tokens"]
    
    return stats


def process_file_parent_child_json_children(file_path: str) -> Dict:
    """Process a file using parent-child chunking with RecursiveJsonSplitter for children."""
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "parent_chunks": 0,
        "child_chunks": 0,
        "total_chunk_chars": 0,
        "parent_chunk_chars": 0,
        "child_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "parent_chunk_tokens": 0,
        "child_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_parent_size": 0,
        "avg_child_size": 0,
        "avg_chunk_tokens": 0,
        "avg_parent_tokens": 0,
        "avg_child_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0
    }
    
    if not LANGCHAIN_AVAILABLE or RecursiveJsonSplitter is None:
        logger.warning("LangChain RecursiveJsonSplitter not available")
        return stats
    
    start_time = time.time()
    
    # Create parent splitter (text-based)
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
        length_function=len
    )
    
    # Create child splitter (JSON-based)
    child_json_splitter = RecursiveJsonSplitter(
        max_chunk_size=500,
        min_chunk_size=100
    )
    
    for resource in resources:
        resource_obj = resource.get("resource", {})
        if not resource_obj:
            continue
        
        # Extract text content for parent chunks
        content = extract_content_from_resource(resource)
        if not content:
            continue
        
        # Create parent chunks from text content
        parent_chunks = parent_splitter.split_text(content)
        
        # For each parent, create child chunks using JSON splitting on the original resource
        all_parents = []
        all_children = []
        
        # Split the resource JSON once (not per parent) to create child chunks
        # Then associate children with parents based on content overlap
        try:
            resource_json = json.dumps(resource_obj, ensure_ascii=False)
            
            # Only split if JSON is not too small
            if len(resource_json) < child_json_splitter.min_chunk_size:
                # If JSON is too small, use it as a single child for all parents
                for parent_text in parent_chunks:
                    all_parents.append(parent_text)
                    all_children.append(resource_json)
            else:
                # Split JSON into child chunks
                try:
                    child_chunks = child_json_splitter.split_text(resource_json)
                except (IndexError, ValueError, KeyError) as split_error:
                    # If splitting fails, log and skip JSON children for this resource
                    logger.debug(f"JSON splitter failed for resource {resource.get('id', 'unknown')}: {split_error}")
                    child_chunks = []
                
                # Convert chunks to strings (handle Document objects if returned)
                child_strings = []
                for chunk in child_chunks:
                    # Check if it's a Document object (has page_content attribute)
                    if hasattr(chunk, 'page_content'):
                        child_strings.append(str(chunk.page_content))
                    elif isinstance(chunk, str):
                        child_strings.append(chunk)
                    elif isinstance(chunk, dict):
                        child_strings.append(json.dumps(chunk, ensure_ascii=False))
                    else:
                        child_strings.append(str(chunk))
                
                # If we got child chunks, associate them with parents
                if child_strings:
                    # Add all parents
                    for parent_text in parent_chunks:
                        all_parents.append(parent_text)
                    # Add all children (they're associated with the resource, not individual parents)
                    all_children.extend(child_strings)
                else:
                    # No children created, just add parents
                    for parent_text in parent_chunks:
                        all_parents.append(parent_text)
                        
        except Exception as e:
            logger.debug(f"Could not create JSON children for resource {resource.get('id', 'unknown')}: {e}")
            # If JSON splitting fails completely, just add parents without children
            for parent_text in parent_chunks:
                all_parents.append(parent_text)
        
        if all_parents or all_children:
            parent_sizes = [len(p) for p in all_parents]
            child_sizes = [len(c) for c in all_children]
            parent_tokens = [count_tokens(p) for p in all_parents]
            child_tokens = [count_tokens(c) for c in all_children]
            all_sizes = parent_sizes + child_sizes
            all_tokens = parent_tokens + child_tokens
            
            stats["total_chunks"] += len(all_parents) + len(all_children)
            stats["parent_chunks"] += len(all_parents)
            stats["child_chunks"] += len(all_children)
            stats["total_chunk_chars"] += sum(all_sizes)
            stats["parent_chunk_chars"] += sum(parent_sizes)
            stats["child_chunk_chars"] += sum(child_sizes)
            stats["total_chunk_tokens"] += sum(all_tokens)
            stats["parent_chunk_tokens"] += sum(parent_tokens)
            stats["child_chunk_tokens"] += sum(child_tokens)
            
            if all_sizes:
                stats["min_chunk_size"] = min(stats["min_chunk_size"], min(all_sizes))
                stats["max_chunk_size"] = max(stats["max_chunk_size"], max(all_sizes))
            if all_tokens:
                stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], min(all_tokens))
                stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], max(all_tokens))
            
            stats["chunks_per_resource"].append({
                "resource_type": resource["resourceType"],
                "total_chunks": len(all_parents) + len(all_children),
                "parent_chunks": len(all_parents),
                "child_chunks": len(all_children),
                "avg_parent_size": sum(parent_sizes) / len(all_parents) if all_parents else 0,
                "avg_child_size": sum(child_sizes) / len(all_children) if all_children else 0,
                "avg_parent_tokens": sum(parent_tokens) / len(all_parents) if all_parents else 0,
                "avg_child_tokens": sum(child_tokens) / len(all_children) if all_children else 0
            })
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    if stats["parent_chunks"] > 0:
        stats["avg_parent_size"] = stats["parent_chunk_chars"] / stats["parent_chunks"]
        stats["avg_parent_tokens"] = stats["parent_chunk_tokens"] / stats["parent_chunks"]
    if stats["child_chunks"] > 0:
        stats["avg_child_size"] = stats["child_chunk_chars"] / stats["child_chunks"]
        stats["avg_child_tokens"] = stats["child_chunk_tokens"] / stats["child_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def process_file_bundle_parent_resource_children(file_path: str) -> Dict:
    """Process a file where the entire FHIR bundle is the parent, and children are grouped by resource type."""
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "parent_chunks": 0,
        "child_chunks": 0,
        "total_chunk_chars": 0,
        "parent_chunk_chars": 0,
        "child_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "parent_chunk_tokens": 0,
        "child_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_parent_size": 0,
        "avg_child_size": 0,
        "avg_chunk_tokens": 0,
        "avg_parent_tokens": 0,
        "avg_child_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0
    }
    
    if not resources:
        return stats
    
    start_time = time.time()
    
    # Build parent document: combine all resources into one text
    parent_parts = []
    for resource in resources:
        content = extract_content_from_resource(resource)
        if content:
            parent_parts.append(content)
    
    parent_text = "\n\n".join(parent_parts)
    
    # Group resources by resource type (Patient, Organization, Encounter, Condition, etc.)
    resources_by_type = {}
    for resource in resources:
        resource_type = resource.get("resourceType", "Unknown")
        if resource_type not in resources_by_type:
            resources_by_type[resource_type] = []
        resources_by_type[resource_type].append(resource)
    
    # Create children: one child per resource type, containing all resources of that type
    all_parents = [parent_text] if parent_text else []
    all_children = []
    
    for resource_type, type_resources in resources_by_type.items():
        # Combine all resources of this type into one child chunk
        type_parts = []
        for resource in type_resources:
            content = extract_content_from_resource(resource)
            if content:
                type_parts.append(content)
        
        if type_parts:
            # Create a child chunk with header indicating the resource type
            child_text = f"=== {resource_type} Resources ({len(type_resources)} total) ===\n\n"
            child_text += "\n\n---\n\n".join(type_parts)
            all_children.append(child_text)
    
    if all_parents or all_children:
        parent_sizes = [len(p) for p in all_parents]
        child_sizes = [len(c) for c in all_children]
        parent_tokens = [count_tokens(p) for p in all_parents]
        child_tokens = [count_tokens(c) for c in all_children]
        all_sizes = parent_sizes + child_sizes
        all_tokens = parent_tokens + child_tokens
        
        stats["total_chunks"] = len(all_parents) + len(all_children)
        stats["parent_chunks"] = len(all_parents)
        stats["child_chunks"] = len(all_children)
        stats["total_chunk_chars"] = sum(all_sizes)
        stats["parent_chunk_chars"] = sum(parent_sizes)
        stats["child_chunk_chars"] = sum(child_sizes)
        stats["total_chunk_tokens"] = sum(all_tokens)
        stats["parent_chunk_tokens"] = sum(parent_tokens)
        stats["child_chunk_tokens"] = sum(child_tokens)
        
        if all_sizes:
            stats["min_chunk_size"] = min(all_sizes)
            stats["max_chunk_size"] = max(all_sizes)
        if all_tokens:
            stats["min_chunk_tokens"] = min(all_tokens)
            stats["max_chunk_tokens"] = max(all_tokens)
        
        # Track stats per resource type
        for resource_type, type_resources in resources_by_type.items():
            type_content = []
            for resource in type_resources:
                content = extract_content_from_resource(resource)
                if content:
                    type_content.append(content)
            
            if type_content:
                type_sizes = [len(c) for c in type_content]
                type_tokens = [count_tokens(c) for c in type_content]
                stats["chunks_per_resource"].append({
                    "resource_type": resource_type,
                    "total_chunks": 1,  # One child chunk per type
                    "parent_chunks": 0,
                    "child_chunks": 1,
                    "resource_count": len(type_resources),
                    "avg_child_size": sum(type_sizes) if type_sizes else 0,
                    "avg_child_tokens": sum(type_tokens) if type_tokens else 0
                })
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    if stats["parent_chunks"] > 0:
        stats["avg_parent_size"] = stats["parent_chunk_chars"] / stats["parent_chunks"]
        stats["avg_parent_tokens"] = stats["parent_chunk_tokens"] / stats["parent_chunks"]
    if stats["child_chunks"] > 0:
        stats["avg_child_size"] = stats["child_chunk_chars"] / stats["child_chunks"]
        stats["avg_child_tokens"] = stats["child_chunk_tokens"] / stats["child_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def process_file_bundle_parent_individual_children(file_path: str) -> Dict:
    """
    Process a file where:
    - Parent = entire FHIR bundle (all resources combined)
    - Children = individual resources (direct chunks, one per resource, no splitting)
    """
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "parent_chunks": 0,
        "child_chunks": 0,
        "total_chunk_chars": 0,
        "parent_chunk_chars": 0,
        "child_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "parent_chunk_tokens": 0,
        "child_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_parent_size": 0,
        "avg_child_size": 0,
        "avg_chunk_tokens": 0,
        "avg_parent_tokens": 0,
        "avg_child_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0
    }
    
    if not resources:
        return stats
    
    start_time = time.time()
    
    # Build parent document: combine ALL resources into one text
    parent_parts = []
    child_chunks = []
    
    for resource in resources:
        content = extract_content_from_resource(resource)
        if not content:
            continue
        
        # Add to parent (entire file)
        parent_parts.append(content)
        
        # Create individual child chunk (direct chunk, no splitting)
        child_chunks.append({
            "content": content,
            "resource_type": resource.get("resourceType", "Unknown"),
            "resource_id": resource.get("id", ""),
            "full_url": resource.get("fullUrl", "")
        })
    
    # Create parent: entire file content
    parent_text = "\n\n".join(parent_parts)
    all_parents = [parent_text] if parent_text else []
    
    # Children are individual resources (already created above)
    all_children = [child["content"] for child in child_chunks]
    
    if all_parents or all_children:
        parent_sizes = [len(p) for p in all_parents]
        child_sizes = [len(c) for c in all_children]
        parent_tokens = [count_tokens(p) for p in all_parents]
        child_tokens = [count_tokens(c) for c in all_children]
        all_sizes = parent_sizes + child_sizes
        all_tokens = parent_tokens + child_tokens
        
        stats["total_chunks"] = len(all_parents) + len(all_children)
        stats["parent_chunks"] = len(all_parents)
        stats["child_chunks"] = len(all_children)
        stats["total_chunk_chars"] = sum(all_sizes)
        stats["parent_chunk_chars"] = sum(parent_sizes)
        stats["child_chunk_chars"] = sum(child_sizes)
        stats["total_chunk_tokens"] = sum(all_tokens)
        stats["parent_chunk_tokens"] = sum(parent_tokens)
        stats["child_chunk_tokens"] = sum(child_tokens)
        
        if all_sizes:
            stats["min_chunk_size"] = min(all_sizes)
            stats["max_chunk_size"] = max(all_sizes)
        if all_tokens:
            stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], min(all_tokens))
            stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], max(all_tokens))
        
        # Track stats per resource type
        resource_type_counts = {}
        for child in child_chunks:
            resource_type = child["resource_type"]
            if resource_type not in resource_type_counts:
                resource_type_counts[resource_type] = {
                    "count": 0,
                    "sizes": [],
                    "tokens": []
                }
            resource_type_counts[resource_type]["count"] += 1
            resource_type_counts[resource_type]["sizes"].append(len(child["content"]))
            resource_type_counts[resource_type]["tokens"].append(count_tokens(child["content"]))
        
        for resource_type, counts in resource_type_counts.items():
            stats["chunks_per_resource"].append({
                "resource_type": resource_type,
                "total_chunks": counts["count"],
                "parent_chunks": 0,
                "child_chunks": counts["count"],
                "avg_child_size": sum(counts["sizes"]) / len(counts["sizes"]) if counts["sizes"] else 0,
                "avg_child_tokens": sum(counts["tokens"]) / len(counts["tokens"]) if counts["tokens"] else 0
            })
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    if stats["parent_chunks"] > 0:
        stats["avg_parent_size"] = stats["parent_chunk_chars"] / stats["parent_chunks"]
        stats["avg_parent_tokens"] = stats["parent_chunk_tokens"] / stats["parent_chunks"]
    if stats["child_chunks"] > 0:
        stats["avg_child_size"] = stats["child_chunk_chars"] / stats["child_chunks"]
        stats["avg_child_tokens"] = stats["child_chunk_tokens"] / stats["child_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def process_file_bundle_parent_recursive_json_children(file_path: str, max_chunk_size: int = 1000, min_chunk_size: int = 800) -> Dict:
    """
    Process a file where:
    - Parent = entire FHIR bundle (all resources combined)
    - Children = recursive JSON chunks from individual resources using RecursiveJsonSplitter
    """
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "parent_chunks": 0,
        "child_chunks": 0,
        "total_chunk_chars": 0,
        "parent_chunk_chars": 0,
        "child_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "parent_chunk_tokens": 0,
        "child_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_parent_size": 0,
        "avg_child_size": 0,
        "avg_chunk_tokens": 0,
        "avg_parent_tokens": 0,
        "avg_child_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "processing_time": 0
    }
    
    if not LANGCHAIN_AVAILABLE or RecursiveJsonSplitter is None:
        logger.warning("LangChain RecursiveJsonSplitter not available")
        return stats
    
    if not resources:
        return stats
    
    start_time = time.time()
    
    # Create JSON splitter for children
    json_splitter = RecursiveJsonSplitter(
        max_chunk_size=max_chunk_size,
        min_chunk_size=min_chunk_size
    )
    
    # Build parent document: combine ALL resources into one text
    parent_parts = []
    all_children = []
    
    for resource in resources:
        resource_obj = resource.get("resource", {})
        if not resource_obj:
            continue
        
        # Extract content for parent
        content = extract_content_from_resource(resource)
        if content:
            parent_parts.append(content)
        
        # Create child chunks using RecursiveJsonSplitter on the JSON
        try:
            resource_json = json.dumps(resource_obj, ensure_ascii=False)
            
            # Only split if JSON is large enough
            if len(resource_json) < json_splitter.min_chunk_size:
                # Too small, use as single chunk
                child_chunks = [resource_json]
            else:
                try:
                    chunks = json_splitter.split_text(resource_json)
                    # Convert chunks to strings (handle Document objects if returned)
                    child_chunks = []
                    for chunk in chunks:
                        if hasattr(chunk, 'page_content'):
                            child_chunks.append(str(chunk.page_content))
                        elif isinstance(chunk, str):
                            child_chunks.append(chunk)
                        elif isinstance(chunk, dict):
                            child_chunks.append(json.dumps(chunk, ensure_ascii=False))
                        else:
                            child_chunks.append(str(chunk))
                except (IndexError, ValueError, KeyError) as split_error:
                    # If splitting fails, use whole JSON as one chunk
                    logger.debug(f"JSON splitter failed for resource {resource.get('id', 'unknown')}: {split_error}")
                    child_chunks = [resource_json]
            
            all_children.extend(child_chunks)
            
        except Exception as e:
            logger.warning(f"Could not process resource {resource.get('id', 'unknown')}: {e}")
            continue
    
    # Create parent: entire file content
    parent_text = "\n\n".join(parent_parts)
    all_parents = [parent_text] if parent_text else []
    
    if all_parents or all_children:
        parent_sizes = [len(p) for p in all_parents]
        child_sizes = [len(c) for c in all_children]
        parent_tokens = [count_tokens(p) for p in all_parents]
        child_tokens = [count_tokens(c) for c in all_children]
        all_sizes = parent_sizes + child_sizes
        all_tokens = parent_tokens + child_tokens
        
        stats["total_chunks"] = len(all_parents) + len(all_children)
        stats["parent_chunks"] = len(all_parents)
        stats["child_chunks"] = len(all_children)
        stats["total_chunk_chars"] = sum(all_sizes)
        stats["parent_chunk_chars"] = sum(parent_sizes)
        stats["child_chunk_chars"] = sum(child_sizes)
        stats["total_chunk_tokens"] = sum(all_tokens)
        stats["parent_chunk_tokens"] = sum(parent_tokens)
        stats["child_chunk_tokens"] = sum(child_tokens)
        
        if all_sizes:
            stats["min_chunk_size"] = min(all_sizes)
            stats["max_chunk_size"] = max(all_sizes)
        if all_tokens:
            stats["min_chunk_tokens"] = min(all_tokens)
            stats["max_chunk_tokens"] = max(all_tokens)
    
    stats["processing_time"] = time.time() - start_time
    
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    if stats["parent_chunks"] > 0:
        stats["avg_parent_size"] = stats["parent_chunk_chars"] / stats["parent_chunks"]
        stats["avg_parent_tokens"] = stats["parent_chunk_tokens"] / stats["parent_chunks"]
    if stats["child_chunks"] > 0:
        stats["avg_child_size"] = stats["child_chunk_chars"] / stats["child_chunks"]
        stats["avg_child_tokens"] = stats["child_chunk_tokens"] / stats["child_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def get_chunking_strategy_for_resource(resource_type: str, content_length: int) -> Dict:
    """
    Return appropriate chunking parameters based on resource type and content length.
    
    This implements resource-aware chunking that adapts to different FHIR resource types.
    """
    # Small, atomic resources - no chunking needed (single chunk)
    if resource_type in ["Patient", "Medication", "Organization"]:
        return {
            "chunk_directly": True,  # Single chunk, no parent-child
            "reason": "Atomic resource, preserve as single unit"
        }
    
    # Medium resources - smaller parent-child with semantic
    elif resource_type in ["Condition", "MedicationRequest", "Immunization", "Procedure"]:
        return {
            "parent_chunk_size": 1500,  # Smaller parents for these
            "child_chunk_size": 400,
            "parent_overlap": 150,
            "child_overlap": 40,
            "use_semantic": True,
            "semantic_threshold": 0.75  # Slightly higher for structured medical content
        }
    
    # Large, narrative resources - full parent-child with semantic
    elif resource_type in ["DiagnosticReport", "Encounter"]:
        return {
            "parent_chunk_size": 2000,
            "child_chunk_size": 500,
            "parent_overlap": 200,
            "child_overlap": 50,
            "use_semantic": True,
            "semantic_threshold": 0.75
        }
    
    # Observation resources - often many, can be small
    elif resource_type == "Observation":
        if content_length < 300:
            return {"chunk_directly": True}
        else:
            return {
                "parent_chunk_size": 1000,
                "child_chunk_size": 300,
                "parent_overlap": 100,
                "child_overlap": 30,
                "use_semantic": True,
                "semantic_threshold": 0.75
            }
    
    # Default for unknown types - use standard parent-child
    else:
        return {
            "parent_chunk_size": 1500,
            "child_chunk_size": 400,
            "parent_overlap": 150,
            "child_overlap": 40,
            "use_semantic": True,
            "semantic_threshold": 0.75
        }


def process_file_resource_aware_chunking(file_path: str) -> Dict:
    """
    Process a file using resource-aware hierarchical chunking.
    
    This strategy:
    - Chunks at the resource level (not document level)
    - Uses resource-type-specific chunking parameters
    - Preserves resource relationships
    - Uses parent-child with semantic chunking for children
    """
    bundle = load_fhir_bundle(file_path)
    if not bundle:
        return None
    
    resources = extract_resources_from_bundle(bundle)
    patient_id = extract_patient_id(resources)
    
    stats = {
        "file": os.path.basename(file_path),
        "patient_id": patient_id,
        "total_resources": len(resources),
        "total_chunks": 0,
        "parent_chunks": 0,
        "child_chunks": 0,
        "direct_chunks": 0,  # Resources chunked directly (no parent-child)
        "total_chunk_chars": 0,
        "parent_chunk_chars": 0,
        "child_chunk_chars": 0,
        "direct_chunk_chars": 0,
        "total_chunk_tokens": 0,
        "parent_chunk_tokens": 0,
        "child_chunk_tokens": 0,
        "direct_chunk_tokens": 0,
        "avg_chunk_size": 0,
        "avg_parent_size": 0,
        "avg_child_size": 0,
        "avg_direct_size": 0,
        "avg_chunk_tokens": 0,
        "avg_parent_tokens": 0,
        "avg_child_tokens": 0,
        "avg_direct_tokens": 0,
        "min_chunk_size": float('inf'),
        "max_chunk_size": 0,
        "min_chunk_tokens": float('inf'),
        "max_chunk_tokens": 0,
        "chunks_per_resource": [],
        "resource_type_strategies": {},  # Track which strategies were used
        "processing_time": 0
    }
    
    start_time = time.time()
    
    for resource in resources:
        resource_type = resource.get("resourceType", "Unknown")
        content = extract_content_from_resource(resource)
        if not content:
            continue
        
        content_length = len(content)
        strategy = get_chunking_strategy_for_resource(resource_type, content_length)
        
        # Track strategy usage
        strategy_key = f"{resource_type}_{'direct' if strategy.get('chunk_directly') else 'parent_child'}"
        if strategy_key not in stats["resource_type_strategies"]:
            stats["resource_type_strategies"][strategy_key] = 0
        stats["resource_type_strategies"][strategy_key] += 1
        
        # Direct chunking for small/atomic resources
        if strategy.get("chunk_directly", False):
            # Single chunk, no parent-child
            chunk_size = len(content)
            chunk_tokens = count_tokens(content)
            
            stats["total_chunks"] += 1
            stats["direct_chunks"] += 1
            stats["total_chunk_chars"] += chunk_size
            stats["direct_chunk_chars"] += chunk_size
            stats["total_chunk_tokens"] += chunk_tokens
            stats["direct_chunk_tokens"] += chunk_tokens
            stats["min_chunk_size"] = min(stats["min_chunk_size"], chunk_size)
            stats["max_chunk_size"] = max(stats["max_chunk_size"], chunk_size)
            stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], chunk_tokens)
            stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], chunk_tokens)
            
            stats["chunks_per_resource"].append({
                "resource_type": resource_type,
                "total_chunks": 1,
                "parent_chunks": 0,
                "child_chunks": 0,
                "direct_chunks": 1,
                "strategy": "direct",
                "avg_direct_size": chunk_size,
                "avg_direct_tokens": chunk_tokens
            })
        
        # Parent-child chunking with resource-specific parameters
        else:
            chunk_hierarchy = parent_child_chunking(
                content,
                parent_chunk_size=strategy.get("parent_chunk_size", 1500),
                child_chunk_size=strategy.get("child_chunk_size", 400),
                parent_overlap=strategy.get("parent_overlap", 150),
                child_overlap=strategy.get("child_overlap", 40),
                use_semantic_for_children=strategy.get("use_semantic", True),
                semantic_threshold=strategy.get("semantic_threshold", 0.75)
            )
            
            if chunk_hierarchy:
                parents = [c for c in chunk_hierarchy if c["chunk_type"] == "parent"]
                children = [c for c in chunk_hierarchy if c["chunk_type"] == "child"]
                
                parent_sizes = [p["chunk_size"] for p in parents]
                child_sizes = [c["chunk_size"] for c in children]
                parent_tokens = [count_tokens(p["text"]) for p in parents]
                child_tokens = [count_tokens(c["text"]) for c in children]
                all_sizes = parent_sizes + child_sizes
                all_tokens = parent_tokens + child_tokens
                
                stats["total_chunks"] += len(chunk_hierarchy)
                stats["parent_chunks"] += len(parents)
                stats["child_chunks"] += len(children)
                stats["total_chunk_chars"] += sum(all_sizes)
                stats["parent_chunk_chars"] += sum(parent_sizes)
                stats["child_chunk_chars"] += sum(child_sizes)
                stats["total_chunk_tokens"] += sum(all_tokens)
                stats["parent_chunk_tokens"] += sum(parent_tokens)
                stats["child_chunk_tokens"] += sum(child_tokens)
                
                if all_sizes:
                    stats["min_chunk_size"] = min(stats["min_chunk_size"], min(all_sizes))
                    stats["max_chunk_size"] = max(stats["max_chunk_size"], max(all_sizes))
                if all_tokens:
                    stats["min_chunk_tokens"] = min(stats["min_chunk_tokens"], min(all_tokens))
                    stats["max_chunk_tokens"] = max(stats["max_chunk_tokens"], max(all_tokens))
                
                stats["chunks_per_resource"].append({
                    "resource_type": resource_type,
                    "total_chunks": len(chunk_hierarchy),
                    "parent_chunks": len(parents),
                    "child_chunks": len(children),
                    "direct_chunks": 0,
                    "strategy": "parent_child",
                    "strategy_params": {
                        "parent_chunk_size": strategy.get("parent_chunk_size", 1500),
                        "child_chunk_size": strategy.get("child_chunk_size", 400),
                        "semantic_threshold": strategy.get("semantic_threshold", 0.75)
                    },
                    "avg_parent_size": sum(parent_sizes) / len(parents) if parents else 0,
                    "avg_child_size": sum(child_sizes) / len(children) if children else 0,
                    "avg_parent_tokens": sum(parent_tokens) / len(parents) if parents else 0,
                    "avg_child_tokens": sum(child_tokens) / len(children) if children else 0
                })
    
    stats["processing_time"] = time.time() - start_time
    
    # Calculate averages
    if stats["total_chunks"] > 0:
        stats["avg_chunk_size"] = stats["total_chunk_chars"] / stats["total_chunks"]
        stats["avg_chunk_tokens"] = stats["total_chunk_tokens"] / stats["total_chunks"]
    if stats["parent_chunks"] > 0:
        stats["avg_parent_size"] = stats["parent_chunk_chars"] / stats["parent_chunks"]
        stats["avg_parent_tokens"] = stats["parent_chunk_tokens"] / stats["parent_chunks"]
    if stats["child_chunks"] > 0:
        stats["avg_child_size"] = stats["child_chunk_chars"] / stats["child_chunks"]
        stats["avg_child_tokens"] = stats["child_chunk_tokens"] / stats["child_chunks"]
    if stats["direct_chunks"] > 0:
        stats["avg_direct_size"] = stats["direct_chunk_chars"] / stats["direct_chunks"]
        stats["avg_direct_tokens"] = stats["direct_chunk_tokens"] / stats["direct_chunks"]
    else:
        stats["min_chunk_size"] = 0
        stats["min_chunk_tokens"] = 0
    
    return stats


def run_comparison_test(data_dir: str, num_files: int = 1000, output_file: str = "chunking_comparison_results.json"):
    """Run comparison test on specified number of files."""
    
    # Get list of JSON files
    data_path = Path(data_dir)
    json_files = list(data_path.glob("*.json"))[:num_files]
    
    if not json_files:
        logger.error(f"No JSON files found in {data_dir}")
        return
    
    logger.info(f"Found {len(json_files)} files to process")
    logger.info("="*80)
    
    # Clear caches before first test
    logger.info("\nClearing caches between tests for fair comparison...")
    clear_caches()
    logger.info("="*80)
    
    # Process with LangChain semantic chunking
    logger.info("Processing with LANGCHAIN SEMANTIC CHUNKING...")
    langchain_semantic_results = []
    langchain_semantic_start = time.time()
    
    for i, file_path in enumerate(json_files, 1):
        if i % 100 == 0:
            logger.info(f"  Processed {i}/{len(json_files)} files...")
        
        stats = process_file_langchain_semantic_chunking(str(file_path))
        if stats:
            langchain_semantic_results.append(stats)
    
    langchain_semantic_total_time = time.time() - langchain_semantic_start
    logger.info(f"Completed LangChain semantic chunking in {langchain_semantic_total_time:.2f} seconds")
    logger.info("="*80)
    
    # Clear caches before second test
    logger.info("\nClearing caches between tests for fair comparison...")
    clear_caches()
    logger.info("="*80)
    
    # Process with resource-aware chunking
    logger.info("Processing with RESOURCE-AWARE CHUNKING...")
    resource_aware_results = []
    resource_aware_start = time.time()
    
    for i, file_path in enumerate(json_files, 1):
        if i % 100 == 0:
            logger.info(f"  Processed {i}/{len(json_files)} files...")
        
        stats = process_file_resource_aware_chunking(str(file_path))
        if stats:
            resource_aware_results.append(stats)
    
    resource_aware_total_time = time.time() - resource_aware_start
    logger.info(f"Completed resource-aware chunking in {resource_aware_total_time:.2f} seconds")
    logger.info("="*80)
    
    # Clear caches before third test
    logger.info("\nClearing caches between tests for fair comparison...")
    clear_caches()
    logger.info("="*80)
    
    # Process with Recursive JSON chunking
    logger.info("Processing with RECURSIVE JSON CHUNKING...")
    recursive_json_results = []
    recursive_json_start = time.time()
    
    for i, file_path in enumerate(json_files, 1):
        if i % 100 == 0:
            logger.info(f"  Processed {i}/{len(json_files)} files...")
        
        stats = process_file_recursive_json(str(file_path))
        if stats:
            recursive_json_results.append(stats)
    
    recursive_json_total_time = time.time() - recursive_json_start
    logger.info(f"Completed Recursive JSON chunking in {recursive_json_total_time:.2f} seconds")
    logger.info("="*80)
    
    # Clear caches before fourth test
    logger.info("\nClearing caches between tests for fair comparison...")
    clear_caches()
    logger.info("="*80)
    
    # Process with Bundle-as-Parent, Resources-as-Children
    logger.info("Processing with BUNDLE-AS-PARENT, RESOURCES-AS-CHILDREN...")
    bundle_parent_results = []
    bundle_parent_start = time.time()
    
    for i, file_path in enumerate(json_files, 1):
        if i % 100 == 0:
            logger.info(f"  Processed {i}/{len(json_files)} files...")
        
        stats = process_file_bundle_parent_individual_children(str(file_path))
        if stats:
            bundle_parent_results.append(stats)
    
    bundle_parent_total_time = time.time() - bundle_parent_start
    logger.info(f"Completed Bundle-as-Parent chunking in {bundle_parent_total_time:.2f} seconds")
    logger.info("="*80)
    
    # Calculate aggregate statistics
    def aggregate_stats(results: List[Dict]) -> Dict:
        if not results:
            return {}
        
        agg = {
            "total_files": len(results),
            "total_resources": sum(r["total_resources"] for r in results),
            "total_chunks": sum(r["total_chunks"] for r in results),
            "total_chunk_chars": sum(r["total_chunk_chars"] for r in results),
            "total_chunk_tokens": sum(r.get("total_chunk_tokens", 0) for r in results),
            "avg_chunks_per_file": sum(r["total_chunks"] for r in results) / len(results),
            "avg_chunk_size": 0,
            "avg_chunk_tokens": 0,
            "min_chunk_size": min(r["min_chunk_size"] for r in results if r["min_chunk_size"] != float('inf')),
            "max_chunk_size": max(r["max_chunk_size"] for r in results),
            "min_chunk_tokens": min(r.get("min_chunk_tokens", float('inf')) for r in results if r.get("min_chunk_tokens", float('inf')) != float('inf')),
            "max_chunk_tokens": max(r.get("max_chunk_tokens", 0) for r in results),
            "total_processing_time": sum(r["processing_time"] for r in results),
            "avg_processing_time_per_file": sum(r["processing_time"] for r in results) / len(results)
        }
        
        if agg["total_chunks"] > 0:
            agg["avg_chunk_size"] = agg["total_chunk_chars"] / agg["total_chunks"]
            agg["avg_chunk_tokens"] = agg["total_chunk_tokens"] / agg["total_chunks"]
        
        return agg
    
    # Aggregate stats for all chunking methods
    langchain_semantic_agg = aggregate_stats(langchain_semantic_results) if langchain_semantic_results else {}
    resource_aware_agg = aggregate_stats(resource_aware_results) if resource_aware_results else {}
    recursive_json_agg = aggregate_stats(recursive_json_results) if recursive_json_results else {}
    bundle_parent_agg = aggregate_stats(bundle_parent_results) if bundle_parent_results else {}
    
    # Add resource-aware specific stats
    if resource_aware_results:
        resource_aware_agg["total_parent_chunks"] = sum(r["parent_chunks"] for r in resource_aware_results)
        resource_aware_agg["total_child_chunks"] = sum(r["child_chunks"] for r in resource_aware_results)
        resource_aware_agg["total_direct_chunks"] = sum(r.get("direct_chunks", 0) for r in resource_aware_results)
        resource_aware_agg["avg_parent_size"] = sum(r.get("avg_parent_size", 0) for r in resource_aware_results) / len(resource_aware_results) if resource_aware_agg.get("total_parent_chunks", 0) > 0 else 0
        resource_aware_agg["avg_child_size"] = sum(r.get("avg_child_size", 0) for r in resource_aware_results) / len(resource_aware_results) if resource_aware_agg.get("total_child_chunks", 0) > 0 else 0
        resource_aware_agg["avg_direct_size"] = sum(r.get("avg_direct_size", 0) for r in resource_aware_results) / len(resource_aware_results) if resource_aware_agg.get("total_direct_chunks", 0) > 0 else 0
        resource_aware_agg["avg_parent_tokens"] = sum(r.get("avg_parent_tokens", 0) for r in resource_aware_results) / len(resource_aware_results) if resource_aware_agg.get("total_parent_chunks", 0) > 0 else 0
        resource_aware_agg["avg_child_tokens"] = sum(r.get("avg_child_tokens", 0) for r in resource_aware_results) / len(resource_aware_results) if resource_aware_agg.get("total_child_chunks", 0) > 0 else 0
        resource_aware_agg["avg_direct_tokens"] = sum(r.get("avg_direct_tokens", 0) for r in resource_aware_results) / len(resource_aware_results) if resource_aware_agg.get("total_direct_chunks", 0) > 0 else 0
        resource_aware_agg["parent_to_child_ratio"] = resource_aware_agg["total_parent_chunks"] / resource_aware_agg["total_child_chunks"] if resource_aware_agg.get("total_child_chunks", 0) > 0 else 0
        # Aggregate resource type strategies
        all_strategies = {}
        for r in resource_aware_results:
            for strategy_key, count in r.get("resource_type_strategies", {}).items():
                all_strategies[strategy_key] = all_strategies.get(strategy_key, 0) + count
        resource_aware_agg["resource_type_strategies"] = all_strategies
    
    # Add bundle-parent specific stats
    if bundle_parent_results:
        bundle_parent_agg["total_parent_chunks"] = sum(r["parent_chunks"] for r in bundle_parent_results)
        bundle_parent_agg["total_child_chunks"] = sum(r["child_chunks"] for r in bundle_parent_results)
        bundle_parent_agg["avg_parent_size"] = sum(r.get("avg_parent_size", 0) for r in bundle_parent_results) / len(bundle_parent_results) if bundle_parent_agg.get("total_parent_chunks", 0) > 0 else 0
        bundle_parent_agg["avg_child_size"] = sum(r.get("avg_child_size", 0) for r in bundle_parent_results) / len(bundle_parent_results) if bundle_parent_agg.get("total_child_chunks", 0) > 0 else 0
        bundle_parent_agg["avg_parent_tokens"] = sum(r.get("avg_parent_tokens", 0) for r in bundle_parent_results) / len(bundle_parent_results) if bundle_parent_agg.get("total_parent_chunks", 0) > 0 else 0
        bundle_parent_agg["avg_child_tokens"] = sum(r.get("avg_child_tokens", 0) for r in bundle_parent_results) / len(bundle_parent_results) if bundle_parent_agg.get("total_child_chunks", 0) > 0 else 0
        bundle_parent_agg["parent_to_child_ratio"] = bundle_parent_agg["total_parent_chunks"] / bundle_parent_agg["total_child_chunks"] if bundle_parent_agg.get("total_child_chunks", 0) > 0 else 0
    
    # Create comparison report
    comparison = {
        "test_config": {
            "num_files_tested": len(json_files),
            "data_directory": data_dir,
            "langchain_semantic_chunking_config": {
                "method": "langchain_semantic_chunker",
                "breakpoint_threshold_type": "percentile",
                "breakpoint_threshold_amount": 75,
                "embeddings": "ollama_mxbai-embed-large",
                "description": "LangChain SemanticChunker using Ollama embeddings"
            },
            "resource_aware_chunking_config": {
                "method": "resource_aware",
                "description": "Resource-aware hierarchical chunking with type-specific strategies",
                "strategies": {
                    "atomic_resources": {
                        "types": ["Patient", "Medication", "Organization"],
                        "strategy": "direct_chunking",
                        "description": "Single chunk, no parent-child for atomic resources"
                    },
                    "medium_resources": {
                        "types": ["Condition", "MedicationRequest", "Immunization", "Procedure"],
                        "strategy": "parent_child",
                        "parent_chunk_size": 1500,
                        "child_chunk_size": 400,
                        "semantic_threshold": 0.75
                    },
                    "large_resources": {
                        "types": ["DiagnosticReport", "Encounter"],
                        "strategy": "parent_child",
                        "parent_chunk_size": 2000,
                        "child_chunk_size": 500,
                        "semantic_threshold": 0.75
                    },
                    "observation_resources": {
                        "types": ["Observation"],
                        "strategy": "conditional",
                        "small_threshold": 300,
                        "small_strategy": "direct_chunking",
                        "large_strategy": "parent_child",
                        "parent_chunk_size": 1000,
                        "child_chunk_size": 300,
                        "semantic_threshold": 0.75
                    }
                }
            },
            "recursive_json_chunking_config": {
                "method": "recursive_json",
                "max_chunk_size": 1000,
                "min_chunk_size": 100,
                "description": "LangChain RecursiveJsonSplitter - splits JSON structure while preserving hierarchy"
            },
            "bundle_parent_individual_children_config": {
                "method": "bundle_parent_individual_children",
                "description": "Bundle as parent (entire file), individual resources as children (direct chunks)",
                "parent": "Entire FHIR bundle content combined",
                "children": "One child per resource, no further splitting"
            }
        },
        "langchain_semantic_chunking": {
            "aggregate_stats": langchain_semantic_agg,
            "total_processing_time": langchain_semantic_total_time,
            "individual_results": langchain_semantic_results
        },
        "resource_aware_chunking": {
            "aggregate_stats": resource_aware_agg,
            "total_processing_time": resource_aware_total_time,
            "individual_results": resource_aware_results
        },
        "recursive_json_chunking": {
            "aggregate_stats": recursive_json_agg,
            "total_processing_time": recursive_json_total_time,
            "individual_results": recursive_json_results
        },
        "bundle_parent_individual_children": {
            "aggregate_stats": bundle_parent_agg,
            "total_processing_time": bundle_parent_total_time,
            "individual_results": bundle_parent_results
        },
        "comparison": {
            "all_methods_summary": {
                "langchain_semantic": {
                    "total_chunks": langchain_semantic_agg.get("total_chunks", 0),
                    "avg_chunk_size": langchain_semantic_agg.get("avg_chunk_size", 0),
                    "avg_chunk_tokens": langchain_semantic_agg.get("avg_chunk_tokens", 0),
                    "processing_time": langchain_semantic_total_time
                },
                "resource_aware": {
                    "total_chunks": resource_aware_agg.get("total_chunks", 0),
                    "avg_chunk_size": resource_aware_agg.get("avg_chunk_size", 0),
                    "avg_chunk_tokens": resource_aware_agg.get("avg_chunk_tokens", 0),
                    "processing_time": resource_aware_total_time,
                    "parent_chunks": resource_aware_agg.get("total_parent_chunks", 0),
                    "child_chunks": resource_aware_agg.get("total_child_chunks", 0),
                    "direct_chunks": resource_aware_agg.get("total_direct_chunks", 0)
                },
                "recursive_json": {
                    "total_chunks": recursive_json_agg.get("total_chunks", 0),
                    "avg_chunk_size": recursive_json_agg.get("avg_chunk_size", 0),
                    "avg_chunk_tokens": recursive_json_agg.get("avg_chunk_tokens", 0),
                    "processing_time": recursive_json_total_time
                },
                "bundle_parent_individual_children": {
                    "total_chunks": bundle_parent_agg.get("total_chunks", 0),
                    "avg_chunk_size": bundle_parent_agg.get("avg_chunk_size", 0),
                    "avg_chunk_tokens": bundle_parent_agg.get("avg_chunk_tokens", 0),
                    "processing_time": bundle_parent_total_time,
                    "parent_chunks": bundle_parent_agg.get("total_parent_chunks", 0),
                    "child_chunks": bundle_parent_agg.get("total_child_chunks", 0)
                }
            },
            "files_processed": {
                "langchain_semantic": len(langchain_semantic_results),
                "resource_aware": len(resource_aware_results),
                "recursive_json": len(recursive_json_results),
                "bundle_parent_individual_children": len(bundle_parent_results)
            }
        }
    }
    
    # Write results to file
    output_path = Path(__file__).parent / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(comparison, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\nResults written to: {output_path}")
    logger.info("\n" + "="*80)
    logger.info("COMPARISON SUMMARY")
    logger.info("="*80)
    logger.info(f"Files processed: {len(json_files)}")
    
    logger.info(f"\n1. LANGCHAIN SEMANTIC CHUNKING:")
    logger.info(f"   Total chunks: {langchain_semantic_agg.get('total_chunks', 0):,}")
    logger.info(f"   Avg chunk size: {langchain_semantic_agg.get('avg_chunk_size', 0):.1f} chars")
    logger.info(f"   Avg chunk tokens: {langchain_semantic_agg.get('avg_chunk_tokens', 0):.1f} tokens")
    logger.info(f"   Processing time: {langchain_semantic_total_time:.2f} seconds")
    
    logger.info(f"\n2. RESOURCE-AWARE CHUNKING:")
    logger.info(f"   Total chunks: {resource_aware_agg.get('total_chunks', 0):,}")
    logger.info(f"   Parent chunks: {resource_aware_agg.get('total_parent_chunks', 0):,}")
    logger.info(f"   Child chunks: {resource_aware_agg.get('total_child_chunks', 0):,}")
    logger.info(f"   Direct chunks: {resource_aware_agg.get('total_direct_chunks', 0):,}")
    logger.info(f"   Avg chunk size: {resource_aware_agg.get('avg_chunk_size', 0):.1f} chars")
    logger.info(f"   Avg parent size: {resource_aware_agg.get('avg_parent_size', 0):.1f} chars")
    logger.info(f"   Avg child size: {resource_aware_agg.get('avg_child_size', 0):.1f} chars")
    logger.info(f"   Avg direct size: {resource_aware_agg.get('avg_direct_size', 0):.1f} chars")
    logger.info(f"   Avg chunk tokens: {resource_aware_agg.get('avg_chunk_tokens', 0):.1f} tokens")
    logger.info(f"   Processing time: {resource_aware_total_time:.2f} seconds")
    if resource_aware_agg.get("resource_type_strategies"):
        logger.info(f"   Resource strategies used: {len(resource_aware_agg['resource_type_strategies'])} different strategies")
    
    logger.info(f"\n3. RECURSIVE JSON CHUNKING:")
    logger.info(f"   Total chunks: {recursive_json_agg.get('total_chunks', 0):,}")
    logger.info(f"   Avg chunk size: {recursive_json_agg.get('avg_chunk_size', 0):.1f} chars")
    logger.info(f"   Avg chunk tokens: {recursive_json_agg.get('avg_chunk_tokens', 0):.1f} tokens")
    logger.info(f"   Processing time: {recursive_json_total_time:.2f} seconds")
    
    logger.info(f"\n4. BUNDLE-AS-PARENT, RESOURCES-AS-CHILDREN:")
    logger.info(f"   Total chunks: {bundle_parent_agg.get('total_chunks', 0):,}")
    logger.info(f"   Parent chunks: {bundle_parent_agg.get('total_parent_chunks', 0):,}")
    logger.info(f"   Child chunks: {bundle_parent_agg.get('total_child_chunks', 0):,}")
    logger.info(f"   Avg chunk size: {bundle_parent_agg.get('avg_chunk_size', 0):.1f} chars")
    logger.info(f"   Avg parent size: {bundle_parent_agg.get('avg_parent_size', 0):.1f} chars")
    logger.info(f"   Avg child size: {bundle_parent_agg.get('avg_child_size', 0):.1f} chars")
    logger.info(f"   Avg chunk tokens: {bundle_parent_agg.get('avg_chunk_tokens', 0):.1f} tokens")
    logger.info(f"   Processing time: {bundle_parent_total_time:.2f} seconds")
    
    logger.info(f"\n{'='*80}")
    logger.info("RANKING BY PROCESSING SPEED (fastest first):")
    times = [
        ("LangChain Semantic", langchain_semantic_total_time),
        ("Resource-Aware", resource_aware_total_time),
        ("Recursive JSON", recursive_json_total_time),
        ("Bundle-as-Parent", bundle_parent_total_time)
    ]
    times.sort(key=lambda x: x[1])
    for i, (name, time_val) in enumerate(times, 1):
        logger.info(f"  {i}. {name}: {time_val:.2f} seconds")
    
    logger.info(f"\n{'='*80}")
    logger.info("RANKING BY CHUNK COUNT (most chunks first):")
    chunks = [
        ("LangChain Semantic", langchain_semantic_agg.get('total_chunks', 0)),
        ("Resource-Aware", resource_aware_agg.get('total_chunks', 0)),
        ("Recursive JSON", recursive_json_agg.get('total_chunks', 0)),
        ("Bundle-as-Parent", bundle_parent_agg.get('total_chunks', 0))
    ]
    chunks.sort(key=lambda x: x[1], reverse=True)
    for i, (name, count) in enumerate(chunks, 1):
        logger.info(f"  {i}. {name}: {count:,} chunks")
    
    logger.info("="*80)


def run_recursive_json_size_comparison(data_dir: str, num_files: int = 10000, output_file: str = "recursive_json_size_comparison.json"):
    """
    Test RecursiveJsonSplitter with different max_chunk_size and min_chunk_size values.
    
    Original tests:
    - max_chunk_size=500, min_chunk_size=100
    - max_chunk_size=750, min_chunk_size=100
    - max_chunk_size=1000, min_chunk_size=100
    
    Additional tests:
    - max_chunk_size=500, min_chunk_size=300
    - max_chunk_size=750, min_chunk_size=500
    - max_chunk_size=1000, min_chunk_size=750
    - max_chunk_size=1000, min_chunk_size=500
    """
    import statistics
    
    # Get list of JSON files
    data_path = Path(data_dir)
    json_files = list(data_path.glob("*.json"))[:num_files]
    
    if not json_files:
        logger.error(f"No JSON files found in {data_dir}")
        return
    
    logger.info(f"Found {len(json_files)} files to process")
    logger.info("="*80)
    
    # Test configurations
    configs = [
        # Original tests
        {"max_chunk_size": 500, "min_chunk_size": 100, "name": "max500_min100"},
        {"max_chunk_size": 750, "min_chunk_size": 100, "name": "max750_min100"},
        {"max_chunk_size": 1000, "min_chunk_size": 100, "name": "max1000_min100"},
        # New tests with different min/max combinations
        {"max_chunk_size": 500, "min_chunk_size": 300, "name": "max500_min300"},
        {"max_chunk_size": 750, "min_chunk_size": 500, "name": "max750_min500"},
        {"max_chunk_size": 1000, "min_chunk_size": 750, "name": "max1000_min750"},
        {"max_chunk_size": 1000, "min_chunk_size": 500, "name": "max1000_min500"}
    ]
    
    all_results = {}
    
    for config in configs:
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing: max_chunk_size={config['max_chunk_size']}, min_chunk_size={config['min_chunk_size']}")
        logger.info(f"{'='*80}")
        
        clear_caches()
        
        results = []
        start_time = time.time()
        
        for i, file_path in enumerate(json_files, 1):
            if i % 1000 == 0:
                logger.info(f"  Processed {i}/{len(json_files)} files...")
            
            stats = process_file_recursive_json(
                str(file_path),
                max_chunk_size=config["max_chunk_size"],
                min_chunk_size=config["min_chunk_size"]
            )
            if stats:
                results.append(stats)
        
        total_time = time.time() - start_time
        
        # Aggregate statistics
        if results:
            all_chunk_tokens = []
            for r in results:
                # Reconstruct all chunk tokens from individual results for median calculation
                # We'll calculate median from per-file medians (approximation)
                # Or we can collect all tokens if we modify the function
                pass
            
            # Calculate aggregate stats
            agg = {
                "config": config,
                "total_files": len(results),
                "total_resources": sum(r["total_resources"] for r in results),
                "total_chunks": sum(r["total_chunks"] for r in results),
                "total_chunk_chars": sum(r["total_chunk_chars"] for r in results),
                "total_chunk_tokens": sum(r.get("total_chunk_tokens", 0) for r in results),
                "avg_chunks_per_file": sum(r["total_chunks"] for r in results) / len(results),
                "avg_chunk_size": 0,
                "avg_chunk_tokens": 0,
                "median_chunk_tokens": 0,  # Will calculate from all chunks
                "min_chunk_size": min(r["min_chunk_size"] for r in results if r["min_chunk_size"] != float('inf')),
                "max_chunk_size": max(r["max_chunk_size"] for r in results),
                "min_chunk_tokens": min(r.get("min_chunk_tokens", float('inf')) for r in results if r.get("min_chunk_tokens", float('inf')) != float('inf')),
                "max_chunk_tokens": max(r.get("max_chunk_tokens", 0) for r in results),
                "total_processing_time": sum(r["processing_time"] for r in results),
                "avg_processing_time_per_file": sum(r["processing_time"] for r in results) / len(results),
                "total_wall_time": total_time
            }
            
            if agg["total_chunks"] > 0:
                agg["avg_chunk_size"] = agg["total_chunk_chars"] / agg["total_chunks"]
                agg["avg_chunk_tokens"] = agg["total_chunk_tokens"] / agg["total_chunks"]
            
            # Calculate true median by collecting all token counts from chunks_per_resource
            # This gives us a better approximation than median of medians
            all_token_counts = []
            for r in results:
                # Collect token counts from chunks_per_resource (more granular than file-level)
                for resource_info in r.get("chunks_per_resource", []):
                    chunk_count = resource_info.get("chunk_count", 0)
                    avg_tokens = resource_info.get("avg_chunk_tokens", 0)
                    if chunk_count > 0 and avg_tokens > 0:
                        # Use average tokens for each chunk in this resource
                        # This is an approximation but better than median of medians
                        all_token_counts.extend([avg_tokens] * chunk_count)
            
            # Calculate true median from all collected token counts
            if all_token_counts:
                sorted_tokens = sorted(all_token_counts)
                n = len(sorted_tokens)
                if n % 2 == 0:
                    agg["median_chunk_tokens"] = (sorted_tokens[n//2 - 1] + sorted_tokens[n//2]) / 2
                else:
                    agg["median_chunk_tokens"] = sorted_tokens[n//2]
            else:
                # Fallback: calculate median of file-level medians
                file_medians = [r.get("median_chunk_tokens", 0) for r in results if r.get("median_chunk_tokens", 0) > 0]
                if file_medians:
                    agg["median_chunk_tokens"] = statistics.median(file_medians)
            
            all_results[config["name"]] = {
                "aggregate_stats": agg,
                "total_processing_time": total_time,
                "individual_results": results
            }
            
            logger.info(f"\nResults for {config['name']}:")
            logger.info(f"  Total chunks: {agg['total_chunks']:,}")
            logger.info(f"  Avg chunk size: {agg['avg_chunk_size']:.1f} chars")
            logger.info(f"  Avg chunk tokens: {agg['avg_chunk_tokens']:.1f} tokens")
            logger.info(f"  Median chunk tokens: {agg['median_chunk_tokens']:.1f} tokens")
            logger.info(f"  Min chunk size: {agg['min_chunk_size']} chars")
            logger.info(f"  Max chunk size: {agg['max_chunk_size']} chars")
            logger.info(f"  Processing time: {total_time:.2f} seconds")
        else:
            all_results[config["name"]] = {
                "aggregate_stats": {},
                "total_processing_time": total_time,
                "individual_results": []
            }
    
    # Write results
    output_path = Path(__file__).parent / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n{'='*80}")
    logger.info("COMPARISON SUMMARY")
    logger.info("="*80)
    logger.info(f"Files processed: {len(json_files)}")
    
    for config in configs:
        name = config["name"]
        if name in all_results and all_results[name]["aggregate_stats"]:
            agg = all_results[name]["aggregate_stats"]
            logger.info(f"\n{name.upper()} (max={config['max_chunk_size']}, min={config['min_chunk_size']}):")
            logger.info(f"  Total chunks: {agg.get('total_chunks', 0):,}")
            logger.info(f"  Avg chunk tokens: {agg.get('avg_chunk_tokens', 0):.1f} tokens")
            logger.info(f"  Median chunk tokens: {agg.get('median_chunk_tokens', 0):.1f} tokens")
            logger.info(f"  Processing time: {agg.get('total_wall_time', 0):.2f} seconds")
    
    logger.info(f"\nResults written to: {output_path}")
    logger.info("="*80)


def run_bundle_parent_json_children_test(data_dir: str, num_files: int = 10000, output_file: str = "bundle_parent_json_children_results.json"):
    """
    Test bundle-as-parent with recursive JSON children chunking.
    
    Compares different min_chunk_size values:
    - min_chunk_size=100, max_chunk_size=1000
    - min_chunk_size=500, max_chunk_size=1000
    - min_chunk_size=800, max_chunk_size=1000
    
    Strategy:
    - Parent = entire FHIR bundle (all resources combined)
    - Children = recursive JSON chunks with different min/max sizes
    """
    # Get list of JSON files
    data_path = Path(data_dir)
    json_files = list(data_path.glob("*.json"))[:num_files]
    
    if not json_files:
        logger.error(f"No JSON files found in {data_dir}")
        return
    
    logger.info(f"Found {len(json_files)} files to process")
    logger.info("="*80)
    
    # Test configurations
    configs = [
        {"max_chunk_size": 1000, "min_chunk_size": 100, "name": "max1000_min100"},
        {"max_chunk_size": 1000, "min_chunk_size": 500, "name": "max1000_min500"},
        {"max_chunk_size": 1000, "min_chunk_size": 800, "name": "max1000_min800"}
    ]
    
    all_results = {}
    
    for config in configs:
        logger.info(f"\n{'='*80}")
        logger.info(f"Testing: Bundle-as-Parent with RecursiveJSON Children")
        logger.info(f"  Parent: Entire FHIR bundle (all resources combined)")
        logger.info(f"  Children: Recursive JSON chunks (max={config['max_chunk_size']}, min={config['min_chunk_size']})")
        logger.info(f"{'='*80}")
        
        clear_caches()
        
        results = []
        start_time = time.time()
        
        for i, file_path in enumerate(json_files, 1):
            if i % 1000 == 0:
                logger.info(f"  Processed {i}/{len(json_files)} files...")
            
            stats = process_file_bundle_parent_recursive_json_children(
                str(file_path),
                max_chunk_size=config["max_chunk_size"],
                min_chunk_size=config["min_chunk_size"]
            )
            if stats:
                results.append(stats)
        
        total_time = time.time() - start_time
        
        # Aggregate statistics for this configuration
        if results:
            agg = {
                "config": config,
                "total_files": len(results),
                "total_resources": sum(r["total_resources"] for r in results),
                "total_chunks": sum(r["total_chunks"] for r in results),
                "parent_chunks": sum(r["parent_chunks"] for r in results),
                "child_chunks": sum(r["child_chunks"] for r in results),
                "total_chunk_chars": sum(r["total_chunk_chars"] for r in results),
                "parent_chunk_chars": sum(r["parent_chunk_chars"] for r in results),
                "child_chunk_chars": sum(r["child_chunk_chars"] for r in results),
                "total_chunk_tokens": sum(r.get("total_chunk_tokens", 0) for r in results),
                "parent_chunk_tokens": sum(r.get("parent_chunk_tokens", 0) for r in results),
                "child_chunk_tokens": sum(r.get("child_chunk_tokens", 0) for r in results),
                "avg_chunks_per_file": sum(r["total_chunks"] for r in results) / len(results),
                "avg_parents_per_file": sum(r["parent_chunks"] for r in results) / len(results),
                "avg_children_per_file": sum(r["child_chunks"] for r in results) / len(results),
                "avg_chunk_size": 0,
                "avg_parent_size": 0,
                "avg_child_size": 0,
                "avg_chunk_tokens": 0,
                "avg_parent_tokens": 0,
                "avg_child_tokens": 0,
                "min_chunk_size": min(r["min_chunk_size"] for r in results if r["min_chunk_size"] != float('inf')),
                "max_chunk_size": max(r["max_chunk_size"] for r in results),
                "min_chunk_tokens": min(r.get("min_chunk_tokens", float('inf')) for r in results if r.get("min_chunk_tokens", float('inf')) != float('inf')),
                "max_chunk_tokens": max(r.get("max_chunk_tokens", 0) for r in results),
                "total_processing_time": sum(r["processing_time"] for r in results),
                "avg_processing_time_per_file": sum(r["processing_time"] for r in results) / len(results),
                "total_wall_time": total_time
            }
            
            if agg["total_chunks"] > 0:
                agg["avg_chunk_size"] = agg["total_chunk_chars"] / agg["total_chunks"]
                agg["avg_chunk_tokens"] = agg["total_chunk_tokens"] / agg["total_chunks"]
            if agg["parent_chunks"] > 0:
                agg["avg_parent_size"] = agg["parent_chunk_chars"] / agg["parent_chunks"]
                agg["avg_parent_tokens"] = agg["parent_chunk_tokens"] / agg["parent_chunks"]
            if agg["child_chunks"] > 0:
                agg["avg_child_size"] = agg["child_chunk_chars"] / agg["child_chunks"]
                agg["avg_child_tokens"] = agg["child_chunk_tokens"] / agg["child_chunks"]
            
            all_results[config["name"]] = {
                "aggregate_stats": agg,
                "total_processing_time": total_time,
                "individual_results": results
            }
            
            logger.info(f"\nResults for {config['name']}:")
            logger.info(f"  Total files: {agg['total_files']:,}")
            logger.info(f"  Total resources: {agg['total_resources']:,}")
            logger.info(f"  Total chunks: {agg['total_chunks']:,}")
            logger.info(f"    - Parent chunks: {agg['parent_chunks']:,} (avg {agg['avg_parents_per_file']:.1f} per file)")
            logger.info(f"    - Child chunks: {agg['child_chunks']:,} (avg {agg['avg_children_per_file']:.1f} per file)")
            logger.info(f"  Avg parent size: {agg['avg_parent_size']:.1f} chars ({agg['avg_parent_tokens']:.1f} tokens)")
            logger.info(f"  Avg child size: {agg['avg_child_size']:.1f} chars ({agg['avg_child_tokens']:.1f} tokens)")
            logger.info(f"  Min chunk size: {agg['min_chunk_size']} chars")
            logger.info(f"  Max chunk size: {agg['max_chunk_size']} chars")
            logger.info(f"  Processing time: {total_time:.2f} seconds")
        else:
            all_results[config["name"]] = {
                "aggregate_stats": {},
                "total_processing_time": total_time,
                "individual_results": []
            }
    
    # Write results
    output_path = Path(__file__).parent / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n{'='*80}")
    logger.info("COMPARISON SUMMARY")
    logger.info("="*80)
    logger.info(f"Files processed: {len(json_files)}")
    
    for config in configs:
        name = config["name"]
        if name in all_results and all_results[name]["aggregate_stats"]:
            agg = all_results[name]["aggregate_stats"]
            logger.info(f"\n{name.upper()} (max={config['max_chunk_size']}, min={config['min_chunk_size']}):")
            logger.info(f"  Total chunks: {agg.get('total_chunks', 0):,}")
            logger.info(f"    - Parent chunks: {agg.get('parent_chunks', 0):,}")
            logger.info(f"    - Child chunks: {agg.get('child_chunks', 0):,}")
            logger.info(f"  Avg child size: {agg.get('avg_child_size', 0):.1f} chars ({agg.get('avg_child_tokens', 0):.1f} tokens)")
            logger.info(f"  Avg children per file: {agg.get('avg_children_per_file', 0):.1f}")
            logger.info(f"  Processing time: {agg.get('total_wall_time', 0):.2f} seconds")
    
    logger.info(f"\nResults written to: {output_path}")
    logger.info("="*80)
    
    return all_results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Compare chunking methods")
    parser.add_argument("--data-dir", type=str, default="../data/fhir", help="Directory containing FHIR JSON files")
    parser.add_argument("--num-files", type=int, default=1000, help="Number of files to process")
    parser.add_argument("--output", type=str, default="chunking_comparison_results.json", help="Output file name")
    parser.add_argument("--test", type=str, choices=["comparison", "recursive_json_sizes", "bundle_parent_json_children"], default="comparison",
                       help="Test to run: 'comparison' for full comparison, 'recursive_json_sizes' for RecursiveJsonSplitter size tests, 'bundle_parent_json_children' for bundle parent with JSON children")
    
    args = parser.parse_args()
    
    if args.test == "recursive_json_sizes":
        # Use 10,000 files or all files, whichever is smaller
        data_path = Path(args.data_dir)
        total_files = len(list(data_path.glob("*.json")))
        num_files = min(10000, total_files)
        logger.info(f"Running RecursiveJsonSplitter size comparison on {num_files} files (out of {total_files} total)")
        run_recursive_json_size_comparison(args.data_dir, num_files, "recursive_json_size_comparison.json")
    elif args.test == "bundle_parent_json_children":
        # Test bundle-as-parent with recursive JSON children
        data_path = Path(args.data_dir)
        total_files = len(list(data_path.glob("*.json")))
        num_files = min(args.num_files, total_files)
        logger.info(f"Running Bundle-Parent with RecursiveJSON children on {num_files} files (out of {total_files} total)")
        run_bundle_parent_json_children_test(args.data_dir, num_files, "bundle_parent_json_children_results.json")
    else:
        run_comparison_test(args.data_dir, args.num_files, args.output)
