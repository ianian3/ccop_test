"""
test_ccop_cp 스키마 (OSINT 표준화) → V4.0 그래프 적재
============================================================
대상 그래프: ccop_osint_demo
V4.0 메타: source_domain='osint', reliability_tier=4 (T4 웹수집)

표준화 테이블 → V4.0 노드 매핑:
  tb_the_cheat_malicious_url_m  (10K 전체)     → vt_site (is_malicious)
  tb_the_cheat_fraud_m          (1K 샘플)      → vt_petition + vt_psn
  tb_the_cheat_spam_sms_m       (1K 샘플)      → vt_msg + vt_telno
  tb_dmn                        (121 전체)     → vt_site
  tb_kywd                       (5 전체)       → site_cluster 키
  tb_dmn_kywd                   (35 전체)      → belongs_to_campaign
  tb_atch_file                  (500 샘플)     → vt_file
  tb_clct_page                  (500 샘플)     → vt_site

V3.7 신규: tb_kywd 그룹별로 site_cluster 자동 생성

실행:
  python3 scripts/build_osint_v40_graph.py [--drop] [--full]
"""
import argparse, sys, logging
from datetime import datetime

sys.path.insert(0, '/Users/iankwon/test/coop_v1.0')
from app import create_app
from app.services.rdb_to_graph_service import RdbToGraphService
from app.database import safe_set_graph_path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('osint_seeder')
_app = create_app(); _app.app_context().push()

GRAPH = 'ccop_osint_demo'
SCHEMA = 'test_ccop_cp'


def cypher_escape(v):
    if v is None or v == '': return "''"
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, float)): return str(v)
    if isinstance(v, datetime): return f"'{v.isoformat()}'"
    s = str(v).replace("'", "''")[:200]  # truncate long strings
    return f"'{s}'"


def props_str(d):
    return ', '.join(f"{k}: {cypher_escape(v)}" for k, v in d.items() if v not in (None, ''))


