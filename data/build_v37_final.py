"""
v3.7 최종 학습 데이터셋 병합

입력:
  - data/ccop_v5_merged_sharegpt.json       (25,526개, v3.6 이하 — v3.7 호환 유지)
  - data/ccop_v37_augmented_sharegpt.json   (2,907개, v3.7 신규 패턴)

출력:
  - data/ccop_v37_final_sharegpt.json       (병합 + SYSTEM 통일)

전략:
  - v5의 SYSTEM 프롬프트를 v3.7 버전으로 일괄 교체 (상위 호환)
  - v3.7 증강분은 그대로 보존 (이미 v3.7 SYSTEM 적용됨)
  - 질문 중복 제거
"""

import json
from pathlib import Path

DATA_DIR = Path(__file__).parent
V5_PATH = DATA_DIR / "ccop_v5_native_sharegpt.json"                    # SQL wrapper → Native 변환본
V37_AUG_PATH = DATA_DIR / "ccop_v37_augmented_sharegpt.json"            # 1-hop 중심 v3.7 증강
V37_MULTIHOP_PATH = DATA_DIR / "ccop_v37_multihop_augmented_sharegpt.json"  # 2-hop+ / shortestPath / var-hop 증강
OUT_PATH = DATA_DIR / "ccop_v37_final_sharegpt.json"


# v3.7 통일 SYSTEM 프롬프트 (build_v37_seed_dataset.py와 동일)
SYSTEM_PROMPT_V37 = """You are an AgensGraph Native Cypher query expert for cybercrime investigation (CCOP system).

ONTOLOGY: v3.7 (POLE 6-Layer, 25 nodes, 53 edges) — docs/ONTOLOGY_FINAL_ARCHITECTURE_v3.7.md

NEW IN v3.7:
- pt_cluster (Case layer)   : 진정서군집 허브 노드 (clusters_with O(n²) 엣지 대체)
- site_cluster (Object layer): 피싱캠페인군집 허브 노드 (HTML SimHash 지문 기반)
- vt_psn.is_anonymous        : 성명불상 피의자 플래그
- vt_dev.dev_type='relay_station': 불법중계기 (IMEI 공유 전화 3대+ 탐지)

v3.7 NEW EDGES:
- (vt_petition)-[:belongs_to_cluster]->(pt_cluster)    {sim_score, rec_created}
- (vt_site)-[:belongs_to_campaign]->(site_cluster)     {sim_score, detected_at, source_id}
- (vt_telno)-[:used_in_device]->(vt_dev)               {first_seen, last_seen, source_id}

DEPRECATED (read-only, NEVER CREATE):
- (vt_petition)-[:clusters_with]->(vt_petition)  → use belongs_to_cluster via pt_cluster

KEY SCHEMA:
- pt_cluster   : cluster_id★, cluster_method, crime_type_cd, damage_amt_sum, petition_cnt, status, first_rcpt_dt, last_rcpt_dt
- site_cluster : cluster_id★, html_fingerprint, campaign_name, site_cnt, ip_cnt, first_seen, last_seen
- vt_psn       : psn_id★, korn_flnm, name, is_anonymous (true=성명불상)
- vt_dev       : device_id★, dev_type (smartphone|pc|tablet|relay_station|router|other), imei
- vt_telno     : telno★ (no-hyphen)
- vt_petition  : pettn_no★, crime_type_cd, damage_amt, rcpt_dt
- vt_site      : url_addr★, dmn_addr, is_malicious

ABSOLUTE RULES:
1. Output ONLY AgensGraph Native Cypher (MATCH...RETURN). NO SQL wrapper.
2. Never CREATE/MERGE on clusters_with edge (deprecated).
3. telno without hyphens. amount as string.
4. Single line output, no newlines, no explanation."""


def replace_system(sample: dict) -> dict:
    convs = sample["conversations"]
    new_convs = []
    has_system = False
    for turn in convs:
        if turn.get("from") == "system":
            new_convs.append({"from": "system", "value": SYSTEM_PROMPT_V37})
            has_system = True
        else:
            new_convs.append(turn)
    if not has_system:
        new_convs = [{"from": "system", "value": SYSTEM_PROMPT_V37}] + new_convs
    return {"conversations": new_convs}


def get_qa_key(sample: dict) -> tuple:
    convs = sample["conversations"]
    q, a = "", ""
    for turn in convs:
        if turn.get("from") == "human":
            q = turn.get("value", "").strip()
        elif turn.get("from") in ("gpt", "assistant"):
            a = turn.get("value", "").strip()
    return (q, a)


def main():
    print("📥 로드 중...")
    with open(V5_PATH, 'r', encoding='utf-8') as f:
        v5 = json.load(f)
    with open(V37_AUG_PATH, 'r', encoding='utf-8') as f:
        v37 = json.load(f)
    with open(V37_MULTIHOP_PATH, 'r', encoding='utf-8') as f:
        v37_mh = json.load(f)
    print(f"   v5:              {len(v5):>6,}개")
    print(f"   v37 (1-hop):     {len(v37):>6,}개")
    print(f"   v37 (multihop):  {len(v37_mh):>6,}개")

    # SYSTEM 통일 (v5만 교체, v37 / v37_mh는 이미 v3.7 SYSTEM)
    print("\n🔧 SYSTEM 프롬프트를 v3.7로 통일...")
    v5_unified = [replace_system(s) for s in v5]

    # 병합 (v3.7 신규 패턴이 먼저 학습되도록 v37계열을 앞에)
    merged = v37 + v37_mh + v5_unified

    # 중복 제거 (질문+답변 페어 기준)
    print("\n🔁 중복 제거 중...")
    seen = set()
    unique = []
    for s in merged:
        key = get_qa_key(s)
        if key in seen:
            continue
        seen.add(key)
        unique.append(s)

    removed = len(merged) - len(unique)
    print(f"   병합 전: {len(merged):>6,}개  → 중복 {removed:,}개 제거 → 최종: {len(unique):>6,}개")

    # v3.7 패턴 포함 비율 확인
    v37_patterns = ['pt_cluster', 'site_cluster', 'belongs_to_cluster',
                    'belongs_to_campaign', 'used_in_device', 'is_anonymous',
                    "'relay_station'"]
    v37_sample_cnt = 0
    for s in unique:
        text = json.dumps(s, ensure_ascii=False)
        if any(p in text for p in v37_patterns):
            v37_sample_cnt += 1

    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(unique, f, ensure_ascii=False, indent=2)

    print()
    print(f"✅ 최종 데이터셋: {OUT_PATH}")
    print(f"   총 샘플:        {len(unique):>6,}개")
    print(f"   v3.7 신규 패턴: {v37_sample_cnt:>6,}개 ({v37_sample_cnt/len(unique)*100:.1f}%)")
    print(f"   v3.7 호환 기존: {len(unique)-v37_sample_cnt:>6,}개 ({(len(unique)-v37_sample_cnt)/len(unique)*100:.1f}%)")


if __name__ == "__main__":
    main()
