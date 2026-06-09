#!/usr/bin/env python3
"""
CCOP SFT 데이터 합성 생성기 V3.2
================================
V3.2 신규 온톨로지 (22 Nodes, 37 Edges)를 반영한 
수사망(Text-to-Cypher) 학습 전용 데이터셋 생성 스크립트.

특징:
  1. 공백 처리(Sanitizer) 로드 감소를 위해, 정답 Cypher 문장 내 키워드 간 공백 엄격 준수.
  2. 신규 엣지(impersonates, filed_as, belongs_to, clusters_with 등) 집중 학습
  3. ShareGPT (korean_cybercrime_sft_v32.json) 및 Alpaca 포맷 동시 배출

실행:
  cd /Users/iankwon/test/coop_v1.0
  python3 scripts/generate_v32_synth_sft.py --target 15000
"""

import os, sys, json, random, argparse
from datetime import datetime

# =========================================================
# 경로 설정
# =========================================================
BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_SHAREGPT = os.path.join(BASE_DIR, "data", "sft_v32_sharegpt.json")
OUT_ALPACA   = os.path.join(BASE_DIR, "data", "sft_v32_alpaca.jsonl")

GRAPH_PATH = "tccop_graph_v6"

# =========================================================
# 가상 도메인 데이터 풀 
# =========================================================
PERSONS = [f"피의자{i}" for i in range(1, 51)] + [f"김철수{i}" for i in range(1, 20)]
ACCOUNTS = [f"110-100{i:03d}-10" for i in range(1, 100)]
BANKS = ["국민은행", "신한은행", "우리은행", "농협은행", "기업은행", "토스뱅크"]
PHONES = [f"010-{random.randint(1111,9999)}-{random.randint(1111,9999)}" for _ in range(50)] + ["0100000001", "1000000001"]
IPS = [f"203.108.1.{i}" for i in range(1, 100)]
CASES = [f"CASE-{2023+i%2}-{i:03d}" for i in range(1, 100)]
PETITIONS = [f"PTN-{i:03d}" for i in range(1, 100)]
ORGS = ["경찰청", "국민은행본점", "금융감독원", "서민금융진흥원", "검찰청"]
LOCS = ["서울지부", "강남구", "대포동", "역삼동 ATM"]
AMOUNTS = [str(i*10000) for i in range(1, 200)]
DATES = ["2023-05-01", "2024-01-10", "2024-03-15"]

def sample_vars() -> dict:
    return {
        "name": random.choice(PERSONS),
        "name2": random.choice(PERSONS),
        "actno": random.choice(ACCOUNTS),
        "telno": random.choice(PHONES).translate(str.maketrans('','','-')),
        "ip_addr": random.choice(IPS),
        "flnm": random.choice(CASES),
        "flnm2": random.choice(CASES),
        "ptn_id": random.choice(PETITIONS),
        "bank_name": random.choice(BANKS),
        "org_name": random.choice(ORGS),
        "loc_name": random.choice(LOCS),
        "amount": random.choice(AMOUNTS),
    }

# =========================================================
# Query Formatter
# =========================================================
def sql(cypher_body: str, cols: list) -> str:
    # 템플릿의 Cypher 쿼리에도 확실한 띄어쓰기(Sanitizer 역할 포함) 적용
    as_str = ", ".join(f"{c} agtype" for c in cols)
    return f"SELECT * FROM cypher('{GRAPH_PATH}', $$ {cypher_body} $$) AS ({as_str});"

# =========================================================
# V3.2 Templates
# =========================================================

