"""
t2c_v2 Step 0: 기존 t2c_v1 데이터 정제 파이프라인

입력:  data/t2c_v1_all_validated.json   (4,132 samples)
출력:  data/t2c_v1_patched.json         (목표 ~2,300 samples)

Step 0-A  RENAME  edges (schema snippet + Cypher 동시 치환)
Step 0-B  FIX     eg_used_* 방향 오류 (vt_petition → vt_case)
Step 0-C  DELETE  deprecated 엣지 사용 샘플 (61개)
Step 0-D  TRIM    단일 노드 과잉 샘플 제거 (3,251 → 1,500)
"""

import json
import re
import random
import copy
from pathlib import Path
from collections import Counter

SEED = 42
random.seed(SEED)

SRC_PATH = Path("data/t2c_v1_all_validated.json")
DST_PATH = Path("data/t2c_v1_patched.json")

# ─── Step 0-A: 엣지 이름 변경 맵 ────────────────────────────────────────────
RENAME_MAP = {
    "similar_to":   "related_case",
    "sent_via":     "sent_msg",
    "received_by":  "received_msg",
}

# ─── Step 0-C: 삭제 대상 deprecated 엣지 ────────────────────────────────────
DEPRECATED_EDGES = {"contacted", "impersonates", "accessed", "performed_by"}

# ─── Step 0-D: 단일 노드 목표 수 ─────────────────────────────────────────────
SINGLE_NODE_TARGET = 1_500

# threat 속성이 있는 샘플 — 우선 보존
THREAT_ATTRS = ["risk_level", "is_burner", "is_frozen", "threat_score",
                "is_active", "fraud_type", "confidence"]

# ─── 헬퍼 ─────────────────────────────────────────────────────────────────────

def get_gpt_value(sample: dict) -> str:
    for c in sample["conversations"]:
        if c["from"] == "gpt":
            return c["value"]
    return ""


def has_edge_in_cypher(sample: dict) -> bool:
    """Cypher 안에 관계 패턴 [:edge_name] 이 있으면 True"""
    gpt = get_gpt_value(sample)
    return bool(re.search(r"\[\w*:[a-z_*]+", gpt))


def has_deprecated_edge(sample: dict) -> bool:
    gpt = get_gpt_value(sample)
    for dep in DEPRECATED_EDGES:
        if re.search(r"\[\w*:\s*" + dep + r"[\s\]{}]", gpt):
            return True
    return False


def has_threat_attr(sample: dict) -> bool:
    full = json.dumps(sample, ensure_ascii=False)
    return any(attr in full for attr in THREAT_ATTRS)


def replace_in_sample(sample: dict, old: str, new: str) -> dict:
    """sample 내 모든 conversation value에서 old→new 단순 치환"""
    s = copy.deepcopy(sample)
    for c in s["conversations"]:
        c["value"] = c["value"].replace(old, new)
    return s


# ─── Step 0-B 전용 패치 ──────────────────────────────────────────────────────

EG_USED_PATTERN = re.compile(
    r"\((\w+):vt_petition\s*\{petition_id:'([^']+)'\}\)",
)
SCHEMA_PETITION_PATTERN = re.compile(
    r"\(vt_petition\)-\[:(eg_used_\w+)[^\]]*\]->",
)


def patch_eg_used_direction(sample: dict) -> dict:
    """
    eg_used_* 방향 수정:
      vt_petition → vt_case,  petition_id → flnm
    스키마 snippet(human) + Cypher(gpt) 모두 치환
    """
    s = copy.deepcopy(sample)
    for c in s["conversations"]:
        v = c["value"]
        # Cypher: (pt:vt_petition {petition_id:'...'}) → (c:vt_case {flnm:'...'})
        v = re.sub(
            r"\((\w+):vt_petition\s*\{petition_id:'([^']+)'\}\)",
            lambda m: f"(c:vt_case {{flnm:'{_generate_case_id(m.group(2))}'}})",
            v,
        )
        # 잔여 vt_petition 변수 참조 (RETURN pt 등)
        v = re.sub(r"\bpt\b(?=\s*(agtype|,|\)))", "c", v)
        # schema snippet — relationship direction
        v = re.sub(
            r"\(vt_petition\)-\[:(eg_used_\w+)",
            r"(vt_case)-[:\1",
            v,
        )
        # schema snippet — node definition line
        # (vt_petition {petition_id, ...}) → (vt_case {flnm, crime_type_cd, ...})
        v = re.sub(
            r"\(vt_petition\s*\{[^}]*\}\)",
            r"(vt_case {flnm, crime_type_cd, damage_amt, status})",
            v,
        )
        # fallback: bare vt_petition remaining
        v = v.replace("vt_petition", "vt_case")
        v = v.replace("petition_id", "flnm")
        c["value"] = v
    return s


