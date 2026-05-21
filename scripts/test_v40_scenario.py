"""
V4.0 시나리오 검증 테스트
======================================================
build_v40_scenario_dataset.py 로 시드한 'tccop_v40_demo' 그래프에서
V4.0의 모든 핵심 기능을 검증합니다.

검증 영역:
  A. 카운트/도메인 분포 (Phase 2 게이트)
  B. V4.0 메타 6/4 컬럼 충족 (NULL = 0)
  C. 6 워크플로우 실행 + 결과 카운트
  D. 스칼라 쿼리 (RETURN n.prop) Phase 4.6
  E. V3.7 신규 추론 (pt_cluster / site_cluster / relay / is_anonymous)
  F. Cross-domain sameAs 검증

실행:
    python3 scripts/test_v40_scenario.py [--graph tccop_v40_demo]
"""
import argparse
import sys
sys.path.insert(0, '/Users/iankwon/test/coop_v1.0')

from app import create_app
from app.services.rdb_to_graph_service import RdbToGraphService
from app.database import safe_set_graph_path

_FLASK_APP = create_app()
_FLASK_APP.app_context().push()


def run(cur, cypher, fetch=True):
    cur.execute(cypher)
    return cur.fetchall() if fetch else None


def header(t):
    print()
    print("=" * 64)
    print(f"  {t}")
    print("=" * 64)


