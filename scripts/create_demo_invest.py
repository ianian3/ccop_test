"""
CCOP v3.4 데모 — 시나리오 2: 수익보장형 가상투자 사기 사건
==============================================================
그래프명: ccop_demo_invest

[사건 개요]
텔레그램·인스타그램에서 "월 30% 확정 수익" 광고로 투자자를 유인,
정상 증권사를 사칭한 가짜 투자플랫폼(앱·사이트)에 투자금을 입금시킨 뒤
출금 불가 후 잠적. 악성 APK 배포로 금융정보 추가 탈취.

[등장인물]
- 오총괄(PSN-A001): 조직 총괄, 가짜 회사 대표
- 나영업(PSN-A002): 투자 유인 영업 담당
- 최기술(PSN-A003): 플랫폼 개발·서버 운영
- 한피해(PSN-V001): 피해자 1 (2400만 원)
- 유피해(PSN-V002): 피해자 2 (1800만 원)
- 강피해(PSN-V003): 피해자 3 (900만 원)

[v3.4 신규 엣지 커버]
★ operates   : 오총괄/최기술 → 투자사이트/텔레그램채널
★ recruits   : 오총괄 → 나영업, 최기술
★ hosts      : 서버IP → 투자사기사이트
★ contains_file: 사이트 → 악성APK
★ located_at : ATM → 출금 위치
"""
import psycopg2

DB    = dict(host='49.50.128.28', port=5333, dbname='tccopdb', user='ccop', password='Ccop@2025')
GRAPH = 'ccop_demo_invest'

def run(cur, cypher, label=''):
    try: cur.execute(cypher)
    except Exception as e: print(f'  ⚠ [{label}] {e}')

