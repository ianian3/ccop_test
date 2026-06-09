"""
v3.7 최종 학습 데이터셋 hop 분포 분석

입력: data/ccop_v37_final_sharegpt.json (28,433개)

분석 항목:
  - 1-hop:     (a)-[r]->(b)
  - 2-hop:     (a)-[r1]->(b)-[r2]->(c)
  - 3-hop+:    3개 이상 관계
  - var-hop:   가변 길이 (*1..5 등) → 별도 분류
  - shortestPath: 최단경로 함수
  - 0-hop:     관계 없이 노드만 조회 (단순 MATCH (n) RETURN n)

v3.7 신규 패턴(pt_cluster, site_cluster, used_in_device 등)이 어느 hop에 분포하는지 함께 측정.
"""

import json
import re
from collections import defaultdict, Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent
INPUT = DATA_DIR / "ccop_v37_final_sharegpt.json"


V37_PATTERNS = [
    'pt_cluster', 'site_cluster', 'belongs_to_cluster',
    'belongs_to_campaign', 'used_in_device', 'is_anonymous',
    "'relay_station'"
]


def get_response(sample: dict) -> str:
    for t in sample["conversations"]:
        if t.get("from") in ("gpt", "assistant"):
            return t.get("value", "")
    return ""


def classify_hops(cypher: str) -> str:
    """Cypher 쿼리의 hop 수를 분류.

    분류 우선순위:
      1. shortestPath / shortest_path 함수 → 'shortestPath'
      2. 가변 길이 패턴 [*N..M] / [*..M] / [*N..] / [*] → 'var-hop'
      3. 화살표 개수로 fixed-hop 분류 (1-hop / 2-hop / 3-hop / 4-hop+)
      4. 관계 없음 → '0-hop'
    """
    c = cypher.strip()

    # shortestPath
    if re.search(r'shortest_?path\s*\(', c, re.IGNORECASE):
        return 'shortestPath'

    # 가변 길이 — [:RELTYPE*1..5], [r*1..3], [*..5], [*2..], [*]
    if re.search(r'\[\s*[\w:]*\*[\d.]*\s*\]', c):
        return 'var-hop'

    # 고정 hop: 단방향(<-/->)과 양방향(--) 화살표 모두 카운트
    # 패턴: -[...]-> 또는 <-[...]- 또는 -[...]-
    arrow_pattern = re.compile(r'-\s*\[[^\]]*\]\s*->|<-\s*\[[^\]]*\]\s*-|-\s*\[[^\]]*\]\s*-')
    arrows = arrow_pattern.findall(c)
    n = len(arrows)

    if n == 0:
        return '0-hop'
    elif n == 1:
        return '1-hop'
    elif n == 2:
        return '2-hop'
    elif n == 3:
        return '3-hop'
    else:
        return '4-hop+'


def is_v37_new(cypher: str) -> bool:
    return any(p in cypher for p in V37_PATTERNS)


def main():
    with open(INPUT, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total = len(data)
    hop_counter = Counter()
    hop_v37 = defaultdict(int)     # hop별 v3.7 신규 샘플 수
    hop_legacy = defaultdict(int)  # hop별 v3.7 호환 기존 샘플 수

    examples = defaultdict(list)   # 카테고리별 샘플 1개씩 저장

    for s in data:
        cypher = get_response(s)
        cat = classify_hops(cypher)
        hop_counter[cat] += 1
        if is_v37_new(cypher):
            hop_v37[cat] += 1
            if len(examples[f'{cat}+v37']) < 1:
                q = ""
                for t in s["conversations"]:
                    if t.get("from") == "human":
                        q = t.get("value", "")
                examples[f'{cat}+v37'].append((q, cypher))
        else:
            hop_legacy[cat] += 1
            if len(examples[f'{cat}+legacy']) < 1:
                q = ""
                for t in s["conversations"]:
                    if t.get("from") == "human":
                        q = t.get("value", "")
                examples[f'{cat}+legacy'].append((q, cypher))

    # 출력
    print(f"📊 데이터셋: {INPUT.name}")
    print(f"   총 샘플: {total:,}개\n")

    order = ['0-hop', '1-hop', '2-hop', '3-hop', '4-hop+', 'var-hop', 'shortestPath']
    print(f"┌─────────────────┬─────────┬──────────┬───────────────┬────────────┐")
    print(f"│ Hop 카테고리    │  전체   │  v3.7신규│  v3.7신규 비중│ 비율(전체) │")
    print(f"├─────────────────┼─────────┼──────────┼───────────────┼────────────┤")
    for cat in order:
        cnt = hop_counter.get(cat, 0)
        v37 = hop_v37.get(cat, 0)
        legacy = hop_legacy.get(cat, 0)
        v37_pct = (v37 / cnt * 100) if cnt else 0
        overall_pct = cnt / total * 100
        print(f"│ {cat:<15s} │ {cnt:>6,}  │ {v37:>7,}  │   {v37_pct:>5.1f}%      │  {overall_pct:>5.1f}%    │")
    print(f"└─────────────────┴─────────┴──────────┴───────────────┴────────────┘")

    print()
    v37_total = sum(hop_v37.values())
    legacy_total = sum(hop_legacy.values())
    print(f"v3.7 신규 합계 : {v37_total:,}개 ({v37_total/total*100:.1f}%)")
    print(f"v3.7 호환 기존 : {legacy_total:,}개 ({legacy_total/total*100:.1f}%)")

    # 카테고리별 대표 예시
    print()
    print("━━━ 카테고리별 대표 샘플 ━━━")
    for cat in order:
        for kind in ('v37', 'legacy'):
            key = f'{cat}+{kind}'
            if key in examples and examples[key]:
                q, c = examples[key][0]
                label = '[v3.7 신규]' if kind == 'v37' else '[v3.7 호환]'
                print(f"\n● {cat} {label}")
                print(f"  Q: {q[:80]}")
                print(f"  A: {c[:140]}")


if __name__ == "__main__":
    main()
