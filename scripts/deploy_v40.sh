#!/usr/bin/env bash
# ============================================================
# v40 학습 완료 후 머지 → vLLM 서빙 자동화 (학습 서버용)
# ============================================================
# 사용법:  bash deploy_v40.sh
# 위치:    학습 서버 ~/ccop_train/ 또는 ~/ 어디든
# 환경:    이 스크립트가 자동으로 llm_env 활성화
# ============================================================
set -euo pipefail

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
TRAIN_OUTPUT="/home/ai-kyw-dev/ccop_train/train/output/qwen25_t2c_v40_v1"
MERGED_DIR="${TRAIN_OUTPUT}_merged"
MODEL_NAME="qwen25_t2c_v40_v1"
VLLM_PORT=8000
VLLM_LOG="/tmp/vllm_v40.log"
LLM_ENV="$HOME/llm_env"
MERGE_SCRIPT="$HOME/ccop_training/merge_lora.py"
BASE_MODEL="Qwen/Qwen2.5-7B-Instruct"

log() { echo -e "\033[1;34m[$(date +%H:%M:%S)]\033[0m $*"; }
err() { echo -e "\033[1;31m[ERROR]\033[0m $*" >&2; }

# ──────────────────────────────────────────────
# 1. 학습 완료 검증
# ──────────────────────────────────────────────
log "1/5 학습 결과 검증..."
if [[ ! -d "$TRAIN_OUTPUT" ]]; then
    err "학습 출력 없음: $TRAIN_OUTPUT"
    exit 1
fi
if [[ ! -f "$TRAIN_OUTPUT/adapter_config.json" ]]; then
    err "어댑터 미완료: $TRAIN_OUTPUT/adapter_config.json"
    exit 1
fi

# train metrics 확인
if [[ -f /tmp/train_v40.log ]]; then
    log "최종 train metrics:"
    grep -E "train_loss|eval_loss|train_runtime" /tmp/train_v40.log | tail -8 | sed 's/^/    /'
fi

# ──────────────────────────────────────────────
# 2. llm_env 활성화
# ──────────────────────────────────────────────
log "2/5 llm_env 활성화..."
if [[ ! -f "$LLM_ENV/bin/activate" ]]; then
    err "llm_env 없음: $LLM_ENV"
    exit 1
fi
source "$LLM_ENV/bin/activate"
log "  python: $(which python)"
log "  torch:  $(python -c 'import torch; print(torch.__version__)' 2>/dev/null || echo 'X')"

# ──────────────────────────────────────────────
# 3. LoRA 머지
# ──────────────────────────────────────────────
log "3/5 LoRA 머지..."
if [[ -d "$MERGED_DIR" && -f "$MERGED_DIR/config.json" ]]; then
    log "  머지 산출물 이미 존재 — 스킵 ($MERGED_DIR)"
else
    cd ~/ccop_training
    python "$MERGE_SCRIPT" \
        --base_model "$BASE_MODEL" \
        --lora_path "$TRAIN_OUTPUT" \
        --output_dir "$MERGED_DIR"
    log "  완료: $MERGED_DIR"
fi

du -sh "$MERGED_DIR" | sed 's/^/    /'

# ──────────────────────────────────────────────
# 4. 기존 vLLM 종료 + 새로 서빙
# ──────────────────────────────────────────────
log "4/5 기존 vLLM 종료..."
pkill -f vllm 2>/dev/null || true
sleep 5
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader | sed 's/^/    GPU: /'

log "  vLLM 서빙 시작 (Sprint 1 옵션 포함)..."
nohup vllm serve "$MERGED_DIR" \
    --served-model-name "$MODEL_NAME" \
    --port "$VLLM_PORT" \
    --host 0.0.0.0 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.85 \
    --dtype bfloat16 \
    --enable-prefix-caching \
    --max-num-batched-tokens 8192 \
    --max-num-seqs 16 \
    > "$VLLM_LOG" 2>&1 &
VLLM_PID=$!
log "  vLLM PID: $VLLM_PID"
log "  로그:     $VLLM_LOG"

# ──────────────────────────────────────────────
# 5. 부팅 대기 + 검증
# ──────────────────────────────────────────────
log "5/5 vLLM 부팅 대기 (~60초)..."
for i in $(seq 1 90); do
    if curl -s -m 2 "http://localhost:$VLLM_PORT/v1/models" 2>/dev/null | grep -q "$MODEL_NAME"; then
        log "  ✅ 부팅 완료 (${i}초)"
        break
    fi
    sleep 1
done

# 최종 확인
if curl -s "http://localhost:$VLLM_PORT/v1/models" | grep -q "$MODEL_NAME"; then
    log "✅ vLLM 정상 — 모델 '$MODEL_NAME' 서빙 중"
    curl -s "http://localhost:$VLLM_PORT/v1/models" | python -m json.tool | head -15
else
    err "vLLM 부팅 실패. 로그 확인: tail -50 $VLLM_LOG"
    tail -30 "$VLLM_LOG"
    exit 1
fi

# ──────────────────────────────────────────────
# 6. 스모크 추론 (학습 모델 동작 확인)
# ──────────────────────────────────────────────
log "스모크 추론 (vt_psn 5건 쿼리)..."
curl -s "http://localhost:$VLLM_PORT/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d '{
        "model": "'$MODEL_NAME'",
        "messages": [{"role": "user", "content": "vt_psn 노드 5개 보여줘"}],
        "max_tokens": 80,
        "temperature": 0.0
    }' | python -c "
import sys, json
r = json.load(sys.stdin)
content = r['choices'][0]['message']['content']
print('    ', content[:200])
"

echo ""
log "🎉 v40 배포 완료"
echo "    로컬 맥에서 다음 실행:"
echo "      cd /Users/iankwon/test/coop_v1.0"
echo "      bash scripts/benchmark_v40.sh"
