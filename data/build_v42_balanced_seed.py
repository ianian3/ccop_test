"""
build_v42_balanced_seed.py — v41 회귀 카테고리 균형 보강 (1,000 시드)
============================================================
근거 (v41 × 232문항 측정, 2026-05-28):
  회귀 4 카테고리 + meta_condition 부분 보강 필요
  v41 의 시드 분포 비대칭으로 인한 trade-off 해소

v42 목표 (232 셋 79.3% → 86%+):
  - chain (3-hop+):       66.7% → 85% (시드 200, 다양한 3-5hop)
  - 1hop_person:          72%   → 88% (시드 250, has_account/owns_phone)
  - 1hop_event:           60%   → 85% (시드 200, caller/callee 방향 정밀)
  - threat_filter:        75%   → 85% (시드 150, 위협점수 메타 다양화)
  - meta_condition:       60%   → 80% (시드 200, 속성 조합 다양화)
  - 1hop_person2person:   80%   → 80% (시드 0, 유지)

설계 원칙 (v41 학습 교훈):
  1. 평가 셋 분포와 정합 (단일 패턴 ≠ 평가 패턴)
  2. v40 + v41 시드 모두 보존 (1hop_person2person 80% 유지)
  3. 카테고리간 비중 균형 (150~250 단위)
  4. 상호 충돌 사전 점검

출력: data/t2c_v42_balanced_train_msg.json
사용: python data/build_v42_balanced_seed.py
"""
import argparse, json, random
from pathlib import Path

random.seed(20260528)

SYSTEM_PROMPT = (
    Path(__file__).parent.parent / "app" / "services" / "prompts" / "t2c_v37_system.txt"
).read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# 변수 풀
# ──────────────────────────────────────────────────────────────────────────────
PERSON_NAMES = ["김민준", "이수진", "박서연", "최도윤", "정하은", "강지호", "한예린", "윤재희",
                "조다영", "송태웅", "홍지수", "임건우", "오서영", "권민재", "유시우", "백나연",
                "피의자1", "피의자2", "피해자1", "피해자2"]
ORG_NAMES = ["국민은행", "신한은행", "우리은행", "하나은행", "농협은행",
             "검찰청", "경찰청", "보이스피싱조직A", "범죄단체알파"]
CASE_NOS = ["CASE-2024-001", "CASE-2025-0301", "C-2026-0044", "2024-사이버-001",
            "C-2026-A-001", "CASE-2024-007"]
ACCOUNTS = ["110-1111-2222", "302-9988-7766", "1002-110-100001", "352-7788-9900",
            "200-9999-9999", "100-2233-4455"]
TELNOS = ["01099999999", "01011112222", "01033445566", "01077778888",
          "07012345678", "01088997766"]
IPS = ["192.168.1.10", "203.0.113.5", "118.32.45.67", "211.114.22.88"]
SITES = ["https://malicious-site.example", "https://kb-phish.example", "https://fake-bank.example"]

RISK_LEVELS = ['HIGH', 'MEDIUM', 'LOW']
THREAT_SCORES = [50, 60, 70, 80, 85, 90, 95]
EVID_GRADES = ['A', 'B', 'C']
AMOUNTS = [500000, 1000000, 3000000, 5000000, 10000000, 50000000, 100000000]
DURATIONS = [30, 60, 120, 180, 300, 600]
TIERS = [1, 2, 3, 4]
DOMAINS_RDB = ['KICS', 'OSINT', 'DIGITAL', 'EXT']
RDB_TO_CODE = {'KICS': 'investigation', 'OSINT': 'osint',
               'DIGITAL': 'partner', 'EXT': 'partner'}

ASK = ["보여주세요", "찾아주세요", "조회해주세요", "검색해주세요", "추적해주세요", "출력해주세요", "알려주세요"]
LIST_S = ["목록", "전체", "리스트", "전부"]
PRE = ["", "혹시 ", "급한데 ", "특히 ", "참고로 ", "확인 차 ", "정확히 "]
SUF = ["", " 부탁드립니다", "", " (긴급)", "", " 부탁드려요"]


def pick(arr): return random.choice(arr)
def diversify(q): return (pick(PRE) + q + pick(SUF)).strip()


