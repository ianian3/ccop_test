"""
generate_t2c_sft.py — Phase 2 Step 1
템플릿 기반 Text2Cypher SFT 데이터셋 생성 (목표: 5,000개)
기준 온톨로지: v3.5 (23 노드, 52 엣지, vt_impersonation 포함)
출력: data/t2c_v1_template.json (ShareGPT 포맷)
"""

import json
import random
import re
import os
from itertools import product
from copy import deepcopy

random.seed(42)

# ─────────────────────────────────────────────────────────────
# 1. 샘플 값 풀
# ─────────────────────────────────────────────────────────────

NAMES = [
    "홍길동", "김철수", "이영희", "박민준", "최지현",
    "정수현", "강민서", "윤지호", "장하은", "임도현",
    "오서연", "신재원", "배수진", "허민지", "류성준",
    "남기태", "양소영", "전현우", "조아름", "문재철",
    "한소희", "권지훈", "노민아", "석진호", "엄수아",
    "천기범", "방예진", "곽도현", "모지수", "봉성철",
    "안채원", "원동혁", "차민경", "탁승준", "하예슬",
    "가나윤", "나다은", "다라진", "마바서", "사아혁",
    "이기택", "정나래", "조민혁", "최서윤", "한다솔",
    "강재원", "김보람", "류시현", "박태양", "송하나",
]

ACCOUNTS = [
    "110-123-456789", "356-0123-4567-01", "901-1234-5678",
    "218-910234-01-011", "001-234567-01-001", "088-12345-67890",
    "620-123456-78901", "102-1234-567890", "567-890123-45678",
    "323-456-789012", "401-2345-678901", "502-3456-789012",
    "703-4567-890123", "804-5678-901234", "905-6789-012345",
    "106-7890-123456", "207-8901-234567", "308-9012-345678",
    "409-0123-456789", "510-1234-567890", "611-2345-678901",
    "712-3456-789012", "813-4567-890123", "914-5678-901234",
    "015-6789-012345", "116-7890-123456", "217-8901-234567",
    "318-9012-345678", "419-0123-456789", "520-1234-567890",
]

BANK_CDS = ["004", "011", "020", "023", "027", "039", "081", "088", "090"]
BANK_NMS = ["국민은행", "농협은행", "우리은행", "SC제일은행", "씨티은행", "경남은행", "하나은행", "신한은행", "카카오뱅크"]

CASE_NOS = [
    "2024-01234", "2023-56789", "2024-00012", "2025-11111",
    "2023-99999", "2024-77890", "2025-00456", "2024-33210",
    "2024-10001", "2024-10002", "2024-10003", "2024-10004",
    "2023-20001", "2023-20002", "2023-20003", "2025-30001",
    "2025-30002", "2024-40001", "2024-40002", "2023-50001",
]

PETITION_IDS = [
    "PT-2024-001", "PT-2024-002", "PT-2023-100", "PT-2025-042",
    "PT-2024-567", "PT-2023-999", "PT-2024-010", "PT-2024-020",
    "PT-2025-001", "PT-2025-002", "PT-2023-050", "PT-2024-100",
]

PHONES = [
    "010-1234-5678", "010-9876-5432", "010-2345-6789",
    "010-3456-7890", "010-4567-8901", "010-5678-9012",
    "02-123-4567", "031-456-7890", "070-1234-5678",
    "010-6789-0123", "010-7890-1234", "010-8901-2345",
    "010-9012-3456", "010-0123-4567", "010-1111-2222",
    "010-3333-4444", "010-5555-6666", "010-7777-8888",
    "010-9999-0000", "011-1234-5678", "016-2345-6789",
    "017-3456-7890", "018-4567-8901", "019-5678-9012",
    "010-2222-3333", "010-4444-5555", "010-6666-7777",
    "010-8888-9999", "010-1357-2468", "010-2468-1357",
]

IPS = [
    "1.2.3.4", "192.168.0.1", "10.0.0.5", "203.0.113.99",
    "172.16.0.10", "8.8.8.8", "198.51.100.42",
    "45.33.32.156", "104.21.30.200", "185.220.101.1",
    "77.88.8.1", "91.108.4.1", "149.154.160.1",
    "174.0.0.1", "208.67.222.222", "1.1.1.1",
    "123.45.67.89", "234.56.78.90", "10.10.10.10",
    "192.0.2.100",
]

URLS = [
    "http://phishing-site.com", "https://fake-bank.kr",
    "http://malware-host.net", "https://scam-shop.co.kr",
    "http://virus-drop.io", "https://fraud-portal.com",
    "http://stolen-data.net", "https://hack-tools.io",
    "http://botnet-cc.ru", "https://darkweb-market.onion",
    "http://credential-steal.xyz", "https://ransomware-drop.io",
    "http://exploit-kit.net", "https://fake-login.co.kr",
    "http://smishing-link.com",
]

ORG_NAMES = [
    "국민은행", "경찰청", "금융감독원", "검찰청", "사이버범죄수사대",
    "신한은행", "하나은행", "카카오", "우리은행", "농협은행",
    "KT", "SK텔레콤", "LG유플러스", "금융위원회", "법원",
]

TRANSFER_IDS = [
    "TR-20240101-001", "TR-20240215-042", "TR-20230901-999",
    "TR-20250310-100", "TR-20240501-200", "TR-20240601-300",
    "TR-20231201-400", "TR-20250101-500", "TR-20240701-600",
    "TR-20240801-700",
]

CALL_IDS = [
    "CALL-20240301-001", "CALL-20231215-999", "CALL-20250101-042",
    "CALL-20240401-100", "CALL-20240501-200", "CALL-20230901-300",
    "CALL-20250201-400", "CALL-20240601-500",
]

VHCLNOS = [
    "12가3456", "34나7890", "56다1234", "78라5678",
    "90마6789", "11바2345", "22사3456", "33아4567",
    "44자5678", "55차6789",
]

DEVICE_IDS = [
    "DEV-AABBCCDD", "DEV-11223344", "DEV-DEADBEEF",
    "DEV-CAFEBABE", "DEV-12345678", "DEV-ABCD1234",
]

WALLET_ADDRS = [
    "0xABCD1234EFGH5678", "bc1qxyzabc123456789", "1A2B3C4D5E6F7G8H",
    "0xDEAD1234BEEF5678", "bc1qabcdef123456789", "3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5",
]

EMAIL_ADDRS = [
    "suspect@gmail.com", "phisher@fake.org", "moneymule123@naver.com",
    "fraud.user@proton.me", "scammer99@yahoo.com", "darknet.actor@tutanota.com",
]

GRAPH = "tccop_graph"

