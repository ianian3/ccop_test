#!/usr/bin/env python3
"""통합 그래프 네트워크 분석 엔진 — 15+ 알고리즘 (중심성·커뮤니티·구조·경로·유사도).

AgensGraph는 전용 GDS(그래프 알고리즘)가 없어, 그래프를 NetworkX로 export 후 계산하고
전역(노드 단위) 결과를 노드 속성으로 되쓴다(--set). 브리핑/시각화/질의(CALL)에서 활용.

■ 노드속성 알고리즘 (--set 으로 사전계산 → Cypher `ORDER BY n.<metric>` 로 조회)
  중심성   pagerank · degree_cent · betweenness(k-샘플) · eigenvector · closeness(--heavy)
  커뮤니티  community_id(Louvain) · community_lp(Label Propagation)
  구조     component(약연결요소) · kcore(k-코어) · clustering(삼각형 계수)
■ 온디맨드 알고리즘 (함수로 노출 — CALL 미들웨어/질의에서 파라미터와 함께 호출)
  경로     algo_shortest_path(src,dst) · algo_all_paths
  유사도    algo_common_neighbors(node) = 공통이웃 Jaccard (링크예측/동일인 후보)
  패턴     algo_cycles = 순환 흐름 탐지 (자금세탁 typology)

실행:
  python3 scripts/graph_analytics.py --graph ccop_ep_integrated          # 리포트만
  python3 scripts/graph_analytics.py --graph ccop_ep_integrated --set    # 노드 속성 되쓰기
  python3 scripts/graph_analytics.py --graph ccop_ep_integrated --heavy  # closeness 포함(느림)
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
      'vt_email': 'email_addr', 'vt_src': 'src_name', 'vt_movement': 'mov_id'}
KEYEXPR = ("coalesce(n.name,n.account_no,n.telno,n.ip_addr,n.id_val,n.flnm,"
           "n.org_name,n.atm_nm,n.email_addr,n.src_name,n.mov_id)")

# 정수(범주) 속성 vs 실수(점수) 속성 구분 — SET 포맷용
INT_METRICS = {'community_id', 'community_lp', 'component', 'kcore', 'community_person'}

# 인물중심 서브그래프 라벨 — 전체 Louvain은 카톡 IP/ID 클러스터가 부피를 지배해
# 조직 경계가 흐림 → 사람·돈·조직·전화만의 유도 서브그래프에 별도 Louvain(community_person).
PERSON_CENTRIC_LABELS = {'vt_psn', 'vt_bacnt', 'vt_org', 'vt_telno'}


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


# ══════════════════════════════════════════════════════════════════
#  온디맨드 알고리즘 (경로·유사도·패턴) — CALL 레이어/질의에서 파라미터와 호출
# ══════════════════════════════════════════════════════════════════
def algo_shortest_path(G, src, dst):
    """최단경로 (무방향). 자금·연락 최단 연결 고리."""
    try:
        return nx.shortest_path(G.to_undirected(), src, dst)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None


def algo_all_paths(G, src, dst, cutoff=5, limit=20):
    """A→B 모든 경로(길이 cutoff 이하). 다단계 경유(layering) 추적."""
    try:
        paths = []
        for p in nx.all_simple_paths(G, src, dst, cutoff=cutoff):
            paths.append(p)
            if len(paths) >= limit:
                break
        return paths
    except nx.NodeNotFound:
        return []


def algo_common_neighbors(G, node, topn=10):
    """공통이웃 Jaccard 유사도 — 링크예측/동일인·공범 후보. [(other, jaccard, 공통수)]."""
    Gu = G.to_undirected()
    if node not in Gu:
        return []
    nb = set(Gu[node])
    if not nb:
        return []
    scores = []
    # 이웃의 이웃만 후보로 (전체 O(V) 회피)
    cand = set()
    for x in nb:
        cand |= set(Gu[x])
    cand.discard(node)
    for other in cand:
        onb = set(Gu[other])
        inter = nb & onb
        if inter:
            union = nb | onb
            scores.append((other, len(inter) / len(union), len(inter)))
    return sorted(scores, key=lambda x: -x[1])[:topn]


def algo_cycles(G, max_len=6, limit=15):
    """순환 흐름 탐지 (방향 그래프) — 자금세탁 circular flow (A→B→C→A)."""
    out = []
    try:
        for c in nx.simple_cycles(G, length_bound=max_len):
            if len(c) >= 2:
                out.append(c)
                if len(out) >= limit:
                    break
    except TypeError:
        # 구버전 networkx: length_bound 미지원 → 수동 필터
        for c in nx.simple_cycles(G):
            if 2 <= len(c) <= max_len:
                out.append(c)
                if len(out) >= limit:
                    break
    return out


# ══════════════════════════════════════════════════════════════════
#  전역(노드 단위) 알고리즘 — --set 으로 노드 속성에 사전계산
# ══════════════════════════════════════════════════════════════════
def compute_node_metrics(G, id2, heavy=False):
    """노드별 지표 dict 를 metric→{node:value} 로 반환 + 커뮤니티 리스트."""
    N = G.number_of_nodes()
    Gu = G.to_undirected()
    M = {}

    # ── 중심성 ──
    print("[centrality] pagerank·degree·betweenness·eigenvector 계산…")
    M['pagerank'] = nx.pagerank(G, alpha=0.85)
    M['degree_cent'] = nx.degree_centrality(G)
    # betweenness: 전 노드는 O(V·E)라 24k에선 무거움 → k-샘플 근사(정규화)
    k = min(500, N) if N > 800 else None
    M['betweenness'] = nx.betweenness_centrality(G, k=k, seed=42, normalized=True)
    try:
        M['eigenvector'] = nx.eigenvector_centrality(G, max_iter=1000, tol=1e-4)
    except (nx.PowerIterationFailedConvergence, nx.AmbiguousSolution):
        M['eigenvector'] = {n: 0.0 for n in G}
    if heavy:
        print("[centrality] closeness (전역 최단경로 — 느림)…")
        M['closeness'] = nx.closeness_centrality(G)

    # ── 커뮤니티 ──
    print("[community] Louvain·Label Propagation…")
    louvain = sorted(nx.community.louvain_communities(Gu, seed=42), key=len, reverse=True)
    M['community_id'] = {n: i for i, c in enumerate(louvain) for n in c}
    lp = sorted(nx.community.label_propagation_communities(Gu), key=len, reverse=True)
    M['community_lp'] = {n: i for i, c in enumerate(lp) for n in c}
    # 인물중심 Louvain — 사람·돈·조직·전화 유도 서브그래프 (진짜 조직 경계)
    pnodes = [n for n in Gu if id2.get(n, ('?',))[0] in PERSON_CENTRIC_LABELS]
    Gp = Gu.subgraph(pnodes)
    print(f"[community] 인물중심 서브그래프 — 노드 {Gp.number_of_nodes()} · 엣지 {Gp.number_of_edges()}")
    louvain_p = sorted(nx.community.louvain_communities(Gp, seed=42), key=len, reverse=True)
    M['community_person'] = {n: i for i, c in enumerate(louvain_p) for n in c}   # 서브그래프 노드에만 부여

    # ── 구조 ──
    print("[structure] 약연결요소·k-core·삼각형계수…")
    comp = sorted(nx.weakly_connected_components(G), key=len, reverse=True)
    M['component'] = {n: i for i, c in enumerate(comp) for n in c}
    M['kcore'] = nx.core_number(Gu)
    M['clustering'] = nx.clustering(Gu)

    return M, louvain, louvain_p


def report_top(M, id2, metric, labels=('vt_bacnt', 'vt_psn', 'vt_ip', 'vt_org', 'vt_telno'), topn=3):
    scores = M.get(metric, {})
    by = defaultdict(list)
    for nid, s in sorted(scores.items(), key=lambda x: -x[1]):
        lbl, key = id2.get(nid, ('?', '?'))
        if key:
            by[lbl].append((key, s))
    print(f"\n  ── {metric} ──")
    for lbl in labels:
        top = by.get(lbl, [])[:topn]
        if top:
            print(f"    [{lbl}] " + " · ".join(f"{k}({s:.4f})" for k, s in top))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--graph', default='ccop_ep_integrated')
    ap.add_argument('--set', action='store_true', help='결과를 노드 속성으로 되쓰기')
    ap.add_argument('--heavy', action='store_true', help='closeness 등 무거운 전역 계산 포함')
    args = ap.parse_args()
    app = create_app()
    with app.app_context():
        conn = psycopg2.connect(**app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()

        def q(c):
            safe_set_graph_path(cur, args.graph)
            cur.execute(c)
            return cur.fetchall()

        # ── export: AgensGraph → NetworkX ──
        id2 = {}
        for nid, lbl, key in q(f"MATCH (n) RETURN id(n), label(n), {KEYEXPR}"):
            id2[str(nid)] = (lbl, key)
        G = nx.DiGraph()
        G.add_nodes_from(id2.keys())
        for a, b in q("MATCH (a)-[r]->(b) RETURN id(a), id(b)"):
            G.add_edge(str(a), str(b))
        print(f"[export] {args.graph} — 노드 {G.number_of_nodes()} · 엣지 {G.number_of_edges()}")

        # ── 전역 알고리즘 계산 ──
        M, louvain, louvain_p = compute_node_metrics(G, id2, heavy=args.heavy)

        # ── 리포트: 중심성 ──
        print("\n=== ① 중심성 (누가 핵심·영향력자인가) ===")
        for metric in ['pagerank', 'betweenness', 'degree_cent', 'eigenvector'] + (['closeness'] if args.heavy else []):
            report_top(M, id2, metric)

        # ── 리포트: 커뮤니티 ──
        print("\n=== ② 커뮤니티 (어떤 무리가 한 조직인가) ===")
        print(f"  Louvain(전체) {len(louvain)}개 (최대 {len(louvain[0])}노드) — 카톡 IP/ID 부피 지배")
        print(f"  Louvain(인물중심) {len(louvain_p)}개 — community_person")
        for i, cset in enumerate(louvain_p[:6]):
            labels = Counter(id2.get(n, ('?', ''))[0] for n in cset)
            persons = [id2[n][1] for n in cset if id2.get(n, ('?', ''))[0] == 'vt_psn' and id2[n][1]][:6]
            orgs = [id2[n][1] for n in cset if id2.get(n, ('?', ''))[0] == 'vt_org' and id2[n][1]]
            print(f"    인물조직#{i}: {len(cset)}노드 {dict(labels)}"
                  + (f" · 조직 {orgs}" if orgs else "") + (f" · 인물 {persons}" if persons else ""))
        for i, c in enumerate(louvain[:5]):
            labels = Counter(id2.get(n, ('?', ''))[0] for n in c)
            persons = [id2[n][1] for n in c if id2.get(n, ('?', ''))[0] == 'vt_psn' and id2[n][1]][:4]
            print(f"    조직#{i}: {len(c)}노드 {dict(labels)}" + (f" · 인물 {persons}" if persons else ""))

        # ── 리포트: 구조 ──
        print("\n=== ③ 구조 (밀집 코어·연결요소) ===")
        core = M['kcore']
        top_core = sorted(core.items(), key=lambda x: -x[1])[:8]
        print("  k-core 상위(밀집 참여): " + " · ".join(
            f"{id2.get(n, ('?', '?'))[1]}(k={k})" for n, k in top_core if id2.get(n, ('?', '?'))[1]))
        ncomp = len(set(M['component'].values()))
        print(f"  약연결요소 {ncomp}개 (최대 요소가 본체)")

        # ── 리포트: 패턴(순환) ──
        print("\n=== ④ 패턴 — 순환 흐름(자금세탁 circular flow) ===")
        cyc = algo_cycles(G, max_len=6, limit=8)
        if cyc:
            for c in cyc[:5]:
                names = [str(id2.get(n, ('?', '?'))[1] or '?') for n in c]
                print(f"    순환({len(c)}): " + " → ".join(names) + f" → {names[0]}")
        else:
            print("    (길이 6 이하 순환 없음)")

        # ── SET back: 10개 노드 지표를 속성으로 ──
        if args.set:
            metrics = list(M.keys())
            print(f"\n[SET] {len(metrics)}개 지표 되쓰기: {metrics}")
            conn.autocommit = False
            cnt = 0
            for nid, (lbl, key) in id2.items():
                if lbl not in KP or not key:
                    continue
                parts = []
                for m in metrics:
                    if nid not in M[m]:   # community_person 등 부분 지표는 보유 노드만 SET
                        continue
                    v = M[m][nid]
                    # 숫자로 저장(따옴표 없음) — 문자열이면 kcore '14'<'7' 정렬 오류·
                    # WHERE 비교 깨짐 (P1-B, docs/T2C_INTEGRATED_PERF_REVIEW.md)
                    parts.append(f"n.{m}={int(v)}" if m in INT_METRICS else f"n.{m}={float(v):.6f}")
                cur.execute(f"MATCH (n:{lbl} {{{KP[lbl]}:'{esc(key)}'}}) SET " + ", ".join(parts))
                cnt += 1
                if cnt % 3000 == 0:
                    conn.commit()
                    print(f"  SET {cnt}…")
            conn.commit()
            print(f"[SET 완료] {cnt}노드에 {len(metrics)}개 지표 부여")
        conn.close()


if __name__ == '__main__':
    main()
