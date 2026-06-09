"""
build_v41_weakness_seed.py — v40 회귀 카테고리 850 시드 보강
============================================================
근거 (v40 × 232문항 측정, 2026-05-27):
  - 1hop_person2person: 80% → 60% (-20p 회귀) → 시드 300 보강
  - meta_condition:     67% → 53% (-14p 회귀) → 시드 300 보강
  - 1hop_event:         60% → 67% (정체) → 시드 150 추가
  - chain (3-hop+):     80% → 시드 100 추가 (1hop→2hop→3hop 점진)

총 850 시드. 베이스: t2c_v40_train_msg.json (33,242) → 34,092

출력: data/t2c_v41_weakness_train_msg.json (OpenAI messages format)
사용: python data/build_v41_weakness_seed.py
"""
import argparse
import json
import random
from pathlib import Path

random.seed(20260527)

SYSTEM_PROMPT = (
    Path(__file__).parent.parent / "app" / "services" / "prompts" / "t2c_v37_system.txt"
).read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# 변수 풀
# ──────────────────────────────────────────────────────────────────────────────
PERSON_NAMES = ["김민준", "이수진", "박서연", "최도윤", "정하은", "강지호", "한예린", "윤재희",
                "조다영", "송태웅", "홍지수", "임건우", "오서영", "권민재", "유시우", "백나연",
                "총책", "관리책", "행동책", "수금책", "총무", "팀장", "실장", "대표"]
ROLE_KOR = ["총책", "관리책", "행동책", "수금책", "콜센터팀장", "콜센터팀원", "현금책",
            "환전책", "조직원", "보스", "넘버2", "넘버3"]
ORG_NAMES = ["국민은행", "신한은행", "우리은행", "하나은행", "검찰청", "경찰청",
             "보이스피싱조직A", "보이스피싱조직B", "범죄단체알파", "범죄단체베타"]
CASE_NOS = ["CASE-2024-001", "CASE-2024-007", "CASE-2025-0301", "2024-사이버-001",
            "C-2025-0301", "C-2026-0044", "C-2026-A-001", "C-2026-A-002"]

RISK_LEVELS = ['HIGH', 'MEDIUM', 'LOW']
THREAT_SCORES = [50, 60, 70, 80, 85, 90, 95]
EVID_GRADES = ['A', 'B', 'C']
AMOUNTS = [500000, 1000000, 3000000, 5000000, 10000000, 50000000, 100000000]
TIERS = [1, 2, 3, 4]
DOMAINS_RDB = ['KICS', 'OSINT', 'DIGITAL', 'EXT']
RDB_TO_CODE = {'KICS': 'investigation', 'OSINT': 'osint',
               'DIGITAL': 'partner', 'EXT': 'partner'}

ASK = ["보여주세요", "찾아주세요", "조회해주세요", "검색해주세요", "추적해주세요", "출력해주세요", "알려주세요"]
LIST_S = ["목록", "전체", "리스트", "전부"]
PRE = ["", "혹시 ", "급한데 ", "특히 ", "참고로 ", "확인 차 ", "정확히 "]
SUF = ["", " 부탁드립니다", "", " (긴급)", "", " 부탁드려요"]


def pick(arr):
    return random.choice(arr)


def diversify(q: str) -> str:
    return (pick(PRE) + q + pick(SUF)).strip()


