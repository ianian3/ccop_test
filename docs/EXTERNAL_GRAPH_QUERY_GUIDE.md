# CCOP 그래프 조회 가이드 (외부 기관용)

**대상**: CCOP 그래프 데이터베이스를 쿼리로 조회하는 외부 기관/협력 업체
**버전**: 2026-06-18 기준
**접근 방식**: API 키 인증 기반 **read-only**(조회 전용) HTTPS API

> 본 가이드는 외부에 전달하는 사용 안내서입니다. 모든 접근은 발급받은 API 키로 인증되며,
> 데이터 변경(CREATE/DELETE/SET 등)은 **불가**합니다. 접근 가능한 그래프·필드는 기관별 권한에 따릅니다.

---

## 1. 시작하기

### 1.1 사전 준비
1. **API 키 발급 요청** — CCOP 운영팀에 기관명/용도/필요 그래프를 알려 발급받습니다. 키는 `ccop_xxxxxxxx...` 형식이며 **최초 1회만 평문 표시**되니 안전히 보관하세요.
2. **베이스 URL 확인** — 운영팀이 안내한 HTTPS 주소 (예: `https://<발급받은-호스트>`).
3. **권한 확인** — 기관별로 ① 사용 가능 엔드포인트(tier) ② 접근 가능 graph_path ③ 분당 요청 한도(rate limit)가 정해집니다.

### 1.2 인증 방식
모든 요청에 API 키를 헤더로 전달합니다 (둘 중 안내받은 방식):
```
Authorization: Bearer ccop_xxxxxxxxxxxxxxxx      # 일반 API(/api/v1/*)
X-API-Key: ccop_xxxxxxxxxxxxxxxx                 # read-only 그래프 API(/api/v1/graph/*)
```

### 1.3 연결 확인 (헬스체크)
```bash
curl -s https://<HOST>/api/v1/health
# → {"service":"CCOP Partner API","status":"healthy","version":"1.0.0"}
```

### 1.4 사용 가능한 그래프 목록
```bash
curl -s -H "Authorization: Bearer $KEY" https://<HOST>/api/v1/graph/list
# → {"status":"success","graphs":[{"name":"tccop_graph_v6","node_count":...}, ...]}
```
> 실제 조회 가능한 그래프는 기관 권한에 따릅니다. `graph_path` 값은 이 목록에서 확인하세요.

---

## 2. 조회 방법 — 무엇을 언제 쓸까

CCOP은 4가지 조회 방식을 제공합니다. **대부분의 조건별 조회는 ②/③(카탈로그·구조화 필터)로 안전하게 해결**되며, 자유 Cypher(④)는 기술 파트너용 옵션입니다.

| 방법 | 엔드포인트 | 적합 상황 | 난이도 |
|------|-----------|----------|--------|
| ① 자연어 | `POST /api/v1/text-to-cypher` | Cypher 모르는 탐색적 질의 | 낮음 |
| ② **쿼리 카탈로그** | (템플릿 → ③/④로 실행) | **사전검증된 표준 조회** (권장 기본) | 낮음 |
| ③ **구조화 필터(네트워크 투영)** | `POST /api/v1/network/project`·`/bipartite` | **공범망·허브 분석** (조건=JSON) | 낮음 |
| ④ 자유 Cypher (read-only) | `POST /api/v1/graph-query`·`/api/v1/graph/read` | 복잡한 다단계/집계 조건 | 높음 |

---

## 3. 조건별 조회 예제

> 아래 예제의 `$KEY`=API 키, `$HOST`=베이스 URL, `graph_path`=권한 내 그래프명.

### 3.1 자연어로 조회 (① text-to-cypher)
```bash
curl -s -X POST https://$HOST/api/v1/text-to-cypher \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"question":"피의자2가 보유한 계좌를 보여줘","schema":{"graph_path":"tccop_graph_v6"}}'
```
응답: `cypher`(생성된 쿼리), `intent`, `elements`(노드/엣지), `results_count`. (응답 최대 120초)

