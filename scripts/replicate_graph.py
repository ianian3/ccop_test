#!/usr/bin/env python3
"""AgensGraph 그래프 복제 — 로컬 DB → 운영 DB (속성 완전 보존, 결정론).

용도: EP 적재 중 일부(EP3-012·EP6 naver·EP7-045)가 세션 인라인이라 스크립트
재실행으로 재현 불가 → 그래프를 데이터 그대로 복제. 신규 그래프만 생성하며
대상 DB의 기존 그래프는 건드리지 않는다. (2026-09-03 운영 이식 승인)

방식: 노드 CREATE 시 임시 _src_id 부여 → property index → 엣지 MATCH(_src_id)
      → 완료 후 _src_id 제거. 그래프별 노드/엣지 수 대조 검증.

실행:
  DST_HOST=49.50.128.28 DST_PORT=5333 python3 scripts/replicate_graph.py ep1_graph ep2_graph ...
  (소스 = .env 의 로컬 DB · 대상 크레덴셜은 소스와 동일 계정 사용)
"""
import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv
load_dotenv()
import psycopg2

SRC = dict(dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
           password=os.getenv('DB_PASSWORD'), host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT'))
DST = dict(SRC, host=os.environ['DST_HOST'], port=os.environ.get('DST_PORT', '5432'),
           dbname=os.environ.get('DST_NAME', os.getenv('DB_NAME')))

GRAPH_RE = __import__('re').compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def props_literal(props):
    """dict → Cypher 맵 리터럴 (agtype 문자열/숫자 보존)."""
    parts = []
    for k, v in (props or {}).items():
        if v is None:
            continue
        if isinstance(v, bool):
            parts.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            parts.append(f"{k}: {v}")
        else:
            parts.append(f"{k}: '{esc(v)}'")
    return "{" + ", ".join(parts) + "}"


def replicate(graph):
    assert GRAPH_RE.match(graph), graph
    s = psycopg2.connect(**SRC); s.autocommit = True; sc = s.cursor()
    d = psycopg2.connect(**DST); d.autocommit = False; dc = d.cursor()
    sc.execute(f"SET graph_path = {graph}")

    # 소스 실측
    sc.execute("MATCH (n) RETURN count(n)"); n_src = sc.fetchone()[0]
    sc.execute("MATCH ()-[r]->() RETURN count(r)"); e_src = sc.fetchone()[0]
    print(f"══ {graph} — 소스 노드 {n_src:,} · 엣지 {e_src:,} ══")

    # 대상 그래프 초기화
    dc.execute(f"DROP GRAPH IF EXISTS {graph} CASCADE")
    dc.execute(f"CREATE GRAPH {graph}")
    dc.execute(f"SET graph_path = {graph}")

    # 라벨 생성
    sc.execute("MATCH (n) RETURN DISTINCT label(n)")
    vlabels = [r[0] for r in sc.fetchall()]
    sc.execute("MATCH ()-[r]->() RETURN DISTINCT type(r)")
    elabels = [r[0] for r in sc.fetchall()]
    for lb in vlabels:
        dc.execute(f"CREATE VLABEL IF NOT EXISTS {lb}")
    for eb in elabels:
        dc.execute(f"CREATE ELABEL IF NOT EXISTS {eb}")

    # ── 노드 복제 (+_src_id) ──
    sc.execute("MATCH (n) RETURN id(n), label(n), properties(n)")
    cnt = 0
    for nid, lbl, props in sc.fetchall():
        p = props if isinstance(props, dict) else json.loads(props)
        p['_src_id'] = str(nid)
        dc.execute(f"CREATE (:{lbl} {props_literal(p)})")
        cnt += 1
        if cnt % 2000 == 0:
            d.commit(); print(f"  노드 {cnt:,}…")
    d.commit()

    # _src_id 인덱스 (엣지 MATCH 가속)
    for lb in vlabels:
        try:
            dc.execute(f"CREATE PROPERTY INDEX ON {lb} (_src_id)")
        except Exception:
            d.rollback()
    d.commit()

    # ── 엣지 복제 ──
    sc.execute("MATCH (a)-[r]->(b) RETURN id(a), label(a), id(b), label(b), type(r), properties(r)")
    cnt = 0
    for aid, albl, bid, blbl, etype, props in sc.fetchall():
        p = props if isinstance(props, dict) else json.loads(props)
        dc.execute(f"MATCH (a:{albl} {{_src_id:'{aid}'}}), (b:{blbl} {{_src_id:'{bid}'}}) "
                   f"CREATE (a)-[:{etype} {props_literal(p)}]->(b)")
        cnt += 1
        if cnt % 2000 == 0:
            d.commit(); print(f"  엣지 {cnt:,}…")
    d.commit()

    # _src_id 제거
    for lb in vlabels:
        dc.execute(f"MATCH (n:{lb}) REMOVE n._src_id")
    d.commit()

    # ── 검증 ──
    dc.execute("MATCH (n) RETURN count(n)"); n_dst = dc.fetchone()[0]
    dc.execute("MATCH ()-[r]->() RETURN count(r)"); e_dst = dc.fetchone()[0]
    ok = (n_src == n_dst and e_src == e_dst)
    print(f"  → 대상 노드 {n_dst:,} · 엣지 {e_dst:,}  {'✅ 일치' if ok else '❌ 불일치!'}")
    s.close(); d.close()
    return ok


if __name__ == '__main__':
    graphs = sys.argv[1:] or [f'ep{i}_graph' for i in range(1, 11)]
    print(f"소스 {SRC['host']}:{SRC['port']} → 대상 {DST['host']}:{DST['port']} · 그래프 {len(graphs)}개")
    bad = [g for g in graphs if not replicate(g)]
    print("\n" + ("✅ 전 그래프 복제·검증 완료" if not bad else f"❌ 불일치: {bad}"))
    sys.exit(1 if bad else 0)
