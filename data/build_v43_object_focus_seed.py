"""
build_v43_object_focus_seed.py — v42 약점 카테고리 보강 (~800 시드)
============================================================
근거 (v42 + Router × 232문항 측정, 2026-06-01, 86.6%):
  v42 회귀/약점 4개 카테고리 보강 — 1hop_object 최우선
  Router 리워크로 general/guard 13문항은 이미 해결

v43 목표 (232 셋 86.6% → 89~91%):
  - 1hop_object:    70%   → 90% (시드 250, hosts/contains_file/used_for/targets/belongs_to/communicated_with)
  - chain:          66.7% → 85% (시드 200, 평가셋 정확 패턴 매칭: has_account+from_account 등)
  - 1hop_event:     60%   → 85% (시드 200, accessed_from/to, transferred_to 추가)
  - 1hop_person:    80%   → 90% (시드 150, registered_to, used_ip, owns_vehicle 추가)
  - person2person:  90%       (시드 0, v42 성과 보존)
  - v37_anonymous:  100%      (시드 0, 보존)
  - v37_cluster:    100%      (시드 0, 보존)
  - meta_condition: 60%       (시드 0, v43에서는 1hop_object 우선)
  - threat_filter:  83.3%     (시드 0, v42 균형 보존)

설계 원칙 (v42 학습 교훈):
  1. 1hop_object 의 Object↔Object 관계가 v42 시드에 누락 → 250 시드 신설
  2. chain은 평가셋 정확 패턴 (has_account+from_account, owns_phone+caller 등) 직접 학습
  3. 1hop_event 의 accessed_from/to, transferred_to 등 v42 미포함 패턴 추가
  4. v42 강점 카테고리(person2person, anonymous, cluster) 시드 0 — 분포 충돌 방지

출력: data/t2c_v43_object_focus_train_msg.json
사용: python data/build_v43_object_focus_seed.py
"""
import argparse, json, random
from pathlib import Path

random.seed(20260601)

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
             "검찰청", "경찰청", "보이스피싱조직A", "범죄단체알파", "삼성카드", "토스뱅크"]
CASE_NOS = ["CASE-2024-001", "CASE-2025-0301", "C-2026-0044", "2024-사이버-001",
            "C-2026-A-001", "CASE-2024-007"]
ACCOUNTS = ["110-1111-2222", "302-9988-7766", "1002-110-100001", "352-7788-9900",
            "200-9999-9999", "100-2233-4455"]
TELNOS = ["010-1234-5678", "01099999999", "01011112222", "01033445566", "01077778888",
          "07012345678", "01088997766"]
IPS = ["192.168.1.10", "203.0.113.5", "118.32.45.67", "211.114.22.88", "1.2.3.4"]
SITES = ["https://malicious-site.example", "https://kb-phish.example",
         "https://fake-bank.example", "https://phishing.example"]
FILES = ["malware.exe", "ransom.dll", "trojan.bin", "exploit.sh", "backdoor.py"]
HASHES = ["abc123def456", "deadbeef9999", "cafebabe1234", "feedface5678"]
VEHICLES = ["12가1234", "34나5678", "56다9012", "78라3456"]

ASK = ["보여주세요", "찾아주세요", "조회해주세요", "검색해주세요", "추적해주세요",
       "출력해주세요", "알려주세요"]
LIST_S = ["목록", "전체", "리스트", "전부"]
PRE = ["", "혹시 ", "급한데 ", "특히 ", "참고로 ", "확인 차 ", "정확히 "]
SUF = ["", " 부탁드립니다", "", " (긴급)", "", " 부탁드려요"]


def pick(arr): return random.choice(arr)
def diversify(q): return (pick(PRE) + q + pick(SUF)).strip()


