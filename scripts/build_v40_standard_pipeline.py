"""
진짜 V4.0 표준화 파이프라인 — L1 raw → L2 V4.0 표준 RDB → L4 그래프
============================================================
격리 스키마: test_v40 (운영 DB tccopdb 내부, public 미영향)
DA팀 V3.7 DDL 작업과 완전 분리.

1단계 — test_v40 스키마 + V4.0 표준 RDB 테이블 생성
  · TB_FRD_VCTM_RPT  (사기 신고)
  · TB_TELNO_MST    (전화번호 마스터)
  · TB_TELNO_SMS_MSG (SMS 메시지)
  · TB_WEB_DMN      (도메인)
  · TB_WEB_MLGN_IDC (악성 지표)
  · TB_DGTL_FILE_INVNT (파일 인벤토리)
  · TB_WEB_PAGE     (수집 페이지)
  모두 V4.0 메타 6컬럼 포함:
    SOURCE_ID / SOURCE_DOMAIN / RELIABILITY_TIER /
    COLLECTED_AT / REC_CREATED / REC_UPDATED

2단계 — L1 raw OSINT (test_ccop_cp) → L2 V4.0 표준 RDB (test_v40) ETL
  · 정규화 + V4.0 메타 자동 부착

3단계 — L2 V4.0 표준 RDB → L4 V4.0 그래프 (ccop_osint_v40_proper)
  · RDB 컬럼 → V4.0 노드 속성 + make_node_props_v40 메타 보정

실행:
  python3 scripts/build_v40_standard_pipeline.py [--drop] [--stage 1|2|3|all]
"""
import argparse, sys, logging, hashlib
from datetime import datetime
sys.path.insert(0, '/Users/iankwon/test/coop_v1.0')
from app import create_app
from app.services.rdb_to_graph_service import RdbToGraphService
from app.database import safe_set_graph_path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('v40_pipeline')
_app = create_app(); _app.app_context().push()

L2_SCHEMA = 'test_v40'
RAW_SCHEMA = 'test_ccop_cp'
GRAPH = 'ccop_osint_v40_proper'


