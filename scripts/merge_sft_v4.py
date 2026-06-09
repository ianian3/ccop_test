#!/usr/bin/env python3
"""
CCOP SFT 데이터 V4 병합기
==========================
기존 korean_cybercrime_sft.json (10,143개) +
신규 ccop_v4_synth_sharegpt.json (23,000개) →
ccop_v4_merged_sharegpt.json (최종 학습 데이터)

실행:
  python3 scripts/merge_sft_v4.py
"""

import os, json, random
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXISTING = os.path.join(BASE, "data", "korean_cybercrime_sft.json")
NEW_DATA  = os.path.join(BASE, "data", "ccop_v4_synth_sharegpt.json")
OUT_MERGED = os.path.join(BASE, "data", "ccop_v4_merged_sharegpt.json")
OUT_ALPACA  = os.path.join(BASE, "data", "ccop_v4_merged_alpaca.jsonl")

SYSTEM_PROMPT_NATIVE = """You are an AgensGraph Native Cypher query expert for cybercrime investigation (CCOP system).

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

Output: AgensGraph Native Cypher only (MATCH...RETURN, no SQL wrapper)"""


def load_existing(path: str):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"  기존 데이터: {len(data):,}개  ({path})")
    return data


def load_new(path: str):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"  신규 데이터: {len(data):,}개  ({path})")
    return data


def categorize(conv_list):
    """conversations 리스트에서 카테고리 추정"""
    gpt_val = next((c["value"] for c in conv_list if c.get("from") in ("gpt","assistant")), "")
    cu = gpt_val.upper()
    if gpt_val.startswith("GENERAL:"):
        return "guardrail"
    if "SHORTESTPATH" in cu:
        return "path"
    if any(h in cu for h in ["*1..","*2..","*3..","*4..","*5.."]):
        return "multihop"
    if "WHERE" in cu and any(op in cu for op in [">=","<=","TOFLOAT","::INT","->>"]):
        return "filter"
    if any(r in gpt_val for r in ["from_account","to_account","caller","callee","eg_used"]):
        return "direction"
    if "MATCH" in cu:
        return "basic"
    return "other"


def merge_and_shuffle(existing, new_data, seed=42):
    random.seed(seed)
    combined = existing + new_data
    random.shuffle(combined)
    return combined


def analyze(data):
    cats = Counter()
    for item in data:
        conv = item.get("conversations", [])
        cats[categorize(conv)] += 1
    total = len(data)
    print(f"\n  {'카테고리':12} {'개수':>7}  {'비율':>6}  {'분포':}")
    for cat, cnt in sorted(cats.items(), key=lambda x: -x[1]):
        bar = "█" * (cnt * 25 // total)
        print(f"  {cat:12} {cnt:7,}  {cnt/total*100:5.1f}%  {bar}")
    print(f"  {'합계':12} {total:7,}  100.0%")


def to_alpaca(item):
    conv = item.get("conversations", [])
    question = next((c["value"] for c in conv if c.get("from") == "human"), "")
    answer   = next((c["value"] for c in conv if c.get("from") in ("gpt","assistant")), "")
    return {
        "instruction": "Convert the following natural language question into an AgensGraph Cypher query for cybercrime investigation.",
        "input":  question,
        "output": answer,
        "graph_path": "tccop_graph_v6",
    }


def main():
    print("[CCOP V4 SFT 병합기]")
    print()

    if not os.path.exists(NEW_DATA):
        print(f"ERROR: 신규 데이터 없음 ({NEW_DATA})")
        print("먼저 실행: python3 scripts/generate_v3_synth_sft.py")
        return

    print("[1/3] 데이터 로드...")
    existing = load_existing(EXISTING)
    new_data = load_new(NEW_DATA)

    print("\n[2/3] 병합 및 셔플...")
    merged = merge_and_shuffle(existing, new_data)
    print(f"  병합 결과: {len(merged):,}개")

    analyze(merged)

    print("\n[3/3] 저장...")
    with open(OUT_MERGED, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    size_mb = os.path.getsize(OUT_MERGED) / 1024 / 1024
    print(f"  ShareGPT: {OUT_MERGED}  ({len(merged):,}개, {size_mb:.1f}MB)")

    with open(OUT_ALPACA, "w", encoding="utf-8") as f:
        for item in merged:
            f.write(json.dumps(to_alpaca(item), ensure_ascii=False) + "\n")
    size_mb = os.path.getsize(OUT_ALPACA) / 1024 / 1024
    print(f"  Alpaca:   {OUT_ALPACA}  ({len(merged):,}개, {size_mb:.1f}MB)")

    print(f"\n[완료] 최종 학습 데이터: {len(merged):,}개")
    print(f"  LLaMA-Factory 설정:")
    print(f"    dataset: ccop_v4_merged")
    print(f"    dataset_dir: data/")
    print(f"    format: sharegpt")


if __name__ == "__main__":
    main()
