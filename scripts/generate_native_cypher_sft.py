"""
CCOP Native Cypher SFT 데이터셋 생성기
실제 DB 스키마 + 확인된 데이터 기반으로 고품질 학습 데이터를 생성합니다.

실제 확인된 DB 정보:
- vt_psn: 피의자1, 피의자2, 피해자1 등 10명
- vt_bacnt: 200-8888-888888(부산은행), 200-9999-999999(새마을금고), 110-1111-1111(국민은행) 등 7개
- vt_telno: 1099999999, 1000000001 등 10개 (하이픈 없음)
- vt_ip: 103.38.1.169, 203.108.1.223, 211.38.1.150 등 5개
- vt_transfer: amount='500000'(문자열) 등 20건
- vt_call: 25건
"""
import json
import random
import os

# ====================================================
# 실제 DB 확인 데이터 (실제 값으로 few-shot 강화)
# ====================================================
PERSONS = ["피의자1", "피의자2", "피해자1", "피해자2", "참고인1"]
ACCOUNTS = ["110-1111-1111", "200-8888-888888", "200-9999-999999", "300-7777-777777"]
PHONES = ["1099999999", "1000000001", "1084573455", "1099011111"]  # 하이픈 없음
IPS = ["203.108.1.223", "103.38.1.169", "211.38.1.150"]
BANKS = ["국민은행", "부산은행", "새마을금고", "신한은행", "하나은행"]
AMOUNTS = ["500000", "700000", "1000000", "3000000", "5000000", "10000000"]
CASES = ["CASE-2023-001", "CASE-2023-002", "CASE-2024-001"]

