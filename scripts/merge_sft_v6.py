#!/usr/bin/env python3
"""
CCOP SFT 데이터 V3.2 통합 병합기 (V6)
=====================================
기존 안정화된 ccop_v5_merged 데이터셋(~34,000개)과 
신규 V3.2 전용 sft_v32 데이터셋(~15,000개)을 혼합합니다.

출력:
  data/ccop_v32_merged_alpaca.jsonl
  data/ccop_v32_merged_sharegpt.json
"""

import os, json, random
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SRC_V5       = os.path.join(BASE, "data", "ccop_v5_merged_alpaca.jsonl")      # 기존 V5 안정화 데이터
SRC_V32      = os.path.join(BASE, "data", "sft_v32_alpaca.jsonl")             # 신규 V3.2 집중 데이터

OUT_ALPACA   = os.path.join(BASE, "data", "ccop_v32_merged_alpaca.jsonl")
OUT_SHAREGPT = os.path.join(BASE, "data", "ccop_v32_merged_sharegpt.json")

SYSTEM_PROMPT = """You are an AgensGraph SQL-Wrapped Cypher query expert for cybercrime investigation (CCOP system).

SCHEMA (tccop_graph_v6):
Nodes:
  vt_psn(name), vt_bacnt(actno, bank_name), vt_telno(telno), vt_ip(ip_addr), vt_transfer(amount), vt_call(duration), vt_case(flnm), vt_petition(flnm), vt_org(org_name), vt_loc(address)

Edges (V3.2):
  has_account, owns_phone, used_ip, involves, from_account, to_account, caller, callee
  impersonates, filed_as, clusters_with, belongs_to, sameAs, resolves_to, eg_used_account, eg_used_phone

Output format:
  SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (a) RETURN a $$) AS (a agtype);
"""


def load_alpaca(path: str) -> list:
    """Alpaca JSONL 로드"""
    samples = []
    if not os.path.exists(path):
        print(f"  ❌ 파일 없음: {path}")
        return samples
        
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
            })
    print(f"  로드 완료: {len(samples):,}개  ({path})")
    return samples

def deduplicate(samples: list) -> list:
    seen = set()
    out = []
    for s in samples:
        # 입력 질문과 정답 쿼리를 키로 사용
        key = (s["input"].strip(), s["output"].strip())
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out

def to_alpaca_line(s: dict) -> dict:
    return {
        "instruction": "Convert the following natural language question into an AgensGraph SQL-Wrapped Cypher query.",
        "input":       s["input"],
        "output":      s["output"],
    }

def to_sharegpt(s: dict) -> dict:
    return {
        "conversations": [
            {"from": "system",    "value": SYSTEM_PROMPT},
            {"from": "human",     "value": s["input"]},
            {"from": "assistant", "value": s["output"]},
        ]
    }

def main():
    random.seed(42)
    print("\n=== CCOP V3.2 SFT 최종 데이터 병합 ===\n[소스 로드]")

    v5_data = load_alpaca(SRC_V5)
    v32_data = load_alpaca(SRC_V32)

    merged = v5_data + v32_data
    print(f"\n  병합 전 합계: {len(merged):,}개")

    merged = deduplicate(merged)
    print(f"  중복 제거 후: {len(merged):,}개")

    random.shuffle(merged)

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
    
    print("\n  🚀 다음 단계: LLaMA-Factory를 이용한 훈련. ")
    print(f"  ex) scp data/ccop_v32_merged_sharegpt.json ai-kyw-dev@192.168.1.133:~/sft_data/\n")

if __name__ == "__main__":
    main()
