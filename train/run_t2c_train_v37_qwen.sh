#!/bin/bash
# Text2Cypher v3.7-Qwen LoRA 학습 실행 스크립트 (서버용)
# 실행: bash run_t2c_train_v37_qwen.sh
#
# 사양:
#   - 모델:     Qwen/Qwen2.5-7B-Instruct + QLoRA 4bit
#   - 데이터:   t2c_v37 (28,109 train / 3,117 eval, EXAONE 학습과 동일)
#   - 온톨로지: v3.7 (25노드, 53엣지)
#   - 예상시간: RTX 5090 32GB 기준 약 1.5시간

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRAIN_DIR="${SCRIPT_DIR}"
YAML_FILE="${TRAIN_DIR}/train_t2c_lora_v3_qwen.yaml"
OUTPUT_DIR="${TRAIN_DIR}/output/qwen25_t2c_v37"
LOG_FILE="${TRAIN_DIR}/t2c_train_v37_qwen_$(date +%Y%m%d_%H%M%S).log"

echo "=========================================="
echo " Qwen2.5-7B Text2Cypher v3.7 LoRA 학습"
echo " 시작:   $(date)"
echo " 설정:   ${YAML_FILE}"
echo " 출력:   ${OUTPUT_DIR}"
echo " 로그:   ${LOG_FILE}"
echo "=========================================="

# 입력 파일 확인
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

# 가상환경 활성화 (학습은 기존 llama_env 사용)
if [ -f ~/llama_env/bin/activate ]; then
    source ~/llama_env/bin/activate
    echo "[환경] venv: ~/llama_env"
elif [ -f ~/miniconda3/etc/profile.d/conda.sh ]; then
    source ~/miniconda3/etc/profile.d/conda.sh
    conda activate llama_factory
    echo "[환경] conda: llama_factory"
fi

# GPU 메모리 점검 (Ollama 등 사전 점유 확인)
echo ""
echo "[GPU 상태]"
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader
echo ""

GPU_FREE_MIB=$(nvidia-smi --query-gpu=memory.free --format=csv,noheader,nounits | head -1)
if [ "$GPU_FREE_MIB" -lt 25000 ]; then
    echo "⚠️  GPU free memory ${GPU_FREE_MIB} MiB — 25 GiB 이상 필요"
    echo "    Ollama 등 다른 프로세스 종료 후 재시도하세요:"
    echo "    for m in \$(ollama ps 2>/dev/null | tail -n +2 | awk '{print \$1}'); do ollama stop \"\$m\"; done"
    exit 1
fi

if ! command -v llamafactory-cli &> /dev/null; then
    echo "❌ llamafactory-cli를 찾을 수 없습니다."
    exit 1
fi

echo "[학습 시작] llamafactory-cli train train_t2c_lora_v3_qwen.yaml"
echo ""

cd "${TRAIN_DIR}"
llamafactory-cli train train_t2c_lora_v3_qwen.yaml 2>&1 | tee "${LOG_FILE}"
TRAIN_EXIT=${PIPESTATUS[0]}

if [ "${TRAIN_EXIT}" -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo " ✅ 학습 완료: $(date)"
    echo " 출력 경로: ${OUTPUT_DIR}"
    echo ""
    echo " 다음 단계:"
    echo "   # 1) LoRA 병합"
    echo "   python /home/ai-kyw-dev/ccop_training/merge_lora.py \\"
    echo "     --base_model Qwen/Qwen2.5-7B-Instruct \\"
    echo "     --lora_path ${OUTPUT_DIR} \\"
    echo "     --output_dir ${TRAIN_DIR}/output/qwen25_t2c_v37_merged"
    echo ""
    echo "   # 2) vLLM 서빙 (Qwen2.5는 trust_remote_code 불필요)"
    echo "   tmux new-session -d -s vllm_qwen \\"
    echo "     \"vllm serve ${TRAIN_DIR}/output/qwen25_t2c_v37_merged \\"
    echo "        --host 0.0.0.0 --port 8000 \\"
    echo "        --served-model-name qwen25_t2c_v37 \\"
    echo "        --max-model-len 4096 \\"
    echo "        --gpu-memory-utilization 0.85\""
    echo "=========================================="
else
    echo ""
    echo "❌ 학습 실패 (exit code: ${TRAIN_EXIT})"
    echo "   로그 확인: ${LOG_FILE}"
    exit "${TRAIN_EXIT}"
fi
