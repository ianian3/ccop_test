# CCOP RDB 스키마 설계 가이드

> 최종 업데이트: 2026-02-19

## 개요

CCOP 시스템은 **8개의 RDB 테이블**을 사용하여 수사 데이터를 관계형으로 저장합니다.
CSV 데이터가 먼저 RDB에 적재된 후, KICS 4-Layer 온톨로지 기반으로 **GDB(그래프 데이터베이스)**에 자동 변환됩니다.

```
CSV 업로드 → rdb_service.py → RDB 적재 → rdb_to_graph_service.py → GDB 변환
```

---

## 테이블 구조 (8개)

### 1. `rdb_cases` — 사건 정보

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `case_id` | INTEGER | **PK** (AUTO) | 내부 식별자 |
| `case_no` | VARCHAR | **UNIQUE**, NOT NULL | 접수번호 |
| `crime_name` | VARCHAR | | 죄명 |
| `crime_type` | VARCHAR | | 죄명 분류코드 |
| `reg_date` | DATE | | 등록일 |
| `org_name` | VARCHAR | | 수사기관명 |
| `status` | VARCHAR | | 수사 상태 |
| `created_at` | TIMESTAMP | DEFAULT now() | 생성일시 |

---

### 2. `rdb_suspects` — 피의자/닉네임

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `suspect_id` | INTEGER | **PK** (AUTO) | 내부 식별자 |
| `user_id` | VARCHAR | **UNIQUE**, NOT NULL | 피의자 ID (닉네임 겸용) |
| `name` | VARCHAR | | 이름/성명 |
| `nickname` | VARCHAR | | 닉네임 |
| `created_at` | TIMESTAMP | DEFAULT now() | 생성일시 |

---

### 3. `rdb_accounts` — 계좌

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `actno` | VARCHAR | **PK** | 계좌번호 |
| `bank_name` | VARCHAR | | 은행명 |
| `holder_name` | VARCHAR | | 예금주 |

---

### 4. `rdb_phones` — 전화번호

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `telno` | VARCHAR | **PK** | 전화번호 |
| `carrier` | VARCHAR | | 통신사 |

---

### 5. `rdb_transfers` — 이체 내역

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `trx_id` | VARCHAR | **PK** | 이체 ID (자동생성: `TRX_uuid`) |
| `amount` | NUMERIC | | 이체 금액 |
| `trx_date` | TIMESTAMP | | 이체 일시 |
| `sender_actno` | VARCHAR | | 송금 계좌 |
| `receiver_actno` | VARCHAR | | 수취 계좌 |

---

### 6. `rdb_calls` — 통화 내역

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `call_id` | VARCHAR | **PK** | 통화 ID (자동생성: `CALL_uuid`) |
| `duration` | INTEGER | | 통화 시간(초) |
| `call_date` | TIMESTAMP | | 통화 일시 |
| `caller_no` | VARCHAR | | 발신 번호 |
| `callee_no` | VARCHAR | | 수신 번호 |

---

### 7. `rdb_ips` — IP 주소

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `ip_id` | INTEGER | **PK** (AUTO) | 내부 식별자 |
| `ip_addr` | VARCHAR | **UNIQUE**, NOT NULL | IP 주소 |
| `isp` | VARCHAR | | ISP 정보 |
| `country` | VARCHAR | | 국가 |

---

### 8. `rdb_relations` — 엔티티 간 관계

| 컬럼 | 타입 | 제약 | 설명 |
| :--- | :--- | :--- | :--- |
| `rel_id` | INTEGER | **PK** (AUTO) | 내부 식별자 |
| `source_type` | VARCHAR | | 출발 타입 (case/suspect/account/phone/ip) |
| `source_value` | VARCHAR | | 출발 값 |
| `target_type` | VARCHAR | | 도착 타입 |
| `target_value` | VARCHAR | | 도착 값 |
| `rel_type` | VARCHAR | | 관계 유형 |
| `weight` | INTEGER | DEFAULT 1 | 관계 가중치 (동일 관계 등장 시 +1) |

> **UNIQUE**: `(source_type, source_value, target_type, target_value, rel_type)`

---

## RDB → GDB 변환 매핑

### 노드 변환

