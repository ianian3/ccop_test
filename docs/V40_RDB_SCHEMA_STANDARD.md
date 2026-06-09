# V4.0 표준 RDB 스키마 (L2 레이어)

**작성일**: 2026-05-21
**상위 표준**: [`CCOP_ONTOLOGY_V4.0.md`](CCOP_ONTOLOGY_V4.0.md)
**대상 DB**: PostgreSQL `tccopdb` (AgensGraph와 동거)
**역할**: 모든 데이터 소스가 수렴하는 **단일 표준 RDB** — V4.0 데이터 아키텍처의 L2 레이어

---

## 0. 위치 — V4.0 5단계 아키텍처에서의 역할

```
L1. 데이터 수집 ──→ L2. 표준 RDB ⭐ 본 문서 범위 ──→ L3. 온톨로지 변환 ──→ L4. 그래프 ──→ L5. 시각화
```

> **L2는 V4.0의 단일 진실(Single Source of Truth)**. 모든 외부 데이터는 L2 표준 RDB로 정규화되어 들어오고, L3 변환기는 L2만 입력으로 받는다.

---

## 1. 핵심 원칙

### 1.1 단일 데이터베이스
- **하나의 PostgreSQL 인스턴스** (`tccopdb`)에 모든 도메인 데이터 수렴
- 도메인별 **스키마(Schema)로 격리**: `tccop_official` (수사), `osint` (공개정보), `partner` (협력기관), `inference` (추론 결과)
- 공통 코드는 `public.tb_cmn_cd` 하나에서 관리

### 1.2 도메인 스키마 분리
```
tccopdb (PostgreSQL Database)
├─ public.*              -- 공통 코드, 표준화 매핑
├─ tccop_official.*      -- 수사 진정·사건 (tier 1)
├─ partner.*             -- 협력기관 (tier 2~3)
├─ osint.*               -- OSINT 크롤링 (tier 4)
├─ inference.*           -- 추론 결과
└─ stg_*                 -- 임시 ETL 스테이징
```

### 1.3 표준 식별자
모든 테이블의 PK는 다음 규칙을 따른다:
- 형식: `{도메인}_{객체타입}_{seq}` (예: `osint_site_00001`, `tccop_case_001`)
- 충돌 방지: 도메인 prefix 의무
- L3 변환 시 그래프 노드 식별자로 사용

### 1.4 V4.0 메타 컬럼 의무화
모든 테이블에 다음 컬럼 의무 포함:
```sql
source_id          VARCHAR(64) NOT NULL,  -- vt_src 참조
source_domain      VARCHAR(16) NOT NULL,  -- 'investigation' | 'osint' | 'partner' | 'inference'
reliability_tier   SMALLINT    NOT NULL,  -- 1~4
collected_at       TIMESTAMP   NOT NULL,
rec_created        TIMESTAMP   NOT NULL DEFAULT NOW(),
rec_updated        TIMESTAMP   NOT NULL DEFAULT NOW()
```

---

## 2. 도메인별 테이블 카탈로그

### 2.1 tccop_official 스키마 (수사 도메인, tier 1)

| 테이블 | PK | 핵심 컬럼 | L3 매핑 노드 |
|---|---|---|---|
| **tb_petition** | petition_id | rcpt_dt, crime_type_cd, damage_amt | vt_petition |
| **tb_case** | case_id (flnm) | incdnt_typ_cd, occrn_dt, damage_amount, status | vt_case |
| **tb_petition_clstr** | (sn_a, sn_b) | sim_score, sim_basis_cd | pt_cluster (6V-1 추론) |
| **tb_prsn** | psn_id | name, korn_flnm, dob, gender, risk_level | vt_psn |
| **tb_org** | org_id | org_name, org_category, brno | vt_org |
| **tb_role** | (case_id, psn_id, role_type) | role_type | suspect_in/victim_in/witness_in 엣지 |
| **tb_bacnt** | account_no | bank_cd, dpstr_nm, is_burner, is_frozen | vt_bacnt |
| **tb_telno** | telno | telco_nm, is_burner, imei | vt_telno |
| **tb_ip** | ip_addr | country, is_vpn, threat_score | vt_ip |
| **tb_email** | email_addr | domain, is_disposable | vt_email |
| **tb_crypto** | wallet_addr | blockchain, risk_score | vt_crypto |
| **tb_vhcl** | vhclno | vhcl_model, owner_nm | vt_vhcl |
| **tb_dev** | device_id | dev_type, imei, mac_addr | vt_dev |
| **tb_atm** | atm_id | bank_nm, address, lat, lng | vt_atm |
| **tb_loc** | loc_id | address, lat, lng | vt_loc |
| **tb_transfer** | transfer_id | amount, dlng_dt | vt_transfer |
| **tb_call** | call_id | call_dt, duration | vt_call |
| **tb_access** | access_id | access_dt, ip_addr | vt_access |
| **tb_movement** | mvmt_id | mvmt_dt, lat, lng | vt_movement |
| **tb_imprsn** | imprsn_id | imprsn_type_cd, dtct_dt | vt_impersonation |
| **tb_evidence** | evidence_id | case_id, evidence_type, target_id | eg_used_* 엣지 |

