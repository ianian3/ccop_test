"""
t2c_v2 Step 1: 템플릿 기반 샘플 생성

입력:  data/t2c_v1_patched.json (2,320개)
출력:  data/t2c_v2_templates.json (~4,500개)

카테고리별 목표 (QUERY 기준):
  기존 엣지 보강 1-hop  ~2,130개
  신규 엣지 15종 1-hop  ~1,370개
  체인/멀티홉           ~1,000개 (Step 3에서 추가 1,000)
  합계                  ~4,500개
"""

import json
import random
import re
from pathlib import Path
from itertools import product

SEED = 42
random.seed(SEED)

DST_PATH = Path("data/t2c_v2_templates.json")

GRAPH_NAME = "tccop_graph"

SYSTEM_PROMPT = (
    "당신은 AgensGraph(Apache AGE 기반) Cypher 쿼리 전문가입니다.\n"
    "사용자의 자연어 질문을 받아 정확한 AgensGraph Cypher 쿼리로 변환하세요.\n\n"
    "[필수 출력 규칙]\n"
    f"1. 반드시 SELECT * FROM cypher('{GRAPH_NAME}', $$ ... $$) AS (...) 형식으로 출력\n"
    "2. RETURN 변수 수와 AS 컬럼 수가 반드시 일치해야 함 (모두 agtype)\n"
    "3. 속성 접근: n->>'속성명' (문자열), toInteger(n->>'속성명') (숫자)\n"
    "4. 쓰기 명령(CREATE/MERGE/DELETE/SET) 금지 — 조회 전용\n"
    f"5. 그래프 이름은 항상 '{GRAPH_NAME}' 사용\n"
    "6. 수사와 무관한 질문은 \"수사 관련 질문만 답변 가능합니다.\" 출력\n\n"
    "[응답 형식]\n"
    "질문을 분석한 후 쿼리만 출력하세요. 설명 없이 SQL 구문만 반환합니다.\n"
)


# ─── 샘플 데이터 ─────────────────────────────────────────────────────────────

NAMES = [
    "김민준", "이서연", "박지호", "최수아", "정우진", "강하은", "윤도현", "임서현",
    "한준혁", "오채원", "서동현", "신유나", "권태양", "황지민", "안민서", "류승현",
    "남기태", "장수빈", "홍준서", "백아린", "고태양", "문지원", "성현우", "배나연",
]
CASE_IDS = [f"2024-사이버-{n:03d}" for n in range(1, 41)] + \
           [f"2023-보이스피싱-{n:03d}" for n in range(1, 21)]
ACCOUNT_NOS = [f"1002-{a:03d}-{b:06d}" for a, b in
               [(i, j) for i in range(110, 125) for j in range(100001, 100008)]]
PHONE_NOS = [f"010-{a:04d}-{b:04d}" for a, b in
             [(a, b) for a in range(1234, 1245) for b in range(5678, 5688)]]
IP_ADDRS = [f"192.168.{a}.{b}" for a, b in
            [(a, b) for a in range(1, 8) for b in range(10, 20)]] + \
           [f"10.{a}.{b}.1" for a in range(0, 5) for b in range(0, 5)]
URLS = [f"https://fake-bank-{i:02d}.kr" for i in range(1, 16)] + \
       [f"http://phishing-site-{i:02d}.com" for i in range(1, 11)]
VHCL_NOS = [f"{n}가{m:04d}" for n in ["12", "34", "56", "78"] for m in range(1111, 1118)]
ORG_NAMES = ["KB국민은행", "신한은행", "우리은행", "하나은행", "농협은행", "카카오뱅크",
             "보이스피싱조직A", "대출사기단B", "사기조직C", "범죄단체D"]
ATM_IDS = [f"ATM-{n:04d}" for n in range(1001, 1016)]
LOC_NAMES = ["서울 강남구", "서울 마포구", "부산 해운대구", "인천 남동구", "대구 달서구",
             "서울 종로구", "수원 팔달구", "경기 성남시", "부산 사상구"]
FILE_HASHES = [f"abc{i:04x}def{i*3:04x}" for i in range(1, 16)]
MSG_IDS = [f"MSG-{n:05d}" for n in range(10001, 10030)]
PSN_IDS = [f"PSN-{n:04d}" for n in range(1001, 1025)]
DEV_IDS = [f"DEV-{n:04d}" for n in range(2001, 2012)]
TRANS_IDS = [f"TXN-{n:06d}" for n in range(100001, 100020)]
CALL_IDS = [f"CALL-{n:05d}" for n in range(50001, 50020)]


def pick(*lst): return random.choice(lst[0] if len(lst) == 1 else lst)


def cypher_wrap(body: str, returns: list[str]) -> str:
    cols = ", ".join(f"{r} agtype" for r in returns)
    ret_vars = ", ".join(returns)
    if "RETURN" not in body:
        body = body.rstrip() + f"\nRETURN {ret_vars}"
    return f"SELECT * FROM cypher('{GRAPH_NAME}', $$\n  {body}\n$$) AS ({cols});"


def make_sample(schema: str, question: str, cypher_body: str,
                returns: list[str], intent: str = "QUERY") -> dict:
    human_val = f"[스키마]\n{schema}\n\n[질문]\n{question}"
    gpt_val = cypher_wrap(cypher_body, returns)
    return {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": human_val},
            {"from": "gpt", "value": gpt_val},
        ],
        "intent": intent,
    }


# ─── 스키마 스니펫 빌더 ───────────────────────────────────────────────────────

def schema_1hop(nodes: list[tuple[str, str]], edge: str,
                edge_props: str = "", src_node: str = None, dst_node: str = None) -> str:
    """nodes: [(label, '{prop1, prop2}'), ...]"""
    node_lines = "\n".join(f"  ({label} {{{props}}})" for label, props in nodes)
    direction = f"  ({src_node})-[:{edge}{' {' + edge_props + '}' if edge_props else ''}]->({dst_node})"
    return (
        f"노드:\n{node_lines}\n"
        f"관계:\n{direction}\n"
        f"속성 접근:\n"
        f"  WHERE n->>'속성명' = '값'  (문자열)\n"
        f"  WHERE toInteger(n->>'속성명') >= 숫자  (숫자)"
    )


def schema_chain(nodes: list[tuple[str, str]], edges: list[tuple[str, str, str]]) -> str:
    """edges: [(src_label, edge_name, dst_label), ...]"""
    node_lines = "\n".join(f"  ({label} {{{props}}})" for label, props in nodes)
    edge_lines = "\n".join(f"  ({s})-[:{e}]->({d})" for s, e, d in edges)
    return (
        f"노드:\n{node_lines}\n"
        f"관계:\n{edge_lines}\n"
        f"속성 접근:\n"
        f"  WHERE n->>'속성명' = '값'  (문자열)\n"
        f"  WHERE toInteger(n->>'속성명') >= 숫자  (숫자)"
    )


# ─── 생성기 함수들 ────────────────────────────────────────────────────────────

