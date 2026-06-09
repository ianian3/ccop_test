"""
RDB → GDB 온톨로지 기반 변환 서비스  [v3.5 POLE 6-Layer]

v3.5 POLE 6계층 온톨로지에 따라 RDB(49개 테이블) 데이터를 그래프로 변환합니다:
  Layer 1 (Source)   → vt_src          [TB_DATA_SRC]
  Layer 2 (Case)     → vt_case, vt_petition   [TB_INCDNT_MST, TB_PETTN_MST]
  Layer 3 (Person)   → vt_psn, vt_org         [TB_PRSN, TB_INST]
  Layer 4 (Object)   → vt_bacnt, vt_telno, vt_ip, vt_site, vt_file,
                        vt_id, vt_email, vt_crypto, vt_dev, vt_atm, vt_vhcl
  Layer 5 (Location) → vt_loc          [TB_LOC_MST]
  Layer 6 (Event)    → vt_transfer, vt_call, vt_msg, vt_access, vt_movement
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
            # Source
            ('TB_DATA_SRC',          'vt_src',      '출처'),
            # Case
            ('TB_INCDNT_MST',        'vt_case',     '사건'),
            ('TB_PETTN_MST',         'vt_petition', '진정서'),
            # Person
            ('TB_PRSN',              'vt_psn',      '인물'),
            ('TB_INST',              'vt_org',      '조직'),
            # Object — 기존
            ('TB_FIN_BACNT',         'vt_bacnt',    '계좌'),
            ('TB_TELNO_MST',         'vt_telno',    '전화번호'),
            ('TB_WEB_DMN',           'vt_site',     '도메인'),
            ('TB_DGTL_FILE_INVNT',   'vt_file',     '파일'),
            ('TB_VHCL_MST',          'vt_vhcl',     '차량'),
            # Object — v3.0 신규
            ('TB_DGTL_ID_MST',       'vt_id',       '디지털ID'),
            ('TB_EMAIL_MST',         'vt_email',    '이메일'),
            ('TB_CRYPTO_WALLET_MST', 'vt_crypto',   '가상자산지갑'),
            ('TB_DEV_MST',           'vt_dev',      '기기'),
            ('TB_ATM_MST',           'vt_atm',      'ATM'),
            # Location
            ('TB_LOC_MST',           'vt_loc',      '위치'),
            # Event
            ('TB_FIN_BACNT_DLNG',    'vt_transfer', '이체'),
            ('TB_TELNO_CALL_DTL',    'vt_call',     '통화'),
            ('TB_TELNO_SMS_MSG',     'vt_msg',      'SMS'),
            ('TB_CHAT_MSG',          'vt_msg',      '채팅'),
            ('TB_SYS_LGN_EVT',      'vt_access',   '접속이벤트'),
            ('TB_GEO_MBL_LOC_EVT',  'vt_movement', '기지국(이동)'),
            ('TB_VHCL_LPR_EVT',     'vt_movement', 'LPR(이동)'),
            # 보조
            ('TB_TELNO_JOIN',        '—',           '전화가입정보'),
            ('TB_FRD_VCTM_RPT',     '—',           '사기신고'),
            ('TB_INCDNT_PRSN',      '—',           '사건-인물 조인'),
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
        RDB V3(49개 테이블) 데이터를 POLE 6계층 온톨로지 기반으로 GDB(AgensGraph)에 변환 적재
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 [RDB → GDB] V3.2 POLE 6계층 온톨로지 기반 변환 시작")
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
            vertex_labels = [
                'vt_src', 'vt_case', 'vt_petition',
                'vt_psn', 'vt_org',
                'vt_bacnt', 'vt_crypto', 'vt_ip', 'vt_site', 'vt_file',
                'vt_id', 'vt_email', 'vt_telno', 'vt_vhcl', 'vt_dev', 'vt_atm',
                'vt_loc',
                'vt_transfer', 'vt_call', 'vt_access', 'vt_msg', 'vt_movement',
            ]
            edge_labels = [
                # 역할 엣지 (v3.0 Role-as-Edge)
                'suspect_in', 'victim_in', 'witness_in',
                # 사건 연결 (v3.1)
                'filed_as', 'clusters_with',
                # 엔티티 해소
                'sameAs', 'contradicts',
                # 사칭 (v3.4: used_for + targets 패턴)
                'used_for', 'targets',
                # 신원/소유
                'has_account', 'controls', 'owns_phone', 'owns_device', 'owns_vehicle',
                'uses_id', 'uses_email', 'drives', 'used_ip', 'owns', 'registered_to',
                # 인물 관계 (v3.4 신규)
                'recruits', 'blackmails', 'accomplice_of', 'sameAs', 'contradicts',
                # 운영/인프라 (v3.4 신규)
                'operates', 'hosts', 'resolves_to', 'contains_file', 'located_at',
                # 이체/통화/이동
                'from_account', 'to_account', 'caller', 'callee',
                'sent_msg', 'received_msg', 'recorded_in',
                # 소유/관계
                'related_case', 'belongs_to', 'works_at', 'member_of', 'linked_to',
                # 디지털 접속
                'accessed_from', 'mentions_account',
                # 출처
                'sourced_from',
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
                        props = f"{{account_no: '{actno}', bank_cd: '{bcode}', bank_name: '{bname}', type: '계좌'}}"
                        cur.execute(f"MERGE (n:vt_bacnt {{account_no: '{actno}'}}) SET n = {props}")
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

            # 3-5. IP + 접속이벤트 (TB_SYS_LGN_EVT) → vt_ip MERGE + vt_access 생성 + accessed_from 엣지
            cur.execute("""
                SELECT LGN_SN, CNNT_IP_ADDR, USER_ID, LGN_DT, LGN_RSLT_CD, SVC_NM
                FROM TB_SYS_LGN_EVT
                WHERE CNNT_IP_ADDR IS NOT NULL AND CNNT_IP_ADDR != ''
            """)
            rows = cur.fetchall()
            for r in rows:
                try:
                    lgn_sn, ip = safe_str(r[0]), safe_str(r[1])
                    user_id, dt, rslt, svc = safe_str(r[2]), safe_str(r[3]), safe_str(r[4]), safe_str(r[5])
                    # vt_ip MERGE (IP 노드)
                    cur.execute(f"MERGE (n:vt_ip {{ip_addr: '{ip}'}}) SET n.ip_addr = '{ip}', n.type = 'IP'")
                    stats["nodes"] += 1
                    # vt_access 이벤트 노드 (Bridge Key: lgn_sn)
                    acc_props = (f"{{access_id: 'lgn-{lgn_sn}', lgn_sn: '{lgn_sn}', "
                                 f"user_id: '{user_id}', timestamp: '{dt}', "
                                 f"result_cd: '{rslt}', service_nm: '{svc}', type: '접속'}}")
                    cur.execute(f"MERGE (a:vt_access {{access_id: 'lgn-{lgn_sn}'}}) SET a = {acc_props}")
                    stats["nodes"] += 1
                    # accessed_from: vt_ip → vt_access
                    cur.execute(f"MATCH (i:vt_ip {{ip_addr: '{ip}'}}), (a:vt_access {{access_id: 'lgn-{lgn_sn}'}}) MERGE (i)-[:accessed_from]->(a)")
                    stats["edges"] += 1
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
                            cur.execute(f"MATCH (n:vt_transfer {{event_id: '{eid}'}}), (a:vt_atm {{atm_id: '{sender}'}}) MERGE (a)-[r:from_account]->(n) SET r.evid_grade = 'A', r.src_tier = 1")
                        else:
                            cur.execute(f"MATCH (n:vt_transfer {{event_id: '{eid}'}}), (a:vt_bacnt {{account_no: '{sender}'}}) MERGE (a)-[r:from_account]->(n) SET r.evid_grade = 'A', r.src_tier = 1")
                        stats["edges"] += 1

                    if receiver:
                        is_atm = receiver.upper().startswith('ATM') or receiver == '현금인출'
                        if is_atm:
                            cur.execute(f"MATCH (n:vt_transfer {{event_id: '{eid}'}}), (a:vt_atm {{atm_id: '{receiver}'}}) MERGE (n)-[r:to_account]->(a) SET r.evid_grade = 'A', r.src_tier = 1")
                        else:
                            cur.execute(f"MATCH (n:vt_transfer {{event_id: '{eid}'}}), (a:vt_bacnt {{account_no: '{receiver}'}}) MERGE (n)-[r:to_account]->(a) SET r.evid_grade = 'A', r.src_tier = 1")
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
                        cur.execute(f"MATCH (n:vt_call {{event_id: '{eid}'}}), (p:vt_telno {{telno: '{caller}'}}) MERGE (p)-[r:caller]->(n) SET r.evid_grade = 'A', r.src_tier = 1")
                        stats["edges"] += 1
                    if callee:
                        cur.execute(f"MATCH (n:vt_call {{event_id: '{eid}'}}), (p:vt_telno {{telno: '{callee}'}}) MERGE (n)-[r:callee]->(p) SET r.evid_grade = 'A', r.src_tier = 1")
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
                    # v3.5: eg_used_account/eg_used_phone은 온톨로지에 공식 등록됨
                    # 단, TB_FRD_VCTM_RPT 데이터는 계좌/전화를 인물을 통해 연결
                    # (Case→Person→Account 경로; eg_used_* 직접 엣지는 명시적 증거 테이블에서 생성)
                    if actno:
                        stats["edges"] += 0  # 직접 엣지 생성 안 함
                    if telno:
                        pass  # 직접 엣지 생성 안 함
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
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid}'}}), (a:vt_bacnt {{account_no: '{actno}'}}) MERGE (p)-[r:has_account]->(a) SET r.evid_grade = 'B', r.src_tier = 1")
                        stats["edges"] += 1
                    if telno:
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid}'}}), (t:vt_telno {{telno: '{telno}'}}) MERGE (p)-[r:owns_phone]->(t) SET r.evid_grade = 'B', r.src_tier = 1")
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
                            # v3.2 Role-as-Edge: ROLE_CD → 역할별 엣지 타입
                            role_edge = 'suspect_in' if role == 'SUSPECT' else 'victim_in' if role == 'VICTIM' else 'witness_in' if role == 'WITNESS' else 'witness_in'
                            cur.execute(f"MATCH (c:vt_case {{flnm: '{case_no}'}}), (p:vt_psn {{id: '{pid}'}}) MERGE (p)-[r:{role_edge}]->(c) SET r.evid_grade = 'A', r.src_tier = 1")
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
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid}'}}), (t:vt_telno {{telno: '{telno}'}}) MERGE (p)-[r:owns_phone]->(t) SET r.evid_grade = 'A', r.src_tier = 1")
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
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid}'}}), (a:vt_bacnt {{account_no: '{actno}'}}) MERGE (p)-[r:has_account]->(a) SET r.evid_grade = 'B', r.src_tier = 1")
                        stats["edges"] += 1; stats["relations"] += 1
                except: pass
            conn.commit()

            # 5-6. used_ip + accessed_from (TB_SYS_LGN_EVT.USER_ID ↔ TB_PRSN 조인)
            #      Person → vt_ip (used_ip), Access → vt_ip (accessed_from)
            cur.execute("""
                SELECT DISTINCT E.LGN_SN, E.CNNT_IP_ADDR, P.PRSN_ID
                FROM TB_SYS_LGN_EVT E
                JOIN TB_PRSN P ON P.KORN_FLNM = E.USER_ID
                WHERE E.CNNT_IP_ADDR IS NOT NULL AND E.CNNT_IP_ADDR != ''
            """)
            rows = cur.fetchall()
            for r in rows:
                try:
                    lgn_sn, ip_addr, pid = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                    if ip_addr and pid:
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid}'}}), (i:vt_ip {{ip_addr: '{ip_addr}'}}) MERGE (p)-[:used_ip]->(i)")
                        stats["edges"] += 1; stats["relations"] += 1
                    if lgn_sn and ip_addr:
                        # v3.4: Access→IP 연결은 accessed_from (performed_by 제거)
                        cur.execute(f"MATCH (a:vt_access {{access_id: 'lgn-{lgn_sn}'}}), (i:vt_ip {{ip_addr: '{ip_addr}'}}) MERGE (a)-[:accessed_from]->(i)")
                        stats["edges"] += 1
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

            # 6-2. 기지국 위치 (TB_GEO_MBL_LOC_EVT) → vt_movement (mov_type='cell_tower')
            cur.execute("SELECT LOC_EVT_SN, TELNO, BSST_LAT, BSST_LOT, OCCRN_DT, EVT_TYP_NM FROM TB_GEO_MBL_LOC_EVT")
            rows = cur.fetchall()
            for r in rows:
                try:
                    eid, telno = safe_str(r[0]), safe_str(r[1])
                    lat, lng = safe_str(r[2]), safe_str(r[3])
                    dt, evt_type = safe_str(r[4]), safe_str(r[5])
                    props = f"{{mov_id: 'cell-{eid}', mov_type: 'cell_tower', loc_evt_sn: '{eid}', telno: '{telno}', lat: '{lat}', lng: '{lng}', timestamp: '{dt}', evt_typ_nm: '{evt_type}'}}"
                    cur.execute(f"MERGE (n:vt_movement {{mov_id: 'cell-{eid}'}}) SET n = {props}")
                    stats["nodes"] += 1
                    if telno:
                        cur.execute(f"MATCH (t:vt_telno {{telno: '{telno}'}}), (m:vt_movement {{mov_id: 'cell-{eid}'}}) MERGE (t)-[:recorded_in]->(m)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 6-3. LPR 인식 (TB_VHCL_LPR_EVT) → vt_movement (mov_type='lpr')
            cur.execute("SELECT RCGN_SN, VHCLNO, RCGN_DT, LAT, LOT, INST_LOC_NM FROM TB_VHCL_LPR_EVT")
            rows = cur.fetchall()
            for r in rows:
                try:
                    eid, vno = safe_str(r[0]), safe_str(r[1])
                    dt, lat, lng = safe_str(r[2]), safe_str(r[3]), safe_str(r[4])
                    loc_nm = safe_str(r[5])
                    props = f"{{mov_id: 'lpr-{eid}', mov_type: 'lpr', rcgn_sn: '{eid}', vhclno: '{vno}', lat: '{lat}', lng: '{lng}', timestamp: '{dt}', cctv_id: '{loc_nm}'}}"
                    cur.execute(f"MERGE (n:vt_movement {{mov_id: 'lpr-{eid}'}}) SET n = {props}")
                    stats["nodes"] += 1
                    if vno:
                        cur.execute(f"MATCH (v:vt_vhcl {{vhclno: '{vno}'}}), (m:vt_movement {{mov_id: 'lpr-{eid}'}}) MERGE (v)-[:recorded_in]->(m)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 6-4. 웹 도메인 (TB_WEB_DMN) → vt_site
            cur.execute("SELECT DMN_ADDR, IP_ADDR FROM TB_WEB_DMN")
            rows = cur.fetchall()
            for r in rows:
                try:
                    dmn, ip = safe_str(r[0]), safe_str(r[1])
                    props = f"{{url_addr: '{dmn}', dmn_addr: '{dmn}', ip_addr: '{ip}'}}"
                    cur.execute(f"MERGE (n:vt_site {{url_addr: '{dmn}'}}) SET n = {props}")
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
                        cur.execute(f"MATCH (a:vt_bacnt {{account_no: '{actno}'}}), (o:vt_org {{org_id: '{inst_id}'}}) MERGE (a)-[:belongs_to]->(o)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # 7-3. resolves_to: Site → IP (v3 방향: vt_site → vt_ip)
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
                        cur.execute(f"MATCH (s:vt_site {{url_addr: '{dmn}'}}), (i:vt_ip {{ip_addr: '{ip}'}}) MERGE (s)-[:resolves_to]->(i)")
                        stats["edges"] += 1
                except: pass
            conn.commit()

            # ─── Phase 6: v3.0 신규 도메인 ───────────────────────────
            logger.info(f"\n🆕 Phase 6: v3.0 신규 도메인 (출처/진정서/OSINT/엔티티해소)")

            # 6A. 출처 마스터 (TB_DATA_SRC) → vt_src
            try:
                cur.execute("""
                    SELECT SRC_ID, SRC_NM, SRC_TYPE_CD, RELI_TIER, INST_CD
                    FROM TB_DATA_SRC
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        sid, sname, stype, tier, inst = safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3]), safe_str(r[4])
                        props = f"{{src_id: '{sid}', src_name: '{sname}', src_type: '{stype}', reliability_tier: '{tier}', inst_cd: '{inst}', type: '출처'}}"
                        cur.execute(f"MERGE (n:vt_src {{src_id: '{sid}'}}) SET n = {props}")
                        stats["nodes"] += 1
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 6A-post. sourced_from 엣지 — vt_case/vt_psn/vt_org/vt_bacnt/vt_telno (v3.6 확정)
            # tier 1~3 노드 → vt_src 엣지 생성. SRC_ID 컬럼 없으면 'src-kics-agency'(tier 2) 사용.
            _src_default = 'src-kics-agency'
            try:
                # 기본 KICS 기관연계 소스 보장
                cur.execute(f"MERGE (s:vt_src {{src_id: '{_src_default}'}}) SET s.src_name = 'KICS 기관연계', s.src_type = 'AGENCY', s.reliability_tier = 2, s.type = '출처'")
                conn.commit()
            except: conn.rollback()

            for _tbl, _label, _key, _col in [
                ('TB_INCDNT_MST', 'vt_case',  'flnm',       'INCDNT_NO'),
                ('TB_PRSN',       'vt_psn',   'id',         'PRSN_ID'),
                ('TB_INST',       'vt_org',   'org_id',     'INST_ID'),
                ('TB_FIN_BACNT',  'vt_bacnt', 'account_no', 'BACNT_NO'),
                ('TB_TELNO_MST',  'vt_telno', 'telno',      'TELNO'),
            ]:
                try:
                    try:
                        cur.execute(f"SELECT {_col}, SRC_ID FROM {_tbl} WHERE SRC_ID IS NOT NULL AND SRC_ID != ''")
                        _rows = cur.fetchall()
                        for _r in _rows:
                            try:
                                _val, _sid = safe_str(_r[0]), safe_str(_r[1])
                                cur.execute(f"MATCH (n:{_label} {{{_key}: '{_val}'}}), (s:vt_src {{src_id: '{_sid}'}}) MERGE (n)-[:sourced_from {{src_tier: 2, rec_created: toString(datetime())}}]->(s)")
                                stats["edges"] += 1
                            except: pass
                    except:  # SRC_ID 컬럼 없음 — 기본 소스로 일괄 연결
                        conn.rollback()
                        safe_set_graph_path(cur, graph_name)
                        cur.execute(f"SELECT {_col} FROM {_tbl}")
                        _rows = cur.fetchall()
                        for _r in _rows:
                            try:
                                _val = safe_str(_r[0])
                                cur.execute(f"MATCH (n:{_label} {{{_key}: '{_val}'}}), (s:vt_src {{src_id: '{_src_default}'}}) MERGE (n)-[:sourced_from {{src_tier: 2, rec_created: toString(datetime())}}]->(s)")
                                stats["edges"] += 1
                            except: pass
                    conn.commit()
                except: conn.rollback()

            # 6B. 진정서 마스터 (TB_PETTN_MST) → vt_petition
            try:
                cur.execute("""
                    SELECT PETITION_ID, DCLR_SN, INCDNT_NO, RCPT_DT, PETTN_TYPE_CD,
                           RPRT_CNTN, SRC_ID
                    FROM TB_PETTN_MST
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        pid, dclr_sn, case_no, dt, ptype, content, src_id = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]),
                            safe_str(r[3]), safe_str(r[4]),
                            safe_str(r[5])[:100], safe_str(r[6])
                        )
                        props = (f"{{petition_id: '{pid}', raw_id: '{dclr_sn}', flnm: '{case_no}', "
                                 f"rcpt_dt: '{dt}', petition_type: '{ptype}', "
                                 f"content_summary: '{content}', src_id: '{src_id}', type: '진정서'}}")
                        cur.execute(f"MERGE (n:vt_petition {{petition_id: '{pid}'}}) SET n = {props}")
                        stats["nodes"] += 1

                        # 진정서 → 사건 연결 (filed_as: Petition→Case, v3 표준)
                        if case_no:
                            cur.execute(f"MATCH (p:vt_petition {{petition_id: '{pid}'}}), (c:vt_case {{flnm: '{case_no}'}}) MERGE (p)-[:filed_as]->(c)")
                            stats["edges"] += 1
                        # 출처 연결
                        if src_id:
                            cur.execute(f"MATCH (p:vt_petition {{petition_id: '{pid}'}}), (s:vt_src {{src_id: '{src_id}'}}) MERGE (p)-[:sourced_from]->(s)")
                            stats["edges"] += 1
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 6B-2. 진정서 피해자 연결 (TB_FRD_VCTM_RPT DCLR_SN → vt_petition.raw_id)
            try:
                cur.execute("""
                    SELECT R.DCLR_SN, R.SUSPCT_BACNT_NO, R.SUSPCT_TELNO, R.VCTM_TELNO
                    FROM TB_FRD_VCTM_RPT R
                    WHERE R.DCLR_SN IS NOT NULL
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        dclr, sus_acnt, sus_tel, vct_tel = safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3])
                        # dclr_sn → petition.raw_id 매핑하여 증거 엣지 생성
                        # v3.4: Petition→Evidence 직접 연결 제거 (반정규화 제거)
                        # 계좌/전화는 suspects를 통해 연결 → linked_to로 임시 보존
                        if sus_acnt:
                            cur.execute(f"MATCH (p:vt_petition {{raw_id: '{dclr}'}}), (a:vt_bacnt {{account_no: '{sus_acnt}'}}) MERGE (p)-[:linked_to {{reason: '진정서 계좌', pending_edge: 'has_account'}}]->(a)")
                            stats["edges"] += 1
                        if sus_tel:
                            cur.execute(f"MATCH (p:vt_petition {{raw_id: '{dclr}'}}), (t:vt_telno {{telno: '{sus_tel}'}}) MERGE (p)-[:linked_to {{reason: '진정서 전화', pending_edge: 'owns_phone'}}]->(t)")
                            stats["edges"] += 1
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 6C. OSINT 평판 데이터 → 기존 그래프 노드 속성 병합
            # IP 평판 (TB_OSINT_IP_REP)
            try:
                cur.execute("""
                    SELECT IP_ADDR, THREAT_SCORE, CATEGORY_CD, BLACKLIST_YN,
                           COUNTRY_CD, ISP_NM, LAST_SEEN_DT
                    FROM TB_OSINT_IP_REP
                    WHERE IP_ADDR IS NOT NULL
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        ip, score, cat, bl, country, isp, seen = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]),
                            safe_str(r[3]), safe_str(r[4]), safe_str(r[5]), safe_str(r[6])
                        )
                        cur.execute(f"""
                            MATCH (n:vt_ip {{ip_addr: '{ip}'}})
                            SET n.threat_score = '{score}', n.category = '{cat}',
                                n.blacklisted = '{bl}', n.country = '{country}',
                                n.isp = '{isp}', n.osint_last_seen = '{seen}'
                        """)
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 도메인 평판 (TB_OSINT_DMN_REP)
            try:
                cur.execute("""
                    SELECT DMN_ADDR, THREAT_SCORE, CATEGORY_CD, BLACKLIST_YN,
                           REGISTRAR_NM, CREATION_DT, EXPIRATION_DT
                    FROM TB_OSINT_DMN_REP
                    WHERE DMN_ADDR IS NOT NULL
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        dmn, score, cat, bl, reg, cr_dt, exp_dt = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]),
                            safe_str(r[3]), safe_str(r[4]), safe_str(r[5]), safe_str(r[6])
                        )
                        cur.execute(f"""
                            MATCH (n:vt_site {{url_addr: '{dmn}'}})
                            SET n.threat_score = '{score}', n.category = '{cat}',
                                n.blacklisted = '{bl}', n.registrar = '{reg}',
                                n.domain_created = '{cr_dt}', n.domain_expires = '{exp_dt}'
                        """)
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 파일 해시 평판 (TB_OSINT_HASH_REP)
            try:
                cur.execute("""
                    SELECT HASH_VAL, MALWARE_NM, THREAT_SCORE, BLACKLIST_YN,
                           FAMILY_NM, FIRST_SEEN_DT
                    FROM TB_OSINT_HASH_REP
                    WHERE HASH_VAL IS NOT NULL
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        hval, malware, score, bl, family, seen = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]),
                            safe_str(r[3]), safe_str(r[4]), safe_str(r[5])
                        )
                        cur.execute(f"""
                            MATCH (n:vt_file {{hash_val: '{hval}'}})
                            SET n.malware_name = '{malware}', n.threat_score = '{score}',
                                n.blacklisted = '{bl}', n.malware_family = '{family}',
                                n.osint_first_seen = '{seen}'
                        """)
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 전화번호 평판 (TB_OSINT_PHON_REP)
            try:
                cur.execute("""
                    SELECT TELNO, SPAM_SCORE, SPAM_TYPE_CD, RPT_CNT, BLACKLIST_YN
                    FROM TB_OSINT_PHON_REP
                    WHERE TELNO IS NOT NULL
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        tel, score, stype, cnt, bl = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]),
                            safe_str(r[3]), safe_str(r[4])
                        )
                        cur.execute(f"""
                            MATCH (n:vt_telno {{telno: '{tel}'}})
                            SET n.spam_score = '{score}', n.spam_type = '{stype}',
                                n.report_count = '{cnt}', n.blacklisted = '{bl}'
                        """)
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 계좌 평판 (TB_OSINT_ACNT_REP)
            try:
                cur.execute("""
                    SELECT ACNT_NO, BANK_CD, RISK_SCORE, FRAUD_REPORT_CNT, BLACKLIST_YN
                    FROM TB_OSINT_ACNT_REP
                    WHERE ACNT_NO IS NOT NULL
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        acnt, bcd, score, cnt, bl = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]),
                            safe_str(r[3]), safe_str(r[4])
                        )
                        cur.execute(f"""
                            MATCH (n:vt_bacnt {{account_no: '{acnt}'}})
                            WHERE n.bank_cd = '{bcd}'
                            SET n.risk_score = '{score}', n.fraud_report_count = '{cnt}',
                                n.blacklisted = '{bl}'
                        """)
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 가상자산 지갑 평판 (TB_OSINT_WALLET_REP)
            try:
                cur.execute("""
                    SELECT WALLET_ADDR, CHAIN_TYPE_CD, RISK_SCORE, SANCTION_YN, CLUSTER_ID
                    FROM TB_OSINT_WALLET_REP
                    WHERE WALLET_ADDR IS NOT NULL
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        waddr, chain, score, sanction, cluster = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]),
                            safe_str(r[3]), safe_str(r[4])
                        )
                        cur.execute(f"""
                            MATCH (n:vt_crypto {{wallet_addr: '{waddr}'}})
                            SET n.chain_type = '{chain}', n.risk_score = '{score}',
                                n.sanctioned = '{sanction}', n.cluster_id = '{cluster}'
                        """)
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 디지털 ID 평판 (TB_OSINT_ID_REP)
            try:
                cur.execute("""
                    SELECT ID_VAL, PLATFORM_CD, RISK_SCORE, FRAUD_REPORT_CNT, BLACKLIST_YN
                    FROM TB_OSINT_ID_REP
                    WHERE ID_VAL IS NOT NULL
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        idv, plat, score, cnt, bl = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]),
                            safe_str(r[3]), safe_str(r[4])
                        )
                        cur.execute(f"""
                            MATCH (n:vt_id {{id_val: '{idv}'}})
                            SET n.platform = '{plat}', n.risk_score = '{score}',
                                n.fraud_report_count = '{cnt}', n.blacklisted = '{bl}'
                        """)
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 6E. v3.0 신규 마스터 테이블 6개 → 그래프 노드 적재
            logger.info(f"\n🆕 Phase 6E: v3.0 신규 마스터 테이블 (id/email/crypto/dev/atm/loc)")

            # 6E-1. 디지털 ID (TB_DGTL_ID_MST) → vt_id
            try:
                cur.execute("""
                    SELECT ID_SN, ID_VAL, PLATFORM_NM, ID_TYP_CD,
                           PROFILE_URL, IS_ACTIVE_YN, REAL_NM, CONFIDENCE, SRC_ID
                    FROM TB_DGTL_ID_MST
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        sn, id_val, plat, id_type, url, active, real_nm, conf, src_id = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3]),
                            safe_str(r[4]), safe_str(r[5]), safe_str(r[6]),
                            safe_str(r[7]), safe_str(r[8])
                        )
                        props = (f"{{id_sn: '{sn}', id_val: '{id_val}', platform: '{plat}', "
                                 f"id_type: '{id_type}', profile_url: '{url}', "
                                 f"is_active: '{active}', real_name: '{real_nm}', "
                                 f"confidence: '{conf}', src_id: '{src_id}', type: '디지털ID'}}")
                        cur.execute(f"MERGE (n:vt_id {{id_val: '{id_val}', platform: '{plat}'}}) SET n = {props}")
                        stats["nodes"] += 1
                        if src_id:
                            cur.execute(f"MATCH (n:vt_id {{id_val: '{id_val}', platform: '{plat}'}}), (s:vt_src {{src_id: '{src_id}'}}) MERGE (n)-[:sourced_from]->(s)")
                            stats["edges"] += 1
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 6E-2. 이메일 (TB_EMAIL_MST) → vt_email
            try:
                cur.execute("""
                    SELECT EMAIL_SN, EMAIL_ADDR, DMN_ADDR, PROVIDER_NM,
                           IS_DISPSBL_YN, IS_VALID_YN, SRC_ID
                    FROM TB_EMAIL_MST
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        sn, addr, dmn, provider, disposable, valid, src_id = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]),
                            safe_str(r[3]), safe_str(r[4]), safe_str(r[5]), safe_str(r[6])
                        )
                        props = (f"{{email_sn: '{sn}', email_addr: '{addr}', "
                                 f"domain: '{dmn}', provider: '{provider}', "
                                 f"is_disposable: '{disposable}', is_valid: '{valid}', "
                                 f"src_id: '{src_id}', type: '이메일'}}")
                        cur.execute(f"MERGE (n:vt_email {{email_addr: '{addr}'}}) SET n = {props}")
                        stats["nodes"] += 1
                        if src_id:
                            cur.execute(f"MATCH (n:vt_email {{email_addr: '{addr}'}}), (s:vt_src {{src_id: '{src_id}'}}) MERGE (n)-[:sourced_from]->(s)")
                            stats["edges"] += 1
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 6E-3. 가상자산 지갑 (TB_CRYPTO_WALLET_MST) → vt_crypto
            try:
                cur.execute("""
                    SELECT WALLET_SN, WALLET_ADDR, BLOCKCHAIN_NM, ASSET_TYP_CD,
                           EXCHANGE_NM, BALANCE, RISK_SCORE, KYC_VRFY_YN, TX_CNT, SRC_ID
                    FROM TB_CRYPTO_WALLET_MST
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        sn, addr, chain, asset, exchange, balance, risk, kyc, tx_cnt, src_id = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3]),
                            safe_str(r[4]), safe_str(r[5]), safe_str(r[6]),
                            safe_str(r[7]), safe_str(r[8]), safe_str(r[9])
                        )
                        props = (f"{{wallet_sn: '{sn}', wallet_addr: '{addr}', "
                                 f"blockchain: '{chain}', asset_type: '{asset}', "
                                 f"exchange: '{exchange}', balance: '{balance}', "
                                 f"risk_score: '{risk}', kyc_verified: '{kyc}', "
                                 f"tx_count: '{tx_cnt}', src_id: '{src_id}', type: '가상자산지갑'}}")
                        cur.execute(f"MERGE (n:vt_crypto {{wallet_addr: '{addr}', blockchain: '{chain}'}}) SET n = {props}")
                        stats["nodes"] += 1
                        if src_id:
                            cur.execute(f"MATCH (n:vt_crypto {{wallet_addr: '{addr}', blockchain: '{chain}'}}), (s:vt_src {{src_id: '{src_id}'}}) MERGE (n)-[:sourced_from]->(s)")
                            stats["edges"] += 1
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 6E-4. 기기 (TB_DEV_MST) → vt_dev
            try:
                cur.execute("""
                    SELECT DEVICE_SN, DEVICE_ID, DEV_TYP_CD, IMEI, MAC_ADDR,
                           MODEL_NM, OS_NM, OS_VER, SRC_ID
                    FROM TB_DEV_MST
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        sn, dev_id, dev_type, imei, mac, model, os_nm, os_ver, src_id = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3]),
                            safe_str(r[4]), safe_str(r[5]), safe_str(r[6]),
                            safe_str(r[7]), safe_str(r[8])
                        )
                        props = (f"{{device_sn: '{sn}', device_id: '{dev_id}', "
                                 f"dev_type: '{dev_type}', imei: '{imei}', "
                                 f"mac_addr: '{mac}', model: '{model}', "
                                 f"os: '{os_nm}', os_version: '{os_ver}', "
                                 f"src_id: '{src_id}', type: '기기'}}")
                        cur.execute(f"MERGE (n:vt_dev {{device_id: '{dev_id}'}}) SET n = {props}")
                        stats["nodes"] += 1
                        # MAC → Access 연결: vt_dev → vt_access (owned_device 추론)
                        if mac:
                            cur.execute(f"MATCH (d:vt_dev {{device_id: '{dev_id}'}}), (a:vt_access) WHERE a.mac_addr = '{mac}' MERGE (d)-[:linked_to {{reason: 'MAC주소 기기추론', pending_edge: 'owns_device'}}]->(a)")
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 6E-5. ATM (TB_ATM_MST) → vt_atm (Bridge Key: atm_id = ATM_MNG_NO)
            try:
                cur.execute("""
                    SELECT ATM_SN, ATM_MNG_NO, BANK_NM, BANK_CD, LOC_ID,
                           INST_ADDR, INST_LAT, INST_LOT, IS_OUTDR_YN
                    FROM TB_ATM_MST
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        sn, atm_no, bank_nm, bank_cd, loc_id, addr, lat, lot, outdoor = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3]),
                            safe_str(r[4]), safe_str(r[5]), safe_str(r[6]),
                            safe_str(r[7]), safe_str(r[8])
                        )
                        props = (f"{{atm_sn: '{sn}', atm_id: '{atm_no}', "
                                 f"bank_name: '{bank_nm}', bank_cd: '{bank_cd}', "
                                 f"loc_id: '{loc_id}', address: '{addr}', "
                                 f"lat: '{lat}', lng: '{lot}', "
                                 f"is_outdoor: '{outdoor}', type: 'ATM'}}")
                        cur.execute(f"MERGE (n:vt_atm {{atm_id: '{atm_no}'}}) SET n = {props}")
                        stats["nodes"] += 1
                        # ATM → 위치 연결
                        if loc_id:
                            cur.execute(f"MATCH (a:vt_atm {{atm_id: '{atm_no}'}}), (l:vt_loc {{loc_id: '{loc_id}'}}) MERGE (a)-[:occurred_at]->(l)")
                            stats["edges"] += 1
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 6E-6. 위치 마스터 (TB_LOC_MST) → vt_loc (Bridge Key: loc_id)
            try:
                cur.execute("""
                    SELECT LOC_SN, LOC_ID, LOC_TYP_CD, ADDR_NM,
                           LAT, LOT, PLACE_NM, SIDO_NM, SIGUNGU_NM,
                           BSST_NM, CCTV_ID
                    FROM TB_LOC_MST
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        sn, loc_id, loc_type, addr, lat, lot, place, sido, sigungu, bsst, cctv = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3]),
                            safe_str(r[4]), safe_str(r[5]), safe_str(r[6]),
                            safe_str(r[7]), safe_str(r[8]), safe_str(r[9]), safe_str(r[10])
                        )
                        props = (f"{{loc_sn: '{sn}', loc_id: '{loc_id}', "
                                 f"loc_type: '{loc_type}', address: '{addr}', "
                                 f"lat: '{lat}', lng: '{lot}', "
                                 f"place_name: '{place}', sido: '{sido}', "
                                 f"sigungu: '{sigungu}', cell_tower: '{bsst}', "
                                 f"cctv_id: '{cctv}', type: '위치'}}")
                        cur.execute(f"MERGE (n:vt_loc {{loc_id: '{loc_id}'}}) SET n = {props}")
                        stats["nodes"] += 1
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 6G. 엔티티 해소 (TB_ENTITY_SAME_AS, STATUS_CD='CONFIRMED') → sameAs 엣지
            try:
                cur.execute("""
                    SELECT SRC_ENTITY_TYPE, SRC_ENTITY_ID, TGT_ENTITY_TYPE, TGT_ENTITY_ID,
                           CONFIDENCE_SCORE, RESOLVE_METHOD_CD
                    FROM TB_ENTITY_SAME_AS
                    WHERE STATUS_CD = 'CONFIRMED'
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        src_type, src_id, tgt_type, tgt_id, conf, method = (
                            safe_str(r[0]), safe_str(r[1]), safe_str(r[2]),
                            safe_str(r[3]), safe_str(r[4]), safe_str(r[5])
                        )
                        # 엔티티 타입 → 그래프 레이블 매핑
                        from app.middleware.services.ontology_service import KICSCrimeDomainOntology
                        label_map = KICSCrimeDomainOntology.GDB_LABEL_MAP
                        src_label = label_map.get(src_type, src_type)
                        tgt_label = label_map.get(tgt_type, tgt_type)
                        cur.execute(f"""
                            MATCH (s:{src_label} {{id: '{src_id}'}}), (t:{tgt_label} {{id: '{tgt_id}'}})
                            MERGE (s)-[e:sameAs {{confidence: '{conf}', method: '{method}'}}]->(t)
                        """)
                        stats["edges"] += 1
                    except: pass
                conn.commit()
            except: conn.rollback()

            # 6H. 모순 정보 (TB_ENTITY_CONFLICT, RESOLVED_YN='N') → contradicts 엣지
            try:
                cur.execute("""
                    SELECT PRSN_ID_A, PRSN_ID_B, CNFL_FIELD_NM, CNFL_TYP_CD
                    FROM TB_ENTITY_CONFLICT
                    WHERE RESOLVED_YN = 'N'
                """)
                rows = cur.fetchall()
                for row in rows:
                    pid_a, pid_b, field, typ = row
                    try:
                        safe_set_graph_path(cur, graph_name)
                        cur.execute(f"""
                            MATCH (a:vt_psn {{id: '{pid_a}'}}), (b:vt_psn {{id: '{pid_b}'}})
                            MERGE (a)-[e:contradicts {{cnfl_field: '{field}', cnfl_type: '{typ}',
                                   rec_created: toString(now())}}]->(b)
                        """)
                        stats["edges"] += 1
                    except: pass
                conn.commit()
                logger.info(f"  contradicts 엣지: {len(rows)}건")
            except: conn.rollback()

            # 6I. 유사 진정서 군집 (TB_PETTN_CLSTR, SIM_SCORE >= 0.7) → clusters_with 엣지
            try:
                cur.execute("""
                    SELECT PETTN_SN_A, PETTN_SN_B, SIM_SCORE, SIM_BASIS_CD
                    FROM TB_PETTN_CLSTR
                    WHERE SIM_SCORE >= 0.7
                """)
                rows = cur.fetchall()
                for row in rows:
                    sn_a, sn_b, score, basis = row
                    try:
                        safe_set_graph_path(cur, graph_name)
                        cur.execute(f"""
                            MATCH (a:vt_petition), (b:vt_petition)
                            WHERE a.raw_id = '{sn_a}' AND b.raw_id = '{sn_b}'
                            MERGE (a)-[e:clusters_with {{sim_score: {score}, basis: '{basis}',
                                   rec_created: toString(now())}}]->(b)
                        """)
                        stats["edges"] += 1
                    except: pass
                conn.commit()
                logger.info(f"  clusters_with 엣지: {len(rows)}건")
            except: conn.rollback()

            # 6J. 사칭 이벤트 (V3.3) — TB_IMPRSN_REL → vt_impersonation 노드 + used_for/targets 엣지
            # 패턴: (Object) -[used_for]-> (vt_impersonation) -[targets]-> (vt_org)
            try:
                cur.execute("""
                    SELECT IMPRSN_SN, IMPRSN_ORG_ID, IMPRSN_TYPE_CD,
                           TELNO, DGTL_ID, EMAIL_ADDR, FRST_DT,
                           FAKE_NM, SCRIPT_TYPE_CD, END_DT
                    FROM TB_IMPRSN_REL
                    WHERE RSLVD_YN = 'N'
                """)
                rows = cur.fetchall()
                imprsn_cnt = 0
                for row in rows:
                    sn, org_id, imp_type, telno, d_id, email, dt, fake_nm, script_type, end_dt = row
                    sn_s   = safe_str(sn);       org_s    = safe_str(org_id)
                    typ_s  = safe_str(imp_type); dt_s     = safe_str(dt)
                    fake_s = safe_str(fake_nm);  script_s = safe_str(script_type)
                    end_s  = safe_str(end_dt)
                    evt_id = f"imp-{sn_s}"
                    try:
                        safe_set_graph_path(cur, graph_name)
                        # Step 1: vt_impersonation 이벤트 노드 MERGE
                        cur.execute(f"""
                            MERGE (imp:vt_impersonation {{event_id: '{evt_id}'}})
                            ON CREATE SET
                                imp.method      = '{typ_s}',
                                imp.fake_name   = '{fake_s}',
                                imp.script_type = '{script_s}',
                                imp.start_dt    = '{dt_s}',
                                imp.end_dt      = '{end_s}',
                                imp.source_id   = 'src-rdb-etl',
                                imp.rec_created = toString(now())
                        """)
                        # Step 2: targets 엣지 — vt_impersonation → vt_org
                        cur.execute(f"""
                            MATCH (imp:vt_impersonation {{event_id: '{evt_id}'}}),
                                  (o:vt_org {{org_id: '{org_s}'}})
                            MERGE (imp)-[e:targets {{
                                source_id: 'src-rdb-etl',
                                rec_created: toString(now())
                            }}]->(o)
                        """)
                        stats["edges"] += 1
                        # Step 3: used_for 엣지 — Object → vt_impersonation (수단별)
                        if telno:
                            tel_s = safe_str(telno)
                            cur.execute(f"""
                                MATCH (t:vt_telno {{telno: '{tel_s}'}}),
                                      (imp:vt_impersonation {{event_id: '{evt_id}'}})
                                MERGE (t)-[e:used_for {{
                                    imprsn_type: '{typ_s}',
                                    source_id: 'src-rdb-etl',
                                    rec_created: toString(now())
                                }}]->(imp)
                            """)
                            stats["edges"] += 1; imprsn_cnt += 1
                        if d_id:
                            id_s = safe_str(d_id)
                            cur.execute(f"""
                                MATCH (i:vt_id {{id_val: '{id_s}'}}),
                                      (imp:vt_impersonation {{event_id: '{evt_id}'}})
                                MERGE (i)-[e:used_for {{
                                    imprsn_type: '{typ_s}',
                                    source_id: 'src-rdb-etl',
                                    rec_created: toString(now())
                                }}]->(imp)
                            """)
                            stats["edges"] += 1; imprsn_cnt += 1
                        if email:
                            em_s = safe_str(email)
                            cur.execute(f"""
                                MATCH (em:vt_email {{email_addr: '{em_s}'}}),
                                      (imp:vt_impersonation {{event_id: '{evt_id}'}})
                                MERGE (em)-[e:used_for {{
                                    imprsn_type: '{typ_s}',
                                    source_id: 'src-rdb-etl',
                                    rec_created: toString(now())
                                }}]->(imp)
                            """)
                            stats["edges"] += 1; imprsn_cnt += 1
                        stats["nodes"] += 1
                    except: pass
                conn.commit()
                logger.info(f"  vt_impersonation 노드+used_for/targets 엣지: {imprsn_cnt}건 ({len(rows)}개 사칭이벤트)")
            except: conn.rollback()

            logger.info(f"✅ V3.3 POLE GDB 변환 완료: {stats}")
            return True, stats

        except Exception as e:
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False, f"V2 ETL 오류: {str(e)}"
        finally:
            cur.close()
            conn.close()