# ============================================================
# 1단계 — V4.0 표준 RDB 스키마 + 테이블 생성
# ============================================================
DDL_V40 = f"""
CREATE SCHEMA IF NOT EXISTS {L2_SCHEMA};

-- 공통 V4.0 메타 6컬럼 매크로용 (각 테이블마다 동일)
-- SOURCE_ID, SOURCE_DOMAIN, RELIABILITY_TIER, COLLECTED_AT, REC_CREATED, REC_UPDATED

-- 1. TB_FRD_VCTM_RPT — 사기 신고
CREATE TABLE IF NOT EXISTS {L2_SCHEMA}.TB_FRD_VCTM_RPT (
    RPT_ID            VARCHAR(64) PRIMARY KEY,
    RPT_DT            DATE,
    CRIME_TYPE        VARCHAR(80),
    VICTIM_TELNO      VARCHAR(20),
    SUSPECT_INFO      VARCHAR(200),
    SUBJECT           VARCHAR(200),
    -- V4.0 메타 6컬럼
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'osint',
    RELIABILITY_TIER  SMALLINT    DEFAULT 4,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 2. TB_TELNO_MST — 전화번호 마스터
CREATE TABLE IF NOT EXISTS {L2_SCHEMA}.TB_TELNO_MST (
    TELNO             VARCHAR(64) PRIMARY KEY,
    HOLDER_NM         VARCHAR(80),
    CARR_CD           VARCHAR(20),
    IS_BURNER         BOOLEAN    DEFAULT FALSE,
    IS_ANONYMOUS      BOOLEAN    DEFAULT FALSE,
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'osint',
    RELIABILITY_TIER  SMALLINT    DEFAULT 4,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 3. TB_TELNO_SMS_MSG — SMS 메시지
CREATE TABLE IF NOT EXISTS {L2_SCHEMA}.TB_TELNO_SMS_MSG (
    MSG_ID            VARCHAR(64) PRIMARY KEY,
    SNDR_TELNO        VARCHAR(64),
    SMS_CONTS         TEXT,
    CONTS_TYP         VARCHAR(20),
    RCV_DT            TIMESTAMP,
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'osint',
    RELIABILITY_TIER  SMALLINT    DEFAULT 4,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 4. TB_WEB_DMN — 도메인
CREATE TABLE IF NOT EXISTS {L2_SCHEMA}.TB_WEB_DMN (
    DMN_ID            VARCHAR(64) PRIMARY KEY,
    URL               VARCHAR(500),
    SITE_NM           VARCHAR(200),
    SITE_TYPE         VARCHAR(40),
    IS_MALICIOUS      BOOLEAN    DEFAULT FALSE,
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'osint',
    RELIABILITY_TIER  SMALLINT    DEFAULT 4,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 5. TB_WEB_MLGN_IDC — 악성 지표 (Malicious Indicator)
CREATE TABLE IF NOT EXISTS {L2_SCHEMA}.TB_WEB_MLGN_IDC (
    IDC_ID            VARCHAR(64) PRIMARY KEY,
    DMN_NM            VARCHAR(200),
    SIGN_KYWD         VARCHAR(200),
    MALICIOUS_URL     VARCHAR(500),
    SRC_IP            VARCHAR(45),
    CHCK_DT           TIMESTAMP,
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'osint',
    RELIABILITY_TIER  SMALLINT    DEFAULT 4,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 6. TB_DGTL_FILE_INVNT — 디지털 파일 인벤토리
CREATE TABLE IF NOT EXISTS {L2_SCHEMA}.TB_DGTL_FILE_INVNT (
    FILE_ID           VARCHAR(64) PRIMARY KEY,
    FILE_NM           VARCHAR(200),
    FILE_EXTN_NM      VARCHAR(20),
    FILE_PATH         VARCHAR(500),
    FILE_URL          VARCHAR(500),
    HASH_VAL          VARCHAR(128),
    MIME_TYPE         VARCHAR(50),
    PARENT_PAGE_ID    VARCHAR(64),  -- TB_WEB_PAGE 참조
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'osint',
    RELIABILITY_TIER  SMALLINT    DEFAULT 4,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 7. TB_WEB_PAGE — 수집 페이지
CREATE TABLE IF NOT EXISTS {L2_SCHEMA}.TB_WEB_PAGE (
    PAGE_ID           VARCHAR(64) PRIMARY KEY,
    URL               VARCHAR(500),
    SITE_NM           VARCHAR(200),
    SITE_TYPE         VARCHAR(40),
    HTML_TTL          VARCHAR(500),
    CLCT_DT           TIMESTAMP,
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'osint',
    RELIABILITY_TIER  SMALLINT    DEFAULT 4,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS IX_FRD_RPT_DT ON {L2_SCHEMA}.TB_FRD_VCTM_RPT (RPT_DT);
CREATE INDEX IF NOT EXISTS IX_SMS_SNDR ON {L2_SCHEMA}.TB_TELNO_SMS_MSG (SNDR_TELNO);
CREATE INDEX IF NOT EXISTS IX_DMN_TYPE ON {L2_SCHEMA}.TB_WEB_DMN (SITE_TYPE);
CREATE INDEX IF NOT EXISTS IX_MLGN_DMN ON {L2_SCHEMA}.TB_WEB_MLGN_IDC (DMN_NM);
CREATE INDEX IF NOT EXISTS IX_FILE_PARENT ON {L2_SCHEMA}.TB_DGTL_FILE_INVNT (PARENT_PAGE_ID);
"""


def stage_1_create_schema(conn, cur):
    log.info("="*60)
    log.info(f"[Stage 1/3] V4.0 표준 스키마 생성: {L2_SCHEMA}")
    log.info("="*60)
    for stmt in DDL_V40.split(';'):
        s = stmt.strip()
        if not s: continue
        try:
            cur.execute(s + ';')
        except Exception as e:
            log.warning(f"  DDL 일부 실패: {str(e)[:80]}")
    # 테이블 확인
    cur.execute(f"""SELECT table_name FROM information_schema.tables
                    WHERE table_schema='{L2_SCHEMA}' AND table_name LIKE 'tb_%'
                    ORDER BY table_name;""")
    tables = [r[0] for r in cur.fetchall()]
    log.info(f"  생성된 테이블 {len(tables)}개:")
    for t in tables: log.info(f"    - {t}")
    return tables