# ─────────────────────────────────────────────────────────────
# 2. 시스템 프롬프트
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """당신은 AgensGraph(Apache AGE 기반) Cypher 쿼리 전문가입니다.
사용자의 자연어 질문을 받아 정확한 AgensGraph Cypher 쿼리로 변환하세요.

[필수 출력 규칙]
1. 반드시 SELECT * FROM cypher('{graph}', $$ ... $$) AS (...) 형식으로 출력
2. RETURN 변수 수와 AS 컬럼 수가 반드시 일치해야 함 (모두 agtype)
3. 속성 접근: n->>'속성명' (문자열), toInteger(n->>'속성명') (숫자)
4. 쓰기 명령(CREATE/MERGE/DELETE/SET) 금지 — 조회 전용
5. 그래프 이름은 항상 '{graph}' 사용
6. 수사와 무관한 질문은 "수사 관련 질문만 답변 가능합니다." 출력

[응답 형식]
질문을 분석한 후 쿼리만 출력하세요. 설명 없이 SQL 구문만 반환합니다.
""".format(graph=GRAPH)

# ─────────────────────────────────────────────────────────────
# 3. 스키마 스니펫 빌더
# ─────────────────────────────────────────────────────────────

NODE_PROPS = {
    "vt_src":      "src_id, src_name, src_type, reliability_tier",
    "vt_case":     "flnm, incdnt_typ_cd, status, damage_amount, risk_level",
    "vt_petition": "petition_id, rcpt_dt, crime_type_cd, damage_amt, status",
    "vt_psn":      "psn_id, name, korn_flnm, dob, gender, rrno_hash, risk_level",
    "vt_org":      "org_id, org_name, org_category, inst_se_cd, bank_cd",
    "vt_bacnt":    "account_no, bank_cd, bank_nm, dpstr_nm, is_burner, is_frozen",
    "vt_telno":    "telno, telco_nm, join_typ_cd, is_burner, spam_cnt",
    "vt_ip":       "ip_addr, is_vpn, is_tor, is_proxy, abuse_score",
    "vt_site":     "url_addr, dmn_addr, site_type, is_malicious, risk_grd",
    "vt_file":     "hash_val, file_nm, is_malicious, vt_score",
    "vt_id":       "id_val, platform, id_type, is_active",
    "vt_vhcl":     "vhclno, carmdl_nm, ownr_nm, stolen_yn",
    "vt_email":    "email_addr, domain, provider, is_disposable",
    "vt_crypto":   "wallet_addr, blockchain, exchange, risk_score, balance",
    "vt_dev":      "device_id, dev_type, imei, mac_addr, os",
    "vt_atm":      "atm_id, bank_nm, bank_cd, loc_id",
    "vt_loc":      "loc_id, loc_type, address, lat, lng",
    "vt_transfer": "transfer_id, dlng_amt, dlng_dt, dlng_se_cd, hop_level, is_suspicious",
    "vt_call":     "call_id, call_strt_dt, call_dur_sec, call_typ_cd",
    "vt_msg":      "msg_id, msg_type, app_nm, spam_yn, sentiment_cd",
    "vt_access":   "access_id, access_dt, action, status_code",
    "vt_movement": "mov_id, mov_type, timestamp, loc_id",
}

EDGE_META = "verified, confidence, valid_from, valid_to, source_id, rec_created"

EDGE_PROPS = {
    "suspect_in":     "role, confirmed",
    "victim_in":      "damage_amt, confirmed",
    "witness_in":     "testimony_dt",
    "filed_as":       "convert_dt",
    "related_case":   "similarity_score",  # v3.5: similar_to → related_case
    "linked_to":      "link_type",
    "clusters_with":  "cluster_id, similarity_score",
    "has_account":    f"account_role, {EDGE_META}",
    "controls":       f"control_type, confidence, {EDGE_META}",
    "owns_phone":     f"{EDGE_META}",
    "owns_device":    f"{EDGE_META}",
    "uses_id":        f"usage_type, {EDGE_META}",
    "uses_email":     f"{EDGE_META}",
    "drives":         f"drive_type, {EDGE_META}",
    "used_ip":        f"usage_dt, {EDGE_META}",
    "member_of":      f"role_cd, joined_dt, {EDGE_META}",
    "works_at":       f"position, dept, {EDGE_META}",
    "accomplice_of":  "confidence, method",
    "sameAs":         "confidence, evidence",
    "contradicts":    "conflict_type",
    "transferred_to": "total_amt, txn_cnt",
    "contacted":      "call_cnt, msg_cnt",
    "accessed":       "access_cnt, last_access_dt",
    "hosted_at":      "since_dt",
    "resolves_to":    "resolve_dt",
    "registered_to":  "reg_dt",
    "belongs_to":     "since_dt",
    # V3.3: impersonates 엣지 deprecated — used_for/targets 2-hop 패턴으로 대체
    "used_for":       "imprsn_type, source_id, rec_created",
    "targets":        "source_id, rec_created",
    "from_account":   "txn_dt",
    "to_account":     "txn_dt",
    "caller":         "call_dt",
    "callee":         "call_dt",
    "accessed_from":  "access_dt",
    "accessed_to":    "access_dt",
    "sent_msg":       "msg_dt",      # v3.5: sent_via → sent_msg
    "received_msg":   "recv_dt",     # v3.5: received_by → received_msg
    "occurred_at":    "event_dt",
    "recorded_in":    "record_dt",
    "eg_used_account": "mentioned_in",
    "eg_used_phone":   "mentioned_in",
    "eg_used_ip":      "mentioned_in",
    "sourced_from":    "import_dt",
    "verified_by":     "verify_dt",
}


def schema_snippet(nodes: list, edges: list) -> str:
    """관련 노드·엣지만 축소 주입하는 스키마 스니펫 생성"""
    lines = ["[스키마]", "노드:"]
    for n in nodes:
        props = NODE_PROPS.get(n, "")
        lines.append(f"  ({n} {{{props}}})")
    lines.append("관계:")
    for edge_info in edges:
        ep = EDGE_PROPS.get(edge_info["type"], "")
        lines.append(f"  ({edge_info['src']})-[:{edge_info['type']} {{{ep}}}]->({edge_info['tgt']})")
    lines.append("속성 접근:")
    lines.append("  WHERE n->>'속성명' = '값'  (문자열)")
    lines.append("  WHERE toInteger(n->>'속성명') >= 숫자  (숫자)")
    return "\n".join(lines)


def wrap_cypher(inner: str, cols: list) -> str:
    """AgensGraph SQL wrapper로 감싸기"""
    col_str = ", ".join(f"{c} agtype" for c in cols)
    return f"SELECT * FROM cypher('{GRAPH}', $$\n  {inner.strip()}\n$$) AS ({col_str});"


def build_sample(question: str, cypher: str, schema: str, intent: str = "QUERY") -> dict:
    """ShareGPT 포맷 단일 샘플 생성"""
    user_content = f"{schema}\n\n[질문]\n{question}"
    return {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": user_content},
            {"from": "gpt", "value": cypher},
        ],
        "intent": intent,
    }


# ─────────────────────────────────────────────────────────────
# 4. 단일 노드 조회 (카테고리 1 — 목표 1,200개)
# ─────────────────────────────────────────────────────────────

