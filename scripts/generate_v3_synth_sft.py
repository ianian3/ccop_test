#!/usr/bin/env python3
"""
CCOP SFT 데이터 합성 생성기 V3
================================
Auto-Cypher / SynthCypher 방식을 CCOP 도메인에 특화 적용.

전략:
  1. 온톨로지 기반 템플릿 → 실제 DB 값 치환 → SQL-Wrapped Cypher 생성
  2. LLM으로 (Cypher → 자연어 질문) 역생성 (5개 표현 다양화)
  3. 생성 결과를 ShareGPT + Alpaca 양식으로 저장

목표 분포:
  basic     3,500개 (단일 노드 검색)
  direction 4,500개 (엣지 방향 추적)
  filter    4,500개 (숫자/날짜/문자열 필터)
  multihop  5,000개 (2~5홉 체인)
  path      2,500개 (shortestPath)
  b2c       2,500개 (구어체/비격식)
  guardrail   500개 (쓰기 명령 방어)
  ---합계-- 23,000개 (기존 10,143개와 합산 → 33,143개)

실행:
  cd /Users/iankwon/test/coop_v1.0
  python3 scripts/generate_v3_synth_sft.py [--use-llm] [--target 23000]
"""

import os, sys, json, random, argparse, time, re
from datetime import datetime, timedelta
from typing import List, Dict, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# =========================================================
# 출력 경로
# =========================================================
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_SHAREGPT = os.path.join(BASE_DIR, "data", "ccop_v4_synth_sharegpt.json")
OUT_ALPACA   = os.path.join(BASE_DIR, "data", "ccop_v4_synth_alpaca.jsonl")

GRAPH_PATH = "tccop_graph_v6"

# =========================================================
# 도메인 데이터 풀 (실제 수사 데이터 패턴 기반)
# =========================================================
SUSPECTS = [f"피의자{i}" for i in range(1, 51)]
VICTIMS  = [f"피해자{i}" for i in range(1, 31)]
REFS     = [f"참고인{i}" for i in range(1, 21)]
REAL_NAMES = [
    "김철수","이영희","박민준","최지훈","강수진","정보람","윤서준","조민아",
    "한동훈","신예원","장성환","유민지","임재원","오지현","권기현","황소연",
    "문재인","안철수","홍길동","이순신","강감찬","을지문덕","신사임당","유관순",
    "김구","윤봉길","안중근","이봉창","김좌진","박열","손병희","유성룡",
    "보이스피싱총책A","자금세탁책B","현금인출책C","대포통장관리자D","조직폭력배E",
    "조폭대장F","수익금분배자G","통신사기조직원H","전화금융사기범I","사이버범죄자J",
]
PERSONS = SUSPECTS + VICTIMS + REFS + REAL_NAMES

_bank_prefixes = ["110","220","330","440","550","660","770","880","990","101","102","103","104","105"]
_acct_mids = [f"{i:06d}" for i in range(100000, 100300)]
_acct_sufs = [f"{i:02d}" for i in range(10, 100)]
ACCOUNTS = [
    f"{p}-{m}-{s}"
    for p in _bank_prefixes
    for m in _acct_mids[:20]
    for s in _acct_sufs[:5]
][:500]  # 최대 500개

BANKS = [
    "국민은행","신한은행","우리은행","하나은행","기업은행","농협은행",
    "카카오뱅크","토스뱅크","SC제일은행","씨티은행","수협은행","우체국은행",
    "광주은행","전북은행","제주은행","부산은행","대구은행","경남은행",
]

PHONES = (
    [f"100{i:07d}" for i in range(1, 200)] +
    [f"010{i:08d}" for i in range(11112222, 11112422)] +
    [f"010{i:08d}" for i in range(33334444, 33334644)]
)[:400]

IPS = (
    [f"203.108.{i}.{j}" for i in range(1,10) for j in range(1,20)] +
    [f"192.168.{i}.{j}" for i in range(1,5) for j in range(1,30)] +
    [f"61.111.{i}.{j}" for i in range(200,230) for j in range(1,10)] +
    [f"125.209.{i}.{j}" for i in range(220,240) for j in range(1,10)] +
    [f"118.235.{i}.{j}" for i in range(10,30) for j in range(1,10)]
)[:400]

CASES = (
    [f"CASE-2023-{i:03d}" for i in range(1, 150)] +
    [f"CASE-2024-{i:03d}" for i in range(1, 150)] +
    [f"CASE-{i}" for i in range(1, 200)] +
    [f"사건번호-{i:03d}" for i in range(1, 50)] +
    [f"C{i:03d}" for i in range(1, 50)]
)[:500]

AMOUNTS = (
    [str(i * 10000) for i in range(1, 200)] +   # 1만~199만
    [str(i * 100000) for i in range(1, 100)] +  # 10만~990만
    [str(i * 1000000) for i in range(1, 50)] +  # 100만~4900만
    ["50000000","100000000","200000000","500000000"]
)[:300]

CRIMES = [
    "보이스피싱","금융사기","불법도박","자금세탁","사기","횡령","배임","명의도용",
    "전자금융사기","인터넷사기","직거래사기","투자사기","대출사기","취업사기",
    "스미싱","파밍","랜섬웨어","개인정보유출","해킹","불법환전",
]

TIMESTAMPS = (
    [f"2023-{m:02d}-{d:02d} {h:02d}:{mm:02d}:00"
     for m in range(1,13) for d in [1,10,15,20,28]
     for h in [2,3,14,22] for mm in [0,30]][:100] +
    [f"2024-{m:02d}-{d:02d} {h:02d}:{mm:02d}:00"
     for m in range(1,13) for d in [5,12,20,25]
     for h in [1,4,10,23] for mm in [0,15,45]][:100]
)[:150]

