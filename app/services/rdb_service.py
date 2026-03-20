import pandas as pd
import psycopg2
from flask import current_app
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

class RDBService:
    @staticmethod
    def get_db_connection():
        """DB 연결 헬퍼"""
        try:
            conn = psycopg2.connect(
                dbname=current_app.config['DB_CONFIG']['dbname'],
                user=current_app.config['DB_CONFIG']['user'],
                password=current_app.config['DB_CONFIG']['password'],
                host=current_app.config['DB_CONFIG']['host'],
                port=current_app.config['DB_CONFIG']['port']
            )
            return conn, conn.cursor()
        except Exception as e:
            logger.error(f"DB 접속 오류: {e}")
            return None, None

    @staticmethod
    def import_predefined_schema_to_rdb(file_path, filename, clear_existing=False):
        import pandas as pd
        import psycopg2
        import uuid
        from flask import current_app
        
        db_config = current_app.config['DB_CONFIG']
        count_stats = {'cases':0, 'suspects':0, 'accounts':0, 'phones':0, 'transfers':0, 'calls':0, 'relations':0}
        
        try:
            conn = psycopg2.connect(**db_config)
            cur = conn.cursor()
            
            if clear_existing:
                logger.info("   [DB] 기존 RDB 데이터 전체 초기화 (TRUNCATE V2, 사전정의 스크립트)...")
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
                logger.info("   [DB] 초기화 완료.")
            
            df = pd.read_csv(file_path).fillna('')
            fname = filename.lower()
            
            import time, random
            def gen_sn(): return int(time.time() * 1e7) + random.randint(0, 9999999)

            if 'tbl_vt_psn' in fname:
                for _, row in df.iterrows():
                    flnm = str(row.get('flnm', '')).strip()
                    if flnm:
                        cur.execute("""
                            INSERT INTO TB_PRSN (PRSN_ID, KORN_FLNM, PRSN_SE_CD)
                            VALUES (%s, %s, '99')
                            ON CONFLICT (PRSN_ID) DO NOTHING
                        """, (flnm, flnm))
                        if cur.rowcount > 0: count_stats['suspects'] += 1
                        
            elif 'tbl_vt_telno' in fname:
                for _, row in df.iterrows():
                    telno = str(row.get('telno', '')).strip()
                    if telno:
                        cur.execute("""
                            INSERT INTO TB_TELNO_MST (TELNO, JOIN_TYP_CD)
                            VALUES (%s, '01')
                            ON CONFLICT (TELNO) DO NOTHING
                        """, (telno,))
                        if cur.rowcount > 0: count_stats['phones'] += 1
                        
            elif 'tbl_vt_bacnt' in fname:
                for _, row in df.iterrows():
                    actno = str(row.get('actno', '')).strip()
                    dpstr = str(row.get('dpstr', '')).strip()
                    bank = str(row.get('bank', '')).strip()
                    if actno:
                        cur.execute("""
                            INSERT INTO TB_FIN_BACNT (BACNT_NO, BANK_CD, BANK_NM, DPSTR_NM)
                            VALUES (%s, '999', %s, %s)
                            ON CONFLICT (BACNT_NO, BANK_CD) DO NOTHING
                        """, (actno, bank, dpstr))
                        if cur.rowcount > 0: count_stats['accounts'] += 1
                        
            elif 'tbl_eg_call' in fname:
                # 실제 CSV 컬럼: id, snerpn, dsptch_no, rcvr, rcptn_no, bgng_ymdhm, end_ymdhm, tlcmco, se, rmrk
                from datetime import datetime as dt_parse
                for _, row in df.iterrows():
                    caller = str(row.get('dsptch_no', '')).strip()
                    callee = str(row.get('rcptn_no', '')).strip()
                    start_dt = str(row.get('bgng_ymdhm', '')).strip()
                    end_dt = str(row.get('end_ymdhm', '')).strip()
                    tlcmco = str(row.get('tlcmco', '')).strip()
                    call_type = str(row.get('se', '')).strip()
                    # 통화시간(초) 계산
                    dur_sec = 0
                    try:
                        t1 = dt_parse.strptime(start_dt, '%Y-%m-%d %H:%M:%S')
                        t2 = dt_parse.strptime(end_dt, '%Y-%m-%d %H:%M:%S')
                        dur_sec = int((t2 - t1).total_seconds())
                    except: pass
                    
                    if caller and callee:
                        # 발신/수신 전화번호 자동 upsert
                        cur.execute("""
                            INSERT INTO TB_TELNO_MST (TELNO, TELCO_NM, JOIN_TYP_CD) VALUES (%s, NULLIF(%s,''), '01') ON CONFLICT DO NOTHING;
                        """, (caller, tlcmco))
                        cur.execute("""
                            INSERT INTO TB_TELNO_MST (TELNO, JOIN_TYP_CD) VALUES (%s, '01') ON CONFLICT DO NOTHING;
                        """, (callee,))
                        # 통화내역 적재
                        call_typ_cd = '01' if call_type == '음성' else '02'  # 02=인터넷접속 등
                        cur.execute("""
                            INSERT INTO TB_TELNO_CALL_DTL (CALL_SN, DSPTCH_TELNO, RCPTN_TELNO, CALL_STRT_DT, CALL_DUR_SEC, CALL_TYP_CD)
                            VALUES (%s, %s, %s, NULLIF(%s, '')::timestamp, %s, %s)
                            ON CONFLICT (CALL_SN) DO NOTHING
                        """, (gen_sn(), caller, callee, start_dt, dur_sec, call_typ_cd))
                        if cur.rowcount > 0: count_stats['calls'] += 1
                        
            elif 'tbl_eg_rmt' in fname:
                # 실제 CSV 컬럼: id, se, dpstr, bank, actno, rmt_se, dpst_amt, abstr, tkmny_amt, rlt_bank, rlt_dpstr, rlt_actno, Ip, rcptn_trmnlno, rmt_ymdhm
                for _, row in df.iterrows():
                    se = str(row.get('se', '')).strip()           # 입금/출금
                    dpstr = str(row.get('dpstr', '')).strip()     # 예금주
                    bank = str(row.get('bank', '')).strip()       # 은행
                    actno = str(row.get('actno', '')).strip()     # 출금계좌
                    rmt_se = str(row.get('rmt_se', '')).strip()   # 이체/현금인출
                    rlt_bank = str(row.get('rlt_bank', '')).strip()
                    rlt_dpstr = str(row.get('rlt_dpstr', '')).strip()
                    rlt_actno = str(row.get('rlt_actno', '')).strip()  # 입금계좌
                    ip_val = str(row.get('Ip', row.get('ip', ''))).strip()
                    date_val = str(row.get('rmt_ymdhm', '')).strip()
                    
                    # 금액: 입금이면 dpst_amt, 출금이면 tkmny_amt
                    try:
                        dpst_amt = int(float(str(row.get('dpst_amt', '0')).replace(',', '') or '0'))
                    except: dpst_amt = 0
                    try:
                        tkmny_amt = int(float(str(row.get('tkmny_amt', '0')).replace(',', '') or '0'))
                    except: tkmny_amt = 0
                    amount = dpst_amt if dpst_amt > 0 else tkmny_amt
                    
                    # 출금계좌 자동 upsert
                    if actno:
                        cur.execute("""
                            INSERT INTO TB_FIN_BACNT (BACNT_NO, BANK_CD, BANK_NM, DPSTR_NM)
                            VALUES (%s, '999', NULLIF(%s,''), NULLIF(%s,''))
                            ON CONFLICT (BACNT_NO, BANK_CD) DO UPDATE SET
                                BANK_NM = COALESCE(EXCLUDED.BANK_NM, TB_FIN_BACNT.BANK_NM),
                                DPSTR_NM = COALESCE(EXCLUDED.DPSTR_NM, TB_FIN_BACNT.DPSTR_NM)
                        """, (actno, bank, dpstr))
                    # 입금계좌 자동 upsert
                    if rlt_actno:
                        cur.execute("""
                            INSERT INTO TB_FIN_BACNT (BACNT_NO, BANK_CD, BANK_NM, DPSTR_NM)
                            VALUES (%s, '999', NULLIF(%s,''), NULLIF(%s,''))
                            ON CONFLICT (BACNT_NO, BANK_CD) DO UPDATE SET
                                BANK_NM = COALESCE(EXCLUDED.BANK_NM, TB_FIN_BACNT.BANK_NM),
                                DPSTR_NM = COALESCE(EXCLUDED.DPSTR_NM, TB_FIN_BACNT.DPSTR_NM)
                        """, (rlt_actno, rlt_bank, rlt_dpstr))
                    
                    # 이체 내역 적재
                    if actno and rlt_actno:
                        dlng_se = '01' if se == '입금' else '02'  # 01=입금, 02=출금
                        cur.execute("""
                            INSERT INTO TB_FIN_BACNT_DLNG (DLNG_SN, BACNT_NO, BANK_CD, DLNG_DT, DLNG_SE_CD, DLNG_AMT, TRRC_PSNNM, TRRC_BACNT_NO)
                            VALUES (%s, %s, '999', NULLIF(%s, '')::timestamp, %s, %s, NULLIF(%s, ''), %s)
                            ON CONFLICT (DLNG_SN) DO NOTHING
                        """, (gen_sn(), actno, date_val, dlng_se, amount, rlt_dpstr, rlt_actno))
                        if cur.rowcount > 0: count_stats['transfers'] += 1
                    
                    # IP 주소가 있으면 접속 로그도 적재
                    if ip_val:
                        cur.execute("""
                            INSERT INTO TB_SYS_LGN_EVT (LGN_EVT_SN, USER_ID, CNNT_IP_ADDR, LGN_DT, LGN_RESULT_CD)
                            VALUES (%s, %s, %s, NULLIF(%s, '')::timestamp, 'S')
                            ON CONFLICT (LGN_EVT_SN) DO NOTHING
                        """, (gen_sn(), dpstr or 'UNKNOWN', ip_val, date_val))

            elif 'tbl_eg_bactno_poss' in fname:
                # 계좌 소유관계: CSV 컬럼 flnm, actno
                for _, row in df.iterrows():
                    flnm = str(row.get('flnm', '')).strip()
                    actno = str(row.get('actno', '')).strip()
                    if flnm and actno:
                        # 인물 upsert
                        cur.execute("""
                            INSERT INTO TB_PRSN (PRSN_ID, KORN_FLNM, PRSN_SE_CD)
                            VALUES (%s, %s, '99')
                            ON CONFLICT (PRSN_ID) DO NOTHING
                        """, (flnm, flnm))
                        # 계좌 upsert
                        cur.execute("""
                            INSERT INTO TB_FIN_BACNT (BACNT_NO, BANK_CD, DPSTR_NM)
                            VALUES (%s, '999', %s)
                            ON CONFLICT (BACNT_NO, BANK_CD) DO UPDATE SET
                                DPSTR_NM = COALESCE(EXCLUDED.DPSTR_NM, TB_FIN_BACNT.DPSTR_NM)
                        """, (actno, flnm))
                        count_stats['relations'] += 1
                        count_stats['accounts'] += 1

            elif 'tbl_eg_telno_poss' in fname:
                # 전화번호 소유관계: CSV 컬럼 flnm, telno
                for _, row in df.iterrows():
                    flnm = str(row.get('flnm', '')).strip()
                    telno = str(row.get('telno', '')).strip()
                    if flnm and telno:
                        # 인물 upsert
                        cur.execute("""
                            INSERT INTO TB_PRSN (PRSN_ID, KORN_FLNM, PRSN_SE_CD)
                            VALUES (%s, %s, '99')
                            ON CONFLICT (PRSN_ID) DO NOTHING
                        """, (flnm, flnm))
                        # 전화번호 upsert
                        cur.execute("""
                            INSERT INTO TB_TELNO_MST (TELNO, JOIN_TYP_CD)
                            VALUES (%s, '01')
                            ON CONFLICT (TELNO) DO NOTHING
                        """, (telno,))
                        # 가입(소유) 관계 적재
                        cur.execute("""
                            INSERT INTO TB_TELNO_JOIN (JOIN_SN, TELNO, JOIN_PSNNM)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (JOIN_SN) DO NOTHING
                        """, (gen_sn(), telno, flnm))
                        count_stats['relations'] += 1
                        count_stats['phones'] += 1

            elif 'tbl_eg_case_prsn' in fname:
                # 사건-인물 관계: CSV 컬럼 incdnt_no, prsn_id, role
                # → 임시 테이블에 저장 (GDB ETL에서 involves 엣지 생성)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS TB_INCDNT_PRSN (
                        INCDNT_NO VARCHAR(100),
                        PRSN_ID VARCHAR(100),
                        ROLE_CD VARCHAR(50),
                        PRIMARY KEY (INCDNT_NO, PRSN_ID)
                    )
                """)
                for _, row in df.iterrows():
                    incdnt_no = str(row.get('incdnt_no', '')).strip()
                    prsn_id = str(row.get('prsn_id', '')).strip()
                    role = str(row.get('role', '')).strip()
                    if incdnt_no and prsn_id:
                        cur.execute("""
                            INSERT INTO TB_INCDNT_PRSN (INCDNT_NO, PRSN_ID, ROLE_CD)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (INCDNT_NO, PRSN_ID) DO UPDATE SET ROLE_CD = EXCLUDED.ROLE_CD
                        """, (incdnt_no, prsn_id, role))
                        count_stats['relations'] += 1

            elif 'tbl_eg_case' in fname:
                # 사건 정보: CSV 컬럼 incdnt_no, incdnt_nm, incdnt_typ_cd, occrn_dt, chrgdp_nm, chrg_plcmn_nm, incdnt_smry_cn
                for _, row in df.iterrows():
                    incdnt_no = str(row.get('incdnt_no', '')).strip()
                    incdnt_nm = str(row.get('incdnt_nm', '')).strip()
                    typ_cd = str(row.get('incdnt_typ_cd', '')).strip()
                    occrn_dt = str(row.get('occrn_dt', '')).strip()
                    chrgdp = str(row.get('chrgdp_nm', '')).strip()
                    plcmn = str(row.get('chrg_plcmn_nm', '')).strip()
                    smry = str(row.get('incdnt_smry_cn', '')).strip()
                    if incdnt_no:
                        cur.execute("""
                            INSERT INTO TB_INCDNT_MST (INCDNT_NO, INCDNT_NM, INCDNT_TYP_CD, OCCRN_DT, CHRGDP_NM, CHRG_PLCMN_NM, INCDNT_SMRY_CN)
                            VALUES (%s, %s, NULLIF(%s,''), NULLIF(%s,'')::timestamp, NULLIF(%s,''), NULLIF(%s,''), NULLIF(%s,''))
                            ON CONFLICT DO NOTHING
                        """, (incdnt_no, incdnt_nm, typ_cd, occrn_dt, chrgdp, plcmn, smry))
                        if cur.rowcount > 0: count_stats['cases'] = count_stats.get('cases', 0) + 1
                        
            conn.commit()
            return True, count_stats
            
        except Exception as e:
            if 'conn' in locals() and conn: conn.rollback()
            return False, str(e)
        finally:
            if 'cur' in locals() and cur: cur.close()
            if 'conn' in locals() and conn: conn.close()

    @staticmethod
    def import_csv_to_rdb(file_path, clear_existing=False, custom_mapping=None):
        """CSV 파일을 분석하여 RDB 테이블(V2 - 27개 구조)에 적재"""
        import time
        import random
        from datetime import datetime
        logger.info(f"▶ [RDB] CSV 적재 시작 (V2): {file_path} (기존 데이터 초기화: {clear_existing})")
        
        conn, cur = RDBService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        
        def gen_sn():
            # NUMERIC(22) 일련번호 생성을 위한 유틸 (Timestamp + Random)
            return int(time.time() * 1000) * 100000 + random.randint(0, 99999)

        try:
            if clear_existing:
                logger.info("   [DB] 기존 RDB 데이터 전체 초기화 (TRUNCATE V2)...")
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
                logger.info("   [DB] 초기화 완료.")
            
            import pandas as pd
            df = pd.read_csv(file_path).fillna('')
            count_stats = {"cases": 0, "suspects": 0, "accounts": 0, "phones": 0, 
                           "transfers": 0, "calls": 0, "ips": 0,
                           "orgs": 0, "sms": 0, "chats": 0, "joins": 0,
                           "locations": 0, "vehicles": 0, "lpr": 0, "domains": 0, "urls": 0, "files": 0}
            logger.info(f"   [CSV] 컬럼 목록: {list(df.columns)}")
            logger.info(f"   [CSV] 전체 행 수: {len(df)}")
            
            # --- Column Mapping 추론 ---
            from app.services.ontology_service import KICSCrimeDomainOntology
            cols = df.columns
            col_map = {}
            patterns = KICSCrimeDomainOntology.COLUMN_PATTERNS
            type_to_rdb = KICSCrimeDomainOntology.COLUMN_TYPE_TO_RDB
            
            if custom_mapping:
                logger.info("   [매핑 V2] 프론트엔드 검토 완료 매핑본 직접 연동")
                for item in custom_mapping:
                    col = item.get("column")
                    mapped_type = item.get("mapped_type")
                    if mapped_type and mapped_type not in ("unmapped", "ignore"):
                        col_type = type_to_rdb.get(mapped_type, mapped_type)
                        col_map[col_type] = col
            else:
                priority_order = ['caller', 'callee', 'sender', 'receiver', 'nickname']
                sorted_patterns = {t: patterns[t] for t in priority_order if t in patterns}
                for t, cfg in patterns.items():
                    if t not in sorted_patterns: sorted_patterns[t] = cfg
                
                # Pass 1: Exact matches for ALL columns
                unmatched_cols = []
                for c in cols:
                    c_lower = c.lower().strip()
                    matched = False
                    for type_name, config in sorted_patterns.items():
                        for pattern in config["patterns"]:
                            if c_lower == pattern.lower():
                                if type_to_rdb.get(type_name) not in col_map:
                                    col_map[type_to_rdb.get(type_name)] = c
                                    matched = True
                                elif col_map[type_to_rdb.get(type_name)] != c:
                                    # Prioritize explicitly named DB columns (actno > bank)
                                    if "actno" in c_lower or "dpstr" in c_lower:
                                        col_map[type_to_rdb.get(type_name)] = c
                                break
                        if matched: break
                    
                    if not matched:
                        unmatched_cols.append(c)
                
                # Pass 2: Substring matches for remaining columns
                for c in unmatched_cols:
                    c_lower = c.lower().strip()
                    matched = False
                    for type_name, config in sorted_patterns.items():
                        for pattern in config["patterns"]:
                            # Avoid 'se' randomly matching 'sender' by imposing a length check
                            if len(c_lower) > 2 and (pattern.lower() in c_lower or c_lower in pattern.lower()):
                                if type_to_rdb.get(type_name) not in col_map:
                                    col_map[type_to_rdb.get(type_name)] = c
                                    matched = True
                                    break
                        if matched: break
            
            logger.info(f"   [매핑 V2] {col_map}")
            
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
                
                # P1 확장 컬럼 추출
                msg_content = str(row.get(col_map.get('message', ''), '')).strip()
                org_name = str(row.get(col_map.get('org', ''), '')).strip()
                
                # P2 확장 컬럼 추출
                vehicle_val = str(row.get(col_map.get('vehicle', ''), '')).strip()
                url_val = str(row.get(col_map.get('site', ''), '')).strip()
                file_val = str(row.get(col_map.get('file', ''), '')).strip()
                lat_val = str(row.get(col_map.get('lat', ''), '')).strip()
                lng_val = str(row.get(col_map.get('lng', ''), '')).strip()

                # 1. 사건 마스터 (TB_INCDNT_MST) — DDL 8컬럼 모두 적재
                if case_val:
                    cur.execute("""
                        INSERT INTO TB_INCDNT_MST (INCDNT_NO, INCDNT_NM, INCDNT_TYP_CD, OCCRN_DT, INCDNT_SMRY_CN)
                        VALUES (%s, %s, %s, NULLIF(%s, '')::timestamp, %s)
                        ON CONFLICT (INCDNT_NO) DO UPDATE SET
                            INCDNT_NM = COALESCE(EXCLUDED.INCDNT_NM, TB_INCDNT_MST.INCDNT_NM),
                            INCDNT_TYP_CD = COALESCE(EXCLUDED.INCDNT_TYP_CD, TB_INCDNT_MST.INCDNT_TYP_CD),
                            INCDNT_SMRY_CN = COALESCE(EXCLUDED.INCDNT_SMRY_CN, TB_INCDNT_MST.INCDNT_SMRY_CN)
                    """, (case_val, crime_val or f"사건_{case_val}", crime_val[:6] if crime_val else None, date_val, crime_val))
                    if cur.rowcount > 0: count_stats['cases'] += 1

                # 2. 사람/신원 (TB_PRSN) — DDL 5컬럼 적재 (RRNO은 CSV에 없으므로 NULL)
                if person_id:
                    # PRSN_SE_CD 추론: suspect 키워드면 '01'(피의자), 아니면 '99'(기타)
                    prsn_se = '01' if 'suspect' in col_map else '99'
                    cur.execute("""
                        INSERT INTO TB_PRSN (PRSN_ID, KORN_FLNM, PRSN_SE_CD, RMK_CN)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (PRSN_ID) DO UPDATE SET 
                            KORN_FLNM = COALESCE(EXCLUDED.KORN_FLNM, TB_PRSN.KORN_FLNM),
                            PRSN_SE_CD = COALESCE(EXCLUDED.PRSN_SE_CD, TB_PRSN.PRSN_SE_CD),
                            RMK_CN = COALESCE(EXCLUDED.RMK_CN, TB_PRSN.RMK_CN)
                    """, (person_id, name_val or person_id, prsn_se, nickname_val))
                    if cur.rowcount > 0: count_stats['suspects'] += 1

                # 3. 금융 계좌 (TB_FIN_BACNT) — DDL 6컬럼 (DPSTR_NM 추가)
                def insert_account(actno, holder_name=''):
                    if not actno: return
                    cur.execute("""
                        INSERT INTO TB_FIN_BACNT (BACNT_NO, BANK_CD, BANK_NM, DPSTR_NM) 
                        VALUES (%s, '999', '미상은행', NULLIF(%s, '')) 
                        ON CONFLICT (BACNT_NO, BANK_CD) DO UPDATE SET
                            DPSTR_NM = COALESCE(EXCLUDED.DPSTR_NM, TB_FIN_BACNT.DPSTR_NM)
                    """, (actno, holder_name))
                
                insert_account(account_val, name_val)
                insert_account(sender_val)
                insert_account(receiver_val)
                if account_val or sender_val or receiver_val: count_stats['accounts'] += 1

                # 4. 이체 내역 (TB_FIN_BACNT_DLNG) — DDL 11컬럼 (DLNG_SE_CD, TRRC_PSNNM 추가)
                real_sender = sender_val if sender_val else (account_val if receiver_val else None)
                real_receiver = receiver_val if receiver_val else (account_val if sender_val else None)
                if real_sender and real_receiver:
                    dlng_se = '03' if real_sender and real_receiver else '01'  # 03=이체, 01=입금
                    cur.execute("""
                        INSERT INTO TB_FIN_BACNT_DLNG (DLNG_SN, BACNT_NO, BANK_CD, DLNG_DT, DLNG_SE_CD, DLNG_AMT, TRRC_PSNNM, TRRC_BACNT_NO)
                        VALUES (%s, %s, '999', NULLIF(%s, '')::timestamp, %s, %s, NULLIF(%s, ''), %s)
                        ON CONFLICT (DLNG_SN) DO NOTHING
                    """, (gen_sn(), real_sender, date_val, dlng_se, amount_val, name_val, real_receiver))
                    count_stats['transfers'] += 1

                # 5. 전화번호 (TB_TELNO_MST) — DDL 3컬럼 (TELCO_NM, JOIN_TYP_CD 추가)
                def insert_phone(telno):
                    if not telno: return
                    cur.execute("""
                        INSERT INTO TB_TELNO_MST (TELNO, JOIN_TYP_CD) 
                        VALUES (%s, '01')
                        ON CONFLICT (TELNO) DO NOTHING
                    """, (telno,))
                
                insert_phone(phone_val)
                insert_phone(caller_val)
                insert_phone(callee_val)
                if phone_val or caller_val or callee_val: count_stats['phones'] += 1

                # 6. 통화 상세 내역 (TB_TELNO_CALL_DTL) — DDL 8컬럼 (CALL_TYP_CD 추가)
                if caller_val and callee_val:
                    cur.execute("""
                        INSERT INTO TB_TELNO_CALL_DTL (CALL_SN, DSPTCH_TELNO, RCPTN_TELNO, CALL_STRT_DT, CALL_DUR_SEC, CALL_TYP_CD)
                        VALUES (%s, %s, %s, NULLIF(%s, '')::timestamp, %s, '01')
                        ON CONFLICT (CALL_SN) DO NOTHING
                    """, (gen_sn(), caller_val, callee_val, date_val, duration_val))
                    count_stats['calls'] += 1

                # 7. 접속 IP 이력 (TB_SYS_LGN_EVT) — DDL 5컬럼 (LGN_RESULT_CD 추가)
                if ip_val:
                    dummy_user = person_id if person_id else "UNKNOWN_USER"
                    cur.execute("""
                        INSERT INTO TB_SYS_LGN_EVT (LGN_EVT_SN, USER_ID, CNNT_IP_ADDR, LGN_DT, LGN_RESULT_CD)
                        VALUES (%s, %s, %s, NULLIF(%s, '')::timestamp, 'S')
                        ON CONFLICT (LGN_EVT_SN) DO NOTHING
                    """, (gen_sn(), dummy_user, ip_val, date_val))
                    count_stats['ips'] += 1

                # 8. 사기 피해 신고 (TB_FRD_VCTM_RPT) — DDL 6컬럼 (DAM_AMT 추가)
                if case_val and (person_id or account_val or phone_val):
                    cur.execute("""
                        INSERT INTO TB_FRD_VCTM_RPT (DCLR_SN, DAM_AMT, DCLR_DT, SUSPCT_TELNO, SUSPCT_BACNT_NO, DAM_CN)
                        VALUES (%s, %s, NULLIF(%s, '')::timestamp, %s, %s, %s)
                        ON CONFLICT (DCLR_SN) DO NOTHING
                    """, (gen_sn(), amount_val, date_val, phone_val, account_val, f"사건참조:{case_val}"))

                # ─── P1 신규 테이블 ───────────────────────────────
                
                # 9. 조직/기관 (TB_INST) — 은행명이 있으면 기관으로 등록
                bank_nm = ''
                if account_val:
                    bank_nm = '미상은행'  # 기본값, 향후 CSV에서 은행명 컬럼 추출
                if org_name:
                    cur.execute("""
                        INSERT INTO TB_INST (INST_ID, INST_NM, INST_SE_CD)
                        VALUES (%s, %s, '99')
                        ON CONFLICT (INST_ID) DO UPDATE SET
                            INST_NM = COALESCE(EXCLUDED.INST_NM, TB_INST.INST_NM)
                    """, (org_name[:20], org_name))
                    count_stats['orgs'] += 1

                # 10. 전화번호 가입정보 (TB_TELNO_JOIN) — 전화번호 + 인물 연결
                join_name = name_val or person_id or nickname_val
                if phone_val and join_name:
                    cur.execute("""
                        INSERT INTO TB_TELNO_JOIN (JOIN_SN, TELNO, JOIN_PSNNM)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (JOIN_SN) DO NOTHING
                    """, (gen_sn(), phone_val, join_name))
                    count_stats['joins'] += 1

                # 11. 문자 메시지 (TB_TELNO_SMS_MSG) — 발신/수신 + 내용
                if msg_content and (caller_val or phone_val) and (callee_val or phone_val):
                    sms_sender = caller_val or phone_val
                    sms_receiver = callee_val or phone_val
                    if sms_sender != sms_receiver:  # 자기 자신에게 보내지 않은 경우만
                        cur.execute("""
                            INSERT INTO TB_TELNO_SMS_MSG (SMS_SN, DSPTCH_TELNO, RCPTN_TELNO, DSPTCH_DT, MSG_CN)
                            VALUES (%s, %s, %s, NULLIF(%s, '')::timestamp, %s)
                            ON CONFLICT (SMS_SN) DO NOTHING
                        """, (gen_sn(), sms_sender, sms_receiver, date_val, msg_content[:4000]))
                        count_stats['sms'] += 1

                # 12. 메신저 대화 (TB_CHAT_MSG) — 닉네임 기반 채팅
                if msg_content and nickname_val:
                    cur.execute("""
                        INSERT INTO TB_CHAT_MSG (CHAT_SN, DSPTCH_USER_ID, MSG_CN, DSPTCH_DT, APP_NM)
                        VALUES (%s, %s, %s, NULLIF(%s, '')::timestamp, '미상')
                        ON CONFLICT (CHAT_SN) DO NOTHING
                    """, (gen_sn(), nickname_val, msg_content, date_val))
                    count_stats['chats'] += 1

                # ─── P2 신규 테이블 ───────────────────────────────

                # 13. 기지국 위치 이벤트 (TB_GEO_MBL_LOC_EVT)
                if lat_val and lng_val and phone_val:
                    try:
                        lat_f = float(lat_val)
                        lng_f = float(lng_val)
                        cur.execute("""
                            INSERT INTO TB_GEO_MBL_LOC_EVT (LOC_EVT_SN, TELNO, BSST_LAT, BSST_LOT, OCCRN_DT)
                            VALUES (%s, %s, %s, %s, NULLIF(%s, '')::timestamp)
                            ON CONFLICT (LOC_EVT_SN) DO NOTHING
                        """, (gen_sn(), phone_val, lat_f, lng_f, date_val))
                        count_stats['locations'] += 1
                    except: pass

                # 14. 차량 마스터 (TB_VHCL_MST)
                if vehicle_val:
                    cur.execute("""
                        INSERT INTO TB_VHCL_MST (VHCLNO, OWNR_NM)
                        VALUES (%s, NULLIF(%s, ''))
                        ON CONFLICT (VHCLNO) DO UPDATE SET
                            OWNR_NM = COALESCE(EXCLUDED.OWNR_NM, TB_VHCL_MST.OWNR_NM)
                    """, (vehicle_val, name_val))
                    count_stats['vehicles'] += 1

                    # 15. 차량 LPR 인식 (TB_VHCL_LPR_EVT) — 위치정보가 있을 때
                    if lat_val and lng_val:
                        try:
                            cur.execute("""
                                INSERT INTO TB_VHCL_LPR_EVT (RCGN_SN, VHCLNO, RCGN_DT, LAT, LOT)
                                VALUES (%s, %s, NULLIF(%s, '')::timestamp, %s, %s)
                                ON CONFLICT (RCGN_SN) DO NOTHING
                            """, (gen_sn(), vehicle_val, date_val, float(lat_val), float(lng_val)))
                            count_stats['lpr'] += 1
                        except: pass

                # 16. 웹 도메인 (TB_WEB_DMN) + URL (TB_WEB_URL)
                if url_val:
                    # 도메인 추출
                    domain = url_val.split('/')[2] if url_val.startswith('http') and len(url_val.split('/')) > 2 else url_val.split('/')[0] if '/' in url_val else url_val
                    domain = domain[:200]
                    cur.execute("""
                        INSERT INTO TB_WEB_DMN (DMN_ADDR)
                        VALUES (%s)
                        ON CONFLICT (DMN_ADDR) DO NOTHING
                    """, (domain,))
                    count_stats['domains'] += 1

                    cur.execute("""
                        INSERT INTO TB_WEB_URL (URL_ADDR, DMN_ADDR)
                        VALUES (%s, %s)
                        ON CONFLICT (URL_ADDR) DO NOTHING
                    """, (url_val[:2000], domain))
                    count_stats['urls'] += 1

                # 17. 디지털 파일 (TB_DGTL_FILE_INVNT)
                if file_val:
                    import hashlib
                    file_hash = hashlib.sha256(file_val.encode()).hexdigest()[:64]
                    ext = file_val.rsplit('.', 1)[-1] if '.' in file_val else ''
                    cur.execute("""
                        INSERT INTO TB_DGTL_FILE_INVNT (FILE_SN, FILE_NM, FILE_EXTSN_NM, HASH_VAL)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (FILE_SN) DO NOTHING
                    """, (gen_sn(), file_val[:300], ext[:10], file_hash))
                    count_stats['files'] += 1

            conn.commit()
            logger.info(f"✅ RDB_V2 적재 완료: {count_stats}")
            return True, count_stats

        except Exception as e:
            conn.rollback()
            logger.error(f"❌ RDB_V2 적재 오류: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
        finally:
            cur.close()
            conn.close()
