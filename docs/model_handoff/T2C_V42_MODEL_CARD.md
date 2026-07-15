# Model Card — CCOP Text2Cypher v42 (qwen25-t2c-v42)

수사 도메인 **자연어 → AgensGraph Cypher** 변환 특화 모델. 이 카드 하나로 무엇을·어떻게 테스트하는지 파악할 수 있게 작성.

---

## 1. 개요

| 항목 | 값 |
|---|---|
| 모델명 | `qwen25-t2c-v42` |
| 베이스 | `Qwen/Qwen2.5-7B-Instruct` |
| 기법 | SFT + LoRA (r=64, α=128) → 병합(merged full weights) |
| 과제 | Text2Cypher — 한국어 수사 질의를 AgensGraph Cypher로 변환 |
| 온톨로지 | KICS POLE 6계층 (25 노드 / 53 엣지) — v3.7 |
| 배포 형태 | 병합 풀웨이트 (bf16, ~15GB, 4 샤드) |
| 라이선스 | 베이스 Qwen2.5 = Apache-2.0 · 데이터/어댑터는 `NOTICE.md` 참조 |

**운영 표준 성능: 자체 232문항 벤치마크 정확도 86.6%** (모델 단독 81.0% + 규칙 Router). 상세는 §4.

---

## 2. 용도 / 비용도

**의도된 용도**
- 수사 그래프 DB(AgensGraph)에 대한 한국어 자연어 조회를 Cypher로 변환
- 온프레미스/폐쇄망 서빙 (외부 API 의존 없음)

**범위 밖 (out-of-scope)**
- KICS/POLE 외 임의 스키마 — 이 스키마에 특화 학습됨(다른 그래프엔 부정확)
- 쓰기 쿼리(CREATE/DELETE 등) — 조회 전용으로 학습, 시스템 프롬프트가 금지
- 범용 대화 — 잡담/비수사 질의는 Router가 차단하는 설계 (§4.3)

---

## 3. 학습 (Training)

**데이터셋** `t2c_v37` — 규칙 시드 + GPT-4o-mini 증강 하이브리드, **31,226 샘플** (train 28,109 / eval 3,117, 13-stratum 층화 분할). 포맷: **OpenAI messages**(ShareGPT+템플릿 조합의 label masking 버그 회피 — `dataset/` 에 동봉).

**하이퍼파라미터** (대표 레시피 `dataset/train_t2c_lora_v3_qwen_v2.yaml`)

| 항목 | 값 |
|---|---|
| LoRA rank / alpha / dropout | 64 / 128 / 0.05 |
| target modules | q,k,v,o,gate,up,down (7개, all-linear) |
| 양자화 | QLoRA 4bit (nf4, double quant, compute bf16) |
| cutoff_len | 1536 |
| learning rate | 1e-4 (cosine, warmup 0.03) |
| epochs / effective batch | 3 / 16 (per_device 2 × grad_accum 8) |
| 하드웨어 | RTX 5090 32GB (Blackwell) |
| 학습 시간 | 약 6~7시간/사이클 |
| train/eval loss | 0.110 / 0.116 (건강 — 과적합 없음) |

**계보(lineage)**: v37(31K 기반) → v40(V4.0 대응) → **v42 = v40 어댑터 위에 균형 시드 970개 continue-learning**. 동봉 yaml은 v37 기반 대표 레시피이며, v42의 정확한 시드 구성·버전별 비교는 `T2C_V40_V41_V42_FINAL_REPORT_20260529.md` 참조. (v43은 어댑터 미재개 단독 학습으로 catastrophic forgetting 발생 → 폐기, v44는 continue-learning으로 계획)

---

## 4. 평가 (Evaluation)

**하니스** `eval/benchmark_t2c_v2.py` — 자체 제작 **232문항 / 23 카테고리**. 규칙 기반 8종 채점(쿼리 구조·RETURN/AS 정합·노드/엣지 화이트리스트·기대 엣지 적중·신규 엣지 정확도·쓰기 금지·거절 응답).

### 4.1 핵심 점수

| 구성 | 232문항 정확도 | 비고 |
|---|---|---|
| **v42 + Router** | **86.6% (201/232)** | 🏆 운영 표준 |
| v42 모델 단독 | 81.0% (188/232) | Router 없이 |
| (참고) GPT-4o zero-shot | 95.4% (152문항 legacy) | 기준선 |
| v3.7 신규 엣지 정확도 | 92.9% | 강점 |
| v3.6 신규 엣지 정확도 | 62.5% | 약점 |

동봉 결과: `eval/bench_v42_router_232.json`(86.6%), `eval/bench_v42_full_232.json`(모델 단독 81.0%).

