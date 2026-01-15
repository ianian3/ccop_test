# CCOP API 파트너 온보딩 가이드

**CCOP (Cyber Crime Operation Platform)**에 오신 것을 환영합니다!

본 문서는 CCOP API를 사용하여 귀사의 서비스에 강력한 그래프 기반 사이버 범죄 분석 기능을 통합하는 방법을 안내합니다.

---

## 📋 목차

1. [CCOP API 소개](#ccop-api-소개)
2. [시작하기](#시작하기)
3. [API 키 발급 받기](#api-키-발급-받기)
4. [빠른 시작 가이드](#빠른-시작-가이드)
5. [티어 및 요금](#티어-및-요금)
6. [주요 기능](#주요-기능)
7. [기술 문서](#기술-문서)
8. [지원 및 문의](#지원-및-문의)
9. [FAQ](#faq)

---

## 🎯 CCOP API 소개

CCOP API는 AI 기반 그래프 데이터베이스 분석 서비스로, 복잡한 사이버 범죄 수사 데이터를 자연어로 쉽게 조회하고 분석할 수 있게 해드립니다.

### 핵심 가치

✅ **AI 기반 자연어 처리**: 전문 지식 없이 일반 언어로 데이터 조회  
✅ **그래프 데이터베이스**: 복잡한 관계망을 시각적으로 분석  
✅ **RESTful API**: 기존 시스템에 쉽게 통합  
✅ **보안 우선**: SHA-256 암호화, 티어별 접근 제어  

---

## 🚀 시작하기

### 1단계: 계정 신청

CCOP 담당자에게 다음 정보를 전달하여 계정을 신청하세요:

- **회사명**
- **담당자 이름 및 연락처**
- **이메일 주소**
- **사용 목적** (간략히)
- **원하는 티어** (Free / Startup / Enterprise)

### 2단계: API 키 수령

계정 승인 후 이메일로 다음 정보를 받게 됩니다:

```
===========================================
CCOP API 접근 정보
===========================================

API 키: ccop_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
티어: [귀사의 티어]
월 요청 제한: [요청 수]

⚠️ 이 API 키는 비밀번호와 같습니다. 
   절대 공개 저장소나 클라이언트 코드에 포함하지 마세요.
===========================================
```

### 3단계: 첫 API 호출

API 키를 받으신 후 바로 사용을 시작할 수 있습니다!

---

## 🔑 API 키 발급 받기

### 신청 방법

**이메일**: support@ccop.example.com  
**제목**: [API 키 신청] 회사명  
**본문**:
```
회사명: _______________
담당자: _______________
연락처: _______________
이메일: _______________
사용 목적: _______________
희망 티어: Free / Startup / Enterprise
```

### 발급 소요 시간

- **영업일 기준 1-2일** 내 처리
- 긴급한 경우 문의 주시면 우선 처리해드립니다

---

## ⚡ 빠른 시작 가이드

### Python 예제

```python
import requests

# API 설정
API_KEY = "ccop_your_api_key_here"  # 발급받은 API 키
API_BASE = "https://api.ccop.example.com/v1"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 1. 자연어로 Cypher 쿼리 생성
question = "접수번호 2019-000392와 관련된 모든 계좌 찾기"

response = requests.post(
    f"{API_BASE}/text-to-cypher",
    headers=headers,
    json={"question": question}
)

result = response.json()
print(f"생성된 쿼리: {result['cypher']}")

# 2. 그래프 데이터 조회 (Startup 이상 티어)
response = requests.post(
    f"{API_BASE}/graph-query",
    headers=headers,
    json={
        "keyword": "2019-000392",
        "graph_path": "your_graph"
    }
)

data = response.json()
print(f"조회 결과: {data['count']}개 발견")
```

### cURL 예제

```bash
# Text-to-Cypher API 호출
curl -X POST https://api.ccop.example.com/v1/text-to-cypher \
  -H "Authorization: Bearer ccop_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"question": "전화번호 010으로 시작하는 연결된 사람 찾기"}'
```

---

## 💰 티어 및 요금

| 구분 | Free | Startup | Enterprise |
|------|------|---------|-----------|
| **월 요청 제한** | 1,000 | 10,000 | 무제한 |
| **결과 제한** | 50개 | 100개 | 500개 |
| **Text-to-Cypher** | ✅ | ✅ | ✅ |
| **Graph Query** | ❌ | ✅ | ✅ |
| **Cypher 검증** | ✅ | ✅ | ✅ |
| **사용량 조회** | ✅ | ✅ | ✅ |
| **기술 지원** | 이메일 | 이메일 + 전화 | 전담 매니저 |
| **월 요금** | **무료** | **₩150,000** | **별도 협의** |

### 추가 옵션

- **초과 요청**: Startup 티어 한도 초과 시 1,000 요청당 ₩15,000
- **전용 그래프 DB**: 월 ₩500,000부터 (데이터 용량에 따라)
- **온프레미스 설치**: 별도 견적

---

## 🎁 주요 기능

### 1. Text-to-Cypher (모든 티어)

자연어 질문을 Cypher 쿼리로 자동 변환합니다.

**입력 예시**:
- "접수번호 2019-000138 관련 계좌 찾기"
- "010으로 시작하는 전화번호 연결된 사람"
- "IP 주소 192.168로 시작하는 모든 사이트"

**응답**:
```json
{
  "status": "success",
  "cypher": "MATCH (v:vt_flnm)-[:USED_ACCOUNT]->(a:vt_bacnt) WHERE v.flnm CONTAINS '2019-000138' RETURN a",
  "response_time_ms": 850
}
```

### 2. Graph Query (Startup 이상)

키워드로 그래프 데이터를 직접 조회합니다.

**응답**:
```json
{
  "status": "success",
  "results": [
    {
      "id": "38.23125",
      "label": "vt_flnm",
      "props": {
        "flnm": "2019-000138",
        "police_station": "부산지방경찰청"
      }
    }
  ],
  "count": 13
}
```

### 3. Cypher 검증 (모든 티어)

쿼리를 실행하기 전에 안전성을 검증합니다.

### 4. 사용량 조회 (모든 티어)

현재 사용량과 남은 할당량을 확인할 수 있습니다.

---

## 📚 기술 문서

상세한 API 참조 문서는 다음을 확인하세요:

- **API 레퍼런스**: `/docs/API_GUIDE.md`
- **샘플 코드**: `/examples/` 디렉토리
- **Swagger UI**: https://api.ccop.example.com/docs (곧 제공 예정)

### 엔드포인트 목록

| 엔드포인트 | 메서드 | 설명 | 티어 |
|----------|--------|------|------|
| `/v1/health` | GET | API 상태 확인 | 모두 (무인증) |
| `/v1/text-to-cypher` | POST | 자연어 → Cypher | 모두 |
| `/v1/graph-query` | POST | 그래프 조회 | Startup+ |
| `/v1/validate-cypher` | POST | 쿼리 검증 | 모두 |
| `/v1/usage` | GET | 사용량 조회 | 모두 |

---

## 🆘 지원 및 문의

### 기술 지원

- **이메일**: support@ccop.example.com
- **응답 시간**: 
  - Free: 영업일 기준 2-3일
  - Startup: 영업일 기준 1일
  - Enterprise: 4시간 이내

### 영업 문의

- **이메일**: sales@ccop.example.com
- **전화**: 02-XXXX-XXXX (평일 9:00-18:00)

### 긴급 장애

- **Enterprise 전용 핫라인**: 010-XXXX-XXXX (24/7)

---

## ❓ FAQ

### Q1: API 키를 분실했어요

**A**: support@ccop.example.com으로 문의하시면 재발급해드립니다. 보안을 위해 기존 키는 즉시 무효화됩니다.

### Q2: 요청 제한을 초과하면 어떻게 되나요?

**A**: `429 Too Many Requests` 오류가 반환됩니다. 다음 시간(매시간 초기화)까지 기다리거나, 티어를 업그레이드하세요.

### Q3: HTTPS를 사용하나요?

**A**: 네, 모든 API 통신은 TLS 1.2 이상으로 암호화됩니다.

### Q4: 여러 개의 API 키를 받을 수 있나요?

**A**: Startup 이상 티어에서는 개발/프로덕션용으로 2개의 키를 제공합니다.

### Q5: 데이터는 어디에 저장되나요?

**A**: 한국 내 데이터센터(AWS Seoul 리전)에 저장되며, ISMS-P 인증을 준수합니다.

### Q6: API 버전 관리는 어떻게 되나요?

**A**: URL에 버전 정보가 포함됩니다(`/v1/`). 새 버전 출시 시 6개월의 마이그레이션 기간을 제공합니다.

---

## 🎓 학습 자료

### 튜토리얼

1. **10분 만에 시작하기**: 첫 번째 API 호출부터 데이터 조회까지
2. **실전 예제**: 사기 사건 분석 자동화
3. **고급 활용**: 커스텀 그래프 스키마 설정

### 비디오 가이드

- CCOP API 소개 (5분)
- Python으로 시작하기 (10분)
- 실전 사례 연구 (20분)

---

## 📝 이용 약관

CCOP API 사용 시 다음 약관에 동의하신 것으로 간주됩니다:

- API 키는 타인과 공유할 수 없습니다
- 서비스 남용(DoS 공격, 크롤링 등)은 엄격히 금지됩니다
- 개인정보보호법 및 관련 법규를 준수해야 합니다
- 상세 약관: https://ccop.example.com/terms

---

## 🎉 환영합니다!

CCOP API를 선택해 주셔서 감사합니다. 

귀사의 사이버 범죄 대응 역량 강화를 위해 최선을 다하겠습니다.

**CCOP 팀 드림**

---

**마지막 업데이트**: 2026년 1월 15일  
**문서 버전**: 1.0
