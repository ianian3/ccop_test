# 시간순 연속성 — 쿼리 생성 로직 설계

> **작성일**: 2026-08-12
> **대상**: [시간순 연속성 적용] 체크박스 true 시 GDB 쿼리에 T(e1) ≤ T(e2) 주입
> **선행**: `docs/TEMPORAL_CONTINUITY_EDGE_CLASSIFICATION_20260812.md` (V/E/N 분류표 71종)
> **결론 한 줄**: sLLM 프롬프트가 아니라 **결정론적 후처리 주입**으로 설계한다. sLLM이 생성한 기본 Cypher의 경로를 파싱해 분류표 기반으로 시간조건을 자동 삽입하고, N형 구간은 `warnings`로 안내한다.

---

## 1. 방식 선택 — 왜 후처리인가

| 방식 | 설명 | 판정 |
|---|---|---|
| (A) 프롬프트 | sLLM에게 "시간순 조건 추가" 지시(few-shot) | ✗ sLLM이 V/E/N·시각속성을 정확히 알아야 함. 실측 데모에서 **방향·값·엣지 선택이 부정확** → 시간조건은 더 불안정 |
| **(B) 후처리 주입** | sLLM은 기본 Cypher만, 파서가 경로 추출 → 분류표로 시각조건 자동 삽입 | ✅ **결정론적·검증가능**. 분류표(SoT)만 신뢰, sLLM 정확도와 분리 |

→ **(B) 채택.** 시간 정확성을 모델 성능에 의존시키지 않는다.

## 2. 아키텍처

```
자연어 + [시간순 ON]
   → sLLM: 기본 Cypher 생성 (시간조건 없음)
   → [후처리] temporal_continuity.inject():
        ① 경로 파싱      (MATCH 노드-엣지 시퀀스 추출)
        ② 구간별 시각식  (V/E/N 분류표 → T_i 표현식)
        ③ 조건 주입      (WHERE date(T_i) <= date(T_{i+1}))
        ④ warnings       (N형 구간 안내)
   → 실행 + 응답(cypher, warnings)
```

파싱·주입은 **순수 함수**(DB 무관, 단위테스트) — ip_role_temporal·lazy_expansion과 동일 패턴.

## 3. 알고리즘

```
inject(cypher, direction_map) -> (cypher', warnings)

1. 경로 추출: MATCH 절에서 [(n0)-[e1(:label var)]->(n1)-[e2]->(n2)...] 시퀀스 파싱
   - 각 엣지: 변수명, 라벨, 방향, 양끝 노드(변수·라벨)

2. 각 엣지 e_i 의 기준시각 표현식 T_i:
   - V형: 경유 Event 노드 변수.시각속성
          (e_i 의 양끝 중 Event 라벨 노드를 찾아 그 var.<시각속성>)
          예: caller → vt_call 노드 var.call_strt_dt
   - E형: e_i.<시각속성>   (valid_from | transfer_date | exchanged_at | first_seen | detected_at)
          예: used_ip → e_i.valid_from
   - N형: None

3. 인접 구간 (e_i, e_{i+1}):
   - T_i, T_{i+1} 모두 존재  → 조건 push:  date(T_i) <= date(T_{i+1})
   - 하나라도 None(N형)      → 조건 생략 + warnings.push(
       "구간 [<e_i> → <e_{i+1}>] 시간기준 없음(N형: <해당 엣지>)")

4. 조건들을 WHERE 에 AND 결합 (기존 WHERE 있으면 AND 추가, 없으면 신설)

5. return (주입된 cypher, warnings)
```

**V형 경유 노드 식별**: 엣지의 domain/range 분류표에서 Event 라벨이 어느 쪽인지 결정 → 경로 파싱의 해당 노드 변수를 참조. Event 노드가 경로에 명시 안 된 경우(축약) → 그 구간 N형 강등 + warning.

## 4. V/E/N 시각 표현식 규칙

| 형 | T_i 표현식 | 예 |
|---|---|---|
| V형 | `<event_var>.<시각속성>` | `t1.dlng_dt`, `c.call_strt_dt`, `a.access_dt`, `m.dsptch_dt` |
| E형 | `<edge_var>.<시각속성>` | `e1.valid_from`, `e1.transfer_date`, `e1.exchanged_at` |
| N형 | (없음) | — → warnings |

시각속성 매핑은 분류표(SoT)에서 로드 — 하드코딩 금지, `RELATIONSHIPS`/`ENTITIES` 파생.

