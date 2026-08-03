"""
few_shot_router.py — Few-shot Dynamic Prompting (학습 없이 +1~2p)
====================================================================
입력 질문을 카테고리 분류 → 해당 카테고리 gold examples를 동적 주입.

기존 system prompt 보존하고, 사용자 메시지 앞에 [예시] 블록을 prepend.
v42+R 86.6% 위에서 약점 카테고리(1hop_event/object/chain/meta_condition) 개선 목표.

사용처:
  - benchmark_t2c_v2.py → call_model_t2c_v37 wrapping
  - langgraph_agent.py → synthesis_node (운영 환경)
"""
import json
import re
from pathlib import Path
from typing import List, Dict, Optional


_EXAMPLES_CACHE: Optional[Dict] = None


def _load_examples() -> Dict:
    """Lazy load + cache."""
    global _EXAMPLES_CACHE
    if _EXAMPLES_CACHE is None:
        path = Path(__file__).parent.parent.parent / "data" / "few_shot_examples.json"
        with open(path, encoding="utf-8") as f:
            _EXAMPLES_CACHE = json.load(f)
    return _EXAMPLES_CACHE


# ─── 카테고리 분류 (regex 기반, 약점 카테고리 우선) ───────────────────────
# 순서 중요: 다홉(chain) > 위협(threat_filter) > Object↔Object > Event > Meta > Person
_CATEGORY_PATTERNS = [
    # reification: V4.4 이벤트 경유 2-hop — 고유 시그널이라 chain보다 먼저 체크
    ("reification", re.compile(
        r'(접속한?\s*(전화|번호|계정|아이디)|IP.*접속.*(전화|계정|번호)|포털.*역조회|'
        r'이체.*접속\s*IP|이체.*IP|모바일뱅킹.*IP|'
        r'언급된?\s*(장소|위치)|메시지.*(장소|위치)|기재된?\s*(장소|좌표)|'
        r'가상자산.*(전송|세탁)|지갑.*전송|계좌.*가상자산|'
        r'ATM.*인출|현금\s*인출|'
        r'통화.*(발신\s*위치|발신위치|기지국)|발신\s*위치|'
        r'계정\s*간|계정끼리|계정.*대화)',
        re.IGNORECASE)),

    # chain: 다홉 — 명시적 다홉 시그널 (먼저 체크)
    ("chain", re.compile(
        r'(체인|chain|→\s*\w+\s*→|흐름|자금세탁|hop|다단계|'
        r'명의.*전화.*통화|소유.*계좌.*이체|호스팅.*악성|차량.*LPR|차량.*이동|'
        r'pt_cluster.*피의자|site_cluster.*사이트|메시지.*언급)',
        re.IGNORECASE)),

    # threat_filter: 위협 — meta보다 먼저
    ("threat_filter", re.compile(
        r'(악성\s*사이트|악성\s*도메인|지급정지|제재.*대상|블랙리스트|blacklist|피싱.*캠페인|'
        r'site_cluster|pt_cluster|threat_score|spam_score|fraud_report|'
        r'위협점수|위험점수|군집)',
        re.IGNORECASE)),

    # 1hop_object: Object↔Object
    ("1hop_object", re.compile(
        r'(호스팅|hosts|악성\s*파일|contains_file|communicated_with|C2|'
        r'소속.*기관|belongs_to|소속.*은행|사칭.*사용|사칭에\s*사용|used_for|'
        r'사칭이?\s*타겟|targets|사이트.*첨부|메시지.*첨부|메시지.*악성|IP끼리)',
        re.IGNORECASE)),

    # 1hop_event: 단일 이벤트 엣지
    ("1hop_event", re.compile(
        r'(발신\s*통화|수신\s*통화|caller|callee|출금된?\s*이체|입금된?\s*이체|'
        r'출금\s*거래|입금\s*거래|from_account|to_account|'
        r'transferred_to|직접\s*이체|accessed_from|accessed_to|접속\s*내역|접속\s*IP|'
        r'이체\s*내역|통화\s*내역)',
        re.IGNORECASE)),

    # meta_condition: WHERE 절 메타 필터
    ("meta_condition", re.compile(
        r'(위험도|risk_level|신뢰도|reliability_tier|증거등급|evid_grade|'
        r'OSINT.*출처|source_domain|성명불상|is_anonymous|대포통장|is_burner|'
        r'is_frozen|sanction|tier\s*\d|KICS\s*공식|공식\s*출처|investigation\s*도메인|'
        r'\d+\s*이상|\d+\s*초과|\d+\s*미만|이상\s*이체|이상\s*인물)',
        re.IGNORECASE)),

    # 1hop_person: Person→Object 소유
    ("1hop_person", re.compile(
        r'(소유\s*계좌|명의\s*계좌|보유\s*계좌|소유\s*전화|owns_phone|has_account|'
        r'명의자|registered_to|사용한?\s*IP|used_ip|owns_vehicle|소유\s*차량|'
        r'운전한?\s*차량|drives|대포폰\s*추적|소유자)',
        re.IGNORECASE)),
]