# ──────────────────────────────────────────────────────────────────────────────
# A. chain (3-hop+) — 200 시드 — 평가 셋 분포 정합 강화
# ──────────────────────────────────────────────────────────────────────────────
def build_chain(n=200):
    """다양한 3-hop ~ 5-hop 패턴. v41 의 단일 패턴 (4-hop pt_cluster) 한계 보완."""
    out = []

    # 사건 중심 chain (가장 일반적)
    while len(out) < int(n * 0.25):
        case = pick(CASE_NOS); v = pick(ASK)
        templates = [
            (f"사건 {case}의 피의자가 보유한 계좌 추적",
             f"MATCH (c:vt_case {{flnm: '{case}'}})<-[:suspect_in]-(p:vt_psn)-[:has_account]->(b:vt_bacnt) RETURN c, p, b"),
            (f"{case} 사건의 피의자가 사용한 전화번호 통화 내역 {v}",
             f"MATCH (c:vt_case {{flnm: '{case}'}})<-[:suspect_in]-(p:vt_psn)-[:owns_phone]->(t:vt_telno)-[:caller]->(call:vt_call) RETURN c, p, t, call"),
            (f"사건 {case} 의 자금 출입 흐름 {v}",
             f"MATCH (c:vt_case {{flnm: '{case}'}})<-[:suspect_in]-(p:vt_psn)-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b2:vt_bacnt) RETURN c, p, b, t, b2"),
        ]
        q, c = pick(templates); out.append((q, c))

    # 자금흐름 chain (다단계)
    while len(out) < int(n * 0.45):
        v = pick(ASK)
        templates = [
            (f"피의자 → 계좌 → 이체 → 수신계좌 4-hop 추적 {v}",
             "MATCH (p:vt_psn)-[:has_account]->(a:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b:vt_bacnt) RETURN p, a, t, b"),
            (f"자금 5-hop 추적 (출금 → 이체 → 입금 → 인출) {v}",
             "MATCH (p1:vt_psn)-[:has_account]->(a:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b:vt_bacnt)<-[:has_account]-(p2:vt_psn) RETURN p1, a, t, b, p2"),
            (f"피의자 간 자금 이동 추적 {v}",
             "MATCH (p1:vt_psn)-[:has_account]->(a:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b:vt_bacnt)<-[:has_account]-(p2:vt_psn) RETURN p1, a, t, b, p2"),
        ]
        q, c = pick(templates); out.append((q, c))

    # 통신 chain
    while len(out) < int(n * 0.65):
        v = pick(ASK)
        templates = [
            (f"인물 → 전화 → 통화 → 수신자 3-hop {v}",
             "MATCH (p1:vt_psn)-[:owns_phone]->(t1:vt_telno)-[:caller]->(c:vt_call)-[:callee]->(t2:vt_telno)<-[:owns_phone]-(p2:vt_psn) RETURN p1, t1, c, t2, p2"),
            (f"전화→통화→발신자→사건 연결 {v}",
             "MATCH (t1:vt_telno)-[:caller]->(c:vt_call)-[:callee]->(t2:vt_telno)<-[:owns_phone]-(p:vt_psn)-[:suspect_in]->(case:vt_case) RETURN t1, c, t2, p, case"),
        ]
        q, c = pick(templates); out.append((q, c))

    # 사이트/IP/접속 chain
    while len(out) < int(n * 0.85):
        v = pick(ASK)
        templates = [
            (f"IP → 사이트 → 접속 → 사건 chain {v}",
             "MATCH (ip:vt_ip)-[:hosts]->(s:vt_site)<-[:eg_used_ip]-(c:vt_case) RETURN ip, s, c"),
            (f"악성 사이트 → 접속 IP → 추가 호스팅 사이트 {v}",
             "MATCH (s1:vt_site {is_malicious: true})<-[:hosts]-(ip:vt_ip)-[:hosts]->(s2:vt_site) RETURN s1, ip, s2"),
        ]
        q, c = pick(templates); out.append((q, c))

    # V3.7 신규 chain (pt_cluster / site_cluster)
    while len(out) < n:
        v = pick(ASK)
        templates = [
            (f"pt_cluster → 피의자 → 계좌 → 이체 4-hop {v}",
             "MATCH (pc:pt_cluster)<-[:belongs_to_cluster]-(p:vt_psn)-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer) RETURN pc, p, b, t"),
            (f"site_cluster → 사이트 → 호스팅 IP 3-hop {v}",
             "MATCH (sc:site_cluster)<-[:belongs_to_campaign]-(s:vt_site)<-[:hosts]-(ip:vt_ip) RETURN sc, s, ip"),
        ]
        q, c = pick(templates); out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# B. 1hop_person — 250 시드 — has_account / owns_phone / drives / works_at
