"""
validate_t2c_dataset.py — Phase 2 Step 4
SFT 데이터셋 자동 품질 검증 및 필터링
검사 항목:
  1. SQL Wrapper 구조 확인 (SELECT * FROM cypher(...) AS ...)
  2. RETURN 변수 수 = AS 컬럼 수
  3. 유효 레이블 (23개) 사용 확인
  4. 쓰기 명령 없음 (CREATE/MERGE/DELETE/SET/REMOVE — 단, GUARD 샘플 제외)
  5. 중복 질문 제거
  6. 빈 값 / 형식 오류 확인
출력: 검증 리포트 + 필터링된 파일
"""

import json
import re
import argparse
import os
from collections import Counter


# ─────────────────────────────────────────────────────────────
# 상수
# ─────────────────────────────────────────────────────────────

VALID_LABELS = {
    "vt_src", "vt_case", "vt_petition",
    "vt_psn", "vt_org",
    "vt_bacnt", "vt_telno", "vt_ip", "vt_site", "vt_file",
    "vt_id", "vt_vhcl", "vt_email", "vt_crypto", "vt_dev", "vt_atm",
    "vt_loc",
    "vt_transfer", "vt_call", "vt_msg", "vt_access", "vt_movement",
    "vt_impersonation",  # v3.3 신설 (23번째 노드)
}

VALID_EDGE_TYPES = {
    # Case 관계 (v3.5)
    "suspect_in", "victim_in", "witness_in", "filed_as", "related_case",
    "linked_to", "clusters_with",
    "eg_used_account", "eg_used_phone", "eg_used_ip",  # Case→Object 직접 증거
    # Person 관계
    "has_account", "controls", "owns_phone", "owns_device", "uses_id",
    "uses_email", "drives", "owns_vehicle", "used_ip", "member_of", "works_at",
    "accomplice_of", "sameAs", "contradicts", "operates", "recruits", "blackmails",
    # Object 관계
    "transferred_to", "communicated_with", "resolves_to", "hosts",
    "registered_to", "belongs_to",
    # Impersonation (v3.3+)
    "used_for", "targets",
    # Event 관계
    "from_account", "to_account", "caller", "callee", "accessed_from",
    "accessed_to", "sent_msg", "received_msg", "mentions_account",
    "occurred_at", "recorded_in",
    # 기타
    "sourced_from", "verified_by",
}

WRITE_COMMANDS = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH\s+DELETE|SET|REMOVE|DROP)\b",
    re.IGNORECASE
)

SQL_WRAPPER_RE = re.compile(
    r"SELECT\s+\*\s+FROM\s+cypher\s*\(",
    re.IGNORECASE
)

AS_COLS_RE = re.compile(
    r"\)\s+AS\s+\(([^)]+)\)\s*;?\s*$",
    re.IGNORECASE | re.DOTALL
)

RETURN_VARS_RE = re.compile(
    r"\bRETURN\s+(.+?)(?:\s+(?:ORDER\s+BY|LIMIT|SKIP|UNION|$)|\$\$|\s*\n\s*\$\$)",
    re.IGNORECASE | re.DOTALL
)

LABEL_IN_CYPHER_RE = re.compile(r"\([\w]*:(\w+)")
EDGE_TYPE_IN_CYPHER_RE = re.compile(r"\[:(\w+)")

GUARD_RESPONSE_PATTERNS = [
    "수사 관련 질문만 답변",
    "데이터 수정",
    "실행할 수 없습니다",
    "조회 쿼리만 지원",
]


def is_guard_response(cypher: str) -> bool:
    return any(p in cypher for p in GUARD_RESPONSE_PATTERNS)


# ─────────────────────────────────────────────────────────────
# 검증 함수들
# ─────────────────────────────────────────────────────────────

def check_structure(sample: dict) -> list:
    """샘플 기본 구조 확인"""
    errors = []
    convs = sample.get("conversations", [])
    if len(convs) < 3:
        errors.append("conversations 3개 미만")
        return errors

    for i, c in enumerate(convs):
        if "from" not in c or "value" not in c:
            errors.append(f"conversations[{i}] from/value 누락")
        if not c.get("value", "").strip():
            errors.append(f"conversations[{i}].value 빈값")

    return errors


