# Text2Cypher v3.7 / v3.8 학습·통합 평가 보고서

**최초 작성일**: 2026-05-20
**갱신일**: 2026-05-21 (v38 결과 반영)
**대상 시스템**: CCOP v1.0 (Cybercrime Investigation Graph Platform)
**평가 모델**: Qwen2.5-7B + LoRA (`qwen25_t2c_v37_v2` → `qwen25_t2c_v38_v1`)
**평가 기준선**: GPT-4o (zero-shot, schema 인-컨텍스트 제공)

---

## 1. 요약 (Executive Summary)

### 1.1 핵심 지표 (v37 → v38)

| 영역 | 지표 | v37 | **v38** | Δ |
|---|---|---|---|---|
| **학습 목표** (v3.7 신규 패턴) | 정확도 | 100% | **100%** | 회귀 없음 ✅ |
| 전체 벤치마크 | 152문항 통과율 | 42.8% | **63.2%** | **+20.4p** |
| v3.6 신규 엣지 정확도 | – | 21.8% | **50.9%** | +29.1p |
| 약점 1hop_case | – | 33.3% | **86.7%** | +53.3p |
| 약점 1hop_person2person | – | 20.0% | **70.0%** | +50.0p |
| 운영 응답 시간 | CCOP API e2e | 1.4초 | **1.4초** | 유지 |
| 잡담 차단 | GENERAL 의도 | sLLM 호출 전 차단 (843ms) | 동일 | 유지 |
| 운영 안정성 | sLLM 실패 → GPT-4o 폴백 | 16초 내 자동 | 동일 | 유지 |
| **GPT-4o와 격차** | – | -52.6p | **-32.2p** | **절반 축소** |

### 1.2 핵심 결론
사이버범죄 수사 v3.7 온톨로지(진정서 군집·사이트 캠페인·불법중계기·성명불상 피의자)에 특화된 Text2Cypher 모델 학습 및 운영 통합을 완료. **v38 재학습으로 v3.6 약점 카테고리 정확도가 1.5~3배 향상**되었으며, v3.7 신규 패턴 100%는 그대로 유지되었다(회귀 없음). 사내 GPU에서 1.4초 응답 시간으로 외부 API 의존 없이 운영 가능하며, CCOP API end-to-end 성공률 100%를 달성했다. 잔여 약점(meta_condition·1hop_object·chain·threat_filter) 보강 시 80~85% 도달이 가능할 것으로 추정된다.

---

## 2. 프로젝트 배경

### 2.1 문제 정의
CCOP는 자연어 질의 → AgensGraph Cypher 변환 → 수사 그래프 시각화를 제공하는 플랫폼이다. 기존 v3.6 온톨로지는 23노드·52엣지 구조였으며, 진정서 군집/사이트 캠페인 등은 `clusters_with` O(n²) 엣지로 표현되어 그래프 알고리즘 효율이 낮았다.

### 2.2 v3.7 온톨로지 확장
| 신규 요소 | 역할 |
|---|---|
| `pt_cluster` (Case layer) | 진정서 군집 허브 노드 |
| `site_cluster` (Object layer) | 피싱 캠페인 허브 노드 (HTML SimHash 지문) |
| `vt_psn.is_anonymous` | 성명불상 피의자 플래그 |
| `vt_dev.dev_type='relay_station'` | 불법중계기 (IMEI 공유 전화 3대+) |
| `belongs_to_cluster`, `belongs_to_campaign`, `used_in_device` | 신규 엣지 3종 |
| Deprecated | `clusters_with` (O(n²) 엣지) |

총 노드/엣지: 23/52 → **25/53**

---

## 3. 학습 데이터셋 구축

### 3.1 데이터 전략 — 하이브리드 (규칙 + GPT-4o 증강)

#### v37 학습 데이터셋
| 단계 | 산출 | 비용 |
|---|---|---|
| 1-hop 규칙 시드 | 323개 | – |
| 1-hop GPT-4o-mini 증강 | 2,907개 | ~$0.06 |
| 멀티홉 시드 (2~4hop, shortestPath, var-hop) | 311개 | – |
| 멀티홉 증강 | 2,793개 | ~$0.05 |
| v5 기존 데이터 정제 (SQL→Native) | 25,526개 | – |
| **v37 합계** | **31,226 샘플** | ~**$0.11** |