# ──────────────────────────────────────────────────────────────────────────────
def build_1hop_person(n=250):
    out = []
    # has_account (가장 빈도 ↑)
    while len(out) < int(n * 0.35):
        name = pick(PERSON_NAMES); v = pick(ASK)
        templates = [
            (f"{name}이 보유한 계좌 {pick(LIST_S)} {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:has_account]->(b:vt_bacnt) RETURN p, b"),
            (f"{name} 명의 계좌 검색 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:has_account]->(b:vt_bacnt) RETURN p, b"),
            (f"피의자가 보유한 모든 계좌 {v}",
             "MATCH (p:vt_psn {role_cd: 'suspect'})-[:has_account]->(b:vt_bacnt) RETURN p, b"),
            (f"위험도 HIGH 인물 계좌 {v}",
             "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) WHERE p.risk_level = 'HIGH' RETURN p, b"),
        ]
        q, c = pick(templates); out.append((q, c))

    # owns_phone
    while len(out) < int(n * 0.6):
        name = pick(PERSON_NAMES); v = pick(ASK)
        templates = [
            (f"{name}이 사용하는 전화번호 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:owns_phone]->(t:vt_telno) RETURN p, t"),
            (f"{name} 명의 핸드폰 {pick(LIST_S)} {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:owns_phone]->(t:vt_telno) RETURN p, t"),
            (f"피해자 보유 전화번호 {v}",
             "MATCH (p:vt_psn {role_cd: 'victim'})-[:owns_phone]->(t:vt_telno) RETURN p, t"),
            (f"대포폰 소유자 추적 {v}",
             "MATCH (p:vt_psn)-[:owns_phone]->(t:vt_telno {is_burner: true}) RETURN p, t"),
            (f"피의자가 사용한 SKT 번호 {v}",
             "MATCH (p:vt_psn {role_cd: 'suspect'})-[:owns_phone]->(t:vt_telno {carr_cd: 'SKT'}) RETURN p, t"),
        ]
        q, c = pick(templates); out.append((q, c))

    # drives / works_at / uses 등 기타
    while len(out) < int(n * 0.8):
        name = pick(PERSON_NAMES); v = pick(ASK)
        org = pick(ORG_NAMES)
        templates = [
            (f"{name}이 운전한 차량 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:drives]->(c:vt_vhcl) RETURN p, c"),
            (f"{name}이 근무한 기관 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:works_at]->(o:vt_org) RETURN p, o"),
            (f"{org} 근무 인물 {pick(LIST_S)} {v}",
             f"MATCH (p:vt_psn)-[:works_at]->(o:vt_org {{org_nm: '{org}'}}) RETURN p, o"),
            (f"피의자가 사용한 ID/계정 {v}",
             "MATCH (p:vt_psn {role_cd: 'suspect'})-[:uses]->(i:vt_id) RETURN p, i"),
        ]
        q, c = pick(templates); out.append((q, c))

    # 복합 has_account + 메타
    while len(out) < n:
        amt = pick(AMOUNTS); v = pick(ASK)
        templates = [
            (f"피의자가 보유한 대포통장 {v}",
             "MATCH (p:vt_psn {role_cd: 'suspect'})-[:has_account]->(b:vt_bacnt {is_burner: true}) RETURN p, b"),
            (f"위험도 HIGH 인물의 계좌 잔액 추적 {v}",
             "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) WHERE p.risk_level = 'HIGH' RETURN p, b"),
            (f"피의자가 보유한 OSINT 출처 계좌 {v}",
             "MATCH (p:vt_psn {role_cd: 'suspect'})-[:has_account]->(b:vt_bacnt {source_domain: 'osint'}) RETURN p, b"),
        ]
        q, c = pick(templates); out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# C. 1hop_event — 200 시드 — caller/callee 방향, from/to_account
