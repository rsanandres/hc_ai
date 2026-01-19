# check-db.py
"""
Diagnostic script to check if the PostgreSQL vector store table exists and has data.
"""
import os
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
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
    """Check database for table and data."""
    print("="*80)
    print("DATABASE DIAGNOSTIC CHECK")
    print("="*80)
    
    # Validate environment variables
    if not all([POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB]):
        print("❌ Missing required environment variables:")
        print(f"   DB_USER: {POSTGRES_USER}")
        print(f"   DB_PASSWORD: {'*' * len(POSTGRES_PASSWORD) if POSTGRES_PASSWORD else 'None'}")
        print(f"   DB_NAME: {POSTGRES_DB}")
        return
    
    print(f"Database: {POSTGRES_DB} @ {POSTGRES_HOST}:{POSTGRES_PORT}")
    print(f"Schema: {SCHEMA_NAME}")
    print(f"Table: {TABLE_NAME}")
    print()
    
    connection_string = f"postgresql+asyncpg://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
    
    try:
        engine = create_async_engine(connection_string)
        
        async with engine.begin() as conn:
            # Check if schema exists
            print("1. Checking if schema exists...")
            schema_check = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.schemata 
                        WHERE schema_name = :schema_name
                    )
                """),
                {"schema_name": SCHEMA_NAME}
            )
            schema_exists = schema_check.scalar_one()
            print(f"   Schema '{SCHEMA_NAME}' exists: {schema_exists}")
            
            if not schema_exists:
                print(f"   ❌ Schema '{SCHEMA_NAME}' does not exist!")
                return
            
            # Check if table exists
            print(f"\n2. Checking if table '{TABLE_NAME}' exists...")
            table_check = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = :schema_name
                        AND table_name = :table_name
                    )
                """),
                {"schema_name": SCHEMA_NAME, "table_name": TABLE_NAME}
            )
            table_exists = table_check.scalar_one()
            print(f"   Table '{SCHEMA_NAME}.{TABLE_NAME}' exists: {table_exists}")
            
            if not table_exists:
                print(f"   ❌ Table '{SCHEMA_NAME}.{TABLE_NAME}' does not exist!")
                print(f"   The table should be created automatically when you first store data.")
                return
            
            # Get table structure
            print(f"\n3. Table structure:")
            columns = await conn.execute(
                text("""
                    SELECT 
                        column_name,
                        data_type,
                        character_maximum_length
                    FROM information_schema.columns
                    WHERE table_schema = :schema_name
                    AND table_name = :table_name
                    ORDER BY ordinal_position
                """),
                {"schema_name": SCHEMA_NAME, "table_name": TABLE_NAME}
            )
            for col in columns:
                col_name, data_type, max_len = col
                type_str = f"{data_type}({max_len})" if max_len else data_type
                print(f"   - {col_name}: {type_str}")
            
            # Check row count
            print(f"\n4. Checking data...")
            row_count = await conn.execute(
                text(f'SELECT COUNT(*) FROM "{SCHEMA_NAME}"."{TABLE_NAME}"')
            )
            count = row_count.scalar_one()
            print(f"   Total rows: {count}")
            
            if count == 0:
                print("   ⚠️  Table exists but is empty!")
                print("   This means:")
                print("   - Table was created successfully")
                print("   - But no data has been inserted yet")
                print("   - Check if process_and_store() is being called")
                print("   - Check logs for any errors during storage")
            else:
                print(f"   ✓ Table has {count} rows!")
                
                # Show sample data
                print(f"\n5. Sample data (first 5 rows):")
                samples = await conn.execute(
                    text(f'''
                        SELECT 
                            langchain_id,
                            LEFT(content, 50) as content_preview,
                            langchain_metadata
                        FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
                        LIMIT 5
                    ''')
                )
                for i, (doc_id, content_preview, metadata) in enumerate(samples, 1):
                    print(f"   [{i}] ID: {str(doc_id)[:36]}...")
                    print(f"       Content: {content_preview[:50]}...")
                    if metadata:
                        print(f"       Metadata keys: {list(metadata.keys())[:5]}")
                    print()
        
        await engine.dispose()
        
    except Exception as e:
        print(f"\n❌ Error connecting to database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_database())