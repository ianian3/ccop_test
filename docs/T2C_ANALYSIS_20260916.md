# Text2Cypher 기능 분석 — 2026-09-16

> 코드 실측 기준(파일:행 인용). 대상: `app/services/langgraph_agent.py`(2,039행) 중심의
> 자연어 → Cypher → AgensGraph 실행 → 시각화 전 구간.

---

## 1. 한눈에 보는 구조

```
사용자 질문
  │
  ├─ POST /api/v1/query            (routes_api.py:~50, UI 챗)   ← temporal_continuity 플래그
  ├─ POST /api/v1/agentic-query    (routes_api.py:236, API 키 필수)
  └─ InvestigationSession          (langgraph_agent.py:1950, 수사 세션 — 대화 맥락·스냅샷)
  ▼
LangGraph 상태기계 (8노드, :1826~1879)
  START → router ─┬→ data_view (일반대화 등 즉시 종결)
                  ├→ path_finding (경로탐색 의도) ─ 실패 시 QUERY 로 fallback
                  └→ context_retrieval → schema_fetching → synthesis → execution
                                                              ▲            │
                                                              └ reflection ┘ (오류 시 재합성 루프)
                                                                            ▼
                                                                        data_view → END
```

응답에는 Cypher·결과 요소·`model_rows`/`anchor_added`(평가 진실값)·경고·노드별 소요시간
(`metrics`)·감사 로그(`_write_audit_log`, :1884)가 포함된다.

## 2. 노드별 역할 (langgraph_agent.py)

| 노드 | 행 | 역할 |
|---|---|---|
| `router_node` | :622 | 의도 분류(PATH/QUERY/GENERAL) — `AIService.route_question` 위임. REPORT 는 폐지되어 QUERY 로 강제 매핑 |
| `path_finding_node` | :667 | 두 엔티티 간 최단경로 의도 전용. 실패 시 QUERY 흐름으로 폴백 |
| `context_retrieval_node` | :709 | Vector RAG 로 유사 질의·예시 검색 |
| `schema_fetching_node` | :808 | 그래프 실스키마 조회 + 예측 라벨로 축약(`_filter_schema_by_labels` :780) |
| `synthesis_node` | :1042 | **Cypher 생성** — 모델 선택·프롬프트 분기·가드 |
| `execution_node` | :1280 | **실행 + 보정 계층**(§4) — 이 기능의 실질 핵심 |
| `reflection_node` | :1580 | 오류 분석 후 재생성 지시(항상 GPT 계열 사용) |
| `data_view_node` | :1642 | 응답 조립 — 시각화 요소·경고·계측 |

## 3. 모델 전략 (synthesis_node)

**3계층 선택** (:1067~1205):

1. **sLLM 우선** — `SLLM_ENDPOINT` 설정 + 학습 프롬프트 존재 시. 현행 **v48**
   (Qwen2.5-Coder-7B LoRA r32/α64 bf16, 엘리스 vLLM 서빙, 실행검증 시드 645건 학습)
2. **그래프별 system prompt 분기** (`_system_prompt_for` :373) — 학습·추론 프롬프트 정합이
   1차 성능 결정 요인(정합화만으로 +2.8%p 실증):
   - `ccop_ep_integrated`·`ccop_test_graph` → `prompts/t2c_integrated_system.txt`(3,988B —
     라벨 12·경로 29·실값 카탈로그 platform/tier/bank_nm/role 포함)
   - 그 외 → `t2c_v37_system.txt`(1,775B) / `t2c_v47_system.txt`(1,016B)
3. **폴백** — sLLM 미설정 시 GPT-4o(`OPENAI_API_KEY`)

**reflection·router 는 항상 OpenAI 우선** (reflection :1584 `gpt-4o-mini` / router
`AIService._get_router_client`). sLLM 은 Cypher 생성 특화라 오류 분석·의도 분류는
GPT 에 맡긴다는 설계.

