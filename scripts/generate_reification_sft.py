#!/usr/bin/env python3
"""V4.4 reification SFT 학습셋 — v46 증강판 (v45 78샘플 실패 교훈 반영).
개선: ① 값 풀·템플릿 대폭 증강(수백~천) ② 편향 케이스(access_via·transferred_to) 가중
      ③ 기존 데이터 믹스(회귀 방지 — v45는 reification만 학습해 기존 능력 훼손).
포맷: v42 messages + system(native Cypher). 출력: data/t2c_v46_reification_mix_msg.json
"""
import json, os, random
random.seed(46)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_base = json.load(open(os.path.join(ROOT, 'train/t2c_v37_train_msg.json'), encoding='utf-8'))
SYSTEM = _base[0]['system']

# ── 값 풀 (대폭 확대) ──────────────────────────────────
IPS = list({f'{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}' for _ in range(50)})
TELS = list({f'010-{random.randint(1000,9999)}-{random.randint(1000,9999)}' for _ in range(50)})
ACCTS = list({f'{random.choice(["1002","110","333","1005","356"])}-{random.randint(10,999)}-{random.randint(100000,999999)}' for _ in range(40)})
IDS = ['pokpok1270','zion7950','darkseller99','ghost_trader','anon4423','crypto_king7','deal_master','safe_trade22',
       'user_9981','hidden_wolf','night_owl3','moneyflow','traderX','silent_k','blackcat77','vipdeal','fastcash9','ninja_seller','coin_hunter','proxy_man']
WALLETS = ['0xA1B2C3D4E5','bc1qxy2kg9','0xDEADBEEF01','TRxS9fLm2','0x77aabbcc','bc1q8h3d','0x9f8e7d','TLm4kP','0xCAFE01','bc1qwww','0x1234ab','TRabcd','0xF00Die','bc1qzzz','0x0Ff1ce']
LOCS = ['강남역 3번 출구','서초구 반포동','수원시 영통구','부산 해운대','인천 송도','대전 유성구','성남 분당','일산 호수공원','청담동 카페','홍대입구','신촌 로터리','판교역','잠실 롯데','목동 사거리','부천 상동','안양 범계','천안 두정동','광주 상무지구','대구 동성로','울산 삼산동']


def s(u, c):
    return {"messages": [{"role": "user", "content": u}, {"role": "assistant", "content": c}], "system": SYSTEM}


samples = []

# ── 패턴 A-1: access_via (IP→전화) 편향 교정 가중 ──────
q_tpls = ["IP {ip}에 접속한 전화번호를 찾아줘", "{ip}로 접속한 통신번호는?", "{ip} 접속 이력의 휴대전화 번호",
          "IP주소 {ip}에서 접속한 전화번호 목록", "{ip}에 붙은 전화번호 조회"]
for ip in IPS:
    for qt in random.sample(q_tpls, 3):
        samples.append(s(qt.format(ip=ip),
            f"MATCH (ip:vt_ip {{ip_addr: '{ip}'}})<-[:accessed_from]-(a:vt_access)-[:access_via]->(t:vt_telno) RETURN t, a"))
# A-2: 전화→접속 IP (역방향, 편향 핵심)
q_tpls2 = ["전화번호 {tel}이 접속한 IP", "{tel}의 접속 IP 목록", "{tel}이 사용한 접속 IP주소", "{tel} 최종 접속 IP"]
for tel in TELS:
    for qt in random.sample(q_tpls2, 3):
        samples.append(s(qt.format(tel=tel),
            f"MATCH (t:vt_telno {{telno: '{tel}'}})<-[:access_via]-(a:vt_access)-[:accessed_from]->(ip:vt_ip) RETURN ip, a"))
# A-3: IP→계정
for ip in random.sample(IPS, 30):
    for qt in ["IP {ip}에서 접속한 계정", "{ip} 접속 계정 (포털 역조회)", "{ip}로 로그인한 아이디"]:
        samples.append(s(qt.format(ip=ip),
            f"MATCH (ip:vt_ip {{ip_addr: '{ip}'}})<-[:accessed_from]-(a:vt_access)-[:access_via]->(id:vt_id) RETURN id, a"))
