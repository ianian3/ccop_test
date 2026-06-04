# Text2Cypher v40 → v41 → v42 → v42+Router → v43 비교 평가 보고서 (FINAL)

**작성일**: 2026-06-01
**대상 모델**: Qwen2.5-7B-Instruct + LoRA (r=64, α=128, QLoRA 4bit)
**평가셋**: 232문항 (V3.7 보강 15 + V4.0 단일 15 + 기존 202)
**판정 기준**: Cypher 정확도 (노드 라벨/엣지 방향/속성/조건절 완전 일치)
**상태**: 5종 측정 완료 ✅
**최종 운영 결정**: **v42 + Router 표준 채택** (86.6%, v43은 catastrophic forgetting 으로 폐기)

---

## 1. 핵심 요약

| 모델 | 학습 시드 | 학습 시간 | 실행 성공률 | 신규 엣지(v3.6) | v3.7 엣지 | 85% 목표 | 비고 |
|---|---|---|---|---|---|---|---|
| v40 | 31K (기존) | ~6h | 81.5% (189/232) | 60.7% | 92.9% | ❌ | baseline |
| v41 | 830 (회귀 특화) | ~4h | 79.3% (184/232) | 66.1% | 92.9% | ❌ | 폐기 |
| v42 | 970 (균형) | 6h 50m | 81.0% (188/232) | 62.5% | 92.9% | ❌ | 모델 단독 |
| **v42 + Router** | + 라우터 코드 | +0 (코드) | **86.6% (201/232)** | 62.5% | 92.9% | **✅ 달성** | **🏆 운영 표준** |
| v43 | 800 (object 집중) | 8m 22s | 60.8% (141/232) | 55.4% | 42.9% | ❌ | **catastrophic forgetting 폐기** |

**최종 판정**:
- **🏆 v42 + Router 운영 표준 유지** — 학습 추가 없이 라우터 코드만으로 86.6% 달성
- **v43 폐기 (catastrophic forgetting)** — 1hop_object 보강은 성공(+20p)했으나 v42의 prior 거의 전체 망각 (-60문항)
- **v44 (계획)**: continue learning 전략 — v42 어댑터 위에 추가 학습, lr↓, epochs↓

---

## 2. 5종 모델 카테고리별 매트릭스

| 카테고리 | v40 | v41 | v42 | **v42+R** | v43 | Δ v43 vs v42+R |
|---|---|---|---|---|---|---|
| 단일노드 | 100% | 96.3% | 100% | **100%** | 77.8% | **-22.2p** ⚠ |
| 1hop_case | 86.7% | 93.3% | 86.7% | **86.7%** | 26.7% | **-60.0p** ⚠⚠ |
| 1hop_person | 84.0% | 72.0% | 80.0% | **80.0%** | 56.0% | -24.0p ⚠ |
| **1hop_person2person** | 60.0% | 80.0% | 90.0% | **90.0%** | 10.0% | **-80.0p** ⚠⚠⚠ |
| 1hop_event | 66.7% | 60.0% | 60.0% | 60.0% | **73.3%** | **+13.3p** ⭐ |
| **1hop_object** | 100% | 90.0% | 70.0% | 70.0% | **90.0%** | **+20.0p** ⭐ |
| meta_condition | 53.3% | 60.0% | 60.0% | **60.0%** | 60.0% | 0p |
| threat_filter | 83.3% | 75.0% | 83.3% | **83.3%** | 41.7% | **-41.7p** ⚠ |
| chain | 80.0% | 66.7% | 66.7% | 66.7% | 66.7% | 0p |
| general | 0% | 0% | 0% | **100%** | 100% | 0p (Router) |
| guard | 0% | 0% | 0% | **100%** | 100% | 0p (Router) |
| v37_cluster | 90.9% | 90.9% | 100% | **100%** | 36.4% | **-63.6p** ⚠⚠ |
| v37_anonymous | 80.0% | 80.0% | 100% | **100%** | 40.0% | **-60.0p** ⚠⚠ |
| v37_relay_station | 83.3% | 83.3% | 83.3% | **83.3%** | 16.7% | **-66.7p** ⚠⚠ |
| v37_multihop | 100% | 100% | 100% | **100%** | 66.7% | -33.3p ⚠ |
| partial_match | 100% | 100% | 100% | **100%** | 66.7% | -33.3p ⚠ |
| multi_where | 100% | 100% | 100% | **100%** | 80.0% | -20.0p ⚠ |
| meta_filter | 100% | 100% | 100% | **100%** | 50.0% | -50.0p ⚠ |
| time_order | 100% | 100% | 100% | **100%** | 100% | 0p |
| edge_direction | 100% | 100% | 100% | **100%** | 80.0% | -20.0p ⚠ |
| edge_naming | 100% | 100% | 100% | **100%** | 80.0% | -20.0p ⚠ |
| hub_node_simple | 100% | 100% | 100% | **100%** | 75.0% | -25.0p ⚠ |
| no_cast | 100% | 100% | 100% | **100%** | 33.3% | **-66.7p** ⚠⚠ |