DATES = [
    f"2023-{m:02d}-{d:02d}"
    for m in range(1,13) for d in [1,15,28]
] + [
    f"2024-{m:02d}-{d:02d}"
    for m in range(1,13) for d in [1,15,28]
]

# =========================================================
# SYSTEM 프롬프트 (한국어 특화 수사 도메인)
# =========================================================
SYSTEM_PROMPT = f"""You are an AgensGraph SQL-Wrapped Cypher query expert for cybercrime investigation (CCOP system).

SCHEMA ({GRAPH_PATH}):
Nodes:
  vt_psn(name, id, type)           -- 인물/피의자/피해자
  vt_bacnt(actno, bank_name, bank_cd) -- 계좌 (bank_name★ 반드시 bank_name 사용)
  vt_telno(telno)                  -- 전화번호 (하이픈없이 숫자만)
  vt_ip(ip_addr)                   -- IP주소
  vt_transfer(amount★string, timestamp) -- 이체 (amount는 문자열)
  vt_call(duration)                -- 통화기록
  vt_case(flnm, crime)             -- 사건

Edges (방향 엄수):
  (p:vt_psn)-[:has_account]->(b:vt_bacnt)
  (p:vt_psn)-[:owns_phone]->(t:vt_telno)
  (p:vt_psn)-[:used_ip]->(i:vt_ip)
  (c:vt_case)-[:involves]->(p:vt_psn)
  (b:vt_bacnt)-[:from_account]->(t:vt_transfer)
  (t:vt_transfer)-[:to_account]->(b:vt_bacnt)
  (t:vt_telno)-[:caller]->(c:vt_call)
  (c:vt_call)-[:callee]->(t:vt_telno)

Output format (AgensGraph SQL-Wrapped):
  SELECT * FROM cypher('{GRAPH_PATH}', $$ MATCH ... RETURN ... $$) AS (...);
"""

# =========================================================
# 템플릿 정의
# 각 엔트리: (question_templates[], cypher_template, category)
# =========================================================

def _w(cols: List[str]) -> str:
    """AS 절 자동 생성: (p agtype, r agtype, ...)"""
    return ", ".join(f"({c} agtype)" for c in cols)

def sql(cypher_body: str, cols: List[str]) -> str:
    col_str = ", ".join(cols)
    as_str  = ", ".join(f"{c} agtype" for c in cols)
    return f"SELECT * FROM cypher('{GRAPH_PATH}', $$ {cypher_body} $$) AS ({as_str});"

# ----------------------------------------------------------
# 1. BASIC — 단일 노드 검색
# ----------------------------------------------------------
BASIC_TEMPLATES = [
    # vt_psn 이름 검색
    (
        ["이름이 '{name}'인 사람 노드를 모두 찾아줘.",
         "'{name}'이라는 사람 정보를 그래프에서 조회해줘.",
         "수사 대상 '{name}'의 노드를 찾아라.",
         "인물 '{name}'을 검색해줘."],
        lambda v: sql(f"MATCH (p:vt_psn {{name: '{v['name']}'}}) RETURN p", ["p"]),
        "basic"
    ),
    # vt_bacnt 계좌 검색
    (
        ["계좌번호 '{actno}'인 계좌를 찾아줘.",
         "'{actno}' 계좌의 정보를 조회해.",
         "계좌 '{actno}'의 데이터를 뽑아줘.",
         "대포통장 '{actno}'를 확인해줘."],
        lambda v: sql(f"MATCH (b:vt_bacnt {{actno: '{v['actno']}'}}) RETURN b", ["b"]),
        "basic"
    ),
    # vt_telno 전화번호 검색
    (
        ["전화번호 '{telno}'인 통신기기를 찾아줘.",
         "번호 '{telno}'의 휴대폰 노드를 조회해.",
         "'{telno}' 전화기를 그래프에서 검색해."],
        lambda v: sql(f"MATCH (t:vt_telno {{telno: '{v['telno']}'}}) RETURN t", ["t"]),
        "basic"
    ),
    # vt_ip 검색
    (
        ["IP '{ip_addr}'를 찾아줘.",
         "접속 IP '{ip_addr}'의 노드를 조회해.",
         "'{ip_addr}' 아이피 정보를 뽑아라."],
        lambda v: sql(f"MATCH (i:vt_ip {{ip_addr: '{v['ip_addr']}'}}) RETURN i", ["i"]),
        "basic"
    ),
    # vt_case 사건 검색
    (
        ["사건번호 '{flnm}'인 사건을 찾아줘.",
         "'{flnm}' 사건의 정보를 조회해.",
         "사건 '{flnm}'을 검색해줘."],
        lambda v: sql(f"MATCH (c:vt_case {{flnm: '{v['flnm']}'}}) RETURN c", ["c"]),
        "basic"
    ),
    # 은행명으로 계좌 검색
    (
        ["{bank_name} 계좌 목록을 모두 뽑아줘.",
         "{bank_name}에 개설된 계좌를 전부 조회해.",
         "{bank_name} 대포통장 리스트 출력해줘."],
        lambda v: sql(f"MATCH (b:vt_bacnt {{bank_name: '{v['bank_name']}'}}) RETURN b", ["b"]),
        "basic"
    ),
    # 죄명으로 사건 검색
    (
        ["{crime} 관련 사건을 모두 찾아줘.",
         "{crime} 혐의 사건 목록 조회해.",
         "{crime}으로 분류된 사건들을 뽑아."],
        lambda v: sql(f"MATCH (c:vt_case {{crime: '{v['crime']}'}}) RETURN c", ["c"]),
        "basic"
    ),
    # 인물 전체 목록
    (
        ["수사 대상 인물 전체 목록을 뽑아줘.",
         "그래프에 등록된 모든 인물을 조회해.",
         "vt_psn 노드 전체를 보여줘."],
        lambda v: sql("MATCH (p:vt_psn) RETURN p", ["p"]),
        "basic"
    ),
]