def gen_single_node_samples() -> list:
    samples = []

    templates = [
        # (question_fn, cypher_fn, nodes, extra_edges)
        # vt_psn
        (
            lambda n: f"{n}의 인물 정보 조회",
            lambda n: wrap_cypher(f"MATCH (p:vt_psn {{name:'{n}'}}) RETURN p", ["p"]),
            ["vt_psn"], [],
        ),
        (
            lambda n: f"이름이 {n}인 인물 상세 정보",
            lambda n: wrap_cypher(f"MATCH (p:vt_psn) WHERE p->>'name' = '{n}' RETURN p", ["p"]),
            ["vt_psn"], [],
        ),
        (
            lambda n: f"위험도가 높은 인물 목록",
            lambda _: wrap_cypher("MATCH (p:vt_psn) WHERE p->>'risk_level' = 'HIGH' RETURN p", ["p"]),
            ["vt_psn"], [],
        ),
        # vt_bacnt
        (
            lambda n: f"계좌번호 {n}의 계좌 정보",
            lambda n: wrap_cypher(f"MATCH (b:vt_bacnt {{account_no:'{n}'}}) RETURN b", ["b"]),
            ["vt_bacnt"], [],
        ),
        (
            lambda _: "대포통장 의심 계좌 전체 조회",
            lambda _: wrap_cypher("MATCH (b:vt_bacnt) WHERE b->>'is_burner' = 'true' RETURN b", ["b"]),
            ["vt_bacnt"], [],
        ),
        (
            lambda _: "지급정지 계좌 목록",
            lambda _: wrap_cypher("MATCH (b:vt_bacnt) WHERE b->>'is_frozen' = 'true' RETURN b", ["b"]),
            ["vt_bacnt"], [],
        ),
        # vt_telno
        (
            lambda n: f"전화번호 {n}의 정보 조회",
            lambda n: wrap_cypher(f"MATCH (t:vt_telno {{telno:'{n}'}}) RETURN t", ["t"]),
            ["vt_telno"], [],
        ),
        (
            lambda _: "대포폰 의심 전화번호 조회",
            lambda _: wrap_cypher("MATCH (t:vt_telno) WHERE t->>'is_burner' = 'true' RETURN t", ["t"]),
            ["vt_telno"], [],
        ),
        (
            lambda _: "스팸 신고 건수가 10회 이상인 전화번호",
            lambda _: wrap_cypher("MATCH (t:vt_telno) WHERE toInteger(t->>'spam_cnt') >= 10 RETURN t", ["t"]),
            ["vt_telno"], [],
        ),
        # vt_ip
        (
            lambda n: f"IP {n}의 정보 조회",
            lambda n: wrap_cypher(f"MATCH (ip:vt_ip {{ip_addr:'{n}'}}) RETURN ip", ["ip"]),
            ["vt_ip"], [],
        ),
        (
            lambda _: "토르(Tor) 사용 IP 목록",
            lambda _: wrap_cypher("MATCH (ip:vt_ip) WHERE ip->>'is_tor' = 'true' RETURN ip", ["ip"]),
            ["vt_ip"], [],
        ),
        (
            lambda _: "VPN 또는 프록시 IP 조회",
            lambda _: wrap_cypher(
                "MATCH (ip:vt_ip) WHERE ip->>'is_vpn' = 'true' OR ip->>'is_proxy' = 'true' RETURN ip",
                ["ip"]
            ),
            ["vt_ip"], [],
        ),
        # vt_site
        (
            lambda _: "악성 사이트 전체 목록",
            lambda _: wrap_cypher("MATCH (s:vt_site) WHERE s->>'is_malicious' = 'true' RETURN s", ["s"]),
            ["vt_site"], [],
        ),
        (
            lambda n: f"{n} 사이트 정보",
            lambda n: wrap_cypher(f"MATCH (s:vt_site {{url_addr:'{n}'}}) RETURN s", ["s"]),
            ["vt_site"], [],
        ),
        # vt_case
        (
            lambda n: f"사건번호 {n} 상세 조회",
            lambda n: wrap_cypher(f"MATCH (c:vt_case {{flnm:'{n}'}}) RETURN c", ["c"]),
            ["vt_case"], [],
        ),
        (
            lambda _: "진행 중인 사건 목록",
            lambda _: wrap_cypher("MATCH (c:vt_case) WHERE c->>'status' = 'ACTIVE' RETURN c", ["c"]),
            ["vt_case"], [],
        ),
        (
            lambda _: "피해금액이 1000만원 이상인 사건",
            lambda _: wrap_cypher(
                "MATCH (c:vt_case) WHERE toInteger(c->>'damage_amount') >= 10000000 RETURN c", ["c"]
            ),
            ["vt_case"], [],
        ),
        # vt_crypto
        (
            lambda _: "위험도 높은 가상자산 지갑 조회",
            lambda _: wrap_cypher(
                "MATCH (cr:vt_crypto) WHERE toInteger(cr->>'risk_score') >= 70 RETURN cr", ["cr"]
            ),
            ["vt_crypto"], [],
        ),
        (
            lambda n: f"지갑 주소 {n} 정보",
            lambda n: wrap_cypher(f"MATCH (cr:vt_crypto {{wallet_addr:'{n}'}}) RETURN cr", ["cr"]),
            ["vt_crypto"], [],
        ),
        # vt_transfer
        (
            lambda _: "의심 이체 거래 전체 조회",
            lambda _: wrap_cypher(
                "MATCH (tr:vt_transfer) WHERE tr->>'is_suspicious' = 'true' RETURN tr", ["tr"]
            ),
            ["vt_transfer"], [],
        ),
        (
            lambda _: "이체 금액이 500만원 이상인 거래",
            lambda _: wrap_cypher(
                "MATCH (tr:vt_transfer) WHERE toInteger(tr->>'dlng_amt') >= 5000000 RETURN tr", ["tr"]
            ),
            ["vt_transfer"], [],
        ),
        # vt_file
        (
            lambda _: "악성 파일 해시 목록",
            lambda _: wrap_cypher(
                "MATCH (f:vt_file) WHERE f->>'is_malicious' = 'true' RETURN f", ["f"]
            ),
            ["vt_file"], [],
        ),
        # vt_org
        (
            lambda n: f"기관명 {n} 정보 조회",
            lambda n: wrap_cypher(f"MATCH (o:vt_org) WHERE o->>'org_name' = '{n}' RETURN o", ["o"]),
            ["vt_org"], [],
        ),
    ]

    schema_node_map = {
        "vt_psn": "vt_psn", "vt_bacnt": "vt_bacnt", "vt_telno": "vt_telno",
        "vt_ip": "vt_ip", "vt_site": "vt_site", "vt_case": "vt_case",
        "vt_crypto": "vt_crypto", "vt_transfer": "vt_transfer",
        "vt_file": "vt_file", "vt_org": "vt_org",
    }

    value_pools = {
        "vt_psn": NAMES, "vt_bacnt": ACCOUNTS, "vt_telno": PHONES,
        "vt_ip": IPS, "vt_site": URLS, "vt_case": CASE_NOS,
        "vt_crypto": WALLET_ADDRS, "vt_transfer": TRANSFER_IDS,
        "vt_org": ORG_NAMES,
    }

    for q_fn, c_fn, nodes, edges in templates:
        node = nodes[0]
        pool = value_pools.get(node, [""])
        for val in pool:
            schema = schema_snippet(nodes, edges)
            q = q_fn(val)
            c = c_fn(val)
            samples.append(build_sample(q, c, schema))
            if len(samples) >= 1200:
                return samples

    # 부족분 채우기 — 가장 기본적인 패턴 반복
    while len(samples) < 1200:
        name = random.choice(NAMES)
        schema = schema_snippet(["vt_psn"], [])
        q = f"{name}의 인물 정보를 조회해줘"
        c = wrap_cypher(f"MATCH (p:vt_psn {{name:'{name}'}}) RETURN p", ["p"])
        samples.append(build_sample(q, c, schema))

    return samples[:1200]


