#!/usr/bin/env python3
"""
보이스피싱 데모 그래프 생성 스크립트 (v3.4 온톨로지 기준)
그래프명: ccop_demo_voice

시나리오:
  검찰청/금감원 사칭 보이스피싱 조직
  - 수사관 사칭 → 피해자 자산 이전 유도
  - 콜센터 발신책 → 피해자 통화 → ATM 출금 유도
  - 현금수거책 → 피해자 대면 수금
  - 다단계 대포통장 세탁 (피해금 → 중간계좌 → 최종계좌)

노드: ~40개
엣지: ~60개
v3.4 신규 엣지: operates, recruits, hosts, located_at, contains_file
"""

import psycopg2

DB = dict(host='49.50.128.28', port=5333, dbname='tccopdb', user='ccop', password='Ccop@2025')

GRAPH_NAME = "ccop_demo_voice"

# ── DDL ──────────────────────────────────────────────────────────────────────
CREATE_GRAPH = f"SELECT create_graph('{GRAPH_NAME}')"

DROP_GRAPH = f"SELECT drop_graph('{GRAPH_NAME}', true)"

SET_GRAPH = f"SET graph_path = {GRAPH_NAME}"

ELABELS = [
    # Case ↔ Person
    "CREATE ELABEL IF NOT EXISTS suspect_in",
    "CREATE ELABEL IF NOT EXISTS victim_in",
    "CREATE ELABEL IF NOT EXISTS witness_in",
    # Person ↔ Person
    "CREATE ELABEL IF NOT EXISTS accomplice_of",
    "CREATE ELABEL IF NOT EXISTS recruits",        # ★ v3.4 신규
    "CREATE ELABEL IF NOT EXISTS blackmails",      # ★ v3.4 신규
    # Person ↔ Object
    "CREATE ELABEL IF NOT EXISTS owns_account",
    "CREATE ELABEL IF NOT EXISTS controls",
    "CREATE ELABEL IF NOT EXISTS uses_phone",
    "CREATE ELABEL IF NOT EXISTS owns_device",
    "CREATE ELABEL IF NOT EXISTS operates",        # ★ v3.4 신규
    # Case ↔ Object (via inference)
    "CREATE ELABEL IF NOT EXISTS linked_to",
    # Object ↔ Object
    "CREATE ELABEL IF NOT EXISTS transferred_to",
    "CREATE ELABEL IF NOT EXISTS caller",
    "CREATE ELABEL IF NOT EXISTS callee",
    "CREATE ELABEL IF NOT EXISTS sent_to",
    "CREATE ELABEL IF NOT EXISTS hosts",           # ★ v3.4 신규
    "CREATE ELABEL IF NOT EXISTS resolves_to",
    "CREATE ELABEL IF NOT EXISTS contains_file",   # ★ v3.4 신규
    "CREATE ELABEL IF NOT EXISTS used_for",
    "CREATE ELABEL IF NOT EXISTS targets",
    # Object ↔ Location
    "CREATE ELABEL IF NOT EXISTS located_at",      # ★ v3.4 신규
    # Case
    "CREATE ELABEL IF NOT EXISTS related_case",
    # Org
    "CREATE ELABEL IF NOT EXISTS belongs_to",
    "CREATE ELABEL IF NOT EXISTS member_of",
    "CREATE ELABEL IF NOT EXISTS partner_with",
]

VLABELS = [
    "CREATE VLABEL IF NOT EXISTS vt_flnm",
    "CREATE VLABEL IF NOT EXISTS vt_psn",
    "CREATE VLABEL IF NOT EXISTS vt_bacnt",
    "CREATE VLABEL IF NOT EXISTS vt_telno",
    "CREATE VLABEL IF NOT EXISTS vt_ip",
    "CREATE VLABEL IF NOT EXISTS vt_site",
    "CREATE VLABEL IF NOT EXISTS vt_file",
    "CREATE VLABEL IF NOT EXISTS vt_id",
    "CREATE VLABEL IF NOT EXISTS vt_atm",
    "CREATE VLABEL IF NOT EXISTS vt_loc",
    "CREATE VLABEL IF NOT EXISTS vt_device",
    "CREATE VLABEL IF NOT EXISTS vt_org",
    "CREATE VLABEL IF NOT EXISTS vt_evt_call",
    "CREATE VLABEL IF NOT EXISTS vt_evt_transfer",
    "CREATE VLABEL IF NOT EXISTS vt_evt_msg",
    "CREATE VLABEL IF NOT EXISTS vt_evt_move",
    "CREATE VLABEL IF NOT EXISTS vt_imp",  # 사칭 이벤트
]

