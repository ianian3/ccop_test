"""
build_v38_weakness_seed.py — Qwen v37 학습 모델 약점 카테고리 1,500 시드 보강

근거 (TEXT2CYPHER_V37_EVAL_REPORT.md 6.1):
  - 1hop_person2person 20% (목표 70%+)
  - 1hop_case 33% (목표 80%+)
  - 1hop_event 40% (목표 80%+)
  - 1hop_object 40% (목표 80%+)
  - 1hop_person 36% (목표 80%+)

출력: data/t2c_v38_weakness_train_msg.json (OpenAI messages format)
       LF dataset_info.json에 t2c_v38_weakness_msg로 등록 후 학습 데이터에 합산.

사용: python data/build_v38_weakness_seed.py [--out data/t2c_v38_weakness_train_msg.json]
"""
import argparse
import json
import random
from pathlib import Path

random.seed(20260520)

# ──────────────────────────────────────────────────────────────────────────────
# 공통 — 학습 system 프롬프트 (학습 데이터와 정확히 동일해야 함)
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = (
    Path(__file__).parent.parent / "app" / "services" / "prompts" / "t2c_v37_system.txt"
).read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# 변수 풀
# ──────────────────────────────────────────────────────────────────────────────

PERSON_NAMES = ["김민준", "이수진", "박서연", "최도윤", "정하은", "강지호", "한예린", "윤재희", "조다영", "송태웅",
                "홍지수", "임건우", "오서영", "권민재", "유시우", "백나연", "황도현", "안수아", "신우진", "구하린"]
ORG_NAMES = ["국민은행", "신한은행", "우리은행", "하나은행", "농협은행", "카카오뱅크", "토스뱅크", "삼성증권", "현대해상", "쿠팡"]
CASE_NOS = ["CASE-2024-001", "CASE-2024-007", "CASE-2024-012", "CASE-2024-023", "CASE-2024-045",
            "2024-사이버-001", "2024-사이버-018", "C-2024-1102", "C-2025-0301", "C-2026-0044"]
PETTN_NOS = ["P2024-1001", "P2024-2050", "P2025-0030", "P2026-0101", "P2026-1301"]
ACCOUNTS = ["110-1111-2222", "302-9988-7766", "1002-110-100001", "1002-220-200002", "352-7788-9900",
            "100-202-333444", "1101-202-303404"]
TELNOS = ["1099999999", "1011112222", "1033445566", "1077778888", "01055443322"]
IPS = ["192.168.1.10", "203.0.113.5", "118.32.45.67", "211.114.22.88", "13.124.55.99"]
SITES = ["https://malicious-site.example", "https://kb-phish.example", "https://kakao-fake.example",
         "https://gov-scam.example", "https://shop-fake.example"]
FILES = ["malware.exe", "trojan.dll", "phishing.html", "dropper.bin", "ransom.zip"]
VEHICLES = ["12가3456", "34나7890", "56다1234", "78라5678", "90마9012"]

ASK_VERBS = ["보여주세요", "찾아주세요", "조회해주세요", "검색해주세요", "추적해주세요", "출력해주세요", "알려주세요"]
LIST_VERBS = ["목록", "전체", "리스트", "전부"]
INFO_VERBS = ["정보", "내역", "데이터", "내용"]


def pick(arr):
    return random.choice(arr)


# ──────────────────────────────────────────────────────────────────────────────
# 시드 빌더 — 카테고리별
# 각 빌더는 (자연어, native_cypher) 튜플 리스트 반환
# ──────────────────────────────────────────────────────────────────────────────