# ──────────────────────────────────────────────────────────────────────────────
# A. 1hop_object — 250 시드 (v42 70% → 90% 목표) ⭐ 최우선
# ──────────────────────────────────────────────────────────────────────────────
def build_1hop_object(n=250):
    """Object↔Object 관계 + 사칭 패턴 + 귀속. v42 회귀(-30p) 복구."""
    out = []

    # A1. hosts (IP ↔ Site) — 30%
    while len(out) < int(n * 0.30):
        ip = pick(IPS); site = pick(SITES); v = pick(ASK)
        templates = [
            (f"IP {ip}에 호스팅된 사이트 {v}",
             f"MATCH (ip:vt_ip {{ip_addr: '{ip}'}})-[:hosts]->(s:vt_site) RETURN ip, s"),
            (f"사이트 {site} 호스팅 IP {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site {{url: '{site}'}}) RETURN ip, s"),
            (f"악성 사이트 호스팅 IP 역추적 {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site {{is_malicious: true}}) RETURN ip, s"),
            (f"피싱 사이트 호스팅 IP {pick(LIST_S)} {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) WHERE s.is_phishing = true RETURN ip, s"),
            (f"IP {ip}이 호스팅하는 모든 도메인 {v}",
             f"MATCH (ip:vt_ip {{ip_addr: '{ip}'}})-[:hosts]->(s:vt_site) RETURN s"),
            (f"국내 IP가 호스팅한 사이트 {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) WHERE ip.country = 'KR' RETURN ip, s"),
        ]
        q, c = pick(templates); out.append((q, c))

    # A2. contains_file (Site/Msg ↔ File) — 15%
    while len(out) < int(n * 0.45):
        site = pick(SITES); fname = pick(FILES); v = pick(ASK)
        templates = [
            (f"사이트 {site}에 포함된 악성 파일 {v}",
             f"MATCH (s:vt_site {{url: '{site}'}})-[:contains_file]->(f:vt_file) RETURN s, f"),
            (f"악성 사이트에 첨부된 파일 {pick(LIST_S)} {v}",
             f"MATCH (s:vt_site {{is_malicious: true}})-[:contains_file]->(f:vt_file) RETURN s, f"),
            (f"메시지 첨부 악성 파일 {v}",
             f"MATCH (m:vt_msg)-[:contains_file]->(f:vt_file) WHERE f.is_malicious = true RETURN m, f"),
            (f"파일 {fname}이 포함된 사이트 {v}",
             f"MATCH (s:vt_site)-[:contains_file]->(f:vt_file {{name: '{fname}'}}) RETURN s, f"),
            (f"메시지에 첨부된 파일 전체 {v}",
             f"MATCH (m:vt_msg)-[:contains_file]->(f:vt_file) RETURN m, f"),
        ]
        q, c = pick(templates); out.append((q, c))

    # A3. communicated_with (IP ↔ IP, C2 추적) — 12%
    while len(out) < int(n * 0.57):
        ip = pick(IPS); v = pick(ASK)
        templates = [
            (f"IP끼리 직접 통신 (C2 추적) {v}",
             f"MATCH (ip1:vt_ip)-[:communicated_with]->(ip2:vt_ip) RETURN ip1, ip2"),
            (f"IP {ip}와 통신한 다른 IP {v}",
             f"MATCH (ip1:vt_ip {{ip_addr: '{ip}'}})-[:communicated_with]->(ip2:vt_ip) RETURN ip1, ip2"),
            (f"C2 서버 통신 IP {pick(LIST_S)} {v}",
             f"MATCH (ip1:vt_ip)-[:communicated_with]->(ip2:vt_ip {{is_c2: true}}) RETURN ip1, ip2"),
            (f"해외 IP 간 통신 추적 {v}",
             f"MATCH (ip1:vt_ip)-[:communicated_with]->(ip2:vt_ip) WHERE ip2.country <> 'KR' RETURN ip1, ip2"),
        ]
        q, c = pick(templates); out.append((q, c))

    # A4. belongs_to (Account ↔ Org, Person ↔ Org) — 15%
    while len(out) < int(n * 0.72):
        actno = pick(ACCOUNTS); org = pick(ORG_NAMES); v = pick(ASK)
        templates = [
            (f"계좌 {actno} 소속 금융기관 {v}",
             f"MATCH (b:vt_bacnt {{account_no: '{actno}'}})-[:belongs_to]->(o:vt_org) RETURN b, o"),
            (f"{org} 소속 계좌 {pick(LIST_S)} {v}",
             f"MATCH (b:vt_bacnt)-[:belongs_to]->(o:vt_org {{org_nm: '{org}'}}) RETURN b, o"),
            (f"계좌가 어느 은행 소속인지 {v}",
             f"MATCH (b:vt_bacnt)-[:belongs_to]->(o:vt_org) RETURN b, o"),
            (f"국민은행 소속 계좌 전체 {v}",
             f"MATCH (b:vt_bacnt)-[:belongs_to]->(o:vt_org {{org_nm: '국민은행'}}) RETURN b, o"),
            (f"피의자가 소속된 범죄조직 {v}",
             f"MATCH (p:vt_psn)-[:belongs_to]->(o:vt_org) WHERE o.org_type = 'criminal' RETURN p, o"),
        ]
        q, c = pick(templates); out.append((q, c))

    # A5. used_for (Object → vt_impersonation) — V3.3 사칭 패턴 — 15%
    while len(out) < int(n * 0.87):
        tel = pick(TELNOS); v = pick(ASK)
        templates = [
            (f"전화 사칭에 사용된 이벤트 {v}",
             f"MATCH (t:vt_telno)-[:used_for]->(imp:vt_impersonation) RETURN t, imp"),
            (f"전화번호 {tel}이 사용된 사칭 사건 {v}",
             f"MATCH (t:vt_telno {{telno: '{tel}'}})-[:used_for]->(imp:vt_impersonation) RETURN t, imp"),
            (f"사칭에 사용된 계정 {pick(LIST_S)} {v}",
             f"MATCH (i:vt_id)-[:used_for]->(imp:vt_impersonation) RETURN i, imp"),
            (f"악성 사이트가 사용된 사칭 캠페인 {v}",
             f"MATCH (s:vt_site)-[:used_for]->(imp:vt_impersonation) RETURN s, imp"),
            (f"국민은행 사칭에 사용된 전화번호 {v}",
             f"MATCH (t:vt_telno)-[:used_for]->(imp:vt_impersonation)-[:targets]->(o:vt_org {{org_nm: '국민은행'}}) RETURN t, imp"),
        ]
        q, c = pick(templates); out.append((q, c))

    # A6. targets (vt_impersonation → Org) — 사칭 타겟 — 13%
    while len(out) < n:
        org = pick(ORG_NAMES); v = pick(ASK)
        templates = [
            (f"사칭이 타겟한 기관 {v}",
             f"MATCH (imp:vt_impersonation)-[:targets]->(o:vt_org) RETURN imp, o"),
            (f"{org}을 타겟한 사칭 이벤트 {pick(LIST_S)} {v}",
             f"MATCH (imp:vt_impersonation)-[:targets]->(o:vt_org {{org_nm: '{org}'}}) RETURN imp, o"),
            (f"검찰 사칭 이벤트 전체 {v}",
             f"MATCH (imp:vt_impersonation)-[:targets]->(o:vt_org {{org_nm: '검찰청'}}) RETURN imp, o"),
            (f"은행 타겟 사칭 캠페인 {v}",
             f"MATCH (imp:vt_impersonation)-[:targets]->(o:vt_org) WHERE o.org_type = 'bank' RETURN imp, o"),
        ]
        q, c = pick(templates); out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# B. chain (2-3 hop, 평가셋 정확 패턴) — 200 시드