| RDB 테이블 | GDB 노드 | KICS Layer | 고유키 |
| :--- | :--- | :--- | :--- |
| `rdb_cases` | `vt_case` | Case | `flnm` |
| `rdb_suspects` | `vt_psn` | Actor | `id` (+ `nickname`) |
| `rdb_accounts` | `vt_bacnt` | Evidence | `actno` |
| `rdb_phones` | `vt_telno` | Evidence | `telno` |
| `rdb_ips` | `vt_ip` | Evidence | `ip_addr` |
| `rdb_transfers` | `vt_event` (type=transfer) | Event | `event_id` |
| `rdb_calls` | `vt_event` (type=call) | Event | `event_id` |

### 엣지(관계) 변환

#### 사건 ↔ 증거 (핵심 수사단서)

| RDB 관계 | GDB 엣지 | 온톨로지 | 설명 |
| :--- | :--- | :--- | :--- |
| case → account (evidence) | `eg_used_account` | ✅ | 사건에 사용된 계좌 |
| case → phone (evidence) | `eg_used_phone` | ✅ | 사건에 사용된 전화번호 |
| case → ip (evidence) | `eg_used_ip` | ✅ | 사건에 사용된 IP |

#### 닉네임/피의자 ↔ 소유 자산 (핵심 수사단서)

| RDB 관계 | GDB 엣지 | 온톨로지 | 설명 |
| :--- | :--- | :--- | :--- |
| suspect → account (owns) | `has_account` | ✅ | 닉네임 소유 계좌 |
| suspect → phone (owns) | `owns_phone` | ✅ | 닉네임 소유 전화 |
| suspect → ip (owns) | `used_ip` | ✅ | 닉네임 사용 IP |

#### 사건 ↔ 인물

| RDB 관계 | GDB 엣지 | 온톨로지 | 설명 |
| :--- | :--- | :--- | :--- |
| case → suspect (involves) | `involves` | ✅ | 사건 연루 인물 |

#### 이벤트 참여

| RDB 관계 | GDB 엣지 | 역할 | 설명 |
| :--- | :--- | :--- | :--- |
| account → transfer event | `participated_in` | sender/receiver | 이체에 참여한 계좌 |
| phone → call event | `participated_in` | caller/callee | 통화에 참여한 전화 |

#### 추론 관계 (자동 생성)

| GDB 엣지 | 설명 |
| :--- | :--- |
| `shared_resource` | 동일 계좌를 공유하는 사건 간 자동 연결 |

---

## CSV 컬럼 자동 인식 규칙

CSV 파일 업로드 시 컬럼명 키워드를 기반으로 자동 매핑됩니다:

| 카테고리 | 인식 키워드 | 적재 테이블 |
| :--- | :--- | :--- |
| 사건 | 접수, case, 번호 | `rdb_cases` |
| 죄명 | 죄명, crime | `rdb_cases.crime_name` |
| 날짜 | 등록일, date | `rdb_cases.reg_date` |
| 피의자 ID | ID, 아이디, 피의자 | `rdb_suspects.user_id` |
| 닉네임 | 닉네임, nickname, nick | `rdb_suspects.nickname` |
| 이름 | 이름, name, 성명 | `rdb_suspects.name` |
| 계좌 | 계좌, account, actno | `rdb_accounts` |
| 전화 | 전화, phone, tel | `rdb_phones` |
| IP | ip | `rdb_ips` |
| 금액 | 금액, amount | `rdb_transfers.amount` |
| 송금계좌 | 송금, 출금, sender | `rdb_transfers.sender_actno` |
| 수취계좌 | 수취, 입금, receiver | `rdb_transfers.receiver_actno` |
| 발신번호 | 발신, caller | `rdb_calls.caller_no` |
| 수신번호 | 수신, callee | `rdb_calls.callee_no` |
| 통화시간 | 시간, duration | `rdb_calls.duration` |

---

## 온톨로지 연동 파일 구조

| 파일 | 역할 |
| :--- | :--- |
| `ontology_service.py` | KICS 온톨로지 정의 (ENTITIES, RELATIONSHIPS, COLUMN_PATTERNS) |
| `rdb_service.py` | CSV → RDB 적재 (키워드 매칭, 관계 타입 결정) |
| `rdb_to_graph_service.py` | RDB → GDB 변환 (RELATION_TO_EDGE 매핑) |
| `relationship_inferencer.py` | AI 자동 분석 (규칙 + LLM 컬럼 타입 추론) |