> ⚠ **정정(2026-09-16 실측)**: OpenAI 계층이 죽으면(폐쇄망 또는 크레딧 소진) 영향이
> reflection 뿐 아니라 **① 의도 분류(router)** 와 **② synthesis 폴백** 까지 3곳에 미친다.
> - router 는 규칙(`fast`) 폴백이 있으나 정확도 열위 — "대한민국 수도는?" 을 QUERY 로
>   오분류(GENERAL 판정 실패)해 무효 Cypher 를 생성함을 실측.
> - synthesis 폴백은 키가 실제로 **429 크레딧 소진** 상태라 현재 무효(§7-R1).
> - 결국 sLLM 만으로는 **의도 분류·오류 재시도·생성 폴백이 모두 반쪽**. 폐쇄망 납품에서는
>   이 3계층의 sLLM/규칙 대체가 함께 필요하다.

## 4. 방어·보정 계층 (이 기능의 차별점)

### 실행 전 (synthesis→execution)
| 장치 | 행 | 동작 |
|---|---|---|
| 쓰기 금지 가드 | :1231 | `DELETE/SET/REMOVE/MERGE/DROP/CREATE/DETACH` 감지 → "보안 정책 위반" 즉시 종결(재시도 없음). 벤치 가드 문항 차단률 100% |
| 스키마 검증 | :883 | 존재하지 않는 라벨·엣지 사용 시 실행 생략 → reflection 유도(`_suggest_corrections` 로 근사 라벨 제안) |
| 비-Cypher 응답 감지 | :1296 | `MATCH/RETURN/SELECT` 부재 → GENERAL_CHAT 종결 (sLLM 이 프리픽스 없이 일반 문장을 낸 케이스, 벤치 F04) |
| **이중 방어** | graph_service.py:1068 | `execute_cypher(allow_write=False)` 기본 + 쓰기 허용 그래프 화이트리스트(`WRITABLE_GRAPHS` = ccop_test_graph 1종) — 에이전트 가드가 뚫려도 DB 계층에서 차단 |

### 실행 시 자동 재작성 (execution_node 내 순서)
1. **tier 실값 치환** (:1329) — '1차사기수취' 등 공백 변형을 DB 실값으로
2. **경로 내 맵리터럴 → WHERE 이동** (:1354) — 위치 키(`bsst_addr`·`place_name` 등)는
   CONTAINS 로 전환(부분일치)
3. **ORDER BY alias 재작성** (:924) · **스칼라 dot-access 재작성** (:968) — AgensGraph 방언 대응
4. **엔진 크래시 회피** (:1444) — '경로 순회+비앵커 속성조건' 형태를 실행 전 정적 탐지
   (`_crashy_traversal_cond` :104) → 조건 노드를 첫 MATCH 로 승격하는 동등 재작성
   (`_anchor_first_rewrite` :53). 운영 DB(2.16-devel) segfault 결함의 대증 방어

### 0건 시 자동 복구 (:1481~)
1. `_ungrounded_literals`(:341) — **질문에도 DB에도 없는 리터럴** 지목(값 환각 탐지)
2. `_anchor_neighborhood`(:243) — 앵커 노드의 실제 이웃 분포를 DB 실측
3. `_bridge_two_hop`(:139) — 방향 반전 → 중간 라벨 경유 2-hop 재합성(자기참조 배제,
   앵커·경로 포함 반환)
4. 재합성도 0건이면 **결과를 꾸미지 않고** `zero_notice` 경고로 명시(:1721)

### 계측 분리 (:1713~1778) — 평가 신뢰성
`model_rows`(모델 Cypher 자체 결과)와 `anchor_added`(시연용 보강)를 분리 반환.
보강이 실패를 가려 88%로 보이던 벤치가 실제 81%였던 사고의 재발 방지 장치.

## 5. 재시도 루프 (:1801)

- 오류 시 `error_count < max_retries+1`(기본 1회) 동안 reflection → synthesis 재합성
- GENERAL_CHAT·보안 위반은 **재시도 없이 즉시 종결** (가드 우회 시도 차단)
- config 스위치: `use_router`·`use_reflection`·`max_retries`·`use_dynamic_schema`·
  `use_relation_fix`·`temporal_continuity`(UI 체크박스 연동)

## 6. 학습·평가 체계

