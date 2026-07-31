#!/usr/bin/env python3
"""A/B 정확도 측정 — 스키마 pruning 키워드 augmentation on/off 비교.

use_keyword_augment=True(키워드 exact-match 보강) vs False(순수 semantic router)
두 조건에서 동일 케이스셋의 Cypher 생성 정답률을 비교해, recall 보강의 순효과를 측정한다.
근거: arXiv 2505.05118 (schema filtering) — 보강이 router 누락을 얼마나 복구하는지 정량화.

전제조건:
  - vLLM(v42) 서빙 도달 (.env SLLM_ENDPOINT, 예: http://localhost:8000/v1)
  - AgensGraph DB 도달 (.env DB_HOST/PORT) + 대상 그래프 존재
채점(test_v40_natural_query.py와 동일):
  - kw_ok : 기대 키워드가 생성 Cypher에 모두 포함
  - res_ok: 에러 없이 결과 반환(또는 COUNT/SUM 집계)

실행: python scripts/ab_schema_augment.py [--limit N] [--category B.]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.services.langgraph_agent import LangGraphAgent
from scripts.test_v40_natural_query import TESTS, GRAPH


def score(out, must):
    """test_v40_natural_query.py와 동일 채점 로직."""
    cypher = (out or {}).get('cypher') or ''
    elements = (out or {}).get('elements') or []
    err = (out or {}).get('error')
    kw_ok = all(kw.lower() in cypher.lower() for kw in must)
    res_ok = (not err) and (len(elements) > 0 or 'COUNT' in cypher.upper() or 'SUM' in cypher.upper())
    return (kw_ok and res_ok), cypher


def run_condition(agent, cases, augment):
    """한 조건(augment on/off)으로 전 케이스 실행 → (통과수, 케이스별 결과)."""
    cfg = {"use_keyword_augment": augment}
    passed = 0
    rows = []
    for cat, q, must in cases:
        try:
            out = agent.run(q, GRAPH, config=cfg)
            ok, cypher = score(out, must)
        except Exception as e:
            ok, cypher = False, f"EXC:{e}"
        passed += int(ok)
        rows.append({"cat": cat, "q": q, "ok": ok, "cypher": cypher[:120]})
    return passed, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=None, help='첫 N 케이스만')
    ap.add_argument('--category', default=None, help='카테고리 prefix (예: B.)')
    args = ap.parse_args()

    cases = TESTS
    if args.category:
        cases = [t for t in cases if t[0].startswith(args.category)]
    if args.limit:
        cases = cases[:args.limit]

    app = create_app()
    app.app_context().push()
    agent = LangGraphAgent()

    n = len(cases)
    print(f"A/B 스키마 pruning augmentation — {n} 케이스 / graph={GRAPH}")
    print("  (같은 케이스를 use_keyword_augment OFF→ON 두 번 실행; router 캐시로 labels는 동일, 보강만 분기)")
    t0 = time.time()
    off_pass, off_rows = run_condition(agent, cases, augment=False)
    on_pass, on_rows = run_condition(agent, cases, augment=True)
    dt = time.time() - t0

    print("=" * 64)
    print(f"  OFF (순수 semantic router): {off_pass}/{n}  ({100*off_pass/n:.1f}%)")
    print(f"  ON  (키워드 exact-match 보강): {on_pass}/{n}  ({100*on_pass/n:.1f}%)")
    print(f"  Δ = {on_pass - off_pass:+d}  ({100*(on_pass - off_pass)/n:+.1f}p)")
    print("=" * 64)

    # 케이스별 변화 (보강이 살린/깨뜨린 케이스)
    flips = []
    for o, nrow in zip(off_rows, on_rows):
        if o['ok'] != nrow['ok']:
            flips.append((nrow['ok'], o['cat'], o['q']))
    if flips:
        print("  변화 케이스:")
        for gained, cat, q in sorted(flips, key=lambda x: not x[0]):
            tag = '＋ OFF✗ → ON✓ (보강이 살림)' if gained else '－ OFF✓ → ON✗ (보강이 깨뜨림 ⚠)'
            print(f"    {tag}  [{cat}] {q}")
    else:
        print("  변화 케이스 없음 (보강이 정답률에 영향 없음)")

    os.makedirs('results', exist_ok=True)
    out_path = 'results/ab_schema_augment.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump({
            "graph": GRAPH, "n": n,
            "off_pass": off_pass, "on_pass": on_pass, "delta": on_pass - off_pass,
            "flips": [{"gained": g, "cat": c, "q": q} for g, c, q in flips],
            "off": off_rows, "on": on_rows, "elapsed_sec": dt,
        }, f, ensure_ascii=False, indent=2)
    print(f"  저장: {out_path}  ({dt:.0f}s)")


if __name__ == '__main__':
    main()
