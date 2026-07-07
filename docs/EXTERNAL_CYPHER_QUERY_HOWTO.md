# CCOP Cypher 쿼리 — 가져오기 & 조회 안내서 (외부 기관용)

**대상**: CCOP 그래프 데이터베이스에서 Cypher 쿼리를 확보(가져오기)하고, 그 쿼리로 데이터를 조회하려는 외부 기관·협력 업체
**버전**: 2026-06-26 기준
**접근 방식**: API 키 인증 기반 **read-only**(조회 전용) HTTPS API

> 본 문서는 「① 사이퍼쿼리를 가져오는 방법」과 「② 가져온 사이퍼쿼리로 조회하는 방법」 두 가지에 집중한 실무 안내서입니다.
> 전체 기능(네트워크 투영·덤프 등)은 별도 문서 `EXTERNAL_GRAPH_QUERY_GUIDE.md` 를 참고하세요.
> 모든 접근은 발급받은 API 키로 인증되며, 데이터 변경(CREATE/DELETE/SET 등)은 **불가**합니다.

---

## 0. 한눈에 보기 — 전체 흐름

```
 [1] 쿼리 가져오기              [2] (선택) 검증         [3] 조회 실행              [4] 결과 사용
 ───────────────────          ──────────────         ──────────────────       ───────────────
 A. 표준 카탈로그 복사  ─┐                              graph/read  (X-API-Key)
 B. 자연어→자동 생성    ─┼──▶  validate-cypher   ──▶                          ──▶ columns / rows
 C. 직접 작성           ─┘     (is_safe 확인)          graph-query (Bearer)        노드·엣지 객체
```

- **가장 쉬운 경로**: `A(카탈로그에서 복사)` → `graph/read 로 실행`. Cypher를 몰라도 됩니다.
- **탐색이 필요할 때**: `B(자연어로 자동 생성)`. 한국어 질문을 보내면 Cypher 문자열을 돌려줍니다.
- **직접 쿼리를 짤 때**: `C` 로 작성 후 `validate-cypher` 로 안전성만 점검하고 실행하세요.

---

## 1. 사전 준비

### 1.1 발급받을 것
| 항목 | 설명 |
|------|------|
| **API 키** | CCOP 운영팀에 기관명/용도/필요 그래프를 알려 발급. 형식 `ccop_xxxxxxxx...`, **최초 1회만 평문 표시**되니 안전히 보관 |
| **베이스 URL(`$HOST`)** | 운영팀이 안내하는 HTTPS 주소 (예: `https://<발급-호스트>`) |
| **graph_path** | 조회 대상 그래프명 (예: `tccop_graph_v6`, `osint_ontology`). 권한 내 그래프만 접근 가능 |

### 1.2 인증 헤더 (엔드포인트별로 다름)
```
Authorization: Bearer ccop_xxxxxxxx     # 일반 API(기관별 발급 키): text-to-cypher / validate-cypher / graph-query / graph/list
X-API-Key:     <조회토큰>                # read-only 그래프 API: graph/read / graph/schema / graph/dump
```
> ⚠️ `Authorization: Bearer` 값은 **기관별로 발급되는 `ccop_` 키**입니다.
> `X-API-Key` 값은 그와 **다른, 운영팀이 별도 안내하는 단일 조회 토큰**입니다(기관별 키가 아님).
> 예제에서 Bearer 는 `$KEY`, X-API-Key 는 `$RTOKEN` 으로 표기합니다.

### 1.3 연결·환경 확인 (복붙)
```bash
export HOST="https://<발급-호스트>"
export KEY="ccop_xxxxxxxx"            # 기관별 발급 키 (Bearer)
export RTOKEN="<운영팀-제공-조회토큰>"   # read-only 그래프 API용 단일 조회 토큰 (X-API-Key)

# (1) 헬스체크 — 인증 불필요
curl -s $HOST/api/v1/health
# → {"service":"CCOP Partner API","status":"healthy","version":"1.0.0"}

# (2) 사용 가능한 그래프 목록 (Bearer)
curl -s -H "Authorization: Bearer $KEY" $HOST/api/v1/graph/list

# (3) 그래프 스키마 — 어떤 라벨/엣지가 있는지 (X-API-Key)
curl -s -H "X-API-Key: $RTOKEN" "$HOST/api/v1/graph/schema?graph_path=tccop_graph_v6"
# → node_labels[], edge_types[], total_nodes, total_edges
```

---

## 2. ① 사이퍼쿼리를 "가져오는" 방법 (3가지)

### 방법 A. 표준 쿼리 카탈로그에서 복사 — **권장 기본**

