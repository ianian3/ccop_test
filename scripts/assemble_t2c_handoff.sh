#!/usr/bin/env bash
# CCOP Text2Cypher v42 전달 번들 조립 (GPU 머신에서 실행)
set -euo pipefail

OUT="$HOME/handoff_t2c_v42"
MERGED="$HOME/ccop_train/train/output/qwen25_t2c_v42_v1_merged"
DATA="$HOME/ccop_train/train"
REPO="$HOME/ccop_test"
STAGE="$HOME/handoff_stage"     # scp 로 올린 문서(MODEL_CARD/SERVING/NOTICE) 위치

log(){ printf "\n\033[1;36m[handoff]\033[0m %s\n" "$*"; }

log "사전 점검"
[ -d "$MERGED" ] || { echo "머지본 없음: $MERGED"; exit 1; }
[ -f "$MERGED/chat_template.jinja" ] || { echo "chat_template.jinja 없음"; exit 1; }
for f in MODEL_CARD.md SERVING.md NOTICE.md; do [ -f "$STAGE/$f" ] || { echo "문서 없음: $STAGE/$f"; exit 1; }; done

log "번들 디렉토리 생성: $OUT"
rm -rf "$OUT"; mkdir -p "$OUT"/{model,prompt,eval,dataset}

log "문서 배치"
cp "$STAGE"/MODEL_CARD.md "$STAGE"/SERVING.md "$STAGE"/NOTICE.md "$OUT"/

log "병합 가중치 복사 (~15GB, 수 분 소요)"
cp -r "$MERGED" "$OUT/model/qwen25-t2c-v42"

log "시스템 프롬프트"
cp "$REPO/app/services/prompts/t2c_v37_system.txt" "$OUT/prompt/"

log "평가 하니스 + 기준 결과"
cp "$REPO/benchmark_t2c_v2.py" "$OUT/eval/"
cp "$REPO/results/bench_v42_router_232.json" "$REPO/results/bench_v42_full_232.json" "$OUT/eval/"

log "데이터셋 (messages 정본) + 학습 설정"
cp "$DATA/t2c_v37_train_msg.json" "$DATA/t2c_v37_eval_msg.json" "$OUT/dataset/"
cp "$REPO/train/train_t2c_lora_v3_qwen_v2.yaml" "$OUT/dataset/"

log "체크섬 생성"
( cd "$OUT" && find . -type f ! -name SHA256SUMS -exec sha256sum {} \; > SHA256SUMS )

log "완료"
du -sh "$OUT"
echo "  파일 수: $(wc -l < "$OUT/SHA256SUMS")"
echo "  트리:"
find "$OUT" -maxdepth 2 -not -path "*/model/qwen25-t2c-v42/*" | sed "s|$OUT|handoff_t2c_v42|" | sort
echo "  (model/qwen25-t2c-v42/ 내용: $(ls "$OUT/model/qwen25-t2c-v42" | wc -l)개 파일, $(du -sh "$OUT/model/qwen25-t2c-v42" | cut -f1))"
