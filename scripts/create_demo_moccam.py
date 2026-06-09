"""
CCOP v3.4 데모 — 시나리오 1: 텔레그램 몸캠피싱 조직 사건
============================================================
그래프명: ccop_demo_moccam

[사건 개요]
텔레그램에서 여성 이름을 가장한 계정으로 피해자에게 접근,
영상통화로 몸캠을 녹화한 뒤 협박금을 대포통장으로 송금받는
조직형 범죄. 해외 서버에 피해자 영상 저장·유포 협박.

[등장인물]
- 김총책(PSN-A001): 조직 총책, 텔레그램 채널 운영
- 이협박(PSN-A002): 직접 협박 담당, 영상통화 실행
- 박현금(PSN-A003): 대포통장 현금 인출 담당
- 최피해(PSN-V001): 피해자 1 (협박금 550만 원)
- 정피해(PSN-V002): 피해자 2 (협박금 300만 원)

[v3.4 신규 엣지 커버]
★ operates   : 김총책 → 텔레그램채널
★ recruits   : 김총책 → 이협박, 박현금
★ blackmails : 이협박 → 최피해, 이협박 → 정피해
★ hosts      : 해외서버IP → 피싱사이트
★ contains_file: 피싱사이트 → 협박영상
★ located_at : ATM → 현금인출 위치
"""
import psycopg2

DB   = dict(host='49.50.128.28', port=5333, dbname='tccopdb', user='ccop', password='Ccop@2025')
GRAPH = 'ccop_demo_moccam'

def run(cur, cypher, label=''):
    try: cur.execute(cypher)
    except Exception as e: print(f'  ⚠ [{label}] {e}')

