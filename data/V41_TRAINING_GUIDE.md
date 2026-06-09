# v41 LoRA 재학습 가이드 (2026-05-27)

- **베이스 모델**: Qwen2.5-7B-Instruct (v40 동일)
- **보강 시드**: 830 (회귀 4 카테고리)
- **병합 데이터셋**: v40 33,242 + v41 830 = **~34,072 샘플**
- **예상 학습 시간**: ~7시간 (3 epoch, RTX 5090)
- **목표**: 1hop_person2person 60% → 80%+, meta_condition 53% → 75%+

## 보강 카테고리

| 카테고리 | 시드 | v40 → v41 목표 |
|----------|------|----------------|
| person2person (recruits/blackmails/accomplice_of/sameAs/member_of) | 297 | 60% → 80% |
| meta_condition (risk_level/threat_score/evid_grade/is_burner) | 290 | 53% → 75% |
| 1hop_event (caller/callee/from_account/to_account 방향) | 145 | 67% → 85% |
| chain (3-4 hop) | 98 | 80% → 90% |
| **합계** | **830** | |

---

## 1단계 — 로컬 → 학습 서버 전송

```bash
# 로컬 맥에서
cd /Users/iankwon/test/coop_v1.0
scp data/t2c_v41_weakness_train_msg.json \
    data/build_v41_weakness_seed.py \
    data/V41_TRAINING_GUIDE.md \
    ai-kyw-dev@192.168.1.133:~/ccop_train/train/
```

## 2단계 — 학습 서버에서 데이터 병합

```bash
ssh ai-kyw-dev@192.168.1.133
cd ~/ccop_train/train

# 이미 t2c_v40_train_msg.json 이 v40 학습 시 사용된 33,242 데이터로 존재함
ls -lh t2c_v40_train_msg.json

# 병합
python3 <<'PY'
import json, random
v40 = json.load(open('t2c_v40_train_msg.json'))   # 33,242
v41_weak = json.load(open('t2c_v41_weakness_train_msg.json'))  # 830
print(f'v40 base: {len(v40)}, v41 weak: {len(v41_weak)}, merge: {len(v40)+len(v41_weak)}')
merged = v40 + v41_weak
random.seed(20260527); random.shuffle(merged)
with open('t2c_v41_train_msg.json', 'w', encoding='utf-8') as f:
    json.dump(merged, f, ensure_ascii=False, indent=2)
print('saved: t2c_v41_train_msg.json')
PY
```

## 3단계 — dataset_info 등록

```bash
python3 <<'PY'
import json
DI = 'dataset_info.json'
d = json.load(open(DI))
# v40_msg 구조 복사
if 't2c_v40_msg' in d:
    new = dict(d['t2c_v40_msg'])
    new['file_name'] = '/home/ai-kyw-dev/ccop_train/train/t2c_v41_train_msg.json'
    d['t2c_v41_msg'] = new
with open(DI, 'w', encoding='utf-8') as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print('t2c_v41_msg 등록')
PY
```

## 4단계 — yaml 생성

```bash
cp train_t2c_lora_v3_qwen_v4.yaml train_t2c_lora_v3_qwen_v5.yaml

sed -i \
    -e 's/t2c_v40_msg/t2c_v41_msg/g' \
    -e 's|output/qwen25_t2c_v40_v1|output/qwen25_t2c_v41_v1|g' \
    -e 's/qwen25_t2c_v40_v1/qwen25_t2c_v41_v1/g' \
    train_t2c_lora_v3_qwen_v5.yaml

grep -E "dataset|output_dir|run_name" train_t2c_lora_v3_qwen_v5.yaml
```

## 5단계 — 학습 시작 (~7h)

```bash
cd ~/ccop_train
source ~/llama_env/bin/activate

nohup llamafactory-cli train ~/ccop_train/train/train_t2c_lora_v3_qwen_v5.yaml \
  > /tmp/train_v41.log 2>&1 &
echo "PID: $!"
date

# 30초 후 부팅 확인
sleep 30
ps -eo pid,etime,cmd | grep llamafactory | grep -v grep
nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv,noheader
tail -30 /tmp/train_v41.log
```

## 6단계 — 머지 + vLLM 서빙

학습 완료 후 (`grep train_runtime /tmp/train_v41.log`):

```bash
deactivate
source ~/llm_env/bin/activate
cd ~/ccop_training

python merge_lora.py \
  --base_model Qwen/Qwen2.5-7B-Instruct \
  --lora_path /home/ai-kyw-dev/ccop_train/train/output/qwen25_t2c_v41_v1 \
  --output_dir /home/ai-kyw-dev/ccop_train/train/output/qwen25_t2c_v41_v1_merged

# 기존 vLLM 종료 → v41 서빙
pkill -9 -f vllm; sleep 10
nvidia-smi --query-gpu=memory.free --format=csv

nohup vllm serve /home/ai-kyw-dev/ccop_train/train/output/qwen25_t2c_v41_v1_merged \
  --served-model-name qwen25_t2c_v41_v1 \
  --port 8000 --host 0.0.0.0 \
  --max-model-len 4096 --gpu-memory-utilization 0.85 --dtype bfloat16 \
  --enable-prefix-caching --max-num-batched-tokens 8192 --max-num-seqs 16 \
  > /tmp/vllm_v41.log 2>&1 &

sleep 45
curl -s http://localhost:8000/v1/models | python -m json.tool | head -8
```

## 7단계 — 로컬 .env + 벤치마크

```bash
# 로컬 맥
cd /Users/iankwon/test/coop_v1.0
sed -i '' 's/SLLM_MODEL_NAME=.*/SLLM_MODEL_NAME=qwen25_t2c_v41_v1/' .env

# 232문항 벤치마크 (V4.0 시나리오 그래프 사용 — 회귀 카테고리 측정에 최적)
python3 benchmark_t2c_v2.py \
  --endpoint http://192.168.1.133:8000/v1 \
  --model qwen25_t2c_v41_v1 \
  --mode t2c_v37 \
  --graph tccop_v40_demo \
  --output results/bench_v41_full_232.json
```

## 예상 결과

| 카테고리 | v40 | v41 목표 | 보강 시드 |
|----------|-----|---------|-----------|
| 1hop_person2person | 60% | **80%** (+20p) | 297 |
| meta_condition | 53.3% | **75%** (+22p) | 290 |
| 1hop_event | 66.7% | **85%** (+18p) | 145 |
| chain | 80% | **90%** (+10p) | 98 |
| 전체 (232) | 81.5% | **85%+** (+3.5p) | |
| 회귀 카테고리 외 | (유지) | (유지) | |

## 회귀 모니터링

학습 도중 다음 주시:
- `eval_loss` v40 0.1159 보다 낮거나 동일
- v40 강점 카테고리 (단일 100%, M~T 50/50) 유지 확인
- 만약 강점에서 5p 이상 떨어지면 → 데이터 비율 재조정

## 다음 체크포인트

v41 학습 완료 + 벤치마크 후 → `docs/CHECKPOINT_20260528.md` (다음 날) 생성 권장.
