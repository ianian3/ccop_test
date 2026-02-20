import sys
import os
import json
from app import create_app
from app.services.schema_mapper import KICSSchemaMapper

sys.path.append(os.getcwd())

app = create_app()

def verify_mapper():
    with app.app_context():
        print("=== KICS Schema Mapper Verification ===\n")
        
        # Test Case 1: Bank Transaction
        columns_1 = ["순번", "거래일시", "출금계좌번호", "입금은행", "입금계좌번호", "거래금액", "적요"]
        sample_1 = ["1", "2024-01-01 12:00:00", "110-123-456789", "국민은행", "999-888-777777", "1000000", "보이스피싱 피해금"]
        
        print(f"Test Case 1: Bank Transfer")
        print(f"Columns: {columns_1}")
        
        # sample_rows must be list of dicts {col: val}
        sample_1_dict = {col: val for col, val in zip(columns_1, sample_1)}
        print("▶ Analyzing CSV structure (via Fallback)...")
        # Direct call to verify fallback logic
        wrapper = KICSSchemaMapper._fallback_mapping(columns_1, [sample_1_dict])
        print(f"DEBUG: wrapper type = {type(wrapper)}")
        print(f"DEBUG: wrapper = {wrapper}")
        
        if isinstance(wrapper, list):
             # Maybe it IS returning something else?
             result = {} 
        else:
             result = wrapper.get('mapping', {})
        
        # 2. Check Action Detection
        action = result.get('detected_action', {})
        print(f"Detected Action: {action.get('type')} (Confidence: {action.get('confidence')})")
        
        if action.get('type') == 'Transfer':
            print("✅ Correctly identified 'Transfer' action.")
        else:
            print(f"⚠️ Expected 'Transfer', got '{action.get('type')}'")

        # 3. Generate ETL Config
        print("▶ Generating ETL Config...")
        print(f"DEBUG: Layer Mapping: {json.dumps(result.get('layer_mapping'), indent=2, ensure_ascii=False)}")
        print(f"DEBUG: Relationships: {json.dumps(result.get('relationships'), indent=2, ensure_ascii=False)}")
        
        etl_configs = KICSSchemaMapper.generate_etl_config(wrapper)
        
        if not etl_configs:
            print("❌ No ETL configuration generated.")
            return

        # 4. Verify Mapping
        # We expect a mapping between two accounts
        found_transfer = False
        for cfg in etl_configs:
            src_col = cfg.get('sourceCol')
            tgt_col = cfg.get('targetCol')
            edge = cfg.get('edgeType')
            src_lbl = cfg.get('srcLabel')
            tgt_lbl = cfg.get('tgtLabel')
            
            print(f" - Config: {src_col}({src_lbl}) -[{edge}]-> {tgt_col}({tgt_lbl})")
            
            if src_lbl == 'vt_bacnt' and tgt_lbl == 'vt_bacnt' and edge in ['transferred_to', 'used_account']:
                found_transfer = True
        
        if found_transfer:
            print("✅ ETL Configuration correctly maps account-to-account transfer.")
        else:
            print("⚠️ Could not find expected account transfer mapping in config.")

        if found_transfer:
            print("✅ ETL Configuration correctly maps account-to-account transfer.")
        else:
            print("⚠️ Could not find expected account transfer mapping in config.")

        # Test Case 2: Call Log
        print("\nTest Case 2: Call Log")
        columns_2 = ["발신번호", "수신번호", "통화시간", "기지국위치"]
        sample_2 = ["010-1234-5678", "02-987-6543", "120", "서울 강남구"]
        sample_2_dict = {col: val for col, val in zip(columns_2, sample_2)}
        
        wrapper_2 = KICSSchemaMapper._fallback_mapping(columns_2, [sample_2_dict])
        etl_configs_2 = KICSSchemaMapper.generate_etl_config(wrapper_2)
        
        found_call = False
        for cfg in etl_configs_2:
            src_lbl = cfg.get('srcLabel')
            tgt_lbl = cfg.get('tgtLabel')
            edge = cfg.get('edgeType')
            print(f" - Config: {cfg.get('sourceCol')}({src_lbl}) -[{edge}]-> {cfg.get('targetCol')}({tgt_lbl})")
            
            if src_lbl == 'vt_telno' and tgt_lbl == 'vt_telno' and edge == 'contacted':
                found_call = True
                
        if found_call:
            print("✅ ETL Configuration correctly maps phone-to-phone call (contacted).")
        else:
             print("⚠️ Could not find expected call mapping.")
             print(f"DEBUG: Layer Mapping 2: {json.dumps(wrapper_2.get('mapping', {}).get('layer_mapping'), indent=2, ensure_ascii=False)}")

        # Test Case 3: IP to IP Communication
        print("\nTest Case 3: IP Log")
        columns_3 = ["Src_IP", "Dst_IP", "Port", "Protocol"]
        sample_3 = ["192.168.1.10", "10.0.0.5", "80", "TCP"]
        sample_3_dict = {col: val for col, val in zip(columns_3, sample_3)}
        
        wrapper_3 = KICSSchemaMapper._fallback_mapping(columns_3, [sample_3_dict])
        etl_configs_3 = KICSSchemaMapper.generate_etl_config(wrapper_3)
        
        found_ip = False
        for cfg in etl_configs_3:
            src_lbl = cfg.get('srcLabel')
            tgt_lbl = cfg.get('tgtLabel')
            edge = cfg.get('edgeType')
            print(f" - Config: {cfg.get('sourceCol')}({src_lbl}) -[{edge}]-> {cfg.get('targetCol')}({tgt_lbl})")
            
            if src_lbl == 'vt_ip' and tgt_lbl == 'vt_ip' and edge == 'communicated_with':
                found_ip = True

        if found_ip:
            print("✅ ETL Configuration correctly maps IP-to-IP communication.")
        else:
             print("⚠️ Could not find expected IP mapping.")
             print(f"DEBUG: Layer Mapping 3: {json.dumps(wrapper_3.get('mapping', {}).get('layer_mapping'), indent=2, ensure_ascii=False)}")

if __name__ == "__main__":
    try:
        verify_mapper()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"CRITICAL ERROR: {e}")
