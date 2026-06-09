"""
CCOP v3.3 온톨로지 데모 데이터셋 생성 스크립트
==================================================
시나리오: 사이버 보이스피싱 + 가상자산 세탁 복합 사건 (DEMO-2026-001)

v3.3 온톨로지 23종 노드 전부 커버:
  L1 Source   : vt_src (1)
  L2 Case     : vt_case (1), vt_petition (2)
  L3 Person   : vt_psn (4), vt_org (3)
  L4 Object   : vt_bacnt (4), vt_telno (3), vt_ip (2), vt_site (1),
                vt_file (1), vt_id (2), vt_email (2), vt_crypto (1),
                vt_dev (1), vt_atm (2), vt_vhcl (1)
  L5 Location : vt_loc (3)
  L6 Event    : vt_transfer (5), vt_call (4), vt_access (2), vt_msg (3),
                vt_movement (2), vt_impersonation (2)   ← V3.3 신설
총 노드: 54개  |  총 엣지: 60+개
"""

import psycopg2

DB = dict(host='49.50.128.28', port=5333, dbname='tccopdb', user='ccop', password='Ccop@2025')
GRAPH = 'ccop_demo_v33'

# ──────────────────────────────────────────────────
# 헬퍼
# ──────────────────────────────────────────────────
def run(cur, cypher, label=""):
    try:
        cur.execute(cypher)
    except Exception as e:
        print(f"  ⚠️  [{label}] {e}")

def q(s):
    """문자열 SQL 이스케이프"""
    return str(s).replace("'", "''")


