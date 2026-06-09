"""
augment_t2c_llm.py — Phase 2 Step 2
GPT-4o-mini를 이용해 기존 템플릿 샘플을 표현 다양화 증강 (목표: 3,000개)
입력:  data/t2c_v1_template.json
출력:  data/t2c_v1_augmented.json
비용 예상: ~$0.5~1.0 (GPT-4o-mini 기준)
"""

import json
import os
import time
import random
import argparse
from openai import OpenAI

random.seed(123)

# ─────────────────────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────────────────────

AUGMENT_SYSTEM = """당신은 한국어 수사 용어 전문가입니다.
아래 [원본 질문]과 [Cypher 쿼리]를 받아, 동일한 의미를 가진 다양한 표현의 질문 {n}개를 생성하세요.

규칙:
1. 각 질문은 의미가 동일해야 합니다 (Cypher는 변경 없이 동일하게 사용).
2. 구어체, 문어체, 수사관 용어, 법률 용어 등 다양하게 변화시키세요.
3. 질문만 출력하세요 (JSON 배열 형식: ["질문1", "질문2", ...]).
4. 고유값(이름, 계좌번호 등)은 그대로 유지하세요.
"""

FEW_SHOT_EXAMPLES = [
    {
        "original": "홍길동이 보유한 계좌 목록",
        "cypher": "SELECT * FROM cypher('tccop_graph', $$ MATCH (p:vt_psn {name:'홍길동'})-[r:has_account]->(b:vt_bacnt) RETURN p, r, b $$) AS (p agtype, r agtype, b agtype);",
        "variations": [
            "홍길동 명의 계좌 전부 조회해줘",
            "피의자 홍길동의 금융 계좌 목록 뽑아줘",
            "홍길동이 가진 통장 다 보여줘",
            "홍길동 계좌 내역 전체 조회",
        ]
    },
    {
        "original": "대포통장 의심 계좌 전체 조회",
        "cypher": "SELECT * FROM cypher('tccop_graph', $$ MATCH (b:vt_bacnt) WHERE b->>'is_burner' = 'true' RETURN b $$) AS (b agtype);",
        "variations": [
            "개설 후 바로 사용된 대포통장 계좌들 목록",
            "명의도용 의심 계좌 전부 뽑아줘",
            "is_burner 표시된 계좌 조회",
            "대포통장으로 표시된 계좌 전체",
        ]
    }
]


def build_augment_prompt(original_q: str, cypher: str, n: int = 3) -> str:
    few_shot = ""
    for ex in FEW_SHOT_EXAMPLES:
        few_shot += f"[원본 질문] {ex['original']}\n"
        few_shot += f"[Cypher] {ex['cypher']}\n"
        few_shot += f"[출력] {json.dumps(ex['variations'], ensure_ascii=False)}\n\n"

    return (
        f"{few_shot}"
        f"[원본 질문] {original_q}\n"
        f"[Cypher] {cypher}\n"
        f"[출력] {n}개 생성하세요:"
    )


def augment_batch(client: OpenAI, samples: list, batch_size: int = 20,
                  variations_per: int = 3, max_retries: int = 2) -> list:
    """샘플 배치를 받아 증강된 새 샘플 목록 반환"""
    augmented = []

    for i in range(0, len(samples), batch_size):
        batch = samples[i:i + batch_size]
        print(f"  배치 {i//batch_size + 1}/{(len(samples)-1)//batch_size + 1} 처리 중 ({len(batch)}개)...")

        for s in batch:
            human_turn = s["conversations"][1]["value"]
            # [질문] 부분만 추출
            if "[질문]" in human_turn:
                original_q = human_turn.split("[질문]")[-1].strip()
            else:
                original_q = human_turn.strip()

            gpt_turn = s["conversations"][2]["value"]

            for attempt in range(max_retries):
                try:
                    resp = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": AUGMENT_SYSTEM.format(n=variations_per)},
                            {"role": "user", "content": build_augment_prompt(original_q, gpt_turn, variations_per)},
                        ],
                        temperature=0.9,
                        max_tokens=400,
                    )
                    raw = resp.choices[0].message.content.strip()

                    # JSON 배열 파싱
                    # 코드블록 제거
                    raw = raw.replace("```json", "").replace("```", "").strip()
                    if raw.startswith("["):
                        variations = json.loads(raw)
                    else:
                        # 줄바꿈으로 분리 시도
                        variations = [line.strip().strip('"').strip("'") for line in raw.split("\n") if line.strip()]

                    # 스키마 섹션 재사용 (원본 스키마 유지)
                    schema_section = human_turn.split("[질문]")[0].strip() if "[질문]" in human_turn else ""

                    for var_q in variations[:variations_per]:
                        if not var_q:
                            continue
                        new_human = f"{schema_section}\n\n[질문]\n{var_q}" if schema_section else f"[질문]\n{var_q}"
                        new_sample = {
                            "conversations": [
                                s["conversations"][0],  # system (재사용)
                                {"from": "human", "value": new_human},
                                {"from": "gpt", "value": gpt_turn},
                            ],
                            "intent": s.get("intent", "QUERY"),
                            "_augmented": True,
                        }
                        augmented.append(new_sample)
                    break

                except (json.JSONDecodeError, Exception) as e:
                    if attempt == max_retries - 1:
                        print(f"    ⚠ 증강 실패 (스킵): {original_q[:40]}... — {e}")
                    else:
                        time.sleep(1)

        # Rate limit 방지
        time.sleep(0.5)

    return augmented


