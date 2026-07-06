#!/usr/bin/env bash
# ============================================================
# CCOP v1.0 — 폐쇄망 1차(인프라) 번들 빌더
#
#   인터넷 되는 x86-64 staging(Rocky 10 권장)에서 실행하여,
#   USB 반입용 1차 번들(ccop_bundle_p1)을 자동 생성한다.
#   런북 docs/AIRGAP_VISIT_INSTALL_RUNBOOK.md §2 를 자동화.
#
#   사용 예:
#     PGPASSWORD='<db비번>' bash scripts/build_airgap_bundle.sh \
#       --db-host 49.50.128.28 --db-port 5333 --db-user ccop --db-name tccopdb
#
#   옵션:
#     --out DIR      번들 출력 경로 (기본 ~/ccop_bundle_p1)
#     --cn NAME      인증서 CN (기본 ccop.cslee.internal)
#     --db-host/-port/-user/-name   원격 DB 접속 (덤프 대상)
#     --app-tag TAG  앱 이미지 태그 (기본 ccop_app:1.0)
#     --skip-db      DB 덤프 생략 (덤프를 별도 반입할 때)
#     --skip-rpm     docker-ce rpm 수집 생략 (Rocky staging 아닐 때)
#
#   ⚠️ staging 은 반드시 linux/amd64. arm64(예: Apple Silicon)에서 만든
#      이미지는 폐쇄망 x86 VM 에서 실행되지 않는다.
# ============================================================
set -euo pipefail

OUT="${HOME}/ccop_bundle_p1"
CN="ccop.cslee.internal"
DB_HOST="49.50.128.28"; DB_PORT="5333"; DB_USER="ccop"; DB_NAME="tccopdb"
APP_TAG="ccop_app:1.0"
SKIP_DB=0; SKIP_RPM=0

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

while [ $# -gt 0 ]; do
  case "$1" in
    --out)      OUT="$2"; shift 2;;
    --cn)       CN="$2"; shift 2;;
    --db-host)  DB_HOST="$2"; shift 2;;
    --db-port)  DB_PORT="$2"; shift 2;;
    --db-user)  DB_USER="$2"; shift 2;;
    --db-name)  DB_NAME="$2"; shift 2;;
    --app-tag)  APP_TAG="$2"; shift 2;;
    --skip-db)  SKIP_DB=1; shift;;
    --skip-rpm) SKIP_RPM=1; shift;;
    -h|--help)  grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
    *) echo "알 수 없는 옵션: $1 (--help 참고)"; exit 1;;
  esac
done

log(){ printf "\n\033[1;36m[bundle]\033[0m %s\n" "$*"; }
warn(){ printf "\033[1;33m⚠️  %s\033[0m\n" "$*"; }
die(){ printf "\033[1;31m[에러]\033[0m %s\n" "$*" >&2; exit 1; }

# ── 0. 사전 점검 ──
log "사전 점검"
command -v docker >/dev/null || die "docker 없음 — 인터넷 되는 staging 에서 실행하세요."
[ -f "$ROOT/Dockerfile" ] || die "Dockerfile 없음 — 저장소 루트가 맞는지 확인."
[ -f "$ROOT/docker-compose.airgap.yml" ] || die "docker-compose.airgap.yml 없음."
[ -f "$ROOT/scripts/gen_selfsigned_cert.sh" ] || die "gen_selfsigned_cert.sh 없음."
ARCH="$(uname -m)"
[ "$ARCH" = "x86_64" ] || warn "아키텍처=$ARCH — 폐쇄망 VM은 x86_64. arm64 빌드 이미지는 실행 불가!"

mkdir -p "$OUT"/{images,rpms,db,src}

# ── 1. 앱 이미지 빌드 + save ──
log "앱 이미지 빌드: $APP_TAG (linux/amd64)"
DF="$ROOT/Dockerfile"
[ -f "$ROOT/Dockerfile.airgap" ] && { DF="$ROOT/Dockerfile.airgap"; log "  → 슬림 Dockerfile.airgap 사용 (RAG/torch 제외)"; }
docker build --platform linux/amd64 -t "$APP_TAG" -f "$DF" "$ROOT"
docker save "$APP_TAG" -o "$OUT/images/ccop_app_1.0.tar"