### 2.2 osint 스키마 (공개정보 도메인, tier 4)

| 테이블 | PK | 핵심 컬럼 | L3 매핑 노드 |
|---|---|---|---|
| **clct_page** | clct_page_id | url, site_nm, clct_dt, html_src | vt_src + vt_site |
| **atch_file** | atch_file_hash_cd | file_nm, clct_page_id | vt_file |
| **scrn_file** | scrn_file_id | clct_page_id | vt_file |
| **cmnty_dtl** | cmnty_dtl_id | cmnty_nm, wrtr_nm, content | vt_msg + vt_id |
| **sns_dtl** | sns_dtl_id | sns_nm, wrtr_nm, content | vt_msg + vt_id |
| **used_mkt_dtl** | used_mkt_dtl_id | used_mkt_pltfrm_nm, wrtr_nm | vt_msg + vt_id |
| **srch_engn_dtl** | srch_engn_dtl_id | clct_page_id, content | vt_msg |
| **chatrm** | chatrm_id | chatrm_pltfrm_nm, members | vt_site (channel) |
| **chat** | chat_id | chatrm_id, user_id, content | vt_msg + vt_id |
| **tb_the_cheat_fraud** | id | suspct_acnt (md5), fraud_amt | vt_bacnt + vt_transfer |
| **tb_the_cheat_url** | id | dmn_nm | vt_site |
| **tb_the_cheat_sms** | id | sndr_telno (md5), content | vt_telno + vt_msg |

### 2.3 partner 스키마 (협력기관, tier 2~3) — 향후

| 테이블 | PK | 도메인 | L3 매핑 |
|---|---|---|---|
| **tb_bank_acnt** | (bank_cd, acnt_no) | 은행 협력 | vt_bacnt |
| **tb_telco_call** | call_id | 통신사 | vt_call |
| **tb_stix_indicator** | indicator_id | 외부 CTI | vt_site / vt_ip / vt_file |

### 2.4 inference 스키마 (추론 결과)

| 테이블 | PK | 출처 | L3 매핑 |
|---|---|---|---|
| **tb_pt_cluster** | cluster_id | 6V-1 추론 | pt_cluster |
| **tb_site_cluster** | cluster_id | SimHash 추론 | site_cluster |
| **tb_sameAs_pair** | (left_id, right_id) | Cross-graph 추론 | sameAs 엣지 |

### 2.5 public 스키마 (공통 코드 SSOT)

| 테이블 | PK | 역할 |
|---|---|---|
| **tb_cmn_cd** | (cd_grp, cd_val) | 모든 enum 닫힌 어휘 (crime_type, risk_level 등) |
| **tb_bank_cd** | bank_cd | 은행 코드 표준 |
| **tb_country_cd** | country_cd | ISO 3166-1 alpha-2 |
| **tb_id_format_std** | id_format | NODE_ID_STANDARD RDB 매핑 |
| **tb_domain_usage_std** | (label, domain) | DOMAIN_USAGE RDB 매핑 |

---

## 3. 표준화 규칙 (Normalization Rules)

### 3.1 식별자 표준화

| 데이터 유형 | 원본 가능 형식 | **L2 표준 형식** | 정규화 함수 |
|---|---|---|---|
| URL | `http://www.daangn.com/x/`, `daangn.com` | `https://daangn.com/x` | `public.normalize_url()` |
| 전화번호 | `010-1234-5678`, `+82-10-1234-5678`, `01012345678` | `01012345678` (no-hyphen E.164 변형) | `public.normalize_telno()` |
| 계좌번호 | `1101111-22-3333`, `110-1111-2222` | `110-1111-2222` (dash-separated) | `public.normalize_account()` |
| 이메일 | 대소문자 혼용 | 소문자 전체 | `public.normalize_email()` |
| MD5 해시 | 32자 hex | 소문자 32자 hex | `public.normalize_md5()` |
| IPv4 | `192.168.001.001` | `192.168.1.1` | `public.normalize_ipv4()` |