# ── 노드 생성 ─────────────────────────────────────────────────────────────────
NODES = [
    # ── 사건 ──────────────────────────────────────────────────────────────────
    """MERGE (c:vt_flnm {
        case_id: 'CASE-2026-VC001',
        case_no: '2026-형제-보이스피싱-001',
        case_name: '검찰청 사칭 보이스피싱 조직 사건',
        crime_type: '보이스피싱',
        status: '수사중',
        opened_dt: '2026-01-10',
        total_damage: 82000000,
        victim_cnt: 3
    })""",

    # ── 인물: 용의자 ──────────────────────────────────────────────────────────
    """MERGE (p:vt_psn {
        psn_id: 'PSN-A001',
        name: '강총책',
        role: '총책',
        nationality: '한국',
        dob: '1980-05-12',
        status: '수배중',
        memo: '해외(필리핀) 거점 운영, 콜센터 총괄'
    })""",
    """MERGE (p:vt_psn {
        psn_id: 'PSN-A002',
        name: '박발신',
        role: '발신책',
        nationality: '한국',
        dob: '1995-03-28',
        status: '체포',
        memo: '검찰 수사관 사칭 전화 담당'
    })""",
    """MERGE (p:vt_psn {
        psn_id: 'PSN-A003',
        name: '윤수거',
        role: '현금수거책',
        nationality: '한국',
        dob: '1998-07-14',
        status: '체포',
        memo: '피해자 대면 현금 수거 담당'
    })""",
    """MERGE (p:vt_psn {
        psn_id: 'PSN-A004',
        name: '임세탁',
        role: '자금세탁책',
        nationality: '한국',
        dob: '1987-11-03',
        status: '추적중',
        memo: '대포통장 관리 및 자금 세탁 담당'
    })""",

    # ── 인물: 피해자 ──────────────────────────────────────────────────────────
    """MERGE (p:vt_psn {
        psn_id: 'PSN-V001',
        name: '이피해',
        role: '피해자',
        nationality: '한국',
        dob: '1965-08-20',
        damage_amount: 35000000,
        memo: '65세 주부, 금감원 직원 사칭에 속음'
    })""",
    """MERGE (p:vt_psn {
        psn_id: 'PSN-V002',
        name: '최피해',
        role: '피해자',
        nationality: '한국',
        dob: '1958-04-05',
        damage_amount: 27000000,
        memo: '68세 남성, 검찰 수사관 사칭에 속음'
    })""",
    """MERGE (p:vt_psn {
        psn_id: 'PSN-V003',
        name: '정피해',
        role: '피해자',
        nationality: '한국',
        dob: '1972-09-17',
        damage_amount: 20000000,
        memo: '54세 여성, 경찰 사칭 문자 후 전화 유도'
    })""",

    # ── 조직 ──────────────────────────────────────────────────────────────────
    """MERGE (o:vt_org {
        org_id: 'ORG-001',
        name: '마닐라 콜센터',
        org_type: '불법콜센터',
        country: '필리핀',
        city: '마닐라',
        established: '2025-06-01',
        memo: '필리핀 소재 불법 보이스피싱 콜센터'
    })""",
    """MERGE (o:vt_org {
        org_id: 'ORG-IMP-001',
        name: '대한민국 검찰청',
        org_type: '공공기관',
        country: '한국',
        memo: '사칭 대상 기관 (실제 기관)'
    })""",
    """MERGE (o:vt_org {
        org_id: 'ORG-IMP-002',
        name: '금융감독원',
        org_type: '공공기관',
        country: '한국',
        memo: '사칭 대상 기관 (실제 기관)'
    })""",

    # ── 계좌 ──────────────────────────────────────────────────────────────────
    """MERGE (a:vt_bacnt {
        acnt_id: 'ACNT-001',
        bank: '우리은행',
        acnt_no: '1002-901-234567',
        holder: '이피해',
        acnt_type: '피해자계좌',
        balance_before: 35000000
    })""",
    """MERGE (a:vt_bacnt {
        acnt_id: 'ACNT-002',
        bank: '농협',
        acnt_no: '352-0912-3456-81',
        holder: '최피해',
        acnt_type: '피해자계좌',
        balance_before: 27000000
    })""",
    """MERGE (a:vt_bacnt {
        acnt_id: 'ACNT-003',
        bank: '카카오뱅크',
        acnt_no: '3333-02-8765432',
        holder: '정피해',
        acnt_type: '피해자계좌',
        balance_before: 20000000
    })""",
    """MERGE (a:vt_bacnt {
        acnt_id: 'ACNT-D001',
        bank: '신한은행',
        acnt_no: '110-456-789012',
        holder: '김유령',
        acnt_type: '대포통장',
        memo: '1차 수금 대포계좌'
    })""",
    """MERGE (a:vt_bacnt {
        acnt_id: 'ACNT-D002',
        bank: '하나은행',
        acnt_no: '391-910234-56789',
        holder: '박유령',
        acnt_type: '대포통장',
        memo: '2차 중간 세탁 계좌'
    })""",
    """MERGE (a:vt_bacnt {
        acnt_id: 'ACNT-D003',
        bank: '국민은행',
        acnt_no: '048-21-0987654',
        holder: '이유령',
        acnt_type: '대포통장',
        memo: '최종 인출 계좌'
    })""",

    # ── 전화번호 ──────────────────────────────────────────────────────────────
    """MERGE (t:vt_telno {
        tel_id: 'TEL-001',
        number: '070-1234-5678',
        tel_type: '070인터넷전화',
        provider: '070콜게이트웨이',
        memo: '검찰 사칭 발신번호 (스푸핑)'
    })""",
    """MERGE (t:vt_telno {
        tel_id: 'TEL-002',
        number: '010-9876-5432',
        tel_type: '선불폰',
        provider: 'SKT',
        memo: '박발신 사용 대포폰'
    })""",
    """MERGE (t:vt_telno {
        tel_id: 'TEL-003',
        number: '010-5555-6666',
        tel_type: '선불폰',
        provider: 'KT',
        memo: '윤수거 연락용 대포폰'
    })""",
    """MERGE (t:vt_telno {
        tel_id: 'TEL-V001',
        number: '010-2345-6789',
        tel_type: '일반폰',
        memo: '이피해 피해자 번호'
    })""",
    """MERGE (t:vt_telno {
        tel_id: 'TEL-V002',
        number: '010-3456-7890',
        tel_type: '일반폰',
        memo: '최피해 피해자 번호'
    })""",
    """MERGE (t:vt_telno {
        tel_id: 'TEL-V003',
        number: '010-4567-8901',
        tel_type: '일반폰',
        memo: '정피해 피해자 번호'
    })""",

    # ── IP ────────────────────────────────────────────────────────────────────
    """MERGE (i:vt_ip {
        ip_id: 'IP-001',
        address: '203.0.113.45',
        ip_type: 'VoIP서버',
        country: 'PH',
        city: '마닐라',
        isp: 'PLDT Inc.',
        memo: '필리핀 VoIP 발신 서버'
    })""",
    """MERGE (i:vt_ip {
        ip_id: 'IP-002',
        address: '198.51.100.88',
        ip_type: '악성사이트서버',
        country: 'US',
        city: 'Los Angeles',
        isp: 'Cloudflare',
        memo: '사칭 사이트 호스팅 서버'
    })""",

    # ── 사이트 ────────────────────────────────────────────────────────────────
    """MERGE (s:vt_site {
        site_id: 'SITE-001',
        url: 'https://prosecution-kr-secure.com',
        site_type: '피싱사이트',
        status: '운영중',
        created_dt: '2026-01-05',
        memo: '검찰청 사칭 피싱 사이트 (개인정보 탈취)'
    })""",
    """MERGE (s:vt_site {
        site_id: 'SITE-002',
        url: 'https://fss-safe-account.net',
        site_type: '피싱사이트',
        status: '운영중',
        created_dt: '2026-01-08',
        memo: '금감원 사칭 안전계좌 이전 유도 사이트'
    })""",

    # ── 파일 ──────────────────────────────────────────────────────────────────
    """MERGE (f:vt_file {
        file_id: 'FILE-001',
        filename: '수사통보서.hwp',
        filetype: 'HWP',
        file_hash: 'sha256:aabbcc1122334455',
        file_size: 125440,
        memo: '위조 검찰 수사통보서 (개인정보 입력 유도)'
    })""",
    """MERGE (f:vt_file {
        file_id: 'FILE-002',
        filename: '금감원_계좌보호신청서.apk',
        filetype: 'APK',
        file_hash: 'sha256:ddeeff6677889900',
        file_size: 4820123,
        memo: '원격제어 악성 APK (통화가로채기 기능 포함)'
    })""",

    # ── 디지털 ID ─────────────────────────────────────────────────────────────
    """MERGE (d:vt_id {
        id_id: 'ID-001',
        id_type: '텔레그램',
        id_value: '@prosecution_official_kr',
        platform: 'Telegram',
        memo: '검찰 사칭 텔레그램 채널'
    })""",
    """MERGE (d:vt_id {
        id_id: 'ID-002',
        id_type: '텔레그램',
        id_value: '@fss_safe_transfer',
        platform: 'Telegram',
        memo: '금감원 사칭 텔레그램 채널'
    })""",

    # ── ATM ───────────────────────────────────────────────────────────────────
    """MERGE (a:vt_atm {
        atm_id: 'ATM-001',
        bank: '우리은행',
        location_desc: '서울 강남구 역삼동 GS25 앞',
        atm_serial: 'WB-ATM-2341',
        memo: '이피해 35백만원 출금 ATM'
    })""",
    """MERGE (a:vt_atm {
        atm_id: 'ATM-002',
        bank: '농협',
        location_desc: '서울 서초구 방배동 CU 편의점 내',
        atm_serial: 'NH-ATM-9876',
        memo: '최피해 27백만원 출금 ATM'
    })""",
    """MERGE (a:vt_atm {
        atm_id: 'ATM-003',
        bank: '국민은행',
        location_desc: '경기 성남시 분당구 서현역 지하',
        atm_serial: 'KB-ATM-5512',
        memo: '정피해 20백만원 출금 ATM'
    })""",

    # ── 위치 ──────────────────────────────────────────────────────────────────
    """MERGE (l:vt_loc {
        loc_id: 'LOC-001',
        loc_name: 'GS25 강남역삼점',
        address: '서울 강남구 역삼동 736-5',
        lat: 37.4989,
        lng: 127.0289,
        loc_type: '편의점ATM',
        cctv_available: true
    })""",
    """MERGE (l:vt_loc {
        loc_id: 'LOC-002',
        loc_name: 'CU 방배중앙로점',
        address: '서울 서초구 방배동 834-12',
        lat: 37.4834,
        lng: 126.9918,
        loc_type: '편의점ATM',
        cctv_available: true
    })""",
    """MERGE (l:vt_loc {
        loc_id: 'LOC-003',
        loc_name: '서현역 지하상가',
        address: '경기 성남시 분당구 서현동 266',
        lat: 37.3844,
        lng: 127.1219,
        loc_type: '지하ATM',
        cctv_available: false
    })""",
    """MERGE (l:vt_loc {
        loc_id: 'LOC-004',
        loc_name: '마닐라 콜센터 빌딩',
        address: 'BGC, Taguig, Metro Manila, Philippines',
        lat: 14.5547,
        lng: 121.0519,
        loc_type: '해외콜센터',
        cctv_available: false
    })""",

    # ── 디바이스 ──────────────────────────────────────────────────────────────
    """MERGE (d:vt_device {
        dev_id: 'DEV-001',
        device_type: '노트북',
        os: 'Windows 11',
        mac_address: 'CC:DD:EE:FF:01:02',
        memo: '박발신 콜센터 발신 장비'
    })""",

    # ── 사칭 이벤트 ───────────────────────────────────────────────────────────
    """MERGE (i:vt_imp {
        imp_id: 'IMP-001',
        imp_type: '공공기관사칭',
        target_org: '대한민국 검찰청',
        method: '전화+피싱사이트+위조문서',
        date: '2026-01-15',
        memo: '검찰 수사관 사칭 — 계좌 동결 위협'
    })""",
    """MERGE (i:vt_imp {
        imp_id: 'IMP-002',
        imp_type: '공공기관사칭',
        target_org: '금융감독원',
        method: '전화+피싱사이트+악성APK',
        date: '2026-01-20',
        memo: '금감원 직원 사칭 — 안전계좌 이전 유도'
    })""",

    # ── 이벤트: 통화 ──────────────────────────────────────────────────────────
    """MERGE (e:vt_evt_call {
        evt_id: 'CALL-001',
        call_dt: '2026-01-15 10:23:00',
        duration_sec: 1823,
        direction: 'outbound',
        memo: '박발신→이피해: 검찰 수사관 사칭 전화 (30분+)'
    })""",
    """MERGE (e:vt_evt_call {
        evt_id: 'CALL-002',
        call_dt: '2026-01-20 14:05:00',
        duration_sec: 2145,
        direction: 'outbound',
        memo: '박발신→최피해: 금감원 직원 사칭 전화'
    })""",
    """MERGE (e:vt_evt_call {
        evt_id: 'CALL-003',
        call_dt: '2026-02-03 11:30:00',
        duration_sec: 956,
        direction: 'outbound',
        memo: '박발신→정피해: 경찰청 사칭 전화'
    })""",

    # ── 이벤트: 송금 ──────────────────────────────────────────────────────────
    """MERGE (e:vt_evt_transfer {
        evt_id: 'TRF-001',
        transfer_dt: '2026-01-15 16:45:00',
        amount: 35000000,
        currency: 'KRW',
        method: 'ATM현금인출+대면수금',
        memo: '이피해 ATM 출금 후 윤수거 수거 (3,500만원)'
    })""",
    """MERGE (e:vt_evt_transfer {
        evt_id: 'TRF-002',
        transfer_dt: '2026-01-21 15:10:00',
        amount: 27000000,
        currency: 'KRW',
        method: 'ATM현금인출+대면수금',
        memo: '최피해 ATM 출금 후 윤수거 수거 (2,700만원)'
    })""",
    """MERGE (e:vt_evt_transfer {
        evt_id: 'TRF-003',
        transfer_dt: '2026-02-03 13:00:00',
        amount: 20000000,
        currency: 'KRW',
        method: '계좌이체',
        memo: '정피해 사칭계좌 이체 (2,000만원)'
    })""",
    """MERGE (e:vt_evt_transfer {
        evt_id: 'TRF-004',
        transfer_dt: '2026-01-16 09:00:00',
        amount: 60000000,
        currency: 'KRW',
        method: '계좌이체',
        memo: '1차 대포계좌 → 2차 세탁 계좌 (이피해+최피해 합산)'
    })""",
    """MERGE (e:vt_evt_transfer {
        evt_id: 'TRF-005',
        transfer_dt: '2026-02-04 10:00:000',
        amount: 82000000,
        currency: 'KRW',
        method: '계좌이체',
        memo: '2차 세탁 → 최종 인출 계좌'
    })""",

    # ── 이벤트: 메시지 ────────────────────────────────────────────────────────
    """MERGE (e:vt_evt_msg {
        evt_id: 'MSG-001',
        msg_dt: '2026-01-14 09:00:00',
        platform: 'SMS',
        content_summary: '[경찰청] 귀하의 명의 대포통장 개설 확인. 즉시 연락 요망.',
        memo: '피해자 불안 유발 문자 — 전화 유도'
    })""",
    """MERGE (e:vt_evt_msg {
        evt_id: 'MSG-002',
        msg_dt: '2026-01-15 11:00:00',
        platform: 'KakaoTalk',
        content_summary: '수사 관련 서류 첨부 (위조 수사통보서 전달)',
        memo: '위조 문서 카카오톡 전달'
    })""",
]

