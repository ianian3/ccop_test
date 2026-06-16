#!/usr/bin/env bash
# ===================================================================
# CCOP 운영 배포 헬퍼 (skai2_vm 에서 실행)
#   사용: bash scripts/deploy.sh
#   동작: origin/dev 최신화 → app 재빌드·재기동 → 헬스체크 → 실패 시 자동 롤백
#   * app 은 Dockerfile 로 빌드되므로 --build 필수. DB/nginx 컨테이너는 유지.
# ===================================================================
set -euo pipefail

cd "$(dirname "$0")/.."   # 리포 루트로 이동
COMPOSE="docker compose -f docker-compose.cslee.yml"
HEALTH_URL="https://localhost/api/v1/health"

echo "==================================================="
echo " CCOP 배포 시작  $(date '+%F %T')"
echo "==================================================="

PREV=$(git rev-parse HEAD)
echo "[1/4] 현재 커밋(롤백 지점): ${PREV:0:7}"

echo "[2/4] 코드 최신화 (origin/dev, fast-forward only)"
git pull --ff-only origin dev

NEW=$(git rev-parse HEAD)
if [ "$PREV" = "$NEW" ]; then
  echo "      변경 없음 (${NEW:0:7}) — 재빌드만 수행"
else
  echo "      ${PREV:0:7} → ${NEW:0:7}"
fi

echo "[3/4] app 재빌드·재기동"
$COMPOSE up -d --build app

echo "[4/4] 헬스체크 (최대 60초)"
ok=0
for i in $(seq 1 12); do
  code=$(curl -sk -o /dev/null -w '%{http_code}' "$HEALTH_URL" 2>/dev/null || echo 000)
  if [ "$code" = "200" ]; then echo "      ✅ healthy (${i}회차)"; ok=1; break; fi
  echo "      ⏳ 대기 ${i}/12 (HTTP $code)"; sleep 5
done

if [ "$ok" != "1" ]; then
  echo "      ❌ 헬스체크 실패 → ${PREV:0:7} 로 롤백"
  git reset --hard "$PREV"
  $COMPOSE up -d --build app
  echo "      ↩ 롤백 완료. 배포 중단."
  exit 1
fi

echo "==================================================="
echo " ✅ 배포 성공: ${NEW:0:7}"
echo "    릴리스 태그(개발 머신에서) 권장:"
echo "      git tag -a prod-$(date +%Y%m%d) ${NEW} -m '운영 배포'"
echo "      git push origin prod-$(date +%Y%m%d)"
echo "==================================================="
