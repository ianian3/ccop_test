#!/bin/bash
# Text2Cypher v3.7 LoRA 학습 실행 스크립트 (서버용)
# 실행: bash run_t2c_train_v37.sh
#
# 사양:
#   - 모델:     EXAONE-3.5-7.8B-Instruct + QLoRA 4bit
#   - 데이터:   t2c_v37 (28,109 train / 3,117 eval)
#   - 온톨로지: v3.7 (25노드, 53엣지)
#   - 예상시간: RTX 5090 32GB 기준 14-20시간

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRAIN_DIR="${SCRIPT_DIR}"
YAML_FILE="${TRAIN_DIR}/train_t2c_lora_v3.yaml"
OUTPUT_DIR="${TRAIN_DIR}/output/exaone_t2c_v37"
LOG_FILE="${TRAIN_DIR}/t2c_train_v37_$(date +%Y%m%d_%H%M%S).log"

echo "=========================================="
echo " EXAONE-3.5-7.8B Text2Cypher v3.7 LoRA 학습"
echo " 시작:   $(date)"
echo " 설정:   ${YAML_FILE}"
echo " 출력:   ${OUTPUT_DIR}"
echo " 로그:   ${LOG_FILE}"
echo "=========================================="

# 입력 파일 존재 확인
for f in "${YAML_FILE}" "${TRAIN_DIR}/t2c_v37_train.json" "${TRAIN_DIR}/t2c_v37_eval.json" "${TRAIN_DIR}/dataset_info.json"; do
    if [ ! -f "$f" ]; then
        echo "❌ 필수 파일 누락: $f"
        exit 1
    fi
done

TRAIN_CNT=$(python3 -c "import json; print(len(json.load(open('${TRAIN_DIR}/t2c_v37_train.json'))))")
EVAL_CNT=$(python3 -c "import json; print(len(json.load(open('${TRAIN_DIR}/t2c_v37_eval.json'))))")
echo "[데이터 확인] train=${TRAIN_CNT}개, eval=${EVAL_CNT}개"
echo ""

# 가상환경 활성화
if [ -f ~/llama_env/bin/activate ]; then
    source ~/llama_env/bin/activate
    echo "[환경] venv: ~/llama_env"
elif [ -f ~/miniconda3/etc/profile.d/conda.sh ]; then
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate llama_factory
    echo "[환경] conda: llama_factory"
fi

# GPU 상태
echo ""
echo "[GPU 상태]"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
echo ""

# LLaMA-Factory 확인
if ! command -v llamafactory-cli &> /dev/null; then
    echo "❌ llamafactory-cli를 찾을 수 없습니다."
    echo "   pip install llamafactory 또는 conda activate llama_factory"
    exit 1
fi

# yaml의 dataset_dir 경로가 현 서버 환경과 일치하는지 점검
EXPECTED_DIR=$(grep -E "^dataset_dir:" "${YAML_FILE}" | awk '{print $2}')
if [ "${EXPECTED_DIR}" != "${TRAIN_DIR}" ]; then
    echo "⚠️  yaml의 dataset_dir(${EXPECTED_DIR})가 현 디렉터리(${TRAIN_DIR})와 다릅니다."
    echo "   계속 진행하려면 yaml의 dataset_dir를 수정하거나 디렉토리 구조를 맞춰주세요."
fi

echo "[학습 시작] llamafactory-cli train train_t2c_lora_v3.yaml"
echo ""

cd "${TRAIN_DIR}"
llamafactory-cli train train_t2c_lora_v3.yaml 2>&1 | tee "${LOG_FILE}"
TRAIN_EXIT=${PIPESTATUS[0]}

if [ "${TRAIN_EXIT}" -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo " ✅ 학습 완료: $(date)"
    echo " 출력 경로: ${OUTPUT_DIR}"
    echo ""
    echo " 다음 단계:"
    echo "   # 1) LoRA 병합"
    echo "   python ${TRAIN_DIR}/merge_lora.py \\"
    echo "     --base LGAI-EXAONE/EXAONE-3.5-7.8B-Instruct \\"
    echo "     --adapter ${OUTPUT_DIR} \\"
    echo "     --output ${TRAIN_DIR}/output/exaone_t2c_v37_merged"
    echo ""
    echo "   # 2) vLLM 서빙"
    echo "   vllm serve ${TRAIN_DIR}/output/exaone_t2c_v37_merged \\"
    echo "     --host 0.0.0.0 --port 8000 --trust-remote-code"
    echo "=========================================="
else
    echo ""
    echo "❌ 학습 실패 (exit code: ${TRAIN_EXIT})"
    echo "   로그 확인: ${LOG_FILE}"
    exit "${TRAIN_EXIT}"
fi