#### v38 약점 보강 (신규)
| 카테고리 | 보강 시드 | 시드/통과율 효과 |
|---|---|---|
| 1hop_person2person | 499개 | 20% → 70% (+50p) |
| 1hop_case | 448개 | 33% → 87% (+53p) |
| 1hop_event | 391개 | 40% → 67% (+27p) |
| 1hop_object | 311개 | 40% → 60% (+20p) |
| 1hop_person | 274개 | 36% → 72% (+36p) |
| **v38 보강 합계** | **1,923개 유니크** | – |

**v38 학습 데이터 총 30,032 샘플** (v37 28,109 + 보강 1,923 = 6.8% 증가)

### 3.2 Hop 분포 (v37 기준)
| Hop | 전체 | v3.7 신규 | v3.7 비중 |
|---|---|---|---|
| 0-hop | 7,070 | 729 | 10.3% |
| 1-hop | 10,183 | 1,683 | 16.5% |
| 2-hop | 4,974 | 792 | 15.9% |
| 3-hop | 2,224 | 1,089 | 49.0% |
| 4-hop+ | 1,243 | 399 | 32.1% |
| var-hop | 468 | 468 | 100% |
| shortestPath | 5,064 | 540 | 10.7% |

### 3.3 Train/Eval 분할
- v37 Train 28,109 / Eval 3,117 (13 stratum × 10% 층화 분할)
- v38 Train 30,032 / Eval 3,117 (Eval은 v37 그대로 유지하여 비교 공정성 확보)

---

## 4. 학습 실행 이력

### 4.1 시도 비교
| | #1 EXAONE | #2 Qwen v37_v1 | #3 Qwen v37_v2 | **#4 Qwen v38_v1 (현행)** |
|---|---|---|---|---|
| 모델 | EXAONE-3.5-7.8B | Qwen2.5-7B | Qwen2.5-7B | Qwen2.5-7B |
| Custom code | 있음 | 없음 | 없음 | 없음 |
| 데이터 포맷 | ShareGPT | ShareGPT | **OpenAI messages** | OpenAI messages |
| 샘플 수 | 31,226 | 31,226 | 31,226 | **30,032** (v38 보강) |
| 학습 시간 | 1h 38m | 1h 30m | ~4h | **6h 5m** |
| eval_loss | 0.352 | 0.0002 (이상) | 정상 수렴 | **0.1159** (정상) |
| train_loss | – | – | – | **0.1205** (eval과 균형) |
| 추론 | 깨진 토큰 | v3.7 미적용 | ✅ 정상 | ✅ 정상 |
| 실패 지점 | transformers/EXAONE 호환성 | LF Loss 마스킹 오류 | – | – |

### 4.2 채택 설정 (`qwen25_t2c_v38_v1`)
- LoRA: rank 64, alpha 128, dropout 0.05
- Target modules: q/k/v/o_proj + gate/up/down_proj (7개)
- QLoRA 4bit, cutoff_len 1536, lr 1e-4 cosine
- Effective batch 16 (2×8 grad accum), 3 epochs, 5,634 steps (v38)
- 하드웨어: RTX 5090 (Blackwell, 32GB)

### 4.3 v38 학습 일정
- 2026-05-20 16:28 학습 시작 (PID 2348280)
- 2026-05-20 22:39 학습 완료 (eval 포함 6h 11m)
- 2026-05-21 09:30 머지 (1m)
- 2026-05-21 09:35 vLLM 서빙
- 2026-05-21 09:40 CCOP `.env` 갱신 + 벤치마크 시작

---

## 5. CCOP 시스템 통합

### 5.1 통합 아키텍처

```
[사용자 자연어]
      ↓
[ai_service.route_question] — intent 분류 (PATH/QUERY/REPORT/GENERAL)
      ↓
  ┌───┴───┐
  ▼       ▼
GENERAL  QUERY/PATH/REPORT
  ↓       ↓
즉시      [LangGraphAgent.synthesis_node]
차단        ├─ schema_info chunk 주입 (Phase 2-A)
            ├─ SLLM_ENDPOINT 설정 시: Qwen v38 호출 (학습 system prompt + schema + 자연어)
            │       ↓ (실패/timeout)
            └─ GPT-4o 자동 폴백 (16초 내)
                    ↓
            [Native Cypher → SQL Wrap 자동 변환]
                    ↓
            [ORDER BY alias 자동 변환] — AgensGraph 제약 우회
                    ↓
            [Cypher 사전 검증] (Phase 3-A) — 라벨/엣지 화이트리스트
                    ↓
            [GraphService.execute_cypher] → AgensGraph
                    ↓
            [0건 시 reflection 자동 재시도] (Phase 3-B)
                    ↓
            [elements (nodes/edges/scalar)] → Cytoscape
```

