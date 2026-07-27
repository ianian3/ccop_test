#!/usr/bin/env python3
"""
수사 증거 CSV → 기존 그래프에 추가(append). 계좌/인물/통화.
- MERGE 로 중복 방지 + 기존 노드에 자동 연결 (정규화 식별자 기준)
- 관계 자동: 인물→계좌(has_account), 인물→전화(owns_phone), 통화(caller/callee)
- 증거 출처 태깅: source_domain='investigation', source_id, evidence_added_at
- 기본 dry-run(미리보기). 실제 반영은 --commit

사용법:
  python scripts/add_evidence_csv.py --dir ~/Downloads/evidence_csv_templates --graph tccop_v40_demo            # dry-run
  python scripts/add_evidence_csv.py --dir <csv폴더> --graph tccop_v40_demo --commit                            # 실제 반영
  python scripts/add_evidence_csv.py --accounts a.csv --persons p.csv --calls c.csv --graph <g> --commit
CSV 컬럼:
  accounts: account_no,bnk_cd,holder_nm,is_burner,owner_psn_id,source_id,memo
  persons : psn_id,name,role_cd,is_anonymous,phone_telno,account_no,source_id,memo
  calls   : call_id,caller_telno,callee_telno,occurred_at,duration,source_id,memo
"""
import argparse
import csv
import os
import re
import sys
from datetime import datetime, timezone

TELNO = re.compile(r"[^0-9]")


def norm_telno(v):   # no_hyphen_e164 정규화 (기존 그래프 형식과 일치)
    return TELNO.sub("", v or "")


def cy(v):
    if v is None or v == "":
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if str(v).lower() in ("true", "false"):
        return str(v).lower()
    # 주의: 전화번호·계좌번호 등 식별자는 순수 숫자여도 '문자열'로 저장해야 함
    #       (무따옴표 정수로 넣으면 선행 0 소실 → 01012345678 → 1012345678, 매칭 실패)
    s = str(v).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{s}'"