def main():
    conn = psycopg2.connect(**DB); conn.autocommit = True; cur = conn.cursor()

    print(f'🗑  {GRAPH} 초기화...')
    try: cur.execute(f'DROP GRAPH {GRAPH} CASCADE')
    except: pass
    cur.execute(f'CREATE GRAPH {GRAPH}')
    cur.execute(f'SET graph_path = {GRAPH}')

    for v in ['vt_src','vt_case','vt_petition','vt_psn','vt_org',
              'vt_bacnt','vt_telno','vt_ip','vt_site','vt_file',
              'vt_id','vt_email','vt_crypto','vt_dev','vt_atm','vt_loc',
              'vt_transfer','vt_call','vt_msg','vt_impersonation']:
        run(cur, f'CREATE VLABEL IF NOT EXISTS {v}', v)
    for e in ['sourced_from','suspect_in','victim_in','filed_as','related_case',
              'has_account','controls','owns_phone','uses_id','uses_email','used_ip',
              'member_of','works_at','accomplice_of','recruits','operates',
              'hosts','contains_file','located_at','resolves_to','used_for','targets',
              'from_account','to_account','transferred_to','owns',
              'caller','callee','sent_msg','received_msg','mentions_account','linked_to']:
        run(cur, f'CREATE ELABEL IF NOT EXISTS {e}', e)
    print('  ✅ 레이블 등록 완료\n')

    print('📌 노드 삽입...')

    run(cur, "CREATE (:vt_src {src_id:'SRC-001',src_name:'KICS 신고시스템',tier:1,rec_created:'2026-02-01'})", 'src')

    run(cur, """CREATE (:vt_case {
        flnm:'CASE-IS-2026', crime_name:'수익보장형 가상투자 사기 사건',
        crime_type:'INVEST_FRAUD', status:'수사중',
        reg_date:'2026-03-05', damage_amt:'51000000', victim_cnt:6
    })""", 'case')
    run(cur, "CREATE (:vt_petition {pettn_id:'PTN-IS-001',petitioner:'한피해',content:'스마트인베스트 앱 투자 후 2400만원 출금 불가',reg_date:'2026-03-01',status:'사건전환'})", 'ptn1')
    run(cur, "CREATE (:vt_petition {pettn_id:'PTN-IS-002',petitioner:'유피해',content:'텔레그램 투자 채널 가입 후 1800만원 사기',reg_date:'2026-03-03',status:'사건전환'})", 'ptn2')

    # Persons
    run(cur, "CREATE (:vt_psn {psn_id:'PSN-A001',name:'오총괄',type:'피의자',birth_dt:'1983-06-15',gender:'M',nationality:'KOR',address:'서울 강남구 청담동',role:'조직총괄·가짜회사대표'})", 'a1')
    run(cur, "CREATE (:vt_psn {psn_id:'PSN-A002',name:'나영업',type:'피의자',birth_dt:'1991-09-22',gender:'F',nationality:'KOR',address:'서울 마포구 상암동',role:'투자유인영업'})", 'a2')
    run(cur, "CREATE (:vt_psn {psn_id:'PSN-A003',name:'최기술',type:'피의자',birth_dt:'1996-02-07',gender:'M',nationality:'KOR',address:'경기 판교 테크노밸리',role:'플랫폼개발·서버운영'})", 'a3')
    run(cur, "CREATE (:vt_psn {psn_id:'PSN-V001',name:'한피해',type:'피해자',birth_dt:'1972-04-18',gender:'M',damage_amt:'24000000'})", 'v1')
    run(cur, "CREATE (:vt_psn {psn_id:'PSN-V002',name:'유피해',type:'피해자',birth_dt:'1980-11-30',gender:'F',damage_amt:'18000000'})", 'v2')
    run(cur, "CREATE (:vt_psn {psn_id:'PSN-V003',name:'강피해',type:'피해자',birth_dt:'1968-08-05',gender:'M',damage_amt:'9000000'})", 'v3')

    # Org
    run(cur, "CREATE (:vt_org {org_id:'ORG-001',org_name:'스마트인베스트(주)',org_type:'FAKE_COMPANY',biz_no:'999-88-12345',desc:'투자사기 위장 페이퍼컴퍼니'})", 'org1')
    run(cur, "CREATE (:vt_org {org_id:'ORG-002',org_name:'미래에셋증권',org_type:'FINANCE',desc:'사칭 대상 정상 금융기관'})", 'org2')

    # BankAccount
    run(cur, "CREATE (:vt_bacnt {bacnt_id:'ACC-001',account_no:'110-2001-3002-01',bank_name:'카카오뱅크',holder:'오총괄',type:'사기계좌'})", 'acc1')
    run(cur, "CREATE (:vt_bacnt {bacnt_id:'ACC-002',account_no:'352-4003-5004-02',bank_name:'농협',holder:'황대포',type:'대포통장'})", 'acc2')
    run(cur, "CREATE (:vt_bacnt {bacnt_id:'ACC-003',account_no:'301-6005-7006-03',bank_name:'국민',holder:'김대포',type:'대포통장'})", 'acc3')
    run(cur, "CREATE (:vt_bacnt {bacnt_id:'ACC-V01',account_no:'088-1001-2002',bank_name:'신한',holder:'한피해',type:'피해자계좌'})", 'acv1')
    run(cur, "CREATE (:vt_bacnt {bacnt_id:'ACC-V02',account_no:'020-3003-4004',bank_name:'우리',holder:'유피해',type:'피해자계좌'})", 'acv2')
    run(cur, "CREATE (:vt_bacnt {bacnt_id:'ACC-V03',account_no:'064-5005-6006',bank_name:'하나',holder:'강피해',type:'피해자계좌'})", 'acv3')

    # Phone
    run(cur, "CREATE (:vt_telno {telno_id:'TEL-A01',telno:'010-2200-1100',type:'발신',carrier:'KT',memo:'나영업 유인 번호'})", 'ta1')
    run(cur, "CREATE (:vt_telno {telno_id:'TEL-V01',telno:'010-3311-2244',type:'수신',carrier:'SKT',memo:'피해자1'})", 'tv1')
    run(cur, "CREATE (:vt_telno {telno_id:'TEL-V02',telno:'010-5522-3355',type:'수신',carrier:'KT',memo:'피해자2'})", 'tv2')
    run(cur, "CREATE (:vt_telno {telno_id:'TEL-V03',telno:'010-7744-5566',type:'수신',carrier:'LGU+',memo:'피해자3'})", 'tv3')

    # IP / Site / File
    run(cur, "CREATE (:vt_ip {ip_id:'IP-001',ip_addr:'45.33.105.220',country:'US',isp:'Linode',threat_score:90,memo:'투자사기 플랫폼 서버'})", 'ip1')
    run(cur, "CREATE (:vt_ip {ip_id:'IP-002',ip_addr:'103.152.220.88',country:'SG',isp:'AWS',threat_score:72,memo:'C2 서버 (앱 통신)'})", 'ip2')
    run(cur, "CREATE (:vt_ip {ip_id:'IP-003',ip_addr:'58.229.44.12',country:'KR',isp:'SK브로드밴드',threat_score:20,memo:'오총괄 접속 IP'})", 'ip3')
    run(cur, "CREATE (:vt_site {site_id:'SITE-001',url:'https://smart-invest-kr.com',domain:'smart-invest-kr.com',type:'투자사기사이트',purpose:'미래에셋 사칭 가짜 투자플랫폼',status:'폐쇄'})", 's1')
    run(cur, "CREATE (:vt_site {site_id:'SITE-002',url:'https://t.me/smartinvest_profit_kr',domain:'t.me',type:'텔레그램채널',purpose:'투자자 유인 채널 (구독 1만2천명)',status:'활성'})", 's2')
    run(cur, "CREATE (:vt_file {file_id:'FILE-001',filename:'SmartInvest_v3.2.apk',filetype:'application/apk',filesize:'18MB',sha256:'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6',purpose:'악성 투자앱 — 금융정보 탈취 RAT'})", 'f1')
    run(cur, "CREATE (:vt_file {file_id:'FILE-002',filename:'invest_contract.pdf',filetype:'application/pdf',filesize:'2MB',sha256:'b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7',purpose:'가짜 투자계약서 (피싱 문서)'})", 'f2')

    # DigitalID / Email / Crypto
    run(cur, "CREATE (:vt_id {id_id:'ID-001',platform:'Telegram',username:'@invest_profit_kr',type:'사기계정',memo:'나영업 운영 유인 계정'})", 'id1')
    run(cur, "CREATE (:vt_id {id_id:'ID-002',platform:'Instagram',username:'smartinvest_official_kr',type:'사기계정',memo:'홍보 인스타 계정'})", 'id2')
    run(cur, "CREATE (:vt_email {email_id:'EMAIL-001',address:'support@smart-invest-kr.com',provider:'FAKE',type:'사기이메일',memo:'고객지원 위장'})", 'em1')
    run(cur, "CREATE (:vt_crypto {crypto_id:'CRYPTO-001',wallet_addr:'bc1q8yz7w4z3k2m4j7h6g1f0e9d8c7b5',currency:'BTC',balance:'1.234',memo:'수익 세탁 비트코인 지갑'})", 'cr1')

    # Device / ATM / Loc
    run(cur, "CREATE (:vt_dev {dev_id:'DEV-001',device_type:'Laptop',model:'MacBook Pro',memo:'최기술 서버관리 기기'})", 'dv1')
    run(cur, "CREATE (:vt_atm {atm_id:'ATM-001',bank_name:'카카오뱅크',atm_no:'KAK-5501',addr:'서울 강남구 청담동 ATM'})", 'atm1')
    run(cur, "CREATE (:vt_loc {loc_id:'LOC-001',addr:'서울 강남구 청담동 22-1',lat:'37.5246',lon:'127.0516',type:'ATM현장'})", 'loc1')
    run(cur, "CREATE (:vt_loc {loc_id:'LOC-002',addr:'경기 성남시 분당구 정자동',lat:'37.3595',lon:'127.1088',type:'서버관리거점'})", 'loc2')

    # Events
    run(cur, "CREATE (:vt_transfer {tf_id:'TRF-001',amount:'24000000',currency:'KRW',tf_dt:'2026-02-25 11:10:00',memo:'피해자1 투자금 입금'})", 't1')
    run(cur, "CREATE (:vt_transfer {tf_id:'TRF-002',amount:'18000000',currency:'KRW',tf_dt:'2026-02-26 14:30:00',memo:'피해자2 투자금 입금'})", 't2')
    run(cur, "CREATE (:vt_transfer {tf_id:'TRF-003',amount:'9000000',currency:'KRW',tf_dt:'2026-02-28 09:45:00',memo:'피해자3 투자금 입금'})", 't3')
    run(cur, "CREATE (:vt_transfer {tf_id:'TRF-004',amount:'45000000',currency:'KRW',tf_dt:'2026-03-01 03:20:00',memo:'세탁 이체 (ACC-001→ACC-002)'})", 't4')
    run(cur, "CREATE (:vt_transfer {tf_id:'TRF-005',amount:'1.234',currency:'BTC',tf_dt:'2026-03-02 05:00:00',memo:'비트코인 환전 세탁'})", 't5')
    run(cur, "CREATE (:vt_call {call_id:'CALL-001',call_dt:'2026-02-20 15:00:00',duration:'3120',call_type:'음성통화',memo:'한피해 투자 권유 상담'})", 'c1')
    run(cur, "CREATE (:vt_call {call_id:'CALL-002',call_dt:'2026-02-23 16:30:00',duration:'1840',call_type:'음성통화',memo:'유피해 투자 권유 상담'})", 'c2')
    run(cur, "CREATE (:vt_msg {msg_id:'MSG-001',content:'[미래에셋증권 제휴] 월 30% 확정수익 특별 이벤트! 지금 가입하세요',platform:'Telegram',sent_dt:'2026-02-18 09:00:00',type:'사기유인'})", 'm1')
    run(cur, "CREATE (:vt_msg {msg_id:'MSG-002',content:'[계좌번호] 110-2001-3002-01 카카오뱅크 오총괄 / 투자원금 송금요청',platform:'KakaoTalk',sent_dt:'2026-02-25 10:30:00',type:'계좌유도'})", 'm2')
    run(cur, "CREATE (:vt_impersonation {imp_id:'IMP-001',method:'FAKE_WEBSITE',target_org:'미래에셋증권',detected_dt:'2026-03-04',desc:'미래에셋 로고·UI 그대로 복제한 가짜 투자 사이트'})", 'imp1')
    print('  ✅ 노드 완료\n')

    print('🔗 엣지 삽입...')

    # Cat.1 사건
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(c:vt_case{flnm:'CASE-IS-2026'}) MERGE (p)-[:suspect_in{verified:true}]->(c)", 'si1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(c:vt_case{flnm:'CASE-IS-2026'}) MERGE (p)-[:suspect_in{verified:true}]->(c)", 'si2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A003'}),(c:vt_case{flnm:'CASE-IS-2026'}) MERGE (p)-[:suspect_in{verified:false}]->(c)", 'si3')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V001'}),(c:vt_case{flnm:'CASE-IS-2026'}) MERGE (p)-[:victim_in{damage_amt:'24000000'}]->(c)", 'vi1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V002'}),(c:vt_case{flnm:'CASE-IS-2026'}) MERGE (p)-[:victim_in{damage_amt:'18000000'}]->(c)", 'vi2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V003'}),(c:vt_case{flnm:'CASE-IS-2026'}) MERGE (p)-[:victim_in{damage_amt:'9000000'}]->(c)", 'vi3')
    run(cur, "MATCH (pt:vt_petition{pettn_id:'PTN-IS-001'}),(c:vt_case{flnm:'CASE-IS-2026'}) MERGE (pt)-[:filed_as{converted_dt:'2026-03-05'}]->(c)", 'fa1')
    run(cur, "MATCH (pt:vt_petition{pettn_id:'PTN-IS-002'}),(c:vt_case{flnm:'CASE-IS-2026'}) MERGE (pt)-[:filed_as{converted_dt:'2026-03-05'}]->(c)", 'fa2')

    # Cat.2 소유
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(a:vt_bacnt{bacnt_id:'ACC-001'}) MERGE (p)-[:controls{method:'명의계좌',verified:true}]->(a)", 'ct1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(a:vt_bacnt{bacnt_id:'ACC-002'}) MERGE (p)-[:controls{method:'대포통장',verified:true}]->(a)", 'ct2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V001'}),(a:vt_bacnt{bacnt_id:'ACC-V01'}) MERGE (p)-[:has_account]->(a)", 'ha-v1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V002'}),(a:vt_bacnt{bacnt_id:'ACC-V02'}) MERGE (p)-[:has_account]->(a)", 'ha-v2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V003'}),(a:vt_bacnt{bacnt_id:'ACC-V03'}) MERGE (p)-[:has_account]->(a)", 'ha-v3')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(t:vt_telno{telno_id:'TEL-A01'}) MERGE (p)-[:owns_phone{verified:true}]->(t)", 'op-a1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V001'}),(t:vt_telno{telno_id:'TEL-V01'}) MERGE (p)-[:owns_phone]->(t)", 'op-v1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V002'}),(t:vt_telno{telno_id:'TEL-V02'}) MERGE (p)-[:owns_phone]->(t)", 'op-v2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V003'}),(t:vt_telno{telno_id:'TEL-V03'}) MERGE (p)-[:owns_phone]->(t)", 'op-v3')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(i:vt_id{id_id:'ID-001'}) MERGE (p)-[:uses_id{platform:'Telegram'}]->(i)", 'ui1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(i:vt_id{id_id:'ID-002'}) MERGE (p)-[:uses_id{platform:'Instagram'}]->(i)", 'ui2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(e:vt_email{email_id:'EMAIL-001'}) MERGE (p)-[:uses_email{verified:true}]->(e)", 'ue1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(c:vt_crypto{crypto_id:'CRYPTO-001'}) MERGE (p)-[:owns{type:'비트코인지갑'}]->(c)", 'ow1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A003'}),(d:vt_dev{dev_id:'DEV-001'}) MERGE (p)-[:owns_device]->(d)", 'od1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A003'}),(ip:vt_ip{ip_id:'IP-001'}) MERGE (p)-[:used_ip{method:'서버접속',verified:true}]->(ip)", 'ui-a3')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(ip:vt_ip{ip_id:'IP-003'}) MERGE (p)-[:used_ip{method:'VPN'}]->(ip)", 'ui-a1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(o:vt_org{org_id:'ORG-001'}) MERGE (p)-[:works_at{role:'대표이사',verified:true}]->(o)", 'wa1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(o:vt_org{org_id:'ORG-001'}) MERGE (p)-[:works_at{role:'영업이사'}]->(o)", 'wa2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A003'}),(o:vt_org{org_id:'ORG-001'}) MERGE (p)-[:works_at{role:'CTO'}]->(o)", 'wa3')

    # Cat.3 ★ recruits
    run(cur, "MATCH (a:vt_psn{psn_id:'PSN-A001'}),(b:vt_psn{psn_id:'PSN-A002'}) MERGE (a)-[:recruits{recruit_type:'영업담당',date:'2025-10-01'}]->(b)", 'rec1')
    run(cur, "MATCH (a:vt_psn{psn_id:'PSN-A001'}),(b:vt_psn{psn_id:'PSN-A003'}) MERGE (a)-[:recruits{recruit_type:'기술담당',date:'2025-09-15'}]->(b)", 'rec2')
    run(cur, "MATCH (a:vt_psn{psn_id:'PSN-A002'}),(b:vt_psn{psn_id:'PSN-A003'}) MERGE (a)-[:accomplice_of]->(b)", 'aco')

    # Cat.4 ★ operates · hosts · contains_file · located_at
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(s:vt_site{site_id:'SITE-002'}) MERGE (p)-[:operates{role:'채널소유자',valid_from:'2025-10-15'}]->(s)", 'op-s2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A003'}),(s:vt_site{site_id:'SITE-001'}) MERGE (p)-[:operates{role:'플랫폼관리자',valid_from:'2025-11-01'}]->(s)", 'op-s1')
    run(cur, "MATCH (ip:vt_ip{ip_id:'IP-001'}),(s:vt_site{site_id:'SITE-001'}) MERGE (ip)-[:hosts{port:443,detected_dt:'2026-02-15'}]->(s)", 'hs1')
    run(cur, "MATCH (ip:vt_ip{ip_id:'IP-002'}),(s:vt_site{site_id:'SITE-001'}) MERGE (ip)-[:hosts{port:8443,detected_dt:'2026-02-15',memo:'C2 통신'}]->(s)", 'hs2')
    run(cur, "MATCH (s:vt_site{site_id:'SITE-001'}),(ip:vt_ip{ip_id:'IP-001'}) MERGE (s)-[:resolves_to]->(ip)", 'rt1')
    run(cur, "MATCH (s:vt_site{site_id:'SITE-001'}),(f:vt_file{file_id:'FILE-001'}) MERGE (s)-[:contains_file{file_role:'악성APK배포'}]->(f)", 'cf1')
    run(cur, "MATCH (s:vt_site{site_id:'SITE-001'}),(f:vt_file{file_id:'FILE-002'}) MERGE (s)-[:contains_file{file_role:'가짜계약서다운로드'}]->(f)", 'cf2')
    run(cur, "MATCH (m:vt_msg{msg_id:'MSG-001'}),(f:vt_file{file_id:'FILE-001'}) MERGE (m)-[:contains_file{file_role:'앱설치유도'}]->(f)", 'cf-msg')
    run(cur, "MATCH (a:vt_atm{atm_id:'ATM-001'}),(l:vt_loc{loc_id:'LOC-001'}) MERGE (a)-[:located_at{verified:true}]->(l)", 'la1')
    run(cur, "MATCH (d:vt_dev{dev_id:'DEV-001'}),(l:vt_loc{loc_id:'LOC-002'}) MERGE (d)-[:located_at{verified:false}]->(l)", 'la2')

    # Cat.5 자금
    run(cur, "MATCH (a:vt_bacnt{bacnt_id:'ACC-V01'}),(t:vt_transfer{tf_id:'TRF-001'}) MERGE (a)-[:from_account]->(t)", 'fra1')
    run(cur, "MATCH (t:vt_transfer{tf_id:'TRF-001'}),(a:vt_bacnt{bacnt_id:'ACC-001'}) MERGE (t)-[:to_account]->(a)", 'toa1')
    run(cur, "MATCH (a:vt_bacnt{bacnt_id:'ACC-V02'}),(t:vt_transfer{tf_id:'TRF-002'}) MERGE (a)-[:from_account]->(t)", 'fra2')
    run(cur, "MATCH (t:vt_transfer{tf_id:'TRF-002'}),(a:vt_bacnt{bacnt_id:'ACC-001'}) MERGE (t)-[:to_account]->(a)", 'toa2')
    run(cur, "MATCH (a:vt_bacnt{bacnt_id:'ACC-V03'}),(t:vt_transfer{tf_id:'TRF-003'}) MERGE (a)-[:from_account]->(t)", 'fra3')
    run(cur, "MATCH (t:vt_transfer{tf_id:'TRF-003'}),(a:vt_bacnt{bacnt_id:'ACC-001'}) MERGE (t)-[:to_account]->(a)", 'toa3')
    run(cur, "MATCH (a:vt_bacnt{bacnt_id:'ACC-001'}),(t:vt_transfer{tf_id:'TRF-004'}) MERGE (a)-[:from_account]->(t)", 'fra4')
    run(cur, "MATCH (t:vt_transfer{tf_id:'TRF-004'}),(a:vt_bacnt{bacnt_id:'ACC-002'}) MERGE (t)-[:to_account]->(a)", 'toa4')
    run(cur, "MATCH (a:vt_bacnt{bacnt_id:'ACC-001'}),(b:vt_bacnt{bacnt_id:'ACC-002'}) MERGE (a)-[:transferred_to{hop_level:1,inferred:true}]->(b)", 'tt1')

    # Cat.6 사칭
    run(cur, "MATCH (s:vt_site{site_id:'SITE-001'}),(imp:vt_impersonation{imp_id:'IMP-001'}) MERGE (s)-[:used_for{method:'FAKE_WEBSITE'}]->(imp)", 'uf1')
    run(cur, "MATCH (imp:vt_impersonation{imp_id:'IMP-001'}),(o:vt_org{org_id:'ORG-002'}) MERGE (imp)-[:targets]->(o)", 'tg1')

    # Cat.7 통신
    run(cur, "MATCH (t:vt_telno{telno_id:'TEL-A01'}),(c:vt_call{call_id:'CALL-001'}) MERGE (t)-[:caller]->(c)", 'cr1')
    run(cur, "MATCH (c:vt_call{call_id:'CALL-001'}),(t:vt_telno{telno_id:'TEL-V01'}) MERGE (c)-[:callee]->(t)", 'ce1')
    run(cur, "MATCH (t:vt_telno{telno_id:'TEL-A01'}),(c:vt_call{call_id:'CALL-002'}) MERGE (t)-[:caller]->(c)", 'cr2')
    run(cur, "MATCH (c:vt_call{call_id:'CALL-002'}),(t:vt_telno{telno_id:'TEL-V02'}) MERGE (c)-[:callee]->(t)", 'ce2')
    run(cur, "MATCH (i:vt_id{id_id:'ID-001'}),(m:vt_msg{msg_id:'MSG-001'}) MERGE (i)-[:sent_msg{platform:'Telegram'}]->(m)", 'sm1')
    run(cur, "MATCH (i:vt_id{id_id:'ID-001'}),(m:vt_msg{msg_id:'MSG-002'}) MERGE (i)-[:sent_msg{platform:'KakaoTalk'}]->(m)", 'sm2')
    run(cur, "MATCH (m:vt_msg{msg_id:'MSG-002'}),(a:vt_bacnt{bacnt_id:'ACC-001'}) MERGE (m)-[:mentions_account]->(a)", 'ma1')

    # Cat.10 출처
    run(cur, "MATCH (c:vt_case{flnm:'CASE-IS-2026'}),(s:vt_src{src_id:'SRC-001'}) MERGE (c)-[:sourced_from]->(s)", 'sf')

    cur.execute("MATCH (n) RETURN count(*) AS cnt"); nodes = cur.fetchone()[0]
    cur.execute("MATCH ()-[r]->() RETURN count(*) AS cnt"); edges = cur.fetchone()[0]
    print(f'\n✅ {GRAPH} — 노드 {nodes}개  엣지 {edges}개')
    conn.close()

if __name__ == '__main__':
    main()