### 3.2 표준화 PL/pgSQL 함수 위치
```sql
public.normalize_url(text)       RETURNS text   -- IMMUTABLE
public.normalize_telno(text)     RETURNS text   -- IMMUTABLE
public.normalize_account(text)   RETURNS text   -- IMMUTABLE
public.normalize_email(text)     RETURNS text   -- IMMUTABLE
public.normalize_md5(text)       RETURNS text   -- IMMUTABLE
public.normalize_ipv4(text)      RETURNS text   -- IMMUTABLE
public.hash_md5(text)            RETURNS text   -- 평문 → MD5 (sameAs 매칭용)
```

### 3.3 정규화 강제 정책

#### Option A: 컬럼 CHECK 제약
```sql
CREATE TABLE osint.clct_page (
    url      TEXT NOT NULL,
    url_norm TEXT GENERATED ALWAYS AS (public.normalize_url(url)) STORED,
    ...
    CHECK (url_norm = public.normalize_url(url))
);
CREATE INDEX ON osint.clct_page (url_norm);  -- 매칭 가속
```

#### Option B: BEFORE INSERT/UPDATE 트리거
원본 보존 + 자동 정규화 컬럼 채움.

**권장**: Option A (Generated Column) — 일관성 보장 + 인덱스 활용.

---

## 4. 공통 코드 마스터 (public.tb_cmn_cd)

### 4.1 스키마
```sql
CREATE TABLE public.tb_cmn_cd (
    cd_grp        VARCHAR(32) NOT NULL,  -- 코드 그룹 (예: 'CRIME_TYPE')
    cd_val        VARCHAR(32) NOT NULL,
    cd_nm_ko      TEXT,
    cd_nm_en      TEXT,
    sort_order    INT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    deprecated    BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (cd_grp, cd_val)
);
```

### 4.2 핵심 코드 그룹 (V4.0 표준)

| cd_grp | 의미 | 값 |
|---|---|---|
| **CRIME_TYPE** | 범죄 유형 | `보이스피싱`, `스미싱`, `메신저피싱`, `몸캠피싱`, `로맨스스캠`, `투자사기`, `중고거래사기`, ... |
| **RISK_LEVEL** | 위험도 | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |
| **CASE_STATUS** | 사건 상태 | `active`, `pending`, `closed`, `archived` |
| **DEV_TYPE** | 디바이스 유형 | `smartphone`, `pc`, `tablet`, `relay_station`, `router`, `other` |
| **MSG_TYPE** | 메시지 유형 | `community`, `sns`, `used_market`, `search_result`, `chat`, `sms`, `email`, `call_recording` |
| **SITE_TYPE** | 사이트 유형 | `web`, `phishing`, `malicious`, `chat_channel`, `used_market`, `community`, `search_engine` |
| **ROLE_TYPE** | 사건 역할 | `suspect`, `victim`, `witness`, `informant` |
| **DOMAIN** | V4.0 도메인 | `investigation`, `osint`, `partner`, `inference` |
| **ID_FORMAT** | 식별자 형식 | `plain`, `plain_dash`, `md5`, `sha1`, `sha256`, `no_hyphen_e164`, `normalized_url`, `ipv4_dotted`, `ipv6` |
| **RELIABILITY_TIER** | 신뢰도 등급 | `1`, `2`, `3`, `4` |
| **EVIDENCE_TYPE** | 증거 유형 | `account`, `phone`, `ip`, `file`, `transfer` |
| **IMPRSN_TYPE** | 사칭 유형 | `bank`, `prosecutor`, `police`, `delivery`, `family`, `other` |
| **BANK_CD** | 은행 코드 | (별도 tb_bank_cd 참조) |

### 4.3 ontology_service.py와의 동기화
```python
# ontology_service.py
VOCABULARY_V40 = {
    'vt_dev.dev_type': {
        'cd_grp': 'DEV_TYPE',
        'sync_with': 'public.tb_cmn_cd',
        'allowed': '<runtime fetch>',
    },
    # ...
}
```
**원칙**: 코드 SSOT는 `tb_cmn_cd`, Python은 캐시.

---

## 5. 외부 데이터 소스 어댑터 표준 (L1 → L2)

