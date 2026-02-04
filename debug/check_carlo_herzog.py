#!/usr/bin/env python3
"""Check if Carlo Herzog appears in the database (chunks and raw FHIR)."""
import asyncio
import os
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


def load_env(path: Path) -> None:
    """Load KEY=VALUE from .env without dotenv package."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)=(.*)", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val.startswith('"') and val.endswith('"') or val.startswith("'") and val.endswith("'"):
                val = val[1:-1].replace("\\n", "\n")
            if key not in os.environ:
                os.environ[key] = val


load_env(ROOT_DIR / ".env")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def check():
    user = os.getenv("DB_USER")
    pw = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    db = os.getenv("DB_NAME")
    if not all([user, pw, db]):
        print("Missing DB_USER, DB_PASSWORD, or DB_NAME in .env")
        return
    schema = os.getenv("HC_AI_SCHEMA", "hc_ai_schema")
    raw_table = os.getenv("HC_AI_RAW_TABLE", "fhir_raw_files")
    conn_str = f"postgresql+asyncpg://{user}:{pw}@{host}:{port}/{db}"
    engine = create_async_engine(conn_str)

    async with engine.begin() as conn:
        # 1) Chunks table: content containing "carlo" and "herzog"
        r = await conn.execute(
            text(
                f'''
                SELECT COUNT(*) FROM "{schema}".hc_ai_table
                WHERE content ILIKE :pat
                '''
            ),
            {"pat": "%carlo%herzog%"},
        )
        chunk_count = r.scalar()
        print("1. Chunks table (hc_ai_table) – content containing 'carlo' and 'herzog':")
        print(f"   Count: {chunk_count}")

        if chunk_count > 0:
            r2 = await conn.execute(
                text(
                    f'''
                    SELECT content, langchain_metadata->>'patient_id' as patient_id
                    FROM "{schema}".hc_ai_table
                    WHERE content ILIKE :pat
                    LIMIT 3
                    '''
                ),
                {"pat": "%carlo%herzog%"},
            )
            for i, row in enumerate(r2.fetchall(), 1):
                content_preview = (row[0] or "")[:200]
                pid = row[1] or "N/A"
                print(f"   Sample {i} (patient_id={pid}): {content_preview}...")

        # 2) Raw FHIR table: bundle_json containing the name
        try:
            r3 = await conn.execute(
                text(
                    f'''
                    SELECT patient_id, source_filename
                    FROM "{schema}"."{raw_table}"
                    WHERE bundle_json::text ILIKE :pat
                    LIMIT 10
                    '''
                ),
                {"pat": "%carlo%herzog%"},
            )
            raw_rows = r3.fetchall()
            print("\n2. Raw FHIR table (fhir_raw_files) – bundle_json containing 'carlo' and 'herzog':")
            print(f"   Rows found: {len(raw_rows)}")
            for row in raw_rows:
                print(f"   - patient_id={row[0]}, file={row[1]}")
        except Exception as e:
            print(f"\n2. Raw FHIR table: (table may not exist) {e}")

    await engine.dispose()
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(check())
