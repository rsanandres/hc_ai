import os
import sys
import asyncio

# Add scripts/ and root to path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, CURRENT_DIR)
sys.path.insert(0, ROOT_DIR)

from utils.env_loader import load_env_recursive
load_env_recursive(ROOT_DIR)

import ingest_fhir_json

async def check_patients():
    candidates = [
        ("Danial935 Larson691", "5e81d5b2-af01-4367-9b2e-0cdf479094a4"),
        ("Zieme669 Ron199", "d8d9460b-4cb6-47f9-a94f-9e58390204b2"),
        ("Doug821 Christiansen946", "0beb6802-3353-4144-8ae3-97176bce86c3"),
        ("Jamie445 Hegmann501", "6a4168a1-2cfd-4269-8139-8a4a663adfe7"),
        ("Carlo512 Herzog43", "7f7ad77a-5dd5-4df0-ba36-f4f1e4b6d368")
    ]
    
    ids = [c[1] for c in candidates]
    
    print(f"Checking {len(ids)} patients in Postgres ({ingest_fhir_json.DB_HOST}:{ingest_fhir_json.DB_PORT}/{ingest_fhir_json.DB_NAME})...")
    
    try:
        found_records = await ingest_fhir_json.get_latest_raw_files_by_patient_ids(ids)
        found_ids = {r['patient_id'] for r in found_records}
        
        missing = []
        for name, pid in candidates:
            if pid in found_ids:
                print(f"✅ FOUND: {name} (ID: {pid})")
            else:
                print(f"❌ MISSING: {name} (ID: {pid})")
                missing.append(pid)
        
        if missing:
            print(f"\nMissing {len(missing)} patients. You may need to ingest the corresponding files.")
        else:
            print("\nAll candidate patients found in Postgres!")
            
    except Exception as e:
        print(f"Error checking DB: {e}")

if __name__ == "__main__":
    asyncio.run(check_patients())