# A-4: 계정→접속 IP
for uid in IDS:
    samples.append(s(f"계정 {uid}이 접속한 IP",
        f"MATCH (id:vt_id {{id_val: '{uid}'}})<-[:access_via]-(a:vt_access)-[:accessed_from]->(ip:vt_ip) RETURN ip"))

# ── 패턴 B: transferred_to(crypto) 편향 교정 가중 ──────
q_tt = ["계좌 {acct}에서 가상자산으로 세탁된 자금 흐름", "{acct}의 자금세탁 추적 (가상자산 경유)",
        "{acct}에서 코인으로 세탁된 돈", "{acct} 자금이 가상자산으로 흘러간 경로"]
for acct in ACCTS:
    for qt in random.sample(q_tt, 3):
        samples.append(s(qt.format(acct=acct),
            f"MATCH (b:vt_bacnt {{account_no: '{acct}'}})-[:transferred_to]->(w:vt_crypto) RETURN b, w"))
for w in WALLETS:
    samples.append(s(f"지갑 {w}로 유입된 자금 출처 계좌",
        f"MATCH (b:vt_bacnt)-[:transferred_to]->(w:vt_crypto {{wallet_addr: '{w}'}}) RETURN b, w"))
# via_ip
for acct in random.sample(ACCTS, 25):
    samples.append(s(f"계좌 {acct} 이체에 사용된 접속 IP",
        f"MATCH (b:vt_bacnt {{account_no: '{acct}'}})-[:from_account]->(tr:vt_transfer)-[:via_ip]->(ip:vt_ip) RETURN tr, ip"))
# from/to crypto
for acct in random.sample(ACCTS, 25):
    samples.append(s(f"계좌 {acct}에서 가상자산 지갑으로 전송한 이체",
        f"MATCH (b:vt_bacnt {{account_no: '{acct}'}})-[:from_account]->(tr:vt_transfer)-[:to_account]->(w:vt_crypto) RETURN tr, w"))
# from/to atm
for acct in random.sample(ACCTS, 20):
    samples.append(s(f"계좌 {acct} ATM 현금 인출 내역",
        f"MATCH (b:vt_bacnt {{account_no: '{acct}'}})-[:from_account]->(tr:vt_transfer)-[:to_account]->(atm:vt_atm) RETURN tr, atm"))

# ── 패턴 E ────────────────────────────────────────────
for tel in random.sample(TELS, 30):
    samples.append(s(f"전화번호 {tel}의 통화 발신 위치",
        f"MATCH (t:vt_telno {{telno: '{tel}'}})-[:caller]->(c:vt_call)-[:occurred_at]->(l:vt_loc) RETURN c, l"))
for loc in LOCS:
    samples.append(s(f"{loc}이 언급된 메시지",
        f"MATCH (m:vt_msg)-[:mentions_location]->(l:vt_loc {{place_nm: '{loc}'}}) RETURN m, l"))
for uid in IDS:
    samples.append(s(f"계정 {uid}이 주고받은 메시지 상대",
        f"MATCH (id1:vt_id {{id_val: '{uid}'}})-[:sent_msg]->(m:vt_msg)-[:received_msg]->(id2:vt_id) RETURN m, id2"))

n_reif = len(samples)

# ── 회귀 방지: 기존 데이터 믹스 (reification만 학습 시 기존 능력 훼손 방지) ──
mix = random.sample(_base, min(500, len(_base)))
samples += mix

random.shuffle(samples)
out = os.path.join(ROOT, 'data/t2c_v46_reification_mix_msg.json')
json.dump(samples, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'reification 증강: {n_reif} + 회귀 믹스: {len(mix)} = 총 {len(samples)}')
from collections import Counter
ec = Counter()
for x in samples[:n_reif] if False else samples:
    cy = x['messages'][1]['content']
    for e in ('access_via','via_ip','transferred_to','mentions_location','occurred_at'):
        if f':{e}]' in cy: ec[e] += 1
print('편향 교정 엣지 분포:', dict(ec))
print('저장:', out)