# ----------------------------------------------------------
# 2. DIRECTION — 엣지 방향 단일 홉
# ----------------------------------------------------------
DIRECTION_TEMPLATES = [
    # 인물 → 계좌
    (
        ["'{name}'이 보유한 계좌를 모두 찾아줘.",
         "피의자 '{name}'의 계좌번호를 뽑아줘.",
         "'{name}' 명의 계좌 목록 조회해.",
         "'{name}'이 가진 대포통장 전부 찾아라.",
         "수사 대상 '{name}'의 금융 계좌를 추출해."],
        lambda v: sql(f"MATCH (p:vt_psn {{name: '{v['name']}'}}) -[r:has_account]->(b:vt_bacnt) RETURN p, r, b", ["p","r","b"]),
        "direction"
    ),
    # 계좌 → 인물 (역방향 자연어 → 올바른 쿼리)
    (
        ["계좌 '{actno}'의 주인을 찾아줘.",
         "'{actno}' 계좌를 소유한 사람을 보여줘.",
         "계좌번호 '{actno}'가 누구 거야?",
         "'{actno}' 통장의 명의자를 조회해."],
        lambda v: sql(f"MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt {{actno: '{v['actno']}'}}) RETURN p, r, b", ["p","r","b"]),
        "direction"
    ),
    # 인물 → 전화
    (
        ["'{name}'이 사용하는 전화번호를 찾아줘.",
         "피의자 '{name}'의 핸드폰 목록을 조회해.",
         "'{name}'이 소유한 전화기를 모두 뽑아."],
        lambda v: sql(f"MATCH (p:vt_psn {{name: '{v['name']}'}}) -[r:owns_phone]->(t:vt_telno) RETURN p, r, t", ["p","r","t"]),
        "direction"
    ),
    # 전화 → 인물 (역방향 자연어)
    (
        ["전화번호 '{telno}'를 소유한 사람은 누구야?",
         "번호 '{telno}'의 명의자를 찾아줘.",
         "'{telno}' 전화기 주인을 조회해."],
        lambda v: sql(f"MATCH (p:vt_psn)-[r:owns_phone]->(t:vt_telno {{telno: '{v['telno']}'}}) RETURN p, r, t", ["p","r","t"]),
        "direction"
    ),
    # 인물 → IP
    (
        ["'{name}'이 사용한 IP를 모두 찾아줘.",
         "피의자 '{name}'의 접속 IP 목록 조회해.",
         "'{name}'이 쓴 아이피 주소들을 뽑아."],
        lambda v: sql(f"MATCH (p:vt_psn {{name: '{v['name']}'}}) -[r:used_ip]->(i:vt_ip) RETURN p, r, i", ["p","r","i"]),
        "direction"
    ),
    # IP → 인물 (역방향 자연어)
    (
        ["IP '{ip_addr}'를 사용한 사람을 찾아줘.",
         "'{ip_addr}'로 접속한 인물을 조회해.",
         "아이피 '{ip_addr}' 접속자를 뽑아라."],
        lambda v: sql(f"MATCH (p:vt_psn)-[r:used_ip]->(i:vt_ip {{ip_addr: '{v['ip_addr']}'}}) RETURN p, r, i", ["p","r","i"]),
        "direction"
    ),
    # 사건 → 인물
    (
        ["사건 '{flnm}'에 연루된 모든 인물을 찾아줘.",
         "'{flnm}' 사건 관련자 목록을 조회해.",
         "사건번호 '{flnm}'의 피의자들을 뽑아."],
        lambda v: sql(f"MATCH (c:vt_case {{flnm: '{v['flnm']}'}}) -[r:involves]->(p:vt_psn) RETURN c, r, p", ["c","r","p"]),
        "direction"
    ),
    # 인물 → 사건 (역방향 자연어)
    (
        ["'{name}'이 연루된 사건을 찾아줘.",
         "피의자 '{name}'이 관련된 사건번호를 조회해.",
         "'{name}'이 엮인 범죄 사건들을 모두 뽑아."],
        lambda v: sql(f"MATCH (c:vt_case)-[r:involves]->(p:vt_psn {{name: '{v['name']}'}}) RETURN c, r, p", ["c","r","p"]),
        "direction"
    ),
    # 계좌 → 이체 (from_account)
    (
        ["계좌 '{actno}'에서 나간 이체 내역을 모두 조회해.",
         "'{actno}' 계좌의 출금 기록 전부 뽑아줘.",
         "'{actno}'에서 송금된 이체 내역을 추출해."],
        lambda v: sql(f"MATCH (b:vt_bacnt {{actno: '{v['actno']}'}}) -[r:from_account]->(t:vt_transfer) RETURN b, r, t", ["b","r","t"]),
        "direction"
    ),
    # 이체 → 계좌 (to_account)
    (
        ["계좌 '{actno}'으로 들어온 입금 이체를 전부 찾아줘.",
         "'{actno}' 계좌로 수신된 자금 이동 내역 조회해.",
         "'{actno}'에 입금된 이체 기록을 뽑아."],
        lambda v: sql(f"MATCH (t:vt_transfer)-[r:to_account]->(b:vt_bacnt {{actno: '{v['actno']}'}}) RETURN t, r, b", ["t","r","b"]),
        "direction"
    ),
    # 전화 → 통화기록 (caller)
    (
        ["전화번호 '{telno}'에서 발신한 통화 기록을 찾아줘.",
         "번호 '{telno}'로 건 전화 목록을 조회해.",
         "'{telno}'의 발신 통화 이력을 뽑아."],
        lambda v: sql(f"MATCH (t:vt_telno {{telno: '{v['telno']}'}}) -[r:caller]->(c:vt_call) RETURN t, r, c", ["t","r","c"]),
        "direction"
    ),
]

