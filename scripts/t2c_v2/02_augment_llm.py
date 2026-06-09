"""
t2c_v2 Step 2: GPT-4o-mini 표현 다양화

입력:  data/t2c_v2_templates.json  (5,100개 — Step 1 결과)
출력:  data/t2c_v2_augmented.json  (목표: ~2,200개 신규 변형)

동작:
  - 템플릿 샘플에서 랜덤 서브셋을 선택
  - GPT-4o-mini로 동일 의미의 다양한 질문 표현 생성
  - Cypher는 그대로, 질문만 달리하는 신규 샘플 생성
  - 배치 처리 + 비용 제어 (--max-cost 인자)

예상 비용: ~$1.0~2.0 (GPT-4o-mini, 2,200개 기준)

사용법:
  python scripts/t2c_v2/02_augment_llm.py
  python scripts/t2c_v2/02_augment_llm.py --target 2200 --max-cost 2.0
  python scripts/t2c_v2/02_augment_llm.py --dry-run  # API 없이 구조 확인
"""

import json
import os
import time
import random
import argparse
import re
import copy
from pathlib import Path

SEED = 42
random.seed(SEED)

SRC_PATH  = Path("data/t2c_v2_templates.json")
DST_PATH  = Path("data/t2c_v2_augmented.json")

# GPT-4o-mini pricing (as of 2025)
INPUT_COST_PER_1K  = 0.00015   # $0.00015 / 1K input tokens
OUTPUT_COST_PER_1K = 0.00060   # $0.00060 / 1K output tokens
AVG_TOKENS_PER_CALL = 400       # 예상 평균 (input ~250 + output ~150)

AUGMENT_SYSTEM = """당신은 한국 경찰청 수사관을 위한 데이터베이스 질의 전문가입니다.
아래 [원본 질문]과 [Cypher 쿼리]를 보고, 동일한 의미의 질문을 {n}개 생성하세요.

규칙:
1. 각 질문은 동일한 Cypher로 답변 가능해야 합니다.
2. 구어체·문어체·수사관 전문용어·법률 용어 등 다양하게 변화시키세요.
3. 고유값(이름, 계좌번호, IP, 사건번호 등)은 그대로 유지하세요.
4. 질문만 JSON 배열 형식으로 출력하세요: ["질문1", "질문2", ...]
5. 설명, 주석, 마크다운 없이 JSON만 출력하세요."""

FEW_SHOT = [
    {
        "q": "이서연의 소유 계좌를 조회해줘",
        "c": "MATCH (p:vt_psn {name:'이서연'})-[r:has_account]->(b:vt_bacnt) RETURN p, r, b",
        "v": '["이서연 명의 계좌 전부 뽑아줘", "피의자 이서연 금융계좌 목록", "이서연이 가진 통장 내역"]'
    },
    {
        "q": "사건 2024-사이버-001의 피의자 목록",
        "c": "MATCH (p:vt_psn)-[r:suspect_in]->(c:vt_case {flnm:'2024-사이버-001'}) RETURN p, r, c",
        "v": '["2024-사이버-001 사건 피의자 조회", "해당 사건에 연루된 피의자 전부", "사건번호 2024-사이버-001 용의자 뽑아줘"]'
    },
]


def build_prompt(original_q: str, cypher_short: str, n: int = 3) -> str:
    few_shot_text = ""
    for ex in FEW_SHOT:
        few_shot_text += (
            f"[원본 질문] {ex['q']}\n"
            f"[Cypher 요약] {ex['c']}\n"
            f"[출력] {ex['v']}\n\n"
        )
    return (
        f"{few_shot_text}"
        f"[원본 질문] {original_q}\n"
        f"[Cypher 요약] {cypher_short}\n"
        f"[출력]"
    )


def extract_cypher_body(gpt_val: str) -> str:
    """SQL 래퍼에서 Cypher 본문만 추출"""
    m = re.search(r"\$\$(.*?)\$\$", gpt_val, re.DOTALL)
    if m:
        return m.group(1).strip()[:300]
    return gpt_val[:200]


def extract_question(human_val: str) -> str:
    """[질문] 섹션 추출"""
    if "[질문]" in human_val:
        return human_val.split("[질문]")[-1].strip()[:200]
    return human_val[-200:].strip()


def extract_schema(human_val: str) -> str:
    """[스키마] 섹션 추출"""
    if "[스키마]" in human_val and "[질문]" in human_val:
        return human_val.split("[질문]")[0].strip()
    return human_val[:400]


def make_augmented_sample(original: dict, new_question: str) -> dict:
    """원본 샘플의 Cypher를 유지하고 질문만 교체"""
    s = copy.deepcopy(original)
    for c in s["conversations"]:
        if c["from"] == "human":
            schema_part = extract_schema(c["value"])
            c["value"] = f"{schema_part}\n\n[질문]\n{new_question}"
            break
    return s


def estimate_cost(n_calls: int) -> float:
    tokens = n_calls * AVG_TOKENS_PER_CALL
    return tokens / 1000 * (INPUT_COST_PER_1K + OUTPUT_COST_PER_1K)


