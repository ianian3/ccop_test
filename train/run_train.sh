#!/bin/bash
# EXAONE-3.5-7.8B 파인튜닝 실행 스크립트
# 사용법: bash run_train.sh [lora|full]

set -e

MODE=${1:-lora}
LLAMA_FACTORY_DIR=${LLAMA_FACTORY_DIR:-"$HOME/LLaMA-Factory"}
TRAIN_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo " EXAONE-3.5-7.8B SFT 파인튜닝"
echo " 모드: $MODE"
echo " 학습 디렉토리: $TRAIN_DIR"
echo "=========================================="

# LLaMA-Factory 설치 확인
if ! command -v llamafactory-cli &>/dev/null; then
    echo "[설치] LLaMA-Factory가 없습니다. 설치를 시작합니다..."
    pip install llamafactory
fi

# dataset_info.json을 LLaMA-Factory data 디렉토리에 심볼릭 링크 또는 복사
if [ -d "$LLAMA_FACTORY_DIR/data" ]; then
    cp "$TRAIN_DIR/dataset_info.json" "$LLAMA_FACTORY_DIR/data/dataset_info.json"
    echo "[설정] dataset_info.json → $LLAMA_FACTORY_DIR/data/"
fi

# 학습 실행
if [ "$MODE" = "full" ]; then
    echo "[실행] Full Fine-tuning 시작..."
    llamafactory-cli train "$TRAIN_DIR/train_exaone_full.yaml"
else
    echo "[실행] LoRA Fine-tuning 시작..."
    llamafactory-cli train "$TRAIN_DIR/train_exaone_lora.yaml"
fi

echo ""
echo "✅ 학습 완료!"
echo "   출력 경로: $TRAIN_DIR/output/exaone-$MODE"
