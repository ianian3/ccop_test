# KICS 기반 온톨로지 매핑 정의서

> **Version**: 1.0  
> **Date**: 2026-01-29  
> **Scope**: KICS ↔ 온톨로지 표준 매핑

---

## 1. 개요

본 문서는 **KICS(형사사법정보시스템)** 데이터 표준과 **CCOP 4-Layer 온톨로지** 간의 매핑 정의를 제공합니다.

### 1.1 매핑 원칙

| 원칙 | 설명 |
|------|------|
| **KICS 우선** | KICS에 정의된 용어가 있으면 그것을 우선 사용 |
| **4자 약어** | 속성명은 4자 이하 약어 사용 (`nm`, `dt`, `cd`) |
| **법적 분류** | 모든 엔티티에 법적 분류(Legal Category) 명시 |

---

## 2. 엔티티 매핑 (16종)

### 2.1 Layer 1: Case (사건)

| 온톨로지 Entity | GDB Label | KICS 테이블 | KICS 속성 매핑 |
|----------------|-----------|-------------|---------------|
| **Case** | `vt_case` | `TB_CASE` | `flnm`(사건번호), `rcpt_no`(접수), `crm_cd`(죄명) |
| **Investigation** | `vt_inv` | `TB_INV` | `inv_id`, `inv_nm`, `dept_cd` |

### 2.2 Layer 2: Actor (행위자)

| 온톨로지 Entity | GDB Label | KICS 테이블 | KICS 속성 매핑 |
|----------------|-----------|-------------|---------------|
| **Person** | `vt_psn` | `TB_PSN` | `nm`(성명), `rrn`(주민번호), `role_cd`(역할) |
| **Organization** | `vt_org` | `TB_CORP` | `corp_nm`, `biz_no`, `corp_tp_cd` |
| **Device** | `vt_dev` | `TB_DVCE` | `dvce_id`, `imei`, `mac_addr` |

### 2.3 Layer 3: Action (행위)

| 온톨로지 Entity | GDB Label | KICS 테이블 | KICS 속성 매핑 |
|----------------|-----------|-------------|---------------|
| **Transfer** | `vt_transfer` | `TB_FIN_TX` | `tx_id`, `amt`, `tx_dt` |
| **Call** | `vt_call` | `TB_COMM_REC` | `comm_id`, `dur_sec`, `comm_dt` |
| **Access** | `vt_access` | `TB_NET_LOG` | `log_id`, `acc_dt`, `act_cd` |
| **Message** | `vt_msg` | `TB_COMM_MSG` | `msg_id`, `msg_dt`, `plat_cd` |

### 2.4 Layer 4: Evidence (증거)

| 온톨로지 Entity | GDB Label | KICS 테이블 | KICS 속성 매핑 | 법적 분류 |
|----------------|-----------|-------------|---------------|----------|
| **BankAccount** | `vt_bacnt` | `TB_ACCT` | `actno`, `bnk_cd`, `acct_nm` | 금융거래정보 |
| **CryptoWallet** | `vt_crypto` | `TB_VASS` | `wlt_addr`, `vass_tp_cd` | 가상자산정보 |
| **Phone** | `vt_telno` | `TB_TELNO` | `telno`, `carr_cd`, `ownr_nm` | 통신사실확인자료 |
| **NetworkTrace** | `vt_ip` | `TB_IP` | `ip_addr`, `isp_cd`, `cntry_cd` | 통신자료 |
| **WebTrace** | `vt_site` | `TB_URL` | `url`, `dmn_nm`, `mlcs_yn` | 인터넷기록 |
| **FileTrace** | `vt_file` | `TB_FILE` | `file_nm`, `file_sz`, `hash_val` | 디지털증거 |
| **Location** | `vt_loc` | `TB_LOC` | `addr`, `lat`, `lng` | 위치정보 |
| **ATM** | `vt_atm` | `TB_ATM` | `atm_id`, `loc_addr`, `bnk_cd` | 물리증거 |

---

## 3. 관계(Edge) 매핑

### 3.1 핵심 관계

| 온톨로지 관계 | KICS 코드 | Domain → Range | KICS 의미 |
|--------------|----------|----------------|----------|
| `performed` | `PRFM_REL` | Person → Action | 행위 수행 |
| `involves` | `INVL_REL` | Case → Person | 사건 연루 |
| `belongs_to` | `BLNG_REL` | Person → Organization | 조직 소속 |
| `controls` | `CTRL_REL` | Person → Account | 실질 지배 |