### 3.2 자유 Cypher로 조건 조회 (④ graph-query, read-only)
```bash
# 5천만원 이상 고액 이체 추적
curl -s -X POST https://$HOST/api/v1/graph-query \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{
        "graph_path":"tccop_graph_v6",
        "cypher":"MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b2:vt_bacnt) WHERE t.amount >= 50000000 RETURN b,t,b2 ORDER BY t.amount DESC LIMIT 100"
      }'
```
- **read-only 강제**: `CREATE/DELETE/SET/MERGE/REMOVE/DROP/DETACH/CALL` 포함 시 **403 거부**.
- 결과는 tier별 상한 적용(`limited:true`면 더 있음). `LIMIT`을 항상 명시하세요.

### 3.3 read-only 전용 API (④ graph/read — X-API-Key)
```bash
curl -s -X POST https://$HOST/api/v1/graph/read \
  -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"graph_path":"tccop_graph_v6","cypher":"MATCH (p:vt_psn) RETURN p","limit":500}'
# LIMIT 미지정 시 자동 주입(기본 500, 최대 5000). 응답: columns/row_count/rows
```

### 3.4 공범 네트워크 (③ network/project — 1-mode 투영)
```bash
# 같은 계좌를 2개 이상 공유한 인물 네트워크
curl -s -X POST https://$HOST/api/v1/network/project \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"graph_path":"tccop_graph_v6","actor_label":"vt_psn","pivot_label":"vt_bacnt","min_shared":2}'
# 응답: nodes[], edges[{source,target,weight,shared_samples}], stats
```

### 3.5 허브 통계 (③ network/bipartite — 2-mode)
```bash
# 이체에 가장 많이 참여한 계좌 Top-N
curl -s -X POST https://$HOST/api/v1/network/bipartite \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"graph_path":"tccop_graph_v6","actor_label":"vt_bacnt","pivot_label":"vt_transfer"}'
# 응답: top_actors[], top_pivots[], actor_count/pivot_count/edge_count
```

### 3.6 스키마/전체 덤프
```bash
curl -s -H "X-API-Key: $KEY" "https://$HOST/api/v1/graph/schema?graph_path=tccop_graph_v6"
# node_labels[], edge_types[], total_nodes/total_edges
curl -s -H "X-API-Key: $KEY" "https://$HOST/api/v1/graph/dump?graph_path=tccop_graph_v6&limit=500&format=triple"
# format=json(노드/엣지) 또는 triple([주어,관계,목적어])
```

---

## 4. 쿼리 카탈로그 (② 권장 기본)

표준 분석 패턴은 **사전 검증된 쿼리 카탈로그**(`exports/queries/CCOP_GRAPH_QUERIES.md`)에서 복사해 §3.2/3.3으로 실행하세요. 카테고리:

| 카테고리 | 예 |
|---------|-----|
| 사건 중심 | 사건 관련 노드, 피의자 목록, 자금 흐름 |
| 인물 중심 | 자산 조회, 관계망, 위험도 필터 |
| 자금 추적 | 입출금 내역, 다단계 세탁, 고액 이체 |
| 통신 분석 | 발신/수신, 대포폰, 불법중계기 |
| OSINT/위협 | 위협점수 필터, 악성 사이트, 피싱 캠페인 |
| 신뢰도 필터 | 공식 출처(tier1)만 / OSINT만 |

> 조건만 바꿔(이름·번호·금액·기간) 재사용하세요. 운영팀이 신규 패턴을 카탈로그에 추가할 수 있습니다.

---

## 5. 온톨로지 (노드/엣지 타입)

조회 대상 그래프는 KICS 온톨로지(`vt_*`)를 따릅니다. 주요 노드:

| 라벨 | 의미 | 라벨 | 의미 |
|------|------|------|------|
| `vt_psn` | 인물 | `vt_bacnt` | 계좌 |
| `vt_telno` | 전화번호 | `vt_call` | 통화 |
| `vt_transfer` | 이체 | `vt_ip` | IP |
| `vt_site` | URL/사이트 | `vt_file` | 파일 |
| `vt_case` | 사건 | `vt_src` | 출처 |

주요 엣지: `has_account`(인물→계좌), `owns_phone`(인물→전화), `from_account/to_account`(이체), `caller/callee`(통화), `sourced_from`(→출처) 등. 전체 스키마는 §3.6 `graph/schema` 또는 `GET /api/v1/schema/layers` 로 확인.

---

## 6. 응답 형식