# ──────────────────────────────────────────────────────────────────────────────
# A. 1hop_person2person 보강 (300 시드)
# ──────────────────────────────────────────────────────────────────────────────
# 회귀 원인 추정: recruits/blackmails/accomplice_of 의 방향성 / 역할 분기 학습 부족
def build_person2person(n=300):
    out = []

    # recruits (총책 → 조직원) — 가장 비중 크게
    while len(out) < int(n * 0.30):
        boss, member = pick(PERSON_NAMES[:8]), pick(PERSON_NAMES[8:])
        v = pick(ASK)
        templates = [
            (f"{boss}이 모집한 조직원 {pick(LIST_S)}을 {v}",
             f"MATCH (b:vt_psn {{name: '{boss}'}})-[:recruits]->(m:vt_psn) RETURN b, m"),
            (f"{member}을 모집한 총책을 {v}",
             f"MATCH (b:vt_psn)-[:recruits]->(m:vt_psn {{name: '{member}'}}) RETURN b, m"),
            (f"보이스피싱 조직의 모집 계층 구조를 {v}",
             "MATCH (b:vt_psn)-[:recruits]->(m:vt_psn) RETURN b, m"),
            (f"{boss}이 영입한 부하 조직원 {pick(LIST_S)}을 {v}",
             f"MATCH (b:vt_psn {{name: '{boss}'}})-[:recruits]->(m:vt_psn) RETURN b, m"),
            (f"총책이 모집한 행동책 {pick(LIST_S)}을 {v}",
             "MATCH (b:vt_psn {role_cd: '총책'})-[:recruits]->(m:vt_psn) RETURN b, m"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # accomplice_of (양방향 공범 관계)
    while len(out) < int(n * 0.50):
        a, b = pick(PERSON_NAMES), pick(PERSON_NAMES)
        v = pick(ASK)
        templates = [
            (f"{a}의 공범 {pick(LIST_S)}을 {v}",
             f"MATCH (p:vt_psn {{name: '{a}'}})-[:accomplice_of]-(o:vt_psn) RETURN p, o"),
            (f"피의자 {a}와 공범관계인 인물을 {v}",
             f"MATCH (p:vt_psn {{name: '{a}'}})-[:accomplice_of]-(o:vt_psn) RETURN p, o"),
            (f"공범 네트워크 전체를 {v}",
             "MATCH (p:vt_psn)-[:accomplice_of]-(o:vt_psn) RETURN p, o"),
            (f"수사 대상자 공범관계 {v}",
             "MATCH (p:vt_psn {role_cd: 'suspect'})-[:accomplice_of]-(o:vt_psn) RETURN p, o"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # blackmails (협박)
    while len(out) < int(n * 0.65):
        a, b = pick(PERSON_NAMES), pick(PERSON_NAMES)
        v = pick(ASK)
        templates = [
            (f"{a}이 협박한 피해자 {pick(LIST_S)}을 {v}",
             f"MATCH (s:vt_psn {{name: '{a}'}})-[:blackmails]->(v:vt_psn) RETURN s, v"),
            (f"{b}을 협박한 가해자를 {v}",
             f"MATCH (s:vt_psn)-[:blackmails]->(v:vt_psn {{name: '{b}'}}) RETURN s, v"),
            (f"협박 사건의 가해자→피해자 관계 {pick(LIST_S)}을 {v}",
             "MATCH (s:vt_psn)-[:blackmails]->(v:vt_psn) RETURN s, v"),
            (f"보이스피싱 협박 관계 전체를 {v}",
             "MATCH (s:vt_psn)-[:blackmails]->(v:vt_psn) RETURN s, v"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # sameAs (동일인물)
    while len(out) < int(n * 0.82):
        a = pick(PERSON_NAMES)
        v = pick(ASK)
        templates = [
            (f"{a}과 동일인물로 추정되는 별명/계정을 {v}",
             f"MATCH (p:vt_psn {{name: '{a}'}})-[:sameAs]-(o:vt_psn) RETURN p, o"),
            (f"동일인물 매칭 {pick(LIST_S)}을 {v}",
             "MATCH (p:vt_psn)-[:sameAs]-(o:vt_psn) RETURN p, o"),
            (f"OSINT 닉네임 ↔ 실명 매칭 {v}",
             "MATCH (p:vt_psn {is_anonymous: true})-[:sameAs]-(o:vt_psn {is_anonymous: false}) RETURN p, o"),
            (f"익명 사용자와 실명 매칭 {v}",
             "MATCH (anon:vt_psn {is_anonymous: true})-[:sameAs]-(real:vt_psn {is_anonymous: false}) RETURN anon, real"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # member_of (조직 소속)
    while len(out) < n:
        org = pick(ORG_NAMES)
        v = pick(ASK)
        templates = [
            (f"{org} 소속 조직원 {pick(LIST_S)}을 {v}",
             f"MATCH (p:vt_psn)-[:member_of]->(o:vt_org {{org_nm: '{org}'}}) RETURN p, o"),
            (f"조직원 → 조직 소속 관계 {v}",
             "MATCH (p:vt_psn)-[:member_of]->(o:vt_org) RETURN p, o"),
            (f"{org} 멤버십 분석 {v}",
             f"MATCH (p:vt_psn)-[:member_of]->(o:vt_org {{org_nm: '{org}'}}) RETURN p.name, p.role_cd, o.org_nm"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# B. meta_condition 보강 (300 시드)
# ──────────────────────────────────────────────────────────────────────────────
# 회귀 원인 추정: 다양한 메타 속성 (risk_level/threat_score/evid_grade/is_*) 학습 부족
def build_meta_condition(n=300):
    out = []

    # risk_level
    while len(out) < int(n * 0.18):
        rl = pick(RISK_LEVELS)
        v = pick(ASK)
        templates = [
            (f"위험도 {rl}인 피의자 {pick(LIST_S)}을 {v}",
             f"MATCH (p:vt_psn) WHERE p.risk_level = '{rl}' RETURN p"),
            (f"위험도 HIGH 또는 MEDIUM 인 인물 {v}",
             "MATCH (p:vt_psn) WHERE p.risk_level IN ['HIGH','MEDIUM'] RETURN p"),
            (f"고위험 피의자가 보유한 계좌 {v}",
             "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) WHERE p.risk_level = 'HIGH' RETURN p, b"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # threat_score
    while len(out) < int(n * 0.35):
        ts = pick(THREAT_SCORES)
        v = pick(ASK)
        templates = [
            (f"위협점수 {ts} 이상인 IP {pick(LIST_S)}을 {v}",
             f"MATCH (ip:vt_ip) WHERE ip.threat_score >= {ts} RETURN ip"),
            (f"위협점수 {ts} 이상인 사이트 {v}",
             f"MATCH (s:vt_site) WHERE s.threat_score >= {ts} RETURN s"),
            (f"위협점수 80 이상 IP 가 접속한 사이트 {v}",
             "MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) WHERE ip.threat_score >= 80 RETURN ip, s"),
            (f"고위협 IP 전체를 {v}",
             "MATCH (ip:vt_ip) WHERE ip.threat_score >= 90 RETURN ip"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # evid_grade
    while len(out) < int(n * 0.5):
        gr = pick(EVID_GRADES)
        v = pick(ASK)
        templates = [
            (f"증거등급 {gr}인 이체 {pick(LIST_S)}을 {v}",
             f"MATCH (t:vt_transfer) WHERE t.evid_grade = '{gr}' RETURN t"),
            (f"등급 A 증거가 있는 사건 {v}",
             "MATCH (c:vt_case) WHERE c.evid_grade = 'A' RETURN c"),
            (f"고급 증거(A등급) 자료 전체를 {v}",
             "MATCH (n) WHERE n.evid_grade = 'A' RETURN n"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # is_burner / is_vpn / is_malicious (bool flags)
    while len(out) < int(n * 0.7):
        v = pick(ASK)
        templates = [
            (f"대포통장 {pick(LIST_S)}을 {v}",
             "MATCH (b:vt_bacnt) WHERE b.is_burner = true RETURN b"),
            (f"대포폰 전체를 {v}",
             "MATCH (t:vt_telno) WHERE t.is_burner = true RETURN t"),
            (f"VPN 사용 IP 를 {v}",
             "MATCH (ip:vt_ip) WHERE ip.is_vpn = true RETURN ip"),
            (f"악성 사이트 전체를 {v}",
             "MATCH (s:vt_site) WHERE s.is_malicious = true RETURN s"),
            (f"VPN 으로 접속한 악성 사이트 {v}",
             "MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) WHERE ip.is_vpn = true AND s.is_malicious = true RETURN ip, s"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 금액/시간 임계
    while len(out) < int(n * 0.85):
        amt = pick(AMOUNTS)
        v = pick(ASK)
        man = f"{amt//10000}만원" if amt < 100000000 else f"{amt//100000000}억"
        templates = [
            (f"피해금액 {man} 이상 사건 {v}",
             f"MATCH (c:vt_case) WHERE c.damage_amount >= {amt} RETURN c"),
            (f"이체 금액 {man} 이상 거래 {v}",
             f"MATCH (t:vt_transfer) WHERE t.amount >= {amt} RETURN t"),
            (f"통화 시간 5분(300초) 이상 {v}",
             "MATCH (c:vt_call) WHERE c.duration >= 300 RETURN c"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 복합 메타 (V4.0 + 임계)
    while len(out) < n:
        v = pick(ASK)
        rdb = pick(DOMAINS_RDB); dom = RDB_TO_CODE[rdb]
        amt = pick(AMOUNTS)
        templates = [
            (f"{rdb} 출처면서 위험도 HIGH 인 인물 {v}",
             f"MATCH (p:vt_psn) WHERE p.source_domain = '{dom}' AND p.risk_level = 'HIGH' RETURN p"),
            (f"고위협 IP가 호스팅하는 OSINT 사이트 {v}",
             "MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) WHERE ip.threat_score >= 80 AND s.source_domain = 'osint' RETURN ip, s"),
            (f"증거등급 A이면서 금액 {amt} 이상 이체 {v}",
             f"MATCH (t:vt_transfer) WHERE t.evid_grade = 'A' AND t.amount >= {amt} RETURN t"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# C. 1hop_event 보강 (150 시드)
# ──────────────────────────────────────────────────────────────────────────────
# 회귀 원인 추정: caller/callee 방향, from_account/to_account 방향 학습 부족
def build_1hop_event(n=150):
    out = []
    TELNOS = ["01012345678", "01098765432", "01055443322", "01077778888"]
    ACCTS = ["110-1111-2222", "302-9988-7766", "1002-110-100001"]

    # caller / callee 방향
    while len(out) < int(n * 0.4):
        t = pick(TELNOS)
        v = pick(ASK)
        templates = [
            (f"{t} 가 발신한 통화 {pick(LIST_S)}을 {v}",
             f"MATCH (telno:vt_telno {{telno: '{t}'}})-[:caller]->(c:vt_call) RETURN telno, c"),
            (f"{t} 로 수신된 통화 {v}",
             f"MATCH (c:vt_call)-[:callee]->(telno:vt_telno {{telno: '{t}'}}) RETURN c, telno"),
            (f"발신 통화 전체 {v}",
             "MATCH (t:vt_telno)-[:caller]->(c:vt_call) RETURN t, c"),
            (f"수신 통화 전체 {v}",
             "MATCH (c:vt_call)-[:callee]->(t:vt_telno) RETURN c, t"),
            (f"통화 한 양쪽 번호 {v}",
             "MATCH (a:vt_telno)-[:caller]->(c:vt_call)-[:callee]->(b:vt_telno) RETURN a, c, b"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # from_account / to_account 방향
    while len(out) < int(n * 0.75):
        a = pick(ACCTS)
        v = pick(ASK)
        templates = [
            (f"{a} 계좌에서 출금된 이체 {v}",
             f"MATCH (b:vt_bacnt {{account_no: '{a}'}})-[:from_account]->(t:vt_transfer) RETURN b, t"),
            (f"{a} 계좌로 입금된 이체 {v}",
             f"MATCH (t:vt_transfer)-[:to_account]->(b:vt_bacnt {{account_no: '{a}'}}) RETURN t, b"),
            (f"계좌 간 자금 흐름 {v}",
             "MATCH (a:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b:vt_bacnt) RETURN a, t, b"),
            (f"입출금 양방향 모두 {v}",
             "MATCH (a:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b:vt_bacnt) RETURN a, t, b"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 접속/이벤트
    while len(out) < n:
        v = pick(ASK)
        templates = [
            (f"사이트 접속 이벤트 전체 {v}",
             "MATCH (a:vt_access)-[:accessed]->(s:vt_site) RETURN a, s"),
            (f"메시지 발송 이벤트 {v}",
             "MATCH (m:vt_msg) RETURN m"),
            (f"사이트와 IP 접속 관계 {v}",
             "MATCH (a:vt_access)-[:accessed]->(s:vt_site) RETURN a, s"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# D. chain (3-hop+) 보강 (100 시드)
# ──────────────────────────────────────────────────────────────────────────────
def build_chain(n=100):
    out = []
    while len(out) < int(n * 0.35):
        v = pick(ASK)
        templates = [
            (f"사건의 피의자가 보유한 계좌의 이체 흐름 {v}",
             "MATCH (c:vt_case)<-[:suspect_in]-(p:vt_psn)-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer) RETURN c, p, b, t"),
            (f"사건→피의자→전화→통화 흐름 {v}",
             "MATCH (c:vt_case)<-[:suspect_in]-(p:vt_psn)-[:owns_phone]->(t:vt_telno)-[:caller]->(call:vt_call) RETURN c, p, t, call"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.65):
        v = pick(ASK)
        templates = [
            (f"피의자→계좌→이체→수신계좌 4-hop 흐름 {v}",
             "MATCH (p:vt_psn)-[:has_account]->(a:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b:vt_bacnt) RETURN p, a, t, b"),
            (f"4단계 자금흐름 추적 {v}",
             "MATCH (p:vt_psn)-[:has_account]->(a:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b:vt_bacnt) RETURN p, a, t, b"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < n:
        v = pick(ASK)
        templates = [
            (f"pt_cluster→피의자→계좌→이체 4-hop {v}",
             "MATCH (pc:pt_cluster)<-[:belongs_to_cluster]-(p:vt_psn)-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer) RETURN pc, p, b, t"),
            (f"캠페인 클러스터의 자금흐름 종단 {v}",
             "MATCH (pc:pt_cluster)<-[:belongs_to_cluster]-(p:vt_psn)-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer) RETURN pc, p, b, t"),
            (f"site_cluster→사이트→IP 추적 {v}",
             "MATCH (sc:site_cluster)<-[:belongs_to_campaign]-(s:vt_site)<-[:hosts]-(ip:vt_ip) RETURN sc, s, ip"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────
PLAN = [
    ("person2person",  build_person2person, 300),
    ("meta_condition", build_meta_condition, 300),
    ("1hop_event",     build_1hop_event,    150),
    ("chain",          build_chain,         100),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/t2c_v41_weakness_train_msg.json")
    parser.add_argument("--report", default="data/t2c_v41_weakness_report.txt")
    args = parser.parse_args()

    all_samples = []
    report_lines = ["=" * 60, "v41 약점 보강 시드 빌더 (4 카테고리 / 850)", "=" * 60]
    for name, builder, target in PLAN:
        samples = builder(target)
        report_lines.append(f"  {name:<22}: {len(samples):4d} (target {target})")
        for q, c in samples:
            all_samples.append({
                "messages": [
                    {"role": "user", "content": diversify(q)},
                    {"role": "assistant", "content": c},
                ],
                "system": SYSTEM_PROMPT,
                "category": name,
            })

    # 중복 제거
    seen = set()
    deduped = []
    for s in all_samples:
        q = s["messages"][0]["content"]
        if q in seen: continue
        seen.add(q)
        deduped.append(s)
    report_lines.append("=" * 60)
    report_lines.append(f"  총 생성: {len(all_samples)} / 중복 제거 후: {len(deduped)}")
    report_lines.append("=" * 60)

    random.shuffle(deduped)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.report).write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("\n".join(report_lines))
    size_kb = out_path.stat().st_size // 1024
    print(f"\n저장: {out_path} ({size_kb} KB)")
    print(f"리포트: {args.report}")


if __name__ == "__main__":
    main()
