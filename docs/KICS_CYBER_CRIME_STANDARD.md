# 사이버 범죄 수사 KICS 기반 표준화 가이드

> **Version**: 1.0  
> **Date**: 2026-01-29  
> **Scope**: 사이버 범죄 수사 데이터 표준화

---

## 1. 개요

본 문서는 한국 경찰청 **KICS(형사사법정보시스템)** 표준을 기반으로 사이버 범죄 수사 데이터의 표준화 방안을 정의합니다.

### 1.1 표준화 목표

| 목표 | 설명 |
|------|------|
| **레거시 호환** | 기존 KICS 데이터와 1:1 매핑 가능 |
| **현장 친화** | 수사관에게 익숙한 용어 사용 |
| **법적 효력** | 증거 능력 확보를 위한 출처 추적 |
| **확장성** | 신규 범죄 유형 추가 용이 |

---

## 2. 사이버 범죄 유형별 KICS 코드

### 2.1 죄명 코드 체계 (CRM_CD)

| 코드 | 대분류 | 세부 유형 |
|------|-------|----------|
| `C100` | 사기 | 보이스피싱, 투자사기, 로맨스스캠 |
| `C200` | 공갈 | 몸캠피싱, 랜섬웨어 |
| `C300` | 금융범죄 | 자금세탁, 불법환전 |
| `C400` | 정보통신망 | 해킹, DDoS, 개인정보침해 |
| `C500` | 불법콘텐츠 | 불법도박, 음란물 유포 |

### 2.2 증거 유형 코드 (EVD_TP_CD)

| 코드 | 유형 | 법적 분류 | 수집 근거 |
|------|------|----------|----------|
| `E01` | 계좌정보 | 금융거래정보 | 특정금융정보법 §4 |
| `E02` | 전화번호 | 통신사실확인자료 | 통신비밀보호법 §13 |
| `E03` | IP주소 | 통신자료 | 전기통신사업법 §83 |
| `E04` | 웹사이트 | 인터넷기록 | 정보통신망법 |
| `E05` | 디지털파일 | 디지털증거 | 형사소송법 §106 |
| `E06` | 가상자산 | 가상자산정보 | 특정금융정보법 |

---

## 3. 엔티티별 KICS 표준 속성

### 3.1 사건 (Case)

| KICS 속성 | 타입 | 설명 | 예시 |
|-----------|------|------|------|
| `flnm` | VARCHAR(20) | 사건관리번호 | 2026-000123 |
| `rcpt_no` | VARCHAR(20) | 접수번호 | 서울중앙-2026-0001 |
| `crm_cd` | VARCHAR(10) | 죄명코드 | C100 |
| `dmg_amt` | NUMERIC | 피해금액 | 50000000 |
| `ocrn_dt` | DATE | 발생일자 | 2026-01-15 |
| `inv_nm` | VARCHAR(50) | 담당수사관 | 김수사 |

### 3.2 인물 (Person)

| KICS 속성 | 타입 | 설명 | 암호화 |
|-----------|------|------|--------|
| `nm` | VARCHAR(50) | 성명 | - |
| `rrn` | VARCHAR(200) | 주민등록번호 | **필수** |
| `role_cd` | VARCHAR(10) | 역할코드 | - |
| `telno` | VARCHAR(20) | 연락처 | 권장 |

**역할 코드 (ROLE_CD)**:
- `01`: 피의자(Suspect)
- `02`: 피해자(Victim)
- `03`: 참고인(Witness)
- `04`: 공범(Accomplice)

### 3.3 금융증거 (BankAccount)

| KICS 속성 | 타입 | 설명 |
|-----------|------|------|
| `actno` | VARCHAR(30) | 계좌번호 |
| `bnk_cd` | VARCHAR(3) | 은행코드 (금결원 표준) |
| `acct_nm` | VARCHAR(50) | 예금주명 |
| `acct_tp_cd` | VARCHAR(10) | 계좌유형 (입출금/정기예금) |

### 3.4 통신증거 (Phone)

| KICS 속성 | 타입 | 설명 |
|-----------|------|------|
| `telno` | VARCHAR(20) | 전화번호 |
| `carr_cd` | VARCHAR(2) | 통신사코드 |
| `ownr_nm` | VARCHAR(50) | 명의자 |
| `brnr_yn` | CHAR(1) | 대포폰여부 (Y/N) |

**통신사 코드 (CARR_CD)**:
- `01`: SKT
- `02`: KT
- `03`: LGU+
- `04`: 알뜰폰(MVNO)

---

## 4. 관계(Edge) 표준

### 4.1 KICS 표준 관계 타입

| 관계 | KICS 코드 | Domain → Range | 의미 |
|------|----------|----------------|------|
| 연루 | `invl_rel` | Case → Person | 사건 관련자 |
| 수행 | `prfm_rel` | Person → Action | 행위 수행 |
| 출금 | `wthd_rel` | Transfer → Account | 출금 계좌 |
| 입금 | `dpst_rel` | Transfer → Account | 입금 계좌 |
| 발신 | `clr_rel` | Call → Phone | 발신 번호 |
| 수신 | `cle_rel` | Call → Phone | 수신 번호 |
| 소유 | `own_rel` | Person → Evidence | 증거 소유 |
| 지배 | `ctrl_rel` | Person → Account | 실질 지배 |

### 4.2 관계 필수 속성

| 속성 | 타입 | 설명 | 필수 |
|------|------|------|------|
| `src_cd` | VARCHAR(20) | 출처코드 | ✅ |
| `src_dt` | DATE | 출처확보일 | ✅ |
| `cnfd_rt` | NUMERIC(3,2) | 신뢰도 | - |

**출처 코드 (SRC_CD)**:
- `TLCM_RPL`: 통신사 회신
- `BANK_RPL`: 금융기관 회신
- `FRSC_RPT`: 포렌식 보고서
- `STMT_REC`: 진술조서
- `CSV_IMP`: CSV 일괄적재 (검증필요)

---

## 5. 5대 사이버 범죄 표준 엔티티 구성

### 5.1 보이스피싱

```
필수 엔티티: Case, Person(피의자/피해자), Phone, BankAccount
필수 관계: involves, used_phone, used_account, transferred_to
```

### 5.2 몸캠피싱

```
필수 엔티티: Case, Person, Site(채팅앱), File(영상), BankAccount
필수 관계: digital_trace, related_file, used_account
```

### 5.3 투자사기

```
필수 엔티티: Case, Person, Site(투자사이트), BankAccount, CryptoWallet
필수 관계: digital_trace, used_account, used_crypto
```

### 5.4 스미싱

```
필수 엔티티: Case, Phone, Site(악성URL), BankAccount
필수 관계: used_phone, accessed_url, used_account
```

### 5.5 자금세탁

```
필수 엔티티: Case, Person, BankAccount(다수), ATM
필수 관계: transferred_to(다단계), withdrawn_at
```

---

## 6. 참고 문서

| 문서 | 설명 |
|------|------|
| [RDB_STANDARDIZATION.md](./RDB_STANDARDIZATION.md) | RDB 테이블 표준화 |
| [ONTOLOGY_GUIDE.md](./ONTOLOGY_GUIDE.md) | 온톨로지 상세 정의 |
| [CCOP_TECHNICAL_DESIGN.md](./CCOP_TECHNICAL_DESIGN.md) | 통합 기술 설계 |
