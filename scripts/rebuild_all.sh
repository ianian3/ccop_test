#!/usr/bin/env bash
# 통합 그래프 재생성 원커맨드 — 수동 4단계(빠뜨림 함정)를 하나로.
#   build_integrated → refine(dpstr·same_as) → analytics --set(지표 10종)
#   → V4.8 전수감사(위반 grep) → T2C 스모크(핵심 5문항)
# 사용: bash scripts/rebuild_all.sh [--skip-bench]
#   · EP 원본 재적재(ingest_*)는 포함하지 않음 — EP 그래프가 이미 있을 때의 통합 파이프라인.
#   · 앱 재시작 불필요: 알고리즘 export 캐시는 fingerprint로 자동 무효화됨.
set -euo pipefail
cd "$(dirname "$0")/.."
GRAPH="${GRAPH:-ccop_ep_integrated}"

echo "══ ① 통합 재생성 ($GRAPH) ══"
python3 scripts/build_integrated_graph.py | tail -2

echo "══ ② 정밀화 (dpstr·same_as) ══"
python3 scripts/refine_integrated_graph.py 2>/dev/null | grep -E "정밀화|same_as 후보"

echo "══ ③ 분석 지표 재계산 (--set) ══"
python3 scripts/graph_analytics.py --graph "$GRAPH" --set 2>/dev/null | grep -E "인물중심 서브그래프|SET 완료"

echo "══ ④ V4.8 전수감사 ══"
python3 scripts/audit_ep_v48.py 2>/dev/null | grep -E "정경 외|위반|deprecated 사용" \
  && { echo "❌ 감사 위반 발견 — 위 항목 확인"; exit 1; } \
  || echo "✅ 위반 0 (전 그래프)"

if [[ "${1:-}" != "--skip-bench" ]]; then
  echo "══ ⑤ T2C 스모크 (핵심 5문항 — 앱 5002 필요) ══"
  if curl -s -m 3 -o /dev/null http://localhost:5002/; then
    python3 scripts/bench_integrated_t2c.py A01 B02 G01 F03 C01 | tail -3
  else
    echo "⚠️ 앱 미기동 — 스모크 생략 (python3 run.py 후 재실행)"
  fi
fi
echo "══ 완료 ══"
