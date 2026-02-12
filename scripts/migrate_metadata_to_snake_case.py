#!/usr/bin/env python3
"""
Migrate existing metadata from camelCase to snake_case.

This script updates all existing records in hc_ai_table to use snake_case
metadata keys for consistency with retrieval code.

Before: {"patientId": "...", "resourceId": "...", ...}
After:  {"patient_id": "...", "resource_id": "...", ...}
"""
import asyncio
import asyncpg
import os
from pathlib import Path
import sys
import json

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))
from utils.env_loader import load_env_recursive
load_env_recursive(ROOT_DIR)


async def migrate_metadata():
    """Migrate all metadata keys from camelCase to snake_case."""
    print("\n" + "="*80)
    print("METADATA MIGRATION: camelCase → snake_case")
    print("="*80)
    
    conn = await asyncpg.connect(
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
    )
    
    try:
        # Count total records
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM hc_ai_schema.hc_ai_table"
        )
        print(f"\n📊 Total records to migrate: {total:,}")
        
        # Show sample BEFORE migration
        print("\n🔍 Sample metadata BEFORE migration:")
        sample_before = await conn.fetchrow("""
            SELECT langchain_metadata 
            FROM hc_ai_schema.hc_ai_table 
            LIMIT 1
        """)
        if sample_before and sample_before['langchain_metadata']:
            metadata = json.loads(sample_before['langchain_metadata']) if isinstance(sample_before['langchain_metadata'], str) else sample_before['langchain_metadata']
            print(f"  Keys: {list(metadata.keys())}")
        
        # Perform migration
        print("\n⚙️  Running migration...")
        result = await conn.execute("""
            UPDATE hc_ai_schema.hc_ai_table
            SET langchain_metadata = (
                SELECT jsonb_object_agg(
                    CASE key
                        -- Core identifiers
                        WHEN 'patientId' THEN 'patient_id'
                        WHEN 'resourceId' THEN 'resource_id'
                        WHEN 'resourceType' THEN 'resource_type'
                        WHEN 'fullUrl' THEN 'full_url'
                        WHEN 'sourceFile' THEN 'source_file'
                        
                        -- Chunk identifiers
                        WHEN 'chunkId' THEN 'chunk_id'
                        WHEN 'chunkIndex' THEN 'chunk_index'
                        WHEN 'totalChunks' THEN 'total_chunks'
                        WHEN 'chunkSize' THEN 'chunk_size'
                        
                        -- Additional metadata
                        WHEN 'effectiveDate' THEN 'effective_date'
                        WHEN 'lastUpdated' THEN 'last_updated'
                        
                        -- Keep other keys as-is (e.g., 'status')
                        ELSE key
                    END,
                    value
                )
                FROM jsonb_each(langchain_metadata::jsonb)
            )::json
        """)
        
        print(f"✅ Migration complete: {result}")
        
        # Show sample AFTER migration
        print("\n🔍 Sample metadata AFTER migration:")
        sample_after = await conn.fetchrow("""
            SELECT langchain_metadata 
            FROM hc_ai_schema.hc_ai_table 
            LIMIT 1
        """)
        if sample_after and sample_after['langchain_metadata']:
            metadata = json.loads(sample_after['langchain_metadata']) if isinstance(sample_after['langchain_metadata'], str) else sample_after['langchain_metadata']
            print(f"  Keys: {list(metadata.keys())}")
            print("\n  Full sample:")
            print(json.dumps(metadata, indent=4))
        
        # Verify patient_id exists (critical for retrieval)
        patient_count = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM hc_ai_schema.hc_ai_table
            WHERE (langchain_metadata::jsonb) ? 'patient_id'
        """)
        print(f"\n✓ Records with 'patient_id' key: {patient_count:,}/{total:,}")
        
        if patient_count == total:
            print("\n🎉 SUCCESS: All records migrated successfully!")
        else:
            print(f"\n⚠️  WARNING: {total - patient_count} records missing 'patient_id' key")
        
    except Exception as e:
        print(f"\n❌ ERROR during migration: {e}")
        raise
    finally:
        await conn.close()
    
    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(migrate_metadata())
