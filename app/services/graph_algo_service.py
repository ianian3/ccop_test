"""그래프 알고리즘 질의 서비스 — CALL ccop.algo.* 구문으로 15+ 네트워크 분석 호출.

AgensGraph에 GDS가 없어, 질의언어(Cypher-유사 CALL 또는 자연어)에서 알고리즘을
호출하면 이 서비스가 dispatch 한다:
  · 전역 지표(top): --set 으로 사전계산된 노드 속성을 Cypher 조회 (빠름, export 불필요)
  · 온디맨드(path/similar/cycles): 그래프를 NetworkX로 export 후 파라미터와 계산

질의 예:
  CALL ccop.algo.top({"metric":"betweenness","label":"vt_bacnt","topN":10})
  CALL ccop.algo.path({"src":"김미영","dst":"조지영"})
  CALL ccop.algo.similar({"node":"1003102115650","topN":5})
  CALL ccop.algo.cycles({"maxLen":6})
  CALL ccop.algo.community({"id":2})

노드 속성은 scripts/graph_analytics.py --set 으로 미리 계산해 둔다.
"""
import re
import json
import networkx as nx
import psycopg2
from flask import current_app
from app.database import safe_set_graph_path

KEYEXPR = ("coalesce(n.name,n.account_no,n.telno,n.ip_addr,n.id_val,n.flnm,"
           "n.org_name,n.atm_nm,n.email_addr,n.src_name,n.mov_id)")

# 사전계산(--set) 노드 지표 화이트리스트 — SQL injection 방지 + 오타 차단
ALLOWED_METRICS = {
    'pagerank', 'degree_cent', 'betweenness', 'eigenvector', 'closeness',
    'community_id', 'community_lp', 'community_person', 'component', 'kcore', 'clustering',
}
GRAPH_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
LABEL_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


_METRIC_KW = [  # (우선순위 순) 질문 키워드 → 지표
    (r'매개\s*중심성|betweenness', 'betweenness'),
    (r'연결\s*중심성|degree', 'degree_cent'),
    (r'고유\s*벡터|eigen', 'eigenvector'),
    (r'k[\- ]?core|케이코어', 'kcore'),
    (r'삼각형|클러스터링\s*계수|군집\s*계수', 'clustering'),
    (r'pagerank|페이지\s*랭크|중심성|영향력', 'pagerank'),
]
_LABEL_KW = [('계좌', 'vt_bacnt'), ('인물', 'vt_psn'), ('사람', 'vt_psn'), ('조직', 'vt_org'),
             ('전화', 'vt_telno'), ('아이피', 'vt_ip'), ('ip', 'vt_ip')]


def detect_algo_intent(question):
    """자연어 질문에서 네트워크 분석 인텐트 감지 — (algo, params) 또는 None.
    Cypher가 원리적으로 못 푸는 클래스(중심성 랭킹·순환)를 CALL 레이어로 사전 라우팅(P1-A)."""
    q = (question or '').strip()
    ql = q.lower()
    if re.search(r'순환|사이클|circular', ql):
        return 'cycles', {'maxLen': 6, 'limit': 12}
    metric = next((m for pat, m in _METRIC_KW if re.search(pat, ql)), None)
    if not metric:
        return None
    label = next((v for k, v in _LABEL_KW if k in ql), None)
    m = re.search(r'(\d+)\s*(개|명|위|건)', q)
    topn = min(50, int(m.group(1))) if m else 10
    return 'top', {'metric': metric, 'label': label, 'topN': topn}


_METRIC_NAME = {'pagerank': 'PageRank(영향력)', 'betweenness': '매개중심성(중개허브)',
                'degree_cent': '연결중심성', 'eigenvector': '고유벡터중심성',
                'kcore': 'k-core(밀집참여)', 'clustering': '삼각형계수(결속)'}


def format_algo_answer(res):
    """알고리즘 결과 → 한 줄 요약 텍스트 (UI answer/로그용)."""
    if res.get('algo') == 'top':
        rows = res.get('results', [])
        head = _METRIC_NAME.get(res.get('metric'), res.get('metric'))
        body = " · ".join(f"{r['rank']}.{r['key']}({r['score']})" for r in rows[:5])
        return f"{head} 상위 {len(rows)} — {body}"
    if res.get('algo') == 'cycles':
        return f"순환 흐름 {res.get('count', 0)}건 탐지 (자금세탁 typology 후보)"
    return ''


