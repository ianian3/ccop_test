"""
v3.7 최종 데이터셋을 train/eval로 층화 분할

입력:  data/ccop_v37_final_sharegpt.json (31,226개)
출력:
  train/t2c_v37_train.json  (~28,100개, 90%)
  train/t2c_v37_eval.json   (~3,100개, 10%)

층화 기준:
  (1) v3.7 신규 vs 호환 기존
  (2) hop 카테고리 (0-hop/1-hop/2-hop/3-hop/4-hop+/var-hop/shortestPath)

각 (v3.7 type × hop) 조합에서 10% 무작위 추출 → eval, 나머지 → train
"""

import json
import random
import re
from collections import defaultdict
from pathlib import Path

random.seed(42)

DATA_DIR = Path(__file__).parent
TRAIN_DIR = DATA_DIR.parent / "train"
INPUT = DATA_DIR / "ccop_v37_final_sharegpt.json"
OUT_TRAIN = TRAIN_DIR / "t2c_v37_train.json"
OUT_EVAL = TRAIN_DIR / "t2c_v37_eval.json"

EVAL_RATIO = 0.10

V37_PATTERNS = [
    'pt_cluster', 'site_cluster', 'belongs_to_cluster',
    'belongs_to_campaign', 'used_in_device', 'is_anonymous',
    "'relay_station'"
]


def get_response(sample):
    for t in sample["conversations"]:
        if t.get("from") in ("gpt", "assistant"):
            return t.get("value", "")
    return ""


def classify_hops(cypher: str) -> str:
    c = cypher.strip()
    if re.search(r'shortest_?path\s*\(', c, re.IGNORECASE):
        return 'shortestPath'
    if re.search(r'\[\s*[\w:]*\*[\d.]*\s*\]', c):
        return 'var-hop'
    arrow_pattern = re.compile(r'-\s*\[[^\]]*\]\s*->|<-\s*\[[^\]]*\]\s*-|-\s*\[[^\]]*\]\s*-')
    n = len(arrow_pattern.findall(c))
    if n == 0: return '0-hop'
    if n == 1: return '1-hop'
    if n == 2: return '2-hop'
    if n == 3: return '3-hop'
    return '4-hop+'


def is_v37_new(cypher: str) -> bool:
    return any(p in cypher for p in V37_PATTERNS)


def main():
    with open(INPUT, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 층화 키별 그룹화
    strata = defaultdict(list)
    for s in data:
        cypher = get_response(s)
        key = (
            'v37_new' if is_v37_new(cypher) else 'legacy',
            classify_hops(cypher),
        )
        strata[key].append(s)

    # 각 stratum에서 10% 무작위 추출 → eval
    train_set, eval_set = [], []
    print(f"📊 층화 분할 ({EVAL_RATIO*100:.0f}% eval):\n")
    print(f"{'stratum':<25s} {'total':>8s} {'train':>8s} {'eval':>8s}")
    print("─" * 55)
    for key, samples in sorted(strata.items()):
        random.shuffle(samples)
        n_eval = max(1, int(len(samples) * EVAL_RATIO))
        eval_part = samples[:n_eval]
        train_part = samples[n_eval:]
        eval_set.extend(eval_part)
        train_set.extend(train_part)
        label = f"{key[0]:<8s}/{key[1]}"
        print(f"{label:<25s} {len(samples):>8,} {len(train_part):>8,} {len(eval_part):>8,}")

    print("─" * 55)
    print(f"{'TOTAL':<25s} {len(data):>8,} {len(train_set):>8,} {len(eval_set):>8,}\n")

    # 셔플 (학습 순서 다양화)
    random.shuffle(train_set)
    random.shuffle(eval_set)

    with open(OUT_TRAIN, 'w', encoding='utf-8') as f:
        json.dump(train_set, f, ensure_ascii=False, indent=2)
    with open(OUT_EVAL, 'w', encoding='utf-8') as f:
        json.dump(eval_set, f, ensure_ascii=False, indent=2)

    print(f"✅ 저장:")
    print(f"   {OUT_TRAIN}  ({len(train_set):,}개)")
    print(f"   {OUT_EVAL}  ({len(eval_set):,}개)")


if __name__ == "__main__":
    main()