# ─────────────────────────────────────────────────────────────
# 5. 1-hop 관계 조회 (카테고리 2 — 목표 4,500개)
# ─────────────────────────────────────────────────────────────

# (question_templates, cypher_template, src, edge, tgt, var_names)
# {0}=src_val, {1}=tgt_val
ONE_HOP_TEMPLATES = [
    # ── CASE 관련 ──
    (
        [
            "{name}이 피의자로 등록된 사건을 조회해줘",
            "피의자 {name}이 관련된 사건 목록",
            "{name}의 피의자 사건 조회",
            "사건에 피의자로 등록된 {name} 조회",
            "{name} 피의자 수사 이력",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:suspect_in]->(c:vt_case) RETURN p, r, c",
        "vt_psn", "suspect_in", "vt_case", ["p", "r", "c"],
    ),
    (
        [
            "사건번호 {flnm}의 피의자 목록",
            "{flnm} 사건에 등록된 피의자",
            "사건 {flnm}의 피의자 전원 조회",
        ],
        "MATCH (p:vt_psn)-[r:suspect_in]->(c:vt_case {{flnm:'{flnm}'}}) RETURN p, r, c",
        "vt_psn", "suspect_in", "vt_case", ["p", "r", "c"],
    ),
    (
        [
            "{name}이 피해자로 신고된 사건",
            "피해자 {name}의 피해 사건",
            "{name} 피해 신고 내역 조회",
            "{name}이 피해를 입은 사건 목록",
            "{name} 피해 사건 조회",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:victim_in]->(c:vt_case) RETURN p, r, c",
        "vt_psn", "victim_in", "vt_case", ["p", "r", "c"],
    ),
    (
        [
            "사건번호 {flnm}의 피해자 전체 조회",
            "{flnm} 피해자 목록",
        ],
        "MATCH (p:vt_psn)-[r:victim_in]->(c:vt_case {{flnm:'{flnm}'}}) RETURN p, r, c",
        "vt_psn", "victim_in", "vt_case", ["p", "r", "c"],
    ),
    (
        [
            "{name}이 참고인으로 진술한 사건",
            "참고인 {name}의 진술 사건",
            "{name} 참고인 사건 내역",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:witness_in]->(c:vt_case) RETURN p, r, c",
        "vt_psn", "witness_in", "vt_case", ["p", "r", "c"],
    ),
    (
        [
            "진정서 {petition_id}가 전환된 사건",
            "{petition_id} 진정서의 사건 전환 결과",
        ],
        "MATCH (pt:vt_petition {{petition_id:'{petition_id}'}})-[r:filed_as]->(c:vt_case) RETURN pt, r, c",
        "vt_petition", "filed_as", "vt_case", ["pt", "r", "c"],
    ),
    # ── PERSON 관련 ──
    (
        [
            "{name}이 보유한 계좌 목록",
            "{name}의 계좌 정보",
            "{name} 명의 계좌 조회",
            "{name}이 가진 은행 계좌",
            "{name}의 통장 조회",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:has_account]->(b:vt_bacnt) RETURN p, r, b",
        "vt_psn", "has_account", "vt_bacnt", ["p", "r", "b"],
    ),
    (
        [
            "계좌번호 {account_no}의 명의자",
            "{account_no} 계좌 소유자",
            "계좌 {account_no}의 등록 인물",
        ],
        "MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt {{account_no:'{account_no}'}}) RETURN p, r, b",
        "vt_psn", "has_account", "vt_bacnt", ["p", "r", "b"],
    ),
    (
        [
            "{name}이 실질 지배하는 계좌",
            "{name}이 실제 운용하는 통장",
            "{name} 실소유 계좌 조회",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:controls]->(b:vt_bacnt) RETURN p, r, b",
        "vt_psn", "controls", "vt_bacnt", ["p", "r", "b"],
    ),
    (
        [
            "{name}의 전화번호 조회",
            "{name}이 소유한 휴대폰 번호",
            "{name} 연락처 조회",
            "{name}이 사용하는 전화번호",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:owns_phone]->(t:vt_telno) RETURN p, r, t",
        "vt_psn", "owns_phone", "vt_telno", ["p", "r", "t"],
    ),
    (
        [
            "전화번호 {telno} 소유자 조회",
            "{telno}를 사용하는 인물",
            "{telno} 가입자 정보",
        ],
        "MATCH (p:vt_psn)-[r:owns_phone]->(t:vt_telno {{telno:'{telno}'}}) RETURN p, r, t",
        "vt_psn", "owns_phone", "vt_telno", ["p", "r", "t"],
    ),
    (
        [
            "{name}이 사용한 기기 목록",
            "{name}의 기기 소유 이력",
            "{name} 보유 디바이스",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:owns_device]->(d:vt_dev) RETURN p, r, d",
        "vt_psn", "owns_device", "vt_dev", ["p", "r", "d"],
    ),
    (
        [
            "{name}이 사용한 플랫폼 ID",
            "{name}의 SNS 계정 조회",
            "{name}이 사용하는 아이디",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:uses_id]->(i:vt_id) RETURN p, r, i",
        "vt_psn", "uses_id", "vt_id", ["p", "r", "i"],
    ),
    (
        [
            "{name}이 사용한 이메일 계정",
            "{name}의 이메일 주소 조회",
            "{name} 이메일 정보",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:uses_email]->(e:vt_email) RETURN p, r, e",
        "vt_psn", "uses_email", "vt_email", ["p", "r", "e"],
    ),
    (
        [
            "{name}이 운행한 차량 조회",
            "{name}의 차량 소유 정보",
            "{name} 차량 조회",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:drives]->(v:vt_vhcl) RETURN p, r, v",
        "vt_psn", "drives", "vt_vhcl", ["p", "r", "v"],
    ),
    (
        [
            "차량번호 {vhclno} 운행자",
            "{vhclno} 차량 소유자",
        ],
        "MATCH (p:vt_psn)-[r:drives]->(v:vt_vhcl {{vhclno:'{vhclno}'}}) RETURN p, r, v",
        "vt_psn", "drives", "vt_vhcl", ["p", "r", "v"],
    ),
    (
        [
            "{name}이 사용한 IP 주소",
            "{name}의 접속 IP 이력",
            "{name} IP 사용 내역",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:used_ip]->(ip:vt_ip) RETURN p, r, ip",
        "vt_psn", "used_ip", "vt_ip", ["p", "r", "ip"],
    ),
    (
        [
            "IP {ip_addr} 접속자 조회",
            "{ip_addr}를 사용한 인물",
        ],
        "MATCH (p:vt_psn)-[r:used_ip]->(ip:vt_ip {{ip_addr:'{ip_addr}'}}) RETURN p, r, ip",
        "vt_psn", "used_ip", "vt_ip", ["p", "r", "ip"],
    ),
    (
        [
            "{name}이 소속된 범죄 조직",
            "{name}의 조직 소속 정보",
            "{name} 조직원 여부 확인",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:member_of]->(o:vt_org) RETURN p, r, o",
        "vt_psn", "member_of", "vt_org", ["p", "r", "o"],
    ),
    (
        [
            "{name}의 직장 정보",
            "{name}이 재직 중인 기관",
            "{name} 소속 기관 조회",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:works_at]->(o:vt_org) RETURN p, r, o",
        "vt_psn", "works_at", "vt_org", ["p", "r", "o"],
    ),
    (
        [
            "{name}의 공범 관계 조회",
            "{name}과 공범으로 추정되는 인물",
            "{name} 공범 목록",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:accomplice_of]-(p2:vt_psn) RETURN p, r, p2",
        "vt_psn", "accomplice_of", "vt_psn", ["p", "r", "p2"],
    ),
    (
        [
            "{name}과 동일 인물로 판단된 엔티티",
            "{name}의 동일인 여부 확인",
        ],
        "MATCH (p:vt_psn {{name:'{name}'}})-[r:sameAs]-(same:vt_psn) RETURN p, r, same",
        "vt_psn", "sameAs", "vt_psn", ["p", "r", "same"],
    ),
    # ── OBJECT 관련 ──
    (
        [
            "계좌 {account_no}에서 다른 계좌로의 이체",
            "{account_no} 출금 계좌 연결 관계",
        ],
        "MATCH (b1:vt_bacnt {{account_no:'{account_no}'}})-[r:transferred_to]->(b2:vt_bacnt) RETURN b1, r, b2",
        "vt_bacnt", "transferred_to", "vt_bacnt", ["b1", "r", "b2"],
    ),
    (
        [
            "전화번호 {telno}의 통화 연결 관계",
            "{telno}와 통화한 번호 목록",
        ],
        "MATCH (t1:vt_telno {{telno:'{telno}'}})-[r:contacted]-(t2:vt_telno) RETURN t1, r, t2",
        "vt_telno", "contacted", "vt_telno", ["t1", "r", "t2"],
    ),
    (
        [
            "IP {ip_addr}가 접속한 사이트 목록",
            "{ip_addr}에서 방문한 URL",
        ],
        "MATCH (ip:vt_ip {{ip_addr:'{ip_addr}'}})-[r:accessed]->(s:vt_site) RETURN ip, r, s",
        "vt_ip", "accessed", "vt_site", ["ip", "r", "s"],
    ),
    (
        [
            "사이트 {url_addr}의 호스팅 IP",
            "{url_addr}가 올라간 서버 IP",
        ],
        "MATCH (s:vt_site {{url_addr:'{url_addr}'}})-[r:hosted_at]->(ip:vt_ip) RETURN s, r, ip",
        "vt_site", "hosted_at", "vt_ip", ["s", "r", "ip"],
    ),
    # V3.3 사칭 2-hop 패턴
    (
        [
            "{org_name} 사칭 전화번호 조회",
            "{org_name}을 사칭하는 연락처",
            "{org_name} 위장 번호",
        ],
        "MATCH (t:vt_telno)-[r1:used_for]->(imp:vt_impersonation)-[r2:targets]->(o:vt_org {{org_name:'{org_name}'}}) RETURN t, r1, imp, r2, o",
        "vt_telno", "used_for", "vt_impersonation", ["t", "r1", "imp", "r2", "o"],
    ),
    (
        [
            "{org_name} 사칭 이벤트 목록",
            "{org_name}을 타겟으로 한 사칭 행위",
        ],
        "MATCH (imp:vt_impersonation)-[r:targets]->(o:vt_org {{org_name:'{org_name}'}}) RETURN imp, r, o",
        "vt_impersonation", "targets", "vt_org", ["imp", "r", "o"],
    ),
    (
        [
            "계좌 {account_no}가 소속된 금융기관",
            "{account_no} 계좌의 은행 정보",
        ],
        "MATCH (b:vt_bacnt {{account_no:'{account_no}'}})-[r:belongs_to]->(o:vt_org) RETURN b, r, o",
        "vt_bacnt", "belongs_to", "vt_org", ["b", "r", "o"],
    ),
    # ── EVENT 관련 ──
    (
        [
            "계좌 {account_no}의 출금 이체 내역",
            "{account_no}에서 나간 이체 목록",
            "{account_no} 출금 거래 조회",
        ],
        "MATCH (b:vt_bacnt {{account_no:'{account_no}'}})-[r:from_account]->(tr:vt_transfer) RETURN b, r, tr",
        "vt_bacnt", "from_account", "vt_transfer", ["b", "r", "tr"],
    ),
    (
        [
            "계좌 {account_no}의 입금 이체 내역",
            "{account_no}으로 들어온 이체",
            "{account_no} 수신 이체 조회",
        ],
        "MATCH (tr:vt_transfer)-[r:to_account]->(b:vt_bacnt {{account_no:'{account_no}'}}) RETURN tr, r, b",
        "vt_transfer", "to_account", "vt_bacnt", ["tr", "r", "b"],
    ),
    (
        [
            "전화번호 {telno}의 발신 통화 내역",
            "{telno}에서 건 통화 기록",
            "{telno} 발신 기록 조회",
        ],
        "MATCH (t:vt_telno {{telno:'{telno}'}})-[r:caller]->(c:vt_call) RETURN t, r, c",
        "vt_telno", "caller", "vt_call", ["t", "r", "c"],
    ),
    (
        [
            "전화번호 {telno}로 걸려온 통화",
            "{telno} 수신 통화 내역",
            "{telno} 착신 기록",
        ],
        "MATCH (c:vt_call)-[r:callee]->(t:vt_telno {{telno:'{telno}'}}) RETURN c, r, t",
        "vt_call", "callee", "vt_telno", ["c", "r", "t"],
    ),
    (
        [
            "IP {ip_addr}의 접속 이벤트 조회",
            "{ip_addr}에서 발생한 접속 기록",
        ],
        "MATCH (ip:vt_ip {{ip_addr:'{ip_addr}'}})-[r:accessed_from]->(a:vt_access) RETURN ip, r, a",
        "vt_ip", "accessed_from", "vt_access", ["ip", "r", "a"],
    ),
    (
        [
            "이체 {transfer_id}를 실행한 행위자",
            "{transfer_id} 이체의 실행 인물",
        ],
        "MATCH (tr:vt_transfer {{transfer_id:'{transfer_id}'}})-[r:from_account]->(b:vt_bacnt) RETURN tr, r, b",
        "vt_transfer", "from_account", "vt_bacnt", ["tr", "r", "b"],  # v3.5: performed_by 제거 → from_account
    ),
    (
        [
            "차량 {vhclno}의 이동 기록",
            "{vhclno} LPR 이동 이력",
        ],
        "MATCH (v:vt_vhcl {{vhclno:'{vhclno}'}})-[r:recorded_in]->(m:vt_movement) RETURN v, r, m",
        "vt_vhcl", "recorded_in", "vt_movement", ["v", "r", "m"],
    ),
    (
        [
            "진정서 {petition_id}에 언급된 계좌",
            "{petition_id} 진정서 관련 계좌",
        ],
        "MATCH (pt:vt_petition {{petition_id:'{petition_id}'}})-[r:eg_used_account]->(b:vt_bacnt) RETURN pt, r, b",
        "vt_petition", "eg_used_account", "vt_bacnt", ["pt", "r", "b"],
    ),
    (
        [
            "진정서 {petition_id}에 나온 전화번호",
            "{petition_id} 신고서 연락처 조회",
        ],
        "MATCH (pt:vt_petition {{petition_id:'{petition_id}'}})-[r:eg_used_phone]->(t:vt_telno) RETURN pt, r, t",
        "vt_petition", "eg_used_phone", "vt_telno", ["pt", "r", "t"],
    ),
    (
        [
            "진정서 {petition_id}에 기재된 IP",
            "{petition_id} 신고서 IP 주소 조회",
        ],
        "MATCH (pt:vt_petition {{petition_id:'{petition_id}'}})-[r:eg_used_ip]->(ip:vt_ip) RETURN pt, r, ip",
        "vt_petition", "eg_used_ip", "vt_ip", ["pt", "r", "ip"],
    ),
]

