# 11. ETRI 전처리 메타데이터 기관 CCOP 반영 결과 정리

**문서 버전**: v1.0
**작성일**: 2026-04-08
**시스템**: CCOP v3.2 (Cybercrime Investigation Graph Platform)
**분류**: 기술 설계서 (보고서용)

---

## 1. 개요

### 1.1 배경

ETRI(한국전자통신연구원)는 사이버범죄 관련 네트워크 트래픽·악성코드·위협 인텔리전스를 자체 분석·전처리하여 구조화된 메타데이터 형태로 수사기관에 제공한다. CCOP v3.2는 이 데이터를 **src_tier=2(간접 공식)** 계층으로 분류하고, KICS 공식 데이터(src_tier=1)와 OSINT(src_tier=3)의 중간 신뢰도 근거로 활용한다.

### 1.2 ETRI 제공 데이터 유형

| 데이터 구분 | 제공 형태 | 갱신 주기 |
|------------|---------|---------|
| 악성 IP 블랙리스트 | JSON / CSV | 일 1회 |
| 악성 도메인·URL 목록 | JSON / CSV | 일 1회 |
| 악성코드 해시 DB | JSON | 주 1회 |
| 사이버공격 캠페인 정보 | JSON (반정형) | 비정기 |
| 침해지표(IoC) 피드 | STIX 2.1 | 일 1회 |
| 취약점 악용 정보 (CVE 연계) | JSON | 비정기 |
| 봇넷 C2 서버 목록 | CSV | 일 1회 |

### 1.3 CCOP 내 위치

```
[데이터 신뢰도 계층]

Tier 1 ─ KICS 공식 DB     : evid_grade='A', src_tier=1  (경찰청·금감원 공식 데이터)
Tier 2 ─ ETRI 전처리 메타  : evid_grade='B', src_tier=2  (공인기관 분석·가공 데이터)
Tier 3 ─ OSINT/인터넷망    : evid_grade='C', src_tier=3  (공개 수집·추정 데이터)
```

ETRI 데이터로 생성된 그래프 엣지는 `evid_grade='B'`(간접증거)로 표시되며, UI에서 **주황색 점선**으로 구분된다.

---

## 2. 반영 대상 및 매핑 구조

### 2.1 ETRI 데이터 → CCOP 테이블 매핑

| ETRI 제공 데이터 | CCOP RDB 테이블 | 그래프 노드 | evid_grade |
|----------------|----------------|-----------|-----------|
| 악성 IP 블랙리스트 | TB_ETRI_IP_LIST | vt_ip | B |
| 악성 도메인·URL | TB_ETRI_DMN_LIST | vt_site | B |
| 악성코드 해시 | TB_ETRI_HASH_LIST | vt_file | B |
| 공격 캠페인 정보 | TB_ETRI_CAMPAIGN | vt_case (연계) | B |
| IoC 피드 (STIX) | TB_ETRI_IOC_FEED | 복합 노드 | B |
| C2 서버 목록 | TB_ETRI_C2_LIST | vt_ip + vt_site | B |
| CVE 취약점 악용 | TB_ETRI_CVE_EXPL | vt_file 연계 | B |

### 2.2 기존 온톨로지 엣지 속성 반영 결과

ETRI 데이터로 생성된 그래프 엣지에 v3.2 표준 속성이 일괄 적용되었다.

```cypher
-- ETRI 기반 엣지 표준 속성 (RdbToGraphService 적용)
SET r.evid_grade = 'B',
    r.src_tier   = 2,
    r.src_label  = 'ETRI',
    r.load_at    = datetime()
```

**적용된 엣지 유형:**

| 엣지 레이블 | 출발 노드 | 도착 노드 | 생성 조건 |
|------------|---------|---------|---------|
| `sourced_from` | vt_ip / vt_site / vt_file | vt_case | ETRI 데이터로 사건 연관 |
| `connects_to` | vt_ip | vt_ip | C2 통신 관계 |
| `resolves_to` | vt_site | vt_ip | 도메인→IP 결정 |
| `drops` | vt_site / vt_ip | vt_file | 악성코드 배포 경로 |
| `part_of_campaign` | vt_ip / vt_site / vt_file | vt_case | 캠페인 참여 |
| `exploits` | vt_file | (CVE 속성) | CVE 취약점 악용 |

---

## 3. 신규 RDB 테이블 설계

### 3.1 TB_ETRI_IP_LIST (ETRI 악성 IP 목록)