## 5. 타입 정합 (필수)

- V형 Event 시각 = `timestamp`(초), E형 valid_from = `date`(일).
- **일 단위로 통일**: 비교 시 양변을 `date(T)`(또는 `T::date`)로 절사.
- 근거: v4.6 S2 백필도 일 단위(하루 내 중복은 노이즈). 일관 기준 유지.
- `<=`(앞서거나 같음) — 동일 시각(같은 날) 허용, 원안 정의 준수.

## 6. N형 warnings 처리

- N형이 낀 구간은 **조건을 넣지 않고**(경로 자체는 유지) `warnings`로만 알린다.
- 응답 예: `warnings: ["구간 [sameAs → has_account]는 시간기준 없음(N형: sameAs)"]`
- 화면(푸터 근처)에서 "일부 구간은 시간순 미보장" 배지로 안내.
- **전량 N형**(모든 구간)이면 시간순 조건 0개 + 전체 warning.

## 7. 예시

**(a) 자금세탁 경로 — 전부 E형** ✅ 완전 적용
```cypher
-- 원본
MATCH (a:vt_bacnt)-[e1:transferred_to]->(b:vt_bacnt)-[e2:transferred_to]->(c)
RETURN a,b,c
-- 주입 후
MATCH (a:vt_bacnt)-[e1:transferred_to]->(b:vt_bacnt)-[e2:transferred_to]->(c)
WHERE date(e1.transfer_date) <= date(e2.transfer_date)
RETURN a,b,c
```

**(b) 접속 경로 — V형(Event 경유)**
```cypher
MATCH (p)-[:performed_by]-(a1:vt_access)-[:accessed_from]->(ip)
      <-[:accessed_from]-(a2:vt_access)-[:accessed_to]->(s)
WHERE date(a1.access_dt) <= date(a2.access_dt)
RETURN ...
```

**(c) 혼합 + N형** — 일부 warning
```cypher
MATCH (p)-[u:used_ip]->(ip)<-[:sameAs]-(ip2)   -- used_ip(E형) + sameAs(N형)
-- used_ip 는 T 있으나 sameAs 가 N형 → 이 구간 조건 생략
-- warnings: ["구간 [used_ip → sameAs]는 시간기준 없음(N형: sameAs)"]
```

## 8. 구현 단계

- [ ] **Q1. 순수 모듈** `app/services/temporal_continuity.py`
  - `classify_edge(edge) -> ('V'|'E'|'N', 시각표현식규칙)` (분류표 SoT 파생)
  - `parse_path(cypher) -> [세그먼트]`
  - `inject(cypher) -> (cypher', warnings)`
  - 단위테스트: 자금세탁(E)·접속(V)·혼합N·전량N
- [ ] **Q2. 연동** — LangGraph synthesis 후처리에 삽입 (체크박스 flag 전달)
- [ ] **Q3. API/UI** — 요청에 `temporal_continuity: bool`, 응답에 `warnings[]`, 푸터 체크박스 연결
- [ ] **Q4. 값 백필 의존성** — E형 valid_from 값이 있어야 실효(§분류표 보완 4종은 적재 백필 대기)

> Q1은 DB·sLLM 무관 순수 로직 → 지금 구현·테스트 가능. Q2~Q4는 파이프라인/적재 연동.

## 9. 리스크 · 결정

| 항목 | 결정 |
|---|---|
| Cypher 파싱 견고성 | 정규식+구조 파싱. 복잡/중첩 패턴은 보수적으로 N형 강등(조건 미주입) + warning |
| 방향(역방향 엣지) | 경로의 화살표 방향과 무관하게 엣지 라벨로 분류(시각은 엣지/노드 속성) |
| Event 노드 미명시 | V형인데 경로에 Event 노드 변수 없으면 참조 불가 → N형 강등 + warning |
| 값 결측 | valid_from NULL 인 인스턴스는 런타임에 조건 통과/제외 정책 필요(기본: NULL 제외 옵션) |
| 성능 | WHERE 추가는 비용 미미. 인덱스는 기존 속성 인덱스 활용 |

---

## 부록 — 관련
- 분류표: `docs/TEMPORAL_CONTINUITY_EDGE_CLASSIFICATION_20260812.md` (V18/E25/N28)
- 시간축 기반: `docs/ONTOLOGY_V46_IP_ROLE_BITEMPORAL_DESIGN.md`(used_ip valid_from S2)
- 패턴: 순수 로직+연동 분리 = `ip_role_temporal`·`lazy_expansion`