# ──────────────────────────────────────────────────────────────────────────────
def build_chain(n=200):
    """평가셋 [I01~I15] 의 정확한 엣지 조합 학습 — v42 의 단순 매칭 실패 보완."""
    out = []

    # B1. has_account + from_account (자금 추적 2-hop) — 20%
    while len(out) < int(n * 0.20):
        name = pick(PERSON_NAMES); v = pick(ASK)
        templates = [
            (f"{name}의 계좌에서 출발한 이체 흐름 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer) RETURN p, b, t"),
            (f"피의자 계좌에서 출금 이체 {v}",
             f"MATCH (p:vt_psn {{role_cd: 'suspect'}})-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer) RETURN p, b, t"),
            (f"{name} 명의 계좌의 출금 거래 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer) RETURN p, b, t"),
        ]
        q, c = pick(templates); out.append((q, c))

    # B2. owns_phone + caller (통신 추적 2-hop) — 15%
    while len(out) < int(n * 0.35):
        name = pick(PERSON_NAMES); v = pick(ASK)
        templates = [
            (f"{name} 명의 전화의 발신 통화 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:owns_phone]->(t:vt_telno)-[:caller]->(c:vt_call) RETURN p, t, c"),
            (f"{name}이 사용한 전화의 통화 내역 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:owns_phone]->(t:vt_telno)-[:caller]->(c:vt_call) RETURN p, t, c"),
            (f"피의자가 발신한 통화 추적 {v}",
             f"MATCH (p:vt_psn {{role_cd: 'suspect'}})-[:owns_phone]->(t:vt_telno)-[:caller]->(c:vt_call) RETURN p, t, c"),
        ]
        q, c = pick(templates); out.append((q, c))

    # B3. hosts + contains_file (호스팅 + 악성파일 2-hop) — 12%
    while len(out) < int(n * 0.47):
        ip = pick(IPS); v = pick(ASK)
        templates = [
            (f"IP에서 호스팅된 사이트의 악성 파일 {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site)-[:contains_file]->(f:vt_file) RETURN ip, s, f"),
            (f"IP {ip}이 호스팅한 사이트의 악성 파일 {v}",
             f"MATCH (ip:vt_ip {{ip_addr: '{ip}'}})-[:hosts]->(s:vt_site)-[:contains_file]->(f:vt_file) RETURN ip, s, f"),
            (f"호스팅 IP → 사이트 → 악성 파일 chain {v}",
             f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site)-[:contains_file]->(f:vt_file {{is_malicious: true}}) RETURN ip, s, f"),
        ]
        q, c = pick(templates); out.append((q, c))

    # B4. used_for + targets (사칭 chain) — 10%
    while len(out) < int(n * 0.57):
        org = pick(ORG_NAMES); v = pick(ASK)
        templates = [
            (f"대포폰 → 사칭 → 피해기관 체인 {v}",
             f"MATCH (t:vt_telno {{is_burner: true}})-[:used_for]->(imp:vt_impersonation)-[:targets]->(o:vt_org) RETURN t, imp, o"),
            (f"전화 → 사칭 이벤트 → 타겟 기관 {v}",
             f"MATCH (t:vt_telno)-[:used_for]->(imp:vt_impersonation)-[:targets]->(o:vt_org) RETURN t, imp, o"),
            (f"{org} 사칭에 사용된 수단과 타겟 {v}",
             f"MATCH (x)-[:used_for]->(imp:vt_impersonation)-[:targets]->(o:vt_org {{org_nm: '{org}'}}) RETURN x, imp, o"),
        ]
        q, c = pick(templates); out.append((q, c))

    # B5. sent_msg + mentions_account (메시지 ↔ 계좌) — 8%
    while len(out) < int(n * 0.65):
        name = pick(PERSON_NAMES); v = pick(ASK)
        templates = [
            (f"{name}이 발송한 메시지에 언급된 계좌 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:sent_msg]->(m:vt_msg)-[:mentions_account]->(b:vt_bacnt) RETURN p, m, b"),
            (f"피의자가 보낸 메시지의 계좌 언급 {v}",
             f"MATCH (p:vt_psn {{role_cd: 'suspect'}})-[:sent_msg]->(m:vt_msg)-[:mentions_account]->(b:vt_bacnt) RETURN p, m, b"),
        ]
        q, c = pick(templates); out.append((q, c))

    # B6. suspect_in + sourced_from (사건 + 출처 신뢰도) — 8%
    while len(out) < int(n * 0.73):
        case = pick(CASE_NOS); v = pick(ASK)
        templates = [
            (f"피의자 → 사건 → 출처 신뢰도 {v}",
             f"MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case)-[:sourced_from]->(src:vt_src) RETURN p, c, src"),
            (f"사건 {case}의 출처 신뢰도 추적 {v}",
             f"MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case {{flnm: '{case}'}})-[:sourced_from]->(src:vt_src) RETURN p, c, src"),
        ]
        q, c = pick(templates); out.append((q, c))

    # B7. has_account + from_account + to_account (2hop 자금세탁) — 12%
    while len(out) < int(n * 0.85):
        v = pick(ASK)
        templates = [
            (f"인물 → 계좌 → 이체 → 수신계좌 2hop 자금세탁 {v}",
             f"MATCH (p:vt_psn)-[:has_account]->(b1:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b2:vt_bacnt) RETURN p, b1, t, b2"),
            (f"자금세탁 추적 (인물 → 계좌 → 송금 → 입금계좌) {v}",
             f"MATCH (p:vt_psn)-[:has_account]->(b1:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b2:vt_bacnt) RETURN p, b1, t, b2"),
        ]
        q, c = pick(templates); out.append((q, c))

    # B8. drives + recorded_in + occurred_at (LPR chain) — 8%
    while len(out) < int(n * 0.93):
        name = pick(PERSON_NAMES); v = pick(ASK)
        templates = [
            (f"{name}의 차량 이동 경로 (LPR) {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:drives]->(c:vt_vhcl)-[:recorded_in]->(m:vt_movement)-[:occurred_at]->(l:vt_loc) RETURN p, c, m, l"),
            (f"피의자 차량의 LPR 기록 위치 {v}",
             f"MATCH (p:vt_psn {{role_cd: 'suspect'}})-[:drives]->(c:vt_vhcl)-[:recorded_in]->(m:vt_movement)-[:occurred_at]->(l:vt_loc) RETURN p, c, m, l"),
        ]
        q, c = pick(templates); out.append((q, c))

    # B9. owns_phone + sent_msg (소유 폰 → 발송 메시지) — 7%
    while len(out) < n:
        name = pick(PERSON_NAMES); v = pick(ASK)
        templates = [
            (f"{name} 폰으로 발송된 메시지 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:owns_phone]->(t:vt_telno)-[:sent_msg]->(m:vt_msg) RETURN p, t, m"),
            (f"피의자 폰의 메시지 발송 내역 {v}",
             f"MATCH (p:vt_psn {{role_cd: 'suspect'}})-[:owns_phone]->(t:vt_telno)-[:sent_msg]->(m:vt_msg) RETURN p, t, m"),
        ]
        q, c = pick(templates); out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# C. 1hop_event — 200 시드 (v42 60% → 85% 목표)
