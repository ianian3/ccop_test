# v40 LoRA 재학습 가이드 (2026-05-26)

- **베이스 모델**: Qwen2.5-7B-Instruct (v37/v38/v39 동일)
- **신규 시드**: 1,548 (v39 약점 8 패턴 보강)
- **병합 데이터셋**: 31,694 (v39) + 1,548 = **~33,242 샘플**
- **예상 학습 시간**: ~7시간 (3 epoch, RTX 5090)
- **예상 결과**: V4.0 시나리오 68.9% → **85%+**, 152문항 72.4% → **82%+**

---

## 1단계 — 로컬 → 학습 서버 전송

```bash
# 로컬 맥에서
scp data/t2c_v40_weakness_train_msg.json \
    ai-kyw-dev@graphai-ws1-ubt24:~/ccop_train/train/

scp data/build_v40_weakness_seed.py \
    ai-kyw-dev@graphai-ws1-ubt24:~/ccop_train/data/

scp data/V40_TRAINING_GUIDE.md \
    ai-kyw-dev@graphai-ws1-ubt24:~/ccop_train/
```

---

## 2단계 — 학습 서버에서 데이터 병합

`~/ccop_train/train/` 의 기존 v38/v39 train_msg 파일과 병합. 사용한 정확한 파일 이름은 학습 서버에 있는 `dataset_info.json` 으로 확인.

```bash
ssh ai-kyw-dev@graphai-ws1-ubt24
cd ~/ccop_train/train
ls -la t2c_v3*_train_msg.json    # v38/v39 학습 데이터 확인

# 병합 — v39 학습 데이터 (31,694) + v40 약점 시드 (1,548)
python3 -c "
import json
v39 = json.load(open('t2c_v39_train_msg.json'))   # ← v39 학습 시 사용한 파일명
v40 = json.load(open('t2c_v40_weakness_train_msg.json'))
print(f'v39: {len(v39)} / v40 add: {len(v40)} / merge: {len(v39)+len(v40)}')
merged = v39 + v40
import random; random.seed(20260526); random.shuffle(merged)
with open('t2c_v40_train_msg.json', 'w', encoding='utf-8') as f:
    json.dump(merged, f, ensure_ascii=False, indent=2)
print('saved: t2c_v40_train_msg.json')
"
```

> ⚠️ v39 학습 데이터 정확한 파일명이 다르면 위 `t2c_v39_train_msg.json` 부분 교체.

---

## 3단계 — dataset_info.json 등록

```bash
# LLaMA-Factory dataset_info.json 위치 확인
find ~/ -name "dataset_info.json" 2>/dev/null | head

# 보통: ~/LLaMA-Factory/data/dataset_info.json
# 다음 항목 추가 (기존 't2c_v39_msg' 옆에):
```

```json
"t2c_v40_msg": {
    "file_name": "/home/ai-kyw-dev/ccop_train/train/t2c_v40_train_msg.json",
    "formatting": "openai_messages",
    "columns": {
        "messages": "messages",
        "system": "system"
    },
    "tags": {
        "role_tag": "role",
        "content_tag": "content",
        "user_tag": "user",
        "assistant_tag": "assistant"
    }
}
```

eval 셋이 별도면 동일 패턴으로 `t2c_v40_eval_msg` 도 등록.

---

## 4단계 — 학습 yaml 생성

```bash
cp ~/ccop_train/train/train_t2c_lora_v3_qwen_v3.yaml \
   ~/ccop_train/train/train_t2c_lora_v3_qwen_v4.yaml

# 다음 항목만 변경:
#   dataset:         t2c_v39_msg → t2c_v40_msg
#   output_dir:      ./output/qwen25_t2c_v37_v2 → ./output/qwen25_t2c_v40_v1
#   logging_dir:     동일 변경
#   run_name:        qwen25_t2c_v40_v1
```

또는 sed 로 일괄 치환:
```bash
sed -i \
    -e 's/t2c_v39_msg/t2c_v40_msg/g' \
    -e 's/qwen25_t2c_v37_v2\|qwen25_t2c_v38_v1\|qwen25_t2c_v39_v1/qwen25_t2c_v40_v1/g' \
    ~/ccop_train/train/train_t2c_lora_v3_qwen_v4.yaml

# 검증
cat ~/ccop_train/train/train_t2c_lora_v3_qwen_v4.yaml | grep -E "dataset|output|run_name"
```

---

## 5단계 — LoRA 학습 시작