# ──────────────────────────────────────────────────────────────────────────────
def build_1hop_event(n=200):
    out = []
    # caller / callee 방향성 (가장 회귀 큰 영역)
    while len(out) < int(n * 0.3):
        t = pick(TELNOS); v = pick(ASK)
        templates = [
            (f"{t} 가 발신한 통화 전체 {v}",
             f"MATCH (telno:vt_telno {{telno: '{t}'}})-[:caller]->(c:vt_call) RETURN telno, c"),
            (f"{t} 로 수신된 통화 내역 {v}",
             f"MATCH (c:vt_call)-[:callee]->(telno:vt_telno {{telno: '{t}'}}) RETURN c, telno"),
            (f"발신 통화 시간 60초 이상 {v}",
             "MATCH (t:vt_telno)-[:caller]->(c:vt_call) WHERE c.duration >= 60 RETURN t, c"),
            (f"수신 통화 30초 이상 {v}",
             "MATCH (c:vt_call)-[:callee]->(t:vt_telno) WHERE c.duration >= 30 RETURN c, t"),
            (f"통화 양쪽 번호 (발신자 & 수신자) {v}",
             "MATCH (a:vt_telno)-[:caller]->(c:vt_call)-[:callee]->(b:vt_telno) RETURN a, c, b"),
        ]
        q, c = pick(templates); out.append((q, c))

    # from_account / to_account 방향
    while len(out) < int(n * 0.6):
        a = pick(ACCOUNTS); v = pick(ASK); amt = pick(AMOUNTS)
        templates = [
            (f"{a} 에서 출금된 이체 {v}",
             f"MATCH (b:vt_bacnt {{account_no: '{a}'}})-[:from_account]->(t:vt_transfer) RETURN b, t"),
            (f"{a} 로 입금된 이체 {v}",
             f"MATCH (t:vt_transfer)-[:to_account]->(b:vt_bacnt {{account_no: '{a}'}}) RETURN t, b"),
            (f"금액 {amt} 이상 출금 거래 {v}",
             f"MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer) WHERE t.amount >= {amt} RETURN b, t"),
            (f"입출금 양방향 계좌 흐름 {v}",
             "MATCH (a:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b:vt_bacnt) RETURN a, t, b"),
            (f"증거등급 A 이체 거래 {v}",
             "MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer {evid_grade: 'A'}) RETURN b, t"),
        ]
        q, c = pick(templates); out.append((q, c))

    # 접속/메시지 이벤트
    while len(out) < int(n * 0.85):
        v = pick(ASK); ip = pick(IPS); site = pick(SITES)
        templates = [
            (f"{ip} 에서 접속한 사이트 {v}",
             f"MATCH (a:vt_access {{src_ip: '{ip}'}})-[:accessed]->(s:vt_site) RETURN a, s"),
            (f"악성 사이트 접속 이벤트 {v}",
             "MATCH (a:vt_access)-[:accessed]->(s:vt_site {is_malicious: true}) RETURN a, s"),
            (f"{site} 사이트 접속 이력 {v}",
             f"MATCH (a:vt_access)-[:accessed]->(s:vt_site {{url_addr: '{site}'}}) RETURN a, s"),
        ]
        q, c = pick(templates); out.append((q, c))

    # 메시지 이벤트
    while len(out) < n:
        v = pick(ASK)
        templates = [
            (f"스팸 SMS 발신자 추적 {v}",
             "MATCH (t:vt_telno {is_burner: true})-[:sent_msg]->(m:vt_msg) RETURN t, m"),
            (f"카카오톡 메시지 이벤트 {v}",
             "MATCH (m:vt_msg) WHERE m.platform = '카카오' RETURN m"),
            (f"발송된 메시지 양쪽 인물 {v}",
             "MATCH (s:vt_psn)-[:sent_msg]->(m:vt_msg)-[:received_by]->(r:vt_psn) RETURN s, m, r"),
        ]
        q, c = pick(templates); out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# D. threat_filter — 150 시드 — 위협 점수 다양화