사전 검증된 표준 쿼리 모음(`exports/queries/CCOP_GRAPH_QUERIES.md`)에서 목적에 맞는 쿼리를 복사해, **조건값만 바꿔** 사용합니다. Cypher 지식 없이도 안전하게 시작할 수 있습니다.

| 카테고리 | 예시 |
|---------|------|
| 전체 조회 | 라벨/엣지 통계, 전체 노드+엣지 |
| 사건 중심 | 사건 관련 노드(2-hop), 피의자 목록, 자금 흐름 |
| 인물 중심 | 인물의 자산(계좌/전화/IP), 관계망, 위험도 필터 |
| 자금 추적 | 입출금 내역, 다단계 세탁(3-hop), 고액 이체 |
| 통신 분석 | 발신/수신 통화, 대포폰, 불법중계기 |
| OSINT/위협 | 위협점수 필터, 악성 사이트, C2 통신, 피싱 군집 |
| 신뢰도 필터 | 공식 출처(tier1)만 / OSINT만 |

예) 카탈로그의 "고액 이체(5천만원 이상)" 쿼리:
```cypher
MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b2:vt_bacnt)
WHERE t.amount >= 50000000
RETURN b, t, b2 ORDER BY t.amount DESC
```
> 금액·이름·번호·기간 등 **조건만 교체**해 재사용하세요. 신규 패턴이 필요하면 운영팀에 카탈로그 추가를 요청할 수 있습니다.

### 방법 B. 자연어 → Cypher 자동 생성 (`text-to-cypher`)

한국어 질문을 보내면 CCOP가 Cypher 쿼리 문자열을 생성해 돌려줍니다. **쿼리가 생성과 동시에 실행**되어 결과(`elements`, `results_count`)도 함께 옵니다. 쿼리 문자열만 필요하면 `cypher` 필드만 쓰면 됩니다.

```bash
curl -s -X POST $HOST/api/v1/text-to-cypher \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"question":"피의자2가 보유한 계좌를 보여줘",
       "schema":{"graph_path":"tccop_graph_v6"}}'
```
응답(요약):
```json
{
  "status": "success",
  "cypher": "MATCH (p:vt_psn {name:'피의자2'})-[:has_account]->(b:vt_bacnt) RETURN p, b",
  "intent": "...",
  "elements": [ ... ],
  "results_count": 5
}
```
**Cypher 문자열만 뽑아내기** (`jq` 사용):
```bash
curl -s -X POST $HOST/api/v1/text-to-cypher \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"question":"피의자2의 계좌","schema":{"graph_path":"tccop_graph_v6"}}' \
  | jq -r '.cypher'
```
> ⚠️ AI 추론이 포함되어 응답이 **최대 약 120초**까지 걸릴 수 있습니다. 호출 timeout 을 130초 이상으로 두세요.
> 생성된 Cypher는 실행 전 **방법 C(검증)** 로 한 번 확인하면 안전합니다.

### 방법 C. 직접 작성 후 검증 (`validate-cypher`)

직접 작성했거나 방법 B로 받은 Cypher를 **실행하지 않고** 문법·안전성만 점검합니다.
```bash
curl -s -X POST $HOST/api/v1/validate-cypher \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"cypher":"MATCH (p:vt_psn) RETURN p LIMIT 10"}'
```
응답:
```json
{ "status": "valid", "is_safe": true, "warnings": [], "cypher": "MATCH (p:vt_psn) RETURN p LIMIT 10" }
```
- `is_safe: false` 이면 쓰기 명령어가 포함된 것 → 실행 시 차단됩니다(아래 §5). `warnings` 를 보고 수정하세요.

---

## 3. ② 가져온 사이퍼쿼리로 "조회하는" 방법

### 방법 ㉠. `graph/read` — read-only 전용 (권장, `X-API-Key`)

외부 read-only 조회의 **표준 엔드포인트**입니다. 쓰기 명령은 차단되고, `LIMIT` 미지정 시 자동으로 붙습니다.
```bash
curl -s -X POST $HOST/api/v1/graph/read \
  -H "X-API-Key: $RTOKEN" -H "Content-Type: application/json" \
  -d '{
        "graph_path": "tccop_graph_v6",
        "cypher": "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) RETURN p, b",
        "limit": 500
      }'
```
- `limit`: 기본 **500**, 최대 **5000**. 쿼리에 `LIMIT` 이 없으면 이 값이 자동 적용됩니다.
- 응답 형식(아래 §3-응답 참고): `{graph_path, cypher, columns, row_count, rows}`

### 방법 ㉡. `graph-query` — 일반 API (`Bearer`)