### 5.1 어댑터 책임 (Contract)
모든 외부 데이터 어댑터는 다음을 의무 수행:

```python
class L2Adapter(ABC):
    source_domain:     str    # 'osint' | 'partner' | ...
    reliability_tier:  int    # 1~4

    @abstractmethod
    def extract(self) -> Iterator[RawRecord]:
        """L1 원본 추출"""

    @abstractmethod
    def normalize(self, raw: RawRecord) -> dict:
        """L2 표준 컬럼 형식으로 변환 (정규화 함수 적용)"""

    @abstractmethod
    def insert_into_l2(self, normalized: dict):
        """L2 표준 테이블에 적재 (도메인 스키마 + V4.0 메타 자동)"""
```

### 5.2 어댑터별 책임 매핑

| 어댑터 | 도메인 | tier | L2 적재 테이블 |
|---|---|---|---|
| `OfficialRDBAdapter` | investigation | 1 | tccop_official.* |
| `OSINTCrawlerAdapter` | osint | 4 | osint.clct_page, osint.atch_file ... |
| `DeocheonAdapter` | osint | 4 | osint.tb_the_cheat_* |
| `BankPartnerAdapter` | partner | 2 | partner.tb_bank_acnt |
| `TelcoPartnerAdapter` | partner | 3 | partner.tb_telco_call |
| `STIXAdapter` | partner / external | 2-3 | partner.tb_stix_indicator |

### 5.3 신규 데이터 소스 온보딩 절차

```
1. 어댑터 클래스 작성 (L2Adapter 상속)
2. 도메인 스키마 결정 (tccop_official / osint / partner)
3. L2 테이블 매핑 (기존 사용 / 신규 추가)
   - 신규 테이블이면 V4.0 메타 컬럼 6종 의무
4. tb_cmn_cd 코드 추가 (필요 시)
5. L3 매핑 명세 갱신 (V40_RDB_TO_GRAPH_MAPPING.md)
6. 테스트 + 적재
```

---

## 6. 인덱스 / 성능 표준

### 6.1 의무 인덱스
모든 L2 테이블은 다음 인덱스 의무:

```sql
-- 1. PK 인덱스 (자동)

-- 2. 표준화 식별자 인덱스 (sameAs 매칭용)
CREATE INDEX ON osint.clct_page (url_norm);
CREATE INDEX ON tccop_official.tb_bacnt (account_no);
CREATE INDEX ON tccop_official.tb_telno (telno);

-- 3. 시간 컬럼 인덱스 (범위 질의)
CREATE INDEX ON tccop_official.tb_transfer (dlng_dt);
CREATE INDEX ON tccop_official.tb_call (call_dt);
CREATE INDEX ON osint.clct_page (collected_at);

-- 4. FK 컬럼 인덱스
CREATE INDEX ON osint.chat (chatrm_id);
CREATE INDEX ON osint.atch_file (clct_page_id);
```

### 6.2 파티셔닝 (대량 테이블)

| 테이블 | 파티션 키 | 파티션 단위 |
|---|---|---|
| osint.srch_engn_dtl (47만+) | collected_at | MONTHLY |
| osint.chat (29K+ /channel) | chatrm_id (LIST) or rec_created (MONTHLY) | – |
| tccop_official.tb_transfer | dlng_dt | YEARLY |
| tccop_official.tb_call | call_dt | YEARLY |

---

## 7. 데이터 품질 검증 표준

### 7.1 의무 검증 항목

| # | 검증 | 방법 | 주기 |
|---|---|---|---|
| Q1 | V4.0 메타 컬럼 NULL 검증 | `SELECT count(*) WHERE source_id IS NULL` | 일배치 |
| Q2 | 정규화 일관성 | `url = public.normalize_url(url)` 일치 검증 | 일배치 |
| Q3 | tb_cmn_cd 외래 무결성 | 모든 enum 컬럼이 tb_cmn_cd 존재 | 일배치 |
| Q4 | reliability_tier 일관성 | `tier`가 source_domain의 기본값과 일치하는지 | 주배치 |
| Q5 | 중복 식별자 | 동일 정규화 식별자가 여러 행 존재 시 경고 | 일배치 |
| Q6 | 누락 FK | osint.chat.chatrm_id가 chatrm에 존재하는지 | 일배치 |
| Q7 | 시간 일관성 | collected_at <= rec_created <= rec_updated | 일배치 |