def build_1hop_person2person(n: int):
    """recruits, blackmails, accomplice_of, sameAs, member_of"""
    out = []
    patterns = [
        ("recruits", "공범 모집", "이 모집한 공범"),
        ("blackmails", "협박", "이 협박하는 인물"),
        ("accomplice_of", "공범", "의 공범"),
        ("sameAs", "동일 인물", "과 동일 인물로 식별된"),
    ]
    while len(out) < int(n * 0.7):
        p = pick(PERSON_NAMES)
        rel, kw1, kw2 = pick(patterns)
        v = pick(ASK_VERBS)
        templates = [
            (f"{p}{kw2} 인물을 {v}",
             f"MATCH (p1:vt_psn {{name: '{p}'}})-[:{rel}]->(p2:vt_psn) RETURN p1, p2"),
            (f"{p}{kw2} 사람들의 {pick(INFO_VERBS)}을 {v}",
             f"MATCH (p1:vt_psn {{name: '{p}'}})-[:{rel}]->(p2:vt_psn) RETURN p1, p2"),
            (f"{p}와 {kw1} 관계에 있는 인물 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (p1:vt_psn {{name: '{p}'}})-[r:{rel}]->(p2:vt_psn) RETURN p1, r, p2"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # member_of: vt_psn -> vt_org
    while len(out) < n:
        p, o = pick(PERSON_NAMES), pick(ORG_NAMES)
        v = pick(ASK_VERBS)
        templates = [
            (f"{p}이 소속된 조직을 {v}",
             f"MATCH (p:vt_psn {{name: '{p}'}})-[:member_of]->(o:vt_org) RETURN p, o"),
            (f"{o} 소속 인물 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (p:vt_psn)-[:member_of]->(o:vt_org {{org_name: '{o}'}}) RETURN p, o"),
            (f"{p}이 {o}에 속해있는지 확인해주세요",
             f"MATCH (p:vt_psn {{name: '{p}'}})-[r:member_of]->(o:vt_org {{org_name: '{o}'}}) RETURN p, r, o"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


def build_1hop_case(n: int):
    """suspect_in, victim_in, witness_in, eg_used_account, eg_used_phone, eg_used_ip, related_case, filed_as"""
    out = []
    role_patterns = [
        ("suspect_in", "피의자", "에서 피의자로 등록된", "이 피의자로 연루된"),
        ("victim_in", "피해자", "의 피해자", "이 피해를 입은"),
        ("witness_in", "참고인", "에서 참고인으로 등록된", "이 참고인으로 등장한"),
    ]
    while len(out) < int(n * 0.4):
        rel, role_ko, asc, desc = pick(role_patterns)
        case = pick(CASE_NOS)
        p = pick(PERSON_NAMES)
        v = pick(ASK_VERBS)
        templates = [
            (f"사건 {case}{asc} 인물 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (p:vt_psn)-[:{rel}]->(c:vt_case {{flnm: '{case}'}}) RETURN p, c"),
            (f"{case} 사건의 {role_ko} {pick(INFO_VERBS)}을 {v}",
             f"MATCH (p:vt_psn)-[r:{rel}]->(c:vt_case {{flnm: '{case}'}}) RETURN p, r, c"),
            (f"{p}{desc} 사건을 {v}",
             f"MATCH (p:vt_psn {{name: '{p}'}})-[:{rel}]->(c:vt_case) RETURN p, c"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # eg_used_* (case → object)
    eg_patterns = [
        ("eg_used_account", "vt_bacnt", "account_no", ACCOUNTS, "사용된 계좌"),
        ("eg_used_phone", "vt_telno", "telno", TELNOS, "사용된 전화번호"),
        ("eg_used_ip", "vt_ip", "ip_addr", IPS, "사용된 IP"),
    ]
    while len(out) < int(n * 0.75):
        rel, lbl, key, pool, ko = pick(eg_patterns)
        case = pick(CASE_NOS)
        val = pick(pool)
        v = pick(ASK_VERBS)
        templates = [
            (f"사건 {case}에 {ko} {pick(LIST_VERBS)}을 {v}",
             f"MATCH (c:vt_case {{flnm: '{case}'}})-[:{rel}]->(e:{lbl}) RETURN c, e"),
            (f"{case} 사건의 {ko} {pick(INFO_VERBS)}을 {v}",
             f"MATCH (c:vt_case {{flnm: '{case}'}})-[r:{rel}]->(e:{lbl}) RETURN c, r, e"),
            (f"{val} {ko[:2]}가 사용된 사건을 {v}",
             f"MATCH (c:vt_case)-[:{rel}]->(e:{lbl} {{{key}: '{val}'}}) RETURN c, e"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # related_case (case ↔ case) + filed_as (petition → case)
    while len(out) < int(n * 0.9):
        c1, c2 = random.sample(CASE_NOS, 2)
        v = pick(ASK_VERBS)
        templates = [
            (f"{c1} 사건과 연관된 다른 사건들을 {v}",
             f"MATCH (a:vt_case {{flnm: '{c1}'}})-[:related_case]->(b:vt_case) RETURN a, b"),
            (f"{c1}과 유사한 사건의 {pick(INFO_VERBS)}을 {v}",
             f"MATCH (a:vt_case {{flnm: '{c1}'}})-[r:related_case]->(b:vt_case) RETURN a, r, b"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < n:
        pn = pick(PETTN_NOS)
        v = pick(ASK_VERBS)
        templates = [
            (f"진정서 {pn}이 접수된 사건을 {v}",
             f"MATCH (p:vt_petition {{pettn_no: '{pn}'}})-[:filed_as]->(c:vt_case) RETURN p, c"),
            (f"{pn} 진정서가 어떤 사건으로 등록됐는지 {v}",
             f"MATCH (p:vt_petition {{pettn_no: '{pn}'}})-[r:filed_as]->(c:vt_case) RETURN p, r, c"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


def build_1hop_event(n: int):
    """caller/callee, from_account/to_account, sent_msg/received_msg, accessed_from/to"""
    out = []
    # 통화
    while len(out) < int(n * 0.3):
        t1, t2 = random.sample(TELNOS, 2)
        v = pick(ASK_VERBS)
        templates = [
            (f"전화번호 {t1}이 발신한 통화 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (t:vt_telno {{telno: '{t1}'}})-[:caller]->(call:vt_call) RETURN t, call"),
            (f"{t1}에서 발신한 통화의 수신번호와 함께 {v}",
             f"MATCH (t1:vt_telno {{telno: '{t1}'}})-[:caller]->(call:vt_call)-[:callee]->(t2:vt_telno) RETURN t1, call, t2"),
            (f"전화번호 {t1}이 수신한 통화를 {v}",
             f"MATCH (call:vt_call)-[:callee]->(t:vt_telno {{telno: '{t1}'}}) RETURN call, t"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 이체
    while len(out) < int(n * 0.6):
        a1, a2 = random.sample(ACCOUNTS, 2)
        v = pick(ASK_VERBS)
        templates = [
            (f"계좌 {a1}에서 발생한 이체 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (b:vt_bacnt {{account_no: '{a1}'}})-[:from_account]->(tr:vt_transfer) RETURN b, tr"),
            (f"{a1}에서 {a2}로 이체된 내역을 {v}",
             f"MATCH (b1:vt_bacnt {{account_no: '{a1}'}})-[:from_account]->(tr:vt_transfer)-[:to_account]->(b2:vt_bacnt {{account_no: '{a2}'}}) RETURN b1, tr, b2"),
            (f"계좌 {a1}로 입금된 이체를 {v}",
             f"MATCH (tr:vt_transfer)-[:to_account]->(b:vt_bacnt {{account_no: '{a1}'}}) RETURN tr, b"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 메시지
    while len(out) < int(n * 0.85):
        t1, t2 = random.sample(TELNOS, 2)
        v = pick(ASK_VERBS)
        templates = [
            (f"{t1}이 보낸 메시지 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (t:vt_telno {{telno: '{t1}'}})-[:sent_msg]->(m:vt_msg) RETURN t, m"),
            (f"{t1}에서 {t2}로 전송된 메시지를 {v}",
             f"MATCH (t1:vt_telno {{telno: '{t1}'}})-[:sent_msg]->(m:vt_msg)-[:received_msg]->(t2:vt_telno {{telno: '{t2}'}}) RETURN t1, m, t2"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 접속
    while len(out) < n:
        ip, site = pick(IPS), pick(SITES)
        v = pick(ASK_VERBS)
        templates = [
            (f"IP {ip}에서 접속한 사이트들을 {v}",
             f"MATCH (a:vt_access)-[:accessed_from]->(ip:vt_ip {{ip_addr: '{ip}'}}) WITH a MATCH (a)-[:accessed_to]->(s:vt_site) RETURN a, s"),
            (f"{site} 사이트에 접속한 IP {pick(LIST_VERBS)}을 {v}",
             f"MATCH (a:vt_access)-[:accessed_to]->(s:vt_site {{url_addr: '{site}'}}) WITH a MATCH (a)-[:accessed_from]->(ip:vt_ip) RETURN a, ip, s"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


def build_1hop_object(n: int):
    """registered_to, belongs_to, contains_file, located_at, hosts"""
    out = []
    while len(out) < int(n * 0.3):
        t, p = pick(TELNOS), pick(PERSON_NAMES)
        v = pick(ASK_VERBS)
        templates = [
            (f"전화번호 {t}의 명의자를 {v}",
             f"MATCH (t:vt_telno {{telno: '{t}'}})-[:registered_to]->(p:vt_psn) RETURN t, p"),
            (f"{p} 명의로 등록된 전화번호 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (t:vt_telno)-[:registered_to]->(p:vt_psn {{name: '{p}'}}) RETURN t, p"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.55):
        a, o = pick(ACCOUNTS), pick(ORG_NAMES)
        v = pick(ASK_VERBS)
        templates = [
            (f"계좌 {a}의 소속 은행을 {v}",
             f"MATCH (b:vt_bacnt {{account_no: '{a}'}})-[:belongs_to]->(o:vt_org) RETURN b, o"),
            (f"{o}의 계좌 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (b:vt_bacnt)-[:belongs_to]->(o:vt_org {{org_name: '{o}'}}) RETURN b, o"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.75):
        s, f = pick(SITES), pick(FILES)
        v = pick(ASK_VERBS)
        templates = [
            (f"{s} 사이트에 포함된 파일을 {v}",
             f"MATCH (s:vt_site {{url_addr: '{s}'}})-[:contains_file]->(f:vt_file) RETURN s, f"),
            (f"{f} 파일을 포함한 사이트 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (s:vt_site)-[:contains_file]->(f:vt_file {{file_name: '{f}'}}) RETURN s, f"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.9):
        ip, site = pick(IPS), pick(SITES)
        v = pick(ASK_VERBS)
        templates = [
            (f"IP {ip}이 호스팅하는 사이트를 {v}",
             f"MATCH (ip:vt_ip {{ip_addr: '{ip}'}})-[:hosts]->(s:vt_site) RETURN ip, s"),
            (f"{site} 사이트의 호스팅 IP를 {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site {{url_addr: '{site}'}}) RETURN ip, s"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < n:
        v = pick(ASK_VERBS)
        atm_id = f"ATM{random.randint(1000,9999)}"
        templates = [
            (f"ATM {atm_id}이 설치된 위치를 {v}",
             f"MATCH (a:vt_atm {{atm_id: '{atm_id}'}})-[:located_at]->(l:vt_loc) RETURN a, l"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


def build_1hop_person(n: int):
    """has_account, owns_phone, drives, works_at"""
    out = []
    while len(out) < int(n * 0.4):
        p, a = pick(PERSON_NAMES), pick(ACCOUNTS)
        v = pick(ASK_VERBS)
        templates = [
            (f"{p}의 계좌 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (p:vt_psn {{name: '{p}'}})-[:has_account]->(b:vt_bacnt) RETURN p, b"),
            (f"계좌 {a}의 소유자와 다른 계좌들을 {v}",
             f"MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt {{account_no: '{a}'}}) WITH p MATCH (p)-[:has_account]->(b2:vt_bacnt) RETURN p, b2"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.7):
        p, t = pick(PERSON_NAMES), pick(TELNOS)
        v = pick(ASK_VERBS)
        templates = [
            (f"{p}의 전화번호 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (p:vt_psn {{name: '{p}'}})-[:owns_phone]->(t:vt_telno) RETURN p, t"),
            (f"전화번호 {t}의 소유자 {pick(INFO_VERBS)}을 {v}",
             f"MATCH (p:vt_psn)-[:owns_phone]->(t:vt_telno {{telno: '{t}'}}) RETURN p, t"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.9):
        p, vh = pick(PERSON_NAMES), pick(VEHICLES)
        v = pick(ASK_VERBS)
        templates = [
            (f"{p}이 운전하는 차량을 {v}",
             f"MATCH (p:vt_psn {{name: '{p}'}})-[:drives]->(c:vt_vhcl) RETURN p, c"),
            (f"차량번호 {vh}의 운전자를 {v}",
             f"MATCH (p:vt_psn)-[:drives]->(c:vt_vhcl {{plate_no: '{vh}'}}) RETURN p, c"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < n:
        p, o = pick(PERSON_NAMES), pick(ORG_NAMES)
        v = pick(ASK_VERBS)
        templates = [
            (f"{p}이 근무하는 기관을 {v}",
             f"MATCH (p:vt_psn {{name: '{p}'}})-[:works_at]->(o:vt_org) RETURN p, o"),
            (f"{o}에서 근무하는 인물 {pick(LIST_VERBS)}을 {v}",
             f"MATCH (p:vt_psn)-[:works_at]->(o:vt_org {{org_name: '{o}'}}) RETURN p, o"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────

PLAN = [
    ("1hop_person2person", build_1hop_person2person, 500),
    ("1hop_case",          build_1hop_case,          450),
    ("1hop_event",         build_1hop_event,         400),
    ("1hop_object",        build_1hop_object,        320),
    ("1hop_person",        build_1hop_person,        280),
]


PREFIX_VARIANTS = ["", "혹시 ", "급한데 ", "특히 ", "참고로 ", "확인 차 "]
SUFFIX_VARIANTS = ["", " (긴급)", "", " 부탁드립니다", "", ""]


def diversify(q: str) -> str:
    """자연어 중복 회피를 위한 가벼운 변형."""
    pre = random.choice(PREFIX_VARIANTS)
    suf = random.choice(SUFFIX_VARIANTS)
    return (pre + q + suf).strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/t2c_v38_weakness_train_msg.json")
    parser.add_argument("--report", default="data/t2c_v38_weakness_report.txt")
    args = parser.parse_args()

    all_samples = []
    report_lines = []
    for name, builder, target in PLAN:
        samples = builder(target)
        report_lines.append(f"{name:<22}: {len(samples)} (target {target})")
        for q, c in samples:
            all_samples.append({
                "messages": [
                    {"role": "user", "content": diversify(q)},
                    {"role": "assistant", "content": c},
                ],
                "system": SYSTEM_PROMPT,
                "category": name,
            })

    # 중복 제거 (자연어 기준)
    seen = set()
    deduped = []
    for s in all_samples:
        q = s["messages"][0]["content"]
        if q in seen:
            continue
        seen.add(q)
        deduped.append(s)
    report_lines.append(f"\n총 생성: {len(all_samples)}  중복 제거 후: {len(deduped)}")

    random.shuffle(deduped)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")

    report = "\n".join(report_lines)
    Path(args.report).write_text(report + "\n", encoding="utf-8")

    print(report)
    print(f"\n저장: {out_path} ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
