"""
build_v39_weakness_seed.py — v38 잔여 약점 카테고리 1,500 시드 보강

근거 (TEXT2CYPHER_V37_EVAL_REPORT.md §7.2, v38 벤치마크):
  - meta_condition  40% (변화 없음, 시드 0) → 목표 75%+
  - 1hop_object     60% (시드 311 부족)    → 목표 80%+
  - chain           60% (멀티홉 시드 부족)  → 목표 80%+
  - threat_filter   50% (위협 필터 시드)    → 목표 80%+

출력: data/t2c_v39_weakness_train_msg.json (OpenAI messages format)
사용: python data/build_v39_weakness_seed.py
"""
import argparse
import json
import random
from pathlib import Path

random.seed(20260521)

SYSTEM_PROMPT = (
    Path(__file__).parent.parent / "app" / "services" / "prompts" / "t2c_v37_system.txt"
).read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# 변수 풀
# ──────────────────────────────────────────────────────────────────────────────

PERSON_NAMES = ["김민준", "이수진", "박서연", "최도윤", "정하은", "강지호", "한예린", "윤재희",
                "조다영", "송태웅", "홍지수", "임건우", "오서영", "권민재", "유시우", "백나연"]
ORG_NAMES = ["국민은행", "신한은행", "우리은행", "하나은행", "농협은행", "카카오뱅크",
             "토스뱅크", "삼성증권", "현대해상"]
CASE_NOS = ["CASE-2024-001", "CASE-2024-007", "CASE-2024-012", "CASE-2024-023",
            "2024-사이버-001", "C-2025-0301", "C-2026-0044"]
ACCOUNTS = ["110-1111-2222", "302-9988-7766", "1002-110-100001", "352-7788-9900"]
TELNOS = ["1099999999", "1011112222", "1033445566", "1077778888"]
IPS = ["192.168.1.10", "203.0.113.5", "118.32.45.67", "211.114.22.88"]
SITES = ["https://malicious-site.example", "https://kb-phish.example", "https://kakao-fake.example"]
FILES = ["malware.exe", "trojan.dll", "phishing.html", "dropper.bin"]
LOCS = ["서울 강남구", "부산 해운대구", "인천 송도", "대전 유성구"]

ASK = ["보여주세요", "찾아주세요", "조회해주세요", "검색해주세요", "추적해주세요", "출력해주세요"]
LIST_S = ["목록", "전체", "리스트", "전부"]
PRE = ["", "혹시 ", "급한데 ", "특히 ", "참고로 ", "확인 차 "]
SUF = ["", " (긴급)", "", " 부탁드립니다", ""]

THREAT_SCORES = [70, 80, 90, 95]
RISK_LEVELS = ['HIGH', 'MEDIUM', 'LOW']
TIERS = [1, 2, 3, 4]
CONFIDENCES = [0.7, 0.8, 0.9, 0.95]


def pick(arr):
    return random.choice(arr)


def diversify(q: str) -> str:
    return (pick(PRE) + q + pick(SUF)).strip()


# ──────────────────────────────────────────────────────────────────────────────
# meta_condition (500개) — WHERE 절 + 메타 속성 (tier, confidence, role, 시간 등)
# ──────────────────────────────────────────────────────────────────────────────

