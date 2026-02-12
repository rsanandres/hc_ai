#!/usr/bin/env python3
import os
import uuid
import asyncio
from pathlib import Path
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from langchain_postgres import PGVectorStore, PGEngine
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings

## Test with Cohere Embeddings (NVM)
# from langchain_cohere import CohereEmbeddings

# Load environment variables from repo root .env
ROOT_DIR = Path(__file__).resolve().parents[1]  # Go up 1 level from scripts/ to project root
import sys
sys.path.insert(0, str(ROOT_DIR))
from utils.env_loader import load_env_recursive
load_env_recursive(ROOT_DIR)

POSTGRES_USER = os.environ.get("DB_USER")  # @param {type: "string"}
POSTGRES_PASSWORD = os.environ.get("DB_PASSWORD")   # @param {type: "string"}
# For local Docker containers, use "localhost" (not the container name)
# Container name "postgres-db" only works from within Docker network
POSTGRES_HOST = os.environ.get("DB_HOST", "localhost")  # Default to localhost for local containers
POSTGRES_PORT = os.environ.get("DB_PORT", "5432")   # Default to standard PostgreSQL port
POSTGRES_DB = os.environ.get("DB_NAME")   # @param {type: "string"}

# Validate required environment variables
required_vars = {
    "DB_USER": POSTGRES_USER,
    "DB_PASSWORD": POSTGRES_PASSWORD,
    "DB_NAME": POSTGRES_DB,
}
# missing_vars = [var for var, value in required_vars.items() if not value]
# if missing_vars:
#     raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

TABLE_NAME = "vectorstore"  # @param {type: "string"}
VECTOR_SIZE = 1024  # @param {type: "int"}
SCHEMA_NAME = "test_schema"


def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_status(message: str, status: str = "✓"):
    """Print a status message with icon"""
    print(f"  {status} {message}")


