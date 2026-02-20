# CCOP 협력기관 데이터 표준화 가이드

> **Version**: 1.0  
> **Date**: 2026-01-30  
> **Scope**: RDB, GDB, Vector DB 연동 표준

---

## 1. 개요

본 문서는 CCOP(Cyber Crime Operation Platform)과 연동하는 **협력기관**을 위한 데이터 표준화 가이드입니다.

### 1.1 대상 기관

| 기관 유형 | 주요 데이터 | 연동 방식 |
|----------|-----------|----------|
| **금융기관** | 계좌정보, 이체내역 | API / 파일 |
| **통신사** | 통화기록, 가입자정보 | 파일 / DB |
| **수사기관** | 사건정보, 피의자정보 | API / 파일 |
| **가상자산사업자** | 지갑주소, 거래내역 | API |

### 1.2 데이터 흐름

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  협력기관   │────▶│  CCOP ETL   │────▶│   CCOP DB   │
│  (원천)     │     │  (변환)     │     │ (RDB+GDB)   │
└─────────────┘     └─────────────┘     └─────────────┘
     CSV/API           매핑/정제          표준 스키마
```

---

## 2. RDB 표준 (관계형 데이터)

### 2.1 테이블 명명 규칙

| 규칙 | 형식 | 예시 |
|------|------|------|
| 테이블명 | `<도메인>_<엔티티>` | `case_info`, `person` |
| PK 컬럼 | `id` (BIGSERIAL) | - |
| FK 컬럼 | `<참조테이블>_id` | `case_id`, `person_id` |
| 코드 컬럼 | `<항목>_cd` | `crime_cd`, `role_cd` |
| 일시 컬럼 | `<항목>_dt` 또는 `<항목>_at` | `created_at`, `tx_dt` |

### 2.2 핵심 테이블 스키마

#### 사건 정보 (case_info)

| 컬럼명 | 타입 | 필수 | KICS 매핑 | 설명 |
|--------|------|------|----------|------|
| `id` | BIGSERIAL | ✅ | - | 내부 PK |
| `receipt_no` | VARCHAR(50) | ✅ | `rcpt_no` | 접수번호 |
| `flnm` | VARCHAR(50) | ✅ | `flnm` | 사건번호 |
| `crime_cd` | VARCHAR(20) | | `crm_cd` | 범죄유형코드 |
| `damage_amount` | NUMERIC(15,2) | | `dmg_amt` | 피해금액 |
| `case_summary` | TEXT | | `smry` | 사건개요 |
| `created_at` | TIMESTAMPTZ | ✅ | - | 생성일시 |

#### 인물 정보 (person)

| 컬럼명 | 타입 | 필수 | KICS 매핑 | 설명 |
|--------|------|------|----------|------|
| `id` | BIGSERIAL | ✅ | - | 내부 PK |
| `name` | VARCHAR(100) | ✅ | `nm` | 성명 |
| `rrn` | VARCHAR(256) | | `rrn` | 주민번호 (암호화) |
| `role_cd` | VARCHAR(20) | | `role_cd` | 역할코드 (victim/suspect) |
| `phone` | VARCHAR(20) | | `telno` | 연락처 |

#### 계좌 정보 (bank_account)

| 컬럼명 | 타입 | 필수 | KICS 매핑 | 설명 |
|--------|------|------|----------|------|
| `id` | BIGSERIAL | ✅ | - | 내부 PK |
| `actno` | VARCHAR(50) | ✅ | `actno` | 계좌번호 |
| `bank_cd` | VARCHAR(10) | ✅ | `bnk_cd` | 은행코드 |
| `holder_name` | VARCHAR(100) | | `acct_nm` | 예금주명 |
| `account_type` | VARCHAR(20) | | `acct_tp_cd` | 계좌유형 |

### 2.3 공통 코드

#### 범죄유형코드 (CRIME_TYPE)

| 코드 | 명칭 | 설명 |
|------|------|------|
| `0100` | 사기(보이스피싱) | 전화금융사기 |
| `0200` | 공갈(몸캠피싱) | 영상협박사기 |
| `0300` | 투자사기 | 허위투자유도 |
| `0400` | 도박사이트 | 불법온라인도박 |
| `0500` | 랜섬웨어 | 시스템협박 |

#### 역할코드 (ROLE)

| 코드 | 명칭 |
|------|------|
| `victim` | 피해자 |
| `suspect` | 피의자 |
| `witness` | 참고인 |
| `informant` | 제보자 |

---

## 3. GDB 표준 (그래프 데이터)

### 3.1 4-Layer 온톨로지

```
┌─────────────────────────────────────────────────────────────┐
│                    CCOP 4-Layer Ontology                     │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Case      │ vt_case (사건), vt_inv (수사)          │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Actor     │ vt_psn (인물), vt_org (조직),          │
│                     │ vt_dev (기기)                          │
├─────────────────────────────────────────────────────────────┤
│  Layer 3: Action    │ vt_transfer (이체), vt_call (통화),    │
│                     │ vt_access (접속), vt_msg (메시지)      │
├─────────────────────────────────────────────────────────────┤
│  Layer 4: Evidence  │ vt_bacnt (계좌), vt_telno (전화),      │
│                     │ vt_ip (IP), vt_site (사이트),          │
│                     │ vt_file (파일)                         │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Vertex Label 명세

