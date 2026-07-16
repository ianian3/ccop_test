# CCOP Partner API 안내서

**사이버범죄 수사 그래프 분석 플랫폼 — 외부 기관 연동 API**

> 본 문서는 CCOP API를 제공받는 협력 기관을 위한 연동 안내서입니다. API 호스트 주소와 인증 키는 **운영팀이 개별 발급**합니다.
> 문서 버전 2026-07 · 대상: 파트너 기관 개발자

---

## 1. 개요

CCOP API는 사이버범죄 수사 그래프(사건·인물·계좌·전화·IP·이체 등)를 프로그램으로 조회·분석할 수 있는 REST API입니다.

| 제공 기능 | 설명 |
|---|---|
| **자연어 → Cypher 변환** | 한국어 질문을 그래프 쿼리(Cypher)로 자동 변환 |
| **그래프 조회** | Cypher 실행, 노드/엣지 조회, 스키마 조회 |
| **수사 분석** | 범죄 패턴 매칭, 증거 완성도, 공범 네트워크 분석 |
| **법률 근거 검색** | 조문·판례 하이브리드 검색 및 근거 인용 자문 |

- **Base URL**: `https://<발급받은-API-호스트>/api/v1`
- **형식**: 요청/응답 모두 JSON (`Content-Type: application/json`), UTF-8
- **전송**: HTTPS(TLS) 필수

---

## 2. 인증

두 가지 인증 방식이 있습니다. 발급받은 자격에 맞는 방식을 사용하세요.

### 2.1 Bearer 키 (파트너 API — 기관별 발급)

대부분의 API에 사용합니다. 발급받은 키(`ccop_`로 시작)를 `Authorization` 헤더에 넣습니다.

```
Authorization: Bearer ccop_xxxxxxxxxxxxxxxxxxxxxxxx
```

### 2.2 X-API-Key (그래프 read-only 조회 토큰)

외부 read-only 그래프 조회 API(`/graph/read`, `/graph/dump`, `/graph/schema`)에만 사용하는 단일 조회 토큰입니다.

```
X-API-Key: <발급받은-조회-토큰>
```

> 키는 안전하게 보관하고 클라이언트(브라우저/모바일)에 노출하지 마세요. 유출 시 운영팀에 즉시 통보 바랍니다.

---

## 3. 티어 및 사용 한도

발급 시 기관 티어가 지정됩니다.

| 티어 | 요청 한도 | 결과 행 제한 | 사용 가능 기능 |
|---|---|---|---|
| **Free** | 1,000 요청/분 | 50행 | 자연어 변환, 사용량 조회 |
| **Startup** | 10,000 요청/분 | 100행 | + Cypher 실행, 검증 |
| **Enterprise** | 무제한 | 500행 | 전체 기능 |

- 한도 초과 시 **429 (Rate limit exceeded)** 반환
- 결과 행 제한(`max_results`)은 그래프 조회 응답의 최대 반환 행 수입니다

---

## 4. 빠른 시작

### curl

```bash
export API="https://<API-호스트>/api/v1"
export KEY="ccop_xxxxxxxx"

# 1) 상태 확인
curl -s $API/health

# 2) 자연어 → Cypher
curl -s -X POST $API/text-to-cypher \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"question":"피의자2의 계좌를 보여줘"}'

# 3) 사용량 조회
curl -s $API/usage -H "Authorization: Bearer $KEY"
```

### Python

```python
import requests

API = "https://<API-호스트>/api/v1"
KEY = "ccop_xxxxxxxx"
H = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

# 자연어 → Cypher
r = requests.post(f"{API}/text-to-cypher", headers=H,
                  json={"question": "부산 보이스피싱 사건의 피의자 보여줘"})
print(r.json()["cypher"])
```

---

## 5. 엔드포인트 레퍼런스

`*` = 필수 파라미터. 별도 표기 없으면 `Authorization: Bearer` 인증.

### 5.1 자연어 · Cypher

