#!/usr/bin/env python3
"""
CCOP SFT 데이터 V5 병합기
==========================
B안: synth(~23k) + korean_cybercrime(10,143) + multihop(1,000) → ~34,000개

실행 순서:
  1. python3 scripts/generate_v3_synth_sft.py --target 33130
  2. python3 scripts/merge_sft_v5.py

출력:
  data/ccop_v5_merged_alpaca.jsonl
  data/ccop_v5_merged_sharegpt.json
"""

import os, json, random
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRC_SYNTH        = os.path.join(BASE, "data", "ccop_v4_synth_alpaca.jsonl")   # generate_v3 출력
SRC_CYBERCRIME   = os.path.join(BASE, "data", "korean_cybercrime_sft.json")   # ShareGPT 포맷
SRC_MULTIHOP     = os.path.join(BASE, "data", "sft_multihop_v2_1k.jsonl")     # Alpaca 포맷

OUT_ALPACA   = os.path.join(BASE, "data", "ccop_v5_merged_alpaca.jsonl")
OUT_SHAREGPT = os.path.join(BASE, "data", "ccop_v5_merged_sharegpt.json")

SYSTEM_PROMPT = """You are an AgensGraph SQL-Wrapped Cypher query expert for cybercrime investigation (CCOP system).

CONFIRMED DB SCHEMA (tccop_graph_v6):
Nodes: vt_psn(name,id,type), vt_bacnt(actno,bank_name★,bank_cd), vt_telno(telno★no-hyphen),
       vt_ip(ip_addr), vt_transfer(amount★string,timestamp), vt_call, vt_case(flnm,crime)

Edges (direction matters!):
  (p:vt_psn)-[:has_account]->(b:vt_bacnt)
  (p:vt_psn)-[:owns_phone]->(t:vt_telno)
  (p:vt_psn)-[:used_ip]->(i:vt_ip)
  (c:vt_case)-[:involves]->(p:vt_psn)
  (b:vt_bacnt)-[:from_account]->(t:vt_transfer)
  (t:vt_transfer)-[:to_account]->(b:vt_bacnt)
  (t:vt_telno)-[:caller]->(c:vt_call)
  (c:vt_call)-[:callee]->(t:vt_telno)

Output: AgensGraph SQL-Wrapped Cypher only (SELECT * FROM cypher(...))"""


def load_synth_alpaca(path: str) -> list:
    """generate_v3_synth_sft.py 출력 (Alpaca JSONL)"""
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            samples.append({
                "instruction": obj.get("instruction", ""),
                "input":       obj.get("input", ""),
                "output":      obj.get("output", ""),
                "category":    obj.get("category", "synth"),
            })
    print(f"  synth (alpaca):       {len(samples):,}개  ({path})")
    return samples


def load_cybercrime_sharegpt(path: str) -> list:
    """korean_cybercrime_sft.json (ShareGPT) → Alpaca 변환"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    samples = []
    for conv in data:
        conversations = conv.get("conversations", [])
        human_turn = next((c["value"] for c in conversations if c.get("from") == "human"), "")
        gpt_turn   = next((c["value"] for c in conversations if c.get("from") in ("gpt", "assistant")), "")
        if not human_turn or not gpt_turn:
            continue

        # 카테고리 추정
        upper = gpt_turn.upper()
        if gpt_turn.startswith("GENERAL:"):
            cat = "guardrail"
        elif "SHORTESTPATH" in upper:
            cat = "path"
        elif upper.count("->") >= 3 or upper.count("-[") >= 3:
            cat = "multihop"
        elif "WHERE" in upper:
            cat = "filter"
        else:
            cat = "direction"

        samples.append({
            "instruction": human_turn,
            "input":       "",
            "output":      gpt_turn,
            "category":    cat,
        })

    print(f"  korean_cybercrime:    {len(samples):,}개  ({path})")
    return samples


def load_multihop_alpaca(path: str) -> list:
    """sft_multihop_v2_1k.jsonl (Alpaca JSONL)"""
    samples = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            samples.append({
                "instruction": obj.get("instruction", ""),
                "input":       obj.get("input", ""),
                "output":      obj.get("output", ""),
                "category":    "multihop",
            })
    print(f"  multihop:             {len(samples):,}개  ({path})")
    return samples


def deduplicate(samples: list) -> list:
    seen = set()
    out = []
    for s in samples:
        key = (s["instruction"].strip(), s["output"].strip())
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def to_alpaca_line(s: dict) -> dict:
    return {
        "instruction": "Convert the following natural language question into an AgensGraph SQL-Wrapped Cypher query.",
        "input":       s["instruction"],
        "output":      s["output"],
    }


def to_sharegpt(s: dict) -> dict:
    return {
        "conversations": [
            {"from": "system",    "value": SYSTEM_PROMPT},
            {"from": "human",     "value": s["instruction"]},
            {"from": "assistant", "value": s["output"]},
        ]
    }


def analyze(samples: list):
    cats = Counter(s.get("category", "unknown") for s in samples)
    print("\n  [카테고리 분포]")
    for cat, cnt in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"    {cat:12}: {cnt:,}개  ({cnt/len(samples)*100:.1f}%)")


def main():
    random.seed(42)
    print("\n=== CCOP V5 SFT 데이터 병합 ===\n[소스 로드]")

    synth      = load_synth_alpaca(SRC_SYNTH)
    cybercrime = load_cybercrime_sharegpt(SRC_CYBERCRIME)
    multihop   = load_multihop_alpaca(SRC_MULTIHOP)

    merged = synth + cybercrime + multihop
    print(f"\n  병합 전 합계: {len(merged):,}개")

    merged = deduplicate(merged)
    print(f"  중복 제거 후: {len(merged):,}개")

    random.shuffle(merged)
    analyze(merged)

    # Alpaca JSONL 저장
    with open(OUT_ALPACA, "w", encoding="utf-8") as f:
        for s in merged:
            f.write(json.dumps(to_alpaca_line(s), ensure_ascii=False) + "\n")
    print(f"\n  ✅ Alpaca 저장: {OUT_ALPACA}  ({len(merged):,}개)")

    # ShareGPT JSON 저장
    sharegpt_data = [to_sharegpt(s) for s in merged]
    with open(OUT_SHAREGPT, "w", encoding="utf-8") as f:
        json.dump(sharegpt_data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ ShareGPT 저장: {OUT_SHAREGPT}  ({len(sharegpt_data):,}개)")

    print(f"\n  → 학습 시: train/train_exaone_lora_v5.yaml 의 max_samples: {len(merged)} 확인\n")


if __name__ == "__main__":
    main()
