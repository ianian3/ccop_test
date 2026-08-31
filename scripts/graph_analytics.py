#!/usr/bin/env python3
"""통합 그래프 그래프분석 — PageRank(영향력 랭킹)·Louvain(자동 조직 탐지).

AgensGraph는 전용 GDS(그래프 알고리즘)가 없어, 그래프를 NetworkX로 export 후 계산하고
결과를 노드 속성(pagerank·community_id)으로 되쓴다(--set). 브리핑/시각화에서 활용.
  · PageRank: 방향 그래프에서 '영향력 있는 노드'(콜센터 IP·집금 계좌·핵심 인물) 자동 랭킹
  · Louvain: 무방향에서 자동 조직(커뮤니티) 탐지 — belongs_to 수동 판정을 자동화
실행: python3 scripts/graph_analytics.py [--graph ccop_ep_integrated] [--set]
"""
import sys
import os
import argparse
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.database import safe_set_graph_path
import psycopg2
import networkx as nx
from collections import Counter, defaultdict

KP = {'vt_psn': 'name', 'vt_bacnt': 'account_no', 'vt_telno': 'telno', 'vt_ip': 'ip_addr',
      'vt_id': 'id_val', 'vt_case': 'flnm', 'vt_org': 'org_name', 'vt_atm': 'atm_nm',
      'vt_email': 'email_addr', 'vt_src': 'src_name'}
KEYEXPR = ("coalesce(n.name,n.account_no,n.telno,n.ip_addr,n.id_val,n.flnm,"
           "n.org_name,n.atm_nm,n.email_addr,n.src_name)")


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--graph', default='ccop_ep_integrated')
    ap.add_argument('--set', action='store_true', help='결과를 노드 속성으로 되쓰기')
    args = ap.parse_args()
    app = create_app()
    with app.app_context():
        conn = psycopg2.connect(**app.config['DB_CONFIG']); conn.autocommit = True; cur = conn.cursor()

        def q(c):
            safe_set_graph_path(cur, args.graph); cur.execute(c); return cur.fetchall()

        # ── export ──
        id2 = {}
        for nid, lbl, key in q(f"MATCH (n) RETURN id(n), label(n), {KEYEXPR}"):
            id2[str(nid)] = (lbl, key)
        G = nx.DiGraph()
        G.add_nodes_from(id2.keys())
        for a, b in q("MATCH (a)-[r]->(b) RETURN id(a), id(b)"):
            G.add_edge(str(a), str(b))
        print(f"[export] {args.graph} — 노드 {G.number_of_nodes()} · 엣지 {G.number_of_edges()}")

        # ── PageRank ──
        pr = nx.pagerank(G, alpha=0.85)
        # ── Louvain (무방향) ──
        comms = nx.community.louvain_communities(G.to_undirected(), seed=42)
        comms_sorted = sorted(comms, key=len, reverse=True)
        node2c = {}
        for i, c in enumerate(comms_sorted):
            for n in c:
                node2c[n] = i
        print(f"[louvain] 커뮤니티 {len(comms)}개 (최대 {len(comms_sorted[0])}노드)")

        # ── Top PageRank (라벨별) ──
        by = defaultdict(list)
        for nid, score in sorted(pr.items(), key=lambda x: -x[1]):
            lbl, key = id2.get(nid, ('?', '?'))
            by[lbl].append((key, score))
        print("\n=== PageRank 상위 (영향력) ===")
        for lbl in ['vt_ip', 'vt_bacnt', 'vt_psn', 'vt_org', 'vt_telno']:
            top = by.get(lbl, [])[:5]
            if top:
                print(f"  [{lbl}] " + " · ".join(f"{k}({s:.4f})" for k, s in top))

        # ── 큰 커뮤니티(조직) ──
        print("\n=== Louvain 자동 조직 (상위 6) ===")
        for i, c in enumerate(comms_sorted[:6]):
            labels = Counter(id2.get(n, ('?', ''))[0] for n in c)
            persons = [id2[n][1] for n in c if id2.get(n, ('?', ''))[0] == 'vt_psn' and id2[n][1]][:5]
            print(f"  조직#{i}: {len(c)}노드 {dict(labels)}")
            if persons:
                print(f"          인물: {persons}")

        # ── SET back ──
        if args.set:
            conn.autocommit = False
            cnt = 0
            for nid, (lbl, key) in id2.items():
                if lbl not in KP or key is None or key == '':
                    continue
                cur.execute(f"MATCH (n:{lbl} {{{KP[lbl]}:'{esc(key)}'}}) "
                            f"SET n.pagerank='{pr.get(nid, 0):.6f}', n.community_id='{node2c.get(nid, -1)}'")
                cnt += 1
                if cnt % 3000 == 0:
                    conn.commit(); print(f"  SET {cnt}…")
            conn.commit()
            print(f"[SET 완료] {cnt}노드에 pagerank·community_id 부여")
        conn.close()


if __name__ == '__main__':
    main()
