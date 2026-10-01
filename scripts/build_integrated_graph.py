#!/usr/bin/env python3
"""EP1~10 → ccop_ep_integrated 통합 그래프 병합.

각 ep_graph 의 노드/엣지를 SoT 정경 키(계좌·전화·IP·계정·사건 등)로 MERGE 한다. EP 마다 가명이 달라도
물리 식별자(계좌/전화/IP/ID)가 겹치면 자동 교차 연결된다. 각 노드에 ep_origin='ep3,ep6,ep7' 을 부여해
어느 EP 들에서 공유되는지(콜센터 IP 등) 추적. 멱등(MERGE). 실행: python3 scripts/build_integrated_graph.py

2026-10-01 정합 2단계 2b — 쓰기는 공용 GraphWriter(app/services/graph_writer.py):
  · 키는 SoT NODE_ID_STANDARD. 종전 손키 표(KP: 인물 name·계정 id_val 단독 등)를 버린다
  · 인물(A안): EP 범위 결정적 ID 'psn:{ep}:{name}' — 종전엔 이름이 키라 다른 EP 의 다른 사람(가림 이름 '김**'
    포함)이 한 노드로 합쳐졌다. EP 간 같은 이름(가림 이름 제외)은 same_as 후보(review_status=pending)로 잇는다
  · 계정은 (platform, id_val) 복합키 — 종전 id_val 단독 키는 플랫폼이 다른 계정을 합쳤다
  · 기관·ATM·출처는 명칭 기반 global ID (실재 기관·장비라 EP 간 공유)
  · 이스케이프·정규화·SET += ·집계·실제 매칭 건수는 GraphWriter 가 맡는다
"""
import sys, os, re, collections
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.database import safe_set_graph_path, validate_graph_path
from app.services.graph_writer import GraphWriter, GraphWriteError
import psycopg2

# 읽어 올 라벨 (키는 SoT 가 정한다)
LABELS = ['vt_bacnt', 'vt_case', 'vt_id', 'vt_psn', 'vt_telno', 'vt_ip', 'vt_org', 'vt_atm', 'vt_src',
          'vt_movement',  # EP9/10 시드: 출입국 이벤트 (V4.8)
          'vt_loc']       # EP5-030-ibk: 거래점 위치 (located_at)
EDGES = ['eg_used_account', 'eg_used_phone', 'eg_used_id', 'has_account', 'victim_in',
         'transferred_to', 'belongs_to', 'registered_to', 'used_ip', 'contacted',
         'sourced_from', 'linked_to', 'uses_id', 'owns_phone', 'same_as',
         'suspect_in', 'performed_by', 'located_at']   # V4.8: same_as 개명 + EP9/10 시드 + 거래점 위치
# V4.9 흡수 — 원본 EP 그래프(이전 적재분)의 라벨·엣지를 통합 그래프에서는 V4.9 표기로 번역해 적재
LEGACY_LABELS = ['vt_email']                    # vt_email → vt_id {platform:'email'}
LEGACY_EDGES = {'uses_email': 'uses_id'}
NUM_EDGE_PROPS = {'total_amount', 'txn_count', 'tx_count', 'wd_count', 'dep_count', 'usage_count', 'evt_count',
                  'msg_count', 'call_count', 'total_dur_sec'}   # 문자열이면 >=/ORDER BY 깨짐
FLOAT_EDGE_PROPS = {'confidence'}                               # same_as 신뢰도 0.0~1.0 — 정수 변환 금지
GRAPHS = ['ep1_graph', 'ep2_graph', 'ep3_graph', 'ep4_graph',
          'ep5_graph', 'ep6_graph', 'ep7_graph', 'ep8_graph',
          'ep9_graph', 'ep10_graph']   # EP9/10: 정형 없음 → 수동 확정 시드(docs/EP910_SEED_DRAFT_20260902.md)
INTEG = 'ccop_ep_integrated'


