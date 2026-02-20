# 테스트 데이터 사용 가이드

## 테스트 데이터 파일

| 파일명 | 범죄 유형 | 테스트 포인트 |
|-------|----------|--------------|
| `test_bodycamp_phishing.csv` | 몸캠피싱 | 사이트+영상파일+계좌 패턴 |
| `test_voice_phishing.csv` | 보이스피싱 | 전화번호+계좌 패턴 |
| `test_money_laundering.csv` | 자금세탁 | 동일 계좌 복수 사건, 다단계 이체 |

---

## 1. 몸캠피싱 테스트 (`test_bodycamp_phishing.csv`)

### ETL 매핑 설정
```json
{
  "sourceCol": "접수번호",
  "targetCol": "사이트",
  "srcLabel": "vt_flnm",
  "tgtLabel": "vt_site",
  "srcKey": "flnm",
  "tgtKey": "site",
  "edgeType": "digital_trace",
  "properties": [
    {"col": "파일명", "key": "filename", "target": "edge"},
    {"col": "계좌번호", "key": "actno", "target": "edge"},
    {"col": "피해금액", "key": "amount", "target": "edge"}
  ]
}
```

### 검증 Cypher
```cypher
MATCH (c:vt_flnm)-[:digital_trace]->(s:vt_site)
WHERE s.site CONTAINS 'chat' OR s.site CONTAINS 'cam' OR s.site CONTAINS '만남'
RETURN c.flnm AS 사건번호, s.site AS 사이트
```

---

## 2. 보이스피싱 테스트 (`test_voice_phishing.csv`)

### ETL 매핑 설정
```json
{
  "sourceCol": "접수번호",
  "targetCol": "전화번호",
  "srcLabel": "vt_flnm",
  "tgtLabel": "vt_telno",
  "srcKey": "flnm",
  "tgtKey": "telno",
  "edgeType": "used_phone",
  "properties": [
    {"col": "계좌번호", "key": "actno", "target": "edge"},
    {"col": "피해금액", "key": "amount", "target": "edge"}
  ]
}
```

### 검증 Cypher
```cypher
// 동일 전화번호 복수 사건 사용 탐지
MATCH (c:vt_flnm)-[:used_phone]->(p:vt_telno)
WITH p, count(DISTINCT c) AS case_count, collect(c.flnm) AS cases
WHERE case_count >= 2
RETURN p.telno AS 공유전화번호, case_count AS 연루사건수, cases AS 사건목록
```

---

## 3. 자금세탁 테스트 (`test_money_laundering.csv`)

### ETL 매핑 설정
```json
{
  "sourceCol": "접수번호",
  "targetCol": "계좌번호",
  "srcLabel": "vt_flnm",
  "tgtLabel": "vt_bacnt",
  "srcKey": "flnm",
  "tgtKey": "actno",
  "edgeType": "used_account",
  "properties": [
    {"col": "이체순서", "key": "seq", "target": "edge"},
    {"col": "이체금액", "key": "amount", "target": "edge"},
    {"col": "은행명", "key": "bank", "target": "target"}
  ]
}
```

### 검증 Cypher
```cypher
// 대포통장 탐지 (3건 이상 사건에서 동일 계좌 사용)
MATCH (c:vt_flnm)-[:used_account]->(a:vt_bacnt)
WITH a, count(DISTINCT c) AS case_count, collect(c.flnm) AS cases
WHERE case_count >= 3
RETURN a.actno AS 의심계좌, case_count AS 연루사건수, cases AS 사건목록
```

**예상 결과:**
- `110-234-567890` 계좌가 3건 사건(2026-00201, 2026-00202, 2026-00203)에서 사용됨 → 대포통장 의심

---

## 4. Temporal/Provenance 속성 검증

### ETL 후 확인 Cypher
```cypher
// 엣지에 timestamp, seq 속성 확인
MATCH (c:vt_flnm)-[r:used_account]->(a:vt_bacnt)
RETURN c.flnm, a.actno, r.timestamp, r.seq, r.source
ORDER BY r.seq
```

### 노드 created_at 확인
```cypher
MATCH (n:vt_flnm)
RETURN n.flnm, n.created_at
ORDER BY n.created_at
```