`Authorization: Bearer` 인증을 쓰는 경우의 조회 엔드포인트입니다. 기관 tier별 결과 상한이 적용됩니다.
```bash
curl -s -X POST $HOST/api/v1/graph-query \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{
        "graph_path": "tccop_graph_v6",
        "cypher": "MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b2:vt_bacnt) WHERE t.amount >= 50000000 RETURN b, t, b2 ORDER BY t.amount DESC LIMIT 100"
      }'
```
- 응답: `{status, results, count, limited, graph_path, response_time_ms}`
- `limited: true` 이면 tier 상한 때문에 잘린 것 → 조건을 좁히거나 운영팀에 상한 상향을 문의하세요. **`LIMIT` 을 항상 명시**하는 것을 권장합니다.

### 응답 읽는 법

**`graph/read` 응답** — 행/열(table) 형태:
```json
{
  "graph_path": "tccop_graph_v6",
  "cypher": "MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt) RETURN p, b LIMIT 500",
  "columns": ["p", "b"],
  "row_count": 47,
  "rows": [
    [ {"id":"4.11","label":"vt_psn","props":{"name":"피의자2"}},
      {"id":"8.23","label":"vt_bacnt","props":{"account_no":"110-1111-2222"}} ],
    ...
  ]
}
```
- `columns` = RETURN 절의 컬럼 순서. `rows[i][j]` = i번째 행의 j번째 컬럼 값.
- 각 값은 **노드/엣지 객체**(`{id, label, props}`) 또는 **스칼라**(숫자·문자열).

**`graph-query` 응답** — 결과 리스트 형태:
```json
{ "status":"success", "results":[ ... ], "count":10, "limited":true, "graph_path":"tccop_graph_v6" }
```

---

## 4. 자주 쓰는 쿼리 — 복붙 빠른 시작

아래를 `graph/read` 의 `cypher` 값에 넣고 **조건값만 교체**하세요.

```cypher
-- (1) 이 그래프에 어떤 노드가 얼마나 있나
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC

-- (2) 특정 사건의 관련 노드 (2-hop) — 'CASE-2024-001' 만 교체
MATCH (c:vt_case {flnm:'CASE-2024-001'})-[r*1..2]-(n) RETURN c, r, n LIMIT 200

-- (3) 특정 인물의 보유 자산 — '김민준' 만 교체
MATCH (p:vt_psn {name:'김민준'})-[r]->(asset)
WHERE type(r) IN ['has_account','owns_phone','used_ip']
RETURN p, r, asset

-- (4) 특정 계좌의 입출금 — 계좌번호만 교체
MATCH (b:vt_bacnt {account_no:'1002-110-100001'})-[r]-(t:vt_transfer) RETURN b, r, t

-- (5) 위협점수 80 이상 IP
MATCH (ip:vt_ip) WHERE ip.threat_score >= 80 RETURN ip ORDER BY ip.threat_score DESC LIMIT 100
```

### 주요 노드/엣지 타입 (KICS 온톨로지)
| 라벨 | 의미 | 라벨 | 의미 |
|------|------|------|------|
| `vt_psn` | 인물 | `vt_bacnt` | 계좌 |
| `vt_telno` | 전화번호 | `vt_call` | 통화 |
| `vt_transfer` | 이체 | `vt_ip` | IP |
| `vt_site` | URL/사이트 | `vt_case` | 사건 |

주요 엣지: `has_account`(인물→계좌), `owns_phone`(인물→전화), `from_account`/`to_account`(이체), `caller`/`callee`(통화), `suspect_in`(인물→사건). 정확한 스키마는 §1.3 `graph/schema` 로 확인하세요.

---

## 5. 규칙·제약 (반드시 준수)

- **read-only 강제**: 데이터 변경·구조변경·프로시저 호출 계열은 모두 **403 차단**됩니다.
  차단 키워드(단어 단위): `CREATE` · `MERGE` · `SET` · `DELETE` · `REMOVE` · `DETACH` · `DROP` (그리고 `graph/read` 는 추가로 `CALL`/`INSERT`/`UPDATE`/`ALTER`/`TRUNCATE` 도 차단).
  → 허용되는 절: `MATCH` · `WHERE` · `WITH` · `RETURN` · `ORDER BY` · `LIMIT` 등 **읽기 절만**.
  → 참고: 문자열 값 안에 위 키워드가 **단독 단어**로 들어가도 차단될 수 있습니다(예: `'DROP'`).