# ----------------------------------------------------------
# 3. FILTER — 숫자/날짜/문자열 조건
# ----------------------------------------------------------
FILTER_TEMPLATES = [
    # 이체 금액 >=
    (
        ["이체 금액이 {amount}원 이상인 거래를 찾아줘.",
         "{amount}원 이상 거액 송금 내역을 모두 조회해.",
         "금액이 {amount} 이상인 이체를 뽑아줘.",
         "의심 거액 이체 — {amount}원 초과 건들 조회해."],
        lambda v: sql(f"MATCH (t:vt_transfer) WHERE toFloat(t.amount) >= {v['amount']} RETURN t", ["t"]),
        "filter"
    ),
    # 이체 금액 <=
    (
        ["이체 금액이 {amount}원 이하인 소액 이체 내역을 찾아줘.",
         "{amount}원 이하 쪼개기 입금 건들을 조회해.",
         "소액({amount} 이하) 이체 내역을 전부 뽑아."],
        lambda v: sql(f"MATCH (t:vt_transfer) WHERE toFloat(t.amount) <= {v['amount']} RETURN t", ["t"]),
        "filter"
    ),
    # 이체 금액 정확히
    (
        ["이체 금액이 딱 {amount}원인 거래를 찾아줘.",
         "정확히 {amount}원인 이체 건들을 조회해.",
         "{amount}원 정확한 이체 내역을 뽑아."],
        lambda v: sql(f"MATCH (t:vt_transfer) WHERE t.amount = '{v['amount']}' RETURN t", ["t"]),
        "filter"
    ),
    # 인물의 계좌 + 금액 필터
    (
        ["'{name}'의 계좌에서 {amount}원 이상 나간 이체 내역을 찾아줘.",
         "피의자 '{name}'의 {amount}원 초과 출금 기록을 조회해.",
         "'{name}'이 {amount}원 이상 송금한 내역을 뽑아."],
        lambda v: sql(
            f"MATCH (p:vt_psn {{name: '{v['name']}'}}) -[:has_account]->(b:vt_bacnt) -[r:from_account]->(t:vt_transfer) "
            f"WHERE toFloat(t.amount) >= {v['amount']} RETURN p, b, r, t",
            ["p","b","r","t"]
        ),
        "filter"
    ),
    # 타임스탬프 이후
    (
        ["'{timestamp}' 이후에 발생한 이체 내역을 조회해.",
         "{timestamp} 이후 자금 이동 내역을 모두 뽑아줘.",
         "'{timestamp}' 이후 이체를 찾아줘."],
        lambda v: sql(f"MATCH (t:vt_transfer) WHERE t.timestamp > '{v['timestamp']}' RETURN t", ["t"]),
        "filter"
    ),
    # 통화 시간 필터
    (
        ["통화 시간이 {duration}초 이상인 통화 기록을 찾아줘.",
         "{duration}초 넘는 장시간 통화 내역을 조회해.",
         "통화시간 {duration}초 초과 건들을 뽑아."],
        lambda v: sql(f"MATCH (c:vt_call) WHERE toFloat(c.duration) >= {v['duration']} RETURN c", ["c"]),
        "filter"
    ),
    # 인물 계좌 + 특정 은행
    (
        ["'{name}'이 {bank_name}에 가진 계좌를 찾아줘.",
         "피의자 '{name}'의 {bank_name} 계좌를 조회해.",
         "'{name}'의 {bank_name} 계좌번호를 뽑아."],
        lambda v: sql(
            f"MATCH (p:vt_psn {{name: '{v['name']}'}}) -[r:has_account]->(b:vt_bacnt {{bank_name: '{v['bank_name']}'}}) RETURN p, r, b",
            ["p","r","b"]
        ),
        "filter"
    ),
    # 금액 범위
    (
        ["{amount_lo}원 이상 {amount_hi}원 이하인 이체 내역을 찾아줘.",
         "{amount_lo}~{amount_hi}원 사이의 의심 이체를 조회해.",
         "금액 범위 {amount_lo}~{amount_hi}원 이체 내역을 뽑아."],
        lambda v: sql(
            f"MATCH (t:vt_transfer) WHERE toFloat(t.amount) >= {v['amount_lo']} AND toFloat(t.amount) <= {v['amount_hi']} RETURN t",
            ["t"]
        ),
        "filter"
    ),
]

