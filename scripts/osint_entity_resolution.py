#!/usr/bin/env python3
"""
CCOP 배치 엔티티해소(EntityResolution) — OSINT ↔ 수사 그래프 sameAs 브릿지 (초안 / 착수용)

정규화 식별자가 일치하는 교차도메인 노드 쌍을 찾아 sameAs 엣지를 idempotent 하게 생성한다.
- blocking: 공통 객체 노드(계좌·전화·IP·URL·해시·계정)의 표준 식별자 정확일치 (같은 자연키=같은 실체)
- 정확일치(exact)  → 자동 confirmed(정책에 따라) / 사람·조직 fuzzy → 항상 pending(검토)
- 전건 자동 sameAs 금지: 교차도메인(osint ↔ 비-osint) 후보만, MERGE로 중복 방지

전제(중요): OSINT·수사 노드가 **같은 그래프**에 source_domain 태그로 공존.
  (별도 그래프면 relational 브릿지 테이블로 조인 — 하단 [SEP] 주석 참조)

사용법:
  python scripts/osint_entity_resolution.py --graph tccop_graph_v6 --confirm-exact
  python scripts/osint_entity_resolution.py --graph tccop_graph_v6 --dry-run       # 후보 건수만(MERGE 안 함)
  python scripts/osint_entity_resolution.py --print-cypher                          # DB 미접촉, 실행할 Cypher만 출력
⚠️ AgensGraph 버전별 확인: cypher() 반환타입 agtype, MERGE/SET 구문 ([AGVER])
"""
import argparse
import os
import sys
from datetime import datetime, timezone

# 공통 객체 노드 = (라벨, 표준 식별자 속성). 식별자 정확일치 = 동일 실체(고신뢰).
EXACT_TYPES = [
    ("vt_bacnt", "account_no"),
    ("vt_telno", "telno"),
    ("vt_ip",    "ip_addr"),
    ("vt_site",  "url_addr"),
    ("vt_file",  "hash_val"),
    ("vt_id",    "id_val"),
]
# 사람/조직 = fuzzy (이름+생년/기관명 유사도) — 항상 검토. (초안: 스텁, 정확일치 컬럼만 예시)
FUZZY_TYPES = [
    ("vt_psn", "korn_flnm"),   # + dob 조합, 유사도 임계 필요
    ("vt_org", "org_name"),
]


def exact_match_cypher(label, idprop, ts, status, dry):
    """정확일치 sameAs. osint 노드(a) → 비-osint 노드(b), 동일 식별자."""
    where = (f"a.{idprop} IS NOT NULL AND a.{idprop} = b.{idprop} "
             f"AND a.source_domain = 'osint' "
             f"AND (b.source_domain IS NULL OR b.source_domain <> 'osint')")
    if dry:
        return (f"MATCH (a:{label}), (b:{label}) WHERE {where} "
                f"RETURN count(*) AS cnt")
    # MERGE idempotent + review_status
    return (f"MATCH (a:{label}), (b:{label}) WHERE {where} "
            f"MERGE (a)-[r:sameAs]->(b) "
            f"ON CREATE SET r.match_score = 1.0, r.match_basis = 'exact:{idprop}', "
            f"r.review_status = '{status}', r.rec_created = '{ts}', r.source_domain='inference' "
            f"RETURN count(r) AS cnt")


def fuzzy_stub_cypher(label, idprop):
    """[스텁] 사람/조직 fuzzy — 이름 정확일치만 예시(실구현: dob·유사도·임계). 항상 pending."""
    return (f"// TODO fuzzy: {label}.{idprop} 유사도(예: dob 조합, 편집거리/자모유사) + 임계 후 pending sameAs\n"
            f"MATCH (a:{label}),(b:{label}) "
            f"WHERE a.{idprop} IS NOT NULL AND a.{idprop}=b.{idprop} "
            f"AND a.source_domain='osint' AND coalesce(b.source_domain,'x')<>'osint' "
            f"MERGE (a)-[r:sameAs]->(b) "
            f"ON CREATE SET r.match_score=0.6, r.match_basis='name:{idprop}', r.review_status='pending'")