### 5.2 핵심 코드 패치 (v37 → v38 사이 추가)

| 파일 | 변경 | 도입 단계 |
|---|---|---|
| `app/services/langgraph_agent.py` | (1) sLLM 분기 + 학습 system 프롬프트 로드 | v37 |
| | (2) `_wrap_native_cypher` Native→SQL 변환 | v37 |
| | (3) `_rewrite_order_by_dot_access` ORDER BY alias 자동 | v37 |
| | (4) GENERAL 의도 사전 차단 | v37 후속 |
| | (5) reflection_node OpenAI 강제 | v37 후속 |
| | (6) sLLM 실패 시 GPT-4o 폴백 | v37 후속 |
| | (7) **Phase 2-A: synthesis_node에 schema_info user 메시지 주입** ⭐ | v37→v38 사이 |
| | (8) **Phase 3-A: `_validate_cypher_schema` 사전 검증** ⭐ | v37→v38 사이 |
| | (9) **Phase 3-B: 0건 결과 자동 재시도 강화** ⭐ | v37→v38 사이 |
| | (10) **버그 수정: GraphService local import 2건 제거** (`:310, :910`) | v38 직후 |
| `app/services/graph_service.py` | 스칼라 RETURN 결과를 `group='scalar'` element로 반환 | v37 |
| `app/services/ai_service.py` | sLLM 클라이언트 `max_retries=0, timeout=15s` | v37 후속 |
| `app/services/rdb_to_graph_service.py` | VLABEL/ELABEL 선언에 v3.7 추가 + `_postprocess_v37()` (6V-1/2/3) | v37 후속 |
| `app/services/prompts/t2c_v37_system.txt` | 학습 데이터 system 프롬프트 파일화 | v37 |
| `.env` | `SLLM_ENDPOINT=http://192.168.1.133:8000/v1` | v37 |
| | `SLLM_MODEL_NAME=qwen25_t2c_v38_v1` ⭐ | v38 |

### 5.3 운영 ETL 매핑 (rdb_to_graph_service.py:6V)
- **6V-1**: TB_PETTN_CLSTR 진정서 쌍 → union-find → `pt_cluster` 허브 + `belongs_to_cluster`
- **6V-2**: 동일 IMEI 3대+ 공유 `vt_telno` → `vt_dev(relay_station)` + `used_in_device`
- **6V-3**: `vt_psn.name`/`korn_flnm`이 빈 값 → `is_anonymous=true`
- **6V-4**: `site_cluster` (HTML SimHash) — RDB 스키마 확인 후 추가 예정

---

## 6. 성능 평가 결과

### 6.1 정확도 비교 — v37 vs v38 vs GPT-4o (152문항)

| 카테고리 | v37 (Qwen) | **v38 (Qwen)** | GPT-4o | v38 vs v37 | v38 vs GPT |
|---|---|---|---|---|---|
| **v37_cluster** | **100%** | **100%** | 75.0% | 동률 | **+25 우세** |
| **v37_anonymous** | **100%** | **100%** | 100% | 동률 | 동률 |
| **v37_multihop** | **100%** | **100%** | 100% | 동률 | 동률 |
| **v37_relay_station** | **100%** | **100%** | 100% | 동률 | 동률 |
| 단일노드 | 91.7% | 91.7% | 100% | 유지 | -8.3 |
| **1hop_case** | 33.3% | **86.7%** | 100% | **+53.3p** ⭐ | -13.3 |
| 1hop_event | 40.0% | 66.7% | 100% | +26.7p | -33.3 |
| 1hop_object | 40.0% | 60.0% | 100% | +20.0p | -40.0 |
| 1hop_person | 36.0% | 72.0% | 96.0% | +36.0p | -24.0 |
| **1hop_person2person** | 20.0% | **70.0%** | 70.0% | **+50.0p** ⭐ | **0 (동률)** |
| chain | 46.7% | 60.0% | 93.3% | +13.3p | -33.3 |
| meta_condition | 40.0% | 40.0% | 93.3% | 0 | -53.3 |
| threat_filter | 41.7% | 50.0% | 100% | +8.3p | -50.0 |
| general | 0% (CCOP 100%*) | 0% (CCOP 100%*) | 100% | – | – |
| guard | 0% (CCOP 100%*) | 0% (CCOP 100%*) | 100% | – | – |
| **전체** | 65/152 (42.8%) | **96/152 (63.2%)** | 145/152 (95.4%) | **+20.4p** | **-32.2p** |
| v3.6 신규 엣지 | 21.8% | 50.9% | 100% | +29.1p | -49.1 |
| v3.7 신규 엣지 | **100%** | **100%** | 100% | 동률 | 동률 |

