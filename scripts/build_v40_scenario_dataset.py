"""
V4.0 시나리오 데이터셋 빌더 — 중규모 (~200 노드)
======================================================
대상 그래프: tccop_v40_demo (별도 graph_path, 운영 데이터 불변)
도메인 4종 교차: KICS / OSINT / DIGITAL / EXT
시나리오: 보이스피싱 캠페인 3건 + site_cluster 2개 + pt_cluster 1개 + 중계기 2대

실행:
    cd /Users/iankwon/test/coop_v1.0
    python3 scripts/build_v40_scenario_dataset.py

옵션:
    --drop  : 기존 tccop_v40_demo 그래프 삭제 후 재생성
    --graph : 그래프 이름 (기본: tccop_v40_demo)
"""
import argparse
import sys
import logging
import random
from datetime import datetime, timedelta

sys.path.insert(0, '/Users/iankwon/test/coop_v1.0')

from app import create_app
from app.services.rdb_to_graph_service import RdbToGraphService
from app.database import safe_set_graph_path

_FLASK_APP = create_app()
_FLASK_APP.app_context().push()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('v40_seeder')

random.seed(20260521)
NOW = datetime(2026, 5, 21, 10, 0, 0)


# ─────────────────────────────────────────────────────────────────────────
# 헬퍼: V4.0 메타 + Cypher 직렬화
# ─────────────────────────────────────────────────────────────────────────
def cypher_escape(v):
    if v is None:
        return "''"
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def props_str(d):
    return ', '.join(f"{k}: {cypher_escape(v)}" for k, v in d.items())


def node_props(label, base, source_domain='KICS', source_id=None,
               minutes_ago=None):
    p = RdbToGraphService.make_node_props_v40(
        label, base, source_domain=source_domain, source_id=source_id,
    )
    if minutes_ago is not None:
        p['collected_at'] = (NOW - timedelta(minutes=minutes_ago)).isoformat() + 'Z'
    return p


def edge_props(etype, base=None, source_domain='KICS', source_id=None,
               minutes_ago=None):
    p = RdbToGraphService.make_edge_props_v40(
        etype, base or {}, source_domain=source_domain, source_id=source_id,
    )
    if minutes_ago is not None:
        p['collected_at'] = (NOW - timedelta(minutes=minutes_ago)).isoformat() + 'Z'
    return p


def run_cypher(cur, cypher):
    cur.execute(cypher)


# ─────────────────────────────────────────────────────────────────────────
# 그래프 초기화
# ─────────────────────────────────────────────────────────────────────────
def reset_graph(conn, cur, graph_name, drop):
    if drop:
        try:
            cur.execute(f"DROP GRAPH IF EXISTS {graph_name} CASCADE;")
            conn.commit()
            log.info(f"기존 그래프 '{graph_name}' 삭제 완료")
        except Exception as e:
            conn.rollback()
            log.warning(f"DROP 실패(무시): {e}")
    try:
        cur.execute(f"CREATE GRAPH IF NOT EXISTS {graph_name};")
        conn.commit()
    except Exception as e:
        conn.rollback()
        log.warning(f"CREATE GRAPH(무시): {e}")
    safe_set_graph_path(cur, graph_name)
    log.info(f"graph_path = '{graph_name}'")