# 2026-10-01 원천 정합 — EP 파서·수동 시드가 쓴 이름을 SoT 속성 사전 이름으로 (통합 그래프에서 번역)
PROP_RENAME = {
    'vt_telno': {'join_typ': 'join_typ_cd'},
    'vt_atm':   {'addr': 'address'},
    'vt_case':  {'case_type': 'incdnt_typ_cd'},
    'vt_ip':    {'country': 'ctry_cd'},          # 2026-10-01 원천 정합 (CSV 규격명)
}
EDGE_PROP_RENAME = {
    'used_ip': {'first_dt': 'valid_from', 'last_dt': 'valid_to', 'tx_count': 'usage_count'},   # V4.9 쌍 집계 규칙
    'same_as': {'conf': 'confidence', 'method': 'match_basis'},                                 # V4.9 속성명 통일
}


def _rename(props, table):
    return {table.get(k, k): v for k, v in props.items()} if table else props


def _canon(label, props):
    """원본 (라벨, 속성) → 통합 그래프 (라벨, 속성). V4.9: vt_email 은 vt_id(platform='email', id_val=소문자)."""
    props = _rename(props, PROP_RENAME.get(label))
    if label != 'vt_email':
        return label, props
    addr = props.get('email_addr')
    props = {a: b for a, b in props.items() if a != 'email_addr'}
    if addr not in (None, ''):
        props.update({'id_val': str(addr).strip().lower(), 'platform': 'email'})
    return 'vt_id', props


def _case_fallback(label, props):
    """vt_case: 정경 incdnt_no 가 빈 EP 시드 데이터는 flnm(예:'EP1-01-01')으로 채운다(폴백값을 canonical 에 보존)."""
    if label == 'vt_case' and props.get('incdnt_no') in (None, '') and props.get('flnm') not in (None, ''):
        props = dict(props, incdnt_no=str(props['flnm']))
    return props


def _num(pr):
    out = {}
    for k, v in pr.items():
        try:
            out[k] = float(v) if k in FLOAT_EDGE_PROPS else (int(float(v)) if k in NUM_EDGE_PROPS else v)
        except (TypeError, ValueError):
            out[k] = v
    return out