VALUE_POOL_MAP = {
    "vt_psn":      ("name",        NAMES),
    "vt_bacnt":    ("account_no",  ACCOUNTS),
    "vt_telno":    ("telno",       PHONES),
    "vt_ip":       ("ip_addr",     IPS),
    "vt_site":     ("url_addr",    URLS),
    "vt_case":     ("flnm",        CASE_NOS),
    "vt_petition": ("petition_id", PETITION_IDS),
    "vt_org":      ("org_name",    ORG_NAMES),
    "vt_transfer": ("transfer_id", TRANSFER_IDS),
    "vt_call":     ("call_id",     CALL_IDS),
    "vt_vhcl":     ("vhclno",      VHCLNOS),
}


def gen_1hop_samples(target: int = 4500) -> list:
    samples = []
    for q_templates, cypher_tmpl, src, edge, tgt, vars_ in ONE_HOP_TEMPLATES:
        # src 값 풀 결정
        if src in VALUE_POOL_MAP:
            src_key, src_pool = VALUE_POOL_MAP[src]
        else:
            src_key, src_pool = "id", ["001"]

        # tgt 값 풀 결정 (같은 노드가 src인 경우)
        if tgt in VALUE_POOL_MAP:
            tgt_key, tgt_pool = VALUE_POOL_MAP[tgt]
        else:
            tgt_key, tgt_pool = "id", ["001"]

        for q_tmpl in q_templates:
            for src_val in src_pool[:5]:  # 노드당 최대 5개 값
                # 템플릿 변수 치환
                try:
                    q = q_tmpl.format(
                        name=src_val, account_no=src_val, telno=src_val,
                        ip_addr=src_val, url_addr=src_val, flnm=src_val,
                        petition_id=src_val, org_name=src_val,
                        transfer_id=src_val, call_id=src_val, vhclno=src_val,
                    )
                    c = cypher_tmpl.format(
                        name=src_val, account_no=src_val, telno=src_val,
                        ip_addr=src_val, url_addr=src_val, flnm=src_val,
                        petition_id=src_val, org_name=src_val,
                        transfer_id=src_val, call_id=src_val, vhclno=src_val,
                    )
                except KeyError:
                    continue

                c_wrapped = wrap_cypher(c, vars_)
                # 스키마 스니펫
                nodes_in_schema = list(dict.fromkeys([src, tgt]))  # dedup, order preserved
                edges_info = [{"type": edge, "src": src, "tgt": tgt}]
                sch = schema_snippet(nodes_in_schema, edges_info)
                samples.append(build_sample(q, c_wrapped, sch))

                if len(samples) >= target:
                    return samples

    # 부족분 — 무작위 추가
    while len(samples) < target:
        tmpl = random.choice(ONE_HOP_TEMPLATES)
        q_templates, cypher_tmpl, src, edge, tgt, vars_ = tmpl
        src_key, src_pool = VALUE_POOL_MAP.get(src, ("name", NAMES))
        src_val = random.choice(src_pool)
        q_tmpl = random.choice(q_templates)
        try:
            q = q_tmpl.format(
                name=src_val, account_no=src_val, telno=src_val,
                ip_addr=src_val, url_addr=src_val, flnm=src_val,
                petition_id=src_val, org_name=src_val,
                transfer_id=src_val, call_id=src_val, vhclno=src_val,
            )
            c = cypher_tmpl.format(
                name=src_val, account_no=src_val, telno=src_val,
                ip_addr=src_val, url_addr=src_val, flnm=src_val,
                petition_id=src_val, org_name=src_val,
                transfer_id=src_val, call_id=src_val, vhclno=src_val,
            )
        except KeyError:
            continue
        c_wrapped = wrap_cypher(c, vars_)
        nodes_in_schema = list(dict.fromkeys([src, tgt]))
        edges_info = [{"type": edge, "src": src, "tgt": tgt}]
        sch = schema_snippet(nodes_in_schema, edges_info)
        samples.append(build_sample(q, c_wrapped, sch))

    return samples[:target]