def classify_question(question: str) -> Optional[str]:
    """질문을 카테고리로 분류. 매칭 없으면 None (예시 주입 안 함)."""
    q = question or ''
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.search(q):
            return category
    return None


# ─── 예시 검색 (카테고리 매칭 + 키워드 유사도) ──────────────────────────────
def retrieve_examples(category: str, question: str, top_k: int = 3) -> List[Dict]:
    """카테고리 내에서 질문과 가장 유사한 K개 예시 반환."""
    examples = _load_examples()
    cat_data = examples.get("categories", {}).get(category, {})
    pool = cat_data.get("examples", [])
    if not pool:
        return []
    if len(pool) <= top_k:
        return pool

    # 간단한 token overlap 기반 유사도
    q_tokens = set(re.findall(r'[가-힣A-Za-z0-9]+', question.lower()))
    scored = []
    for ex in pool:
        ex_tokens = set(re.findall(r'[가-힣A-Za-z0-9]+', ex["question"].lower()))
        overlap = len(q_tokens & ex_tokens)
        scored.append((overlap, ex))

    # overlap 높은 순 + 동점 시 원래 순서
    scored.sort(key=lambda x: -x[0])
    return [ex for _, ex in scored[:top_k]]


# ─── 프롬프트 구성 ──────────────────────────────────────────────────────
def build_few_shot_prompt(question: str, top_k: int = 3) -> str:
    """
    질문 앞에 동적 예시 블록을 prepend.
    카테고리 매칭 없으면 원본 질문 그대로 반환 (no-op).
    """
    category = classify_question(question)
    if not category:
        return question

    examples = retrieve_examples(category, question, top_k=top_k)
    if not examples:
        return question

    # 예시 블록 (system prompt 보존, user 메시지에만 추가)
    lines = [f"[유사 예시 — 카테고리: {category}]"]
    for i, ex in enumerate(examples, 1):
        lines.append(f"질문{i}: {ex['question']}")
        lines.append(f"답{i}: {ex['cypher']}")
    lines.append("")
    lines.append(f"[실제 질문]")
    lines.append(question)
    return "\n".join(lines)


# ─── 통계 (디버깅용) ────────────────────────────────────────────────────
_STATS = {"total": 0, "matched": 0, "by_category": {}}


def get_stats() -> Dict:
    return dict(_STATS)


def reset_stats():
    _STATS["total"] = 0
    _STATS["matched"] = 0
    _STATS["by_category"] = {}


def build_few_shot_prompt_with_stats(question: str, top_k: int = 3) -> str:
    """get_stats() 로 카테고리 분포 확인 가능."""
    _STATS["total"] += 1
    category = classify_question(question)
    if not category:
        return question
    _STATS["matched"] += 1
    _STATS["by_category"][category] = _STATS["by_category"].get(category, 0) + 1
    return build_few_shot_prompt(question, top_k=top_k)


if __name__ == "__main__":
    # 자가 검증
    test_qs = [
        "전화번호 010-1234-5678의 발신 통화 내역",
        "IP 192.168.1.10에 호스팅된 사이트",
        "위험도 HIGH 인물의 계좌",
        "김민준의 소유 계좌 조회",
        "악성 사이트 전체",
        "오늘 날씨 알려줘",  # no match
    ]
    for q in test_qs:
        cat = classify_question(q)
        print(f"[{cat or 'NONE':15s}] {q}")
        if cat:
            prompt = build_few_shot_prompt(q, top_k=2)
            print(f"  → prompt preview ({len(prompt)} chars):")
            print("  " + prompt.replace("\n", "\n  ")[:300])
            print()
