#!/usr/bin/env python3
"""테스트 그래프(ccop_test_graph) 시드 — 데모·기능시험용 가상 데이터.

목적: 운영 그래프(ccop_ep_integrated 등)는 읽기 전용으로 잠겨 있어 적재·수정 기능을
      시연하거나 시험할 수 없다. 이 그래프만 앱 계정에 쓰기 권한을 주고, 실존하지 않는
      가상 데이터를 넣어 안전하게 실험할 수 있게 한다.

데이터 원칙 (실제 정보 혼입 방지):
  · IP        — RFC 5737 문서화 전용 대역(192.0.2.0/24). 인터넷에 실존하지 않는다.
  · 전화번호  — 010-0000-XXXX (미할당 번호대)
  · 계좌번호  — TEST- 접두 (실계좌 형식과 구분)
  · 인물/조직 — 가상 인물. 모든 노드에 source_id='TEST-SEED' 표시
  · 실제 사건·피의자와 무관한 창작 시나리오

시나리오(중고거래 사기 축약형):
  피해자 5 → 1차 수취계좌 3 → 2차 집금 1 → 3차 해외송금 1
  피의자 4(주범 1·공범 3) · 콜센터 IP 1 · 메신저 계정 4 · 출국 2건

멱등(MERGE) — 반복 실행해도 중복되지 않는다.
실행: python3 scripts/seed_test_graph.py
"""
import os
import re
import sys

import psycopg2

GRAPH = "ccop_test_graph"
SRC = "TEST-SEED"


def esc(v):
    return str(v).replace("\\", "\\\\").replace("'", "''")


def props(d):
    """속성 딕셔너리 → Cypher 맵 리터럴. source_id·is_test 를 항상 붙인다."""
    d = dict(d, source_id=SRC, is_test="true")
    return "{" + ", ".join(f"{k}: '{esc(v)}'" for k, v in d.items()) + "}"


# ── 노드 정의 ────────────────────────────────────────────────────────────────
PERSONS = [
    # 피의자
    ("강도현", {"role": "주범(특정 1순위)", "evid_grade": "A", "addr_base": "서울시"}),
    ("윤재호", {"role": "공범", "evid_grade": "A", "addr_base": "경기도"}),
    ("배소민", {"role": "공범", "evid_grade": "B", "addr_base": "인천시"}),
    ("한지우", {"role": "3차집금 명의", "evid_grade": "B", "addr_base": "부산시"}),
    # 피해자
    ("피해자1", {"role": "피해자"}), ("피해자2", {"role": "피해자"}),
    ("피해자3", {"role": "피해자"}), ("피해자4", {"role": "피해자"}),
    ("피해자5", {"role": "피해자"}),
    # 계좌 명의자(대포통장)
    ("서민아", {"role": "명의대여"}), ("노경태", {"role": "명의대여"}),
]

ACCOUNTS = [
    ("TEST-1001-001", {"bank_nm": "농협", "dpstr": "서민아", "tier": "1차 사기수취"}),
    ("TEST-1001-002", {"bank_nm": "국민", "dpstr": "노경태", "tier": "1차 사기수취"}),
    ("TEST-1001-003", {"bank_nm": "신한", "dpstr": "서민아", "tier": "1차 사기수취"}),
    ("TEST-2002-001", {"bank_nm": "기업", "dpstr": "한지우", "tier": "3차집금"}),
    ("TEST-3003-001", {"bank_nm": "우리", "dpstr": "강도현", "tier": "4차 해외송금 수취"}),
]

PHONES = ["01000000101", "01000000102", "01000000103", "07000000201"]
IPS = [("192.0.2.10", {"country": "중국"}), ("192.0.2.11", {}), ("192.0.2.12", {})]
IDS = [("test_kakao_01", {"platform": "kakao"}), ("test_kakao_02", {"platform": "kakao"}),
       ("test_naver_01", {"platform": "naver"}), ("test_naver_02", {"platform": "naver"})]
CASES = [(f"TEST-2017-{i:03d}", {"case_type": "사기(테스트 시나리오)",
                                 "crime_site": "테스트 중고장터",
                                 "occrn_dt": f"2017-03-{10 + i:02d}"}) for i in range(1, 6)]
ORGS = [("테스트상사", {})]
MOVEMENTS = [("TEST-MOV-강도현-20170401", {"mov_type": "출국", "mov_dt": "2017-04-01", "dest": "중국"}),
             ("TEST-MOV-윤재호-20170403", {"mov_type": "출국", "mov_dt": "2017-04-03", "dest": "중국"})]

