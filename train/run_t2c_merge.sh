#!/bin/bash
# Text2Cypher v1 LoRA 병합 + vLLM 서빙 스크립트 (서버용)
# 실행: bash run_t2c_merge.sh

set -e

BASE_DIR="/home/ai-kyw-dev/ccop_train"
LORA_PATH="${BASE_DIR}/train/output/exaone_t2c_v1"
MERGED_DIR="${BASE_DIR}/models/exaone_t2c_v1_merged"
BASE_MODEL="LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct"

echo "=========================================="
echo " Text2Cypher v1 LoRA 병합"
echo " LoRA:   ${LORA_PATH}"
echo " 출력:   ${MERGED_DIR}"
echo "=========================================="

# 가상환경 활성화
if [ -f ~/llama_env/bin/activate ]; then
    source ~/llama_env/bin/activate
elif [ -f ~/miniconda3/etc/profile.d/conda.sh ]; then
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate llama_factory
fi

# LoRA 어댑터 존재 확인
if [ ! -d "${LORA_PATH}" ]; then
    echo "❌ LoRA 경로 없음: ${LORA_PATH}"
    exit 1
fi

echo "[방법 1] LLaMA-Factory export 시도..."
if command -v llamafactory-cli &> /dev/null; then
    llamafactory-cli export \
        --model_name_or_path "${BASE_MODEL}" \
        --adapter_name_or_path "${LORA_PATH}" \
        --template exaone \
        --finetuning_type lora \
        --export_dir "${MERGED_DIR}" \
        --trust_remote_code true \
        --export_legacy_format false

    echo ""
    echo "✅ 병합 완료: ${MERGED_DIR}"
else
    echo "[방법 2] merge_lora.py 사용..."
    mkdir -p "${BASE_DIR}/models"
    python "${BASE_DIR}/scripts/merge_lora.py" \
        --base_model "${BASE_MODEL}" \
        --lora_path "${LORA_PATH}" \
        --output_dir "${MERGED_DIR}"
fi

echo ""
echo "=========================================="
echo " 병합 완료. 다음 단계: vLLM 서빙"
echo "=========================================="
echo ""
echo " tmux new -s vllm_serve"
echo " vllm serve ${MERGED_DIR} \\"
echo "   --host 0.0.0.0 --port 8000 \\"
echo "   --trust-remote-code \\"
echo "   --max-model-len 2048 \\"
echo "   --gpu-memory-utilization 0.85"
echo ""
echo " # CCOP .env 설정:"
echo " SLLM_ENDPOINT=http://192.168.1.133:8000/v1"
echo " SLLM_MODEL_NAME=exaone_t2c_v1_merged"
