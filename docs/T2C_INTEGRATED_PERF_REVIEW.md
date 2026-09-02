# Text2Cypher 통합 그래프 성능 검토 — 리서치 검증·보완

> **작성일**: 2026-09-02
> **대상**: `ccop_ep_integrated` (24,287노드 · 25,573엣지 · 22 노드타입) + sLLM v47(Qwen2.5-Coder-7B LoRA)
> **한 줄**: 2025~26 논문의 3대 기법(스키마 필터링·grounding·반복 정제)은 **이미 코드에 구현·실측(+5.5p)돼 있다**.
> 진짜 갭은 기법이 아니라 **① 학습-서빙 스키마 불일치 ② 통합 그래프 전용 벤치 부재**다.

---

## 1. 리서치 요약 (2025~2026)

| 기법 | 핵심 | 출처 |
|---|---|---|
| 동적 스키마 pruning | 질문 관련 스키마만 주입 — "Pruned by Exact-Match"가 최고 정확도·토큰↓ | [arXiv 2505.05118](https://arxiv.org/html/2505.05118v2) |
| 스키마 표현/grounding | 온톨로지→경량 semantic schema + 관련 subgraph 주입 (T2CSS) | [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S016792362500154X) |
| 반복 정제 | 생성→검증→교정 루프, 실행 에러/결과 피드백 재생성 | [Neo4j Iterative Refinement](https://neo4j.com/blog/developer/iterative-refinement-for-text2cypher/) |
| 다중 후보+검증 | n개 후보 생성 → 실행 성공 후보 선택 | [Auto-Cypher 2412.12612](https://www.alphaxiv.org/overview/2412.12612v2) · [Multi-Agent GraphRAG 2511.08274](https://arxiv.org/pdf/2511.08274) |
| hard-example 학습 pruning | 소규모 고품질 학습 > 대규모 (학습비용 반감) | [arXiv 2505.05122](https://arxiv.org/abs/2505.05122) |
| (효과 없음) NER masking | 논문 실측에서 성능 개선 없음 — 도입 불필요 | arXiv 2505.05118 |

## 2. 코드 실측 검증 — 3대 기법은 이미 구현돼 있음

| 논문 기법 | CCOP 구현 (langgraph_agent.py) | 상태 |
|---|---|---|
| 스키마 pruning | `schema_fetching_node`(457): 동적 스키마 + `use_keyword_augment` exact-match 라벨 보강(483, arXiv 2505.05118 인용) + `_filter_schema_by_labels`(429) | ✅ 기본 ON, ab_schema_augment로 **88.9→94.5%(+5.5p) 실측** |
| 엔티티 grounding | `context_retrieval` 노드 — `search_nodes`로 DB 실존 확인 후 `{entity_context}` 주입 | ✅ 구현 |
| 반복 정제 | 검증·재시도 루프(P1, 커밋 86898fc) + `reflection_context` + `_is_data_absence_likely`(0건=데이터부재 휴리스틱) | ✅ 구현 |
| 앵커 노드 보강 | `_augment_anchor_node` — v47 "찾아줘→has_account만" 편향 후처리 보정 | ✅ 2026-09-01 추가 |

→ 논문 대비 **기법 갭 없음**. exact-match 도 한국어 별칭(`match_labels_by_keywords`)으로 로컬라이즈됨.

## 3. 실제 남은 이슈 (우선순위)

### P0-A · 학습-서빙 스키마 불일치 (근본 원인)
- v47은 **tccop_graph 645건**으로 학습 → 통합 그래프(22타입·72엣지)에서 편향("X 찾아줘"→has_account 계좌만 RETURN).
- 단기: 앵커 후처리(적용됨) + few-shot. **근본: v48 = 통합 그래프 실행검증 시드 + 회귀믹스**(v43 catastrophic forgetting·v45 실패→v46 회귀믹스 성공 교훈).

### P0-B · 통합 그래프 전용 벤치 부재 (모든 개선의 전제)
- 232벤치(`bench_v47_232_langgraph.py`)는 tccop_graph 기준. 통합 그래프 30~50문항 벤치 필요.
- 지표: 실행성공률 · 비공집합률 · 정답검증(기대 엔티티 포함 여부) · latency · (선택) 토큰.
- → **`scripts/bench_integrated_t2c.py`** (이 검토와 함께 구축).

### P1-A · 알고리즘 질문 라우팅 (설계 ③)
- "매개중심성 높은 계좌"류는 Cypher가 원리적으로 못 푸는 클래스 → `CALL ccop.algo.*`(구현됨)로 라우팅하면 클래스 전체가 정답화. 라우터 인텐트 1개 추가.

### P1-B · 지표 속성 숫자화
- `graph_analytics.py --set`이 지표를 **문자열 저장**(`'0.003419'`) → pagerank류(고정폭)는 우연히 정렬 일치하나 **kcore '14'<'7' 정렬 오류**, `WHERE n.pagerank > 0.001` 비교 깨짐. 숫자 저장 전환 필요.

### P2 · 다중 후보 n-sampling
- vLLM 자체 서빙이라 n=3 저비용(단일 요청 n 파라미터). 실행 성공 후보 선택. **벤치 실측 후** 도입 판단.

## 4. 로드맵

```
1) P0-B 통합그래프 벤치 구축 + 베이스라인 실측   ← 시작점
2) P1-A 알고리즘 라우팅 (CALL 레이어 연결)
3) P1-B --set 숫자 저장 전환 + 재적재
4) 실측 기반 v48 시드 설계 (통합그래프 실행검증 + 회귀믹스)
5) (선택) P2 n-sampling A/B
```

## 5. 참고 — 기존 자산
- `scripts/bench_v47_232_langgraph.py` (232벤치, tccop_graph) · `scripts/ab_schema_augment.py` (+5.5p A/B)
- v47 서빙: 엘리스 vLLM base+LoRA (reference_elice_server.md 레시피) · 터널 8002
- 앵커 보강: `app/services/langgraph_agent.py::_augment_anchor_node`