def reset_graph(conn, cur, drop=False):
    if drop:
        try: cur.execute(f"DROP GRAPH IF EXISTS {GRAPH} CASCADE;")
        except Exception as e: log.warning(f"DROP 실패(무시): {e}")
    try: cur.execute(f"CREATE GRAPH IF NOT EXISTS {GRAPH};")
    except Exception: pass
    safe_set_graph_path(cur, GRAPH)

    # VLABEL/ELABEL 사전 선언
    for v in ['vt_site', 'vt_petition', 'vt_psn', 'vt_msg', 'vt_telno',
              'vt_file', 'site_cluster']:
        try: cur.execute(f"CREATE VLABEL IF NOT EXISTS {v};")
        except: pass
    for e in ['belongs_to_campaign', 'contains_file', 'sent_msg', 'reports',
              'mentions', 'sourced_from', 'hosts']:
        try: cur.execute(f"CREATE ELABEL IF NOT EXISTS {e};")
        except: pass
    log.info(f"graph_path='{GRAPH}' (vlabel 7 / elabel 7 선언)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--drop', action='store_true', help='기존 그래프 삭제')
    parser.add_argument('--full', action='store_true', help='샘플링 없이 전체 적재')
    parser.add_argument('--sample-fraud', type=int, default=1000)
    parser.add_argument('--sample-spam', type=int, default=1000)
    parser.add_argument('--sample-file', type=int, default=500)
    parser.add_argument('--sample-page', type=int, default=500)
    args = parser.parse_args()

    log.info("="*60)
    log.info(f"OSINT (test_ccop_cp) → V4.0 그래프 적재 (target: {GRAPH})")
    log.info("="*60)

    conn, cur = RdbToGraphService.get_db_connection()
    if not conn: log.error("DB 연결 실패"); sys.exit(1)
    conn.autocommit = True   # 트랜잭션 시작 전 설정 필수
    cur.execute(f"SET search_path = {SCHEMA}, public;")
    reset_graph(conn, cur, drop=args.drop)
    safe_set_graph_path(cur, GRAPH)

    stats = {'nodes': 0, 'edges': 0, 'by_label': {}, 'by_edge': {}}

    def add_node(label, base, source_domain='osint', source_id=None):
        p = RdbToGraphService.make_node_props_v40(label, base,
                                                   source_domain=source_domain,
                                                   source_id=source_id)
        try:
            cur.execute(f"CREATE (n:{label} {{{props_str(p)}}})")
            stats['nodes'] += 1
            stats['by_label'][label] = stats['by_label'].get(label, 0) + 1
            return True
        except Exception as e:
            log.warning(f"  노드 실패 {label}: {str(e)[:100]}")
            safe_set_graph_path(cur, GRAPH)
            return False

    def add_edge(src_label, src_key, src_val, etype, tgt_label, tgt_key, tgt_val,
                 base=None, source_domain='osint'):
        ep = RdbToGraphService.make_edge_props_v40(etype, base or {},
                                                    source_domain=source_domain)
        try:
            cur.execute(
                f"MATCH (a:{src_label} {{{src_key}: {cypher_escape(src_val)}}}), "
                f"(b:{tgt_label} {{{tgt_key}: {cypher_escape(tgt_val)}}}) "
                f"CREATE (a)-[:{etype} {{{props_str(ep)}}}]->(b)"
            )
            stats['edges'] += 1
            stats['by_edge'][etype] = stats['by_edge'].get(etype, 0) + 1
            return True
        except Exception:
            safe_set_graph_path(cur, GRAPH)
            return False

    def fetch_data(table, sample_n=None):
        cur.execute(f"SET search_path = {SCHEMA}, public;")
        sql = f'SELECT * FROM "{SCHEMA}"."{table}"'
        if sample_n and not args.full:
            sql += f' LIMIT {sample_n}'
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        safe_set_graph_path(cur, GRAPH)
        return cols, rows

    # ════════════════════════════════════════════════════════════════════
    # 1. tb_dmn → vt_site (도메인 마스터)
    # ════════════════════════════════════════════════════════════════════
    log.info("[1/8] tb_dmn → vt_site (도메인)")
    cols, rows = fetch_data('tb_dmn')
    for r in rows:
        d = dict(zip(cols, r))
        if not d.get('dmn_id'): continue
        add_node('vt_site', {
            'site_id':   d['dmn_id'],
            'url_addr':  d.get('url', ''),
            'domain':    d.get('site_nm', ''),
            'site_type': d.get('site_type', ''),
            'is_malicious': d.get('site_type') == '유해사이트',
        }, source_id=d['dmn_id'])

    # ════════════════════════════════════════════════════════════════════
    # 2. tb_kywd → site_cluster 자동 생성 (V3.7 신규)
    # ════════════════════════════════════════════════════════════════════
    log.info("[2/8] tb_kywd → site_cluster (V3.7 신규)")
    cols, rows = fetch_data('tb_kywd')
    for r in rows:
        d = dict(zip(cols, r))
        kwd_id = d.get('kywd_id'); name = d.get('kywd_nm', '')
        if not kwd_id: continue
        add_node('site_cluster', {
            'cluster_id':   f"OSINT-KWD-{name}",
            'cluster_nm':   f"키워드 '{name}' 군집",
            'kywd_id':      kwd_id,
            'kywd_nm':      name,
            'simhash64':    0,  # OSINT 키워드 군집은 SimHash 없음
            'member_cnt':   0,
        }, source_id=kwd_id)

    # ════════════════════════════════════════════════════════════════════
    # 3. tb_dmn_kywd → belongs_to_campaign 엣지
    # ════════════════════════════════════════════════════════════════════
    log.info("[3/8] tb_dmn_kywd → belongs_to_campaign 엣지")
    # 키워드 id → name 매핑
    cur.execute(f"SET search_path = {SCHEMA}, public;")
    cur.execute(f'SELECT kywd_id, kywd_nm FROM "{SCHEMA}".tb_kywd;')
    kwd_map = {k: n for k, n in cur.fetchall()}
    safe_set_graph_path(cur, GRAPH)

    cols, rows = fetch_data('tb_dmn_kywd')
    for r in rows:
        d = dict(zip(cols, r))
        kwd_id = d.get('kywd_id'); dmn_id = d.get('dmn_id')
        if not kwd_id or not dmn_id: continue
        kwd_nm = kwd_map.get(kwd_id, '')
        cluster_id = f"OSINT-KWD-{kwd_nm}"
        add_edge('vt_site', 'site_id', dmn_id, 'belongs_to_campaign',
                 'site_cluster', 'cluster_id', cluster_id)

    # ════════════════════════════════════════════════════════════════════
    # 4. tb_the_cheat_malicious_url_m → vt_site (악성 URL)
    # ════════════════════════════════════════════════════════════════════
    log.info("[4/8] tb_the_cheat_malicious_url_m → vt_site (악성 URL)")
    cols, rows = fetch_data('tb_the_cheat_malicious_url_m',
                            sample_n=None if args.full else 2000)
    for r in rows:
        d = dict(zip(cols, r))
        if not d.get('id'): continue
        site_id = f"THECHEAT-URL-{d['id']}"
        add_node('vt_site', {
            'site_id':      site_id,
            'url_addr':     d.get('screenshot_url', ''),
            'domain':       d.get('dmn_nm', ''),
            'sign_kywd':    d.get('sign_kywd', ''),
            'is_malicious': True,
            'src_ip':       d.get('ip', ''),
        }, source_id=str(d['id']))

    # ════════════════════════════════════════════════════════════════════
    # 5. tb_the_cheat_spam_sms_m → vt_msg + vt_telno
    # ════════════════════════════════════════════════════════════════════
    log.info("[5/8] tb_the_cheat_spam_sms_m → vt_msg + vt_telno (스팸)")
    cols, rows = fetch_data('tb_the_cheat_spam_sms_m', sample_n=args.sample_spam)
    seen_telnos = set()
    for r in rows:
        d = dict(zip(cols, r))
        if not d.get('id'): continue
        msg_id = f"OSINT-SMS-{d['id']}"
        add_node('vt_msg', {
            'msg_id':    msg_id,
            'msg_type':  d.get('conts_typ', ''),
            'content':   (d.get('sms_conts', '') or '')[:200],
            'occurred_at': str(d.get('rcv_dt', '')),
        }, source_id=str(d['id']))
        # 발신 전화번호 (hash 형태)
        sender = d.get('sndr_telno')
        if sender:
            tel = f"SPAM-HASH-{sender[:16]}"
            if tel not in seen_telnos:
                seen_telnos.add(tel)
                add_node('vt_telno', {
                    'telno':     tel,
                    'holder_nm': 'SPAM_ANON',
                    'carr_cd':   'UNK',
                    'is_burner': True,
                    'is_anonymous': True,
                })
            add_edge('vt_telno','telno',tel, 'sent_msg', 'vt_msg','msg_id',msg_id)

    # ════════════════════════════════════════════════════════════════════
    # 6. tb_the_cheat_fraud_m → vt_petition + vt_psn (사기 신고)
    # ════════════════════════════════════════════════════════════════════
    log.info("[6/8] tb_the_cheat_fraud_m → vt_petition (사기 신고)")
    cols, rows = fetch_data('tb_the_cheat_fraud_m', sample_n=args.sample_fraud)
    for r in rows:
        d = dict(zip(cols, r))
        pid = d.get('id') if 'id' in d else None
        if pid is None: continue
        pet_id = f"OSINT-FRAUD-{pid}"
        # 가능한 컬럼 추출 (any)
        base = {'petition_id': pet_id, 'subject': 'OSINT 사기 신고'}
        for k in ('crime_type','fraud_type','damage_amount','victim_telno','reporter','rpt_dt'):
            if k in d and d[k] is not None: base[k] = str(d[k])[:100]
        add_node('vt_petition', base, source_id=str(pid))

    # ════════════════════════════════════════════════════════════════════
    # 7. tb_atch_file → vt_file
    # ════════════════════════════════════════════════════════════════════
    log.info("[7/8] tb_atch_file → vt_file")
    cols, rows = fetch_data('tb_atch_file', sample_n=args.sample_file)
    for r in rows:
        d = dict(zip(cols, r))
        fid = d.get('atch_file_id')
        if not fid: continue
        add_node('vt_file', {
            'file_id':     fid,
            'file_nm':     d.get('atch_file_nm', ''),
            'file_extn':   d.get('atch_file_extn_nm', ''),
            'file_url':    d.get('atch_file_url', ''),
            'file_path':   d.get('atch_file_path', ''),
            'hash_val':    d.get('atch_file_hash_cd', ''),
            'mime_type':   d.get('atch_file_extn_nm', ''),
        }, source_id=fid)
        # contains_file: vt_site → vt_file
        clct_page_id = d.get('clct_page_id')
        if clct_page_id:
            add_edge('vt_site','site_id',clct_page_id, 'contains_file',
                     'vt_file','file_id',fid)

    # ════════════════════════════════════════════════════════════════════
    # 8. tb_clct_page → vt_site (수집 페이지)
    # ════════════════════════════════════════════════════════════════════
    log.info("[8/8] tb_clct_page → vt_site (수집 페이지)")
    cols, rows = fetch_data('tb_clct_page', sample_n=args.sample_page)
    for r in rows:
        d = dict(zip(cols, r))
        pid = d.get('clct_page_id')
        if not pid: continue
        add_node('vt_site', {
            'site_id':     pid,
            'url_addr':    d.get('url', ''),
            'domain':      d.get('site_nm', ''),
            'site_type':   d.get('site_type', ''),
            'title':       d.get('html_ttl', ''),
            'collected_at': str(d.get('clct_dt', '')),
        }, source_id=pid)

    # 통계
    log.info("="*60)
    log.info("✅ OSINT V4.0 그래프 적재 완료")
    log.info(f"  노드: {stats['nodes']}")
    log.info(f"  엣지: {stats['edges']}")
    log.info("  라벨별:")
    for k, v in sorted(stats['by_label'].items(), key=lambda x: -x[1]):
        log.info(f"    {k:18s} {v}")
    log.info("  엣지별:")
    for k, v in sorted(stats['by_edge'].items(), key=lambda x: -x[1]):
        log.info(f"    {k:25s} {v}")
    log.info("="*60)
    log.info(f"브라우저에서 그래프 셀렉터: {GRAPH}")
    log.info("자연어 추천:")
    log.info('  - "악성 사이트 보여줘"')
    log.info('  - "유해사이트 키워드 군집"')
    log.info('  - "OSINT 도메인 노드"')
    log.info('  - "스팸 SMS 발신자"')
    log.info('  - "site_cluster 보여줘"')

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
