"""
RDB → GDB 온톨로지 기반 변환 서비스

KICS 4-Layer 온톨로지 모델에 따라 RDB 데이터를 그래프로 변환합니다:
  Layer 1 (Case)     → vt_case
  Layer 2 (Actor)    → vt_psn  
  Layer 3 (Action)   → vt_transfer, vt_call
  Layer 4 (Evidence) → vt_bacnt, vt_telno, vt_ip
"""
import psycopg2
import json
import traceback
import logging
from flask import current_app
from app.database import safe_set_graph_path
from app.services.ontology_service import KICSCrimeDomainOntology, OntologyEnricher

logger = logging.getLogger(__name__)

class RdbToGraphService:
    @staticmethod
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
            logger.error(f"❌ DB 연결 실패: {e}")
            return None, None

    @staticmethod
    def get_conversion_preview():
        """변환 전 미리보기 — 각 RDB 테이블 레코드 수 조회"""
        conn, cur = RdbToGraphService.get_db_connection()
        if not conn:
            return None
        
        tables = [
            ('TB_INCDNT_MST', 'vt_case', '사건'),
            ('TB_PRSN', 'vt_psn', '인물'),
            ('TB_INST', 'vt_org', '조직'),
            ('TB_FIN_BACNT', 'vt_bacnt', '계좌'),
            ('TB_FIN_BACNT_DLNG', 'vt_transfer', '이체'),
            ('TB_TELNO_MST', 'vt_telno', '전화번호'),
            ('TB_TELNO_CALL_DTL', 'vt_call', '통화'),
            ('TB_TELNO_SMS_MSG', 'vt_msg', 'SMS'),
            ('TB_TELNO_JOIN', '—', '가입정보'),
            ('TB_CHAT_MSG', 'vt_msg', '채팅'),
            ('TB_SYS_LGN_EVT', 'vt_ip', 'IP'),
            ('TB_FRD_VCTM_RPT', '—', '사기신고'),
            ('TB_GEO_MBL_LOC_EVT', 'vt_loc_evt', '위치'),
            ('TB_VHCL_MST', 'vt_vhcl', '차량'),
            ('TB_VHCL_LPR_EVT', 'vt_lpr_evt', 'LPR'),
            ('TB_WEB_DMN', 'vt_site', '도메인'),
            ('TB_DGTL_FILE_INVNT', 'vt_file', '파일'),
        ]
        
        preview = []
        try:
            for tbl, label, desc in tables:
                try:
                    cur.execute(f"SELECT count(*) FROM {tbl}")
                    cnt = cur.fetchone()[0]
                    preview.append({'table': tbl, 'graph_label': label, 'description': desc, 'count': cnt})
                except:
                    conn.rollback()
                    preview.append({'table': tbl, 'graph_label': label, 'description': desc, 'count': 0})
            return preview
        except Exception as e:
            logger.error(f"미리보기 오류: {e}")
            return None
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def transfer_data(graph_name="test_ai01"):
        """
        RDB V2(27개 테이블) 데이터를 KICS 온톨로지 기반으로 GDB(AgensGraph)에 변환 적재
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 [RDB → GDB] V2 온톨로지 기반 변환 시작")
        logger.info(f"   Graph: {graph_name}")
        logger.info(f"{'='*60}")

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
            return str(val).replace("'", "").replace("\\", "").replace('"', '').strip()

        try:
            # --- 1. 그래프 설정 ---
            try:
                safe_set_graph_path(cur, graph_name)
                conn.commit()
            except:
                conn.rollback()
                try:
                    cur.execute(f"CREATE GRAPH IF NOT EXISTS {graph_name}")
                    conn.commit()
                    safe_set_graph_path(cur, graph_name)
                    conn.commit()
                    logger.info(f"  ✓ 새 그래프 '{graph_name}' 생성됨")
                except Exception as ge:
                    conn.rollback()
                    raise Exception(f"그래프 '{graph_name}' 설정 실패: {ge}")

            # --- 2. 라벨 생성 ---
            vertex_labels = ['vt_case', 'vt_psn', 'vt_bacnt', 'vt_telno', 'vt_ip', 'vt_event', 
                             'vt_transfer', 'vt_call', 'vt_loc_evt', 'vt_vhcl',
                             'vt_org', 'vt_msg', 'vt_atm',
                             'vt_lpr_evt', 'vt_site', 'vt_file']  # P2 추가
            edge_labels = [
                'involves', 'eg_used_account', 'eg_used_phone', 'eg_used_ip',
                'has_account', 'owns_phone', 'used_ip', 'linked_to',
                'from_account', 'to_account', 'caller', 'callee', 'contacted',
                'sent_msg', 'received_msg',
                'owns_vehicle', 'located_at', 'detected_at', 'contains_file',
                'related_case', 'belongs_to', 'resolved_to', 'works_at'  # Enhancement
            ]
            
            for vl in vertex_labels:
                try: cur.execute(f"CREATE VLABEL IF NOT EXISTS {vl}"); conn.commit()
                except: conn.rollback(); safe_set_graph_path(cur, graph_name)
            
            for el in edge_labels:
                try: cur.execute(f"CREATE ELABEL IF NOT EXISTS {el}"); conn.commit()
                except: conn.rollback(); safe_set_graph_path(cur, graph_name)

            # --- 3. 노드 적재 (TB_ 테이블 병합) ---
            logger.info(f"\n📦 Phase 1: V2 노드 변환")
            
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

            # 3-3. Account (TB_FIN_BACNT) — ATM/현금인출은 vt_atm으로 분류
            cur.execute("SELECT BACNT_NO, BANK_CD, BANK_NM FROM TB_FIN_BACNT")
            rows = cur.fetchall()
            for r in rows:
                try:
                    actno, bcode, bname = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                    is_atm = actno.upper().startswith('ATM') or actno == '현금인출'
                    if is_atm:
                        # ATM ID에서 위치 정보 파싱 (예: ATM-부산002 → 부산, 002)
                        import re
                        loc_match = re.search(r'[가-힣]+', actno)
                        no_match = re.search(r'(\d+)$', actno)
                        atm_loc = loc_match.group() if loc_match else '미상'
                        atm_no = no_match.group() if no_match else ''
                        display_name = f"{atm_loc} ATM {atm_no}".strip() if actno != '현금인출' else '현금인출'
                        props = f"{{atm_id: '{actno}', location: '{atm_loc}', atm_no: '{atm_no}', name: '{display_name}', type: 'ATM'}}"
                        cur.execute(f"MERGE (n:vt_atm {{atm_id: '{actno}'}}) SET n = {props}")
                    else:
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

            logger.info(f"\n🔗 Phase 2: V2 액션/이벤트 및 엣지 변환")
            
            # 4-1. 이체 (TB_FIN_BACNT_DLNG) -> Action Node & Edges
            cur.execute("SELECT DLNG_SN, BACNT_NO, DLNG_DT, DLNG_AMT, TRRC_BACNT_NO, DLNG_SE_CD FROM TB_FIN_BACNT_DLNG")
            rows = cur.fetchall()
            for r in rows:
                try:
                    eid, base_act, dt, amt, other_act, se_cd = safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3]), safe_str(r[4]), safe_str(r[5])
                    props = f"{{event_id: '{eid}', event_type: 'transfer', amount: '{amt}', timestamp: '{dt}', type: '이체'}}"
                    cur.execute(f"MERGE (n:vt_transfer {{event_id: '{eid}'}}) SET n = {props}")
                    stats["nodes"] += 1; stats["transfers"] += 1
                    
                    # 01(입금)이면 돈이 상대(TRRC)에서 기준(BACNT)으로 들어왔음을 의미. 02(출금)은 그 반대.
                    sender = other_act if se_cd == '01' else base_act
                    receiver = base_act if se_cd == '01' else other_act
                    
                    if sender:
                        is_atm = sender.upper().startswith('ATM') or sender == '현금인출'
                        if is_atm:
                            cur.execute(f"MATCH (n:vt_transfer {{event_id: '{eid}'}}), (a:vt_atm {{atm_id: '{sender}'}}) MERGE (a)-[r:from_account]->(n)")
                        else:
                            cur.execute(f"MATCH (n:vt_transfer {{event_id: '{eid}'}}), (a:vt_bacnt {{actno: '{sender}'}}) MERGE (a)-[r:from_account]->(n)")
                        stats["edges"] += 1
                        
                    if receiver:
                        is_atm = receiver.upper().startswith('ATM') or receiver == '현금인출'
                        if is_atm:
                            cur.execute(f"MATCH (n:vt_transfer {{event_id: '{eid}'}}), (a:vt_atm {{atm_id: '{receiver}'}}) MERGE (n)-[r:to_account]->(a)")
                        else:
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
                        cur.execute(f"MATCH (n:vt_call {{event_id: '{eid}'}}), (p:vt_telno {{telno: '{caller}'}}) MERGE (p)-[r:caller]->(n)")
                        stats["edges"] += 1
                    if callee:
                        cur.execute(f"MATCH (n:vt_call {{event_id: '{eid}'}}), (p:vt_telno {{telno: '{callee}'}}) MERGE (n)-[r:callee]->(p)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 4-3. 사기 신고 (TB_FRD_VCTM_RPT) - Case to Evidence Edge 생성
            # CSV 적재 시 DAM_CN 에 '사건참조:INCDNT_NO' 형태로 넣은 것을 파싱하여 조인
            cur.execute("""
                SELECT R.DCLR_SN, substring(R.DAM_CN from '사건참조:(.*)'), R.SUSPCT_BACNT_NO, R.SUSPCT_TELNO 
                FROM TB_FRD_VCTM_RPT R
                WHERE R.DAM_CN LIKE '사건참조:%'
            """)
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
            cur.execute("""
                SELECT P.PRSN_ID, R.SUSPCT_BACNT_NO, R.SUSPCT_TELNO
                FROM TB_PRSN P, TB_FRD_VCTM_RPT R 
                WHERE R.DAM_CN LIKE '사건참조:%'
                LIMIT 1000
            """) # 매우 간단화된 룰 
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

            # ─── P1 확장: Phase 3 ───────────────────────────────
            logger.info(f"\n🔗 Phase 3: P1 도메인 확장 (조직/메시지/소유관계)")

            # 5-1. 조직/기관 (TB_INST) → vt_org
            cur.execute("SELECT INST_ID, INST_NM, INST_SE_CD FROM TB_INST")
            rows = cur.fetchall()
            for r in rows:
                try:
                    oid, oname, otype = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                    props = f"{{org_id: '{oid}', org_name: '{oname}', org_type: '{otype}', type: '조직'}}"
                    cur.execute(f"MERGE (n:vt_org {{org_id: '{oid}'}}) SET n = {props}")
                    stats["nodes"] += 1
                except: pass
            conn.commit()

            # 5-2. SMS 메시지 (TB_TELNO_SMS_MSG) → vt_msg + 발신/수신 엣지
            cur.execute("SELECT SMS_SN, DSPTCH_TELNO, RCPTN_TELNO, DSPTCH_DT, MSG_CN FROM TB_TELNO_SMS_MSG")
            rows = cur.fetchall()
            for r in rows:
                try:
                    eid, sender, receiver, dt, content = safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3]), safe_str(r[4])
                    summary = content[:50] if content else ''
                    props = f"{{event_id: '{eid}', event_type: 'sms', timestamp: '{dt}', summary: '{summary}', type: '문자'}}"
                    cur.execute(f"MERGE (n:vt_msg {{event_id: '{eid}'}}) SET n = {props}")
                    stats["nodes"] += 1
                    
                    if sender:
                        cur.execute(f"MATCH (n:vt_msg {{event_id: '{eid}'}}), (p:vt_telno {{telno: '{sender}'}}) MERGE (p)-[r:sent_msg]->(n)")
                        stats["edges"] += 1
                    if receiver:
                        cur.execute(f"MATCH (n:vt_msg {{event_id: '{eid}'}}), (p:vt_telno {{telno: '{receiver}'}}) MERGE (n)-[r:received_msg]->(p)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 5-3. involves 엣지 (vt_case → vt_psn) — 사건·인물 직접 연결
            # TB_INCDNT_PRSN 조인 테이블 기반 (tbl_eg_case_prsn.csv에서 적재)
            try:
                cur.execute("""
                    SELECT IP.INCDNT_NO, IP.PRSN_ID, IP.ROLE_CD
                    FROM TB_INCDNT_PRSN IP
                    JOIN TB_INCDNT_MST M ON M.INCDNT_NO = IP.INCDNT_NO
                    JOIN TB_PRSN P ON P.PRSN_ID = IP.PRSN_ID
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        case_no, pid, role = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                        if case_no and pid:
                            cur.execute(f"MATCH (c:vt_case {{flnm: '{case_no}'}}), (p:vt_psn {{id: '{pid}'}}) MERGE (c)-[r:involves {{role: '{role}'}}]->(p)")
                            stats["edges"] += 1
                    except: pass
                conn.commit()
            except:
                conn.rollback()  # TB_INCDNT_PRSN 없으면 무시

            # 5-4. owns_phone 강화 (TB_TELNO_JOIN 기반, 가입자명↔인물 조인)
            cur.execute("""
                SELECT J.TELNO, P.PRSN_ID
                FROM TB_TELNO_JOIN J
                JOIN TB_PRSN P ON P.KORN_FLNM = J.JOIN_PSNNM
            """)
            rows = cur.fetchall()
            for r in rows:
                try:
                    telno, pid = safe_str(r[0]), safe_str(r[1])
                    if telno and pid:
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid}'}}), (t:vt_telno {{telno: '{telno}'}}) MERGE (p)-[:owns_phone]->(t)")
                        stats["edges"] += 1; stats["relations"] += 1
                except: pass
            conn.commit()

            # 5-5. has_account 강화 (TB_FIN_BACNT.DPSTR_NM ↔ TB_PRSN.KORN_FLNM 조인)
            cur.execute("""
                SELECT B.BACNT_NO, P.PRSN_ID
                FROM TB_FIN_BACNT B
                JOIN TB_PRSN P ON P.KORN_FLNM = B.DPSTR_NM
                WHERE B.DPSTR_NM IS NOT NULL AND B.DPSTR_NM != ''
            """)
            rows = cur.fetchall()
            for r in rows:
                try:
                    actno, pid = safe_str(r[0]), safe_str(r[1])
                    if actno and pid:
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid}'}}), (a:vt_bacnt {{actno: '{actno}'}}) MERGE (p)-[:has_account]->(a)")
                        stats["edges"] += 1; stats["relations"] += 1
                except: pass
            conn.commit()

            # 5-6. used_ip (TB_SYS_LGN_EVT.USER_ID ↔ TB_PRSN 조인 → 인물-IP 연결)
            cur.execute("""
                SELECT DISTINCT E.CNNT_IP_ADDR, P.PRSN_ID
                FROM TB_SYS_LGN_EVT E
                JOIN TB_PRSN P ON P.KORN_FLNM = E.USER_ID
                WHERE E.CNNT_IP_ADDR IS NOT NULL AND E.CNNT_IP_ADDR != ''
            """)
            rows = cur.fetchall()
            for r in rows:
                try:
                    ip_addr, pid = safe_str(r[0]), safe_str(r[1])
                    if ip_addr and pid:
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid}'}}), (i:vt_ip {{ip_addr: '{ip_addr}'}}) MERGE (p)-[:used_ip]->(i)")
                        stats["edges"] += 1; stats["relations"] += 1
                except: pass
            conn.commit()

            # ─── P2 확장: Phase 4 ───────────────────────────────
            logger.info(f"\n🌐 Phase 4: P2 위치/차량/웹 도메인")

            # 6-1. 차량 (TB_VHCL_MST) → vt_vhcl + owns_vehicle 엣지
            cur.execute("SELECT VHCLNO, CARMDL_NM, OWNR_NM FROM TB_VHCL_MST")
            rows = cur.fetchall()
            for r in rows:
                try:
                    vno, model, owner = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                    props = f"{{vhclno: '{vno}', car_model: '{model}', owner_name: '{owner}', type: '차량'}}"
                    cur.execute(f"MERGE (n:vt_vhcl {{vhclno: '{vno}'}}) SET n = {props}")
                    stats["nodes"] += 1
                    # owns_vehicle: 소유자명 ↔ 인물 조인
                    if owner:
                        cur.execute(f"MATCH (p:vt_psn {{name: '{owner}'}}), (v:vt_vhcl {{vhclno: '{vno}'}}) MERGE (p)-[:owns_vehicle]->(v)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 6-2. 기지국 위치 (TB_GEO_MBL_LOC_EVT) → vt_loc_evt + located_at 엣지
            cur.execute("SELECT LOC_EVT_SN, TELNO, BSST_LAT, BSST_LOT, OCCRN_DT, EVT_TYP_NM FROM TB_GEO_MBL_LOC_EVT")
            rows = cur.fetchall()
            for r in rows:
                try:
                    eid, telno = safe_str(r[0]), safe_str(r[1])
                    lat, lng = safe_str(r[2]), safe_str(r[3])
                    dt, evt_type = safe_str(r[4]), safe_str(r[5])
                    props = f"{{event_id: '{eid}', lat: '{lat}', lng: '{lng}', timestamp: '{dt}', event_type: '{evt_type}', type: '위치'}}"
                    cur.execute(f"MERGE (n:vt_loc_evt {{event_id: '{eid}'}}) SET n = {props}")
                    stats["nodes"] += 1
                    if telno:
                        cur.execute(f"MATCH (t:vt_telno {{telno: '{telno}'}}), (l:vt_loc_evt {{event_id: '{eid}'}}) MERGE (t)-[:located_at]->(l)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 6-3. LPR 인식 (TB_VHCL_LPR_EVT) → vt_lpr_evt + detected_at 엣지
            cur.execute("SELECT RCGN_SN, VHCLNO, RCGN_DT, LAT, LOT, INST_LOC_NM FROM TB_VHCL_LPR_EVT")
            rows = cur.fetchall()
            for r in rows:
                try:
                    eid, vno = safe_str(r[0]), safe_str(r[1])
                    dt, lat, lng = safe_str(r[2]), safe_str(r[3]), safe_str(r[4])
                    loc_nm = safe_str(r[5])
                    props = f"{{event_id: '{eid}', lat: '{lat}', lng: '{lng}', timestamp: '{dt}', location: '{loc_nm}', type: 'LPR'}}"
                    cur.execute(f"MERGE (n:vt_lpr_evt {{event_id: '{eid}'}}) SET n = {props}")
                    stats["nodes"] += 1
                    if vno:
                        cur.execute(f"MATCH (v:vt_vhcl {{vhclno: '{vno}'}}), (l:vt_lpr_evt {{event_id: '{eid}'}}) MERGE (v)-[:detected_at]->(l)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 6-4. 웹 도메인 (TB_WEB_DMN) → vt_site
            cur.execute("SELECT DMN_ADDR, IP_ADDR FROM TB_WEB_DMN")
            rows = cur.fetchall()
            for r in rows:
                try:
                    dmn, ip = safe_str(r[0]), safe_str(r[1])
                    props = f"{{domain: '{dmn}', ip_addr: '{ip}', type: '사이트'}}"
                    cur.execute(f"MERGE (n:vt_site {{domain: '{dmn}'}}) SET n = {props}")
                    stats["nodes"] += 1
                except: pass
            conn.commit()

            # 6-5. 디지털 파일 (TB_DGTL_FILE_INVNT) → vt_file
            cur.execute("SELECT FILE_SN, FILE_NM, FILE_EXTSN_NM, HASH_VAL FROM TB_DGTL_FILE_INVNT")
            rows = cur.fetchall()
            for r in rows:
                try:
                    fid, fname, fext, fhash = safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3])
                    props = f"{{file_id: '{fid}', filename: '{fname}', extension: '{fext}', hash: '{fhash}', type: '파일'}}"
                    cur.execute(f"MERGE (n:vt_file {{file_id: '{fid}'}}) SET n = {props}")
                    stats["nodes"] += 1
                except: pass
            conn.commit()

            # ─── Enhancement: Phase 5 — 자동 추론 엣지 ───────────────
            logger.info(f"\n🧠 Phase 5: 자동 추론 엣지 (교차 도메인)")

            # 7-1. related_case: 동일 증거(계좌/전화) 공유 사건 연결
            cur.execute("""
                SELECT DISTINCT c1.flnm, c2.flnm
                FROM (
                    SELECT substring(R1.DAM_CN from '사건참조:(.*)') as flnm, R1.SUSPCT_BACNT_NO as evidence
                    FROM TB_FRD_VCTM_RPT R1 WHERE R1.SUSPCT_BACNT_NO IS NOT NULL AND R1.SUSPCT_BACNT_NO != ''
                    UNION
                    SELECT substring(R2.DAM_CN from '사건참조:(.*)'), R2.SUSPCT_TELNO
                    FROM TB_FRD_VCTM_RPT R2 WHERE R2.SUSPCT_TELNO IS NOT NULL AND R2.SUSPCT_TELNO != ''
                ) c1
                JOIN (
                    SELECT substring(R3.DAM_CN from '사건참조:(.*)') as flnm, R3.SUSPCT_BACNT_NO as evidence
                    FROM TB_FRD_VCTM_RPT R3 WHERE R3.SUSPCT_BACNT_NO IS NOT NULL AND R3.SUSPCT_BACNT_NO != ''
                    UNION
                    SELECT substring(R4.DAM_CN from '사건참조:(.*)'), R4.SUSPCT_TELNO
                    FROM TB_FRD_VCTM_RPT R4 WHERE R4.SUSPCT_TELNO IS NOT NULL AND R4.SUSPCT_TELNO != ''
                ) c2 ON c1.evidence = c2.evidence AND c1.flnm != c2.flnm
                LIMIT 500
            """)
            rows = cur.fetchall()
            for r in rows:
                try:
                    case1, case2 = safe_str(r[0]), safe_str(r[1])
                    if case1 and case2:
                        cur.execute(f"MATCH (c1:vt_case {{flnm: '{case1}'}}), (c2:vt_case {{flnm: '{case2}'}}) MERGE (c1)-[:related_case {{confidence: '0.75', reason: 'shared_evidence'}}]->(c2)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 7-2. belongs_to: 계좌 → 기관 연결 (TB_FIN_BACNT.INST_ID)
            cur.execute("""
                SELECT B.BACNT_NO, I.INST_ID
                FROM TB_FIN_BACNT B
                JOIN TB_INST I ON B.INST_ID = I.INST_ID
                WHERE B.INST_ID IS NOT NULL
            """)
            rows = cur.fetchall()
            for r in rows:
                try:
                    actno, inst_id = safe_str(r[0]), safe_str(r[1])
                    if actno and inst_id:
                        cur.execute(f"MATCH (a:vt_bacnt {{actno: '{actno}'}}), (o:vt_org {{org_id: '{inst_id}'}}) MERGE (a)-[:belongs_to]->(o)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 7-3. resolved_to: IP → 도메인 (TB_WEB_DMN.IP_ADDR)
            cur.execute("""
                SELECT D.IP_ADDR, D.DMN_ADDR
                FROM TB_WEB_DMN D
                WHERE D.IP_ADDR IS NOT NULL AND D.IP_ADDR != ''
            """)
            rows = cur.fetchall()
            for r in rows:
                try:
                    ip, dmn = safe_str(r[0]), safe_str(r[1])
                    if ip and dmn:
                        cur.execute(f"MATCH (i:vt_ip {{ip_addr: '{ip}'}}), (s:vt_site {{domain: '{dmn}'}}) MERGE (i)-[:resolved_to]->(s)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            logger.info(f"✅ V2 GDB 변환 완료: {stats}")
            return True, stats

        except Exception as e:
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False, f"V2 ETL 오류: {str(e)}"
        finally:
            cur.close()
            conn.close()
