#!/bin/bash
# v3.7-Qwen-v2 (messages format) 학습 파일 업로드
# 사용법: bash train/upload_t2c_v37_qwen_v2.sh <서버IP> [서버유저]

set -e

SERVER_IP=${1:?"서버 IP 필요"}
SERVER_USER=${2:-ai-kyw-dev}
SERVER_DIR="/home/${SERVER_USER}/ccop_train"
LOCAL_ROOT="/Users/iankwon/test/coop_v1.0"

echo "=========================================="
echo " Qwen2.5-7B v37-v2 (messages format) 업로드"
echo " 대상: ${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}"
echo "=========================================="

ssh "${SERVER_USER}@${SERVER_IP}" "mkdir -p ${SERVER_DIR}/train"

echo ""
echo "[1/3] 데이터셋 (messages format) 전송..."
scp "${LOCAL_ROOT}/train/t2c_v37_train_msg.json" \
    "${LOCAL_ROOT}/train/t2c_v37_eval_msg.json" \
    "${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}/train/"

echo "[2/3] dataset_info.json 전송 (v37_msg 항목 추가됨)..."
scp "${LOCAL_ROOT}/train/dataset_info.json" \
    "${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}/train/"

echo "[3/3] yaml 전송..."
scp "${LOCAL_ROOT}/train/train_t2c_lora_v3_qwen_v2.yaml" \
    "${SERVER_USER}@${SERVER_IP}:${SERVER_DIR}/train/"

echo ""
echo "✅ 업로드 완료!"
echo ""
echo "서버에서 실행:"
echo "  ssh ${SERVER_USER}@${SERVER_IP}"
echo "  cd ${SERVER_DIR}/train"
echo "  source ~/llama_env/bin/activate"
echo "  # 기존 vLLM 종료 (GPU 회수)"
echo "  pkill -f 'vllm serve'"
echo "  sleep 5"
echo "  # nohup 백그라운드 학습"
echo "  nohup llamafactory-cli train train_t2c_lora_v3_qwen_v2.yaml \\"
echo "    > t2c_train_v37_qwen_v2_\$(date +%Y%m%d_%H%M%S).log 2>&1 &"
echo "  disown"
echo ""
echo "  # 진행 확인"
echo "  tail -f \$(ls -t t2c_train_v37_qwen_v2_*.log | head -1)"
