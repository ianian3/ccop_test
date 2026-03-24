import sys
import os
import pandas as pd

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.etl_service import StandardCodeMapper

def verify_standardization():
    """
    Verifies that raw inputs are correctly mapped to standard codes
    using the StandardCodeMapper class.
    """
    app = create_app()
    with app.app_context():
        print("\n=== CCOP Standardization Verification ===\n")
        
        # 1. Bank Code Verification
        print("1. Bank Code Mapping (Raw -> Standard)")
        print("-" * 50)
        bank_inputs = ['국민', 'KB', '국민은행', '신한', 'SH', '우리은행', '토스']
        for raw in bank_inputs:
            mapped = StandardCodeMapper.map_bank_code(raw)
            print(f"   '{raw}' \t-> '{mapped}'")
            
        print("\n2. Carrier Code Verification (Raw -> Standard)")
        print("-" * 50)
        carrier_inputs = ['SKT', 'SK', 'KT', 'LGU+', 'LG', '알뜰폰']
        for raw in carrier_inputs:
            mapped = StandardCodeMapper.map_carrier_code(raw)
            print(f"   '{raw}' \t-> '{mapped}'")

        print("\n3. Hash Algorithm Normalization")
        print("-" * 50)
        hash_inputs = ['md5', 'SHA-1', 'sha256', 'SHA512']
        for raw in hash_inputs:
            mapped = StandardCodeMapper.normalize_hash_algorithm(raw)
            print(f"   '{raw}' \t-> '{mapped}'")
            
        print("\n4. Node Enrichment Simulation")
        print("-" * 50)
        
        # Case 1: Account Node
        acct_props = {'actno': '110-222-333', 'bank': '국민은행'}
        enriched_acct = StandardCodeMapper.auto_enrich('vt_bacnt', acct_props.copy())
        print(f"   [vt_bacnt] Input: {acct_props}")
        print(f"              Result: {enriched_acct} (bnk_cd added?)")
        
        # Case 2: Phone Node
        phone_props = {'telno': '010-9999-8888', 'carrier': 'SKT'}
        enriched_phone = StandardCodeMapper.auto_enrich('vt_telno', phone_props.copy())
        print(f"   [vt_telno] Input: {phone_props}")
        print(f"              Result: {enriched_phone} (carr_cd added?)")

        print("\n=== Verification Completed ===\n")

if __name__ == "__main__":
    verify_standardization()
