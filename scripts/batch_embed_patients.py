#!/usr/bin/env python
"""
Batch Embedding Script for FHIR Patient Data

This script embeds all patients that don't already have embeddings in the database.
It includes:
- Duplicate detection and cleanup
- Progress tracking with estimates
- Resume capability (skips already-embedded patients)
- Batch processing for efficiency
- Error handling and logging

Usage:
    python scripts/batch_embed_patients.py [options]

Options:
    --dry-run           Show what would be done without making changes
    --check-duplicates  Only check for duplicates, don't embed
    --clean-duplicates  Remove duplicate embeddings before processing
    --limit N           Only process first N patients
    --batch-size N      Number of patients per batch (default: 10)
    --ollama-url URL    Override OLLAMA_BASE_URL

Environment Variables:
    OLLAMA_BASE_URL     Ollama endpoint (default: http://localhost:11434)
    DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME - Database connection
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Set, Optional, Tuple
import logging

# Setup path
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from utils.env_loader import load_env_recursive
load_env_recursive(ROOT_DIR)

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
SCHEMA_NAME = os.getenv("HC_AI_SCHEMA", "hc_ai_schema")

# Global engine
_engine: Optional[AsyncEngine] = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        conn_str = f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        _engine = create_async_engine(conn_str, echo=False)
    return _engine


# ═══════════════════════════════════════════════════════════════════════════════
# DUPLICATE DETECTION & CLEANUP
# ═══════════════════════════════════════════════════════════════════════════════

async def check_duplicates() -> Dict[str, Any]:
    """Check for duplicate chunks in the database."""
    engine = get_engine()
    async with engine.begin() as conn:
        # Check for duplicate chunk_ids
        result = await conn.execute(text(f'''
            SELECT langchain_metadata->>'chunk_id' as chunk_id, COUNT(*) as cnt
            FROM "{SCHEMA_NAME}".hc_ai_table
            WHERE langchain_metadata->>'chunk_id' IS NOT NULL
            GROUP BY langchain_metadata->>'chunk_id'
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
        '''))
        duplicates = result.fetchall()
        
        # Get total count
        result = await conn.execute(text(f'SELECT COUNT(*) FROM "{SCHEMA_NAME}".hc_ai_table'))
        total_embeddings = result.scalar()
        
        return {
            "total_embeddings": total_embeddings,
            "duplicate_groups": len(duplicates),
            "duplicate_details": [(d[0], d[1]) for d in duplicates[:20]]  # Top 20
        }


async def clean_duplicates(dry_run: bool = True) -> int:
    """Remove duplicate chunks, keeping only the first occurrence."""
    engine = get_engine()
    
    if dry_run:
        # Just count what would be deleted
        async with engine.begin() as conn:
            result = await conn.execute(text(f'''
                WITH duplicates AS (
                    SELECT langchain_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY langchain_metadata->>'chunk_id' 
                               ORDER BY langchain_id
                           ) as rn
                    FROM "{SCHEMA_NAME}".hc_ai_table
                    WHERE langchain_metadata->>'chunk_id' IS NOT NULL
                )
                SELECT COUNT(*) FROM duplicates WHERE rn > 1
            '''))
            return result.scalar() or 0
    
    # Actually delete duplicates
    async with engine.begin() as conn:
        result = await conn.execute(text(f'''
            DELETE FROM "{SCHEMA_NAME}".hc_ai_table
            WHERE langchain_id IN (
                SELECT langchain_id FROM (
                    SELECT langchain_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY langchain_metadata->>'chunk_id' 
                               ORDER BY langchain_id
                           ) as rn
                    FROM "{SCHEMA_NAME}".hc_ai_table
                    WHERE langchain_metadata->>'chunk_id' IS NOT NULL
                ) t
                WHERE rn > 1
            )
        '''))
        return result.rowcount


# ═══════════════════════════════════════════════════════════════════════════════
# PATIENT DISCOVERY
# ═══════════════════════════════════════════════════════════════════════════════

async def get_embedded_patients() -> Set[str]:
    """Get set of patient IDs that already have embeddings."""
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text(f'''
            SELECT DISTINCT langchain_metadata->>'patient_id' 
            FROM "{SCHEMA_NAME}".hc_ai_table
            WHERE langchain_metadata->>'patient_id' IS NOT NULL
        '''))
        return {row[0] for row in result.fetchall()}


async def get_all_fhir_patients() -> List[str]:
    """Get all patient IDs from FHIR raw files."""
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text(f'''
            SELECT DISTINCT patient_id 
            FROM "{SCHEMA_NAME}".fhir_raw_files
            ORDER BY patient_id
        '''))
        return [row[0] for row in result.fetchall()]


async def get_patients_needing_embedding() -> List[str]:
    """Get patient IDs that need embedding (not yet embedded)."""
    embedded = await get_embedded_patients()
    all_patients = await get_all_fhir_patients()
    return [p for p in all_patients if p not in embedded]


async def get_patient_fhir_data(patient_id: str) -> List[Dict[str, Any]]:
    """Get FHIR bundle data for a patient."""
    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(text(f'''
            SELECT source_filename, bundle_json
            FROM "{SCHEMA_NAME}".fhir_raw_files
            WHERE patient_id = :patient_id
            ORDER BY version DESC
            LIMIT 1
        '''), {"patient_id": patient_id})
        rows = result.fetchall()
        return [{"filename": r[0], "bundle": r[1]} for r in rows]


# ═══════════════════════════════════════════════════════════════════════════════
# EMBEDDING PROCESSING
# ═══════════════════════════════════════════════════════════════════════════════

async def embed_patient(patient_id: str, api_url: str, dry_run: bool = False) -> Tuple[bool, int, str]:
    """
    Embed a single patient's FHIR data.
    
    Returns: (success, chunks_count, error_message)
    """
    import aiohttp
    
    try:
        # Get patient's FHIR data
        fhir_data = await get_patient_fhir_data(patient_id)
        if not fhir_data:
            return False, 0, "No FHIR data found"
        
        chunks_embedded = 0
        
        for data in fhir_data:
            bundle = data["bundle"]
            filename = data["filename"]
            
            if not isinstance(bundle, dict):
                continue
                
            entries = bundle.get("entry", [])
            
            for entry in entries:
                resource = entry.get("resource", {})
                resource_type = resource.get("resourceType", "")
                resource_id = resource.get("id", entry.get("fullUrl", ""))
                
                if not resource_type:
                    continue
                
                # Build content for embedding
                content = extract_content(resource, resource_type)
                if not content or len(content.strip()) == 0:
                    continue
                
                if dry_run:
                    chunks_embedded += 1
                    continue
                
                # Send to embedding API
                payload = {
                    "id": resource_id,
                    "fullUrl": entry.get("fullUrl", ""),
                    "resourceType": resource_type,
                    "content": content,
                    "patientId": patient_id,
                    "resourceJson": json.dumps(resource),
                    "sourceFile": filename
                }
                
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{api_url}/embeddings/ingest",
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=60)
                        ) as resp:
                            if resp.status == 200:
                                chunks_embedded += 1
                            else:
                                error_text = await resp.text()
                                logger.warning(f"  Failed to embed {resource_id}: {resp.status} - {error_text[:100]}")
                except Exception as e:
                    logger.warning(f"  API error for {resource_id}: {e}")
        
        return True, chunks_embedded, ""
        
    except Exception as e:
        return False, 0, str(e)


def extract_content(resource: Dict[str, Any], resource_type: str) -> str:
    """Extract meaningful content from a FHIR resource for embedding."""
    parts = []
    
    # Try text.div first
    if "text" in resource and isinstance(resource["text"], dict):
        div = resource["text"].get("div", "")
        if div:
            # Clean HTML
            div = div.replace("<div>", "").replace("</div>", "")
            div = div.replace("<", "").replace(">", " ")
            if div.strip():
                return div.strip()
    
    # Resource-specific extraction
    if resource_type == "Patient":
        parts.append("Patient Information:")
        if "name" in resource and resource["name"]:
            name = resource["name"][0]
            if "family" in name:
                parts.append(f"Name: {name.get('family', '')}")
            if "given" in name and name["given"]:
                parts.append(name["given"][0])
        if "gender" in resource:
            parts.append(f"Gender: {resource['gender']}")
        if "birthDate" in resource:
            parts.append(f"Date of Birth: {resource['birthDate']}")
    
    elif resource_type == "Condition":
        parts.append("Medical Condition:")
        if "code" in resource:
            code = resource["code"]
            if "text" in code:
                parts.append(code["text"])
            elif "coding" in code and code["coding"]:
                parts.append(code["coding"][0].get("display", ""))
        if "clinicalStatus" in resource:
            parts.append(f"Status: {resource['clinicalStatus']}")
    
    elif resource_type == "Observation":
        parts.append("Clinical Observation:")
        if "code" in resource:
            code = resource["code"]
            if "text" in code:
                parts.append(code["text"])
            elif "coding" in code and code["coding"]:
                parts.append(code["coding"][0].get("display", ""))
        if "valueQuantity" in resource:
            vq = resource["valueQuantity"]
            parts.append(f"Value: {vq.get('value', '')} {vq.get('unit', '')}")
    
    elif resource_type == "Encounter":
        parts.append("Healthcare Encounter:")
        if "type" in resource and resource["type"]:
            enc_type = resource["type"][0]
            if "text" in enc_type:
                parts.append(enc_type["text"])
            elif "coding" in enc_type and enc_type["coding"]:
                parts.append(enc_type["coding"][0].get("display", ""))
    
    elif resource_type == "MedicationRequest":
        parts.append("Medication Prescription:")
        if "medicationCodeableConcept" in resource:
            med = resource["medicationCodeableConcept"]
            if "text" in med:
                parts.append(med["text"])
            elif "coding" in med and med["coding"]:
                parts.append(med["coding"][0].get("display", ""))
        if "status" in resource:
            parts.append(f"Status: {resource['status']}")
    
    elif resource_type == "Procedure":
        parts.append("Medical Procedure:")
        if "code" in resource:
            code = resource["code"]
            if "text" in code:
                parts.append(code["text"])
            elif "coding" in code and code["coding"]:
                parts.append(code["coding"][0].get("display", ""))
    
    elif resource_type == "Immunization":
        parts.append("Immunization:")
        if "vaccineCode" in resource:
            vax = resource["vaccineCode"]
            if "text" in vax:
                parts.append(vax["text"])
            elif "coding" in vax and vax["coding"]:
                parts.append(vax["coding"][0].get("display", ""))
    
    else:
        # Generic extraction
        if "code" in resource:
            code = resource["code"]
            if isinstance(code, dict):
                if "text" in code:
                    parts.append(code["text"])
                elif "coding" in code and code["coding"]:
                    parts.append(code["coding"][0].get("display", ""))
    
    return " ".join(parts) if parts else ""


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BATCH PROCESSING
# ═══════════════════════════════════════════════════════════════════════════════

async def run_batch_embedding(
    api_url: str,
    batch_size: int = 10,
    limit: Optional[int] = None,
    dry_run: bool = False
) -> Dict[str, Any]:
    """Run batch embedding for all patients needing it."""
    
    start_time = time.time()
    
    # Get patients needing embedding
    logger.info("Discovering patients needing embedding...")
    patients = await get_patients_needing_embedding()
    
    if limit:
        patients = patients[:limit]
    
    total_patients = len(patients)
    logger.info(f"Found {total_patients} patients to embed")
    
    if total_patients == 0:
        return {"status": "complete", "message": "All patients already embedded"}
    
    # Stats
    stats = {
        "total_patients": total_patients,
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "total_chunks": 0,
        "errors": []
    }
    
    # Process in batches
    for i in range(0, len(patients), batch_size):
        batch = patients[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(patients) + batch_size - 1) // batch_size
        
        # Progress info
        elapsed = time.time() - start_time
        if stats["processed"] > 0:
            rate = stats["processed"] / elapsed
            remaining = (total_patients - stats["processed"]) / rate
            eta = timedelta(seconds=int(remaining))
        else:
            eta = "calculating..."
        
        logger.info(f"\n{'═'*60}")
        logger.info(f"BATCH {batch_num}/{total_batches} | Progress: {stats['processed']}/{total_patients} | ETA: {eta}")
        logger.info(f"{'═'*60}")
        
        # Process batch
        for patient_id in batch:
            stats["processed"] += 1
            
            if dry_run:
                logger.info(f"  [DRY-RUN] Would embed patient: {patient_id[:8]}...")
                stats["successful"] += 1
                continue
            
            success, chunks, error = await embed_patient(patient_id, api_url, dry_run)
            
            if success:
                stats["successful"] += 1
                stats["total_chunks"] += chunks
                logger.info(f"  ✓ {patient_id[:8]}...: {chunks} chunks")
            else:
                stats["failed"] += 1
                stats["errors"].append({"patient_id": patient_id, "error": error})
                logger.error(f"  ✗ {patient_id[:8]}...: {error}")
        
        # Small delay between batches to avoid overwhelming the API
        if not dry_run and i + batch_size < len(patients):
            await asyncio.sleep(0.5)
    
    # Final stats
    total_time = time.time() - start_time
    stats["total_time_seconds"] = total_time
    stats["rate_patients_per_second"] = stats["processed"] / total_time if total_time > 0 else 0
    
    return stats


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Batch embed FHIR patient data into vector database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--check-duplicates", 
        action="store_true",
        help="Only check for duplicates, don't embed"
    )
    parser.add_argument(
        "--clean-duplicates", 
        action="store_true",
        help="Remove duplicate embeddings before processing"
    )
    parser.add_argument(
        "--limit", 
        type=int, 
        default=None,
        help="Only process first N patients"
    )
    parser.add_argument(
        "--batch-size", 
        type=int, 
        default=10,
        help="Number of patients per batch (default: 10)"
    )
    parser.add_argument(
        "--api-url", 
        default="http://localhost:8000",
        help="API endpoint URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--ollama-url",
        default=None,
        help="Override OLLAMA_BASE_URL environment variable"
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    
    # Override Ollama URL if specified
    if args.ollama_url:
        os.environ["OLLAMA_BASE_URL"] = args.ollama_url
        logger.info(f"Using Ollama URL: {args.ollama_url}")
    
    print("\n" + "═" * 70)
    print("  FHIR Patient Batch Embedding Script")
    print("═" * 70)
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Database: {DB_NAME}@{DB_HOST}:{DB_PORT}")
    print(f"  API URL: {args.api_url}")
    print(f"  Ollama URL: {os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}")
    print("═" * 70 + "\n")
    
    # Check duplicates
    if args.check_duplicates or args.clean_duplicates:
        logger.info("Checking for duplicates...")
        dup_info = await check_duplicates()
        
        print(f"\nDuplicate Check Results:")
        print(f"  Total embeddings: {dup_info['total_embeddings']}")
        print(f"  Duplicate chunk_id groups: {dup_info['duplicate_groups']}")
        
        if dup_info['duplicate_details']:
            print(f"\n  Top duplicates:")
            for chunk_id, count in dup_info['duplicate_details'][:10]:
                print(f"    {chunk_id[:50]}...: {count} copies")
        
        if args.clean_duplicates and dup_info['duplicate_groups'] > 0:
            # First show what would be deleted
            would_delete = await clean_duplicates(dry_run=True)
            print(f"\n  Would delete {would_delete} duplicate rows")
            
            if not args.dry_run:
                confirm = input("\n  Proceed with deletion? (yes/no): ")
                if confirm.lower() == "yes":
                    deleted = await clean_duplicates(dry_run=False)
                    print(f"  ✓ Deleted {deleted} duplicate rows")
                else:
                    print("  Skipped deletion")
        
        if args.check_duplicates:
            return
    
    # Run batch embedding
    stats = await run_batch_embedding(
        api_url=args.api_url,
        batch_size=args.batch_size,
        limit=args.limit,
        dry_run=args.dry_run
    )
    
    # Print summary
    print("\n" + "═" * 70)
    print("  EMBEDDING COMPLETE")
    print("═" * 70)
    print(f"  Total patients processed: {stats.get('processed', 0)}")
    print(f"  Successful: {stats.get('successful', 0)}")
    print(f"  Failed: {stats.get('failed', 0)}")
    print(f"  Total chunks embedded: {stats.get('total_chunks', 0)}")
    print(f"  Total time: {stats.get('total_time_seconds', 0):.1f}s")
    print(f"  Rate: {stats.get('rate_patients_per_second', 0):.2f} patients/sec")
    
    if stats.get('errors'):
        print(f"\n  Errors ({len(stats['errors'])} total):")
        for err in stats['errors'][:5]:
            print(f"    - {err['patient_id'][:20]}...: {err['error'][:50]}")
    
    print("═" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
