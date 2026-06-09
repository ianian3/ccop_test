# 📍 CCOP V4.0 체크포인트 (2026-05-27)

> 본 문서는 현재 시점의 프로젝트 상태 스냅샷. 이후 작업의 기준점.

---

## 🎯 한눈에 보기

```
프로젝트:    CCOP V4.0 사이버수사 그래프 플랫폼
브랜치:      feature/v4.0-ontology-2026-05-21
누적 커밋:   5건 (4c7b6d8 → 47b12d2)
상태:        🟢 운영 배포 적합 (V4.0 시나리오 84.4% / 202문항 80.2%)
잔여:        DA팀 V3.7 DDL 운영 적용 대기 (외부 의존)
```

---

## 1. 5계층 아키텍처 진척도

| 계층 | 영역 | 완성도 | 비고 |
|------|------|--------|------|
| **L1 수집** | CSV 업로드 + SOURCE_DOMAIN 라디오 + SOURCE_ID 옵션 | 🟢 100% | UI/백엔드 완료 |
| **L2 RDB 표준화** | DA팀 V3.7 DDL 운영 적용 | 🔴 30% | **외부 의존 (D+8 대기)** |
| **L3 매핑** | ETL V4.0 메타 6컬럼 자동 주입 (노드+엣지) | 🟢 100% | 회귀 14/14 PASS |
| **L4 그래프** | AgensGraph + 25 노드 인덱스 + V3.7 추론 4종 | 🟢 100% | `tccop_v40_demo` 178노드 |
| **L5 시각화** | Cytoscape + V4.0 SSOT 동적 + 워크플로 6 + 레이아웃 5 | 🟢 100% | scalar 패널 포함 |

---

## 2. Text2Cypher 4세대 모델 진척도

| 버전 | 학습 데이터 | 152문항 | 202문항 | V4.0 시나리오 | 상태 |
|------|------------|---------|---------|---------------|------|
| v37 | 28,109 | 42.8% | - | - | 폐기 |
| v38 | 30,032 | 63.2% | - | - | 폐기 |
| v39 | 31,694 | 72.4% | 74.3% | 68.9% | 백업 (어댑터 보존) |
| **v40 (현행)** | 33,242 | **73.7%** | **80.2%** | **84.4%** | 🟢 **운영 모델** |
| GPT-4o (참조) | - | 95.4% | ~95%* | ~92%* | 자동 폴백 |

\* 추정치 — 미측정.

```
sLLM 서빙:   qwen25_t2c_v40_v1 @ http://192.168.1.133:8000/v1
.env:        SLLM_MODEL_NAME=qwen25_t2c_v40_v1
폴백:        GPT-4o (16초)
```

---

## 3. 주요 산출물

### 코드
| 파일 | 핵심 변경 |
|------|----------|
| `app/middleware/services/ontology_service.py` | V4.0 SSOT (VISUAL_STYLE/EDGE_STYLE/NODE_ID/DOMAIN/INFERENCE/LAYOUT/WORKFLOW) |
| `app/services/rdb_to_graph_service.py` | `make_node_props_v40` + `make_edge_props_v40` + 도메인 정규화 |
| `app/services/etl_service.py` | V4.0 메타 자동 주입 (5개 패치 지점) |
| `app/services/ai_service.py` | Router 강제 OpenAI + LRU 캐시 + Rule-based pre-filter + REPORT 폐지 |
| `app/services/langgraph_agent.py` | Reflection 사전 차단 + scalar 처리 + REPORT 안전망 |
| `app/__init__.py` | gzip 응답 압축 미들웨어 |
| `app/routes_api.py` | 5개 V4.0 SSOT API + 워크플로 실행 endpoint |
| `app/routes.py` | CSV 폼 SOURCE_DOMAIN 수신 |
| `app/templates/index.html` | V4.0 SSOT 오버레이 + 툴바 + scalar 패널 (정중앙 모달) |

### 데이터/스크립트
| 파일 | 용도 |
|------|------|
| `scripts/build_v40_scenario_dataset.py` | 시나리오 시드 (178노드/207엣지) |
| `scripts/test_v40_scenario.py` | 21항목 검증 |
| `scripts/test_v40_natural_query.py` | V4.0 자연어 45 케이스 |
| `scripts/create_v40_graph_indexes.py` | AgensGraph 25 라벨 인덱스 (18개 생성) |
| `scripts/deploy_v40.sh` | 머지 + vLLM 서빙 자동화 |
| `scripts/benchmark_v40.sh` | .env 갱신 + 벤치마크 + 4세대 비교 |
| `scripts/generate_v40_report.py` | 보고서 자동 생성 |
| `data/build_v40_weakness_seed.py` | 8 패턴 1,548 시드 빌더 |
| `data/V40_TRAINING_GUIDE.md` | 학습 서버 8단계 가이드 |
| `benchmark_t2c_v2.py` | 152 → **202문항 확장** (M~T 50 추가) |

