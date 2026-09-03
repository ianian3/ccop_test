# T2C v48 학습 시드 설계 — 70문항 벤치 실패 유형 기반

> **작성일**: 2026-09-03 · **근거**: `scripts/bench_integrated_t2c.py` 70문항(신규 38 확장) 실측
> **베이스라인**: v47 + 서버 보정(앵커·grounding·ALGO라우팅) = 기존 32문항 100% 유지, 신규 38문항에서 실패 수집
> **원칙**: v46 교훈 그대로 — **실행검증 시드 + 회귀믹스 필수**(v43 catastrophic forgetting·v45 소량실패 → v46 1185샘플+회귀믹스+epoch2 성공)

## 1. 실패 유형 분석 (v47 모델 한계 — 서버 보정 불가분)

### 유형 A · 스키마 환각 — 존재하지 않는 속성/값을 지어냄 (7건, 최다)
| 문항 | 환각 | 정답 스키마 |
|---|---|---|
| H03 통화 4월 | `a.call_start` | `contacted.first_dt` |
| K02 이체 많이 받은 | `b.recvd_amt` | count(transferred_to) 집계 |
| L01 기업+3차집금 | `is_third_party` · `bank_nm='기업은행'` | `tier='3차집금'` · `bank_nm='기업'` |
| M01 피의자 전부 | `p.is_suspect` | `(p)-[:suspect_in]->(c)` |
| M08 해외송금 수취 | `b.country` | `tier='4차 해외송금 수취'` |
| N03 증거등급 A | `p.evidence_grade` | `p.evid_grade` |
| N01 (해소) | — | ep_count 숫자화로 데이터측 해결 |

### 유형 B · EP9/10 신규 스키마 미지 (3건)
- M03·M04: `accomplice_of`(데이터 0건) 사용 — **suspect_in·performed_by·vt_movement·role='주범'을 모름** (v47 학습 시점에 없던 스키마)
- M05: 무관 전화번호 환각(`010-1234-5678`) — 조정모→owns_phone/uses_id 패턴 미지

### 유형 C · 시간 속성/필터 미지 (3건)
- H02: 방향 반전 + 날짜 속성 부재 / H03: `call_start` 환각 / H04: `p.out_date` 환각
- 정답 패턴: `WHERE e.first_dlng_dt >= '2017-03-21'` · `first_dt STARTS WITH '2017-04'` · `(m:vt_movement{mov_dt})-[:performed_by]->(p)`

### (해소됨 — 모델 무관)
- N01 ep_count 문자열 저장 → **build 숫자화 + 일괄 변환 완료**
- N02·N04 ALGO 라우팅 정답을 벤치가 오판 → **채점 보정 완료**

## 2. v48 시드 스펙

| 카테고리 | 시드 수 | 내용 |
|---|---|---|
| A-속성 정합 | 120 | 실스키마 속성 전수(evid_grade·tier·first_dlng_dt·first_dt·mov_dt·ep_count·role·bank_nm 실값) — 환각 속성별 대조쌍 포함 |
| B-신규 서사 | 100 | suspect_in·performed_by·vt_movement·uses_id·same_as — 피의자/출국/주범/해외송금 표현 변형 |
| C-시간 필터 | 80 | 연·월·일·기간·이후/이전 × 이체/통화/출입국 (STARTS WITH·범위 비교) |
| D-집계 고급 | 60 | 관계 count 집계(이체 수취 상위)·그룹핑·상위N (`WITH … ORDER BY` 패턴) |
| E-다중 조건 | 40 | AND 결합(은행값+tier, 기간+기간) |
| **회귀믹스** | **300+** | v47 기존 645건에서 층화 샘플 — 기존 32문항 영역(단순·1hop·집계·방향·가드) 보존 |
| 합계 | **~700** | v46(1,185)과 유사 규모 · epoch 2 |

## 3. 생성·학습 방법 (기존 검증 파이프라인 재사용)
1. **시드 생성**: 실행검증 방식 — 질문 변형(GPT-4o 증강) → 정답 Cypher는 **통합 그래프에서 실행해 비공집합 확인된 것만** 채택 (`scripts/generate_reification_sft.py` 패턴 확장)
2. **회귀믹스**: v47 학습셋(645) 층화 샘플 300+ 혼합 — v43 망각 방지
3. **학습**: 엘리스 lf_venv3 레시피 그대로(bf16 LoRA r32/α64 · CUDA_VISIBLE_DEVICES=0 강제 · setsid) — `reference_elice_server.md` 2026-08-13 항목
4. **평가 게이트**: ①70문항 벤치 ≥95% ②232벤치(tccop) 회귀 ≥ v47 수준 ③가드 100% — 셋 다 통과 시 v48 채택

## 4. 실측 경과
- 1차(확장 직후): 56/70(80.0%) — 실패 14
- 데이터·채점 수정 후(ep_count 숫자화·ALGO 채점 보정): **59/70(84.3%)** — 잔여 11 = 순수 모델 갭
- **시드 생성 실행(2026-09-03)**: 후보 105 → **실행검증 채택 93**(A30·B35·C13·D7·E8, 탈락 12는 데이터 부재로 정당)
  → 엘리스 병합: train **385**(회귀 300 층화 + 신규 85) · eval 72(+신규 8) → **v48 LoRA 학습(GPU1, 4ep)**

## (구) 현재 성능 (참고 — 서버 보정 포함 운영 수치)
- 70문항: 데이터/채점 수정 후 재측정치는 `results/bench_integrated_t2c.json` 참조 (기존 32문항 영역 100% 유지)
- 실패는 전부 신규 확장 영역 = **v47 학습 범위 밖** — 서버 보정(앵커·값grounding·ALGO라우팅)이 커버 못 하는 순수 모델 지식 갭