# ── 2. 베이스 이미지 pull + save ──
log "베이스 이미지 pull + save (agensgraph, nginx)"
docker pull bitnine/agensgraph:v2.13.2
docker pull nginx:alpine
docker save bitnine/agensgraph:v2.13.2 -o "$OUT/images/agensgraph_2.13.2.tar"
docker save nginx:alpine              -o "$OUT/images/nginx_alpine.tar"

# ── 3. Docker CE el10 오프라인 rpm ──
if [ "$SKIP_RPM" = "0" ]; then
  if command -v dnf >/dev/null; then
    log "Docker CE el10 rpm 수집 (호스트 dnf)"
    dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo 2>/dev/null || true
    dnf download --resolve --alldeps --destdir="$OUT/rpms" \
        docker-ce docker-ce-cli containerd.io docker-compose-plugin \
      || warn "rpm 수집 실패"
  else
    log "dnf 없음(예: Ubuntu staging) → Rocky10 컨테이너로 el10 rpm 수집"
    docker run --rm --platform linux/amd64 -v "$OUT/rpms":/rpms quay.io/rockylinux/rockylinux:10 bash -c '
      dnf install -y dnf-plugins-core >/dev/null 2>&1
      dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo >/dev/null 2>&1
      dnf download --resolve --alldeps --destdir=/rpms docker-ce docker-ce-cli containerd.io docker-compose-plugin
    ' || warn "Rocky10 컨테이너 rpm 수집 실패 — 네트워크/quay.io 이미지 확인"
  fi
else
  log "rpm 수집 생략(--skip-rpm)"
fi

# ── 4. DB 덤프 ──
if [ "$SKIP_DB" = "0" ]; then
  log "DB 덤프: $DB_HOST:$DB_PORT/$DB_NAME"
  [ -n "${PGPASSWORD:-}" ] || warn "PGPASSWORD 미설정 — 덤프 인증 실패 가능"
  if command -v pg_dump >/dev/null; then
    pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F c -f "$OUT/db/tccopdb.dump"
  else
    log "pg_dump 없음 → postgres 컨테이너로 덤프"
    docker run --rm --platform linux/amd64 -e PGPASSWORD="${PGPASSWORD:-}" -v "$OUT/db":/db postgres:16 \
      pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F c -f /db/tccopdb.dump
  fi
  gzip -f "$OUT/db/tccopdb.dump"
  warn "테스트엔 tccop_graph_v6 만 필요. osint_ontology(6.89M) 포함 시 덤프 대용량."
  warn "pg_dump 버전 < 서버(AgensGraph)면 실패 가능 — 실패 시 서버 호환 버전으로."
else
  log "DB 덤프 생략(--skip-db) — db/tccopdb.dump.gz 를 수동 반입하세요."
fi

# ── 5. 자체서명 인증서 + 소스 tar (작업트리 그대로: airgap 자산·인증서 포함) ──
log "자체서명 인증서 생성 (deploy/ssl/cert.pem,key.pem)"
bash "$ROOT/scripts/gen_selfsigned_cert.sh" "$CN" 3650

log "소스 tar 생성 (git 미커밋 파일 포함 위해 작업트리 아카이브)"
#   ⚠️ 실 .env(원격DB 비번/OpenAI 키)는 제외 — 폐쇄망은 .env.airgap.phase1.template 사용
tar czf "$OUT/src/ccop_test.tar.gz" -C "$ROOT" \
    --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
    --exclude='*.log' --exclude='chroma_data' --exclude='.pytest_cache' \
    --exclude='.env' --exclude='ccop_bundle_p1' .

# ── 6. 체크섬 ──
log "SHA256SUMS 생성"
( cd "$OUT" && find . -type f ! -name SHA256SUMS -exec sha256sum {} \; > SHA256SUMS )

# ── 7. 요약 ──
log "완료 — 번들: $OUT"
du -sh "$OUT" 2>/dev/null || true
printf "  이미지 %s개 / rpm %s개 / DB덤프 %s\n" \
  "$(ls "$OUT/images" 2>/dev/null | wc -l | tr -d ' ')" \
  "$(ls "$OUT/rpms"  2>/dev/null | wc -l | tr -d ' ')" \
  "$([ -f "$OUT/db/tccopdb.dump.gz" ] && echo 있음 || echo 없음)"
echo "  다음: exFAT USB로 복사 → 반입 → 폐쇄망에서 'sha256sum -c SHA256SUMS' → 런북 §4"