### 7.2 검증 도구 — `OntologyValidator`
별도 산출물 (`docs/V40_VALIDATION_GUIDE.md` 향후 작성).

---

## 8. 마이그레이션 — 기존 RDB → V4.0 표준

### 8.1 마이그레이션 단계

```sql
-- Step 1: 도메인 스키마 생성
CREATE SCHEMA IF NOT EXISTS tccop_official;
CREATE SCHEMA IF NOT EXISTS osint;
CREATE SCHEMA IF NOT EXISTS partner;
CREATE SCHEMA IF NOT EXISTS inference;

-- Step 2: 기존 테이블 이동
ALTER TABLE public.tb_prsn SET SCHEMA tccop_official;
ALTER TABLE public.tb_case SET SCHEMA tccop_official;
-- ...
ALTER TABLE test_ccop_cp.clct_page SET SCHEMA osint;
ALTER TABLE test_ccop_cp.chat SET SCHEMA osint;
-- ...

-- Step 3: V4.0 메타 컬럼 추가
ALTER TABLE tccop_official.tb_prsn ADD COLUMN IF NOT EXISTS source_domain VARCHAR(16) DEFAULT 'investigation';
ALTER TABLE tccop_official.tb_prsn ADD COLUMN IF NOT EXISTS reliability_tier SMALLINT DEFAULT 1;
ALTER TABLE tccop_official.tb_prsn ADD COLUMN IF NOT EXISTS collected_at TIMESTAMP DEFAULT NOW();
-- ... (모든 테이블)

-- Step 4: 정규화 컬럼 추가 (Generated Column)
ALTER TABLE osint.clct_page ADD COLUMN url_norm TEXT GENERATED ALWAYS AS (public.normalize_url(url)) STORED;
CREATE INDEX ON osint.clct_page (url_norm);

-- Step 5: 공통 코드 마스터 import
INSERT INTO public.tb_cmn_cd VALUES ('CRIME_TYPE', '보이스피싱', '보이스피싱', 'Voice Phishing', 1, true, false);
-- ...
```

### 8.2 호환성 보존
- 기존 view (`test_ccop_cp.*`)는 backward-compat alias로 1년간 유지
- 외부 API/리포팅 코드의 점진 마이그레이션 허용

---

## 9. 보안 / 권한 표준

### 9.1 도메인 스키마별 권한

| Role | tccop_official | osint | partner | inference | public |
|---|---|---|---|---|---|
| `ccop_etl` | RW | RW | RW | RW | R |
| `ccop_query` | R | R | R | R | R |
| `ccop_admin` | RW | RW | RW | RW | RW |
| `osint_loader` | – | RW | – | – | R |
| `partner_loader` | – | – | RW | – | R |

### 9.2 민감 데이터 마스킹
- 개인정보 컬럼 (`name`, `korn_flnm`, `rrno_hash`)은 별도 view에서 마스킹
- 운영 외 환경에서는 원본 NULL 처리

---

## 10. V4.0 RDB 표준 산출물 매트릭스

| # | 산출물 | 위치 | 상태 |
|---|---|---|---|
| 1 | 본 문서 (RDB 스키마 표준) | `docs/V40_RDB_SCHEMA_STANDARD.md` | ✅ |
| 2 | RDB → 그래프 매핑 명세 | `docs/V40_RDB_TO_GRAPH_MAPPING.md` | 다음 단계 |
| 3 | 시각화 표준 (L5) | `docs/V40_VISUALIZATION_STANDARD.md` | 다음 단계 |
| 4 | 표준화 함수 (`normalize_*`) | `02_DDL_COMPLETE.sql` 등 | 부분 존재 |
| 5 | tb_cmn_cd 코드 마스터 | `docs/COMMON_CODES.md` | 부분 존재 |
| 6 | 마이그레이션 스크립트 | `migrations/v40_*.sql` | 향후 |
| 7 | DB 품질 검증 도구 | `app/services/rdb_validator.py` | 향후 |

---

## 11. 핵심 결론

> **V4.0의 L2 표준 RDB는 모든 데이터 도메인이 단일 PostgreSQL에서 schema로 격리되어 동거하면서, V4.0 메타 컬럼 6종 + 정규화 컬럼 + tb_cmn_cd 공통 코드를 의무화한다.** 이 표준 위에서 L3 변환기는 RDB만 입력으로 받아 V3.7 카탈로그 노드/엣지를 생성하고, 시각화는 그 그래프 위에서 동작한다.

---

**문서 끝**