# ----------------------------------------------------------
# 4. MULTIHOP — 2~5홉 체인
# ----------------------------------------------------------
MULTIHOP_TEMPLATES = [
    # 2홉: 인물 → 계좌 → 이체
    (
        ["'{name}'의 계좌에서 나간 이체 내역 전체를 조회해.",
         "피의자 '{name}'의 출금 이체 체인을 추적해.",
         "'{name}'이 보낸 모든 이체 기록을 찾아줘."],
        lambda v: sql(
            f"MATCH (p:vt_psn {{name: '{v['name']}'}}) -[:has_account]->(b:vt_bacnt) -[r:from_account]->(t:vt_transfer) RETURN p, b, r, t",
            ["p","b","r","t"]
        ),
        "multihop"
    ),
    # 2홉: 인물 → 계좌 ← 이체 수신
    (
        ["'{name}'의 계좌로 들어온 입금 내역을 모두 찾아줘.",
         "피의자 '{name}'에게 자금이 들어온 경로를 조회해.",
         "'{name}' 명의 계좌로 수신된 이체를 전부 뽑아."],
        lambda v: sql(
            f"MATCH (p:vt_psn {{name: '{v['name']}'}}) -[:has_account]->(b:vt_bacnt) <-[r:to_account]-(t:vt_transfer) RETURN p, b, r, t",
            ["p","b","r","t"]
        ),
        "multihop"
    ),
    # 3홉: 계좌 → 이체 → 계좌 → 인물
    (
        ["계좌 '{actno}'에서 이체된 자금을 받은 사람을 찾아줘.",
         "'{actno}'의 출금 자금 수신자를 추적해.",
         "'{actno}'에서 돈이 어디로 갔는지 3단계 추적해줘."],
        lambda v: sql(
            f"MATCH (b1:vt_bacnt {{actno: '{v['actno']}'}}) -[:from_account]->(t:vt_transfer) -[:to_account]->(b2:vt_bacnt) <-[:has_account]-(p:vt_psn) RETURN b1, t, b2, p",
            ["b1","t","b2","p"]
        ),
        "multihop"
    ),
    # 3홉: 사건 → 인물 → 계좌 → 이체
    (
        ["사건 '{flnm}'에 연루된 피의자들의 출금 이체 내역을 찾아줘.",
         "'{flnm}' 사건 관련자들의 계좌 출금 기록을 조회해.",
         "사건번호 '{flnm}'의 용의자 계좌 이체 체인을 추적해."],
        lambda v: sql(
            f"MATCH (c:vt_case {{flnm: '{v['flnm']}'}}) -[:involves]->(p:vt_psn) -[:has_account]->(b:vt_bacnt) -[r:from_account]->(t:vt_transfer) RETURN c, p, b, r, t",
            ["c","p","b","r","t"]
        ),
        "multihop"
    ),
    # 3홉: 인물 → 전화 → 통화 ← 전화
    (
        ["'{name}'이 통화한 상대방 전화번호를 모두 찾아줘.",
         "피의자 '{name}'의 통화 상대를 추적해.",
         "'{name}'이 연락한 번호들을 전부 조회해."],
        lambda v: sql(
            f"MATCH (p:vt_psn {{name: '{v['name']}'}}) -[:owns_phone]->(t1:vt_telno) -[:caller]->(c:vt_call) -[:callee]->(t2:vt_telno) RETURN p, t1, c, t2",
            ["p","t1","c","t2"]
        ),
        "multihop"
    ),
    # 4홉: 인물 → 계좌 → 이체 → 계좌 → 인물 (자금 수신자)
    (
        ["'{name}'이 보낸 돈을 최종적으로 받은 사람을 찾아줘.",
         "피의자 '{name}'의 자금 이동 최종 수신자를 추적해.",
         "'{name}'에서 4단계 거쳐 도달한 계좌 소유자를 찾아."],
        lambda v: sql(
            f"MATCH (p1:vt_psn {{name: '{v['name']}'}}) -[:has_account]->(b1:vt_bacnt) -[:from_account]->(t:vt_transfer) -[:to_account]->(b2:vt_bacnt) <-[:has_account]-(p2:vt_psn) RETURN p1, b1, t, b2, p2",
            ["p1","b1","t","b2","p2"]
        ),
        "multihop"
    ),
    # 4홉: 사건 → 인물 → 전화 → 통화 → 전화
    (
        ["사건 '{flnm}'에 연루된 인물들의 통화 상대를 조회해.",
         "'{flnm}' 사건 용의자들의 연락 체계를 추적해.",
         "사건번호 '{flnm}'의 피의자 통화 네트워크를 뽑아줘."],
        lambda v: sql(
            f"MATCH (c:vt_case {{flnm: '{v['flnm']}'}}) -[:involves]->(p:vt_psn) -[:owns_phone]->(t1:vt_telno) -[:caller]->(call:vt_call) -[:callee]->(t2:vt_telno) RETURN c, p, t1, call, t2",
            ["c","p","t1","call","t2"]
        ),
        "multihop"
    ),
    # 5홉: 자금세탁 체인
    (
        ["계좌 '{actno}'에서 5단계를 거쳐 세탁된 자금의 종착 계좌를 찾아줘.",
         "'{actno}'의 자금이 5번 이체 후 최종 도달한 계좌를 추적해.",
         "'{actno}'에서 시작한 5단계 이체 체인의 끝을 찾아."],
        lambda v: sql(
            f"MATCH (b1:vt_bacnt {{actno: '{v['actno']}'}}) -[:from_account]->(:vt_transfer) -[:to_account]->(:vt_bacnt) -[:from_account]->(:vt_transfer) -[:to_account]->(:vt_bacnt) -[:from_account]->(t5:vt_transfer) -[:to_account]->(b_final:vt_bacnt) RETURN b1, b_final",
            ["b1","b_final"]
        ),
        "multihop"
    ),
    # 공통 인물: 두 사건 모두 등장
    (
        ["사건 '{flnm1}'과 '{flnm2}' 두 사건에 모두 연루된 피의자를 찾아줘.",
         "'{flnm1}'과 '{flnm2}' 사건에 동시에 등장하는 인물을 조회해.",
         "두 사건 '{flnm1}', '{flnm2}'에 공통 연루된 용의자를 뽑아."],
        lambda v: sql(
            f"MATCH (c1:vt_case {{flnm: '{v['flnm1']}'}}) -[:involves]->(p:vt_psn) <-[:involves]-(c2:vt_case {{flnm: '{v['flnm2']}'}}) RETURN c1, p, c2",
            ["c1","p","c2"]
        ),
        "multihop"
    ),
    # 인물 → IP → (같은 IP 사용한 다른 인물)
    (
        ["'{name}'과 같은 IP를 사용한 공범을 찾아줘.",
         "피의자 '{name}'과 동일 접속 IP를 쓴 다른 인물을 조회해.",
         "'{name}'과 IP를 공유한 연루자를 추적해."],
        lambda v: sql(
            f"MATCH (p1:vt_psn {{name: '{v['name']}'}}) -[:used_ip]->(i:vt_ip) <-[:used_ip]-(p2:vt_psn) WHERE p1 <> p2 RETURN p1, i, p2",
            ["p1","i","p2"]
        ),
        "multihop"
    ),
    # 계좌 공유 공범
    (
        ["'{name}'과 같은 계좌를 공유한 인물을 찾아줘.",
         "'{name}'과 동일 계좌에 연결된 다른 사람을 조회해."],
        lambda v: sql(
            f"MATCH (p1:vt_psn {{name: '{v['name']}'}}) -[:has_account]->(b:vt_bacnt) <-[:has_account]-(p2:vt_psn) WHERE p1 <> p2 RETURN p1, b, p2",
            ["p1","b","p2"]
        ),
        "multihop"
    ),
    # 3개 사건 공통 피의자
    (
        ["3개 이상의 금융 사기 사건에 공통으로 등장하는 핵심 피의자를 찾아줘.",
         "여러 사건에 반복 등장하는 용의자를 뽑아줘.",
         "사건 3개에 모두 연루된 인물을 조회해."],
        lambda v: sql(
            f"MATCH (c1:vt_case)-[:involves]->(p:vt_psn)<-[:involves]-(c2:vt_case), (c3:vt_case)-[:involves]->(p) WHERE c1 <> c2 AND c2 <> c3 AND c1 <> c3 RETURN p, count(DISTINCT c1) AS case_count",
            ["p","case_count"]
        ),
        "multihop"
    ),
]

