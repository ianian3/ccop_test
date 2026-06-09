"""
CCOP 온톨로지 v3.4 설계 시뮬레이션
====================================
8대 사이버 범죄 유형별 가상 시나리오 생성 → 엣지 사용 패턴 분석 → 최적 온톨로지 도출

사건 유형:
  SIM-MC  : 몸캠피싱
  SIM-VP  : 보이스피싱
  SIM-IM  : 사칭
  SIM-IS  : 투자사기
  SIM-GB  : 도박사이트
  SIM-DA  : 대포통장
  SIM-DR  : 사이버마약
  SIM-TG  : 텔레그램 범죄 (불법촬영물 유포)
"""

import psycopg2
from collections import defaultdict

DB = dict(host='49.50.128.28', port=5333, dbname='tccopdb', user='ccop', password='Ccop@2025')

# ── 후보 엣지 정의 (현행 + 신규 테스트) ─────────────────────────────
CANDIDATE_EDGES = {
    # 현행 유지
    'suspect_in', 'victim_in', 'witness_in', 'filed_as', 'clusters_with', 'related_case',
    'has_account', 'controls', 'owns_phone', 'owns_device', 'owns_vehicle', 'drives',
    'owns', 'uses_id', 'uses_email', 'registered_to',
    'member_of', 'works_at', 'accomplice_of', 'sameAs', 'contradicts',
    'belongs_to', 'resolves_to', 'linked_to', 'mentions_account', 'sourced_from',
    'from_account', 'to_account', 'transferred_to',
    'used_for', 'targets',
    'caller', 'callee', 'sent_msg', 'received_msg',
    'used_ip', 'accessed_from',
    'recorded_in', 'occurred_at',
    # 신규 후보 ← 시뮬레이션으로 검증
    'operates',       # Person/Org → Site/Platform/Channel
    'hosts',          # NetworkTrace → WebTrace
    'blackmails',     # Person → Person
    'recruits',       # Person → Person
    'contains_file',  # Site/Msg → File
    'located_at',     # ATM/Device/Org → Location
}