**노드/엣지 (Cytoscape 호환)**
```json
{
  "elements": [
    {"group":"nodes","data":{"id":"4.11","label":"vt_psn","props":{"name":"피의자2"}}},
    {"group":"edges","data":{"id":"15.2","source":"4.11","target":"8.23","label":"has_account"}}
  ],
  "results_count": 5
}
```
**Triple (경량, LLM용)**: `{"triples":[["피의자2","has_account","110-1111-2222"], ...]}`

페이징: tier별 결과 상한 + `LIMIT`/`limit` 파라미터. 대량은 조건을 좁혀 나눠 조회하세요.

---

## 7. 인증·한도·에러

| HTTP | 의미 | 조치 |
|------|------|------|
| 401 | 인증 헤더 누락/형식 오류 | `Authorization: Bearer` 또는 `X-API-Key` 확인 |
| 403 | 키 무효 / 권한 없는 엔드포인트 / **read-only 위반** | 키·권한 확인, 쓰기 명령 제거 |
| 429 | 분당 요청 한도 초과 | 잠시 후(다음 분) 재시도, 병렬 호출 자제 |
| 400 | 잘못된 graph_path/파라미터 | graph_path는 영문/숫자/_ 만, `graph/list`로 확인 |
| 500 | 쿼리 실행 오류 | Cypher 문법/스키마 확인 후 운영팀 문의 |

**Rate limit**: 기관 tier별 분당 요청 수 제한. 응답에 `response_time_ms` 포함.

---

## 8. 보안·이용 수칙 (필수 준수)

- **API 키**는 환경변수/시크릿 저장소에 보관. 코드/저장소에 하드코딩 금지. 유출 의심 시 즉시 운영팀에 회전 요청.
- **HTTPS만** 사용.
- **조회 전용**: 데이터 변경 불가(시도 시 403). 자동화 시 rate limit 준수.
- **데이터 취급**: 조회 결과에는 수사 관련 민감정보가 포함될 수 있습니다. 기관 내 **개인정보·수사보안 규정**에 따라 보관·파기하세요. (서버 측 마스킹/접근범위 정책은 운영팀과 협의)
- **접근 범위**: 권한 외 graph_path/엔드포인트 접근은 차단됩니다. 추가 권한은 운영팀에 신청.

---

## 9. Python 예시 (requests)
```python
import requests, os
HOST = "https://<HOST>"; KEY = os.environ["CCOP_API_KEY"]
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

# 자연어
r = requests.post(f"{HOST}/api/v1/text-to-cypher",
    json={"question":"피의자2의 계좌","schema":{"graph_path":"tccop_graph_v6"}}, headers=H, timeout=130)
print(r.json()["cypher"], r.json()["results_count"])

# 자유 Cypher (read-only)
r = requests.post(f"{HOST}/api/v1/graph-query",
    json={"graph_path":"tccop_graph_v6",
          "cypher":"MATCH (p:vt_psn {name:'피의자2'})-[:has_account]->(b:vt_bacnt) RETURN p,b LIMIT 50"},
    headers=H, timeout=60)
print(r.json()["count"])
```
> CCOP Python SDK(`sdk/`)도 제공됩니다 — `text_to_cypher()`, `project_1mode()`, `execute_cypher()`, `list_graphs()` 등. 운영팀에 문의.

---

## 10. 문의
- 기술/쿼리 지원, API 키 발급·권한·그래프 추가: **CCOP 운영팀** (연락처는 발급 시 안내)

---
### 부록 — 엔드포인트 요약
| 기능 | 메서드·경로 | 인증 |
|------|------------|------|
| 헬스체크 | `GET /api/v1/health` | 없음 |
| 그래프 목록 | `GET /api/v1/graph/list` | Bearer |
| 스키마 | `GET /api/v1/graph/schema` · `GET /api/v1/schema/layers` | X-API-Key / 없음 |
| 자연어 질의 | `POST /api/v1/text-to-cypher` · `/api/v1/agentic-query` | Bearer |
| 자유 Cypher(RO) | `POST /api/v1/graph-query` · `POST /api/v1/graph/read` | Bearer / X-API-Key |
| Cypher 검증 | `POST /api/v1/validate-cypher` | Bearer |
| 네트워크 투영 | `POST /api/v1/network/project` · `/api/v1/network/bipartite` | Bearer |
| 전체 덤프 | `GET /api/v1/graph/dump` | X-API-Key |