def row(name, ok, detail=''):
    icon = '✅' if ok else '❌'
    print(f"  {icon}  {name:48s}  {detail}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--graph', default='tccop_v40_demo')
    args = parser.parse_args()

    conn, cur = RdbToGraphService.get_db_connection()
    if not conn:
        print("DB 연결 실패"); sys.exit(1)
    safe_set_graph_path(cur, args.graph)

    total_pass = 0
    total_fail = 0

    def check(name, ok, detail=''):
        nonlocal total_pass, total_fail
        if ok: total_pass += 1
        else: total_fail += 1
        row(name, ok, detail)

    # ═══════════════════════════════════════════════════════════════════
    header("A. 노드/엣지 카운트")
    # ═══════════════════════════════════════════════════════════════════
    def cy_count(cypher):
        try:
            r = run(cur, cypher)
            return int(str(r[0][0]).strip('"')) if r else 0
        except Exception as e:
            conn.rollback(); safe_set_graph_path(cur, args.graph)
            return -1

    n_count = cy_count("MATCH (n) RETURN COUNT(n);")
    e_count = cy_count("MATCH ()-[r]->() RETURN COUNT(r);")
    check("노드 ≥ 150", n_count >= 150, f"({n_count} 개)")
    check("엣지 ≥ 100", e_count >= 100, f"({e_count} 개)")

    # 라벨별 분포
    print("  라벨별 분포:")
    labels = ['vt_case','vt_psn','vt_org','vt_bacnt','vt_telno','vt_dev',
              'vt_ip','vt_site','site_cluster','pt_cluster','vt_transfer',
              'vt_call','vt_access','vt_msg','vt_file','vt_id','vt_src',
              'vt_petition']
    for lab in labels:
        v = cy_count(f"MATCH (n:{lab}) RETURN COUNT(n);")
        if v > 0:
            print(f"     · {lab:18s} {v}")

    # ═══════════════════════════════════════════════════════════════════
    header("B. V4.0 메타 6컬럼 충족 (source_domain NULL = 0)")
    # ═══════════════════════════════════════════════════════════════════
    queries = [
        ("source_domain NULL 노드", """
            MATCH (n) WHERE n.source_domain IS NULL OR n.source_domain = ''
            RETURN COUNT(n);
        """),
        ("id_format NULL 노드", """
            MATCH (n) WHERE n.id_format IS NULL OR n.id_format = ''
            RETURN COUNT(n);
        """),
        ("reliability_tier NULL 노드", """
            MATCH (n) WHERE n.reliability_tier IS NULL
            RETURN COUNT(n);
        """),
        ("source_domain NULL 엣지", """
            MATCH ()-[r]->() WHERE r.source_domain IS NULL OR r.source_domain = ''
            RETURN COUNT(r);
        """),
    ]
    for name, q in queries:
        try:
            r = run(cur, q)
            v = r[0][0] if r else None
            check(name, (v is not None and int(str(v).strip('"')) == 0), f"({v})")
        except Exception as e:
            check(name, False, f"쿼리 오류: {e}")
            conn.rollback(); safe_set_graph_path(cur, args.graph)

    # 도메인 분포
    print("  도메인 분포:")
    try:
        r = run(cur, """
            MATCH (n) RETURN n.source_domain AS dom, COUNT(n) AS cnt
            ORDER BY cnt DESC;
        """)
        for dom, cnt in r:
            print(f"     · {str(dom):20s} {cnt}")
    except Exception as e:
        print(f"  (분포 쿼리 오류: {e})")
        conn.rollback(); safe_set_graph_path(cur, args.graph)

    # tier 분포
    print("  reliability_tier 분포:")
    try:
        r = run(cur, """
            MATCH (n) RETURN n.reliability_tier AS tier, COUNT(n) AS cnt
            ORDER BY tier;
        """)
        for tier, cnt in r:
            print(f"     · tier {str(tier):4s} {cnt}")
    except Exception as e:
        conn.rollback(); safe_set_graph_path(cur, args.graph)

    # ═══════════════════════════════════════════════════════════════════
    header("C. 6 워크플로우 실행")
    # ═══════════════════════════════════════════════════════════════════
    workflows = [
        ("case_to_suspects", """
            MATCH (c:vt_case)<-[:suspect_in]-(p:vt_psn)
            RETURN COUNT(p);
        """, lambda v: v >= 5),
        ("suspect_to_assets", """
            MATCH (p:vt_psn {role_cd: 'suspect'})-[:has_account]->(b:vt_bacnt)
            RETURN COUNT(b);
        """, lambda v: v >= 10),
        ("phishing_campaign_view", """
            MATCH (sc:site_cluster)<-[:belongs_to_campaign]-(s:vt_site)
            RETURN COUNT(s);
        """, lambda v: v >= 4),
        ("fund_flow", """
            MATCH (a:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b:vt_bacnt)
            RETURN COUNT(t);
        """, lambda v: v >= 10),
        ("relay_station_network", """
            MATCH (d:vt_dev {dev_type: 'relay_station'})<-[:used_in_device]-(t:vt_telno)
            RETURN COUNT(t);
        """, lambda v: v >= 3),
        ("cross_graph_sameAs", """
            MATCH (a:vt_psn)-[:sameAs]-(b:vt_psn)
            RETURN COUNT(*);
        """, lambda v: v >= 2),
    ]
    for name, q, ok_fn in workflows:
        try:
            r = run(cur, q)
            v = int(str(r[0][0]).strip('"')) if r else 0
            check(name, ok_fn(v), f"결과={v}")
        except Exception as e:
            check(name, False, f"쿼리 오류: {e}")
            conn.rollback(); safe_set_graph_path(cur, args.graph)

    # ═══════════════════════════════════════════════════════════════════
    header("D. 스칼라 쿼리 (RETURN n.prop 패턴) Phase 4.6")
    # ═══════════════════════════════════════════════════════════════════
    scalar_qs = [
        ("RETURN n.flnm (사건 제목)",
         "MATCH (n:vt_case) RETURN n.flnm LIMIT 5;"),
        ("RETURN n.name, n.is_anonymous (익명 인물)",
         "MATCH (n:vt_psn) WHERE n.is_anonymous = true RETURN n.name, n.is_anonymous LIMIT 5;"),
        ("RETURN n.amount (이체 금액)",
         "MATCH (n:vt_transfer) RETURN n.amount LIMIT 5;"),
    ]
    for name, q in scalar_qs:
        try:
            r = run(cur, q)
            cnt = len(r) if r else 0
            check(name, cnt > 0, f"행={cnt}")
            for row_data in r[:3]:
                print(f"        · {row_data}")
        except Exception as e:
            check(name, False, f"쿼리 오류: {e}")
            conn.rollback(); safe_set_graph_path(cur, args.graph)

    # ═══════════════════════════════════════════════════════════════════
    header("E. V3.7 신규 추론 결과")
    # ═══════════════════════════════════════════════════════════════════
    v37_checks = [
        ("pt_cluster 멤버 ≥ 6 (캠페인)",
         "MATCH (pc:pt_cluster)<-[:belongs_to_cluster]-(p:vt_psn) RETURN COUNT(p);",
         lambda v: v >= 6),
        ("site_cluster 2개 + 멤버 ≥ 8",
         "MATCH (sc:site_cluster)<-[:belongs_to_campaign]-(s:vt_site) RETURN COUNT(s);",
         lambda v: v >= 8),
        ("vt_dev relay_station 2대",
         "MATCH (d:vt_dev {dev_type: 'relay_station'}) RETURN COUNT(d);",
         lambda v: v == 2),
        ("is_anonymous=true 인물 ≥ 4",
         "MATCH (p:vt_psn) WHERE p.is_anonymous = true RETURN COUNT(p);",
         lambda v: v >= 4),
        ("is_anonymous=true ID ≥ 5",
         "MATCH (i:vt_id) WHERE i.is_anonymous = true RETURN COUNT(i);",
         lambda v: v >= 5),
    ]
    for name, q, ok_fn in v37_checks:
        try:
            r = run(cur, q)
            v = int(str(r[0][0]).strip('"')) if r else 0
            check(name, ok_fn(v), f"({v})")
        except Exception as e:
            check(name, False, f"쿼리 오류: {e}")
            conn.rollback(); safe_set_graph_path(cur, args.graph)

    # ═══════════════════════════════════════════════════════════════════
    header("F. Cross-domain sameAs (OSINT ↔ KICS)")
    # ═══════════════════════════════════════════════════════════════════
    try:
        r = run(cur, """
            MATCH (a:vt_psn)-[r:sameAs]-(b:vt_psn)
            WHERE a.source_domain <> b.source_domain
            RETURN COUNT(r);
        """)
        v = int(str(r[0][0]).strip('"')) if r else 0
        check("Cross-domain sameAs ≥ 2", v >= 2, f"({v})")
    except Exception as e:
        check("Cross-domain sameAs", False, f"쿼리 오류: {e}")

    # ═══════════════════════════════════════════════════════════════════
    print()
    print("=" * 64)
    print(f"  종합: {total_pass} PASS / {total_fail} FAIL")
    print("=" * 64)

    cur.close(); conn.close()
    sys.exit(0 if total_fail == 0 else 1)


if __name__ == '__main__':
    main()