```sql
CREATE TABLE TB_ETRI_IP_LIST (
    SEQ             BIGSERIAL       PRIMARY KEY,
    IP_ADDR         VARCHAR(45)     NOT NULL,
    CIDR            VARCHAR(50),                        -- CIDR 표기 (범위 지정 시)
    THREAT_TYPE     VARCHAR(50),                        -- BOTNET/C2/SCANNER/BRUTEFORCE 등
    CAMPAIGN_ID     VARCHAR(100),                       -- 연관 캠페인 ID
    CONFIDENCE      SMALLINT        DEFAULT 80,         -- ETRI 내부 신뢰도 (0~100)
    COUNTRY_CD      CHAR(2),
    ASN_NO          VARCHAR(20),
    FIRST_SEEN_AT   TIMESTAMP,
    LAST_SEEN_AT    TIMESTAMP,
    ETRI_REF_ID     VARCHAR(100),                       -- ETRI 내부 참조 ID
    FEED_VERSION    VARCHAR(20),                        -- 피드 버전 (날짜 기반)
    IS_ACTIVE       CHAR(1)         NOT NULL DEFAULT 'Y',
    LOAD_AT         TIMESTAMP       NOT NULL DEFAULT NOW(),
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_ETRI_IP_LIST_ADDR ON TB_ETRI_IP_LIST (IP_ADDR);
CREATE INDEX IX_ETRI_IP_LIST_THREAT      ON TB_ETRI_IP_LIST (THREAT_TYPE);
CREATE INDEX IX_ETRI_IP_LIST_CAMPAIGN    ON TB_ETRI_IP_LIST (CAMPAIGN_ID);
CREATE INDEX IX_ETRI_IP_LIST_ACTIVE      ON TB_ETRI_IP_LIST (IS_ACTIVE) WHERE IS_ACTIVE = 'Y';
CREATE INDEX IX_ETRI_IP_LIST_LAST_SEEN   ON TB_ETRI_IP_LIST (LAST_SEEN_AT DESC);

COMMENT ON TABLE  TB_ETRI_IP_LIST            IS 'ETRI 전처리 - 악성 IP 블랙리스트 (src_tier=2)';
COMMENT ON COLUMN TB_ETRI_IP_LIST.CONFIDENCE IS 'ETRI 분석 신뢰도 (0=불확실, 100=확실)';
COMMENT ON COLUMN TB_ETRI_IP_LIST.ETRI_REF_ID IS 'ETRI 내부 분석보고서 참조 ID';
```

### 3.2 TB_ETRI_DMN_LIST (ETRI 악성 도메인·URL 목록)

```sql
CREATE TABLE TB_ETRI_DMN_LIST (
    SEQ             BIGSERIAL       PRIMARY KEY,
    DOMAIN_NM       VARCHAR(500)    NOT NULL,
    DOMAIN_TYPE     CHAR(1)         NOT NULL DEFAULT 'D',-- D:Domain U:URL
    THREAT_TYPE     VARCHAR(50),
    CAMPAIGN_ID     VARCHAR(100),
    CONFIDENCE      SMALLINT        DEFAULT 80,
    RESOLVE_IPS     TEXT,                               -- JSON 배열
    IS_PHISHING     CHAR(1)         DEFAULT 'N',
    IS_C2           CHAR(1)         DEFAULT 'N',        -- C2 서버 여부
    FIRST_SEEN_AT   TIMESTAMP,
    LAST_SEEN_AT    TIMESTAMP,
    ETRI_REF_ID     VARCHAR(100),
    FEED_VERSION    VARCHAR(20),
    IS_ACTIVE       CHAR(1)         NOT NULL DEFAULT 'Y',
    LOAD_AT         TIMESTAMP       NOT NULL DEFAULT NOW(),
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_ETRI_DMN_LIST_NM  ON TB_ETRI_DMN_LIST (DOMAIN_NM, DOMAIN_TYPE);
CREATE INDEX IX_ETRI_DMN_LIST_THREAT     ON TB_ETRI_DMN_LIST (THREAT_TYPE);
CREATE INDEX IX_ETRI_DMN_LIST_CAMPAIGN   ON TB_ETRI_DMN_LIST (CAMPAIGN_ID);
CREATE INDEX IX_ETRI_DMN_LIST_C2         ON TB_ETRI_DMN_LIST (IS_C2) WHERE IS_C2 = 'Y';
CREATE INDEX IX_ETRI_DMN_LIST_ACTIVE     ON TB_ETRI_DMN_LIST (IS_ACTIVE) WHERE IS_ACTIVE = 'Y';

COMMENT ON TABLE TB_ETRI_DMN_LIST IS 'ETRI 전처리 - 악성 도메인/URL 목록 (src_tier=2)';
```

