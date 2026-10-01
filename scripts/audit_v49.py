#!/usr/bin/env python3
"""V4.9 SoT 정합 감사 — 그래프 1개 이상의 라벨·엣지·방향·정경 키를 SoT(KICSCrimeDomainOntology) 기준으로 센다.

audit_ep_v48.py(손키 표·EP 그래프 고정 목록)의 V4.9 판. 정합 2단계 2e(재구축 리허설·운영 재구축) 검증용.

  위반 (0 이어야 함)
    label_outside   SoT 밖 노드 라벨          label_deprecated  삭제 라벨(vt_email)
    edge_outside    SoT 밖·삭제 엣지 타입      edge_direction    edge_rules 의 출발/도착 라벨 위반
    key_missing     정경 키(NODE_ID_STANDARD.canonical_field)가 빈 노드
  참고
    labels / edges  라벨별 노드 수 · (타입, 출발, 도착)별 엣지 수

쿼리는 라벨 단위 단순 MATCH 와 속성 조건 없는 1홉 패턴만 쓴다 — 운영 엔진의 '경로 + 비앵커 노드 속성 조건'
크래시 패턴을 쓰지 않는다(reference: 운영 DB 엔진 크래시 결함).

실행: python3 scripts/audit_v49.py GRAPH [GRAPH ...]      (DB 는 환경변수 DB_* — 앱과 같음)
종료 코드: 위반이 있으면 1
"""
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.database import safe_set_graph_path, validate_graph_path  # noqa: E402
from app.services.ontology_service import KICSCrimeDomainOntology as O  # noqa: E402


def _key_fields(label):
    canon = (O.NODE_ID_STANDARD.get(label) or {}).get('canonical_field') or ''
    return [f.strip() for f in canon.strip('()').split(',') if f.strip()]


def graph_labels(cur, graph):
    """그래프에 실제로 있는 (라벨명, 종류 'v'|'e') — 빈 라벨 포함."""
    cur.execute("SELECT l.labname, l.labkind FROM ag_label l JOIN ag_graph g ON g.oid = l.graphid "
                "WHERE g.graphname = %s AND l.labname NOT IN ('ag_vertex', 'ag_edge')", (graph,))
    return cur.fetchall()


def audit(cur, graph):
    if not validate_graph_path(graph):
        raise ValueError(f'허용되지 않는 그래프명: {graph!r}')
    sot_labels = {v['label'] for v in O.ENTITIES.values()}
    dep_labels = set(getattr(O, 'DEPRECATED_LABELS', {}) or {})
    dep_edges = set(getattr(O, 'DEPRECATED_EDGES', {}) or {})
    rules = O.edge_rules()
    lab = graph_labels(cur, graph)
    safe_set_graph_path(cur, graph)
    labels, edges, keys = {}, {}, {}
    for name, kind in lab:
        if kind != 'v':
            continue
        cur.execute(f'MATCH (n:{name}) RETURN count(n)')
        n = int(cur.fetchone()[0] or 0)
        if not n:
            continue
        labels[name] = n
        fs = _key_fields(name)
        if fs and name in sot_labels:
            cond = ' OR '.join(f'n.{f} IS NULL' for f in fs)
            cur.execute(f'MATCH (n:{name}) WHERE {cond} RETURN count(n)')
            keys[name] = int(cur.fetchone()[0] or 0)
    for name, kind in lab:
        if kind != 'e':
            continue
        cur.execute(f'MATCH (a)-[e:{name}]->(b) RETURN label(a), label(b), count(e)')
        for la, lb, n in cur.fetchall():
            edges[f'{name}|{la}|{lb}'] = int(n)
    v = {
        'label_outside': {l: n for l, n in labels.items() if l not in sot_labels and l not in dep_labels},
        'label_deprecated': {l: n for l, n in labels.items() if l in dep_labels},
        'edge_outside': {}, 'edge_direction': {},
        'key_missing': {l: n for l, n in keys.items() if n},
    }
    for k, n in edges.items():
        t, la, lb = k.split('|')
        r = rules.get(t)
        if r is None or t in dep_edges:
            v['edge_outside'][k] = n
        elif (r[0] is not None and la not in r[0]) or (r[1] is not None and lb not in r[1]):
            v['edge_direction'][k] = n
    return {'graph': graph, 'nodes': sum(labels.values()), 'edges': sum(edges.values()),
            'labels': labels, 'edge_types': edges, 'violations': v,
            'violation_count': sum(sum(x.values()) for x in v.values())}


def main():
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv()
    graphs = sys.argv[1:]
    if not graphs:
        sys.exit(__doc__)
    conn = psycopg2.connect(dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'),
                            host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'))
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor()
    bad = 0
    for g in graphs:
        r = audit(cur, g)
        bad += r['violation_count']
        print(f"[{g}] 노드 {r['nodes']:,} · 엣지 {r['edges']:,} · 위반 {r['violation_count']}")
        for kind, d in r['violations'].items():
            if d:
                print(f'  {kind}: {json.dumps(d, ensure_ascii=False)}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