# ============================================================
# 2단계 — L1 raw → L2 V4.0 표준 RDB ETL
# ============================================================
def stage_2_etl(conn, cur, args):
    log.info("="*60)
    log.info(f"[Stage 2/3] L1 raw (test_ccop_cp) → L2 V4.0 표준 ({L2_SCHEMA}) ETL")
    log.info("="*60)
    stats = {}

    def insert_many(table_l2, rows, columns):
        """배치 INSERT 헬퍼."""
        if not rows: return 0
        placeholders = ','.join(['%s']*len(columns))
        cols = ','.join(columns)
        sql = f"INSERT INTO {L2_SCHEMA}.{table_l2} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        ok = 0
        for r in rows:
            try:
                cur.execute(sql, r); ok += cur.rowcount
            except Exception as e:
                if ok < 3: log.warning(f"    insert fail: {str(e)[:80]}")
        return ok

    # ────────────────────────────────────────────────────────
    # 2.1 tb_the_cheat_fraud_m → TB_FRD_VCTM_RPT
    # ────────────────────────────────────────────────────────
    log.info("[2.1] tb_the_cheat_fraud_m → TB_FRD_VCTM_RPT")
    cur.execute(f"SET search_path = {RAW_SCHEMA}, public;")
    cur.execute(f"""SELECT id, rpt_dt, intg_dt
                    FROM {RAW_SCHEMA}.tb_the_cheat_fraud_m
                    LIMIT {args.sample_fraud}""")
    rows = []
    for r in cur.fetchall():
        rid = str(r[0]); rpt_dt = r[1]; intg_dt = r[2]
        rows.append((
            f"OSINT-FRAUD-{rid}",      # RPT_ID
            rpt_dt,                    # RPT_DT
            'OSINT사기',                # CRIME_TYPE
            None,                      # VICTIM_TELNO
            f"thecheat_id={rid}",      # SUSPECT_INFO
            f"OSINT 사기 신고 #{rid}",  # SUBJECT
            rid,                       # SOURCE_ID
            'osint', 4, intg_dt        # V4.0 메타
        ))
    n = insert_many('TB_FRD_VCTM_RPT',
                    rows,
                    ['RPT_ID','RPT_DT','CRIME_TYPE','VICTIM_TELNO','SUSPECT_INFO',
                     'SUBJECT','SOURCE_ID','SOURCE_DOMAIN','RELIABILITY_TIER','COLLECTED_AT'])
    stats['TB_FRD_VCTM_RPT'] = n
    log.info(f"  → {n} 행 적재")

    # ────────────────────────────────────────────────────────
    # 2.2 tb_the_cheat_spam_sms_m → TB_TELNO_SMS_MSG + TB_TELNO_MST
    # ────────────────────────────────────────────────────────
    log.info("[2.2] tb_the_cheat_spam_sms_m → TB_TELNO_SMS_MSG + TB_TELNO_MST")
    cur.execute(f"""SELECT id, conts_typ, sms_conts, sndr_telno, rcv_dt, intg_dt
                    FROM {RAW_SCHEMA}.tb_the_cheat_spam_sms_m
                    LIMIT {args.sample_spam}""")
    sms_rows = []; tel_rows = []; seen_tel = set()
    for r in cur.fetchall():
        mid, ctyp, conts, sndr, rcv_dt, intg_dt = r
        mid_v = f"OSINT-SMS-{mid}"
        sndr_telno = f"SPAM-HASH-{(sndr or '')[:16]}" if sndr else None
        sms_rows.append((mid_v, sndr_telno, (conts or '')[:1000], ctyp,
                         rcv_dt, str(mid), 'osint', 4, intg_dt))
        if sndr_telno and sndr_telno not in seen_tel:
            seen_tel.add(sndr_telno)
            tel_rows.append((sndr_telno, 'SPAM_ANON', 'UNK', True, True,
                             sndr[:32] if sndr else None, 'osint', 4, intg_dt))
    n1 = insert_many('TB_TELNO_SMS_MSG',
                     sms_rows,
                     ['MSG_ID','SNDR_TELNO','SMS_CONTS','CONTS_TYP','RCV_DT',
                      'SOURCE_ID','SOURCE_DOMAIN','RELIABILITY_TIER','COLLECTED_AT'])
    n2 = insert_many('TB_TELNO_MST',
                     tel_rows,
                     ['TELNO','HOLDER_NM','CARR_CD','IS_BURNER','IS_ANONYMOUS',
                      'SOURCE_ID','SOURCE_DOMAIN','RELIABILITY_TIER','COLLECTED_AT'])
    stats['TB_TELNO_SMS_MSG'] = n1; stats['TB_TELNO_MST'] = n2
    log.info(f"  → SMS {n1} / 발신번호 {n2}")

    # ────────────────────────────────────────────────────────
    # 2.3 tb_dmn → TB_WEB_DMN
    # ────────────────────────────────────────────────────────
    log.info("[2.3] tb_dmn → TB_WEB_DMN")
    cur.execute(f"""SELECT dmn_id, url, site_nm, site_type, crt_dt
                    FROM {RAW_SCHEMA}.tb_dmn""")
    rows = [(r[0], r[1], r[2], r[3], r[3] == '유해사이트',
             r[0], 'osint', 4, r[4]) for r in cur.fetchall()]
    n = insert_many('TB_WEB_DMN', rows,
                    ['DMN_ID','URL','SITE_NM','SITE_TYPE','IS_MALICIOUS',
                     'SOURCE_ID','SOURCE_DOMAIN','RELIABILITY_TIER','COLLECTED_AT'])
    stats['TB_WEB_DMN'] = n
    log.info(f"  → {n} 행")

    # ────────────────────────────────────────────────────────
    # 2.4 tb_the_cheat_malicious_url_m → TB_WEB_MLGN_IDC + TB_WEB_DMN
    # ────────────────────────────────────────────────────────
    log.info("[2.4] tb_the_cheat_malicious_url_m → TB_WEB_MLGN_IDC + TB_WEB_DMN")
    cur.execute(f"""SELECT id, dmn_nm, sign_kywd, ip, chck_dt, screenshot_url, intg_dt
                    FROM {RAW_SCHEMA}.tb_the_cheat_malicious_url_m
                    LIMIT {args.sample_mlgn}""")
    idc_rows = []; dmn_extra = []; seen_dmn = set()
    for r in cur.fetchall():
        rid, dmn_nm, sign, ip, chck, scrn, intg = r
        idc_rows.append((
            f"OSINT-MLGN-{rid}",
            dmn_nm, (sign or '')[:200], scrn, ip, chck,
            str(rid), 'osint', 4, intg
        ))
        if dmn_nm and dmn_nm not in seen_dmn:
            seen_dmn.add(dmn_nm)
            dmn_id = f"OSINT-DMN-{hashlib.md5(dmn_nm.encode()).hexdigest()[:12]}"
            dmn_extra.append((dmn_id, f"http://{dmn_nm}", dmn_nm, '유해사이트',
                              True, str(rid), 'osint', 4, intg))
    n1 = insert_many('TB_WEB_MLGN_IDC', idc_rows,
                     ['IDC_ID','DMN_NM','SIGN_KYWD','MALICIOUS_URL','SRC_IP','CHCK_DT',
                      'SOURCE_ID','SOURCE_DOMAIN','RELIABILITY_TIER','COLLECTED_AT'])
    n2 = insert_many('TB_WEB_DMN', dmn_extra,
                     ['DMN_ID','URL','SITE_NM','SITE_TYPE','IS_MALICIOUS',
                      'SOURCE_ID','SOURCE_DOMAIN','RELIABILITY_TIER','COLLECTED_AT'])
    stats['TB_WEB_MLGN_IDC'] = n1
    stats['TB_WEB_DMN'] = stats.get('TB_WEB_DMN', 0) + n2
    log.info(f"  → 악성지표 {n1} / 도메인 +{n2}")

    # ────────────────────────────────────────────────────────
    # 2.5 tb_clct_page → TB_WEB_PAGE
    # ────────────────────────────────────────────────────────
    log.info("[2.5] tb_clct_page → TB_WEB_PAGE")
    cur.execute(f"""SELECT clct_page_id, url, site_nm, site_type, html_ttl, clct_dt
                    FROM {RAW_SCHEMA}.tb_clct_page
                    LIMIT {args.sample_page}""")
    rows = [(r[0], r[1], r[2], r[3], (r[4] or '')[:500], r[5],
             r[0], 'osint', 4, r[5]) for r in cur.fetchall()]
    n = insert_many('TB_WEB_PAGE', rows,
                    ['PAGE_ID','URL','SITE_NM','SITE_TYPE','HTML_TTL','CLCT_DT',
                     'SOURCE_ID','SOURCE_DOMAIN','RELIABILITY_TIER','COLLECTED_AT'])
    stats['TB_WEB_PAGE'] = n
    log.info(f"  → {n} 행")

    # ────────────────────────────────────────────────────────
    # 2.6 tb_atch_file → TB_DGTL_FILE_INVNT
    # ────────────────────────────────────────────────────────
    log.info("[2.6] tb_atch_file → TB_DGTL_FILE_INVNT")
    cur.execute(f"""SELECT atch_file_id, atch_file_nm, atch_file_extn_nm, atch_file_path,
                           atch_file_url, atch_file_hash_cd, clct_page_id
                    FROM {RAW_SCHEMA}.tb_atch_file
                    LIMIT {args.sample_file}""")
    rows = []
    for r in cur.fetchall():
        rows.append((r[0], r[1], r[2], r[3], r[4], r[5],
                     r[2] or 'unknown', r[6],   # MIME_TYPE, PARENT_PAGE_ID
                     r[0], 'osint', 4, datetime.utcnow()))
    n = insert_many('TB_DGTL_FILE_INVNT', rows,
                    ['FILE_ID','FILE_NM','FILE_EXTN_NM','FILE_PATH','FILE_URL',
                     'HASH_VAL','MIME_TYPE','PARENT_PAGE_ID',
                     'SOURCE_ID','SOURCE_DOMAIN','RELIABILITY_TIER','COLLECTED_AT'])
    stats['TB_DGTL_FILE_INVNT'] = n
    log.info(f"  → {n} 행")

    log.info("─"*60)
    log.info(f"  ETL 완료 — V4.0 표준 RDB ({L2_SCHEMA}) 적재 통계:")
    total = 0
    for t, c in stats.items():
        log.info(f"    {t:25s} {c}")
        total += c
    log.info(f"  총 적재: {total} 행")
    return stats


