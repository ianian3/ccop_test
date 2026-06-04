# CCOP 그래프 DB 표준 Cypher 쿼리 모음

**버전**: v4.0
**대상**: 외부 기관 (검찰/협력경찰/FIU/통신3사/위협인텔리전스 등)
**제공 형식**: AgensGraph Cypher (PostgreSQL + AGE 호환)

---

## 🔌 사용 방법

### Option 1 — CCOP API 호출 (권장)

```bash
curl -X POST http://<CCOP_HOST>:5002/api/v1/graph/read \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <발급된_키>" \
  -d '{
    "graph_path": "osint_ontology",
    "cypher": "<아래 쿼리 중 하나>",
    "limit": 500
  }'
```

### Option 2 — PostgreSQL 직접 (read-only 계정 발급 시)

```sql
SET graph_path = osint_ontology;
<아래 쿼리>
```

---

## 🟢 카테고리 1: 전체 조회

### 1-1. 그래프 스키마 (어떤 라벨/엣지 있는지)

```cypher
MATCH (n) RETURN labels(n)[0] AS label, count(n) AS cnt ORDER BY cnt DESC
```

### 1-2. 엣지 통계

```cypher
MATCH ()-[r]->() RETURN type(r) AS edge, count(r) AS cnt ORDER BY cnt DESC
```

### 1-3. 전체 노드+엣지 (LIMIT 필수)

```cypher
MATCH (n)-[r]->(m)
RETURN id(n), labels(n), properties(n),
       id(r), type(r), properties(r),
       id(m), labels(m), properties(m)
LIMIT 500
```

---

## 🟢 카테고리 2: 사건 중심

### 2-1. 특정 사건의 모든 관련 노드 (2-hop)

```cypher
MATCH (c:vt_case {flnm: 'CASE-2024-001'})-[r*1..2]-(n)
RETURN c, r, n LIMIT 200
```

> `CASE-2024-001` 부분만 실제 사건번호로 변경.

### 2-2. 사건의 피의자 목록

```cypher
MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case {flnm: 'CASE-2024-001'})
RETURN p
```

### 2-3. 사건의 자금 흐름

```cypher
MATCH (c:vt_case {flnm: 'CASE-2024-001'})
      <-[:suspect_in]-(p:vt_psn)
      -[:has_account]->(b1:vt_bacnt)
      -[:from_account]->(t:vt_transfer)
      -[:to_account]->(b2:vt_bacnt)
RETURN p, b1, t, b2
```

### 2-4. 사건 간 연관 (공유 증거)

```cypher
MATCH (c1:vt_case)-[:eg_used_account]->(b:vt_bacnt)
      <-[:eg_used_account]-(c2:vt_case)
WHERE c1 <> c2
RETURN c1, b, c2
```

---

## 🟢 카테고리 3: 인물 중심

### 3-1. 특정 인물의 모든 자산 (계좌/전화/IP/차량)

```cypher
MATCH (p:vt_psn {name: '김민준'})-[r]->(asset)
WHERE type(r) IN ['has_account', 'owns_phone', 'used_ip', 'owns_vehicle']
RETURN p, r, asset
```

### 3-2. 인물 간 관계망 (공통 사건)

```cypher
MATCH (p1:vt_psn)-[:suspect_in]->(c:vt_case)<-[:suspect_in]-(p2:vt_psn)
WHERE p1 <> p2
RETURN p1, c, p2
```

### 3-3. 위험도 HIGH 인물 + 보유 계좌

```cypher
MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt)
WHERE p.risk_level = 'HIGH'
RETURN p, b
```

---

## 🟢 카테고리 4: 자금 추적

### 4-1. 특정 계좌의 입출금 내역

```cypher
MATCH (b:vt_bacnt {account_no: '1002-110-100001'})-[r]-(t:vt_transfer)
RETURN b, r, t
```

### 4-2. 다단계 자금 세탁 (3-hop)

```cypher
MATCH path = (b1:vt_bacnt)-[:from_account]->(:vt_transfer)
              -[:to_account]->(b2:vt_bacnt)
              -[:from_account]->(:vt_transfer)
              -[:to_account]->(b3:vt_bacnt)
RETURN path LIMIT 50
```

### 4-3. 고액 이체 (5천만원 이상)

```cypher
MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer)-[:to_account]->(b2:vt_bacnt)
WHERE t.amount >= 50000000
RETURN b, t, b2 ORDER BY t.amount DESC
```

---

## 🟢 카테고리 5: 통신 분석

### 5-1. 특정 번호의 발신/수신 통화

