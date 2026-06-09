#!/bin/bash
# Text2Cypher v3.7-Qwen 학습 파일 서버 업로드 스크립트
# 사용법: bash train/upload_t2c_v37_qwen.sh <서버IP> [서버유저]
# 예시:   bash train/upload_t2c_v37_qwen.sh 192.168.1.133 ai-kyw-dev

set -e

SERVER_IP=${1:?"서버 IP를 입력하세요"}
SERVER_USER=${2:-ai-kyw-dev}
SERVER_DIR="/home/${SERVER_USER}/ccop_train"

LOCAL_ROOT="/Users/iankwon/test/coop_v1.0"

echo "=========================================="
echo " Text2Cypher v3.7-Qwen 학습 파일 업로드"
echo " 베이스:   Qwen/Qwen2.5-7B-Instruct"
echo " 온톨로지: v3.7 (25노드, 53엣지)"
echo " 데이터:   28,109 train / 3,117 eval (기존 재사용)"
echo " 대상:     ${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}"
echo "=========================================="

ssh "${SERVER_USER}@${SERVER_IP}" "mkdir -p ${SERVER_DIR}/train"

# Qwen yaml + 실행 스크립트만 전송 (데이터셋·dataset_info는 이미 서버에 있음)
echo ""
echo "[1/2] yaml 전송..."
scp "${LOCAL_ROOT}/train/train_t2c_lora_v3_qwen.yaml" \
    "${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}/train/"

echo "[2/2] 실행 스크립트 전송..."
scp "${LOCAL_ROOT}/train/run_t2c_train_v37_qwen.sh" \
    "${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}/train/"

echo ""
echo "✅ 업로드 완료!"
echo ""
echo "다음 단계 (서버에서 실행):"
echo "  ssh ${SERVER_USER}@${SERVER_IP}"
echo "  cd ${SERVER_DIR}/train"
echo "  bash run_t2c_train_v37_qwen.sh"
echo ""
echo "또는 tmux로 안전 백그라운드:"
echo "  tmux new-session -d -s qwen_train 'bash run_t2c_train_v37_qwen.sh'"
echo "  tmux attach -t qwen_train  # Ctrl+B,D로 빠져나오기"
