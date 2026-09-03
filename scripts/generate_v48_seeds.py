#!/usr/bin/env python3
"""T2C v48 학습 시드 생성 — 70문항 벤치 실패 유형(A~E) 기반, 실행검증 필수.

docs/T2C_V48_SEED_DESIGN.md 스펙 구현:
  · 템플릿 × 실값 슬롯(통합 그래프 실측) × 표현 변형 → 후보 생성
  · 정답 Cypher를 ccop_ep_integrated 에서 **실행해 비공집합(count류는 성공)만 채택**
  · system 프롬프트 = 통합 그래프 실측 스키마 경로(신규 suspect_in·performed_by 포함)
  · 출력: train/t2c_v48_new_msg.json (v47과 동일 {system, messages} 포맷)

실행: python3 scripts/generate_v48_seeds.py   (OpenAI 불요 — 결정론 템플릿)
"""
import sys
import os
import json
import itertools
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from dotenv import load_dotenv
load_dotenv()
import psycopg2

GRAPH = 'ccop_ep_integrated'
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'train', 't2c_v48_new_msg.json')

conn = psycopg2.connect(dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'),
                        password=os.getenv('DB_PASSWORD'), host=os.getenv('DB_HOST'),
                        port=os.getenv('DB_PORT'))
conn.autocommit = True
cur = conn.cursor()
cur.execute(f"SET graph_path = {GRAPH}")


def q(c):
    cur.execute(c)
    return cur.fetchall()


# ── system 프롬프트: 실측 스키마 경로 (v47 방식 + V4.8 신규 포함) ──
paths = q("MATCH (a)-[r]->(b) RETURN DISTINCT label(a), type(r), label(b)")
labels = sorted({r[0] for r in q("MATCH (n) RETURN DISTINCT label(n)")})
path_str = "; ".join(f"({a})-[{e}]->({b})" for a, e, b in sorted(paths))
SYSTEM = ("당신은 CCOP 사이버범죄 수사 그래프의 Text2Cypher 변환기입니다. "
          "실제 스키마에 존재하는 라벨/관계/속성만 사용해 네이티브 Cypher를 생성하세요.\n"
          f"노드: {', '.join(labels)}\n관계 경로: {path_str}\n"
          "주요 속성: vt_bacnt(account_no, bank_nm, dpstr, tier, evid_grade, ep_count) · "
          "vt_psn(name, role, evid_grade) · vt_ip(ip_addr, country, ep_count) · "
          "vt_telno(telno) · vt_id(id_val, platform) · vt_case(flnm, case_type) · "
          "vt_movement(mov_id, mov_type, mov_dt, dest) · "
          "transferred_to(first_dlng_dt, last_dlng_dt, total_amount) · contacted(first_dt, last_dt)")

# ── 실값 슬롯 (통합 그래프 실측) ──
V = {}
V['bank'] = [r[0] for r in q("MATCH (b:vt_bacnt) WHERE b.bank_nm IS NOT NULL RETURN DISTINCT b.bank_nm LIMIT 6")]
V['suspect'] = [r[0] for r in q("MATCH (p:vt_psn)-[:suspect_in]->() RETURN DISTINCT p.name")]
V['tier'] = [r[0] for r in q("MATCH (b:vt_bacnt) WHERE b.tier IS NOT NULL RETURN DISTINCT b.tier")]
V['psn_named'] = [r[0] for r in q("MATCH (p:vt_psn)-[:has_account]->() RETURN DISTINCT p.name LIMIT 12") if r[0]]
V['acct_hub'] = [r[0] for r in q("MATCH (a)-[:transferred_to]->(b:vt_bacnt) RETURN b.account_no, count(*) AS c ORDER BY c DESC LIMIT 6")]
V['month'] = ['3', '4', '5']
V['grade'] = ['A', 'B']

ASK = ['보여줘', '알려줘', '조회해줘', '찾아줘', '목록 뽑아줘']   # 표현 변형


def wrap(cy):
    return cy   # native cypher (v47 학습 포맷과 동일 — SQL wrap은 앱단)


SEEDS = []   # (category, question, cypher, verify_mode)  verify: 'rows'|'exec'

def add(cat, question, cypher, verify='rows'):
    SEEDS.append((cat, question, cypher, verify))


# ══ A. 속성 정합 (환각 속성 → 실스키마) ══
for g in V['grade']:
    for lbl, ko in [('vt_psn', '인물'), ('vt_bacnt', '계좌')]:
        for a in ASK[:3]:
            add('A', f"증거등급이 {g}인 {ko}를 {a}",
                f"MATCH (n:{lbl}) WHERE n.evid_grade = '{g}' RETURN n LIMIT 50")
for t in V['tier']:
    for a in ASK[:3]:
        add('A', f"{t} 계좌를 {a}", f"MATCH (b:vt_bacnt) WHERE b.tier = '{t}' RETURN b")
