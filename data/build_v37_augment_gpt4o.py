"""
v3.7 시드 데이터셋 GPT-4o 다양성 증강

입력:  data/ccop_v37_seed_sharegpt.json   (323개 시드)
출력:  data/ccop_v37_augmented_sharegpt.json (시드 1개당 8개 변형 질문)

전략:
  - Cypher는 원본 유지 (의미 보존)
  - GPT-4o-mini로 동일 의도의 한국어 질문 변형 8개 생성
  - 다양성: 정중체/구어체, 키워드 동의어 치환, 어순 변경, 약어/풀네임
  - 비동기 동시 호출 (concurrency=10)으로 빠르게 처리

비용 추정 (gpt-4o-mini, 323개 시드):
  - 입력 ~250 토큰/req × 323 = ~80K  → $0.012
  - 출력 ~250 토큰/req × 323 = ~80K  → $0.048
  - 합계 약 $0.06
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).parent
SEED_PATH = DATA_DIR / "ccop_v37_seed_sharegpt.json"
OUT_PATH = DATA_DIR / "ccop_v37_augmented_sharegpt.json"

MODEL = "gpt-4o-mini"
N_VARIANTS = 8
CONCURRENCY = 10

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


AUGMENT_SYSTEM = """당신은 사이버 수사 도메인의 한국어 자연어 질문 변형 전문가입니다.
원본 질문과 동일한 의도를 유지하면서, 표현·어순·동의어만 바꾼 변형 질문 N개를 생성하세요.

규칙:
1. 의미(의도)는 절대 바꾸지 않는다.
2. 매개변수(이름, 사건번호, IMEI, 금액, 도메인, 날짜, ID)는 원본 그대로 보존.
3. 다양성: 정중체("~보여줘", "~확인해줘", "~알려줘"), 구어체("뭐 있어?", "어떻게 돼?"),
   명사화("~목록", "~조회", "~현황"), 의문문/명령문 혼용.
4. 동의어 활용:
   - 진정서 ↔ 진정 ↔ 신고서
   - 군집 ↔ 클러스터 ↔ 그룹 ↔ 묶음
   - 피의자 ↔ 용의자
   - 성명불상 ↔ 신원미상 ↔ 이름불상 ↔ 인적사항 미상
   - 불법중계기 ↔ 사설중계기 ↔ 불법 기지국
   - 피싱 캠페인 ↔ 사기사이트 그룹 ↔ 악성사이트 캠페인
   - 사건 ↔ 케이스 ↔ 수사건
5. 출력은 JSON 배열만 — 다른 설명 금지: {"variants": ["변형1", "변형2", ...]}"""


async def augment_one(original_q: str) -> list[str]:
    user_msg = f"원본 질문: {original_q}\n\n위 질문의 변형 {N_VARIANTS}개를 JSON으로 생성하세요."
    try:
        resp = await client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": AUGMENT_SYSTEM},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0.85,
            max_tokens=600,
        )
        content = resp.choices[0].message.content
        data = json.loads(content)
        variants = data.get("variants", [])
        if not isinstance(variants, list):
            return []
        return [v for v in variants if isinstance(v, str) and v.strip()]
    except Exception as e:
        print(f"⚠️  실패: {original_q[:40]}... — {e}", file=sys.stderr)
        return []


async def process_seed(sem: asyncio.Semaphore, idx: int, seed: dict, total: int) -> list[dict]:
    async with sem:
        convs = seed["conversations"]
        system_v = convs[0]["value"]
        original_q = convs[1]["value"]
        cypher = convs[2]["value"]

        variants = await augment_one(original_q)
        if (idx + 1) % 10 == 0:
            print(f"  [{idx+1:4d}/{total}] {len(variants)}개 변형 — {original_q[:50]}")

        out = [seed]  # 원본 시드 보존
        for v in variants[:N_VARIANTS]:
            out.append({
                "conversations": [
                    {"from": "system", "value": system_v},
                    {"from": "human", "value": v},
                    {"from": "gpt", "value": cypher},
                ]
            })
        return out


async def main():
    with open(SEED_PATH, 'r', encoding='utf-8') as f:
        seeds = json.load(f)

    print(f"📥 시드: {len(seeds)}개  →  목표: 시드당 {N_VARIANTS}개 변형 ({len(seeds) * (N_VARIANTS+1)}개 예상)")
    print(f"🤖 모델: {MODEL},  concurrency={CONCURRENCY}")
    print()

    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = [process_seed(sem, i, s, len(seeds)) for i, s in enumerate(seeds)]
    results = await asyncio.gather(*tasks)

    all_samples = []
    for r in results:
        all_samples.extend(r)

    # 질문 중복 제거 (Cypher가 같더라도 질문이 같으면 중복)
    seen_q = set()
    unique = []
    for s in all_samples:
        q = s["conversations"][1]["value"].strip()
        c = s["conversations"][2]["value"].strip()
        key = (q, c)
        if key in seen_q:
            continue
        seen_q.add(key)
        unique.append(s)

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print()
    print(f"✅ 완료: 총 {len(all_samples)}개 생성 → 중복 제거 후 {len(unique)}개")
    print(f"   출력: {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