### 4.2 ⚠️ 반드시 알아둘 점 — 모델 단독 vs +Router

**Router는 규칙 기반 사전 분기기**로, 모델이 약한 두 카테고리(GUARD=쓰기·프롬프트인젝션 차단, GENERAL=잡담 거절)를 LLM 호출 전에 처리한다. 그래서:
- **모델만 순수 테스트하면 general/guard 카테고리가 0%로 나오는 게 정상** (모델이 그 응답을 안 배움) → 전체 81%
- Router를 앞단에 두면 그 두 카테고리가 100% → 전체 86.6%
- 즉 **"모델 실력"과 "시스템(Router) 보정"을 분리해서 해석할 것.** 벤치마크의 `pre_route` 옵션으로 두 모드 모두 측정 가능.

### 4.3 약점 카테고리 (개선 대상)

| 카테고리 | v42+R | 성격 |
|---|---|---|
| meta_condition | 60% | 메타 필터 복합 조건 |
| 1hop_event | 60% | 이벤트(이체/통화) 1-hop |
| chain | 66.7% | 다단계 체인 |
| 1hop_object | 70% | 객체 1-hop |
| v3.6 신규 엣지 | 62.5% | 신규 관계 |

강점: 단일노드·v3.7 cluster/anonymous·multihop·edge_direction 등은 90~100%.

---

## 5. 서빙 (Quickstart)

**시스템 프롬프트가 필수다.** 이 모델은 `prompt/t2c_v37_system.txt`(온톨로지 스키마 주입)로 학습됐다. **동일 프롬프트를 system 메시지로 넣지 않으면 성능이 급락한다.**

검증된 서빙 레시피(상세는 `SERVING.md`):
```bash
# 검증 조합 (CUDA 12.x 드라이버 기준) — 온라인이면 pip 설치
pip install "vllm==0.6.3.post1" "transformers==4.46.3"

vllm serve ./model/qwen25-t2c-v42 \
  --served-model-name qwen25-t2c-v42 \
  --max-model-len 16384 --gpu-memory-utilization 0.9 \
  --chat-template ./model/qwen25-t2c-v42/chat_template.jinja
```
> `--chat-template` 명시 필수(모델에 분리 저장됨). 최신 GPU/드라이버면 최신 vLLM도 가능하나 위 조합이 안전값.

호출 예:
```bash
curl http://localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d '{
  "model": "qwen25-t2c-v42",
  "messages": [
    {"role":"system","content":"<prompt/t2c_v37_system.txt 내용 그대로>"},
    {"role":"user","content":"피의자2의 계좌를 보여줘"}
  ], "temperature": 0
}'
```

---

## 6. 이 번들의 구성

```
handoff_t2c_v42/
├── MODEL_CARD.md                      ← 이 문서
├── SERVING.md                         서빙 상세(설치·트러블슈팅·Router 적용)
├── NOTICE.md                          라이선스·데이터 민감도 고지
├── model/qwen25-t2c-v42/             병합 풀웨이트 15GB (4샤드+tokenizer+chat_template.jinja)
├── prompt/t2c_v37_system.txt         ⚠️ 시스템 프롬프트 (서빙 시 필수)
├── eval/
│   ├── benchmark_t2c_v2.py            벤치마크 하니스 (232문항)
│   ├── bench_v42_router_232.json      기준 결과 86.6% (+Router)
│   └── bench_v42_full_232.json        기준 결과 81.0% (모델 단독)
├── dataset/
│   ├── t2c_v37_train_msg.json         학습셋 (messages, 정본) — 재학습용
│   ├── t2c_v37_eval_msg.json          eval셋
│   └── train_t2c_lora_v3_qwen_v2.yaml 학습 하이퍼파라미터
└── SHA256SUMS                         무결성 (shasum -a 256 -c 로 검증)
```

## 7. 재현 (벤치마크 돌려보기)

```bash
# vLLM 서빙 중일 때
python eval/benchmark_t2c_v2.py --endpoint http://localhost:8000/v1 \
  --model qwen25-t2c-v42 --mode t2c_v37 --output my_result.json
# 기대: 모델 단독 ~81% / Router 적용 시 ~86.6% (SERVING.md §Router 참조)
```

## 8. 연락 / 출처

- 개발: CCOP 프로젝트 (Ian Kwon)
- 상세 문서(리포): `docs/T2C_V40_V41_V42_FINAL_REPORT_20260529.md`, `docs/TEXT2CYPHER_V37_EVAL_REPORT.md`, `docs/VLLM_SETUP_GUIDE.md`
- 모델 버전: v42 (2026-06-01 운영 표준 확정)