async def verify_table_exists(engine, schema_name: str, table_name: str) -> bool:
    """Check if table exists in the database"""
    async with engine.begin() as conn:
        res = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE  table_schema = :schema_name
                    AND    table_name   = :table_name
                )
            """),
            {"schema_name": schema_name, "table_name": table_name}
        )
        return res.scalar_one()


async def get_table_info(engine, schema_name: str, table_name: str):
    """Get table structure information"""
    async with engine.begin() as conn:
        res = await conn.execute(
            text("""
                SELECT 
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable
                FROM information_schema.columns
                WHERE table_schema = :schema_name
                AND table_name = :table_name
                ORDER BY ordinal_position
            """),
            {"schema_name": schema_name, "table_name": table_name}
        )
        return res.fetchall()


async def get_row_count(engine, schema_name: str, table_name: str) -> int:
    """Get the number of rows in the table"""
    async with engine.begin() as conn:
        res = await conn.execute(
            text(f'SELECT COUNT(*) FROM "{schema_name}"."{table_name}"')
        )
        return res.scalar_one()


async def get_sample_documents(engine, schema_name: str, table_name: str, limit: int = 5):
    """Get sample documents from the table"""
    async with engine.begin() as conn:
        res = await conn.execute(
            text(f'''
                SELECT 
                    langchain_id,
                    LEFT(content, 50) as content_preview,
                    langchain_metadata
                FROM "{schema_name}"."{table_name}"
                LIMIT :limit
            '''),
            {"limit": limit}
        )
        return res.fetchall()


async def main():
    print_section("PostgreSQL Vector Store Test")
    print(f"  Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Database: {POSTGRES_DB} @ {POSTGRES_HOST}:{POSTGRES_PORT}")
    print(f"  Schema: {SCHEMA_NAME}")
    print(f"  Table: {TABLE_NAME}")
    
    ## Create the Table
    CONNECTION_STRING = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    engine = create_async_engine(
        CONNECTION_STRING,
    )
    
    ## Create the schema if it doesn't exist
    print_section("1. Schema Creation")
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA_NAME}"'))
    print_status(f"Schema '{SCHEMA_NAME}' created/verified")
    
    pg_engine = PGEngine.from_engine(engine=engine)

    # Check if the table already exists before trying to create it
    print_section("2. Table Creation")
    already_exists = await verify_table_exists(engine, SCHEMA_NAME, TABLE_NAME)
    
    if not already_exists:
        await pg_engine.ainit_vectorstore_table(
            table_name=TABLE_NAME,
            vector_size=VECTOR_SIZE,
            schema_name=SCHEMA_NAME,    # Default: "public"
        )
        print_status(f"Table '{SCHEMA_NAME}.{TABLE_NAME}' created successfully")
    else:
        print_status(f"Table '{SCHEMA_NAME}.{TABLE_NAME}' already exists, skipping creation.", "ℹ")
    
    # Verify table exists and show structure
    table_exists = await verify_table_exists(engine, SCHEMA_NAME, TABLE_NAME)
    if table_exists:
        print_status("Table verification: EXISTS", "✓")
        table_info = await get_table_info(engine, SCHEMA_NAME, TABLE_NAME)
        print("\n  Table Structure:")
        print("  " + "-" * 66)
        print(f"  {'Column':<25} {'Type':<25} {'Nullable':<10}")
        print("  " + "-" * 66)
        for col in table_info:
            col_name, data_type, max_len, nullable = col
            type_str = f"{data_type}({max_len})" if max_len else data_type
            print(f"  {col_name:<25} {type_str:<25} {nullable:<10}")
    else:
        print_status("Table verification: NOT FOUND", "✗")
        raise Exception("Table was not created successfully!")

    ## Embeddings
    # Example: Use Cohere embeddings or Ollama mxbai-embed-large:latest (local)
    # Uncomment what you wish to use:

    # Option 1: Cohere
    # embedding = CohereEmbeddings(model="embed-english-v3.0", cohere_api_key=os.environ["COHERE_API_KEY"])

    # Option 2: Ollama local embedding (mxbai-embed-large:latest)
    embedding = OllamaEmbeddings(
        model="mxbai-embed-large:latest",  # for local Ollama
        base_url="http://localhost:11434" # default for Ollama
    )

    ## Vector Store
    store = await PGVectorStore.create(
        engine=pg_engine,
        table_name=TABLE_NAME,
        schema_name=SCHEMA_NAME,
        embedding_service=embedding,
    )

    ## Add Documents
    docs = [
        Document(
            id=str(uuid.uuid4()),
            page_content="Red Apple",
            metadata={"description": "red", "content": "1", "category": "fruit"},
        ),
        Document(
            id=str(uuid.uuid4()),
            page_content="Banana Cavendish",
            metadata={"description": "yellow", "content": "2", "category": "fruit"},
        ),
        Document(
            id=str(uuid.uuid4()),
            page_content="Orange Navel",
            metadata={"description": "orange", "content": "3", "category": "fruit"},
        ),
    ]

    print_section("3. Adding Documents")
    await store.aadd_documents(docs)
    print_status(f"Added {len(docs)} documents")
    
    # Verify documents were added
    row_count = await get_row_count(engine, SCHEMA_NAME, TABLE_NAME)
    print_status(f"Total rows in table: {row_count}", "✓")

    ## Add Texts
    print_section("4. Adding Texts")
    all_texts = ["Apples and oranges", "Cars and airplanes", "Pineapple", "Train", "Banana"]
    metadatas = [{"len": len(t)} for t in all_texts]
    ids = [str(uuid.uuid4()) for _ in all_texts]
    await store.aadd_texts(all_texts, metadatas=metadatas, ids=ids)
    print_status(f"Added {len(all_texts)} text entries")
    
    # Verify all data was added
    final_row_count = await get_row_count(engine, SCHEMA_NAME, TABLE_NAME)
    expected_count = len(docs) + len(all_texts)
    print_status(f"Total rows in table: {final_row_count} (expected: {expected_count})", "✓")
    
    if final_row_count == expected_count:
        print_status("Row count matches expected value!", "✓")
    else:
        print_status(f"Warning: Row count mismatch! Expected {expected_count}, got {final_row_count}", "⚠")
    
    # Show sample documents
    print_section("5. Sample Data Preview")
    samples = await get_sample_documents(engine, SCHEMA_NAME, TABLE_NAME, limit=5)
    if samples:
        print(f"  Showing {len(samples)} sample rows:\n")
        for i, (doc_id, content_preview, metadata) in enumerate(samples, 1):
            # Safely handle doc_id (could be UUID object or None)
            doc_id_str = str(doc_id) if doc_id else "N/A"
            doc_id_display = doc_id_str[:36] + "..." if len(doc_id_str) > 36 else doc_id_str
            
            # Safely handle content_preview (could be None)
            content_display = str(content_preview) if content_preview else "N/A"
            if len(content_display) > 50:
                content_display = content_display[:50] + "..."
            
            print(f"  [{i}] ID: {doc_id_display}")
            print(f"      Content: {content_display}")
            if metadata:
                print(f"      Metadata: {metadata}")
            print()
    else:
        print_status("No documents found in table", "⚠")

    ## Drop the Table
    print_section("6. Dropping Table")
    await pg_engine.adrop_table(TABLE_NAME, schema_name=SCHEMA_NAME)
    print_status(f"Table '{SCHEMA_NAME}.{TABLE_NAME}' dropped")

    # Drop all other non-extension objects in the database, confirm truly empty.
    print_section("7. Dropping ALL Tables, Views, and Sequences from Schema")
    async with engine.begin() as conn:
        # Drop all user tables, views, and sequences from the target schema
        # Use format() with %I for safe identifier quoting in PL/pgSQL
        result = await conn.execute(
            text(f"""
            DO $$
            DECLARE
                r RECORD;
                schema_name TEXT := '{SCHEMA_NAME.replace("'", "''")}';
            BEGIN
                -- Drop TABLES
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = schema_name) LOOP
                    EXECUTE format('DROP TABLE IF EXISTS %I.%I CASCADE', schema_name, r.tablename);
                END LOOP;
                -- Drop VIEWS
                FOR r IN (SELECT viewname FROM pg_views WHERE schemaname = schema_name) LOOP
                    EXECUTE format('DROP VIEW IF EXISTS %I.%I CASCADE', schema_name, r.viewname);
                END LOOP;
                -- Drop SEQUENCES
                FOR r IN (SELECT sequencename FROM pg_sequences WHERE schemaname = schema_name) LOOP
                    EXECUTE format('DROP SEQUENCE IF EXISTS %I.%I CASCADE', schema_name, r.sequencename);
                END LOOP;
            END$$;
            """)
        )

    print_status("Dropped all tables, views, and sequences (except extensions) in schema", "✓")

    # Show that database is empty except for extensions
    print_section("8. Current non-extension Objects in Schema")
    async with engine.connect() as conn:
        rows = []
        result = await conn.execute(
            text("""
            SELECT 'table' AS type, tablename AS name FROM pg_tables WHERE schemaname = :schema_name
            UNION ALL
            SELECT 'view', viewname FROM pg_views WHERE schemaname = :schema_name
            UNION ALL
            SELECT 'sequence', sequencename FROM pg_sequences WHERE schemaname = :schema_name
            ORDER BY type, name;
            """),
            {"schema_name": SCHEMA_NAME}
        )
        rows = result.fetchall()

        if not rows:
            print_status("Database is clean: No tables/views/sequences remain! (Extensions not shown)", "✓")
        else:
            print(f"  Found objects still present in schema '{SCHEMA_NAME}':")
            for row in rows:
                print(f"    - {row.type}: {row.name}")

    
    print_section("Test Complete")
    print(f"  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n")


if __name__ == "__main__":
    asyncio.run(main())
