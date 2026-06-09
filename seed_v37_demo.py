"""
seed_v37_demo.py — v3.7 신규 온톨로지 데모 시드 데이터 주입

생성/연결:
- pt_cluster 3개 + vt_petition 9개 + belongs_to_cluster 엣지
- site_cluster 3개 + vt_site 9개 + belongs_to_campaign 엣지
- vt_dev 5개 (relay_station 2 + smartphone 3) + used_in_device 엣지 (기존 vt_telno 사용)
- 기존 vt_psn 일부에 is_anonymous=true 부여

실행: python seed_v37_demo.py [--graph tccop_graph_v6]
"""
import argparse
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# 시드 데이터
# ──────────────────────────────────────────────────────────────────────────────

PT_CLUSTERS = [
    {"cluster_id": "ptc-2026-001", "cluster_method": "SimHash", "crime_type_cd": "보이스피싱",
     "damage_amt_sum": 150000000, "petition_cnt": 3, "status": "active",
     "first_rcpt_dt": "2026-01-10", "last_rcpt_dt": "2026-02-20"},
    {"cluster_id": "ptc-2026-002", "cluster_method": "SimHash", "crime_type_cd": "스미싱",
     "damage_amt_sum": 80000000, "petition_cnt": 3, "status": "active",
     "first_rcpt_dt": "2026-02-01", "last_rcpt_dt": "2026-03-15"},
    {"cluster_id": "ptc-2026-013", "cluster_method": "MinHash", "crime_type_cd": "메신저피싱",
     "damage_amt_sum": 230000000, "petition_cnt": 3, "status": "active",
     "first_rcpt_dt": "2026-03-01", "last_rcpt_dt": "2026-04-10"},
]

VT_PETITIONS = [
    # pettn_no, crime_type_cd, damage_amt, rcpt_dt, cluster_id, sim_score
    ("P2026-0101", "보이스피싱",  50000000, "2026-01-10", "ptc-2026-001", 0.92),
    ("P2026-0102", "보이스피싱",  45000000, "2026-01-25", "ptc-2026-001", 0.89),
    ("P2026-0103", "보이스피싱",  55000000, "2026-02-20", "ptc-2026-001", 0.94),
    ("P2026-0201", "스미싱",      25000000, "2026-02-01", "ptc-2026-002", 0.88),
    ("P2026-0202", "스미싱",      30000000, "2026-02-15", "ptc-2026-002", 0.91),
    ("P2026-0203", "스미싱",      25000000, "2026-03-15", "ptc-2026-002", 0.87),
    ("P2026-1301", "메신저피싱",  80000000, "2026-03-01", "ptc-2026-013", 0.96),
    ("P2026-1302", "메신저피싱",  70000000, "2026-03-20", "ptc-2026-013", 0.93),
    ("P2026-1303", "메신저피싱",  80000000, "2026-04-10", "ptc-2026-013", 0.95),
]

SITE_CLUSTERS = [
    {"cluster_id": "sc-2026-001", "html_fingerprint": "a1b2c3d4e5f6",
     "campaign_name": "가짜 은행 캠페인 A", "site_cnt": 3, "ip_cnt": 2,
     "first_seen": "2026-01-15", "last_seen": "2026-03-10"},
    {"cluster_id": "sc-2026-002", "html_fingerprint": "f7e8d9c0b1a2",
     "campaign_name": "가짜 쇼핑몰 캠페인 B", "site_cnt": 3, "ip_cnt": 3,
     "first_seen": "2026-02-10", "last_seen": "2026-04-05"},
    {"cluster_id": "sc-2026-007", "html_fingerprint": "9a8b7c6d5e4f",
     "campaign_name": "메신저피싱 랜딩 캠페인 G", "site_cnt": 3, "ip_cnt": 2,
     "first_seen": "2026-03-05", "last_seen": "2026-04-15"},
]