# ── 엣지 정의 (from_label, from_key, edge, to_label, to_key, props) ──────────
EDGES = [
    # 피해자 → 사건
    *[("vt_psn", f"피해자{i}", "victim_in", "vt_case", f"TEST-2017-{i:03d}", {}) for i in range(1, 6)],
    # 사건 → 사용된 계좌
    ("vt_case", "TEST-2017-001", "eg_used_account", "vt_bacnt", "TEST-1001-001", {}),
    ("vt_case", "TEST-2017-002", "eg_used_account", "vt_bacnt", "TEST-1001-001", {}),
    ("vt_case", "TEST-2017-003", "eg_used_account", "vt_bacnt", "TEST-1001-002", {}),
    ("vt_case", "TEST-2017-004", "eg_used_account", "vt_bacnt", "TEST-1001-003", {}),
    ("vt_case", "TEST-2017-005", "eg_used_account", "vt_bacnt", "TEST-1001-001", {}),
    # 명의자 → 계좌
    ("vt_psn", "서민아", "has_account", "vt_bacnt", "TEST-1001-001", {}),
    ("vt_psn", "서민아", "has_account", "vt_bacnt", "TEST-1001-003", {}),
    ("vt_psn", "노경태", "has_account", "vt_bacnt", "TEST-1001-002", {}),
    ("vt_psn", "한지우", "has_account", "vt_bacnt", "TEST-2002-001", {}),
    ("vt_psn", "강도현", "has_account", "vt_bacnt", "TEST-3003-001", {}),
    # 자금 흐름: 1차 → 집금 → 해외송금
    ("vt_bacnt", "TEST-1001-001", "transferred_to", "vt_bacnt", "TEST-2002-001",
     {"first_dlng_dt": "2017-03-12", "last_dlng_dt": "2017-03-18", "total_amount": "4200000"}),
    ("vt_bacnt", "TEST-1001-002", "transferred_to", "vt_bacnt", "TEST-2002-001",
     {"first_dlng_dt": "2017-03-14", "last_dlng_dt": "2017-03-19", "total_amount": "2800000"}),
    ("vt_bacnt", "TEST-1001-003", "transferred_to", "vt_bacnt", "TEST-2002-001",
     {"first_dlng_dt": "2017-03-15", "last_dlng_dt": "2017-03-20", "total_amount": "1500000"}),
    ("vt_bacnt", "TEST-2002-001", "transferred_to", "vt_bacnt", "TEST-3003-001",
     {"first_dlng_dt": "2017-03-21", "last_dlng_dt": "2017-03-25", "total_amount": "8300000"}),
    # 조직
    ("vt_bacnt", "TEST-3003-001", "belongs_to", "vt_org", "테스트상사", {}),
    # 통신: 회선 명의 + 통화
    ("vt_telno", "01000000101", "registered_to", "vt_psn", "강도현", {}),
    ("vt_telno", "01000000102", "registered_to", "vt_psn", "윤재호", {}),
    ("vt_telno", "01000000103", "registered_to", "vt_psn", "배소민", {}),
    ("vt_psn", "강도현", "owns_phone", "vt_telno", "01000000101", {}),
    ("vt_telno", "07000000201", "contacted", "vt_telno", "01000000101",
     {"first_dt": "2017-03-11", "last_dt": "2017-03-22"}),
    ("vt_telno", "01000000101", "contacted", "vt_telno", "01000000102",
     {"first_dt": "2017-03-12", "last_dt": "2017-03-24"}),
    ("vt_telno", "01000000102", "contacted", "vt_telno", "01000000103",
     {"first_dt": "2017-03-13", "last_dt": "2017-03-23"}),
    # 계정 → 인물(명의) + 접속 IP  ← EP7형 '위장 뒤 실사용자' 2-hop 구조 재현
    ("vt_id", "test_kakao_01", "registered_to", "vt_psn", "강도현", {}),
    ("vt_id", "test_kakao_02", "registered_to", "vt_psn", "윤재호", {}),
    ("vt_id", "test_naver_01", "registered_to", "vt_psn", "배소민", {}),
    ("vt_id", "test_naver_02", "registered_to", "vt_psn", "한지우", {}),
    ("vt_id", "test_kakao_01", "used_ip", "vt_ip", "192.0.2.10", {}),
    ("vt_id", "test_kakao_02", "used_ip", "vt_ip", "192.0.2.10", {}),
    ("vt_id", "test_naver_01", "used_ip", "vt_ip", "192.0.2.10", {}),
    ("vt_id", "test_naver_02", "used_ip", "vt_ip", "192.0.2.11", {}),
    ("vt_telno", "07000000201", "used_ip", "vt_ip", "192.0.2.10", {}),
    ("vt_bacnt", "TEST-2002-001", "used_ip", "vt_ip", "192.0.2.12", {}),
    # 피의자 → 사건
    *[("vt_psn", p, "suspect_in", "vt_case", "TEST-2017-001", {})
      for p in ("강도현", "윤재호", "배소민", "한지우")],
    # 출입국
    ("vt_movement", "TEST-MOV-강도현-20170401", "performed_by", "vt_psn", "강도현", {}),
    ("vt_movement", "TEST-MOV-윤재호-20170403", "performed_by", "vt_psn", "윤재호", {}),
    # 동일인(이명)
    ("vt_psn", "강도현", "same_as", "vt_psn", "한지우", {}),
]