def main():
    conn = psycopg2.connect(**DB); conn.autocommit = True; cur = conn.cursor()

    # 0. 초기화
    print(f'🗑  {GRAPH} 초기화...')
    try: cur.execute(f'DROP GRAPH {GRAPH} CASCADE')
    except: pass
    cur.execute(f'CREATE GRAPH {GRAPH}')
    cur.execute(f'SET graph_path = {GRAPH}')

    # 1. 레이블
    for v in ['vt_src','vt_case','vt_petition','vt_psn','vt_org',
              'vt_bacnt','vt_telno','vt_ip','vt_site','vt_file',
              'vt_id','vt_email','vt_dev','vt_atm','vt_loc',
              'vt_transfer','vt_call','vt_access','vt_msg','vt_movement']:
        run(cur, f'CREATE VLABEL IF NOT EXISTS {v}', v)
    for e in ['sourced_from','suspect_in','victim_in','filed_as','related_case',
              'has_account','controls','owns_phone','owns_device','used_ip','uses_id',
              'member_of','accomplice_of','recruits','blackmails','operates',
              'hosts','contains_file','located_at','resolves_to',
              'from_account','to_account','transferred_to',
              'caller','callee','sent_msg','received_msg',
              'accessed_from','recorded_in','occurred_at','linked_to']:
        run(cur, f'CREATE ELABEL IF NOT EXISTS {e}', e)
    print('  ✅ 레이블 등록 완료\n')

    # ── 노드 ──────────────────────────────────────
    print('📌 노드 삽입...')

    # Source
    run(cur, "CREATE (:vt_src {src_id:'SRC-001',src_name:'KICS 신고시스템',tier:1,rec_created:'2026-01-15'})", 'src')

    # Case / Petition
    run(cur, """CREATE (:vt_case {
        flnm:'CASE-MC-2026', crime_name:'텔레그램 조직형 몸캠피싱 사건',
        crime_type:'MOCCAM_PHISHING', status:'수사중',
        reg_date:'2026-02-15', damage_amt:'8500000', victim_cnt:2
    })""", 'case')
    run(cur, """CREATE (:vt_petition {
        pettn_id:'PTN-MC-001', petitioner:'최피해',
        content:'텔레그램에서 만난 여성이 영상통화 후 550만원 협박 요구',
        reg_date:'2026-02-13', status:'사건전환'
    })""", 'ptn1')
    run(cur, """CREATE (:vt_petition {
        pettn_id:'PTN-MC-002', petitioner:'정피해',
        content:'텔레그램 계정 @moccam_girl99에게 영상 녹화 후 협박',
        reg_date:'2026-02-14', status:'사건전환'
    })""", 'ptn2')

    # Persons
    run(cur, """CREATE (:vt_psn {
        psn_id:'PSN-A001', name:'김총책', type:'피의자',
        birth_dt:'1988-03-12', gender:'M', nationality:'KOR',
        address:'서울 구로구 신도림동', role:'조직총책'
    })""", 'psn-A001')
    run(cur, """CREATE (:vt_psn {
        psn_id:'PSN-A002', name:'이협박', type:'피의자',
        birth_dt:'1994-07-28', gender:'M', nationality:'KOR',
        address:'경기 부천시 원미구', role:'협박·영상통화담당'
    })""", 'psn-A002')
    run(cur, """CREATE (:vt_psn {
        psn_id:'PSN-A003', name:'박현금', type:'피의자',
        birth_dt:'1997-11-03', gender:'M', nationality:'KOR',
        address:'인천 계양구 계산동', role:'현금인출·대포통장관리'
    })""", 'psn-A003')
    run(cur, """CREATE (:vt_psn {
        psn_id:'PSN-V001', name:'최피해', type:'피해자',
        birth_dt:'1999-05-17', gender:'M', damage_amt:'5500000'
    })""", 'psn-V001')
    run(cur, """CREATE (:vt_psn {
        psn_id:'PSN-V002', name:'정피해', type:'피해자',
        birth_dt:'2001-02-24', gender:'M', damage_amt:'3000000'
    })""", 'psn-V002')

    # Org
    run(cur, """CREATE (:vt_org {
        org_id:'ORG-001', org_name:'텔레그램몸캠조직A',
        org_type:'CRIMINAL', desc:'조직형 몸캠피싱 전문 범죄단'
    })""", 'org')

    # BankAccount
    run(cur, "CREATE (:vt_bacnt {bacnt_id:'ACC-001',account_no:'110-1111-2222-01',bank_name:'카카오뱅크',holder:'황대포1',type:'대포통장'})", 'acc1')
    run(cur, "CREATE (:vt_bacnt {bacnt_id:'ACC-002',account_no:'352-3333-4444-02',bank_name:'농협',holder:'임대포2',type:'대포통장'})", 'acc2')
    run(cur, "CREATE (:vt_bacnt {bacnt_id:'ACC-V01',account_no:'088-5555-6666',bank_name:'신한',holder:'최피해',type:'피해자계좌'})", 'acc-v1')
    run(cur, "CREATE (:vt_bacnt {bacnt_id:'ACC-V02',account_no:'020-7777-8888',bank_name:'우리',holder:'정피해',type:'피해자계좌'})", 'acc-v2')

    # Phone
    run(cur, "CREATE (:vt_telno {telno_id:'TEL-A01',telno:'070-9001-1234',type:'발신',carrier:'인터넷전화',memo:'협박 전용 번호'})", 'tel-a1')
    run(cur, "CREATE (:vt_telno {telno_id:'TEL-A02',telno:'070-9001-5678',type:'발신',carrier:'인터넷전화',memo:'2차 협박 번호'})", 'tel-a2')
    run(cur, "CREATE (:vt_telno {telno_id:'TEL-V01',telno:'010-1111-2233',type:'수신',carrier:'SKT',memo:'피해자1 번호'})", 'tel-v1')
    run(cur, "CREATE (:vt_telno {telno_id:'TEL-V02',telno:'010-4455-6677',type:'수신',carrier:'KT',memo:'피해자2 번호'})", 'tel-v2')

    # IP / Site / File
    run(cur, "CREATE (:vt_ip {ip_id:'IP-001',ip_addr:'185.220.101.55',country:'NL',isp:'Tor Exit',threat_score:97,memo:'몸캠 서버 IP'})", 'ip1')
    run(cur, "CREATE (:vt_ip {ip_id:'IP-002',ip_addr:'121.53.44.88',country:'KR',isp:'KT',threat_score:25,memo:'총책 접속 IP'})", 'ip2')
    run(cur, """CREATE (:vt_site {
        site_id:'SITE-001', url:'https://moccam-leak.xyz/v',
        domain:'moccam-leak.xyz', type:'협박사이트',
        purpose:'피해자 영상 업로드·유포 협박 플랫폼', status:'활성'
    })""", 'site')
    run(cur, """CREATE (:vt_site {
        site_id:'SITE-002', url:'https://t.me/moccam_vip_real',
        domain:'t.me', type:'텔레그램채널',
        purpose:'피해자 유인 채널', status:'활성'
    })""", 'tg-ch')
    run(cur, "CREATE (:vt_file {file_id:'FILE-001',filename:'victim_choi_20260213.mp4',filetype:'video/mp4',filesize:'128MB',sha256:'c1a2b3d4e5f6a7b8c9d0e1f2a3b4c5d6',purpose:'협박용 몸캠 영상'})", 'file1')
    run(cur, "CREATE (:vt_file {file_id:'FILE-002',filename:'victim_jung_20260214.mp4',filetype:'video/mp4',filesize:'96MB',sha256:'d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7',purpose:'협박용 몸캠 영상 2'})", 'file2')

    # DigitalID
    run(cur, "CREATE (:vt_id {id_id:'ID-001',platform:'Telegram',username:'@moccam_girl99',type:'사기계정',memo:'피해자 유인 계정'})", 'id1')
    run(cur, "CREATE (:vt_id {id_id:'ID-002',platform:'Telegram',username:'@video_handler01',type:'협박계정',memo:'영상 협박 전담 계정'})", 'id2')

    # Device / ATM / Location
    run(cur, "CREATE (:vt_dev {dev_id:'DEV-001',device_type:'Smartphone',model:'Galaxy S24',imei:'359012345678901',memo:'이협박 사용 기기'})", 'dev1')
    run(cur, "CREATE (:vt_atm {atm_id:'ATM-001',bank_name:'카카오뱅크',atm_no:'KAK-3301',addr:'인천 계양구 계산동 ATM'})", 'atm1')
    run(cur, "CREATE (:vt_atm {atm_id:'ATM-002',bank_name:'농협',atm_no:'NH-8812',addr:'서울 구로구 신도림역 ATM'})", 'atm2')
    run(cur, "CREATE (:vt_loc {loc_id:'LOC-001',addr:'인천 계양구 계산동 44-2',lat:'37.5380',lon:'126.7375',type:'ATM현장'})", 'loc1')
    run(cur, "CREATE (:vt_loc {loc_id:'LOC-002',addr:'서울 구로구 신도림역 1번출구',lat:'37.5086',lon:'126.8916',type:'ATM현장'})", 'loc2')

    # Events
    run(cur, "CREATE (:vt_transfer {tf_id:'TRF-001',amount:'5500000',currency:'KRW',tf_dt:'2026-02-13 16:40:00',memo:'협박금 1차 (최피해→ACC-001)'})", 'trf1')
    run(cur, "CREATE (:vt_transfer {tf_id:'TRF-002',amount:'5000000',currency:'KRW',tf_dt:'2026-02-13 17:15:00',memo:'세탁 이체 (ACC-001→ACC-002)'})", 'trf2')
    run(cur, "CREATE (:vt_transfer {tf_id:'TRF-003',amount:'3000000',currency:'KRW',tf_dt:'2026-02-14 14:20:00',memo:'협박금 2차 (정피해→ACC-002)'})", 'trf3')
    run(cur, "CREATE (:vt_call {call_id:'CALL-001',call_dt:'2026-02-12 21:00:00',duration:'2543',call_type:'영상통화',memo:'몸캠 녹화 유인 통화'})", 'call1')
    run(cur, "CREATE (:vt_call {call_id:'CALL-002',call_dt:'2026-02-13 15:30:00',duration:'480',call_type:'음성통화',memo:'협박 전화 — 입금 독촉'})", 'call2')
    run(cur, "CREATE (:vt_call {call_id:'CALL-003',call_dt:'2026-02-14 13:10:00',duration:'310',call_type:'음성통화',memo:'2차 피해자 협박 전화'})", 'call3')
    run(cur, "CREATE (:vt_msg {msg_id:'MSG-001',content:'영상 유포하기 싫으면 30분 안에 550만원 입금해',platform:'Telegram',sent_dt:'2026-02-13 15:00:00',type:'협박메시지'})", 'msg1')
    run(cur, "CREATE (:vt_msg {msg_id:'MSG-002',content:'영상 클립 올려놨음. 지금 바로 300만원 송금',platform:'Telegram',sent_dt:'2026-02-14 13:30:00',type:'협박메시지'})", 'msg2')
    run(cur, "CREATE (:vt_access {access_id:'ACC-LOG-001',access_dt:'2026-02-11 03:22:00',method:'HTTPS',memo:'서버 관리 접속'})", 'acc-log')
    run(cur, "CREATE (:vt_movement {mov_id:'MOV-001',mov_dt:'2026-02-13 17:30:00',loc_from:'인천 계양구',loc_to:'인천 계산동 ATM',method:'도보',memo:'현금 인출 이동'})", 'mov1')
    print('  ✅ 노드 완료\n')

    # ── 엣지 ──────────────────────────────────────
    print('🔗 엣지 삽입...')

    # Cat.1 사건
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(c:vt_case{flnm:'CASE-MC-2026'}) MERGE (p)-[:suspect_in{verified:true}]->(c)", 'si-A001')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(c:vt_case{flnm:'CASE-MC-2026'}) MERGE (p)-[:suspect_in{verified:true}]->(c)", 'si-A002')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A003'}),(c:vt_case{flnm:'CASE-MC-2026'}) MERGE (p)-[:suspect_in{verified:false}]->(c)", 'si-A003')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V001'}),(c:vt_case{flnm:'CASE-MC-2026'}) MERGE (p)-[:victim_in{damage_amt:'5500000'}]->(c)", 'vi-V001')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V002'}),(c:vt_case{flnm:'CASE-MC-2026'}) MERGE (p)-[:victim_in{damage_amt:'3000000'}]->(c)", 'vi-V002')
    run(cur, "MATCH (pt:vt_petition{pettn_id:'PTN-MC-001'}),(c:vt_case{flnm:'CASE-MC-2026'}) MERGE (pt)-[:filed_as{converted_dt:'2026-02-15'}]->(c)", 'fa1')
    run(cur, "MATCH (pt:vt_petition{pettn_id:'PTN-MC-002'}),(c:vt_case{flnm:'CASE-MC-2026'}) MERGE (pt)-[:filed_as{converted_dt:'2026-02-15'}]->(c)", 'fa2')

    # Cat.2 소유
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(a:vt_bacnt{bacnt_id:'ACC-001'}) MERGE (p)-[:controls{method:'대포통장',verified:true}]->(a)", 'ctrl1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A003'}),(a:vt_bacnt{bacnt_id:'ACC-002'}) MERGE (p)-[:has_account{type:'대포통장명의'}]->(a)", 'ha2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V001'}),(a:vt_bacnt{bacnt_id:'ACC-V01'}) MERGE (p)-[:has_account]->(a)", 'ha-v1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V002'}),(a:vt_bacnt{bacnt_id:'ACC-V02'}) MERGE (p)-[:has_account]->(a)", 'ha-v2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(t:vt_telno{telno_id:'TEL-A01'}) MERGE (p)-[:owns_phone{verified:false}]->(t)", 'op-a01')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(t:vt_telno{telno_id:'TEL-A02'}) MERGE (p)-[:owns_phone{verified:true}]->(t)", 'op-a02')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V001'}),(t:vt_telno{telno_id:'TEL-V01'}) MERGE (p)-[:owns_phone]->(t)", 'op-v1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-V002'}),(t:vt_telno{telno_id:'TEL-V02'}) MERGE (p)-[:owns_phone]->(t)", 'op-v2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(i:vt_id{id_id:'ID-001'}) MERGE (p)-[:uses_id{platform:'Telegram'}]->(i)", 'uid1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(i:vt_id{id_id:'ID-002'}) MERGE (p)-[:uses_id{platform:'Telegram'}]->(i)", 'uid2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(d:vt_dev{dev_id:'DEV-001'}) MERGE (p)-[:owns_device]->(d)", 'od1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(ip:vt_ip{ip_id:'IP-002'}) MERGE (p)-[:used_ip{method:'VPN'}]->(ip)", 'ui-a1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(o:vt_org{org_id:'ORG-001'}) MERGE (p)-[:member_of{role:'admin'}]->(o)", 'mo1')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(o:vt_org{org_id:'ORG-001'}) MERGE (p)-[:member_of{role:'member'}]->(o)", 'mo2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A003'}),(o:vt_org{org_id:'ORG-001'}) MERGE (p)-[:member_of{role:'member'}]->(o)", 'mo3')

    # Cat.3 ★ recruits · blackmails
    run(cur, "MATCH (a:vt_psn{psn_id:'PSN-A001'}),(b:vt_psn{psn_id:'PSN-A002'}) MERGE (a)-[:recruits{recruit_type:'협박담당',date:'2025-12-10'}]->(b)", 'rec1')
    run(cur, "MATCH (a:vt_psn{psn_id:'PSN-A001'}),(b:vt_psn{psn_id:'PSN-A003'}) MERGE (a)-[:recruits{recruit_type:'현금인출',date:'2025-12-15'}]->(b)", 'rec2')
    run(cur, "MATCH (a:vt_psn{psn_id:'PSN-A002'}),(b:vt_psn{psn_id:'PSN-V001'}) MERGE (a)-[:blackmails{method:'몸캠영상유포협박',date:'2026-02-13'}]->(b)", 'bm1')
    run(cur, "MATCH (a:vt_psn{psn_id:'PSN-A002'}),(b:vt_psn{psn_id:'PSN-V002'}) MERGE (a)-[:blackmails{method:'몸캠영상유포협박',date:'2026-02-14'}]->(b)", 'bm2')
    run(cur, "MATCH (a:vt_psn{psn_id:'PSN-A002'}),(b:vt_psn{psn_id:'PSN-A003'}) MERGE (a)-[:accomplice_of]->(b)", 'aco')

    # Cat.4 ★ operates · hosts · contains_file · located_at
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A001'}),(s:vt_site{site_id:'SITE-002'}) MERGE (p)-[:operates{role:'채널관리자',valid_from:'2025-11-01'}]->(s)", 'op-site2')
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A002'}),(s:vt_site{site_id:'SITE-001'}) MERGE (p)-[:operates{role:'영상업로더',valid_from:'2025-11-15'}]->(s)", 'op-site1')
    run(cur, "MATCH (ip:vt_ip{ip_id:'IP-001'}),(s:vt_site{site_id:'SITE-001'}) MERGE (ip)-[:hosts{port:443,detected_dt:'2026-02-11'}]->(s)", 'hs1')
    run(cur, "MATCH (s:vt_site{site_id:'SITE-001'}),(ip:vt_ip{ip_id:'IP-001'}) MERGE (s)-[:resolves_to]->(ip)", 'rt1')
    run(cur, "MATCH (s:vt_site{site_id:'SITE-001'}),(f:vt_file{file_id:'FILE-001'}) MERGE (s)-[:contains_file{file_role:'협박영상저장'}]->(f)", 'cf1')
    run(cur, "MATCH (s:vt_site{site_id:'SITE-001'}),(f:vt_file{file_id:'FILE-002'}) MERGE (s)-[:contains_file{file_role:'협박영상저장'}]->(f)", 'cf2')
    run(cur, "MATCH (m:vt_msg{msg_id:'MSG-001'}),(f:vt_file{file_id:'FILE-001'}) MERGE (m)-[:contains_file{file_role:'협박첨부'}]->(f)", 'cf-msg')
    run(cur, "MATCH (a:vt_atm{atm_id:'ATM-001'}),(l:vt_loc{loc_id:'LOC-001'}) MERGE (a)-[:located_at{verified:true}]->(l)", 'la1')
    run(cur, "MATCH (a:vt_atm{atm_id:'ATM-002'}),(l:vt_loc{loc_id:'LOC-002'}) MERGE (a)-[:located_at{verified:true}]->(l)", 'la2')

    # Cat.5 자금
    run(cur, "MATCH (a:vt_bacnt{bacnt_id:'ACC-V01'}),(t:vt_transfer{tf_id:'TRF-001'}) MERGE (a)-[:from_account]->(t)", 'fa-1')
    run(cur, "MATCH (t:vt_transfer{tf_id:'TRF-001'}),(a:vt_bacnt{bacnt_id:'ACC-001'}) MERGE (t)-[:to_account]->(a)", 'ta-1')
    run(cur, "MATCH (a:vt_bacnt{bacnt_id:'ACC-001'}),(t:vt_transfer{tf_id:'TRF-002'}) MERGE (a)-[:from_account]->(t)", 'fa-2')
    run(cur, "MATCH (t:vt_transfer{tf_id:'TRF-002'}),(a:vt_bacnt{bacnt_id:'ACC-002'}) MERGE (t)-[:to_account]->(a)", 'ta-2')
    run(cur, "MATCH (a:vt_bacnt{bacnt_id:'ACC-V02'}),(t:vt_transfer{tf_id:'TRF-003'}) MERGE (a)-[:from_account]->(t)", 'fa-3')
    run(cur, "MATCH (t:vt_transfer{tf_id:'TRF-003'}),(a:vt_bacnt{bacnt_id:'ACC-002'}) MERGE (t)-[:to_account]->(a)", 'ta-3')
    run(cur, "MATCH (a:vt_bacnt{bacnt_id:'ACC-001'}),(b:vt_bacnt{bacnt_id:'ACC-002'}) MERGE (a)-[:transferred_to{hop_level:1,inferred:true}]->(b)", 'tt')

    # Cat.7 통신
    run(cur, "MATCH (t:vt_telno{telno_id:'TEL-A01'}),(c:vt_call{call_id:'CALL-001'}) MERGE (t)-[:caller]->(c)", 'cr1')
    run(cur, "MATCH (c:vt_call{call_id:'CALL-001'}),(t:vt_telno{telno_id:'TEL-V01'}) MERGE (c)-[:callee]->(t)", 'ce1')
    run(cur, "MATCH (t:vt_telno{telno_id:'TEL-A01'}),(c:vt_call{call_id:'CALL-002'}) MERGE (t)-[:caller]->(c)", 'cr2')
    run(cur, "MATCH (c:vt_call{call_id:'CALL-002'}),(t:vt_telno{telno_id:'TEL-V01'}) MERGE (c)-[:callee]->(t)", 'ce2')
    run(cur, "MATCH (t:vt_telno{telno_id:'TEL-A02'}),(c:vt_call{call_id:'CALL-003'}) MERGE (t)-[:caller]->(c)", 'cr3')
    run(cur, "MATCH (c:vt_call{call_id:'CALL-003'}),(t:vt_telno{telno_id:'TEL-V02'}) MERGE (c)-[:callee]->(t)", 'ce3')
    run(cur, "MATCH (i:vt_id{id_id:'ID-002'}),(m:vt_msg{msg_id:'MSG-001'}) MERGE (i)-[:sent_msg{platform:'Telegram'}]->(m)", 'sm1')
    run(cur, "MATCH (m:vt_msg{msg_id:'MSG-001'}),(t:vt_telno{telno_id:'TEL-V01'}) MERGE (m)-[:received_msg]->(t)", 'rm1')
    run(cur, "MATCH (i:vt_id{id_id:'ID-002'}),(m:vt_msg{msg_id:'MSG-002'}) MERGE (i)-[:sent_msg{platform:'Telegram'}]->(m)", 'sm2')
    run(cur, "MATCH (m:vt_msg{msg_id:'MSG-002'}),(t:vt_telno{telno_id:'TEL-V02'}) MERGE (m)-[:received_msg]->(t)", 'rm2')

    # Cat.8 접속
    run(cur, "MATCH (a:vt_access{access_id:'ACC-LOG-001'}),(ip:vt_ip{ip_id:'IP-001'}) MERGE (a)-[:accessed_from]->(ip)", 'af1')
    run(cur, "MATCH (d:vt_dev{dev_id:'DEV-001'}),(ip:vt_ip{ip_id:'IP-002'}) MERGE (d)-[:used_ip{method:'직접접속'}]->(ip)", 'ui-dev')

    # Cat.9 이동
    run(cur, "MATCH (p:vt_psn{psn_id:'PSN-A003'}),(m:vt_movement{mov_id:'MOV-001'}) MERGE (p)-[:recorded_in{method:'CCTV'}]->(m)", 'ri1')
    run(cur, "MATCH (m:vt_movement{mov_id:'MOV-001'}),(l:vt_loc{loc_id:'LOC-001'}) MERGE (m)-[:occurred_at]->(l)", 'oa1')

    # Cat.10 출처
    run(cur, "MATCH (c:vt_case{flnm:'CASE-MC-2026'}),(s:vt_src{src_id:'SRC-001'}) MERGE (c)-[:sourced_from]->(s)", 'sf')

    # 통계
    cur.execute("MATCH (n) RETURN count(*) AS cnt")
    nodes = cur.fetchone()[0]
    cur.execute("MATCH ()-[r]->() RETURN count(*) AS cnt")
    edges = cur.fetchone()[0]
    print(f'\n✅ {GRAPH} — 노드 {nodes}개  엣지 {edges}개')
    conn.close()

if __name__ == '__main__':
    main()
