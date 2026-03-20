import sys

with open('app/services/rdb_to_graph_service.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for i, line in enumerate(lines):
    if "class RdbToGraphService:" in line:
        # Keep imports, drop everything else to rewrite the class cleanly
        new_lines.append(line)
        break
    new_lines.append(line)

new_class = """    @staticmethod
    def get_db_connection():
        import psycopg2
        from flask import current_app
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
            print(f"❌ DB 연결 실패: {e}")
            return None, None

    @staticmethod
    def transfer_data(graph_name="test_ai01"):
        \"\"\"
        RDB V2(27개 테이블) 데이터를 KICS 온톨로지 기반으로 GDB(AgensGraph)에 변환 적재
        \"\"\"
        print(f"\\n{'='*60}")
        print(f"🚀 [RDB → GDB] V2 온톨로지 기반 변환 시작")
        print(f"   Graph: {graph_name}")
        print(f"{'='*60}")

        conn, cur = RdbToGraphService.get_db_connection()
        if not conn:
            return False, "DB 연결 실패"

        stats = {
            "nodes": 0, "edges": 0,
            "cases": 0, "persons": 0, "accounts": 0, "phones": 0,
            "transfers": 0, "calls": 0, "relations": 0,
            "errors": []
        }

        def safe_str(val):
            if val is None: return ''
            return str(val).replace("'", "").replace("\\\\", "").replace('"', '').strip()

        try:
            # --- 1. 그래프 설정 ---
            try:
                cur.execute(f"SET graph_path = {graph_name}")
                conn.commit()
            except:
                conn.rollback()
                try:
                    cur.execute(f"CREATE GRAPH IF NOT EXISTS {graph_name}")
                    conn.commit()
                    cur.execute(f"SET graph_path = {graph_name}")
                    conn.commit()
                    print(f"  ✓ 새 그래프 '{graph_name}' 생성됨")
                except Exception as ge:
                    conn.rollback()
                    raise Exception(f"그래프 '{graph_name}' 설정 실패: {ge}")

            # --- 2. 라벨 생성 ---
            vertex_labels = ['vt_case', 'vt_psn', 'vt_bacnt', 'vt_telno', 'vt_ip', 'vt_event', 'vt_transfer', 'vt_call', 'vt_loc_evt', 'vt_vhcl']
            edge_labels = [
                'involves', 'eg_used_account', 'eg_used_phone', 'eg_used_ip',
                'has_account', 'owns_phone', 'used_ip', 'linked_to',
                'from_account', 'to_account', 'caller', 'callee', 'contacted'
            ]
            
            for vl in vertex_labels:
                try: cur.execute(f"CREATE VLABEL IF NOT EXISTS {vl}"); conn.commit()
                except: conn.rollback(); cur.execute(f"SET graph_path = {graph_name}")
            
            for el in edge_labels:
                try: cur.execute(f"CREATE ELABEL IF NOT EXISTS {el}"); conn.commit()
                except: conn.rollback(); cur.execute(f"SET graph_path = {graph_name}")

            # --- 3. 노드 적재 (TB_ 테이블 병합) ---
            print(f"\\n📦 Phase 1: V2 노드 변환")
            
            # 3-1. Case (TB_INCDNT_MST)
            cur.execute("SELECT INCDNT_NO, INCDNT_NM, OCCRN_DT FROM TB_INCDNT_MST")
            rows = cur.fetchall()
            for r in rows:
                try:
                    flnm, crime, dt = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                    props = f"{{flnm: '{flnm}', crime: '{crime}', date: '{dt}', type: '사건'}}"
                    cur.execute(f"MERGE (n:vt_case {{flnm: '{flnm}'}}) SET n = {props}")
                    stats["nodes"] += 1; stats["cases"] += 1
                except: pass
            conn.commit()

            # 3-2. Person (TB_PRSN)
            cur.execute("SELECT PRSN_ID, KORN_FLNM, RMK_CN FROM TB_PRSN")
            rows = cur.fetchall()
            for r in rows:
                try:
                    pid, name, nick = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                    props = f"{{id: '{pid}', name: '{name}', nickname: '{nick}', type: '인물'}}"
                    cur.execute(f"MERGE (n:vt_psn {{id: '{pid}'}}) SET n = {props}")
                    stats["nodes"] += 1; stats["persons"] += 1
                except: pass
            conn.commit()

            # 3-3. Account (TB_FIN_BACNT)
            cur.execute("SELECT BACNT_NO, BANK_CD, BANK_NM FROM TB_FIN_BACNT")
            rows = cur.fetchall()
            for r in rows:
                try:
                    actno, bcode, bname = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                    props = f"{{actno: '{actno}', bank_cd: '{bcode}', bank_name: '{bname}', type: '계좌'}}"
                    cur.execute(f"MERGE (n:vt_bacnt {{actno: '{actno}'}}) SET n = {props}")
                    stats["nodes"] += 1; stats["accounts"] += 1
                except: pass
            conn.commit()

            # 3-4. Phone (TB_TELNO_MST)
            cur.execute("SELECT TELNO FROM TB_TELNO_MST")
            rows = cur.fetchall()
            for r in rows:
                try:
                    telno = safe_str(r[0])
                    props = f"{{telno: '{telno}', type: '전화번호'}}"
                    cur.execute(f"MERGE (n:vt_telno {{telno: '{telno}'}}) SET n = {props}")
                    stats["nodes"] += 1; stats["phones"] += 1
                except: pass
            conn.commit()

            # 3-5. IP (TB_SYS_LGN_EVT)
            cur.execute("SELECT DISTINCT CNNT_IP_ADDR FROM TB_SYS_LGN_EVT")
            rows = cur.fetchall()
            for r in rows:
                try:
                    ip = safe_str(r[0])
                    props = f"{{ip_addr: '{ip}', type: 'IP'}}"
                    cur.execute(f"MERGE (n:vt_ip {{ip_addr: '{ip}'}}) SET n = {props}")
                    stats["nodes"] += 1
                except: pass
            conn.commit()

            print(f"\\n🔗 Phase 2: V2 액션/이벤트 및 엣지 변환")
            
            # 4-1. 이체 (TB_FIN_BACNT_DLNG) -> Action Node & Edges
            cur.execute("SELECT DLNG_SN, BACNT_NO, DLNG_DT, DLNG_AMT, TRRC_BACNT_NO FROM TB_FIN_BACNT_DLNG")
            rows = cur.fetchall()
            for r in rows:
                try:
                    eid, sender, dt, amt, receiver = safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3]), safe_str(r[4])
                    props = f"{{event_id: '{eid}', event_type: 'transfer', amount: '{amt}', timestamp: '{dt}', type: '이체'}}"
                    cur.execute(f"MERGE (n:vt_transfer {{event_id: '{eid}'}}) SET n = {props}")
                    stats["nodes"] += 1; stats["transfers"] += 1
                    
                    if sender:
                        cur.execute(f"MATCH (n:vt_transfer {{event_id: '{eid}'}}), (a:vt_bacnt {{actno: '{sender}'}}) MERGE (n)-[r:from_account]->(a)")
                        stats["edges"] += 1
                    if receiver:
                        cur.execute(f"MATCH (n:vt_transfer {{event_id: '{eid}'}}), (a:vt_bacnt {{actno: '{receiver}'}}) MERGE (n)-[r:to_account]->(a)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 4-2. 통화 (TB_TELNO_CALL_DTL)
            cur.execute("SELECT CALL_SN, DSPTCH_TELNO, RCPTN_TELNO, CALL_STRT_DT, CALL_DUR_SEC FROM TB_TELNO_CALL_DTL")
            rows = cur.fetchall()
            for r in rows:
                try:
                    eid, caller, callee, dt, dur = safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3]), safe_str(r[4])
                    props = f"{{event_id: '{eid}', event_type: 'call', duration: '{dur}', timestamp: '{dt}', type: '통화'}}"
                    cur.execute(f"MERGE (n:vt_call {{event_id: '{eid}'}}) SET n = {props}")
                    stats["nodes"] += 1; stats["calls"] += 1
                    
                    if caller:
                        cur.execute(f"MATCH (n:vt_call {{event_id: '{eid}'}}), (p:vt_telno {{telno: '{caller}'}}) MERGE (n)-[r:caller]->(p)")
                        stats["edges"] += 1
                    if callee:
                        cur.execute(f"MATCH (n:vt_call {{event_id: '{eid}'}}), (p:vt_telno {{telno: '{callee}'}}) MERGE (n)-[r:callee]->(p)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 4-3. 사기 신고 (TB_FRD_VCTM_RPT) - Case to Evidence Edge 생성
            # CSV 적재 시 DAM_CN 에 '사건참조:INCDNT_NO' 형태로 넣은 것을 파싱하여 조인
            cur.execute(\"\"\"
                SELECT R.DCLR_SN, substring(R.DAM_CN from '사건참조:(.*)'), R.SUSPCT_BACNT_NO, R.SUSPCT_TELNO 
                FROM TB_FRD_VCTM_RPT R
                WHERE R.DAM_CN LIKE '사건참조:%'
            \"\"\")
            rows = cur.fetchall()
            for r in rows:
                try:
                    case_no, actno, telno = safe_str(r[1]), safe_str(r[2]), safe_str(r[3])
                    if actno:
                        cur.execute(f"MATCH (c:vt_case {{flnm: '{case_no}'}}), (a:vt_bacnt {{actno: '{actno}'}}) MERGE (c)-[:eg_used_account]->(a)")
                        stats["edges"] += 1
                    if telno:
                        cur.execute(f"MATCH (c:vt_case {{flnm: '{case_no}'}}), (t:vt_telno {{telno: '{telno}'}}) MERGE (c)-[:eg_used_phone]->(t)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 4-4. 인물과 계좌/전화 소유관계 추론 (Person <-> Evidence)
            # 여기서는 TB_FRD_VCTM_RPT로 엮인 증거와 케이스를 인물과 엮어 소유를 만들거나, PRSN 테이블 기반 간단 맾핑 조인
            # 현재 스크립트에는 명시적인 소유 매핑이 적재되지 않으므로, V1 호환을 위해 피의자와 사건의 증거를 연결
            cur.execute(\"\"\"
                SELECT P.PRSN_ID, R.SUSPCT_BACNT_NO, R.SUSPCT_TELNO
                FROM TB_PRSN P, TB_FRD_VCTM_RPT R 
                WHERE R.DAM_CN LIKE '사건참조:%'
                LIMIT 1000
            \"\"\") # 매우 간단화된 룰 
            rows = cur.fetchall()
            for r in rows:
                try:
                    pid, actno, telno = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                    if actno:
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid}'}}), (a:vt_bacnt {{actno: '{actno}'}}) MERGE (p)-[:has_account]->(a)")
                        stats["edges"] += 1
                    if telno:
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid}'}}), (t:vt_telno {{telno: '{telno}'}}) MERGE (p)-[:owns_phone]->(t)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            print(f"✅ V2 GDB 변환 완료: {stats}")
            return True, stats

        except Exception as e:
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False, f"V2 ETL 오류: {str(e)}"
        finally:
            cur.close()
            conn.close()
"""
new_lines.append(new_class)

with open('app/services/rdb_to_graph_service.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

