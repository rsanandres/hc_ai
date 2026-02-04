#!/usr/bin/env python
"""
Quick script to embed the 5 verified test patients.
"""
import subprocess
import sys

# The 5 verified test patient IDs (partial)
PATIENT_PREFIXES = [
    '5e81d5b2',  # Danial Larson
    'd8d9460b',  # Ron Zieme
    '0beb6802',  # Doug Christiansen
    '6a4168a1',  # Jamie Hegmann
    '7f7ad77a',  # Carlo Herzog
]

def main():
    print("="*70)
    print("  Embedding 5 Verified Test Patients")
    print("="*70)
    
    # Get full patient IDs from database
    get_ids_script = """
import asyncio
import os
from pathlib import Path
import sys
sys.path.insert(0, '.')
from utils.env_loader import load_env_recursive
load_env_recursive(Path('.'))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def get_ids():
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST', 'localhost')
    port = os.getenv('DB_PORT', '5432')
    name = os.getenv('DB_NAME')
    
    conn_str = f'postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}'
    engine = create_async_engine(conn_str, echo=False)
    
    prefixes = %s
    patient_ids = []
    
    async with engine.begin() as conn:
        for prefix in prefixes:
            result = await conn.execute(text('''
                SELECT DISTINCT patient_id 
                FROM hc_ai_schema.fhir_raw_files
                WHERE patient_id LIKE :prefix
            '''), {'prefix': f'{prefix}%%'})
            pid = result.scalar()
            if pid:
                patient_ids.append(pid)
    
    for pid in patient_ids:
        print(pid)

asyncio.run(get_ids())
""" % PATIENT_PREFIXES
    
    result = subprocess.run(
        ['python', '-c', get_ids_script],
        capture_output=True,
        text=True,
        cwd='/Users/raph/Documents/hc_ai'
    )
    
    if result.returncode != 0:
        print(f"Error getting patient IDs: {result.stderr}")
        sys.exit(1)
    
    patient_ids = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
    
    print(f"\nFound {len(patient_ids)} patients to embed:")
    for pid in patient_ids:
        print(f"  - {pid[:20]}...")
    
    # Now run batch embed for just these patients
    print(f"\nRunning batch_embed_patients.py with limit {len(patient_ids)}...")
    result = subprocess.run(
        ['python', 'scripts/batch_embed_patients.py', '--limit', str(len(patient_ids))],
        cwd='/Users/raph/Documents/hc_ai'
    )
    
    sys.exit(result.returncode)

if __name__ == '__main__':
    main()