### 3.3 TB_ETRI_HASH_LIST (ETRI 악성코드 해시 목록)

```sql
CREATE TABLE TB_ETRI_HASH_LIST (
    SEQ             BIGSERIAL       PRIMARY KEY,
    HASH_VAL        VARCHAR(128)    NOT NULL,
    HASH_TYPE       VARCHAR(10)     NOT NULL,           -- MD5/SHA1/SHA256
    FILE_NM         VARCHAR(500),
    MALWARE_FAMILY  VARCHAR(100),
    MALWARE_TYPE    VARCHAR(50),                        -- Trojan/Ransomware/Spyware 등
    THREAT_TYPE     VARCHAR(50),
    CAMPAIGN_ID     VARCHAR(100),
    CVE_LIST        TEXT,                               -- 악용 CVE JSON 배열 ["CVE-2024-1234"]
    CONFIDENCE      SMALLINT        DEFAULT 80,
    FIRST_SEEN_AT   TIMESTAMP,
    LAST_SEEN_AT    TIMESTAMP,
    ETRI_REF_ID     VARCHAR(100),
    FEED_VERSION    VARCHAR(20),
    IS_ACTIVE       CHAR(1)         NOT NULL DEFAULT 'Y',
    LOAD_AT         TIMESTAMP       NOT NULL DEFAULT NOW(),
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_ETRI_HASH_LIST_VAL ON TB_ETRI_HASH_LIST (HASH_VAL);
CREATE INDEX IX_ETRI_HASH_LIST_FAMILY     ON TB_ETRI_HASH_LIST (MALWARE_FAMILY);
CREATE INDEX IX_ETRI_HASH_LIST_CAMPAIGN   ON TB_ETRI_HASH_LIST (CAMPAIGN_ID);
CREATE INDEX IX_ETRI_HASH_LIST_ACTIVE     ON TB_ETRI_HASH_LIST (IS_ACTIVE) WHERE IS_ACTIVE = 'Y';

COMMENT ON TABLE  TB_ETRI_HASH_LIST          IS 'ETRI 전처리 - 악성코드 해시 목록 (src_tier=2)';
COMMENT ON COLUMN TB_ETRI_HASH_LIST.CVE_LIST IS '악용된 CVE 목록 JSON 배열';
```

### 3.4 TB_ETRI_CAMPAIGN (ETRI 공격 캠페인 정보)

```sql
CREATE TABLE TB_ETRI_CAMPAIGN (
    SEQ             BIGSERIAL       PRIMARY KEY,
    CAMPAIGN_ID     VARCHAR(100)    NOT NULL,           -- ETRI 캠페인 식별자
    CAMPAIGN_NM     VARCHAR(300)    NOT NULL,           -- 캠페인명 (예: "Lazarus Group 2026")
    THREAT_ACTOR    VARCHAR(200),                       -- 위협 행위자 그룹명
    ORIGIN_COUNTRY  CHAR(2),                            -- 공격 추정 국가
    START_AT        DATE,
    END_AT          DATE,                               -- NULL이면 현재 진행 중
    IS_ACTIVE       CHAR(1)         DEFAULT 'Y',
    TARGET_SECTORS  TEXT,                               -- 피해 분야 JSON 배열 (금융/의료/정부 등)
    TARGET_COUNTRIES TEXT,                              -- 피해 국가 JSON 배열
    MITRE_TACTICS   TEXT,                               -- MITRE ATT&CK 전술 JSON 배열
    MITRE_TECHNIQUES TEXT,                              -- MITRE ATT&CK 기법 JSON 배열
    IOC_COUNT       INTEGER         DEFAULT 0,          -- 연관 IoC 수
    SUMMARY         TEXT,                               -- 캠페인 요약 (한글)
    ETRI_REPORT_URL VARCHAR(500),                       -- ETRI 분석보고서 URL
    TLP             CHAR(1)         DEFAULT 'A',        -- 공유 등급
    CONFIDENCE      SMALLINT        DEFAULT 80,
    ETRI_REF_ID     VARCHAR(100),
    LOAD_AT         TIMESTAMP       NOT NULL DEFAULT NOW(),
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_ETRI_CAMPAIGN_ID    ON TB_ETRI_CAMPAIGN (CAMPAIGN_ID);
CREATE INDEX IX_ETRI_CAMPAIGN_ACTOR        ON TB_ETRI_CAMPAIGN (THREAT_ACTOR);
CREATE INDEX IX_ETRI_CAMPAIGN_ORIGIN       ON TB_ETRI_CAMPAIGN (ORIGIN_COUNTRY);
CREATE INDEX IX_ETRI_CAMPAIGN_ACTIVE       ON TB_ETRI_CAMPAIGN (IS_ACTIVE) WHERE IS_ACTIVE = 'Y';

COMMENT ON TABLE  TB_ETRI_CAMPAIGN               IS 'ETRI 전처리 - 사이버공격 캠페인 메타정보';
COMMENT ON COLUMN TB_ETRI_CAMPAIGN.MITRE_TACTICS IS '["TA0001","TA0002"] MITRE ATT&CK 전술 ID';
```