# ──────────────────────────────────────────────────────────────────────────────
def build_threat_filter(n=150):
    out = []
    # threat_score 임계
    while len(out) < int(n * 0.35):
        ts = pick(THREAT_SCORES); v = pick(ASK)
        templates = [
            (f"위협점수 {ts} 이상 IP {v}",
             f"MATCH (ip:vt_ip) WHERE ip.threat_score >= {ts} RETURN ip"),
            (f"위협점수 {ts} 미만 사이트 {v}",
             f"MATCH (s:vt_site) WHERE s.threat_score < {ts} RETURN s"),
            (f"위협점수 80 이상 90 이하 IP {v}",
             "MATCH (ip:vt_ip) WHERE ip.threat_score >= 80 AND ip.threat_score <= 90 RETURN ip"),
            (f"고위협 IP가 호스팅한 사이트 {v}",
             "MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) WHERE ip.threat_score >= 80 RETURN ip, s"),
        ]
        q, c = pick(templates); out.append((q, c))

    # risk_level 위협
    while len(out) < int(n * 0.55):
        rl = pick(RISK_LEVELS); v = pick(ASK)
        templates = [
            (f"위험도 {rl} 피의자 {v}",
             f"MATCH (p:vt_psn) WHERE p.risk_level = '{rl}' RETURN p"),
            (f"고위험 인물의 통화 내역 {v}",
             "MATCH (p:vt_psn {risk_level: 'HIGH'})-[:owns_phone]->(t:vt_telno)-[:caller]->(c:vt_call) RETURN p, t, c"),
            (f"위험도 HIGH 또는 MEDIUM 인물 {v}",
             "MATCH (p:vt_psn) WHERE p.risk_level IN ['HIGH','MEDIUM'] RETURN p"),
        ]
        q, c = pick(templates); out.append((q, c))

    # threat_level (pt_cluster)
    while len(out) < int(n * 0.75):
        v = pick(ASK)
        templates = [
            (f"위협레벨 5 캠페인 클러스터 {v}",
             "MATCH (pc:pt_cluster) WHERE pc.threat_level = 5 RETURN pc"),
            (f"위협레벨 4 이상 캠페인 {v}",
             "MATCH (pc:pt_cluster) WHERE pc.threat_level >= 4 RETURN pc"),
            (f"고위협 캠페인의 멤버 추적 {v}",
             "MATCH (pc:pt_cluster)<-[:belongs_to_cluster]-(p:vt_psn) WHERE pc.threat_level >= 4 RETURN pc, p"),
        ]
        q, c = pick(templates); out.append((q, c))

    # is_malicious / is_burner 위협 플래그
    while len(out) < n:
        v = pick(ASK)
        templates = [
            (f"악성 사이트 + VPN IP 결합 위협 {v}",
             "MATCH (ip:vt_ip {is_vpn: true})-[:hosts]->(s:vt_site {is_malicious: true}) RETURN ip, s"),
            (f"대포통장 거래 위협 추적 {v}",
             "MATCH (b:vt_bacnt {is_burner: true})-[:from_account]->(t:vt_transfer) RETURN b, t"),
            (f"위협점수 80+ 사이트의 IP {v}",
             "MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) WHERE s.threat_score >= 80 RETURN ip, s"),
        ]
        q, c = pick(templates); out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# E. meta_condition — 200 시드 — 속성 조합 다양화
