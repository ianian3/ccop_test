#!/usr/bin/env python3
"""vt_id 엔티티 해소 — sameAs 후보 생성 (자동 확정 금지, candidate_only).

② 네이버 마스킹 쌍: 'traveller5' ↔ 'traveller5****' (접두 일치, 비식별 마스킹 차이) — conf 0.60
③ 플랫폼 교차 동일 핸들: 'coma1576'(kakao) ↔ 'coma1576'(naver) — conf 0.75 (동일인 단서)

원칙(V4.5 G11 · EntityResolutionCandidate): 후보만 자동 생성.
  traversal_policy='candidate_only'(점선·기본 미순회) · verified=false · creation_method='inference'
  → 수사관이 확인 후에만 follow 로 승격(확정). 자동 병합 금지.

실행: python3 scripts/generate_sameas_candidates.py [--dry-run]
"""
import argparse
import re
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.database import safe_set_graph_path
import psycopg2

GRAPH = 'tccop_graph_v6'


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def find_candidates(cur):
    """(id_val_a, platform_a, id_val_b, platform_b, kind, confidence, basis) 후보 리스트."""
    cands = []
    # 전체 vt_id 로드
    cur.execute("MATCH (i:vt_id) RETURN i.platform, i.id_val")
    ids = [(str(p), str(v)) for p, v in cur.fetchall() if v]

    # ② 마스킹 접두 매칭 (동일 platform)
    masked = [(p, v) for p, v in ids if '*' in v]
    full = [(p, v) for p, v in ids if '*' not in v]
    for mp, mv in masked:
        prefix = mv.split('*')[0]
        if len(prefix) < 3:            # 접두 3자 미만은 오탐 위험 → 제외
            continue
        for fp, fv in full:
            if fp == mp and fv.startswith(prefix):
                cands.append((mv, mp, fv, fp, 'masked_prefix', 0.60,
                              f"네이버 마스킹 접두 일치('{prefix}…')"))

    # ③ 플랫폼 교차 동일 핸들 (id_val 정확 일치, platform 다름)
    from collections import defaultdict
    by_val = defaultdict(set)
    for p, v in ids:
        by_val[v].add(p)
    for v, plats in by_val.items():
        if '*' in v:
            continue
        pl = sorted(plats)
        for a in range(len(pl)):
            for b in range(a + 1, len(pl)):
                cands.append((v, pl[a], v, pl[b], 'cross_platform', 0.75,
                              f"플랫폼 교차 동일 핸들('{v}': {pl[a]}↔{pl[b]})"))
    return cands


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    app = create_app()
    with app.app_context():
        conn = psycopg2.connect(**app.config['DB_CONFIG'])
        conn.autocommit = False
        cur = conn.cursor()
        safe_set_graph_path(cur, GRAPH)
        cands = find_candidates(cur)

        print(f"[후보] sameAs {len(cands)}쌍")
        for a, ap_, b, bp, kind, conf, basis in cands:
            print(f"  [{kind}] {ap_}:{a}  ~  {bp}:{b}  (conf {conf}) — {basis}")

        if args.dry_run or not cands:
            conn.rollback(); conn.close(); return

        cur.execute("CREATE ELABEL IF NOT EXISTS sameAs;")
        n = 0
        for a, ap_, b, bp, kind, conf, basis in cands:
            q = (f"MATCH (x:vt_id {{platform:'{esc(ap_)}', id_val:'{esc(a)}'}}), "
                 f"(y:vt_id {{platform:'{esc(bp)}', id_val:'{esc(b)}'}}) "
                 f"MERGE (x)-[e:sameAs]->(y) "
                 f"SET e.traversal_policy='candidate_only', e.verified=false, "
                 f"e.creation_method='inference', e.confidence={conf}, "
                 f"e.resolution_kind='{esc(kind)}', e.inference_basis='{esc(basis)}', "
                 f"e.source_id='ER-vtid-{esc(kind)}'")
            cur.execute(q)
            n += 1
        conn.commit()
        print(f"\n[생성 완료] sameAs 후보 {n}개 (candidate_only·verified=false) → {GRAPH}")
        conn.close()


if __name__ == '__main__':
    main()