def main():
    parser = argparse.ArgumentParser(description="GPT-4o-mini를 이용한 SFT 데이터 증강")
    parser.add_argument("--input",  default="data/t2c_v1_template.json", help="입력 파일")
    parser.add_argument("--output", default="data/t2c_v1_augmented.json", help="출력 파일")
    parser.add_argument("--target", type=int, default=3000, help="목표 샘플 수")
    parser.add_argument("--variations", type=int, default=3, help="샘플당 생성할 변형 수")
    parser.add_argument("--dry-run", action="store_true", help="API 없이 테스트 (질문만 복사)")
    args = parser.parse_args()

    print("=== augment_t2c_llm.py ===")
    print(f"입력: {args.input}")
    print(f"목표: {args.target}개\n")

    # 입력 로드
    with open(args.input, encoding="utf-8") as f:
        template_samples = json.load(f)

    print(f"템플릿 샘플 로드: {len(template_samples)}개")

    # QUERY 샘플만 선택 (GENERAL 제외)
    query_samples = [s for s in template_samples if s.get("intent", "QUERY") == "QUERY"]
    print(f"QUERY 샘플: {len(query_samples)}개")

    # 증강 대상 샘플 선택 (목표 / variations 개수)
    n_to_augment = min(args.target // args.variations + 1, len(query_samples))
    selected = random.sample(query_samples, n_to_augment)
    print(f"증강 대상 선택: {n_to_augment}개 → {n_to_augment * args.variations}개 예상\n")

    if args.dry_run:
        print("[DRY RUN] API 호출 없이 원본 질문 복사로 대체")
        augmented = []
        for s in selected[:args.target]:
            human = s["conversations"][1]["value"]
            gpt = s["conversations"][2]["value"]
            # 질문 표현 약간 변형 (단순 postfix 추가)
            suffixes = ["(조회)", "(확인 요청)", "(수사 조회)", "(내역 요청)"]
            for suf in suffixes[:args.variations]:
                if "[질문]" in human:
                    q = human.split("[질문]")[-1].strip()
                    schema_part = human.split("[질문]")[0].strip()
                    new_q = q + " " + suf
                    new_human = f"{schema_part}\n\n[질문]\n{new_q}"
                else:
                    new_human = human + " " + suf

                augmented.append({
                    "conversations": [
                        s["conversations"][0],
                        {"from": "human", "value": new_human},
                        {"from": "gpt", "value": gpt},
                    ],
                    "intent": s.get("intent", "QUERY"),
                    "_augmented": True,
                })
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
            print("   export OPENAI_API_KEY=sk-... 후 재실행하세요.")
            return

        client = OpenAI(api_key=api_key)
        augmented = augment_batch(
            client, selected,
            batch_size=20,
            variations_per=args.variations,
        )

    # 목표 수로 자르기
    augmented = augmented[:args.target]
    print(f"\n증강 완료: {len(augmented)}개")

    # 저장
    os.makedirs("data", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(augmented, f, ensure_ascii=False, indent=2)

    print(f"저장 완료: {args.output}")
    print("\n✓ 완료!")


if __name__ == "__main__":
    main()
