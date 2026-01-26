#!/usr/bin/env python3
"""
Quick script to check if embeddings are actually in the database.
"""
import os
import sys
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]  # Go up 1 level from scripts/ to project root
sys.path.insert(0, str(ROOT_DIR))
from utils.env_loader import load_env_recursive
load_env_recursive(ROOT_DIR)

POSTGRES_USER = os.environ.get("DB_USER")
POSTGRES_PASSWORD = os.environ.get("DB_PASSWORD")
POSTGRES_HOST = os.environ.get("DB_HOST", "localhost")
POSTGRES_PORT = os.environ.get("DB_PORT", "5432")
POSTGRES_DB = os.environ.get("DB_NAME")
SCHEMA_NAME = "hc_ai_schema"
TABLE_NAME = "hc_ai_table"

async def check_database():
    connection_string = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    engine = create_async_engine(connection_string, echo=False)
    
    try:
        async with engine.begin() as conn:
            # Check row count
            result = await conn.execute(
                text(f'SELECT COUNT(*) FROM "{SCHEMA_NAME}"."{TABLE_NAME}"')
            )
            count = result.scalar_one()
            print(f"Total rows in {SCHEMA_NAME}.{TABLE_NAME}: {count}")
            
            # Check if embeddings (vectors) are present
            result = await conn.execute(
                text(f'''
                    SELECT 
                        COUNT(*) as total,
                        COUNT(embedding) as with_embeddings,
                        COUNT(*) - COUNT(embedding) as without_embeddings
                    FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
                ''')
            )
            row = result.fetchone()
            if row:
                total, with_emb, without_emb = row
                print(f"  - Total rows: {total}")
                print(f"  - Rows with embeddings: {with_emb}")
                print(f"  - Rows without embeddings: {without_emb}")
            
            # Sample a few rows to see what's there
            if count > 0:
                result = await conn.execute(
                    text(f'''
                        SELECT 
                            id,
                            LENGTH(page_content) as content_length,
                            embedding IS NOT NULL as has_embedding,
                            metadata
                        FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
                        LIMIT 5
                    ''')
                )
                print("\nSample rows:")
                print("-" * 80)
                for row in result:
                    row_id, content_len, has_emb, metadata = row
                    print(f"ID: {row_id[:50]}...")
                    print(f"  Content length: {content_len} chars")
                    print(f"  Has embedding: {has_emb}")
                    print(f"  Metadata keys: {list(metadata.keys()) if metadata else 'None'}")
                    print()
    except Exception as e:
        print(f"Error checking database: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check_database())
