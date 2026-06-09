"""
v3.7 신규 패턴 시드 데이터셋 생성기 (규칙 기반 골격)

생성 카테고리 (총 5종):
  1. pt_cluster / belongs_to_cluster      — 진정서 군집
  2. site_cluster / belongs_to_campaign   — 피싱 캠페인
  3. used_in_device + RelayStationDetection — 불법중계기 탐지
  4. vt_psn.is_anonymous                  — 성명불상 피의자
  5. clusters_with deprecated 회피        — 신규 패턴 가이드

출력:
  data/ccop_v37_seed_sharegpt.json (ShareGPT 포맷)

후속 단계 (별도 스크립트):
  - build_v37_augment_gpt4o.py : 시드를 GPT-4o로 다양성 증강
  - build_v37_final.py         : v5 정제본 + v3.7 시드 + GPT-4o 증강분 병합
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

DATA_DIR = Path(__file__).parent
OUT_PATH = DATA_DIR / "ccop_v37_seed_sharegpt.json"


# ──────────────────────────────────────────────────────────────────
# v3.7 SYSTEM PROMPT — 25노드 / 53엣지, 신규 패턴 가이드
# ──────────────────────────────────────────────────────────────────
SYSTEM_PROMPT_V37 = """You are an AgensGraph Native Cypher query expert for cybercrime investigation (CCOP system).

ONTOLOGY: v3.7 (POLE 6-Layer, 25 nodes, 53 edges) — docs/ONTOLOGY_FINAL_ARCHITECTURE_v3.7.md

NEW IN v3.7:
- pt_cluster (Case layer)   : 진정서군집 허브 노드 (clusters_with O(n²) 엣지 대체)
- site_cluster (Object layer): 피싱캠페인군집 허브 노드 (HTML SimHash 지문 기반)
- vt_psn.is_anonymous        : 성명불상 피의자 플래그
- vt_dev.dev_type='relay_station': 불법중계기 (IMEI 공유 전화 3대+ 탐지)

v3.7 NEW EDGES:
- (vt_petition)-[:belongs_to_cluster]->(pt_cluster)    {sim_score, rec_created}
- (vt_site)-[:belongs_to_campaign]->(site_cluster)     {sim_score, detected_at, source_id}
- (vt_telno)-[:used_in_device]->(vt_dev)               {first_seen, last_seen, source_id}

DEPRECATED (read-only, NEVER CREATE):
- (vt_petition)-[:clusters_with]->(vt_petition)  → use belongs_to_cluster via pt_cluster

KEY SCHEMA:
- pt_cluster   : cluster_id★, cluster_method, crime_type_cd, damage_amt_sum, petition_cnt, status, first_rcpt_dt, last_rcpt_dt
- site_cluster : cluster_id★, html_fingerprint, campaign_name, site_cnt, ip_cnt, first_seen, last_seen
- vt_psn       : psn_id★, korn_flnm, name, is_anonymous (true=성명불상)
- vt_dev       : device_id★, dev_type (smartphone|pc|tablet|relay_station|router|other), imei
- vt_telno     : telno★ (no-hyphen)
- vt_petition  : pettn_no★, crime_type_cd, damage_amt, rcpt_dt
- vt_site      : url_addr★, dmn_addr, is_malicious