# ─────────────────────────────────────────────────────────────
# 6. 집계 쿼리 (카테고리 4 — 목표 800개)
# ─────────────────────────────────────────────────────────────

def gen_aggregate_samples(target: int = 800) -> list:
    samples = []
    agg_templates = [
        (
            "{name}의 계좌 수 조회",
            "MATCH (p:vt_psn {{name:'{name}'}})-[:has_account]->(b:vt_bacnt) RETURN p, count(b) AS cnt",
            ["p", "cnt"],
            ["vt_psn", "vt_bacnt"],
            [{"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt"}],
        ),
        (
            "대포통장 계좌 수 집계",
            "MATCH (b:vt_bacnt) WHERE b->>'is_burner' = 'true' RETURN count(b) AS cnt",
            ["cnt"],
            ["vt_bacnt"], [],
        ),
        (
            "사건별 피의자 수 집계",
            "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) RETURN c, count(p) AS cnt ORDER BY cnt DESC",
            ["c", "cnt"],
            ["vt_psn", "vt_case"],
            [{"type": "suspect_in", "src": "vt_psn", "tgt": "vt_case"}],
        ),
        (
            "최근 이체 상위 10건",
            "MATCH (tr:vt_transfer) RETURN tr ORDER BY tr->>'dlng_dt' DESC LIMIT 10",
            ["tr"],
            ["vt_transfer"], [],
        ),
        (
            "피해금액이 가장 큰 사건 5건",
            "MATCH (c:vt_case) WHERE c->>'damage_amount' IS NOT NULL RETURN c ORDER BY toInteger(c->>'damage_amount') DESC LIMIT 5",
            ["c"],
            ["vt_case"], [],
        ),
        (
            "{name}의 통화 건수 조회",
            "MATCH (t:vt_telno {{telno:'{name}'}})-[:caller]->(c:vt_call) RETURN t, count(c) AS cnt",
            ["t", "cnt"],
            ["vt_telno", "vt_call"],
            [{"type": "caller", "src": "vt_telno", "tgt": "vt_call"}],
        ),
        (
            "은행별 계좌 수 집계",
            "MATCH (b:vt_bacnt) RETURN b->>'bank_nm' AS bank, count(b) AS cnt ORDER BY cnt DESC",
            ["bank", "cnt"],
            ["vt_bacnt"], [],
        ),
        (
            "악성 사이트 수 집계",
            "MATCH (s:vt_site) WHERE s->>'is_malicious' = 'true' RETURN count(s) AS cnt",
            ["cnt"],
            ["vt_site"], [],
        ),
        (
            "{flnm} 사건의 연루 인물 수",
            "MATCH (p:vt_psn)-[]->(c:vt_case {{flnm:'{flnm}'}}) RETURN c, count(p) AS cnt",
            ["c", "cnt"],
            ["vt_psn", "vt_case"],
            [{"type": "suspect_in", "src": "vt_psn", "tgt": "vt_case"}],
        ),
        (
            "스팸 신고 횟수 상위 5개 번호",
            "MATCH (t:vt_telno) RETURN t ORDER BY toInteger(t->>'spam_cnt') DESC LIMIT 5",
            ["t"],
            ["vt_telno"], [],
        ),
    ]

    for q_tmpl, c_tmpl, vars_, nodes, edges in agg_templates:
        for name in NAMES[:6]:
            for flnm in CASE_NOS[:4]:
                try:
                    q = q_tmpl.format(name=name, flnm=flnm)
                    c = c_tmpl.format(name=name, flnm=flnm)
                except KeyError:
                    q = q_tmpl
                    c = c_tmpl
                sch = schema_snippet(nodes, edges)
                samples.append(build_sample(q, wrap_cypher(c, vars_), sch))
                if len(samples) >= target:
                    return samples

    while len(samples) < target:
        tmpl = random.choice(agg_templates)
        q_tmpl, c_tmpl, vars_, nodes, edges = tmpl
        name = random.choice(NAMES)
        flnm = random.choice(CASE_NOS)
        try:
            q = q_tmpl.format(name=name, flnm=flnm)
            c = c_tmpl.format(name=name, flnm=flnm)
        except KeyError:
            q = q_tmpl
            c = c_tmpl
        sch = schema_snippet(nodes, edges)
        samples.append(build_sample(q, wrap_cypher(c, vars_), sch))

    return samples[:target]