```cypher
MATCH (t:vt_telno {telno: '010-1234-5678'})-[:caller]->(c:vt_call)-[:callee]->(t2:vt_telno)
RETURN t, c, t2
UNION
MATCH (t2:vt_telno)-[:caller]->(c:vt_call)-[:callee]->(t:vt_telno {telno: '010-1234-5678'})
RETURN t2, c, t
```

### 5-2. 대포폰 (실사용자 ≠ 명의자)

```cypher
MATCH (p1:vt_psn)-[:owns_phone]->(t:vt_telno)-[:registered_to]->(p2:vt_psn)
WHERE p1 <> p2
RETURN p1, t, p2
```

### 5-3. 불법중계기 경유 전화

```cypher
MATCH (t:vt_telno)-[:used_in_device]->(d:vt_dev {dev_type: 'relay_station'})
RETURN t, d
```

---

## 🟢 카테고리 6: OSINT/위협 정보

### 6-1. 위협점수 80 이상 IP

```cypher
MATCH (ip:vt_ip)
WHERE ip.threat_score >= 80
RETURN ip ORDER BY ip.threat_score DESC
```

### 6-2. 악성 사이트 호스팅 IP

```cypher
MATCH (ip:vt_ip)-[:hosts]->(s:vt_site)
WHERE s.is_malicious = true
RETURN ip, s
```

### 6-3. C2 통신 (IP↔IP)

```cypher
MATCH (ip1:vt_ip)-[:communicated_with]->(ip2:vt_ip)
WHERE ip2.is_c2 = true OR ip2.threat_score >= 90
RETURN ip1, ip2
```

### 6-4. 피싱 캠페인 군집

```cypher
MATCH (sc:site_cluster)<-[:belongs_to_campaign]-(s:vt_site)
RETURN sc, s
```

---

## 🟢 카테고리 7: 사칭 분석

### 7-1. 사칭 이벤트 전체 (수단 + 타겟)

```cypher
MATCH (x)-[:used_for]->(imp:vt_impersonation)-[:targets]->(o:vt_org)
RETURN x, imp, o
```

### 7-2. 특정 기관 사칭 (예: 검찰)

```cypher
MATCH (x)-[:used_for]->(imp:vt_impersonation)-[:targets]->(o:vt_org {org_nm: '검찰청'})
RETURN x, imp, o
```

---

## 🟢 카테고리 8: 신뢰도/출처 필터

### 8-1. T1 공식 출처(KICS) 데이터만

```cypher
MATCH (n)
WHERE n.source_domain = 'investigation' AND n.reliability_tier = 1
RETURN n LIMIT 500
```

### 8-2. OSINT 데이터만

```cypher
MATCH (n)
WHERE n.source_domain = 'osint'
RETURN labels(n)[0] AS label, count(n) AS cnt
```

---

## 📊 응답 데이터 구조

CCOP API `/api/v1/graph/read` 응답:

```json
{
  "graph_path": "osint_ontology",
  "cypher": "MATCH ...",
  "columns": ["c", "p"],
  "row_count": 47,
  "rows": [
    [{"id": "...", "label": "vt_case", "props": {"flnm": "CASE-2024-001", ...}},
     {"id": "...", "label": "vt_psn",  "props": {"name": "김민준", ...}}],
    ...
  ]
}
```

각 row의 각 컬럼은 **그래프 노드/엣지 객체** 또는 **스칼라 값**.

---

## 🗂 사용 가능한 그래프

| graph_path | 용도 | 노드 수 |
|---|---|---|
| `my_v40_demo` | 데모/테스트 (KICS 7개 CSV 기반) | ~350 |
| `osint_ontology` | OSINT 위협 인텔리전스 | (실측 필요) |
| `tccop_v40_demo` | V4.0 전체 시나리오 | (실측 필요) |

각 그래프의 정확한 노드/엣지 수는 카테고리 1-1, 1-2 쿼리로 확인 가능.

---

## 🛡 운영 정책

- **Read-only**: CREATE/DELETE/SET/MERGE 등 쓰기 명령은 차단됨 (403 응답)
- **LIMIT 강제**: 미지정 시 500, 최대 5000
- **API key**: 헤더 `X-API-Key` 필요 (발급 받은 키)
- **Rate limit**: 기본 100 req/min (협의 조정)
- **개인정보**: 마스킹 필요 시 별도 `/api/v1/export/case_subgraph` 사용

---

## 📞 문의

- 기술 문의: ccop-tech@example.gov.kr
- 권한/MOU: ccop-admin@example.gov.kr
- 응답 사양/추가 쿼리: 본 문서 GitHub 이슈 참조

**버전 이력**: v4.0 (2026-06-02) — 초기 공개
