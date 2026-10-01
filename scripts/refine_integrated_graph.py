#!/usr/bin/env python3
"""통합 그래프(ccop_ep_integrated) 정밀화 후처리 — build_integrated_graph.py 재생성 후 실행.

① dpstr 병합충돌 해소: 같은 계좌번호가 EP마다 다른 명의(EP1 이진아 vs EP7 적요 푸른웹/블루웹)로 덮이는 문제 →
   has_account 명의 중 **상호/적요 패턴(웹·미디어 등) 제외한 사람이름 우선**으로 dpstr 통일, 원래 값은 dpstr_variants 보존.
② same_as 후보: 같은 계좌·전화를 공유하는 **사람 vt_psn 쌍**(상호/적요 제외) = 같은 실인물 후보 →
   same_as {verified:false, traversal_policy:candidate_only}. IP 공유는 콜센터 공동사용이라 제외.
멱등(same_as 전체 삭제 후 재생성). 실행: python3 scripts/refine_integrated_graph.py
"""
import sys, os, re
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.database import safe_set_graph_path
import psycopg2
from collections import defaultdict

INTEG = 'ccop_ep_integrated'
# 상호·적요·기관 패턴(사람 명의가 아님)
BIZLIKE = re.compile(r'(웹|미디어|프로젝트|컴퍼니|㈜|은행|카드|보험|화재|생명|캐피탈|증권|저축|스튜디오|헤어|베베|월세|마트|프로|닷컴|샵|스토어)')


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def is_person(name):
    return bool(name) and re.fullmatch(r'[가-힣]{2,4}', name) and not BIZLIKE.search(name)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--graph', default=INTEG, help='대상 통합 그래프 (기본 ccop_ep_integrated)')
    graph = ap.parse_args().graph
    app = create_app()
    with app.app_context():
        conn = psycopg2.connect(**app.config['DB_CONFIG']); conn.autocommit = True
        cur = conn.cursor()
        safe_set_graph_path(cur, graph)

        def q(c):
            cur.execute(c); return cur.fetchall()

        # ── ① dpstr 병합충돌 해소 (사람이름 우선) ──
        rows = q("MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) RETURN b.account_no, p.name")
        acc_names = defaultdict(set)
        for ac, nm in rows:
            if ac and nm:
                acc_names[ac].add(nm)
        cur_dpstr = {r[0]: r[1] for r in q("MATCH (b:vt_bacnt) RETURN b.account_no, b.dpstr")}
        fixed = 0
        for ac, names in acc_names.items():
            people = sorted(n for n in names if is_person(n))
            canonical = people[0] if people else sorted(names)[0]
            variants = set(names)
            cd = cur_dpstr.get(ac)
            if cd and cd not in variants:
                variants.add(cd)
            if cd != canonical:
                cur.execute(f"MATCH (b:vt_bacnt {{account_no:'{esc(ac)}'}}) "
                            f"SET b.dpstr='{esc(canonical)}', b.dpstr_variants='{esc(','.join(sorted(variants)))}'")
                fixed += 1
        print(f"① dpstr 정밀화: {fixed}계좌 (사람이름 우선, 상호/적요 제외)")

        # ── ② same_as 후보 (사람끼리만) ──
        cur.execute("CREATE ELABEL IF NOT EXISTS same_as")
        # 이 스크립트가 만든 후보만 정리 후 재생성 — 2026-10-01: 통합 빌더의 EP 간 동일 이름 후보(BUILD-name-match)는 보존
        cur.execute("MATCH (:vt_psn)-[e:same_as]->(:vt_psn) WHERE e.source_id = 'REFINE-shared-key' DELETE e")
        made = defaultdict(int)
        for rel, conf in [('has_account', 0.7), ('owns_phone', 0.65)]:   # V4.9: confidence 는 숫자
            method = 'shared_account' if rel == 'has_account' else 'shared_phone'
            # 2026-10-01 정합 2b: 인물은 psn_id 로 찾는다(이름은 EP 마다 다른 사람일 수 있음 — A안)
            pairs = q(f"MATCH (p1:vt_psn)-[:{rel}]->(x)<-[:{rel}]-(p2:vt_psn) "
                      f"WHERE id(p1) < id(p2) RETURN DISTINCT p1.name, p2.name, p1.psn_id, p2.psn_id")
            for n1, n2, i1, i2 in pairs:
                if not (is_person(n1) and is_person(n2)) or not (i1 and i2):
                    continue
                cur.execute(f"MATCH (p1:vt_psn {{psn_id:'{esc(i1)}'}}), (p2:vt_psn {{psn_id:'{esc(i2)}'}}) "
                            f"MERGE (p1)-[e:same_as]->(p2) "
                            # V4.9 속성명 통일: match_basis(구 method)·confidence(구 conf)·review_status
                            f"SET e.source_id='REFINE-shared-key', e.match_basis='{method}', e.confidence={conf}, "
                            f"e.review_status='pending', e.verified=false, e.traversal_policy='candidate_only'")
                made[method] += 1
        sa = q("MATCH ()-[e:same_as]->() RETURN count(*)")[0][0]
        print(f"② same_as 후보: {sa} (candidate_only·verified=false) · 방법별 {dict(made)}")
        samp = q("MATCH (p1:vt_psn)-[e:same_as]->(p2:vt_psn) RETURN p1.name, p2.name, e.match_basis")
        print("   샘플:", [(a, b, m) for a, b, m in samp[:8]])
        conn.close()


if __name__ == '__main__':
    main()
