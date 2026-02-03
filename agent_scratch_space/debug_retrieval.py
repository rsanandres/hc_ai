import asyncio
import os
import sys
import json
from dotenv import load_dotenv
from sqlalchemy import text

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

from api.database.postgres import hybrid_search, initialize_vector_store, _engine
from api.database.bm25_search import bm25_search, SCHEMA_NAME, TABLE_NAME

TEST_CASES = [
    {
        "name": "Soybean IgE Ab (Observation)",
        "patient_id": "169e6f60-d231-4093-93bf-5ae317c9ca7c",
        "query": "What was this patient's Soybean IgE Ab in Serum on 2012-05-11?",
        "keywords": ["Soybean", "IgE", "Serum"]
    },
    {
        "name": "Glucose (Observation)",
        "patient_id": "e149aa89-cc9e-483e-b78b-00f0433072e0",
        "query": "What was this patient's Glucose on 2016-02-22?",
        "keywords": ["Glucose"]
    }
]

async def inspect_ts_content(conn, patient_id):
    print(f"\n--- Inspecting ts_content for Patient {patient_id} ---")
    
    # Check if we have any rows for this patient
    count_sql = f"""
        SELECT COUNT(*) 
        FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
        WHERE langchain_metadata->>'patient_id' = :patient_id
    """
    count = await conn.execute(text(count_sql), {"patient_id": patient_id})
    total_chunks = count.scalar()
    print(f"Total chunks for patient: {total_chunks}")
    
    if total_chunks == 0:
        print("❌ NO DATA FOUND FOR PATIENT!")
        return

    # Check how many have populated ts_content
    ts_count_sql = f"""
        SELECT COUNT(*) 
        FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
        WHERE langchain_metadata->>'patient_id' = :patient_id
        AND ts_content IS NOT NULL
    """
    ts_count = await conn.execute(text(ts_count_sql), {"patient_id": patient_id})
    ts_populated = ts_count.scalar()
    print(f"Chunks with populated ts_content: {ts_populated} / {total_chunks}")
    
    # Sample verification of ts_content
    sample_sql = f"""
        SELECT content, ts_content 
        FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
        WHERE langchain_metadata->>'patient_id' = :patient_id
        LIMIT 1
    """
    result = await conn.execute(text(sample_sql), {"patient_id": patient_id})
    row = result.fetchone()
    if row:
        print(f"Sample content: {row[0][:100]}...")
        print(f"Sample ts_content vector: {str(row[1])[:100]}...")

async def test_searches():
    print("Initializing Vector Store...")
    await initialize_vector_store()
    
    # Get engine from module (it's initialized global)
    from api.database.postgres import _engine as engine
    
    async with engine.connect() as conn:
        for case in TEST_CASES:
            print(f"\n\n{'='*60}")
            print(f"TESTING CASE: {case['name']}")
            print(f"Query: {case['query']}")
            print(f"{'='*60}")
            
            # 1. Inspect Indexing
            await inspect_ts_content(conn, case['patient_id'])
            
            # 2. Run Direct SQL Keyword Check
            print(f"\n--- SQL Keyword Check ---")
            for kw in case['keywords']:
                kw_sql = f"""
                    SELECT COUNT(*) 
                    FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
                    WHERE langchain_metadata->>'patient_id' = :patient_id
                    AND (
                        content ILIKE :ilike_kw 
                        OR ts_content @@ plainto_tsquery('english', :ts_kw)
                    )
                """
                res = await conn.execute(text(kw_sql), {
                    "patient_id": case["patient_id"], 
                    "ilike_kw": f"%{kw}%",
                    "ts_kw": kw
                })
                count = res.scalar()
                print(f"Chunks containing '{kw}': {count}")

            # 3. Run BM25 Only
            print(f"\n--- BM25 Search Results (Top 5) ---")
            bm25_docs = await bm25_search(
                query=case['query'], 
                k=5, 
                filter_metadata={"patient_id": case["patient_id"]}
            )
            for i, doc in enumerate(bm25_docs):
                score = doc.metadata.get('_bm25_score', 'N/A')
                print(f"[{i+1}] Score: {score} | Content: {doc.page_content[:100]}...")
                
            if not bm25_docs:
                print("❌ NO RESULTS FOUND (BM25)")

            # 4. Run Hybrid Search
            print(f"\n--- Hybrid Search Results (Top 5) ---")
            hybrid_docs = await hybrid_search(
                query=case['query'],
                k=5,
                filter_metadata={"patient_id": case["patient_id"]},
                bm25_weight=0.5,
                semantic_weight=0.5
            )
            for i, doc in enumerate(hybrid_docs):
                h_score = doc.metadata.get('_hybrid_score', 'N/A')
                bm25_score = doc.metadata.get('_bm25_component', 'N/A')
                sem_score = doc.metadata.get('_semantic_component', 'N/A')
                print(f"[{i+1}] Hybrid: {h_score:.4f} (BM25: {bm25_score:.4f}, Sem: {sem_score:.4f}) | Content: {doc.page_content[:100]}...")

            if not hybrid_docs:
                print("❌ NO RESULTS FOUND (Hybrid)")

            # 5. Test OR Logic Fix
            print(f"\n--- Testing OR Logic Fix ---")
            # Construct an OR query from keywords
            or_query = " | ".join(case['keywords'])
            print(f"OR Query: {or_query}")
            
            or_sql = f"""
                SELECT content, ts_rank(ts_content, to_tsquery('english', :query)) as rank
                FROM "{SCHEMA_NAME}"."{TABLE_NAME}"
                WHERE langchain_metadata->>'patient_id' = :patient_id
                AND ts_content @@ to_tsquery('english', :query)
                ORDER BY rank DESC
                LIMIT 5
            """
            res = await conn.execute(text(or_sql), {
                "patient_id": case["patient_id"], 
                "query": or_query
            })
            rows = res.fetchall()
            for i, row in enumerate(rows):
                print(f"[{i+1}] Rank: {row[1]} | Content: {row[0][:100]}...")
                
            if not rows:
                print("❌ NO RESULTS FOUND (OR Logic)")

if __name__ == "__main__":
    asyncio.run(test_searches())
