# 그래프 시각화 쿼리 스펙 — 노드 검색 / 노드 확장 (개발사 전달용)

> CCOP 그래프 시각화의 **노드 검색**과 **노드 확장** 두 기능을, AgensGraph Cypher로 구현하기 위한 쿼리·알고리즘·인터페이스 명세.
> 개발사가 이 문서만으로 재구현할 수 있도록 **실제 실행 쿼리, 단계별 알고리즘, AgensGraph 함정, 입출력 계약**을 담았다.
>
> 참조 구현: `app/services/graph_service.py` (`search_nodes`, `expand_node`)

---

## 0. 범위

| 기능 | 트리거(UI) | 입력 | 출력 |
|------|-----------|------|------|
| **A. 노드 검색** | 검색창에 키워드 입력 | `keyword`, `graph_path` | 매칭 노드 + 그 노드들이 얽힌 엣지 (서브그래프) |
| **B. 노드 확장** | 그래프에서 노드 더블클릭 | `node_id`, `graph_path` | 해당 노드의 직접 이웃 노드 + 엣지 |

---

## 1. 공통 전제

### 1.1 실행 환경
- **DB**: AgensGraph (PostgreSQL 기반). Cypher를 SQL 커넥션에서 직접 실행한다.
- **그래프 선택**: 매 쿼리 전 반드시 `SET graph_path = <graph_path>;` 를 먼저 실행. 이후 `MATCH ...` 가 해당 그래프에 적용된다.
- **커밋**: 커넥션은 `autocommit = ON`. (OFF일 경우 쿼리 하나가 실패하면 트랜잭션이 abort되어 이후 쿼리가 전부 `current transaction is aborted`로 무시됨 — §4 참고.)

### 1.2 노드 식별자 (graphid)
- 노드/엣지 id는 `id(n)` 으로 얻으며 **`"4.1"`, `"5.12"` 형태의 graphid**다(`라벨번호.로컬번호`).
- 매칭은 **문자열 등호**로 한다: `WHERE id(n) = '4.1'` ✅
- ⚠️ **`id(n) IN ['4.1','4.2']` 는 동작하지 않는다** (§4.1).

### 1.3 결과 포맷 (Cytoscape.js `elements`)
프런트 시각화(Cytoscape)가 그대로 먹는 배열. 노드/엣지를 하나의 리스트에 섞어 반환한다.

```jsonc
[
  { "group": "nodes", "data": { "id": "4.1", "label": "vt_psn",     "props": { "name": "피의자1", ... } } },
  { "group": "edges", "data": { "id": "23.1", "source": "4.1", "target": "5.1",
                                "label": "has_account", "props": { ... } } }
]
```
- `id`: graphid 문자열. **엣지의 `source`/`target` 은 반드시 실재 노드 `id` 와 일치**해야 한다.
- `label`: 노드는 **라벨명**(`vt_psn`, `vt_bacnt` …), 엣지는 **관계 타입**(`has_account` …).
- `props`: 속성 map.

### 1.4 라벨 결정 규칙 (노드)
1. Cypher `labels(n)` 의 **첫 원소**를 우선 사용.
2. 비어 있으면 속성 기반 추론(`determine_node_label(props)`) — 도메인 규칙 폴백.

### 1.5 엣지 라벨 규칙
- 기본은 `type(r)`.
- `type(r)` 가 제네릭 `ag_edge` 이면 속성에서 실제 관계를 추출: `semantic_relation → domain_meaning → edge_type → type → 'related_to'` 순, 소문자화.

---

## 2. 기능 A — 노드 검색

### 2.1 알고리즘
```
입력: keyword, graph_path
1) SET graph_path = graph_path
2) [노드] 전체 속성 텍스트에서 keyword 부분매칭 → 매칭 노드 수집 (id 목록 보관)
3) [엣지] 수집된 노드가 한쪽 끝이라도 걸리는 엣지 조회
        → 엣지 + 그 양끝 노드(검색 안 된 상대 노드 포함)를 결과에 추가
4) elements(nodes+edges) 반환   ※ 노드 중복은 id 集合으로 제거
```

### 2.2 쿼리

**① 노드 검색** (모든 라벨, 전체 속성 부분매칭)
```cypher
MATCH (n)
WHERE properties(n)::text CONTAINS '<keyword>'
RETURN id(n), labels(n), properties(n)
LIMIT 50
```
> `properties(n)::text` = 노드의 전 속성을 텍스트로 캐스팅 → 기존 SQL `properties::text LIKE '%kw%'` 와 동일 효과.

**② 검색 노드가 포함된 엣지** (수집 id가 `n₁, n₂, …` 일 때)
```cypher
MATCH (a)-[r]->(b)
WHERE id(a) = 'n₁' OR id(b) = 'n₁' OR id(a) = 'n₂' OR id(b) = 'n₂' OR ...
RETURN id(r), type(r), properties(r),
       id(a), labels(a), properties(a),
       id(b), labels(b), properties(b)
LIMIT 100
```
> `(a)-[r]->(b)` 방향 유지 → `source=id(a)`, `target=id(b)`. `id() IN [...]` 대신 **OR 체인**(§4.1).

### 2.3 입력 / 출력
- **입력**: `keyword`(문자열, 부분매칭), `graph_path`
- **출력**: `elements` — 매칭 노드 + 그 노드들이 얽힌 엣지 + 엣지 상대 노드
- keyword의 작은따옴표/역슬래시는 **이스케이프** 필요(`'` → `\'`).

### 2.4 엣지 케이스
- 매칭 노드 0 → 빈 배열.
- 엣지 쿼리 실패가 노드 결과까지 버리지 않도록 **엣지 조회는 독립적으로 처리**(실패해도 노드는 반환) 권장.

---

## 3. 기능 B — 노드 확장

