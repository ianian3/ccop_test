"""
2025_demo_data 7 CSV → V4.0 온톨로지 그래프 적재
============================================================
대상 그래프: tccop_2025_demo (별도 분리)
V4.0 메타 6컬럼 자동 부착 (make_node_props_v40)

CSV 매핑:
  tbl_vt_psn.csv         → vt_psn        (flnm, rrno, gndr)
  tbl_vt_bacnt.csv       → vt_bacnt      (actno, dpstr, bank)
  tbl_vt_telno.csv       → vt_telno      (telno, flnm, tlcmco)
  tbl_eg_call.csv        → vt_call + caller/callee
  tbl_eg_rmt.csv         → vt_transfer + from_account/to_account
  tbl_eg_bactno_poss.csv → has_account (vt_psn → vt_bacnt)
  tbl_eg_telno_poss.csv  → owns_phone  (vt_psn → vt_telno)

실행:
  python3 scripts/build_2025_demo_graph.py [--drop]
"""
import argparse, csv, sys, logging
from pathlib import Path

sys.path.insert(0, '/Users/iankwon/test/coop_v1.0')

from app import create_app
from app.services.rdb_to_graph_service import RdbToGraphService
from app.database import safe_set_graph_path

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('2025_seeder')

_app = create_app(); _app.app_context().push()

DATA_DIR = Path('/Users/iankwon/test/coop_v1.0/2025_demo_data')
GRAPH = 'tccop_2025_demo'

# 은행 한글명 → 코드 매핑 (V4.0 표준)
BANK_CD = {
    '국민은행': '004', '신한은행': '088', '우리은행': '020',
    '하나은행': '081', '농협은행': '003', '카카오뱅크': '090',
    '토스뱅크': '092', '새마을금고': '045', 'NOBANKNM': '999',
}
CARR_CD = {'SKT': 'SKT', 'KT': 'KT', 'LGU': 'LGU', 'LG': 'LGU', 'NOTLCMCO': 'UNK'}


def cypher_escape(v):
    if v is None or v == '': return "''"
    if isinstance(v, bool): return 'true' if v else 'false'
    if isinstance(v, (int, float)): return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def props_str(d):
    return ', '.join(f"{k}: {cypher_escape(v)}" for k, v in d.items() if v not in (None, ''))


