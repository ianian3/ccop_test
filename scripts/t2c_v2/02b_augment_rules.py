"""
t2c_v2 Step 2b: 규칙 기반 표현 다양화 (API 없이 오프라인 실행)

입력:  data/t2c_v2_templates.json  (5,100개)
       data/t2c_v1_patched.json    (3,895개)
출력:  data/t2c_v2_augmented.json  (~3,000개 신규 변형)

동작:
  - 동의어 치환 + 어미 변환 + 조사 변환으로 질문 표현 다양화
  - Cypher는 그대로 유지
  - GPT 없이 즉시 실행 가능

표현 다양화 규칙:
  R1. 명령형 ↔ 의문형 ("조회해줘" ↔ "조회하고 싶어" / "어떻게 되나요")
  R2. 동의어 치환 ("계좌" ↔ "통장", "조회" ↔ "확인" / "검색")
  R3. 경어체 ↔ 반말체 ("조회해줘" ↔ "조회해주세요" / "조회하시오")
  R4. 수사 전문어 추가 ("피의자" ↔ "용의자" ↔ "피고인")
  R5. 접두어 변형 (직접 → "급합니다", "긴급조회:", "수사관요청:")
"""

import json
import re
import copy
import random
from pathlib import Path
from collections import Counter

SEED = 42
random.seed(SEED)

INPUT_FILES = [
    Path("data/t2c_v2_templates.json"),
    Path("data/t2c_v1_patched.json"),
]
DST_PATH = Path("data/t2c_v2_augmented.json")

TARGET = 3_000


# ─── 동의어 치환 테이블 ───────────────────────────────────────────────────────

SYNONYM_RULES: list[tuple[str, list[str]]] = [
    # 노드 명칭
    ("계좌",     ["통장", "금융계좌", "은행계좌", "입출금 계좌"]),
    ("전화번호", ["전화", "번호", "폰번호", "휴대폰 번호", "연락처"]),
    ("IP",       ["IP 주소", "아이피", "아이피 주소"]),
    ("사이트",   ["웹사이트", "사이트", "홈페이지", "URL"]),
    ("인물",     ["사람", "피의자", "용의자"]),
    ("계좌번호", ["통장번호", "계좌 번호"]),
    # 동사/서술어
    ("조회해줘",       ["확인해줘", "검색해줘", "찾아줘", "뽑아줘", "알려줘"]),
    ("조회하고 싶어",  ["확인하고 싶어", "검색하고 싶어", "찾고 싶어"]),
    ("목록",           ["리스트", "내역", "현황", "목록 조회"]),
    ("전체",           ["모두", "전부", "일체", "모든"]),
    ("조회",           ["확인", "검색", "조사", "파악"]),
    ("추적",           ["역추적", "추적 조회", "이력 조회"]),
    # 수식어
    ("피의자",         ["용의자", "피고인", "수사 대상자", "혐의자"]),
    ("피해자",         ["피해 당사자", "고소인", "신고인"]),
    ("공범",           ["공모자", "공동 피의자", "연루자"]),
    # 전문 용어
    ("대포통장",       ["명의도용 계좌", "차명 계좌", "대포 계좌"]),
    ("대포폰",         ["차명폰", "명의도용 전화", "개통 명의 의심폰"]),
    ("보이스피싱",     ["전화사기", "전화 금융사기", "보이스피싱 범죄"]),
    ("악성",           ["의심", "사기", "피싱", "해킹"]),
]

SUFFIX_VARIANTS: list[list[str]] = [
    # 명령형 변형
    ["조회해줘", "조회해주세요", "조회하시오", "조회 바랍니다", "조회 요청합니다"],
    ["확인해줘", "확인해주세요", "확인하시오", "확인 바랍니다"],
    ["알려줘", "알려주세요", "알려주시기 바랍니다"],
    ["뽑아줘", "뽑아주세요", "추출해줘", "추출해주세요"],
    ["찾아줘", "찾아주세요", "검색해줘", "검색해주세요"],
    ["보여줘", "보여주세요", "출력해줘", "출력해주세요"],
]

PREFIX_VARIANTS = [
    "",
    "긴급) ",
    "수사관 요청: ",
    "조회 요청 — ",
    "급합니다. ",
    "빠른 답변 부탁: ",
    "담당 수사관이 요청한 ",
    "[우선순위 높음] ",
]

QUESTION_ENDINGS = [
    "",
    "?",
    " (빠른 조회 요청)",
    " (수사 목적)",
    " (증거 자료용)",
    " 조회 바람",
    " 내역 필요",
    " 파악 요청",
]


