"""
RDB → GDB 온톨로지 기반 변환 서비스  [v3.5 POLE 6-Layer]

v3.5 POLE 6계층 온톨로지에 따라 RDB(49개 테이블) 데이터를 그래프로 변환합니다:
  Layer 1 (Source)   → vt_src          [TB_DATA_SRC]
  Layer 2 (Case)     → vt_case, vt_petition   [TB_INCDNT_MST, TB_PETTN_MST]
  Layer 3 (Person)   → vt_psn, vt_org         [TB_PRSN, TB_INST]
  Layer 4 (Object)   → vt_bacnt, vt_telno, vt_ip, vt_site, vt_file,
                        vt_id, vt_email, vt_crypto, vt_dev, vt_atm, vt_vhcl
  Layer 5 (Location) → vt_loc          [TB_LOC_MST]
  Layer 6 (Event)    → vt_transfer, vt_call, vt_msg, vt_access, vt_movement,
                        vt_impersonation  [V3.3 신설 — TB_IMPRSN_REL, used_for/targets 패턴]
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
            # 스키마 감지
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'tb_incdnt_mst'
                )
            """)
            use_kics = cur.fetchone()[0]

            if not use_kics:
                # rdb_* fallback 테이블 목록
                tables = [
                    ('rdb_cases',      'vt_case',     '사건'),
                    ('rdb_suspects',   'vt_psn',      '피의자'),
                    ('rdb_accounts',   'vt_bacnt',    '계좌'),
                    ('rdb_calls',      'vt_call',     '통화'),
                    ('rdb_transfers',  'vt_transfer', '이체'),
                    ('tb_incdnt_prsn', '—',           '사건-인물 조인'),
                ]

            for tbl, label, desc in tables:
                try:
                    cur.execute(f"SELECT count(*) FROM {tbl}")
                    cnt = cur.fetchone()[0]
                    preview.append({'table': tbl, 'graph_label': label, 'description': desc, 'count': cnt,
                                    'schema': 'kics' if use_kics else 'legacy'})
                except:
                    conn.rollback()
                    preview.append({'table': tbl, 'graph_label': label, 'description': desc, 'count': 0,
                                    'schema': 'kics' if use_kics else 'legacy'})
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
                'vt_impersonation',  # V3.3 신설
                'pt_cluster', 'site_cluster',  # V3.7 허브 노드
            ]
            edge_labels = [
                # 역할 엣지 (v3.0 Role-as-Edge)
                'suspect_in', 'victim_in', 'witness_in',
                # 엔티티 해소
                'sameAs', 'contradicts',
                # 증거 연결
                'eg_used_account', 'eg_used_phone', 'eg_used_ip',
                'has_account', 'owns_phone', 'used_ip', 'linked_to',
                # 이체/통화/이동
                'from_account', 'to_account', 'caller', 'callee', 'contacted',
                'sent_msg', 'received_msg', 'recorded_in',
                # 소유/관계
                'owns_vehicle', 'contains_file',
                'related_case', 'belongs_to', 'resolved_to', 'works_at',
                # 출처
                'sourced_from',
                # v3.0 신규: 인물 → 디지털 증거
                'uses_id', 'uses_email', 'owns_wallet', 'uses_device',
                # v3.0 신규: 기타
                'filed_as', 'occurred_at', 'accessed_from', 'performed_by',
                'clusters_with', 'resolves_to',
                # v3.3 사칭 패턴 (impersonates는 하위호환 읽기용)
                'used_for', 'targets', 'impersonates',
                # v3.7 신규 엣지
                'belongs_to_cluster', 'belongs_to_campaign', 'used_in_device',
                # (구) 호환
                'involves',
            ]
            
            for vl in vertex_labels:
                try: cur.execute(f"CREATE VLABEL IF NOT EXISTS {vl}"); conn.commit()
                except: conn.rollback(); safe_set_graph_path(cur, graph_name)
            
            for el in edge_labels:
                try: cur.execute(f"CREATE ELABEL IF NOT EXISTS {el}"); conn.commit()
                except: conn.rollback(); safe_set_graph_path(cur, graph_name)

            # --- 3. 스키마 감지 ---
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'tb_incdnt_mst'
                )
            """)
            use_kics_schema = cur.fetchone()[0]
            logger.info(f"   스키마: {'KICS 표준(TB_)' if use_kics_schema else 'rdb_* 레거시 fallback'}")

            # --- 4. 노드 적재 ---
            logger.info(f"\n📦 Phase 1: 노드 변환")

            if not use_kics_schema:
                # ── rdb_* 레거시 테이블 fallback ──────────────────────────────
                logger.info("   [fallback] rdb_* 테이블 사용")

                # F-1. Case (rdb_cases → vt_case)
                try:
                    cur.execute("SELECT case_id, case_no, crime_name, crime_type, reg_date, org_name FROM rdb_cases")
                    rows = cur.fetchall()
                    for r in rows:
                        try:
                            cid, cno, cname, ctype, cdate, org = [safe_str(x) for x in r]
                            flnm = cno or cid
                            props = f"{{flnm: '{flnm}', crime: '{cname}', crime_type: '{ctype}', date: '{cdate}', org: '{org}', type: '사건'}}"
                            cur.execute(f"MERGE (n:vt_case {{flnm: '{flnm}'}}) SET n = {props}")
                            stats["nodes"] += 1; stats["cases"] += 1
                        except: pass
                    conn.commit()
                    logger.info(f"  ✓ vt_case (rdb_cases): {stats['cases']}건")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"  ⚠ rdb_cases 오류: {e}")

                # tb_incdnt_prsn의 incdnt_no도 vt_case로 merge
                try:
                    cur.execute("SELECT DISTINCT incdnt_no FROM tb_incdnt_prsn WHERE incdnt_no IS NOT NULL")
                    rows = cur.fetchall()
                    for r in rows:
                        try:
                            flnm = safe_str(r[0])
                            props = f"{{flnm: '{flnm}', type: '사건'}}"
                            cur.execute(f"MERGE (n:vt_case {{flnm: '{flnm}'}}) ON CREATE SET n = {props}")
                            stats["nodes"] += 1; stats["cases"] += 1
                        except: pass
                    conn.commit()
                    logger.info(f"  ✓ vt_case (tb_incdnt_prsn): {stats['cases']}건")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"  ⚠ tb_incdnt_prsn case merge 오류: {e}")

                # F-2. Person (rdb_suspects → vt_psn)
                try:
                    cur.execute("SELECT suspect_id, user_id, name, nickname FROM rdb_suspects")
                    rows = cur.fetchall()
                    for r in rows:
                        try:
                            sid, uid, name, nick = safe_str(r[0]), safe_str(r[1]), safe_str(r[2]), safe_str(r[3])
                            pid = f"suspect_{sid}"
                            props = f"{{id: '{pid}', user_id: '{uid}', name: '{name}', nickname: '{nick}', type: '피의자'}}"
                            cur.execute(f"MERGE (n:vt_psn {{id: '{pid}'}}) SET n = {props}")
                            stats["nodes"] += 1; stats["persons"] += 1
                        except: pass
                    conn.commit()
                    logger.info(f"  ✓ vt_psn (rdb_suspects): {stats['persons']}건")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"  ⚠ rdb_suspects 오류: {e}")

                # tb_incdnt_prsn의 prsn_id도 vt_psn으로 merge
                try:
                    cur.execute("SELECT prsn_id, role_cd FROM tb_incdnt_prsn WHERE prsn_id IS NOT NULL")
                    rows = cur.fetchall()
                    for r in rows:
                        try:
                            pid, role = safe_str(r[0]), safe_str(r[1])
                            props = f"{{id: '{pid}', name: '{pid}', type: '{role}'}}"
                            cur.execute(f"MERGE (n:vt_psn {{id: '{pid}'}}) ON CREATE SET n = {props}")
                            stats["nodes"] += 1; stats["persons"] += 1
                        except: pass
                    conn.commit()
                    logger.info(f"  ✓ vt_psn (tb_incdnt_prsn): {stats['persons']}건")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"  ⚠ tb_incdnt_prsn person merge 오류: {e}")

                # F-3. Account (rdb_accounts → vt_bacnt)
                try:
                    cur.execute("SELECT actno, bank_name, holder_name FROM rdb_accounts")
                    rows = cur.fetchall()
                    for r in rows:
                        try:
                            actno, bname, holder = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                            if not actno: continue
                            props = f"{{actno: '{actno}', bank: '{bname}', holder: '{holder}', type: '계좌'}}"
                            cur.execute(f"MERGE (n:vt_bacnt {{actno: '{actno}'}}) SET n = {props}")
                            stats["nodes"] += 1; stats["accounts"] += 1
                        except: pass
                    conn.commit()
                    logger.info(f"  ✓ vt_bacnt (rdb_accounts): {stats['accounts']}건")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"  ⚠ rdb_accounts 오류: {e}")

                # F-4. Phone (rdb_calls caller/callee → vt_telno)
                try:
                    cur.execute("SELECT DISTINCT caller_no FROM rdb_calls WHERE caller_no IS NOT NULL UNION SELECT DISTINCT callee_no FROM rdb_calls WHERE callee_no IS NOT NULL")
                    rows = cur.fetchall()
                    for r in rows:
                        try:
                            telno = safe_str(r[0])
                            if not telno: continue
                            props = f"{{telno: '{telno}', type: '전화번호'}}"
                            cur.execute(f"MERGE (n:vt_telno {{telno: '{telno}'}}) SET n = {props}")
                            stats["nodes"] += 1; stats["phones"] += 1
                        except: pass
                    conn.commit()
                    logger.info(f"  ✓ vt_telno (rdb_calls): {stats['phones']}건")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"  ⚠ rdb_calls telno 오류: {e}")

                # F-5. Transfer (rdb_transfers → vt_transfer)
                try:
                    cur.execute("SELECT trx_id, amount, trx_date, sender_actno, receiver_actno FROM rdb_transfers")
                    rows = cur.fetchall()
                    for r in rows:
                        try:
                            tid, amt, dt, snd, rcv = [safe_str(x) for x in r]
                            props = f"{{id: '{tid}', amount: '{amt}', date: '{dt}', sender: '{snd}', receiver: '{rcv}', type: '이체'}}"
                            cur.execute(f"MERGE (n:vt_transfer {{id: '{tid}'}}) SET n = {props}")
                            stats["nodes"] += 1; stats["transfers"] += 1
                        except: pass
                    conn.commit()
                    logger.info(f"  ✓ vt_transfer (rdb_transfers): {stats['transfers']}건")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"  ⚠ rdb_transfers 오류: {e}")

                # F-6. Call (rdb_calls → vt_call)
                try:
                    cur.execute("SELECT call_id, duration, call_date, caller_no, callee_no FROM rdb_calls")
                    rows = cur.fetchall()
                    for r in rows:
                        try:
                            cid, dur, dt, caller, callee = [safe_str(x) for x in r]
                            props = f"{{id: '{cid}', duration: '{dur}', date: '{dt}', caller: '{caller}', callee: '{callee}', type: '통화'}}"
                            cur.execute(f"MERGE (n:vt_call {{id: '{cid}'}}) SET n = {props}")
                            stats["nodes"] += 1; stats["calls"] += 1
                        except: pass
                    conn.commit()
                    logger.info(f"  ✓ vt_call (rdb_calls): {stats['calls']}건")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"  ⚠ rdb_calls call 오류: {e}")

                # F-7. 엣지: suspect_in / victim_in (tb_incdnt_prsn)
                try:
                    cur.execute("SELECT prsn_id, incdnt_no, role_cd FROM tb_incdnt_prsn")
                    rows = cur.fetchall()
                    for r in rows:
                        try:
                            pid, incdnt, role = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                            if not pid or not incdnt: continue
                            edge_type = 'suspect_in' if '피의자' in role else ('victim_in' if '피해자' in role else 'witness_in')
                            cur.execute(f"""
                                MATCH (p:vt_psn {{id: '{pid}'}}), (c:vt_case {{flnm: '{incdnt}'}})
                                MERGE (p)-[:{edge_type} {{role: '{role}'}}]->(c)
                            """)
                            stats["edges"] += 1; stats["relations"] += 1
                        except: pass
                    conn.commit()
                    logger.info(f"  ✓ 역할 엣지 (tb_incdnt_prsn): {stats['relations']}건")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"  ⚠ tb_incdnt_prsn 엣지 오류: {e}")

                # F-8. 엣지: has_account (rdb_suspects ↔ rdb_accounts, user_id 매칭)
                try:
                    cur.execute("""
                        SELECT s.suspect_id, a.actno
                        FROM rdb_suspects s
                        JOIN rdb_accounts a ON a.holder_name = s.name
                    """)
                    rows = cur.fetchall()
                    for r in rows:
                        try:
                            pid, actno = f"suspect_{safe_str(r[0])}", safe_str(r[1])
                            cur.execute(f"""
                                MATCH (p:vt_psn {{id: '{pid}'}}), (a:vt_bacnt {{actno: '{actno}'}})
                                MERGE (p)-[:has_account]->(a)
                            """)
                            stats["edges"] += 1
                        except: pass
                    conn.commit()
                    logger.info(f"  ✓ has_account 엣지: {stats['edges']}건")
                except Exception as e:
                    conn.rollback()
                    logger.warning(f"  ⚠ has_account 엣지 오류: {e}")

                logger.info(f"\n✅ [fallback] 변환 완료: 노드 {stats['nodes']}건, 엣지 {stats['edges']}건")
                return True, stats

            # ── KICS 표준 스키마 (TB_ 테이블) ────────────────────────────────────

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
            from app.services.etl_service import StandardCodeMapper
            cur.execute("SELECT BACNT_NO, BANK_CD, BANK_NM FROM TB_FIN_BACNT")
            rows = cur.fetchall()
            for r in rows:
                try:
                    actno, bcode, bname = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                    # StandardCodeMapper: 은행명/약어 → 금결원 표준코드
                    normalized_bcode = StandardCodeMapper.map_bank_code(bname) or \
                                       StandardCodeMapper.map_bank_code(bcode) or bcode
                    is_atm = actno.upper().startswith('ATM') or actno == '현금인출'
                    if is_atm:
                        import re
                        loc_match = re.search(r'[가-힣]+', actno)
                        no_match = re.search(r'(\d+)$', actno)
                        atm_loc = loc_match.group() if loc_match else '미상'
                        atm_no = no_match.group() if no_match else ''
                        display_name = f"{atm_loc} ATM {atm_no}".strip() if actno != '현금인출' else '현금인출'
                        props = f"{{atm_id: '{actno}', location: '{atm_loc}', atm_no: '{atm_no}', name: '{display_name}', type: 'ATM'}}"
                        cur.execute(f"MERGE (n:vt_atm {{atm_id: '{actno}'}}) SET n = {props}")
                    else:
                        props = (f"{{account_no: '{actno}', bank_cd: '{normalized_bcode}', "
                                 f"bank_name: '{bname}', type: '계좌'}}")
                        cur.execute(f"MERGE (n:vt_bacnt {{account_no: '{actno}'}}) SET n = {props}")
                    stats["nodes"] += 1; stats["accounts"] += 1
                except: pass
            conn.commit()

            # 3-4. Phone (TB_TELNO_MST) — 통신사 코드 정규화 포함
            try:
                cur.execute("SELECT TELNO, TELE_CMPN_NM, TELE_CMPN_CD FROM TB_TELNO_MST")
            except Exception:
                conn.rollback()
                cur.execute("SELECT TELNO FROM TB_TELNO_MST")
            rows = cur.fetchall()
            for r in rows:
                try:
                    telno = safe_str(r[0])
                    carrier_nm = safe_str(r[1]) if len(r) > 1 else ''
                    carrier_cd = safe_str(r[2]) if len(r) > 2 else ''
                    # StandardCodeMapper: 통신사명/약어 → 표준코드
                    normalized_carrier = StandardCodeMapper.map_carrier_code(carrier_nm) or \
                                         StandardCodeMapper.map_carrier_code(carrier_cd) or carrier_cd
                    props = (f"{{telno: '{telno}', carrier_cd: '{normalized_carrier}', "
                             f"carrier_name: '{carrier_nm}', type: '전화번호'}}")
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
                    if actno:
                        cur.execute(f"MATCH (c:vt_case {{flnm: '{case_no}'}}), (a:vt_bacnt {{account_no: '{actno}'}}) MERGE (c)-[:eg_used_account]->(a)")
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
                            role_edge = 'suspect_in' if role == 'SUSPECT' else 'victim_in' if role == 'VICTIM' else 'witness_in' if role == 'WITNESS' else 'involves'
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

            # 5-6. used_ip + performed_by (TB_SYS_LGN_EVT.USER_ID ↔ TB_PRSN 조인)
            #      Person → vt_ip (used_ip), Person → vt_access (performed_by)
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
                    if lgn_sn and pid:
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid}'}}), (a:vt_access {{access_id: 'lgn-{lgn_sn}'}}) MERGE (p)-[:performed_by]->(a)")
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
                        if sus_acnt:
                            cur.execute(f"MATCH (p:vt_petition {{raw_id: '{dclr}'}}), (a:vt_bacnt {{account_no: '{sus_acnt}'}}) MERGE (p)-[:eg_used_account]->(a)")
                            stats["edges"] += 1
                        if sus_tel:
                            cur.execute(f"MATCH (p:vt_petition {{raw_id: '{dclr}'}}), (t:vt_telno {{telno: '{sus_tel}'}}) MERGE (p)-[:eg_used_phone]->(t)")
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
                        # MAC → IP 연결: vt_dev → vt_access (접속 기기 추론)
                        if mac:
                            cur.execute(f"MATCH (d:vt_dev {{device_id: '{dev_id}'}}), (a:vt_access) WHERE a.mac_addr = '{mac}' MERGE (d)-[:performed_by]->(a)")
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

            # 6D. 엔티티 해소 (TB_ENTITY_SAME_AS, STATUS_CD='CONFIRMED') → sameAs 엣지
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
            # ⚠️ v3.7부터 deprecated. pt_cluster 허브 노드(6V-1)로 대체. 하위호환 위해 유지.
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

            # 6J. 사칭 관계 (TB_IMPRSN_REL) → V3.3 패턴
            #   1) vt_impersonation 노드 MERGE
            #   2) (vt_impersonation)-[targets]->(vt_org)
            #   3) (vt_telno/vt_id/vt_email)-[used_for]->(vt_impersonation)
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
                    sn_s   = safe_str(sn);       org_s  = safe_str(org_id)
                    typ_s  = safe_str(imp_type); dt_s   = safe_str(dt)
                    fnm_s  = safe_str(fake_nm);  sct_s  = safe_str(script_type)
                    edt_s  = safe_str(end_dt);   eid_s  = f"imp-{sn_s}"
                    try:
                        safe_set_graph_path(cur, graph_name)
                        # ① vt_impersonation 노드 생성
                        cur.execute(f"""
                            MERGE (imp:vt_impersonation {{event_id: '{eid_s}'}})
                            ON CREATE SET imp.method = '{typ_s}',
                                          imp.fake_name = '{fnm_s}',
                                          imp.script_type = '{sct_s}',
                                          imp.start_dt = '{dt_s}',
                                          imp.end_dt = '{edt_s}',
                                          imp.source_id = '{sn_s}',
                                          imp.rec_created = toString(now())
                        """)
                        stats["nodes"] += 1
                        # ② vt_impersonation -[targets]-> vt_org
                        cur.execute(f"""
                            MATCH (imp:vt_impersonation {{event_id: '{eid_s}'}}),
                                  (o:vt_org {{org_id: '{org_s}'}})
                            MERGE (imp)-[e:targets {{source_id: '{sn_s}'}}]->(o)
                        """)
                        stats["edges"] += 1
                        # ③ 수단 노드 -[used_for]-> vt_impersonation
                        if telno:
                            tel_s = safe_str(telno)
                            cur.execute(f"""
                                MATCH (t:vt_telno {{telno: '{tel_s}'}}),
                                      (imp:vt_impersonation {{event_id: '{eid_s}'}})
                                MERGE (t)-[e:used_for {{source_id: '{sn_s}',
                                           rec_created: toString(now())}}]->(imp)
                            """)
                            stats["edges"] += 1; imprsn_cnt += 1
                        if d_id:
                            id_s = safe_str(d_id)
                            cur.execute(f"""
                                MATCH (i:vt_id {{id_val: '{id_s}'}}),
                                      (imp:vt_impersonation {{event_id: '{eid_s}'}})
                                MERGE (i)-[e:used_for {{source_id: '{sn_s}',
                                           rec_created: toString(now())}}]->(imp)
                            """)
                            stats["edges"] += 1; imprsn_cnt += 1
                        if email:
                            em_s = safe_str(email)
                            cur.execute(f"""
                                MATCH (em:vt_email {{email_addr: '{em_s}'}}),
                                      (imp:vt_impersonation {{event_id: '{eid_s}'}})
                                MERGE (em)-[e:used_for {{source_id: '{sn_s}',
                                            rec_created: toString(now())}}]->(imp)
                            """)
                            stats["edges"] += 1; imprsn_cnt += 1
                    except: pass
                conn.commit()
                logger.info(f"  V3.3 사칭 ETL: vt_impersonation {len(rows)}개 노드, used_for/targets 엣지 {imprsn_cnt}건")
            except: conn.rollback()

            # ─── Phase 7: v3.0 인물 → 디지털 증거 소유관계 추론 ─────────────
            logger.info(f"\n🔗 Phase 7: 인물 → v3.0 디지털 증거 소유관계")

            # 7-1. Person → Digital ID (TB_DGTL_ID_MST.REAL_NM ↔ TB_PRSN.KORN_FLNM)
            try:
                cur.execute("""
                    SELECT D.ID_VAL, D.PLATFORM_NM, P.PRSN_ID
                    FROM TB_DGTL_ID_MST D
                    JOIN TB_PRSN P ON P.KORN_FLNM = D.REAL_NM
                    WHERE D.REAL_NM IS NOT NULL AND D.REAL_NM != ''
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        id_val, plat, pid = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                        cur.execute(f"""
                            MATCH (p:vt_psn {{id: '{pid}'}}),
                                  (d:vt_id {{id_val: '{id_val}', platform: '{plat}'}})
                            MERGE (p)-[e:uses_id {{evid_grade: 'B', src_tier: 2}}]->(d)
                        """)
                        stats["edges"] += 1
                    except: pass
                conn.commit()
                logger.info(f"  ✓ uses_id 엣지 (인물→디지털ID): {len(rows)}건")
            except: conn.rollback()

            # 7-2. Person → Email (TB_EMAIL_MST.REAL_NM ↔ TB_PRSN.KORN_FLNM)
            try:
                cur.execute("""
                    SELECT E.EMAIL_ADDR, P.PRSN_ID
                    FROM TB_EMAIL_MST E
                    JOIN TB_PRSN P ON P.KORN_FLNM = E.REAL_NM
                    WHERE E.REAL_NM IS NOT NULL AND E.REAL_NM != ''
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        email, pid = safe_str(r[0]), safe_str(r[1])
                        cur.execute(f"""
                            MATCH (p:vt_psn {{id: '{pid}'}}),
                                  (e:vt_email {{email_addr: '{email}'}})
                            MERGE (p)-[r:uses_email {{evid_grade: 'B', src_tier: 2}}]->(e)
                        """)
                        stats["edges"] += 1
                    except: pass
                conn.commit()
                logger.info(f"  ✓ uses_email 엣지 (인물→이메일): {len(rows)}건")
            except: conn.rollback()

            # 7-3. Person → Crypto Wallet (TB_CRYPTO_WALLET_MST.OWNER_NM ↔ TB_PRSN.KORN_FLNM)
            try:
                cur.execute("""
                    SELECT C.WALLET_ADDR, C.BLOCKCHAIN_NM, P.PRSN_ID
                    FROM TB_CRYPTO_WALLET_MST C
                    JOIN TB_PRSN P ON P.KORN_FLNM = C.OWNER_NM
                    WHERE C.OWNER_NM IS NOT NULL AND C.OWNER_NM != ''
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        waddr, chain, pid = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                        cur.execute(f"""
                            MATCH (p:vt_psn {{id: '{pid}'}}),
                                  (w:vt_crypto {{wallet_addr: '{waddr}', blockchain: '{chain}'}})
                            MERGE (p)-[r:owns_wallet {{evid_grade: 'B', src_tier: 2}}]->(w)
                        """)
                        stats["edges"] += 1
                    except: pass
                conn.commit()
                logger.info(f"  ✓ owns_wallet 엣지 (인물→가상자산): {len(rows)}건")
            except: conn.rollback()

            # 7-4. Person → Device (TB_DEV_MST.OWNER_NM ↔ TB_PRSN.KORN_FLNM)
            try:
                cur.execute("""
                    SELECT D.DEVICE_ID, P.PRSN_ID
                    FROM TB_DEV_MST D
                    JOIN TB_PRSN P ON P.KORN_FLNM = D.OWNER_NM
                    WHERE D.OWNER_NM IS NOT NULL AND D.OWNER_NM != ''
                """)
                rows = cur.fetchall()
                for r in rows:
                    try:
                        dev_id, pid = safe_str(r[0]), safe_str(r[1])
                        cur.execute(f"""
                            MATCH (p:vt_psn {{id: '{pid}'}}),
                                  (d:vt_dev {{device_id: '{dev_id}'}})
                            MERGE (p)-[r:uses_device {{evid_grade: 'B', src_tier: 2}}]->(d)
                        """)
                        stats["edges"] += 1
                    except: pass
                conn.commit()
                logger.info(f"  ✓ uses_device 엣지 (인물→기기): {len(rows)}건")
            except: conn.rollback()

            # 7-5. Case → Account / Phone 직접 엣지 (KICS 표준: TB_INCDNT_EVID)
            try:
                cur.execute("""
                    SELECT INCDNT_NO, EVID_TYPE_CD, EVID_VAL
                    FROM TB_INCDNT_EVID
                    WHERE EVID_TYPE_CD IN ('BACNT', 'TELNO', 'IP', 'SITE')
                      AND INCDNT_NO IS NOT NULL AND EVID_VAL IS NOT NULL
                """)
                rows = cur.fetchall()
                evid_type_map = {
                    'BACNT': ('vt_bacnt', 'account_no', 'eg_used_account'),
                    'TELNO': ('vt_telno', 'telno',      'eg_used_phone'),
                    'IP':    ('vt_ip',    'ip_addr',    'eg_used_ip'),
                    'SITE':  ('vt_site',  'url_addr',   'linked_to'),
                }
                for r in rows:
                    try:
                        case_no, etype, eval_ = safe_str(r[0]), safe_str(r[1]), safe_str(r[2])
                        if etype not in evid_type_map: continue
                        label, key, edge_type = evid_type_map[etype]
                        cur.execute(f"""
                            MATCH (c:vt_case {{flnm: '{case_no}'}}),
                                  (e:{label} {{{key}: '{eval_}'}})
                            MERGE (c)-[r:{edge_type} {{evid_grade: 'A', src_tier: 1}}]->(e)
                        """)
                        stats["edges"] += 1
                    except: pass
                conn.commit()
                logger.info(f"  ✓ Case→Evidence 직접 엣지 (TB_INCDNT_EVID): {len(rows)}건")
            except: conn.rollback()

            # ── 6V. V3.7 후처리: pt_cluster 허브, relay_station 탐지, is_anonymous 마킹 ──
            try:
                v37_stats = RdbToGraphService._postprocess_v37(cur, conn, graph_name)
                stats["v37"] = v37_stats
                logger.info(f"  ✓ V3.7 후처리: {v37_stats}")
            except Exception as e:
                logger.warning(f"  ⚠ V3.7 후처리 실패: {e}")
                conn.rollback()

            logger.info(f"✅ V3.2 POLE GDB 변환 완료: {stats}")
            return True, stats

        except Exception as e:
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False, f"V2 ETL 오류: {str(e)}"
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def _postprocess_v37(cur, conn, graph_name: str) -> dict:
        """V3.7 후처리: 그래프 상태 기반으로 pt_cluster 허브, relay_station, is_anonymous 생성/마킹.

        - 6V-1: TB_PETTN_CLSTR의 PETTN_SN 쌍을 union-find로 묶어 pt_cluster + belongs_to_cluster
        - 6V-2: 동일 IMEI 3대+ 공유하는 vt_telno 그룹을 vt_dev(relay_station) + used_in_device로 표현
        - 6V-3: vt_psn 중 name이 빈 값/NULL → is_anonymous=true
        """
        out = {"pt_clusters": 0, "belongs_to_cluster": 0, "relay_stations": 0,
               "used_in_device": 0, "anonymized_psn": 0}
        from app.database import safe_set_graph_path
        from collections import defaultdict

        # 6V-1: TB_PETTN_CLSTR → pt_cluster + belongs_to_cluster (union-find)
        try:
            cur.execute("SELECT PETTN_SN_A, PETTN_SN_B, SIM_SCORE, SIM_BASIS_CD FROM TB_PETTN_CLSTR WHERE SIM_SCORE >= 0.7")
            pairs = cur.fetchall()
            parent = {}
            def find(x):
                while parent.get(x, x) != x:
                    parent[x] = parent.get(parent[x], parent[x])
                    x = parent[x]
                return x
            def union(a, b):
                ra, rb = find(a), find(b)
                if ra != rb:
                    parent[ra] = rb
            for sn_a, sn_b, _, _ in pairs:
                parent.setdefault(sn_a, sn_a); parent.setdefault(sn_b, sn_b)
                union(sn_a, sn_b)
            clusters = defaultdict(list)
            for node in parent:
                clusters[find(node)].append(node)
            scores_by_pair = {(sn_a, sn_b): score for sn_a, sn_b, score, _ in pairs}
            for idx, (root, members) in enumerate(sorted(clusters.items())):
                if len(members) < 2:
                    continue
                cluster_id = f"ptc-auto-{idx:04d}"
                safe_set_graph_path(cur, graph_name)
                cur.execute(f"MERGE (c:pt_cluster {{cluster_id: '{cluster_id}'}}) "
                            f"SET c.cluster_method = 'union_find', c.petition_cnt = {len(members)}, "
                            f"c.status = 'active', c.rec_created = toString(now())")
                out["pt_clusters"] += 1
                for sn in members:
                    sim = max((s for (a, b), s in scores_by_pair.items() if sn in (a, b)), default=0.7)
                    try:
                        cur.execute(f"MATCH (p:vt_petition), (c:pt_cluster {{cluster_id: '{cluster_id}'}}) "
                                    f"WHERE p.raw_id = '{sn}' "
                                    f"MERGE (p)-[r:belongs_to_cluster]->(c) "
                                    f"SET r.sim_score = {sim}, r.rec_created = toString(now())")
                        out["belongs_to_cluster"] += 1
                    except Exception:
                        pass
            conn.commit()
        except Exception as e:
            logger.warning(f"    6V-1 pt_cluster 생성 실패: {e}")
            conn.rollback()

        # 6V-2: relay_station 탐지 (동일 IMEI 3대+ 공유 vt_telno)
        try:
            safe_set_graph_path(cur, graph_name)
            # 1단계: IMEI별 vt_telno 카운트 (count로 임계 필터)
            cur.execute("MATCH (t:vt_telno) WHERE t.imei IS NOT NULL "
                        "WITH t.imei AS imei, count(t) AS cnt "
                        "WHERE cnt >= 3 RETURN imei")
            imeis = [str(r[0]).strip('"') for r in cur.fetchall()]
            for imei_s in imeis:
                if not imei_s or imei_s == "unknown":
                    continue
                # 2단계: 해당 IMEI를 가진 telno 수집
                cur.execute(f"MATCH (t:vt_telno) WHERE t.imei = '{imei_s}' RETURN t.telno")
                telnos = [str(r[0]).strip('"') for r in cur.fetchall()]
                device_id = f"DEV-RELAY-AUTO-{imei_s[-8:] if len(imei_s) >= 8 else imei_s}"
                cur.execute(f"MERGE (d:vt_dev {{device_id: '{device_id}'}}) "
                            f"SET d.dev_type = 'relay_station', d.imei = '{imei_s}', "
                            f"d.detected_by = 'auto_imei_share', d.rec_created = toString(now())")
                out["relay_stations"] += 1
                for telno in telnos:
                    if not telno:
                        continue
                    try:
                        cur.execute(f"MATCH (t:vt_telno {{telno: '{telno}'}}), "
                                    f"(d:vt_dev {{device_id: '{device_id}'}}) "
                                    f"MERGE (t)-[r:used_in_device]->(d) "
                                    f"SET r.source_id = 'auto_imei_share', r.rec_created = toString(now())")
                        out["used_in_device"] += 1
                    except Exception:
                        pass
            conn.commit()
        except Exception as e:
            logger.warning(f"    6V-2 relay_station 탐지 실패: {e}")
            conn.rollback()

        # 6V-3: vt_psn.is_anonymous 마킹 (name이 빈 문자열 또는 NULL)
        try:
            safe_set_graph_path(cur, graph_name)
            cur.execute("MATCH (p:vt_psn) "
                        "WHERE p.name IS NULL OR p.name = '' OR p.korn_flnm IS NULL OR p.korn_flnm = '' "
                        "SET p.is_anonymous = true "
                        "RETURN count(p) AS n")
            row = cur.fetchone()
            out["anonymized_psn"] = int(row[0]) if row and row[0] is not None else 0
            conn.commit()
        except Exception as e:
            logger.warning(f"    6V-3 is_anonymous 마킹 실패: {e}")
            conn.rollback()

        # 6V-4 (V4.0): 모든 노드에 id_format / source_domain / reliability_tier 메타 보정
        try:
            v40_result = RdbToGraphService._postprocess_v40_meta(cur, conn, graph_name, source_domain='investigation')
            out['v40_meta_applied'] = v40_result
        except Exception as e:
            logger.warning(f"    6V-4 V4.0 메타 보정 실패: {e}")
            conn.rollback()

        return out

    @staticmethod
    def _postprocess_v40_meta(cur, conn, graph_name: str, source_domain: str = 'investigation') -> dict:
        """V4.0 표준 메타 일괄 보정 — id_format / source_domain / reliability_tier 누락 노드에 적용.

        라벨별 default 값:
        - id_format:       KICSCrimeDomainOntology.NODE_ID_STANDARD[label]['default_format']
        - source_domain:   파라미터 (CCOP ETL이면 'investigation', OSINT ETL이면 'osint')
        - reliability_tier:1 (investigation) / 4 (osint) / 2-3 (partner)

        Args:
            cur, conn:       DB 연결
            graph_name:      그래프 이름
            source_domain:   'investigation' | 'osint' | 'partner' | 'inference'

        Returns: {label: count} — 라벨별 보정 노드 수
        """
        from app.database import safe_set_graph_path
        from app.middleware.services.ontology_service import KICSCrimeDomainOntology as Onto

        tier_map = {'investigation': 1, 'partner': 2, 'osint': 4, 'inference': 3}
        default_tier = tier_map.get(source_domain, 3)

        out = {}
        safe_set_graph_path(cur, graph_name)

        # 카탈로그의 모든 노드 라벨 순회 — 도메인 사용 가능한 라벨만
        for label in Onto.DOMAIN_USAGE.keys():
            if not Onto.is_applicable(label, source_domain):
                continue

            id_fmt_meta = Onto.get_id_format(label)
            default_fmt = id_fmt_meta.get('default_format', 'plain')

            # 누락 노드만 보정 (already-set 노드는 보존)
            try:
                cur.execute(f"""
                    MATCH (n:{label})
                    WHERE n.id_format IS NULL OR n.source_domain IS NULL OR n.reliability_tier IS NULL
                    SET n.id_format        = COALESCE(n.id_format, '{default_fmt}'),
                        n.source_domain    = COALESCE(n.source_domain, '{source_domain}'),
                        n.reliability_tier = COALESCE(n.reliability_tier, {default_tier})
                    RETURN count(n)
                """)
                row = cur.fetchone()
                cnt = int(row[0]) if row and row[0] is not None else 0
                if cnt > 0:
                    out[label] = cnt
            except Exception as e:
                logger.warning(f"    [V4.0 메타] {label} 보정 실패: {e}")
                conn.rollback()
                safe_set_graph_path(cur, graph_name)

        conn.commit()
        total = sum(out.values())
        logger.info(f"    [V4.0 메타] 보정 완료: 총 {total}개 노드 ({len(out)}개 라벨)")
        return out

    @staticmethod
    def make_node_props_v40(label: str, base_props: dict, source_domain: str = 'investigation',
                             source_id: str = None, reliability_tier: int = None) -> dict:
        """V4.0 표준 메타가 포함된 노드 속성 dict 생성 (새 ETL 코드용 헬퍼).

        사용 예:
            props = RdbToGraphService.make_node_props_v40(
                'vt_bacnt',
                {'account_no': '110-1111-2222', 'bank_cd': 'KB'},
                source_domain='investigation',
                source_id='tccop_official_001',
            )
            cur.execute(f"MERGE (n:vt_bacnt {{account_no: '{actno}'}}) SET n = {props}")
        """
        from app.middleware.services.ontology_service import KICSCrimeDomainOntology as Onto
        from datetime import datetime

        # V4.0 P0 — RDB 도메인 키(DA팀 표준: KICS/OSINT/DIGITAL/EXT) ↔ 코드 도메인 키 매핑
        # Why: DOMAIN_USAGE / tier_map 은 investigation/osint/partner/inference 사용. RDB는
        # KICS/OSINT/DIGITAL/EXT. 매핑 없으면 KICS 데이터가 tier 3 으로 fallback 되어 신뢰도 강등.
        rdb_to_code_domain = {
            'KICS':          'investigation',
            'OSINT':         'osint',
            'DIGITAL':       'partner',
            'EXT':           'partner',
            'INVESTIGATION': 'investigation',
            'PARTNER':       'partner',
            'INFERENCE':     'inference',
        }
        canonical_domain = rdb_to_code_domain.get(
            (source_domain or '').upper(),
            source_domain,
        )

        tier_map = {'investigation': 1, 'partner': 2, 'osint': 4, 'inference': 3}
        if reliability_tier is None:
            reliability_tier = tier_map.get(canonical_domain, 3)

        id_fmt_meta = Onto.get_id_format(label)
        default_fmt = id_fmt_meta.get('default_format', 'plain')

        out = dict(base_props)
        out.setdefault('id_format', default_fmt)
        out.setdefault('source_domain', canonical_domain)
        out.setdefault('reliability_tier', reliability_tier)
        if source_id:
            out.setdefault('source_id', source_id)
        out.setdefault('rec_created', datetime.utcnow().isoformat() + 'Z')
        return out

    # V4.0 P2.1.D — 엣지 메타 표준 키
    _RDB_TO_CODE_DOMAIN = {
        'KICS':          'investigation',
        'OSINT':         'osint',
        'DIGITAL':       'partner',
        'EXT':           'partner',
        'INVESTIGATION': 'investigation',
        'PARTNER':       'partner',
        'INFERENCE':     'inference',
    }

    @staticmethod
    def make_edge_props_v40(edge_type: str, base_props: dict = None,
                             source_domain: str = 'investigation',
                             source_id: str = None,
                             collected_at: str = None) -> dict:
        """V4.0 표준 메타가 포함된 엣지 속성 dict 생성 (Phase 2.1.D).

        엣지는 노드와 달리 id_format / reliability_tier 가 없고,
        source_domain / source_id / collected_at / rec_created 4 메타만 보유.

        사용 예:
            eprops = RdbToGraphService.make_edge_props_v40('holds',
                {'from_dt': '2026-01-01'}, source_domain='KICS')
            cypher = f"... CREATE (a)-[:holds {{{props_str}}}]->(b)"
        """
        from datetime import datetime

        canonical = RdbToGraphService._RDB_TO_CODE_DOMAIN.get(
            (source_domain or '').upper(), source_domain,
        )
        now_iso = datetime.utcnow().isoformat() + 'Z'
        out = dict(base_props or {})
        out.setdefault('source_domain', canonical)
        if source_id:
            out.setdefault('source_id', source_id)
        out.setdefault('collected_at', collected_at or now_iso)
        out.setdefault('rec_created', now_iso)
        # 엣지 타입은 라벨로 표현되므로 속성으로 중복 저장하지 않음 (필요 시 호출자 결정)
        return out

    @staticmethod
    def transfer_case(case_no: str, graph_name: str):
        """특정 사건번호에 속한 노드·엣지만 부분 ETL (수사관 세션 시작 시 호출)

        적재 범위:
          - vt_case (사건 노드)
          - vt_psn  (해당 사건 관련 인물)  → suspect_in/victim_in/witness_in
          - vt_bacnt (피의자 관련 계좌)   → sourced_from vt_src (KICS 공식, tier 1)
          - vt_telno (피의자 관련 전화)   → sourced_from vt_src (KICS 공식, tier 1)
        """
        conn, cur = RdbToGraphService.get_db_connection()
        if not conn:
            return False, "DB 연결 실패"
        stats = {"nodes": 0, "edges": 0}

        def safe_str(v):
            return str(v).replace("'", "''") if v is not None else ''

        try:
            from app.database import safe_set_graph_path
            safe_set_graph_path(cur, graph_name)

            case_s = safe_str(case_no)

            # KICS 공식 출처 노드 MERGE (tier 1 — sourced_from 엣지 생성 기준)
            cur.execute("""
                MERGE (s:vt_src {src_id: 'src-kics-official'})
                SET s.src_name = 'KICS 공식수사자료', s.src_type = 'OFFICIAL',
                    s.reliability_tier = 1, s.type = '출처'
            """)
            conn.commit()

            # ─── 1. 사건 노드 ───────────────────────────────────────
            cur.execute(f"""
                SELECT INCDNT_NO, INCDNT_NM, INCDNT_SE_CD, INCDNT_STTS_CD,
                       OCCUR_DT, CLOSE_DT
                FROM TB_INCDNT_MST
                WHERE INCDNT_NO = '{case_s}'
            """)
            row = cur.fetchone()
            if not row:
                return False, f"사건번호 {case_no} 없음"
            nm, se, st, odt, cdt = safe_str(row[1]), safe_str(row[2]), safe_str(row[3]), safe_str(row[4]), safe_str(row[5])
            props = (f"{{flnm: '{case_s}', case_name: '{nm}', case_type: '{se}', "
                     f"status: '{st}', open_date: '{odt}', close_date: '{cdt}', type: '사건'}}")
            cur.execute(f"MERGE (c:vt_case {{flnm: '{case_s}'}}) SET c = {props}")
            stats["nodes"] += 1
            conn.commit()

            # ─── 2. 관련 인물 + role 엣지 ──────────────────────────
            cur.execute(f"""
                SELECT IP.PRSN_ID, IP.ROLE_CD,
                       P.KORN_FLNM, P.BRTD_YMD, P.GNDR_CD, P.RSDNT_RGST_NO
                FROM TB_INCDNT_PRSN IP
                JOIN TB_PRSN P ON P.PRSN_ID = IP.PRSN_ID
                WHERE IP.INCDNT_NO = '{case_s}'
            """)
            prsn_rows = cur.fetchall()
            prsn_ids = []
            for r in prsn_rows:
                try:
                    pid, role = safe_str(r[0]), safe_str(r[1])
                    nm2, brtd, gndr = safe_str(r[2]), safe_str(r[3]), safe_str(r[4])
                    props_p = (f"{{id: '{pid}', name: '{nm2}', birth_date: '{brtd}', "
                               f"gender: '{gndr}', type: '인물'}}")
                    cur.execute(f"MERGE (p:vt_psn {{id: '{pid}'}}) SET p = {props_p}")
                    stats["nodes"] += 1
                    role_edge = 'suspect_in' if role == 'SUSPECT' else 'victim_in' if role == 'VICTIM' else 'witness_in' if role == 'WITNESS' else 'involves'
                    cur.execute(f"MATCH (c:vt_case {{flnm: '{case_s}'}}), (p:vt_psn {{id: '{pid}'}}) MERGE (p)-[r:{role_edge}]->(c) SET r.evid_grade = 'A', r.src_tier = 1")
                    stats["edges"] += 1
                    # sourced_from: 인물 → vt_src (v3.6 확정: tier 1은 엣지 생성)
                    cur.execute(f"MATCH (s:vt_src {{src_id: 'src-kics-official'}}), (p:vt_psn {{id: '{pid}'}}) MERGE (p)-[:sourced_from {{src_tier: 1, rec_created: toString(datetime())}}]->(s)")
                    stats["edges"] += 1
                    prsn_ids.append(pid)
                except: pass
            conn.commit()

            # ─── 3. 관련 계좌 + sourced_from ──────────────────────
            for pid in prsn_ids:
                pid_s = safe_str(pid)
                # TB_FRD_VCTM_RPT 경유 계좌
                cur.execute(f"""
                    SELECT DISTINCT R.SUSPCT_BACNT_NO
                    FROM TB_FRD_VCTM_RPT R
                    WHERE R.DAM_CN LIKE '사건참조:{case_s}%'
                      AND R.SUSPCT_BACNT_NO IS NOT NULL
                """)
                for br in cur.fetchall():
                    try:
                        actno = safe_str(br[0])
                        cur.execute(f"""
                            SELECT BACNT_NO, BANK_CD, DPSTR_NM, OPNG_DT
                            FROM TB_FIN_BACNT WHERE BACNT_NO = '{actno}'
                        """)
                        ab = cur.fetchone()
                        if ab:
                            aprops = (f"{{account_no: '{actno}', bank_cd: '{safe_str(ab[1])}', "
                                      f"depositor_nm: '{safe_str(ab[2])}', open_date: '{safe_str(ab[3])}', type: '계좌'}}")
                            cur.execute(f"MERGE (a:vt_bacnt {{account_no: '{actno}'}}) SET a = {aprops}")
                            stats["nodes"] += 1
                        cur.execute(f"MATCH (a:vt_bacnt {{account_no: '{actno}'}}), (s:vt_src {{src_id: 'src-kics-official'}}) MERGE (a)-[:sourced_from {{src_tier: 1, rec_created: toString(datetime())}}]->(s)")
                        stats["edges"] += 1
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid_s}'}}), (a:vt_bacnt {{account_no: '{actno}'}}) MERGE (p)-[r:has_account]->(a) SET r.evid_grade = 'B', r.src_tier = 1")
                        stats["edges"] += 1
                    except: pass

            # ─── 4. 관련 전화번호 + sourced_from ──────────────────
                cur.execute(f"""
                    SELECT DISTINCT R.SUSPCT_TELNO
                    FROM TB_FRD_VCTM_RPT R
                    WHERE R.DAM_CN LIKE '사건참조:{case_s}%'
                      AND R.SUSPCT_TELNO IS NOT NULL
                """)
                for tr in cur.fetchall():
                    try:
                        telno = safe_str(tr[0])
                        cur.execute(f"""
                            SELECT TELNO, TELNO_SE_CD, JOIN_DT
                            FROM TB_TELNO_MST WHERE TELNO = '{telno}'
                        """)
                        tb = cur.fetchone()
                        if tb:
                            tprops = (f"{{telno: '{telno}', telno_type: '{safe_str(tb[1])}', "
                                      f"join_date: '{safe_str(tb[2])}', type: '전화번호'}}")
                            cur.execute(f"MERGE (t:vt_telno {{telno: '{telno}'}}) SET t = {tprops}")
                            stats["nodes"] += 1
                        cur.execute(f"MATCH (t:vt_telno {{telno: '{telno}'}}), (s:vt_src {{src_id: 'src-kics-official'}}) MERGE (t)-[:sourced_from {{src_tier: 1, rec_created: toString(datetime())}}]->(s)")
                        stats["edges"] += 1
                        cur.execute(f"MATCH (p:vt_psn {{id: '{pid_s}'}}), (t:vt_telno {{telno: '{telno}'}}) MERGE (p)-[r:owns_phone]->(t) SET r.evid_grade = 'B', r.src_tier = 1")
                        stats["edges"] += 1
                    except: pass

            conn.commit()
            logger.info(f"✅ transfer_case({case_no}) 완료: {stats}")
            return True, stats

        except Exception as e:
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False, f"transfer_case 오류: {str(e)}"
        finally:
            cur.close()
            conn.close()