### 3.5 TB_ETRI_IOC_FEED (ETRI STIX 2.1 IoC 피드)

ETRI가 제공하는 STIX 2.1 형식 침해지표를 정규화하여 저장한다.

```sql
CREATE TABLE TB_ETRI_IOC_FEED (
    SEQ             BIGSERIAL       PRIMARY KEY,
    STIX_ID         VARCHAR(200)    NOT NULL,           -- STIX 2.1 Object ID
    STIX_TYPE       VARCHAR(50)     NOT NULL,           -- indicator/malware/threat-actor 등
    IOC_TYPE        VARCHAR(20),                        -- IP/DOMAIN/URL/HASH/EMAIL
    IOC_VAL         VARCHAR(1000),                      -- 정규화된 IoC 값
    IOC_VAL_HASH    VARCHAR(64),                        -- SHA-256 (검색용)
    PATTERN         TEXT,                               -- STIX 패턴 표현식
    CAMPAIGN_ID     VARCHAR(100),
    THREAT_ACTOR    VARCHAR(200),
    CONFIDENCE      SMALLINT        DEFAULT 80,
    VALID_FROM      TIMESTAMP,
    VALID_UNTIL     TIMESTAMP,
    KILL_CHAIN_PHASE VARCHAR(50),                       -- MITRE 킬체인 단계
    LABELS          TEXT,                               -- STIX 레이블 JSON 배열
    MODIFIED_AT     TIMESTAMP,                          -- STIX 수정 일시
    ETRI_REF_ID     VARCHAR(100),
    FEED_VERSION    VARCHAR(20),
    IS_ACTIVE       CHAR(1)         NOT NULL DEFAULT 'Y',
    LOAD_AT         TIMESTAMP       NOT NULL DEFAULT NOW(),
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_ETRI_IOC_FEED_STIX  ON TB_ETRI_IOC_FEED (STIX_ID);
CREATE INDEX IX_ETRI_IOC_FEED_TYPE         ON TB_ETRI_IOC_FEED (IOC_TYPE);
CREATE INDEX IX_ETRI_IOC_FEED_HASH         ON TB_ETRI_IOC_FEED (IOC_VAL_HASH);
CREATE INDEX IX_ETRI_IOC_FEED_CAMPAIGN     ON TB_ETRI_IOC_FEED (CAMPAIGN_ID);
CREATE INDEX IX_ETRI_IOC_FEED_VALID        ON TB_ETRI_IOC_FEED (VALID_FROM, VALID_UNTIL);
CREATE INDEX IX_ETRI_IOC_FEED_ACTIVE       ON TB_ETRI_IOC_FEED (IS_ACTIVE) WHERE IS_ACTIVE = 'Y';

COMMENT ON TABLE  TB_ETRI_IOC_FEED              IS 'ETRI 전처리 - STIX 2.1 IoC 피드 정규화 저장';
COMMENT ON COLUMN TB_ETRI_IOC_FEED.STIX_TYPE   IS 'indicator/malware/threat-actor/campaign 등';
COMMENT ON COLUMN TB_ETRI_IOC_FEED.PATTERN     IS "[url:value = 'http://evil.com'] STIX 패턴";
```

### 3.6 TB_ETRI_C2_LIST (ETRI C2 서버 목록)