TEMPLATES = [
    # 1. 신규 엣지: impersonates (사칭)
    (
        ["번호 '{telno}'가 {org_name}을 사칭한 목록을 보여줘.", 
         "{org_name}을 사칭한 '{telno}'을 조사해 줘.",
         "기관 {org_name}을 사칭해 사용된 번호 '{telno}' 내역."],
        lambda v: sql(f"MATCH (t:vt_telno {{ telno: '{v['telno']}' }})-[r:impersonates]->(o:vt_org {{ org_name: '{v['org_name']}' }}) RETURN t, r, o", ["t","r","o"])
    ),
    (
        ["{org_name}을 사칭한 전화번호들을 다 찾아봐.", 
         "'{org_name}' 사칭에 이용된 번호 리스트."],
        lambda v: sql(f"MATCH (t:vt_telno)-[r:impersonates]->(o:vt_org {{ org_name: '{v['org_name']}' }}) RETURN t, r, o", ["t","r","o"])
    ),
    
    # 2. 신규 엣지: filed_as (진정서 -> 사건 병합)
    (
        ["진정서 '{ptn_id}'가 어떤 정식 수사 사건으로 접수되었는지 찾아줘.",
         "'{ptn_id}' 진정서가 귀속된 사건번호.",
         "'{ptn_id}' 진정서의 연계 사건 목록."],
        lambda v: sql(f"MATCH (pt:vt_petition {{ flnm: '{v['ptn_id']}' }})-[r:filed_as]->(c:vt_case) RETURN pt, r, c", ["pt","r","c"])
    ),
    
    # 3. 신규 엣지: clusters_with (진정서 군집)
    (
        ["진정서 '{ptn_id}'와 병합(클러스터링)된 다른 진정서들을 보여줘.",
         "'{ptn_id}'와 동일 성격으로 군집화된 진정서 내역.",
         "'{ptn_id}' 관련 유사 진정서 그룹."],
        lambda v: sql(f"MATCH (pt1:vt_petition {{ flnm: '{v['ptn_id']}' }})-[r:clusters_with]-(pt2:vt_petition) RETURN pt1, r, pt2", ["pt1","r","pt2"])
    ),
    
    # 4. 신규 엣지: belongs_to (계좌 소속 은행 기관)
    (
        ["계좌 '{actno}'를 개설해 준 은행 본점(조직)을 확인해.",
         "'{actno}' 계좌가 속한 금융 기관을 조회해 줘.",
         "계좌 '{actno}'의 소속 기관 정보."],
        lambda v: sql(f"MATCH (b:vt_bacnt {{ actno: '{v['actno']}' }})-[r:belongs_to]->(o:vt_org) RETURN b, r, o", ["b","r","o"])
    ),
    
    # 5. 신규 엣지: sameAs (동일인)
    (
        ["피의자 '{name}'과 동일 인물로 추정되는 다른 프로필을 찾아줘.",
         "'{name}'과 동일인으로 병합된 다른 계정을 보여줘.",
         "'{name}'의 동일인(sameAs) 연결망."],
        lambda v: sql(f"MATCH (p1:vt_psn {{ name: '{v['name']}' }})-[r:sameAs]->(p2:vt_psn) RETURN p1, r, p2", ["p1","r","p2"])
    ),
    
    # 6. 신규 엣지: eg_used_account (진정 증거 계좌)
    (
        ["진정서 '{ptn_id}'에 접수된 피해 계좌 목록을 보여줘.",
         "'{ptn_id}' 사건 증거로 제출된 계좌 번호들.",
         "진정 '{ptn_id}'에 기록된 범행 계좌."],
        lambda v: sql(f"MATCH (pt:vt_petition {{ flnm: '{v['ptn_id']}' }})-[r:eg_used_account]->(b:vt_bacnt) RETURN pt, r, b", ["pt","r","b"])
    ),
    
    # 7. 신규 Multihop: 진정서 -> 사건 -> 피의자 -> 계좌
    (
        ["진정서 '{ptn_id}'가 정식 사건으로 접수된 후 연루된 피의자들의 계좌를 찾아줘.",
         "'{ptn_id}' 진정서와 엮인 사건의 피의자들이 가진 계좌 출금 내역.",
         "'{ptn_id}' 사건 관련자들의 자금 은닉처."],
        lambda v: sql(f"MATCH (pt:vt_petition {{ flnm: '{v['ptn_id']}' }})-[r1:filed_as]->(c:vt_case)-[r2:involves]->(p:vt_psn)-[r3:has_account]->(b:vt_bacnt) RETURN pt, c, p, b", ["pt","c","p","b"])
    ),
    
    # 8. 기존 Path의 디테일 교정
    (
        ["피의자 '{name}'에서 피의자 '{name2}' 사이 최단 경로 알려줘.",
         "'{name}'과 '{name2}'의 연관성을 뽑아줘."],
        lambda v: sql(f"MATCH path = shortestPath((p1:vt_psn {{ name: '{v['name']}' }})-[*]-(p2:vt_psn {{ name: '{v['name2']}' }})) RETURN path", ["path"])
    ),
]


def generate_sft(target: int):
    random.seed(42)
    sft_data = []
    
    system_prompt = """You are an AgensGraph SQL-Wrapped Cypher query expert for cybercrime investigation (CCOP system).

SCHEMA (tccop_graph_v6):
Nodes:
  vt_psn(name), vt_bacnt(actno, bank_name), vt_telno(telno), vt_ip(ip_addr), vt_transfer(amount), vt_call(duration), vt_case(flnm), vt_petition(flnm), vt_org(org_name), vt_loc(address)

Edges (V3.2):
  has_account, owns_phone, used_ip, involves, from_account, to_account, caller, callee
  impersonates, filed_as, clusters_with, belongs_to, sameAs, resolves_to, eg_used_account, eg_used_phone

Output format:
  SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (a) RETURN a $$) AS (a agtype);
"""
    
    # 템플릿 비례 확장
    for i in range(target):
        q_list, cypher_fn = random.choice(TEMPLATES)
        v = sample_vars()
        question = random.choice(q_list)
        for key, val in v.items():
            question = question.replace(f"{{{key}}}", val)
            
        cypher_str = cypher_fn(v)
        
        # Alpaca
        sft_data.append({
            "instruction": "Convert the following natural language question into an AgensGraph SQL-Wrapped Cypher query for cybercrime investigation.",
            "input": question,
            "output": cypher_str,
        })
        
    # JSONL 로 저장 (Alpaca)
    with open(OUT_ALPACA, "w", encoding="utf-8") as f:
        for item in sft_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
    # ShareGPT 변환
    sharegpt = {"conversations": []}
    for item in sft_data:
        sharegpt["conversations"].append([
            {"from": "system", "value": system_prompt},
            {"from": "human", "value": item["input"]},
            {"from": "gpt", "value": item["output"]}
        ])
        
    with open(OUT_SHAREGPT, "w", encoding="utf-8") as f:
        json.dump(sharegpt["conversations"], f, ensure_ascii=False, indent=2)
        
    print(f"✅ V3.2 SFT 데이터셋 {target}건 생성 완료!")
    print(f"  - Alpaca  : {OUT_ALPACA}")
    print(f"  - ShareGPT: {OUT_SHAREGPT}")
    print(f"  (기존 V3 SFT 데이터와 병합하여 LLaMA-Factory로 훈련하세요.)")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=int, default=15000)
    args = parser.parse_args()
    generate_sft(args.target)
