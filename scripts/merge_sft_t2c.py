"""
merge_sft_t2c.py — Phase 2 Step 5
검증된 SFT 데이터를 병합하고 학습/검증 세트로 분할
입력:  data/t2c_v1_all_validated.json  (또는 개별 validated 파일들)
출력:
  data/t2c_v1_sharegpt.json      (전체, 최대 10,000개)
  data/t2c_v1_train.json         (학습용, 9,500개)
  data/t2c_v1_eval.json          (검증용, 500개)
  train/dataset_info.json        (LLaMA-Factory 등록용 업데이트)
"""

import json
import os
import random
import argparse
from collections import Counter

random.seed(42)


# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

DEFAULT_INPUTS = [
    "data/t2c_v1_template_validated.json",
    "data/t2c_v1_augmented_validated.json",
    "data/t2c_v1_manual_validated.json",
]
FALLBACK_INPUT = "data/t2c_v1_all_validated.json"

TARGET_TOTAL = 10_000
EVAL_SIZE = 500


# ─────────────────────────────────────────────────────────────
# 병합 및 분할
# ─────────────────────────────────────────────────────────────

def load_samples(input_files: list) -> list:
    all_samples = []
    for path in input_files:
        if not os.path.exists(path):
            print(f"  ⚠ 없음 (스킵): {path}")
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        print(f"  로드: {path} → {len(data)}개")
        all_samples.extend(data)
    return all_samples


def deduplicate(samples: list) -> list:
    seen = set()
    result = []
    for s in samples:
        convs = s.get("conversations", [])
        if len(convs) < 2:
            continue
        key = convs[1].get("value", "")
        if key not in seen:
            seen.add(key)
            result.append(s)
    print(f"  중복 제거: {len(samples)} → {len(result)}개")
    return result


def stratified_split(samples: list, eval_size: int) -> tuple:
    """인텐트 비율을 유지하면서 eval 셋 분리"""
    intent_groups: dict = {}
    for s in samples:
        intent = s.get("intent", "QUERY")
        intent_groups.setdefault(intent, []).append(s)

    eval_set = []
    train_set = []

    total = len(samples)
    for intent, group in intent_groups.items():
        n_eval = max(1, round(len(group) / total * eval_size))
        n_eval = min(n_eval, len(group))
        random.shuffle(group)
        eval_set.extend(group[:n_eval])
        train_set.extend(group[n_eval:])

    # eval_size 맞추기
    random.shuffle(eval_set)
    if len(eval_set) > eval_size:
        train_set.extend(eval_set[eval_size:])
        eval_set = eval_set[:eval_size]
    elif len(eval_set) < eval_size:
        deficit = eval_size - len(eval_set)
        extra = train_set[:deficit]
        train_set = train_set[deficit:]
        eval_set.extend(extra)

    random.shuffle(train_set)
    random.shuffle(eval_set)
    return train_set, eval_set


def clean_sample(s: dict) -> dict:
    """학습용 필드만 남기기 (_augmented, _source 등 메타 제거)"""
    return {
        "conversations": s["conversations"],
        "intent": s.get("intent", "QUERY"),
    }


# ─────────────────────────────────────────────────────────────
# dataset_info.json 업데이트
# ─────────────────────────────────────────────────────────────

DATASET_INFO_ENTRY = {
    "t2c_v1": {
        "file_name": "../data/t2c_v1_train.json",
        "formatting": "sharegpt",
        "columns": {
            "messages": "conversations",
            "system": "system",
        },
    },
    "t2c_v1_eval": {
        "file_name": "../data/t2c_v1_eval.json",
        "formatting": "sharegpt",
        "columns": {
            "messages": "conversations",
            "system": "system",
        },
    },
}