def read_csv(name):
    p = DATA_DIR / name
    if not p.exists():
        log.warning(f"파일 없음: {p}")
        return []
    # utf-8-sig → BOM(﻿) 자동 제거
    with open(p, encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def reset_graph(conn, cur, drop=False):
    if drop:
        try:
            cur.execute(f"DROP GRAPH IF EXISTS {GRAPH} CASCADE;")
            conn.commit()
            log.info(f"기존 '{GRAPH}' 그래프 삭제")
        except Exception as e:
            conn.rollback()
            log.warning(f"DROP 실패(무시): {e}")
    try:
        cur.execute(f"CREATE GRAPH IF NOT EXISTS {GRAPH};")
        conn.commit()
    except Exception:
        conn.rollback()
    safe_set_graph_path(cur, GRAPH)

    # VLABEL/ELABEL 사전 선언 (AgensGraph 라벨 자동 declare 안정성 보장)
    for vlabel in ['vt_psn', 'vt_bacnt', 'vt_telno', 'vt_call', 'vt_transfer']:
        try: cur.execute(f"CREATE VLABEL IF NOT EXISTS {vlabel};"); conn.commit()
        except: conn.rollback(); safe_set_graph_path(cur, GRAPH)
    for elabel in ['has_account', 'owns_phone', 'caller', 'callee',
                   'from_account', 'to_account']:
        try: cur.execute(f"CREATE ELABEL IF NOT EXISTS {elabel};"); conn.commit()
        except: conn.rollback(); safe_set_graph_path(cur, GRAPH)
    log.info(f"graph_path = '{GRAPH}' (라벨 5+6 선언 완료)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--drop', action='store_true', help='기존 그래프 삭제 후 재생성')
    args = parser.parse_args()

    log.info("=" * 60)
    log.info(f"2025_demo_data → V4.0 그래프 적재 시작 (target: {GRAPH})")
    log.info("=" * 60)

    conn, cur = RdbToGraphService.get_db_connection()
    if not conn: log.error("DB 연결 실패"); sys.exit(1)

    # autocommit — 각 노드/엣지 독립 커밋 (라벨 declared 즉시 반영)
    conn.autocommit = True

    reset_graph(conn, cur, drop=args.drop)
    stats = {'nodes': 0, 'edges': 0, 'by_label': {}, 'by_edge': {}}

    def add_node(label, base, source_domain='KICS', source_id=None):
        p = RdbToGraphService.make_node_props_v40(
            label, base, source_domain=source_domain, source_id=source_id,
        )
        cypher = f"CREATE (n:{label} {{{props_str(p)}}})"
        try:
            cur.execute(cypher)
            stats['nodes'] += 1
            stats['by_label'][label] = stats['by_label'].get(label, 0) + 1
            return True
        except Exception as e:
            log.warning(f"  노드 실패 {label}: {str(e)[:120]}")
            log.warning(f"    cypher: {cypher[:160]}")
            try: conn.rollback()
            except: pass
            safe_set_graph_path(cur, GRAPH)
            return False

    def add_edge(src_label, src_key, src_val, etype, tgt_label, tgt_key, tgt_val,
                 base=None, source_domain='KICS'):
        ep = RdbToGraphService.make_edge_props_v40(etype, base or {}, source_domain=source_domain)
        cypher = (
            f"MATCH (a:{src_label} {{{src_key}: {cypher_escape(src_val)}}}), "
            f"(b:{tgt_label} {{{tgt_key}: {cypher_escape(tgt_val)}}}) "
            f"CREATE (a)-[:{etype} {{{props_str(ep)}}}]->(b)"
        )
        try:
            cur.execute(cypher)
            stats['edges'] += 1
            stats['by_edge'][etype] = stats['by_edge'].get(etype, 0) + 1
            return True
        except Exception as e:
            log.warning(f"  엣지 실패 {src_label}({src_val})→{tgt_label}({tgt_val}) [{etype}]: {str(e)[:80]}")
            conn.rollback(); safe_set_graph_path(cur, GRAPH)
            return False

    # ════════════════════════════════════════════════════════════════════
    # 1. 인물 (vt_psn)
    # ════════════════════════════════════════════════════════════════════
    log.info("[1/7] vt_psn 적재")
    persons = read_csv('tbl_vt_psn.csv')
    for r in persons:
        nm = r.get('flnm', '').strip()
        if not nm: continue
        # role_cd 자동 추론 (이름 기반)
        role = 'suspect' if '피의자' in nm else ('victim' if '피해자' in nm else 'unknown')
        add_node('vt_psn', {
            'psn_id': nm,                         # 시연 데이터는 flnm 을 PK 로 사용
            'name': nm,
            'rrno_hash': r.get('rrno', ''),
            'gender': r.get('gndr', ''),
            'role_cd': role,
            'is_anonymous': nm.startswith('NONM') or not nm,
        })

    # ════════════════════════════════════════════════════════════════════
    # 2. 계좌 (vt_bacnt)
    # ════════════════════════════════════════════════════════════════════
    log.info("[2/7] vt_bacnt 적재")
    accounts = read_csv('tbl_vt_bacnt.csv')
    for r in accounts:
        actno = r.get('actno', '').strip()
        if not actno: continue
        bnk = r.get('bank', '')
        add_node('vt_bacnt', {
            'account_no': actno,
            'holder_nm': r.get('dpstr', ''),
            'bank_nm': bnk,
            'bnk_cd': BANK_CD.get(bnk, '999'),
            'is_burner': r.get('dpstr', '') == 'NONM',
        })

    # ════════════════════════════════════════════════════════════════════
    # 3. 전화 (vt_telno)
    # ════════════════════════════════════════════════════════════════════
    log.info("[3/7] vt_telno 적재")
    telnos = read_csv('tbl_vt_telno.csv')
    for r in telnos:
        t = r.get('telno', '').strip()
        if not t: continue
        carr = r.get('tlcmco', '')
        add_node('vt_telno', {
            'telno': t,
            'holder_nm': r.get('flnm', ''),
            'carr_cd': CARR_CD.get(carr, 'UNK'),
            'is_burner': r.get('flnm', '') == 'NONM',
        })

    # ════════════════════════════════════════════════════════════════════
    # 4. 통화 이벤트 (vt_call) + caller/callee
    # ════════════════════════════════════════════════════════════════════
    log.info("[4/7] vt_call + caller/callee")
    calls = read_csv('tbl_eg_call.csv')
    for r in calls:
        cid = r.get('id', '').strip()
        if not cid: continue
        # 지속시간 계산 (bgng~end)
        bgn = r.get('bgng_ymdhm', '')
        end = r.get('end_ymdhm', '')
        duration = 0
        if bgn and end:
            try:
                from datetime import datetime
                fmt = '%Y-%m-%d %H:%M:%S'
                duration = int((datetime.strptime(end, fmt) - datetime.strptime(bgn, fmt)).total_seconds())
            except Exception: pass
        call_id = f'CALL-2025-{int(cid):05d}'
        add_node('vt_call', {
            'call_id':     call_id,
            'duration':    duration,
            'occurred_at': bgn,
            'end_at':      end,
            'carr_cd':     CARR_CD.get(r.get('tlcmco', ''), 'UNK'),
            'msg_type':    r.get('se', ''),
            'remarks':     r.get('rmrk', ''),
        })
        # caller: vt_telno → vt_call
        caller_tel = r.get('dsptch_no', '').strip()
        callee_tel = r.get('rcptn_no', '').strip()
        if caller_tel: add_edge('vt_telno','telno',caller_tel, 'caller', 'vt_call','call_id',call_id)
        if callee_tel: add_edge('vt_call','call_id',call_id, 'callee', 'vt_telno','telno',callee_tel)

    # ════════════════════════════════════════════════════════════════════
    # 5. 이체 이벤트 (vt_transfer) + from/to_account
    # ════════════════════════════════════════════════════════════════════
    log.info("[5/7] vt_transfer + from/to_account")
    rmts = read_csv('tbl_eg_rmt.csv')
    for r in rmts:
        rid = r.get('id', '').strip()
        if not rid: continue
        try: amount = int(r.get('dpst_amt', '0') or 0)
        except: amount = 0
        tid = f'TXN-2025-{int(rid):05d}'
        add_node('vt_transfer', {
            'transfer_id':   tid,
            'transfer_type': r.get('rmt_se', ''),
            'amount':        amount,
            'tkmny_amt':     int(r.get('tkmny_amt','0') or 0),
            'abstract_text': r.get('abstr', ''),
            'occurred_at':   r.get('rmt_ymdhm', ''),
            'src_ip':        r.get('Ip', ''),
        })
        # from_account: 출금계좌 (rlt_actno = 피해자 송금원)
        # 실데이터 보면: dpstr=피의자, actno=피의자계좌(입금), rlt_dpstr/rlt_actno=피해자(원본)
        # 즉 흐름: rlt_actno (피해자) → vt_transfer → actno (피의자)
        src_act = r.get('rlt_actno','').strip()
        tgt_act = r.get('actno','').strip()
        if src_act: add_edge('vt_bacnt','account_no',src_act, 'from_account', 'vt_transfer','transfer_id',tid)
        if tgt_act: add_edge('vt_transfer','transfer_id',tid, 'to_account', 'vt_bacnt','account_no',tgt_act)

    # ════════════════════════════════════════════════════════════════════
    # 6. has_account (vt_psn → vt_bacnt)
    # ════════════════════════════════════════════════════════════════════
    log.info("[6/7] has_account 엣지")
    for r in read_csv('tbl_eg_bactno_poss.csv'):
        nm = r.get('flnm','').strip(); act = r.get('actno','').strip()
        if nm and act:
            add_edge('vt_psn','name',nm, 'has_account', 'vt_bacnt','account_no',act)

    # ════════════════════════════════════════════════════════════════════
    # 7. owns_phone (vt_psn → vt_telno)
    # ════════════════════════════════════════════════════════════════════
    log.info("[7/7] owns_phone 엣지")
    for r in read_csv('tbl_eg_telno_poss.csv'):
        nm = r.get('flnm','').strip(); t = r.get('telno','').strip()
        if nm and t:
            add_edge('vt_psn','name',nm, 'owns_phone', 'vt_telno','telno',t)

    conn.commit()

    # 통계 출력
    log.info("=" * 60)
    log.info("✅ 적재 완료")
    log.info(f"  노드: {stats['nodes']}개")
    log.info(f"  엣지: {stats['edges']}개")
    log.info("  라벨별:")
    for k, v in sorted(stats['by_label'].items(), key=lambda x: -x[1]):
        log.info(f"    {k:18s} {v}")
    log.info("  엣지별:")
    for k, v in sorted(stats['by_edge'].items(), key=lambda x: -x[1]):
        log.info(f"    {k:18s} {v}")
    log.info("=" * 60)
    log.info(f"브라우저에서: {GRAPH} 선택")
    log.info("예시 질의:")
    log.info("  - '피의자 목록 보여줘'")
    log.info("  - '피의자가 보유한 계좌'")
    log.info("  - '피해자→피의자 자금 흐름'")
    log.info("  - '대포통장 보여줘'")
    log.info("  - '통화 내역'")

    cur.close(); conn.close()


if __name__ == '__main__':
    main()
