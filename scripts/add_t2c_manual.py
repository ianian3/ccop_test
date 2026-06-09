"""
add_t2c_manual.py — Phase 2 Step 3
수동 제작 고품질 샘플 2,000개
  - 엣지 메타속성 조건 (verified / confidence / valid_from~valid_to): 600개
  - 위협 속성 필터 (is_burner / is_tor / is_malicious 등): 400개
  - 1.5-hop 체인 쿼리: 500개
  - 집계 + 정렬 고급 패턴: 300개
  - 보안 가드레일 (쓰기 명령 거부): 200개
출력: data/t2c_v1_manual.json (ShareGPT 포맷)
"""

import json
import os
import random

random.seed(77)

GRAPH = "tccop_graph"

# ─────────────────────────────────────────────────────────────
# 공통 헬퍼
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
""".format(graph=GRAPH)

GUARD_RESPONSE = "죄송합니다. 데이터 수정(CREATE/MERGE/DELETE/SET) 명령은 실행할 수 없습니다. 조회 쿼리만 지원합니다."
GENERAL_RESPONSE = "수사 관련 질문만 답변 가능합니다."

NODE_PROPS = {
    "vt_psn":      "psn_id, name, korn_flnm, dob, gender, rrno_hash, risk_level",
    "vt_bacnt":    "account_no, bank_cd, bank_nm, dpstr_nm, is_burner, is_frozen",
    "vt_telno":    "telno, telco_nm, join_typ_cd, is_burner, spam_cnt",
    "vt_ip":       "ip_addr, is_vpn, is_tor, is_proxy, abuse_score",
    "vt_site":     "url_addr, dmn_addr, site_type, is_malicious, risk_grd",
    "vt_case":     "flnm, incdnt_typ_cd, status, damage_amount, risk_level",
    "vt_transfer": "transfer_id, dlng_amt, dlng_dt, dlng_se_cd, hop_level, is_suspicious",
    "vt_call":     "call_id, call_strt_dt, call_dur_sec, call_typ_cd",
    "vt_org":      "org_id, org_name, org_category, bank_cd",
    "vt_vhcl":     "vhclno, carmdl_nm, ownr_nm, stolen_yn",
    "vt_loc":      "loc_id, loc_type, address, lat, lng",
    "vt_movement": "mov_id, mov_type, timestamp, loc_id",
    "vt_crypto":   "wallet_addr, blockchain, exchange, risk_score, balance",
    "vt_petition": "petition_id, rcpt_dt, crime_type_cd, damage_amt, status",
    "vt_access":   "access_id, access_dt, action, status_code",
}

EDGE_META_PROPS = "verified, confidence, valid_from, valid_to, source_id"


def make_schema(nodes: list, edges: list) -> str:
    lines = ["[스키마]", "노드:"]
    for n in nodes:
        props = NODE_PROPS.get(n, "")
        lines.append(f"  ({n} {{{props}}})")
    if edges:
        lines.append("관계:")
        for e in edges:
            meta = f", {EDGE_META_PROPS}" if e.get("has_meta") else ""
            extra = e.get("extra_props", "")
            if extra:
                prop_str = f"{extra}{meta}"
            else:
                prop_str = EDGE_META_PROPS if e.get("has_meta") else ""
            lines.append(f"  ({e['src']})-[:{e['type']} {{{prop_str}}}]->({e['tgt']})")
    lines.append("속성 접근:")
    lines.append("  WHERE n->>'속성명' = '값'  (문자열 비교)")
    lines.append("  WHERE toInteger(n->>'속성명') >= 숫자  (숫자 비교)")
    lines.append("  WHERE r.verified = true  (엣지 메타속성 직접 접근)")
    return "\n".join(lines)


def wrap(inner: str, cols: list) -> str:
    col_str = ", ".join(f"{c} agtype" for c in cols)
    return f"SELECT * FROM cypher('{GRAPH}', $$\n  {inner.strip()}\n$$) AS ({col_str});"


def sample(q: str, cypher: str, schema: str, intent: str = "QUERY") -> dict:
    return {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT},
            {"from": "human", "value": f"{schema}\n\n[질문]\n{q}"},
            {"from": "gpt", "value": cypher},
        ],
        "intent": intent,
        "_source": "manual",
    }


# ─────────────────────────────────────────────────────────────
# 카테고리 1: 엣지 메타속성 조건 쿼리 (600개)
# ─────────────────────────────────────────────────────────────

NAMES = [
    "홍길동", "김철수", "이영희", "박민준", "최지현", "정수현", "강민서", "윤지호", "장하은", "임도현",
    "오서연", "신재원", "배수진", "허민지", "류성준", "남기태", "양소영", "전현우", "조아름", "문재철",
    "한소희", "권지훈", "노민아", "석진호", "엄수아", "천기범", "방예진", "곽도현", "모지수", "봉성철",
]
ACCOUNTS = [
    "110-123-456789", "356-0123-4567-01", "901-1234-5678",
    "218-910234-01-011", "001-234567-01-001", "088-12345-67890",
    "620-123456-78901", "102-1234-567890", "567-890123-45678",
    "323-456-789012",
]
PHONES = [
    "010-1234-5678", "010-9876-5432", "010-2345-6789",
    "010-3456-7890", "010-4567-8901", "010-5678-9012",
    "010-6789-0123", "010-7890-1234", "010-8901-2345", "010-9012-3456",
]
CASE_NOS = [
    "2024-01234", "2023-56789", "2024-00012", "2025-11111", "2023-99999",
    "2024-77890", "2025-00456", "2024-33210", "2024-10001", "2023-20001",
]


def gen_meta_samples(target: int = 600) -> list:
    samples = []

    # (질문_표현_리스트, cypher_tmpl, vars, nodes, edges)
    META_TEMPLATES = [
        # verified = true — has_account
        (
            [
                "검증된 계좌 소유 관계만 조회",
                "공식 확인된 계좌 명의 관계 조회",
                "verified=true인 계좌 소유 엣지",
                "검증이 완료된 계좌 소유자 연결",
                "공문서로 확인된 계좌 보유 관계",
            ],
            "MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt)\n  WHERE r.verified = true\n  RETURN p, r, b",
            ["p", "r", "b"],
            ["vt_psn", "vt_bacnt"],
            [{"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": True, "extra_props": "account_role"}],
        ),
        # verified = true — owns_phone
        (
            [
                "공식 확인된 전화 소유 관계 조회",
                "검증된 전화번호 소유 엣지 조회",
                "verified 전화번호 보유 관계",
                "공식 확인된 휴대폰 소유자 연결",
                "공문서로 확인된 전화 소유 관계",
            ],
            "MATCH (p:vt_psn)-[r:owns_phone]->(t:vt_telno)\n  WHERE r.verified = true\n  RETURN p, r, t",
            ["p", "r", "t"],
            ["vt_psn", "vt_telno"],
            [{"type": "owns_phone", "src": "vt_psn", "tgt": "vt_telno", "has_meta": True}],
        ),
        # verified = true — member_of
        (
            [
                "조직 소속이 검증된 구성원 조회",
                "공식 확인된 조직원 관계",
                "검증된 조직 소속 엣지",
                "verified=true인 조직 멤버",
                "공문서로 확인된 조직 소속 인물",
            ],
            "MATCH (p:vt_psn)-[r:member_of]->(o:vt_org)\n  WHERE r.verified = true\n  RETURN p, r, o",
            ["p", "r", "o"],
            ["vt_psn", "vt_org"],
            [{"type": "member_of", "src": "vt_psn", "tgt": "vt_org", "has_meta": True, "extra_props": "role_cd, joined_dt"}],
        ),
        # confidence >= 0.7 — controls
        (
            [
                "신뢰도 0.7 이상인 실질 지배 계좌",
                "확신도 70% 이상의 계좌 실소유 관계",
                "confidence >= 0.7 인 controls 엣지",
                "신뢰도 높은 실질 지배 계좌 조회",
                "0.7 이상 신뢰도의 계좌 통제 관계",
            ],
            "MATCH (p:vt_psn)-[r:controls]->(b:vt_bacnt)\n  WHERE r.confidence >= 0.7\n  RETURN p, r, b",
            ["p", "r", "b"],
            ["vt_psn", "vt_bacnt"],
            [{"type": "controls", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": True, "extra_props": "control_type, confidence"}],
        ),
        # confidence >= 0.8 — accomplice_of
        (
            [
                "공범 확신도 0.8 이상인 공범 관계",
                "신뢰도 80% 이상의 공범 연결",
                "높은 확신도의 공범 추정 관계",
                "confidence >= 0.8 공범 엣지",
                "강한 증거의 공범 관계 조회",
            ],
            "MATCH (p:vt_psn)-[r:accomplice_of]-(p2:vt_psn)\n  WHERE r.confidence >= 0.8\n  RETURN p, r, p2",
            ["p", "r", "p2"],
            ["vt_psn"],
            [{"type": "accomplice_of", "src": "vt_psn", "tgt": "vt_psn", "has_meta": False, "extra_props": "confidence, method"}],
        ),
        # confidence < 0.5 — member_of
        (
            [
                "신뢰도 0.5 미만인 조직 소속 관계",
                "낮은 확신도의 조직 소속 엣지",
                "불확실한 조직 구성원 관계 조회",
                "confidence < 0.5 조직 멤버 조회",
                "50% 미만 신뢰도의 조직원 관계",
            ],
            "MATCH (p:vt_psn)-[r:member_of]->(o:vt_org)\n  WHERE r.confidence < 0.5\n  RETURN p, r, o",
            ["p", "r", "o"],
            ["vt_psn", "vt_org"],
            [{"type": "member_of", "src": "vt_psn", "tgt": "vt_org", "has_meta": True, "extra_props": "role_cd"}],
        ),
        # valid_from/valid_to — 2024년 1월
        (
            [
                "2024년 1월에 유효했던 계좌 소유 관계",
                "2024-01 기간 동안 활성화된 계좌 명의",
                "2024년 1월 기준 유효 계좌 소유 엣지",
                "2024년 1월 유효 기간 내 계좌 보유 관계",
                "valid_from~valid_to가 2024년 1월을 포함하는 계좌",
            ],
            "MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt)\n  WHERE r.valid_from <= '2024-01-31'\n    AND (r.valid_to IS NULL OR r.valid_to >= '2024-01-01')\n  RETURN p, r, b",
            ["p", "r", "b"],
            ["vt_psn", "vt_bacnt"],
            [{"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": True}],
        ),
        # valid_to IS NULL — owns_phone
        (
            [
                "현재도 유효한 전화번호 소유 관계",
                "아직 종료되지 않은 전화 소유 엣지",
                "valid_to가 null인 전화번호 소유",
                "지금도 사용 중인 전화 소유 관계",
                "만료되지 않은 전화번호 명의 조회",
            ],
            "MATCH (p:vt_psn)-[r:owns_phone]->(t:vt_telno)\n  WHERE r.valid_to IS NULL\n  RETURN p, r, t",
            ["p", "r", "t"],
            ["vt_psn", "vt_telno"],
            [{"type": "owns_phone", "src": "vt_psn", "tgt": "vt_telno", "has_meta": True}],
        ),
        # valid_to 2023년 — works_at
        (
            [
                "2023년에 종료된 직장 소속 관계",
                "2023년 퇴직 처리된 직장 엣지",
                "2023년 내 valid_to인 works_at",
                "2023년에 끝난 재직 관계 조회",
                "2023년 이직/퇴직 인물 직장 관계",
            ],
            "MATCH (p:vt_psn)-[r:works_at]->(o:vt_org)\n  WHERE r.valid_to >= '2023-01-01' AND r.valid_to <= '2023-12-31'\n  RETURN p, r, o",
            ["p", "r", "o"],
            ["vt_psn", "vt_org"],
            [{"type": "works_at", "src": "vt_psn", "tgt": "vt_org", "has_meta": True, "extra_props": "position, dept"}],
        ),
        # verified AND confidence >= 0.9
        (
            [
                "검증되고 신뢰도 0.9 이상인 실질 지배 관계",
                "verified이면서 confidence 0.9 이상인 controls 엣지",
                "이중 검증된 계좌 실소유 관계",
                "공식 확인 + 고신뢰도 계좌 통제 관계",
                "검증 완료 + 90% 이상 확신 계좌 지배",
            ],
            "MATCH (p:vt_psn)-[r:controls]->(b:vt_bacnt)\n  WHERE r.verified = true AND r.confidence >= 0.9\n  RETURN p, r, b",
            ["p", "r", "b"],
            ["vt_psn", "vt_bacnt"],
            [{"type": "controls", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": True, "extra_props": "control_type, confidence"}],
        ),
        # 인물별 verified 계좌
        (
            [
                "{name}의 검증된 계좌 소유만 조회",
                "{name} 명의 공식 확인 계좌",
                "{name}이 실제로 검증된 통장",
                "피의자 {name}의 verified 계좌",
                "{name} 검증 완료 계좌 목록",
            ],
            "MATCH (p:vt_psn {{name:'{name}'}})-[r:has_account]->(b:vt_bacnt)\n  WHERE r.verified = true\n  RETURN p, r, b",
            ["p", "r", "b"],
            ["vt_psn", "vt_bacnt"],
            [{"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": True}],
        ),
        # 인물별 현재 전화
        (
            [
                "{name}이 현재도 사용 중인 전화번호",
                "{name}의 아직 유효한 전화 소유 관계",
                "현재 {name}이 보유 중인 번호",
                "{name}의 valid_to=null 전화",
                "지금도 활성화된 {name} 전화번호",
            ],
            "MATCH (p:vt_psn {{name:'{name}'}})-[r:owns_phone]->(t:vt_telno)\n  WHERE r.valid_to IS NULL\n  RETURN p, r, t",
            ["p", "r", "t"],
            ["vt_psn", "vt_telno"],
            [{"type": "owns_phone", "src": "vt_psn", "tgt": "vt_telno", "has_meta": True}],
        ),
    ]

    for q_list, c_tmpl, vars_, nodes, edges in META_TEMPLATES:
        for q_tmpl in q_list:
            # {name} 있으면 모든 NAMES 순회, 없으면 1번만
            name_iter = NAMES if "{name}" in q_tmpl else [""]
            for name in name_iter:
                q = q_tmpl.format(name=name) if name else q_tmpl
                c = c_tmpl.format(name=name) if name else c_tmpl
                sch = make_schema(nodes, edges)
                samples.append(sample(q, wrap(c, vars_), sch))
                if len(samples) >= target:
                    return samples

    # 부족분
    while len(samples) < target:
        name = random.choice(NAMES)
        q = f"{name}의 검증된 계좌 소유 관계 조회"
        c = f"MATCH (p:vt_psn {{name:'{name}'}})-[r:has_account]->(b:vt_bacnt)\n  WHERE r.verified = true\n  RETURN p, r, b"
        sch = make_schema(["vt_psn", "vt_bacnt"], [{"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": True}])
        samples.append(sample(q, wrap(c, ["p", "r", "b"]), sch))

    return samples[:target]


# ─────────────────────────────────────────────────────────────
# 카테고리 2: 위협 속성 필터 (400개)
# ─────────────────────────────────────────────────────────────

def gen_threat_samples(target: int = 400) -> list:
    samples = []

    # (질문_표현_리스트, cypher, vars, nodes, edges)
    THREAT_TEMPLATES = [
        (
            ["대포통장으로 의심되는 계좌 전체", "is_burner=true 계좌 조회", "명의도용 의심 통장 목록",
             "개설 직후 사용된 대포 계좌", "범죄 연루 의심 계좌 전체"],
            "MATCH (b:vt_bacnt) WHERE b->>'is_burner' = 'true' RETURN b",
            ["b"], ["vt_bacnt"], [],
        ),
        (
            ["지급정지된 계좌 목록", "동결된 계좌 전체 조회", "is_frozen=true 계좌",
             "사용 정지 계좌 조회", "금융 거래가 정지된 계좌"],
            "MATCH (b:vt_bacnt) WHERE b->>'is_frozen' = 'true' RETURN b",
            ["b"], ["vt_bacnt"], [],
        ),
        (
            ["대포통장이면서 지급정지된 계좌", "대포+동결 이중 의심 계좌", "is_burner AND is_frozen 계좌",
             "명의도용+지급정지 계좌 조회", "대포통장 중 동결된 계좌"],
            "MATCH (b:vt_bacnt) WHERE b->>'is_burner' = 'true' AND b->>'is_frozen' = 'true' RETURN b",
            ["b"], ["vt_bacnt"], [],
        ),
        (
            ["대포폰 의심 번호 목록", "is_burner 전화번호 조회", "명의 도용 대포폰",
             "단기 개통 의심 번호", "범죄 연루 대포폰 전체"],
            "MATCH (t:vt_telno) WHERE t->>'is_burner' = 'true' RETURN t",
            ["t"], ["vt_telno"], [],
        ),
        (
            ["스팸 신고 5회 이상인 번호", "spam_cnt >= 5 전화번호", "다중 신고된 번호 조회",
             "스팸 의심 전화번호 목록", "5건 이상 스팸 신고 번호"],
            "MATCH (t:vt_telno) WHERE toInteger(t->>'spam_cnt') >= 5 RETURN t",
            ["t"], ["vt_telno"], [],
        ),
        (
            ["스팸 신고 10회 이상인 번호", "spam_cnt >= 10 고위험 번호", "10건 이상 신고된 번호",
             "다수 피해자가 신고한 전화", "고위험 스팸 번호 조회"],
            "MATCH (t:vt_telno) WHERE toInteger(t->>'spam_cnt') >= 10 RETURN t",
            ["t"], ["vt_telno"], [],
        ),
        (
            ["토르 네트워크 사용 IP", "is_tor=true IP 조회", "다크웹 접속 IP",
             "토르 브라우저 사용 추정 IP", "익명화 네트워크 IP 목록"],
            "MATCH (ip:vt_ip) WHERE ip->>'is_tor' = 'true' RETURN ip",
            ["ip"], ["vt_ip"], [],
        ),
        (
            ["VPN 사용 IP 목록", "is_vpn=true IP 조회", "가상사설망 접속 IP",
             "VPN 우회 의심 IP", "신원 숨긴 VPN IP"],
            "MATCH (ip:vt_ip) WHERE ip->>'is_vpn' = 'true' RETURN ip",
            ["ip"], ["vt_ip"], [],
        ),
        (
            ["토르 또는 VPN 사용 IP", "is_tor OR is_vpn IP", "익명 접속 IP 전체",
             "신원 은폐 IP 조회", "토르/VPN 모두 포함 IP 목록"],
            "MATCH (ip:vt_ip) WHERE ip->>'is_tor' = 'true' OR ip->>'is_vpn' = 'true' RETURN ip",
            ["ip"], ["vt_ip"], [],
        ),
        (
            ["어뷰즈 점수 50 이상인 IP", "abuse_score >= 50 악성 IP", "위험 점수 높은 IP",
             "어뷰즈DB 등록 IP 조회", "악성 행위 이력 IP"],
            "MATCH (ip:vt_ip) WHERE toInteger(ip->>'abuse_score') >= 50 RETURN ip",
            ["ip"], ["vt_ip"], [],
        ),
        (
            ["악성 사이트 목록", "is_malicious=true 사이트", "피싱/악성코드 사이트 조회",
             "범죄 연루 웹사이트 전체", "악성 URL 목록"],
            "MATCH (s:vt_site) WHERE s->>'is_malicious' = 'true' RETURN s",
            ["s"], ["vt_site"], [],
        ),
        (
            ["고위험 사이트 (risk_grd = HIGH)", "risk_grd HIGH 사이트 조회", "위험도 최상 사이트",
             "HIGH 등급 위험 사이트 목록", "고위험 URL 조회"],
            "MATCH (s:vt_site) WHERE s->>'risk_grd' = 'HIGH' RETURN s",
            ["s"], ["vt_site"], [],
        ),
        (
            ["악성 파일 해시 목록", "is_malicious=true 파일", "멀웨어 파일 조회",
             "랜섬웨어 등 악성 파일 전체", "바이러스 감염 파일 목록"],
            "MATCH (f:vt_file) WHERE f->>'is_malicious' = 'true' RETURN f",
            ["f"], ["vt_file"], [],
        ),
        (
            ["바이러스토탈 점수 70 이상 파일", "vt_score >= 70 파일", "VirusTotal 고위험 파일",
             "70점 이상 악성 파일", "고위험 해시값 파일 조회"],
            "MATCH (f:vt_file) WHERE toInteger(f->>'vt_score') >= 70 RETURN f",
            ["f"], ["vt_file"], [],
        ),
        (
            ["고위험 가상자산 지갑 (risk_score >= 70)", "위험 점수 70 이상 지갑", "자금세탁 의심 지갑",
             "risk_score 고위험 크립토 지갑", "위험 등급 가상화폐 지갑 조회"],
            "MATCH (cr:vt_crypto) WHERE toInteger(cr->>'risk_score') >= 70 RETURN cr",
            ["cr"], ["vt_crypto"], [],
        ),
        (
            ["도난 차량 목록", "stolen_yn=true 차량", "도난 신고 차량 조회",
             "불법 취득 차량 전체", "도난 등록 차량 목록"],
            "MATCH (v:vt_vhcl) WHERE v->>'stolen_yn' = 'true' RETURN v",
            ["v"], ["vt_vhcl"], [],
        ),
        (
            ["위험도가 HIGH인 인물 목록", "risk_level=HIGH 인물 조회", "고위험 수사 대상자",
             "위험 등급 최상 인물 전체", "HIGH 위험도 인물 목록"],
            "MATCH (p:vt_psn) WHERE p->>'risk_level' = 'HIGH' RETURN p",
            ["p"], ["vt_psn"], [],
        ),
        (
            ["위험도가 CRITICAL인 사건 목록", "risk_level=CRITICAL 사건", "최고 위험 사건 조회",
             "긴급 수사 사건 전체", "CRITICAL 등급 사건 목록"],
            "MATCH (c:vt_case) WHERE c->>'risk_level' = 'CRITICAL' RETURN c",
            ["c"], ["vt_case"], [],
        ),
    ]

    for q_list, c, vars_, nodes, edges in THREAT_TEMPLATES:
        for q in q_list:
            sch = make_schema(nodes, edges)
            samples.append(sample(q, wrap(c, vars_), sch))
            if len(samples) >= target:
                return samples

    # 조합 패턴 추가
    combo_templates = [
        ("대포통장을 보유한 인물 조회",
         "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) WHERE b->>'is_burner' = 'true' RETURN p, b",
         ["p", "b"], ["vt_psn", "vt_bacnt"],
         [{"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": False}]),
        ("대포폰 소유 인물 조회",
         "MATCH (p:vt_psn)-[:owns_phone]->(t:vt_telno) WHERE t->>'is_burner' = 'true' RETURN p, t",
         ["p", "t"], ["vt_psn", "vt_telno"],
         [{"type": "owns_phone", "src": "vt_psn", "tgt": "vt_telno", "has_meta": False}]),
        ("토르 IP를 사용한 인물 조회",
         "MATCH (p:vt_psn)-[:used_ip]->(ip:vt_ip) WHERE ip->>'is_tor' = 'true' RETURN p, ip",
         ["p", "ip"], ["vt_psn", "vt_ip"],
         [{"type": "used_ip", "src": "vt_psn", "tgt": "vt_ip", "has_meta": False}]),
        ("악성 사이트에 접속한 IP 조회",
         "MATCH (ip:vt_ip)-[:accessed]->(s:vt_site) WHERE s->>'is_malicious' = 'true' RETURN ip, s",
         ["ip", "s"], ["vt_ip", "vt_site"],
         [{"type": "accessed", "src": "vt_ip", "tgt": "vt_site", "has_meta": False}]),
        ("도난 차량을 운행한 인물",
         "MATCH (p:vt_psn)-[:drives]->(v:vt_vhcl) WHERE v->>'stolen_yn' = 'true' RETURN p, v",
         ["p", "v"], ["vt_psn", "vt_vhcl"],
         [{"type": "drives", "src": "vt_psn", "tgt": "vt_vhcl", "has_meta": False}]),
    ]

    for q, c, vars_, nodes, edges in combo_templates:
        for _ in range(15):  # 반복
            sch = make_schema(nodes, edges)
            samples.append(sample(q, wrap(c, vars_), sch))
            if len(samples) >= target:
                return samples

    while len(samples) < target:
        q = "대포통장 의심 계좌 전체 목록"
        c = "MATCH (b:vt_bacnt) WHERE b->>'is_burner' = 'true' RETURN b"
        sch = make_schema(["vt_bacnt"], [])
        samples.append(sample(q, wrap(c, ["b"]), sch))

    return samples[:target]


# ─────────────────────────────────────────────────────────────
# 카테고리 3: 1.5-hop 체인 쿼리 (500개)
# ─────────────────────────────────────────────────────────────

def gen_chain_samples(target: int = 500) -> list:
    samples = []

    CHAIN_TEMPLATES = [
        # 자금 흐름 체인
        (
            "{name}의 계좌에서 나간 이체 내역 (인물→계좌→이체)",
            "MATCH (p:vt_psn {{name:'{name}'}})-[:has_account]->(b:vt_bacnt)-[:from_account]->(tr:vt_transfer)\n  RETURN p, b, tr",
            ["p", "b", "tr"],
            ["vt_psn", "vt_bacnt", "vt_transfer"],
            [
                {"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": False},
                {"type": "from_account", "src": "vt_bacnt", "tgt": "vt_transfer", "has_meta": False},
            ],
        ),
        (
            "{name}의 계좌로 들어온 이체 (인물→계좌←이체)",
            "MATCH (p:vt_psn {{name:'{name}'}})-[:has_account]->(b:vt_bacnt)<-[:to_account]-(tr:vt_transfer)\n  RETURN p, b, tr",
            ["p", "b", "tr"],
            ["vt_psn", "vt_bacnt", "vt_transfer"],
            [
                {"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": False},
                {"type": "to_account", "src": "vt_transfer", "tgt": "vt_bacnt", "has_meta": False},
            ],
        ),
        (
            "계좌 {account_no}의 이체 흐름 전체 (출금→이체→입금)",
            "MATCH (b1:vt_bacnt {{account_no:'{account_no}'}})-[:from_account]->(tr:vt_transfer)-[:to_account]->(b2:vt_bacnt)\n  RETURN b1, tr, b2",
            ["b1", "tr", "b2"],
            ["vt_bacnt", "vt_transfer"],
            [
                {"type": "from_account", "src": "vt_bacnt", "tgt": "vt_transfer", "has_meta": False},
                {"type": "to_account", "src": "vt_transfer", "tgt": "vt_bacnt", "has_meta": False},
            ],
        ),
        # 보이스피싱 통화 체인
        (
            "대포폰 {telno}의 발신 통화 체인 (대포폰→통화→수신번호)",
            "MATCH (t1:vt_telno {{telno:'{telno}'}})-[:caller]->(c:vt_call)-[:callee]->(t2:vt_telno)\n  WHERE t1->>'is_burner' = 'true'\n  RETURN t1, c, t2",
            ["t1", "c", "t2"],
            ["vt_telno", "vt_call"],
            [
                {"type": "caller", "src": "vt_telno", "tgt": "vt_call", "has_meta": False},
                {"type": "callee", "src": "vt_call", "tgt": "vt_telno", "has_meta": False},
            ],
        ),
        (
            "{name}의 전화번호 발신 통화 목록 (인물→전화→통화)",
            "MATCH (p:vt_psn {{name:'{name}'}})-[:owns_phone]->(t:vt_telno)-[:caller]->(c:vt_call)\n  RETURN p, t, c",
            ["p", "t", "c"],
            ["vt_psn", "vt_telno", "vt_call"],
            [
                {"type": "owns_phone", "src": "vt_psn", "tgt": "vt_telno", "has_meta": False},
                {"type": "caller", "src": "vt_telno", "tgt": "vt_call", "has_meta": False},
            ],
        ),
        # IP → 접속 → 사이트
        (
            "IP {ip_addr}의 접속 사이트 체인",
            "MATCH (ip:vt_ip {{ip_addr:'{ip_addr}'}})-[:accessed_from]->(a:vt_access)-[:accessed_to]->(s:vt_site)\n  RETURN ip, a, s",
            ["ip", "a", "s"],
            ["vt_ip", "vt_access", "vt_site"],
            [
                {"type": "accessed_from", "src": "vt_ip", "tgt": "vt_access", "has_meta": False},
                {"type": "accessed_to", "src": "vt_access", "tgt": "vt_site", "has_meta": False},
            ],
        ),
        (
            "{name}이 사용한 IP로 접속한 사이트 (인물→IP→접속→사이트)",
            "MATCH (p:vt_psn {{name:'{name}'}})-[:used_ip]->(ip:vt_ip)-[:accessed_from]->(a:vt_access)-[:accessed_to]->(s:vt_site)\n  RETURN p, ip, a, s",
            ["p", "ip", "a", "s"],
            ["vt_psn", "vt_ip", "vt_access", "vt_site"],
            [
                {"type": "used_ip", "src": "vt_psn", "tgt": "vt_ip", "has_meta": False},
                {"type": "accessed_from", "src": "vt_ip", "tgt": "vt_access", "has_meta": False},
                {"type": "accessed_to", "src": "vt_access", "tgt": "vt_site", "has_meta": False},
            ],
        ),
        # 차량 → 이동 → 위치
        (
            "차량 {vhclno}의 이동 경로 (차량→이동→위치)",
            "MATCH (v:vt_vhcl {{vhclno:'{vhclno}'}})-[:recorded_in]->(m:vt_movement)-[:occurred_at]->(loc:vt_loc)\n  RETURN v, m, loc",
            ["v", "m", "loc"],
            ["vt_vhcl", "vt_movement", "vt_loc"],
            [
                {"type": "recorded_in", "src": "vt_vhcl", "tgt": "vt_movement", "has_meta": False},
                {"type": "occurred_at", "src": "vt_movement", "tgt": "vt_loc", "has_meta": False},
            ],
        ),
        # 피의자 → 사건 (체인에서 피의자 정보)
        (
            "사건 {flnm}의 피의자와 해당 피의자의 계좌 (사건→피의자→계좌)",
            "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case {{flnm:'{flnm}'}})\n  OPTIONAL MATCH (p)-[:has_account]->(b:vt_bacnt)\n  RETURN p, c, b",
            ["p", "c", "b"],
            ["vt_psn", "vt_case", "vt_bacnt"],
            [
                {"type": "suspect_in", "src": "vt_psn", "tgt": "vt_case", "has_meta": False},
                {"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": False},
            ],
        ),
        # 이체 행위자 체인
        (
            "이체 {transfer_id}를 실행한 인물과 그 인물의 사건 연루 (이체→행위자→사건)",
            "MATCH (tr:vt_transfer {{transfer_id:'{transfer_id}'}})-[:performed_by]->(p:vt_psn)-[:suspect_in]->(c:vt_case)\n  RETURN tr, p, c",
            ["tr", "p", "c"],
            ["vt_transfer", "vt_psn", "vt_case"],
            [
                {"type": "performed_by", "src": "vt_transfer", "tgt": "vt_psn", "has_meta": False},
                {"type": "suspect_in", "src": "vt_psn", "tgt": "vt_case", "has_meta": False},
            ],
        ),
    ]

    vhclnos = ["12가3456", "34나7890", "56다1234"]
    transfer_ids = ["TR-20240101-001", "TR-20240215-042"]
    ips = ["1.2.3.4", "192.168.0.1", "10.0.0.5", "203.0.113.99"]

    for q_tmpl, c_tmpl, vars_, nodes, edges in CHAIN_TEMPLATES:
        # 모든 이름/계좌 조합 순회 (cross product 대신 순서 순회)
        for i in range(max(len(NAMES), len(ACCOUNTS))):
            name = NAMES[i % len(NAMES)]
            account_no = ACCOUNTS[i % len(ACCOUNTS)]
            telno = PHONES[i % len(PHONES)]
            flnm = CASE_NOS[i % len(CASE_NOS)]
            ip_addr = ips[i % len(ips)]
            vhclno = vhclnos[i % len(vhclnos)]
            transfer_id = transfer_ids[i % len(transfer_ids)]
            try:
                q = q_tmpl.format(
                    name=name, account_no=account_no, telno=telno,
                    flnm=flnm, ip_addr=ip_addr, vhclno=vhclno,
                    transfer_id=transfer_id,
                )
                c = c_tmpl.format(
                    name=name, account_no=account_no, telno=telno,
                    flnm=flnm, ip_addr=ip_addr, vhclno=vhclno,
                    transfer_id=transfer_id,
                )
            except KeyError:
                continue
            sch = make_schema(nodes, edges)
            samples.append(sample(q, wrap(c, vars_), sch))
            if len(samples) >= target:
                return samples

    while len(samples) < target:
        name = random.choice(NAMES)
        account_no = random.choice(ACCOUNTS)
        q = f"{name}의 계좌에서 나간 이체 내역"
        c = f"MATCH (p:vt_psn {{name:'{name}'}})-[:has_account]->(b:vt_bacnt)-[:from_account]->(tr:vt_transfer)\n  RETURN p, b, tr"
        sch = make_schema(
            ["vt_psn", "vt_bacnt", "vt_transfer"],
            [
                {"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": False},
                {"type": "from_account", "src": "vt_bacnt", "tgt": "vt_transfer", "has_meta": False},
            ]
        )
        samples.append(sample(q, wrap(c, ["p", "b", "tr"]), sch))

    return samples[:target]


# ─────────────────────────────────────────────────────────────
# 카테고리 4: 집계 + 정렬 고급 패턴 (300개)
# ─────────────────────────────────────────────────────────────

def gen_advanced_agg_samples(target: int = 300) -> list:
    samples = []

    ADV_TEMPLATES = [
        (
            "피의자가 가장 많은 사건 TOP 5",
            "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case)\n  RETURN c, count(p) AS suspect_cnt\n  ORDER BY suspect_cnt DESC\n  LIMIT 5",
            ["c", "suspect_cnt"],
            ["vt_psn", "vt_case"],
            [{"type": "suspect_in", "src": "vt_psn", "tgt": "vt_case", "has_meta": False}],
        ),
        (
            "계좌별 총 이체 금액 집계 (내림차순 상위 10)",
            "MATCH (b:vt_bacnt)-[:from_account]->(tr:vt_transfer)\n  RETURN b, sum(toInteger(tr->>'dlng_amt')) AS total_amt\n  ORDER BY total_amt DESC\n  LIMIT 10",
            ["b", "total_amt"],
            ["vt_bacnt", "vt_transfer"],
            [{"type": "from_account", "src": "vt_bacnt", "tgt": "vt_transfer", "has_meta": False}],
        ),
        (
            "인물별 보유 계좌 수 집계",
            "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt)\n  RETURN p, count(b) AS acnt_cnt\n  ORDER BY acnt_cnt DESC",
            ["p", "acnt_cnt"],
            ["vt_psn", "vt_bacnt"],
            [{"type": "has_account", "src": "vt_psn", "tgt": "vt_bacnt", "has_meta": False}],
        ),
        (
            "스팸 신고 합계가 가장 높은 전화번호 10개",
            "MATCH (t:vt_telno)\n  RETURN t\n  ORDER BY toInteger(t->>'spam_cnt') DESC\n  LIMIT 10",
            ["t"], ["vt_telno"], [],
        ),
        (
            "이체 호수(hop_level)별 의심 이체 건수 집계",
            "MATCH (tr:vt_transfer) WHERE tr->>'is_suspicious' = 'true'\n  RETURN tr->>'hop_level' AS hop, count(tr) AS cnt\n  ORDER BY hop",
            ["hop", "cnt"], ["vt_transfer"], [],
        ),
        (
            "{name}의 사건별 역할 분포 (피의자/피해자/참고인)",
            "MATCH (p:vt_psn {{name:'{name}'}})-[r]->(c:vt_case)\n  RETURN type(r) AS role, count(c) AS cnt",
            ["role", "cnt"],
            ["vt_psn", "vt_case"],
            [{"type": "suspect_in", "src": "vt_psn", "tgt": "vt_case", "has_meta": False}],
        ),
        (
            "최근 1개월 이내 이체된 의심 거래",
            "MATCH (tr:vt_transfer)\n  WHERE tr->>'is_suspicious' = 'true'\n    AND tr->>'dlng_dt' >= '2024-03-01'\n  RETURN tr\n  ORDER BY tr->>'dlng_dt' DESC",
            ["tr"], ["vt_transfer"], [],
        ),
        (
            "피해금액 합계가 5천만원 이상인 사건 유형",
            "MATCH (c:vt_case)\n  RETURN c->>'incdnt_typ_cd' AS type, sum(toInteger(c->>'damage_amount')) AS total\n  HAVING total >= 50000000\n  ORDER BY total DESC",
            ["type", "total"], ["vt_case"], [],
        ),
        (
            "조직별 구성원 수 집계 (상위 5개 조직)",
            "MATCH (p:vt_psn)-[:member_of]->(o:vt_org)\n  RETURN o, count(p) AS member_cnt\n  ORDER BY member_cnt DESC\n  LIMIT 5",
            ["o", "member_cnt"],
            ["vt_psn", "vt_org"],
            [{"type": "member_of", "src": "vt_psn", "tgt": "vt_org", "has_meta": False}],
        ),
        (
            "이체 금액 구간별 건수 (구간: 0~100만, 100~500만, 500만+)",
            "MATCH (tr:vt_transfer)\n  RETURN\n    CASE\n      WHEN toInteger(tr->>'dlng_amt') < 1000000 THEN '0~100만'\n      WHEN toInteger(tr->>'dlng_amt') < 5000000 THEN '100~500만'\n      ELSE '500만+'\n    END AS range,\n    count(tr) AS cnt",
            ["range", "cnt"], ["vt_transfer"], [],
        ),
    ]

    for q_tmpl, c_tmpl, vars_, nodes, edges in ADV_TEMPLATES:
        name_iter = NAMES if "{name}" in q_tmpl else [""]
        flnm_iter = CASE_NOS if "{flnm}" in q_tmpl else [""]
        for name in name_iter:
            for flnm in flnm_iter:
                q = q_tmpl.replace("{name}", name).replace("{flnm}", flnm) if (name or flnm) else q_tmpl
                c = c_tmpl.replace("{name}", name).replace("{flnm}", flnm) if (name or flnm) else c_tmpl
                if not q.strip():
                    continue
                sch = make_schema(nodes, edges)
                samples.append(sample(q, wrap(c, vars_), sch))
                if len(samples) >= target:
                    return samples

    while len(samples) < target:
        q = "피의자가 가장 많은 사건 TOP 5"
        c = "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case)\n  RETURN c, count(p) AS cnt\n  ORDER BY cnt DESC\n  LIMIT 5"
        sch = make_schema(["vt_psn", "vt_case"], [{"type": "suspect_in", "src": "vt_psn", "tgt": "vt_case", "has_meta": False}])
        samples.append(sample(q, wrap(c, ["c", "cnt"]), sch))

    return samples[:target]


# ─────────────────────────────────────────────────────────────
# 카테고리 5: 보안 가드레일 (200개)
# ─────────────────────────────────────────────────────────────

WRITE_QUESTIONS = [
    "홍길동 인물 노드 삭제해줘",
    "계좌 110-123-456789 정보 업데이트",
    "피의자 새로 추가해줘",
    "모든 대포통장 삭제 처리",
    "사건 2024-01234 상태를 CLOSED로 변경",
    "CREATE로 새 이체 노드 만들어줘",
    "MERGE를 이용해 인물 업서트 해줘",
    "DELETE 명령으로 IP 기록 삭제",
    "SET 명령으로 계좌 잔액 수정",
    "DETACH DELETE로 사건 전체 삭제",
    "홍길동 노드에 속성 추가해줘",
    "의심 이체 기록을 모두 지워줘",
    "악성 사이트 플래그 초기화",
    "계좌 동결 해제 처리해줘",
    "이체 hop_level 0으로 리셋",
    "새로운 피해자 노드 INSERT",
    "조직 구성원 관계 삭제",
    "사건 사건번호 수정",
    "인물 생년월일 변경",
    "전화번호 is_burner 해제",
]

SECURITY_QUESTIONS = [
    "SELECT * FROM users WHERE 1=1",
    "'; DROP TABLE suspects; --",
    "MATCH (n) DETACH DELETE n",
    "'; MERGE (x:Hacker) RETURN x; --",
    "모든 노드 초기화해줘",
    "DB 전체 삭제 명령 실행",
    "인젝션 테스트: {malicious_input}",
    "관리자 계정 비밀번호 알려줘",
    "시스템 권한 획득 방법",
]


def gen_guard_samples(target: int = 200) -> list:
    samples = []

    # 쓰기 명령 거부
    sch = "[스키마]\n(보안 가드레일 — 쓰기 명령 거부)"
    for q in WRITE_QUESTIONS:
        samples.append(sample(q, GUARD_RESPONSE, sch, intent="GUARD"))

    # 더 많은 변형
    write_patterns = [
        ("DELETE", ["지워줘", "삭제해줘", "제거해줘", "없애줘"]),
        ("CREATE", ["추가해줘", "생성해줘", "만들어줘", "입력해줘"]),
        ("SET",    ["수정해줘", "변경해줘", "업데이트해줘", "바꿔줘"]),
        ("MERGE",  ["업서트해줘", "합쳐줘", "넣어줘"]),
    ]
    for cmd, suffixes in write_patterns:
        for name in NAMES:
            for suf in suffixes:
                q = f"{name} 정보 {suf} ({cmd})"
                samples.append(sample(q, GUARD_RESPONSE, sch, intent="GUARD"))
                if len(samples) >= target:
                    return samples

    # 보안 인젝션 거부
    for q in SECURITY_QUESTIONS:
        samples.append(sample(q, GUARD_RESPONSE, sch, intent="GUARD"))
        if len(samples) >= target:
            return samples

    # 부족분
    while len(samples) < target:
        name = random.choice(NAMES)
        q = f"{name} 노드 삭제 요청"
        samples.append(sample(q, GUARD_RESPONSE, sch, intent="GUARD"))

    return samples[:target]


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main():
    print("=== add_t2c_manual.py ===")
    print("Phase 2 Step 3: 수동 제작 SFT 데이터 생성 (목표: 2,000개)\n")

    print("[1/5] 엣지 메타속성 조건 쿼리 생성... (목표: 600)")
    meta = gen_meta_samples(600)
    print(f"  → {len(meta)}개")

    print("[2/5] 위협 속성 필터 쿼리 생성... (목표: 400)")
    threat = gen_threat_samples(400)
    print(f"  → {len(threat)}개")

    print("[3/5] 1.5-hop 체인 쿼리 생성... (목표: 500)")
    chain = gen_chain_samples(500)
    print(f"  → {len(chain)}개")

    print("[4/5] 집계 + 정렬 고급 패턴 생성... (목표: 300)")
    agg = gen_advanced_agg_samples(300)
    print(f"  → {len(agg)}개")

    print("[5/5] 보안 가드레일 샘플 생성... (목표: 200)")
    guard = gen_guard_samples(200)
    print(f"  → {len(guard)}개")

    all_samples = meta + threat + chain + agg + guard

    # 중복 제거
    seen = set()
    deduped = []
    for s in all_samples:
        key = s["conversations"][1]["value"]
        if key not in seen:
            seen.add(key)
            deduped.append(s)

    random.shuffle(deduped)
    deduped = deduped[:2000]
    print(f"\n중복 제거 후: {len(deduped)}개")

    os.makedirs("data", exist_ok=True)
    out_path = "data/t2c_v1_manual.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(deduped, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {out_path}")

    # 통계
    intents = {}
    for s in deduped:
        k = s.get("intent", "QUERY")
        intents[k] = intents.get(k, 0) + 1
    print("\n[인텐트 분포]")
    for k, v in sorted(intents.items()):
        print(f"  {k}: {v}개 ({v/len(deduped)*100:.1f}%)")

    print("\n✓ 완료!")


if __name__ == "__main__":
    main()
