"""
t2c_v2 Step 4: 자동 품질 검증

입력:  data/t2c_v1_patched.json
       data/t2c_v2_templates.json
       data/t2c_v2_augmented.json  (있으면)
       data/t2c_v2_manual.json

출력:  data/t2c_v2_validated.json  (검증 통과 샘플만)
       data/t2c_v2_rejected.json   (검증 실패 샘플 — 디버깅용)

검증 규칙:
  R01  SQL 래퍼 존재: SELECT * FROM cypher('...', $$ ... $$) AS (...)
  R02  그래프 이름: tccop_graph
  R03  RETURN 변수 수 == AS 컬럼 수 (path 예외)
  R04  agtype 키워드 존재
  R05  쓰기 명령 없음 (CREATE/MERGE/DELETE/SET/DETACH/REMOVE) — QUERY 한정
  R06  GUARD/GENERAL: gpt 응답이 거절 문구 포함
  R07  deprecated 엣지 없음 (contacted/impersonates/accessed/performed_by)
  R08  conversations 구조: system + human + gpt 순서
  R09  intent 필드 유효 (QUERY/GENERAL/GUARD)
"""

import json
import re
from pathlib import Path
from collections import Counter

INPUT_FILES = [
    Path("data/t2c_v1_patched.json"),
    Path("data/t2c_v2_templates.json"),
    Path("data/t2c_v2_augmented.json"),
    Path("data/t2c_v2_manual.json"),
]
OUT_VALID   = Path("data/t2c_v2_validated.json")
OUT_REJECT  = Path("data/t2c_v2_rejected.json")

GRAPH_NAME   = "tccop_graph"
WRITE_CMDS   = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE)\b", re.IGNORECASE)
DEPRECATED   = {"contacted", "impersonates", "accessed", "performed_by"}
GUARD_PHRASES = [
    "수사 관련 질문만 답변 가능합니다",
    "죄송합니다",           # 쓰기 명령 거절 문구
    "실행할 수 없습니다",    # 대체 거절 표현
    "답변할 수 없습니다",
]
VALID_INTENTS = {"QUERY", "GENERAL", "GUARD"}


def get_conv(sample: dict, frm: str) -> str:
    for c in sample.get("conversations", []):
        if c.get("from") == frm:
            return c.get("value", "")
    return ""


def validate(sample: dict) -> list[str]:
    """실패 규칙 코드 목록 반환 (빈 리스트 = 통과)"""
    failures = []
    intent = sample.get("intent", "")
    gpt    = get_conv(sample, "gpt")

    # R09
    if intent not in VALID_INTENTS:
        failures.append("R09_invalid_intent")
        return failures  # 이후 검사 스킵

    # R08: conversations 구조
    convs = sample.get("conversations", [])
    froms = [c.get("from") for c in convs]
    if froms != ["system", "human", "gpt"]:
        failures.append("R08_conv_structure")

    if intent in ("GENERAL", "GUARD"):
        # R06
        if not any(phrase in gpt for phrase in GUARD_PHRASES):
            failures.append("R06_no_guard_phrase")
        return failures

    # ── QUERY 전용 ──────────────────────────────────────────
    # R01
    if f"SELECT * FROM cypher('{GRAPH_NAME}'" not in gpt:
        failures.append("R01_no_wrapper")
        return failures  # 래퍼 없으면 나머지 검사 의미 없음

    # R02 (이미 R01에 포함되지만 명시)
    if GRAPH_NAME not in gpt:
        failures.append("R02_wrong_graph")

    # R04
    if "agtype" not in gpt:
        failures.append("R04_no_agtype")

    # R05
    cypher_body_m = re.search(r"\$\$(.*?)\$\$", gpt, re.DOTALL)
    if cypher_body_m:
        body = cypher_body_m.group(1)
        if WRITE_CMDS.search(body):
            failures.append("R05_write_command")

    # R07
    for dep in DEPRECATED:
        if re.search(r"\[\w*:" + dep + r"[\s\]{}]", gpt):
            failures.append(f"R07_deprecated_{dep}")

    # R03: RETURN/AS 컬럼 수 일치 (path 패턴 제외)
    if "path" not in gpt.lower():
        ret_m = re.search(r"RETURN\s+(.+?)[\n\$]", gpt)
        as_m  = re.search(r"AS\s*\(([^)]+)\)",    gpt)
        if ret_m and as_m:
            ret_vars = [v.strip() for v in ret_m.group(1).split(",")
                        if v.strip() and not v.strip().startswith("--")]
            as_cols  = [c.strip() for c in as_m.group(1).split(",") if c.strip()]
            if len(ret_vars) != len(as_cols):
                failures.append(f"R03_return_as_mismatch({len(ret_vars)}vs{len(as_cols)})")

    return failures


def main():
    all_samples: list[dict] = []
    for path in INPUT_FILES:
        if not path.exists():
            print(f"  [SKIP] {path} (없음)")
            continue
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        print(f"  로드: {path.name:<35} {len(data):>6,}개")
        all_samples.extend(data)

    print(f"\n합계 입력: {len(all_samples):,}개")

    valid: list[dict] = []
    rejected: list[dict] = []
    failure_counts: Counter = Counter()

    for s in all_samples:
        fails = validate(s)
        if fails:
            for f in fails:
                failure_counts[f] += 1
            s["_reject_reasons"] = fails
            rejected.append(s)
        else:
            valid.append(s)

    # 출력
    OUT_VALID.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_VALID, "w", encoding="utf-8") as f:
        json.dump(valid, f, ensure_ascii=False, indent=2)
    with open(OUT_REJECT, "w", encoding="utf-8") as f:
        json.dump(rejected, f, ensure_ascii=False, indent=2)

    print(f"\n=== 04_validate 완료 ===")
    print(f"  통과: {len(valid):,}개 → {OUT_VALID}")
    print(f"  실패: {len(rejected):,}개 → {OUT_REJECT}")
    print(f"  통과율: {len(valid)/len(all_samples)*100:.2f}%")

    if failure_counts:
        print(f"\n  실패 원인 분포:")
        for rule, cnt in failure_counts.most_common():
            print(f"    {rule:<45} {cnt:>5}")

    # Intent 분포
    intents = Counter(s.get("intent") for s in valid)
    print(f"\n  유효 샘플 Intent: {dict(intents)}")


if __name__ == "__main__":
    main()