def check_cypher(cypher: str, intent: str) -> list:
    """Cypher 쿼리 문법 검사"""
    errors = []

    # GUARD/GENERAL 샘플은 Cypher 규칙 적용 안 함
    if is_guard_response(cypher):
        return errors

    # 1. SQL Wrapper 확인
    if not SQL_WRAPPER_RE.search(cypher):
        errors.append("SQL Wrapper 누락: SELECT * FROM cypher(...)")

    # 2. RETURN 변수 수 == AS 컬럼 수
    as_match = AS_COLS_RE.search(cypher)
    return_match = RETURN_VARS_RE.search(cypher)
    if as_match and return_match:
        as_cols_raw = as_match.group(1)
        # AS 컬럼 파싱: "p agtype, r agtype, b agtype" → ["p", "r", "b"]
        as_cols = [c.strip().split()[0] for c in as_cols_raw.split(",") if c.strip()]

        return_raw = return_match.group(1).strip()
        # RETURN 변수 파싱: "p, r, b" → ["p", "r", "b"]
        # count(...) AS alias, sum(...) AS alias 같은 집계함수 처리
        return_vars = []
        for part in return_raw.split(","):
            part = part.strip()
            if not part:
                continue
            # ORDER BY / LIMIT 등이 섞인 경우 제거
            if re.match(r"(ORDER|LIMIT|SKIP|UNION|WHERE)", part, re.IGNORECASE):
                break
            return_vars.append(part.split()[-1])  # alias 또는 variable

        if len(as_cols) != len(return_vars):
            errors.append(
                f"RETURN/AS 불일치: RETURN {len(return_vars)}개, AS {len(as_cols)}개"
                f" | AS cols: {as_cols} | RETURN vars: {return_vars}"
            )

    # 3. 쓰기 명령 확인 (inner cypher 부분에서)
    inner_match = re.search(r"\$\$(.*?)\$\$", cypher, re.DOTALL)
    if inner_match:
        inner = inner_match.group(1)
        write_found = WRITE_COMMANDS.findall(inner)
        if write_found:
            errors.append(f"쓰기 명령 포함: {write_found}")

    # 4. 레이블 검증
    labels_in_query = LABEL_IN_CYPHER_RE.findall(cypher)
    for label in labels_in_query:
        if label not in VALID_LABELS:
            errors.append(f"알 수 없는 레이블: {label}")

    return errors


def validate_dataset(samples: list) -> dict:
    """전체 데이터셋 검증"""
    results = {
        "total": len(samples),
        "valid": 0,
        "invalid": 0,
        "errors": Counter(),
        "invalid_indices": [],
        "valid_samples": [],
    }

    seen_questions = {}
    duplicate_count = 0

    for idx, s in enumerate(samples):
        # 구조 검사
        struct_errors = check_structure(s)
        if struct_errors:
            results["invalid"] += 1
            for e in struct_errors:
                results["errors"][e] += 1
            results["invalid_indices"].append(idx)
            continue

        # human 질문 추출
        human_val = s["conversations"][1]["value"]
        if "[질문]" in human_val:
            question = human_val.split("[질문]")[-1].strip()
        else:
            question = human_val.strip()

        # 중복 확인
        if question in seen_questions:
            duplicate_count += 1
            continue
        seen_questions[question] = idx

        # Cypher 검사
        cypher = s["conversations"][2]["value"]
        intent = s.get("intent", "QUERY")
        cypher_errors = check_cypher(cypher, intent)

        if cypher_errors:
            results["invalid"] += 1
            for e in cypher_errors:
                results["errors"][e] += 1
            results["invalid_indices"].append(idx)
        else:
            results["valid"] += 1
            results["valid_samples"].append(s)

    results["duplicates_removed"] = duplicate_count
    return results


# ─────────────────────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SFT 데이터셋 품질 검증")
    parser.add_argument("--inputs", nargs="+", default=[
        "data/t2c_v1_template.json",
        "data/t2c_v1_augmented.json",
        "data/t2c_v1_manual.json",
    ], help="검증할 파일 목록")
    parser.add_argument("--output-dir", default="data", help="검증된 파일 출력 디렉터리")
    parser.add_argument("--verbose", action="store_true", help="에러 상세 출력")
    args = parser.parse_args()

    print("=== validate_t2c_dataset.py ===")
    print("Phase 2 Step 4: 데이터셋 품질 검증\n")

    all_valid = []

    for input_file in args.inputs:
        if not os.path.exists(input_file):
            print(f"  ⚠ 파일 없음 (스킵): {input_file}")
            continue

        with open(input_file, encoding="utf-8") as f:
            samples = json.load(f)

        print(f"[{input_file}] {len(samples)}개 검증 중...")
        results = validate_dataset(samples)

        print(f"  전체:    {results['total']}개")
        print(f"  유효:    {results['valid']}개")
        print(f"  무효:    {results['invalid']}개")
        print(f"  중복제거: {results['duplicates_removed']}개")

        if results["errors"] and (args.verbose or results["invalid"] > 0):
            print("  에러 유형:")
            for err, cnt in results["errors"].most_common(10):
                print(f"    - {err}: {cnt}건")

        # 파일별 검증 완료 파일 저장
        stem = os.path.splitext(os.path.basename(input_file))[0]
        out_file = os.path.join(args.output_dir, f"{stem}_validated.json")
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(results["valid_samples"], f, ensure_ascii=False, indent=2)
        print(f"  → 저장: {out_file}\n")

        all_valid.extend(results["valid_samples"])

    # 전체 합산 검증 (중복 재확인)
    print(f"[전체 합산] {len(all_valid)}개 → 최종 중복 제거 중...")
    seen = set()
    final = []
    for s in all_valid:
        human_val = s["conversations"][1]["value"]
        q = human_val.split("[질문]")[-1].strip() if "[질문]" in human_val else human_val.strip()
        if q not in seen:
            seen.add(q)
            final.append(s)

    print(f"최종 유효 샘플: {len(final)}개")

    out_all = os.path.join(args.output_dir, "t2c_v1_all_validated.json")
    with open(out_all, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"통합 저장: {out_all}")

    # 인텐트 분포
    intents = Counter(s.get("intent", "QUERY") for s in final)
    print("\n[인텐트 분포]")
    for k, v in intents.most_common():
        print(f"  {k}: {v}개 ({v/len(final)*100:.1f}%)")

    print("\n✓ 검증 완료!")


if __name__ == "__main__":
    main()