| 자산 | 내용 |
|---|---|
| 학습 레시피 | LLaMA-Factory, 엘리스 A100(lf_venv3: torch2.3.1+cu121, bf16 LoRA, 단일 GPU) |
| 시드 생성 | `scripts/`(v48 시드 설계 `docs/T2C_V48_SEED_DESIGN.md`) — **실행검증**: 생성 Cypher 를 실 DB 에서 돌려 통과분만 학습 데이터화 |
| 회귀 벤치 | `bench_integrated_t2c.py`(276행) — 232문항 + `integrity_snapshot()`(벤치 쓰기 질의의 데이터 변조 탐지) |
| 홀드아웃 | `bench_integrated_100.py` — 실무형 100문항, 채점은 `model_rows` 기준 |
| 채택 게이트 | 3중: 신규 70문항 + 232 회귀(망각 검사) + 가드 문항 100% |

**모델 이력**: v37~39(72.4%) → v42(86.6%) → v46(88.8%) → v47(앱 연결) →
**v48 채택**(2026-09-03: 70문항 68/70=97.1% · 232 회귀 −2 · 가드 100%) → 홀드아웃 93%.
232 하네스 절대값은 상대비교용(앵커 문항 구성 특성).

## 7. 강점·리스크 평가

**강점**
- 실행검증 학습 + 프롬프트 정합 원칙(사실은 넣되 절차 지시는 금지 — 절차 넣으면 91→84% 회귀 실증)
- 보정 계층이 모델 한계를 구조적으로 흡수(방언·크래시·0건·환각)
- 평가 무결성 장치로 성능 수치의 신뢰성 확보(거짓통과 7건 적발 이력)
- 쓰기 차단 이중화(에이전트 키워드 가드 + DB 계층 read-only)

**리스크·약점**
| # | 항목 | 내용 |
|---|---|---|
| 1 | **OpenAI 3계층 의존 → 해소(2026-09-16)** | router·reflection·synthesis 폴백이 OpenAI 우선이던 문제. **규칙 대체 완료**: router = `_rule_classify`(의도·키워드·레이블·PATH 규칙화, 20문항 의도 100%) · reflection = 결정론 진단(근사 라벨·앵커 실측 이웃) 피드백 폴백 · synthesis 폴백 = 학습 프롬프트 통일. 폐쇄망(OPENAI 제거) E2E 4경로 + 2회 재시도 루프 실동작 검증. 커밋 210078b·후속 |
| 1b | 폴백 무효화 결함(수정됨) | `AgentState` 에 `error_message` 필드 부재로 LangGraph 가 노드 반환을 폐기 → 폴백 실패·가드 상태가 전파 안 되던 버그. 2026-09-16 수정(커밋 8d1fa72). 부수로 GUARD_BLOCK 이 execution 에서 '쿼리 없음'에 덮여 쓰기 차단이 새던 잠재결함도 수정 |
| 1c | 잔여 | 규칙 라우터·reflection 은 LLM 대비 정밀도 열위(키워드·의도 미묘 케이스). 온라인은 여전히 LLM 우선이라 무영향. 폐쇄망 정밀도는 v49 규칙 확장으로 개선 여지 |
| 2 | 크래시 가드는 대증요법 | 근본 조치는 운영 DB 안정판 교체(요청 대기). 가드 패턴에 없는 새 크래시 형태 위험 잔존 |
| 3 | 라우터 오분류 | `AIService.route_question` 의존 — PATH/QUERY 오판 시 흐름 자체가 어긋남(폴백은 있음) |
| 4 | max_retries=1 | 복합 오류에서 1회 성찰로 부족할 수 있음(비용 균형 판단이나 설정 노출 필요) |
| 5 | v49 어휘 갭 | registered_to 방향 · role vs tier 혼동 · uses_ip 환각 · `WHERE n:label` 문법 · count 누락 (시드 후보 목록 보유) |
| 6 | 프롬프트 3종 병존 | v37/v47/integrated — 그래프 추가 시 분기 관리 부담. 신규 그래프는 기본값(v37)으로 떨어짐 |

## 8. 개선 우선순위 제안

1. **폐쇄망 reflection 대체** — 스키마 검증 실패·문법 오류의 규칙 기반 교정(이미 있는
   `_suggest_corrections` 확장)으로 GPT 없이 1차 재시도 가능하게
2. v49 시드에 어휘 갭 반영(§7-5) — 시드 설계 문서 기반
3. 신규 그래프 온보딩 절차 문서화 — system prompt 작성 규칙(실값 카탈로그 필수,
   절차 지시 금지)과 `_system_prompt_for` 등록
4. 크래시 형태 자동 학습 가드(특허 아이디어 4와 연계) — 발생 시 패턴 자동 일반화