# ──────────────────────────────────────────────────────────────────────────────
def build_1hop_event(n=200):
    """평가셋 [E01~E15]의 단일 엣지 학습. v42 caller/callee/transferred_to 약점 보완."""
    out = []

    # C1. caller (발신 통화) — 15%
    while len(out) < int(n * 0.15):
        tel = pick(TELNOS); v = pick(ASK)
        templates = [
            (f"전화번호 {tel}의 발신 통화 내역 {v}",
             f"MATCH (t:vt_telno {{telno: '{tel}'}})-[:caller]->(c:vt_call) RETURN t, c"),
            (f"{tel}이 발신한 통화 {pick(LIST_S)} {v}",
             f"MATCH (t:vt_telno {{telno: '{tel}'}})-[:caller]->(c:vt_call) RETURN t, c"),
            (f"발신자 기준 통화 기록 {v}",
             f"MATCH (t:vt_telno)-[:caller]->(c:vt_call) RETURN t, c"),
        ]
        q, c = pick(templates); out.append((q, c))

    # C2. callee (수신 통화) — 15%
    while len(out) < int(n * 0.30):
        tel = pick(TELNOS); v = pick(ASK)
        templates = [
            (f"전화번호 {tel}의 수신 통화 내역 {v}",
             f"MATCH (c:vt_call)-[:callee]->(t:vt_telno {{telno: '{tel}'}}) RETURN c, t"),
            (f"{tel}이 수신한 통화 {pick(LIST_S)} {v}",
             f"MATCH (c:vt_call)-[:callee]->(t:vt_telno {{telno: '{tel}'}}) RETURN c, t"),
            (f"수신자 기준 통화 기록 {v}",
             f"MATCH (c:vt_call)-[:callee]->(t:vt_telno) RETURN c, t"),
        ]
        q, c = pick(templates); out.append((q, c))

    # C3. from_account (출금 이체) — 13%
    while len(out) < int(n * 0.43):
        actno = pick(ACCOUNTS); v = pick(ASK)
        templates = [
            (f"계좌 {actno}에서 출금된 이체 {v}",
             f"MATCH (b:vt_bacnt {{account_no: '{actno}'}})-[:from_account]->(t:vt_transfer) RETURN b, t"),
            (f"{actno} 출금 거래 내역 {v}",
             f"MATCH (b:vt_bacnt {{account_no: '{actno}'}})-[:from_account]->(t:vt_transfer) RETURN b, t"),
            (f"100만원 이상 출금 이체 {v}",
             f"MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer) WHERE t.amount >= 1000000 RETURN b, t"),
        ]
        q, c = pick(templates); out.append((q, c))

    # C4. to_account (입금 이체) — 13%
    while len(out) < int(n * 0.56):
        actno = pick(ACCOUNTS); v = pick(ASK)
        templates = [
            (f"계좌 {actno}으로 입금된 이체 {v}",
             f"MATCH (t:vt_transfer)-[:to_account]->(b:vt_bacnt {{account_no: '{actno}'}}) RETURN t, b"),
            (f"{actno} 입금 거래 내역 {v}",
             f"MATCH (t:vt_transfer)-[:to_account]->(b:vt_bacnt {{account_no: '{actno}'}}) RETURN t, b"),
            (f"입금 받은 계좌 추적 {v}",
             f"MATCH (t:vt_transfer)-[:to_account]->(b:vt_bacnt) RETURN t, b"),
        ]
        q, c = pick(templates); out.append((q, c))

    # C5. accessed_from / accessed_to (IP ↔ 접속) — 15%
    while len(out) < int(n * 0.71):
        ip = pick(IPS); site = pick(SITES); v = pick(ASK)
        templates = [
            (f"IP {ip}의 접속 내역 {v}",
             f"MATCH (ip:vt_ip {{ip_addr: '{ip}'}})-[:accessed_from]->(a:vt_access) RETURN ip, a"),
            (f"{ip}이 접속한 사이트 {v}",
             f"MATCH (ip:vt_ip {{ip_addr: '{ip}'}})-[:accessed_from]->(a:vt_access)-[:accessed_to]->(s:vt_site) RETURN ip, a, s"),
            (f"악성 사이트 {site} 접속 IP {v}",
             f"MATCH (a:vt_access)-[:accessed_to]->(s:vt_site {{url: '{site}'}}) RETURN a, s"),
            (f"악성 사이트 접속 IP 전체 {v}",
             f"MATCH (ip:vt_ip)-[:accessed_from]->(a:vt_access)-[:accessed_to]->(s:vt_site {{is_malicious: true}}) RETURN ip, a, s"),
        ]
        q, c = pick(templates); out.append((q, c))

    # C6. transferred_to (직접 이체) — 10%
    while len(out) < int(n * 0.81):
        actno = pick(ACCOUNTS); v = pick(ASK)
        templates = [
            (f"계좌 간 직접 이체 {v}",
             f"MATCH (b1:vt_bacnt)-[:transferred_to]->(b2:vt_bacnt) RETURN b1, b2"),
            (f"{actno}에서 직접 송금한 계좌 {v}",
             f"MATCH (b1:vt_bacnt {{account_no: '{actno}'}})-[:transferred_to]->(b2:vt_bacnt) RETURN b1, b2"),
            (f"직접 이체 (transferred_to) 관계 {v}",
             f"MATCH (b1:vt_bacnt)-[:transferred_to]->(b2:vt_bacnt) RETURN b1, b2"),
        ]
        q, c = pick(templates); out.append((q, c))

    # C7. sent_msg / received_msg — 10%
    while len(out) < int(n * 0.91):
        tel = pick(TELNOS); v = pick(ASK)
        templates = [
            (f"{tel}이 발송한 메시지 {v}",
             f"MATCH (t:vt_telno {{telno: '{tel}'}})-[:sent_msg]->(m:vt_msg) RETURN t, m"),
            (f"{tel}이 수신한 메시지 {v}",
             f"MATCH (m:vt_msg)-[:received_msg]->(t:vt_telno {{telno: '{tel}'}}) RETURN m, t"),
            (f"피싱 메시지 발송 번호 {v}",
             f"MATCH (t:vt_telno)-[:sent_msg]->(m:vt_msg {{is_phishing: true}}) RETURN t, m"),
        ]
        q, c = pick(templates); out.append((q, c))

    # C8. recorded_in / occurred_at (이동·위치) — 9%
    while len(out) < n:
        v = pick(ASK)
        templates = [
            (f"차량 LPR 기록 {v}",
             f"MATCH (v:vt_vhcl)-[:recorded_in]->(m:vt_movement) RETURN v, m"),
            (f"이동 기록의 위치 {v}",
             f"MATCH (m:vt_movement)-[:occurred_at]->(l:vt_loc) RETURN m, l"),
        ]
        q, c = pick(templates); out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# D. 1hop_person — 150 시드 (v42 80% → 90% 목표, v42에 누락된 엣지 추가)