# ====================================================
# SFT 템플릿 정의 (질문 → 정확한 Native Cypher)
# ====================================================
def generate_sft_pairs():
    pairs = []

    # ── Layer 1: 단일 노드 검색 ──────────────────────────────
    for person in PERSONS:
        pairs.append({
            "instruction": f"이름이 '{person}'인 사람 노드를 찾아줘.",
            "output": f"MATCH (p:vt_psn {{name: '{person}'}}) RETURN p"
        })
        pairs.append({
            "instruction": f"{person} 정보 조회해줘",
            "output": f"MATCH (p:vt_psn {{name: '{person}'}}) RETURN p"
        })
        pairs.append({
            "instruction": f"수사 대상 {person}의 노드를 그래프에서 보여줘.",
            "output": f"MATCH (p:vt_psn {{name: '{person}'}}) RETURN p"
        })

    for acct in ACCOUNTS:
        pairs.append({
            "instruction": f"계좌번호가 '{acct}'인 계좌 정보를 보여줘.",
            "output": f"MATCH (b:vt_bacnt {{actno: '{acct}'}}) RETURN b"
        })
        pairs.append({
            "instruction": f"'{acct}' 계좌 찾아줘",
            "output": f"MATCH (b:vt_bacnt {{actno: '{acct}'}}) RETURN b"
        })

    for phone in PHONES:
        pairs.append({
            "instruction": f"전화번호가 '{phone}'인 통신기기 정보.",
            "output": f"MATCH (t:vt_telno {{telno: '{phone}'}}) RETURN t"
        })
        # 하이픈 있는 입력 → 하이픈 없는 쿼리 변환 학습
        phone_with_hyphen = phone[:3] + "-" + phone[3:7] + "-" + phone[7:]
        pairs.append({
            "instruction": f"전화번호 '{phone_with_hyphen}' 소유자 찾아줘.",
            "output": f"MATCH (p:vt_psn)-[:owns_phone]->(t:vt_telno {{telno: '{phone}'}}) RETURN p, t"
        })

    for ip in IPS:
        pairs.append({
            "instruction": f"IP 주소 '{ip}'에 대한 정보를 찾아줘.",
            "output": f"MATCH (i:vt_ip {{ip_addr: '{ip}'}}) RETURN i"
        })

    for bank in BANKS:
        pairs.append({
            "instruction": f"{bank} 계좌 목록 전부 뽑아줘.",
            "output": f"MATCH (b:vt_bacnt {{bank_name: '{bank}'}}) RETURN b"
        })
        pairs.append({
            "instruction": f"{bank}에 개설된 계좌들을 조회해.",
            "output": f"MATCH (b:vt_bacnt {{bank_name: '{bank}'}}) RETURN b"
        })

    # ── Layer 2: 인물-계좌 관계 (has_account) ──────────────────
    for person in PERSONS:
        pairs.append({
            "instruction": f"{person} 명의의 계좌 목록을 보여줘.",
            "output": f"MATCH (p:vt_psn {{name: '{person}'}})-[:has_account]->(b:vt_bacnt) RETURN p, b"
        })
        pairs.append({
            "instruction": f"{person}이 보유한 모든 계좌번호를 찾아줘.",
            "output": f"MATCH (p:vt_psn {{name: '{person}'}})-[:has_account]->(b:vt_bacnt) RETURN p.name, b.actno, b.bank_name"
        })
        pairs.append({
            "instruction": f"{person}의 계좌에서 나간 이체 내역 전부.",
            "output": f"MATCH (p:vt_psn {{name: '{person}'}})-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer) RETURN p, b, t"
        })
        pairs.append({
            "instruction": f"{person} 명의 계좌로 입금된 거래 이력을 찾아줘.",
            "output": f"MATCH (p:vt_psn {{name: '{person}'}})-[:has_account]->(b:vt_bacnt)-[:to_account]-(t:vt_transfer) RETURN p, b, t"
        })

    for acct in ACCOUNTS:
        pairs.append({
            "instruction": f"계좌번호 '{acct}'의 명의자는 누구야?",
            "output": f"MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt {{actno: '{acct}'}}) RETURN p, b"
        })
        pairs.append({
            "instruction": f"'{acct}' 계좌 주인을 찾아줘.",
            "output": f"MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt {{actno: '{acct}'}}) RETURN p, b"
        })
        pairs.append({
            "instruction": f"계좌 '{acct}'에서 출금된 이체 내역 전부 조회해.",
            "output": f"MATCH (b:vt_bacnt {{actno: '{acct}'}})-[:from_account]->(t:vt_transfer) RETURN b, t ORDER BY t.timestamp"
        })
        pairs.append({
            "instruction": f"'{acct}' 계좌로 입금된 거래 내역을 보여줘.",
            "output": f"MATCH (t:vt_transfer)-[:to_account]->(b:vt_bacnt {{actno: '{acct}'}}) RETURN t, b"
        })

    # ── Layer 3: 전화 관계 (owns_phone, caller, callee) ──────────
    for person in PERSONS:
        pairs.append({
            "instruction": f"{person}이 사용하는 전화번호 목록.",
            "output": f"MATCH (p:vt_psn {{name: '{person}'}})-[:owns_phone]->(t:vt_telno) RETURN p, t"
        })
        pairs.append({
            "instruction": f"{person}의 통화 기록 전체를 조회해줘.",
            "output": f"MATCH (p:vt_psn {{name: '{person}'}})-[:owns_phone]->(t:vt_telno)-[:caller]->(c:vt_call) RETURN p, t, c"
        })

    for phone in PHONES:
        pairs.append({
            "instruction": f"번호 '{phone}'에서 발신한 통화 기록 전부.",
            "output": f"MATCH (t:vt_telno {{telno: '{phone}'}})-[:caller]->(c:vt_call) RETURN t, c"
        })
        pairs.append({
            "instruction": f"'{phone}' 번호로 걸려온 수신 통화 내역.",
            "output": f"MATCH (c:vt_call)-[:callee]->(t:vt_telno {{telno: '{phone}'}}) RETURN c, t"
        })

    # ── Layer 4: IP 관계 (used_ip) ──────────────────────────────
    for person in PERSONS:
        pairs.append({
            "instruction": f"{person}이 접속에 사용한 IP 주소 목록.",
            "output": f"MATCH (p:vt_psn {{name: '{person}'}})-[:used_ip]->(i:vt_ip) RETURN p, i"
        })

    for ip in IPS:
        pairs.append({
            "instruction": f"'{ip}' IP를 사용하여 접속한 인물 목록.",
            "output": f"MATCH (p:vt_psn)-[:used_ip]->(i:vt_ip {{ip_addr: '{ip}'}}) RETURN p, i"
        })
        pairs.append({
            "instruction": f"IP '{ip}'로 접속한 수사 대상자 찾아줘.",
            "output": f"MATCH (p:vt_psn)-[:used_ip]->(i:vt_ip {{ip_addr: '{ip}'}}) RETURN p.name, i.ip_addr"
        })

    # ── Layer 5: 금액 필터링 (amount는 문자열) ──────────────────
    for threshold in ["1000000", "3000000", "5000000", "10000000"]:
        pairs.append({
            "instruction": f"이체 금액이 {int(threshold)//10000}만원({threshold}) 이상인 거래 내역.",
            "output": f"MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer) WHERE t.amount >= '{threshold}' RETURN b, t"
        })
        pairs.append({
            "instruction": f"{int(threshold)//10000}만원 이상 출금한 계좌와 이체 정보.",
            "output": f"MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt)-[:from_account]->(t:vt_transfer) WHERE t.amount >= '{threshold}' RETURN p, b, t"
        })

    pairs.append({
        "instruction": "소액 이체(50만원 미만) 내역을 찾아줘.",
        "output": "MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer) WHERE t.amount < '500000' RETURN b, t"
    })
    pairs.append({
        "instruction": "이체 금액이 정확히 50만원(500000)인 거래를 찾아.",
        "output": "MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer) WHERE t.amount = '500000' RETURN b, t"
    })

    # ── Layer 6: Multi-hop 추적 ──────────────────────────────────
    for p1, p2 in [("피의자1", "피해자1"), ("피의자2", "피해자1"), ("피의자1", "피의자2")]:
        pairs.append({
            "instruction": f"{p1}과 {p2} 사이에 연결된 자금 이동 경로를 추적해.",
            "output": f"MATCH (p1:vt_psn {{name: '{p1}'}})-[:has_account]->(b1:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b2:vt_bacnt)-[:has_account]-(p2:vt_psn {{name: '{p2}'}}) RETURN p1, b1, t, b2, p2"
        })
        pairs.append({
            "instruction": f"{p1}에서 {p2}로 가는 최단 관계 경로.",
            "output": f"MATCH path=shortestPath((p1:vt_psn {{name: '{p1}'}})-[*..5]-(p2:vt_psn {{name: '{p2}'}})) RETURN path"
        })

    for person in PERSONS[:3]:
        pairs.append({
            "instruction": f"{person}의 계좌, 전화, IP를 한꺼번에 조회해줘.",
            "output": f"MATCH (p:vt_psn {{name: '{person}'}}) OPTIONAL MATCH (p)-[:has_account]->(b:vt_bacnt) OPTIONAL MATCH (p)-[:owns_phone]->(t:vt_telno) OPTIONAL MATCH (p)-[:used_ip]->(i:vt_ip) RETURN p, b, t, i"
        })

    # ── Layer 7: 전체/집계 조회 ──────────────────────────────────
    pairs.extend([
        {
            "instruction": "그래프에 있는 모든 인물 목록을 보여줘.",
            "output": "MATCH (p:vt_psn) RETURN p"
        },
        {
            "instruction": "등록된 모든 계좌 정보를 조회해.",
            "output": "MATCH (b:vt_bacnt) RETURN b"
        },
        {
            "instruction": "이체 내역 전체를 시간순으로 정렬해서 보여줘.",
            "output": "MATCH (t:vt_transfer) RETURN t ORDER BY t.timestamp"
        },
        {
            "instruction": "모든 통화 기록을 보여줘.",
            "output": "MATCH (c:vt_call) RETURN c"
        },
        {
            "instruction": "현재 그래프에 등록된 IP 주소 전체 목록.",
            "output": "MATCH (i:vt_ip) RETURN i"
        },
        {
            "instruction": "의심스러운 IP에 접속한 피의자들과 그들의 계좌를 찾아줘.",
            "output": "MATCH (p:vt_psn)-[:used_ip]->(i:vt_ip) MATCH (p)-[:has_account]->(b:vt_bacnt) RETURN p, i, b"
        },
        {
            "instruction": "계좌 간 자금이 이동한 모든 이체 경로.",
            "output": "MATCH (b1:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b2:vt_bacnt) RETURN b1, t, b2"
        },
        {
            "instruction": "동일한 IP를 사용한 인물들을 그룹핑해서 보여줘.",
            "output": "MATCH (p:vt_psn)-[:used_ip]->(i:vt_ip) RETURN i.ip_addr, collect(p.name) AS users"
        },
        {
            "instruction": "가장 많은 이체를 한 계좌 TOP 5를 뽑아줘.",
            "output": "MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer) RETURN b.actno, count(t) AS cnt ORDER BY cnt DESC LIMIT 5"
        },
        {
            "instruction": "피의자들이 공통으로 사용한 IP 주소를 찾아줘.",
            "output": "MATCH (p1:vt_psn)-[:used_ip]->(i:vt_ip)<-[:used_ip]-(p2:vt_psn) WHERE p1 <> p2 RETURN i.ip_addr, p1.name, p2.name"
        }
    ])

    # ── Layer 8: B2C 비격식 한국어 ────────────────────────────────
    for acct in ACCOUNTS[:2]:
        pairs.append({
            "instruction": f"내 통장({acct})에서 돈 빼간 놈들 찾아줘",
            "output": f"MATCH (t:vt_transfer)-[:to_account]->(b:vt_bacnt {{actno: '{acct}'}}) MATCH (b2:vt_bacnt)-[:from_account]->(t) MATCH (p:vt_psn)-[:has_account]->(b2) RETURN p, b2, t"
        })
    pairs.extend([
        {
            "instruction": "국민은행 통장 튼 수상한 인간 다 뽑아봐",
            "output": "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt {bank_name: '국민은행'}) RETURN p, b"
        },
        {
            "instruction": "새벽에 이상한 IP로 접속한 놈 누구야",
            "output": "MATCH (p:vt_psn)-[:used_ip]->(i:vt_ip) RETURN p, i"
        },
        {
            "instruction": "피의자1이랑 피의자2가 같이 쓴 전화번호 있어?",
            "output": "MATCH (p1:vt_psn {name: '피의자1'})-[:owns_phone]->(t:vt_telno)<-[:owns_phone]-(p2:vt_psn {name: '피의자2'}) RETURN p1, t, p2"
        }
    ])

    return pairs