def apply_synonym(q: str) -> object:
    """랜덤 동의어 1개 치환. 변경 없으면 None 반환"""
    shuffled = list(SYNONYM_RULES)
    random.shuffle(shuffled)
    for original, synonyms in shuffled:
        if original in q:
            replacement = random.choice(synonyms)
            if replacement != original:
                return q.replace(original, replacement, 1)
    return None


def apply_suffix(q: str) -> object:
    """어미 변환"""
    for group in SUFFIX_VARIANTS:
        for base in group:
            if q.endswith(base):
                candidates = [s for s in group if s != base]
                if candidates:
                    return q[:-len(base)] + random.choice(candidates)
    return None


def apply_prefix(q: str) -> str:
    """접두어 추가"""
    prefix = random.choice([p for p in PREFIX_VARIANTS if p])
    if not q.startswith(prefix.strip()):
        return prefix + q
    return q


def apply_ending(q: str) -> str:
    """문장 끝 변형"""
    ending = random.choice([e for e in QUESTION_ENDINGS if e])
    if not any(q.endswith(e) for e in QUESTION_ENDINGS if e):
        return q + ending
    return q


def variate_question(q: str, strategy: int) -> object:
    """strategy 번호에 따라 다른 변형 규칙 적용"""
    if strategy == 0:
        return apply_synonym(q)
    elif strategy == 1:
        return apply_suffix(q)
    elif strategy == 2:
        result = apply_synonym(q)
        if result:
            return apply_prefix(result)
        return apply_prefix(q)
    elif strategy == 3:
        result = apply_synonym(q)
        if result:
            return apply_ending(result)
        return None
    elif strategy == 4:
        result = apply_suffix(q)
        if result:
            return apply_prefix(result)
        return None
    return None


def extract_question(human_val: str) -> str:
    if "[질문]" in human_val:
        return human_val.split("[질문]")[-1].strip()
    return human_val[-150:].strip()


def extract_schema(human_val: str) -> str:
    if "[스키마]" in human_val and "[질문]" in human_val:
        return human_val.split("[질문]")[0].strip()
    return human_val[:400]


def make_variant(original: dict, new_q: str) -> dict:
    s = copy.deepcopy(original)
    for c in s["conversations"]:
        if c["from"] == "human":
            schema = extract_schema(c["value"])
            c["value"] = f"{schema}\n\n[질문]\n{new_q}"
            break
    return s


def main():
    all_input: list[dict] = []
    for path in INPUT_FILES:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        # QUERY만 대상
        query_only = [d for d in data if d.get("intent") == "QUERY"]
        all_input.extend(query_only)
        print(f"  로드: {path.name:<35} QUERY {len(query_only):,}개")

    print(f"\n총 QUERY 입력: {len(all_input):,}개  목표 변형: {TARGET:,}개")

    augmented: list[dict] = []
    seen_qs: set[str] = set()

    # 기존 질문 등록 (중복 방지)
    for d in all_input:
        human = next(c["value"] for c in d["conversations"] if c["from"] == "human")
        seen_qs.add(extract_question(human))

    # 변형 생성
    attempts = 0
    max_attempts = TARGET * 10

    while len(augmented) < TARGET and attempts < max_attempts:
        sample = random.choice(all_input)
        human = next(c["value"] for c in sample["conversations"] if c["from"] == "human")
        orig_q = extract_question(human)

        strategy = random.randint(0, 4)
        new_q = variate_question(orig_q, strategy)

        if new_q and new_q not in seen_qs and new_q != orig_q:
            seen_qs.add(new_q)
            augmented.append(make_variant(sample, new_q))

        attempts += 1

    print(f"\n변형 생성: {len(augmented):,}개 (시도: {attempts:,}회)")

    # GUARD/GENERAL은 변형 불필요 — 고정 샘플 유지
    # augmented는 QUERY만

    DST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DST_PATH, "w", encoding="utf-8") as f:
        json.dump(augmented, f, ensure_ascii=False, indent=2)

    print(f"\n=== 02b_augment_rules 완료 ===")
    print(f"  출력: {len(augmented):,}개 → {DST_PATH}")

    # 변형 예시
    if augmented:
        sample = random.choice(augmented[:20])
        human = next(c["value"] for c in sample["conversations"] if c["from"] == "human")
        print(f"\n  변형 예시:")
        print(f"    → {extract_question(human)[:80]}")


if __name__ == "__main__":
    main()