```sql
CREATE TABLE TB_ETRI_C2_LIST (
    SEQ             BIGSERIAL       PRIMARY KEY,
    C2_ADDR         VARCHAR(500)    NOT NULL,           -- IP 또는 도메인
    C2_TYPE         CHAR(1)         NOT NULL DEFAULT 'I',-- I:IP D:Domain
    C2_PORT         INTEGER,                            -- 주요 포트
    C2_PROTOCOL     VARCHAR(20),                        -- HTTP/HTTPS/IRC/DNS/CUSTOM
    MALWARE_FAMILY  VARCHAR(100),                       -- 사용 악성코드 패밀리
    CAMPAIGN_ID     VARCHAR(100),
    THREAT_ACTOR    VARCHAR(200),
    CONFIDENCE      SMALLINT        DEFAULT 85,
    FIRST_SEEN_AT   TIMESTAMP,
    LAST_SEEN_AT    TIMESTAMP,
    ETRI_REF_ID     VARCHAR(100),
    FEED_VERSION    VARCHAR(20),
    IS_ACTIVE       CHAR(1)         NOT NULL DEFAULT 'Y',
    LOAD_AT         TIMESTAMP       NOT NULL DEFAULT NOW(),
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_ETRI_C2_LIST_ADDR ON TB_ETRI_C2_LIST (C2_ADDR, C2_TYPE, C2_PORT);
CREATE INDEX IX_ETRI_C2_LIST_FAMILY      ON TB_ETRI_C2_LIST (MALWARE_FAMILY);
CREATE INDEX IX_ETRI_C2_LIST_CAMPAIGN    ON TB_ETRI_C2_LIST (CAMPAIGN_ID);
CREATE INDEX IX_ETRI_C2_LIST_ACTIVE      ON TB_ETRI_C2_LIST (IS_ACTIVE) WHERE IS_ACTIVE = 'Y';

COMMENT ON TABLE TB_ETRI_C2_LIST IS 'ETRI 전처리 - 봇넷 C2 서버 목록 (src_tier=2)';
```

### 3.7 TB_ETRI_CVE_EXPL (ETRI CVE 취약점 악용 정보)

```sql
CREATE TABLE TB_ETRI_CVE_EXPL (
    SEQ             BIGSERIAL       PRIMARY KEY,
    CVE_ID          VARCHAR(20)     NOT NULL,           -- CVE-YYYY-NNNNN
    CVSS_SCORE      NUMERIC(3,1),                       -- CVSS v3.1 기준
    CVSS_VECTOR     VARCHAR(100),
    EXPLOIT_TYPE    VARCHAR(50),                        -- RCE/LPE/SQLi/XSS/DoS 등
    IS_WILD         CHAR(1)         DEFAULT 'N',        -- 실제 공격에 활용 여부
    CAMPAIGN_ID     VARCHAR(100),
    THREAT_ACTOR    VARCHAR(200),
    AFFECTED_PRODS  TEXT,                               -- 영향받는 제품 JSON 배열
    PATCH_AVAIL     CHAR(1)         DEFAULT 'N',        -- 패치 제공 여부
    PATCH_AT        DATE,
    EXPLOIT_URL     VARCHAR(500),                       -- 익스플로잇 코드 URL (공개된 경우)
    ETRI_REF_ID     VARCHAR(100),
    FEED_VERSION    VARCHAR(20),
    IS_ACTIVE       CHAR(1)         NOT NULL DEFAULT 'Y',
    LOAD_AT         TIMESTAMP       NOT NULL DEFAULT NOW(),
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_ETRI_CVE_EXPL_ID   ON TB_ETRI_CVE_EXPL (CVE_ID);
CREATE INDEX IX_ETRI_CVE_EXPL_WILD        ON TB_ETRI_CVE_EXPL (IS_WILD) WHERE IS_WILD = 'Y';
CREATE INDEX IX_ETRI_CVE_EXPL_CAMPAIGN    ON TB_ETRI_CVE_EXPL (CAMPAIGN_ID);
CREATE INDEX IX_ETRI_CVE_EXPL_CVSS        ON TB_ETRI_CVE_EXPL (CVSS_SCORE DESC);

COMMENT ON TABLE  TB_ETRI_CVE_EXPL         IS 'ETRI 전처리 - CVE 취약점 악용 정보 (src_tier=2)';
COMMENT ON COLUMN TB_ETRI_CVE_EXPL.IS_WILD IS 'Y: 실제 사이버공격에서 활용 확인됨';
```

---

## 4. ETL 파이프라인 반영 결과

### 4.1 ETRI 데이터 적재 흐름