def to_alpaca_format(pairs, graph_path="tccop_graph_v6"):
    """Alpaca 형식으로 변환"""
    alpaca = []
    for p in pairs:
        alpaca.append({
            "instruction": p["instruction"],
            "input": f"Graph: {graph_path} | Generate AgensGraph Native Cypher query only.",
            "output": p["output"]
        })
    return alpaca


def to_sharegpt_format(pairs):
    """ShareGPT (대화) 형식으로 변환 - vLLM/LLaMA 파인튜닝에 최적"""
    system_msg = """You are an AgensGraph Native Cypher query expert for cybercrime investigation.

SCHEMA (Confirmed from actual DB):
Nodes: vt_psn(name,id,type), vt_bacnt(actno,bank_name★,bank_cd), vt_telno(telno★no-hyphen), vt_ip(ip_addr), vt_transfer(amount★string,timestamp), vt_call, vt_case(flnm,crime)

Edges:
- (vt_psn)-[:has_account]->(vt_bacnt)
- (vt_psn)-[:owns_phone]->(vt_telno)  
- (vt_psn)-[:used_ip]->(vt_ip)
- (vt_bacnt)-[:from_account]->(vt_transfer)-[:to_account]->(vt_bacnt)
- (vt_telno)-[:caller]->(vt_call)-[:callee]->(vt_telno)

RULES:
1. Output ONLY Native Cypher (MATCH...RETURN). NO SQL wrapper.
2. bank_name (NOT bank), telno without hyphens, amount as string comparison
3. One line, no newlines."""

    sharegpt = []
    for p in pairs:
        sharegpt.append({
            "conversations": [
                {"from": "system", "value": system_msg},
                {"from": "human", "value": p["instruction"]},
                {"from": "gpt", "value": p["output"]}
            ]
        })
    return sharegpt