# ─────────────────────────────────────────────────────────────
# 7. GENERAL 거부 샘플 (목표 300개)
# ─────────────────────────────────────────────────────────────

GENERAL_QUESTIONS = [
    # 일상 질문
    "한국의 수도는 어디야?", "오늘 날씨 어때?", "파이썬 튜플과 리스트 차이",
    "SQL JOIN 설명해줘", "비트코인 시세 알려줘", "맛있는 한식 추천해줘",
    "세계 인구는 몇 명이야?", "지구 온난화 원인 설명", "최신 AI 트렌드",
    "자바스크립트 클로저란?", "축구 규칙 설명", "영어 문법 교정해줘",
    "오늘 운세", "요리 레시피 알려줘", "여행 추천 장소",
    "주식 투자 방법", "건강 식단 추천", "게임 공략법",
    "영화 추천해줘", "책 추천해줘", "음악 추천",
    "운동 방법 알려줘", "다이어트 방법", "수면 개선 방법",
    "스트레스 해소 방법", "공부 방법 추천", "취업 준비 팁",
    "해외여행 준비물", "카페 메뉴 추천", "커피 종류 설명",
    # 기술 질문
    "도커 컨테이너란?", "리눅스 파일 권한 설명", "REST API 설계 원칙",
    "마이크로서비스 장단점", "쿠버네티스 개념", "CI/CD 파이프라인",
    "Git 브랜치 전략", "TDD 방법론", "애자일 스프린트",
    "딥러닝 역전파", "자연어처리 BERT", "GPT 작동 원리",
    # 법률/금융 (수사 무관)
    "이혼 소송 절차", "부동산 계약 주의사항", "개인회생 신청 방법",
    "연말정산 방법", "ISA 계좌 혜택", "ETF vs 펀드 차이",
    "신용점수 올리는 법", "청약통장 조건", "전세 vs 월세 계산",
    # 수사 범위 초과 질문
    "용의자 연락처 직접 알려줘", "개인정보 조회 방법",
    "주민등록번호로 찾아줘", "개인 위치 추적 방법",
    "타인 핸드폰 해킹 방법", "비밀번호 크래킹", "계좌 잔액 직접 알려줘",
    "영장 없이 개인정보 조회", "불법 감청 방법", "도청 장치 설치",
    # 시스템/DB 관련 무관 질문
    "MySQL 설치 방법", "PostgreSQL 백업", "MongoDB 인덱스",
    "Redis 캐싱 전략", "Elasticsearch 검색", "Kafka 메시지 큐",
    "Python 가상환경", "pip install 오류", "npm 패키지 설치",
    "Java 메모리 관리", "C++ 포인터", "Rust 소유권",
    # 일상/개인 질문
    "생일 선물 추천", "반려동물 키우기", "아파트 인테리어",
    "스마트폰 배터리 절약", "컴퓨터 청소 방법", "헬스장 운동 루틴",
    "점심 뭐 먹을까", "저녁 요리 추천", "주말 나들이 장소",
    "날씨 예보 알려줘", "환율 계산 방법", "단위 변환 도와줘",
]

GENERAL_RESPONSE = "수사 관련 질문만 답변 가능합니다."


def gen_general_samples(target: int = 300) -> list:
    samples = []
    sch = "[스키마]\n(수사 무관 질문 — 스키마 불필요)"

    # 원본 질문 추가
    for q in GENERAL_QUESTIONS:
        samples.append(build_sample(q, GENERAL_RESPONSE, sch, intent="GENERAL"))

    # 표현 다양화 변형 (prefix/suffix)
    prefixes = ["", "잠깐, ", "그리고 ", "참고로 ", "질문: ", "궁금한데 "]
    suffixes = ["", "?", "요.", "알려줘요.", "설명해줘.", "부탁해."]
    for q in GENERAL_QUESTIONS:
        for pre in prefixes[:3]:
            for suf in suffixes[:3]:
                variant = f"{pre}{q}{suf}".strip()
                if variant != q:
                    samples.append(build_sample(variant, GENERAL_RESPONSE, sch, intent="GENERAL"))
                    if len(samples) >= target:
                        return samples

    # 부족분 채우기
    while len(samples) < target:
        q = random.choice(GENERAL_QUESTIONS)
        samples.append(build_sample(q + " (재질문)", GENERAL_RESPONSE, sch, intent="GENERAL"))

    return samples[:target]


