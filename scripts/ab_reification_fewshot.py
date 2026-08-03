#!/usr/bin/env python3
"""A/B — V4.4 reification 2-hop 쿼리의 few-shot 효과 측정.
use_few_shot on/off로 reification 질문의 Cypher 생성 정확도(엣지명 포함)를 비교.
reification 엣지는 신규(그래프에 데이터 미적재)라 결과(res)가 아닌 '엣지명 정확도(kw)'를 채점 —
sLLM이 2-hop 패턴(access_via/via_ip/mentions_location/다형)을 올바로 생성하는지가 핵심.

전제: vLLM(v42) 서빙 + langgraph 경로. 실행: python scripts/ab_reification_fewshot.py
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app
from app.services.langgraph_agent import LangGraphAgent

GRAPH = 'tccop_v40_demo'

# (질문, 기대 엣지명 — 2-hop reification 시그니처)
CASES = [
    ("IP '198.51.100.7'에 접속한 전화번호를 찾아줘",        ['access_via']),
    ("특정 IP에서 접속한 계정 목록 (포털 역조회)",           ['access_via']),
    ("이 계좌 이체에 사용된 접속 IP",                        ['via_ip']),
    ("계좌에서 가상자산 지갑으로 전송한 이체 내역",           ['to_account']),
    ("ATM 현금 인출 이체 내역",                              ['to_account']),
    ("메시지에 언급된 거래 장소",                            ['mentions_location']),
    ("전화번호의 통화 발신 위치",                            ['occurred_at']),
    ("두 계정 간 주고받은 메시지",                            ['sent_msg']),
    ("가상자산으로 세탁된 자금 흐름",                        ['transferred_to']),
]


def score(out, must):
    cypher = (out or {}).get('cypher') or ''
    kw_ok = all(kw.lower() in cypher.lower() for kw in must)
    return kw_ok, cypher


def run_condition(agent, few_shot):
    # use_router=False: Router(OpenAI, 크레딧 429) 우회 — few-shot만 순수 변수로 격리
    cfg = {"use_few_shot": few_shot, "use_router": False}
    passed = 0
    rows = []
    for q, must in CASES:
        try:
            out = agent.run(q, GRAPH, config=cfg)
            ok, cy = score(out, must)
        except Exception as e:
            ok, cy = False, f"EXC:{e}"
        passed += int(ok)
        rows.append({"q": q, "must": must, "ok": ok, "cypher": cy[:160]})
    return passed, rows


def main():
    app = create_app()
    app.app_context().push()
    agent = LangGraphAgent()

    n = len(CASES)
    print(f"reification few-shot A/B — {n} 케이스 (2-hop 엣지명 정확도) / graph={GRAPH}")
    t0 = time.time()
    off_p, off = run_condition(agent, few_shot=False)
    on_p, on = run_condition(agent, few_shot=True)
    dt = time.time() - t0

    print("=" * 60)
    print(f"  OFF (few-shot 없음): {off_p}/{n}  ({100*off_p/n:.1f}%)")
    print(f"  ON  (few-shot 주입): {on_p}/{n}  ({100*on_p/n:.1f}%)")
    print(f"  Δ = {on_p - off_p:+d}  ({100*(on_p - off_p)/n:+.1f}p)")
    print("=" * 60)
    for o, nrow in zip(off, on):
        if o['ok'] != nrow['ok']:
            tag = '＋ OFF✗→ON✓ (few-shot이 살림)' if nrow['ok'] else '－ OFF✓→ON✗'
            print(f"  {tag}  {o['q']}")
    # 실패 케이스의 실제 생성 cypher(ON) 일부 출력
    print("  --- ON 생성 예시 ---")
    for nrow in on[:3]:
        print(f"    [{'✓' if nrow['ok'] else '✗'}] {nrow['q']}")
        print(f"        {nrow['cypher']}")

    os.makedirs('results', exist_ok=True)
    with open('results/ab_reification_fewshot.json', 'w', encoding='utf-8') as f:
        json.dump({"n": n, "off_pass": off_p, "on_pass": on_p,
                   "delta": on_p - off_p, "off": off, "on": on, "elapsed_sec": dt},
                  f, ensure_ascii=False, indent=2)
    print(f"  저장: results/ab_reification_fewshot.json ({dt:.0f}s)")


if __name__ == '__main__':
    main()