if __name__ == "__main__":
    print("🔧 CCOP Native Cypher SFT 데이터 생성 중...")
    
    pairs = generate_sft_pairs()
    random.shuffle(pairs)
    
    print(f"✅ 총 {len(pairs)}개 SFT 쌍 생성 완료")
    
    # 출력 경로
    out_dir = "/Users/iankwon/test/coop_v1.0/data"
    os.makedirs(out_dir, exist_ok=True)
    
    # 1. Alpaca 형식 (JSONL)
    alpaca_path = f"{out_dir}/native_cypher_sft_alpaca.jsonl"
    alpaca_data = to_alpaca_format(pairs)
    with open(alpaca_path, "w", encoding="utf-8") as f:
        for item in alpaca_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"📄 Alpaca JSONL: {alpaca_path} ({len(alpaca_data)} samples)")
    
    # 2. ShareGPT 형식 (JSON)
    sharegpt_path = f"{out_dir}/native_cypher_sft_sharegpt.json"
    sharegpt_data = to_sharegpt_format(pairs)
    with open(sharegpt_path, "w", encoding="utf-8") as f:
        json.dump(sharegpt_data, f, ensure_ascii=False, indent=2)
    print(f"📄 ShareGPT JSON: {sharegpt_path} ({len(sharegpt_data)} samples)")
    
    # 3. 샘플 확인 출력
    print("\n" + "="*60)
    print("📊 샘플 데이터 확인 (처음 5개):")
    print("="*60)
    for i, p in enumerate(pairs[:5]):
        print(f"\n[{i+1}] 질문: {p['instruction']}")
        print(f"     쿼리: {p['output']}")
    
    print("\n" + "="*60)
    print(f"✅ SFT 데이터 생성 완료! 총 {len(pairs)}개")
    print(f"   - Alpaca:   {alpaca_path}")
    print(f"   - ShareGPT: {sharegpt_path}")
    print("="*60)
    print("\n다음 단계: LoRA 파인튜닝 실행")
    print("  scripts/run_native_cypher_lora.sh")
