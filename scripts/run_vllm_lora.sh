#!/bin/bash
# -------------------------------------------------------------
# Script to launch vLLM with the trained LoRA adapter
# -------------------------------------------------------------

BASE_MODEL="deepseek-ai/deepseek-coder-7b-instruct-v1.5"
LORA_PATH="/home/ai-kyw-dev/text2cypher_train/models/text2cypher-lora"
PORT=8000

echo "🚀 Starting vLLM serving with base model: $BASE_MODEL"
echo "🔧 Attaching trained Text-to-Cypher LoRA adapter: $LORA_PATH"

source ~/llm_env/bin/activate
pip install vllm  # Make sure vLLM is properly installed in this virtual environment to avoid conflicts

python3 -m vllm.entrypoints.openai.api_server \
    --model $BASE_MODEL \
    --enable-lora \
    --lora-modules text-to-cypher=$LORA_PATH \
    --max-lora-rank 32 \
    --host 0.0.0.0 \
    --port $PORT \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.90 \
    --dtype bfloat16