# ── 엣지 생성 ─────────────────────────────────────────────────────────────────
EDGES = [
    # ── Case ↔ Person ─────────────────────────────────────────────────────────
    "MATCH (c:vt_flnm{case_id:'CASE-2026-VC001'}),(p:vt_psn{psn_id:'PSN-A001'}) MERGE (p)-[:suspect_in{role:'총책',confirmed:true}]->(c)",
    "MATCH (c:vt_flnm{case_id:'CASE-2026-VC001'}),(p:vt_psn{psn_id:'PSN-A002'}) MERGE (p)-[:suspect_in{role:'발신책',confirmed:true}]->(c)",
    "MATCH (c:vt_flnm{case_id:'CASE-2026-VC001'}),(p:vt_psn{psn_id:'PSN-A003'}) MERGE (p)-[:suspect_in{role:'현금수거책',confirmed:true}]->(c)",
    "MATCH (c:vt_flnm{case_id:'CASE-2026-VC001'}),(p:vt_psn{psn_id:'PSN-A004'}) MERGE (p)-[:suspect_in{role:'자금세탁책',confirmed:false}]->(c)",
    "MATCH (c:vt_flnm{case_id:'CASE-2026-VC001'}),(p:vt_psn{psn_id:'PSN-V001'}) MERGE (p)-[:victim_in{damage_amount:35000000}]->(c)",
    "MATCH (c:vt_flnm{case_id:'CASE-2026-VC001'}),(p:vt_psn{psn_id:'PSN-V002'}) MERGE (p)-[:victim_in{damage_amount:27000000}]->(c)",
    "MATCH (c:vt_flnm{case_id:'CASE-2026-VC001'}),(p:vt_psn{psn_id:'PSN-V003'}) MERGE (p)-[:victim_in{damage_amount:20000000}]->(c)",

    # ── ★ recruits (v3.4 신규) ───────────────────────────────────────────────
    "MATCH (a:vt_psn{psn_id:'PSN-A001'}),(b:vt_psn{psn_id:'PSN-A002'}) MERGE (a)-[:recruits{recruit_type:'발신책',date:'2025-07-15',payment:'건당5만원'}]->(b)",
    "MATCH (a:vt_psn{psn_id:'PSN-A001'}),(b:vt_psn{psn_id:'PSN-A003'}) MERGE (a)-[:recruits{recruit_type:'현금수거책',date:'2025-08-01',payment:'건당10만원'}]->(b)",
    "MATCH (a:vt_psn{psn_id:'PSN-A001'}),(b:vt_psn{psn_id:'PSN-A004'}) MERGE (a)-[:recruits{recruit_type:'자금세탁책',date:'2025-09-10',payment:'5%커미션'}]->(b)",

    # ── accomplice_of ────────────────────────────────────────────────────────
    "MATCH (a:vt_psn{psn_id:'PSN-A002'}),(b:vt_psn{psn_id:'PSN-A003'}) MERGE (a)-[:accomplice_of{relation:'동일조직',org_id:'ORG-001'}]->(b)",
    "MATCH (a:vt_psn{psn_id:'PSN-A003'}),(b:vt_psn{psn_id:'PSN-A004'}) MERGE (a)-[:accomplice_of{relation:'현금→세탁인계',org_id:'ORG-001'}]->(b)",

    # ── Person → Org ─────────────────────────────────────────────────────────
    "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(o:vt_org{org_id:'ORG-001'}) MERGE (p)-[:belongs_to{role:'총책',join_dt:'2025-06-01'}]->(o)",
    "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(o:vt_org{org_id:'ORG-001'}) MERGE (p)-[:belongs_to{role:'발신책',join_dt:'2025-07-15'}]->(o)",

    # ── Person → 계좌 ─────────────────────────────────────────────────────────
    "MATCH (p:vt_psn{psn_id:'PSN-V001'}),(a:vt_bacnt{acnt_id:'ACNT-001'}) MERGE (p)-[:owns_account{verified:true}]->(a)",
    "MATCH (p:vt_psn{psn_id:'PSN-V002'}),(a:vt_bacnt{acnt_id:'ACNT-002'}) MERGE (p)-[:owns_account{verified:true}]->(a)",
    "MATCH (p:vt_psn{psn_id:'PSN-V003'}),(a:vt_bacnt{acnt_id:'ACNT-003'}) MERGE (p)-[:owns_account{verified:true}]->(a)",
    "MATCH (p:vt_psn{psn_id:'PSN-A004'}),(a:vt_bacnt{acnt_id:'ACNT-D001'}) MERGE (p)-[:controls{method:'차명계좌',verified:false}]->(a)",
    "MATCH (p:vt_psn{psn_id:'PSN-A004'}),(a:vt_bacnt{acnt_id:'ACNT-D002'}) MERGE (p)-[:controls{method:'차명계좌',verified:false}]->(a)",
    "MATCH (p:vt_psn{psn_id:'PSN-A004'}),(a:vt_bacnt{acnt_id:'ACNT-D003'}) MERGE (p)-[:controls{method:'차명계좌',verified:false}]->(a)",

    # ── Person → 전화 ─────────────────────────────────────────────────────────
    "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(t:vt_telno{tel_id:'TEL-002'}) MERGE (p)-[:uses_phone{is_burner:true}]->(t)",
    "MATCH (p:vt_psn{psn_id:'PSN-A003'}),(t:vt_telno{tel_id:'TEL-003'}) MERGE (p)-[:uses_phone{is_burner:true}]->(t)",
    "MATCH (p:vt_psn{psn_id:'PSN-V001'}),(t:vt_telno{tel_id:'TEL-V001'}) MERGE (p)-[:uses_phone{is_burner:false}]->(t)",
    "MATCH (p:vt_psn{psn_id:'PSN-V002'}),(t:vt_telno{tel_id:'TEL-V002'}) MERGE (p)-[:uses_phone{is_burner:false}]->(t)",
    "MATCH (p:vt_psn{psn_id:'PSN-V003'}),(t:vt_telno{tel_id:'TEL-V003'}) MERGE (p)-[:uses_phone{is_burner:false}]->(t)",

    # ── Person → 디바이스 ─────────────────────────────────────────────────────
    "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(d:vt_device{dev_id:'DEV-001'}) MERGE (p)-[:owns_device{usage:'발신장비'}]->(d)",

    # ── ★ operates (v3.4 신규) ───────────────────────────────────────────────
    "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(s:vt_site{site_id:'SITE-001'}) MERGE (p)-[:operates{role:'사이트운영자',since:'2026-01-05'}]->(s)",
    "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(s:vt_site{site_id:'SITE-002'}) MERGE (p)-[:operates{role:'사이트운영자',since:'2026-01-08'}]->(s)",
    "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(d:vt_id{id_id:'ID-001'}) MERGE (p)-[:operates{role:'채널운영자',platform:'Telegram'}]->(d)",
    "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(d:vt_id{id_id:'ID-002'}) MERGE (p)-[:operates{role:'채널운영자',platform:'Telegram'}]->(d)",
    "MATCH (o:vt_org{org_id:'ORG-001'}),(s:vt_site{site_id:'SITE-001'}) MERGE (o)-[:operates{role:'조직운영'}]->(s)",

    # ── ★ hosts (v3.4 신규) ──────────────────────────────────────────────────
    "MATCH (i:vt_ip{ip_id:'IP-001'}),(s:vt_site{site_id:'SITE-001'}) MERGE (i)-[:hosts{port:443,detected_dt:'2026-01-10'}]->(s)",
    "MATCH (i:vt_ip{ip_id:'IP-002'}),(s:vt_site{site_id:'SITE-002'}) MERGE (i)-[:hosts{port:80,detected_dt:'2026-01-12'}]->(s)",

    # ── ★ contains_file (v3.4 신규) ──────────────────────────────────────────
    "MATCH (s:vt_site{site_id:'SITE-001'}),(f:vt_file{file_id:'FILE-001'}) MERGE (s)-[:contains_file{file_role:'위조문서다운로드'}]->(f)",
    "MATCH (s:vt_site{site_id:'SITE-002'}),(f:vt_file{file_id:'FILE-002'}) MERGE (s)-[:contains_file{file_role:'악성APK다운로드'}]->(f)",
    "MATCH (m:vt_evt_msg{evt_id:'MSG-002'}),(f:vt_file{file_id:'FILE-001'}) MERGE (m)-[:contains_file{delivery_method:'카카오톡'}]->(f)",

    # ── ★ located_at (v3.4 신규) ─────────────────────────────────────────────
    "MATCH (a:vt_atm{atm_id:'ATM-001'}),(l:vt_loc{loc_id:'LOC-001'}) MERGE (a)-[:located_at{verified:true}]->(l)",
    "MATCH (a:vt_atm{atm_id:'ATM-002'}),(l:vt_loc{loc_id:'LOC-002'}) MERGE (a)-[:located_at{verified:true}]->(l)",
    "MATCH (a:vt_atm{atm_id:'ATM-003'}),(l:vt_loc{loc_id:'LOC-003'}) MERGE (a)-[:located_at{verified:false}]->(l)",
    "MATCH (o:vt_org{org_id:'ORG-001'}),(l:vt_loc{loc_id:'LOC-004'}) MERGE (o)-[:located_at{verified:false}]->(l)",

    # ── 사칭 이벤트 ───────────────────────────────────────────────────────────
    "MATCH (imp:vt_imp{imp_id:'IMP-001'}),(o:vt_org{org_id:'ORG-IMP-001'}) MERGE (imp)-[:targets{method:'전화사칭'}]->(o)",
    "MATCH (imp:vt_imp{imp_id:'IMP-002'}),(o:vt_org{org_id:'ORG-IMP-002'}) MERGE (imp)-[:targets{method:'전화+사이트사칭'}]->(o)",
    "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(imp:vt_imp{imp_id:'IMP-001'}) MERGE (p)-[:used_for{role:'사칭실행자'}]->(imp)",
    "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(imp:vt_imp{imp_id:'IMP-002'}) MERGE (p)-[:used_for{role:'사칭실행자'}]->(imp)",
    "MATCH (s:vt_site{site_id:'SITE-001'}),(imp:vt_imp{imp_id:'IMP-001'}) MERGE (s)-[:used_for{purpose:'신뢰도강화'}]->(imp)",
    "MATCH (s:vt_site{site_id:'SITE-002'}),(imp:vt_imp{imp_id:'IMP-002'}) MERGE (s)-[:used_for{purpose:'계좌이전유도'}]->(imp)",

    # ── 통화 이벤트 ───────────────────────────────────────────────────────────
    "MATCH (t:vt_telno{tel_id:'TEL-001'}),(e:vt_evt_call{evt_id:'CALL-001'}) MERGE (t)-[:caller{spoof:true}]->(e)",
    "MATCH (e:vt_evt_call{evt_id:'CALL-001'}),(t:vt_telno{tel_id:'TEL-V001'}) MERGE (e)-[:callee{}]->(t)",
    "MATCH (t:vt_telno{tel_id:'TEL-001'}),(e:vt_evt_call{evt_id:'CALL-002'}) MERGE (t)-[:caller{spoof:true}]->(e)",
    "MATCH (e:vt_evt_call{evt_id:'CALL-002'}),(t:vt_telno{tel_id:'TEL-V002'}) MERGE (e)-[:callee{}]->(t)",
    "MATCH (t:vt_telno{tel_id:'TEL-002'}),(e:vt_evt_call{evt_id:'CALL-003'}) MERGE (t)-[:caller{spoof:false}]->(e)",
    "MATCH (e:vt_evt_call{evt_id:'CALL-003'}),(t:vt_telno{tel_id:'TEL-V003'}) MERGE (e)-[:callee{}]->(t)",

    # ── IP → 통화 발신 ────────────────────────────────────────────────────────
    "MATCH (i:vt_ip{ip_id:'IP-001'}),(e:vt_evt_call{evt_id:'CALL-001'}) MERGE (i)-[:linked_to{reason:'VoIP발신경로'}]->(e)",
    "MATCH (i:vt_ip{ip_id:'IP-001'}),(e:vt_evt_call{evt_id:'CALL-002'}) MERGE (i)-[:linked_to{reason:'VoIP발신경로'}]->(e)",

    # ── 메시지 이벤트 ─────────────────────────────────────────────────────────
    "MATCH (t:vt_telno{tel_id:'TEL-001'}),(m:vt_evt_msg{evt_id:'MSG-001'}) MERGE (t)-[:sent_to{platform:'SMS'}]->(m)",
    "MATCH (m:vt_evt_msg{evt_id:'MSG-001'}),(t:vt_telno{tel_id:'TEL-V001'}) MERGE (m)-[:sent_to{}]->(t)",
    "MATCH (d:vt_id{id_id:'ID-001'}),(m:vt_evt_msg{evt_id:'MSG-002'}) MERGE (d)-[:sent_to{platform:'KakaoTalk'}]->(m)",

    # ── 송금 이벤트 ───────────────────────────────────────────────────────────
    "MATCH (a:vt_bacnt{acnt_id:'ACNT-001'}),(e:vt_evt_transfer{evt_id:'TRF-001'}) MERGE (a)-[:transferred_to{amount:35000000}]->(e)",
    "MATCH (e:vt_evt_transfer{evt_id:'TRF-001'}),(a:vt_bacnt{acnt_id:'ACNT-D001'}) MERGE (e)-[:transferred_to{}]->(a)",
    "MATCH (a:vt_bacnt{acnt_id:'ACNT-002'}),(e:vt_evt_transfer{evt_id:'TRF-002'}) MERGE (a)-[:transferred_to{amount:27000000}]->(e)",
    "MATCH (e:vt_evt_transfer{evt_id:'TRF-002'}),(a:vt_bacnt{acnt_id:'ACNT-D001'}) MERGE (e)-[:transferred_to{}]->(a)",
    "MATCH (a:vt_bacnt{acnt_id:'ACNT-003'}),(e:vt_evt_transfer{evt_id:'TRF-003'}) MERGE (a)-[:transferred_to{amount:20000000}]->(e)",
    "MATCH (e:vt_evt_transfer{evt_id:'TRF-003'}),(a:vt_bacnt{acnt_id:'ACNT-D001'}) MERGE (e)-[:transferred_to{}]->(a)",
    # 자금 세탁 경로
    "MATCH (a:vt_bacnt{acnt_id:'ACNT-D001'}),(e:vt_evt_transfer{evt_id:'TRF-004'}) MERGE (a)-[:transferred_to{amount:60000000}]->(e)",
    "MATCH (e:vt_evt_transfer{evt_id:'TRF-004'}),(a:vt_bacnt{acnt_id:'ACNT-D002'}) MERGE (e)-[:transferred_to{}]->(a)",
    "MATCH (a:vt_bacnt{acnt_id:'ACNT-D002'}),(e:vt_evt_transfer{evt_id:'TRF-005'}) MERGE (a)-[:transferred_to{amount:82000000}]->(e)",
    "MATCH (e:vt_evt_transfer{evt_id:'TRF-005'}),(a:vt_bacnt{acnt_id:'ACNT-D003'}) MERGE (e)-[:transferred_to{}]->(a)",

    # ── ATM → 송금 이벤트 ────────────────────────────────────────────────────
    "MATCH (a:vt_atm{atm_id:'ATM-001'}),(e:vt_evt_transfer{evt_id:'TRF-001'}) MERGE (a)-[:linked_to{reason:'ATM출금경로'}]->(e)",
    "MATCH (a:vt_atm{atm_id:'ATM-002'}),(e:vt_evt_transfer{evt_id:'TRF-002'}) MERGE (a)-[:linked_to{reason:'ATM출금경로'}]->(e)",
    "MATCH (a:vt_atm{atm_id:'ATM-003'}),(e:vt_evt_transfer{evt_id:'TRF-003'}) MERGE (a)-[:linked_to{reason:'ATM출금경로'}]->(e)",
]


