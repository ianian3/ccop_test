"""
CCOP v3.4 온톨로지 데모 데이터셋 생성 스크립트
==================================================
시나리오: 텔레그램 기반 몸캠피싱 + 투자사기 + 대포통장 복합 조직 사건
         (DEMO-2026-V34)

v3.4 신규 엣지 6종 전부 시연:
  ★ operates    : 조직원 → 텔레그램채널 / 피싱사이트 운영
  ★ recruits    : 총책 → 조직원 (대포통장·해커·투자사기 모집)
  ★ blackmails  : 총책 → 피해자 (몸캠 협박)
  ★ hosts       : 서버IP → 피싱사이트 / 투자사기사이트 호스팅
  ★ contains_file: 사이트/메시지 → 협박영상 / 악성코드
  ★ located_at  : ATM → 위치 (출금 현장)

노드 구성 (전 타입 커버):
  L0 Source     : vt_src ×1
  L1 Case       : vt_case ×2, vt_petition ×2
  L2 Person     : vt_psn ×6, vt_org ×3
  L3 Object     : vt_bacnt ×4, vt_telno ×4, vt_ip ×3, vt_site ×3,
                  vt_file ×2, vt_id ×3, vt_email ×2, vt_crypto ×1,
                  vt_dev ×2, vt_atm ×2, vt_vhcl ×1
  L4 Location   : vt_loc ×3
  L5 Event      : vt_transfer ×5, vt_call ×3, vt_access ×2,
                  vt_msg ×3, vt_movement ×2, vt_impersonation ×1
총 노드: 58개  |  총 엣지: 70+개
"""

import psycopg2

DB = dict(host='49.50.128.28', port=5333, dbname='tccopdb', user='ccop', password='Ccop@2025')
GRAPH = 'ccop_demo_v34'


def run(cur, cypher, label=""):
    try:
        cur.execute(cypher)
    except Exception as e:
        print(f"  ⚠️  [{label}] {e}")


def q(s):
    return str(s).replace("'", "''")