```
[ETRI 데이터 수신]
  - 전용 SFTP / API Gateway 수신
  - 파일 형식: JSON / CSV / STIX 2.1 Bundle
        │
        ▼
[ETRI ETL 서비스] (app/middleware/services/etri_etl_service.py)
  EtriEtlService.load_ip_list()
  EtriEtlService.load_dmn_list()
  EtriEtlService.load_hash_list()
  EtriEtlService.load_campaign()
  EtriEtlService.load_ioc_feed_stix()    ← STIX 2.1 파서 포함
  EtriEtlService.load_c2_list()
  EtriEtlService.load_cve_expl()
        │
        ▼
[RDB 적재] TB_ETRI_* 테이블 UPSERT (ETRI_REF_ID 기준)
        │
        ▼
[그래프 연동] RdbToGraphService.from_etri_data()
  MERGE (n:vt_ip  {ip_addr: $ip})
  MERGE (n:vt_site{url:     $url})
  MERGE (n:vt_file{hash:    $hash})
  SET n.src_tier = 2, n.etri_ref = $ref_id

  -- sourced_from 엣지 (캠페인 연관 시)
  MATCH (s), (c:vt_case {case_no: $case_no})
  MERGE (s)-[r:sourced_from]->(c)
  SET r.evid_grade='B', r.src_tier=2, r.src_label='ETRI'
```

### 4.2 STIX 2.1 파서 구현 결과

ETRI가 제공하는 STIX 2.1 Bundle을 CCOP 스키마로 변환하는 파서를 구현했다.

```python
class StixParser:
    """
    ETRI STIX 2.1 Bundle → TB_ETRI_IOC_FEED 변환
    """
    SUPPORTED_TYPES = {
        "indicator":    "_parse_indicator",
        "malware":      "_parse_malware",
        "threat-actor": "_parse_threat_actor",
        "campaign":     "_parse_campaign",
        "relationship": "_parse_relationship",
    }

    @classmethod
    def parse_bundle(cls, bundle: dict) -> List[Dict]:
        """STIX Bundle → 정규화 레코드 목록"""
        results = []
        for obj in bundle.get("objects", []):
            stix_type = obj.get("type")
            parser_fn = cls.SUPPORTED_TYPES.get(stix_type)
            if parser_fn:
                record = getattr(cls, parser_fn)(obj)
                if record:
                    results.append(record)
        return results

    @classmethod
    def _parse_indicator(cls, obj: dict) -> Dict:
        """
        STIX indicator → IOC 값 추출
        pattern: "[ipv4-addr:value = '1.2.3.4']"
        """
        ioc_type, ioc_val = cls._extract_pattern(obj.get("pattern", ""))
        return {
            "stix_id":   obj["id"],
            "stix_type": "indicator",
            "ioc_type":  ioc_type,
            "ioc_val":   ioc_val,
            "ioc_val_hash": hashlib.sha256(ioc_val.encode()).hexdigest() if ioc_val else None,
            "pattern":   obj.get("pattern"),
            "confidence": obj.get("confidence", 80),
            "valid_from": obj.get("valid_from"),
            "valid_until": obj.get("valid_until"),
            "labels":    json.dumps(obj.get("labels", [])),
            "modified_at": obj.get("modified"),
        }

    @classmethod
    def _extract_pattern(cls, pattern: str):
        """
        STIX 패턴에서 IOC 타입과 값 추출
        "[ipv4-addr:value = '1.2.3.4']" → ('IP', '1.2.3.4')
        "[url:value = 'http://...']"     → ('URL', 'http://...')
        "[file:hashes.SHA256 = 'abc']"  → ('HASH', 'abc')
        """
        PATTERN_MAP = {
            r"ipv4-addr:value\s*=\s*'([^']+)'":       "IP",
            r"domain-name:value\s*=\s*'([^']+)'":     "DOMAIN",
            r"url:value\s*=\s*'([^']+)'":              "URL",
            r"file:hashes\.SHA256\s*=\s*'([^']+)'":   "HASH",
            r"email-addr:value\s*=\s*'([^']+)'":      "EMAIL",
        }
        for regex, ioc_type in PATTERN_MAP.items():
            m = re.search(regex, pattern, re.IGNORECASE)
            if m:
                return ioc_type, m.group(1)
        return None, None
```

---

## 5. 그래프 온톨로지 반영 결과

### 5.1 신규 엣지 레이블 추가

ETRI 캠페인 데이터 반영으로 기존 42개 엣지에 3개 추가, **총 45개 엣지**가 되었다.