def gen_has_account(n: int) -> list[dict]:
    samples = []
    schema = schema_1hop(
        [("vt_psn", "psn_id, name, risk_level"), ("vt_bacnt", "account_no, bank_nm, is_burner, is_frozen")],
        "has_account", src_node="vt_psn", dst_node="vt_bacnt"
    )
    templates = [
        ("{name}의 소유 계좌를 조회해줘",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:has_account]->(b:vt_bacnt) RETURN p, r, b",
         ["p", "r", "b"]),
        ("{name} 명의 계좌 전체 목록",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:has_account]->(b:vt_bacnt) RETURN p, r, b",
         ["p", "r", "b"]),
        ("계좌 {acct}를 보유한 인물",
         "MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt {{account_no:'{acct}'}}) RETURN p, r, b",
         ["p", "r", "b"]),
        ("{name}의 대포통장 여부 확인",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:has_account]->(b:vt_bacnt) WHERE b->>'is_burner' = 'true' RETURN p, r, b",
         ["p", "r", "b"]),
        ("동결된 계좌를 소유한 피의자",
         "MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt) WHERE b->>'is_frozen' = 'true' RETURN p, r, b",
         ["p", "r", "b"]),
        ("위험도가 높은 인물의 계좌",
         "MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt) WHERE p->>'risk_level' = 'HIGH' RETURN p, r, b",
         ["p", "r", "b"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        acct = pick(ACCOUNT_NOS)
        q = tpl.format(name=name, acct=acct)
        c = cypher.format(name=name, acct=acct)
        samples.append(make_sample(schema, q, c, rets))
    return samples


def gen_owns_phone(n: int) -> list[dict]:
    samples = []
    schema = schema_1hop(
        [("vt_psn", "psn_id, name, dob"), ("vt_telno", "telno, is_burner, carrier")],
        "owns_phone", src_node="vt_psn", dst_node="vt_telno"
    )
    templates = [
        ("{name}이 소유한 전화번호",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:owns_phone]->(t:vt_telno) RETURN p, r, t",
         ["p", "r", "t"]),
        ("전화번호 {telno}의 소유자",
         "MATCH (p:vt_psn)-[r:owns_phone]->(t:vt_telno {{telno:'{telno}'}}) RETURN p, r, t",
         ["p", "r", "t"]),
        ("{name} 명의 대포폰",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:owns_phone]->(t:vt_telno) WHERE t->>'is_burner' = 'true' RETURN p, r, t",
         ["p", "r", "t"]),
        ("대포폰을 가진 피의자 전체",
         "MATCH (p:vt_psn)-[r:owns_phone]->(t:vt_telno) WHERE t->>'is_burner' = 'true' RETURN p, r, t",
         ["p", "r", "t"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        telno = pick(PHONE_NOS)
        q = tpl.format(name=name, telno=telno)
        c = cypher.format(name=name, telno=telno)
        samples.append(make_sample(schema, q, c, rets))
    return samples


def gen_suspect_victim_witness(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_psn", "psn_id, name, risk_level"), ("vt_case", "flnm, incdnt_typ_cd, damage_amount, status")],
        [("vt_psn", "suspect_in|victim_in|witness_in", "vt_case")]
    )
    templates = [
        ("사건 {flnm}의 피의자 목록",
         "MATCH (p:vt_psn)-[r:suspect_in]->(c:vt_case {{flnm:'{flnm}'}}) RETURN p, r, c",
         ["p", "r", "c"]),
        ("{name}이 피의자로 등록된 사건",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:suspect_in]->(c:vt_case) RETURN p, r, c",
         ["p", "r", "c"]),
        ("사건 {flnm}의 피해자",
         "MATCH (p:vt_psn)-[r:victim_in]->(c:vt_case {{flnm:'{flnm}'}}) RETURN p, r, c",
         ["p", "r", "c"]),
        ("{name}이 피해를 입은 사건 전체",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:victim_in]->(c:vt_case) RETURN p, r, c",
         ["p", "r", "c"]),
        ("사건 {flnm} 참고인(증인) 목록",
         "MATCH (p:vt_psn)-[r:witness_in]->(c:vt_case {{flnm:'{flnm}'}}) RETURN p, r, c",
         ["p", "r", "c"]),
        ("위험도 HIGH 피의자가 관련된 사건",
         "MATCH (p:vt_psn)-[r:suspect_in]->(c:vt_case) WHERE p->>'risk_level' = 'HIGH' RETURN p, r, c",
         ["p", "r", "c"]),
        ("피해금액이 1000만원 이상인 사건의 피의자",
         "MATCH (p:vt_psn)-[r:suspect_in]->(c:vt_case) WHERE toInteger(c->>'damage_amount') >= 10000000 RETURN p, r, c",
         ["p", "r", "c"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        flnm = pick(CASE_IDS)
        q = tpl.format(name=name, flnm=flnm)
        c = cypher.format(name=name, flnm=flnm)
        samples.append(make_sample(schema, q, c, rets))
    return samples


def gen_caller_callee(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_telno", "telno, is_burner"), ("vt_call", "call_id, call_dt, duration_sec, call_type")],
        [("vt_telno", "caller", "vt_call"), ("vt_telno", "callee", "vt_call")]
    )
    templates = [
        ("전화번호 {telno}의 발신 통화 내역",
         "MATCH (t:vt_telno {{telno:'{telno}'}})-[r:caller]->(c:vt_call) RETURN t, r, c",
         ["t", "r", "c"]),
        ("전화번호 {telno}의 수신 통화 내역",
         "MATCH (t:vt_telno {{telno:'{telno}'}})-[r:callee]->(c:vt_call) RETURN t, r, c",
         ["t", "r", "c"]),
        ("대포폰의 발신 통화 목록",
         "MATCH (t:vt_telno)-[r:caller]->(c:vt_call) WHERE t->>'is_burner' = 'true' RETURN t, r, c",
         ["t", "r", "c"]),
        ("3분 이상 통화한 발신 기록",
         "MATCH (t:vt_telno)-[r:caller]->(c:vt_call) WHERE toInteger(c->>'duration_sec') >= 180 RETURN t, r, c",
         ["t", "r", "c"]),
        ("{telno}의 발신 횟수",
         "MATCH (t:vt_telno {{telno:'{telno}'}})-[r:caller]->(c:vt_call) RETURN t, count(c) AS call_cnt",
         ["t", "call_cnt"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        telno = pick(PHONE_NOS)
        q = tpl.format(telno=telno)
        c = cypher.format(telno=telno)
        samples.append(make_sample(schema, q, c, rets))
    return samples


def gen_transfer_edges(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_bacnt", "account_no, bank_nm, is_frozen"),
         ("vt_transfer", "txn_id, amount, txn_dt, txn_type")],
        [("vt_bacnt", "from_account", "vt_transfer"), ("vt_transfer", "to_account", "vt_bacnt")]
    )
    templates = [
        ("계좌 {acct}에서 출금된 이체 내역",
         "MATCH (b:vt_bacnt {{account_no:'{acct}'}})-[r:from_account]->(tr:vt_transfer) RETURN b, r, tr",
         ["b", "r", "tr"]),
        ("계좌 {acct}로 입금된 이체 내역",
         "MATCH (tr:vt_transfer)-[r:to_account]->(b:vt_bacnt {{account_no:'{acct}'}}) RETURN tr, r, b",
         ["tr", "r", "b"]),
        ("100만원 이상 이체 내역",
         "MATCH (b:vt_bacnt)-[r:from_account]->(tr:vt_transfer) WHERE toInteger(tr->>'amount') >= 1000000 RETURN b, r, tr",
         ["b", "r", "tr"]),
        ("동결 계좌의 이체 내역",
         "MATCH (b:vt_bacnt)-[r:from_account]->(tr:vt_transfer) WHERE b->>'is_frozen' = 'true' RETURN b, r, tr",
         ["b", "r", "tr"]),
        ("계좌 {acct}의 이체 건수",
         "MATCH (b:vt_bacnt {{account_no:'{acct}'}})-[r:from_account]->(tr:vt_transfer) RETURN b, count(tr) AS cnt",
         ["b", "cnt"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        acct = pick(ACCOUNT_NOS)
        q = tpl.format(acct=acct)
        c = cypher.format(acct=acct)
        samples.append(make_sample(schema, q, c, rets))
    return samples


def gen_transferred_to(n: int) -> list[dict]:
    samples = []
    schema = schema_1hop(
        [("vt_bacnt", "account_no, bank_nm, is_burner, is_frozen")],
        "transferred_to", src_node="vt_bacnt", dst_node="vt_bacnt"
    )
    templates = [
        ("계좌 {acct}에서 직접 이체된 계좌 목록",
         "MATCH (a:vt_bacnt {{account_no:'{acct}'}})-[r:transferred_to]->(b:vt_bacnt) RETURN a, r, b",
         ["a", "r", "b"]),
        ("대포통장으로 이체된 계좌",
         "MATCH (a:vt_bacnt)-[r:transferred_to]->(b:vt_bacnt) WHERE b->>'is_burner' = 'true' RETURN a, r, b",
         ["a", "r", "b"]),
        ("계좌 {acct}로 이체한 원천 계좌",
         "MATCH (a:vt_bacnt)-[r:transferred_to]->(b:vt_bacnt {{account_no:'{acct}'}}) RETURN a, r, b",
         ["a", "r", "b"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        acct = pick(ACCOUNT_NOS)
        q = tpl.format(acct=acct)
        c = cypher.format(acct=acct)
        samples.append(make_sample(schema, q, c, rets))
    return samples


def gen_access_edges(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_ip", "ip_addr, country, is_vpn, threat_score"),
         ("vt_access", "access_id, access_dt, access_type"),
         ("vt_site", "url_addr, is_malicious")],
        [("vt_ip", "accessed_from", "vt_access"), ("vt_access", "accessed_to", "vt_site")]
    )
    templates = [
        ("IP {ip}의 접속 내역",
         "MATCH (i:vt_ip {{ip_addr:'{ip}'}})-[r:accessed_from]->(a:vt_access) RETURN i, r, a",
         ["i", "r", "a"]),
        ("사이트 {url}에 접속한 IP 내역",
         "MATCH (a:vt_access)-[r:accessed_to]->(s:vt_site {{url_addr:'{url}'}}) RETURN a, r, s",
         ["a", "r", "s"]),
        ("악성 사이트에 접속한 IP",
         "MATCH (i:vt_ip)-[:accessed_from]->(a:vt_access)-[r:accessed_to]->(s:vt_site) WHERE s->>'is_malicious' = 'true' RETURN i, r, s",
         ["i", "r", "s"]),
        ("VPN을 통한 접속 기록",
         "MATCH (i:vt_ip)-[r:accessed_from]->(a:vt_access) WHERE i->>'is_vpn' = 'true' RETURN i, r, a",
         ["i", "r", "a"]),
        ("위협점수 80 이상 IP 접속 내역",
         "MATCH (i:vt_ip)-[r:accessed_from]->(a:vt_access) WHERE toInteger(i->>'threat_score') >= 80 RETURN i, r, a",
         ["i", "r", "a"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        ip = pick(IP_ADDRS)
        url = pick(URLS)
        q = tpl.format(ip=ip, url=url)
        c = cypher.format(ip=ip, url=url)
        samples.append(make_sample(schema, q, c, rets))
    return samples


def gen_used_ip(n: int) -> list[dict]:
    samples = []
    schema = schema_1hop(
        [("vt_psn", "psn_id, name, risk_level"), ("vt_ip", "ip_addr, country, is_vpn, threat_score")],
        "used_ip", src_node="vt_psn", dst_node="vt_ip"
    )
    templates = [
        ("{name}이 사용한 IP 목록",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:used_ip]->(i:vt_ip) RETURN p, r, i",
         ["p", "r", "i"]),
        ("IP {ip}를 사용한 인물",
         "MATCH (p:vt_psn)-[r:used_ip]->(i:vt_ip {{ip_addr:'{ip}'}}) RETURN p, r, i",
         ["p", "r", "i"]),
        ("해외 IP를 사용한 피의자",
         "MATCH (p:vt_psn)-[r:used_ip]->(i:vt_ip) WHERE i->>'country' <> 'KR' RETURN p, r, i",
         ["p", "r", "i"]),
        ("VPN IP를 사용한 인물",
         "MATCH (p:vt_psn)-[r:used_ip]->(i:vt_ip) WHERE i->>'is_vpn' = 'true' RETURN p, r, i",
         ["p", "r", "i"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        ip = pick(IP_ADDRS)
        q = tpl.format(name=name, ip=ip)
        c = cypher.format(name=name, ip=ip)
        samples.append(make_sample(schema, q, c, rets))
    return samples


def gen_member_works(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_psn", "psn_id, name, risk_level"), ("vt_org", "org_id, org_name, org_type, is_criminal")],
        [("vt_psn", "member_of", "vt_org"), ("vt_psn", "works_at", "vt_org")]
    )
    templates = [
        ("{name}이 소속된 조직",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:member_of]->(o:vt_org) RETURN p, r, o",
         ["p", "r", "o"]),
        ("범죄조직 {org}의 구성원",
         "MATCH (p:vt_psn)-[r:member_of]->(o:vt_org {{org_name:'{org}'}}) RETURN p, r, o",
         ["p", "r", "o"]),
        ("범죄 조직에 속한 피의자 전체",
         "MATCH (p:vt_psn)-[r:member_of]->(o:vt_org) WHERE o->>'is_criminal' = 'true' RETURN p, r, o",
         ["p", "r", "o"]),
        ("{name}의 재직 기관",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:works_at]->(o:vt_org) RETURN p, r, o",
         ["p", "r", "o"]),
        ("금융기관에 재직 중인 인물",
         "MATCH (p:vt_psn)-[r:works_at]->(o:vt_org) WHERE o->>'org_type' = 'FINANCIAL' RETURN p, r, o",
         ["p", "r", "o"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        org = pick(ORG_NAMES)
        q = tpl.format(name=name, org=org)
        c = cypher.format(name=name, org=org)
        samples.append(make_sample(schema, q, c, rets))
    return samples


def gen_accomplice_sameAs(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_psn", "psn_id, name, risk_level")],
        [("vt_psn", "accomplice_of", "vt_psn"), ("vt_psn", "sameAs", "vt_psn")]
    )
    templates = [
        ("{name}의 공범 목록",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:accomplice_of]-(q:vt_psn) RETURN p, r, q",
         ["p", "r", "q"]),
        ("공범 신뢰도 0.8 이상인 관계",
         "MATCH (p:vt_psn)-[r:accomplice_of]-(q:vt_psn) WHERE toFloat(r->>'confidence') >= 0.8 RETURN p, r, q",
         ["p", "r", "q"]),
        ("{name}과 동일인물로 추정되는 별명",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:sameAs]-(q:vt_psn) RETURN p, r, q",
         ["p", "r", "q"]),
        ("동일인물 추정 쌍 전체 목록",
         "MATCH (p:vt_psn)-[r:sameAs]->(q:vt_psn) RETURN p, r, q",
         ["p", "r", "q"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        q_str = tpl.format(name=name)
        c = cypher.format(name=name)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_drives_eg_used(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_psn", "psn_id, name"), ("vt_vhcl", "vhclno, make, color"),
         ("vt_case", "flnm, crime_type_cd"), ("vt_bacnt", "account_no"),
         ("vt_telno", "telno"), ("vt_ip", "ip_addr")],
        [("vt_psn", "drives", "vt_vhcl"),
         ("vt_case", "eg_used_account", "vt_bacnt"),
         ("vt_case", "eg_used_phone", "vt_telno"),
         ("vt_case", "eg_used_ip", "vt_ip")]
    )
    templates = [
        ("{name}이 운전한 차량 (LPR 기반)",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:drives]->(v:vt_vhcl) RETURN p, r, v",
         ["p", "r", "v"]),
        ("차량 {vhcl}의 운전자",
         "MATCH (p:vt_psn)-[r:drives]->(v:vt_vhcl {{vhclno:'{vhcl}'}}) RETURN p, r, v",
         ["p", "r", "v"]),
        ("사건 {flnm}에서 사용된 계좌 (증거)",
         "MATCH (c:vt_case {{flnm:'{flnm}'}})-[r:eg_used_account]->(b:vt_bacnt) RETURN c, r, b",
         ["c", "r", "b"]),
        ("사건 {flnm}에서 사용된 전화번호 (증거)",
         "MATCH (c:vt_case {{flnm:'{flnm}'}})-[r:eg_used_phone]->(t:vt_telno) RETURN c, r, t",
         ["c", "r", "t"]),
        ("사건 {flnm}에서 사용된 IP 주소 (증거)",
         "MATCH (c:vt_case {{flnm:'{flnm}'}})-[r:eg_used_ip]->(i:vt_ip) RETURN c, r, i",
         ["c", "r", "i"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        vhcl = pick(VHCL_NOS)
        flnm = pick(CASE_IDS)
        q_str = tpl.format(name=name, vhcl=vhcl, flnm=flnm)
        c = cypher.format(name=name, vhcl=vhcl, flnm=flnm)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_filed_as_linked_to(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_petition", "petition_id, rcpt_dt, crime_type_cd, damage_amt, status"),
         ("vt_case", "flnm, incdnt_typ_cd, status, damage_amount, risk_level")],
        [("vt_petition", "filed_as", "vt_case"),
         ("vt_petition", "linked_to", "vt_case")]
    )
    templates = [
        ("진정서 {pid}가 전환된 사건",
         "MATCH (pt:vt_petition {{petition_id:'{pid}'}})-[r:filed_as]->(c:vt_case) RETURN pt, r, c",
         ["pt", "r", "c"]),
        ("{flnm} 사건과 연결된 진정서",
         "MATCH (pt:vt_petition)-[r:filed_as]->(c:vt_case {{flnm:'{flnm}'}}) RETURN pt, r, c",
         ["pt", "r", "c"]),
        ("진정서 {pid}와 연관된 기존 사건",
         "MATCH (pt:vt_petition {{petition_id:'{pid}'}})-[r:linked_to]->(c:vt_case) RETURN pt, r, c",
         ["pt", "r", "c"]),
        ("접수 대기 중인 진정서와 연결 사건",
         "MATCH (pt:vt_petition)-[r:filed_as]->(c:vt_case) WHERE pt->>'status' = 'PENDING' RETURN pt, r, c",
         ["pt", "r", "c"]),
    ]
    petition_ids = [f"PT-{y}-{n:03d}" for y in [2023, 2024] for n in range(1, 15)]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        pid = pick(petition_ids)
        flnm = pick(CASE_IDS)
        q_str = tpl.format(pid=pid, flnm=flnm)
        c = cypher.format(pid=pid, flnm=flnm)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_recorded_occurred(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_vhcl", "vhclno"), ("vt_movement", "movement_id, movement_dt, speed"),
         ("vt_loc", "loc_id, address, latitude, longitude")],
        [("vt_vhcl", "recorded_in", "vt_movement"),
         ("vt_movement", "occurred_at", "vt_loc")]
    )
    templates = [
        ("차량 {vhcl}의 이동 기록",
         "MATCH (v:vt_vhcl {{vhclno:'{vhcl}'}})-[r:recorded_in]->(m:vt_movement) RETURN v, r, m",
         ["v", "r", "m"]),
        ("이동 이벤트의 발생 위치",
         "MATCH (m:vt_movement)-[r:occurred_at]->(l:vt_loc) RETURN m, r, l",
         ["m", "r", "l"]),
        ("차량 {vhcl}의 이동 경로와 위치",
         "MATCH (v:vt_vhcl {{vhclno:'{vhcl}'}})-[:recorded_in]->(m:vt_movement)-[r:occurred_at]->(l:vt_loc) RETURN v, m, r, l",
         ["v", "m", "r", "l"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        vhcl = pick(VHCL_NOS)
        q_str = tpl.format(vhcl=vhcl)
        c = cypher.format(vhcl=vhcl)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_belongs_to(n: int) -> list[dict]:
    samples = []
    schema = schema_1hop(
        [("vt_bacnt", "account_no, bank_nm, bank_cd"),
         ("vt_org", "org_id, org_name, org_type")],
        "belongs_to", src_node="vt_bacnt", dst_node="vt_org"
    )
    templates = [
        ("계좌 {acct}가 속한 금융기관",
         "MATCH (b:vt_bacnt {{account_no:'{acct}'}})-[r:belongs_to]->(o:vt_org) RETURN b, r, o",
         ["b", "r", "o"]),
        ("{org}에 속한 계좌 목록",
         "MATCH (b:vt_bacnt)-[r:belongs_to]->(o:vt_org {{org_name:'{org}'}}) RETURN b, r, o",
         ["b", "r", "o"]),
        ("KB국민은행 계좌 전체",
         "MATCH (b:vt_bacnt)-[r:belongs_to]->(o:vt_org) WHERE o->>'org_name' = 'KB국민은행' RETURN b, r, o",
         ["b", "r", "o"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        acct = pick(ACCOUNT_NOS)
        org = pick(ORG_NAMES[:5])
        q_str = tpl.format(acct=acct, org=org)
        c = cypher.format(acct=acct, org=org)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_used_for_targets(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_telno", "telno, is_burner"),
         ("vt_impersonation", "event_id, method, fake_name, start_dt"),
         ("vt_org", "org_id, org_name")],
        [("vt_telno", "used_for", "vt_impersonation"),
         ("vt_impersonation", "targets", "vt_org")]
    )
    templates = [
        ("전화 {telno}가 사칭에 사용된 이벤트",
         "MATCH (t:vt_telno {{telno:'{telno}'}})-[r:used_for]->(i:vt_impersonation) RETURN t, r, i",
         ["t", "r", "i"]),
        ("{org}을 사칭한 이벤트 목록",
         "MATCH (i:vt_impersonation)-[r:targets]->(o:vt_org {{org_name:'{org}'}}) RETURN i, r, o",
         ["i", "r", "o"]),
        ("대포폰으로 사칭된 기관 체인",
         "MATCH (t:vt_telno)-[:used_for]->(i:vt_impersonation)-[r:targets]->(o:vt_org) WHERE t->>'is_burner' = 'true' RETURN t, i, r, o",
         ["t", "i", "r", "o"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        telno = pick(PHONE_NOS)
        org = pick(ORG_NAMES[:6])
        q_str = tpl.format(telno=telno, org=org)
        c = cypher.format(telno=telno, org=org)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


# ─── 신규 엣지 15종 생성기 ─────────────────────────────────────────────────────

def gen_related_case(n: int) -> list[dict]:
    samples = []
    schema = schema_1hop(
        [("vt_case", "flnm, incdnt_typ_cd, damage_amount, status")],
        "related_case", "confidence, inference", src_node="vt_case", dst_node="vt_case"
    )
    templates = [
        ("사건 {flnm}과 연관된 유사 사건",
         "MATCH (c1:vt_case {{flnm:'{flnm}'}})-[r:related_case]-(c2:vt_case) RETURN c1, r, c2",
         ["c1", "r", "c2"]),
        ("공유 증거 기반 유사 사건 목록",
         "MATCH (c1:vt_case)-[r:related_case]->(c2:vt_case) WHERE toFloat(r->>'confidence') >= 0.75 RETURN c1, r, c2",
         ["c1", "r", "c2"]),
        ("동일 피의자가 연루된 관련 사건",
         "MATCH (c1:vt_case {{flnm:'{flnm}'}})-[r:related_case]->(c2:vt_case) WHERE r->>'inference' = 'SHARED_SUSPECT' RETURN c1, r, c2",
         ["c1", "r", "c2"]),
        ("연관 사건이 있는 보이스피싱 사건",
         "MATCH (c1:vt_case)-[r:related_case]->(c2:vt_case) WHERE c1->>'incdnt_typ_cd' = 'VOICE_PHISHING' RETURN c1, r, c2",
         ["c1", "r", "c2"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        flnm = pick(CASE_IDS)
        q_str = tpl.format(flnm=flnm)
        c = cypher.format(flnm=flnm)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_owns_vehicle(n: int) -> list[dict]:
    samples = []
    schema = schema_1hop(
        [("vt_psn", "psn_id, name"), ("vt_vhcl", "vhclno, make, color, reg_dt")],
        "owns_vehicle", "valid_from, valid_to", src_node="vt_psn", dst_node="vt_vhcl"
    )
    templates = [
        ("{name}이 법적으로 소유한 차량 (등록원부 기준)",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:owns_vehicle]->(v:vt_vhcl) RETURN p, r, v",
         ["p", "r", "v"]),
        ("차량 {vhcl}의 법적 소유주",
         "MATCH (p:vt_psn)-[r:owns_vehicle]->(v:vt_vhcl {{vhclno:'{vhcl}'}}) RETURN p, r, v",
         ["p", "r", "v"]),
        ("{name}이 소유하지만 다른 사람이 운전한 차량",
         "MATCH (owner:vt_psn {{name:'{name}'}})-[:owns_vehicle]->(v:vt_vhcl)<-[r:drives]-(driver:vt_psn) WHERE owner <> driver RETURN owner, v, r, driver",
         ["owner", "v", "r", "driver"]),
        ("차량 등록 소유자와 실제 운전자가 다른 경우",
         "MATCH (owner:vt_psn)-[:owns_vehicle]->(v:vt_vhcl)<-[r:drives]-(driver:vt_psn) WHERE owner <> driver RETURN owner, v, r, driver",
         ["owner", "v", "r", "driver"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        vhcl = pick(VHCL_NOS)
        q_str = tpl.format(name=name, vhcl=vhcl)
        c = cypher.format(name=name, vhcl=vhcl)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_registered_to(n: int) -> list[dict]:
    samples = []
    schema = schema_1hop(
        [("vt_telno", "telno, is_burner, carrier"),
         ("vt_psn", "psn_id, name")],
        "registered_to", src_node="vt_telno", dst_node="vt_psn"
    )
    templates = [
        ("{telno}의 명의자 조회",
         "MATCH (t:vt_telno {{telno:'{telno}'}})-[r:registered_to]->(p:vt_psn) RETURN t, r, p",
         ["t", "r", "p"]),
        ("{name} 명의로 등록된 전화번호 역방향 조회",
         "MATCH (p:vt_psn {{name:'{name}'}})<-[r:registered_to]-(t:vt_telno) RETURN t, r, p",
         ["t", "r", "p"]),
        ("대포폰의 명의자 (registered_to 기준)",
         "MATCH (t:vt_telno)-[r:registered_to]->(p:vt_psn) WHERE t->>'is_burner' = 'true' RETURN t, r, p",
         ["t", "r", "p"]),
        ("실사용자(owns_phone)와 명의자(registered_to)가 다른 번호",
         "MATCH (actual:vt_psn)-[:owns_phone]->(t:vt_telno)-[r:registered_to]->(reg:vt_psn) WHERE actual <> reg RETURN actual, t, r, reg",
         ["actual", "t", "r", "reg"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        telno = pick(PHONE_NOS)
        q_str = tpl.format(name=name, telno=telno)
        c = cypher.format(name=name, telno=telno)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_mentions_account(n: int) -> list[dict]:
    samples = []
    schema = schema_1hop(
        [("vt_msg", "msg_id, msg_type, app_nm, dsptch_dt, spam_yn"),
         ("vt_bacnt", "account_no, bank_nm, is_burner")],
        "mentions_account", "confidence", src_node="vt_msg", dst_node="vt_bacnt"
    )
    templates = [
        ("계좌번호 {acct}가 언급된 메시지",
         "MATCH (m:vt_msg)-[r:mentions_account]->(b:vt_bacnt {{account_no:'{acct}'}}) RETURN m, r, b",
         ["m", "r", "b"]),
        ("보이스피싱 의심 문자에서 계좌 언급 (confidence 0.85 이상)",
         "MATCH (m:vt_msg)-[r:mentions_account]->(b:vt_bacnt) WHERE toFloat(r->>'confidence') >= 0.85 RETURN m, r, b",
         ["m", "r", "b"]),
        ("대포통장이 언급된 스팸 문자",
         "MATCH (m:vt_msg)-[r:mentions_account]->(b:vt_bacnt) WHERE b->>'is_burner' = 'true' AND m->>'spam_yn' = 'Y' RETURN m, r, b",
         ["m", "r", "b"]),
        ("카카오톡 메시지에서 언급된 계좌",
         "MATCH (m:vt_msg)-[r:mentions_account]->(b:vt_bacnt) WHERE m->>'app_nm' = '카카오톡' RETURN m, r, b",
         ["m", "r", "b"]),
        ("계좌 언급 건수가 많은 메시지 TOP 10",
         "MATCH (m:vt_msg)-[r:mentions_account]->(b:vt_bacnt) RETURN m, count(b) AS cnt ORDER BY cnt DESC LIMIT 10",
         ["m", "cnt"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        acct = pick(ACCOUNT_NOS)
        q_str = tpl.format(acct=acct)
        c = cypher.format(acct=acct)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_communicated_with(n: int) -> list[dict]:
    samples = []
    schema = schema_1hop(
        [("vt_ip", "ip_addr, country, is_vpn, threat_score")],
        "communicated_with", "protocol, detected_at", src_node="vt_ip", dst_node="vt_ip"
    )
    templates = [
        ("IP {ip}와 직접 통신한 IP 목록 (C2 추적)",
         "MATCH (i1:vt_ip {{ip_addr:'{ip}'}})-[r:communicated_with]->(i2:vt_ip) RETURN i1, r, i2",
         ["i1", "r", "i2"]),
        ("IP {ip}의 양방향 통신 IP",
         "MATCH (i1:vt_ip {{ip_addr:'{ip}'}})-[r:communicated_with]-(i2:vt_ip) RETURN i1, r, i2",
         ["i1", "r", "i2"]),
        ("해외 IP와 통신한 국내 IP",
         "MATCH (i1:vt_ip)-[r:communicated_with]->(i2:vt_ip) WHERE i1->>'country' = 'KR' AND i2->>'country' <> 'KR' RETURN i1, r, i2",
         ["i1", "r", "i2"]),
        ("C2 서버로 의심되는 IP (위협점수 90 이상과 통신)",
         "MATCH (i1:vt_ip)-[r:communicated_with]->(i2:vt_ip) WHERE toInteger(i2->>'threat_score') >= 90 RETURN i1, r, i2",
         ["i1", "r", "i2"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        ip = pick(IP_ADDRS)
        q_str = tpl.format(ip=ip)
        c = cypher.format(ip=ip)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_operates(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_psn", "psn_id, name, risk_level"),
         ("vt_org", "org_id, org_name"),
         ("vt_site", "url_addr, is_malicious, site_type"),
         ("vt_id", "id_val, platform, is_active")],
        [("vt_psn", "operates", "vt_site"), ("vt_psn", "operates", "vt_id"),
         ("vt_org", "operates", "vt_id")]
    )
    templates = [
        ("{name}이 운영하는 웹사이트",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:operates]->(s:vt_site) RETURN p, r, s",
         ["p", "r", "s"]),
        ("{name}의 플랫폼 계정 (디지털 ID)",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:operates]->(i:vt_id) RETURN p, r, i",
         ["p", "r", "i"]),
        ("{url}의 운영자",
         "MATCH (p:vt_psn)-[r:operates]->(s:vt_site {{url_addr:'{url}'}}) RETURN p, r, s",
         ["p", "r", "s"]),
        ("악성 사이트 운영자 전체",
         "MATCH (p:vt_psn)-[r:operates]->(s:vt_site) WHERE s->>'is_malicious' = 'true' RETURN p, r, s",
         ["p", "r", "s"]),
        ("{org}이 운영하는 디지털 채널",
         "MATCH (o:vt_org {{org_name:'{org}'}})-[r:operates]->(i:vt_id) RETURN o, r, i",
         ["o", "r", "i"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        url = pick(URLS)
        org = pick(ORG_NAMES)
        q_str = tpl.format(name=name, url=url, org=org)
        c = cypher.format(name=name, url=url, org=org)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_recruits_blackmails(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_psn", "psn_id, name, risk_level")],
        [("vt_psn", "recruits", "vt_psn"), ("vt_psn", "blackmails", "vt_psn")]
    )
    templates = [
        ("{name}이 모집한 조직원",
         "MATCH (boss:vt_psn {{name:'{name}'}})-[r:recruits]->(member:vt_psn) RETURN boss, r, member",
         ["boss", "r", "member"]),
        ("{name}을 모집한 상위 모집책",
         "MATCH (boss:vt_psn)-[r:recruits]->(member:vt_psn {{name:'{name}'}}) RETURN boss, r, member",
         ["boss", "r", "member"]),
        ("보이스피싱 조직 모집 체인 (2~3단계)",
         "MATCH path = (boss:vt_psn)-[:recruits*2..3]->(foot:vt_psn) RETURN path",
         ["path"]),
        ("{name}이 협박한 피해자 목록",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:blackmails]->(victim:vt_psn) RETURN p, r, victim",
         ["p", "r", "victim"]),
        ("몸캠피싱 협박 피해자 전체",
         "MATCH (p:vt_psn)-[r:blackmails]->(victim:vt_psn) WHERE r->>'method' = '몸캠피싱' RETURN p, r, victim",
         ["p", "r", "victim"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        q_str = tpl.format(name=name)
        c = cypher.format(name=name)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_hosts(n: int) -> list[dict]:
    samples = []
    schema = schema_1hop(
        [("vt_ip", "ip_addr, country, threat_score"),
         ("vt_site", "url_addr, is_malicious, site_type")],
        "hosts", "port, detected_at", src_node="vt_ip", dst_node="vt_site"
    )
    templates = [
        ("IP {ip}에 호스팅된 사이트",
         "MATCH (ip:vt_ip {{ip_addr:'{ip}'}})-[r:hosts]->(s:vt_site) RETURN ip, r, s",
         ["ip", "r", "s"]),
        ("{url}의 호스팅 서버 IP",
         "MATCH (ip:vt_ip)-[r:hosts]->(s:vt_site {{url_addr:'{url}'}}) RETURN ip, r, s",
         ["ip", "r", "s"]),
        ("악성 사이트를 호스팅하는 IP",
         "MATCH (ip:vt_ip)-[r:hosts]->(s:vt_site) WHERE s->>'is_malicious' = 'true' RETURN ip, r, s",
         ["ip", "r", "s"]),
        ("피싱 사이트 인프라 역추적 (IP → Site)",
         "MATCH (ip:vt_ip)-[r:hosts]->(s:vt_site) WHERE s->>'site_type' = 'PHISHING' RETURN ip, r, s",
         ["ip", "r", "s"]),
        ("동일 IP에 호스팅된 악성 사이트 수",
         "MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) WHERE s->>'is_malicious' = 'true' RETURN ip, count(s) AS site_cnt ORDER BY site_cnt DESC",
         ["ip", "site_cnt"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        ip = pick(IP_ADDRS)
        url = pick(URLS)
        q_str = tpl.format(ip=ip, url=url)
        c = cypher.format(ip=ip, url=url)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_contains_file(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_site", "url_addr, is_malicious"),
         ("vt_msg", "msg_id, msg_type"),
         ("vt_file", "file_hash, file_name, is_malicious, file_type")],
        [("vt_site", "contains_file", "vt_file"),
         ("vt_msg", "contains_file", "vt_file")]
    )
    templates = [
        ("{url}에 포함된 파일 목록",
         "MATCH (s:vt_site {{url_addr:'{url}'}})-[r:contains_file]->(f:vt_file) RETURN s, r, f",
         ["s", "r", "f"]),
        ("사이트에 포함된 악성 파일",
         "MATCH (s:vt_site)-[r:contains_file]->(f:vt_file) WHERE f->>'is_malicious' = 'true' RETURN s, r, f",
         ["s", "r", "f"]),
        ("메시지 첨부 악성 파일",
         "MATCH (m:vt_msg)-[r:contains_file]->(f:vt_file) WHERE f->>'is_malicious' = 'true' RETURN m, r, f",
         ["m", "r", "f"]),
        ("해시 {fhash}인 파일이 있는 사이트",
         "MATCH (s:vt_site)-[r:contains_file]->(f:vt_file {{file_hash:'{fhash}'}}) RETURN s, r, f",
         ["s", "r", "f"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        url = pick(URLS)
        fhash = pick(FILE_HASHES)
        q_str = tpl.format(url=url, fhash=fhash)
        c = cypher.format(url=url, fhash=fhash)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_located_at(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_atm", "atm_id, bank_nm"),
         ("vt_dev", "device_id, device_type"),
         ("vt_org", "org_id, org_name"),
         ("vt_loc", "loc_id, address, latitude, longitude")],
        [("vt_atm", "located_at", "vt_loc"),
         ("vt_dev", "located_at", "vt_loc"),
         ("vt_org", "located_at", "vt_loc")]
    )
    templates = [
        ("ATM {atm}의 설치 위치",
         "MATCH (a:vt_atm {{atm_id:'{atm}'}})-[r:located_at]->(l:vt_loc) RETURN a, r, l",
         ["a", "r", "l"]),
        ("기기 {dev}의 현재 위치",
         "MATCH (d:vt_dev {{device_id:'{dev}'}})-[r:located_at]->(l:vt_loc) RETURN d, r, l",
         ["d", "r", "l"]),
        ("{loc} 지역의 ATM 목록",
         "MATCH (a:vt_atm)-[r:located_at]->(l:vt_loc) WHERE l->>'address' CONTAINS '{loc}' RETURN a, r, l",
         ["a", "r", "l"]),
        ("{org}의 지점 주소",
         "MATCH (o:vt_org {{org_name:'{org}'}})-[r:located_at]->(l:vt_loc) RETURN o, r, l",
         ["o", "r", "l"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        atm = pick(ATM_IDS)
        dev = pick(DEV_IDS)
        loc = pick(LOC_NAMES)
        org = pick(ORG_NAMES[:5])
        q_str = tpl.format(atm=atm, dev=dev, loc=loc, org=org)
        c = cypher.format(atm=atm, dev=dev, loc=loc, org=org)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_sent_received_msg(n: int) -> list[dict]:
    samples = []
    schema = schema_chain(
        [("vt_psn", "psn_id, name"),
         ("vt_msg", "msg_id, msg_type, app_nm, dsptch_dt, spam_yn, content_hash"),
         ("vt_telno", "telno, is_burner")],
        [("vt_psn", "sent_msg", "vt_msg"),
         ("vt_msg", "received_msg", "vt_telno")]
    )
    templates = [
        ("{name}이 발송한 메시지",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:sent_msg]->(m:vt_msg) RETURN p, r, m",
         ["p", "r", "m"]),
        ("{telno}로 수신된 메시지",
         "MATCH (m:vt_msg)-[r:received_msg]->(t:vt_telno {{telno:'{telno}'}}) RETURN m, r, t",
         ["m", "r", "t"]),
        ("{name}이 보낸 스팸 메시지",
         "MATCH (p:vt_psn {{name:'{name}'}})-[r:sent_msg]->(m:vt_msg) WHERE m->>'spam_yn' = 'Y' RETURN p, r, m",
         ["p", "r", "m"]),
        ("대포폰으로 수신된 카카오톡 메시지",
         "MATCH (m:vt_msg)-[r:received_msg]->(t:vt_telno) WHERE t->>'is_burner' = 'true' AND m->>'app_nm' = '카카오톡' RETURN m, r, t",
         ["m", "r", "t"]),
        ("{name}이 발송한 메시지 수신 전화번호 체인",
         "MATCH (p:vt_psn {{name:'{name}'}})-[:sent_msg]->(m:vt_msg)-[r:received_msg]->(t:vt_telno) RETURN p, m, r, t",
         ["p", "m", "r", "t"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        name = pick(NAMES)
        telno = pick(PHONE_NOS)
        q_str = tpl.format(name=name, telno=telno)
        c = cypher.format(name=name, telno=telno)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


def gen_sourced_from(n: int) -> list[dict]:
    samples = []
    schema = (
        "노드:\n"
        "  (vt_src {src_id, src_name, src_type, reliability_tier})\n"
        "  (vt_psn {psn_id, name})\n"
        "  (vt_bacnt {account_no, bank_nm})\n"
        "  (vt_case {flnm, incdnt_typ_cd})\n"
        "관계:\n"
        "  (Any)-[:sourced_from {src_tier, rec_created}]->(vt_src)\n"
        "속성 접근:\n"
        "  WHERE n->>'속성명' = '값'  (문자열)\n"
        "  WHERE toInteger(n->>'속성명') >= 숫자  (숫자)"
    )
    templates = [
        ("tier 1~2 공식 출처의 계좌만 조회",
         "MATCH (b:vt_bacnt)-[r:sourced_from]->(s:vt_src) WHERE toInteger(s->>'reliability_tier') <= 2 RETURN b, r, s",
         ["b", "r", "s"]),
        ("KICS 공식 수사자료에서 수집된 인물 정보",
         "MATCH (p:vt_psn)-[r:sourced_from]->(s:vt_src) WHERE s->>'src_type' = 'OFFICIAL' RETURN p, r, s",
         ["p", "r", "s"]),
        ("출처별 수집 노드 수 집계",
         "MATCH (n)-[:sourced_from]->(s:vt_src) RETURN s->>'src_name' AS src_name, count(n) AS cnt ORDER BY cnt DESC",
         ["src_name", "cnt"]),
        ("OSINT 제외한 피의자 목록 (tier 1~3)",
         "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case), (p)-[:sourced_from]->(s:vt_src) WHERE toInteger(s->>'reliability_tier') <= 3 RETURN p, c, s",
         ["p", "c", "s"]),
        ("출처 신뢰도 tier 4 이상 (OSINT/보고서) 데이터",
         "MATCH (n)-[r:sourced_from]->(s:vt_src) WHERE toInteger(s->>'reliability_tier') >= 4 RETURN n, r, s",
         ["n", "r", "s"]),
        ("기관연계(AGENCY) 출처 계좌",
         "MATCH (b:vt_bacnt)-[r:sourced_from]->(s:vt_src) WHERE s->>'src_type' = 'AGENCY' RETURN b, r, s",
         ["b", "r", "s"]),
    ]
    for _ in range(n):
        tpl, cypher, rets = random.choice(templates)
        q_str = tpl
        c = cypher
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


# ─── 체인/멀티홉 생성기 ───────────────────────────────────────────────────────

def gen_multihop_chains(n: int) -> list[dict]:
    """핵심 수사 시나리오 체인 패턴 (1,000개 목표)"""
    samples = []

    chain_templates = [
        # 자금세탁: 인물→계좌→이체→계좌
        (
            schema_chain(
                [("vt_psn", "psn_id, name"), ("vt_bacnt", "account_no, bank_nm, is_burner"),
                 ("vt_transfer", "txn_id, amount, txn_dt"), ("vt_bacnt", "account_no, bank_nm")],
                [("vt_psn", "has_account", "vt_bacnt"),
                 ("vt_bacnt", "from_account", "vt_transfer"),
                 ("vt_transfer", "to_account", "vt_bacnt")]
            ),
            "{name}의 계좌에서 출발한 이체 흐름 추적",
            "MATCH (p:vt_psn {{name:'{name}'}})-[:has_account]->(b1:vt_bacnt)-[:from_account]->(tr:vt_transfer)-[r:to_account]->(b2:vt_bacnt) RETURN p, b1, tr, r, b2",
            ["p", "b1", "tr", "r", "b2"],
        ),
        # 보이스피싱: 전화→통화 (발신 이력)
        (
            schema_chain(
                [("vt_psn", "psn_id, name"), ("vt_telno", "telno, is_burner"),
                 ("vt_call", "call_id, call_dt, duration_sec")],
                [("vt_psn", "owns_phone", "vt_telno"),
                 ("vt_telno", "caller", "vt_call")]
            ),
            "{name} 명의 전화의 발신 통화 내역",
            "MATCH (p:vt_psn {{name:'{name}'}})-[:owns_phone]->(t:vt_telno)-[r:caller]->(c:vt_call) RETURN p, t, r, c",
            ["p", "t", "r", "c"],
        ),
        # 인프라 추적: IP→사이트→파일
        (
            schema_chain(
                [("vt_ip", "ip_addr, threat_score"),
                 ("vt_site", "url_addr, is_malicious"),
                 ("vt_file", "file_hash, is_malicious")],
                [("vt_ip", "hosts", "vt_site"),
                 ("vt_site", "contains_file", "vt_file")]
            ),
            "IP {ip}에서 호스팅된 사이트의 악성 파일 추적",
            "MATCH (ip:vt_ip {{ip_addr:'{ip}'}})-[:hosts]->(s:vt_site)-[r:contains_file]->(f:vt_file) WHERE f->>'is_malicious' = 'true' RETURN ip, s, r, f",
            ["ip", "s", "r", "f"],
        ),
        # 사칭 체인: 전화→사칭이벤트→피해기관
        (
            schema_chain(
                [("vt_telno", "telno, is_burner"),
                 ("vt_impersonation", "event_id, method, fake_name"),
                 ("vt_org", "org_name, org_type")],
                [("vt_telno", "used_for", "vt_impersonation"),
                 ("vt_impersonation", "targets", "vt_org")]
            ),
            "대포폰으로 사칭된 금융기관 체인",
            "MATCH (t:vt_telno)-[:used_for]->(i:vt_impersonation)-[r:targets]->(o:vt_org) WHERE t->>'is_burner' = 'true' RETURN t, i, r, o",
            ["t", "i", "r", "o"],
        ),
        # 조직망: 총책→모집→말단
        (
            schema_chain(
                [("vt_psn", "psn_id, name, risk_level")],
                [("vt_psn", "recruits", "vt_psn")]
            ),
            "보이스피싱 조직 2~3단계 모집 체인",
            "MATCH path = (boss:vt_psn)-[:recruits*2..3]->(foot:vt_psn) RETURN path",
            ["path"],
        ),
        # 이동추적: 차량→이동→위치
        (
            schema_chain(
                [("vt_psn", "psn_id, name"), ("vt_vhcl", "vhclno"),
                 ("vt_movement", "movement_id, movement_dt"),
                 ("vt_loc", "loc_id, address")],
                [("vt_psn", "drives", "vt_vhcl"),
                 ("vt_vhcl", "recorded_in", "vt_movement"),
                 ("vt_movement", "occurred_at", "vt_loc")]
            ),
            "{name}이 운전한 차량의 이동 경로",
            "MATCH (p:vt_psn {{name:'{name}'}})-[:drives]->(v:vt_vhcl)-[:recorded_in]->(m:vt_movement)-[r:occurred_at]->(l:vt_loc) RETURN p, v, m, r, l",
            ["p", "v", "m", "r", "l"],
        ),
        # 메시지→계좌 언급→계좌
        (
            schema_chain(
                [("vt_psn", "psn_id, name"), ("vt_msg", "msg_id, msg_type, spam_yn"),
                 ("vt_bacnt", "account_no, is_burner")],
                [("vt_psn", "sent_msg", "vt_msg"),
                 ("vt_msg", "mentions_account", "vt_bacnt")]
            ),
            "{name}이 발송한 메시지에 언급된 계좌",
            "MATCH (p:vt_psn {{name:'{name}'}})-[:sent_msg]->(m:vt_msg)-[r:mentions_account]->(b:vt_bacnt) RETURN p, m, r, b",
            ["p", "m", "r", "b"],
        ),
        # 피의자→사건→출처 신뢰도
        (
            schema_chain(
                [("vt_psn", "psn_id, name"), ("vt_case", "flnm, incdnt_typ_cd"),
                 ("vt_src", "src_id, src_name, reliability_tier")],
                [("vt_psn", "suspect_in", "vt_case"),
                 ("vt_case", "sourced_from", "vt_src")]
            ),
            "출처 신뢰도 tier 2 이하 사건의 피의자",
            "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case)-[r:sourced_from]->(s:vt_src) WHERE toInteger(s->>'reliability_tier') <= 2 RETURN p, c, r, s",
            ["p", "c", "r", "s"],
        ),
        # 계좌 소속 기관 역추적
        (
            schema_chain(
                [("vt_psn", "psn_id, name"), ("vt_bacnt", "account_no, bank_nm"),
                 ("vt_org", "org_id, org_name")],
                [("vt_psn", "has_account", "vt_bacnt"),
                 ("vt_bacnt", "belongs_to", "vt_org")]
            ),
            "{name}의 계좌가 속한 금융기관",
            "MATCH (p:vt_psn {{name:'{name}'}})-[:has_account]->(b:vt_bacnt)-[r:belongs_to]->(o:vt_org) RETURN p, b, r, o",
            ["p", "b", "r", "o"],
        ),
        # 동일인물 통합 계좌 조회
        (
            schema_chain(
                [("vt_psn", "psn_id, name"), ("vt_bacnt", "account_no")],
                [("vt_psn", "sameAs", "vt_psn"), ("vt_psn", "has_account", "vt_bacnt")]
            ),
            "{name}의 별명/동일인물 포함 전체 계좌",
            "MATCH (p:vt_psn {{name:'{name}'}})-[:sameAs*0..2]-(alias:vt_psn)-[r:has_account]->(b:vt_bacnt) RETURN alias, r, b",
            ["alias", "r", "b"],
        ),
        # IP→접속→악성사이트→파일
        (
            schema_chain(
                [("vt_ip", "ip_addr, is_vpn"),
                 ("vt_access", "access_id, access_dt"),
                 ("vt_site", "url_addr, is_malicious"),
                 ("vt_file", "file_hash, file_type, is_malicious")],
                [("vt_ip", "accessed_from", "vt_access"),
                 ("vt_access", "accessed_to", "vt_site"),
                 ("vt_site", "contains_file", "vt_file")]
            ),
            "VPN IP가 접속한 악성 사이트의 파일",
            "MATCH (ip:vt_ip)-[:accessed_from]->(a:vt_access)-[:accessed_to]->(s:vt_site)-[r:contains_file]->(f:vt_file) WHERE ip->>'is_vpn' = 'true' AND f->>'is_malicious' = 'true' RETURN ip, s, r, f",
            ["ip", "s", "r", "f"],
        ),
    ]

    for _ in range(n):
        schema, q_tpl, c_tpl, rets = random.choice(chain_templates)
        name = pick(NAMES)
        ip = pick(IP_ADDRS)
        flnm = pick(CASE_IDS)
        q_str = q_tpl.format(name=name, ip=ip, flnm=flnm)
        c = c_tpl.format(name=name, ip=ip, flnm=flnm)
        samples.append(make_sample(schema, q_str, c, rets))
    return samples


# ─── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    all_samples: list[dict] = []

    # ── 기존 엣지 보강 (1-hop) ─────────────────────────────────────────────
    gen_plan = [
        ("has_account",       gen_has_account,       200),
        ("owns_phone",        gen_owns_phone,         150),
        ("suspect/victim/wit",gen_suspect_victim_witness, 430),
        ("caller/callee",     gen_caller_callee,      200),
        ("from/to_account",   gen_transfer_edges,     200),
        ("transferred_to",    gen_transferred_to,     100),
        ("accessed_*",        gen_access_edges,       150),
        ("used_ip",           gen_used_ip,            100),
        ("member/works",      gen_member_works,       250),
        ("accomplice/sameAs", gen_accomplice_sameAs,  200),
        ("drives/eg_used",    gen_drives_eg_used,     200),
        ("filed_as/linked",   gen_filed_as_linked_to, 150),
        ("recorded/occurred", gen_recorded_occurred,  100),
        ("belongs_to",        gen_belongs_to,         100),
        ("used_for/targets",  gen_used_for_targets,   100),
    ]

    # ── 신규 엣지 15종 ─────────────────────────────────────────────────────
    new_edge_plan = [
        ("related_case",      gen_related_case,       120),
        ("owns_vehicle",      gen_owns_vehicle,       100),
        ("registered_to",     gen_registered_to,      100),
        ("mentions_account",  gen_mentions_account,   150),
        ("communicated_with", gen_communicated_with,   80),
        ("operates",          gen_operates,           150),
        ("recruits/blackmails",gen_recruits_blackmails,150),
        ("hosts",             gen_hosts,              120),
        ("contains_file",     gen_contains_file,      100),
        ("located_at",        gen_located_at,         100),
        ("sent/received_msg", gen_sent_received_msg,  120),
        ("sourced_from",      gen_sourced_from,       180),
    ]

    # ── 체인/멀티홉 ────────────────────────────────────────────────────────
    chain_plan = [
        ("multihop_chains",   gen_multihop_chains,    1_000),
    ]

    full_plan = gen_plan + new_edge_plan + chain_plan
    total_target = sum(t for _, _, t in full_plan)

    print(f"생성 계획: {len(full_plan)} 카테고리, 목표 {total_target:,}개\n")

    for label, gen_fn, target in full_plan:
        samples = gen_fn(target)
        all_samples.extend(samples)
        print(f"  {label:<22} {len(samples):>5,}개 생성")

    random.shuffle(all_samples)

    DST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DST_PATH, "w", encoding="utf-8") as f:
        json.dump(all_samples, f, ensure_ascii=False, indent=2)

    print(f"\n=== 01_generate_templates 완료 ===")
    print(f"  총 생성: {len(all_samples):,}개 → {DST_PATH}")

    # 분포 확인
    from collections import Counter
    intents = Counter(s.get("intent") for s in all_samples)
    print(f"  Intent: {dict(intents)}")

    # 엣지 타입 분포
    edge_cnt: Counter = Counter()
    for s in all_samples:
        gpt = next((c["value"] for c in s["conversations"] if c["from"] == "gpt"), "")
        for m in re.finditer(r"\[:([a-z_*]+)", gpt):
            edge_cnt[m.group(1)] += 1
    print(f"\n  상위 20 엣지:")
    for edge, cnt in edge_cnt.most_common(20):
        print(f"    {edge:<30} {cnt:>5}")


if __name__ == "__main__":
    main()