def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()

    # ── 0. 그래프 초기화 ───────────────────────────
    print(f"🗑️  기존 그래프 '{GRAPH}' 삭제 중...")
    try:
        cur.execute(f"DROP GRAPH {GRAPH} CASCADE")
    except Exception:
        pass
    cur.execute(f"CREATE GRAPH {GRAPH}")
    cur.execute(f"SET graph_path = {GRAPH}")
    print(f"✅ 그래프 '{GRAPH}' 생성 완료\n")

    # ── 1. 레이블 등록 ─────────────────────────────
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
        # Cat.1 사건 연결
        'suspect_in', 'victim_in', 'witness_in', 'filed_as', 'clusters_with', 'related_case',
        # Cat.2 신원/소유
        'has_account', 'controls', 'owns_phone', 'owns_device', 'owns_vehicle',
        'uses_id', 'uses_email', 'drives', 'used_ip', 'owns', 'registered_to',
        # Cat.3 인물 관계 (v3.4 신규 포함)
        'member_of', 'works_at', 'accomplice_of', 'sameAs', 'contradicts',
        'recruits', 'blackmails',
        # Cat.4 운영/인프라 (v3.4 신규)
        'operates', 'hosts', 'resolves_to', 'contains_file', 'located_at', 'belongs_to',
        # Cat.5 자금 흐름
        'from_account', 'to_account', 'transferred_to',
        # Cat.6 사칭 패턴
        'used_for', 'targets',
        # Cat.7 통신
        'caller', 'callee', 'sent_msg', 'received_msg',
        # Cat.8 디지털 접속
        'accessed_from', 'linked_to',
        # Cat.9 위치/이동
        'recorded_in', 'occurred_at', 'mentions_account',
        # Cat.10 메타
        'sourced_from',
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

    # ── L0 · Source ────────────────────────────────
    print("  [L0 Source]")
    run(cur, """
        CREATE (:vt_src {
            src_id: 'SRC-KICS-001',
            src_name: 'KICS 사이버범죄신고시스템',
            src_type: 'OFFICIAL', tier: 1,
            reliability: 0.95,
            rec_created: '2026-01-10'
        })
    """, "vt_src")

    # ── L1 · Case ──────────────────────────────────
    print("  [L1 Case + Petition]")
    run(cur, """
        CREATE (:vt_case {
            flnm: 'CASE-MC-001',
            crime_name: '텔레그램 몸캠피싱 협박 사건',
            crime_type: 'MOCCAM_PHISHING',
            crime_method: '영상협박형',
            status: '수사중',
            reg_date: '2026-02-10',
            damage_amt: '55000000',
            victim_cnt: 2
        })
    """, "vt_case-MC")

    run(cur, """
        CREATE (:vt_case {
            flnm: 'CASE-IS-001',
            crime_name: '가상투자플랫폼 투자사기 사건',
            crime_type: 'INVEST_FRAUD',
            crime_method: '수익보장형',
            status: '수사중',
            reg_date: '2026-02-20',
            damage_amt: '120000000',
            victim_cnt: 5
        })
    """, "vt_case-IS")

    run(cur, """
        CREATE (:vt_petition {
            pettn_id: 'PTN-2026-011',
            petitioner: '최피해자',
            content: '텔레그램에서 만난 상대가 영상통화 녹화 후 유포 협박',
            reg_date: '2026-02-08',
            status: '사건전환',
            source_id: 'SRC-KICS-001'
        })
    """, "vt_petition-1")

    run(cur, """
        CREATE (:vt_petition {
            pettn_id: 'PTN-2026-012',
            petitioner: '박투자',
            content: '월 30% 수익보장 투자플랫폼에 투자 후 출금 불가',
            reg_date: '2026-02-18',
            status: '사건전환',
            source_id: 'SRC-KICS-001'
        })
    """, "vt_petition-2")

    # ── L2 · Person ────────────────────────────────
    print("  [L2 Person]")
    # 총책
    run(cur, """
        CREATE (:vt_psn {
            psn_id: 'PSN-A001',
            name: '김총책',
            type: '피의자',
            birth_dt: '1987-04-12',
            gender: 'M',
            nationality: 'KOR',
            address: '서울 강남구 논현동',
            role: '조직총책'
        })
    """, "vt_psn-김총책")

    # 대포통장 모집책
    run(cur, """
        CREATE (:vt_psn {
            psn_id: 'PSN-A002',
            name: '박모집',
            type: '피의자',
            birth_dt: '1993-08-30',
            gender: 'M',
            nationality: 'KOR',
            address: '인천 남동구 구월동',
            role: '대포통장모집'
        })
    """, "vt_psn-박모집")

    # 해커 (서버 관리)
    run(cur, """
        CREATE (:vt_psn {
            psn_id: 'PSN-A003',
            name: '이해커',
            type: '피의자',
            birth_dt: '1995-01-17',
            gender: 'M',
            nationality: 'KOR',
            address: '경기 성남시 분당구',
            role: '서버관리·피싱사이트운영'
        })
    """, "vt_psn-이해커")

    # 투자사기 담당
    run(cur, """
        CREATE (:vt_psn {
            psn_id: 'PSN-A004',
            name: '정사기',
            type: '피의자',
            birth_dt: '1990-11-05',
            gender: 'F',
            nationality: 'KOR',
            address: '부산 해운대구 우동',
            role: '투자사기담당'
        })
    """, "vt_psn-정사기")

    # 피해자
    run(cur, """
        CREATE (:vt_psn {
            psn_id: 'PSN-V001',
            name: '최피해자',
            type: '피해자',
            birth_dt: '1998-07-22',
            gender: 'M',
            damage_amt: '5500000',
            memo: '몸캠피싱 피해자'
        })
    """, "vt_psn-최피해자")

    run(cur, """
        CREATE (:vt_psn {
            psn_id: 'PSN-V002',
            name: '박투자',
            type: '피해자',
            birth_dt: '1975-03-14',
            gender: 'F',
            damage_amt: '24000000',
            memo: '투자사기 피해자'
        })
    """, "vt_psn-박투자")

    # ── L2 · Organization ──────────────────────────
    print("  [L2 Organization]")
    run(cur, """
        CREATE (:vt_org {
            org_id: 'ORG-001',
            org_name: '텔레그램범죄조직A',
            org_type: 'CRIMINAL',
            desc: '몸캠피싱·투자사기 복합 범죄조직',
            established: '2025-06-01'
        })
    """, "vt_org-범죄조직")

    run(cur, """
        CREATE (:vt_org {
            org_id: 'ORG-002',
            org_name: '스마트인베스트(주)',
            org_type: 'FAKE_COMPANY',
            biz_no: '999-88-77777',
            desc: '투자사기 위장 페이퍼컴퍼니'
        })
    """, "vt_org-위장회사")

    run(cur, """
        CREATE (:vt_org {
            org_id: 'ORG-003',
            org_name: '한국투자증권',
            org_type: 'FINANCE',
            desc: '사칭 대상 정상 금융기관'
        })
    """, "vt_org-한국투자증권")

    # ── L3 · Object — 계좌 ─────────────────────────
    print("  [L3 BankAccount]")
    run(cur, """
        CREATE (:vt_bacnt {
            bacnt_id: 'ACC-001',
            account_no: '110-2345-6789-01',
            bank_name: '카카오뱅크',
            holder: '황대포',
            type: '대포통장',
            balance: '0',
            opened_dt: '2025-12-01'
        })
    """, "vt_bacnt-001")

    run(cur, """
        CREATE (:vt_bacnt {
            bacnt_id: 'ACC-002',
            account_no: '352-0987-6543-21',
            bank_name: '농협',
            holder: '임대포',
            type: '대포통장',
            balance: '0',
            opened_dt: '2026-01-05'
        })
    """, "vt_bacnt-002")

    run(cur, """
        CREATE (:vt_bacnt {
            bacnt_id: 'ACC-003',
            account_no: '088-1234-5678',
            bank_name: '신한은행',
            holder: '최피해자',
            type: '피해자계좌',
            balance: '2300000'
        })
    """, "vt_bacnt-003")

    run(cur, """
        CREATE (:vt_bacnt {
            bacnt_id: 'ACC-004',
            account_no: '301-0192-8374-55',
            bank_name: 'KB국민은행',
            holder: '박투자',
            type: '피해자계좌',
            balance: '980000'
        })
    """, "vt_bacnt-004")

    # ── L3 · Object — 전화번호 ─────────────────────
    print("  [L3 Phone]")
    run(cur, """
        CREATE (:vt_telno {
            telno_id: 'TEL-A01',
            telno: '070-1234-5678',
            type: '발신번호',
            carrier: '070 인터넷전화',
            memo: '총책 사용 협박 번호'
        })
    """, "vt_telno-A01")

    run(cur, """
        CREATE (:vt_telno {
            telno_id: 'TEL-A02',
            telno: '010-9876-5432',
            type: '발신번호',
            carrier: 'SKT',
            memo: '투자사기 유인 번호'
        })
    """, "vt_telno-A02")

    run(cur, """
        CREATE (:vt_telno {
            telno_id: 'TEL-V01',
            telno: '010-3344-1122',
            type: '수신번호',
            carrier: 'KT',
            memo: '몸캠 피해자 번호'
        })
    """, "vt_telno-V01")

    run(cur, """
        CREATE (:vt_telno {
            telno_id: 'TEL-V02',
            telno: '010-5566-7788',
            type: '수신번호',
            carrier: 'LGU+',
            memo: '투자사기 피해자 번호'
        })
    """, "vt_telno-V02")

    # ── L3 · Object — IP ───────────────────────────
    print("  [L3 IP]")
    run(cur, """
        CREATE (:vt_ip {
            ip_id: 'IP-001',
            ip_addr: '185.220.101.45',
            country: 'NL',
            isp: 'Tor Exit Node',
            threat_score: 95,
            type: 'SERVER',
            memo: '피싱사이트 호스팅 서버 IP (해외)'
        })
    """, "vt_ip-001")

    run(cur, """
        CREATE (:vt_ip {
            ip_id: 'IP-002',
            ip_addr: '45.33.105.220',
            country: 'US',
            isp: 'Linode',
            threat_score: 88,
            type: 'SERVER',
            memo: '투자사기 플랫폼 서버 IP'
        })
    """, "vt_ip-002")

    run(cur, """
        CREATE (:vt_ip {
            ip_id: 'IP-003',
            ip_addr: '121.53.24.107',
            country: 'KR',
            isp: 'KT',
            threat_score: 30,
            type: 'CLIENT',
            memo: '총책 접속 IP (국내 VPN)'
        })
    """, "vt_ip-003")

    # ── L3 · Object — Site ─────────────────────────
    print("  [L3 Site]")
    run(cur, """
        CREATE (:vt_site {
            site_id: 'SITE-001',
            url: 'https://moccam-share.xyz/upload',
            domain: 'moccam-share.xyz',
            type: '피싱사이트',
            purpose: '몸캠영상 유포 협박 플랫폼',
            status: '활성',
            detected_dt: '2026-02-12'
        })
    """, "vt_site-001")

    run(cur, """
        CREATE (:vt_site {
            site_id: 'SITE-002',
            url: 'https://t.me/smartinvest_profit',
            domain: 't.me',
            type: '텔레그램채널',
            purpose: '투자사기 유인 채널 (구독자 8200명)',
            status: '활성',
            detected_dt: '2026-02-15'
        })
    """, "vt_site-002")

    run(cur, """
        CREATE (:vt_site {
            site_id: 'SITE-003',
            url: 'https://smart-invest-kr.com',
            domain: 'smart-invest-kr.com',
            type: '투자사기사이트',
            purpose: '가짜 투자플랫폼 — 한국투자증권 사칭',
            status: '폐쇄',
            detected_dt: '2026-02-22'
        })
    """, "vt_site-003")

    # ── L3 · Object — File ─────────────────────────
    print("  [L3 File]")
    run(cur, """
        CREATE (:vt_file {
            file_id: 'FILE-001',
            filename: 'victim_20260208.mp4',
            filetype: 'video/mp4',
            filesize: '84MB',
            sha256: 'a3f8c2d1e4b7f9a0c2e5d8b1f4a7c0e3',
            purpose: '협박용 몸캠 영상',
            memo: '피해자 최피해자 녹화 영상'
        })
    """, "vt_file-001")

    run(cur, """
        CREATE (:vt_file {
            file_id: 'FILE-002',
            filename: 'invest_guide.apk',
            filetype: 'application/apk',
            filesize: '12MB',
            sha256: 'b5e2a9c4d7f0b3e6a9c2d5f8b1e4a7d0',
            purpose: '악성 투자앱 (RAT 포함)',
            memo: '설치 시 금융정보 탈취'
        })
    """, "vt_file-002")

    # ── L3 · Object — DigitalID ────────────────────
    print("  [L3 DigitalID]")
    run(cur, """
        CREATE (:vt_id {
            id_id: 'ID-001',
            platform: 'Telegram',
            username: '@moccam_handler01',
            type: '협박계정',
            memo: '총책 직접 사용 텔레그램 계정'
        })
    """, "vt_id-001")

    run(cur, """
        CREATE (:vt_id {
            id_id: 'ID-002',
            platform: 'Telegram',
            username: '@invest_advisor99',
            type: '사기계정',
            memo: '투자사기 유인 텔레그램 계정 (정사기 사용)'
        })
    """, "vt_id-002")

    run(cur, """
        CREATE (:vt_id {
            id_id: 'ID-003',
            platform: 'Instagram',
            username: 'smartinvest_official',
            type: '사기계정',
            memo: '투자사기 홍보 인스타 계정'
        })
    """, "vt_id-003")

    # ── L3 · Object — Email ────────────────────────
    print("  [L3 Email]")
    run(cur, """
        CREATE (:vt_email {
            email_id: 'EMAIL-001',
            address: 'blackmail@protonmail.com',
            provider: 'ProtonMail',
            type: '협박이메일',
            memo: '피해자에게 협박 이메일 발송'
        })
    """, "vt_email-001")

    run(cur, """
        CREATE (:vt_email {
            email_id: 'EMAIL-002',
            address: 'invest.support@smart-invest-kr.com',
            provider: 'FAKE',
            type: '사기이메일',
            memo: '투자사기 고객지원 위장 이메일'
        })
    """, "vt_email-002")

    # ── L3 · Object — Crypto ───────────────────────
    print("  [L3 Crypto]")
    run(cur, """
        CREATE (:vt_crypto {
            crypto_id: 'CRYPTO-001',
            wallet_addr: 'bc1q9xy8w5z3k2m4j7h6g1f0e9d8c7b6a5',
            currency: 'BTC',
            balance: '0.847',
            total_received: '2.34',
            memo: '범죄수익 세탁용 비트코인 지갑'
        })
    """, "vt_crypto-001")

    # ── L3 · Object — Device ───────────────────────
    print("  [L3 Device]")
    run(cur, """
        CREATE (:vt_dev {
            dev_id: 'DEV-001',
            device_type: 'Smartphone',
            model: 'iPhone 15 Pro',
            imei: '352456789012345',
            mac_addr: 'A4:B0:C3:D2:E1:F0',
            os: 'iOS 17.3',
            memo: '총책 사용 기기'
        })
    """, "vt_dev-001")

    run(cur, """
        CREATE (:vt_dev {
            dev_id: 'DEV-002',
            device_type: 'Laptop',
            model: 'MacBook Pro 14',
            imei: '',
            mac_addr: 'B5:C1:D4:E3:F2:A0',
            os: 'macOS 14.3',
            memo: '해커 이해커 사용 서버관리 노트북'
        })
    """, "vt_dev-002")

    # ── L3 · Object — ATM ──────────────────────────
    print("  [L3 ATM]")
    run(cur, """
        CREATE (:vt_atm {
            atm_id: 'ATM-001',
            bank_name: '카카오뱅크',
            atm_no: 'KAK-2026-0412',
            addr: '서울 강남구 역삼동 123-4',
            installed_dt: '2024-03-15'
        })
    """, "vt_atm-001")

    run(cur, """
        CREATE (:vt_atm {
            atm_id: 'ATM-002',
            bank_name: '농협',
            atm_no: 'NH-2026-0891',
            addr: '인천 남동구 구월동 45-7',
            installed_dt: '2023-11-20'
        })
    """, "vt_atm-002")

    # ── L3 · Object — Vehicle ──────────────────────
    print("  [L3 Vehicle]")
    run(cur, """
        CREATE (:vt_vhcl {
            vhcl_id: 'VHC-001',
            vhcl_no: '서울 12가 3456',
            model: 'Hyundai Sonata',
            color: 'Black',
            year: '2023',
            owner: 'PSN-A001',
            memo: '총책 차량 — ATM 출금 현장 CCTV 포착'
        })
    """, "vt_vhcl-001")

    # ── L4 · Location ──────────────────────────────
    print("  [L4 Location]")
    run(cur, """
        CREATE (:vt_loc {
            loc_id: 'LOC-001',
            addr: '서울 강남구 역삼동 123-4',
            lat: '37.4993',
            lon: '127.0285',
            type: 'ATM현장',
            memo: '카카오뱅크 ATM — 대포통장 출금 현장'
        })
    """, "vt_loc-001")

    run(cur, """
        CREATE (:vt_loc {
            loc_id: 'LOC-002',
            addr: '인천 남동구 구월동 45-7',
            lat: '37.4478',
            lon: '126.7311',
            type: 'ATM현장',
            memo: '농협 ATM — 2차 세탁 출금 현장'
        })
    """, "vt_loc-002")

    run(cur, """
        CREATE (:vt_loc {
            loc_id: 'LOC-003',
            addr: '경기 성남시 분당구 정자동',
            lat: '37.3595',
            lon: '127.1088',
            type: '거주지',
            memo: '이해커 거주지 / 서버 원격관리 장소'
        })
    """, "vt_loc-003")

    # ── L5 · Events ────────────────────────────────
    print("  [L5 Events]")

    # 이체
    run(cur, """
        CREATE (:vt_transfer {
            tf_id: 'TRF-001',
            amount: '5500000',
            currency: 'KRW',
            tf_dt: '2026-02-09 14:22:00',
            memo: '협박금 송금 (최피해자→ACC-001)',
            method: '인터넷뱅킹'
        })
    """, "vt_transfer-001")

    run(cur, """
        CREATE (:vt_transfer {
            tf_id: 'TRF-002',
            amount: '5000000',
            currency: 'KRW',
            tf_dt: '2026-02-09 15:10:00',
            memo: '1차 세탁 (ACC-001→ACC-002)',
            method: '자동이체'
        })
    """, "vt_transfer-002")

    run(cur, """
        CREATE (:vt_transfer {
            tf_id: 'TRF-003',
            amount: '12000000',
            currency: 'KRW',
            tf_dt: '2026-02-21 11:30:00',
            memo: '투자금 송금 1차 (박투자→ACC-002)',
            method: '인터넷뱅킹'
        })
    """, "vt_transfer-003")

    run(cur, """
        CREATE (:vt_transfer {
            tf_id: 'TRF-004',
            amount: '12000000',
            currency: 'KRW',
            tf_dt: '2026-02-22 09:45:00',
            memo: '투자금 송금 2차',
            method: '인터넷뱅킹'
        })
    """, "vt_transfer-004")

    run(cur, """
        CREATE (:vt_transfer {
            tf_id: 'TRF-005',
            amount: '0.847',
            currency: 'BTC',
            tf_dt: '2026-02-23 03:17:00',
            memo: '비트코인 환전 세탁',
            method: 'P2P거래소'
        })
    """, "vt_transfer-005")

    # 통화
    run(cur, """
        CREATE (:vt_call {
            call_id: 'CALL-001',
            call_dt: '2026-02-08 20:14:00',
            duration: '1847',
            call_type: '영상통화',
            memo: '몸캠 피싱 초기 유인 통화'
        })
    """, "vt_call-001")

    run(cur, """
        CREATE (:vt_call {
            call_id: 'CALL-002',
            call_dt: '2026-02-09 13:50:00',
            duration: '382',
            call_type: '음성통화',
            memo: '협박 전화 — 입금 독촉'
        })
    """, "vt_call-002")

    run(cur, """
        CREATE (:vt_call {
            call_id: 'CALL-003',
            call_dt: '2026-02-19 16:30:00',
            duration: '2730',
            call_type: '음성통화',
            memo: '투자사기 유인 상담 전화'
        })
    """, "vt_call-003")

    # 접속 로그
    run(cur, """
        CREATE (:vt_access {
            access_id: 'ACC-LOG-001',
            access_dt: '2026-02-12 02:33:00',
            method: 'HTTPS',
            result: 'SUCCESS',
            memo: '이해커의 피싱서버 관리 접속'
        })
    """, "vt_access-001")

    run(cur, """
        CREATE (:vt_access {
            access_id: 'ACC-LOG-002',
            access_dt: '2026-02-22 04:11:00',
            method: 'SSH',
            result: 'SUCCESS',
            memo: '총책의 투자사기 서버 원격 접속'
        })
    """, "vt_access-002")

    # 메시지
    run(cur, """
        CREATE (:vt_msg {
            msg_id: 'MSG-001',
            content: '영상 유포하기 싫으면 지금 바로 500만원 입금해',
            platform: 'Telegram',
            sent_dt: '2026-02-09 13:30:00',
            type: '협박메시지'
        })
    """, "vt_msg-001")

    run(cur, """
        CREATE (:vt_msg {
            msg_id: 'MSG-002',
            content: '지금 가입하면 월 30% 확정 수익! 오늘만 특별 혜택',
            platform: 'Telegram',
            sent_dt: '2026-02-18 10:00:00',
            type: '투자사기유인'
        })
    """, "vt_msg-002")

    run(cur, """
        CREATE (:vt_msg {
            msg_id: 'MSG-003',
            content: '[계좌번호: 352-0987-6543-21] 농협 임대포 / 투자원금 송금요',
            platform: 'KakaoTalk',
            sent_dt: '2026-02-20 14:22:00',
            type: '계좌유도메시지'
        })
    """, "vt_msg-003")

    # 이동
    run(cur, """
        CREATE (:vt_movement {
            mov_id: 'MOV-001',
            mov_dt: '2026-02-09 15:30:00',
            loc_from: '서울 강남구',
            loc_to: '서울 강남구 역삼동 ATM',
            method: '차량',
            memo: '총책 ATM 출금 이동'
        })
    """, "vt_movement-001")

    run(cur, """
        CREATE (:vt_movement {
            mov_id: 'MOV-002',
            mov_dt: '2026-02-23 10:15:00',
            loc_from: '인천 남동구',
            loc_to: '인천 남동구 구월동 ATM',
            method: '도보',
            memo: '박모집 2차 세탁 ATM 출금 이동'
        })
    """, "vt_movement-002")

    # 사칭 이벤트
    run(cur, """
        CREATE (:vt_impersonation {
            imp_id: 'IMP-001',
            method: 'FAKE_WEBSITE',
            target_org: '한국투자증권',
            detected_dt: '2026-02-22',
            desc: '투자증권사 위장 사이트로 투자자 유인'
        })
    """, "vt_impersonation-001")

    print("\n✅ 노드 삽입 완료\n")

    # ══════════════════════════════════════════════
    # 3. 엣지 삽입
    # ══════════════════════════════════════════════
    print("🔗 엣지 삽입 중...\n")

    # ── Cat.1 — 사건 연결 ──────────────────────────
    print("  [Cat.1 사건 연결]")
    # 피의자 → 사건
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (c:vt_case {flnm:'CASE-MC-001'}) MERGE (p)-[:suspect_in {verified:true, source_id:'SRC-KICS-001'}]->(c)", "suspect_in-A001-MC")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (c:vt_case {flnm:'CASE-MC-001'}) MERGE (p)-[:suspect_in {verified:true, source_id:'SRC-KICS-001'}]->(c)", "suspect_in-A002-MC")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A003'}), (c:vt_case {flnm:'CASE-MC-001'}) MERGE (p)-[:suspect_in {verified:false, source_id:'SRC-KICS-001'}]->(c)", "suspect_in-A003-MC")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (c:vt_case {flnm:'CASE-IS-001'}) MERGE (p)-[:suspect_in {verified:true, source_id:'SRC-KICS-001'}]->(c)", "suspect_in-A001-IS")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A004'}), (c:vt_case {flnm:'CASE-IS-001'}) MERGE (p)-[:suspect_in {verified:true, source_id:'SRC-KICS-001'}]->(c)", "suspect_in-A004-IS")
    # 피해자 → 사건
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-V001'}), (c:vt_case {flnm:'CASE-MC-001'}) MERGE (p)-[:victim_in {damage_amt:'5500000', source_id:'SRC-KICS-001'}]->(c)", "victim_in-V001")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-V002'}), (c:vt_case {flnm:'CASE-IS-001'}) MERGE (p)-[:victim_in {damage_amt:'24000000', source_id:'SRC-KICS-001'}]->(c)", "victim_in-V002")
    # 진정서 → 사건
    run(cur, "MATCH (pt:vt_petition {pettn_id:'PTN-2026-011'}), (c:vt_case {flnm:'CASE-MC-001'}) MERGE (pt)-[:filed_as {converted_dt:'2026-02-10'}]->(c)", "filed_as-1")
    run(cur, "MATCH (pt:vt_petition {pettn_id:'PTN-2026-012'}), (c:vt_case {flnm:'CASE-IS-001'}) MERGE (pt)-[:filed_as {converted_dt:'2026-02-20'}]->(c)", "filed_as-2")
    # 사건 연계
    run(cur, "MATCH (c1:vt_case {flnm:'CASE-MC-001'}), (c2:vt_case {flnm:'CASE-IS-001'}) MERGE (c1)-[:related_case {reason:'동일조직 PSN-A001 공유', confidence:0.95}]->(c2)", "related_case")

    # ── Cat.2 — 신원/소유 ──────────────────────────
    print("  [Cat.2 신원/소유]")
    # 계좌 소유/지배
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (a:vt_bacnt {bacnt_id:'ACC-001'}) MERGE (p)-[:controls {method:'대포통장', verified:true}]->(a)", "controls-A001")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (a:vt_bacnt {bacnt_id:'ACC-002'}) MERGE (p)-[:has_account {type:'대포통장명의'}]->(a)", "has_account-A002")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-V001'}), (a:vt_bacnt {bacnt_id:'ACC-003'}) MERGE (p)-[:has_account {type:'피해자계좌'}]->(a)", "has_account-V001")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-V002'}), (a:vt_bacnt {bacnt_id:'ACC-004'}) MERGE (p)-[:has_account {type:'피해자계좌'}]->(a)", "has_account-V002")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (c:vt_crypto {crypto_id:'CRYPTO-001'}) MERGE (p)-[:owns {type:'비트코인지갑', verified:false}]->(c)", "owns-crypto")
    # 전화 소유
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (t:vt_telno {telno_id:'TEL-A01'}) MERGE (p)-[:owns_phone {verified:false}]->(t)", "owns_phone-A01")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A004'}), (t:vt_telno {telno_id:'TEL-A02'}) MERGE (p)-[:owns_phone {verified:true}]->(t)", "owns_phone-A02")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-V001'}), (t:vt_telno {telno_id:'TEL-V01'}) MERGE (p)-[:owns_phone {verified:true}]->(t)", "owns_phone-V01")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-V002'}), (t:vt_telno {telno_id:'TEL-V02'}) MERGE (p)-[:owns_phone {verified:true}]->(t)", "owns_phone-V02")
    # ID 사용
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (i:vt_id {id_id:'ID-001'}) MERGE (p)-[:uses_id {platform:'Telegram', verified:true}]->(i)", "uses_id-A001")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A004'}), (i:vt_id {id_id:'ID-002'}) MERGE (p)-[:uses_id {platform:'Telegram', verified:true}]->(i)", "uses_id-A004")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A004'}), (i:vt_id {id_id:'ID-003'}) MERGE (p)-[:uses_id {platform:'Instagram', verified:false}]->(i)", "uses_id-A004-ig")
    # 이메일
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (e:vt_email {email_id:'EMAIL-001'}) MERGE (p)-[:uses_email {verified:false}]->(e)", "uses_email-A001")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A004'}), (e:vt_email {email_id:'EMAIL-002'}) MERGE (p)-[:uses_email {verified:true}]->(e)", "uses_email-A004")
    # 기기 소유
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (d:vt_dev {dev_id:'DEV-001'}) MERGE (p)-[:owns_device {verified:true}]->(d)", "owns_device-A001")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A003'}), (d:vt_dev {dev_id:'DEV-002'}) MERGE (p)-[:owns_device {verified:true}]->(d)", "owns_device-A003")
    # IP 사용
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (i:vt_ip {ip_id:'IP-003'}) MERGE (p)-[:used_ip {method:'VPN', verified:false}]->(i)", "used_ip-A001")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A003'}), (i:vt_ip {ip_id:'IP-001'}) MERGE (p)-[:used_ip {method:'서버접속', verified:true}]->(i)", "used_ip-A003")
    # 차량 소유
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (v:vt_vhcl {vhcl_id:'VHC-001'}) MERGE (p)-[:owns_vehicle {verified:true}]->(v)", "owns_vehicle")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (v:vt_vhcl {vhcl_id:'VHC-001'}) MERGE (p)-[:drives {detected_dt:'2026-02-09'}]->(v)", "drives")
    # 조직 소속
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (o:vt_org {org_id:'ORG-001'}) MERGE (p)-[:member_of {role:'admin', verified:true}]->(o)", "member_of-A001")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (o:vt_org {org_id:'ORG-001'}) MERGE (p)-[:member_of {role:'member', verified:false}]->(o)", "member_of-A002")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A003'}), (o:vt_org {org_id:'ORG-001'}) MERGE (p)-[:member_of {role:'member', verified:false}]->(o)", "member_of-A003")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A004'}), (o:vt_org {org_id:'ORG-002'}) MERGE (p)-[:works_at {role:'대표', verified:true}]->(o)", "works_at-A004")
    # 계좌 소속 기관
    run(cur, "MATCH (a:vt_bacnt {bacnt_id:'ACC-003'}), (o:vt_org {org_id:'ORG-003'}) MERGE (a)-[:belongs_to]->(o)", "belongs_to-ACC003")

    # ── Cat.3 — 인물 관계 (v3.4 신규 포함) ───────────
    print("  [Cat.3 인물 관계 ★ recruits · blackmails]")
    run(cur, "MATCH (a:vt_psn {psn_id:'PSN-A001'}), (b:vt_psn {psn_id:'PSN-A002'}) MERGE (a)-[:recruits {recruit_type:'대포통장모집', date:'2025-11-15'}]->(b)", "recruits-A001-A002")
    run(cur, "MATCH (a:vt_psn {psn_id:'PSN-A001'}), (b:vt_psn {psn_id:'PSN-A003'}) MERGE (a)-[:recruits {recruit_type:'해커모집', date:'2025-12-01'}]->(b)", "recruits-A001-A003")
    run(cur, "MATCH (a:vt_psn {psn_id:'PSN-A001'}), (b:vt_psn {psn_id:'PSN-A004'}) MERGE (a)-[:recruits {recruit_type:'투자사기담당모집', date:'2026-01-10'}]->(b)", "recruits-A001-A004")
    run(cur, "MATCH (a:vt_psn {psn_id:'PSN-A001'}), (b:vt_psn {psn_id:'PSN-V001'}) MERGE (a)-[:blackmails {method:'몸캠영상유포협박', date:'2026-02-09'}]->(b)", "blackmails-A001-V001")
    run(cur, "MATCH (a:vt_psn {psn_id:'PSN-A002'}), (b:vt_psn {psn_id:'PSN-A003'}) MERGE (a)-[:accomplice_of]->(b)", "accomplice_of")

    # ── Cat.4 — 운영/인프라 (v3.4 신규) ──────────────
    print("  [Cat.4 운영/인프라 ★ operates · hosts · contains_file · located_at]")
    # operates
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A001'}), (s:vt_site {site_id:'SITE-002'}) MERGE (p)-[:operates {role:'채널관리자', valid_from:'2025-10-01'}]->(s)", "operates-A001-SITE002")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A003'}), (s:vt_site {site_id:'SITE-001'}) MERGE (p)-[:operates {role:'서버관리자', valid_from:'2026-01-15'}]->(s)", "operates-A003-SITE001")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A004'}), (s:vt_site {site_id:'SITE-003'}) MERGE (p)-[:operates {role:'사이트관리자', valid_from:'2026-02-01'}]->(s)", "operates-A004-SITE003")
    run(cur, "MATCH (o:vt_org {org_id:'ORG-001'}), (i:vt_id {id_id:'ID-001'}) MERGE (o)-[:operates {role:'조직계정'}]->(i)", "operates-ORG-ID001")
    # hosts
    run(cur, "MATCH (i:vt_ip {ip_id:'IP-001'}), (s:vt_site {site_id:'SITE-001'}) MERGE (i)-[:hosts {port:443, detected_dt:'2026-02-12'}]->(s)", "hosts-IP001-SITE001")
    run(cur, "MATCH (i:vt_ip {ip_id:'IP-002'}), (s:vt_site {site_id:'SITE-003'}) MERGE (i)-[:hosts {port:443, detected_dt:'2026-02-22'}]->(s)", "hosts-IP002-SITE003")
    # resolves_to
    run(cur, "MATCH (s:vt_site {site_id:'SITE-001'}), (i:vt_ip {ip_id:'IP-001'}) MERGE (s)-[:resolves_to {record_type:'A', ttl:300}]->(i)", "resolves_to-SITE001")
    run(cur, "MATCH (s:vt_site {site_id:'SITE-003'}), (i:vt_ip {ip_id:'IP-002'}) MERGE (s)-[:resolves_to {record_type:'A', ttl:300}]->(i)", "resolves_to-SITE003")
    # contains_file
    run(cur, "MATCH (s:vt_site {site_id:'SITE-001'}), (f:vt_file {file_id:'FILE-001'}) MERGE (s)-[:contains_file {file_role:'협박영상', detected_dt:'2026-02-12'}]->(f)", "contains_file-SITE001-FILE001")
    run(cur, "MATCH (s:vt_site {site_id:'SITE-003'}), (f:vt_file {file_id:'FILE-002'}) MERGE (s)-[:contains_file {file_role:'악성APK배포', detected_dt:'2026-02-22'}]->(f)", "contains_file-SITE003-FILE002")
    run(cur, "MATCH (m:vt_msg {msg_id:'MSG-001'}), (f:vt_file {file_id:'FILE-001'}) MERGE (m)-[:contains_file {file_role:'협박증거첨부'}]->(f)", "contains_file-MSG001-FILE001")
    # located_at
    run(cur, "MATCH (a:vt_atm {atm_id:'ATM-001'}), (l:vt_loc {loc_id:'LOC-001'}) MERGE (a)-[:located_at {verified:true}]->(l)", "located_at-ATM001")
    run(cur, "MATCH (a:vt_atm {atm_id:'ATM-002'}), (l:vt_loc {loc_id:'LOC-002'}) MERGE (a)-[:located_at {verified:true}]->(l)", "located_at-ATM002")
    run(cur, "MATCH (d:vt_dev {dev_id:'DEV-002'}), (l:vt_loc {loc_id:'LOC-003'}) MERGE (d)-[:located_at {verified:false}]->(l)", "located_at-DEV002")

    # ── Cat.5 — 자금 흐름 ──────────────────────────
    print("  [Cat.5 자금 흐름]")
    run(cur, "MATCH (a:vt_bacnt {bacnt_id:'ACC-003'}), (t:vt_transfer {tf_id:'TRF-001'}) MERGE (a)-[:from_account]->(t)", "from_account-001")
    run(cur, "MATCH (t:vt_transfer {tf_id:'TRF-001'}), (a:vt_bacnt {bacnt_id:'ACC-001'}) MERGE (t)-[:to_account]->(a)", "to_account-001")
    run(cur, "MATCH (a:vt_bacnt {bacnt_id:'ACC-001'}), (t:vt_transfer {tf_id:'TRF-002'}) MERGE (a)-[:from_account]->(t)", "from_account-002")
    run(cur, "MATCH (t:vt_transfer {tf_id:'TRF-002'}), (a:vt_bacnt {bacnt_id:'ACC-002'}) MERGE (t)-[:to_account]->(a)", "to_account-002")
    run(cur, "MATCH (a:vt_bacnt {bacnt_id:'ACC-004'}), (t:vt_transfer {tf_id:'TRF-003'}) MERGE (a)-[:from_account]->(t)", "from_account-003")
    run(cur, "MATCH (t:vt_transfer {tf_id:'TRF-003'}), (a:vt_bacnt {bacnt_id:'ACC-002'}) MERGE (t)-[:to_account]->(a)", "to_account-003")
    run(cur, "MATCH (a:vt_bacnt {bacnt_id:'ACC-001'}), (b:vt_bacnt {bacnt_id:'ACC-002'}) MERGE (a)-[:transferred_to {hop_level:1, inferred:true}]->(b)", "transferred_to")

    # ── Cat.6 — 사칭 패턴 ──────────────────────────
    print("  [Cat.6 사칭 패턴]")
    run(cur, "MATCH (s:vt_site {site_id:'SITE-003'}), (imp:vt_impersonation {imp_id:'IMP-001'}) MERGE (s)-[:used_for {method:'FAKE_WEBSITE'}]->(imp)", "used_for-SITE003")
    run(cur, "MATCH (imp:vt_impersonation {imp_id:'IMP-001'}), (o:vt_org {org_id:'ORG-003'}) MERGE (imp)-[:targets]->(o)", "targets-ORG003")

    # ── Cat.7 — 통신 ───────────────────────────────
    print("  [Cat.7 통신]")
    run(cur, "MATCH (t:vt_telno {telno_id:'TEL-A01'}), (c:vt_call {call_id:'CALL-001'}) MERGE (t)-[:caller]->(c)", "caller-001")
    run(cur, "MATCH (c:vt_call {call_id:'CALL-001'}), (t:vt_telno {telno_id:'TEL-V01'}) MERGE (c)-[:callee]->(t)", "callee-001")
    run(cur, "MATCH (t:vt_telno {telno_id:'TEL-A01'}), (c:vt_call {call_id:'CALL-002'}) MERGE (t)-[:caller]->(c)", "caller-002")
    run(cur, "MATCH (c:vt_call {call_id:'CALL-002'}), (t:vt_telno {telno_id:'TEL-V01'}) MERGE (c)-[:callee]->(t)", "callee-002")
    run(cur, "MATCH (t:vt_telno {telno_id:'TEL-A02'}), (c:vt_call {call_id:'CALL-003'}) MERGE (t)-[:caller]->(c)", "caller-003")
    run(cur, "MATCH (c:vt_call {call_id:'CALL-003'}), (t:vt_telno {telno_id:'TEL-V02'}) MERGE (c)-[:callee]->(t)", "callee-003")
    run(cur, "MATCH (i:vt_id {id_id:'ID-001'}), (m:vt_msg {msg_id:'MSG-001'}) MERGE (i)-[:sent_msg {platform:'Telegram'}]->(m)", "sent_msg-001")
    run(cur, "MATCH (m:vt_msg {msg_id:'MSG-001'}), (t:vt_telno {telno_id:'TEL-V01'}) MERGE (m)-[:received_msg]->(t)", "received_msg-001")
    run(cur, "MATCH (i:vt_id {id_id:'ID-002'}), (m:vt_msg {msg_id:'MSG-002'}) MERGE (i)-[:sent_msg {platform:'Telegram'}]->(m)", "sent_msg-002")
    run(cur, "MATCH (i:vt_id {id_id:'ID-002'}), (m:vt_msg {msg_id:'MSG-003'}) MERGE (i)-[:sent_msg {platform:'KakaoTalk'}]->(m)", "sent_msg-003")
    run(cur, "MATCH (m:vt_msg {msg_id:'MSG-003'}), (a:vt_bacnt {bacnt_id:'ACC-002'}) MERGE (m)-[:mentions_account]->(a)", "mentions_account")

    # ── Cat.8 — 디지털 접속 ────────────────────────
    print("  [Cat.8 디지털 접속]")
    run(cur, "MATCH (a:vt_access {access_id:'ACC-LOG-001'}), (i:vt_ip {ip_id:'IP-001'}) MERGE (a)-[:accessed_from]->(i)", "accessed_from-001")
    run(cur, "MATCH (a:vt_access {access_id:'ACC-LOG-002'}), (i:vt_ip {ip_id:'IP-003'}) MERGE (a)-[:accessed_from]->(i)", "accessed_from-002")
    run(cur, "MATCH (d:vt_dev {dev_id:'DEV-001'}), (i:vt_ip {ip_id:'IP-003'}) MERGE (d)-[:used_ip {method:'VPN'}]->(i)", "used_ip-DEV001")

    # ── Cat.9 — 위치/이동 ──────────────────────────
    print("  [Cat.9 위치/이동]")
    run(cur, "MATCH (v:vt_vhcl {vhcl_id:'VHC-001'}), (m:vt_movement {mov_id:'MOV-001'}) MERGE (v)-[:recorded_in]->(m)", "recorded_in-VHC001")
    run(cur, "MATCH (t:vt_telno {telno_id:'TEL-A01'}), (m:vt_movement {mov_id:'MOV-001'}) MERGE (t)-[:recorded_in {method:'기지국'}]->(m)", "recorded_in-TEL-A01")
    run(cur, "MATCH (p:vt_psn {psn_id:'PSN-A002'}), (m:vt_movement {mov_id:'MOV-002'}) MERGE (p)-[:recorded_in {method:'CCTV'}]->(m)", "recorded_in-PSN-A002")
    run(cur, "MATCH (m:vt_movement {mov_id:'MOV-001'}), (l:vt_loc {loc_id:'LOC-001'}) MERGE (m)-[:occurred_at]->(l)", "occurred_at-MOV001")
    run(cur, "MATCH (m:vt_movement {mov_id:'MOV-002'}), (l:vt_loc {loc_id:'LOC-002'}) MERGE (m)-[:occurred_at]->(l)", "occurred_at-MOV002")

    # ── Cat.10 — 출처 ──────────────────────────────
    print("  [Cat.10 출처]")
    run(cur, "MATCH (c:vt_case {flnm:'CASE-MC-001'}), (s:vt_src {src_id:'SRC-KICS-001'}) MERGE (c)-[:sourced_from]->(s)", "sourced_from-MC")
    run(cur, "MATCH (c:vt_case {flnm:'CASE-IS-001'}), (s:vt_src {src_id:'SRC-KICS-001'}) MERGE (c)-[:sourced_from]->(s)", "sourced_from-IS")

    print("\n✅ 엣지 삽입 완료\n")

    # ── 최종 통계 ───────────────────────────────────
    cur.execute(f"""
        SELECT (SELECT count(*) FROM {GRAPH}.ag_vertex) AS nodes,
               (SELECT count(*) FROM {GRAPH}.ag_edge) AS edges
    """)
    r = cur.fetchone()
    print("=" * 55)
    print(f"📊 그래프 생성 완료: '{GRAPH}'")
    print(f"   노드: {r[0]}개  |  엣지: {r[1]}개")
    print("=" * 55)
    print("\n★ v3.4 신규 엣지 커버:")
    print("   operates    ✅  (총책·해커·사기담당 → 사이트/채널 운영)")
    print("   recruits    ✅  (총책 → 대포통장모집·해커·사기담당 모집)")
    print("   blackmails  ✅  (총책 → 피해자 협박)")
    print("   hosts       ✅  (서버IP → 피싱사이트/투자사기사이트)")
    print("   contains_file ✅  (사이트/메시지 → 협박영상/악성APK)")
    print("   located_at  ✅  (ATM×2/기기 → 위치)")
    print()

    conn.close()


if __name__ == '__main__':
    main()
