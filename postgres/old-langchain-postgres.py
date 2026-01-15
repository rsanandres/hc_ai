import os
import sys
import uuid
import asyncio
from datetime import datetime
from typing import List

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from langchain_postgres import PGVectorStore, PGEngine
from langchain_core.documents import Document

# Add parent directory to path to import from POC_embeddings/helper.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from POC_embeddings.helper import get_chunk_embedding


# Search for .env file
load_dotenv()

POSTGRES_USER = os.environ.get("DB_USER")  # @param {type: "string"}
POSTGRES_PASSWORD = os.environ.get("DB_PASSWORD")   # @param {type: "string"}
POSTGRES_HOST = os.environ.get("DB_HOST", "localhost")  # Default to localhost for local containers
POSTGRES_PORT = os.environ.get("DB_PORT", "5432")   # Default to standard PostgreSQL port
POSTGRES_DB = os.environ.get("DB_NAME")   # @param {type: "string"}

# Validate required environment variables
required_vars = {
    "DB_USER": POSTGRES_USER,
    "DB_PASSWORD": POSTGRES_PASSWORD,
    "DB_NAME": POSTGRES_DB,
}

TABLE_NAME = "hc_ai_table"  # @param {type: "string"}
# We are using mxbai-embed-large:latest for embeddings
VECTOR_SIZE = 512  # @param {type: "int"}
SCHEMA_NAME = "hc_ai_schema"

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


async def get_table_info(engine: AsyncEngine, schema_name: str, table_name: str):
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


async def initialize_vector_store() -> PGVectorStore:
    """
    Initialize and return the PostgreSQL vector store.
    Creates schema and table if they don't exist.
    Uses connection pooling for efficiency.
    """
    global _engine, _pg_engine, _vector_store
    
    # Reuse existing connection if available
    if _vector_store is not None:
        return _vector_store
    
    # Validate required environment variables
    required_vars = {
        "DB_USER": POSTGRES_USER,
        "DB_PASSWORD": POSTGRES_PASSWORD,
        "DB_NAME": POSTGRES_DB,
    }
    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Create engine if not exists
    if _engine is None:
        connection_string = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
        _engine = create_async_engine(connection_string)
        _pg_engine = PGEngine.from_engine(engine=_engine)
    
    # Create schema if it doesn't exist
    async with _engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA_NAME}"'))
    
    # Create table if it doesn't exist
    already_exists = await verify_table_exists(_engine, SCHEMA_NAME, TABLE_NAME)
    if not already_exists:
        await _pg_engine.ainit_vectorstore_table(
            table_name=TABLE_NAME,
            vector_size=VECTOR_SIZE,
            schema_name=SCHEMA_NAME, 
        )
    
    # Verify table exists
    table_exists = await verify_table_exists(_engine, SCHEMA_NAME, TABLE_NAME)
    if not table_exists:
        raise Exception("Table was not created successfully!")
    
    # Create embeddings instance
    embedding = CustomEmbeddings()

    
    