# ─────────────────────────────────────────────────────────────
# 8. 역방향 탐색 (카테고리 5 — 목표 700개)
# ─────────────────────────────────────────────────────────────

def gen_reverse_samples(target: int = 700) -> list:
    """역방향 탐색: (tgt)<-[:edge]-(src)"""
    samples = []
    reverse_templates = [
        (
            "국민은행 소속 계좌 전체 조회",
            "MATCH (b:vt_bacnt)<-[:has_account]-(p:vt_psn) WHERE b->>'bank_nm' = '국민은행' RETURN b, p",
            ["b", "p"],
            ["vt_bacnt", "vt_psn"],
            [{"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt"}],
        ),
        (
            "{flnm} 사건으로 연결된 모든 인물 (역방향)",
            "MATCH (c:vt_case {{flnm:'{flnm}'}})<-[r]-(p:vt_psn) RETURN c, r, p",
            ["c", "r", "p"],
            ["vt_case", "vt_psn"],
            [{"type": "suspect_in", "src": "vt_psn", "tgt": "vt_case"}],
        ),
        (
            "계좌 {account_no}에서 돈을 받은 출금 계좌",
            "MATCH (b2:vt_bacnt {{account_no:'{account_no}'}})<-[:transferred_to]-(b1:vt_bacnt) RETURN b1, b2",
            ["b1", "b2"],
            ["vt_bacnt"],
            [{"type": "transferred_to", "src": "vt_bacnt", "tgt": "vt_bacnt"}],
        ),
        (
            "{telno}로 문자 보낸 번호들",
            "MATCH (t:vt_telno {{telno:'{telno}'}})<-[:contacted]-(t2:vt_telno) RETURN t2, t",
            ["t2", "t"],
            ["vt_telno"],
            [{"type": "contacted", "src": "vt_telno", "tgt": "vt_telno"}],
        ),
        (
            "사이트 {url_addr}에 접속한 IP 목록",
            "MATCH (s:vt_site {{url_addr:'{url_addr}'}})<-[:accessed]-(ip:vt_ip) RETURN ip, s",
            ["ip", "s"],
            ["vt_site", "vt_ip"],
            [{"type": "accessed", "src": "vt_ip", "tgt": "vt_site"}],
        ),
        (
            "이체를 받은 계좌 {account_no}와 이체 정보",
            "MATCH (b:vt_bacnt {{account_no:'{account_no}'}})<-[:to_account]-(tr:vt_transfer) RETURN tr, b",
            ["tr", "b"],
            ["vt_bacnt", "vt_transfer"],
            [{"type": "to_account", "src": "vt_transfer", "tgt": "vt_bacnt"}],
        ),
        # V3.3 사칭 reverse 패턴
        (
            "{org_name}에 사칭되는 수단 목록",
            "MATCH (t)-[:used_for]->(imp:vt_impersonation)-[:targets]->(o:vt_org {{org_name:'{org_name}'}}) RETURN t, imp, o",
            ["t", "imp", "o"],
            ["vt_org", "vt_impersonation", "vt_telno"],
            [{"type": "used_for", "src": "vt_telno", "tgt": "vt_impersonation"},
             {"type": "targets", "src": "vt_impersonation", "tgt": "vt_org"}],
        ),
    ]

    for q_tmpl, c_tmpl, vars_, nodes, edges in reverse_templates:
        for name, flnm, account_no, telno, url_addr, org_name in zip(
            NAMES, CASE_NOS, ACCOUNTS, PHONES, URLS, ORG_NAMES
        ):
            try:
                q = q_tmpl.format(
                    name=name, flnm=flnm, account_no=account_no,
                    telno=telno, url_addr=url_addr, org_name=org_name,
                )
                c = c_tmpl.format(
                    name=name, flnm=flnm, account_no=account_no,
                    telno=telno, url_addr=url_addr, org_name=org_name,
                )
            except KeyError:
                continue
            sch = schema_snippet(nodes, edges)
            samples.append(build_sample(q, wrap_cypher(c, vars_), sch))
            if len(samples) >= target:
                return samples

    while len(samples) < target:
        tmpl = random.choice(reverse_templates)
        q_tmpl, c_tmpl, vars_, nodes, edges = tmpl
        try:
            q = q_tmpl.format(
                name=random.choice(NAMES), flnm=random.choice(CASE_NOS),
                account_no=random.choice(ACCOUNTS), telno=random.choice(PHONES),
                url_addr=random.choice(URLS), org_name=random.choice(ORG_NAMES),
            )
            c = c_tmpl.format(
                name=random.choice(NAMES), flnm=random.choice(CASE_NOS),
                account_no=random.choice(ACCOUNTS), telno=random.choice(PHONES),
                url_addr=random.choice(URLS), org_name=random.choice(ORG_NAMES),
            )
        except KeyError:
            continue
        sch = schema_snippet(nodes, edges)
        samples.append(build_sample(q, wrap_cypher(c, vars_), sch))

    return samples[:target]


# ─────────────────────────────────────────────────────────────
# 9. 메인 실행
# ─────────────────────────────────────────────────────────────

def deduplicate(samples: list) -> list:
    seen = set()
    result = []
    for s in samples:
        key = s["conversations"][1]["value"]  # human turn
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def main():
    print("=== generate_t2c_sft.py ===")
    print("Phase 2 Step 1: 템플릿 기반 SFT 데이터 생성 (목표: 5,000개)\n")

    print("[1/5] 단일 노드 조회 생성 중... (목표: 1,200)")
    single = gen_single_node_samples()
    print(f"  → {len(single)}개 생성")

    print("[2/5] 1-hop 관계 조회 생성 중... (목표: 4,500)")
    one_hop = gen_1hop_samples(4500)
    print(f"  → {len(one_hop)}개 생성")

    print("[3/5] 집계 쿼리 생성 중... (목표: 800)")
    agg = gen_aggregate_samples(800)
    print(f"  → {len(agg)}개 생성")

    print("[4/5] 역방향 탐색 생성 중... (목표: 700)")
    reverse = gen_reverse_samples(700)
    print(f"  → {len(reverse)}개 생성")

    print("[5/5] GENERAL 거부 샘플 생성 중... (목표: 300)")
    general = gen_general_samples(300)
    print(f"  → {len(general)}개 생성")

    all_samples = single + one_hop + agg + reverse + general
    all_samples = deduplicate(all_samples)
    random.shuffle(all_samples)

    # 5,000개로 자르기
    all_samples = all_samples[:5000]

    print(f"\n중복 제거 후: {len(all_samples)}개")

    # 출력
    os.makedirs("data", exist_ok=True)
    out_path = "data/t2c_v1_template.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_samples, f, ensure_ascii=False, indent=2)

    print(f"\n저장 완료: {out_path}")

    # 통계
    intents = {}
    for s in all_samples:
        intent = s.get("intent", "QUERY")
        intents[intent] = intents.get(intent, 0) + 1
    print("\n[인텐트 분포]")
    for k, v in sorted(intents.items()):
        print(f"  {k}: {v}개 ({v/len(all_samples)*100:.1f}%)")

    print("\n✓ 완료!")


if __name__ == "__main__":
    main()