KEY = {"vt_psn": "name", "vt_bacnt": "account_no", "vt_telno": "telno", "vt_ip": "ip_addr",
       "vt_id": "id_val", "vt_case": "flnm", "vt_org": "org_name", "vt_movement": "mov_id"}


def main():
    from dotenv import load_dotenv
    load_dotenv()
    # 쓰기가 필요하므로 계정을 인자/환경변수로 받는다(앱 계정은 이 그래프에만 쓰기 가능).
    user = os.getenv("SEED_DB_USER") or os.getenv("DB_USER")
    pw = os.getenv("SEED_DB_PASSWORD") or os.getenv("DB_PASSWORD")
    conn = psycopg2.connect(host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
                            dbname=os.getenv("DB_NAME"), user=user, password=pw,
                            connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(f"SET graph_path = {GRAPH}")

    # 라벨(스키마) 생성은 그래프 소유자 권한이 필요하다. 앱 계정은 데이터만 조작하도록
    # 분리했으므로, 라벨이 없을 때만 관리 계정으로 미리 만들어 두면 된다(최소 권한).
    for vl in KEY:
        try:
            cur.execute(f"CREATE VLABEL IF NOT EXISTS {vl}")
        except psycopg2.errors.InsufficientPrivilege:
            conn.rollback()
            break   # 소유자가 아니면 이미 준비된 라벨을 쓴다
    else:
        for el in sorted({e[2] for e in EDGES}):
            try:
                cur.execute(f"CREATE ELABEL IF NOT EXISTS {el}")
            except psycopg2.errors.InsufficientPrivilege:
                conn.rollback()
                break

    n = 0
    for name, extra in PERSONS:
        cur.execute(f"MERGE (p:vt_psn {{name: '{esc(name)}'}}) SET p += {props(extra)}"); n += 1
    for acc, extra in ACCOUNTS:
        cur.execute(f"MERGE (b:vt_bacnt {{account_no: '{esc(acc)}'}}) SET b += {props(extra)}"); n += 1
    for tel in PHONES:
        cur.execute(f"MERGE (t:vt_telno {{telno: '{esc(tel)}'}}) SET t += {props({})}"); n += 1
    for ip, extra in IPS:
        cur.execute(f"MERGE (i:vt_ip {{ip_addr: '{esc(ip)}'}}) SET i += {props(extra)}"); n += 1
    for idv, extra in IDS:
        cur.execute(f"MERGE (d:vt_id {{id_val: '{esc(idv)}'}}) SET d += {props(extra)}"); n += 1
    for flnm, extra in CASES:
        cur.execute(f"MERGE (c:vt_case {{flnm: '{esc(flnm)}'}}) SET c += {props(extra)}"); n += 1
    for org, extra in ORGS:
        cur.execute(f"MERGE (o:vt_org {{org_name: '{esc(org)}'}}) SET o += {props(extra)}"); n += 1
    for mov, extra in MOVEMENTS:
        cur.execute(f"MERGE (m:vt_movement {{mov_id: '{esc(mov)}'}}) SET m += {props(extra)}"); n += 1
    print(f"[노드] {n}건 MERGE", flush=True)

    e = 0
    for fl, fk, el, tl, tk, ep in EDGES:
        setp = ""
        if ep:
            setp = " SET " + ", ".join(f"r.{k} = '{esc(v)}'" for k, v in ep.items())
        cur.execute(f"MATCH (a:{fl} {{{KEY[fl]}: '{esc(fk)}'}}), (b:{tl} {{{KEY[tl]}: '{esc(tk)}'}}) "
                    f"MERGE (a)-[r:{el}]->(b)" + setp)
        e += 1
    print(f"[엣지] {e}건 MERGE", flush=True)

    cur.execute("MATCH (x) RETURN count(x)")
    print(f"[결과] 노드 {cur.fetchone()[0]}", flush=True)
    cur.execute("MATCH ()-[r]->() RETURN count(r)")
    print(f"[결과] 엣지 {cur.fetchone()[0]}", flush=True)
    conn.close()


if __name__ == "__main__":
    main()