def call_gpt(client, original_q: str, cypher_body: str, n: int = 3,
             model: str = "gpt-4o-mini") -> list[str]:
    system = AUGMENT_SYSTEM.format(n=n)
    prompt = build_prompt(original_q, cypher_body, n)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0.9,
        max_tokens=300,
    )
    raw = resp.choices[0].message.content.strip()

    # JSON 배열 파싱
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if m:
        try:
            questions = json.loads(m.group())
            return [q.strip() for q in questions if isinstance(q, str) and q.strip()]
        except json.JSONDecodeError:
            pass

    # 폴백: 줄 분리
    lines = [l.strip().strip('"').strip("'").strip("-").strip()
             for l in raw.splitlines() if l.strip()]
    return [l for l in lines if 5 < len(l) < 200][:n]


def dry_run_augment(samples: list[dict], target: int) -> list[dict]:
    """API 없이 구조 검증용 — 원본 질문 끝에 '(변형N)' 추가"""
    subset = random.sample(samples, min(len(samples), target // 3 + 1))
    augmented = []
    for s in subset:
        human = next(c["value"] for c in s["conversations"] if c["from"] == "human")
        orig_q = extract_question(human)
        for i in range(1, 4):
            new_q = f"{orig_q} (표현변형{i})"
            augmented.append(make_augmented_sample(s, new_q))
        if len(augmented) >= target:
            break
    return augmented[:target]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target",   type=int,   default=2_200)
    parser.add_argument("--max-cost", type=float, default=3.0,
                        help="최대 허용 비용 USD (초과 시 중단)")
    parser.add_argument("--batch",    type=int,   default=3,
                        help="샘플당 생성 변형 수")
    parser.add_argument("--delay",    type=float, default=0.3,
                        help="API 호출 간 딜레이(초)")
    parser.add_argument("--dry-run",  action="store_true",
                        help="API 없이 구조 검증만 수행")
    parser.add_argument("--model",    default="gpt-4o-mini")
    args = parser.parse_args()

    with open(SRC_PATH, encoding="utf-8") as f:
        templates: list[dict] = json.load(f)

    print(f"입력: {len(templates):,}개  목표 증강: {args.target:,}개")

    if args.dry_run:
        print("[DRY RUN] API 호출 없이 구조 검증...")
        augmented = dry_run_augment(templates, args.target)
        DST_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DST_PATH, "w", encoding="utf-8") as f:
            json.dump(augmented, f, ensure_ascii=False, indent=2)
        print(f"DRY RUN 완료: {len(augmented):,}개 → {DST_PATH}")
        return

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        print("   export OPENAI_API_KEY=sk-... 후 재실행하세요.")
        print("   구조 확인만 하려면 --dry-run 옵션을 사용하세요.")
        return

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    # 서브셋 선정: target/batch 개 샘플 필요
    n_calls = (args.target + args.batch - 1) // args.batch
    estimated_cost = estimate_cost(n_calls)
    print(f"예상 API 호출: {n_calls:,}회  예상 비용: ${estimated_cost:.2f}")

    if estimated_cost > args.max_cost:
        print(f"⚠️  예상 비용(${estimated_cost:.2f}) > 한도(${args.max_cost:.2f})")
        print(f"   --max-cost {estimated_cost:.1f} 로 재실행하거나 --target을 줄이세요.")
        return

    subset = random.sample(templates, min(len(templates), n_calls))

    augmented: list[dict] = []
    total_cost = 0.0
    errors = 0

    print(f"\n증강 시작 (model={args.model}, batch={args.batch})...")
    for i, sample in enumerate(subset):
        if len(augmented) >= args.target:
            break

        human = next(c["value"] for c in sample["conversations"] if c["from"] == "human")
        gpt   = next(c["value"] for c in sample["conversations"] if c["from"] == "gpt")
        orig_q = extract_question(human)
        cypher_body = extract_cypher_body(gpt)

        try:
            variations = call_gpt(client, orig_q, cypher_body, args.batch, args.model)
            for v in variations:
                augmented.append(make_augmented_sample(sample, v))
            call_cost = estimate_cost(1)
            total_cost += call_cost
        except Exception as e:
            errors += 1
            if errors > 20:
                print(f"\n오류 누적 {errors}회, 중단합니다: {e}")
                break
            continue

        if (i + 1) % 50 == 0:
            print(f"  [{i+1:>4}/{n_calls}] 생성: {len(augmented):,}개  누적비용: ${total_cost:.3f}")

        if total_cost >= args.max_cost:
            print(f"\n비용 한도(${args.max_cost}) 도달, 중단.")
            break

        time.sleep(args.delay)

    augmented = augmented[:args.target]

    DST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DST_PATH, "w", encoding="utf-8") as f:
        json.dump(augmented, f, ensure_ascii=False, indent=2)

    print(f"\n=== 02_augment_llm 완료 ===")
    print(f"  생성:      {len(augmented):,}개 → {DST_PATH}")
    print(f"  API 오류:  {errors}회")
    print(f"  실제 비용: ${total_cost:.3f}")


if __name__ == "__main__":
    main()