VT_SITES = [
    # url_addr, dmn_addr, is_malicious, cluster_id, sim_score
    ("https://kookmin-secure.example", "kookmin-secure.example", True, "sc-2026-001", 0.95),
    ("https://kb-bank-login.example",  "kb-bank-login.example",  True, "sc-2026-001", 0.93),
    ("https://kookmin-cert.example",   "kookmin-cert.example",   True, "sc-2026-001", 0.91),
    ("https://shop-coupang-sale.example",   "shop-coupang-sale.example",   True, "sc-2026-002", 0.89),
    ("https://gmarket-event-2026.example",  "gmarket-event-2026.example",  True, "sc-2026-002", 0.92),
    ("https://11st-flash-sale.example",     "11st-flash-sale.example",     True, "sc-2026-002", 0.88),
    ("https://kakao-bank-check.example",    "kakao-bank-check.example",    True, "sc-2026-007", 0.97),
    ("https://kakaotalk-verify.example",    "kakaotalk-verify.example",    True, "sc-2026-007", 0.94),
    ("https://kakao-account-help.example",  "kakao-account-help.example",  True, "sc-2026-007", 0.96),
]

# vt_dev: dev_type=relay_station 2개 + 일반 3개
VT_DEVS = [
    {"device_id": "DEV-RELAY-001", "dev_type": "relay_station", "imei": "352000123456789", "model": "SimBox-32"},
    {"device_id": "DEV-RELAY-002", "dev_type": "relay_station", "imei": "352000987654321", "model": "SimBox-64"},
    {"device_id": "DEV-PHONE-001", "dev_type": "smartphone",    "imei": "354000111222333", "model": "Galaxy S23"},
    {"device_id": "DEV-PHONE-002", "dev_type": "smartphone",    "imei": "354000444555666", "model": "iPhone 15"},
    {"device_id": "DEV-PC-001",    "dev_type": "pc",            "imei": "",                "model": "ThinkPad X1"},
]

# vt_telno → vt_dev 매핑 (used_in_device)
# 기존 그래프의 telno 'XXXXXXXXXX' 4개가 동일 relay 1대에 묶이는 시나리오
TELNO_DEV_MAPPINGS = [
    # (telno_pattern_or_seed, device_id)
    ("1099990001", "DEV-RELAY-001"),
    ("1099990002", "DEV-RELAY-001"),
    ("1099990003", "DEV-RELAY-001"),
    ("1099990004", "DEV-RELAY-001"),  # 4대 공유 → 중계기 탐지 룰
    ("1099990005", "DEV-RELAY-002"),
    ("1099990006", "DEV-RELAY-002"),
    ("1099990007", "DEV-RELAY-002"),
    ("1099990008", "DEV-PHONE-001"),
    ("1099990009", "DEV-PHONE-002"),
]

# is_anonymous=true 부여할 psn 개수 (기존 vt_psn 중 일부)
ANONYMIZE_FIRST_N = 3


# ──────────────────────────────────────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────────────────────────────────────

def run_cypher(conn, graph: str, cypher: str):
    """AgensGraph Native Cypher 실행. SET graph_path는 호출 전 1회 수행 필요."""
    with conn.cursor() as cur:
        cur.execute(cypher)
    return None


def kv_to_cypher_props(d: dict) -> str:
    """{'k': 'v', 'n': 1} → "k: 'v', n: 1" """
    parts = []
    for k, v in d.items():
        if isinstance(v, bool):
            parts.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            parts.append(f"{k}: {v}")
        else:
            sv = str(v).replace("'", "\\'")
            parts.append(f"{k}: '{sv}'")
    return ", ".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# 시드 작업
# ──────────────────────────────────────────────────────────────────────────────

def seed_pt_clusters_and_petitions(conn, graph: str):
    print("[1/5] pt_cluster + vt_petition + belongs_to_cluster 시드...")
    for c in PT_CLUSTERS:
        run_cypher(conn, graph,
                   f"MERGE (c:pt_cluster {{cluster_id: '{c['cluster_id']}'}}) "
                   f"SET c += {{{kv_to_cypher_props({k:v for k,v in c.items() if k!='cluster_id'})}}}")
    for pettn_no, crime, dmg, dt, cid, sim in VT_PETITIONS:
        run_cypher(conn, graph,
                   f"MERGE (p:vt_petition {{pettn_no: '{pettn_no}'}}) "
                   f"SET p.crime_type_cd = '{crime}', p.damage_amt = '{dmg}', p.rcpt_dt = '{dt}'")
        run_cypher(conn, graph,
                   f"MATCH (p:vt_petition {{pettn_no: '{pettn_no}'}}), "
                   f"(c:pt_cluster {{cluster_id: '{cid}'}}) "
                   f"MERGE (p)-[r:belongs_to_cluster]->(c) "
                   f"SET r.sim_score = {sim}, r.rec_created = '2026-05-20'")
    print(f"  -> pt_cluster {len(PT_CLUSTERS)}, vt_petition {len(VT_PETITIONS)}, belongs_to_cluster {len(VT_PETITIONS)}")


