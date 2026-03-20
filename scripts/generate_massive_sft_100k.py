import os
import json
import random
import argparse
from tqdm import tqdm

# ----- Entity Generators -----
KOR_NAMES = ["김철수", "이영희", "박민준", "최서연", "정지훈", "강하늘", "조민수", "윤서아", "장도연", "임시완",
             "한소희", "오지호", "서강준", "신세경", "권유리", "황정민", "안보현", "송중기", "류준열", "전지현",
             "홍길동", "피의자1", "피해자1", "피해자2", "용의자A", "참고인B", "대포통장주", "총책"]

def get_name():
    return random.choice(KOR_NAMES) + str(random.randint(1, 99) if random.random() > 0.8 else "")

def get_phone():
    prefixes = ["010", "02", "070"]
    return f"{random.choice(prefixes)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"

def get_account():
    banks = ["110", "200", "005", "3333", "777"]
    return f"{random.choice(banks)}-{random.randint(100, 999)}-{random.randint(100000, 999999)}"

def get_ip():
    return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"

def get_amount():
    base = random.choice([10000, 50000, 100000, 500000, 1000000, 5000000, 10000000, 20000000, 50000000])
    jitter = random.randint(0, 9999) * 100
    return str(base + jitter)

def get_duration():
    return str(random.randint(10, 3600))

def get_case():
    return f"CASE-202{random.randint(4,6)}-{random.randint(1000, 9999)}"

def get_date():
    return f"202{random.randint(4,6)}-0{random.randint(1,9)}-1{random.randint(0,9)} 14:00:00"