# ── 시뮬레이션 데이터 정의 ────────────────────────────────────────────
SCENARIOS = {

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SIM-MC: 몸캠피싱
    # 흐름: 가짜계정으로 피해자 접촉 → 영상 녹화 → 협박 → 이체
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'ccop_sim_mc': {
        'name': '몸캠피싱',
        'case_id': 'SIM-MC-2026-001',
        'nodes': [
            ("vt_psn",  "psn_id:'PSN-MC-A01', name:'박몸캠', type:'피의자'"),
            ("vt_psn",  "psn_id:'PSN-MC-V01', name:'홍피해', type:'피해자'"),
            ("vt_id",   "id_id:'ID-MC-01', id_val:'@sexy_friend99', platform:'텔레그램', real_nm:'박몸캠'"),
            ("vt_id",   "id_id:'ID-MC-02', id_val:'RandomChat_fake', platform:'랜덤채팅앱', real_nm:'박몸캠'"),
            ("vt_site", "site_id:'SITE-MC-01', url:'randomchat-kr.app', site_type:'랜덤채팅앱', status:'운영중'"),
            ("vt_file", "file_id:'FILE-MC-01', file_name:'피해자영상_20260115.mp4', file_type:'MP4', malware_type:'협박증거물'"),
            ("vt_msg",  "msg_id:'MSG-MC-01', msg_type:'텔레그램', content:'영상 유포 원하지 않으면 200만원 입금', is_phishing:true"),
            ("vt_bacnt","acnt_id:'ACNT-MC-01', actno:'110-8888-111111', bank_cd:'004', holder:'차명인', acnt_type:'대포통장'"),
            ("vt_transfer","tx_id:'TX-MC-01', dlng_amt:'2000000', tx_type:'이체', dlng_dt:'2026-01-16 09:00:00'"),
            ("vt_case", "flnm:'SIM-MC-2026-001', crime_type:'몸캠피싱', crime_method:'SNS접촉형', damage_amt:'2000000'"),
        ],
        'edges': [
            # 인물 → 사건
            ("MATCH (p:vt_psn {psn_id:'PSN-MC-A01'}),(c:vt_case {flnm:'SIM-MC-2026-001'}) CREATE (p)-[:suspect_in {role:'주범'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-MC-V01'}),(c:vt_case {flnm:'SIM-MC-2026-001'}) CREATE (p)-[:victim_in {damage_amt:'2000000'}]->(c)", 'victim_in'),
            # 피의자 → 가짜 계정/플랫폼
            ("MATCH (p:vt_psn {psn_id:'PSN-MC-A01'}),(i:vt_id {id_id:'ID-MC-01'}) CREATE (p)-[:uses_id {platform:'텔레그램'}]->(i)", 'uses_id'),
            ("MATCH (p:vt_psn {psn_id:'PSN-MC-A01'}),(i:vt_id {id_id:'ID-MC-02'}) CREATE (p)-[:uses_id {platform:'랜덤채팅앱'}]->(i)", 'uses_id'),
            # 피의자가 랜덤채팅 플랫폼 계정 운영 ← NEW
            ("MATCH (p:vt_psn {psn_id:'PSN-MC-A01'}),(s:vt_site {site_id:'SITE-MC-01'}) CREATE (p)-[:operates {role:'계정운영', method:'가짜프로필'}]->(s)", 'operates'),
            # 협박 관계 ← NEW
            ("MATCH (a:vt_psn {psn_id:'PSN-MC-A01'}),(v:vt_psn {psn_id:'PSN-MC-V01'}) CREATE (a)-[:blackmails {method:'영상유포협박', amount:'2000000', rec_created:'2026-01-15'}]->(v)", 'blackmails'),
            # 메시지에 영상 포함 ← NEW
            ("MATCH (m:vt_msg {msg_id:'MSG-MC-01'}),(f:vt_file {file_id:'FILE-MC-01'}) CREATE (m)-[:contains_file {purpose:'협박증거'}]->(f)", 'contains_file'),
            # 메시지 발신
            ("MATCH (i:vt_id {id_id:'ID-MC-01'}),(m:vt_msg {msg_id:'MSG-MC-01'}) CREATE (i)-[:sent_msg {rec_created:'2026-01-15'}]->(m)", 'sent_msg'),
            # 자금 이동
            ("MATCH (b:vt_bacnt {acnt_id:'ACNT-MC-01'}),(tx:vt_transfer {tx_id:'TX-MC-01'}) CREATE (b)-[:to_account]->(tx)", 'to_account'),
            ("MATCH (p:vt_psn {psn_id:'PSN-MC-A01'}),(b:vt_bacnt {acnt_id:'ACNT-MC-01'}) CREATE (p)-[:controls {verified:false}]->(b)", 'controls'),
        ],
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SIM-VP: 보이스피싱 (기관사칭형)
    # 흐름: 사칭번호 → 피해자 통화 → 계좌이체 → ATM출금
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'ccop_sim_vp': {
        'name': '보이스피싱',
        'case_id': 'SIM-VP-2026-001',
        'nodes': [
            ("vt_psn",   "psn_id:'PSN-VP-A01', name:'이사칭', type:'피의자'"),
            ("vt_psn",   "psn_id:'PSN-VP-V01', name:'김피해', type:'피해자'"),
            ("vt_org",   "org_id:'ORG-VP-01', org_name:'금융감독원', org_type:'GOV'"),
            ("vt_telno", "tel_id:'TEL-VP-01', telno:'02-1332-0001', tel_type:'사칭번호'"),
            ("vt_impersonation", "event_id:'IMP-VP-01', method:'전화사칭', fake_name:'금감원 수사관 김대리', script_type:'계좌보호명목이체유도', confidence:0.98"),
            ("vt_bacnt", "acnt_id:'ACNT-VP-V01', actno:'110-2222-333333', holder:'김피해', acnt_type:'일반'"),
            ("vt_bacnt", "acnt_id:'ACNT-VP-01', actno:'110-9999-000000', holder:'차명인', acnt_type:'대포통장'"),
            ("vt_transfer","tx_id:'TX-VP-01', dlng_amt:'30000000', tx_type:'이체', dlng_dt:'2026-02-10 14:00:00'"),
            ("vt_call",  "call_id:'CALL-VP-01', call_dt:'2026-02-10 13:00:00', duration:1800, call_type:'사칭전화'"),
            ("vt_case",  "flnm:'SIM-VP-2026-001', crime_type:'보이스피싱', crime_method:'기관사칭형', damage_amt:'30000000'"),
        ],
        'edges': [
            ("MATCH (p:vt_psn {psn_id:'PSN-VP-A01'}),(c:vt_case {flnm:'SIM-VP-2026-001'}) CREATE (p)-[:suspect_in {role:'주범'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-VP-V01'}),(c:vt_case {flnm:'SIM-VP-2026-001'}) CREATE (p)-[:victim_in]->(c)", 'victim_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-VP-A01'}),(t:vt_telno {tel_id:'TEL-VP-01'}) CREATE (p)-[:owns_phone]->(t)", 'owns_phone'),
            # V3.3 사칭 패턴
            ("MATCH (t:vt_telno {tel_id:'TEL-VP-01'}),(i:vt_impersonation {event_id:'IMP-VP-01'}) CREATE (t)-[:used_for {imprsn_type:'전화사칭'}]->(i)", 'used_for'),
            ("MATCH (i:vt_impersonation {event_id:'IMP-VP-01'}),(o:vt_org {org_id:'ORG-VP-01'}) CREATE (i)-[:targets]->(o)", 'targets'),
            ("MATCH (t:vt_telno {tel_id:'TEL-VP-01'}),(c:vt_call {call_id:'CALL-VP-01'}) CREATE (t)-[:caller]->(c)", 'caller'),
            ("MATCH (b:vt_bacnt {acnt_id:'ACNT-VP-V01'}),(tx:vt_transfer {tx_id:'TX-VP-01'}) CREATE (b)-[:from_account]->(tx)", 'from_account'),
            ("MATCH (tx:vt_transfer {tx_id:'TX-VP-01'}),(b:vt_bacnt {acnt_id:'ACNT-VP-01'}) CREATE (tx)-[:to_account]->(b)", 'to_account'),
            ("MATCH (p:vt_psn {psn_id:'PSN-VP-V01'}),(b:vt_bacnt {acnt_id:'ACNT-VP-V01'}) CREATE (p)-[:has_account]->(b)", 'has_account'),
            ("MATCH (p:vt_psn {psn_id:'PSN-VP-A01'}),(b:vt_bacnt {acnt_id:'ACNT-VP-01'}) CREATE (p)-[:controls]->(b)", 'controls'),
        ],
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SIM-IM: 사칭 (지인사칭 / SNS 계정탈취 후 지인 사칭)
    # 흐름: SNS 계정탈취 → 지인 사칭 → 금전 요구
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'ccop_sim_im': {
        'name': '사칭',
        'case_id': 'SIM-IM-2026-001',
        'nodes': [
            ("vt_psn",  "psn_id:'PSN-IM-A01', name:'최해커', type:'피의자'"),
            ("vt_psn",  "psn_id:'PSN-IM-V01', name:'정피해', type:'피해자'"),
            ("vt_psn",  "psn_id:'PSN-IM-R01', name:'박친구', type:'피해자'"),   # 사칭 당한 지인
            ("vt_id",   "id_id:'ID-IM-01', id_val:'park_friend_kakao', platform:'카카오톡', real_nm:'박친구'"),
            ("vt_id",   "id_id:'ID-IM-02', id_val:'park_friend_hacked', platform:'카카오톡', real_nm:'최해커'"),  # 탈취 계정
            ("vt_impersonation", "event_id:'IMP-IM-01', method:'SNS계정탈취사칭', fake_name:'박친구', script_type:'지인사칭긴급금전요구', confidence:0.92"),
            ("vt_msg",  "msg_id:'MSG-IM-01', msg_type:'카카오톡', content:'나 지금 급해서 50만원만 빌려줘 바로 갚을게', is_phishing:true"),
            ("vt_bacnt","acnt_id:'ACNT-IM-01', actno:'301-1111-222222', holder:'차명인', acnt_type:'대포통장'"),
            ("vt_case", "flnm:'SIM-IM-2026-001', crime_type:'사칭', crime_method:'SNS계정탈취형', damage_amt:'500000'"),
        ],
        'edges': [
            ("MATCH (p:vt_psn {psn_id:'PSN-IM-A01'}),(c:vt_case {flnm:'SIM-IM-2026-001'}) CREATE (p)-[:suspect_in {role:'주범'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-IM-V01'}),(c:vt_case {flnm:'SIM-IM-2026-001'}) CREATE (p)-[:victim_in]->(c)", 'victim_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-IM-R01'}),(c:vt_case {flnm:'SIM-IM-2026-001'}) CREATE (p)-[:victim_in {note:'계정탈취피해'}]->(c)", 'victim_in'),
            # 탈취한 계정으로 사칭
            ("MATCH (p:vt_psn {psn_id:'PSN-IM-A01'}),(i:vt_id {id_id:'ID-IM-02'}) CREATE (p)-[:uses_id {method:'계정탈취'}]->(i)", 'uses_id'),
            # 사칭 이벤트 (지인 사칭)
            ("MATCH (i:vt_id {id_id:'ID-IM-02'}),(imp:vt_impersonation {event_id:'IMP-IM-01'}) CREATE (i)-[:used_for {imprsn_type:'SNS계정사칭'}]->(imp)", 'used_for'),
            # targets는 개인 (vt_psn) — 기관 아닌 경우도 있음
            ("MATCH (imp:vt_impersonation {event_id:'IMP-IM-01'}),(p:vt_psn {psn_id:'PSN-IM-R01'}) CREATE (imp)-[:targets {target_type:'개인'}]->(p)", 'targets'),
            ("MATCH (i:vt_id {id_id:'ID-IM-02'}),(m:vt_msg {msg_id:'MSG-IM-01'}) CREATE (i)-[:sent_msg]->(m)", 'sent_msg'),
            ("MATCH (p:vt_psn {psn_id:'PSN-IM-A01'}),(b:vt_bacnt {acnt_id:'ACNT-IM-01'}) CREATE (p)-[:controls]->(b)", 'controls'),
            # 동일인물 해소 (박친구 원래 ID vs 탈취 ID)
            ("MATCH (i1:vt_id {id_id:'ID-IM-01'}),(i2:vt_id {id_id:'ID-IM-02'}) CREATE (i2)-[:contradicts {reason:'계정탈취'}]->(i1)", 'contradicts'),
        ],
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SIM-IS: 투자사기
    # 흐름: 가짜 투자 플랫폼 운영 → 수익 미끼 → 입금 → 출금 거부 → 잠적
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'ccop_sim_is': {
        'name': '투자사기',
        'case_id': 'SIM-IS-2026-001',
        'nodes': [
            ("vt_psn",  "psn_id:'PSN-IS-A01', name:'강투자', type:'피의자'"),
            ("vt_psn",  "psn_id:'PSN-IS-A02', name:'윤모집', type:'피의자'"),    # 투자자 모집책
            ("vt_psn",  "psn_id:'PSN-IS-V01', name:'조피해', type:'피해자'"),
            ("vt_psn",  "psn_id:'PSN-IS-V02', name:'임피해', type:'피해자'"),
            ("vt_org",  "org_id:'ORG-IS-01', org_name:'(주)코인스타트업', org_type:'FAKE_CORP'"),
            ("vt_site", "site_id:'SITE-IS-01', url:'coinstartup-invest.com', site_type:'투자사기사이트', status:'운영중'"),
            ("vt_ip",   "ip_id:'IP-IS-01', ip_addr:'23.45.67.89', isp:'Cloudflare', country:'USA', is_vpn:true"),
            ("vt_id",   "id_id:'ID-IS-01', id_val:'코인전문가_강', platform:'카카오오픈채팅'"),
            ("vt_bacnt","acnt_id:'ACNT-IS-01', actno:'110-7777-888888', holder:'차명인', acnt_type:'대포통장'"),
            ("vt_crypto","wallet_id:'WALLET-IS-01', address:'3FZbgi29cpjq2GjdwV8eyHuJJnkLtktZc5', coin_type:'BTC'"),
            ("vt_transfer","tx_id:'TX-IS-01', dlng_amt:'50000000', tx_type:'이체', dlng_dt:'2026-02-20 11:00:00'"),
            ("vt_transfer","tx_id:'TX-IS-02', dlng_amt:'70000000', tx_type:'이체', dlng_dt:'2026-02-21 14:00:00'"),
            ("vt_case", "flnm:'SIM-IS-2026-001', crime_type:'투자사기', crime_method:'가짜플랫폼형', damage_amt:'120000000'"),
        ],
        'edges': [
            ("MATCH (p:vt_psn {psn_id:'PSN-IS-A01'}),(c:vt_case {flnm:'SIM-IS-2026-001'}) CREATE (p)-[:suspect_in {role:'주범/운영자'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-IS-A02'}),(c:vt_case {flnm:'SIM-IS-2026-001'}) CREATE (p)-[:suspect_in {role:'모집책'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-IS-V01'}),(c:vt_case {flnm:'SIM-IS-2026-001'}) CREATE (p)-[:victim_in {damage_amt:'50000000'}]->(c)", 'victim_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-IS-V02'}),(c:vt_case {flnm:'SIM-IS-2026-001'}) CREATE (p)-[:victim_in {damage_amt:'70000000'}]->(c)", 'victim_in'),
            # 투자사이트 운영 ← NEW
            ("MATCH (p:vt_psn {psn_id:'PSN-IS-A01'}),(s:vt_site {site_id:'SITE-IS-01'}) CREATE (p)-[:operates {role:'운영자', org:'ORG-IS-01'}]->(s)", 'operates'),
            # 서버 호스팅 ← NEW
            ("MATCH (ip:vt_ip {ip_id:'IP-IS-01'}),(s:vt_site {site_id:'SITE-IS-01'}) CREATE (ip)-[:hosts {server_type:'투자사기서버'}]->(s)", 'hosts'),
            # 모집책이 피해자 모집 ← NEW
            ("MATCH (a:vt_psn {psn_id:'PSN-IS-A02'}),(v:vt_psn {psn_id:'PSN-IS-V01'}) CREATE (a)-[:recruits {method:'카카오오픈채팅', rec_created:'2026-02-15'}]->(v)", 'recruits'),
            ("MATCH (a:vt_psn {psn_id:'PSN-IS-A02'}),(v:vt_psn {psn_id:'PSN-IS-V02'}) CREATE (a)-[:recruits {method:'카카오오픈채팅'}]->(v)", 'recruits'),
            ("MATCH (p:vt_psn {psn_id:'PSN-IS-A01'}),(b:vt_bacnt {acnt_id:'ACNT-IS-01'}) CREATE (p)-[:controls]->(b)", 'controls'),
            ("MATCH (b:vt_bacnt {acnt_id:'ACNT-IS-01'}),(tx:vt_transfer {tx_id:'TX-IS-01'}) CREATE (b)-[:to_account]->(tx)", 'to_account'),
            ("MATCH (b:vt_bacnt {acnt_id:'ACNT-IS-01'}),(tx:vt_transfer {tx_id:'TX-IS-02'}) CREATE (b)-[:to_account]->(tx)", 'to_account'),
            ("MATCH (p:vt_psn {psn_id:'PSN-IS-A01'}),(w:vt_crypto {wallet_id:'WALLET-IS-01'}) CREATE (p)-[:owns {asset_type:'BTC'}]->(w)", 'owns'),
            ("MATCH (p:vt_psn {psn_id:'PSN-IS-A01'}),(i:vt_id {id_id:'ID-IS-01'}) CREATE (p)-[:uses_id]->(i)", 'uses_id'),
            # 공범 관계
            ("MATCH (a1:vt_psn {psn_id:'PSN-IS-A01'}),(a2:vt_psn {psn_id:'PSN-IS-A02'}) CREATE (a1)-[:accomplice_of]->(a2)", 'accomplice_of'),
        ],
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SIM-GB: 도박사이트 제작/운영
    # 흐름: 해외 서버 개설 → 사이트 운영 → 회원 모집 → 입출금 세탁
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'ccop_sim_gb': {
        'name': '도박사이트',
        'case_id': 'SIM-GB-2026-001',
        'nodes': [
            ("vt_psn",  "psn_id:'PSN-GB-A01', name:'한도박', type:'피의자'"),   # 운영자
            ("vt_psn",  "psn_id:'PSN-GB-A02', name:'류총판', type:'피의자'"),   # 총판
            ("vt_psn",  "psn_id:'PSN-GB-M01', name:'나회원', type:'참고인'"),   # 이용자
            ("vt_org",  "org_id:'ORG-GB-01', org_name:'도박조직 K-BET', org_type:'CRIMINAL_ORG'"),
            ("vt_site", "site_id:'SITE-GB-01', url:'kbet-online.ph', site_type:'불법도박', status:'운영중'"),
            ("vt_ip",   "ip_id:'IP-GB-01', ip_addr:'103.55.88.12', isp:'Philippin Telecom', country:'PHL', is_vpn:false"),
            ("vt_ip",   "ip_id:'IP-GB-02', ip_addr:'175.198.55.21', isp:'SKB', country:'KOR'"),
            ("vt_bacnt","acnt_id:'ACNT-GB-01', actno:'110-6666-777777', holder:'차명인1', acnt_type:'대포통장'"),
            ("vt_bacnt","acnt_id:'ACNT-GB-02', actno:'088-3333-444444', holder:'차명인2', acnt_type:'대포통장'"),
            ("vt_crypto","wallet_id:'WALLET-GB-01', address:'bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh', coin_type:'BTC'"),
            ("vt_case", "flnm:'SIM-GB-2026-001', crime_type:'불법도박사이트', crime_method:'해외서버운영형', damage_amt:'500000000'"),
        ],
        'edges': [
            ("MATCH (p:vt_psn {psn_id:'PSN-GB-A01'}),(c:vt_case {flnm:'SIM-GB-2026-001'}) CREATE (p)-[:suspect_in {role:'운영자'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-GB-A02'}),(c:vt_case {flnm:'SIM-GB-2026-001'}) CREATE (p)-[:suspect_in {role:'총판'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-GB-M01'}),(c:vt_case {flnm:'SIM-GB-2026-001'}) CREATE (p)-[:witness_in]->(c)", 'witness_in'),
            # 조직 소속
            ("MATCH (p:vt_psn {psn_id:'PSN-GB-A01'}),(o:vt_org {org_id:'ORG-GB-01'}) CREATE (p)-[:member_of {role:'두목'}]->(o)", 'member_of'),
            ("MATCH (p:vt_psn {psn_id:'PSN-GB-A02'}),(o:vt_org {org_id:'ORG-GB-01'}) CREATE (p)-[:member_of {role:'총판'}]->(o)", 'member_of'),
            # 사이트 운영 ← NEW
            ("MATCH (o:vt_org {org_id:'ORG-GB-01'}),(s:vt_site {site_id:'SITE-GB-01'}) CREATE (o)-[:operates {role:'개설/운영', since:'2025-06-01'}]->(s)", 'operates'),
            # 해외 서버 호스팅 ← NEW
            ("MATCH (ip:vt_ip {ip_id:'IP-GB-01'}),(s:vt_site {site_id:'SITE-GB-01'}) CREATE (ip)-[:hosts {server_type:'도박서버', country:'PHL'}]->(s)", 'hosts'),
            # 국내 접속 IP
            ("MATCH (ip:vt_ip {ip_id:'IP-GB-02'}),(s:vt_site {site_id:'SITE-GB-01'}) CREATE (ip)-[:accessed_from]->(s)", 'accessed_from'),
            # 총판이 회원 모집 ← NEW
            ("MATCH (a:vt_psn {psn_id:'PSN-GB-A02'}),(m:vt_psn {psn_id:'PSN-GB-M01'}) CREATE (a)-[:recruits {method:'카카오채팅', commission_rate:0.1}]->(m)", 'recruits'),
            # 자금 흐름
            ("MATCH (p:vt_psn {psn_id:'PSN-GB-A01'}),(b:vt_bacnt {acnt_id:'ACNT-GB-01'}) CREATE (p)-[:controls]->(b)", 'controls'),
            ("MATCH (p:vt_psn {psn_id:'PSN-GB-A01'}),(w:vt_crypto {wallet_id:'WALLET-GB-01'}) CREATE (p)-[:owns]->(w)", 'owns'),
            ("MATCH (b1:vt_bacnt {acnt_id:'ACNT-GB-01'}),(b2:vt_bacnt {acnt_id:'ACNT-GB-02'}) CREATE (b1)-[:transferred_to {note:'세탁'}]->(b2)", 'transferred_to'),
        ],
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SIM-DA: 대포통장
    # 흐름: 모집책 → 명의자 섭외 → 통장 양도 → 여러 사기에 활용
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'ccop_sim_da': {
        'name': '대포통장',
        'case_id': 'SIM-DA-2026-001',
        'nodes': [
            ("vt_psn",  "psn_id:'PSN-DA-A01', name:'오모집', type:'피의자'"),   # 모집책
            ("vt_psn",  "psn_id:'PSN-DA-N01', name:'서명의1', type:'피의자'"),  # 명의자1
            ("vt_psn",  "psn_id:'PSN-DA-N02', name:'전명의2', type:'피의자'"),  # 명의자2
            ("vt_psn",  "psn_id:'PSN-DA-U01', name:'실사용자_보이스피싱조직', type:'피의자'"),
            ("vt_id",   "id_id:'ID-DA-01', id_val:'알바구함_고수익', platform:'중고나라'"),  # 모집 광고
            ("vt_msg",  "msg_id:'MSG-DA-01', msg_type:'문자', content:'통장 빌려주면 일당 30만원, 010-5555-6666으로 연락', is_phishing:false"),
            ("vt_bacnt","acnt_id:'ACNT-DA-01', actno:'020-1111-111111', bank_cd:'020', holder:'서명의1', acnt_type:'대포통장'"),
            ("vt_bacnt","acnt_id:'ACNT-DA-02', actno:'090-2222-222222', bank_cd:'090', holder:'전명의2', acnt_type:'대포통장'"),
            ("vt_case", "flnm:'SIM-DA-2026-001', crime_type:'대포통장', crime_method:'모집형', damage_amt:'0'"),
        ],
        'edges': [
            ("MATCH (p:vt_psn {psn_id:'PSN-DA-A01'}),(c:vt_case {flnm:'SIM-DA-2026-001'}) CREATE (p)-[:suspect_in {role:'모집책'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-DA-N01'}),(c:vt_case {flnm:'SIM-DA-2026-001'}) CREATE (p)-[:suspect_in {role:'명의제공자'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-DA-N02'}),(c:vt_case {flnm:'SIM-DA-2026-001'}) CREATE (p)-[:suspect_in {role:'명의제공자'}]->(c)", 'suspect_in'),
            # 모집 광고 게시
            ("MATCH (p:vt_psn {psn_id:'PSN-DA-A01'}),(i:vt_id {id_id:'ID-DA-01'}) CREATE (p)-[:uses_id {purpose:'대포통장모집광고'}]->(i)", 'uses_id'),
            # 명의자 모집 ← NEW
            ("MATCH (a:vt_psn {psn_id:'PSN-DA-A01'}),(n:vt_psn {psn_id:'PSN-DA-N01'}) CREATE (a)-[:recruits {method:'알바광고', reward:'30만원/통장'}]->(n)", 'recruits'),
            ("MATCH (a:vt_psn {psn_id:'PSN-DA-A01'}),(n:vt_psn {psn_id:'PSN-DA-N02'}) CREATE (a)-[:recruits {method:'지인소개'}]->(n)", 'recruits'),
            # 명의 등록 vs 실 지배
            ("MATCH (n:vt_psn {psn_id:'PSN-DA-N01'}),(b:vt_bacnt {acnt_id:'ACNT-DA-01'}) CREATE (n)-[:has_account {note:'명의만 보유'}]->(b)", 'has_account'),
            ("MATCH (n:vt_psn {psn_id:'PSN-DA-N02'}),(b:vt_bacnt {acnt_id:'ACNT-DA-02'}) CREATE (n)-[:has_account {note:'명의만 보유'}]->(b)", 'has_account'),
            ("MATCH (u:vt_psn {psn_id:'PSN-DA-U01'}),(b:vt_bacnt {acnt_id:'ACNT-DA-01'}) CREATE (u)-[:controls {method:'통장양도', verified:true}]->(b)", 'controls'),
            ("MATCH (u:vt_psn {psn_id:'PSN-DA-U01'}),(b:vt_bacnt {acnt_id:'ACNT-DA-02'}) CREATE (u)-[:controls {method:'통장양도'}]->(b)", 'controls'),
            # 계좌 간 이체 세탁
            ("MATCH (b1:vt_bacnt {acnt_id:'ACNT-DA-01'}),(b2:vt_bacnt {acnt_id:'ACNT-DA-02'}) CREATE (b1)-[:transferred_to {note:'세탁이체'}]->(b2)", 'transferred_to'),
        ],
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SIM-DR: 사이버 마약
    # 흐름: 텔레그램 채널 개설 → 판매원 모집 → 암호화폐 결제 → 위치 거래
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'ccop_sim_dr': {
        'name': '사이버마약',
        'case_id': 'SIM-DR-2026-001',
        'nodes': [
            ("vt_psn",  "psn_id:'PSN-DR-A01', name:'마공급', type:'피의자'"),    # 공급책
            ("vt_psn",  "psn_id:'PSN-DR-A02', name:'마판매1', type:'피의자'"),   # 판매원
            ("vt_psn",  "psn_id:'PSN-DR-A03', name:'마판매2', type:'피의자'"),   # 판매원
            ("vt_psn",  "psn_id:'PSN-DR-B01', name:'마구매자', type:'피의자'"),  # 구매자
            ("vt_id",   "id_id:'ID-DR-01', id_val:'@drug_market_kr', platform:'텔레그램', channel_type:'마약거래채널'"),
            ("vt_id",   "id_id:'ID-DR-02', id_val:'@판매1_bot', platform:'텔레그램'"),
            ("vt_msg",  "msg_id:'MSG-DR-01', msg_type:'텔레그램', content:'필로폰 1g - BTC 0.05', is_phishing:false"),
            ("vt_crypto","wallet_id:'WALLET-DR-01', address:'1DrV5RFKPtkMJpfT6Q6aY2M6XRBX7Xzme', coin_type:'BTC'"),
            ("vt_crypto","wallet_id:'WALLET-DR-02', address:'3GRdnTq18LyNveWa1gQJcgp8qEnzijv5vR', coin_type:'BTC'"),
            ("vt_loc",  "loc_id:'LOC-DR-01', loc_name:'서울 강남구 역삼동 CU편의점 앞', loc_type:'마약거래지점', lat:'37.498', lon:'127.028'"),
            ("vt_movement","mov_id:'MOV-DR-01', mov_type:'cell', timestamp:'2026-03-15 22:00:00', cell_id:'CELL-강남-0099'"),
            ("vt_case", "flnm:'SIM-DR-2026-001', crime_type:'사이버마약', crime_method:'텔레그램채널형', damage_amt:'0'"),
        ],
        'edges': [
            ("MATCH (p:vt_psn {psn_id:'PSN-DR-A01'}),(c:vt_case {flnm:'SIM-DR-2026-001'}) CREATE (p)-[:suspect_in {role:'공급책'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-DR-A02'}),(c:vt_case {flnm:'SIM-DR-2026-001'}) CREATE (p)-[:suspect_in {role:'판매원'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-DR-B01'}),(c:vt_case {flnm:'SIM-DR-2026-001'}) CREATE (p)-[:suspect_in {role:'구매자'}]->(c)", 'suspect_in'),
            # 채널 운영 ← NEW
            ("MATCH (p:vt_psn {psn_id:'PSN-DR-A01'}),(i:vt_id {id_id:'ID-DR-01'}) CREATE (p)-[:operates {role:'채널관리자', method:'텔레그램비밀채널'}]->(i)", 'operates'),
            # 판매원 모집 ← NEW
            ("MATCH (a:vt_psn {psn_id:'PSN-DR-A01'}),(s:vt_psn {psn_id:'PSN-DR-A02'}) CREATE (a)-[:recruits {method:'텔레그램DM', reward:'수익30%'}]->(s)", 'recruits'),
            ("MATCH (a:vt_psn {psn_id:'PSN-DR-A01'}),(s:vt_psn {psn_id:'PSN-DR-A03'}) CREATE (a)-[:recruits {method:'텔레그램DM'}]->(s)", 'recruits'),
            # 판매원 채널 운영
            ("MATCH (p:vt_psn {psn_id:'PSN-DR-A02'}),(i:vt_id {id_id:'ID-DR-02'}) CREATE (p)-[:operates {role:'판매봇운영'}]->(i)", 'operates'),
            # 거래 메시지
            ("MATCH (i:vt_id {id_id:'ID-DR-01'}),(m:vt_msg {msg_id:'MSG-DR-01'}) CREATE (i)-[:sent_msg]->(m)", 'sent_msg'),
            # 가상화폐 결제
            ("MATCH (p:vt_psn {psn_id:'PSN-DR-A01'}),(w:vt_crypto {wallet_id:'WALLET-DR-01'}) CREATE (p)-[:owns]->(w)", 'owns'),
            ("MATCH (p:vt_psn {psn_id:'PSN-DR-B01'}),(w:vt_crypto {wallet_id:'WALLET-DR-02'}) CREATE (p)-[:owns]->(w)", 'owns'),
            ("MATCH (w1:vt_crypto {wallet_id:'WALLET-DR-02'}),(w2:vt_crypto {wallet_id:'WALLET-DR-01'}) CREATE (w1)-[:transferred_to {amount:'0.05BTC', note:'마약대금'}]->(w2)", 'transferred_to'),
            # 거래 위치
            ("MATCH (p:vt_psn {psn_id:'PSN-DR-A02'}),(m:vt_movement {mov_id:'MOV-DR-01'}) CREATE (p)-[:recorded_in {source:'기지국'}]->(m)", 'recorded_in'),
            ("MATCH (m:vt_movement {mov_id:'MOV-DR-01'}),(l:vt_loc {loc_id:'LOC-DR-01'}) CREATE (m)-[:occurred_at]->(l)", 'occurred_at'),
        ],
    },

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SIM-TG: 텔레그램 범죄 (불법촬영물 유포 / N번방 유형)
    # 흐름: 채널 개설 → 유료 멤버십 → 불법파일 유포 → 가상화폐 수익
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    'ccop_sim_tg': {
        'name': '텔레그램범죄',
        'case_id': 'SIM-TG-2026-001',
        'nodes': [
            ("vt_psn",  "psn_id:'PSN-TG-A01', name:'양관리', type:'피의자'"),   # 채널 관리자
            ("vt_psn",  "psn_id:'PSN-TG-A02', name:'권업로드', type:'피의자'"),  # 업로더
            ("vt_psn",  "psn_id:'PSN-TG-M01', name:'익명1', type:'피의자'"),    # 유료 멤버
            ("vt_id",   "id_id:'ID-TG-01', id_val:'@illegal_room_master', platform:'텔레그램', channel_type:'불법촬영물유포채널'"),
            ("vt_id",   "id_id:'ID-TG-02', id_val:'@uploader_99', platform:'텔레그램'"),
            ("vt_file", "file_id:'FILE-TG-01', file_name:'피해자A_불법촬영.mp4', file_type:'MP4', malware_type:'불법촬영물', hash_val:'a1b2c3d4e5f6789012345678'"),
            ("vt_file", "file_id:'FILE-TG-02', file_name:'피해자B_유포물.mp4', file_type:'MP4', malware_type:'불법촬영물', hash_val:'b2c3d4e5f6789012345679'"),
            ("vt_msg",  "msg_id:'MSG-TG-01', msg_type:'텔레그램', content:'VIP방 입장 BTC 0.1 입금 후 인증', is_phishing:false"),
            ("vt_crypto","wallet_id:'WALLET-TG-01', address:'1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf8N', coin_type:'BTC'"),
            ("vt_case", "flnm:'SIM-TG-2026-001', crime_type:'텔레그램불법촬영물유포', crime_method:'유료채널형', damage_amt:'0'"),
        ],
        'edges': [
            ("MATCH (p:vt_psn {psn_id:'PSN-TG-A01'}),(c:vt_case {flnm:'SIM-TG-2026-001'}) CREATE (p)-[:suspect_in {role:'채널관리자'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-TG-A02'}),(c:vt_case {flnm:'SIM-TG-2026-001'}) CREATE (p)-[:suspect_in {role:'업로더'}]->(c)", 'suspect_in'),
            ("MATCH (p:vt_psn {psn_id:'PSN-TG-M01'}),(c:vt_case {flnm:'SIM-TG-2026-001'}) CREATE (p)-[:suspect_in {role:'유포참여자'}]->(c)", 'suspect_in'),
            # 채널 운영 ← NEW
            ("MATCH (p:vt_psn {psn_id:'PSN-TG-A01'}),(i:vt_id {id_id:'ID-TG-01'}) CREATE (p)-[:operates {role:'채널관리자/개설자'}]->(i)", 'operates'),
            ("MATCH (p:vt_psn {psn_id:'PSN-TG-A02'}),(i:vt_id {id_id:'ID-TG-02'}) CREATE (p)-[:operates {role:'업로더'}]->(i)", 'operates'),
            # 채널 멤버
            ("MATCH (p:vt_psn {psn_id:'PSN-TG-M01'}),(i:vt_id {id_id:'ID-TG-01'}) CREATE (p)-[:member_of {membership:'VIP유료', fee:'0.1BTC'}]->(i)", 'member_of'),
            # 불법 파일 채널에 포함 ← NEW
            ("MATCH (i:vt_id {id_id:'ID-TG-01'}),(f:vt_file {file_id:'FILE-TG-01'}) CREATE (i)-[:contains_file {distributed_dt:'2026-03-10'}]->(f)", 'contains_file'),
            ("MATCH (i:vt_id {id_id:'ID-TG-02'}),(f:vt_file {file_id:'FILE-TG-02'}) CREATE (i)-[:contains_file {distributed_dt:'2026-03-11'}]->(f)", 'contains_file'),
            # 메시지 발송
            ("MATCH (i:vt_id {id_id:'ID-TG-01'}),(m:vt_msg {msg_id:'MSG-TG-01'}) CREATE (i)-[:sent_msg]->(m)", 'sent_msg'),
            # 수익 가상화폐
            ("MATCH (p:vt_psn {psn_id:'PSN-TG-A01'}),(w:vt_crypto {wallet_id:'WALLET-TG-01'}) CREATE (p)-[:owns]->(w)", 'owns'),
            # 공범 관계
            ("MATCH (a1:vt_psn {psn_id:'PSN-TG-A01'}),(a2:vt_psn {psn_id:'PSN-TG-A02'}) CREATE (a1)-[:accomplice_of]->(a2)", 'accomplice_of'),
        ],
    },
}

# ── 엣지 사용 빈도 집계 ────────────────────────────────────────────────
def analyze_edge_usage(scenarios):
    edge_usage = defaultdict(list)
    for graph_key, scenario in scenarios.items():
        crime_type = scenario['name']
        for _, edge_type in scenario['edges']:
            edge_usage[edge_type].append(crime_type)
    return edge_usage

def run_simulation():
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor()

    results = {}

    for graph_key, scenario in SCENARIOS.items():
        print(f"\n{'='*60}")
        print(f"  [{scenario['name']}] {scenario['case_id']}")
        print(f"{'='*60}")

        # 그래프 재생성
        try:
            cur.execute(f"DROP GRAPH {graph_key} CASCADE")
        except Exception:
            pass
        cur.execute(f"CREATE GRAPH {graph_key}")
        cur.execute(f"SET graph_path = {graph_key}")

        # 노드 레이블 등록
        all_vlabels = set(label for label, _ in scenario['nodes'])
        all_vlabels.add('vt_impersonation')
        for v in all_vlabels:
            try:
                cur.execute(f"CREATE VLABEL IF NOT EXISTS {v}")
            except Exception as e:
                print(f"  ⚠️ vlabel {v}: {e}")

        # 엣지 레이블 등록
        all_elabels = set(et for _, et in scenario['edges'])
        all_elabels.update(CANDIDATE_EDGES)
        for e in all_elabels:
            try:
                cur.execute(f"CREATE ELABEL IF NOT EXISTS {e}")
            except Exception as e2:
                pass

        # 노드 삽입
        node_count = 0
        for label, props in scenario['nodes']:
            try:
                cur.execute(f"CREATE (:{label} {{{props}}})")
                node_count += 1
            except Exception as e:
                print(f"  ⚠️ 노드 {label}: {e}")

        # 엣지 삽입
        edge_count = 0
        used_edges = []
        for cypher, edge_type in scenario['edges']:
            try:
                cur.execute(cypher)
                edge_count += 1
                used_edges.append(edge_type)
            except Exception as e:
                print(f"  ⚠️ 엣지 {edge_type}: {e}")

        print(f"  ✅ 노드 {node_count}개, 엣지 {edge_count}개 생성")
        print(f"  📎 사용 엣지: {sorted(set(used_edges))}")
        results[scenario['name']] = set(used_edges)

    conn.close()
    return results

def print_analysis(results):
    all_edges = sorted(set(e for edges in results.values() for e in edges))
    crime_types = list(results.keys())

    print(f"\n\n{'='*80}")
    print("  엣지 사용 패턴 분석 — 8대 범죄 유형")
    print(f"{'='*80}")
    print(f"{'엣지':<22}", end="")
    for ct in crime_types:
        print(f"  {ct[:4]}", end="")
    print("  | 커버")

    new_edges = {'operates', 'hosts', 'blackmails', 'recruits', 'contains_file', 'located_at'}

    for edge in all_edges:
        marker = " ★" if edge in new_edges else "  "
        print(f"{marker}{edge:<20}", end="")
        cover_count = 0
        for ct in crime_types:
            if edge in results[ct]:
                print("  ✅  ", end="")
                cover_count += 1
            else:
                print("  ·   ", end="")
        print(f"  | {cover_count}/{len(crime_types)}")

    print(f"\n★ = 신규 후보 엣지")
    print(f"\n신규 엣지 커버리지:")
    for edge in new_edges:
        count = sum(1 for edges in results.values() if edge in edges)
        crimes = [ct for ct, edges in results.items() if edge in edges]
        print(f"  {edge:<20} {count}개 사건: {', '.join(crimes)}")

if __name__ == '__main__':
    print("🔬 온톨로지 v3.4 시뮬레이션 시작...")
    results = run_simulation()
    print_analysis(results)
    print("\n✅ 시뮬레이션 완료")