def seed_site_clusters_and_sites(conn, graph: str):
    print("[2/5] site_cluster + vt_site + belongs_to_campaign 시드...")
    for c in SITE_CLUSTERS:
        run_cypher(conn, graph,
                   f"MERGE (c:site_cluster {{cluster_id: '{c['cluster_id']}'}}) "
                   f"SET c += {{{kv_to_cypher_props({k:v for k,v in c.items() if k!='cluster_id'})}}}")
    for url, dmn, mal, cid, sim in VT_SITES:
        run_cypher(conn, graph,
                   f"MERGE (s:vt_site {{url_addr: '{url}'}}) "
                   f"SET s.dmn_addr = '{dmn}', s.is_malicious = {str(mal).lower()}")
        run_cypher(conn, graph,
                   f"MATCH (s:vt_site {{url_addr: '{url}'}}), "
                   f"(c:site_cluster {{cluster_id: '{cid}'}}) "
                   f"MERGE (s)-[r:belongs_to_campaign]->(c) "
                   f"SET r.sim_score = {sim}, r.detected_at = '2026-05-20', r.source_id = 'seed_v37'")
    print(f"  -> site_cluster {len(SITE_CLUSTERS)}, vt_site {len(VT_SITES)}, belongs_to_campaign {len(VT_SITES)}")


def seed_devices(conn, graph: str):
    print("[3/5] vt_dev 시드...")
    for d in VT_DEVS:
        run_cypher(conn, graph,
                   f"MERGE (dev:vt_dev {{device_id: '{d['device_id']}'}}) "
                   f"SET dev += {{{kv_to_cypher_props({k:v for k,v in d.items() if k!='device_id'})}}}")
    print(f"  -> vt_dev {len(VT_DEVS)} (relay_station 2 + smartphone 2 + pc 1)")


def seed_telno_and_used_in_device(conn, graph: str):
    print("[4/5] vt_telno (필요시 생성) + used_in_device 엣지 시드...")
    for telno, device_id in TELNO_DEV_MAPPINGS:
        run_cypher(conn, graph,
                   f"MERGE (t:vt_telno {{telno: '{telno}'}})")
        run_cypher(conn, graph,
                   f"MATCH (t:vt_telno {{telno: '{telno}'}}), "
                   f"(d:vt_dev {{device_id: '{device_id}'}}) "
                   f"MERGE (t)-[r:used_in_device]->(d) "
                   f"SET r.first_seen = '2026-01-01', r.last_seen = '2026-05-15', r.source_id = 'seed_v37'")
    print(f"  -> used_in_device {len(TELNO_DEV_MAPPINGS)} (DEV-RELAY-001은 4대 공유)")


def seed_anonymous_psn(conn, graph: str, n: int):
    print(f"[5/5] 기존 vt_psn 중 {n}개에 is_anonymous=true 부여...")
    with conn.cursor() as cur:
        cur.execute(f"MATCH (p:vt_psn) WITH p LIMIT {n} SET p.is_anonymous = true RETURN p.psn_id")
        rows = cur.fetchall()
        for r in rows:
            print(f"  -> anonymized: {r[0]}")
    return len(rows)


# ──────────────────────────────────────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", default=os.getenv("DEFAULT_GRAPH_PATH", "tccop_graph_v6"))
    args = parser.parse_args()

    print(f"v3.7 데모 시드 시작: graph={args.graph}")
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    conn.autocommit = False
    try:
        if not args.graph.replace("_", "").isalnum():
            raise ValueError(f"유효하지 않은 graph_path: {args.graph}")
        with conn.cursor() as cur:
            cur.execute(f"SET graph_path = {args.graph};")

        seed_pt_clusters_and_petitions(conn, args.graph)
        seed_site_clusters_and_sites(conn, args.graph)
        seed_devices(conn, args.graph)
        seed_telno_and_used_in_device(conn, args.graph)
        seed_anonymous_psn(conn, args.graph, ANONYMIZE_FIRST_N)

        conn.commit()
        print("\n✅ v3.7 시드 완료")
    except Exception as e:
        conn.rollback()
        print(f"\n❌ 시드 실패: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