def get_db_connection():
    return psycopg2.connect(**DB)


def run_query(cur, query, label=""):
    try:
        cur.execute(query)
        return True
    except Exception as e:
        tag = f"[{label}] " if label else ""
        print(f"  {tag}WARN: {e}")
        return False


def main():
    conn = get_db_connection()
    conn.autocommit = True
    cur = conn.cursor()

    print(f"\n{'='*60}")
    print(f"  보이스피싱 데모 그래프 생성: {GRAPH_NAME}")
    print(f"{'='*60}")

    # 기존 그래프 삭제
    print("\n[1] 기존 그래프 삭제...")
    try:
        cur.execute(f"DROP GRAPH {GRAPH_NAME} CASCADE")
        print(f"  기존 '{GRAPH_NAME}' 그래프 삭제 완료")
    except Exception:
        print(f"  '{GRAPH_NAME}' 그래프 없음 (신규 생성)")

    # 그래프 생성
    print("\n[2] 그래프 생성...")
    cur.execute(f"CREATE GRAPH {GRAPH_NAME}")
    print(f"  '{GRAPH_NAME}' 그래프 생성 완료")

    # SET graph_path
    cur.execute(SET_GRAPH)

    # 레이블 생성
    print("\n[3] 버텍스/엣지 레이블 생성...")
    for stmt in VLABELS + ELABELS:
        run_query(cur, stmt)
    print(f"  {len(VLABELS)} 버텍스 레이블, {len(ELABELS)} 엣지 레이블 등록")

    # 노드 생성
    print("\n[4] 노드 생성...")
    ok = sum(run_query(cur, q, "NODE") for q in NODES)
    print(f"  {ok}/{len(NODES)} 노드 생성 완료")

    # 엣지 생성
    print("\n[5] 엣지 생성...")
    ok = sum(run_query(cur, q, "EDGE") for q in EDGES)
    print(f"  {ok}/{len(EDGES)} 엣지 생성 완료")

    # 통계
    print("\n[6] 생성 결과 확인...")
    cur.execute(SET_GRAPH)
    cur.execute("MATCH (n) RETURN labels(n) AS label, count(*) AS cnt ORDER BY cnt DESC")
    rows = cur.fetchall()
    total_nodes = sum(r[1] for r in rows)
    print(f"\n  노드 통계 (총 {total_nodes}개):")
    for label, cnt in rows:
        print(f"    {label}: {cnt}")

    cur.execute("MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS cnt ORDER BY cnt DESC")
    rows = cur.fetchall()
    total_edges = sum(r[1] for r in rows)
    print(f"\n  엣지 통계 (총 {total_edges}개):")
    for rel, cnt in rows:
        print(f"    {rel}: {cnt}")

    # v3.4 신규 엣지 확인
    print("\n  [★ v3.4 신규 엣지 검증]")
    for new_edge in ['operates', 'recruits', 'hosts', 'contains_file', 'located_at']:
        cur.execute(f"MATCH ()-[r:{new_edge}]->() RETURN count(r) AS cnt")
        cnt = cur.fetchone()[0]
        status = "✅" if cnt > 0 else "❌"
        print(f"    {status} {new_edge}: {cnt}개")

    cur.close()
    conn.close()

    print(f"\n{'='*60}")
    print(f"  완료! 그래프 '{GRAPH_NAME}' 생성 성공")
    print(f"  UI: http://localhost:5002")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