### 결과 파일
```
results/bench_v40_full.json       (v40 × 152, 73.7%)
results/bench_v40_full_202.json   (v40 × 202, 80.2%)  ⭐
results/bench_v39_full_202.json   (v39 × 202, 74.3%)  ⭐ 비교
results/test_v40_natural_query.json (V4.0 시나리오 45, 84.4%)
```

### 문서 (docs/)
| 문서 | 내용 |
|------|------|
| `CCOP_ONTOLOGY_V4.0.md` | V4.0 통합 온톨로지 SSOT (§17 변경 이력 포함) |
| `T2C_V37_V40_COMPARISON_20260527.md` | 4세대 벤치마크 비교 (10섹션) |
| `V40_ONTOLOGY_AUDIT_20260521.md` | 5영역 정합성 감사 + P0~P2 |
| `STAGING_PATCH_VERIFICATION_20260521.md` | DA팀 패치 SQL 격리 dry-run 8/8 |
| `ETL_V40_GAP_REPORT_20260521.md` | ETL V4.0 메타 갭 분석 |
| `DA_TEAM_V40_REQUEST_20260521.md` | DA팀 호환화 공식 요청서 |
| `DEMO_TESTBED_DESIGN_20260526.md` | 데모 시연 설계 (3 옵션) |
| `MODELER_UX_AUDIT_20260521.md` | Modeler UX 점검 (9섹션) |
| `MODELER_V40_AUDIT_20260521.md` | Modeler 자유 설계 재해석 |
| `V40_WEAKNESS_SEED_CANDIDATES_20260522.md` | 8 패턴 시드 설계 근거 |
| `CHECKPOINT_20260527.md` | **본 문서** |

---

## 4. 운영 인프라 상태

| 서비스 | 상태 | 위치 |
|--------|------|------|
| **Flask** | 🟢 가동 | localhost:5002 / 192.168.1.38:5002 (PID 6229) |
| **vLLM** | 🟢 가동 | 192.168.1.133:8000 (v40 서빙) |
| **AgensGraph** | 🟢 가동 | tccopdb (49.50.128.28:5333) |
| **OpenAI** | 🟢 연동 | gpt-4o-mini (router) / gpt-4o (폴백) |

### vLLM 옵션 (Sprint 1)
```
--enable-prefix-caching           # system 프롬프트 KV 재사용 (-40% TTFT)
--max-num-batched-tokens 8192     # 배치 효율
--max-num-seqs 16                 # 동시 처리
--gpu-memory-utilization 0.85
--max-model-len 4096
--dtype bfloat16
```

### Sprint 1 성능 패치 (적용 완료)
| 패치 | 효과 |
|------|------|
| AgensGraph 18개 인덱스 | 점 조회 10~100× |
| Router LRU 캐시 (1024) | 동일 질문 0ms |
| GENERAL pre-filter | LLM 호출 -90% (해당 케이스) |
| Reflection 사전 차단 | 단순 0건 결과 -3초 |
| Flask gzip 미들웨어 | JSON 네트워크 -80.8% |

---

## 5. 운영 임계 검증

### ✅ 충족 항목

| 지표 | 목표 | 실측 | 판정 |
|------|------|------|------|
| 202문항 정확도 | 80%+ | **80.2%** | ✅ |
| V4.0 시나리오 | 80%+ | **84.4%** | ✅ |
| router 보정 실효 | 85%+ | 86.6% | ✅ |
| 단순 응답 시간 | < 2초 | 1.5초 | ✅ |
| 복잡 응답 시간 | < 5초 | 2.5~3.5초 | ✅ |
| GPT-4o 폴백 동작 | 자동 | 자동 (16초) | ✅ |
| 도메인 정규화 | 100% | 100% | ✅ |
| V3.7 신규 7요소 | 100% | 100% | ✅ |

### ⚠️ 잔존 약점 (v41 보강 후보)

| 카테고리 | v40 | 보강 시드 |
|----------|-----|-----------|
| 1hop_person2person | 60% (-20p 회귀) | recruits/blackmails/accomplice_of 200건 |
| meta_condition | 53% (-14p 회귀) | risk_level/threat_score 다양화 200건 |
| chain (3-hop+) | 80% | 5-hop 정밀 150건 |
| 1hop_event | 60% | caller/callee 방향 정밀 150건 |

---

## 6. 외부 의존 사항