(*) CCOP 통합 단계의 `route_question` GENERAL 분류로 sLLM 호출 전 차단됨

### 6.2 응답 시간 — CCOP API end-to-end

| 지표 | v37 (10케이스) | **v38 (10케이스)** |
|---|---|---|
| 전체 평균 | 1,295ms | **1,439ms** |
| p50 | 1,374ms | – |
| 수사 쿼리 평균 | 1,408ms | 1,500ms 안팎 |
| GENERAL 차단 평균 | 843ms | 813ms |
| 성공률 | 10/10 (100%) | **10/10 (100%)** |
| sLLM→GPT-4o 폴백 시 | 16초 | 16초 |

v38은 응답 시간이 100~200ms 정도 증가했으나(첫 호출 cold start + schema chunk 길이 증가) 1.5초대 안정.

### 6.3 v3.7 실데이터 조회 검증 (시드 데이터 기준)

| 쿼리 유형 | 시드 데이터 | v37 응답 | v38 응답 |
|---|---|---|---|
| `pt_cluster` 전체 | 3건 | 3건 ✅ | 3건 ✅ |
| `vt_dev(relay_station)` | 2건 | 2건 ✅ | 2건 ✅ |
| `belongs_to_cluster` 1-hop | 9건 | 3건 (필터) ✅ | **4건 (필터, 더 정확)** ✅ |
| `belongs_to_campaign` 1-hop | 9건 | 3건 (필터) ✅ | 3건 (필터) ✅ |
| `is_anonymous=true` | 35건 | 35건 ✅ | 35건 ✅ |
| `used_in_device` (중계기→전화) | 9건 | 4건 (필터) ✅ | 5건 (필터) ✅ |

### 6.4 단위 테스트
- `tests/test_t2c_v37_helpers.py` — **20문항** (v37 14 + Phase 3-A 6 추가)
  - `_wrap_native_cypher` 7개
  - `_rewrite_order_by_dot_access` 7개
  - `_validate_cypher_schema` 6개 ⭐
- **20/20 통과 (0.28초)**

### 6.5 약점 카테고리 시드 효율 분석 (v38)

| 카테고리 | 보강 시드 | 개선폭 | **샘플당 효율** | 평가 |
|---|---|---|---|---|
| 1hop_case | 448개 | +53.3p | **0.119p/시드** | ✅ 최고 효율 |
| 1hop_person | 274개 | +36.0p | **0.131p/시드** | ✅ |
| 1hop_person2person | 499개 | +50.0p | 0.100p/시드 | ✅ |
| 1hop_event | 391개 | +26.7p | 0.068p/시드 | △ |
| 1hop_object | 311개 | +20.0p | 0.064p/시드 | △ |

→ **person/case 패턴이 시드 효율 가장 높음**. v39 보강 시 동일 패턴 시드를 추가 투입할 가치.

---

## 7. 강점 / 약점 분석

### 7.1 강점 — 학습이 성공한 영역 (v38)
1. **v3.7 신규 어휘 완전 학습** — 4개 카테고리 모두 100% (`v37_cluster`는 GPT-4o 75%를 25p 차로 우세)
2. **v3.6 약점 카테고리 회복** — 1hop_case 87%, 1hop_person2person 70%, 1hop_person 72% 등 목표 달성
3. **자연어→Cypher 변환 일관성** — Native Cypher 출력 안정, ORDER BY alias 자동 변환, 스칼라 결과 처리
4. **응답 속도** — 1.4초 (사내 GPU, 외부 의존 없음)
5. **운영 안정성** — Schema 사전 검증, 0건 자동 재시도, sLLM 실패 시 GPT-4o 폴백
6. **회귀 없음** — v3.7 신규 4 카테고리 100% 그대로 유지