| 메서드·경로 | 요청(body) | 응답(주요 필드) | 설명 |
|---|---|---|---|
| `POST /text-to-cypher` | `question`*, `schema.graph_path`(선택) | `cypher`, `intent`, `elements`, `results_count` | 자연어 질문을 Cypher로 변환·실행 |
| `POST /agentic-query` | `question`*, `graph_path`(선택) | `agent_response` | 다단계 추론 에이전트 분석 |
| `POST /graph-query` | `cypher`*, `graph_path`(선택) | `results`, `count`, `limited` | Cypher 실행 (**읽기 전용**, 티어 행 제한) |
| `POST /validate-cypher` | `cypher`* | `is_safe`, `warnings[]` | Cypher 문법·안전성 검증(실행 없음) |

**예시 — graph-query**
```bash
curl -s -X POST $API/graph-query -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"cypher":"MATCH (v:vt_flnm) RETURN v LIMIT 10","graph_path":"tccop_graph_v6"}'
```
> 조회 전용입니다. `CREATE/DELETE/SET/MERGE/DROP` 등 쓰기 구문은 **403**으로 거부됩니다.

### 5.2 그래프 read-only 조회 (X-API-Key)

외부 시스템/LLM이 그래프 데이터를 직접 가져갈 때 사용합니다. `X-API-Key` 인증.

| 메서드·경로 | 요청 | 응답 | 설명 |
|---|---|---|---|
| `POST /graph/read` | body `cypher`*, `graph_path`(기본 my_v40_demo), `limit`(기본 500·최대 5000) | `columns`, `row_count`, `rows` | read-only Cypher 실행 → 테이블 |
| `GET /graph/dump` | query `graph_path`*, `limit`, `format`(json\|triple) | `nodes`,`edges` 또는 `triples` | 그래프 전체 덤프 |
| `GET /graph/schema` | query `graph_path`* | `node_labels[]`, `edge_types[]`, `total_nodes/edges` | 스키마 요약(라벨/카운트) |

**예시**
```bash
curl -s -X POST $API/graph/read -H "X-API-Key: $RTOKEN" \
  -H "Content-Type: application/json" \
  -d '{"cypher":"MATCH (n) RETURN n LIMIT 10","graph_path":"tccop_graph_v6"}'

curl -s -H "X-API-Key: $RTOKEN" "$API/graph/schema?graph_path=tccop_graph_v6"
```
> `/graph/read`도 읽기 전용 강제입니다(쓰기 구문 403). `LIMIT` 미지정 시 자동 주입됩니다.

### 5.3 수사 분석

| 메서드·경로 | 요청 | 응답 | 설명 |
|---|---|---|---|
| `POST /analyze-pattern` | `case_id`*, `graph_path`(선택) | `matched_patterns[]`, `primary_pattern`, `confidence` | 사건의 범죄 패턴 자동 인식 |
| `GET /evidence-completeness/<case_id>` | query `graph_path` | `score`, `missing_evidence[]` | 증거 완성도·기소 준비도 |
| `GET /patterns` | — | `patterns[]`, `total` | 지원 범죄 패턴 목록 |
| `POST /network/project` | `graph_path`, `actor_label`(기본 vt_psn), `pivot_label`(기본 vt_bacnt), `min_shared`(기본 1) | `nodes[]`, `edges[]`, `stats` | 공유 자원 기반 공범 네트워크(1-mode 투영) |
| `POST /network/bipartite` | `graph_path`, `actor_label`, `pivot_label` | `top_actors[]`, `top_pivots[]`, 카운트 | 이분 그래프 분포 통계 |

### 5.4 법률 근거 검색 (Legal RAG)

| 메서드·경로 | 요청 | 응답 | 설명 |
|---|---|---|---|
| `POST /legal/search` | `question`*(≤2000자), `top_k`(기본 5·1~20), `mode`(hybrid\|bm25\|vector), `rerank`(bool) | `results[]`(조문·점수) | 법률 근거 하이브리드 검색 |
| `POST /legal/answer` | `question`*(≤2000자), `top_k`(기본 4·1~10) | `answer`, `citations[]` | 근거 인용 자문 답변 |
| `GET /legal/status` | — | 인덱스 상태 | 법률 검색 가용 상태 |

