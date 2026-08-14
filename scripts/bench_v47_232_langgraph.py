#!/usr/bin/env python3
"""
v47용 232문항 벤치 하네스 — v46과 '동일 조건'의 순수 프롬프트 비교.

핵심: eval_response는 생성된 Cypher '문자열'만 채점 → 실행 불필요.
      langgraph run()의 실행/data_view가 특정 문항서 hang 유발 → '생성만' 경로로 전환.

v46 측정(benchmark_t2c_v2 --mode t2c_v37 --no-few-shot)과 완전 동일하게 재사용:
  · BENCH_ITEMS            (232문항)
  · eval_response          (SQL-Wrapped Cypher 채점)
  · pre_route_guard_general (GUARD/GENERAL 사전 차단)
  · call_model_t2c_v37     (system + 질문 + native→SQL-Wrap)  ← 동일 생성 함수
  · few-shot OFF

유일한 차이(= 목적):  system 프롬프트만 v37 → **v47**(t2c_v47_system.txt, 실스키마 26경로)
                      즉 순수 'v37 프롬프트 vs v47 프롬프트' 비교.

실행:  python3 -u scripts/bench_v47_232_langgraph.py
출력:  results/bench_v47_232_langgraph.json  (v46 결과와 동일 키)
"""
import sys, os, json
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(_ROOT, ".env"))
from openai import OpenAI
from benchmark_t2c_v2 import BENCH_ITEMS, eval_response, pre_route_guard_general, call_model_t2c_v37

ENDPOINT = os.getenv("SLLM_ENDPOINT", "http://localhost:8002/v1")
MODEL    = os.getenv("SLLM_MODEL_NAME", "qwen25-coder-t2c-v47")
GRAPH    = os.getenv("TEST_GRAPH_PATH", "tccop_graph_v6")
SYSTEM_V47 = open(os.path.join(_ROOT, "app/services/prompts/t2c_v47_system.txt"), encoding="utf-8").read()
OUT = os.path.join(_ROOT, "results", "bench_v47_232_langgraph.json")

print(f"MODEL={MODEL}  ENDPOINT={ENDPOINT}  GRAPH={GRAPH}  문항={len(BENCH_ITEMS)}  system=v47(실스키마)", flush=True)
client = OpenAI(base_url=ENDPOINT, api_key="EMPTY", max_retries=1, timeout=30)

results = []
for item in BENCH_ITEMS:
    try:
        pre = pre_route_guard_general(item.question)  # v46과 동일 사전 차단
        if pre is not None:
            response = pre
        else:
            # v47 프롬프트 방식: v47 system + 질문(few-shot OFF) → native → SQL-Wrap. 생성만(실행 없음 = hang 없음)
            response = call_model_t2c_v37(client, item.question, MODEL, SYSTEM_V47, GRAPH, use_few_shot=False)
        res = eval_response(item, response)
        results.append(res)
        print(f"  {'✅' if res['pass'] else '❌'} [{item.id}] {item.question[:42]}", flush=True)
    except Exception as e:
        results.append({"id": item.id, "error": str(e), "pass": False})
        print(f"  ⚠️  [{item.id}] {e}", flush=True)

# ── 집계 (benchmark_t2c_v2.main과 동일) ──
total = len(results)
passed = sum(1 for r in results if r.get("pass"))
by_cat = {}
for r in results:
    it = next((i for i in BENCH_ITEMS if i.id == r.get("id")), None)
    by_cat.setdefault(it.category if it else "unknown", []).append(bool(r.get("pass", False)))

def _acc(k):
    vs = [r["checks"].get(k) for r in results
          if isinstance(r.get("checks"), dict) and k in r.get("checks", {})]
    return round(sum(vs) / len(vs) * 100, 1) if vs else 0.0

out = {
    "model": MODEL, "endpoint": ENDPOINT, "mode": "v47프롬프트(질문만+실스키마)·생성만",
    "total": total, "passed": passed,
    "pass_rate": round(passed / total * 100, 1) if total else 0.0,
    "new_edge_accuracy": _acc("new_edge_accuracy"),
    "v37_edge_accuracy": _acc("v37_edge_accuracy"),
    "by_category": {c: {"passed": sum(v), "total": len(v), "rate": round(sum(v)/len(v)*100, 1)}
                    for c, v in sorted(by_cat.items())},
    "details": results,
}
os.makedirs(os.path.join(_ROOT, "results"), exist_ok=True)
json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print(f"\n{'='*60}", flush=True)
print(f"  v47(v47프롬프트) 전체: {passed}/{total} ({out['pass_rate']}%)", flush=True)
print(f"  v3.6 신규 엣지: {out['new_edge_accuracy']}%   v3.7 신규 엣지: {out['v37_edge_accuracy']}%", flush=True)
print(f"  저장: {OUT}", flush=True)