### 7.2 약점 — 후속 학습 권장 영역 (v39 대상)
1. **meta_condition 40%** — v38에서 변화 없음. 시드 보강 안 됐음. 우선 시드 대상.
2. **1hop_object 60%** — 절반만 회복. `hosts`, `belongs_to` 같은 일부 엣지 시드 부족.
3. **chain 60%** — 멀티홉 시드 추가 필요.
4. **threat_filter 50%** — 위협 점수/필터 조건 시드 부족.
5. **General/Guard 자체 학습 부재** — 학습 system 프롬프트에 거절 룰이 없어 모델 단독으론 0%. CCOP 통합에서 route_question 사전 차단으로 운영상 해결됨.

### 7.3 평가 조건 차이 (해석 시 주의)
- GPT-4o: SYSTEM_PROMPT(v3.6 기준) + 매 질문에 schema 힌트 user 메시지로 제공
- Qwen v38: 학습된 v3.7 system 프롬프트 + 동적 schema chunk (Phase 2-A)
- 즉 v38의 63.2%는 schema 힌트 활용한 결과이며, **fine-tuning 자체의 효과(+학습 데이터 보강)는 v37→v38 비교에서 +20.4p**로 측정됨

### 7.4 ROI 분석
- 추가 시드 1,923개 (학습 데이터 6.8% 증가)
- 정확도 **+20.4p (47.7% 상대 향상)**
- 학습 시간 6시간, 비용 $0
- GPT-4o 호출 비용 절감 효과 (1,000회/일 호출 시 ~$1/일 절감)

---

## 8. 운영 권고

### 8.1 현재 운영 구성 (이미 구현됨, v38 시점)
1. **1차 호출** — Qwen v38 sLLM (1.4초, 무료, 데이터 격리)
2. **Schema chunk 동적 주입** — 질문 라벨 기반 관련 스키마만 user 메시지에 포함
3. **GENERAL 사전 차단** — sLLM 호출 자체 skip (813ms)
4. **Cypher 사전 검증** — 라벨/엣지 화이트리스트 위반 시 reflection 유도
5. **0건 결과 자동 재시도** — 첫 시도에서 결과 0건이면 reflection_log 보강 후 재시도
6. **GPT-4o 자동 폴백** — sLLM connect/timeout 시 (16초 내)
7. **Reflection** — 항상 OpenAI gpt-4o-mini (학습 모델은 자연어 피드백 불가)
8. **AgensGraph 제약 자동 우회** — ORDER BY alias, 스칼라 결과 처리

### 8.2 운영 모니터링 지표
- sLLM 폴백 발생률 (학습 서버 가용성 지표)
- 평균 latency p50/p95
- intent 분포 (QUERY/PATH/REPORT/GENERAL)
- AgensGraph 실행 실패율
- Schema 검증 실패율 (모델 품질 지표)
- 0건 재시도 후 성공률

### 8.3 데이터 보안
- `.env`의 `OPENAI_API_KEY` 노출 점검 (git history 확인 권장)
- sLLM 사용 시 외부 전송 없음 — 폴백 발생 시에만 OpenAI 전송

---

## 9. 향후 작업 (우선순위)

### 🔴 High — 다음 학습 라운드 (v39)
- **잔여 약점 카테고리 시드 보강** (~1,500개)
  - meta_condition: 0 → 500개 (시드 신규)
  - 1hop_object: 311 → 500개 추가 (hosts/belongs_to/contains_file 패턴)
  - chain: 멀티홉 시드 300개 추가
  - threat_filter: 위협 점수/필터 시드 200개 추가
  - 예상 개선: 63.2% → **75~80%**
- **site_cluster ETL (6V-4)** — HTML SimHash 지문 RDB 테이블 명세 후 자동 클러스터링

