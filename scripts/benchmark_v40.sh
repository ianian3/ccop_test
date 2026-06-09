#!/usr/bin/env bash
# ============================================================
# v40 .env 갱신 + 벤치마크 + 4세대 비교 자동화 (로컬 맥용)
# ============================================================
# 사용법:  bash scripts/benchmark_v40.sh
# 위치:    /Users/iankwon/test/coop_v1.0
# 전제:    학습 서버에서 deploy_v40.sh 완료, vLLM 서빙 중
# ============================================================
set -euo pipefail

cd "$(dirname "$0")/.."

MODEL=qwen25_t2c_v40_v1
ENDPOINT=http://192.168.1.133:8000/v1
BENCHMARK_GRAPH=tccop_graph_v6
V40_GRAPH=tccop_v40_demo
RESULTS_DIR=results
BENCH_OUT=$RESULTS_DIR/bench_v40_full.json
V40_OUT=$RESULTS_DIR/test_v40_natural_query.json

log() { echo -e "\033[1;34m[$(date +%H:%M:%S)]\033[0m $*"; }
err() { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; }

mkdir -p "$RESULTS_DIR"

# ──────────────────────────────────────────────
# 1. vLLM 도달 가능 확인
# ──────────────────────────────────────────────
log "1/5 학습 서버 vLLM 연결 확인..."
if ! curl -s -m 5 "$ENDPOINT/models" | grep -q "$MODEL"; then
    err "vLLM 응답 없음 또는 모델 '$MODEL' 미등록"
    err "학습 서버에서 다음 확인:"
    err "  curl -s http://localhost:8000/v1/models | python -m json.tool"
    exit 1
fi
log "  ✅ $MODEL 서빙 확인"

# ──────────────────────────────────────────────
# 2. .env SLLM_MODEL_NAME 갱신
# ──────────────────────────────────────────────
log "2/5 .env 갱신..."
if [[ ! -f .env ]]; then
    err ".env 없음. 현재 디렉토리: $(pwd)"
    exit 1
fi
OLD_MODEL=$(grep "^SLLM_MODEL_NAME=" .env | cut -d= -f2)
sed -i '' "s/^SLLM_MODEL_NAME=.*/SLLM_MODEL_NAME=$MODEL/" .env
NEW_MODEL=$(grep "^SLLM_MODEL_NAME=" .env | cut -d= -f2)
log "  $OLD_MODEL → $NEW_MODEL"

# ──────────────────────────────────────────────
# 3. 152문항 벤치마크
# ──────────────────────────────────────────────
log "3/5 152문항 벤치마크 시작 (~5분)..."
python3 benchmark_t2c_v2.py \
    --endpoint "$ENDPOINT" \
    --model "$MODEL" \
    --mode t2c_v37 \
    --graph "$BENCHMARK_GRAPH" \
    --output "$BENCH_OUT"

if [[ ! -f "$BENCH_OUT" ]]; then
    err "벤치마크 결과 파일 없음: $BENCH_OUT"
    exit 1
fi
log "  결과: $BENCH_OUT"

# ──────────────────────────────────────────────
# 4. V4.0 시나리오 45 케이스
# ──────────────────────────────────────────────
log "4/5 V4.0 시나리오 45 케이스 (~90초)..."
python3 scripts/test_v40_natural_query.py
log "  결과: $V40_OUT"

# ──────────────────────────────────────────────
# 5. 4세대 비교 보고서
# ──────────────────────────────────────────────
log "5/5 v37/v38/v39/v40 4세대 비교 보고서 생성..."

python3 << 'PY'
import json, os
from pathlib import Path

RESULTS = {
    'v37': 'results/bench_v37_full.json',
    'v38': 'results/bench_v38_full.json',
    'v39': 'results/bench_v39_full.json',
    'v40': 'results/bench_v40_full.json',
}

print()
print("="*72)
print("  v37 → v38 → v39 → v40  4세대 벤치마크 비교 (152문항)")
print("="*72)
print()
print(f"  {'카테고리':<26} {'v37':>8} {'v38':>8} {'v39':>8} {'v40':>8}  {'Δ(v40-v39)':>11}")
print(f"  {'-'*26} {'-'*8} {'-'*8} {'-'*8} {'-'*8}  {'-'*11}")

data = {}
for k, p in RESULTS.items():
    if os.path.exists(p):
        with open(p) as f:
            data[k] = json.load(f)
    else:
        data[k] = None

# 전체 통과율
def passed(d):
    if not d: return '-'
    p, t = d.get('passed'), d.get('total')
    if p is None: return '-'
    return f"{p}/{t}"

def pct(d):
    if not d or d.get('passed') is None: return None
    return 100 * d['passed'] / d['total']

print(f"  {'전체 통과':<26} {passed(data['v37']):>8} {passed(data['v38']):>8} "
      f"{passed(data['v39']):>8} {passed(data['v40']):>8}")
v37p, v38p, v39p, v40p = pct(data['v37']), pct(data['v38']), pct(data['v39']), pct(data['v40'])
def f(x): return f"{x:.1f}%" if x is not None else '-'
delta = (v40p - v39p) if (v40p is not None and v39p is not None) else None
print(f"  {'전체 %':<26} {f(v37p):>8} {f(v38p):>8} {f(v39p):>8} {f(v40p):>8}  "
      f"{(f'{delta:+.1f}p' if delta is not None else '-'):>11}")

# 카테고리별 (v40 기준)
if data['v40']:
    print()
    cats = (data['v40'].get('category_stats') or {})
    if cats:
        print("  ── 카테고리별 (v39 대비) ──")
        for cat in sorted(cats):
            v40_c = cats[cat]
            v39_cats = (data['v39'] or {}).get('category_stats', {})
            v39_c = v39_cats.get(cat, {})
            v40_pct = 100 * v40_c.get('pass', 0) / max(v40_c.get('total', 1), 1)
            v39_pct = 100 * v39_c.get('pass', 0) / max(v39_c.get('total', 1), 1) if v39_c else None
            delta_str = f"{v40_pct - v39_pct:+.1f}p" if v39_pct is not None else '-'
            print(f"    {cat:<24} v39={v39_pct:5.1f}% v40={v40_pct:5.1f}%  {delta_str}")

# V4.0 시나리오 45 케이스
print()
print("="*72)
print("  V4.0 시나리오 45 케이스 비교")
print("="*72)
v40_scen = json.load(open('results/test_v40_natural_query.json'))
print(f"  v40: {v40_scen['passed']}/{v40_scen['total']} ({100*v40_scen['passed']/v40_scen['total']:.1f}%)")
print("  카테고리별:")
for cat, st in sorted((v40_scen.get('category_stats') or {}).items()):
    p, t = st['pass'], st['total']
    avg = st['time_sum'] / t if t else 0
    print(f"    {cat:<10} {p}/{t}  ({100*p/t:5.1f}%)  평균 {avg:.0f}ms")

print()
print("="*72)
PY

log "🎉 벤치마크 + 비교 완료"
echo ""
echo "  결과 파일:"
echo "    - $BENCH_OUT"
echo "    - $V40_OUT"
echo ""
echo "  요약 결과를 보고서로 만들려면:"
echo "    python3 scripts/generate_v40_report.py"
