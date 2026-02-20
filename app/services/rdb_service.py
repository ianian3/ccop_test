import pandas as pd
import psycopg2
from flask import current_app
from datetime import datetime
import uuid

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
            print(f"DB 접속 오류: {e}")
            return None, None

    @staticmethod
    def import_csv_to_rdb(file_path):
        """CSV 파일을 분석하여 RDB 테이블에 적재"""
        print(f"▶ [RDB] CSV 적재 시작: {file_path}")
        
        conn, cur = RDBService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        
        try:
            df = pd.read_csv(file_path).fillna('')
            count_stats = {"cases": 0, "suspects": 0, "accounts": 0, "phones": 0, "relations": 0}
            
            # 컬럼 매핑 추론 (온톨로지 기반 COLUMN_PATTERNS 참조)
            from app.services.ontology_service import KICSCrimeDomainOntology
            cols = df.columns
            col_map = {}
            patterns = KICSCrimeDomainOntology.COLUMN_PATTERNS
            type_to_rdb = KICSCrimeDomainOntology.COLUMN_TYPE_TO_RDB
            
            # 구체적 타입을 먼저 매칭 (caller > phone, sender > account)
            priority_order = ['caller', 'callee', 'sender', 'receiver', 'nickname']
            sorted_patterns = {}
            for t in priority_order:
                if t in patterns:
                    sorted_patterns[t] = patterns[t]
            for t, cfg in patterns.items():
                if t not in sorted_patterns:
                    sorted_patterns[t] = cfg
            
            for c in cols:
                c_lower = c.lower().strip()
                matched = False
                
                # 1단계: 정확한 패턴 매칭
                for type_name, config in sorted_patterns.items():
                    for pattern in config["patterns"]:
                        if c_lower == pattern.lower():
                            rdb_key = type_to_rdb.get(type_name)
                            if rdb_key and rdb_key not in col_map:
                                col_map[rdb_key] = c
                            matched = True
                            break
                    if matched:
                        break
                
                # 2단계: 부분 매칭 (정확 매칭 실패 시)
                if not matched:
                    for type_name, config in sorted_patterns.items():
                        for pattern in config["patterns"]:
                            if pattern.lower() in c_lower or c_lower in pattern.lower():
                                rdb_key = type_to_rdb.get(type_name)
                                if rdb_key and rdb_key not in col_map:
                                    col_map[rdb_key] = c
                                matched = True
                                break
                        if matched:
                            break
            
            print(f"   [매핑] {col_map}")
            
            for _, row in df.iterrows():
                # 1. 사건 적재 (기존 로직)
                case_val = str(row[col_map['case']]).strip() if 'case' in col_map else None
                if case_val:
                    crime_val = str(row.get(col_map.get('crime'), '')).strip()
                    date_val = str(row.get(col_map.get('date'), '')).strip()
                    
                    cur.execute("""
                        INSERT INTO rdb_cases (case_no, crime_name, reg_date)
                        VALUES (%s, %s, NULLIF(%s, '')::date)
                        ON CONFLICT (case_no) DO NOTHING
                    """, (case_val, crime_val, date_val))
                    if cur.rowcount > 0: count_stats['cases'] += 1

                # 2. 피의자/닉네임 적재
                suspect_val = str(row[col_map['suspect']]).strip() if 'suspect' in col_map else None
                nickname_val = str(row[col_map['nickname']]).strip() if 'nickname' in col_map else None
                name_val = str(row[col_map['name']]).strip() if 'name' in col_map else None
                
                # 닉네임이 있으면 피의자로 간주
                person_id = suspect_val or nickname_val
                person_name = name_val or nickname_val or suspect_val
                
                if person_id:
                    cur.execute("""
                        INSERT INTO rdb_suspects (user_id, name, nickname)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (user_id) DO UPDATE SET 
                            name = COALESCE(EXCLUDED.name, rdb_suspects.name),
                            nickname = COALESCE(EXCLUDED.nickname, rdb_suspects.nickname)
                    """, (person_id, person_name, nickname_val or ''))
                    if cur.rowcount > 0: count_stats['suspects'] += 1
                
                # 3. 계좌 적재 (송금/수취 계좌 모두 처리)
                # 메인 계좌
                account_val = str(row[col_map['account']]).strip() if 'account' in col_map else None
                if account_val:
                    cur.execute("INSERT INTO rdb_accounts (actno) VALUES (%s) ON CONFLICT (actno) DO NOTHING", (account_val,))
                # 송금/수취 계좌도 계좌 테이블에 존재해야 함
                sender_val = str(row.get(col_map.get('sender'), '')).strip()
                if sender_val:
                    cur.execute("INSERT INTO rdb_accounts (actno) VALUES (%s) ON CONFLICT (actno) DO NOTHING", (sender_val,))
                receiver_val = str(row.get(col_map.get('receiver'), '')).strip()
                if receiver_val:
                    cur.execute("INSERT INTO rdb_accounts (actno) VALUES (%s) ON CONFLICT (actno) DO NOTHING", (receiver_val,))
                
                if account_val or sender_val or receiver_val: count_stats['accounts'] += 1

                # 4. 전화번호 적재
                phone_val = str(row[col_map['phone']]).strip() if 'phone' in col_map else None
                if phone_val:
                    cur.execute("INSERT INTO rdb_phones (telno) VALUES (%s) ON CONFLICT (telno) DO NOTHING", (phone_val,))
                caller_val = str(row.get(col_map.get('caller'), '')).strip()
                if caller_val:
                    cur.execute("INSERT INTO rdb_phones (telno) VALUES (%s) ON CONFLICT (telno) DO NOTHING", (caller_val,))
                callee_val = str(row.get(col_map.get('callee'), '')).strip()
                if callee_val:
                    cur.execute("INSERT INTO rdb_phones (telno) VALUES (%s) ON CONFLICT (telno) DO NOTHING", (callee_val,))

                if phone_val or caller_val or callee_val: count_stats['phones'] += 1

                # 5. 이체 내역 적재 (Transaction)
                if 'amount' in col_map and (sender_val or receiver_val):
                    amount_Raw = str(row.get(col_map.get('amount'), '0')).replace(',', '')
                    try:
                        amount_val = int(float(amount_Raw))
                    except:
                        amount_val = 0
                    
                    trx_date = str(row.get(col_map.get('date'), datetime.now()))
                    
                    # 송금자가 없으면 본인 계좌(account_val)를 송금자로 가정하거나 NULL
                    real_sender = sender_val if sender_val else (account_val if receiver_val else None)
                    real_receiver = receiver_val if receiver_val else (account_val if sender_val else None)

                    if real_sender or real_receiver:
                        trx_id = f"TRX_{uuid.uuid4().hex[:12]}"
                        cur.execute("""
                            INSERT INTO rdb_transfers (trx_id, amount, trx_date, sender_actno, receiver_actno)
                            VALUES (%s, %s, NULLIF(%s, '')::timestamp, NULLIF(%s, ''), NULLIF(%s, ''))
                            ON CONFLICT (trx_id) DO NOTHING
                        """, (trx_id, amount_val, trx_date, real_sender, real_receiver))
                        count_stats.setdefault('transfers', 0)
                        count_stats['transfers'] += 1

                # 6. 통화 내역 적재 (Call)
                if (caller_val or callee_val):
                    duration_val = 0
                    if 'duration' in col_map:
                        try: duration_val = int(row[col_map['duration']])
                        except: pass
                    
                    call_date = str(row.get(col_map.get('date'), datetime.now()))
                    
                    call_id = f"CALL_{uuid.uuid4().hex[:12]}"
                    cur.execute("""
                        INSERT INTO rdb_calls (call_id, duration, call_date, caller_no, callee_no)
                        VALUES (%s, %s, NULLIF(%s, '')::timestamp, NULLIF(%s, ''), NULLIF(%s, ''))
                        ON CONFLICT (call_id) DO NOTHING
                    """, (call_id, duration_val, call_date, caller_val, callee_val))
                    count_stats.setdefault('calls', 0)
                    count_stats['calls'] += 1

                # 6-1. IP 적재
                ip_val = str(row[col_map['ip']]).strip() if 'ip' in col_map else None
                if ip_val:
                    cur.execute("INSERT INTO rdb_ips (ip_addr) VALUES (%s) ON CONFLICT (ip_addr) DO NOTHING", (ip_val,))
                    count_stats.setdefault('ips', 0)
                    count_stats['ips'] += 1

                # 7. 관계 적재 (온톨로지 기반 교차 연결)
                from app.services.rdb_to_graph_service import RdbToGraphService
                entities = []
                if case_val: entities.append(('case', case_val))
                if person_id: entities.append(('suspect', person_id))
                if account_val: entities.append(('account', account_val))
                if phone_val: entities.append(('phone', phone_val))
                if ip_val: entities.append(('ip', ip_val))
                
                # 온톨로지 매핑에서 관계 타입 자동 결정
                ONTOLOGY_REL_MAP = {}
                for (s, t, r), edge in RdbToGraphService.RELATION_TO_EDGE.items():
                    if (s, t) not in ONTOLOGY_REL_MAP:
                        ONTOLOGY_REL_MAP[(s, t)] = r  # 첫번째 매핑의 rel_type 사용
                
                for i in range(len(entities)):
                    for j in range(i + 1, len(entities)):
                        src_type, src_val = entities[i]
                        tgt_type, tgt_val = entities[j]
                        
                        # 온톨로지 기반 관계 타입 결정
                        rel_type = ONTOLOGY_REL_MAP.get((src_type, tgt_type), 'related_to')
                        
                        cur.execute("""
                            INSERT INTO rdb_relations (source_type, source_value, target_type, target_value, rel_type)
                            VALUES (%s, %s, %s, %s, %s)
                            ON CONFLICT (source_type, source_value, target_type, target_value, rel_type) 
                            DO UPDATE SET weight = rdb_relations.weight + 1
                        """, (src_type, src_val, tgt_type, tgt_val, rel_type))
                        count_stats['relations'] += 1

            conn.commit()
            print(f"✅ RDB 적재 완료: {count_stats}")
            return True, count_stats

        except Exception as e:
            conn.rollback()
            print(f"❌ RDB 적재 오류: {e}")
            import traceback
            traceback.print_exc()
            return False, str(e)
        finally:
            conn.close()