### 3.2 행위-증거 관계

| 온톨로지 관계 | KICS 코드 | Domain → Range | KICS 의미 |
|--------------|----------|----------------|----------|
| `from_account` | `WTHD_ACCT` | Transfer → Account | 출금 계좌 |
| `to_account` | `DPST_ACCT` | Transfer → Account | 입금 계좌 |
| `caller` | `CLR_REL` | Call → Phone | 발신 번호 |
| `callee` | `CLE_REL` | Call → Phone | 수신 번호 |
| `accessed_from` | `ACC_FROM` | Access → IP | 접속 IP |
| `accessed_to` | `ACC_TO` | Access → Site | 접속 URL |

### 3.3 사건-증거 관계

| 온톨로지 관계 | KICS 코드 | Domain → Range | KICS 의미 |
|--------------|----------|----------------|----------|
| `digital_trace` | `DGTL_TRC` | Case → Evidence | 디지털 흔적 |
| `used_account` | `USE_ACCT` | Case → Account | 사용 계좌 |
| `used_phone` | `USE_TEL` | Case → Phone | 사용 전화 |

### 3.4 추론 관계

| 온톨로지 관계 | KICS 코드 | 추론 속성 | 설명 |
|--------------|----------|----------|------|
| `transferred_to` | `TRF_TO` | `transitive: True` | 자금 이체 (다단계 추적) |
| `accomplice_of` | `ACMP_REL` | `inferred: True` | 공범 관계 (추론) |
| `shared_resource` | `SHRD_RES` | `inferred: True` | 공유 증거 (추론) |

---

## 4. 속성(Property) 매핑

### 4.1 공통 속성

| 온톨로지 속성 | KICS 표준 | 타입 | 설명 |
|--------------|----------|------|------|
| `name` | `nm` | VARCHAR(50) | 성명 |
| `amount` | `amt` | NUMERIC(15,2) | 금액 |
| `timestamp` | `ts` | TIMESTAMPTZ | 발생 일시 |
| `date` | `dt` | DATE | 날짜 |
| `code` | `cd` | VARCHAR(10) | 코드 |
| `number` | `no` | VARCHAR(20) | 번호 |
| `type` | `tp` | VARCHAR(10) | 유형 |
| `id` | `id` | VARCHAR(50) | 식별자 |

### 4.2 RDB-GDB 연결 키

| 용도 | 속성명 | 설명 |
|------|--------|------|
| RDB 참조 | `rdb_id` | RDB 테이블의 PK 값 (BIGINT) |
| RDB 테이블 | `rdb_table` | 원본 RDB 테이블명 |

---

## 5. 법적 분류 코드 (Legal Category)

| 코드 | 한글명 | 법적 근거 |
|------|-------|----------|
| `FIN_TX` | 금융거래정보 | 특정금융거래정보법 §4 |
| `COMM_FAC` | 통신사실확인자료 | 통신비밀보호법 §13 |
| `COMM_DAT` | 통신자료 | 전기통신사업법 §83 |
| `INET_REC` | 인터넷기록 | 정보통신망법 |
| `DGTL_EVD` | 디지털증거 | 형사소송법 §106 |
| `VASS_TX` | 가상자산정보 | 특정금융정보법 |
| `PSN_INFO` | 피의자정보 | 형사소송법 |
| `LOC_INFO` | 위치정보 | 위치정보보호법 |

---

## 6. 코드 정의 위치

| 파일 | 정의 내용 |
|------|----------|
| `app/services/ontology_service.py` | `ENTITIES`, `RELATIONSHIPS` 딕셔너리 |
| `scripts/init.sql` | GDB VLABEL, ELABEL 정의 |
| `docs/KICS_CYBER_CRIME_STANDARD.md` | 사이버 범죄별 표준 정의 |

---

## 7. 참고 문서

- [ONTOLOGY_GUIDE.md](./ONTOLOGY_GUIDE.md): 4-Layer 온톨로지 상세
- [RDB_STANDARDIZATION.md](./RDB_STANDARDIZATION.md): RDB 표준화
- [CCOP_TECHNICAL_DESIGN.md](./CCOP_TECHNICAL_DESIGN.md): 통합 기술 설계