| 신규 엣지 | 의미 | 출발 | 도착 | evid_grade |
|---------|------|------|------|-----------|
| `connects_to` | C2 통신 관계 | vt_ip | vt_ip | B |
| `drops` | 악성코드 배포 | vt_site / vt_ip | vt_file | B |
| `part_of_campaign` | 캠페인 참여 | vt_ip / vt_site / vt_file | vt_case | B |

### 5.2 기존 노드 속성 확장

ETRI 데이터 반영으로 그래프 노드에 추가된 속성:

```cypher
-- vt_ip 노드 ETRI 속성 추가
n.etri_threat_type  -- ETRI 분류 위협 유형
n.etri_campaign_id  -- 연관 캠페인 ID
n.etri_confidence   -- ETRI 분석 신뢰도
n.etri_ref_id       -- ETRI 내부 참조 ID
n.etri_last_seen    -- ETRI 마지막 탐지 일시
n.src_tier          -- 2 (ETRI 기반 노드)

-- vt_file 노드 ETRI 속성 추가
n.malware_family    -- 악성코드 패밀리명
n.malware_type      -- Trojan/Ransomware/Spyware
n.cve_list          -- 악용 CVE JSON 배열
n.etri_ref_id
```

### 5.3 vt_case 연계 결과 (캠페인 기반)

수사 사건번호와 ETRI 캠페인 간의 자동 연계 로직:

```python
def _link_case_to_campaign(case_no: str, graph_name: str):
    """
    수사 사건의 IOC가 ETRI 캠페인에 포함된 경우 자동 연계
    1. 사건 내 vt_ip / vt_site / vt_file 노드 추출
    2. TB_ETRI_IP_LIST / TB_ETRI_DMN_LIST / TB_ETRI_HASH_LIST에서 CAMPAIGN_ID 조회
    3. 매칭되는 캠페인 정보를 vt_case 노드 속성으로 추가
    4. part_of_campaign 엣지 생성
    """
    # 사건 내 IP 목록 조회
    case_ips = _get_case_ips(case_no, graph_name)
    for ip in case_ips:
        row = db.execute(
            "SELECT CAMPAIGN_ID, THREAT_TYPE, CONFIDENCE FROM TB_ETRI_IP_LIST "
            "WHERE IP_ADDR = %s AND IS_ACTIVE = 'Y'", (ip,)
        ).fetchone()
        if row:
            _create_part_of_campaign_edge(ip, case_no, row, graph_name)
```

---

## 6. UI 반영 결과

### 6.1 증거등급 시각화 (evid_grade='B' 확장)

기존 B등급(주황색 점선) 스타일에 ETRI 전용 배지 추가:

```javascript
// index.html - ETRI 데이터 배지
function renderEvidenceBadge(props) {
    if (props.src_label === 'ETRI') {
        return `<span class="badge badge-etri">🔬 ETRI</span>`;
    }
    // ...
}
```

**엣지 스타일 매핑:**

| evid_grade | src_label | 스타일 | 의미 |
|-----------|----------|-------|------|
| A | KICS | 실선, 파란색 | 공식 증거 |
| B | ETRI | 점선, 주황색 🔬 | ETRI 분석 데이터 |
| B | (기타) | 점선, 주황색 ⚠️ | 간접 추론 |
| C | OSINT | 점선, 빨간색 ❓ | OSINT 추정 |

### 6.2 노드 클릭 패널 ETRI 정보 표시

노드 tap 핸들러에 ETRI 캠페인 정보 카드 추가:

```javascript
// ETRI 캠페인 카드
if (nodeData.etri_campaign_id) {
    panelHtml += `
    <div class="bridge-key-card etri-card">
      <div class="bk-header">🔬 ETRI 캠페인 연계</div>
      <div class="bk-row">
        <span class="bk-label">캠페인 ID</span>
        <span class="bk-val">${nodeData.etri_campaign_id}</span>
      </div>
      <div class="bk-row">
        <span class="bk-label">위협 유형</span>
        <span class="bk-val">${nodeData.etri_threat_type || '-'}</span>
      </div>
      <div class="bk-row">
        <span class="bk-label">신뢰도</span>
        <span class="bk-val">${nodeData.etri_confidence || 80}%</span>
      </div>
    </div>`;
}
```

---

## 7. 반영 결과 수치 요약

### 7.1 DDL 변경 현황

