"""
v3.7 멀티홉 / shortestPath / var-hop 추가 시드 생성기

현재 v3.7 신규 패턴이 다음 hop 카테고리에 부재:
  - 2-hop: 144개 (3.3%) — 부족
  - 4-hop+: 0개
  - var-hop (*N..M): 0개
  - shortestPath: 0개

본 스크립트는 위 카테고리를 채우는 시드를 생성한다.

출력: data/ccop_v37_multihop_seed_sharegpt.json
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(2026)

DATA_DIR = Path(__file__).parent
OUT_PATH = DATA_DIR / "ccop_v37_multihop_seed_sharegpt.json"


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
                '윤도윤', '장하은', '임건우', '한지유', '오재현', '서아인', '신우진']

CRIME_TYPES = [
    ('보이스피싱', 'VP01'), ('스미싱', 'SM01'), ('로맨스스캠', 'RS01'),
    ('투자사기', 'IS01'), ('중고거래사기', 'TS01'), ('메신저피싱', 'MP01'),
]

CAMPAIGNS = [
    '카카오뱅크사칭', '국민은행사칭', '검찰청사칭', '금감원사칭', '경찰청사칭',
    '쿠팡사칭', '네이버사칭', '우체국사칭',
]

PT_CLUSTER_IDS = [f'ptc-2026-{i:03d}' for i in range(1, 51)]
SITE_CLUSTER_IDS = [f'sc-2026-{i:03d}' for i in range(1, 51)]


def rand_amount(min_v=1_000_000, max_v=500_000_000) -> int:
    return random.randint(min_v // 10000, max_v // 10000) * 10000


def rand_telno() -> str:
    return f"010{random.randint(10000000, 99999999)}"


def rand_imei() -> str:
    return ''.join(random.choices('0123456789', k=15))


def rand_date(start='2025-01-01', end='2026-05-12') -> str:
    s = datetime.strptime(start, '%Y-%m-%d').date()
    e = datetime.strptime(end, '%Y-%m-%d').date()
    return (s + timedelta(days=random.randint(0, (e - s).days))).isoformat()


# ──────────────────────────────────────────────────────────────────
# 2-hop pt_cluster 패턴 (~100개)
# ──────────────────────────────────────────────────────────────────
def gen_2hop_pt_cluster(n=100):
    samples = []
    for _ in range(n):
        kind = random.randint(0, 5)
        cid = random.choice(PT_CLUSTER_IDS)
        crime_name, crime_cd = random.choice(CRIME_TYPES)
        amt = rand_amount()

        if kind == 0:
            q = f"진정서 군집 '{cid}'에 속한 진정서들이 어떤 사건과 연결되어 있어?"
            c = (f"MATCH (c:pt_cluster {{cluster_id: '{cid}'}})<-[:belongs_to_cluster]-(p:vt_petition)"
                 f"-[:filed_as]->(case:vt_case) "
                 f"RETURN c.cluster_id, p.pettn_no, case.flnm, case.crime_type_cd")
        elif kind == 1:
            q = f"{crime_name} 군집 중 피해액 합계가 {amt//10000}만원 이상인 진정서 목록"
            c = (f"MATCH (c:pt_cluster {{crime_type_cd: '{crime_cd}'}})<-[:belongs_to_cluster]-(p:vt_petition) "
                 f"WHERE c.damage_amt_sum >= {amt} "
                 f"RETURN c.cluster_id, p.pettn_no, p.damage_amt, p.rcpt_dt "
                 f"ORDER BY c.damage_amt_sum DESC")
        elif kind == 2:
            q = f"진정서 군집 '{cid}'에 속한 진정서들의 접수일자별 분포"
            c = (f"MATCH (c:pt_cluster {{cluster_id: '{cid}'}})<-[:belongs_to_cluster]-(p:vt_petition) "
                 f"RETURN p.rcpt_dt, count(p) AS cnt ORDER BY p.rcpt_dt")
        elif kind == 3:
            q = f"활성 진정서 군집과 군집별 사건 수"
            c = (f"MATCH (c:pt_cluster {{status: 'active'}})<-[:belongs_to_cluster]-(p:vt_petition)"
                 f"-[:filed_as]->(case:vt_case) "
                 f"RETURN c.cluster_id, count(DISTINCT case) AS case_cnt "
                 f"ORDER BY case_cnt DESC")
        elif kind == 4:
            q = f"진정서 5건 이상 군집의 진정 접수 패턴"
            c = (f"MATCH (c:pt_cluster)<-[:belongs_to_cluster]-(p:vt_petition) "
                 f"WHERE c.petition_cnt >= 5 "
                 f"RETURN c.cluster_id, min(p.rcpt_dt) AS first_dt, max(p.rcpt_dt) AS last_dt, "
                 f"count(p) AS member_cnt ORDER BY member_cnt DESC")
        else:
            q = f"진정서 군집별 피해액 합계와 평균 유사도"
            c = (f"MATCH (c:pt_cluster)<-[r:belongs_to_cluster]-(p:vt_petition) "
                 f"RETURN c.cluster_id, c.damage_amt_sum, avg(r.sim_score) AS avg_sim, count(p) AS cnt "
                 f"ORDER BY c.damage_amt_sum DESC LIMIT 50")
        samples.append((q, c))
    return samples


# ──────────────────────────────────────────────────────────────────
# 2-hop site_cluster 패턴 (~100개)
# ──────────────────────────────────────────────────────────────────
def gen_2hop_site_cluster(n=100):
    samples = []
    for _ in range(n):
        kind = random.randint(0, 5)
        cid = random.choice(SITE_CLUSTER_IDS)
        campaign = random.choice(CAMPAIGNS)

        if kind == 0:
            q = f"'{campaign}' 캠페인의 모든 사이트와 그에 대응되는 IP"
            c = (f"MATCH (c:site_cluster {{campaign_name: '{campaign}'}})<-[:belongs_to_campaign]-(s:vt_site)"
                 f"-[:resolves_to]->(ip:vt_ip) "
                 f"RETURN c.campaign_name, s.dmn_addr, ip.ip_addr, ip.country")
        elif kind == 1:
            q = f"캠페인 군집 '{cid}'에서 발생한 접속 이벤트 전체"
            c = (f"MATCH (c:site_cluster {{cluster_id: '{cid}'}})<-[:belongs_to_campaign]-(s:vt_site)"
                 f"<-[:accessed_to]-(a:vt_access) "
                 f"RETURN c.cluster_id, s.dmn_addr, a.access_id, a.access_dt "
                 f"ORDER BY a.access_dt DESC LIMIT 100")
        elif kind == 2:
            q = f"'{campaign}' 캠페인에서 다운로드된 파일 목록"
            c = (f"MATCH (c:site_cluster {{campaign_name: '{campaign}'}})<-[:belongs_to_campaign]-(s:vt_site)"
                 f"-[:contains_file]->(f:vt_file) "
                 f"RETURN c.campaign_name, s.dmn_addr, f.file_nm, f.is_malicious")
        elif kind == 3:
            q = f"피싱 캠페인별 호스팅 IP와 그 IP가 위치한 국가 분포"
            c = (f"MATCH (c:site_cluster)<-[:belongs_to_campaign]-(s:vt_site)<-[:hosts]-(ip:vt_ip) "
                 f"RETURN c.cluster_id, c.campaign_name, ip.country, count(DISTINCT ip) AS ip_cnt "
                 f"ORDER BY ip_cnt DESC")
        elif kind == 4:
            q = f"캠페인 군집 '{cid}'의 피해자 인물 목록"
            c = (f"MATCH (c:site_cluster {{cluster_id: '{cid}'}})<-[:belongs_to_campaign]-(s:vt_site)"
                 f"<-[:accessed_to]-(a:vt_access)<-[:victim_in]-(p:vt_psn) "
                 f"RETURN c.cluster_id, p.psn_id, p.korn_flnm, p.is_anonymous")
        else:
            q = f"동일 IP에 호스팅된 피싱 캠페인의 도메인 그룹"
            c = (f"MATCH (ip:vt_ip)-[:hosts]->(s:vt_site)-[:belongs_to_campaign]->(c:site_cluster) "
                 f"RETURN ip.ip_addr, c.campaign_name, collect(DISTINCT s.dmn_addr) AS domains "
                 f"ORDER BY size(domains) DESC")
        samples.append((q, c))
    return samples


# ──────────────────────────────────────────────────────────────────
# 3-hop 중계기/캠페인 체인 (~100개)
# ──────────────────────────────────────────────────────────────────
def gen_3hop_chains(n=100):
    samples = []
    for _ in range(n):
        kind = random.randint(0, 5)
        imei = rand_imei()
        cid = random.choice(SITE_CLUSTER_IDS)
        campaign = random.choice(CAMPAIGNS)
        telno = rand_telno()

        if kind == 0:
            q = f"불법중계기 IMEI '{imei}'에 연결된 전화번호의 통화 상대방"
            c = (f"MATCH (d:vt_dev {{imei: '{imei}', dev_type: 'relay_station'}})"
                 f"<-[:used_in_device]-(t1:vt_telno)-[:caller]->(call:vt_call)-[:callee]->(t2:vt_telno) "
                 f"RETURN d.imei, t1.telno, call.call_dt, t2.telno LIMIT 100")
        elif kind == 1:
            q = f"불법중계기에 연결된 전화번호의 명의자 전체"
            c = (f"MATCH (d:vt_dev {{dev_type: 'relay_station'}})<-[:used_in_device]-(t:vt_telno)"
                 f"-[:registered_to]->(p:vt_psn) "
                 f"RETURN d.device_id, d.imei, t.telno, p.korn_flnm, p.is_anonymous "
                 f"ORDER BY d.device_id")
        elif kind == 2:
            q = f"'{campaign}' 캠페인의 호스팅 IP가 속한 조직과 그 조직의 명의자"
            c = (f"MATCH (c:site_cluster {{campaign_name: '{campaign}'}})<-[:belongs_to_campaign]-(s:vt_site)"
                 f"<-[:hosts]-(ip:vt_ip), (ip)-[:belongs_to]->(o:vt_org) "
                 f"RETURN c.campaign_name, s.dmn_addr, ip.ip_addr, o.org_name")
        elif kind == 3:
            q = f"캠페인 군집 '{cid}'의 접속 이벤트에서 발신된 IP의 명의자"
            c = (f"MATCH (c:site_cluster {{cluster_id: '{cid}'}})<-[:belongs_to_campaign]-(s:vt_site)"
                 f"<-[:accessed_to]-(a:vt_access)-[:accessed_from]->(ip:vt_ip) "
                 f"RETURN c.cluster_id, s.dmn_addr, a.access_id, ip.ip_addr ORDER BY a.access_dt DESC")
        elif kind == 4:
            q = f"성명불상 피의자가 사용한 전화번호가 등록된 기기"
            c = (f"MATCH (p:vt_psn {{is_anonymous: true}})-[:owns_phone]->(t:vt_telno)"
                 f"-[:used_in_device]->(d:vt_dev) "
                 f"RETURN p.psn_id, t.telno, d.device_id, d.imei, d.dev_type")
        else:
            q = f"전화번호 '{telno}'을 거친 통화에서 동일 기기 사용 이력 추적"
            c = (f"MATCH (t1:vt_telno {{telno: '{telno}'}})-[:used_in_device]->(d:vt_dev)"
                 f"<-[:used_in_device]-(t2:vt_telno) "
                 f"WHERE t1 <> t2 "
                 f"RETURN d.device_id, d.imei, t1.telno AS focal, collect(t2.telno) AS co_phones")
        samples.append((q, c))
    return samples


# ──────────────────────────────────────────────────────────────────
# 4-hop+ 추적 체인 (~80개)
# ──────────────────────────────────────────────────────────────────
def gen_4hop_chains(n=80):
    samples = []
    for _ in range(n):
        kind = random.randint(0, 3)
        cid = random.choice(SITE_CLUSTER_IDS)
        pt_cid = random.choice(PT_CLUSTER_IDS)
        campaign = random.choice(CAMPAIGNS)

        if kind == 0:
            q = f"'{campaign}' 캠페인 → 사이트 → 호스팅 IP → 명의자(조직) → 그 조직의 계좌"
            c = (f"MATCH (c:site_cluster {{campaign_name: '{campaign}'}})<-[:belongs_to_campaign]-(s:vt_site)"
                 f"<-[:hosts]-(ip:vt_ip)-[:belongs_to]->(o:vt_org), (b:vt_bacnt)-[:belongs_to]->(o) "
                 f"RETURN c.campaign_name, s.dmn_addr, ip.ip_addr, o.org_name, b.account_no")
        elif kind == 1:
            q = f"진정서 군집 '{pt_cid}' → 사건 → 사용된 계좌 → 자금이체 흐름"
            c = (f"MATCH (c:pt_cluster {{cluster_id: '{pt_cid}'}})<-[:belongs_to_cluster]-(p:vt_petition)"
                 f"-[:filed_as]->(case:vt_case)-[:eg_used_account]->(b:vt_bacnt)"
                 f"-[:from_account]->(tr:vt_transfer)-[:to_account]->(b2:vt_bacnt) "
                 f"RETURN c.cluster_id, case.flnm, b.account_no, tr.amount, b2.account_no "
                 f"ORDER BY tr.amount DESC LIMIT 50")
        elif kind == 2:
            q = f"불법중계기 → 전화번호 → 통화 → 상대번호 → 그 상대번호 명의자"
            c = (f"MATCH (d:vt_dev {{dev_type: 'relay_station'}})<-[:used_in_device]-(t1:vt_telno)"
                 f"-[:caller]->(call:vt_call)-[:callee]->(t2:vt_telno)-[:registered_to]->(p:vt_psn) "
                 f"RETURN d.imei, t1.telno, call.call_dt, t2.telno, p.korn_flnm "
                 f"ORDER BY call.call_dt DESC LIMIT 100")
        else:
            q = f"캠페인 군집 '{cid}' → 사이트 → 파일 → 그 파일을 다운받은 인물 → 그 인물의 사건"
            c = (f"MATCH (c:site_cluster {{cluster_id: '{cid}'}})<-[:belongs_to_campaign]-(s:vt_site)"
                 f"-[:contains_file]->(f:vt_file)<-[:downloaded]-(p:vt_psn)-[:victim_in]->(case:vt_case) "
                 f"RETURN c.cluster_id, s.dmn_addr, f.file_nm, p.psn_id, case.flnm")
        samples.append((q, c))
    return samples


# ──────────────────────────────────────────────────────────────────
# shortestPath 패턴 (~80개)
# ──────────────────────────────────────────────────────────────────
def gen_shortest_path(n=80):
    samples = []
    for _ in range(n):
        kind = random.randint(0, 4)
        cid = random.choice(SITE_CLUSTER_IDS)
        pt_cid = random.choice(PT_CLUSTER_IDS)
        campaign = random.choice(CAMPAIGNS)
        name1 = random.choice(KOREAN_NAMES)

        if kind == 0:
            q = f"성명불상 피의자와 인물 '{name1}' 사이의 최단 경로"
            c = (f"MATCH path = shortest_path("
                 f"(anon:vt_psn {{is_anonymous: true}})-[*1..6]-(known:vt_psn {{korn_flnm: '{name1}'}})"
                 f") RETURN path LIMIT 5")
        elif kind == 1:
            q = f"진정서 군집 '{pt_cid}'과 인물 '{name1}' 간의 최단 경로"
            c = (f"MATCH path = shortest_path("
                 f"(c:pt_cluster {{cluster_id: '{pt_cid}'}})-[*1..6]-(p:vt_psn {{korn_flnm: '{name1}'}})"
                 f") RETURN path")
        elif kind == 2:
            q = f"피싱 캠페인 '{campaign}'과 성명불상 피의자 간 최단 연결"
            c = (f"MATCH path = shortest_path("
                 f"(c:site_cluster {{campaign_name: '{campaign}'}})-[*1..7]-(p:vt_psn {{is_anonymous: true}})"
                 f") RETURN path LIMIT 10")
        elif kind == 3:
            q = f"진정서 군집 '{pt_cid}'과 캠페인 군집 '{cid}' 간 최단 경로"
            c = (f"MATCH path = shortest_path("
                 f"(pc:pt_cluster {{cluster_id: '{pt_cid}'}})-[*1..8]-(sc:site_cluster {{cluster_id: '{cid}'}})"
                 f") RETURN path")
        else:
            q = f"불법중계기와 진정서 군집 '{pt_cid}' 간의 최단 연결"
            c = (f"MATCH path = shortest_path("
                 f"(d:vt_dev {{dev_type: 'relay_station'}})-[*1..6]-(c:pt_cluster {{cluster_id: '{pt_cid}'}})"
                 f") RETURN path LIMIT 5")
        samples.append((q, c))
    return samples


# ──────────────────────────────────────────────────────────────────
# var-hop 패턴 (~80개) — *1..N 가변 길이
# ──────────────────────────────────────────────────────────────────
def gen_var_hop(n=80):
    samples = []
    for _ in range(n):
        kind = random.randint(0, 4)
        cid = random.choice(SITE_CLUSTER_IDS)
        pt_cid = random.choice(PT_CLUSTER_IDS)
        campaign = random.choice(CAMPAIGNS)
        imei = rand_imei()

        if kind == 0:
            q = f"진정서 군집 '{pt_cid}' 멤버와 1~3홉 내에 연결된 인물"
            c = (f"MATCH (c:pt_cluster {{cluster_id: '{pt_cid}'}})<-[:belongs_to_cluster]-(p:vt_petition)"
                 f"-[*1..3]-(person:vt_psn) "
                 f"RETURN DISTINCT c.cluster_id, p.pettn_no, person.psn_id, person.korn_flnm LIMIT 100")
        elif kind == 1:
            q = f"'{campaign}' 캠페인 사이트와 2~4홉 내에 있는 모든 계좌"
            c = (f"MATCH (c:site_cluster {{campaign_name: '{campaign}'}})<-[:belongs_to_campaign]-(s:vt_site)"
                 f"-[*2..4]-(b:vt_bacnt) "
                 f"RETURN DISTINCT c.campaign_name, s.dmn_addr, b.account_no, b.bank_nm LIMIT 100")
        elif kind == 2:
            q = f"성명불상 피의자와 2~5홉 내에 있는 사건 목록"
            c = (f"MATCH (p:vt_psn {{is_anonymous: true}})-[*2..5]-(case:vt_case) "
                 f"RETURN DISTINCT p.psn_id, case.flnm, case.crime_type_cd LIMIT 100")
        elif kind == 3:
            q = f"불법중계기 IMEI '{imei}'에서 1~4홉 안의 모든 노드 종류와 개수"
            c = (f"MATCH (d:vt_dev {{imei: '{imei}', dev_type: 'relay_station'}})-[*1..4]-(x) "
                 f"RETURN labels(x) AS node_type, count(DISTINCT x) AS cnt ORDER BY cnt DESC")
        else:
            q = f"캠페인 군집 '{cid}'과 2~6홉 거리 내의 인물·조직 관계망"
            c = (f"MATCH (c:site_cluster {{cluster_id: '{cid}'}})-[*2..6]-(actor) "
                 f"WHERE actor:vt_psn OR actor:vt_org "
                 f"RETURN DISTINCT c.cluster_id, labels(actor) AS type, actor LIMIT 200")
        samples.append((q, c))
    return samples


# ──────────────────────────────────────────────────────────────────
# ShareGPT 변환 + 메인
# ──────────────────────────────────────────────────────────────────
def to_sharegpt(q, c):
    return {
        "conversations": [
            {"from": "system", "value": SYSTEM_PROMPT_V37},
            {"from": "human",  "value": q},
            {"from": "gpt",    "value": c},
        ]
    }


def main():
    pairs = []
    pairs.extend(gen_2hop_pt_cluster(100))
    pairs.extend(gen_2hop_site_cluster(100))
    pairs.extend(gen_3hop_chains(100))
    pairs.extend(gen_4hop_chains(80))
    pairs.extend(gen_shortest_path(80))
    pairs.extend(gen_var_hop(80))

    # 중복 제거
    seen = set()
    unique = []
    for q, c in pairs:
        key = (q.strip(), c.strip())
        if key in seen:
            continue
        seen.add(key)
        unique.append((q, c))

    random.shuffle(unique)
    samples = [to_sharegpt(q, c) for q, c in unique]

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)

    # 카테고리 분포 (간이)
    cat_2hop = sum(1 for q, c in unique if '2hop' in q or ('-[' in c and c.count('-[') == 2))
    print(f"✅ 멀티홉 시드 생성: {len(samples)}개")
    print(f"   출력: {OUT_PATH}")


if __name__ == "__main__":
    main()
