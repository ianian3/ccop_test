#!/bin/bash
# 로컬 → 서버 파일 전송 스크립트
# 사용법: bash upload_to_server.sh [서버IP] [서버유저명]
# 예시:   bash upload_to_server.sh 192.168.1.100 ubuntu

set -e

SERVER_IP=${1:?"서버 IP를 입력하세요. 예: bash upload_to_server.sh 192.168.1.100 ubuntu"}
SERVER_USER=${2:-ubuntu}
SERVER_DIR="~/ccop_train"

LOCAL_DATA_DIR="/Users/iankwon/test/coop_v1.0/data"
LOCAL_TRAIN_DIR="/Users/iankwon/test/coop_v1.0/train"

echo "=========================================="
echo " 서버로 파일 전송"
echo " 대상: ${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}"
echo "=========================================="

# 서버에 디렉토리 생성
ssh "${SERVER_USER}@${SERVER_IP}" "mkdir -p ${SERVER_DIR}/data ${SERVER_DIR}/train"

# 데이터셋 전송 (가장 큰 파일)
echo "[1/2] 데이터셋 전송 중... (korean_cybercrime_sft.json)"
scp "${LOCAL_DATA_DIR}/korean_cybercrime_sft.json" \
    "${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}/data/"

# 학습 설정 파일 전송
echo "[2/2] 학습 설정 파일 전송 중..."
scp "${LOCAL_TRAIN_DIR}/dataset_info.json" \
    "${LOCAL_TRAIN_DIR}/train_exaone_lora.yaml" \
    "${LOCAL_TRAIN_DIR}/train_exaone_full.yaml" \
    "${LOCAL_TRAIN_DIR}/server_setup.sh" \
    "${LOCAL_TRAIN_DIR}/run_train.sh" \
    "${LOCAL_TRAIN_DIR}/test_inference.py" \
    "${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}/train/"

echo ""
echo "✅ 전송 완료!"
echo ""
echo "다음 단계 (서버에서 실행):"
echo "  ssh ${SERVER_USER}@${SERVER_IP}"
echo "  cd ${SERVER_DIR}/train"
echo "  bash server_setup.sh          # 최초 1회만"
echo "  source ~/llama_env/bin/activate"
echo "  bash run_train.sh lora        # 학습 시작"