def build_meta_condition(n: int):
    out = []
    # G1: tier 기반 필터
    while len(out) < int(n * 0.25):
        t = pick(TIERS)
        v = pick(ASK)
        templates = [
            (f"신뢰도 tier {t} 이상인 출처에서 수집한 계좌 {pick(LIST_S)}을 {v}",
             f"MATCH (b:vt_bacnt)-[:sourced_from]->(s:vt_src) WHERE s.reliability_tier <= {t} RETURN b, s"),
            (f"tier {t} 출처의 인물 노드를 {v}",
             f"MATCH (p:vt_psn)-[:sourced_from]->(s:vt_src {{reliability_tier: {t}}}) RETURN p, s"),
            (f"OSINT(tier 4) 데이터에서 수집한 사이트들을 {v}",
             f"MATCH (site:vt_site)-[:sourced_from]->(s:vt_src) WHERE s.reliability_tier = 4 RETURN site, s"),
            (f"공식(tier 1~2) 출처의 전화번호 {pick(LIST_S)}을 {v}",
             f"MATCH (t:vt_telno)-[:sourced_from]->(s:vt_src) WHERE s.reliability_tier <= 2 RETURN t, s"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # G2: 금액/수치 임계값 필터
    while len(out) < int(n * 0.45):
        amt = random.choice([10000000, 50000000, 100000000, 500000000])
        v = pick(ASK)
        templates = [
            (f"피해금액 {amt:,}원 이상인 사건 {pick(LIST_S)}을 {v}",
             f"MATCH (c:vt_case) WHERE c.damage_amount >= {amt} RETURN c"),
            (f"이체금액 {amt:,}원 이상의 거래를 {v}",
             f"MATCH (t:vt_transfer) WHERE (t.amount)::int >= {amt} RETURN t"),
            (f"{amt:,}원 이상 출금한 계좌와 이체 내역을 {v}",
             f"MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer) WHERE (t.amount)::int >= {amt} RETURN b, t"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # G3: 신뢰도(confidence) 속성 필터 (엣지 속성)
    while len(out) < int(n * 0.6):
        conf = pick(CONFIDENCES)
        v = pick(ASK)
        templates = [
            (f"confidence {conf} 이상의 mentions_account 메시지를 {v}",
             f"MATCH (m:vt_msg)-[r:mentions_account]->(b:vt_bacnt) WHERE r.confidence >= {conf} RETURN m, r, b"),
            (f"공범 관계 중 신뢰도 {conf} 이상인 쌍을 {v}",
             f"MATCH (p1:vt_psn)-[r:accomplice_of]->(p2:vt_psn) WHERE r.confidence >= {conf} RETURN p1, r, p2"),
            (f"신뢰도 {conf} 이상인 사칭 사용 관계를 {v}",
             f"MATCH (t:vt_telno)-[r:used_for]->(imp:vt_impersonation) WHERE r.confidence >= {conf} RETURN t, r, imp"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # G4: 시간 기간 필터
    while len(out) < int(n * 0.8):
        date = pick(['2026-01-01', '2026-03-01', '2026-04-01', '2025-12-01'])
        v = pick(ASK)
        templates = [
            (f"{date} 이후 발생한 통화 기록을 {v}",
             f"MATCH (call:vt_call) WHERE call.call_dt >= '{date}' RETURN call"),
            (f"{date} 이후 접수된 진정서 {pick(LIST_S)}을 {v}",
             f"MATCH (p:vt_petition) WHERE p.rcpt_dt >= '{date}' RETURN p"),
            (f"{date} 이후 수집된 사이트들을 {v}",
             f"MATCH (s:vt_site)-[:sourced_from]->(src:vt_src) WHERE src.collected_at >= '{date}' RETURN s, src"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # G5: enum/플래그 필터
    while len(out) < n:
        v = pick(ASK)
        templates = [
            (f"is_burner=true인 대포통장 {pick(LIST_S)}을 {v}",
             f"MATCH (b:vt_bacnt {{is_burner: true}}) RETURN b"),
            (f"is_burner=true인 대포폰을 {v}",
             f"MATCH (t:vt_telno {{is_burner: true}}) RETURN t"),
            (f"is_malicious=true인 사이트 {pick(LIST_S)}을 {v}",
             f"MATCH (s:vt_site {{is_malicious: true}}) RETURN s"),
            (f"is_active=false인 계정을 {v}",
             f"MATCH (id:vt_id {{is_active: false}}) RETURN id"),
            (f"is_vpn=true인 IP {pick(LIST_S)}을 {v}",
             f"MATCH (ip:vt_ip {{is_vpn: true}}) RETURN ip"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# threat_filter (300개) — 위협 점수/플래그 + 1~2hop
# ──────────────────────────────────────────────────────────────────────────────

def build_threat_filter(n: int):
    out = []
    while len(out) < int(n * 0.3):
        score = pick(THREAT_SCORES)
        v = pick(ASK)
        templates = [
            (f"위협점수 {score} 이상인 IP {pick(LIST_S)}을 {v}",
             f"MATCH (ip:vt_ip) WHERE ip.threat_score >= {score} RETURN ip"),
            (f"위협점수 {score} 이상인 IP가 호스팅하는 사이트를 {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) WHERE ip.threat_score >= {score} RETURN ip, s"),
            (f"위협점수 {score}점 이상 IP와 통신한 다른 IP를 {v}",
             f"MATCH (ip1:vt_ip)-[:communicated_with]->(ip2:vt_ip) WHERE ip1.threat_score >= {score} RETURN ip1, ip2"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.55):
        risk = pick(RISK_LEVELS)
        v = pick(ASK)
        templates = [
            (f"위험도 {risk}인 피의자 {pick(LIST_S)}을 {v}",
             f"MATCH (p:vt_psn {{risk_level: '{risk}'}}) RETURN p"),
            (f"위험도 {risk} 피의자가 소유한 대포폰을 {v}",
             f"MATCH (p:vt_psn {{risk_level: '{risk}'}})-[:owns_phone]->(t:vt_telno {{is_burner: true}}) RETURN p, t"),
            (f"위험도 {risk} 피의자의 대포통장 계좌를 {v}",
             f"MATCH (p:vt_psn {{risk_level: '{risk}'}})-[:has_account]->(b:vt_bacnt {{is_burner: true}}) RETURN p, b"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.8):
        v = pick(ASK)
        templates = [
            (f"대포통장이면서 동결된 계좌 {pick(LIST_S)}을 {v}",
             f"MATCH (b:vt_bacnt {{is_burner: true, is_frozen: true}}) RETURN b"),
            (f"악성 파일을 포함한 피싱 사이트들을 {v}",
             f"MATCH (s:vt_site {{is_malicious: true}})-[:contains_file]->(f:vt_file {{is_malicious: true}}) RETURN s, f"),
            (f"VPN IP가 접속한 악성 사이트를 {v}",
             f"MATCH (a:vt_access)-[:accessed_from]->(ip:vt_ip {{is_vpn: true}}) WITH a MATCH (a)-[:accessed_to]->(s:vt_site {{is_malicious: true}}) RETURN a, ip, s"),
            (f"해외 VPN IP 중 위협점수 80 이상인 IP를 {v}",
             f"MATCH (ip:vt_ip {{is_vpn: true}}) WHERE ip.country <> 'KR' AND ip.threat_score >= 80 RETURN ip"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < n:
        score = pick(THREAT_SCORES)
        v = pick(ASK)
        templates = [
            (f"악성 사이트를 호스팅하는 해외 IP {pick(LIST_S)}을 {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site {{is_malicious: true}}) WHERE ip.country <> 'KR' RETURN ip, s"),
            (f"abuse_score {score} 이상 IP에서 접속한 사이트를 {v}",
             f"MATCH (a:vt_access)-[:accessed_from]->(ip:vt_ip) WHERE ip.abuse_score >= {score} WITH a MATCH (a)-[:accessed_to]->(s:vt_site) RETURN a, ip, s"),
            (f"대포폰으로 금융기관을 사칭한 사례를 {v}",
             f"MATCH (t:vt_telno {{is_burner: true}})-[:used_for]->(imp:vt_impersonation)-[:targets]->(o:vt_org) RETURN t, imp, o"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# chain (400개) — 2~3hop 추적 흐름
# ──────────────────────────────────────────────────────────────────────────────

def build_chain(n: int):
    out = []
    # 자금 흐름 체인
    while len(out) < int(n * 0.3):
        p = pick(PERSON_NAMES)
        v = pick(ASK)
        templates = [
            (f"{p}의 계좌에서 출발한 이체 흐름을 {v}",
             f"MATCH (p:vt_psn {{name: '{p}'}})-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b2:vt_bacnt) RETURN p, b, t, b2"),
            (f"{p}이 받은 이체와 송금 계좌를 {v}",
             f"MATCH (p:vt_psn {{name: '{p}'}})-[:has_account]->(b:vt_bacnt)<-[:to_account]-(t:vt_transfer)<-[:from_account]-(b2:vt_bacnt) RETURN p, b, t, b2"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 통신 체인
    while len(out) < int(n * 0.5):
        p = pick(PERSON_NAMES)
        v = pick(ASK)
        templates = [
            (f"{p} 명의 전화로 발신한 통화의 수신번호를 {v}",
             f"MATCH (p:vt_psn {{name: '{p}'}})-[:owns_phone]->(t1:vt_telno)-[:caller]->(call:vt_call)-[:callee]->(t2:vt_telno) RETURN p, t1, call, t2"),
            (f"{p}이 보낸 메시지의 수신자 전화번호를 {v}",
             f"MATCH (p:vt_psn {{name: '{p}'}})-[:owns_phone]->(t1:vt_telno)-[:sent_msg]->(m:vt_msg)-[:received_msg]->(t2:vt_telno) RETURN p, t1, m, t2"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 사이트→IP→파일 인프라 체인
    while len(out) < int(n * 0.7):
        site = pick(SITES)
        v = pick(ASK)
        templates = [
            (f"{site} 사이트가 호스팅된 IP와 그 IP가 호스팅하는 다른 악성 사이트를 {v}",
             f"MATCH (s1:vt_site {{url_addr: '{site}'}})<-[:hosts]-(ip:vt_ip)-[:hosts]->(s2:vt_site) WHERE s1 <> s2 RETURN s1, ip, s2"),
            (f"IP에서 호스팅된 사이트의 악성 파일을 {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site)-[:contains_file]->(f:vt_file) WHERE f.is_malicious = true RETURN ip, s, f"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 사건→증거→객체 체인
    while len(out) < int(n * 0.9):
        case = pick(CASE_NOS)
        v = pick(ASK)
        templates = [
            (f"{case} 사건에 사용된 계좌와 그 계좌의 이체 흐름을 {v}",
             f"MATCH (c:vt_case {{flnm: '{case}'}})-[:eg_used_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer) RETURN c, b, t"),
            (f"{case} 사건의 피의자와 그 피의자의 계좌를 {v}",
             f"MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case {{flnm: '{case}'}}) WITH p MATCH (p)-[:has_account]->(b:vt_bacnt) RETURN p, c, b"),
            (f"{case} 사건에 사용된 IP가 접속한 악성 사이트를 {v}",
             f"MATCH (c:vt_case {{flnm: '{case}'}})-[:eg_used_ip]->(ip:vt_ip)<-[:accessed_from]-(a:vt_access)-[:accessed_to]->(s:vt_site) RETURN c, ip, a, s"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # shortestPath
    while len(out) < n:
        p1, p2 = random.sample(PERSON_NAMES, 2)
        v = pick(ASK)
        templates = [
            (f"{p1}과 {p2}의 최단 연결 경로를 {v}",
             f"MATCH p=shortestPath((a:vt_psn {{name: '{p1}'}})-[*..6]-(b:vt_psn {{name: '{p2}'}})) RETURN p"),
            (f"{p1}과 {p2}이 어떻게 연결되어 있는지 추적해주세요",
             f"MATCH p=shortestPath((a:vt_psn {{name: '{p1}'}})-[*..6]-(b:vt_psn {{name: '{p2}'}})) RETURN p"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# 1hop_object 추가 (300개) — hosts/belongs_to/contains_file/located_at/resolves_to
# ──────────────────────────────────────────────────────────────────────────────

def build_1hop_object_extra(n: int):
    out = []
    # hosts (IP→Site)
    while len(out) < int(n * 0.3):
        ip, site = pick(IPS), pick(SITES)
        v = pick(ASK)
        templates = [
            (f"IP {ip}에 호스팅된 사이트 {pick(LIST_S)}을 {v}",
             f"MATCH (ip:vt_ip {{ip_addr: '{ip}'}})-[:hosts]->(s:vt_site) RETURN ip, s"),
            (f"{site} 사이트를 호스팅하는 IP를 {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site {{url_addr: '{site}'}}) RETURN ip, s"),
            (f"피싱 사이트의 호스팅 IP를 역추적해 {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site {{is_malicious: true}}) RETURN ip, s"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # contains_file
    while len(out) < int(n * 0.55):
        site, f = pick(SITES), pick(FILES)
        v = pick(ASK)
        templates = [
            (f"{site} 사이트에 포함된 악성 파일들을 {v}",
             f"MATCH (s:vt_site {{url_addr: '{site}'}})-[:contains_file]->(f:vt_file) RETURN s, f"),
            (f"{f} 파일을 포함한 사이트 {pick(LIST_S)}을 {v}",
             f"MATCH (s:vt_site)-[:contains_file]->(f:vt_file {{file_nm: '{f}'}}) RETURN s, f"),
            (f"메시지에 첨부된 악성 파일을 {v}",
             f"MATCH (m:vt_msg)-[:contains_file]->(f:vt_file {{is_malicious: true}}) RETURN m, f"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # belongs_to
    while len(out) < int(n * 0.75):
        a, o = pick(ACCOUNTS), pick(ORG_NAMES)
        v = pick(ASK)
        templates = [
            (f"계좌 {a}의 소속 금융기관을 {v}",
             f"MATCH (b:vt_bacnt {{account_no: '{a}'}})-[:belongs_to]->(o:vt_org) RETURN b, o"),
            (f"{o} 소속 계좌 {pick(LIST_S)}을 {v}",
             f"MATCH (b:vt_bacnt)-[:belongs_to]->(o:vt_org {{org_name: '{o}'}}) RETURN b, o"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # located_at / resolves_to
    while len(out) < int(n * 0.9):
        loc = pick(LOCS)
        v = pick(ASK)
        atm_id = f"ATM{random.randint(1000,9999)}"
        templates = [
            (f"{loc} 지역에 위치한 ATM {pick(LIST_S)}을 {v}",
             f"MATCH (a:vt_atm)-[:located_at]->(l:vt_loc {{address: '{loc}'}}) RETURN a, l"),
            (f"ATM {atm_id}의 설치 위치를 {v}",
             f"MATCH (a:vt_atm {{atm_id: '{atm_id}'}})-[:located_at]->(l:vt_loc) RETURN a, l"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # resolves_to (vt_site → vt_ip)
    while len(out) < n:
        site = pick(SITES)
        v = pick(ASK)
        templates = [
            (f"{site} 사이트의 DNS IP를 {v}",
             f"MATCH (s:vt_site {{url_addr: '{site}'}})-[:resolves_to]->(ip:vt_ip) RETURN s, ip"),
            (f"피싱 사이트가 해소된 IP {pick(LIST_S)}을 {v}",
             f"MATCH (s:vt_site {{is_malicious: true}})-[:resolves_to]->(ip:vt_ip) RETURN s, ip"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────

PLAN = [
    ("meta_condition",   build_meta_condition,       600),  # 가장 약한 카테고리
    ("threat_filter",    build_threat_filter,        350),
    ("chain",            build_chain,                450),
    ("1hop_object_extra",build_1hop_object_extra,    350),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/t2c_v39_weakness_train_msg.json")
    parser.add_argument("--report", default="data/t2c_v39_weakness_report.txt")
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
    Path(args.report).write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("\n".join(report_lines))
    print(f"\n저장: {out_path} ({out_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