for bk in V['bank']:
    for suf in ['은행', '']:
        add('A', f"{bk}{suf} 계좌 중 명의자가 있는 것을 보여줘",
            f"MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) WHERE b.bank_nm = '{bk}' RETURN p, b")
add('A', "ep_count가 3 이상인 IP를 보여줘", "MATCH (ip:vt_ip) WHERE ip.ep_count >= 3 RETURN ip")
add('A', "여러 EP에 등장한 계좌를 찾아줘", "MATCH (b:vt_bacnt) WHERE b.ep_count >= 2 RETURN b")
add('A', "5개 이상 EP에서 나온 IP는?", "MATCH (ip:vt_ip) WHERE ip.ep_count >= 5 RETURN ip")

# ══ B. 신규 서사 (suspect_in·performed_by·movement·role) ══
for a in ASK:
    add('B', f"피의자를 전부 {a}", "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) RETURN p, c")
    add('B', f"이 사건의 피의자들을 {a}", "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) RETURN p, c")
add('B', "주범은 누구야?", "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) WHERE p.role CONTAINS '주범' RETURN p")
add('B', "주범을 찾아줘", "MATCH (p:vt_psn) WHERE p.role CONTAINS '주범' RETURN p")
add('B', "공범들을 보여줘", "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) WHERE p.role CONTAINS '공범' RETURN p")
for nm in V['suspect']:
    add('B', f"{nm}의 출국 기록을 보여줘",
        f"MATCH (m:vt_movement)-[:performed_by]->(p:vt_psn) WHERE p.name = '{nm}' RETURN m, p")
    add('B', f"{nm}은 언제 출국했어?",
        f"MATCH (m:vt_movement)-[:performed_by]->(p:vt_psn) WHERE p.name = '{nm}' RETURN m.mov_dt, m.dest")
for a in ASK[:3]:
    add('B', f"중국으로 출국한 사람들을 {a}",
        "MATCH (m:vt_movement)-[:performed_by]->(p:vt_psn) WHERE m.dest = '중국' RETURN p, m")
add('B', "출국한 피의자 수를 세줘",
    "MATCH (m:vt_movement)-[:performed_by]->(p:vt_psn)-[:suspect_in]->() RETURN count(DISTINCT p)", 'exec')
add('B', "피의자 수는 몇 명이야?", "MATCH (p:vt_psn)-[:suspect_in]->() RETURN count(DISTINCT p)", 'exec')
add('B', "조정모가 사용한 전화번호와 카카오톡 계정을 보여줘",
    "MATCH (p:vt_psn {name: '조정모'}) OPTIONAL MATCH (p)-[:owns_phone]->(t:vt_telno) OPTIONAL MATCH (p)-[:uses_id]->(d:vt_id) RETURN p, t, d")
add('B', "4차 해외송금 수취 계좌들을 보여줘", "MATCH (b:vt_bacnt) WHERE b.tier CONTAINS '해외송금' RETURN b")
add('B', "해외로 송금된 계좌 목록", "MATCH (b:vt_bacnt) WHERE b.tier CONTAINS '해외송금' RETURN b")
add('B', "황민규가 피해자인 사건을 보여줘",
    "MATCH (p:vt_psn {name: '황민규'})-[:victim_in]->(c:vt_case) RETURN p, c")
add('B', "동일인 후보 쌍을 보여줘", "MATCH (a:vt_psn)-[s:same_as]->(b:vt_psn) RETURN a, s, b")

# ══ C. 시간 필터 ══
for m in V['month']:
    for a in ASK[:2]:
        add('C', f"2017년 {m}월에 발생한 이체 내역을 {a}",
            f"MATCH (a:vt_bacnt)-[e:transferred_to]->(b:vt_bacnt) WHERE e.first_dlng_dt STARTS WITH '2017-0{m}' RETURN a, e, b")
        add('C', f"{m}월에 있었던 통화 내역을 {a}",
            f"MATCH (a)-[e:contacted]->(b) WHERE e.first_dt STARTS WITH '2017-0{m}' RETURN a, e, b LIMIT 100")
add('C', "2017-03-21 이후의 이체를 보여줘",
    "MATCH (a:vt_bacnt)-[e:transferred_to]->(b:vt_bacnt) WHERE e.first_dlng_dt >= '2017-03-21' RETURN a, e, b")
add('C', "3월 15일 이전 이체 내역",
    "MATCH (a:vt_bacnt)-[e:transferred_to]->(b:vt_bacnt) WHERE e.first_dlng_dt < '2017-03-15' RETURN a, e, b")
add('C', "3월 1일부터 3월 15일 사이 이체 건수",
    "MATCH ()-[e:transferred_to]->() WHERE e.first_dlng_dt >= '2017-03-01' AND e.first_dlng_dt <= '2017-03-15' RETURN count(e)", 'exec')
add('C', "2017년 5월에 중국으로 출국한 기록",
    "MATCH (m:vt_movement)-[:performed_by]->(p:vt_psn) WHERE m.mov_dt STARTS WITH '2017-05' AND m.dest = '중국' RETURN m, p")