def update_dataset_info(train_dir: str = "train"):
    """train/dataset_info.json에 t2c_v1 항목 추가"""
    dataset_info_path = os.path.join(train_dir, "dataset_info.json")

    if os.path.exists(dataset_info_path):
        with open(dataset_info_path, encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = {}

    # t2c_v1 항목이 이미 있으면 업데이트, 없으면 추가
    for key, val in DATASET_INFO_ENTRY.items():
        existing[key] = val

    os.makedirs(train_dir, exist_ok=True)
    with open(dataset_info_path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"  dataset_info.json 업데이트: {dataset_info_path}")
    return dataset_info_path


# ─────────────────────────────────────────────────────────────
# 통계 출력
# ─────────────────────────────────────────────────────────────

def print_stats(label: str, samples: list):
    intents = Counter(s.get("intent", "QUERY") for s in samples)
    print(f"\n[{label}] 총 {len(samples)}개")
    for k, v in intents.most_common():
        print(f"  {k}: {v}개 ({v/len(samples)*100:.1f}%)")


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SFT 데이터 병합 + 분할")
    parser.add_argument("--inputs", nargs="*", default=None, help="입력 파일 목록")
    parser.add_argument("--output-dir", default="data", help="출력 디렉터리")
    parser.add_argument("--train-dir", default="train", help="LLaMA-Factory train 디렉터리")
    parser.add_argument("--target", type=int, default=TARGET_TOTAL, help="목표 샘플 수")
    parser.add_argument("--eval-size", type=int, default=EVAL_SIZE, help="검증 세트 크기")
    args = parser.parse_args()

    print("=== merge_sft_t2c.py ===")
    print("Phase 2 Step 5: 데이터 병합 + 분할\n")

    # 입력 파일 결정
    if args.inputs:
        input_files = args.inputs
    elif os.path.exists(FALLBACK_INPUT):
        input_files = [FALLBACK_INPUT]
    else:
        input_files = DEFAULT_INPUTS

    print("[1] 데이터 로드...")
    raw = load_samples(input_files)
    print(f"  전체 로드: {len(raw)}개")

    print("\n[2] 중복 제거...")
    deduped = deduplicate(raw)

    # 목표 수 제한
    if len(deduped) > args.target:
        print(f"\n[3] {args.target}개로 다운샘플링 (인텐트 비율 유지)...")
        # 인텐트별 비율에 맞게 샘플링
        intent_groups: dict = {}
        for s in deduped:
            k = s.get("intent", "QUERY")
            intent_groups.setdefault(k, []).append(s)
        total = len(deduped)
        final_list = []
        for intent, group in intent_groups.items():
            n = round(len(group) / total * args.target)
            random.shuffle(group)
            final_list.extend(group[:n])
        # 오차 보정
        random.shuffle(final_list)
        final_list = final_list[:args.target]
    else:
        final_list = deduped
        print(f"\n[3] 총 {len(final_list)}개 (목표 {args.target}개 미달 — 전부 사용)")

    print(f"\n[4] 학습/검증 분할 (eval={args.eval_size})...")
    train_samples, eval_samples = stratified_split(final_list, args.eval_size)
    print(f"  학습: {len(train_samples)}개")
    print(f"  검증: {len(eval_samples)}개")

    # 메타 필드 정리
    train_clean = [clean_sample(s) for s in train_samples]
    eval_clean = [clean_sample(s) for s in eval_samples]
    all_clean = [clean_sample(s) for s in final_list]

    # 저장
    os.makedirs(args.output_dir, exist_ok=True)

    paths = {
        "전체": (os.path.join(args.output_dir, "t2c_v1_sharegpt.json"), all_clean),
        "학습": (os.path.join(args.output_dir, "t2c_v1_train.json"), train_clean),
        "검증": (os.path.join(args.output_dir, "t2c_v1_eval.json"), eval_clean),
    }

    print("\n[5] 파일 저장...")
    for label, (path, data) in paths.items():
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  {label}: {path} ({len(data)}개)")

    # 통계
    print_stats("학습 세트", train_clean)
    print_stats("검증 세트", eval_clean)

    # dataset_info.json 업데이트
    print("\n[6] LLaMA-Factory dataset_info.json 업데이트...")
    updated_path = update_dataset_info(args.train_dir)
    print(f"  완료: {updated_path}")

    print(f"""
─────────────────────────────────────────────────
SFT 데이터 준비 완료!

  학습 데이터: data/t2c_v1_train.json   ({len(train_clean)}개)
  검증 데이터: data/t2c_v1_eval.json    ({len(eval_clean)}개)
  전체 데이터: data/t2c_v1_sharegpt.json ({len(all_clean)}개)

다음 단계:
  llamafactory-cli train train/train_t2c_lora.yaml
─────────────────────────────────────────────────
""")


if __name__ == "__main__":
    main()