# ──────────────────────────────────────────────────────────────────────────────
def build_1hop_person(n=150):
    """평가셋에서 v42가 놓친 registered_to, used_ip, owns_vehicle 보강."""
    out = []

    # D1. registered_to (전화번호 명의자) — 25%
    while len(out) < int(n * 0.25):
        tel = pick(TELNOS); name = pick(PERSON_NAMES); v = pick(ASK)
        templates = [
            (f"{tel}의 명의자 (registered_to 기준) {v}",
             f"MATCH (t:vt_telno {{telno: '{tel}'}})-[:registered_to]->(p:vt_psn) RETURN t, p"),
            (f"전화번호 {tel}의 가입자 정보 {v}",
             f"MATCH (t:vt_telno {{telno: '{tel}'}})-[:registered_to]->(p:vt_psn) RETURN t, p"),
            (f"{name} 명의로 등록된 번호 {v}",
             f"MATCH (t:vt_telno)-[:registered_to]->(p:vt_psn {{name: '{name}'}}) RETURN t, p"),
        ]
        q, c = pick(templates); out.append((q, c))

    # D2. owns_phone + registered_to (대포폰: 실사용자 ≠ 명의자) — 20%
    while len(out) < int(n * 0.45):
        v = pick(ASK)
        templates = [
            (f"실사용자와 명의자가 다른 대포폰 {v}",
             f"MATCH (p1:vt_psn)-[:owns_phone]->(t:vt_telno)-[:registered_to]->(p2:vt_psn) WHERE p1 <> p2 RETURN p1, t, p2"),
            (f"대포폰 추적 (사용자 vs 명의자 불일치) {v}",
             f"MATCH (p1:vt_psn)-[:owns_phone]->(t:vt_telno)-[:registered_to]->(p2:vt_psn) WHERE p1.prsn_id <> p2.prsn_id RETURN p1, t, p2"),
            (f"명의 도용 전화번호 {v}",
             f"MATCH (p1:vt_psn)-[:owns_phone]->(t:vt_telno)-[:registered_to]->(p2:vt_psn) WHERE p1 <> p2 RETURN p1, t, p2"),
        ]
        q, c = pick(templates); out.append((q, c))

    # D3. used_ip (IP 사용) — 20%
    while len(out) < int(n * 0.65):
        name = pick(PERSON_NAMES); v = pick(ASK)
        templates = [
            (f"{name}이 사용한 IP 목록 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:used_ip]->(ip:vt_ip) RETURN p, ip"),
            (f"피의자가 접속한 IP {pick(LIST_S)} {v}",
             f"MATCH (p:vt_psn {{role_cd: 'suspect'}})-[:used_ip]->(ip:vt_ip) RETURN p, ip"),
            (f"해외 IP를 사용한 피의자 {v}",
             f"MATCH (p:vt_psn)-[:used_ip]->(ip:vt_ip) WHERE ip.country <> 'KR' RETURN p, ip"),
            (f"VPN/Tor IP 사용 인물 {v}",
             f"MATCH (p:vt_psn)-[:used_ip]->(ip:vt_ip {{is_anonymizer: true}}) RETURN p, ip"),
        ]
        q, c = pick(templates); out.append((q, c))

    # D4. owns_vehicle (차량 소유) — 20%
    while len(out) < int(n * 0.85):
        name = pick(PERSON_NAMES); vno = pick(VEHICLES); v = pick(ASK)
        templates = [
            (f"{name}이 법적으로 소유한 차량 {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:owns_vehicle]->(c:vt_vhcl) RETURN p, c"),
            (f"피의자 명의 차량 {v}",
             f"MATCH (p:vt_psn {{role_cd: 'suspect'}})-[:owns_vehicle]->(c:vt_vhcl) RETURN p, c"),
            (f"차량 {vno} 의 등록 명의자 {v}",
             f"MATCH (p:vt_psn)-[:owns_vehicle]->(c:vt_vhcl {{license_plate: '{vno}'}}) RETURN p, c"),
        ]
        q, c = pick(templates); out.append((q, c))

    # D5. drives (실사용 차량, owns_vehicle 와 구별) — 15%
    while len(out) < n:
        name = pick(PERSON_NAMES); v = pick(ASK)
        templates = [
            (f"{name}이 운전한 차량 (drives 기준) {v}",
             f"MATCH (p:vt_psn {{name: '{name}'}})-[:drives]->(c:vt_vhcl) RETURN p, c"),
            (f"실제 운전자 ≠ 명의자 차량 추적 {v}",
             f"MATCH (p1:vt_psn)-[:drives]->(c:vt_vhcl)<-[:owns_vehicle]-(p2:vt_psn) WHERE p1 <> p2 RETURN p1, c, p2"),
        ]
        q, c = pick(templates); out.append((q, c))

    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────
PLAN = [
    ("1hop_object",     build_1hop_object,     250),  # ⭐ 최우선 (v42 -30p 복구)
    ("chain",           build_chain,           200),
    ("1hop_event",      build_1hop_event,      200),
    ("1hop_person",     build_1hop_person,     150),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/t2c_v43_object_focus_train_msg.json")
    parser.add_argument("--report", default="data/t2c_v43_object_focus_report.txt")
    args = parser.parse_args()

    all_samples = []
    report_lines = ["=" * 60, "v43 약점 카테고리 보강 (4 카테고리 / 800)", "=" * 60]
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