| 구분 | 변경 전 | 변경 후 | 증감 |
|------|--------|--------|------|
| RDB 테이블 수 | 52개 | 59개 | +7개 |
| 그래프 엣지 레이블 수 | 42개 | 45개 | +3개 |
| 그래프 노드 속성 (평균) | 8개 | 13개 | +5개 |
| ETL 서비스 메서드 수 | 12개 | 19개 | +7개 |

### 7.2 신뢰도 계층 완성도

| 계층 | 데이터 소스 | 반영 테이블 수 | evid_grade |
|------|-----------|-------------|-----------|
| Tier 1 (공식) | KICS, 금감원, 경찰청 | 32개 | A |
| Tier 2 (전처리) | **ETRI** (이번 반영) | **7개** | **B** |
| Tier 3 (OSINT) | 인터넷망 수집 | 10개 | C |
| **합계** | | **49개** | |

> 기존 52개 테이블 중 비 ETRI/OSINT 메타·시스템 테이블 3개 포함 시 총 62개

### 7.3 bridge_key 매핑 확장 (21개 → 28개)

```python
_BRIDGE_KEY_MAP = {
    # ... 기존 21개 유지 ...

    # ETRI 신규 추가 (7개)
    "etri_ip":       ("TB_ETRI_IP_LIST",   "SEQ",         "ip_addr"),
    "etri_domain":   ("TB_ETRI_DMN_LIST",  "SEQ",         "domain_nm"),
    "etri_hash":     ("TB_ETRI_HASH_LIST", "SEQ",         "hash_val"),
    "etri_campaign": ("TB_ETRI_CAMPAIGN",  "CAMPAIGN_ID", "campaign_id"),
    "etri_ioc":      ("TB_ETRI_IOC_FEED",  "STIX_ID",     "stix_id"),
    "etri_c2":       ("TB_ETRI_C2_LIST",   "SEQ",         "c2_addr"),
    "etri_cve":      ("TB_ETRI_CVE_EXPL",  "CVE_ID",      "cve_id"),
}
```

---

## 8. CCOP 전체 데이터 계층 최종 구성

```
┌─────────────────────────────────────────────────────────────────────┐
│                   CCOP v3.2 데이터 계층 (완성)                       │
├─────────────┬────────────────────────────────────┬──────────────────┤
│ Tier        │ 주요 소스                            │ 신뢰도           │
├─────────────┼────────────────────────────────────┼──────────────────┤
│ 1 (공식)    │ KICS, 금감원 FIU, 경찰청 범죄DB      │ evid_grade = A   │
│             │ TB_INCDNT_*, TB_FIN_*, TB_PRSN 등  │ src_tier = 1     │
│             │ (32개 테이블)                        │ UI: 실선 파란색  │
├─────────────┼────────────────────────────────────┼──────────────────┤
│ 2 (전처리)  │ ETRI 악성코드·캠페인·IoC 피드         │ evid_grade = B   │
│             │ TB_ETRI_IP/DMN/HASH/CAMPAIGN 등    │ src_tier = 2     │
│             │ (7개 테이블) ← 이번 반영            │ UI: 점선 주황색🔬 │
├─────────────┼────────────────────────────────────┼──────────────────┤
│ 3 (OSINT)   │ VirusTotal, AbuseIPDB, Chainalysis  │ evid_grade = C   │
│             │ TB_OSINT_*, TB_WEB_* 등             │ src_tier = 3     │
│             │ (10개 테이블)                        │ UI: 점선 빨간색❓ │
└─────────────┴────────────────────────────────────┴──────────────────┘
```

---

## 9. 향후 과제

| 과제 | 내용 | 우선순위 |
|-----|------|---------|
| MITRE ATT&CK 시각화 | 캠페인 전술/기법을 그래프에 레이어로 표시 | 상 |
| ETRI 실시간 피드 구독 | SFTP 폴링 → Webhook 전환 | 중 |
| 캠페인 자동 연계 정확도 향상 | IOC 매칭 시 퍼지 매칭 적용 (IP 대역 포함) | 중 |
| STIX 관계(relationship) 그래프 전파 | STIX relationship 객체 → 그래프 엣지 자동 생성 | 하 |
| CVE 취약점 → 피해 시스템 연계 | TB_ETRI_CVE_EXPL → 피해 단말 노드 연결 | 하 |

---

## 10. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| v1.0 | 2026-04-08 | 최초 작성 — ETRI 전처리 메타데이터 CCOP v3.2 반영 결과 정리 |