# ----------------------------------------------------------
# 5. PATH — shortestPath
# ----------------------------------------------------------
PATH_TEMPLATES = [
    (
        ["'{name1}'과 '{name2}' 사이의 최단 경로를 찾아줘.",
         "피의자 '{name1}'에서 '{name2}'로 가는 최단 연결 고리를 추적해.",
         "'{name1}'와 '{name2}' 사이의 연관 경로를 그려줘.",
         "'{name1}'에서 '{name2}'까지의 최단 연결을 조회해."],
        lambda v: sql(
            f"MATCH path = shortestPath((p1:vt_psn {{name: '{v['name1']}'}}) -[*]- (p2:vt_psn {{name: '{v['name2']}'}})) RETURN path",
            ["path"]
        ),
        "path"
    ),
    (
        ["계좌 '{actno1}'과 계좌 '{actno2}' 사이의 자금 이동 경로를 찾아줘.",
         "'{actno1}'에서 '{actno2}'로 자금이 이동한 경로를 추적해.",
         "두 계좌 '{actno1}', '{actno2}' 간 최단 자금세탁 경로를 조회해."],
        lambda v: sql(
            f"MATCH path = shortestPath((b1:vt_bacnt {{actno: '{v['actno1']}'}}) -[*]- (b2:vt_bacnt {{actno: '{v['actno2']}'}})) RETURN path",
            ["path"]
        ),
        "path"
    ),
    (
        ["'{name}'에서 계좌 '{actno}'까지의 연결 경로를 찾아줘.",
         "피의자 '{name}'과 계좌 '{actno}'의 연관성을 최단 경로로 보여줘.",
         "'{name}'이 '{actno}' 계좌와 어떻게 연결되는지 추적해."],
        lambda v: sql(
            f"MATCH path = shortestPath((p:vt_psn {{name: '{v['name']}'}}) -[*]- (b:vt_bacnt {{actno: '{v['actno']}' }})) RETURN path",
            ["path"]
        ),
        "path"
    ),
    (
        ["'{name}'과 사건 '{flnm}' 사이의 연관 경로를 찾아줘.",
         "피의자 '{name}'이 사건 '{flnm}'에 어떻게 연결되는지 경로를 조회해.",
         "'{name}'에서 사건번호 '{flnm}'까지 최단 경로를 추적해."],
        lambda v: sql(
            f"MATCH path = shortestPath((p:vt_psn {{name: '{v['name']}'}}) -[*]- (c:vt_case {{flnm: '{v['flnm']}'}})) RETURN path",
            ["path"]
        ),
        "path"
    ),
]

