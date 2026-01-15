# CCOP Partner API Guide

외부 파트너가 CCOP의 AI 기반 그래프 분석 기능을 사용하기 위한 API 가이드입니다.

## 🚀 시작하기

### 1. API 키 받기

API 키는 CCOP 관리자에게 요청하여 받을 수 있습니다.

**API 키 형식:**
```
ccop_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 2. 인증 방법

모든 API 요청에는 `Authorization` 헤더에 Bearer 토큰을 포함해야 합니다:

```http
Authorization: Bearer ccop_your_api_key_here
```

---

## 📚 API 엔드포인트

Base URL: `http://your-server:5001/api/v1`

### 1. Text-to-Cypher 변환

자연어 질문을 Cypher 쿼리로 변환합니다.

**Endpoint:** `POST /api/v1/text-to-cypher`

**Request:**
```json
{
  "question": "접수번호 2019-000392와 관련된 모든 계좌 찾기"
}
```

**Response:**
```json
{
  "status": "success",
  "cypher": "MATCH (v:vt_flnm)-[:USED_ACCOUNT]->(n:vt_bacnt) WHERE v.flnm CONTAINS '2019-000392' RETURN v, n",
  "partner": "demo_partner",
  "response_time_ms": 245.67
}
```

**cURL 예제:**
```bash
curl -X POST http://localhost:5001/api/v1/text-to-cypher \
  -H "Authorization: Bearer ccop_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"question": "접수번호 2019-000392 관련 계좌 찾기"}'
```

---

### 2. Graph Query 실행

Cypher 쿼리를 실행합니다 (읽기 전용).

**Endpoint:** `POST /api/v1/graph-query`

**Request:**
```json
{
  "cypher": "MATCH (v:vt_flnm) RETURN v LIMIT 10",
  "graph_path": "demo_tst1"
}
```

**Response:**
```json
{
  "status": "success",
  "results": [
    {"id": "1.234", "label": "vt_flnm", "properties": {"flnm": "2019-000138"}},
    ...
  ],
  "count": 10,
  "total_count": 150,
  "limited": true,
  "graph_path": "demo_tst1",
  "response_time_ms": 89.23
}
```

**제한사항:**
- ✅ 허용: `MATCH`, `RETURN`, `WHERE`, `LIMIT`
- ❌ 금지: `DELETE`, `DROP`, `CREATE`, `MERGE`, `SET`, `REMOVE`

---

### 3. Cypher 검증

Cypher 쿼리의 문법과 안전성을 검증합니다 (실행하지 않음).

**Endpoint:** `POST /api/v1/validate-cypher`

**Request:**
```json
{
  "cypher": "MATCH (v) RETURN v"
}
```

**Response:**
```json
{
  "status": "valid",
  "is_safe": true,
  "warnings": [],
  "cypher": "MATCH (v) RETURN v"
}
```

---

### 4. 사용량 조회

파트너의 API 사용량을 조회합니다.

**Endpoint:** `GET /api/v1/usage`

**Response:**
```json
{
  "partner": "demo_partner",
  "tier": "free",
  "current_month": {
    "requests": 150,
    "limit": 1000,
    "remaining": 850
  },
  "allowed_endpoints": ["text-to-cypher", "graph-query", "usage"]
}
```

---

### 5. Health Check

API 상태를 확인합니다 (인증 불필요).

**Endpoint:** `GET /api/v1/health`

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "service": "CCOP Partner API"
}
```

---

## 🐍 Python 예제

```python
import requests

API_KEY = "ccop_your_api_key_here"
BASE_URL = "http://localhost:5001/api/v1"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 1. Text-to-Cypher
response = requests.post(
    f"{BASE_URL}/text-to-cypher",
    headers=headers,
    json={"question": "접수번호 2019-000392 관련 계좌"}
)
print(response.json())

# 2. Graph Query
cypher = response.json()['cypher']
response = requests.post(
    f"{BASE_URL}/graph-query",
    headers=headers,
    json={
        "cypher": cypher,
        "graph_path": "demo_tst1"
    }
)
print(response.json())

# 3. Usage
response = requests.get(
    f"{BASE_URL}/usage",
    headers=headers
)
print(response.json())
```

---

## 📊 티어 및 제한

| 티어 | 월 요청 제한 | 결과 제한 | 허용 엔드포인트 | 가격 |
|------|-------------|----------|----------------|------|
| **Free** | 1,000 | 50개 | text-to-cypher, usage | 무료 |
| **Startup** | 10,000 | 100개 | 전체 (graph-query 포함) | $99/월 |
| **Enterprise** | 무제한 | 500개 | 전체 + 우선 지원 | 협의 |

---

## 🔒 보안 모범 사례

1. **API 키 보호**
   - 절대 코드에 하드코딩하지 마세요
   - 환경 변수에 저장하세요
   ```python
   import os
   API_KEY = os.getenv("CCOP_API_KEY")
   ```

2. **HTTPS 사용**
   - 프로덕션에서는 반드시 HTTPS 사용

3. **에러 처리**
   ```python
   try:
       response = requests.post(url, headers=headers, json=data)
       response.raise_for_status()
       return response.json()
   except requests.exceptions.HTTPError as e:
       print(f"HTTP Error: {e.response.status_code}")
       print(e.response.json())
   ```

---

## 🐛 에러 코드

| 코드 | 의미 | 해결방법 |
|------|------|---------|
| 400 | Bad Request | 요청 형식 확인 |
| 401 | Unauthorized | Authorization 헤더 확인 |
| 403 | Forbidden | API 키 또는 권한 확인 |
| 429 | Too Many Requests | Rate Limit 초과, 잠시 후 재시도 |
| 500 | Internal Server Error | 관리자에게 문의 |

---

## 📞 지원

- 이메일: support@ccop.example.com
- 문서: https://docs.ccop.example.com
- GitHub Issues: https://github.com/ianian3/ccop_test/issues
