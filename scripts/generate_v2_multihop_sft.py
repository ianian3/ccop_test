import os
import json
import random

OUTPUT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/sft_multihop_v2_1k.jsonl'))

ATMS = [f"ATM-부산{str(i).zfill(3)}" for i in range(1, 100)] + [f"ATM-서울{str(i).zfill(3)}" for i in range(1, 100)]
IPS = [f"192.168.{random.randint(0,255)}.{random.randint(1,255)}" for _ in range(200)] + [f"103.22.{random.randint(10,50)}.1" for _ in range(50)]
SITES = ["www.illegal-bet.com", "casino-vip777.net", "scam-loan88.co.kr", "phishing-warning.kr", "darkweb-market.onion"]
CARS = [f"{random.randint(10, 99)}가 {random.randint(1000, 9999)}" for _ in range(500)]
PHONES = [f"010-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}" for _ in range(500)]
ACCOUNTS = [f"{random.randint(100, 999)}-{random.randint(100000, 999999)}-{random.randint(10, 99)}" for _ in range(500)]
PERSONS = ["김철수", "이영희", "박지성", "최동석", "강백호", "용의자A", "피의자1", "조폭김씨", "황자금"]

TEMPLATES = [
    {
        "questions": ["특정 ATM 기기 '{atm}'에서 돈을 입금시킨 사람들의 이름 찾아줘.", "ATM '{atm}'에서 이체된 자금의 출금 계좌 소유자를 전부 뽑아."],
        "cypher": "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (p:vt_psn)-[r1:has_account]->(b:vt_bacnt)-[r2:from_account]->(t:vt_transfer)-[r3:to_account]->(a:vt_atm {{atm_id: '{atm}'}}) RETURN p, r1, b, r2, t, r3, a $$) AS (p agtype, r1 agtype, b agtype, r2 agtype, t agtype, r3 agtype, a agtype);"
    },
    {
        "questions": ["IP 주소 '{ip}'를 사용해서 접속한 전화기 소유자", "'{ip}'에서 로그인 이력이 있는 폰을 가진 사람 찾아줘."],
        "cypher": "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (p:vt_psn)-[r1:owns_phone]->(tel:vt_telno)-[r2:used_ip]->(i:vt_ip {{ip_addr: '{ip}'}}) RETURN p, r1, tel, r2, i $$) AS (p agtype, r1 agtype, tel agtype, r2 agtype, i agtype);"
    },
    {
        "questions": ["불법 사이트 '{site}'에 접속한 적 있는 사람 찾기", "주소 '{site}' 도메인에 연결된 IP를 쓴 놈들 수사해."],
        "cypher": "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (p:vt_psn)-[r1:owns_phone]->(tel:vt_telno)-[r2:used_ip]->(i:vt_ip)-[r3:accessed]->(s:vt_site {{url: '{site}'}}) RETURN p, r1, tel, r2, i, r3, s $$) AS (p agtype, r1 agtype, tel agtype, r2 agtype, i agtype, r3 agtype, s agtype);"
    },
    {
        "questions": ["차량번호 '{car}' 차주의 계좌에서 이체된 내역들", "번호판 '{car}'인 차를 가진 사람의 계좌 출금 내역 싹 뽑아."],
        "cypher": "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (c:vt_car {{car_no: '{car}'}})<-[r1:owns_car]-(p:vt_psn)-[r2:has_account]->(b:vt_bacnt)-[r3:from_account]->(t:vt_transfer) RETURN c, r1, p, r2, b, r3, t $$) AS (c agtype, r1 agtype, p agtype, r2 agtype, b agtype, r3 agtype, t agtype);"
    },
    {
        "questions": ["'{person}'이라는 이름의 피의자가 접속한 사이트의 IP와, 해당 IP 대역에서 주로 접근하는 ATM 기기 망을 연관지어줘"],
        "cypher": "SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (p:vt_psn {{name: '{person}'}})-[:accessed]->(s:vt_site)<-[:hosted_on]-(i:vt_ip)-[:located_near]->(a:vt_atm) RETURN p, s, i, a $$) AS (p agtype, s agtype, i agtype, a agtype);"
    }
]

def generate_dataset():
    generated = 0
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        while generated < 1000:
            template = random.choice(TEMPLATES)
            q_template = random.choice(template["questions"])
            
            atm = random.choice(ATMS)
            ip = random.choice(IPS)
            site = random.choice(SITES)
            car = random.choice(CARS)
            act = random.choice(ACCOUNTS)
            person = random.choice(PERSONS)
            
            question = q_template.format(atm=atm, ip=ip, site=site, car=car, act=act, person=person)
            cypher = template["cypher"].format(atm=atm, ip=ip, site=site, car=car, act=act, person=person)
            
            # Use original Alpaca format matching 'train_lora.py'
            dialogue = {
                "instruction": "Convert the following natural language question into an AgensGraph Cypher query.",
                "input": question,
                "output": cypher,
                "graph_path": "tccop_graph_v6"
            }
            f.write(json.dumps(dialogue, ensure_ascii=False) + "\n")
            generated += 1

if __name__ == "__main__":
    generate_dataset()