# ----------------------------------------------------------
# 6. B2C — 구어체/비격식 표현
# ----------------------------------------------------------
B2C_TEMPLATES = [
    (
        ["내 {bank_name} 통장 '{actno}'에서 돈 빠진 내역 다 뽑아줘.",
         "{bank_name} 계좌 '{actno}'에서 무단 출금된 거 다 보여줘.",
         "'{actno}' 통장에서 돈 나간 거 싹 다 찾아줘."],
        lambda v: sql(
            f"MATCH (b:vt_bacnt {{actno: '{v['actno']}', bank_name: '{v['bank_name']}'}}) -[r:from_account]->(t:vt_transfer) RETURN b, r, t",
            ["b","r","t"]
        ),
        "b2c"
    ),
    (
        ["'{name}'이라는 놈이 어디 계좌를 갖고 있는지 다 뽑아.",
         "'{name}' 찾아서 계좌 전부 조회해줘.",
         "'{name}' 이 사람 계좌 리스트 다 보여줘."],
        lambda v: sql(
            f"MATCH (p:vt_psn {{name: '{v['name']}'}}) -[:has_account]->(b:vt_bacnt) RETURN p, b",
            ["p","b"]
        ),
        "b2c"
    ),
    (
        ["{bank_name} 계좌 가진 애들 명단 싹 뽑아줘.",
         "{bank_name}에 통장 튼 사람들 다 찾아줘.",
         "{bank_name} 대포통장 보유자 전부 조회해."],
        lambda v: sql(
            f"MATCH (p:vt_psn) -[:has_account]->(b:vt_bacnt {{bank_name: '{v['bank_name']}'}}) RETURN p, b",
            ["p","b"]
        ),
        "b2c"
    ),
    (
        ["새벽에 이상한 IP에서 접속한 놈들 전부 다 찾아줘.",
         "수상한 IP 쓴 사람들 목록 뽑아줘.",
         "이상한 아이피로 로그인한 놈들 누구야?"],
        lambda v: sql(
            "MATCH (p:vt_psn) -[:used_ip]->(i:vt_ip) RETURN p, i",
            ["p","i"]
        ),
        "b2c"
    ),
    (
        ["'{name}'이 전화한 놈들 다 찾아줘.",
         "'{name}'이 연락한 사람들 전부 조회해.",
         "'{name}' 통화 상대 리스트 뽑아줘."],
        lambda v: sql(
            f"MATCH (p:vt_psn {{name: '{v['name']}'}}) -[:owns_phone]->(t1:vt_telno) -[:caller]->(c:vt_call) -[:callee]->(t2:vt_telno) RETURN p, t1, c, t2",
            ["p","t1","c","t2"]
        ),
        "b2c"
    ),
    (
        ["사기 사건 '{flnm}'에 엮인 놈들 다 잡아줘.",
         "'{flnm}' 사건 관련자 전부 뽑아줘.",
         "'{flnm}' 사기에 연루된 사람들 싹 다 찾아."],
        lambda v: sql(
            f"MATCH (c:vt_case {{flnm: '{v['flnm']}'}}) -[:involves]->(p:vt_psn) RETURN c, p",
            ["c","p"]
        ),
        "b2c"
    ),
    (
        ["500만원 넘게 보낸 놈들 다 잡아줘.",
         "거액 이체한 놈들 찾아줘.",
         "5백만원 이상 송금 내역 싹 다 뽑아."],
        lambda v: sql(
            "MATCH (t:vt_transfer) WHERE toFloat(t.amount) >= 5000000 RETURN t",
            ["t"]
        ),
        "b2c"
    ),
]

# ----------------------------------------------------------
# 7. GUARDRAIL — 쓰기 명령 방어 학습
# ----------------------------------------------------------
GUARDRAIL_TEMPLATES = [
    (["모든 노드를 삭제해줘.", "그래프 초기화해.", "노드 싹 다 지워줘."],
     "GENERAL: 데이터 변경(삭제/수정/생성) 명령은 수행할 수 없습니다. 조회 질문만 가능합니다.", "guardrail"),
    (["피의자1 노드를 제거해줘.", "'{name}' 데이터를 삭제해.", "'{name}' 정보를 그래프에서 없애줘."],
     "GENERAL: 데이터 삭제는 허용되지 않습니다. 조회 관련 질문을 입력해주세요.", "guardrail"),
    (["새로운 피의자 노드를 만들어줘.", "계좌 노드를 추가해줘.", "그래프에 데이터를 입력해."],
     "GENERAL: 데이터 생성(INSERT) 명령은 수행할 수 없습니다. 읽기 전용 조회만 가능합니다.", "guardrail"),
    (["피의자1의 이름을 '용의자A'로 바꿔줘.", "계좌 정보를 수정해줘.", "노드 속성을 업데이트해."],
     "GENERAL: 데이터 수정(UPDATE) 명령은 수행할 수 없습니다.", "guardrail"),
    (["파이썬이 뭐야?", "오늘 날씨 어때?", "맛집 추천해줘.", "코딩 어떻게 하는지 알려줘."],
     "GENERAL: 수사 시스템은 범죄 수사 관련 그래프 조회 질문만 처리할 수 있습니다.", "guardrail"),
]


# =========================================================
# 값 샘플러
# =========================================================

def sample_vars() -> Dict:
    names  = random.sample(PERSONS, k=min(2, len(PERSONS)))
    cases  = random.sample(CASES, k=min(2, len(CASES)))
    acts   = random.sample(ACCOUNTS, k=min(2, len(ACCOUNTS)))
    amt_pool = sorted([int(a) for a in AMOUNTS])
    lo = random.choice(amt_pool[:-1])
    hi = random.choice([a for a in amt_pool if a > lo])
    return {
        "name":      names[0],
        "name1":     names[0],
        "name2":     names[1],
        "actno":     acts[0],
        "actno1":    acts[0],
        "actno2":    acts[1],
        "telno":     random.choice(PHONES),
        "ip_addr":   random.choice(IPS),
        "flnm":      cases[0],
        "flnm1":     cases[0],
        "flnm2":     cases[1],
        "bank_name": random.choice(BANKS),
        "amount":    random.choice(AMOUNTS),
        "amount_lo": str(lo),
        "amount_hi": str(hi),
        "crime":     random.choice(CRIMES),
        "timestamp": random.choice(TIMESTAMPS),
        "duration":  str(random.choice([60, 120, 300, 600, 900, 1800])),
    }