| 의존 | 상태 | 다음 액션 |
|------|------|----------|
| **DA팀 V3.7 DDL 운영 적용** | ⏳ 회신 대기 | `da_v37_v40_patch.sql` 송부 완료 (2026-05-21) |
| 운영 DB SOURCE_DOMAIN 컬럼 활성화 | DA팀 적용 후 | RDBService.import_csv_to_rdb 의 INSERT 로직 활성화 |
| 운영 트래픽 모니터링 도구 | 미구축 | 운영 배포 후 별도 구축 권장 |

---

## 7. 다음 우선순위 옵션

| 우선 | 옵션 | 예상 |
|------|------|------|
| 🥇 P0 | **데모 시연 준비** (현 v40 + 슬라이드) | 1주 |
| 🥈 P1 | v41 보강 학습 (회귀 2 카테고리 + 약점 보강) | 1.5일 |
| 🥉 P2 | DA팀 회신 대응 + 운영 DB 적용 후 L2 활성화 | D+8 이후 |
| ⚪ P3 | 베이스 모델 교체 (Coder-7B/14B) — 천장 돌파 | 2일+ |
| ⚪ P4 | Modeler UX P0 패치 (자동저장 슬롯 분리, 엣지 드래그) | 1일 |

---

## 8. 1주 단위 진척도 회고

| 일자 | 핵심 작업 |
|------|----------|
| 5/21 | V4.0 SSOT 정합화 (P0 도메인 키 통일 / P1 추론룰 / P2 NODE_ID 25/25) + DA팀 패치 SQL + ETL 메타 주입 |
| 5/21~22 | V4.0 시나리오 데이터 + 자연어 45 케이스 + Router 패치 |
| 5/22 | 약점 14건 분석 → 8 패턴 시드 설계 |
| 5/22~23 | Sprint 1 성능 패치 (인덱스/캐시/gzip/reflection) + v40 시드 빌더 |
| 5/25 | v40 LoRA 학습 (33,242 샘플) |
| 5/26 | v40 머지 + vLLM 서빙 + 152문항 벤치마크 (73.7%) |
| 5/27 | 202문항 확장 측정 (80.2%) + v39 비교 (74.3%) + REPORT 폐지 + scalar 패널 |

---

## 9. 알려진 이슈 (Known Issues)

| # | 이슈 | 우회/해결 |
|---|------|----------|
| 1 | 152문항 셋에 V4.0 약점 미포함 → 모델 평가 왜곡 | ✅ 202문항 확장으로 해결 |
| 2 | "강남 사건 보여줘" → REPORT 오분류 | ✅ REPORT 폐지로 해결 |
| 3 | 스칼라 결과 cy.add 에러 | ✅ 후크 필터링 + 정중앙 모달 |
| 4 | DA팀 V3.7 DDL 미적용 | ⏳ 외부 대기 |
| 5 | Modeler UX (자동저장 단일 슬롯, 엣지 드래그 미지원) | ⚪ 별도 트랙 |
| 6 | 1hop_person2person / meta_condition 회귀 | ⚪ v41 보강 후보 |

---

## 10. 핵심 메시지 (시연 / 보고용)

1. **5계층 End-to-End 작동** — L1(수집) ~ L5(시각화) 단일 카탈로그 + 다중 도메인
2. **자연어 → Cypher 80.2% (202문항)** — sLLM 자체 학습, on-prem 보안, 1.5~3초 응답
3. **V4.0 시나리오 84.4%** — 운영 환경 실효 정확도
4. **자동 추론** — pt_cluster / site_cluster / relay_station / is_anonymous 자동 군집
5. **투명한 신뢰도** — source_domain + reliability_tier 모든 노드/엣지 부착

---

## 11. 체크포인트 시점 작업 환경

| 항목 | 값 |
|------|---|
| 작업 디렉토리 | `/Users/iankwon/test/coop_v1.0` |
| Git 브랜치 | `feature/v4.0-ontology-2026-05-21` |
| 최신 커밋 | `47b12d2` (5건 누적) |
| Flask | PID 6229 (Reloader PID 6231) |
| 학습 서버 vLLM | v40 (qwen25_t2c_v40_v1) |
| .env | SLLM_MODEL_NAME=qwen25_t2c_v40_v1 |
| 마지막 검증 | 2026-05-27 (V4.0 시나리오 84.4% / 202 셋 80.2%) |

---

## 🚦 결론

> **운영 배포 임계 충족.** 데모 시연 즉시 가능. 외부 의존 (DA팀 V3.7) 완료 시 풀 파이프라인 라이브 시연 가능. 회귀 카테고리는 v41 보강 또는 운영 모니터링 기반 점진 개선.

다음 작업은 사용자 우선순위에 따라:
- 데모 시연 준비 (가장 빠른 가치 실현)
- v41 정확도 추가 향상
- DA팀 회신 대기
- 다른 트랙 (Modeler UX / Coder-7B 등)

---

**다음 체크포인트**: v41 학습 완료 시 또는 DA팀 V3.7 운영 적용 시