```bash
cd ~/ccop_train
source ~/llama_env/bin/activate

# 학습 시작 (백그라운드)
nohup llamafactory-cli train ~/ccop_train/train/train_t2c_lora_v3_qwen_v4.yaml \
  > /tmp/train_v40.log 2>&1 &

echo "Training PID: $!"

# 진행 모니터링
tail -f /tmp/train_v40.log | grep -E "loss|eval_loss|epoch|step"
```

**예상 일정**:
- 시작: 0h
- 완료: ~7h (RTX 5090, batch_size 4, 3 epoch, ~5,500 step)

---

## 6단계 — 머지 + vLLM 서빙

```bash
source ~/llm_env/bin/activate
cd ~/ccop_training

python merge_lora.py \
  --base_model Qwen/Qwen2.5-7B-Instruct \
  --lora_path /home/ai-kyw-dev/ccop_train/train/output/qwen25_t2c_v40_v1 \
  --output_dir /home/ai-kyw-dev/ccop_train/train/output/qwen25_t2c_v40_v1_merged

# vLLM 종료 + 재시작 (Sprint 1 옵션 포함)
pkill -f vllm
sleep 5
nohup vllm serve /home/ai-kyw-dev/ccop_train/train/output/qwen25_t2c_v40_v1_merged \
  --served-model-name qwen25_t2c_v40_v1 \
  --port 8000 \
  --host 0.0.0.0 \
  --max-model-len 4096 \
  --gpu-memory-utilization 0.85 \
  --dtype bfloat16 \
  --enable-prefix-caching \
  --max-num-batched-tokens 8192 \
  --max-num-seqs 16 \
  > /tmp/vllm_v40.log 2>&1 &

sleep 45 && tail -20 /tmp/vllm_v40.log | grep -E "Uvicorn"
curl -s http://localhost:8000/v1/models | python -m json.tool
```

---

## 7단계 — 로컬 `.env` 갱신 + 벤치마크

```bash
# 로컬 맥에서
cd /Users/iankwon/test/coop_v1.0
sed -i '' 's/SLLM_MODEL_NAME=.*/SLLM_MODEL_NAME=qwen25_t2c_v40_v1/' .env

# 152문항 벤치마크
python3 benchmark_t2c_v2.py \
  --endpoint http://192.168.1.133:8000/v1 \
  --model qwen25_t2c_v40_v1 \
  --mode t2c_v37 \
  --graph tccop_graph_v6 \
  --output results/bench_v40_full.json

# 45 케이스 V4.0 시나리오 테스트
python3 scripts/test_v40_natural_query.py
```

---

## 8단계 — 결과 비교 보고서

다음 명령으로 자동 비교 보고서 생성 (생성 후 보고서를 본 conversation 에 붙여주면 분석):

```bash
python3 -c "
import json
v37 = json.load(open('results/bench_v37_full.json'))   # 65/152
v38 = json.load(open('results/bench_v38_full.json'))   # 96/152
v39 = json.load(open('results/bench_v39_full.json'))   # 110/152
v40 = json.load(open('results/bench_v40_full.json'))
print(f'v37: {v37[\"passed\"]}/{v37[\"total\"]}')
print(f'v38: {v38[\"passed\"]}/{v38[\"total\"]}')
print(f'v39: {v39[\"passed\"]}/{v39[\"total\"]}')
print(f'v40: {v40[\"passed\"]}/{v40[\"total\"]}')
"
```

---

## 📊 카테고리별 v39 vs v40 예상 비교

| 카테고리 | v39 | v40 예상 | Δ |
|----------|-----|---------|---|
| meta_condition | 66.7% | 85% | +18p |
| chain | 60% | 80% | +20p |
| threat_filter | 83.3% | 90% | +7p |
| 1hop_object | 90% | 92% | +2p |
| **신규 (v40)**: partial_match | - | 85% | NEW |
| **신규**: multi_where | - | 75% | NEW |
| **신규**: time_order | - | 90% | NEW |
| **전체 (V4.0 시나리오 45케이스)** | 68.9% | **85%** | **+16p** |
| **전체 (벤치마크 152문항)** | 72.4% | **82%+** | **+10p** |

---

## ⚠️ 학습 회귀 모니터링

학습 도중 다음 지표를 주시:
- `eval_loss` v39 의 0.1159 보다 낮거나 동일 (낮으면 우수, 높으면 회귀)
- `train_loss` 점진 감소 (epoch 진행할수록 감소해야 함)
- 만약 `eval_loss` 가 v39 대비 0.02 이상 증가하면 **학습 중단 + 데이터 분포 점검**

회귀 위험 카테고리 (v39 에서 100% 인 항목): v37_anonymous / v37_cluster / v37_multihop / v37_relay_station. 이들이 v40 에서 95% 미만으로 떨어지면 시드 비율 재조정 필요.
