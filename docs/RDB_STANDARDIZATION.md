# CCOP RDB 표준화 가이드라인

> **Version**: 1.0  
> **Date**: 2026-01-29  
> **Scope**: PostgreSQL (Raw Data Store)

---

## 1. 개요

본 문서는 CCOP 시스템의 RDB(PostgreSQL) 스키마 설계 시 준수해야 할 표준화 원칙을 정의합니다. **KICS(형사사법정보시스템)** 데이터와의 호환성을 최우선으로 하며, 장기적인 데이터 품질 확보를 목표로 합니다.

## 2. 명명 자명 (Naming Convention)

### 2.1 기본 원칙
1. **Snake Case 사용**: 모든 테이블명, 컬럼명은 소문자와 언더스코어(`_`) 조합을 사용합니다. (예: `case_info`, `created_at`)
2. **단수형 테이블명**: 테이블 이름은 단수형 명사로 정의합니다. (예: `case` (O), `cases` (X))
3. **접두어/접미어 사용 자제**: `tb_`, `col_` 등의 헝가리안 표기법은 사용하지 않습니다.

### 2.2 KICS 용어 준수
경찰청 표준 용어 사전(KICS Data Dictionary)을 기준으로 영문 약어를 사용합니다.

| 한글명 | 표준 영문명 | 약어(컬럼명) | 비고 |
|-------|------------|-------------|------|
| 접수번호 | Receipt Number | `receipt_no` | - |
| 사건번호 | Case File Number | `flnm` | KICS 고유 용어 |
| 피의자 | Suspect | `suspect` | - |
| 피해자 | Victim | `victim` | - |
| 계좌번호 | Account Number | `actno` | `bacnt` 혼용 주의 |
| 전화번호 | Telephone Number | `telno` | `phone` 혼용 주의 |
| 주민등록번호 | Resident Registration Number | `rrn` | 암호화 필수 |

---

## 3. 데이터 타입 표준 (Data Type Standards)

| 데이터 유형 | PostgreSQL 타입 | 설명 |
|------------|-----------------|------|
| **기본 키 (PK)** | `BIGSERIAL` 또는 `BIGINT` | 자동 증가 정수형. 비즈니스 키(접수번호 등)는 PK로 쓰지 않고 UK로 설정. |
| **문자열** | `VARCHAR(n)` | 가변 길이 문자열. 길이 제한 필요. |
| **긴 텍스트** | `TEXT` | 진술 조서 등 4000자 이상 텍스트. |
| **일시** | `TIMESTAMPTZ` | Timezone 포함 일시 (`TIMESTAMP WITH TIME ZONE`). UTC 권장. |
| **금액** | `NUMERIC(15, 2)` | 부동소수점 오차 방지를 위해 `DOUBLE` 사용 금지. |
| **논리값** | `BOOLEAN` | `TRUE` / `FALSE` |
| **JSON** | `JSONB` | 비정형 메타데이터 저장 시 사용. (검색 효율 위해 `JSON` 대신 `JSONB`) |

---

## 4. 공통 컬럼 정의 (Audit Columns)

모든 테이블(코드성 테이블 제외)은 데이터 이력 추적을 위해 아래 공통 컬럼을 포함해야 합니다.

| 컬럼명 | 타입 | Null 여부 | 기본값 | 설명 |
|-------|------|----------|-------|------|
| `id` | `BIGSERIAL` | NN | - | 시스템 내부 식별자 (SK) |
| `created_at` | `TIMESTAMPTZ` | NN | `NOW()` | 최초 생성 일시 |
| `created_by` | `VARCHAR` | NN | `'SYSTEM'` | 생성자 ID |
| `updated_at` | `TIMESTAMPTZ` | NULL | - | 최종 수정 일시 |
| `updated_by` | `VARCHAR` | NULL | - | 수정자 ID |
| `is_deleted` | `BOOLEAN` | NN | `FALSE` | 논리적 삭제 플래그 (Soft Delete) |

---

## 5. 코드 관리 방안 (Common Codes)

시스템 전반에서 사용되는 코드(은행코드, 죄명코드, 수사상태 등)는 통합 코드 테이블에서 관리합니다.

### 5.1 테이블 구조 설게
```sql
-- 코드 그룹 (상위 코드)
CREATE TABLE code_group (
    group_code VARCHAR(20) PRIMARY KEY, -- 예: 'BANK_CD', 'CRIME_TYPE'
    group_name VARCHAR(50) NOT NULL,
    description TEXT,
    is_use BOOLEAN DEFAULT TRUE
);

-- 상세 코드
CREATE TABLE common_code (
    group_code VARCHAR(20) REFERENCES code_group(group_code),
    code VARCHAR(20) NOT NULL,          -- 예: '004' (국민은행)
    name VARCHAR(100) NOT NULL,         -- 예: 'KB국민은행'
    sort_order INT DEFAULT 0,
    is_use BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (group_code, code)
);
```

### 5.2 주요 코드 그룹 예시
- `BANK_CD`: 은행 식별 코드 (금융결제원 표준)
- `TELECOM_CD`: 통신사 코드 (SKT, KT, LGU+, MVNO)
- `CRIME_TYPE`: 죄명 분류 (사기, 횡령, 배임 등)
- `INVESTIGATION_STATUS`: 수사 진행 상태 (접수, 내사, 입건, 송치)

---

## 6. 인덱스 및 제약조건 표준

1. **PK/UK**: 모든 테이블은 PK를 가져야 하며, 비즈니스 식별자(접수번호 등)에는 반드시 `UNIQUE` 제약조건을 부여합니다.
2. **FK 인덱스**: 외래키(FK) 컬럼에는 반드시 인덱스를 생성하여 조인 성능을 확보합니다.
3. **명명 규칙**:
   - PK: `pk_<테이블명>` (예: `pk_case`)
   - UK: `uk_<테이블명>_<컬럼명>` (예: `uk_case_receipt_no`)
   - IDX: `idx_<테이블명>_<컬럼명>` (예: `idx_case_created_at`)

---

## 7. 보안 및 개인정보 (Security)

1. **암호화 컬럼**: 개인식별정보(PII)는 DB 레벨 또는 애플리케이션 레벨에서 반드시 암호화하여 저장합니다.
   - 대상: 주민등록번호(`rrn`), 휴대폰번호(`telno`), 계좌번호(`actno`), 비밀번호
2. **마스킹**: 로그나 화면 출력 시 PII는 마스킹 처리해야 합니다.
3. **접근 제어**: DB 계정은 App용(`app_user`), 분석용(`readonly_user`), 관리자용(`admin`)으로 분리합니다.
