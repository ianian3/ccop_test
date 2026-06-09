"""
KICS 온톨로지 v3.5 기반 데모 그래프 데이터 생성 스크립트
시나리오: 보이스피싱 범죄 조직 수사 (3단계 대포통장 자금세탁 + 사칭이벤트)

그래프명: ccop_demo_v35
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "ccopdb"),
    "user": os.getenv("DB_USER", "ccop"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", "5432")
}

GRAPH_NAME = "ccop_demo_v35"

def execute_cypher(cur, cypher):
    """AgensGraph 네이티브 Cypher 실행"""
    cur.execute(cypher)

def safe_set_graph(cur, graph_name):
    cur.execute(f"SET graph_path = {graph_name}")

def create_graph_if_not_exists(conn):
    cur = conn.cursor()
    try:
        cur.execute(f"CREATE GRAPH {GRAPH_NAME}")
        conn.commit()
        print(f"[OK] 그래프 '{GRAPH_NAME}' 생성 완료")
    except Exception as e:
        if "already exists" in str(e) or "이미 존재" in str(e):
            conn.rollback()
            print(f"[INFO] 그래프 '{GRAPH_NAME}' 이미 존재 - 기존 데이터 삭제 후 재생성")
            cur.execute(f"DROP GRAPH {GRAPH_NAME} CASCADE")
            conn.commit()
            cur.execute(f"CREATE GRAPH {GRAPH_NAME}")
            conn.commit()
            print(f"[OK] 그래프 '{GRAPH_NAME}' 재생성 완료")
        else:
            conn.rollback()
            raise e
    cur.close()

def load_nodes(conn):
    cur = conn.cursor()
    safe_set_graph(cur, GRAPH_NAME)
    conn.commit()

    nodes = []

    # ─── 소스 ───────────────────────────────────────────────────────────
    nodes.append(("vt_src", "src_id", "SRC-001", {
        "src_name": "경찰청 KICS",
        "src_type": "investigative_system",
        "reliability_tier": "A"
    }))

    # ─── 사건 ───────────────────────────────────────────────────────────
    nodes.append(("vt_case", "flnm", "2024-서울-00123", {
        "incdnt_no": "INC-2024-00123",
        "incdnt_nm": "조직형 보이스피싱 수사건",
        "crime_type": "전기통신금융사기",
        "occrn_dt": "2024-03-15",
        "damage_amount": "87000000",
        "status": "수사중",
        "police_station": "서울지방경찰청 사이버수사대"
    }))

    # ─── 인물 (Person) ───────────────────────────────────────────────────
    # 피의자 1 - 총책
    nodes.append(("vt_psn", "psn_id", "PSN-001", {
        "korn_flnm": "김철수",
        "name": "김철수",
        "dob": "1985-07-22",
        "gender": "M",
        "nationality": "KR",
        "risk_level": "HIGH",
        "confidence": "0.95"
    }))
    # 피의자 2 - 인출책
    nodes.append(("vt_psn", "psn_id", "PSN-002", {
        "korn_flnm": "이영호",
        "name": "이영호",
        "dob": "1992-11-03",
        "gender": "M",
        "nationality": "KR",
        "risk_level": "HIGH",
        "confidence": "0.88"
    }))
    # 피의자 3 - 전화상담원
    nodes.append(("vt_psn", "psn_id", "PSN-003", {
        "korn_flnm": "박지영",
        "name": "박지영",
        "dob": "1998-04-15",
        "gender": "F",
        "nationality": "KR",
        "risk_level": "MEDIUM",
        "confidence": "0.75"
    }))
    # 피해자 1
    nodes.append(("vt_psn", "psn_id", "PSN-101", {
        "korn_flnm": "정미숙",
        "name": "정미숙",
        "dob": "1961-09-30",
        "gender": "F",
        "nationality": "KR",
        "risk_level": "LOW",
        "confidence": "1.0"
    }))
    # 피해자 2
    nodes.append(("vt_psn", "psn_id", "PSN-102", {
        "korn_flnm": "오병준",
        "name": "오병준",
        "dob": "1958-02-14",
        "gender": "M",
        "nationality": "KR",
        "risk_level": "LOW",
        "confidence": "1.0"
    }))

    # ─── 조직 ────────────────────────────────────────────────────────────
    nodes.append(("vt_org", "org_id", "ORG-001", {
        "org_name": "태양콜센터 (위장업체)",
        "org_category": "criminal_org",
        "addr": "서울시 강남구 역삼동 (위장사무소)",
        "activity_type": "voice_phishing",
        "member_count": "15"
    }))

    # ─── 계좌 (대포통장) ─────────────────────────────────────────────────
    nodes.append(("vt_bacnt", "account_no", "110-2345-6789", {
        "bank_cd": "088",
        "bank_nm": "신한은행",
        "dpstr_nm": "이영호",
        "account_type": "수시입출금",
        "is_burner": "true",
        "is_frozen": "true",
        "total_received": "87000000",
        "total_sent": "85000000",
        "transaction_cnt": "23"
    }))
    nodes.append(("vt_bacnt", "account_no", "352-0987-6543", {
        "bank_cd": "020",
        "bank_nm": "우리은행",
        "dpstr_nm": "김철수",
        "account_type": "수시입출금",
        "is_burner": "true",
        "is_frozen": "false",
        "total_received": "85000000",
        "total_sent": "84500000",
        "transaction_cnt": "12"
    }))
    # 피해자 계좌
    nodes.append(("vt_bacnt", "account_no", "219-3456-7890", {
        "bank_cd": "004",
        "bank_nm": "국민은행",
        "dpstr_nm": "정미숙",
        "account_type": "수시입출금",
        "is_burner": "false",
        "is_frozen": "false",
        "total_received": "0",
        "total_sent": "50000000",
        "transaction_cnt": "2"
    }))
    nodes.append(("vt_bacnt", "account_no", "301-4567-8901", {
        "bank_cd": "039",
        "bank_nm": "경남은행",
        "dpstr_nm": "오병준",
        "account_type": "수시입출금",
        "is_burner": "false",
        "is_frozen": "false",
        "total_received": "0",
        "total_sent": "37000000",
        "transaction_cnt": "3"
    }))

    # ─── 전화번호 (대포폰) ───────────────────────────────────────────────
    nodes.append(("vt_telno", "telno", "010-5678-1234", {
        "country_code": "+82",
        "telco_nm": "KT",
        "join_typ_cd": "선불",
        "is_registered": "false",
        "is_burner": "true",
        "spam_cnt": "847"
    }))
    nodes.append(("vt_telno", "telno", "010-9012-3456", {
        "country_code": "+82",
        "telco_nm": "SK텔레콤",
        "join_typ_cd": "선불",
        "is_registered": "false",
        "is_burner": "true",
        "spam_cnt": "312"
    }))
    nodes.append(("vt_telno", "telno", "02-1234-5678", {
        "country_code": "+82",
        "telco_nm": "KT",
        "join_typ_cd": "법인",
        "is_registered": "false",
        "is_burner": "true",
        "spam_cnt": "1243",
        "subs_holder": "가짜법원 대표번호"
    }))

    # ─── IP 주소 ─────────────────────────────────────────────────────────
    nodes.append(("vt_ip", "ip_addr", "103.45.67.89", {
        "version": "IPv4",
        "isp": "China Telecom",
        "country": "CN",
        "is_vpn": "true",
        "is_proxy": "false",
        "is_hosting": "true",
        "abuse_score": "92"
    }))
    nodes.append(("vt_ip", "ip_addr", "185.220.101.45", {
        "version": "IPv4",
        "isp": "Mullvad VPN",
        "country": "SE",
        "is_vpn": "true",
        "is_tor": "true",
        "abuse_score": "98"
    }))

    # ─── 사이트 (피싱사이트) ─────────────────────────────────────────────
    nodes.append(("vt_site", "url_addr", "https://fake-court-kr.com/warrant/2024", {
        "dmn_addr": "fake-court-kr.com",
        "site_type": "phishing",
        "is_malicious": "true",
        "risk_grd": "S",
        "sign_kwrd": "법원,영장,계좌압류",
        "detct_dt": "2024-03-18",
        "page_title": "대한민국 법원 - 계좌 동결 안내"
    }))
    nodes.append(("vt_site", "url_addr", "https://police-safe-kr.net/auth", {
        "dmn_addr": "police-safe-kr.net",
        "site_type": "phishing",
        "is_malicious": "true",
        "risk_grd": "S",
        "sign_kwrd": "경찰청,수사,개인정보입력",
        "detct_dt": "2024-03-20",
        "page_title": "경찰청 - 수사협조 안전계좌 이체"
    }))

    # ─── 디지털ID ────────────────────────────────────────────────────────
    nodes.append(("vt_id", "id_val", "taeyang_call_admin", {
        "platform": "telegram",
        "id_type": "메신저ID",
        "is_active": "true",
        "real_name": "김철수(추정)"
    }))

    # ─── ATM ────────────────────────────────────────────────────────────
    nodes.append(("vt_atm", "atm_id", "ATM-KANGNAM-0342", {
        "bank_nm": "신한은행",
        "bank_cd": "088",
        "address": "서울시 강남구 역삼동 123-45",
        "is_outdoor": "true"
    }))
    nodes.append(("vt_atm", "atm_id", "ATM-JONGNO-0117", {
        "bank_nm": "우리은행",
        "bank_cd": "020",
        "address": "서울시 종로구 세종대로 185",
        "is_outdoor": "false"
    }))

    # ─── 위치 ────────────────────────────────────────────────────────────
    nodes.append(("vt_loc", "loc_id", "LOC-001", {
        "loc_type": "address",
        "address": "서울시 강남구 역삼동 456-78 (콜센터 위장 사무소)",
        "sido_nm": "서울특별시",
        "sigungu_nm": "강남구",
        "place_name": "태양빌딩 3층"
    }))

    # ─── 사칭이벤트 ─────────────────────────────────────────────────────
    nodes.append(("vt_impersonation", "event_id", "IMP-001", {
        "method": "TELNO",
        "fake_name": "박대한 검사 (서울중앙지검)",
        "script_type": "보이스피싱-검사사칭",
        "start_dt": "2024-03-15",
        "end_dt": "2024-03-22"
    }))
    nodes.append(("vt_impersonation", "event_id", "IMP-002", {
        "method": "SITE",
        "fake_name": "대한민국 법원",
        "script_type": "보이스피싱-법원사칭",
        "start_dt": "2024-03-15",
        "end_dt": "2024-03-25"
    }))

    # ─── 이체 이벤트 ─────────────────────────────────────────────────────
    nodes.append(("vt_transfer", "event_id", "TRF-001", {
        "dlng_sn": "20240316-001",
        "dlng_amt": "50000000",
        "dlng_dt": "2024-03-16 14:23:11",
        "dlng_memo_cn": "안전계좌 이체",
        "is_suspicious": "true",
        "hop_level": "1"
    }))
    nodes.append(("vt_transfer", "event_id", "TRF-002", {
        "dlng_sn": "20240316-002",
        "dlng_amt": "37000000",
        "dlng_dt": "2024-03-16 16:45:30",
        "dlng_memo_cn": "계좌 보호 이체",
        "is_suspicious": "true",
        "hop_level": "1"
    }))
    nodes.append(("vt_transfer", "event_id", "TRF-003", {
        "dlng_sn": "20240317-001",
        "dlng_amt": "84500000",
        "dlng_dt": "2024-03-17 09:12:05",
        "dlng_memo_cn": "자금 이동",
        "is_suspicious": "true",
        "hop_level": "2"
    }))

    # ─── 통화 이벤트 ─────────────────────────────────────────────────────
    nodes.append(("vt_call", "event_id", "CALL-001", {
        "call_sn": "20240315-9012",
        "call_strt_dt": "2024-03-15 10:30:00",
        "call_dur_sec": "2340",
        "call_typ_cd": "발신",
        "dsptch_telno": "010-5678-1234",
        "rcptn_telno": "010-9876-5432"
    }))
    nodes.append(("vt_call", "event_id", "CALL-002", {
        "call_sn": "20240315-9013",
        "call_strt_dt": "2024-03-15 11:15:00",
        "call_dur_sec": "1820",
        "call_typ_cd": "발신",
        "dsptch_telno": "010-5678-1234",
        "rcptn_telno": "010-1234-5678"
    }))

    # 노드 적재
    total = 0
    for (label, key_prop, key_val, props) in nodes:
        all_props = {key_prop: key_val}
        all_props.update(props)
        # 속성 문자열 빌드
        props_parts = []
        for k, v in all_props.items():
            safe_v = str(v).replace("'", "\\'")
            props_parts.append(f"{k}: '{safe_v}'")
        props_str = ", ".join(props_parts)
        cypher = f"MERGE (n:{label} {{{key_prop}: '{key_val}'}}) ON CREATE SET n = {{{props_str}}} RETURN n"
        try:
            execute_cypher(cur, cypher)
            conn.commit()
            total += 1
        except Exception as e:
            conn.rollback()
            print(f"  [ERROR] {label} {key_val}: {e}")
            safe_set_graph(cur, GRAPH_NAME)
            conn.commit()

    cur.close()
    print(f"[OK] 노드 {total}개 적재 완료")
    return total


def load_edges(conn):
    cur = conn.cursor()
    safe_set_graph(cur, GRAPH_NAME)
    conn.commit()

    edges = []

    # ── [CASE] 역할 엣지 ─────────────────────────────────────────────────
    edges.append(("suspect_in",  "vt_psn",    "psn_id",    "PSN-001",
                                 "vt_case",   "flnm",      "2024-서울-00123",
                                 {"confidence": "0.95", "verified": "true"}))
    edges.append(("suspect_in",  "vt_psn",    "psn_id",    "PSN-002",
                                 "vt_case",   "flnm",      "2024-서울-00123",
                                 {"confidence": "0.88", "verified": "true"}))
    edges.append(("suspect_in",  "vt_psn",    "psn_id",    "PSN-003",
                                 "vt_case",   "flnm",      "2024-서울-00123",
                                 {"confidence": "0.75", "verified": "false"}))
    edges.append(("victim_in",   "vt_psn",    "psn_id",    "PSN-101",
                                 "vt_case",   "flnm",      "2024-서울-00123",
                                 {"confidence": "1.0", "verified": "true"}))
    edges.append(("victim_in",   "vt_psn",    "psn_id",    "PSN-102",
                                 "vt_case",   "flnm",      "2024-서울-00123",
                                 {"confidence": "1.0", "verified": "true"}))

    # ── [ORG] 조직 소속 ──────────────────────────────────────────────────
    edges.append(("belongs_to",  "vt_psn",    "psn_id",    "PSN-001",
                                 "vt_org",    "org_id",    "ORG-001",
                                 {"confidence": "0.9"}))
    edges.append(("belongs_to",  "vt_psn",    "psn_id",    "PSN-002",
                                 "vt_org",    "org_id",    "ORG-001",
                                 {"confidence": "0.85"}))
    edges.append(("belongs_to",  "vt_psn",    "psn_id",    "PSN-003",
                                 "vt_org",    "org_id",    "ORG-001",
                                 {"confidence": "0.7"}))

    # ── [ACCOUNT] 계좌 소유 ──────────────────────────────────────────────
    edges.append(("has_account", "vt_psn",    "psn_id",    "PSN-002",
                                 "vt_bacnt",  "account_no","110-2345-6789",
                                 {"confidence": "0.92", "verified": "true"}))
    edges.append(("has_account", "vt_psn",    "psn_id",    "PSN-001",
                                 "vt_bacnt",  "account_no","352-0987-6543",
                                 {"confidence": "0.88", "verified": "true"}))
    edges.append(("has_account", "vt_psn",    "psn_id",    "PSN-101",
                                 "vt_bacnt",  "account_no","219-3456-7890",
                                 {"confidence": "1.0", "verified": "true"}))
    edges.append(("has_account", "vt_psn",    "psn_id",    "PSN-102",
                                 "vt_bacnt",  "account_no","301-4567-8901",
                                 {"confidence": "1.0", "verified": "true"}))

    # ── [PHONE] 전화번호 소유 ────────────────────────────────────────────
    edges.append(("owns_phone",  "vt_psn",    "psn_id",    "PSN-003",
                                 "vt_telno",  "telno",     "010-5678-1234",
                                 {"confidence": "0.8"}))
    edges.append(("owns_phone",  "vt_psn",    "psn_id",    "PSN-001",
                                 "vt_telno",  "telno",     "010-9012-3456",
                                 {"confidence": "0.85"}))
    edges.append(("owns_phone",  "vt_org",    "org_id",    "ORG-001",
                                 "vt_telno",  "telno",     "02-1234-5678",
                                 {"confidence": "0.95"}))

    # ── [IP] IP 사용 ─────────────────────────────────────────────────────
    edges.append(("used_ip",     "vt_org",    "org_id",    "ORG-001",
                                 "vt_ip",     "ip_addr",   "103.45.67.89",
                                 {"confidence": "0.9"}))
    edges.append(("used_ip",     "vt_org",    "org_id",    "ORG-001",
                                 "vt_ip",     "ip_addr",   "185.220.101.45",
                                 {"confidence": "0.88"}))

    # ── [SITE] 사이트 운영 ───────────────────────────────────────────────
    edges.append(("operates",    "vt_org",    "org_id",    "ORG-001",
                                 "vt_site",   "url_addr",  "https://fake-court-kr.com/warrant/2024",
                                 {"confidence": "0.93"}))
    edges.append(("operates",    "vt_org",    "org_id",    "ORG-001",
                                 "vt_site",   "url_addr",  "https://police-safe-kr.net/auth",
                                 {"confidence": "0.91"}))

    # ── [TRANSFER] 이체 관계 ────────────────────────────────────────────
    # 피해자 → 대포통장으로 송금
    edges.append(("sent_from",   "vt_transfer","event_id", "TRF-001",
                                 "vt_bacnt",  "account_no","219-3456-7890",
                                 {}))
    edges.append(("sent_to",     "vt_transfer","event_id", "TRF-001",
                                 "vt_bacnt",  "account_no","110-2345-6789",
                                 {}))
    edges.append(("sent_from",   "vt_transfer","event_id", "TRF-002",
                                 "vt_bacnt",  "account_no","301-4567-8901",
                                 {}))
    edges.append(("sent_to",     "vt_transfer","event_id", "TRF-002",
                                 "vt_bacnt",  "account_no","110-2345-6789",
                                 {}))
    # 대포통장 → 최종 수령 계좌
    edges.append(("sent_from",   "vt_transfer","event_id", "TRF-003",
                                 "vt_bacnt",  "account_no","110-2345-6789",
                                 {}))
    edges.append(("sent_to",     "vt_transfer","event_id", "TRF-003",
                                 "vt_bacnt",  "account_no","352-0987-6543",
                                 {}))

    # ── [CALL] 통화 관계 ────────────────────────────────────────────────
    edges.append(("made_call",   "vt_psn",    "psn_id",    "PSN-003",
                                 "vt_call",   "event_id",  "CALL-001",
                                 {}))
    edges.append(("made_call",   "vt_psn",    "psn_id",    "PSN-003",
                                 "vt_call",   "event_id",  "CALL-002",
                                 {}))

    # ── [IMPERSONATION] 사칭 관계 ───────────────────────────────────────
    edges.append(("performed",   "vt_psn",    "psn_id",    "PSN-003",
                                 "vt_impersonation","event_id","IMP-001",
                                 {}))
    edges.append(("performed",   "vt_org",    "org_id",    "ORG-001",
                                 "vt_impersonation","event_id","IMP-002",
                                 {}))

    # ── [LOCATION] 위치 관계 ────────────────────────────────────────────
    edges.append(("located_at",  "vt_org",    "org_id",    "ORG-001",
                                 "vt_loc",    "loc_id",    "LOC-001",
                                 {"confidence": "0.85"}))
    edges.append(("located_at",  "vt_atm",    "atm_id",    "ATM-KANGNAM-0342",
                                 "vt_loc",    "loc_id",    "LOC-001",
                                 {}))

    # 엣지 적재
    total = 0
    for edge_data in edges:
        (rel_type,
         src_label, src_key, src_val,
         tgt_label, tgt_key, tgt_val,
         props) = edge_data

        if props:
            props_parts = []
            for k, v in props.items():
                safe_v = str(v).replace("'", "\\'")
                props_parts.append(f"{k}: '{safe_v}'")
            props_str = "{" + ", ".join(props_parts) + "}"
        else:
            props_str = "{}"

        cypher = (
            f"MATCH (s:{src_label} {{{src_key}: '{src_val}'}}), "
            f"(t:{tgt_label} {{{tgt_key}: '{tgt_val}'}}) "
            f"MERGE (s)-[r:{rel_type} {props_str}]->(t) "
            f"RETURN r"
        )
        try:
            execute_cypher(cur, cypher)
            conn.commit()
            total += 1
        except Exception as e:
            conn.rollback()
            print(f"  [ERROR] ({src_label}:{src_val})-[{rel_type}]->({tgt_label}:{tgt_val}): {e}")
            safe_set_graph(cur, GRAPH_NAME)
            conn.commit()

    cur.close()
    print(f"[OK] 엣지 {total}개 적재 완료")
    return total


def verify_graph(conn):
    cur = conn.cursor()
    safe_set_graph(cur, GRAPH_NAME)
    conn.commit()

    print("\n=== 그래프 검증 ===")

    # 노드 수 확인
    labels = ["vt_case", "vt_psn", "vt_org", "vt_bacnt", "vt_telno",
              "vt_ip", "vt_site", "vt_impersonation", "vt_transfer",
              "vt_call", "vt_atm", "vt_loc"]
    for label in labels:
        try:
            cur.execute(f"MATCH (n:{label}) RETURN count(n)")
            row = cur.fetchone()
            cnt = row[0] if row else 0
            print(f"  {label}: {cnt}개")
        except Exception as e:
            conn.rollback()
            print(f"  {label}: ERROR - {e}")
            safe_set_graph(cur, GRAPH_NAME)
            conn.commit()

    # 엣지 수 확인
    print()
    edge_types = ["suspect_in", "victim_in", "belongs_to", "has_account",
                  "owns_phone", "used_ip", "operates", "sent_from", "sent_to",
                  "made_call", "performed", "located_at"]
    for et in edge_types:
        try:
            cur.execute(f"MATCH ()-[r:{et}]->() RETURN count(r)")
            row = cur.fetchone()
            cnt = row[0] if row else 0
            print(f"  [{et}]: {cnt}개")
        except Exception as e:
            conn.rollback()
            safe_set_graph(cur, GRAPH_NAME)
            conn.commit()

    cur.close()


if __name__ == "__main__":
    print(f"=== CCOP Demo 그래프 생성: {GRAPH_NAME} ===")
    print(f"시나리오: 조직형 보이스피싱 수사 (피해자 2명, 피의자 3명, 대포통장 2개)")
    print()

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        create_graph_if_not_exists(conn)
        load_nodes(conn)
        load_edges(conn)
        verify_graph(conn)
        print(f"\n[완료] 그래프 '{GRAPH_NAME}' 생성 완료")
        print(f"  → 메인 화면에서 그래프를 '{GRAPH_NAME}'으로 전환하여 시각화하세요.")
    finally:
        conn.close()