ABSOLUTE RULES:
1. Output ONLY AgensGraph Native Cypher (MATCH...RETURN). NO SQL wrapper.
2. Never CREATE/MERGE on clusters_with edge (deprecated).
3. telno without hyphens. amount as string.
4. Single line output, no newlines, no explanation."""


# ──────────────────────────────────────────────────────────────────
# 매개변수 풀
# ──────────────────────────────────────────────────────────────────
KOREAN_NAMES = ['김민준', '이서연', '박지호', '최예린', '정현우', '강수아', '조민수',
                '윤도윤', '장하은', '임건우', '한지유', '오재현', '서아인', '신우진',
                '권민서', '황도현', '안서윤', '송지환', '문채원', '백시우']

CRIME_TYPES = [
    ('보이스피싱', 'VP01'), ('스미싱', 'SM01'), ('로맨스스캠', 'RS01'),
    ('투자사기', 'IS01'), ('중고거래사기', 'TS01'), ('대출사기', 'LS01'),
    ('메신저피싱', 'MP01'), ('몸캠피싱', 'BP01'),
]

CAMPAIGNS = [
    '카카오뱅크사칭', '국민은행사칭', '검찰청사칭', '금감원사칭', '경찰청사칭',
    '쿠팡사칭', '네이버사칭', '우체국사칭', '신한은행사칭', '관세청사칭',
]

BANKS = ['국민', '신한', '우리', '하나', '농협', '기업', '카카오뱅크', '토스뱅크']

# 클러스터 ID 풀
PT_CLUSTER_IDS = [f'ptc-2026-{i:03d}' for i in range(1, 51)]
SITE_CLUSTER_IDS = [f'sc-2026-{i:03d}' for i in range(1, 51)]


def rand_date(start='2025-01-01', end='2026-05-12') -> str:
    s = datetime.strptime(start, '%Y-%m-%d').date()
    e = datetime.strptime(end, '%Y-%m-%d').date()
    delta = (e - s).days
    return (s + timedelta(days=random.randint(0, delta))).isoformat()


def rand_telno() -> str:
    return f"010{random.randint(10000000, 99999999)}"


def rand_imei() -> str:
    return ''.join(random.choices('0123456789', k=15))


def rand_domain() -> str:
    prefixes = ['secure', 'login', 'verify', 'account', 'gov', 'help', 'check']
    tlds = ['.com', '.kr', '.co.kr', '.net', '.info', '.xyz']
    return random.choice(prefixes) + str(random.randint(100, 999)) + random.choice(tlds)


def rand_amount(min_v=1_000_000, max_v=500_000_000) -> int:
    return random.randint(min_v // 10000, max_v // 10000) * 10000


# ──────────────────────────────────────────────────────────────────
# 카테고리 1: pt_cluster / belongs_to_cluster (진정서 군집)
# ──────────────────────────────────────────────────────────────────
def gen_pt_cluster_samples(n=200):
    samples = []
    for _ in range(n):
        kind = random.randint(0, 7)
        cluster_id = random.choice(PT_CLUSTER_IDS)
        crime_name, crime_cd = random.choice(CRIME_TYPES)
        amt = rand_amount()

        if kind == 0:
            q = f"피해액 {amt//10000}만원 이상인 진정서 군집 목록 보여줘"
            c = (f"MATCH (c:pt_cluster) WHERE c.damage_amt_sum >= {amt} "
                 f"RETURN c.cluster_id, c.crime_type_cd, c.damage_amt_sum, c.petition_cnt "
                 f"ORDER BY c.damage_amt_sum DESC")
        elif kind == 1:
            q = f"진정서 군집 '{cluster_id}'에 속한 모든 진정서"
            c = (f"MATCH (p:vt_petition)-[:belongs_to_cluster]->(c:pt_cluster {{cluster_id: '{cluster_id}'}}) "
                 f"RETURN p.pettn_no, p.rcpt_dt, p.damage_amt ORDER BY p.rcpt_dt")
        elif kind == 2:
            q = f"{crime_name} 관련 진정서 군집 중 활성 상태인 것"
            c = (f"MATCH (c:pt_cluster) WHERE c.crime_type_cd = '{crime_cd}' AND c.status = 'active' "
                 f"RETURN c.cluster_id, c.petition_cnt, c.damage_amt_sum, c.last_rcpt_dt "
                 f"ORDER BY c.last_rcpt_dt DESC")
        elif kind == 3:
            q = f"진정서 5건 이상이 묶인 군집 보여줘"
            c = (f"MATCH (c:pt_cluster) WHERE c.petition_cnt >= 5 "
                 f"RETURN c.cluster_id, c.crime_type_cd, c.petition_cnt, c.damage_amt_sum "
                 f"ORDER BY c.petition_cnt DESC")
        elif kind == 4:
            q = f"진정서 군집 '{cluster_id}'의 대표 피의자 목록"
            c = (f"MATCH (c:pt_cluster {{cluster_id: '{cluster_id}'}})<-[:belongs_to_cluster]-(p:vt_petition)"
                 f"-[:filed_as]->(case:vt_case)<-[:suspect_in]-(s:vt_psn) "
                 f"RETURN DISTINCT s.psn_id, s.korn_flnm, s.is_anonymous LIMIT 50")
        elif kind == 5:
            d = rand_date()
            q = f"{d} 이후 최초 접수된 진정서 군집"
            c = (f"MATCH (c:pt_cluster) WHERE c.first_rcpt_dt >= '{d}' "
                 f"RETURN c.cluster_id, c.first_rcpt_dt, c.petition_cnt, c.crime_type_cd "
                 f"ORDER BY c.first_rcpt_dt")
        elif kind == 6:
            q = f"SimHash 기반으로 묶인 진정서 군집의 평균 유사도"
            c = (f"MATCH (p:vt_petition)-[r:belongs_to_cluster]->(c:pt_cluster) "
                 f"WHERE c.cluster_method = 'simhash' "
                 f"RETURN c.cluster_id, avg(r.sim_score) AS avg_sim, count(p) AS member_cnt "
                 f"ORDER BY avg_sim DESC")
        else:
            q = f"진정서 군집 통계 — 군집별 진정서 수와 피해액 합계"
            c = (f"MATCH (c:pt_cluster) "
                 f"RETURN c.cluster_id, c.petition_cnt, c.damage_amt_sum, c.status "
                 f"ORDER BY c.damage_amt_sum DESC LIMIT 100")

        samples.append((q, c))
    return samples


# ──────────────────────────────────────────────────────────────────
# 카테고리 2: site_cluster / belongs_to_campaign (피싱 캠페인)
# ──────────────────────────────────────────────────────────────────
def gen_site_cluster_samples(n=200):
    samples = []
    for _ in range(n):
        kind = random.randint(0, 7)
        cluster_id = random.choice(SITE_CLUSTER_IDS)
        campaign = random.choice(CAMPAIGNS)
        domain = rand_domain()

        if kind == 0:
            q = f"'{campaign}' 캠페인에 속한 도메인 전체 보여줘"
            c = (f"MATCH (s:vt_site)-[:belongs_to_campaign]->(c:site_cluster {{campaign_name: '{campaign}'}}) "
                 f"RETURN s.url_addr, s.dmn_addr, s.is_malicious, s.detct_dt ORDER BY s.detct_dt DESC")
        elif kind == 1:
            q = f"피싱 캠페인 군집 중 사이트 10개 이상 묶인 것"
            c = (f"MATCH (c:site_cluster) WHERE c.site_cnt >= 10 "
                 f"RETURN c.cluster_id, c.campaign_name, c.site_cnt, c.ip_cnt "
                 f"ORDER BY c.site_cnt DESC")
        elif kind == 2:
            q = f"도메인 '{domain}'이 속한 캠페인 정보"
            c = (f"MATCH (s:vt_site {{dmn_addr: '{domain}'}})-[:belongs_to_campaign]->(c:site_cluster) "
                 f"RETURN c.cluster_id, c.campaign_name, c.html_fingerprint, c.site_cnt")
        elif kind == 3:
            q = f"캠페인 군집 '{cluster_id}' 관련 IP 주소 전체"
            c = (f"MATCH (s:vt_site)-[:belongs_to_campaign]->(c:site_cluster {{cluster_id: '{cluster_id}'}}), "
                 f"(s)-[:resolves_to]->(ip:vt_ip) "
                 f"RETURN DISTINCT ip.ip_addr, ip.country, ip.is_hosting")
        elif kind == 4:
            d = rand_date()
            q = f"{d} 이후 최초 탐지된 피싱 캠페인"
            c = (f"MATCH (c:site_cluster) WHERE c.first_seen >= '{d}' "
                 f"RETURN c.cluster_id, c.campaign_name, c.first_seen, c.site_cnt "
                 f"ORDER BY c.first_seen")
        elif kind == 5:
            q = f"동일 HTML 지문을 공유하는 사이트 그룹 (SimHash 기준)"
            c = (f"MATCH (s:vt_site)-[r:belongs_to_campaign]->(c:site_cluster) "
                 f"WHERE c.cluster_method = 'simhash' "
                 f"RETURN c.cluster_id, c.html_fingerprint, count(s) AS site_count, "
                 f"avg(r.sim_score) AS avg_sim ORDER BY site_count DESC")
        elif kind == 6:
            q = f"'{campaign}' 캠페인의 피해자 수 집계"
            c = (f"MATCH (c:site_cluster {{campaign_name: '{campaign}'}})<-[:belongs_to_campaign]-(s:vt_site)"
                 f"<-[:accessed_to]-(a:vt_access)<-[:recorded_in]-(v:vt_psn) "
                 f"RETURN count(DISTINCT v) AS victim_cnt")
        else:
            q = f"활성 피싱 캠페인 군집과 최근 탐지일"
            c = (f"MATCH (c:site_cluster) "
                 f"RETURN c.cluster_id, c.campaign_name, c.last_seen, c.site_cnt, c.ip_cnt "
                 f"ORDER BY c.last_seen DESC LIMIT 50")

        samples.append((q, c))
    return samples


# ──────────────────────────────────────────────────────────────────
# 카테고리 3: used_in_device + RelayStationDetection (불법중계기)
# ──────────────────────────────────────────────────────────────────
def gen_relay_station_samples(n=200):
    samples = []
    for _ in range(n):
        kind = random.randint(0, 6)
        telno = rand_telno()
        imei = rand_imei()

        if kind == 0:
            q = f"동일 IMEI에 3개 이상 전화번호가 사용된 불법중계기 탐지"
            c = (f"MATCH (t:vt_telno)-[:used_in_device]->(d:vt_dev) "
                 f"WITH d, collect(t.telno) AS phones, count(t) AS phone_cnt "
                 f"WHERE phone_cnt >= 3 "
                 f"RETURN d.device_id, d.imei, d.dev_type, phone_cnt, phones "
                 f"ORDER BY phone_cnt DESC")
        elif kind == 1:
            q = f"IMEI '{imei}'에 등록된 전화번호 전체"
            c = (f"MATCH (t:vt_telno)-[r:used_in_device]->(d:vt_dev {{imei: '{imei}'}}) "
                 f"RETURN t.telno, r.first_seen, r.last_seen ORDER BY r.first_seen")
        elif kind == 2:
            q = f"전화번호 '{telno}'이 사용된 기기 이력"
            c = (f"MATCH (t:vt_telno {{telno: '{telno}'}})-[r:used_in_device]->(d:vt_dev) "
                 f"RETURN d.device_id, d.imei, d.dev_type, r.first_seen, r.last_seen "
                 f"ORDER BY r.first_seen")
        elif kind == 3:
            q = f"불법중계기로 분류된 기기 목록"
            c = (f"MATCH (d:vt_dev) WHERE d.dev_type = 'relay_station' "
                 f"RETURN d.device_id, d.imei, d.model, d.os ORDER BY d.device_id")
        elif kind == 4:
            q = f"불법중계기에 연결된 전화번호의 명의자 정보"
            c = (f"MATCH (d:vt_dev {{dev_type: 'relay_station'}})<-[:used_in_device]-(t:vt_telno)"
                 f"-[:registered_to]->(p:vt_psn) "
                 f"RETURN d.device_id, t.telno, p.korn_flnm, p.is_anonymous")
        elif kind == 5:
            q = f"기기당 사용된 전화번호 수가 많은 순으로 정렬 (TOP 20)"
            c = (f"MATCH (t:vt_telno)-[:used_in_device]->(d:vt_dev) "
                 f"WITH d, count(t) AS phone_cnt "
                 f"RETURN d.device_id, d.imei, d.dev_type, phone_cnt "
                 f"ORDER BY phone_cnt DESC LIMIT 20")
        else:
            d = rand_date()
            q = f"{d} 이후 새로 식별된 불법중계기"
            c = (f"MATCH (t:vt_telno)-[r:used_in_device]->(d:vt_dev) "
                 f"WHERE d.dev_type = 'relay_station' AND r.first_seen >= '{d}' "
                 f"RETURN d.device_id, d.imei, count(t) AS phone_cnt, min(r.first_seen) AS detected_at "
                 f"ORDER BY detected_at DESC")

        samples.append((q, c))
    return samples


# ──────────────────────────────────────────────────────────────────
# 카테고리 4: vt_psn.is_anonymous (성명불상)
# ──────────────────────────────────────────────────────────────────
def gen_anonymous_person_samples(n=200):
    samples = []
    for _ in range(n):
        kind = random.randint(0, 6)
        name = random.choice(KOREAN_NAMES)
        crime_name, crime_cd = random.choice(CRIME_TYPES)
        amt = rand_amount()

        if kind == 0:
            q = f"성명불상 피의자가 연루된 사건 전체"
            c = (f"MATCH (p:vt_psn {{is_anonymous: true}})-[:suspect_in]->(c:vt_case) "
                 f"RETURN c.flnm, c.crime_type_cd, p.psn_id ORDER BY c.flnm")
        elif kind == 1:
            q = f"성명불상 피의자가 연루된 {crime_name} 사건"
            c = (f"MATCH (p:vt_psn {{is_anonymous: true}})-[:suspect_in]->(c:vt_case {{crime_type_cd: '{crime_cd}'}}) "
                 f"RETURN c.flnm, p.psn_id, c.rcpt_dt ORDER BY c.rcpt_dt DESC")
        elif kind == 2:
            q = f"성명불상 피의자 수 집계"
            c = (f"MATCH (p:vt_psn) WHERE p.is_anonymous = true "
                 f"RETURN count(p) AS anonymous_cnt")
        elif kind == 3:
            q = f"성명불상 피의자가 사용한 전화번호 목록"
            c = (f"MATCH (p:vt_psn {{is_anonymous: true}})-[:owns_phone]->(t:vt_telno) "
                 f"RETURN p.psn_id, collect(t.telno) AS phones")
        elif kind == 4:
            q = f"피해액 {amt//10000}만원 이상 사건의 성명불상 피의자"
            c = (f"MATCH (p:vt_psn {{is_anonymous: true}})-[:suspect_in]->(c:vt_case), "
                 f"(c)-[:eg_used_account]->(b:vt_bacnt)-[:from_account]->(tr:vt_transfer) "
                 f"WHERE tr.amount >= '{amt}' "
                 f"RETURN DISTINCT p.psn_id, c.flnm, tr.amount")
        elif kind == 5:
            q = f"동일인 가능성이 검토 중인 성명불상-기지(known) 인물 쌍"
            c = (f"MATCH (anon:vt_psn {{is_anonymous: true}})-[r:sameAs]->(known:vt_psn {{is_anonymous: false}}) "
                 f"WHERE r.review_status = 'pending' "
                 f"RETURN anon.psn_id, known.korn_flnm, r.match_score "
                 f"ORDER BY r.match_score DESC")
        else:
            q = f"신원이 확정된 피의자만 조회 (성명불상 제외)"
            c = (f"MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) "
                 f"WHERE p.is_anonymous = false OR p.is_anonymous IS NULL "
                 f"RETURN p.korn_flnm, c.flnm, c.crime_type_cd ORDER BY c.flnm")

        samples.append((q, c))
    return samples


# ──────────────────────────────────────────────────────────────────
# 카테고리 5: clusters_with deprecated → belongs_to_cluster 가이드
# ──────────────────────────────────────────────────────────────────
def gen_deprecated_avoidance_samples(n=100):
    """clusters_with 패턴을 떠올릴 만한 질문에 대해 belongs_to_cluster를 출력하도록 학습"""
    samples = []
    crime_pool = CRIME_TYPES.copy()
    for _ in range(n):
        kind = random.randint(0, 4)
        crime_name, crime_cd = random.choice(crime_pool)

        if kind == 0:
            q = f"유사한 진정서끼리 묶어서 보여줘"
            c = (f"MATCH (p:vt_petition)-[:belongs_to_cluster]->(c:pt_cluster) "
                 f"RETURN c.cluster_id, collect(p.pettn_no) AS petitions, c.petition_cnt "
                 f"ORDER BY c.petition_cnt DESC")
        elif kind == 1:
            q = f"진정서 'PT-2026-12345'와 유사한 진정서 목록"
            c = (f"MATCH (target:vt_petition {{pettn_no: 'PT-2026-12345'}})-[:belongs_to_cluster]->(c:pt_cluster)"
                 f"<-[:belongs_to_cluster]-(other:vt_petition) "
                 f"WHERE other.pettn_no <> 'PT-2026-12345' "
                 f"RETURN other.pettn_no, other.rcpt_dt, c.cluster_id")
        elif kind == 2:
            q = f"{crime_name} 진정서들의 군집 패턴"
            c = (f"MATCH (p:vt_petition {{crime_type_cd: '{crime_cd}'}})-[:belongs_to_cluster]->(c:pt_cluster) "
                 f"RETURN c.cluster_id, c.petition_cnt, c.damage_amt_sum "
                 f"ORDER BY c.petition_cnt DESC")
        elif kind == 3:
            q = f"진정서 간 유사도가 0.8 이상인 그룹"
            c = (f"MATCH (p:vt_petition)-[r:belongs_to_cluster]->(c:pt_cluster) "
                 f"WHERE r.sim_score >= 0.8 "
                 f"RETURN c.cluster_id, count(p) AS member_cnt, avg(r.sim_score) AS avg_sim "
                 f"ORDER BY avg_sim DESC")
        else:
            q = f"같은 수법으로 추정되는 진정서 묶음"
            c = (f"MATCH (c:pt_cluster)<-[:belongs_to_cluster]-(p:vt_petition) "
                 f"WHERE c.petition_cnt >= 3 "
                 f"RETURN c.cluster_id, c.crime_type_cd, c.petition_cnt, "
                 f"collect(p.pettn_no)[..10] AS sample_petitions "
                 f"ORDER BY c.petition_cnt DESC")

        samples.append((q, c))
    return samples


# ──────────────────────────────────────────────────────────────────
# ShareGPT 변환 및 메인
# ──────────────────────────────────────────────────────────────────
def to_sharegpt(question: str, cypher: str) -> dict:
    return {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT_V37},
            {"from": "human",  "value": question},
            {"from": "gpt",    "value": cypher},
        ]
    }


def main():
    all_pairs = []
    all_pairs.extend(gen_pt_cluster_samples(200))
    all_pairs.extend(gen_site_cluster_samples(200))
    all_pairs.extend(gen_relay_station_samples(200))
    all_pairs.extend(gen_anonymous_person_samples(200))
    all_pairs.extend(gen_deprecated_avoidance_samples(100))

    # 중복 제거 (질문 기준)
    seen = set()
    unique = []
    for q, c in all_pairs:
        key = (q.strip(), c.strip())
        if key in seen:
            continue
        seen.add(key)
        unique.append((q, c))

    random.shuffle(unique)
    samples = [to_sharegpt(q, c) for q, c in unique]

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)

    # 카테고리별 통계
    cat_counts = {'pt_cluster': 0, 'site_cluster': 0, 'used_in_device': 0,
                  'is_anonymous': 0, 'belongs_to_cluster_only': 0}
    for q, c in unique:
        if 'pt_cluster' in c:
            cat_counts['pt_cluster'] += 1
        if 'site_cluster' in c:
            cat_counts['site_cluster'] += 1
        if 'used_in_device' in c or "'relay_station'" in c:
            cat_counts['used_in_device'] += 1
        if 'is_anonymous' in c:
            cat_counts['is_anonymous'] += 1
        if 'belongs_to_cluster' in c and 'pt_cluster' not in c:
            cat_counts['belongs_to_cluster_only'] += 1

    print(f"✅ 생성 완료: {len(samples)}개 시드 샘플")
    print(f"   출력: {OUT_PATH}")
    print(f"   카테고리별 등장 (Cypher 기준):")
    for k, v in cat_counts.items():
        print(f"     {k:30s}: {v:4d}건")


if __name__ == "__main__":
    main()