- **LIMIT**: `graph/read` 는 미지정 시 자동 주입(기본 500, 최대 5000). 대량 조회는 조건을 좁혀 **나눠** 호출하세요.
- **graph_path**: 영문/숫자/`_` 만 허용. 권한 외 그래프는 차단(400/403). 사용 가능 목록은 `graph/list` 로 확인.
- **Rate limit**: 기관 tier별 분당 요청 수 제한(기본 100 req/min, 협의 조정). 초과 시 429 → 잠시 후 재시도, 병렬 호출 자제.
- **보안·데이터 취급**:
  - API 키는 환경변수/시크릿 저장소에 보관, 코드·저장소에 **하드코딩 금지**. 유출 의심 시 즉시 운영팀에 키 회전 요청.
  - **HTTPS만** 사용.
  - 조회 결과에는 수사 관련 민감정보가 포함될 수 있습니다. 기관 내 **개인정보·수사보안 규정**에 따라 보관·파기하세요.

---

## 6. 문제 해결 (에러 코드)

| HTTP | 의미 | 조치 |
|------|------|------|
| 401 | 인증 헤더 누락/무효 | 엔드포인트에 맞는 `Authorization: Bearer` 또는 `X-API-Key` 확인 |
| 403 | 권한 없음 / **read-only 위반** | 쓰기 명령 제거, 키·graph_path 권한 확인 |
| 400 | 잘못된 `graph_path`/파라미터 | `graph_path` 는 영문/숫자/`_` 만, `cypher` 필드 필수 |
| 429 | 분당 한도 초과 | 다음 분에 재시도, 호출 빈도 축소 |
| 500 | 쿼리 실행 오류 | Cypher 문법/스키마 확인(§1.3) 후에도 지속되면 운영팀 문의 |

---

## 7. 전체 예시 — Python (가져오기 → 조회 end-to-end)

```python
import os, requests

HOST   = os.environ["CCOP_HOST"]          # 예: https://<발급-호스트>
KEY    = os.environ["CCOP_API_KEY"]       # 기관별 발급 키 (Bearer)
RTOKEN = os.environ["CCOP_READ_TOKEN"]    # read-only 그래프 API용 단일 조회 토큰 (X-API-Key)
BEARER = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}
XKEY   = {"X-API-Key": RTOKEN,            "Content-Type": "application/json"}

# ── ① 쿼리 가져오기: 자연어 → Cypher (방법 B) ─────────────────
r = requests.post(f"{HOST}/api/v1/text-to-cypher",
        json={"question": "피의자2가 보유한 계좌",
              "schema": {"graph_path": "tccop_graph_v6"}},
        headers=BEARER, timeout=130)
cypher = r.json()["cypher"]
print("가져온 Cypher:", cypher)

# ── ②(선택) 검증 (방법 C) ───────────────────────────────────
v = requests.post(f"{HOST}/api/v1/validate-cypher",
        json={"cypher": cypher}, headers=BEARER, timeout=30).json()
assert v["is_safe"], f"안전하지 않은 쿼리: {v['warnings']}"

# ── ③ 조회 실행: graph/read (방법 ㉠) ───────────────────────
res = requests.post(f"{HOST}/api/v1/graph/read",
        json={"graph_path": "tccop_graph_v6", "cypher": cypher, "limit": 500},
        headers=XKEY, timeout=60).json()

print("컬럼:", res["columns"], "| 행 수:", res["row_count"])
for row in res["rows"][:5]:
    print(row)
```
> CCOP Python SDK(`sdk/`)도 제공됩니다 — `text_to_cypher()`, `execute_cypher()`, `list_graphs()` 등. 운영팀에 문의하세요.

---

## 부록 A. 엔드포인트 요약

| 용도 | 메서드·경로 | 인증 | 비고 |
|------|------------|------|------|
| 헬스체크 | `GET /api/v1/health` | 없음 | 연결 확인 |
| 그래프 목록 | `GET /api/v1/graph/list` | Bearer | 사용 가능 graph_path |
| 스키마 요약 | `GET /api/v1/graph/schema?graph_path=…` | X-API-Key | 라벨/엣지 카운트 |
| **쿼리 가져오기**(자연어) | `POST /api/v1/text-to-cypher` | Bearer | 응답 `cypher` 회수 |
| **쿼리 검증** | `POST /api/v1/validate-cypher` | Bearer | 실행 안 함 |
| **조회 실행**(권장) | `POST /api/v1/graph/read` | X-API-Key | read-only, LIMIT 자동 |
| **조회 실행** | `POST /api/v1/graph-query` | Bearer | tier 결과 상한 |

## 부록 B. 함께 보면 좋은 자료
- `exports/queries/CCOP_GRAPH_QUERIES.md` — **표준 Cypher 쿼리 카탈로그**(방법 A의 원본, 8개 카테고리)
- `docs/EXTERNAL_GRAPH_QUERY_GUIDE.md` — 외부 기관용 **전체** 그래프 조회 가이드(네트워크 투영·덤프 등 포함)

## 부록 C. 문의
- 기술/쿼리 지원, API 키 발급·권한·그래프 추가: **CCOP 운영팀** (연락처는 발급 시 안내)
