"""
t2c_v2 Step 5: 병합·중복제거·분할

입력:  data/t2c_v2_validated.json
출력:
  data/t2c_v2_all.json       — 전체 (11,000개, 층화 트리밍)
  data/t2c_v2_train.json     — 학습용  (9,900개, 90%)
  data/t2c_v2_eval.json      — 검증용  (1,100개, 10%, 층화 추출)
  train/dataset_info.json    — LLaMA-Factory 데이터셋 등록 (업데이트)

분할 전략:
  - 중복 제거: gpt 응답 기준 exact-match
  - 층화 추출: QUERY(단일/멀티)/GENERAL/GUARD 비율 유지
  - 11,000 초과 시 QUERY 중 멀티홉 랜덤 제거로 트리밍
"""

import json
import random
from pathlib import Path
from collections import Counter, defaultdict

SEED = 42
random.seed(SEED)

SRC_PATH    = Path("data/t2c_v2_validated.json")
ALL_PATH    = Path("data/t2c_v2_all.json")
TRAIN_PATH  = Path("data/t2c_v2_train.json")
EVAL_PATH   = Path("data/t2c_v2_eval.json")
DATASET_INFO_PATH = Path("train/dataset_info.json")

TARGET_TOTAL   = 11_000
EVAL_RATIO     = 0.10

# 목표 Intent 비율
TARGET_INTENT = {
    "QUERY":   9_500,
    "GENERAL": 750,   # 500+200 (manual 보강 포함)
    "GUARD":   750,   # 500+300
}


def get_gpt(sample: dict) -> str:
    for c in sample.get("conversations", []):
        if c.get("from") == "gpt":
            return c.get("value", "")
    return ""


def has_edge(gpt: str) -> bool:
    import re
    return bool(re.search(r"\[\w*:[a-z_*]+", gpt))


def get_human(sample: dict) -> str:
    for c in sample.get("conversations", []):
        if c.get("from") == "human":
            v = c.get("value", "")
            # [질문] 섹션만 키로 사용
            if "[질문]" in v:
                return v.split("[질문]")[-1].strip()
            return v[-150:].strip()
    return ""


def dedup(samples: list[dict]) -> list[dict]:
    """(질문, GPT응답) 쌍 기준 중복 제거 — 같은 Cypher라도 질문이 다르면 유지"""
    seen = set()
    result = []
    for s in samples:
        q   = get_human(s)
        ans = get_gpt(s).strip()
        key = (q, ans)
        if key not in seen:
            seen.add(key)
            result.append(s)
    return result


def stratified_sample(samples: list[dict], n: int) -> list[dict]:
    """
    Intent + 단일노드/멀티홉 층 기준으로 n개 비율 유지 추출
    """
    # 층 분류
    strata: dict[str, list[dict]] = defaultdict(list)
    for s in samples:
        intent = s.get("intent", "QUERY")
        if intent == "QUERY":
            gpt = get_gpt(s)
            key = "QUERY_MULTI" if has_edge(gpt) else "QUERY_SINGLE"
        else:
            key = intent
        strata[key].append(s)

    total = len(samples)
    result = []
    for key, group in strata.items():
        quota = max(1, round(len(group) / total * n))
        random.shuffle(group)
        result.extend(group[:quota])

    # 수량 보정
    random.shuffle(result)
    if len(result) < n:
        remaining = [s for s in samples if s not in set(id(x) for x in result)]
        result.extend(random.sample(remaining, min(n - len(result), len(remaining))))
    return result[:n]


