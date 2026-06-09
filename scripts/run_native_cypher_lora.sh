#!/bin/bash
# =====================================================================
# CCOP Native Cypher LoRA 파인튜닝 스크립트
# 대상 서버: 192.168.1.133 (vLLM + GPU)
# 기반 모델: ccop-t2c-v2 (현재 운영 모델)
# =====================================================================

set -e

# ── 환경 설정 ──────────────────────────────────────────────────────
BASE_MODEL="/path/to/ccop-t2c-v2"       # 서버에서 실제 경로로 수정
SFT_DATA="/path/to/native_cypher_sft_sharegpt.json"  # 업로드된 데이터 경로
OUTPUT_DIR="/path/to/ccop-native-lora"  # LoRA 가중치 저장 경로
MERGED_DIR="/path/to/ccop-t2c-v3"       # 병합 후 모델 저장 경로

LORA_RANK=16
LORA_ALPHA=32
EPOCHS=3
BATCH_SIZE=4
MAX_LEN=512
LR=2e-4

# ── Step 1: 데이터 확인 ──────────────────────────────────────────────
echo "📊 학습 데이터 확인..."
python3 -c "
import json
with open('$SFT_DATA') as f:
    data = json.load(f)
print(f'총 학습 샘플: {len(data)}개')
print(f'샘플: {data[0][\"conversations\"][1][\"value\"][:60]}')
"

# ── Step 2: LLaMA-Factory로 LoRA 파인튜닝 ───────────────────────────
# LLaMA-Factory(권장) 또는 Axolotl 사용
echo "🚀 LoRA 파인튜닝 시작..."

# LLaMA-Factory 방식
llamafactory-cli train \
    --model_name_or_path $BASE_MODEL \
    --stage sft \
    --do_train \
    --finetuning_type lora \
    --lora_rank $LORA_RANK \
    --lora_alpha $LORA_ALPHA \
    --lora_target q_proj,v_proj,k_proj,o_proj \
    --dataset_dir $(dirname $SFT_DATA) \
    --dataset $(basename $SFT_DATA .json) \
    --template llama3 \
    --cutoff_len $MAX_LEN \
    --max_samples 99999 \
    --output_dir $OUTPUT_DIR \
    --num_train_epochs $EPOCHS \
    --per_device_train_batch_size $BATCH_SIZE \
    --gradient_accumulation_steps 4 \
    --learning_rate $LR \
    --lr_scheduler_type cosine \
    --warmup_ratio 0.05 \
    --logging_steps 10 \
    --save_steps 100 \
    --fp16 \
    --report_to none

echo "✅ LoRA 파인튜닝 완료: $OUTPUT_DIR"

# ── Step 3: LoRA 가중치 병합 ─────────────────────────────────────────
echo "🔗 LoRA 가중치 병합 중..."

llamafactory-cli export \
    --model_name_or_path $BASE_MODEL \
    --adapter_name_or_path $OUTPUT_DIR \
    --template llama3 \
    --finetuning_type lora \
    --export_dir $MERGED_DIR \
    --export_size 2 \
    --export_legacy_format false

echo "✅ 모델 병합 완료: $MERGED_DIR"

# ── Step 4: vLLM으로 새 모델 서빙 ────────────────────────────────────
echo "🌐 새 모델(ccop-t2c-v3)로 vLLM 재시작..."

# 기존 vLLM 종료
pkill -f "vllm.entrypoints.openai" || true
sleep 3

# 새 모델로 실행
nohup python -m vllm.entrypoints.openai.api_server \
    --model $MERGED_DIR \
    --served-model-name ccop-t2c-v3 \
    --port 8000 \
    --gpu-memory-utilization 0.9 \
    --max-model-len 4096 \
    --dtype float16 \
    > /var/log/vllm_v3.log 2>&1 &

echo "⏳ 서버 시작 대기..."
sleep 30

# ── Step 5: 성능 검증 ─────────────────────────────────────────────────
echo "📈 새 모델 성능 검증..."
python3 -c "
from openai import OpenAI
client = OpenAI(base_url='http://192.168.1.133:8000/v1', api_key='EMPTY')
resp = client.chat.completions.create(
    model='ccop-t2c-v3',
    messages=[{'role':'user','content':'피의자1 보유 계좌 찾아줘'}],
    temperature=0
)
print('응답:', resp.choices[0].message.content)
"
echo "✅ ccop-t2c-v3 서빙 완료!"