---

## 3. 정량 지표 (최종)

| 지표 | 목표 | v40 | v41 | v42 | **v42+Router** | v43 | 판정 |
|---|---|---|---|---|---|---|---|
| 실행 성공률 | **85%+** | 81.5% | 79.3% | 81.0% | **86.6%** | 60.8% | **v42+R ✅** |
| v3.6 신규 엣지 | 65%+ | 60.7% | 66.1% | 62.5% | 62.5% | 55.4% | v41 ✅ |
| v3.7 신규 엣지 | 65%+ | 92.9% | 92.9% | 92.9% | **92.9%** | 42.9% | v42+R ✅✅ |

---

## 4. v43 실패 분석 — Catastrophic Forgetting

### 4.1 학습 메트릭 vs 실제 성능 괴리

```
v43 학습 결과 (8분 22초):
  train_loss: 0.1511
  eval_loss:  0.0025  ← ⚠ 비정상적으로 낮음 (over-fit 신호)

v42 비교 (6h 50m):
  train_loss: 0.1103
  eval_loss:  0.1159  ← 정상 (gap 0.006, over-fit 없음)
```

**eval_loss 0.0025 가 경고 신호였음** — eval 78 샘플이 train 802 샘플과 동일 템플릿 패턴이라 자명한 패턴만 외움. 실제 232문항 벤치마크에서 일반화 실패 드러남.

### 4.2 회귀 분포 (v42+R 대비)

```
의도한 개선:    +4문항  (1hop_object +2 / 1hop_event +2)
의도치 않은 회귀: -64문항 (16개 카테고리 전반에서 회귀)
순효과:         -60문항 (201 → 141)
```

가장 큰 회귀 7개 (모두 v43 시드에 없던 카테고리):
| 카테고리 | v42+R | v43 | Δ | 시드 포함? |
|---|---|---|---|---|
| 1hop_person2person | 90% | 10% | **-80p** | ❌ (v42 보존 의도) |
| no_cast | 100% | 33% | -67p | ❌ |
| relay_station | 83% | 17% | -67p | ❌ |
| v37_cluster | 100% | 36% | -64p | ❌ |
| 1hop_case | 87% | 27% | -60p | ❌ |
| v37_anonymous | 100% | 40% | -60p | ❌ |
| meta_filter | 100% | 50% | -50p | ❌ |

### 4.3 근본 원인 분석

```
v42 학습 구조 (성공):
  Qwen2.5-base → [v40 31K 시드 → v40 어댑터]
              → [v40 어댑터 위에서 v42 970 시드 추가] → v42 어댑터
              = 균형 잡힌 prior + 신규 카테고리 보강

v43 학습 구조 (실패):
  Qwen2.5-base → [v43 800 시드만 단독] → v43 어댑터
              ❌ v42 어댑터를 base로 지정 안 함
              ❌ 8분 학습 = 시드 패턴만 외우고 v37/v40 prior 망각
              ❌ base seed 미포함 → general capability 손실
```

핵심 실수:
1. `adapter_name_or_path` 에 v42 어댑터 미지정 → Qwen2.5 vanilla에서 시작
2. `learning_rate 5e-5` + `epochs 3` → 800 시드에 과적합
3. `val_size 0.1` (78 샘플) → eval 신호 가짜로 좋게 나옴

### 4.4 v43 효과 검증 (긍정적 데이터)

회귀에 묻혀버린 의도한 효과는 실제로 존재했음:

| 카테고리 | v42+R | v43 | v44 목표 |
|---|---|---|---|
| 1hop_object | 70% | **90%** ⭐ | 90% (효과 보존 + 회귀 제거) |
| 1hop_event | 60% | **73%** ⭐ | 80%+ |

**시드 자체는 효과적이었음** — 학습 방법(continue learning)만 수정하면 v44는 성공 가능성 높음.

---

## 5. v44 학습 전략 (다음 사이클)