### 🟡 Mid — Phase 2-B (Schema chunk fine-tuning)
- 학습 데이터의 user 메시지에 schema chunk prefix 포함하여 재학습
- 모델이 schema 인-컨텍스트를 학습 분포로 받아들이게 됨
- 예상 추가 효과: +5~10p (특히 1hop_object/event)
- 자동 클러스터링 배치 잡 (pt_cluster/site_cluster 주기 갱신)
- 벤치마크 카테고리 가중치 (운영 중요도 반영)
- 프론트엔드 scalar 결과 표시 패치

### 🟢 Low
- 운영 대시보드 (폴백률, latency p95, intent 분포 추적)
- AgensGraph 제약 학습 데이터 반영 (ORDER BY alias 패턴 명시 학습)
- LoRA rank 128 또는 self-consistency

---

## 10. 부록

### 10.1 산출 파일

| 파일 | 내용 |
|---|---|
| `results/bench_v37_full.json` | Qwen v37 152문항 벤치마크 상세 |
| `results/bench_v38_full.json` ⭐ | **Qwen v38 152문항 벤치마크 상세** |
| `results/bench_gpt4o_legacy.json` | GPT-4o 152문항 벤치마크 상세 |
| `results/latency_v37.json` | CCOP API end-to-end latency 10케이스 |
| `seed_v37_demo.py` | v3.7 데모 시드 스크립트 |
| `data/build_v38_weakness_seed.py` ⭐ | **v38 약점 보강 시드 빌더 (1,923개 출력)** |
| `data/t2c_v38_weakness_train_msg.json` ⭐ | **v38 보강 학습 데이터** |
| `train/retrain_v38.sh` ⭐ | **v38 재학습 통합 스크립트** |
| `app/services/prompts/t2c_v37_system.txt` | 학습 system 프롬프트 |
| `tests/test_t2c_v37_helpers.py` | 단위 테스트 20문항 (v37 14 + Phase 3-A 6) |

### 10.2 벤치마크 재현 명령

```bash
# Qwen v38 학습 모델 (t2c_v37 모드, 현행)
python benchmark_t2c_v2.py \
  --endpoint http://192.168.1.133:8000/v1 \
  --model qwen25_t2c_v38_v1 \
  --mode t2c_v37 \
  --graph tccop_graph_v6 \
  --output results/bench_v38_full.json

# Qwen v37 비교 (이전 모델)
python benchmark_t2c_v2.py \
  --endpoint http://192.168.1.133:8000/v1 \
  --model qwen25_t2c_v37_v2 \
  --mode t2c_v37 \
  --graph tccop_graph_v6 \
  --output results/bench_v37_full.json

# GPT-4o 기준선 (legacy 모드)
export OPENAI_API_KEY=$(grep '^OPENAI_API_KEY=' .env | cut -d= -f2-)
python benchmark_t2c_v2.py \
  --endpoint https://api.openai.com/v1 \
  --model gpt-4o \
  --mode legacy \
  --graph tccop_graph_v6 \
  --output results/bench_gpt4o_legacy.json
```

### 10.3 v38 재학습 재현 명령 (학습 서버)

```bash
cd /home/ai-kyw-dev/ccop_train/train
bash retrain_v38.sh start    # 전체 준비 + 학습 시작 (~6h)
# 학습 완료 후:
bash retrain_v38.sh merge    # LoRA 머지 (1m)
bash retrain_v38.sh serve    # vLLM 재시작 (10s)
```

### 10.4 누적 비용 / 시간

| 항목 | 비용 / 시간 |
|---|---|
| GPT-4o-mini 데이터 증강 (v37) | ~$0.11 |
| Qwen v37 학습 (RTX 5090) | ~4시간 |
| Qwen v38 학습 (RTX 5090) | ~6시간 |
| GPT-4o 벤치마크 152문항 ×2회 | ~$0.20 |
| v38 약점 보강 데이터 (규칙 기반) | $0 |
| 운영 단위 호출 | $0 (사내 GPU) |
| **총 누적 비용** | **~$0.31 + 사내 GPU 시간** |

---

## 11. 변경 이력

| 일자 | 변경 | 작성자 |
|---|---|---|
| 2026-05-20 | 최초 작성 (Qwen v37 기준) | CCOP 팀 |
| 2026-05-21 | v38 결과 반영 (정확도 42.8% → 63.2%, 약점 카테고리 1.5~3배 향상) | CCOP 팀 |

---

**보고서 끝**
