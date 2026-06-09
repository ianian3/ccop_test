"""
build_v40_weakness_seed.py — v39 잔여 약점 8 패턴 1,650 시드 보강
============================================================
근거: docs/V40_WEAKNESS_SEED_CANDIDATES_20260522.md
     V4.0 자연어 45 케이스 테스트 결과 (v39 68.9%) 14 실패 분석

8 패턴 (총 1,650):
  P1. partial_match    200  CONTAINS / STARTS WITH
  P2. multi_where      400  AND/OR 다중 조건
  P3. meta_filter      300  source_domain / reliability_tier
  P4. time_order       200  ORDER BY occurred_at DESC LIMIT N
  P5. edge_direction   200  방향 정확성 (hosts, has_account 등)
  P6. edge_naming      150  involves(deprecated) → suspect_in/victim_in
  P7. hub_node_simple  100  pt_cluster, site_cluster, vt_dev 단순 RETURN
  P8. no_cast          100  ::int / ::float 캐스팅 금지

출력: data/t2c_v40_weakness_train_msg.json (OpenAI messages format)
사용: python data/build_v40_weakness_seed.py
"""
import argparse
import json
import random
from pathlib import Path

random.seed(20260526)

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
REGIONS = ["강남", "부산", "대구", "대전", "광주", "인천", "수원", "성남", "고양", "용인"]
CRIMES = ["보이스피싱", "스미싱", "사칭", "메신저피싱", "로맨스스캠", "투자사기",
          "전세사기", "대출사기", "가족사칭", "기관사칭"]
CASE_NOS = ["CASE-2026-A-001", "CASE-2026-A-002", "CASE-2026-A-003",
            "C-2025-0301", "C-2026-0044", "2026-사이버-001"]
ACCOUNTS = ["110-1111-2222", "302-9988-7766", "1002-110-100001", "352-7788-9900"]
TELNOS = ["01099999999", "01011112222", "01033445566", "01077778888", "07012345678"]
IPS = ["192.168.1.10", "203.0.113.5", "118.32.45.67", "211.114.22.88"]
SITES = ["https://malicious-site.example", "https://kb-phish.example", "https://kakao-fake.example"]
DOMAINS = ['investigation', 'osint', 'partner', 'inference']
DOMAINS_RDB = ['KICS', 'OSINT', 'DIGITAL', 'EXT']
# RDB ↔ canonical 매핑 — rdb 와 dom 을 동기화해서 pick 할 때 사용
RDB_TO_CODE = {'KICS': 'investigation', 'OSINT': 'osint',
               'DIGITAL': 'partner', 'EXT': 'partner'}
TIERS = [1, 2, 3, 4]
AMOUNTS = [100000, 500000, 1000000, 3000000, 5000000, 10000000]

ASK = ["보여주세요", "찾아주세요", "조회해주세요", "검색해주세요", "출력해주세요", "알려주세요"]
LIST_S = ["목록", "전체", "리스트", "전부"]
PRE = ["", "혹시 ", "급한데 ", "특히 ", "참고로 ", "확인 차 "]
SUF = ["", " 부탁드립니다", "", " (긴급)", ""]


def pick(arr):
    return random.choice(arr)


def diversify(q: str) -> str:
    return (pick(PRE) + q + pick(SUF)).strip()