### 5.1 방법 A: Continue Learning (권장)

```yaml
# train/train_v44_continue.yaml
model_name_or_path: Qwen/Qwen2.5-7B-Instruct
adapter_name_or_path: /home/ai-kyw-dev/ccop_train/train/output/qwen25_t2c_v42_v1  # ⭐ 핵심
create_new_adapter: false   # v42 어댑터 위에 누적 학습
finetuning_type: lora
lora_rank: 64
lora_alpha: 128

dataset: t2c_v43_object_focus  # 동일 시드 재사용
learning_rate: 1.0e-5         # ⭐ v42의 1/5 (망각 방지)
num_train_epochs: 1.0         # ⭐ 1 epoch만 (3 epoch = over-fit)
warmup_ratio: 0.1
```

**예상 효과**: 86.6% → 89~91% (1hop_object/event 개선 + v42 prior 보존)
**학습 시간**: 1~2시간

### 5.2 방법 B: 통합 시드 (대안)

```python
# v40 base 시드 일부 + v42 시드 일부 + v43 시드 통합
combined_seeds = (
    sample(v40_base_seeds, 300) +    # general capability 보존
    sample(v42_balanced_seeds, 300) + # person2person, anonymous 보존
    v43_object_focus_seeds            # 1hop_object 보강
)  # 총 1400 시드
# 처음부터 새로 학습
```

학습 시간 6~7h, 더 안정적이나 비용 높음.

### 5.3 v44 의사결정

| 옵션 | 예상 정확도 | 비용 | 리스크 |
|---|---|---|---|
| **A (continue)** | 89~91% | 1~2h | 낮음 — v42에서 시작 |
| B (통합) | 88~92% | 6~7h | 중간 — 새 학습 |
| **현재 운영 유지 (v42+R)** | 86.6% | 0 | 없음 (이미 운영 임계 충족) |

**권고**: 운영은 v42+R 유지, v44는 백그라운드로 방법 A 시도. 실패해도 운영 영향 없음.

---

## 6. 최종 운영 권고

### 6.1 🏆 운영 표준: v42 + Router

```
모델 ID:     qwen25-t2c-v42 (Qwen2.5-7B + LoRA r=64 병합)
체크포인트:  /home/ai-kyw-dev/ccop_train/train/output/qwen25_t2c_v42_v1_merged
서빙:        vLLM 0.0.0.0:8000 (--gpu-memory-utilization 0.85)
앞단:        ai_service.py 라우터 (GUARD/GENERAL 사전 차단)
LangGraph:   GUARD/GENERAL intent 차단 응답 분기

지표:
  ✅ 실행 성공률 86.6% (운영 임계 85% 초과)
  ✅ V3.7 신규 엣지 92.9% (목표 65% 큰폭 초과)
  ✅ V4.0 person2person 90% (v40 대비 +30p)
  ✅ V3.7 cluster/anonymous 100% 달성
  ⚠ 1hop_object 70% (v44 보강 대상)
```

### 6.2 모델 아카이브 정책

```
✅ 보존:
  qwen25_t2c_v42_v1_merged/    ← 운영 표준 (배포)
  qwen25_t2c_v42_v1/           ← LoRA 어댑터 (v44 base로 사용)
  qwen25_t2c_v43_v1/           ← v43 어댑터 (시드 자체는 유효, 학습 방법만 수정)

🗑️ 폐기:
  qwen25_t2c_v43_v1_merged/    ← 60.8% 운영 불가 (15GB 디스크 회수)
  qwen25_t2c_v40_v1_merged/    ← v42 대체 (15GB)
  qwen25_t2c_v41_v1_merged/    ← v41 폐기 (15GB)
```

### 6.3 v44 학습 시점

```
즉시 가능:
  - 시드 (data/t2c_v43_object_focus_train_msg.json) 재사용
  - 학습 시간 1~2시간
  - 운영 영향 없음 (별도 어댑터, 측정 완료 시 채택 결정)

선결 조건:
  - GPU 서버 디스크 회수 (v43_merged 폐기로 15GB 확보)
  - v42 어댑터 보존 확인 (continue learning base)
```

---

## 7. 학습 메트릭 비교 (참고)