def main():
    # 통합 대상·산출 그래프를 인자로 받는다(기본값은 종전과 동일 — EP1~10 → ccop_ep_integrated).
    # 협력기관 납품본처럼 새 출처를 합칠 때 --graphs 에 추가하면 된다. 같은 물리 식별자
    # (계좌·전화·IP·계정)를 쓰면 기존 EP 데이터와 자동으로 교차 연결된다.
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--graphs', nargs='+', default=GRAPHS, help='통합할 원본 그래프들')
    ap.add_argument('--target', default=INTEG, help='산출 통합 그래프')
    a = ap.parse_args()
    src_graphs, integ = a.graphs, a.target
    for g in src_graphs + [integ]:
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', g):
            sys.exit(f'invalid graph name: {g}')
    print(f"[대상] {', '.join(src_graphs)} → {integ}", flush=True)

    app = create_app()
    with app.app_context():
        conn = psycopg2.connect(**app.config['DB_CONFIG']); conn.autocommit = True
        cur = conn.cursor()
        safe_set_graph_path(cur, src_graphs[0])
        keyer = GraphWriter(cur, src_graphs[0], mode='warn')        # 키 계산 전용 (쓰지 않음)
        nodes = {}      # (label, key_tuple) -> {'props':{}, 'origins':set()}
        edges = []      # (el, (la, key), (lb, key), props)
        skipped = collections.Counter()

        def keyed(label, props, ep):
            props = _case_fallback(label, props)
            key = keyer.key_for(label, props, scope=ep)
            return {**props, **key}, key

        # ── 수집 ──
        for g in src_graphs:
            ep = g.replace('_graph', '')
            safe_set_graph_path(cur, g)
            for src_label in LABELS + LEGACY_LABELS:
                try:
                    cur.execute(f"MATCH (n:{src_label}) RETURN properties(n)")
                except Exception:
                    safe_set_graph_path(cur, g); continue
                for (props,) in cur.fetchall():
                    if not props:
                        continue
                    label, props = _canon(src_label, props)
                    try:
                        props, key = keyed(label, props, ep)
                    except GraphWriteError as e:
                        skipped[f'노드 키 없음 {label}'] += 1; continue
                    k = (label, tuple(sorted(key.items())))
                    d = nodes.setdefault(k, {'props': {}, 'origins': set()})
                    d['props'].update({a: b for a, b in props.items() if b not in (None, '')})
                    d['origins'].add(ep)
            for src_el in EDGES + list(LEGACY_EDGES):
                el = LEGACY_EDGES.get(src_el, src_el)   # V4.9 uses_email → uses_id
                try:
                    cur.execute(f"MATCH (a)-[r:{src_el}]->(b) "
                                f"RETURN label(a),properties(a),label(b),properties(b),properties(r)")
                except Exception:
                    safe_set_graph_path(cur, g); continue
                for la, pa, lb, pb, pr in cur.fetchall():
                    if not pa or not pb:
                        continue
                    (la, pa), (lb, pb) = _canon(la, pa), _canon(lb, pb)
                    if la not in LABELS or lb not in LABELS:
                        skipped[f'엣지 라벨 밖 {src_el}'] += 1; continue
                    try:
                        _, ka = keyed(la, pa, ep)
                        _, kb = keyed(lb, pb, ep)
                    except GraphWriteError:
                        skipped[f'엣지 끝 키 없음 {src_el}'] += 1; continue
                    if src_el == 'uses_email':
                        pr = dict(pr or {}, platform='email')
                    pr = _rename(pr or {}, EDGE_PROP_RENAME.get(el))
                    if el == 'same_as':
                        pr.setdefault('review_status', 'pending'); pr.setdefault('traversal_policy', 'candidate_only')
                    edges.append((el, (la, ka), (lb, kb), _num(pr)))
        print(f"[수집] 노드 {len(nodes)} · 엣지 {len(edges)} · 건너뜀 {dict(skipped)}", flush=True)

        # ── EP 간 동일 이름 인물 → same_as 후보 (A안). 가림 이름('*' 포함)은 근거가 약해 제외 ──
        by_name = collections.defaultdict(list)
        for (label, kt), d in nodes.items():
            nm = d['props'].get('name')
            if label == 'vt_psn' and nm and '*' not in str(nm):
                by_name[str(nm).strip()].append(dict(kt))
        cand = 0
        for nm, keys in by_name.items():
            keys = sorted(keys, key=lambda k: k['psn_id'])
            for a, b in zip(keys, keys[1:]):
                edges.append(('same_as', ('vt_psn', a), ('vt_psn', b),
                              {'confidence': 0.5, 'match_basis': 'name_exact', 'review_status': 'pending',
                               'traversal_policy': 'candidate_only', 'source_id': 'BUILD-name-match'}))
                cand += 1
        print(f"[same_as 후보] EP 간 동일 이름 {cand}쌍 (pending)", flush=True)

        # ── 통합 그래프 생성 ──
        cur.execute(f"DROP GRAPH IF EXISTS {integ} CASCADE;")
        cur.execute(f"CREATE GRAPH IF NOT EXISTS {integ};")
        w = GraphWriter(cur, integ, mode='warn', batch_size=500)
        for (label, kt), d in nodes.items():
            props = dict(d['props'])
            props['ep_origin'] = ','.join(sorted(d['origins']))
            props['ep_count'] = len(d['origins'])     # 숫자 저장 — WHERE ep_count>=3 비교 (P1-B 동일 원칙)
            w.node(label, props)
        for el, (la, ka), (lb, kb), pr in edges:
            w.edge(el, (la, ka), (lb, kb), pr)
        stats = w.flush()
        print(f"[통합 완료] {integ} · 노드 {stats['nodes']} · 엣지 {stats['edges']} · 미연결 {stats['edges_unmatched']}", flush=True)
        for m, n in sorted(stats.get('warning_counts', {}).items(), key=lambda x: -x[1]):
            print(f"  [사전 밖] {m} × {n}", flush=True)
        conn.close()


if __name__ == '__main__':
    main()