def make_sample(template_tuple, use_llm: bool = False) -> Dict:
    """템플릿 → (question, cypher, category) 생성"""
    questions, cypher_fn, category = template_tuple

    v = sample_vars()

    # guardrail은 고정 응답
    if category == "guardrail":
        q = random.choice(questions)
        for key, val in v.items():
            q = q.replace(f"{{{key}}}", val)
        cypher_str = cypher_fn  # guardrail은 lambda가 아닌 문자열
        return {"question": q, "cypher": cypher_str, "category": category}

    q = random.choice(questions)
    for key, val in v.items():
        q = q.replace(f"{{{key}}}", val)

    cypher_str = cypher_fn(v)

    return {"question": q, "cypher": cypher_str, "category": category}


# =========================================================
# ShareGPT / Alpaca 포맷 변환
# =========================================================

def to_sharegpt(sample: Dict) -> Dict:
    return {
        "conversations": [
            {"from": "system",  "value": SYSTEM_PROMPT},
            {"from": "human",   "value": sample["question"]},
            {"from": "gpt",     "value": sample["cypher"]},
        ]
    }


def to_alpaca(sample: Dict) -> Dict:
    return {
        "instruction": "Convert the following natural language question into an AgensGraph SQL-Wrapped Cypher query for cybercrime investigation.",
        "input":  sample["question"],
        "output": sample["cypher"],
        "graph_path": GRAPH_PATH,
        "category": sample["category"],
    }


# =========================================================
# 생성 계획
# =========================================================
GENERATION_PLAN = [
    # (template_pool, target_count)
    (BASIC_TEMPLATES,     3500),
    (DIRECTION_TEMPLATES, 4500),
    (FILTER_TEMPLATES,    4500),
    (MULTIHOP_TEMPLATES,  5000),
    (PATH_TEMPLATES,      2500),
    (B2C_TEMPLATES,       2500),
    (GUARDRAIL_TEMPLATES,  500),
]


def generate(target_total: int = 23_000, use_llm: bool = False, seed: int = 42) -> List[Dict]:
    random.seed(seed)
    samples = []

    total_plan = sum(n for _, n in GENERATION_PLAN)
    scale = target_total / total_plan

    for pool, n in GENERATION_PLAN:
        scaled_n = max(1, int(n * scale))
        cat_name = pool[0][2] if pool else "?"
        print(f"  [{cat_name:10}] {scaled_n:,}개 생성 중...", end="", flush=True)
        t0 = time.time()

        for _ in range(scaled_n):
            tmpl = random.choice(pool)
            try:
                s = make_sample(tmpl, use_llm=use_llm)
                samples.append(s)
            except Exception as e:
                pass  # 생성 실패 skip

        print(f" 완료 ({time.time()-t0:.1f}s)")

    random.shuffle(samples)
    return samples


def deduplicate(samples: List[Dict]) -> List[Dict]:
    """완전히 동일한 (question, cypher) 쌍 제거"""
    seen = set()
    out  = []
    for s in samples:
        key = (s["question"], s["cypher"])
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def analyze(samples: List[Dict]):
    from collections import Counter
    cats = Counter(s["category"] for s in samples)
    print("\n=== 생성 결과 분포 ===")
    total = len(samples)
    for cat, cnt in sorted(cats.items()):
        bar = "█" * (cnt * 30 // total)
        print(f"  {cat:12}: {cnt:6,}개 ({cnt/total*100:5.1f}%) {bar}")
    print(f"  {'합계':12}: {total:6,}개")


# =========================================================
# 메인
# =========================================================

def main():
    parser = argparse.ArgumentParser(description="CCOP V4 SFT 데이터 합성 생성기")
    parser.add_argument("--target", type=int, default=23_000, help="생성 목표 샘플 수 (기본: 23,000)")
    parser.add_argument("--use-llm", action="store_true", help="LLM 역생성 활성화 (OPENAI_API_KEY 필요)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"[CCOP V4 SFT 생성기]")
    print(f"  목표: {args.target:,}개  |  LLM 역생성: {args.use_llm}  |  시드: {args.seed}")
    print(f"  출력: {OUT_SHAREGPT}")
    print()

    print("[1/3] 샘플 생성...")
    samples = generate(target_total=args.target, use_llm=args.use_llm, seed=args.seed)

    print(f"\n[2/3] 중복 제거...")
    before = len(samples)
    samples = deduplicate(samples)
    print(f"  {before:,}개 → {len(samples):,}개 ({before - len(samples):,}개 제거)")

    analyze(samples)

    print(f"\n[3/3] 파일 저장...")

    # ShareGPT 포맷 (기존 korean_cybercrime_sft와 동일 구조)
    sharegpt_data = [to_sharegpt(s) for s in samples]
    with open(OUT_SHAREGPT, "w", encoding="utf-8") as f:
        json.dump(sharegpt_data, f, ensure_ascii=False, indent=2)
    print(f"  ShareGPT: {OUT_SHAREGPT}  ({len(sharegpt_data):,}개)")

    # Alpaca 포맷
    with open(OUT_ALPACA, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(to_alpaca(s), ensure_ascii=False) + "\n")
    print(f"  Alpaca:   {OUT_ALPACA}  ({len(samples):,}개)")

    print(f"\n[완료] 기존 10,143개 + 신규 {len(samples):,}개 = {10143 + len(samples):,}개")
    print("다음 단계: scripts/merge_sft_v4.py 로 기존 데이터와 병합 후 학습")


if __name__ == "__main__":
    main()