#### Layer 1: Case (사건)

| Label | 설명 | 필수 속성 | 선택 속성 |
|-------|------|----------|----------|
| `vt_case` | 사건 | `flnm` (사건번호) | `crime_type`, `damage_amount` |
| `vt_inv` | 수사 | `inv_id` | `inv_nm`, `dept_cd` |

#### Layer 2: Actor (행위자)

| Label | 설명 | 필수 속성 | 선택 속성 |
|-------|------|----------|----------|
| `vt_psn` | 인물 | `name` | `rrn`, `role`, `phone` |
| `vt_org` | 조직 | `corp_nm` | `biz_no`, `addr` |
| `vt_dev` | 기기 | `dvce_id` | `imei`, `mac_addr` |

#### Layer 3: Action (행위)

| Label | 설명 | 필수 속성 | 선택 속성 |
|-------|------|----------|----------|
| `vt_transfer` | 이체 | `tx_id`, `amount` | `tx_dt`, `memo` |
| `vt_call` | 통화 | `call_id` | `dur_sec`, `call_dt` |
| `vt_access` | 접속 | `log_id` | `acc_dt`, `act_cd` |
| `vt_msg` | 메시지 | `msg_id` | `msg_dt`, `content` |

#### Layer 4: Evidence (증거)

| Label | 설명 | 필수 속성 | 선택 속성 |
|-------|------|----------|----------|
| `vt_bacnt` | 계좌 | `actno` | `bank_cd`, `holder` |
| `vt_telno` | 전화 | `telno` | `carrier`, `holder` |
| `vt_ip` | IP | `ip_addr` | `isp_cd`, `country` |
| `vt_site` | 사이트 | `url` | `domain`, `is_malicious` |
| `vt_file` | 파일 | `file_nm` | `hash`, `size` |

### 3.3 Edge Label 명세

#### 핵심 관계

| Edge | 의미 | From → To | 속성 |
|------|------|----------|------|
| `involves` | 연루 | Case → Person | `role` |
| `performed` | 수행 | Person → Action | `dt` |
| `controls` | 지배 | Person → Account | `type` |

#### 이체 관계

| Edge | 의미 | From → To | 속성 |
|------|------|----------|------|
| `from_account` | 출금 | Transfer → Account | - |
| `to_account` | 입금 | Transfer → Account | - |
| `transferred_to` | 자금흐름 | Account → Account | `amount`, `dt` |

#### 통신 관계

| Edge | 의미 | From → To | 속성 |
|------|------|----------|------|
| `caller` | 발신 | Call → Phone | - |
| `callee` | 수신 | Call → Phone | - |

#### 증거 관계

| Edge | 의미 | From → To | 속성 |
|------|------|----------|------|
| `used_account` | 사용계좌 | Case → Account | `type` |
| `used_phone` | 사용전화 | Case → Phone | `type` |
| `digital_trace` | 디지털흔적 | Case → Evidence | - |

---

## 4. Vector DB 표준 (임베딩 데이터)

### 4.1 개요

CCOP은 **ChromaDB**를 사용하여 법률 문서의 임베딩을 저장합니다.

| 항목 | 값 |
|------|-----|
| **임베딩 모델** | OpenAI text-embedding-3-small |
| **차원** | 1536 |
| **검색 방식** | Cosine Similarity |

