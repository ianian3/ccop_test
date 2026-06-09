"""
v5 데이터셋의 SQL Wrapper 응답을 Native Cypher로 변환

입력: data/ccop_v5_merged_sharegpt.json (25,526개)
출력: data/ccop_v5_native_sharegpt.json

변환 패턴:
  SELECT * FROM cypher('graph', $$ MATCH ... RETURN ... $$) AS (...)
  → MATCH ... RETURN ...

엣지 케이스:
  - 이미 Native Cypher (변환 불필요)
  - 멀티라인 쿼리 (개행 → 공백 정규화)
  - 비표준 wrapper (UPDATE/CREATE 포함, 추출 후 검증)
"""

import json
import re
from pathlib import Path
from collections import Counter

DATA_DIR = Path(__file__).parent
INPUT = DATA_DIR / "ccop_v5_merged_sharegpt.json"
OUTPUT = DATA_DIR / "ccop_v5_native_sharegpt.json"

# SQL wrapper 패턴 — $$ ... $$ 사이의 내용 추출
WRAPPER_RE = re.compile(
    r"SELECT\s+.*?\bFROM\s+cypher\s*\(\s*'[^']*'\s*,\s*\$\$(.*?)\$\$\s*\)\s*AS\s*\([^)]*\)\s*;?",
    re.IGNORECASE | re.DOTALL
)
INNER_DOLLAR_RE = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)


def normalize_whitespace(s: str) -> str:
    """개행과 다중 공백을 단일 공백으로 정규화."""
    return re.sub(r"\s+", " ", s).strip()


def convert_response(resp: str) -> tuple[str, str]:
    """응답을 Native Cypher로 변환. 반환: (변환된_쿼리, 변환_상태)"""
    resp = resp.strip()

    # 이미 Native Cypher인지 확인
    if not re.search(r"\bSELECT\b.*\bcypher\s*\(", resp, re.IGNORECASE):
        # MATCH/CREATE/MERGE/RETURN으로 시작하는 순수 Cypher
        if re.match(r"^\s*(MATCH|CREATE|MERGE|WITH|UNWIND|CALL|RETURN|OPTIONAL)\b",
                    resp, re.IGNORECASE):
            return normalize_whitespace(resp), "already_native"
        return resp, "unknown_format"

    # 표준 wrapper 매칭
    m = WRAPPER_RE.search(resp)
    if m:
        inner = m.group(1)
        return normalize_whitespace(inner), "wrapper_extracted"

    # 비표준 wrapper — $$ ... $$ 만 직접 추출 시도
    m = INNER_DOLLAR_RE.search(resp)
    if m:
        inner = m.group(1)
        return normalize_whitespace(inner), "dollar_only_extracted"

    return resp, "extraction_failed"


def main():
    print(f"📥 로드: {INPUT.name}")
    with open(INPUT, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"   총 {len(data):,}개")

    status_counter = Counter()
    converted = []
    failures = []

    for i, sample in enumerate(data):
        convs = sample["conversations"]
        new_convs = []
        for t in convs:
            if t.get("from") in ("gpt", "assistant"):
                native, status = convert_response(t.get("value", ""))
                status_counter[status] += 1
                if status == "extraction_failed":
                    failures.append((i, t.get("value", "")[:200]))
                new_convs.append({**t, "value": native})
            else:
                new_convs.append(t)
        converted.append({"conversations": new_convs})

    with open(OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(converted, f, ensure_ascii=False, indent=2)

    print()
    print("📊 변환 상태:")
    for status, cnt in status_counter.most_common():
        pct = cnt / len(data) * 100
        print(f"   {status:30s}: {cnt:>6,}개 ({pct:5.1f}%)")

    if failures:
        print(f"\n⚠️  추출 실패 샘플 (최대 3개 미리보기):")
        for idx, snippet in failures[:3]:
            print(f"   [#{idx}] {snippet}")

    print(f"\n✅ 출력: {OUTPUT}")


if __name__ == "__main__":
    main()
