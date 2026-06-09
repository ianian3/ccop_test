#!/bin/bash
# retrain_v39.sh — Qwen2.5-7B v39 재학습 (v38 잔여 약점 보강)
#
# 사전: scp t2c_v39_weakness_train_msg.json + retrain_v39.sh → 학습 서버

set -e
TRAIN_DIR="/home/ai-kyw-dev/ccop_train/train"
OUT_DIR="${TRAIN_DIR}/output/qwen25_t2c_v39_v1"
MERGED_DIR="${OUT_DIR}_merged"
MERGE_PY="/home/ai-kyw-dev/ccop_training/merge_lora.py"
LOG_FILE="/tmp/train_v39.log"

cd "$TRAIN_DIR"

prep() {
  echo "[1/4] v38 + v39 시드 병합..."
  python3 <<'PY'
import json, random
random.seed(20260521)
with open('t2c_v38_train_msg.json') as f: v38 = json.load(f)
with open('t2c_v39_weakness_train_msg.json') as f: v39_new = json.load(f)
for s in v39_new: s.pop('category', None)
combined = v38 + v39_new
random.shuffle(combined)
with open('t2c_v39_train_msg.json', 'w') as f:
    json.dump(combined, f, ensure_ascii=False, indent=2)
print(f'기존 v38: {len(v38)}, 보강: {len(v39_new)}, 합계: {len(combined)}')
PY

  echo "[2/4] dataset_info.json에 t2c_v39_msg 등록..."
  python3 <<'PY'
import json
with open('dataset_info.json') as f: info = json.load(f)
info['t2c_v39_msg'] = {
    "file_name": "t2c_v39_train_msg.json",
    "formatting": "sharegpt",
    "columns": {"messages": "messages", "system": "system"},
    "tags": {"role_tag": "role", "content_tag": "content",
             "user_tag": "user", "assistant_tag": "assistant"}
}
with open('dataset_info.json', 'w') as f:
    json.dump(info, f, ensure_ascii=False, indent=2)
print('dataset_info.json 갱신 완료')
PY

  echo "[3/4] train YAML 생성 (t2c_v38_msg → t2c_v39_msg)..."
  cp train_t2c_lora_v3_qwen_v3.yaml train_t2c_lora_v3_qwen_v4.yaml
  sed -i 's/t2c_v38_msg/t2c_v39_msg/g; s|output/qwen25_t2c_v38_v1|output/qwen25_t2c_v39_v1|g' \
    train_t2c_lora_v3_qwen_v4.yaml
  echo "  생성: train_t2c_lora_v3_qwen_v4.yaml"
}

start() {
  prep
  echo "[4/4] LoRA 학습 시작 (예상 ~6.5h, 로그: $LOG_FILE)..."
  source ~/llama_env/bin/activate
  nohup llamafactory-cli train train_t2c_lora_v3_qwen_v4.yaml > "$LOG_FILE" 2>&1 &
  echo "  PID: $!"
  echo ""
  echo "진행 확인: tail -f $LOG_FILE"
  echo "학습 완료 후: bash retrain_v39.sh merge"
}

merge() {
  echo "[머지] Base + LoRA → standalone 14GB 모델"
  source ~/llama_env/bin/activate
  python3 "$MERGE_PY" \
    --base_model Qwen/Qwen2.5-7B-Instruct \
    --lora_path "$OUT_DIR" \
    --output_dir "$MERGED_DIR"
  echo "완료: $MERGED_DIR"
}

serve() {
  echo "[서빙] vLLM 재시작"
  pkill -f "vllm serve" || true
  sleep 3
  source ~/llama_env/bin/activate
  nohup vllm serve "$MERGED_DIR" \
    --served-model-name qwen25_t2c_v39_v1 \
    --host 0.0.0.0 --port 8000 \
    --dtype bfloat16 --max-model-len 4096 --gpu-memory-utilization 0.9 \
    > /tmp/vllm_v39.log 2>&1 &
  echo "  PID: $!"
  sleep 8
  curl -s http://localhost:8000/v1/models | head -c 200
  echo ""
}

case "${1:-help}" in
  prep)  prep ;;
  start) start ;;
  merge) merge ;;
  serve) serve ;;
  *)     echo "사용: bash retrain_v39.sh {prep|start|merge|serve}" ;;
esac