# ----- Templates -----
# (Pattern Name, [NL variations], Cypher template)
TEMPLATES = [
    # 1. Person -> Account (has_account)
    (
        "person_has_account",
        [
            "{name}이(가) 보유하고 있는(has_account) 계좌(vt_bacnt) 목록을 보여줘.",
            "인물 {name}의 계좌번호(actno)를 전부 조회해줘.",
            "피의자 {name} 명의로 개설된 은행 계좌(vt_bacnt)를 찾아줘.",
            "{name}이 소유한 계좌들을 리스트업해라.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (p:vt_psn {{name: '{name}'}})-[:has_account]->(b:vt_bacnt) RETURN p, b $$) AS (p agtype, b agtype);"
    ),
    # 2. Account -> Person (has_account reverse representation)
    (
        "account_owner",
        [
            "계좌번호 '{account}'을 가지고 있는(has_account) 사람을 찾아줘.",
            "'{account}' 계좌의 명의자(vt_psn)를 확인해줘.",
            "은행 계좌 '{account}'의 주인이 누구인지 조회해라.",
            "계좌번호 {account}에 연결된 인물을 추적해줘.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (b:vt_bacnt {{actno: '{account}'}})-[:has_account]->(p:vt_psn) RETURN p, b $$) AS (p agtype, b agtype);"
    ),
    # 3. Person -> Phone (owns_phone)
    (
        "person_owns_phone",
        [
            "{name}이(가) 소유한(owns_phone) 전화번호(vt_telno)를 찾아줘.",
            "인물 {name} 명의의 휴대폰 번호(telno)를 전부 가져와.",
            "용의자 {name}과 연결된 통신기기 전화번호를 리스트업해줘.",
            "{name}의 연락처 정보를 조회해라.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (p:vt_psn {{name: '{name}'}})-[:owns_phone]->(t:vt_telno) RETURN p, t $$) AS (p agtype, t agtype);"
    ),
    # 4. Transfer Amount (amount parameter is STRING!)
    (
        "transfer_amount",
        [
            "송금액(amount)이 문자열 '{amount}'인 이체 내역(vt_transfer)을 찾아줘.",
            "금액이 '{amount}'원인 계좌 이체(vt_transfer) 기록을 보여줘.",
            "'{amount}'원의 자금이 이동된 이체내역을 조회해라.",
            "정확히 '{amount}'만큼 이체된(transfer) 내역을 검색해줘.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (t:vt_transfer {{amount: '{amount}'}}) RETURN t $$) AS (t agtype);"
    ),
    # 5. Call Duration (duration parameter is STRING!)
    (
        "call_duration",
        [
            "통화시간(duration)이 문자열 '{duration}'인 통화내역(vt_call)을 찾아줘.",
            "정확히 '{duration}'초 동안 지속된 전화 통화 기록을 보여줘.",
            "duration 값이 '{duration}'인 통화(vt_call) 내역을 검색해라.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (c:vt_call) WHERE c->>'duration' = '{duration}' RETURN c $$) AS (c agtype);"
    ),
    # 6. Case -> Person (involves)
    (
        "case_involves_person",
        [
            "사건 '{case_id}'에 연루된(involves) 모든 사람들의 이름(name)을 알고 싶어.",
            "'{case_id}' 사건의 피의자 및 피해자(vt_psn) 목록을 보여줘.",
            "사건번호 {case_id}와 관련된 인물들을 모조리 찾아줘.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (c:vt_case {{name: '{case_id}'}})-[:involves]->(p:vt_psn) RETURN p $$) AS (p agtype);"
    ),
    # 7. Person -> IP (used_ip)
    (
        "person_used_ip",
        [
            "{name}이(가) 사용한(used_ip) IP 주소(vt_ip)를 찾아줘.",
            "인물 {name}의 접속 이력 중 IP 주소(ip_addr) 목록을 보여줘.",
            "{name}과(와) 연결된 네트워크 흔적(vt_ip)을 조회해라.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (p:vt_psn {{name: '{name}'}})-[:used_ip]->(i:vt_ip) RETURN p, i $$) AS (p agtype, i agtype);"
    ),
    # 8. IP -> Person
    (
        "ip_used_by_person",
        [
            "IP 주소(ip_addr)가 '{ip}'인 IP(vt_ip)를 사용한(used_ip) 인물들을 추출해줘.",
            "'{ip}' IP로 접속한 기록이 있는 수사 대상자(vt_psn)를 찾아줘.",
            "특정 IP '{ip}'를 할당받아 쓴 사람을 확인해라.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (p:vt_psn)-[:used_ip]->(i:vt_ip) WHERE i->>'ip_addr' = '{ip}' RETURN p, i $$) AS (p agtype, i agtype);"
    ),
    # 9. Transfer Path Pattern (from_account -> transfer -> to_account)
    (
        "transfer_path",
        [
            "계좌 '{account}'에서 나간(from_account) 이체(vt_transfer) 내역과 목적지 계좌(to_account) 경로를 정리해줘.",
            "출금 계좌가 '{account}'인 자금의 전체 이체 흐름을 보여줘.",
            "계좌 '{account}'에서 출발하여 다른 계좌로 자금이 넘어간 이력을 추적해라.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (b1:vt_bacnt {{actno: '{account}'}})-[:from_account]->(t:vt_transfer)-[:to_account]->(b2:vt_bacnt) RETURN b1, t, b2 $$) AS (b1 agtype, t agtype, b2 agtype);"
    ),
    # 10. Call Pattern (caller -> callee)
    (
        "call_path",
        [
            "전화번호 '{phone}'에서 발신(caller)되어 수신자(callee)에게 도달한 통화 기록(vt_call)을 찾아줘.",
            "'{phone}' 번호가 건 전화 기록을 통화내역(vt_call)에서 추적해줘.",
            "발신 번호 '{phone}'의 통화 방향 경로를 보여줘.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (t1:vt_telno {{telno: '{phone}'}})<-[:caller]-(c:vt_call)-[:callee]->(t2:vt_telno) RETURN t1, c, t2 $$) AS (t1 agtype, c agtype, t2 agtype);"
    ),
    # 11. Shortest Path (Graph DB 특화)
    (
        "shortest_path",
        [
            "{name}과(와) 인물 '{account}'(이름대신) 사이의 엮인 최단 경로(Shortest Path)를 보여줘.",
            "수사 대상자 {name}에서 시작해서 {account}로 향하는 연결망 최단 경로를 추출해줘.",
            "피의자 {name}과 {account}가 어떤 관계망으로 연결되어 있는지 최단경로 함수로 파악해라.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH path = shortest_path((p1:vt_psn {{name: '{name}'}})-[*1..5]-(p2:vt_psn {{name: '{account}'}})) RETURN path $$) AS (path agtype);"
    ),
    # 12. Type Casting (Numeric String Comparison)
    (
        "type_casting_amount",
        [
            "이체 금액(amount)이 {amount}원 이상(>=)인 초대형 이체 내역(vt_transfer)을 찾아줘.",
            "송금액이 {amount}을 넘는 계좌 이체(vt_transfer) 기록을 전부 조회해줘.",
            "숫자 {amount} 이상으로 자금이 움직인(amount) 이체내역을 추적해라.",
        ],
        "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (t:vt_transfer) WHERE (t->>'amount')::int >= {amount} RETURN t, t->>'amount' AS amount $$) AS (t agtype, amount agtype);"
    ),
]

def generate_sample():
    template_type, questions, cypher = random.choice(TEMPLATES)
    
    # Generate parameters
    params = {
        "name": get_name(),
        "account": get_account() if template_type != "shortest_path" else get_name(), # shortest_path에선 account 변수에 사람 이름 재활용
        "phone": get_phone(),
        "ip": get_ip(),
        "amount": get_amount(),
        "duration": get_duration(),
        "case_id": get_case(),
    }
    
    # Format instruction and cypher
    instruction = random.choice(questions).format(**params)
    output_cypher = cypher.format(**params)
    
    return {
        "instruction": instruction,
        "input": "Translate the natural language forensic question into a valid AgensGraph Cypher query.",
        "output": output_cypher,
        "graph_path": "tccop_graph_v6"
    }

def main():
    parser = argparse.ArgumentParser(description="Generate Massive Synthetic Data for KICS Ontology")
    parser.add_argument("--count", type=int, default=10000, help="Number of records to generate")
    parser.add_argument("--output", type=str, default="data/sft_dataset_10k_v3.jsonl", help="Output file path")
    
    args = parser.parse_args()
    
    print(f"Generating {args.count} synthetic ontology records...")
    
    samples = []
    # Using a set to ensure minimum uniqueness in instruction
    unique_instructions = set()
    
    with tqdm(total=args.count) as pbar:
        while len(samples) < args.count:
            sample = generate_sample()
            
            if sample["instruction"] not in unique_instructions:
                unique_instructions.add(sample["instruction"])
                samples.append(sample)
                pbar.update(1)
                
    # Save to file
    print(f"Saving to {args.output}...")
    with open(args.output, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
            
    print("Done! 🎉")

if __name__ == "__main__":
    main()