# ─────────────────────────────────────────────────────────────────────────
# 시드 — 시나리오 3건 + V3.7 신규
# ─────────────────────────────────────────────────────────────────────────
def seed(conn, cur):
    stats = {'nodes': 0, 'edges': 0, 'by_label': {}, 'by_edge': {}, 'by_domain': {}}

    def add_node(label, base, source_domain='KICS', source_id=None, minutes_ago=None):
        p = node_props(label, base, source_domain, source_id, minutes_ago)
        run_cypher(cur, f"CREATE (n:{label} {{{props_str(p)}}})")
        stats['nodes'] += 1
        stats['by_label'][label] = stats['by_label'].get(label, 0) + 1
        d = p.get('source_domain', '?')
        stats['by_domain'][d] = stats['by_domain'].get(d, 0) + 1
        return p

    def add_edge(src_label, src_key, src_val, etype, tgt_label, tgt_key, tgt_val,
                 base=None, source_domain='KICS', source_id=None, minutes_ago=None):
        ep = edge_props(etype, base, source_domain, source_id, minutes_ago)
        cypher = (
            f"MATCH (a:{src_label} {{{src_key}: {cypher_escape(src_val)}}}), "
            f"(b:{tgt_label} {{{tgt_key}: {cypher_escape(tgt_val)}}}) "
            f"CREATE (a)-[:{etype} {{{props_str(ep)}}}]->(b)"
        )
        try:
            run_cypher(cur, cypher)
            stats['edges'] += 1
            stats['by_edge'][etype] = stats['by_edge'].get(etype, 0) + 1
        except Exception as e:
            log.warning(f"  엣지 실패 {src_label}.{src_val}→{tgt_label}.{tgt_val} ({etype}): {e}")
            conn.rollback()
            safe_set_graph_path(cur, 'tccop_v40_demo')

    # ═══════════════════════════════════════════════════════════════════
    # SOURCE & 사건 3건
    # ═══════════════════════════════════════════════════════════════════
    log.info("[1/8] vt_src + vt_case 3건")
    for sid, snm, dom in [('kics_main', 'KICS 형사사법시스템', 'KICS'),
                          ('osint_collector', 'OSINT 자동수집기', 'OSINT'),
                          ('digital_forensic', '디지털 포렌식랩', 'DIGITAL'),
                          ('ext_bank', '금융위 외부제공', 'EXT')]:
        add_node('vt_src', {'src_id': sid, 'src_nm': snm, 'src_type': dom},
                 source_domain=dom)

    cases = [
        ('CASE-2026-A-001', '강남 보이스피싱 일당 캠페인', '2026-04-01'),
        ('CASE-2026-A-002', '부산 가족사칭 송금 사건', '2026-04-15'),
        ('CASE-2026-A-003', '대구 보험금 갈취 모집', '2026-04-22'),
    ]
    for cno, flnm, occ in cases:
        add_node('vt_case', {'case_no': cno, 'flnm': flnm, 'occurred_at': occ})

    # 진정서 1건
    add_node('vt_petition',
             {'petition_id': 'PET-2026-001', 'subject': '피싱사이트 다중신고',
              'filed_at': '2026-03-20'})
    add_edge('vt_petition', 'petition_id', 'PET-2026-001',
             'filed_as',
             'vt_case', 'case_no', 'CASE-2026-A-001')

    # ═══════════════════════════════════════════════════════════════════
    # 인물 15명 (피의자 9 + 피해자 6, OSINT 익명 5명 포함)
    # ═══════════════════════════════════════════════════════════════════
    log.info("[2/8] vt_psn 15명 (익명 5 포함)")
    suspects = [
        ('PSN-S001', '김두목', False),
        ('PSN-S002', '이실장', False),
        ('PSN-S003', '박팀장', False),
        ('PSN-S004', '최팀원', False),
        ('PSN-S005', '정팀원', False),
        ('PSN-S006', '강행동책', False),
    ]
    for psn_id, name, anon in suspects:
        add_node('vt_psn',
                 {'psn_id': psn_id, 'name': name, 'is_anonymous': anon,
                  'role_cd': 'suspect'})

    # OSINT 익명 닉네임 4명
    for i in range(4):
        psn_id = f'OSINT-NICK-{i+1:03d}'
        add_node('vt_psn',
                 {'psn_id': psn_id, 'name': f'@anon_user_{i+1}',
                  'is_anonymous': True, 'role_cd': 'suspect_alias'},
                 source_domain='OSINT')

    # 피해자 5명
    for i in range(5):
        psn_id = f'PSN-V{i+1:03d}'
        add_node('vt_psn',
                 {'psn_id': psn_id, 'name': f'피해자{i+1}',
                  'is_anonymous': False, 'role_cd': 'victim'})

    # suspect_in / victim_in 엣지
    psn_to_case = {
        'PSN-S001': 'CASE-2026-A-001', 'PSN-S002': 'CASE-2026-A-001',
        'PSN-S003': 'CASE-2026-A-001', 'PSN-S004': 'CASE-2026-A-002',
        'PSN-S005': 'CASE-2026-A-002', 'PSN-S006': 'CASE-2026-A-003',
    }
    for psn, case in psn_to_case.items():
        add_edge('vt_psn', 'psn_id', psn, 'suspect_in',
                 'vt_case', 'case_no', case)
    victims_to_case = {f'PSN-V{i+1:03d}': cases[i % 3][0] for i in range(5)}
    for psn, case in victims_to_case.items():
        add_edge('vt_psn', 'psn_id', psn, 'victim_in',
                 'vt_case', 'case_no', case)

    # ═══════════════════════════════════════════════════════════════════
    # 조직 2개
    # ═══════════════════════════════════════════════════════════════════
    log.info("[3/8] vt_org 2개")
    for org_id, nm in [('ORG-001', '강남 보이스피싱 콜센터'),
                       ('ORG-002', '부산 위장 대부업체')]:
        add_node('vt_org', {'org_id': org_id, 'org_nm': nm})
    add_edge('vt_psn', 'psn_id', 'PSN-S001', 'operates',
             'vt_org', 'org_id', 'ORG-001')
    add_edge('vt_psn', 'psn_id', 'PSN-S004', 'operates',
             'vt_org', 'org_id', 'ORG-002')

    # ═══════════════════════════════════════════════════════════════════
    # 계좌 25개 (KICS 15 + OSINT 5 + EXT 5)
    # ═══════════════════════════════════════════════════════════════════
    log.info("[4/8] vt_bacnt 25개 + holds/has_account 엣지")
    bank_codes = ['004', '088', '020', '081', '003']
    bacnts = []
    for i in range(15):
        actno = f"{bank_codes[i%5]}-{(1000+i*7):04d}-{(2000+i*13):04d}"
        bacnts.append(('vt_bacnt', actno, 'KICS'))
        add_node('vt_bacnt',
                 {'account_no': actno, 'bnk_cd': bank_codes[i % 5],
                  'holder_nm': f'명의자{i+1}'},
                 source_domain='KICS')
    for i in range(5):
        actno = f"OSINT-LEAK-{i+1:04d}"
        bacnts.append(('vt_bacnt', actno, 'OSINT'))
        add_node('vt_bacnt',
                 {'account_no': actno, 'bnk_cd': '999', 'holder_nm': 'unknown'},
                 source_domain='OSINT')
    for i in range(5):
        actno = f"EXT-PARTNER-{(3000+i):04d}"
        bacnts.append(('vt_bacnt', actno, 'EXT'))
        add_node('vt_bacnt', {'account_no': actno, 'bnk_cd': '002'},
                 source_domain='EXT')

    # 계좌 소유 — 피의자 → 계좌 (has_account)
    susp_list = list(psn_to_case.keys())
    for idx, (_, actno, _) in enumerate(bacnts):
        psn = susp_list[idx % len(susp_list)]
        add_edge('vt_psn', 'psn_id', psn, 'has_account',
                 'vt_bacnt', 'account_no', actno)

    # OSINT 익명 ID → 계좌 (cross-domain sameAs 일부)
    for i in range(3):
        actno = bacnts[i][1]
        add_edge('vt_psn', 'psn_id', f'OSINT-NICK-{i+1:03d}', 'sameAs',
                 'vt_psn', 'psn_id', susp_list[i],
                 source_domain='INFERENCE')

    # ═══════════════════════════════════════════════════════════════════
    # 전화 25개 + 중계기 2대 (V3.7 relay_station)
    # ═══════════════════════════════════════════════════════════════════
    log.info("[5/8] vt_telno 25 + vt_dev relay 2 (V3.7)")
    telnos = []
    for i in range(20):
        tel = f"010{(10000000 + i*371):08d}"
        telnos.append(tel)
        add_node('vt_telno',
                 {'telno': tel, 'carr_cd': ['SKT', 'KT', 'LGU'][i % 3]})
    # 중계기 경유 5개 (V3.7)
    for i in range(5):
        tel = f"070{(20000000 + i*511):08d}"
        telnos.append(tel)
        add_node('vt_telno',
                 {'telno': tel, 'carr_cd': 'VOIP', 'is_relay_via': True})

    # owns_phone — 인물 → 전화
    for idx, tel in enumerate(telnos[:18]):
        psn = susp_list[idx % len(susp_list)]
        add_edge('vt_psn', 'psn_id', psn, 'owns_phone',
                 'vt_telno', 'telno', tel)

    # 중계기 2대 (V3.7 신규 — relay_station)
    for i, dev_id in enumerate(['DEV-RELAY-001', 'DEV-RELAY-002']):
        add_node('vt_dev',
                 {'dev_id': dev_id, 'dev_type': 'relay_station',
                  'imei': f'35{(100000000 + i*99999):010d}'},
                 source_domain='INFERENCE')
    # used_in_device — VOIP 전화 → 중계기
    for idx, tel in enumerate(telnos[20:25]):
        dev = ['DEV-RELAY-001', 'DEV-RELAY-002'][idx % 2]
        add_edge('vt_telno', 'telno', tel, 'used_in_device',
                 'vt_dev', 'dev_id', dev, source_domain='INFERENCE')

    # ═══════════════════════════════════════════════════════════════════
    # IP / 사이트 / site_cluster (V3.7)
    # ═══════════════════════════════════════════════════════════════════
    log.info("[6/8] vt_ip 10 + vt_site 8 + site_cluster 2 (V3.7)")
    for i in range(10):
        add_node('vt_ip',
                 {'ip_addr': f'175.{i%5+100}.{(i*17)%256}.{(i*31)%256}'},
                 source_domain='OSINT' if i >= 5 else 'KICS')

    sites = []
    for i in range(8):
        url = f"https://fake-bank-{chr(97+i)}.com/login"
        sites.append(url)
        add_node('vt_site',
                 {'url_addr': url, 'domain': f'fake-bank-{chr(97+i)}.com'},
                 source_domain='OSINT')

    # site_cluster 2개 (V3.7 신규)
    add_node('site_cluster',
             {'cluster_id': 'SC-2026-001', 'cluster_nm': '강남 피싱 캠페인 A',
              'simhash64': 1234567890123456, 'member_cnt': 4},
             source_domain='OSINT')
    add_node('site_cluster',
             {'cluster_id': 'SC-2026-002', 'cluster_nm': '부산 피싱 캠페인 B',
              'simhash64': 9876543210987654, 'member_cnt': 4},
             source_domain='OSINT')

    # belongs_to_campaign — site → site_cluster
    for i, url in enumerate(sites):
        cluster = 'SC-2026-001' if i < 4 else 'SC-2026-002'
        add_edge('vt_site', 'url_addr', url, 'belongs_to_campaign',
                 'site_cluster', 'cluster_id', cluster,
                 source_domain='OSINT')

    # hosts — IP → site
    for i, url in enumerate(sites):
        ip = f'175.{i%5+100}.{(i*17)%256}.{(i*31)%256}'
        add_edge('vt_ip', 'ip_addr', ip, 'hosts',
                 'vt_site', 'url_addr', url)

    # ═══════════════════════════════════════════════════════════════════
    # pt_cluster 1개 (V3.7 신규 캠페인)
    # ═══════════════════════════════════════════════════════════════════
    log.info("[7/8] pt_cluster 1 (V3.7 캠페인)")
    add_node('pt_cluster',
             {'cluster_id': 'PTC-2026-001',
              'campaign_nm': '전국 보이스피싱 조직 추적',
              'threat_level': 5, 'member_cnt': 9},
             source_domain='INFERENCE')
    for psn in susp_list:
        add_edge('vt_psn', 'psn_id', psn, 'belongs_to_cluster',
                 'pt_cluster', 'cluster_id', 'PTC-2026-001',
                 source_domain='INFERENCE')

    # ═══════════════════════════════════════════════════════════════════
    # 이벤트 — 이체 30 + 통화 25 + 접속 10 + 메시지 5
    # ═══════════════════════════════════════════════════════════════════
    log.info("[8/8] 이벤트 70건 + 디지털 파일 5건")
    # vt_transfer 30건 — 자금흐름
    for i in range(30):
        tid = f'TXN-{i+1:05d}'
        src = bacnts[i % len(bacnts)][1]
        tgt = bacnts[(i + 7) % len(bacnts)][1]
        add_node('vt_transfer',
                 {'transfer_id': tid, 'amount': (50000 + i*13000),
                  'occurred_at': (NOW - timedelta(days=i//5, hours=i%24)).isoformat()})
        add_edge('vt_bacnt', 'account_no', src, 'from_account',
                 'vt_transfer', 'transfer_id', tid)
        add_edge('vt_transfer', 'transfer_id', tid, 'to_account',
                 'vt_bacnt', 'account_no', tgt)

    # vt_call 25건
    for i in range(25):
        cid = f'CALL-{i+1:05d}'
        a = telnos[i % len(telnos)]
        b = telnos[(i + 5) % len(telnos)]
        add_node('vt_call',
                 {'call_id': cid, 'duration': 30 + i*7,
                  'occurred_at': (NOW - timedelta(hours=i*3)).isoformat()})
        add_edge('vt_telno', 'telno', a, 'caller',
                 'vt_call', 'call_id', cid)
        add_edge('vt_call', 'call_id', cid, 'callee',
                 'vt_telno', 'telno', b)

    # vt_access 10건 (피해자 IP → 가짜 사이트)
    for i in range(10):
        aid = f'ACC-{i+1:05d}'
        add_node('vt_access',
                 {'access_id': aid, 'src_ip': f'192.168.{i%5}.{i*7%256}',
                  'occurred_at': (NOW - timedelta(hours=i*2)).isoformat()})
        url = sites[i % len(sites)]
        add_edge('vt_access', 'access_id', aid, 'accessed',
                 'vt_site', 'url_addr', url)

    # vt_msg 5건
    for i in range(5):
        mid = f'MSG-{i+1:05d}'
        add_node('vt_msg', {'msg_id': mid, 'platform': 'kakao',
                            'msg_type': 'text'},
                 source_domain='DIGITAL')

    # vt_file 5건 (DIGITAL)
    for i in range(5):
        fid = f'FILE-{i+1:05d}'
        add_node('vt_file',
                 {'file_id': fid, 'hash_val': f'sha256-{i:064x}',
                  'file_nm': f'malware_sample_{i+1}.exe',
                  'mime_type': 'application/x-msdownload'},
                 source_domain='DIGITAL')

    # vt_id 5개 (OSINT 익명)
    for i in range(5):
        idv = f'OSINT-ID-{i+1:04d}'
        add_node('vt_id',
                 {'id_val': idv, 'platform': 'telegram',
                  'is_anonymous': True},
                 source_domain='OSINT')

    conn.commit()
    return stats


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='V4.0 시나리오 시드')
    parser.add_argument('--graph', default='tccop_v40_demo')
    parser.add_argument('--drop', action='store_true')
    args = parser.parse_args()

    log.info("=" * 60)
    log.info(f"V4.0 시나리오 시드 시작 — graph='{args.graph}', drop={args.drop}")
    log.info("=" * 60)

    conn, cur = RdbToGraphService.get_db_connection()
    if not conn:
        log.error("DB 연결 실패")
        sys.exit(1)

    try:
        reset_graph(conn, cur, args.graph, args.drop)
        stats = seed(conn, cur)
        log.info("=" * 60)
        log.info("✅ 시드 완료")
        log.info(f"  노드: {stats['nodes']}개")
        log.info(f"  엣지: {stats['edges']}개")
        log.info("  라벨별:")
        for k, v in sorted(stats['by_label'].items(), key=lambda x: -x[1]):
            log.info(f"    {k:18s} {v}")
        log.info("  도메인별:")
        for k, v in sorted(stats['by_domain'].items(), key=lambda x: -x[1]):
            log.info(f"    {k:15s} {v}")
        log.info("  엣지 타입 상위 10:")
        for k, v in sorted(stats['by_edge'].items(), key=lambda x: -x[1])[:10]:
            log.info(f"    {k:24s} {v}")
        log.info("=" * 60)
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass


if __name__ == '__main__':
    main()