### 3.1 알고리즘
```
입력: node_id, graph_path
1) SET graph_path = graph_path
2) outgoing: (node)-[r]->(이웃)  조회
3) incoming: (node)<-[r]-(이웃)  조회
4) 각 결과에서 이웃 노드 + 엣지를 elements 에 추가 (엣지 id 集合으로 중복 제거)
5) elements 반환
```
> 방향 정보를 지키려고 **outgoing/incoming 두 쿼리**로 나눈다(단일 무방향 `-[r]-` 로는 source/target 판별이 모호).

### 3.2 쿼리
```cypher
-- outgoing: 현재 노드(n)가 출발
MATCH (n)-[r]->(m) WHERE id(n) = '<node_id>'
RETURN id(r), type(r), properties(r), id(n), id(m), id(m), labels(m), properties(m)
LIMIT 200

-- incoming: 현재 노드(n)가 도착
MATCH (n)<-[r]-(m) WHERE id(n) = '<node_id>'
RETURN id(r), type(r), properties(r), id(m), id(n), id(m), labels(m), properties(m)
LIMIT 200
```
> RETURN 컬럼을 **통일**: `edge_id, type, edge_props, source_id, target_id, 이웃id, 이웃labels, 이웃props`.
> outgoing은 `source=id(n)`, incoming은 `source=id(m)` 이 되도록 순서만 바꿔 정렬.

### 3.3 입력 / 출력
- **입력**: `node_id`(graphid 문자열), `graph_path`
- **출력**: `elements` — 이웃 노드 + 연결 엣지(방향 유지)

### 3.4 엣지 케이스
- **고립 노드**(이웃 0)면 빈 배열 — 정상. (예: 실제로 노드는 존재하나 연결 엣지가 없는 경우)

---

## 4. ⚠️ AgensGraph 함정 (반드시 준수)

| # | 함정 | 잘못된 예 | 올바른 방법 |
|---|------|-----------|-------------|
| 4.1 | **`id() IN [리스트]` 미지원** — 리스트가 jsonb로 해석돼 `graph object cannot be jsonb` 오류 | `WHERE id(a) IN ['4.1','4.2']` | `WHERE id(a)='4.1' OR id(a)='4.2'` (OR 체인) |
| 4.2 | **`toString(map)` 불가** — 속성 전체를 toString 못 함 | `toString(properties(n))` | `properties(n)::text` (텍스트 캐스팅) |
| 4.3 | **전체 속성 검색** | 라벨/속성 일일이 나열 | `properties(n)::text CONTAINS 'kw'` (모든 라벨·속성 한 번에) |
| 4.4 | **graphid 매칭은 문자열 등호** | `id(n) = 4.1` (일부 상황 실패) | `id(n) = '4.1'` |
| 4.5 | **트랜잭션 abort 전파** — autocommit OFF면 첫 오류 후 모든 쿼리 무시 | 커넥션 기본값 방치 | `autocommit = ON` 또는 쿼리별 커밋/롤백 |
| 4.6 | **그래프 선택 누락** | 바로 `MATCH` | 매 실행 전 `SET graph_path = <name>;` |

---

## 5. API 계약 (현재 구현 기준)

| 메서드 | 경로 | 파라미터 | 응답 |
|--------|------|----------|------|
| GET | `/api/search` | `keyword`, `graph_path` | `elements` 배열 |
| GET | `/api/expand` | `id`(또는 `node_id`), `graph_path` | `elements` 배열 |

**요청 예**
```
GET /api/search?keyword=피의자&graph_path=tccop_graph_v6
GET /api/expand?id=4.1&graph_path=tccop_graph_v6
```

**응답 예** (`/api/expand?id=4.1`)
```json
[
  {"group":"nodes","data":{"id":"5.1","label":"vt_bacnt","props":{"account_no":"..."}}},
  {"group":"edges","data":{"id":"23.1","source":"4.1","target":"5.1","label":"has_account","props":{}}},
  {"group":"nodes","data":{"id":"3.2","label":"vt_case","props":{"flnm":"CASE-..."}}},
  {"group":"edges","data":{"id":"51.2","source":"4.1","target":"3.2","label":"suspect_in","props":{}}}
]
```

---

## 6. 참조 구현 & 검증

- 코드: `app/services/graph_service.py` → `search_nodes(keyword, graph_path)`, `expand_node(node_id, graph_path)`
- 실행 쿼리는 애플리케이션 로그에 `[QUERY]` 프리픽스로 남는다(디버깅/재현용):
  ```
  [QUERY] SET graph_path = tccop_graph_v6;
  [QUERY] MATCH (n) WHERE properties(n)::text CONTAINS '피의자' RETURN id(n), labels(n), properties(n) LIMIT 50
  [QUERY] MATCH (a)-[r]->(b) WHERE id(a)='4.11' OR id(b)='4.11' OR ... RETURN ... LIMIT 100
  [QUERY] MATCH (n)-[r]->(m) WHERE id(n)='4.1' RETURN ... LIMIT 200
  ```
- 검증 예: `tccop_graph_v6` 에서 `keyword=피의자` → nodes 37 / edges 11, `expand id=4.1` → nodes 3 / edges 3.

---

## 부록. 확장 시 참고
- **N-hop 확장**: 기능 B를 이웃에 대해 반복(BFS)하거나 `MATCH (n)-[*1..k]-(m)` 가변 길이 패턴.
- **경로 탐색**: `MATCH (u)-[]-(v) WHERE id(u)='src'` BFS 또는 `shortestPath((a)-[*..6]-(b))`.
- **성능**: 대용량 그래프에선 `properties(n)::text CONTAINS` 가 풀스캔이므로, 자주 검색되는 속성은 인덱스/전용 검색 노드 설계 고려.
