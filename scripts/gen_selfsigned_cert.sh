#!/usr/bin/env bash
# ============================================================
# CCOP v1.0 — 폐쇄망 nginx 용 자체서명 인증서 생성
#   nginx.cslee.conf 가 참조하는 파일명(cert.pem / key.pem)에 맞춰 deploy/ssl/ 에 생성한다.
#   외부 CA·Let's Encrypt 불가한 폐쇄망 전용. staging 에서 생성해 번들에 포함하거나 현장 생성.
#
#   사용:  bash scripts/gen_selfsigned_cert.sh [CN] [유효일수]
#   예:    bash scripts/gen_selfsigned_cert.sh ccop.cslee.internal 3650
# ============================================================
set -euo pipefail

CN="${1:-ccop.cslee.internal}"      # 인증서 CN — nginx server_name 과 일치 권장
DAYS="${2:-3650}"
SSL_DIR="$(cd "$(dirname "$0")/.." && pwd)/deploy/ssl"

mkdir -p "$SSL_DIR"

openssl req -x509 -nodes -days "$DAYS" -newkey rsa:2048 \
  -keyout "$SSL_DIR/key.pem" \
  -out    "$SSL_DIR/cert.pem" \
  -subj   "/CN=${CN}" \
  -addext "subjectAltName=DNS:${CN},DNS:localhost,IP:127.0.0.1"

chmod 600 "$SSL_DIR/key.pem"
chmod 644 "$SSL_DIR/cert.pem"

echo "✔ 자체서명 인증서 생성 완료"
echo "  - $SSL_DIR/cert.pem"
echo "  - $SSL_DIR/key.pem"
echo "  CN=${CN}, 유효기간 ${DAYS}일"
echo "  (nginx.cslee.conf 의 ssl_certificate=/etc/nginx/ssl/cert.pem 와 일치)"