def connect():
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    return psycopg2.connect(
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST", "127.0.0.1"), port=os.getenv("DB_PORT", "5432"))


def set_graph(cur, graph):
    import re
    assert re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", graph), f"invalid graph: {graph}"
    cur.execute(f"SET graph_path = {graph}")   # AgensGraph 네이티브 — 이후 Cypher 직접 실행


def run(cur, q):
    cur.execute(q)
    row = cur.fetchone()
    try:
        return int(str(row[0])) if row and row[0] is not None else 0
    except (ValueError, TypeError):
        return 0


def main():
    ap = argparse.ArgumentParser(description="CCOP OSINT↔수사 sameAs 배치 엔티티해소")
    ap.add_argument("--graph", default="tccop_graph_v6", help="OSINT·수사가 공존하는 그래프")
    ap.add_argument("--confirm-exact", action="store_true", help="정확일치를 confirmed 로(기본 pending)")
    ap.add_argument("--dry-run", action="store_true", help="후보 건수만(MERGE 안 함)")
    ap.add_argument("--print-cypher", action="store_true", help="DB 미접촉 — 실행할 Cypher만 출력")
    ap.add_argument("--fuzzy", action="store_true", help="사람/조직 fuzzy 스텁도 실행")
    args = ap.parse_args()

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status = "confirmed" if args.confirm_exact else "pending"

    if args.print_cypher:
        print("=== 정확일치(exact) sameAs — 실행 예정 Cypher ===")
        for label, idp in EXACT_TYPES:
            print(f"\n# {label}.{idp}")
            print(exact_match_cypher(label, idp, ts, status, dry=False))
        print("\n=== fuzzy(사람/조직) — 스텁 ===")
        for label, idp in FUZZY_TYPES:
            print(f"\n# {label}.{idp}\n{fuzzy_stub_cypher(label, idp)}")
        return

    conn = connect(); cur = conn.cursor()
    # 검토 로그(관계형 미러 — 검토 UI/워크플로우용)
    cur.execute("""CREATE SCHEMA IF NOT EXISTS graph_meta;
                   CREATE TABLE IF NOT EXISTS graph_meta.sameas_run (
                     run_id bigserial PRIMARY KEY, graph text, label text, basis text,
                     matched int, status text, dry boolean, ran_at timestamptz DEFAULT now());""")
    set_graph(cur, args.graph)
    if not args.dry_run:
        cur.execute("CREATE ELABEL IF NOT EXISTS sameAs")
    total = 0
    try:
        for label, idp in EXACT_TYPES:
            q = exact_match_cypher(label, idp, ts, status, dry=args.dry_run)
            cnt = run(cur, q)
            total += cnt
            print(f"  {label:12s} exact:{idp:12s} → {cnt}건" + (" (dry)" if args.dry_run else f" [{status}]"))
            if not args.dry_run:
                cur.execute("""INSERT INTO graph_meta.sameas_run(graph,label,basis,matched,status,dry)
                               VALUES (%s,%s,%s,%s,%s,%s)""",
                            (args.graph, label, f"exact:{idp}", cnt, status, False))
        if args.fuzzy and not args.dry_run:
            print("  [fuzzy] 스텁 실행(사람/조직, pending) — 실구현 시 유사도·임계 교체")
            for label, idp in FUZZY_TYPES:
                run(cur, fuzzy_stub_cypher(label, idp))
        if not args.dry_run:
            conn.commit()
        print(f"\n{'[dry-run] 후보' if args.dry_run else '생성/확인'} 합계: {total}건 "
              f"({'MERGE 안 함' if args.dry_run else 'sameAs MERGE 완료'})")
        if not args.dry_run:
            print("  검토: graph_meta.sameas_run · sameAs.review_status='pending' 항목을 수사관이 confirm/reject")
    except Exception as e:
        conn.rollback(); print(f"❌ 실패(롤백): {e}"); sys.exit(1)
    finally:
        cur.close(); conn.close()

# [SEP] OSINT가 별도 그래프면: 각 그래프에서 (label,idprop,node_key)를 graph_meta.identity_block 로 추출→
#       SQL JOIN(동일 idprop, 도메인 상이)으로 후보 산출→ 각 그래프에 sameAs 대신 관계형 bridge 테이블 기록.


if __name__ == "__main__":
    main()
