import asyncio
import os
import sys
import json
from datetime import datetime

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

# Import Tools
from api.agent.tools.calculators import (
    calculate_gfr, calculate_bmi, calculate_bsa, calculate_creatinine_clearance
)
from api.agent.tools.fda_tools import (
    search_fda_drugs, get_drug_recalls, get_drug_shortages, get_faers_events
)
from api.agent.tools.dosage_validator import validate_dosage
from api.agent.tools.terminology_tools import (
    search_icd10, validate_icd10_code, lookup_rxnorm
)
from api.agent.tools.loinc_lookup import lookup_loinc
from api.agent.tools.research_tools import (
    search_pubmed, search_clinical_trials, get_who_stats
)

class ToolTester:
    def __init__(self):
        self.results = []
        self.errors = []

    def log_result(self, tool_name, success, message, details=None):
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} [{tool_name}]: {message}")
        self.results.append({
            "tool": tool_name,
            "success": success,
            "message": message,
            "details": details
        })
        if not success:
            self.errors.append(f"{tool_name}: {message}")

    async def test_calculators(self):
        print("\n--- Testing Calculators ---")
        
        # Test BMI
        # 70kg, 175cm -> 22.9 (Normal)
        try:
            # Synchronous tool, use invoke
            res = calculate_bmi.invoke({"weight_kg": 70, "height_cm": 175})
            # LangChain tools might return string or dict depending on implementation. 
            # Our tools return Dict[str, Any].
            bmi = res['result']['bmi']
            category = res['result']['category']
            if 22.8 <= bmi <= 23.0 and category == "Normal":
                self.log_result("calculate_bmi", True, f"BMI {bmi} ({category}) correct for 70kg/175cm")
            else:
                self.log_result("calculate_bmi", False, f"Unexpected BMI result: {res}")
        except Exception as e:
            self.log_result("calculate_bmi", False, f"Exception: {str(e)}")

        # Test GFR (CKD-EPI 2021)
        # Male, 50, Cr 1.0 -> ~98
        try:
            res = calculate_gfr.invoke({"age": 50, "sex": "male", "creatinine": 1.0})
            gfr = res['result']['gfr']
            if 90 < gfr < 110:
                 self.log_result("calculate_gfr", True, f"eGFR {gfr} reasonable for healthy male")
            else:
                 self.log_result("calculate_gfr", False, f"Unexpected GFR: {gfr} (Expected ~98)")
        except Exception as e:
            self.log_result("calculate_gfr", False, f"Exception: {str(e)}")

    async def test_fda_tools(self):
        print("\n--- Testing FDA Tools (Live API) ---")
        
        # Search Drug
        try:
            # Async tool, use ainvoke
            res = await search_fda_drugs.ainvoke({"drug_name": "Ibuprofen", "limit": 1})
            if res['count'] > 0:
                self.log_result("search_fda_drugs", True, "Found 'Ibuprofen' labels")
            else:
                self.log_result("search_fda_drugs", False, "No results for 'Ibuprofen'")
        except Exception as e:
            self.log_result("search_fda_drugs", False, f"Exception: {str(e)}")

        # Validate Dosage
        # Ibuprofen 200mg is standard
        try:
            res = await validate_dosage.ainvoke({"drug_name": "Ibuprofen", "dose_amount": 200, "dose_unit": "mg", "frequency": "Q4H"})
            if res['is_valid']:
                 self.log_result("validate_dosage", True, "Ibuprofen 200mg validated as safe")
            else:
                 self.log_result("validate_dosage", False, f"Ibuprofen 200mg marked invalid: {res.get('warnings')}")
        except Exception as e:
            self.log_result("validate_dosage", False, f"Exception: {str(e)}")

    async def test_terminology(self):
        print("\n--- Testing Terminology Tools ---")

        # ICD-10 Validation
        # E11.9 is Type 2 Diabetes (Valid)
        try:
            res = await validate_icd10_code.ainvoke({"code": "E11.9"})
            valid = res['results'][0]['valid'] if res['results'] else False
            if valid:
                self.log_result("validate_icd10_code", True, "E11.9 validated successfully")
            else:
                self.log_result("validate_icd10_code", False, "E11.9 failed validation")
        except Exception as e:
             self.log_result("validate_icd10_code", False, f"Exception: {str(e)}")

        # ICD-10 Invalid
        try:
            res = await validate_icd10_code.ainvoke({"code": "ZZZ.999"})
            valid = res['results'][0]['valid'] if res['results'] else False
            if not valid:
                self.log_result("validate_icd10_code (Negative)", True, "Fake code correctly rejected")
            else:
                self.log_result("validate_icd10_code (Negative)", False, "Fake code accepted as valid")
        except Exception as e:
             self.log_result("validate_icd10_code (Negative)", False, f"Exception: {str(e)}")

        # RxNorm
        try:
            res = await lookup_rxnorm.ainvoke({"drug_name": "Metformin"})
            if res['count'] > 0:
                 self.log_result("lookup_rxnorm", True, "Found RxCUI for Metformin")
            else:
                 self.log_result("lookup_rxnorm", False, "No RxCUI for Metformin")
        except Exception as e:
             self.log_result("lookup_rxnorm", False, f"Exception: {str(e)}")
             
        # LOINC
        # 4548-4 is HbA1c
        try:
            res = await lookup_loinc.ainvoke({"code": "4548-4"})
            if res.get('success', False) and res.get('name'):
                 self.log_result("lookup_loinc", True, f"Found LOINC 4548-4: {res.get('name')[:30]}...")
            else:
                 self.log_result("lookup_loinc", False, f"LOINC 4548-4 not found. Response: {res}")
        except Exception as e:
             self.log_result("lookup_loinc", False, f"Exception: {str(e)}")

    async def test_research(self):
        print("\n--- Testing Research Tools ---")
        
        # PubMed
        try:
            res = await search_pubmed.ainvoke({"query": "diabetes", "max_results": 1})
            if res['count'] > 0:
                 self.log_result("search_pubmed", True, "PubMed returned results for 'diabetes'")
            else:
                 self.log_result("search_pubmed", False, "PubMed returned 0 results")
        except Exception as e:
             self.log_result("search_pubmed", False, f"Exception: {str(e)}")

    async def run_all(self):
        await self.test_calculators()
        await self.test_fda_tools()
        await self.test_terminology()
        await self.test_research()
        
        print("\n" + "="*50)
        print(f"SUMMARY: {len(self.results) - len(self.errors)}/{len(self.results)} Tests Passed")
        if self.errors:
            print("FAILURES:")
            for err in self.errors:
                print(f"  - {err}")
        print("="*50)

if __name__ == "__main__":
    tester = ToolTester()
    asyncio.run(tester.run_all())
