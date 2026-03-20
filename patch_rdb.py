import sys

with open('app/services/rdb_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "@staticmethod" in line and "def import_csv_to_rdb" in lines[i+1]:
        break
    new_lines.append(line)

new_func = """    @staticmethod
    def import_csv_to_rdb(file_path, clear_existing=False):
        \"\"\"CSV 파일을 분석하여 RDB 테이블(V2 - 27개 구조)에 적재\"\"\"
        import time
        import random
        from datetime import datetime
        print(f"▶ [RDB] CSV 적재 시작 (V2): {file_path} (기존 데이터 초기화: {clear_existing})")
        
        conn, cur = RDBService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        
        def gen_sn():
            # NUMERIC(22) 일련번호 생성을 위한 유틸 (Timestamp + Random)
            return int(time.time() * 1000) * 100000 + random.randint(0, 99999)

        try:
            if clear_existing:
                print("   [DB] 기존 RDB 데이터 전체 초기화 (TRUNCATE V2)...")
                tables_to_clear = [
                    'TB_DGTL_FILE_INVNT', 'TB_EML_TRNS_EVT', 'TB_SYS_LGN_EVT',
                    'TB_DRUG_SLANG', 'TB_DRUG_CLUE', 'TB_FRD_VCTM_RPT',
                    'TB_WEB_MLGN_IDC', 'TB_WEB_ATCH', 'TB_WEB_PAGE', 'TB_WEB_URL', 'TB_WEB_DMN',
                    'TB_VHCL_TOLL_EVT', 'TB_VHCL_LPR_EVT', 'TB_VHCL_MST',
                    'TB_GEO_TRST_CARD_TRIP', 'TB_GEO_MBL_LOC_EVT',
                    'TB_CHAT_MSG', 'TB_TELNO_SMS_MSG', 'TB_TELNO_CALL_DTL', 'TB_TELNO_JOIN', 'TB_TELNO_MST',
                    'TB_FIN_EXTRC_BACNT', 'TB_FIN_BACNT_DLNG', 'TB_FIN_BACNT',
                    'TB_INST', 'TB_PRSN', 'TB_INCDNT_MST'
                ]
                for table in tables_to_clear:
                    cur.execute(f"TRUNCATE TABLE {table} CASCADE;")
                print("   [DB] 초기화 완료.")
            
            import pandas as pd
            df = pd.read_csv(file_path).fillna('')
            count_stats = {"cases": 0, "suspects": 0, "accounts": 0, "phones": 0, "transfers": 0, "calls": 0, "ips": 0}
            
            # --- Column Mapping 추론 ---
            from app.services.ontology_service import KICSCrimeDomainOntology
            cols = df.columns
            col_map = {}
            patterns = KICSCrimeDomainOntology.COLUMN_PATTERNS
            type_to_rdb = KICSCrimeDomainOntology.COLUMN_TYPE_TO_RDB
            
            priority_order = ['caller', 'callee', 'sender', 'receiver', 'nickname']
            sorted_patterns = {t: patterns[t] for t in priority_order if t in patterns}
            for t, cfg in patterns.items():
                if t not in sorted_patterns: sorted_patterns[t] = cfg
            
            for c in cols:
                c_lower = c.lower().strip()
                matched = False
                for type_name, config in sorted_patterns.items():
                    for pattern in config["patterns"]:
                        if c_lower == pattern.lower():
                            if type_to_rdb.get(type_name) not in col_map:
                                col_map[type_to_rdb.get(type_name)] = c
                            matched = True; break
                    if matched: break
                
                if not matched:
                    for type_name, config in sorted_patterns.items():
                        for pattern in config["patterns"]:
                            if pattern.lower() in c_lower or c_lower in pattern.lower():
                                if type_to_rdb.get(type_name) not in col_map:
                                    col_map[type_to_rdb.get(type_name)] = c
                                matched = True; break
                        if matched: break
            
            print(f"   [매핑 V2] {col_map}")
            
            for _, row in df.iterrows():
                # Extract Values
                case_val = str(row.get(col_map.get('case', ''), '')).strip()
                crime_val = str(row.get(col_map.get('crime', ''), '')).strip()
                date_val = str(row.get(col_map.get('date', ''), '')).strip() or str(datetime.now())
                
                person_id = str(row.get(col_map.get('suspect', ''), '')).strip()
                nickname_val = str(row.get(col_map.get('nickname', ''), '')).strip()
                name_val = str(row.get(col_map.get('name', ''), '')).strip()
                person_id = person_id or nickname_val or name_val # ensure ID exists if any present
                
                account_val = str(row.get(col_map.get('account', ''), '')).strip()
                sender_val = str(row.get(col_map.get('sender', ''), '')).strip()
                receiver_val = str(row.get(col_map.get('receiver', ''), '')).strip()
                
                phone_val = str(row.get(col_map.get('phone', ''), '')).strip()
                caller_val = str(row.get(col_map.get('caller', ''), '')).strip()
                callee_val = str(row.get(col_map.get('callee', ''), '')).strip()
                
                ip_val = str(row.get(col_map.get('ip', ''), '')).strip()
                
                amount_raw = str(row.get(col_map.get('amount', ''), '0')).replace(',', '')
                try: amount_val = int(float(amount_raw))
                except: amount_val = 0
                
                duration_val = 0
                if 'duration' in col_map:
                    try: duration_val = int(row[col_map['duration']])
                    except: pass

                # 1. 사건 마스터 (TB_INCDNT_MST)
                if case_val:
                    cur.execute(\"\"\"
                        INSERT INTO TB_INCDNT_MST (INCDNT_NO, INCDNT_NM, OCCRN_DT)
                        VALUES (%s, %s, NULLIF(%s, '')::timestamp)
                        ON CONFLICT (INCDNT_NO) DO NOTHING
                    \"\"\", (case_val, crime_val or f"사건_{case_val}", date_val))
                    if cur.rowcount > 0: count_stats['cases'] += 1

                # 2. 사람/신원 (TB_PRSN)
                if person_id:
                    cur.execute(\"\"\"
                        INSERT INTO TB_PRSN (PRSN_ID, KORN_FLNM, RMK_CN)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (PRSN_ID) DO UPDATE SET 
                            KORN_FLNM = COALESCE(EXCLUDED.KORN_FLNM, TB_PRSN.KORN_FLNM),
                            RMK_CN = COALESCE(EXCLUDED.RMK_CN, TB_PRSN.RMK_CN)
                    \"\"\", (person_id, name_val or person_id, nickname_val))
                    if cur.rowcount > 0: count_stats['suspects'] += 1

                # 3. 금융 계좌 (TB_FIN_BACNT)
                def insert_account(actno):
                    if not actno: return
                    cur.execute(\"\"\"
                        INSERT INTO TB_FIN_BACNT (BACNT_NO, BANK_CD, BANK_NM) 
                        VALUES (%s, '999', '미상은행') 
                        ON CONFLICT (BACNT_NO, BANK_CD) DO NOTHING
                    \"\"\", (actno,))
                
                insert_account(account_val)
                insert_account(sender_val)
                insert_account(receiver_val)
                if account_val or sender_val or receiver_val: count_stats['accounts'] += 1

                # 4. 이체 내역 (TB_FIN_BACNT_DLNG)
                real_sender = sender_val if sender_val else (account_val if receiver_val else None)
                real_receiver = receiver_val if receiver_val else (account_val if sender_val else None)
                if real_sender and real_receiver:
                    cur.execute(\"\"\"
                        INSERT INTO TB_FIN_BACNT_DLNG (DLNG_SN, BACNT_NO, BANK_CD, DLNG_DT, DLNG_AMT, TRRC_BACNT_NO)
                        VALUES (%s, %s, '999', NULLIF(%s, '')::timestamp, %s, %s)
                        ON CONFLICT (DLNG_SN) DO NOTHING
                    \"\"\", (gen_sn(), real_sender, date_val, amount_val, real_receiver))
                    count_stats['transfers'] += 1

                # 5. 전화번호 (TB_TELNO_MST)
                def insert_phone(telno):
                    if not telno: return
                    cur.execute("INSERT INTO TB_TELNO_MST (TELNO) VALUES (%s) ON CONFLICT (TELNO) DO NOTHING", (telno,))
                
                insert_phone(phone_val)
                insert_phone(caller_val)
                insert_phone(callee_val)
                if phone_val or caller_val or callee_val: count_stats['phones'] += 1

                # 6. 통화 상세 내역 (TB_TELNO_CALL_DTL)
                if caller_val and callee_val:
                    cur.execute(\"\"\"
                        INSERT INTO TB_TELNO_CALL_DTL (CALL_SN, DSPTCH_TELNO, RCPTN_TELNO, CALL_STRT_DT, CALL_DUR_SEC)
                        VALUES (%s, %s, %s, NULLIF(%s, '')::timestamp, %s)
                        ON CONFLICT (CALL_SN) DO NOTHING
                    \"\"\", (gen_sn(), caller_val, callee_val, date_val, duration_val))
                    count_stats['calls'] += 1

                # 7. 접속 IP 이력 (TB_SYS_LGN_EVT)
                if ip_val:
                    dummy_user = person_id if person_id else "UNKNOWN_USER"
                    cur.execute(\"\"\"
                        INSERT INTO TB_SYS_LGN_EVT (LGN_EVT_SN, USER_ID, CNNT_IP_ADDR, LGN_DT)
                        VALUES (%s, %s, %s, NULLIF(%s, '')::timestamp)
                        ON CONFLICT (LGN_EVT_SN) DO NOTHING
                    \"\"\", (gen_sn(), dummy_user, ip_val, date_val))
                    count_stats['ips'] += 1

                # 8. 사기 피해 신고 (사건-증거 결합 테이블 용도)
                if case_val and (person_id or account_val or phone_val):
                    cur.execute(\"\"\"
                        INSERT INTO TB_FRD_VCTM_RPT (DCLR_SN, DCLR_DT, SUSPCT_TELNO, SUSPCT_BACNT_NO, DAM_CN)
                        VALUES (%s, NULLIF(%s, '')::timestamp, %s, %s, %s)
                        ON CONFLICT (DCLR_SN) DO NOTHING
                    \"\"\", (gen_sn(), date_val, phone_val, account_val, f"사건참조:{case_val}"))

            conn.commit()
            print(f"✅ RDB_V2 적재 완료: {count_stats}")
            return True, count_stats

        except Exception as e:
            conn.rollback()
            print(f"❌ RDB_V2 적재 오류: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
        finally:
            cur.close()
            conn.close()
"""

new_lines.append(new_func)

with open('app/services/rdb_service.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
