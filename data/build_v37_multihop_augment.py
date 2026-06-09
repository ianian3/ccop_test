"""
v3.7 멀티홉 시드 GPT-4o 증강

입력:  data/ccop_v37_multihop_seed_sharegpt.json (311개)
출력:  data/ccop_v37_multihop_augmented_sharegpt.json
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
SEED_PATH = DATA_DIR / "ccop_v37_multihop_seed_sharegpt.json"
OUT_PATH = DATA_DIR / "ccop_v37_multihop_augmented_sharegpt.json"

MODEL = "gpt-4o-mini"
N_VARIANTS = 8
CONCURRENCY = 10

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

AUGMENT_SYSTEM = """당신은 사이버 수사 도메인의 한국어 자연어 질문 변형 전문가입니다.
원본 질문과 동일한 의도를 유지하면서, 표현·어순·동의어만 바꾼 변형 질문 N개를 생성하세요.

규칙:
1. 의미(의도)는 절대 바꾸지 않는다.
2. 매개변수(이름, 사건번호, IMEI, 금액, 도메인, 날짜, ID, 클러스터ID)는 원본 그대로 보존.
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
   - 최단 경로 ↔ shortest path ↔ 최단 연결 ↔ 가장 짧은 경로
   - 명의자 ↔ 가입자 ↔ 명의인
   - 통화 상대방 ↔ 통화 상대 ↔ 발수신 상대
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
            max_tokens=700,
        )
        data = json.loads(resp.choices[0].message.content)
        variants = data.get("variants", [])
        if not isinstance(variants, list):
            return []
        return [v for v in variants if isinstance(v, str) and v.strip()]
    except Exception as e:
        print(f"⚠️  실패: {original_q[:40]}... — {e}", file=sys.stderr)
        return []


async def process_seed(sem, idx, seed, total):
    async with sem:
        convs = seed["conversations"]
        system_v = convs[0]["value"]
        original_q = convs[1]["value"]
        cypher = convs[2]["value"]

        variants = await augment_one(original_q)
        if (idx + 1) % 20 == 0:
            print(f"  [{idx+1:4d}/{total}] {len(variants)}개 변형")

        out = [seed]
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

    print(f"📥 시드: {len(seeds)}개  →  목표: 시드당 {N_VARIANTS}개 변형")
    print(f"🤖 모델: {MODEL},  concurrency={CONCURRENCY}\n")

    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = [process_seed(sem, i, s, len(seeds)) for i, s in enumerate(seeds)]
    results = await asyncio.gather(*tasks)

    all_samples = [s for r in results for s in r]

    seen = set()
    unique = []
    for s in all_samples:
        q = s["conversations"][1]["value"].strip()
        c = s["conversations"][2]["value"].strip()
        key = (q, c)
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료: 총 {len(all_samples)}개 → 중복 제거 후 {len(unique)}개")
    print(f"   출력: {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