def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()

    # ── 0. 기존 그래프 삭제 후 재생성 ──────────────
    print(f"🗑️  기존 그래프 '{GRAPH}' 삭제 중...")
    try:
        cur.execute(f"DROP GRAPH {GRAPH} CASCADE")
    except Exception:
        pass
    cur.execute(f"CREATE GRAPH {GRAPH}")
    cur.execute(f"SET graph_path = {GRAPH}")
    print(f"✅ 그래프 '{GRAPH}' 생성 완료\n")

    # ── 1. Vertex / Edge 레이블 등록 ───────────────
    print("📋 레이블 등록 중...")
    vlabels = [
        'vt_src', 'vt_case', 'vt_petition',
        'vt_psn', 'vt_org',
        'vt_bacnt', 'vt_telno', 'vt_ip', 'vt_site', 'vt_file',
        'vt_id', 'vt_email', 'vt_crypto', 'vt_dev', 'vt_atm', 'vt_vhcl',
        'vt_loc',
        'vt_transfer', 'vt_call', 'vt_access', 'vt_msg', 'vt_movement',
        'vt_impersonation',
    ]
    elabels = [
        'sourced_from', 'filed_as', 'clusters_with',
        'suspect_in', 'victim_in', 'witness_in',
        'member_of', 'works_at',
        'has_account', 'owns_phone', 'uses_id', 'uses_email',
        'owns_wallet', 'uses_device', 'owns_vehicle', 'belongs_to',
        'from_account', 'to_account',
        'caller', 'callee',
        'sent_msg', 'received_msg',
        'used_ip', 'accessed_from', 'resolves_to', 'contains_file', 'linked_to',
        'recorded_in', 'occurred_at',
        'located_at', 'detected_at',
        'used_for', 'targets',          # V3.3 사칭 패턴
    ]
    for v in vlabels:
        run(cur, f"CREATE VLABEL IF NOT EXISTS {v}", v)
    for e in elabels:
        run(cur, f"CREATE ELABEL IF NOT EXISTS {e}", e)
    print(f"  ✅ 노드 레이블 {len(vlabels)}종, 엣지 레이블 {len(elabels)}종\n")

    # ══════════════════════════════════════════════
    # 2. 노드 삽입
    # ══════════════════════════════════════════════
    print("📌 노드 삽입 중...\n")

    # ── L1 · Source ────────────────────────────────
    print("  [L1 Source]")
    run(cur, """
        CREATE (:vt_src {
            src_id: 'SRC-KICS-001',
            src_name: 'KICS 사이버범죄신고시스템',
            src_type: 'OFFICIAL',
            tier: 1,
            reliability: 0.95,
            rec_created: '2026-03-01'
        })
    """, "vt_src")

    # ── L2 · Case ──────────────────────────────────
    print("  [L2 Case]")
    run(cur, """
        CREATE (:vt_case {
            flnm: 'DEMO-2026-001',
            crime_name: '사이버 보이스피싱 + 가상자산 세탁 복합 사건',
            crime_type: 'VOICE_PHISHING',
            crime_method: '기관사칭형',
            status: '수사중',
            reg_date: '2026-03-05',
            close_date: '',
            damage_amt: '85000000',
            victim_cnt: 3
        })
    """, "vt_case")

    run(cur, """
        CREATE (:vt_petition {
            pettn_id: 'PTN-2026-001',
            petitioner: '김피해',
            content: '국민은행 직원이라며 계좌이체를 요구받음',
            reg_date: '2026-03-02',
            status: '접수',
            source_id: 'SRC-KICS-001'
        })
    """, "vt_petition-1")

    run(cur, """
        CREATE (:vt_petition {
            pettn_id: 'PTN-2026-002',
            petitioner: '이피해',
            content: '검찰청 직원을 사칭한 전화 후 가상화폐 송금 요구받음',
            reg_date: '2026-03-03',
            status: '접수',
            source_id: 'SRC-KICS-001'
        })
    """, "vt_petition-2")

    # ── L3 · Person ────────────────────────────────
    print("  [L3 Person]")
    # 피의자
    run(cur, """
        CREATE (:vt_psn {
            psn_id: 'PSN-A001',
            name: '김하나',
            type: '피의자',
            birth_dt: '1990-05-15',
            gender: 'F',
            nationality: 'KOR',
            address: '서울 강남구 역삼동'
        })
    """, "vt_psn-김하나")

    run(cur, """
        CREATE (:vt_psn {
            psn_id: 'PSN-A002',
            name: '이두리',
            type: '피의자',
            birth_dt: '1988-11-23',
            gender: 'M',
            nationality: 'KOR',
            address: '인천 부평구 부평동'
        })
    """, "vt_psn-이두리")

    # 피해자
    run(cur, """
        CREATE (:vt_psn {
            psn_id: 'PSN-V001',
            name: '김피해',
            type: '피해자',
            birth_dt: '1965-03-20',
            gender: 'F',
            nationality: 'KOR',
            damage_amt: '45000000'
        })
    """, "vt_psn-김피해")

    run(cur, """
        CREATE (:vt_psn {
            psn_id: 'PSN-V002',
            name: '이피해',
            type: '피해자',
            birth_dt: '1972-07-08',
            gender: 'M',
            nationality: 'KOR',
            damage_amt: '40000000'
        })
    """, "vt_psn-이피해")

    # 조직
    run(cur, """
        CREATE (:vt_org {
            org_id: 'ORG-001',
            org_name: '국민은행',
            org_type: 'BANK',
            biz_no: '123-45-67890',
            address: '서울 중구 을지로'
        })
    """, "vt_org-국민은행")

    run(cur, """
        CREATE (:vt_org {
            org_id: 'ORG-002',
            org_name: '대검찰청',
            org_type: 'GOV',
            biz_no: '000-00-00001',
            address: '서울 서초구 반포대로'
        })
    """, "vt_org-대검찰청")

    run(cur, """
        CREATE (:vt_org {
            org_id: 'ORG-003',
            org_name: '서울경찰청 사이버수사대',
            org_type: 'POLICE',
            address: '서울 종로구 사직로'
        })
    """, "vt_org-사이버수사대")

    # ── L4 · Object ────────────────────────────────
    print("  [L4 Object]")

    # vt_bacnt
    run(cur, """CREATE (:vt_bacnt {acnt_id:'ACNT-001', actno:'110-9999-111111', bank_cd:'004', bank_name:'국민은행', holder:'김하나', acnt_type:'대포통장', open_dt:'2026-01-10'})""", "bacnt-1")
    run(cur, """CREATE (:vt_bacnt {acnt_id:'ACNT-002', actno:'088-1234-567890', bank_cd:'020', bank_name:'우리은행', holder:'차명인', acnt_type:'대포통장', open_dt:'2026-02-01'})""", "bacnt-2")
    run(cur, """CREATE (:vt_bacnt {acnt_id:'ACNT-V01', actno:'110-1111-111111', bank_cd:'004', bank_name:'국민은행', holder:'김피해', acnt_type:'일반', open_dt:'2015-06-01'})""", "bacnt-v1")
    run(cur, """CREATE (:vt_bacnt {acnt_id:'ACNT-V02', actno:'301-2222-222222', bank_cd:'090', bank_name:'카카오뱅크', holder:'이피해', acnt_type:'일반', open_dt:'2020-11-15'})""", "bacnt-v2")

    # vt_telno
    run(cur, """CREATE (:vt_telno {tel_id:'TEL-001', telno:'010-7777-0001', carrier:'SKT', tel_type:'사칭번호', reg_dt:'2026-02-15', fake_target:'국민은행'})""", "telno-1")
    run(cur, """CREATE (:vt_telno {tel_id:'TEL-002', telno:'02-530-4800', carrier:'KT', tel_type:'사칭번호', reg_dt:'2026-02-20', fake_target:'대검찰청'})""", "telno-2")
    run(cur, """CREATE (:vt_telno {tel_id:'TEL-A01', telno:'010-1234-5678', carrier:'LGU+', tel_type:'개인', reg_dt:'2020-03-01'})""", "telno-a1")

    # vt_ip
    run(cur, """CREATE (:vt_ip {ip_id:'IP-001', ip_addr:'182.191.45.23', isp:'SKB', country:'KOR', city:'서울', is_vpn:false, first_seen:'2026-02-10'})""", "ip-1")
    run(cur, """CREATE (:vt_ip {ip_id:'IP-002', ip_addr:'104.28.55.99', isp:'Cloudflare', country:'USA', city:'San Francisco', is_vpn:true, first_seen:'2026-02-18'})""", "ip-2")

    # vt_site
    run(cur, """CREATE (:vt_site {site_id:'SITE-001', url:'http://kookmin-bank-secure.xyz', domain:'kookmin-bank-secure.xyz', site_type:'피싱', reg_dt:'2026-02-05', status:'차단완료'})""", "site-1")

    # vt_file
    run(cur, """CREATE (:vt_file {file_id:'FILE-001', file_name:'금융보안인증서_설치.exe', file_hash:'a3f1c2d4e5b6789012345678abcdef01', file_type:'EXE', malware_type:'RAT', detected_dt:'2026-03-01'})""", "file-1")

    # vt_id
    run(cur, """CREATE (:vt_id {id_id:'ID-001', id_val:'hana_k_2026', platform:'텔레그램', real_nm:'김하나', reg_dt:'2026-01-05'})""", "id-1")
    run(cur, """CREATE (:vt_id {id_id:'ID-002', id_val:'darkweb_duri88', platform:'다크웹포럼', real_nm:'이두리', reg_dt:'2025-12-10'})""", "id-2")

    # vt_email
    run(cur, """CREATE (:vt_email {email_id:'EMAIL-001', email_addr:'kookmin.secure@gmail.com', provider:'Gmail', used_for:'피싱메일발송', reg_dt:'2026-02-03'})""", "email-1")
    run(cur, """CREATE (:vt_email {email_id:'EMAIL-002', email_addr:'prosecutor.notice@naver.com', provider:'Naver', used_for:'피싱메일발송', reg_dt:'2026-02-15'})""", "email-2")

    # vt_crypto
    run(cur, """CREATE (:vt_crypto {wallet_id:'WALLET-001', address:'1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf8N', coin_type:'BTC', balance:'1.234', exchange:'바이낸스', first_tx_dt:'2026-03-08'})""", "crypto-1")

    # vt_dev
    run(cur, """CREATE (:vt_dev {dev_id:'DEV-001', dev_type:'스마트폰', model:'Galaxy S24', imei:'359876543210001', os:'Android 14', seized:true, seized_dt:'2026-03-20'})""", "dev-1")

    # vt_atm
    run(cur, """CREATE (:vt_atm {atm_id:'ATM-001', atm_no:'ATM-KB-강남-001', bank_cd:'004', bank_name:'국민은행', address:'서울 강남구 역삼동 123', lat:'37.498', lon:'127.028'})""", "atm-1")
    run(cur, """CREATE (:vt_atm {atm_id:'ATM-002', atm_no:'ATM-WR-부평-005', bank_cd:'020', bank_name:'우리은행', address:'인천 부평구 부평동 45', lat:'37.489', lon:'126.723'})""", "atm-2")

    # vt_vhcl
    run(cur, """CREATE (:vt_vhcl {vhcl_id:'VHC-001', plate_no:'12가3456', model:'소나타', color:'흰색', owner:'이두리', reg_dt:'2023-04-01'})""", "vhcl-1")

    # ── L5 · Location ──────────────────────────────
    print("  [L5 Location]")
    run(cur, """CREATE (:vt_loc {loc_id:'LOC-001', loc_name:'서울 강남구 역삼동', lat:'37.498', lon:'127.028', loc_type:'ATM출금지점', addr:'서울 강남구 역삼동 123'})""", "loc-1")
    run(cur, """CREATE (:vt_loc {loc_id:'LOC-002', loc_name:'인천 부평구 부평동', lat:'37.489', lon:'126.723', loc_type:'ATM출금지점', addr:'인천 부평구 부평동 45'})""", "loc-2")
    run(cur, """CREATE (:vt_loc {loc_id:'LOC-003', loc_name:'서울 강북구 미아동', lat:'37.643', lon:'127.025', loc_type:'기지국위치', addr:'서울 강북구 미아동 일대'})""", "loc-3")

    # ── L6 · Event ─────────────────────────────────
    print("  [L6 Event]")

    # vt_transfer
    run(cur, """CREATE (:vt_transfer {tx_id:'TX-001', dlng_amt:'15000000', dlng_dt:'2026-03-05 14:23:00', tx_type:'이체', memo:'보안계좌이체', verified:true})""", "tx-1")
    run(cur, """CREATE (:vt_transfer {tx_id:'TX-002', dlng_amt:'30000000', dlng_dt:'2026-03-05 15:10:00', tx_type:'이체', memo:'', verified:true})""", "tx-2")
    run(cur, """CREATE (:vt_transfer {tx_id:'TX-003', dlng_amt:'10000000', dlng_dt:'2026-03-06 09:30:00', tx_type:'ATM출금', memo:'', verified:true})""", "tx-3")
    run(cur, """CREATE (:vt_transfer {tx_id:'TX-004', dlng_amt:'10000000', dlng_dt:'2026-03-06 10:15:00', tx_type:'ATM출금', memo:'', verified:true})""", "tx-4")
    run(cur, """CREATE (:vt_transfer {tx_id:'TX-005', dlng_amt:'20000000', dlng_dt:'2026-03-07 11:00:00', tx_type:'가상화폐전환', memo:'BTC전환', verified:false})""", "tx-5")

    # vt_call
    run(cur, """CREATE (:vt_call {call_id:'CALL-001', call_dt:'2026-03-04 13:00:00', duration:1240, call_type:'사칭전화', direction:'발신', content_summary:'국민은행 직원 사칭, 보안계좌 이체 요구'})""", "call-1")
    run(cur, """CREATE (:vt_call {call_id:'CALL-002', call_dt:'2026-03-04 15:30:00', duration:980, call_type:'사칭전화', direction:'발신', content_summary:'검찰청 직원 사칭, 수사 협조 명목 송금 요구'})""", "call-2")
    run(cur, """CREATE (:vt_call {call_id:'CALL-003', call_dt:'2026-03-05 09:00:00', duration:320, call_type:'일반통화', direction:'수신', content_summary:'피해자 확인 전화'})""", "call-3")
    run(cur, """CREATE (:vt_call {call_id:'CALL-004', call_dt:'2026-03-06 08:45:00', duration:180, call_type:'일반통화', direction:'발신', content_summary:'공범 간 연락'})""", "call-4")

    # vt_access
    run(cur, """CREATE (:vt_access {access_id:'ACC-001', access_dt:'2026-02-28 02:15:00', access_type:'웹접속', target:'kookmin-bank-secure.xyz', result:'성공', user_agent:'Chrome/120'})""", "access-1")
    run(cur, """CREATE (:vt_access {access_id:'ACC-002', access_dt:'2026-03-01 03:30:00', access_type:'C2서버접속', target:'104.28.55.99:4444', result:'성공', user_agent:'python-requests'})""", "access-2")

    # vt_msg
    run(cur, """CREATE (:vt_msg {msg_id:'MSG-001', send_dt:'2026-03-04 12:55:00', msg_type:'문자', content:'[국민은행] 고객님 계좌 이상거래 감지. 즉시 연락주세요 010-7777-0001', is_phishing:true})""", "msg-1")
    run(cur, """CREATE (:vt_msg {msg_id:'MSG-002', send_dt:'2026-03-04 15:20:00', msg_type:'문자', content:'[대검찰청] 귀하의 계좌가 범죄에 연루. 수사관 02-530-4800으로 연락', is_phishing:true})""", "msg-2")
    run(cur, """CREATE (:vt_msg {msg_id:'MSG-003', send_dt:'2026-03-05 08:30:00', msg_type:'텔레그램', content:'오늘 출금 완료하면 40% 줄게', is_phishing:false})""", "msg-3")

    # vt_movement
    run(cur, """CREATE (:vt_movement {mov_id:'MOV-001', mov_type:'lpr', timestamp:'2026-03-06 09:20:00', plate_no:'12가3456', speed:45, direction:'남→북'})""", "mov-1")
    run(cur, """CREATE (:vt_movement {mov_id:'MOV-002', mov_type:'cell', timestamp:'2026-03-06 10:00:00', cell_id:'CELL-강북-0234', signal_strength:-78})""", "mov-2")

    # vt_impersonation ← V3.3 핵심 신설 노드
    run(cur, """
        CREATE (:vt_impersonation {
            event_id: 'IMP-001',
            method: '전화사칭',
            fake_name: '국민은행 보안팀 박대리',
            script_type: '보안계좌이체유도',
            start_dt: '2026-03-04 13:00:00',
            end_dt: '2026-03-04 14:00:00',
            source_id: 'SRC-KICS-001',
            confidence: 0.97,
            verified: true
        })
    """, "impersonation-1")

    run(cur, """
        CREATE (:vt_impersonation {
            event_id: 'IMP-002',
            method: '전화+문자사칭',
            fake_name: '대검찰청 수사관 최검사',
            script_type: '수사협조명목송금유도',
            start_dt: '2026-03-04 15:30:00',
            end_dt: '2026-03-04 17:00:00',
            source_id: 'SRC-KICS-001',
            confidence: 0.95,
            verified: true
        })
    """, "impersonation-2")

    print("  ✅ 노드 삽입 완료\n")

    # ══════════════════════════════════════════════
    # 3. 엣지 삽입
    # ══════════════════════════════════════════════
    print("🔗 엣지 삽입 중...\n")

    # L1 → L2: sourced_from
    run(cur, "MATCH (c:vt_case {flnm:'DEMO-2026-001'}), (s:vt_src {src_id:'SRC-KICS-001'}) CREATE (c)-[:sourced_from {rec_created:'2026-03-05', verified:true}]->(s)", "src←case")
    run(cur, "MATCH (p:vt_petition {pettn_id:'PTN-2026-001'}), (s:vt_src {src_id:'SRC-KICS-001'}) CREATE (p)-[:sourced_from {rec_created:'2026-03-02'}]->(s)", "src←ptn1")
    run(cur, "MATCH (p:vt_petition {pettn_id:'PTN-2026-002'}), (s:vt_src {src_id:'SRC-KICS-001'}) CREATE (p)-[:sourced_from {rec_created:'2026-03-03'}]->(s)", "src←ptn2")

    # L2: petition → case (filed_as)
    run(cur, "MATCH (p:vt_petition {pettn_id:'PTN-2026-001'}), (c:vt_case {flnm:'DEMO-2026-001'}) CREATE (p)-[:filed_as {rec_created:'2026-03-05'}]->(c)", "filed_as-1")
    run(cur, "MATCH (p:vt_petition {pettn_id:'PTN-2026-002'}), (c:vt_case {flnm:'DEMO-2026-001'}) CREATE (p)-[:filed_as {rec_created:'2026-03-05'}]->(c)", "filed_as-2")
    run(cur, "MATCH (p1:vt_petition {pettn_id:'PTN-2026-001'}), (p2:vt_petition {pettn_id:'PTN-2026-002'}) CREATE (p1)-[:clusters_with {similarity:0.87, rec_created:'2026-03-05'}]->(p2)", "clusters_with")

    # L3 Person → Case
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (c:vt_case {flnm:'DEMO-2026-001'}) CREATE (p)-[:suspect_in {role:'주범', rec_created:'2026-03-10', verified:true}]->(c)", "suspect_in-1")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (c:vt_case {flnm:'DEMO-2026-001'}) CREATE (p)-[:suspect_in {role:'공범', rec_created:'2026-03-10', verified:true}]->(c)", "suspect_in-2")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-V001'}), (c:vt_case {flnm:'DEMO-2026-001'}) CREATE (p)-[:victim_in {damage_amt:'45000000', rec_created:'2026-03-05'}]->(c)", "victim_in-1")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-V002'}), (c:vt_case {flnm:'DEMO-2026-001'}) CREATE (p)-[:victim_in {damage_amt:'40000000', rec_created:'2026-03-05'}]->(c)", "victim_in-2")

    # L3 Person → Org
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (o:vt_org {org_id:'ORG-003'}) CREATE (p)-[:works_at {role:'수배자', rec_created:'2026-03-15'}]->(o)", "works_at")

    # L4: Person → Object (소유)
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (b:vt_bacnt {acnt_id:'ACNT-001'}) CREATE (p)-[:has_account {verified:true, rec_created:'2026-03-10'}]->(b)", "has_acnt-1")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (b:vt_bacnt {acnt_id:'ACNT-002'}) CREATE (p)-[:has_account {verified:true, rec_created:'2026-03-12'}]->(b)", "has_acnt-2")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-V001'}), (b:vt_bacnt {acnt_id:'ACNT-V01'}) CREATE (p)-[:has_account {verified:true, rec_created:'2026-03-05'}]->(b)", "has_acnt-v1")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-V002'}), (b:vt_bacnt {acnt_id:'ACNT-V02'}) CREATE (p)-[:has_account {verified:true, rec_created:'2026-03-05'}]->(b)", "has_acnt-v2")

    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (t:vt_telno {tel_id:'TEL-001'}) CREATE (p)-[:owns_phone {verified:true, rec_created:'2026-03-10'}]->(t)", "owns_phone-1")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (t:vt_telno {tel_id:'TEL-002'}) CREATE (p)-[:owns_phone {verified:true, rec_created:'2026-03-12'}]->(t)", "owns_phone-2")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (t:vt_telno {tel_id:'TEL-A01'}) CREATE (p)-[:owns_phone {verified:true, rec_created:'2026-03-10'}]->(t)", "owns_phone-3")

    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (i:vt_id {id_id:'ID-001'}) CREATE (p)-[:uses_id {platform:'텔레그램', verified:true, rec_created:'2026-03-10'}]->(i)", "uses_id-1")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (i:vt_id {id_id:'ID-002'}) CREATE (p)-[:uses_id {platform:'다크웹포럼', verified:false, rec_created:'2026-03-12'}]->(i)", "uses_id-2")

    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (e:vt_email {email_id:'EMAIL-001'}) CREATE (p)-[:uses_email {verified:true, rec_created:'2026-03-10'}]->(e)", "uses_email-1")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (e:vt_email {email_id:'EMAIL-002'}) CREATE (p)-[:uses_email {verified:false, rec_created:'2026-03-12'}]->(e)", "uses_email-2")

    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (w:vt_crypto {wallet_id:'WALLET-001'}) CREATE (p)-[:owns_wallet {verified:false, rec_created:'2026-03-15'}]->(w)", "owns_wallet")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (d:vt_dev {dev_id:'DEV-001'}) CREATE (p)-[:uses_device {seized:true, rec_created:'2026-03-20'}]->(d)", "uses_device")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (v:vt_vhcl {vhcl_id:'VHC-001'}) CREATE (p)-[:owns_vehicle {verified:true, rec_created:'2026-03-12'}]->(v)", "owns_vehicle")

    # vt_bacnt → vt_org (belongs_to)
    run(cur, "MATCH (b:vt_bacnt {acnt_id:'ACNT-001'}), (o:vt_org {org_id:'ORG-001'}) CREATE (b)-[:belongs_to {rec_created:'2026-03-10'}]->(o)", "belongs_to-1")
    run(cur, "MATCH (b:vt_bacnt {acnt_id:'ACNT-V01'}), (o:vt_org {org_id:'ORG-001'}) CREATE (b)-[:belongs_to {rec_created:'2026-03-05'}]->(o)", "belongs_to-2")

    # vt_site → vt_ip (resolves_to)
    run(cur, "MATCH (s:vt_site {site_id:'SITE-001'}), (ip:vt_ip {ip_id:'IP-001'}) CREATE (s)-[:resolves_to {rec_created:'2026-02-28'}]->(ip)", "resolves_to")

    # vt_site → vt_file (contains_file)
    run(cur, "MATCH (s:vt_site {site_id:'SITE-001'}), (f:vt_file {file_id:'FILE-001'}) CREATE (s)-[:contains_file {rec_created:'2026-02-28'}]->(f)", "contains_file")

    # ── V3.3 사칭 2-홉 패턴: used_for → vt_impersonation → targets → vt_org
    run(cur, "MATCH (t:vt_telno {tel_id:'TEL-001'}), (imp:vt_impersonation {event_id:'IMP-001'}) CREATE (t)-[:used_for {imprsn_type:'전화사칭', source_id:'SRC-KICS-001', rec_created:'2026-03-10', verified:true}]->(imp)", "used_for-tel1")
    run(cur, "MATCH (e:vt_email {email_id:'EMAIL-001'}), (imp:vt_impersonation {event_id:'IMP-001'}) CREATE (e)-[:used_for {imprsn_type:'이메일사칭', source_id:'SRC-KICS-001', rec_created:'2026-03-10', verified:true}]->(imp)", "used_for-email1")
    run(cur, "MATCH (imp:vt_impersonation {event_id:'IMP-001'}), (o:vt_org {org_id:'ORG-001'}) CREATE (imp)-[:targets {source_id:'SRC-KICS-001', rec_created:'2026-03-10', verified:true}]->(o)", "targets-1")

    run(cur, "MATCH (t:vt_telno {tel_id:'TEL-002'}), (imp:vt_impersonation {event_id:'IMP-002'}) CREATE (t)-[:used_for {imprsn_type:'전화사칭', source_id:'SRC-KICS-001', rec_created:'2026-03-12', verified:true}]->(imp)", "used_for-tel2")
    run(cur, "MATCH (e:vt_email {email_id:'EMAIL-002'}), (imp:vt_impersonation {event_id:'IMP-002'}) CREATE (e)-[:used_for {imprsn_type:'이메일사칭', source_id:'SRC-KICS-001', rec_created:'2026-03-12', verified:false}]->(imp)", "used_for-email2")
    run(cur, "MATCH (imp:vt_impersonation {event_id:'IMP-002'}), (o:vt_org {org_id:'ORG-002'}) CREATE (imp)-[:targets {source_id:'SRC-KICS-001', rec_created:'2026-03-12', verified:true}]->(o)", "targets-2")

    # ── 이체 흐름: 피해자계좌 → vt_transfer → 대포계좌
    run(cur, "MATCH (b:vt_bacnt {acnt_id:'ACNT-V01'}), (tx:vt_transfer {tx_id:'TX-001'}) CREATE (b)-[:from_account {rec_created:'2026-03-05'}]->(tx)", "from_acnt-1")
    run(cur, "MATCH (tx:vt_transfer {tx_id:'TX-001'}), (b:vt_bacnt {acnt_id:'ACNT-001'}) CREATE (tx)-[:to_account {rec_created:'2026-03-05'}]->(b)", "to_acnt-1")

    run(cur, "MATCH (b:vt_bacnt {acnt_id:'ACNT-V02'}), (tx:vt_transfer {tx_id:'TX-002'}) CREATE (b)-[:from_account {rec_created:'2026-03-05'}]->(tx)", "from_acnt-2")
    run(cur, "MATCH (tx:vt_transfer {tx_id:'TX-002'}), (b:vt_bacnt {acnt_id:'ACNT-002'}) CREATE (tx)-[:to_account {rec_created:'2026-03-05'}]->(b)", "to_acnt-2")

    run(cur, "MATCH (b:vt_bacnt {acnt_id:'ACNT-001'}), (tx:vt_transfer {tx_id:'TX-003'}) CREATE (b)-[:from_account {rec_created:'2026-03-06'}]->(tx)", "from_acnt-3")
    run(cur, "MATCH (b:vt_bacnt {acnt_id:'ACNT-002'}), (tx:vt_transfer {tx_id:'TX-004'}) CREATE (b)-[:from_account {rec_created:'2026-03-06'}]->(tx)", "from_acnt-4")
    run(cur, "MATCH (b:vt_bacnt {acnt_id:'ACNT-001'}), (tx:vt_transfer {tx_id:'TX-005'}) CREATE (b)-[:from_account {rec_created:'2026-03-07'}]->(tx)", "from_acnt-5")
    run(cur, "MATCH (tx:vt_transfer {tx_id:'TX-005'}), (w:vt_crypto {wallet_id:'WALLET-001'}) CREATE (tx)-[:to_account {rec_created:'2026-03-07'}]->(w)", "to_crypto")

    # ── 통화 이벤트
    run(cur, "MATCH (t:vt_telno {tel_id:'TEL-001'}), (c:vt_call {call_id:'CALL-001'}) CREATE (t)-[:caller {rec_created:'2026-03-04'}]->(c)", "caller-1")
    run(cur, "MATCH (c:vt_call {call_id:'CALL-001'}), (t:vt_telno {tel_id:'TEL-A01'}) CREATE (c)-[:callee {rec_created:'2026-03-04'}]->(t)", "callee-1")
    run(cur, "MATCH (t:vt_telno {tel_id:'TEL-002'}), (c:vt_call {call_id:'CALL-002'}) CREATE (t)-[:caller {rec_created:'2026-03-04'}]->(c)", "caller-2")
    run(cur, "MATCH (t:vt_telno {tel_id:'TEL-A01'}), (c:vt_call {call_id:'CALL-003'}) CREATE (t)-[:caller {rec_created:'2026-03-05'}]->(c)", "caller-3")
    run(cur, "MATCH (t:vt_telno {tel_id:'TEL-001'}), (c:vt_call {call_id:'CALL-004'}) CREATE (t)-[:caller {rec_created:'2026-03-06'}]->(c)", "caller-4")

    # ── 문자 이벤트
    run(cur, "MATCH (t:vt_telno {tel_id:'TEL-001'}), (m:vt_msg {msg_id:'MSG-001'}) CREATE (t)-[:sent_msg {rec_created:'2026-03-04'}]->(m)", "sent_msg-1")
    run(cur, "MATCH (t:vt_telno {tel_id:'TEL-002'}), (m:vt_msg {msg_id:'MSG-002'}) CREATE (t)-[:sent_msg {rec_created:'2026-03-04'}]->(m)", "sent_msg-2")
    run(cur, "MATCH (i:vt_id {id_id:'ID-001'}), (m:vt_msg {msg_id:'MSG-003'}) CREATE (i)-[:sent_msg {rec_created:'2026-03-05'}]->(m)", "sent_msg-3")

    # ── 접속 이벤트
    # ACC-001: 피싱 사이트 접속 (국내 IP → 피싱 사이트)
    run(cur, "MATCH (ip:vt_ip {ip_id:'IP-001'}), (a:vt_access {access_id:'ACC-001'}) CREATE (ip)-[:used_ip {rec_created:'2026-02-28'}]->(a)", "used_ip-1")
    run(cur, "MATCH (a:vt_access {access_id:'ACC-001'}), (s:vt_site {site_id:'SITE-001'}) CREATE (a)-[:accessed_from {rec_created:'2026-02-28'}]->(s)", "accessed_from-1")
    # ACC-002: C2 서버 접속 — 압수폰(DEV-001) → VPN(IP-002) → C2 접속, 주범(PSN-A001) 행위자
    run(cur, "MATCH (d:vt_dev {dev_id:'DEV-001'}), (ip:vt_ip {ip_id:'IP-002'}) CREATE (d)-[:used_ip {source:'기기로그', note:'C2 접속용 VPN', rec_created:'2026-03-01', verified:true}]->(ip)", "dev_used_vpn")
    run(cur, "MATCH (ip:vt_ip {ip_id:'IP-002'}), (a:vt_access {access_id:'ACC-002'}) CREATE (ip)-[:used_ip {rec_created:'2026-03-01'}]->(a)", "used_ip-2")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (a:vt_access {access_id:'ACC-002'}) CREATE (p)-[:recorded_in {source:'C2서버로그', note:'파이썬스크립트 자동접속', rec_created:'2026-03-01', verified:false}]->(a)", "psn_c2_access")

    # ── 이동 이벤트
    # MOV-001: 차량 LPR — 차량 → 이동 → 위치
    run(cur, "MATCH (v:vt_vhcl {vhcl_id:'VHC-001'}), (m:vt_movement {mov_id:'MOV-001'}) CREATE (v)-[:recorded_in {rec_created:'2026-03-06'}]->(m)", "recorded_in-vhcl")
    run(cur, "MATCH (m:vt_movement {mov_id:'MOV-001'}), (l:vt_loc {loc_id:'LOC-001'}) CREATE (m)-[:occurred_at {rec_created:'2026-03-06'}]->(l)", "occurred_at-1")
    # MOV-002: 기지국 추적 — 인물(이두리) + 전화번호 → 이동 → 위치
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (m:vt_movement {mov_id:'MOV-002'}) CREATE (p)-[:recorded_in {source:'기지국데이터', rec_created:'2026-03-06', verified:true}]->(m)", "recorded_in-psn")
    run(cur, "MATCH (t:vt_telno {tel_id:'TEL-A01'}), (m:vt_movement {mov_id:'MOV-002'}) CREATE (t)-[:recorded_in {source:'기지국데이터', rec_created:'2026-03-06', verified:true}]->(m)", "recorded_in-tel")
    run(cur, "MATCH (m:vt_movement {mov_id:'MOV-002'}), (l:vt_loc {loc_id:'LOC-003'}) CREATE (m)-[:occurred_at {rec_created:'2026-03-06'}]->(l)", "occurred_at-2")

    # ── ATM → Location
    run(cur, "MATCH (a:vt_atm {atm_id:'ATM-001'}), (l:vt_loc {loc_id:'LOC-001'}) CREATE (a)-[:located_at {rec_created:'2026-03-01'}]->(l)", "located_at-1")
    run(cur, "MATCH (a:vt_atm {atm_id:'ATM-002'}), (l:vt_loc {loc_id:'LOC-002'}) CREATE (a)-[:located_at {rec_created:'2026-03-01'}]->(l)", "located_at-2")

    # ── 기기 → IP
    run(cur, "MATCH (d:vt_dev {dev_id:'DEV-001'}), (ip:vt_ip {ip_id:'IP-001'}) CREATE (d)-[:used_ip {rec_created:'2026-03-01'}]->(ip)", "dev_used_ip")

    print("  ✅ 엣지 삽입 완료\n")

    # ══════════════════════════════════════════════
    # 4. 최종 통계 확인
    # ══════════════════════════════════════════════
    print("📊 최종 통계:")
    vlabels_check = [
        'vt_src','vt_case','vt_petition','vt_psn','vt_org',
        'vt_bacnt','vt_telno','vt_ip','vt_site','vt_file',
        'vt_id','vt_email','vt_crypto','vt_dev','vt_atm','vt_vhcl',
        'vt_loc','vt_transfer','vt_call','vt_access','vt_msg',
        'vt_movement','vt_impersonation'
    ]
    total = 0
    for lbl in vlabels_check:
        try:
            cur.execute(f"MATCH (n:{lbl}) RETURN count(n)")
            cnt = int(str(cur.fetchone()[0]))
            if cnt > 0:
                print(f"  {lbl}: {cnt}개")
                total += cnt
        except Exception:
            conn.rollback()
            cur.execute(f"SET graph_path = {GRAPH}")
    print(f"  ────────────────")
    print(f"  총 노드: {total}개")

    try:
        cur.execute("MATCH ()-[r]->() RETURN count(r)")
        e_cnt = cur.fetchone()[0]
        print(f"  총 엣지: {e_cnt}개")
    except Exception:
        print("  총 엣지: (집계 생략)")

    print(f"\n✅ 데모 데이터셋 생성 완료!")
    print(f"   그래프명: {GRAPH}")
    print(f"   UI에서 그래프 선택 후 확인하세요.")

    conn.close()


if __name__ == '__main__':
    main()