def parse_call(s):
    """`CALL ccop.algo.<name>({...})` → (algo, params). params 는 JSON 객체."""
    m = re.match(r"CALL\s+ccop\.algo\.(\w+)\s*\((.*)\)\s*;?\s*$", (s or '').strip(), re.I | re.S)
    if not m:
        raise ValueError("CALL ccop.algo.<name>({...}) 구문이 아닙니다")
    algo = m.group(1).lower()
    arg = m.group(2).strip()
    params = json.loads(arg) if arg else {}
    if not isinstance(params, dict):
        raise ValueError("파라미터는 JSON 객체여야 합니다")
    return algo, params


class GraphAlgoService:
    _cache = {}   # graph_path → (nx.DiGraph, id2)  export 캐시(온디맨드 알고리즘용)

    # ── 인프라 ──
    @staticmethod
    def _cur():
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        conn.autocommit = True
        return conn, conn.cursor()

    @staticmethod
    def _export(graph):
        """AgensGraph → NetworkX (id2: nid→(label,key)).
        캐시 + fingerprint(노드·엣지 수) 검증 — 그래프 재생성(DROP+build) 시
        stale export로 옛 결과를 반환하던 문제 방지 (검증 비용 = count 2회)."""
        conn, cur = GraphAlgoService._cur()
        safe_set_graph_path(cur, graph)
        cur.execute("MATCH (n) RETURN count(n)")
        n_cnt = cur.fetchone()[0]
        cur.execute("MATCH ()-[r]->() RETURN count(r)")
        e_cnt = cur.fetchone()[0]
        fp = (n_cnt, e_cnt)
        cached = GraphAlgoService._cache.get(graph)
        if cached and cached[0] == fp:
            conn.close()
            return cached[1], cached[2]
        cur.execute(f"MATCH (n) RETURN id(n), label(n), {KEYEXPR}")
        id2 = {str(nid): (lbl, key) for nid, lbl, key in cur.fetchall()}
        G = nx.DiGraph()
        G.add_nodes_from(id2.keys())
        cur.execute("MATCH (a)-[r]->(b) RETURN id(a), id(b)")
        for a, b in cur.fetchall():
            G.add_edge(str(a), str(b))
        conn.close()
        GraphAlgoService._cache[graph] = (fp, G, id2)
        return G, id2

    @staticmethod
    def invalidate(graph=None):
        """그래프 변경 시 export 캐시 무효화."""
        if graph:
            GraphAlgoService._cache.pop(graph, None)
        else:
            GraphAlgoService._cache.clear()

    # ── ① 전역 지표 상위 (사전계산 속성 조회) ──
    @staticmethod
    def top(graph, params):
        metric = params.get('metric', 'pagerank')
        label = params.get('label')
        topn = int(params.get('topN', params.get('topn', 10)))
        if metric not in ALLOWED_METRICS:
            raise ValueError(f"미지원 지표 '{metric}' (가능: {sorted(ALLOWED_METRICS)})")
        if label and not LABEL_RE.match(label):
            raise ValueError("label 형식 오류")
        conn, cur = GraphAlgoService._cur()
        safe_set_graph_path(cur, graph)
        lf = f":{label}" if label else ""
        cur.execute(f"MATCH (n{lf}) WHERE n.{metric} IS NOT NULL "
                    f"RETURN {KEYEXPR}, n.{metric}, label(n)")
        rows = []
        for k, v, l in cur.fetchall():
            try:
                rows.append((k, float(str(v).strip('"')), l))
            except (ValueError, TypeError):
                pass
        conn.close()
        rows.sort(key=lambda x: -x[1])   # AgensGraph 문자열 정렬 한계 → Python 정렬
        return {'algo': 'top', 'metric': metric, 'label': label, 'total': len(rows),
                'results': [{'rank': i + 1, 'key': k, 'score': round(s, 6), 'label': l}
                            for i, (k, s, l) in enumerate(rows[:topn])]}

    # ── ② 최단경로 (온디맨드) ──
    @staticmethod
    def path(graph, params):
        G, id2 = GraphAlgoService._export(graph)
        key2id = {v[1]: k for k, v in id2.items() if v[1]}
        src = key2id.get(str(params.get('src')))
        dst = key2id.get(str(params.get('dst')))
        if not src or not dst:
            return {'algo': 'path', 'error': 'src/dst 노드를 찾을 수 없음', 'path': None}
        try:
            p = nx.shortest_path(G.to_undirected(), src, dst)
            return {'algo': 'path', 'length': len(p) - 1,
                    'path': [{'key': id2[n][1], 'label': id2[n][0]} for n in p]}
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return {'algo': 'path', 'path': None, 'note': '연결 경로 없음'}

    # ── ③ 공통이웃 Jaccard 유사도 (온디맨드) ──
    @staticmethod
    def similar(graph, params):
        G, id2 = GraphAlgoService._export(graph)
        key2id = {v[1]: k for k, v in id2.items() if v[1]}
        node = key2id.get(str(params.get('node')))
        if not node:
            return {'algo': 'similar', 'error': '노드를 찾을 수 없음', 'results': []}
        topn = int(params.get('topN', 10))
        Gu = G.to_undirected()
        nb = set(Gu[node])
        cand = set()
        for x in nb:
            cand |= set(Gu[x])
        cand.discard(node)
        out = []
        for o in cand:
            onb = set(Gu[o])
            inter = nb & onb
            if inter:
                out.append((o, len(inter) / len(nb | onb), len(inter)))
        out.sort(key=lambda x: -x[1])
        return {'algo': 'similar', 'node': params.get('node'),
                'results': [{'key': id2[o][1], 'label': id2[o][0],
                             'jaccard': round(j, 4), 'common': c} for o, j, c in out[:topn]]}

    # ── ④ 순환 흐름 탐지 (온디맨드) ──
    @staticmethod
    def cycles(graph, params):
        G, id2 = GraphAlgoService._export(graph)
        maxlen = int(params.get('maxLen', 6))
        limit = int(params.get('limit', 15))
        out = []
        try:
            it = nx.simple_cycles(G, length_bound=maxlen)
        except TypeError:
            it = (c for c in nx.simple_cycles(G) if len(c) <= maxlen)
        for c in it:
            if len(c) >= 2:
                out.append(c)
                if len(out) >= limit:
                    break
        return {'algo': 'cycles', 'count': len(out),
                'cycles': [[{'key': id2.get(n, ('?', '?'))[1], 'label': id2.get(n, ('?', '?'))[0]}
                            for n in c] for c in out]}

    # ── ⑤ 커뮤니티 멤버 조회 (사전계산 속성) ──
    @staticmethod
    def community(graph, params):
        cid = int(params.get('id', 0))
        metric = params.get('metric', 'community_id')
        if metric not in ('community_id', 'community_lp', 'community_person'):
            raise ValueError("community metric은 community_id/community_lp/community_person만")
        conn, cur = GraphAlgoService._cur()
        safe_set_graph_path(cur, graph)
        # P1-B 이후 지표는 숫자 저장 — 문자열 quote 시 타입 불일치로 0건 (검증에서 적발)
        cur.execute(f"MATCH (n) WHERE n.{metric}={cid} RETURN {KEYEXPR}, label(n)")
        members = [{'key': k, 'label': l} for k, l in cur.fetchall() if k]
        conn.close()
        from collections import Counter
        return {'algo': 'community', 'id': cid, 'metric': metric, 'size': len(members),
                'labels': dict(Counter(m['label'] for m in members)),
                'members': members[:50]}

    # ── dispatch ──
    _FN = None

    @staticmethod
    def dispatch(graph, algo, params):
        if not GRAPH_RE.match(graph or ''):
            raise ValueError("graph_path 형식 오류")
        fn = {
            'top': GraphAlgoService.top,
            'path': GraphAlgoService.path,
            'similar': GraphAlgoService.similar,
            'cycles': GraphAlgoService.cycles,
            'community': GraphAlgoService.community,
        }.get((algo or '').lower())
        if not fn:
            raise ValueError(f"미지원 알고리즘 '{algo}' "
                             f"(가능: top·path·similar·cycles·community)")
        return fn(graph, params or {})