> 법률 답변은 **수사 참고용 정보**이며 법률 자문이 아닙니다. 적용 전 원문(law.go.kr) 및 전문가 확인이 필요합니다.

### 5.5 스키마 · 메타

| 메서드·경로 | 응답 | 설명 |
|---|---|---|
| `GET /schema/layers` | `entities{}`, `relationships{}` | 온톨로지 4계층·엔티티·관계 정의 |
| `GET /ontology/meta` | `node_id_standard`, `domain_usage`, `inference_rules` | 온톨로지 메타(식별자·도메인·추론규칙) |

### 5.6 계정

| 메서드·경로 | 응답 | 설명 |
|---|---|---|
| `GET /usage` | `tier`, `current_month{requests,limit,remaining}` | 사용량·한도 조회 |
| `GET /health` | `status` | API 상태 확인(인증 불요) |

---

## 6. 온톨로지 요약 (Cypher 작성용)

그래프는 KICS 표준 기반 POLE 6계층 구조입니다. Cypher 작성 시 아래 노드 라벨을 사용합니다.

| 라벨 | 의미 | 라벨 | 의미 |
|---|---|---|---|
| `vt_flnm` / `vt_case` | 사건 | `vt_psn` | 인물(피의자·피해자) |
| `vt_bacnt` | 계좌 | `vt_telno` | 전화번호 |
| `vt_ip` | IP 주소 | `vt_site` | 사이트/URL |
| `vt_atm` | ATM | `vt_file` | 파일/증거 |
| `vt_transfer` | 이체 | `vt_call` | 통화 |
| `vt_org` | 조직 | `vt_dev` | 단말기 |

주요 관계(엣지): `suspect_in`(피의자↔사건), `has_account`(인물↔계좌), `owns_phone`(인물↔전화), `transferred_to`/`from_account`/`to_account`(이체), `accomplice_of`(공범), `communicated_with`(통신). 전체 목록은 `/schema/layers` 응답 참조.

```cypher
-- 예: 특정 사건의 피의자와 그 계좌
MATCH (c:vt_flnm {flnm:'2024-001'})<-[:suspect_in]-(p:vt_psn)-[:has_account]->(a:vt_bacnt)
RETURN p, a
```

---

## 7. 에러 코드

에러 응답은 항상 `error` 필드를 포함합니다: `{"error": "...", "message": "..."}`

| 코드 | 의미 | 대응 |
|---|---|---|
| 400 | 필수 파라미터 누락·잘못된 값 | 요청 본문 확인 |
| 401 | 인증 헤더 없음/형식 오류 | `Authorization: Bearer` 또는 `X-API-Key` 확인 |
| 403 | 키 무효 / 권한(티어) 부족 / 쓰기 구문 | 키·티어·읽기전용 여부 확인 |
| 404 | 리소스 없음(사건 등) | 식별자 확인 |
| 429 | 요청 한도 초과 | 잠시 후 재시도, 필요 시 티어 상향 문의 |
| 500 | 서버 내부 오류 | 지속 시 운영팀 문의 |

---

## 8. 이용 정책 및 지원

- **조회 전용**: 본 API는 데이터 조회·분석 전용입니다. 쓰기 작업은 제공되지 않습니다.
- **접근 제어**: 기관 공인 IP를 사전 등록해야 접속이 허용될 수 있습니다(운영팀 협의).
- **보안**: 키를 소스코드·클라이언트에 하드코딩하지 말고 서버 측 환경변수/시크릿으로 관리하세요.
- **문의**: API 키 발급·티어 조정·IP 등록·장애 문의는 운영팀으로 연락 바랍니다.

---

*본 안내서의 엔드포인트·파라미터는 CCOP API v1 기준입니다. 사양 변경 시 운영팀이 사전 공지합니다.*
