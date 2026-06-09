#!/usr/bin/env python3
import os, json, random

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_SHAREGPT = os.path.join(BASE, "data", "ccop_v33_final_sharegpt.json")

SYSTEM_PROMPT = """You are an AgensGraph SQL-Wrapped Cypher query expert for cybercrime investigation (CCOP system).

SCHEMA (tccop_graph_v6):
Nodes:
  vt_psn(name), vt_bacnt(actno, bank_name), vt_telno(telno), vt_ip(ip_addr), vt_transfer(amount), vt_call(duration), vt_case(flnm), vt_petition(flnm), vt_org(org_name), vt_loc(address), vt_impersonation(event_id, method)

Edges (V3.3):
  has_account, owns_phone, used_ip, involves, from_account, to_account, caller, callee
  used_for, targets, filed_as, clusters_with, belongs_to, sameAs, resolves_to, eg_used_account, eg_used_phone

Output format:
  SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (a) RETURN a $$) AS (a agtype);
"""

def load_alpaca(path):
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            obj = json.loads(line)
            
            # 질문 추출 우선순위 적용 (버그 방어)
            question = obj.get("input", "")
            if not question or "Convert the following" in question:
                question = obj.get("instruction", "")
            
            if not question or "Convert the following" in question:
                continue

            samples.append({
                "human": question.strip(),
                "gpt": obj.get("output", "").strip()
            })
    print(f"로드 완료: {len(samples)}건 ({path})")
    return samples

def load_sharegpt(path):
    samples = []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        for conv in data:
            conversations = conv.get("conversations", [])
            human = next((c["value"] for c in conversations if c.get("from") == "human"), "")
            gpt = next((c["value"] for c in conversations if c.get("from") in ("gpt", "assistant")), "")
            if human and gpt and "Convert the following" not in human:
                samples.append({
                    "human": human.strip(),
                    "gpt": gpt.strip()
                })
    print(f"로드 완료: {len(samples)}건 ({path})")
    return samples

def main():
    random.seed(42)
    p1 = os.path.join(BASE, "data", "ccop_v4_synth_alpaca.jsonl")      # 23,000 건
    p2 = os.path.join(BASE, "data", "korean_cybercrime_sft.json")      # 10,000 건
    p3 = os.path.join(BASE, "data", "sft_multihop_v2_1k.jsonl")        #  1,000 건
    p4 = os.path.join(BASE, "data", "sft_v33_alpaca.jsonl")            # 15,000 건 (신규 V3.3)

    s1 = load_alpaca(p1)
    s2 = load_sharegpt(p2)
    s3 = load_alpaca(p3)
    s4 = load_alpaca(p4)

    all_samples = s1 + s2 + s3 + s4
    
    # 중복 제거
    seen = set()
    unique_samples = []
    for s in all_samples:
        key = (s["human"], s["gpt"])
        if key not in seen:
            seen.add(key)
            unique_samples.append(s)

    random.shuffle(unique_samples)

    sharegpt_data = []
    for s in unique_samples:
        sharegpt_data.append({
            "conversations": [
                {"from": "system", "value": SYSTEM_PROMPT},
                {"from": "human",  "value": s["human"]},
                {"from": "gpt",    "value": s["gpt"]},
            ]
        })

    with open(OUT_SHAREGPT, "w", encoding="utf-8") as f:
        json.dump(sharegpt_data, f, ensure_ascii=False, indent=2)

    print(f"\n최종 V3.3 무결점 SFT 데이터 저장 완료: {len(sharegpt_data)}건 -> {OUT_SHAREGPT}")

    # 샘플 출력
    print("\n[👀 생성된 데이터 샘플 Top 3 확인]")
    for i in range(3):
        print(f"\n--- 샘플 {i+1} ---")
        print(f"🗣️ 질문: {sharegpt_data[i]['conversations'][1]['value']}")
        print(f"🚀 정답: {sharegpt_data[i]['conversations'][2]['value']}")

if __name__ == "__main__":
    main()