def read_csv(path):
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8-sig") as f:
        return [ {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                 for row in csv.DictReader(f) ]


def connect():
    import psycopg2
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
    conn = psycopg2.connect(dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
                            password=os.getenv("DB_PASSWORD"), host=os.getenv("DB_HOST"),
                            port=os.getenv("DB_PORT"))
    return conn


def build_statements(accounts, persons, calls, ts):
    """(설명, Cypher) 리스트. 순서: 노드 먼저 MERGE → 관계 MERGE."""
    stmts = []
    meta = f"n.source_domain='investigation', n.evidence_added_at={cy(ts)}"

    # 계좌
    for r in accounts:
        acc = r.get("account_no")
        if not acc:
            continue
        sets = [f"n.bnk_cd={cy(r.get('bnk_cd'))}", f"n.holder_nm={cy(r.get('holder_nm'))}",
                f"n.is_burner={cy(r.get('is_burner') or 'false')}", f"n.id_format='plain_dash'",
                f"n.source_id={cy(r.get('source_id'))}", meta]
        stmts.append((f"계좌 {acc}",
                      f"MERGE (n:vt_bacnt {{account_no:{cy(acc)}}}) SET " + ", ".join(sets)))

    # 인물
    for r in persons:
        pid = r.get("psn_id")
        if not pid:
            continue
        sets = [f"n.name={cy(r.get('name'))}", f"n.role_cd={cy(r.get('role_cd') or 'suspect')}",
                f"n.is_anonymous={cy(r.get('is_anonymous') or 'false')}", f"n.id_format='plain'",
                f"n.source_id={cy(r.get('source_id'))}", meta]
        stmts.append((f"인물 {pid}({r.get('name')})",
                      f"MERGE (n:vt_psn {{psn_id:{cy(pid)}}}) SET " + ", ".join(sets)))

    # 전화(인물 phone_telno / 통화 양끝) — 노드 보장용 MERGE
    telnos = set()
    for r in persons:
        if r.get("phone_telno"): telnos.add(norm_telno(r["phone_telno"]))
    for r in calls:
        for k in ("caller_telno", "callee_telno"):
            if r.get(k): telnos.add(norm_telno(r[k]))
    for t in sorted(telnos):
        stmts.append((f"전화 {t}",
                      f"MERGE (n:vt_telno {{telno:{cy(t)}}}) SET n.id_format='no_hyphen_e164', {meta}"))

    # 관계: 인물→계좌(has_account), 인물→전화(owns_phone)
    for r in persons:
        pid = r.get("psn_id")
        if pid and r.get("account_no"):
            stmts.append((f"관계 {pid}-[:has_account]->{r['account_no']}",
                          f"MATCH (p:vt_psn {{psn_id:{cy(pid)}}}),(b:vt_bacnt {{account_no:{cy(r['account_no'])}}}) "
                          f"MERGE (p)-[:has_account]->(b)"))
        if pid and r.get("phone_telno"):
            t = norm_telno(r["phone_telno"])
            stmts.append((f"관계 {pid}-[:owns_phone]->{t}",
                          f"MATCH (p:vt_psn {{psn_id:{cy(pid)}}}),(t:vt_telno {{telno:{cy(t)}}}) "
                          f"MERGE (p)-[:owns_phone]->(t)"))
    # accounts.owner_psn_id 로도 연결
    for r in accounts:
        if r.get("owner_psn_id") and r.get("account_no"):
            stmts.append((f"관계 {r['owner_psn_id']}-[:has_account]->{r['account_no']}",
                          f"MATCH (p:vt_psn {{psn_id:{cy(r['owner_psn_id'])}}}),(b:vt_bacnt {{account_no:{cy(r['account_no'])}}}) "
                          f"MERGE (p)-[:has_account]->(b)"))

    # 통화 노드 + caller/callee
    for r in calls:
        cid = r.get("call_id")
        if not cid:
            continue
        sets = [f"n.duration={cy(r.get('duration'))}", f"n.occurred_at={cy(r.get('occurred_at'))}",
                f"n.id_format='plain'", f"n.source_id={cy(r.get('source_id'))}", meta]
        stmts.append((f"통화 {cid}",
                      f"MERGE (n:vt_call {{call_id:{cy(cid)}}}) SET " + ", ".join(sets)))
        if r.get("caller_telno"):
            t = norm_telno(r["caller_telno"])
            stmts.append((f"관계 {t}-[:caller]->{cid}",
                          f"MATCH (t:vt_telno {{telno:{cy(t)}}}),(c:vt_call {{call_id:{cy(cid)}}}) "
                          f"MERGE (t)-[:caller]->(c)"))
        if r.get("callee_telno"):
            t = norm_telno(r["callee_telno"])
            stmts.append((f"관계 {cid}-[:callee]->{t}",
                          f"MATCH (c:vt_call {{call_id:{cy(cid)}}}),(t:vt_telno {{telno:{cy(t)}}}) "
                          f"MERGE (c)-[:callee]->(t)"))
    return stmts


def main():
    ap = argparse.ArgumentParser(description="증거 CSV → 그래프 추가 (계좌/인물/통화)")
    ap.add_argument("--graph", required=True)
    ap.add_argument("--dir", help="accounts.csv/persons.csv/calls.csv 가 있는 폴더")
    ap.add_argument("--accounts"); ap.add_argument("--persons"); ap.add_argument("--calls")
    ap.add_argument("--commit", action="store_true", help="실제 반영(미지정 시 dry-run)")
    args = ap.parse_args()
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", args.graph):
        sys.exit("유효하지 않은 그래프 이름")

    d = args.dir
    acc = read_csv(args.accounts or (os.path.join(d, "accounts.csv") if d else None))
    per = read_csv(args.persons or (os.path.join(d, "persons.csv") if d else None))
    cal = read_csv(args.calls or (os.path.join(d, "calls.csv") if d else None))
    print(f"입력: 계좌 {len(acc)} · 인물 {len(per)} · 통화 {len(cal)}")
    if not (acc or per or cal):
        sys.exit("입력 CSV 없음 (--dir 또는 --accounts/--persons/--calls)")

    # 타임스탬프는 인자로 주입(스크립트 내 Date 호출 회피)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stmts = build_statements(acc, per, cal, ts)
    print(f"생성할 문장 {len(stmts)}개 (노드 MERGE + 관계 MERGE)\n")

    if not args.commit:
        for desc, q in stmts:
            print(f"  [dry] {desc}")
        print(f"\n[dry-run] {len(stmts)}개 미리보기 완료. 실제 반영: --commit 추가")
        print("        (권장: 반영 전 그래프 스냅샷 백업)")
        return

    conn = connect(); cur = conn.cursor()
    conn.autocommit = False
    try:
        cur.execute(f"SET graph_path = {args.graph}")
        for l in ("vt_bacnt", "vt_psn", "vt_telno", "vt_call"):
            cur.execute(f"CREATE VLABEL IF NOT EXISTS {l}")
        for l in ("has_account", "owns_phone", "caller", "callee"):
            cur.execute(f"CREATE ELABEL IF NOT EXISTS {l}")
        ok = 0
        for desc, q in stmts:
            cur.execute(q); ok += 1
        conn.commit()
        print(f"✅ 반영 완료: {ok}개 문장 → graph '{args.graph}' (source_id 로 추적 가능)")
    except Exception as e:
        conn.rollback()
        print(f"❌ 실패(전체 롤백): {e}"); sys.exit(1)
    finally:
        cur.close(); conn.close()


if __name__ == "__main__":
    main()
