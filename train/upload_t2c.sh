#!/bin/bash
# Text2Cypher v1 학습 파일 서버 업로드 스크립트
# 사용법: bash train/upload_t2c.sh [서버IP] [서버유저명]
# 예시:   bash train/upload_t2c.sh 192.168.1.100 ai-kyw-dev

set -e

SERVER_IP=${1:?"서버 IP를 입력하세요. 예: bash train/upload_t2c.sh 192.168.1.100 ai-kyw-dev"}
SERVER_USER=${2:-ai-kyw-dev}
SERVER_DIR="/home/${SERVER_USER}/ccop_train"

LOCAL_ROOT="/Users/iankwon/test/coop_v1.0"

echo "=========================================="
echo " Text2Cypher v1 학습 파일 업로드"
echo " 대상: ${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}"
echo "=========================================="

# 서버 디렉토리 생성
ssh "${SERVER_USER}@${SERVER_IP}" "mkdir -p ${SERVER_DIR}/data ${SERVER_DIR}/train"

# 데이터 파일 전송
echo "[1/3] 학습 데이터 전송 중..."
scp "${LOCAL_ROOT}/data/t2c_v1_train.json" \
    "${LOCAL_ROOT}/data/t2c_v1_eval.json" \
    "${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}/data/"

# 학습 설정 전송
echo "[2/3] 학습 설정 파일 전송 중..."
scp "${LOCAL_ROOT}/train/train_t2c_lora.yaml" \
    "${LOCAL_ROOT}/train/dataset_info.json" \
    "${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}/train/"

# 런스크립트 전송
echo "[3/3] 실행 스크립트 전송 중..."
scp "${LOCAL_ROOT}/train/run_t2c_train.sh" \
    "${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}/train/"

echo ""
echo "✅ 업로드 완료!"
echo ""
echo "다음 단계 (서버에서 실행):"
echo "  ssh ${SERVER_USER}@${SERVER_IP}"
echo "  cd ${SERVER_DIR}/train"
echo "  bash run_t2c_train.sh"