### 4.2 법률 문서 연동

#### 지원 형식

| 형식 | 확장자 | 처리 방식 |
|------|--------|----------|
| PDF | `.pdf` | PyPDF2 텍스트 추출 |
| 텍스트 | `.txt` | 직접 청킹 |
| Markdown | `.md` | 직접 청킹 |

#### 청킹 규칙

| 항목 | 값 |
|------|-----|
| Chunk Size | 1000 문자 |
| Overlap | 200 문자 |
| Separator | `\n\n` (단락 구분) |

#### 메타데이터 구조

```json
{
  "source": "형법_제347조.pdf",
  "chunk_index": 0,
  "page": 1,
  "law_name": "형법",
  "article": "제347조",
  "category": "재산범죄"
}
```

---

## 5. 데이터 제출 형식

### 5.1 CSV 템플릿

#### 금융기관 (계좌이체 데이터)

```csv
접수번호,출금계좌,입금계좌,이체금액,이체일시,은행명,비고
2026-00101,110-111-222333,221-222-333444,50000000,2026-01-15 10:30:00,국민은행,보이스피싱
2026-00101,221-222-333444,332-333-444555,49500000,2026-01-15 11:00:00,신한은행,2차이체
```

#### 통신사 (통화기록 데이터)

```csv
접수번호,발신번호,수신번호,통화시작,통화종료,기지국,발신자명
2026-00101,010-1234-5678,010-9999-8888,2026-01-15 09:00:00,2026-01-15 09:30:00,서울강남,김피해
```

#### 수사기관 (사건 데이터)

```csv
접수번호,사건번호,범죄유형,피해금액,피해자명,피의자명,사건개요
2026-00101,2026-000123,0100,50000000,김피해,박범죄,검찰 사칭 보이스피싱
```

### 5.2 API 연동

#### 인증

```http
POST /api/v1/auth/token
Content-Type: application/json

{
  "api_key": "your-api-key",
  "secret": "your-secret"
}
```

#### 데이터 전송

```http
POST /api/v1/data/upload
Authorization: Bearer {token}
Content-Type: multipart/form-data

file: (CSV 파일)
data_type: "transfer" | "call" | "case"
```

---

## 6. 데이터 품질 기준

### 6.1 필수 검증 항목

| 항목 | 검증 규칙 | 오류 시 처리 |
|------|----------|-------------|
| 사건번호 | 형식: `YYYY-NNNNNN` | 거부 |
| 계좌번호 | 숫자+하이픈, 10~20자 | 거부 |
| 전화번호 | 형식: `0XX-XXXX-XXXX` | 정규화 |
| 금액 | 양수, 소수점 2자리 | 거부 |
| 일시 | ISO 8601 형식 | 정규화 |

### 6.2 데이터 품질 점수

| 등급 | 점수 | 기준 |
|------|------|------|
| A | 95% 이상 | 모든 필수 항목 완비, 오류 없음 |
| B | 80~94% | 필수 항목 완비, 경미한 오류 |
| C | 60~79% | 일부 필수 항목 누락 |
| D | 60% 미만 | 재제출 요청 |

---

## 7. 보안 요구사항

### 7.1 민감정보 처리

| 정보 유형 | 처리 방식 | 저장 형태 |
|----------|----------|----------|
| 주민등록번호 | AES-256 암호화 | 암호문 |
| 계좌번호 | 마스킹 + 원본 별도 저장 | `110-***-***333` |
| 전화번호 | 마스킹 + 원본 별도 저장 | `010-****-5678` |

### 7.2 전송 보안

| 방식 | 요구사항 |
|------|---------|
| HTTPS | TLS 1.2 이상 |
| API 인증 | OAuth 2.0 / API Key |
| 파일 전송 | SFTP / 암호화 ZIP |

---

## 8. 문의처

| 구분 | 연락처 |
|------|--------|
| 기술 지원 | tech@ccop.go.kr |
| 데이터 표준 | standard@ccop.go.kr |
| API 발급 | api@ccop.go.kr |

---

## 부록 A: KICS 코드 매핑표

[별첨 문서 참조: KICS_CODE_MAPPING.xlsx]

## 부록 B: 샘플 데이터셋

[별첨 문서 참조: sample_data/]

## 부록 C: API 명세서

[별첨 문서 참조: API_SPECIFICATION.md]