# ──────────────────────────────────────────────────────────────────────────────
def build_meta_condition(n=200):
    out = []
    # evid_grade 다양화
    while len(out) < int(n * 0.25):
        gr = pick(EVID_GRADES); v = pick(ASK)
        templates = [
            (f"증거등급 {gr} 사건 {v}",
             f"MATCH (c:vt_case) WHERE c.evid_grade = '{gr}' RETURN c"),
            (f"등급 A 이체 거래 {v}",
             "MATCH (t:vt_transfer) WHERE t.evid_grade = 'A' RETURN t"),
            (f"고급 증거 (A등급) 자료 {v}",
             "MATCH (n) WHERE n.evid_grade = 'A' RETURN n"),
        ]
        q, c = pick(templates); out.append((q, c))

    # is_* boolean 플래그 조합
    while len(out) < int(n * 0.5):
        v = pick(ASK)
        templates = [
            (f"대포통장 {v}",
             "MATCH (b:vt_bacnt) WHERE b.is_burner = true RETURN b"),
            (f"대포폰 전체 {v}",
             "MATCH (t:vt_telno) WHERE t.is_burner = true RETURN t"),
            (f"VPN 사용 IP {v}",
             "MATCH (ip:vt_ip) WHERE ip.is_vpn = true RETURN ip"),
            (f"악성 사이트 + 위협점수 80+ {v}",
             "MATCH (s:vt_site) WHERE s.is_malicious = true AND s.threat_score >= 80 RETURN s"),
            (f"동결 계좌 {v}",
             "MATCH (b:vt_bacnt) WHERE b.is_frozen = true RETURN b"),
        ]
        q, c = pick(templates); out.append((q, c))

    # 금액/시간 임계
    while len(out) < int(n * 0.7):
        amt = pick(AMOUNTS); dur = pick(DURATIONS); v = pick(ASK)
        man = f"{amt//10000}만원" if amt < 100000000 else f"{amt//100000000}억"
        templates = [
            (f"피해금액 {man} 이상 사건 {v}",
             f"MATCH (c:vt_case) WHERE c.damage_amount >= {amt} RETURN c"),
            (f"통화 {dur}초 이상 {v}",
             f"MATCH (c:vt_call) WHERE c.duration >= {dur} RETURN c"),
            (f"이체 {man} 이상 거래 {v}",
             f"MATCH (t:vt_transfer) WHERE t.amount >= {amt} RETURN t"),
            (f"통화 {dur}초~{dur*3}초 사이 {v}",
             f"MATCH (c:vt_call) WHERE c.duration >= {dur} AND c.duration <= {dur*3} RETURN c"),
        ]
        q, c = pick(templates); out.append((q, c))

    # 복합 메타 (속성 조합)
    while len(out) < int(n * 0.9):
        v = pick(ASK); rdb = pick(DOMAINS_RDB); dom = RDB_TO_CODE[rdb]
        amt = pick(AMOUNTS)
        templates = [
            (f"{rdb} 도메인 + 위험도 HIGH 인물 {v}",
             f"MATCH (p:vt_psn) WHERE p.source_domain = '{dom}' AND p.risk_level = 'HIGH' RETURN p"),
            (f"증거등급 A + 금액 {amt} 이상 이체 {v}",
             f"MATCH (t:vt_transfer) WHERE t.evid_grade = 'A' AND t.amount >= {amt} RETURN t"),
            (f"대포통장 + 위험계좌 동결 {v}",
             "MATCH (b:vt_bacnt) WHERE b.is_burner = true AND b.is_frozen = true RETURN b"),
        ]
        q, c = pick(templates); out.append((q, c))

    # 메타 + 1-hop
    while len(out) < n:
        v = pick(ASK); rdb = pick(DOMAINS_RDB); dom = RDB_TO_CODE[rdb]
        templates = [
            (f"{rdb} 출처 계좌의 출금 거래 {v}",
             f"MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer) WHERE b.source_domain = '{dom}' RETURN b, t"),
            (f"신뢰도 1 사건의 피의자 {v}",
             "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) WHERE c.reliability_tier = 1 RETURN p, c"),
        ]
        q, c = pick(templates); out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# F. person2person — 0 시드 (v41 80% 유지, 보강 안 함)
# ──────────────────────────────────────────────────────────────────────────────
# v41 에서 297 시드로 60%→80% 달성. 추가 시드 시 분포 충돌 우려 → 유지.


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────
PLAN = [
    ("1hop_person",     build_1hop_person,     250),
    ("meta_condition",  build_meta_condition,  200),
    ("1hop_event",      build_1hop_event,      200),
    ("chain",           build_chain,           200),
    ("threat_filter",   build_threat_filter,   150),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/t2c_v42_balanced_train_msg.json")
    parser.add_argument("--report", default="data/t2c_v42_balanced_report.txt")
    args = parser.parse_args()

    all_samples = []
    report_lines = ["=" * 60, "v42 균형 시드 빌더 (5 카테고리 / 1,000)", "=" * 60]
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

    seen = set(); deduped = []
    for s in all_samples:
        q = s["messages"][0]["content"]
        if q in seen: continue
        seen.add(q); deduped.append(s)
    report_lines.append("=" * 60)
    report_lines.append(f"  총 생성: {len(all_samples)} / 중복 제거 후: {len(deduped)}")
    report_lines.append("=" * 60)

    random.shuffle(deduped)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(deduped, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.report).write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print("\n".join(report_lines))
    print(f"\n저장: {out_path} ({out_path.stat().st_size // 1024} KB)")
    print(f"리포트: {args.report}")


if __name__ == "__main__":
    main()