# ──────────────────────────────────────────────────────────────────────────────
# P1. partial_match (CONTAINS) — 200
# ──────────────────────────────────────────────────────────────────────────────
def build_partial_match(n=200):
    out = []
    while len(out) < int(n * 0.4):
        region = pick(REGIONS)
        v = pick(ASK)
        templates = [
            (f"{region} 사건 {pick(LIST_S)} {v}",
             f"MATCH (c:vt_case) WHERE c.flnm CONTAINS '{region}' RETURN c"),
            (f"{region} 관련 사건의 피의자 {v}",
             f"MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) WHERE c.flnm CONTAINS '{region}' RETURN p, c"),
            (f"{region} 지역 피의자가 보유한 계좌 {v}",
             f"MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) WHERE p.name CONTAINS '{region}' RETURN p, b"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.7):
        crime = pick(CRIMES)
        v = pick(ASK)
        templates = [
            (f"{crime} 관련 사건 {pick(LIST_S)} {v}",
             f"MATCH (c:vt_case) WHERE c.crime_type CONTAINS '{crime}' OR c.flnm CONTAINS '{crime}' RETURN c"),
            (f"{crime} 사건의 피의자 {v}",
             f"MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) WHERE c.crime_type CONTAINS '{crime}' RETURN p, c"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < n:
        org = pick(ORG_NAMES)
        v = pick(ASK)
        templates = [
            (f"{org} 사칭 사이트 {pick(LIST_S)} {v}",
             f"MATCH (s:vt_site) WHERE s.domain CONTAINS '{org}' OR s.url_addr CONTAINS '{org}' RETURN s"),
            (f"{org} 명의 계좌 {pick(LIST_S)} {v}",
             f"MATCH (b:vt_bacnt) WHERE b.holder_nm CONTAINS '{org}' RETURN b"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# P2. multi_where (AND/OR) — 400
# ──────────────────────────────────────────────────────────────────────────────
def build_multi_where(n=400):
    out = []
    # 다중 AND — 노드 속성
    while len(out) < int(n * 0.3):
        v = pick(ASK)
        dom = pick(['osint', 'investigation', 'partner'])
        templates = [
            (f"익명이면서 {dom.upper()} 출처인 인물 {v}",
             f"MATCH (p:vt_psn) WHERE p.is_anonymous = true AND p.source_domain = '{dom}' RETURN p"),
            (f"{dom.upper()} 도메인이면서 신뢰도 {pick(TIERS)} 이상인 계좌 {v}",
             f"MATCH (b:vt_bacnt) WHERE b.source_domain = '{dom}' AND b.reliability_tier <= {pick(TIERS)} RETURN b"),
            (f"VOIP 통신사이면서 중계기 경유한 전화 {v}",
             f"MATCH (t:vt_telno)-[:used_in_device]->(d:vt_dev) WHERE t.carr_cd = 'VOIP' AND d.dev_type = 'relay_station' RETURN t, d"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 숫자 비교 (캐스팅 없이)
    while len(out) < int(n * 0.55):
        amt = pick(AMOUNTS)
        v = pick(ASK)
        man_unit = f"{amt//10000}만원" if amt < 10000000 else f"{amt//10000000}천만원"
        templates = [
            (f"금액 {man_unit} 이상 이체 {v}",
             f"MATCH (t:vt_transfer) WHERE t.amount >= {amt} RETURN t"),
            (f"통화 {pick([30, 60, 120, 300])}초 이상 {pick(LIST_S)} {v}",
             f"MATCH (c:vt_call) WHERE c.duration >= {pick([30,60,120,300])} RETURN c"),
            (f"금액 {man_unit} 이상이면서 {dom.upper()} 도메인 이체 {v}",
             f"MATCH (t:vt_transfer) WHERE t.amount >= {amt} AND t.source_domain = '{pick(['investigation','osint'])}' RETURN t"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # OR 패턴
    while len(out) < int(n * 0.75):
        v = pick(ASK)
        templates = [
            (f"피의자 또는 피해자 인물 {v}",
             f"MATCH (p:vt_psn) WHERE p.role_cd = 'suspect' OR p.role_cd = 'victim' RETURN p"),
            (f"국민은행 또는 신한은행 계좌 {v}",
             f"MATCH (b:vt_bacnt) WHERE b.bnk_cd = '004' OR b.bnk_cd = '088' RETURN b"),
            (f"SKT 또는 KT 통신사 전화 {v}",
             f"MATCH (t:vt_telno) WHERE t.carr_cd = 'SKT' OR t.carr_cd = 'KT' RETURN t"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 다중 AND + 엣지 결합
    while len(out) < n:
        v = pick(ASK)
        amt = pick(AMOUNTS)
        templates = [
            (f"익명 인물이 보유한 OSINT 계좌의 이체 내역 {v}",
             "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer) "
             "WHERE p.is_anonymous = true AND b.source_domain = 'osint' RETURN p, b, t"),
            (f"신뢰도 1인 사건과 그 피의자 {v}",
             "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) "
             "WHERE c.reliability_tier = 1 RETURN p, c"),
            (f"{amt} 이상 이체이면서 OSINT 출처인 거래 {v}",
             f"MATCH (t:vt_transfer) WHERE t.amount >= {amt} AND t.source_domain = 'osint' RETURN t"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# P3. meta_filter (V4.0 source_domain / reliability_tier) — 300
# ──────────────────────────────────────────────────────────────────────────────
def build_meta_filter(n=300):
    out = []
    while len(out) < int(n * 0.35):
        rdb = pick(DOMAINS_RDB)
        dom = RDB_TO_CODE[rdb]   # rdb ↔ canonical 매핑으로 동기화
        v = pick(ASK)
        templates = [
            (f"{rdb} 도메인 노드 {pick(LIST_S)} {v}",
             f"MATCH (n) WHERE n.source_domain = '{dom}' RETURN n"),
            (f"{rdb} 출처 계좌 {v}",
             f"MATCH (b:vt_bacnt) WHERE b.source_domain = '{dom}' RETURN b"),
            (f"{rdb} 도메인 인물 {v}",
             f"MATCH (p:vt_psn) WHERE p.source_domain = '{dom}' RETURN p"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.65):
        tier = pick(TIERS)
        v = pick(ASK)
        tier_kor = {1: '공식', 2: '수사', 3: '시민제보', 4: '웹수집'}.get(tier, '')
        templates = [
            (f"신뢰도 {tier} 노드 {pick(LIST_S)} {v}",
             f"MATCH (n) WHERE n.reliability_tier = {tier} RETURN n"),
            (f"신뢰도 {tier} ({tier_kor}) 계좌 {v}",
             f"MATCH (b:vt_bacnt) WHERE b.reliability_tier = {tier} RETURN b"),
            (f"신뢰도 {tier} 이상 노드 {v}",
             f"MATCH (n) WHERE n.reliability_tier <= {tier} RETURN n"),
            (f"공식 데이터만 {v}",
             f"MATCH (n) WHERE n.reliability_tier <= 2 RETURN n"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 도메인별 집계
    while len(out) < int(n * 0.85):
        v = pick(ASK)
        templates = [
            (f"도메인별 노드 수 {v}",
             "MATCH (n) RETURN n.source_domain AS domain, count(n) AS cnt ORDER BY cnt DESC"),
            (f"도메인별 계좌 통계 {v}",
             "MATCH (b:vt_bacnt) RETURN b.source_domain AS domain, count(b) AS cnt"),
            (f"신뢰도 등급별 노드 수 {v}",
             "MATCH (n) RETURN n.reliability_tier AS tier, count(n) AS cnt ORDER BY tier"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 메타 + 1-hop
    while len(out) < n:
        rdb = pick(DOMAINS_RDB)
        dom = RDB_TO_CODE[rdb]   # 동기화
        v = pick(ASK)
        templates = [
            (f"{rdb} 계좌의 이체 내역 {v}",
             f"MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer) "
             f"WHERE b.source_domain = '{dom}' RETURN b, t"),
            (f"{rdb} 인물이 소유한 전화 {v}",
             f"MATCH (p:vt_psn)-[:owns_phone]->(t:vt_telno) "
             f"WHERE p.source_domain = '{dom}' RETURN p, t"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# P4. time_order (ORDER BY occurred_at) — 200
# ──────────────────────────────────────────────────────────────────────────────
def build_time_order(n=200):
    out = []
    while len(out) < int(n * 0.4):
        k = pick([3, 5, 10, 20])
        v = pick(ASK)
        templates = [
            (f"최근 이체 {k}건 {v}",
             f"MATCH (t:vt_transfer) RETURN t ORDER BY t.occurred_at DESC LIMIT {k}"),
            (f"최근 통화 {k}건 {v}",
             f"MATCH (c:vt_call) RETURN c ORDER BY c.occurred_at DESC LIMIT {k}"),
            (f"최근 접속 {k}건 {v}",
             f"MATCH (a:vt_access) RETURN a ORDER BY a.occurred_at DESC LIMIT {k}"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.65):
        k = pick([3, 5, 10])
        v = pick(ASK)
        templates = [
            (f"오래된 이체 {k}건 {v}",
             f"MATCH (t:vt_transfer) RETURN t ORDER BY t.occurred_at ASC LIMIT {k}"),
            (f"가장 오래된 통화 {k}건 {v}",
             f"MATCH (c:vt_call) RETURN c ORDER BY c.occurred_at ASC LIMIT {k}"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 시간 범위 + 정렬
    while len(out) < int(n * 0.85):
        v = pick(ASK)
        templates = [
            (f"오늘 이체 {v}",
             "MATCH (t:vt_transfer) WHERE t.occurred_at >= date() RETURN t ORDER BY t.occurred_at DESC"),
            (f"이번 주 통화 {v}",
             "MATCH (c:vt_call) WHERE c.occurred_at >= date() - duration({days: 7}) RETURN c"),
            (f"이번 달 이체 금액 큰 순 {v}",
             "MATCH (t:vt_transfer) WHERE t.occurred_at >= date('2026-05-01') "
             "RETURN t ORDER BY t.amount DESC"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # 정렬 + 메타 결합
    while len(out) < n:
        v = pick(ASK)
        dom = pick(['osint', 'investigation'])
        k = pick([5, 10, 20])
        templates = [
            (f"{dom.upper()} 도메인 최근 이체 {k}건 {v}",
             f"MATCH (t:vt_transfer) WHERE t.source_domain = '{dom}' "
             f"RETURN t ORDER BY t.occurred_at DESC LIMIT {k}"),
            (f"최근 익명 인물 {k}명 {v}",
             f"MATCH (p:vt_psn) WHERE p.is_anonymous = true "
             f"RETURN p ORDER BY p.rec_created DESC LIMIT {k}"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# P5. edge_direction — 200
# ──────────────────────────────────────────────────────────────────────────────
def build_edge_direction(n=200):
    out = []
    # hosts: IP → site
    while len(out) < int(n * 0.25):
        v = pick(ASK)
        templates = [
            (f"사이트가 호스팅된 IP {v}",
             "MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) RETURN ip, s"),
            (f"피싱 사이트의 호스팅 서버 IP {v}",
             "MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) RETURN ip, s LIMIT 20"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # has_account: psn → bacnt
    while len(out) < int(n * 0.45):
        v = pick(ASK)
        templates = [
            (f"피의자가 보유한 계좌 {v}",
             "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) RETURN p, b"),
            (f"계좌 소유 인물 {v}",
             "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) RETURN p, b"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # from_account / to_account
    while len(out) < int(n * 0.7):
        v = pick(ASK)
        templates = [
            (f"계좌에서 출금된 이체 {v}",
             "MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer) RETURN b, t"),
            (f"입금받은 이체 {v}",
             "MATCH (t:vt_transfer)-[:to_account]->(b:vt_bacnt) RETURN t, b"),
            (f"계좌 간 자금 이동 흐름 {v}",
             "MATCH (a:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b:vt_bacnt) "
             "RETURN a, t, b"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # caller/callee
    while len(out) < int(n * 0.85):
        v = pick(ASK)
        templates = [
            (f"발신한 통화 {v}",
             "MATCH (t:vt_telno)-[:caller]->(c:vt_call) RETURN t, c"),
            (f"수신한 통화 {v}",
             "MATCH (c:vt_call)-[:callee]->(t:vt_telno) RETURN c, t"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    # used_in_device, belongs_to_*
    while len(out) < n:
        v = pick(ASK)
        templates = [
            (f"중계기를 경유한 전화 {v}",
             "MATCH (t:vt_telno)-[:used_in_device]->(d:vt_dev) "
             "WHERE d.dev_type = 'relay_station' RETURN t, d"),
            (f"사이트 캠페인 소속 사이트 {v}",
             "MATCH (s:vt_site)-[:belongs_to_campaign]->(sc:site_cluster) RETURN s, sc"),
            (f"클러스터에 속한 피의자 {v}",
             "MATCH (p:vt_psn)-[:belongs_to_cluster]->(pc:pt_cluster) RETURN p, pc"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# P6. edge_naming (involves deprecated → suspect_in/victim_in) — 150
# ──────────────────────────────────────────────────────────────────────────────
def build_edge_naming(n=150):
    out = []
    while len(out) < int(n * 0.4):
        v = pick(ASK)
        templates = [
            (f"사건의 피의자 {v}",
             "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) RETURN p, c"),
            (f"사건별 피의자 수 {v}",
             "MATCH (c:vt_case)<-[:suspect_in]-(p:vt_psn) "
             "RETURN c.flnm AS case, count(p) AS suspects ORDER BY suspects DESC"),
            (f"피의자가 가장 많은 사건 {v}",
             "MATCH (c:vt_case)<-[:suspect_in]-(p:vt_psn) "
             "RETURN c.flnm, count(p) AS cnt ORDER BY cnt DESC LIMIT 5"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.7):
        v = pick(ASK)
        templates = [
            (f"사건의 피해자 {v}",
             "MATCH (p:vt_psn)-[:victim_in]->(c:vt_case) RETURN p, c"),
            (f"피해자가 있는 사건 {v}",
             "MATCH (c:vt_case)<-[:victim_in]-(p:vt_psn) RETURN c, p"),
            (f"사건별 피해자 수 {v}",
             "MATCH (c:vt_case)<-[:victim_in]-(p:vt_psn) "
             "RETURN c.flnm, count(p) AS victims ORDER BY victims DESC"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < n:
        v = pick(ASK)
        templates = [
            (f"참고인 진술이 있는 사건 {v}",
             "MATCH (c:vt_case)<-[:witness_in]-(p:vt_psn) RETURN c, p"),
            (f"사건의 모든 관련 인물 {v}",
             "MATCH (p:vt_psn)-[r:suspect_in|victim_in|witness_in]->(c:vt_case) "
             "RETURN p, type(r) AS role, c"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# P7. hub_node_simple (pt_cluster / site_cluster / vt_dev) — 100
# ──────────────────────────────────────────────────────────────────────────────
def build_hub_node_simple(n=100):
    out = []
    while len(out) < int(n * 0.35):
        v = pick(ASK)
        templates = [
            ("pt_cluster 노드 " + v,                "MATCH (c:pt_cluster) RETURN c"),
            ("pt_cluster 전체 " + v,                "MATCH (c:pt_cluster) RETURN c LIMIT 50"),
            ("캠페인 군집 " + pick(LIST_S) + " " + v, "MATCH (c:pt_cluster) RETURN c"),
            ("범죄 조직 클러스터 " + v,              "MATCH (c:pt_cluster) RETURN c"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.7):
        v = pick(ASK)
        templates = [
            ("site_cluster 노드 " + v,         "MATCH (c:site_cluster) RETURN c"),
            ("피싱 사이트 클러스터 " + v,        "MATCH (c:site_cluster) RETURN c"),
            ("사이트 군집 " + pick(LIST_S) + " " + v, "MATCH (c:site_cluster) RETURN c LIMIT 50"),
            ("OSINT 자동 군집 결과 " + v,       "MATCH (c:site_cluster) RETURN c"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < n:
        v = pick(ASK)
        templates = [
            ("중계기 노드 " + v,
             "MATCH (d:vt_dev) WHERE d.dev_type = 'relay_station' RETURN d"),
            ("relay_station 기기 " + v,
             "MATCH (d:vt_dev {dev_type: 'relay_station'}) RETURN d"),
            ("vt_dev 전체 " + v,
             "MATCH (d:vt_dev) RETURN d"),
            ("익명 사용자 " + v,
             "MATCH (p:vt_psn) WHERE p.is_anonymous = true RETURN p"),
            ("익명 ID " + v,
             "MATCH (i:vt_id) WHERE i.is_anonymous = true RETURN i"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# P8. no_cast (::int / ::float 금지) — 100
# ──────────────────────────────────────────────────────────────────────────────
def build_no_cast(n=100):
    """모델이 ::int 캐스팅을 학습 분포에서 흔히 시도. AgensGraph 에서는 agtype 자동 비교 가능."""
    out = []
    while len(out) < int(n * 0.5):
        amt = pick(AMOUNTS)
        v = pick(ASK)
        templates = [
            (f"금액 {amt} 이상 이체 {v}",
             f"MATCH (t:vt_transfer) WHERE t.amount >= {amt} RETURN t"),
            (f"금액 {amt} 미만 이체 {v}",
             f"MATCH (t:vt_transfer) WHERE t.amount < {amt} RETURN t"),
            (f"금액 {amt} 이상 {amt*5} 이하 이체 {v}",
             f"MATCH (t:vt_transfer) WHERE t.amount >= {amt} AND t.amount <= {amt*5} RETURN t"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < int(n * 0.8):
        dur = pick([30, 60, 120, 300, 600])
        v = pick(ASK)
        templates = [
            (f"통화 시간 {dur}초 이상 {v}",
             f"MATCH (c:vt_call) WHERE c.duration >= {dur} RETURN c"),
            (f"통화 시간 {dur}초 미만 {v}",
             f"MATCH (c:vt_call) WHERE c.duration < {dur} RETURN c"),
        ]
        q, c = pick(templates)
        out.append((q, c))

    while len(out) < n:
        tier = pick(TIERS)
        v = pick(ASK)
        templates = [
            (f"신뢰도 {tier} 이상 노드 {v}",
             f"MATCH (n) WHERE n.reliability_tier <= {tier} RETURN n"),
            (f"신뢰도 {tier} 미만 노드 {v}",
             f"MATCH (n) WHERE n.reliability_tier > {tier} RETURN n"),
        ]
        q, c = pick(templates)
        out.append((q, c))
    return out[:n]


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────
PLAN = [
    ("multi_where",      build_multi_where,      400),
    ("meta_filter",      build_meta_filter,      300),
    ("partial_match",    build_partial_match,    200),
    ("time_order",       build_time_order,       200),
    ("edge_direction",   build_edge_direction,   200),
    ("edge_naming",      build_edge_naming,      150),
    ("hub_node_simple",  build_hub_node_simple,  100),
    ("no_cast",          build_no_cast,          100),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/t2c_v40_weakness_train_msg.json")
    parser.add_argument("--report", default="data/t2c_v40_weakness_report.txt")
    args = parser.parse_args()

    all_samples = []
    report_lines = ["=" * 60, "v40 약점 보강 시드 빌더 (8 패턴 / 1,650)", "=" * 60]
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
        if q in seen:
            continue
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
