"""v37/v38/v39/v40 4세대 비교 보고서 자동 생성기
출력: docs/T2C_V37_V40_COMPARISON_<date>.md
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
RESULTS_DIR = ROOT / 'results'
DOCS_DIR = ROOT / 'docs'

VERSIONS = ['v37', 'v38', 'v39', 'v40']
BENCH_FILES = {v: RESULTS_DIR / f'bench_{v}_full.json' for v in VERSIONS}
V40_SCEN = RESULTS_DIR / 'test_v40_natural_query.json'

# 사전 알려진 카테고리 (벤치마크 결과 파싱용)
KNOWN_CATEGORIES = [
    'v37_anonymous', 'v37_cluster', 'v37_multihop', 'v37_relay_station',
    'meta_condition', 'chain', 'threat_filter', '1hop_object', '1hop_object_extra',
    '1hop_case', '1hop_event', '1hop_person', '1hop_person2person',
    '단일노드', 'general', 'guard',
    # v40 신규
    'multi_where', 'meta_filter', 'partial_match', 'time_order',
    'edge_direction', 'edge_naming', 'hub_node_simple', 'no_cast',
]


def load_bench(version):
    p = BENCH_FILES[version]
    if not p.exists():
        return None
    try:
        return json.load(open(p))
    except Exception as e:
        print(f'⚠️  {p} 로드 실패: {e}', file=sys.stderr)
        return None


def cat_pct(bench, cat_key):
    if not bench:
        return None
    # 다양한 구조 지원
    if 'category_stats' in bench:
        c = bench['category_stats'].get(cat_key)
        if c:
            p, t = c.get('pass', c.get('passed', 0)), c.get('total', 0)
            if t > 0:
                return (p, t, 100 * p / t)
    if '카테고리별' in bench:
        c = bench['카테고리별'].get(cat_key)
        if c:
            return c
    if 'results' in bench:
        # results 가 list 일 때
        items = [r for r in bench['results'] if r.get('category') == cat_key or r.get('cat') == cat_key]
        if items:
            ok = sum(1 for r in items if r.get('ok') or r.get('passed'))
            return (ok, len(items), 100 * ok / len(items))
    return None


def main():
    data = {v: load_bench(v) for v in VERSIONS}
    if not any(data.values()):
        print('❌ 벤치마크 결과 파일 없음. 먼저 benchmark_v40.sh 실행.')
        sys.exit(1)

    today = datetime.now().strftime('%Y%m%d')
    out_path = DOCS_DIR / f'T2C_V37_V40_COMPARISON_{today}.md'

    lines = []
    lines.append(f'# Text2Cypher v37 → v40 4세대 비교 보고서')
    lines.append('')
    lines.append(f'- **작성일**: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    lines.append('- **베이스 모델**: Qwen2.5-7B-Instruct')
    lines.append('- **데이터셋 진화**: v37 28,109 → v38 30,032 → v39 31,694 → v40 33,242')
    lines.append('- **GPT-4o 참조 천장**: 95.4% (145/152)')
    lines.append('')
    lines.append('---')
    lines.append('')

    # ─────────────────────────────────────────────
    # 1. 전체 통과율
    # ─────────────────────────────────────────────
    lines.append('## 1. 전체 정확도 비교 (152문항)')
    lines.append('')
    lines.append('| 버전 | 통과 | 전체 | 정확도 | Δ |')
    lines.append('|------|------|------|--------|---|')
    prev_pct = None
    for v in VERSIONS:
        d = data[v]
        if not d:
            lines.append(f'| {v} | - | - | - | - |')
            continue
        p, t = d.get('passed'), d.get('total')
        pct = 100 * p / t if t else 0
        delta = f"{pct - prev_pct:+.1f}p" if prev_pct is not None else '-'
        lines.append(f'| **{v}** | {p} | {t} | **{pct:.1f}%** | {delta} |')
        prev_pct = pct
    lines.append('')

    # GPT-4o 격차
    if data.get('v40') and data['v40'].get('passed'):
        v40p = 100 * data['v40']['passed'] / data['v40']['total']
        lines.append(f'**GPT-4o (95.4%) 와의 격차**: {v40p - 95.4:.1f}p')
        lines.append('')

    # ─────────────────────────────────────────────
    # 2. 카테고리별 추이
    # ─────────────────────────────────────────────
    lines.append('## 2. 카테고리별 정확도 추이')
    lines.append('')
    lines.append('| 카테고리 | v37 | v38 | v39 | v40 | Δ (v40-v39) |')
    lines.append('|----------|-----|-----|-----|-----|-------------|')
    for cat in KNOWN_CATEGORIES:
        cells = []
        pcts = {}
        for v in VERSIONS:
            r = cat_pct(data.get(v), cat)
            if r:
                p, t, pct = r
                cells.append(f'{pct:.0f}%')
                pcts[v] = pct
            else:
                cells.append('-')
        if all(c == '-' for c in cells):
            continue  # 어디에도 없는 카테고리 스킵
        v40p, v39p = pcts.get('v40'), pcts.get('v39')
        if v40p is not None and v39p is not None:
            delta = f'{v40p - v39p:+.0f}p'
        else:
            delta = '-'
        lines.append(f'| {cat} | {cells[0]} | {cells[1]} | {cells[2]} | {cells[3]} | {delta} |')
    lines.append('')

    # ─────────────────────────────────────────────
    # 3. V4.0 시나리오 45 케이스
    # ─────────────────────────────────────────────
    if V40_SCEN.exists():
        scen = json.load(open(V40_SCEN))
        lines.append('## 3. V4.0 시나리오 자연어 45 케이스 (tccop_v40_demo)')
        lines.append('')
        passed = scen.get('passed', 0); total = scen.get('total', 45)
        lines.append(f'**전체**: {passed}/{total} ({100*passed/total:.1f}%)')
        lines.append('')
        lines.append('| 카테고리 | 통과 | 전체 | 정확도 | 평균 ms |')
        lines.append('|----------|------|------|--------|---------|')
        for cat, st in sorted((scen.get('category_stats') or {}).items()):
            p, t = st.get('pass', 0), st.get('total', 0)
            ms = (st.get('time_sum', 0) / t) if t else 0
            pct_v = (100 * p / t) if t else 0
            lines.append(f'| {cat} | {p} | {t} | {pct_v:.1f}% | {ms:.0f} |')
        lines.append('')

    # ─────────────────────────────────────────────
    # 4. v40 핵심 변경 사항 (학습 데이터)
    # ─────────────────────────────────────────────
    lines.append('## 4. v40 학습 데이터 변경 사항')
    lines.append('')
    lines.append('| 패턴 | 시드 | 목적 |')
    lines.append('|------|------|------|')
    lines.append('| multi_where | 374 | 다중 AND/OR WHERE 조건 |')
    lines.append('| meta_filter | 283 | V4.0 source_domain / reliability_tier |')
    lines.append('| partial_match | 197 | CONTAINS / STARTS WITH |')
    lines.append('| time_order | 195 | ORDER BY occurred_at DESC LIMIT N |')
    lines.append('| edge_direction | 184 | hosts/has_account/from_account 방향 |')
    lines.append('| edge_naming | 139 | involves(deprecated) → suspect_in |')
    lines.append('| hub_node_simple | 97 | pt_cluster/site_cluster 단순 RETURN |')
    lines.append('| no_cast | 98 | ::int 캐스팅 금지 |')
    lines.append('| **합계** | **1,548** | |')
    lines.append('')

    # ─────────────────────────────────────────────
    # 5. 결론
    # ─────────────────────────────────────────────
    lines.append('## 5. 결론')
    lines.append('')
    if data.get('v40') and data.get('v39'):
        v40p = 100 * data['v40']['passed'] / data['v40']['total']
        v39p = 100 * data['v39']['passed'] / data['v39']['total']
        delta = v40p - v39p
        verdict = '🎉 큰 개선' if delta >= 5 else '🟢 개선' if delta > 0 else '🟡 정체' if delta > -3 else '🔴 회귀'
        lines.append(f'- **v39 → v40**: {v39p:.1f}% → {v40p:.1f}% ({delta:+.1f}p) {verdict}')
    lines.append('- 약점 보강 시드 1,548 의 효과 검증 — 다중 WHERE / 메타 필터 / CONTAINS 등 8 패턴')
    lines.append('')
    lines.append('---')
    lines.append('')
    lines.append('**자동 생성**: `scripts/generate_v40_report.py`')

    out_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f'✅ 보고서 생성: {out_path}')
    print(f'   ({out_path.stat().st_size // 1024} KB)')


if __name__ == '__main__':
    main()