# ============================================================
# 3단계 — L2 V4.0 표준 RDB → L4 V4.0 그래프
# ============================================================
def stage_3_to_graph(conn, cur, args):
    log.info("="*60)
    log.info(f"[Stage 3/3] L2 RDB ({L2_SCHEMA}) → L4 V4.0 그래프 ({GRAPH})")
    log.info("="*60)

    # 그래프 초기화 (set 전에 CREATE 필요)
    if args.drop:
        try: cur.execute(f"DROP GRAPH IF EXISTS {GRAPH} CASCADE;")
        except: pass
    try: cur.execute(f"CREATE GRAPH IF NOT EXISTS {GRAPH};")
    except: pass
    safe_set_graph_path(cur, GRAPH)

    # 라벨 사전 선언
    for v in ['vt_site','vt_petition','vt_msg','vt_telno','vt_file','vt_psn','site_cluster']:
        try: cur.execute(f"CREATE VLABEL IF NOT EXISTS {v};")
        except: pass
    for e in ['hosts','contains_file','sent_msg','belongs_to_campaign','reports']:
        try: cur.execute(f"CREATE ELABEL IF NOT EXISTS {e};")
        except: pass

    stats = {'nodes': 0, 'edges': 0, 'by_label': {}, 'by_edge': {}}

    def props_str(d):
        parts = []
        for k, v in d.items():
            if v is None or v == '': continue
            if isinstance(v, bool): parts.append(f"{k}: {'true' if v else 'false'}")
            elif isinstance(v, (int, float)): parts.append(f"{k}: {v}")
            else:
                s = str(v).replace("'", "''")[:200]
                parts.append(f"{k}: '{s}'")
        return ', '.join(parts)

    def graph_create_node(label, base_props, source_id):
        p = RdbToGraphService.make_node_props_v40(
            label, base_props, source_domain='osint', source_id=source_id
        )
        try:
            cur.execute(f"CREATE (n:{label} {{{props_str(p)}}})")
            stats['nodes'] += 1
            stats['by_label'][label] = stats['by_label'].get(label, 0) + 1
            return True
        except Exception as e:
            safe_set_graph_path(cur, GRAPH)
            return False

    def graph_create_edge(src_label, src_key, src_val, etype, tgt_label, tgt_key, tgt_val):
        ep = RdbToGraphService.make_edge_props_v40(etype, {}, source_domain='osint')
        try:
            cur.execute(
                f"MATCH (a:{src_label} {{{src_key}: '{src_val}'}}), "
                f"(b:{tgt_label} {{{tgt_key}: '{tgt_val}'}}) "
                f"CREATE (a)-[:{etype} {{{props_str(ep)}}}]->(b)"
            )
            stats['edges'] += 1
            stats['by_edge'][etype] = stats['by_edge'].get(etype, 0) + 1
            return True
        except Exception:
            safe_set_graph_path(cur, GRAPH)
            return False

    # ────────────────────────────────────────────────────────
    # 3.1 TB_WEB_DMN → vt_site
    # ────────────────────────────────────────────────────────
    log.info("[3.1] TB_WEB_DMN → vt_site")
    cur.execute(f"SELECT dmn_id, url, site_nm, site_type, is_malicious, source_id FROM {L2_SCHEMA}.TB_WEB_DMN")
    for dmn_id, url, site_nm, site_type, is_mal, sid in cur.fetchall():
        graph_create_node('vt_site', {
            'site_id': dmn_id, 'url_addr': url, 'domain': site_nm,
            'site_type': site_type, 'is_malicious': bool(is_mal),
        }, source_id=sid)

    # ────────────────────────────────────────────────────────
    # 3.2 TB_WEB_MLGN_IDC → vt_site (악성 지표)
    # ────────────────────────────────────────────────────────
    log.info("[3.2] TB_WEB_MLGN_IDC → vt_site (악성)")
    cur.execute(f"SELECT idc_id, dmn_nm, sign_kywd, malicious_url, src_ip, source_id FROM {L2_SCHEMA}.TB_WEB_MLGN_IDC")
    for idc_id, dmn_nm, sign, url, ip, sid in cur.fetchall():
        graph_create_node('vt_site', {
            'site_id': idc_id, 'url_addr': url, 'domain': dmn_nm,
            'sign_kywd': sign, 'src_ip': ip, 'is_malicious': True,
        }, source_id=sid)

    # ────────────────────────────────────────────────────────
    # 3.3 TB_WEB_PAGE → vt_site
    # ────────────────────────────────────────────────────────
    log.info("[3.3] TB_WEB_PAGE → vt_site (수집페이지)")
    cur.execute(f"SELECT page_id, url, site_nm, site_type, html_ttl, source_id FROM {L2_SCHEMA}.TB_WEB_PAGE")
    for pid, url, site_nm, st, ttl, sid in cur.fetchall():
        graph_create_node('vt_site', {
            'site_id': pid, 'url_addr': url, 'domain': site_nm,
            'site_type': st, 'title': ttl,
        }, source_id=sid)

    # ────────────────────────────────────────────────────────
    # 3.4 TB_FRD_VCTM_RPT → vt_petition
    # ────────────────────────────────────────────────────────
    log.info("[3.4] TB_FRD_VCTM_RPT → vt_petition")
    cur.execute(f"SELECT rpt_id, rpt_dt, crime_type, subject, source_id FROM {L2_SCHEMA}.TB_FRD_VCTM_RPT")
    for rid, dt, ct, sub, sid in cur.fetchall():
        graph_create_node('vt_petition', {
            'petition_id': rid, 'filed_at': str(dt) if dt else '',
            'crime_type': ct, 'subject': sub,
        }, source_id=sid)

    # ────────────────────────────────────────────────────────
    # 3.5 TB_TELNO_MST → vt_telno
    # ────────────────────────────────────────────────────────
    log.info("[3.5] TB_TELNO_MST → vt_telno")
    cur.execute(f"SELECT telno, holder_nm, carr_cd, is_burner, is_anonymous, source_id FROM {L2_SCHEMA}.TB_TELNO_MST")
    for tel, hn, cc, ib, ia, sid in cur.fetchall():
        graph_create_node('vt_telno', {
            'telno': tel, 'holder_nm': hn, 'carr_cd': cc,
            'is_burner': bool(ib), 'is_anonymous': bool(ia),
        }, source_id=sid)

    # ────────────────────────────────────────────────────────
    # 3.6 TB_TELNO_SMS_MSG → vt_msg + sent_msg 엣지
    # ────────────────────────────────────────────────────────
    log.info("[3.6] TB_TELNO_SMS_MSG → vt_msg + sent_msg 엣지")
    cur.execute(f"""SELECT msg_id, sndr_telno, sms_conts, conts_typ, rcv_dt, source_id
                    FROM {L2_SCHEMA}.TB_TELNO_SMS_MSG""")
    for mid, sndr, conts, ct, rcv, sid in cur.fetchall():
        graph_create_node('vt_msg', {
            'msg_id': mid, 'msg_type': ct,
            'content': (conts or '')[:200], 'occurred_at': str(rcv) if rcv else '',
        }, source_id=sid)
        if sndr:
            graph_create_edge('vt_telno', 'telno', sndr, 'sent_msg',
                              'vt_msg', 'msg_id', mid)

    # ────────────────────────────────────────────────────────
    # 3.7 TB_DGTL_FILE_INVNT → vt_file + contains_file 엣지
    # ────────────────────────────────────────────────────────
    log.info("[3.7] TB_DGTL_FILE_INVNT → vt_file + contains_file 엣지")
    cur.execute(f"""SELECT file_id, file_nm, file_extn_nm, file_path, file_url,
                           hash_val, mime_type, parent_page_id, source_id
                    FROM {L2_SCHEMA}.TB_DGTL_FILE_INVNT""")
    for fid, fnm, ext, fp, fu, hv, mt, ppid, sid in cur.fetchall():
        graph_create_node('vt_file', {
            'file_id': fid, 'file_nm': fnm, 'file_extn': ext,
            'file_path': fp, 'file_url': fu, 'hash_val': hv,
            'mime_type': mt,
        }, source_id=sid)
        if ppid:
            graph_create_edge('vt_site', 'site_id', ppid, 'contains_file',
                              'vt_file', 'file_id', fid)

    log.info("─"*60)
    log.info(f"  L4 그래프 적재 완료")
    log.info(f"    노드 {stats['nodes']} / 엣지 {stats['edges']}")
    for k, v in sorted(stats['by_label'].items(), key=lambda x: -x[1]):
        log.info(f"    {k:18s} {v}")
    for k, v in sorted(stats['by_edge'].items(), key=lambda x: -x[1]):
        log.info(f"    edge {k:18s} {v}")
    return stats


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--drop', action='store_true', help='기존 그래프 삭제 후 재생성')
    parser.add_argument('--stage', default='all', choices=['1','2','3','all'])
    parser.add_argument('--sample-fraud', type=int, default=1000)
    parser.add_argument('--sample-spam',  type=int, default=1000)
    parser.add_argument('--sample-mlgn',  type=int, default=2000)
    parser.add_argument('--sample-file',  type=int, default=500)
    parser.add_argument('--sample-page',  type=int, default=500)
    args = parser.parse_args()

    conn, cur = RdbToGraphService.get_db_connection()
    if not conn: log.error("DB 연결 실패"); sys.exit(1)
    conn.autocommit = True

    if args.stage in ('1','all'):
        stage_1_create_schema(conn, cur)
    if args.stage in ('2','all'):
        stage_2_etl(conn, cur, args)
    if args.stage in ('3','all'):
        stage_3_to_graph(conn, cur, args)

    log.info("="*60)
    log.info("✅ V4.0 표준화 파이프라인 완료")
    log.info(f"   L2 RDB: tccopdb.{L2_SCHEMA}.TB_*  (격리 스키마)")
    log.info(f"   L4 그래프: {GRAPH}")
    log.info("="*60)
    log.info("브라우저: 그래프 셀렉터 → ccop_osint_v40_proper")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