```
모델   train_loss   eval_loss   train-eval gap   eval samples   학습시간   결과
v42      0.1103     0.1159       0.0056          3,117          6h 50m   81.0% (모델 단독)
v43      0.1511     0.0025       0.1486          78             8m 22s   60.8% (catastrophic)

해석:
  v42: gap 0.006 = 건강한 학습 (over-fit 없음)
  v43: gap 0.149 = 심각한 over-fit (eval 78샘플이 train과 동일 패턴)

교훈: eval_loss 가 낮을수록 좋은 게 아님 — eval set 다양성 + 232문항 측정이 진실
```

---

## 8. 측정 환경

```
GPU:           NVIDIA RTX 5090 32GB
프레임워크:    LLaMA-Factory + transformers 4.x
기법:          QLoRA 4bit (BitsAndBytes nf4)
어댑터:        r=64, α=128, dropout=0.05
LR:            5e-5 (cosine) — v44는 1e-5 권장
배치:          per_device=4, accum=8 (effective 32)
서빙:          vLLM (--gpu-memory-utilization 0.85, --dtype bfloat16)
벤치마크:      benchmark_t2c_v2.py --mode t2c_v37, 232문항
라우터:        ai_service.py + langgraph_agent.py + benchmark_t2c_v2.py 사전 라우터
```

---

## 9. 결과 파일

- v40: [results/bench_v40_full_232.json](../results/bench_v40_full_232.json)
- v41: [results/bench_v41_full_232.json](../results/bench_v41_full_232.json)
- v42: [results/bench_v42_full_232.json](../results/bench_v42_full_232.json)
- **v42+Router**: [results/bench_v42_router_232.json](../results/bench_v42_router_232.json) 🏆
- v43 (catastrophic forgetting): [results/bench_v43_router_232.json](../results/bench_v43_router_232.json)

---

## 10. 관련 문서 / 데이터

- [V4.0 시나리오 측정 보고서](./T2C_V40_V41_COMPARISON_20260528.md)
- [V4.0 SSOT 체크포인트](../MEMORY/project_v40_checkpoint.md)
- v43 시드 빌더: [data/build_v43_object_focus_seed.py](../data/build_v43_object_focus_seed.py)
- v43 시드 데이터: `data/t2c_v43_object_focus_train_msg.json` (v44 재사용 가능)

---

## 11. 변경 이력

| 일자 | 사이클 | 결과 |
|---|---|---|
| 2026-05-26 | v40 학습 (31K 시드, 6h) | 81.5% baseline |
| 2026-05-27 | v41 회귀 특화 (830 시드, 4h) | 79.3% (person2person +20p, 회귀 -22.9p) |
| 2026-05-27 | v42 균형 시드 (970 시드, 6h50m) | 81.0% (person2person 90%, 기타 보존) |
| 2026-06-01 | v42 병합 + 232 측정 | 81.0% 확정 |
| 2026-06-01 | **Router 리워크 + 재측정** | **86.6% — 85% 임계 달성 ✅ 🏆** |
| 2026-06-01 | v43 object-focus (800 시드, 8m) | 60.8% — **catastrophic forgetting, 폐기** |
| **2026-06-01** | **최종 운영 권고: v42+Router 표준 채택** | **89% 목표는 v44 continue learning 으로 연기** |

---

## 12. 교훈 (Lessons Learned)

### 12.1 LoRA 추가 학습 시 주의사항
- ❌ **하지 말 것**: 새 어댑터 + 적은 시드 + 높은 lr + 많은 epoch → catastrophic forgetting
- ✅ **할 것**: 기존 어댑터 continue + 낮은 lr (1e-5) + 1 epoch + warmup 충분

### 12.2 학습 메트릭 신뢰도
- `eval_loss` 가 train_loss 보다 훨씬 낮으면 **반드시 의심** (eval set 단조로움)
- 실제 일반화는 **별도 holdout 평가셋** (232문항)에서만 검증 가능
- 학습 시간이 비정상적으로 짧으면(8분 < 1h) 학습 깊이 부족 또는 데이터셋 작음

### 12.3 시스템 가드레일 (Router) 의 가치
- 모델 학습 추가 없이 **+5.6p 개선** (81.0% → 86.6%)
- 정규식 패턴 매칭이 LLM 보다 GUARD/GENERAL 차단에 더 정확하고 빠름
- 운영 안전성 (DDL/DML 차단, 프롬프트 인젝션 방어) 보너스

### 12.4 시드 자체는 효과적이었음
- v43 1hop_object 70% → 90% (+20p), 1hop_event 60% → 73% (+13p)
- 학습 방법만 수정하면 (continue from v42) 시드 효과 살리면서 회귀 방지 가능
- → v44 에서 동일 시드 재사용 권고