def update_dataset_info(path: Path) -> None:
    """LLaMA-Factory dataset_info.json에 t2c_v2 등록"""
    if not path.exists():
        info = {}
    else:
        with open(path, encoding="utf-8") as f:
            info = json.load(f)

    info["t2c_v2"] = {
        "file_name": "t2c_v2_train.json",
        "file_sha256": "",
        "formatting": "sharegpt",
        "columns": {
            "messages": "conversations",
            "system": "system",
        },
        "tags": {
            "role_tag": "from",
            "content_tag": "value",
            "user_tag": "human",
            "assistant_tag": "gpt",
            "system_tag": "system",
        },
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print(f"  dataset_info.json 업데이트 → {path}")


def main():
    with open(SRC_PATH, encoding="utf-8") as f:
        data: list[dict] = json.load(f)
    print(f"입력: {len(data):,}개")

    # 1. 중복 제거
    data = dedup(data)
    print(f"중복 제거 후: {len(data):,}개")

    # 2. Intent별 분류
    by_intent: dict[str, list[dict]] = defaultdict(list)
    for s in data:
        by_intent[s.get("intent", "QUERY")].append(s)
    for k, v in by_intent.items():
        print(f"  {k}: {len(v):,}")

    # 3. Intent별 트리밍 (목표 초과 시 랜덤 제거)
    trimmed: list[dict] = []
    for intent, target in TARGET_INTENT.items():
        group = by_intent.get(intent, [])
        if len(group) > target:
            # QUERY는 단일노드 우선 보존, 멀티홉에서 제거
            if intent == "QUERY":
                single = [s for s in group if not has_edge(get_gpt(s))]
                multi  = [s for s in group if has_edge(get_gpt(s))]
                random.shuffle(multi)
                keep = single + multi[:max(0, target - len(single))]
            else:
                random.shuffle(group)
                keep = group[:target]
        else:
            keep = group
        trimmed.extend(keep)

    # 남은 intent (TARGET_INTENT에 없는 것)
    for intent, group in by_intent.items():
        if intent not in TARGET_INTENT:
            trimmed.extend(group)

    print(f"\n트리밍 후: {len(trimmed):,}개")

    random.shuffle(trimmed)
    all_data = trimmed

    # 4. 전체 저장
    ALL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(ALL_PATH, "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)

    # 5. 층화 분할 (eval 10%)
    n_eval = max(100, round(len(all_data) * EVAL_RATIO))

    eval_data  = stratified_sample(all_data, n_eval)
    eval_ids   = {id(s) for s in eval_data}
    train_data = [s for s in all_data if id(s) not in eval_ids]

    with open(TRAIN_PATH, "w", encoding="utf-8") as f:
        json.dump(train_data, f, ensure_ascii=False, indent=2)
    with open(EVAL_PATH, "w", encoding="utf-8") as f:
        json.dump(eval_data, f, ensure_ascii=False, indent=2)

    # 6. dataset_info.json 업데이트
    if DATASET_INFO_PATH.exists():
        update_dataset_info(DATASET_INFO_PATH)
    else:
        print(f"  [SKIP] {DATASET_INFO_PATH} 없음 (수동 업데이트 필요)")

    # 7. 최종 리포트
    train_intents = Counter(s.get("intent") for s in train_data)
    eval_intents  = Counter(s.get("intent") for s in eval_data)

    print(f"\n=== 05_merge_split 완료 ===")
    print(f"  전체:  {len(all_data):,}개 → {ALL_PATH}")
    print(f"  train: {len(train_data):,}개 → {TRAIN_PATH}")
    print(f"  eval:  {len(eval_data):,}개 → {EVAL_PATH}")
    print(f"\n  train Intent: {dict(train_intents)}")
    print(f"  eval  Intent: {dict(eval_intents)}")

    # QUERY 복잡도 분포 (train)
    single = sum(1 for s in train_data
                 if s.get("intent") == "QUERY" and not has_edge(get_gpt(s)))
    multi  = sum(1 for s in train_data
                 if s.get("intent") == "QUERY" and has_edge(get_gpt(s)))
    q_total = single + multi
    if q_total:
        print(f"\n  train QUERY 복잡도:")
        print(f"    단일노드: {single:,}  ({single/q_total*100:.1f}%)")
        print(f"    멀티홉:   {multi:,}  ({multi/q_total*100:.1f}%)")


if __name__ == "__main__":
    main()