add('C', "5월 10일 이후 출국한 사람",
    "MATCH (m:vt_movement)-[:performed_by]->(p:vt_psn) WHERE m.mov_dt >= '2017-05-10' RETURN p, m")
add('C', "가장 이른 이체 날짜는?",
    "MATCH ()-[e:transferred_to]->() WHERE e.first_dlng_dt IS NOT NULL RETURN min(e.first_dlng_dt)", 'exec')
add('C', "가장 최근 통화는 언제야?",
    "MATCH ()-[e:contacted]->() WHERE e.first_dt IS NOT NULL RETURN max(e.first_dt)", 'exec')

# ══ D. 집계 고급 (관계 count·상위N·그룹핑) ══
add('D', "이체를 가장 많이 받은 계좌 5개",
    "MATCH (a)-[e:transferred_to]->(b:vt_bacnt) WITH b, count(e) AS cnt RETURN b, cnt ORDER BY cnt DESC LIMIT 5")
add('D', "이체를 가장 많이 보낸 계좌 5개",
    "MATCH (a:vt_bacnt)-[e:transferred_to]->(b) WITH a, count(e) AS cnt RETURN a, cnt ORDER BY cnt DESC LIMIT 5")
add('D', "통화 횟수가 가장 많은 전화번호는?",
    "MATCH (t:vt_telno)-[e:contacted]-() WITH t, count(e) AS cnt RETURN t, cnt ORDER BY cnt DESC LIMIT 5")
add('D', "은행별 계좌 수를 알려줘",
    "MATCH (b:vt_bacnt) WHERE b.bank_nm IS NOT NULL RETURN b.bank_nm, count(b)", 'exec')
add('D', "계좌를 가장 많이 가진 사람 5명",
    "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) WITH p, count(b) AS cnt RETURN p, cnt ORDER BY cnt DESC LIMIT 5")
add('D', "연결이 가장 많은 IP 5개",
    "MATCH (ip:vt_ip)<-[e:used_ip]-() WITH ip, count(e) AS cnt RETURN ip, cnt ORDER BY cnt DESC LIMIT 5")
add('D', "피해자가 가장 많은 사건 5건",
    "MATCH (p:vt_psn)-[:victim_in]->(c:vt_case) WITH c, count(p) AS cnt RETURN c, cnt ORDER BY cnt DESC LIMIT 5")

# ══ E. 다중 조건 ══
for bk in V['bank'][:4]:
    add('E', f"{bk} 계좌 중 이체 내역이 있는 것",
        f"MATCH (b:vt_bacnt)-[e:transferred_to]-() WHERE b.bank_nm = '{bk}' RETURN DISTINCT b")
add('E', "기업은행이면서 3차집금인 계좌",
    "MATCH (b:vt_bacnt) WHERE b.bank_nm = '기업' AND b.tier CONTAINS '3차' RETURN b")
add('E', "피어스미디어 소속이면서 명의자가 있는 계좌",
    "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt)-[:belongs_to]->(o:vt_org {org_name: '피어스미디어'}) RETURN p, b")
add('E', "3월에 이체하고 4월에도 이체한 계좌",
    "MATCH (b:vt_bacnt)-[e1:transferred_to]-() , (b)-[e2:transferred_to]-() "
    "WHERE e1.first_dlng_dt STARTS WITH '2017-03' AND e2.first_dlng_dt STARTS WITH '2017-04' RETURN DISTINCT b")
add('E', "증거등급 A이면서 여러 EP에 나온 계좌",
    "MATCH (b:vt_bacnt) WHERE b.evid_grade = 'A' AND b.ep_count >= 2 RETURN b")

# ══ 실행 검증 ══
kept, dropped = [], []
for cat, question, cy, verify in SEEDS:
    try:
        cur.execute(cy)
        rows = cur.fetchall()
        ok = (len(rows) > 0) if verify == 'rows' else True
        # rows 모드에서 전부 NULL인 행뿐이면 탈락
        if ok and verify == 'rows' and all(all(v is None for v in r) for r in rows[:5]):
            ok = False
        (kept if ok else dropped).append((cat, question, cy))
    except Exception as e:
        dropped.append((cat, question, f"ERR {str(e)[:60]}"))

# ── 출력 (v47 messages 포맷) ──
out = [{"system": SYSTEM,
        "messages": [{"role": "user", "content": qst},
                     {"role": "assistant", "content": cy}]}
       for cat, qst, cy in kept]
os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

from collections import Counter
print(f"[생성] 후보 {len(SEEDS)} → 채택 {len(kept)} · 탈락 {len(dropped)}")
print("  채택 분포:", dict(Counter(c for c, _, _ in kept)))
if dropped[:5]:
    print("  탈락 예:", [(c, d[:40]) for c, d, _ in dropped[:5]])
print(f"[저장] {OUT}")
print(f"[system 스키마] 라벨 {len(labels)} · 경로 {len(paths)}")
conn.close()
