#!/bin/bash
# Text2Cypher v1 LoRA 학습 실행 스크립트 (서버용)
# 실행: bash run_t2c_train.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRAIN_DIR="${SCRIPT_DIR}"
OUTPUT_DIR="${TRAIN_DIR}/output/exaone_t2c_v1"
LOG_FILE="${TRAIN_DIR}/t2c_train_$(date +%Y%m%d_%H%M%S).log"

echo "=========================================="
echo " EXAONE-3.5-7.8B Text2Cypher LoRA 학습"
echo " 시작: $(date)"
echo " 설정: ${TRAIN_DIR}/train_t2c_lora.yaml"
echo " 로그: ${LOG_FILE}"
echo "=========================================="

# 가상환경 활성화 (경로 맞게 수정)
if [ -f ~/llama_env/bin/activate ]; then
    source ~/llama_env/bin/activate
    echo "가상환경: ~/llama_env"
elif [ -f ~/miniconda3/etc/profile.d/conda.sh ]; then
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate llama_factory
    echo "conda 환경: llama_factory"
fi

# GPU 상태 확인
echo ""
echo "[GPU 상태]"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
echo ""

# LLaMA-Factory 설치 확인
if ! command -v llamafactory-cli &> /dev/null; then
    echo "❌ llamafactory-cli를 찾을 수 없습니다."
    echo "   pip install llamafactory 또는 conda activate llama_factory"
    exit 1
fi

echo "[학습 시작] llamafactory-cli train train_t2c_lora.yaml"
echo ""

# 학습 실행 (백그라운드 + 로그 저장)
cd "${TRAIN_DIR}"

llamafactory-cli train train_t2c_lora.yaml 2>&1 | tee "${LOG_FILE}"

TRAIN_EXIT=$?

if [ $TRAIN_EXIT -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo " ✅ 학습 완료: $(date)"
    echo " 출력 경로: ${OUTPUT_DIR}"
    echo ""
    echo " 다음 단계:"
    echo "   # LoRA 병합"
    echo "   python scripts/merge_lora.py \\"
    echo "     --base LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct \\"
    echo "     --lora ${OUTPUT_DIR} \\"
    echo "     --output models/exaone_t2c_v1_merged"
    echo ""
    echo "   # vLLM 서빙"
    echo "   vllm serve models/exaone_t2c_v1_merged \\"
    echo "     --host 0.0.0.0 --port 8000 \\"
    echo "     --trust-remote-code"
    echo "=========================================="
else
    echo ""
    echo "❌ 학습 실패 (exit code: ${TRAIN_EXIT})"
    echo "   로그 확인: ${LOG_FILE}"
    exit $TRAIN_EXIT
fi