def _generate_case_id(petition_id: str) -> str:
    """PT-2024-567 형태 → 2024-사이버-567 형태로 변환"""
    m = re.match(r"PT-(\d{4})-(\d+)", petition_id)
    if m:
        return f"{m.group(1)}-사이버-{m.group(2)}"
    return petition_id


# ─── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    with open(SRC_PATH, encoding="utf-8") as f:
        data: list[dict] = json.load(f)

    stats = {
        "input": len(data),
        "0a_renamed": 0,
        "0b_eg_fixed": 0,
        "0c_deleted": 0,
        "0d_trimmed": 0,
        "output": 0,
    }

    patched: list[dict] = []

    # ── Step 0-A + 0-B + 0-C 를 한 번에 순회 ──────────────────────────────
    for sample in data:
        # 0-C: deprecated 엣지 포함 샘플 삭제
        if has_deprecated_edge(sample):
            stats["0c_deleted"] += 1
            continue

        s = copy.deepcopy(sample)

        # 0-A: 엣지 이름 변경 (schema + Cypher)
        full_before = json.dumps(s, ensure_ascii=False)
        for old, new in RENAME_MAP.items():
            s = replace_in_sample(s, old, new)
        if json.dumps(s, ensure_ascii=False) != full_before:
            stats["0a_renamed"] += 1

        # 0-B: eg_used_* 방향 수정
        full_before = json.dumps(s, ensure_ascii=False)
        if "eg_used" in full_before:
            s = patch_eg_used_direction(s)
            stats["0b_eg_fixed"] += 1

        patched.append(s)

    # ── Step 0-D: 단일 노드 과잉 제거 ──────────────────────────────────────
    non_query   = [s for s in patched if s.get("intent") != "QUERY"]
    multi_hop   = [s for s in patched if s.get("intent") == "QUERY" and has_edge_in_cypher(s)]
    single_node = [s for s in patched if s.get("intent") == "QUERY" and not has_edge_in_cypher(s)]

    print(f"\n[0-D 전] 단일 노드 QUERY: {len(single_node)}")
    print(f"         멀티홉 QUERY:    {len(multi_hop)}")
    print(f"         비QUERY:         {len(non_query)}")

    if len(single_node) > SINGLE_NODE_TARGET:
        threat_singles    = [s for s in single_node if has_threat_attr(s)]
        non_threat_singles = [s for s in single_node if not has_threat_attr(s)]

        # 우선 보존: threat 속성 포함 → 부족하면 non_threat 에서 채움
        keep = []
        if len(threat_singles) >= SINGLE_NODE_TARGET:
            random.shuffle(threat_singles)
            keep = threat_singles[:SINGLE_NODE_TARGET]
        else:
            keep = threat_singles
            remain = SINGLE_NODE_TARGET - len(keep)
            random.shuffle(non_threat_singles)
            keep += non_threat_singles[:remain]

        stats["0d_trimmed"] = len(single_node) - len(keep)
        single_node = keep

    final = non_query + multi_hop + single_node
    random.shuffle(final)

    stats["output"] = len(final)

    DST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DST_PATH, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    # ── 리포트 ──────────────────────────────────────────────────────────────
    print("\n=== 00_patch_v1_dataset 완료 ===")
    print(f"  입력:           {stats['input']:>6,}")
    print(f"  0-A 이름변경:   {stats['0a_renamed']:>6,}")
    print(f"  0-B eg방향수정: {stats['0b_eg_fixed']:>6,}")
    print(f"  0-C deprecated: -{stats['0c_deleted']:>5,}")
    print(f"  0-D 단일노드↓:  -{stats['0d_trimmed']:>5,}")
    print(f"  출력:           {stats['output']:>6,}  → {DST_PATH}")

    # 최종 분포 확인
    intents = Counter(s.get("intent") for s in final)
    print(f"\n  Intent: {dict(intents)}")
    query_samples = [s for s in final if s.get("intent") == "QUERY"]
    single_final  = sum(1 for s in query_samples if not has_edge_in_cypher(s))
    multi_final   = sum(1 for s in query_samples if has_edge_in_cypher(s))
    print(f"  QUERY 단일노드: {single_final}")
    print(f"  QUERY 멀티홉:   {multi_final}")

    # deprecated 잔류 확인
    dep_remain = sum(1 for s in final if has_deprecated_edge(s))
    print(f"  deprecated 잔류: {dep_remain}  (0이어야 함)")

    # vt_petition 잔류: filed_as 샘플은 정상, eg_used 혼재만 오류
    petition_remain = [
        s for s in final
        if "vt_petition" in json.dumps(s, ensure_ascii=False)
    ]
    petition_eg_remain = [
        s for s in petition_remain
        if "eg_used" in json.dumps(s, ensure_ascii=False)
    ]
    print(f"  vt_petition 잔류: {len(petition_remain)}  (filed_as 유효 샘플)")
    print(f"  vt_petition+eg_used 오류: {len(petition_eg_remain)}  (0이어야 함)")


if __name__ == "__main__":
    main()
