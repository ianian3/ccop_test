# 10. 인터넷망 수집DB 설계서

**문서 버전**: v1.0
**작성일**: 2026-04-07
**시스템**: CCOP v3.2 (Cybercrime Investigation Graph Platform)
**분류**: 기술 설계서 (보고서용)

---

## 1. 개요

### 1.1 목적

본 설계서는 CCOP v3.2에서 인터넷망(공개망)으로부터 수집되는 외부 위협 인텔리전스(Threat Intelligence) 및 OSINT(Open-Source Intelligence) 데이터를 저장·관리하기 위한 데이터베이스 구조를 정의한다.

인터넷망 수집DB는 사건수사 과정에서 수사관이 식별한 계좌번호·IP 주소·전화번호·도메인·암호화폐 지갑·악성코드 해시 등 핵심 식별자(IOC: Indicators of Compromise)에 대해 **외부 평판 정보를 자동 조회**하고, 그 결과를 CCOP 그래프 온톨로지의 `evid_grade = 'C'` 추정 근거로 활용할 수 있도록 설계한다.

### 1.2 적용 범위

| 수집 채널 | 주요 데이터 |
|-----------|------------|
| 외부 IP 평판 서비스 (VirusTotal, AbuseIPDB, Shodan) | IP 신뢰도, 악성 여부, 지역 정보 |
| 도메인 평판 서비스 (URLhaus, PhishTank, WHOIS) | 도메인 등록 정보, 악성 URL, 피싱 여부 |
| 파일 해시 서비스 (VirusTotal, MalwareBazaar) | 악성코드 해시, 탐지 엔진 결과 |
| 전화번호 조회 서비스 (NumVerify, 자체 신고DB) | 보이스피싱 신고 이력, 통신사 정보 |
| 금융 계좌 조회 (금융보안원 연계, 자체 신고DB) | 사기계좌 신고 횟수 |
| 암호화폐 지갑 분석 (Chainalysis, Elliptic) | 다크웹 거래 이력, 믹싱 여부 |
| 소셜미디어·다크웹 ID 수집 (수동/자동 크롤) | 아이디 활동 기록, 이상 패턴 |
| 웹 도메인·악성지표 수집 (자동 크롤) | C2 서버, 익스플로잇 키트 URL |

### 1.3 연계 시스템

```
[외부 API/OSINT 소스]
        │
        ▼
[인터넷망 수집 파이프라인]  ←──  스케줄러(Cron) / 트리거(API 요청)
        │
        ▼
[인터넷망 수집DB]  ─────────────────────────────────┐
  TB_OSINT_IP_REP     TB_OSINT_DMN_REP               │
  TB_OSINT_HASH_REP   TB_OSINT_PHON_REP              │
  TB_OSINT_ACNT_REP   TB_OSINT_WALLET_REP            │
  TB_OSINT_ID_REP     TB_WEB_DMN                     │
  TB_WEB_MLGN_IDC     TB_OSINT_COLLECT_LOG           │
        │                                             │
        ▼                                             │
[ETL 서비스 (RdbToGraphService)]                      │
  sourced_from 엣지 (evid_grade='C', src_tier=3)      │
        │                                             │
        ▼                                             │
[AgensGraph 그래프DB] ◄───────────────────────────────┘
  vt_ip / vt_site / vt_file / vt_telno / vt_bacnt
```

---

## 2. 수집 파이프라인 설계

### 2.1 파이프라인 구성

인터넷망 수집은 **3가지 트리거 방식**으로 동작한다.

| 트리거 유형 | 설명 | 주기 |
|------------|------|------|
| 정기 배치 (Cron) | 기등록 IOC 전체 재조회 | 1일 1회 (심야) |
| On-Demand (API 요청) | 수사관이 특정 IOC 즉시 조회 | 실시간 |
| ETL 연동 (이벤트) | transfer_case() 실행 시 자동 트리거 | 사건 등록 시 |

### 2.2 수집 흐름

```
1. IOC 식별
   수사관 입력 또는 RDB(KICS) 추출 → 조회 대상 IOC 목록 구성

2. 외부 API 호출
   API 키 로테이션 → Rate Limit 준수 → 결과 JSON 수신

3. 파싱 및 정규화
   원시 응답 → 공통 스키마 변환 → 신뢰도 점수(0~100) 계산

4. DB 적재
   UPSERT (IOC 값 기준) → TB_OSINT_*_REP 저장 → 수집 로그 기록

5. 그래프 연동
   ETL 서비스 호출 → 해당 노드에 sourced_from 엣지 추가
   evid_grade='C', src_tier=3
```

### 2.3 신뢰도 점수 산정 기준

```
REPUTATION_SCORE (0~100, 높을수록 위험)

0~19  : 정상 (LOW)       - 탐지 없음, 신고 이력 없음
20~49 : 주의 (MEDIUM)    - 소수 탐지 또는 신고 이력 존재
50~79 : 위험 (HIGH)      - 다수 탐지, 악성 판정 다수
80~100: 매우위험 (CRITICAL) - 블랙리스트 등재, 다크웹 연계
```

---

## 3. 테이블 정의

### 3.1 TB_OSINT_IP_REP (IP 평판 정보)

외부 IP에 대한 위협 인텔리전스 평판 정보를 저장한다.

```sql
CREATE TABLE TB_OSINT_IP_REP (
    SEQ             BIGSERIAL       PRIMARY KEY,
    IP_ADDR         VARCHAR(45)     NOT NULL,           -- IPv4/IPv6
    REP_SCORE       SMALLINT        NOT NULL DEFAULT 0, -- 0~100 (높을수록 위험)
    REP_GRADE       CHAR(1)         NOT NULL DEFAULT 'L',-- L/M/H/C
    IS_MALICIOUS    CHAR(1)         NOT NULL DEFAULT 'N',
    IS_PROXY        CHAR(1)         NOT NULL DEFAULT 'N',
    IS_TOR          CHAR(1)         NOT NULL DEFAULT 'N',
    IS_VPN          CHAR(1)         NOT NULL DEFAULT 'N',
    COUNTRY_CD      CHAR(2),                            -- ISO 3166-1 alpha-2
    ASN_NO          VARCHAR(20),                        -- AS번호 (예: AS15169)
    ASN_ORG         VARCHAR(200),                       -- AS 조직명
    ABUSE_CNT       INTEGER         DEFAULT 0,           -- 신고 횟수 (AbuseIPDB)
    LAST_ABUSE_AT   TIMESTAMP,                          -- 최근 신고 일시
    VT_DETECT_CNT   SMALLINT        DEFAULT 0,           -- VirusTotal 탐지 엔진 수
    VT_TOTAL_CNT    SMALLINT        DEFAULT 0,           -- VirusTotal 전체 엔진 수
    VT_PERMALINK    VARCHAR(500),                        -- VT 결과 링크
    SHODAN_PORTS    TEXT,                               -- Shodan 개방 포트 (JSON 배열)
    SHODAN_TAGS     TEXT,                               -- Shodan 태그 (JSON 배열)
    RAW_RESPONSE    JSONB,                              -- 원시 API 응답
    DATA_SRC        VARCHAR(50)     NOT NULL,           -- 'VIRUSTOTAL','ABUSEIPDB','SHODAN' 등
    COLLECT_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    EXPIRE_AT       TIMESTAMP,                          -- TTL (기본 7일)
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_OSINT_IP_REP_ADDR ON TB_OSINT_IP_REP (IP_ADDR);
CREATE INDEX IX_OSINT_IP_REP_SCORE    ON TB_OSINT_IP_REP (REP_SCORE DESC);
CREATE INDEX IX_OSINT_IP_REP_COUNTRY  ON TB_OSINT_IP_REP (COUNTRY_CD);
CREATE INDEX IX_OSINT_IP_REP_EXPIRE   ON TB_OSINT_IP_REP (EXPIRE_AT);

COMMENT ON TABLE  TB_OSINT_IP_REP              IS 'OSINT - IP 평판 정보';
COMMENT ON COLUMN TB_OSINT_IP_REP.REP_SCORE    IS '위험도 점수 (0=안전, 100=매우위험)';
COMMENT ON COLUMN TB_OSINT_IP_REP.REP_GRADE    IS 'L:Low M:Medium H:High C:Critical';
COMMENT ON COLUMN TB_OSINT_IP_REP.IS_TOR       IS 'Tor 출구 노드 여부';
COMMENT ON COLUMN TB_OSINT_IP_REP.SHODAN_PORTS IS '["22","80","443"] 형태 JSON';
```

### 3.2 TB_OSINT_DMN_REP (도메인 평판 정보)

도메인·URL에 대한 피싱·악성 여부 및 WHOIS 등록 정보를 저장한다.

```sql
CREATE TABLE TB_OSINT_DMN_REP (
    SEQ             BIGSERIAL       PRIMARY KEY,
    DOMAIN_NM       VARCHAR(500)    NOT NULL,           -- 도메인 또는 URL
    DOMAIN_TYPE     CHAR(1)         NOT NULL DEFAULT 'D',-- D:Domain U:URL
    REP_SCORE       SMALLINT        NOT NULL DEFAULT 0,
    REP_GRADE       CHAR(1)         NOT NULL DEFAULT 'L',
    IS_PHISHING     CHAR(1)         NOT NULL DEFAULT 'N',
    IS_MALWARE      CHAR(1)         NOT NULL DEFAULT 'N',
    IS_DEFACED      CHAR(1)         NOT NULL DEFAULT 'N',
    REGISTRAR_NM    VARCHAR(200),                       -- 도메인 등록기관
    REGISTRANT_NM   VARCHAR(200),                       -- 등록자명 (WHOIS)
    REGISTRANT_EML  VARCHAR(200),                       -- 등록자 이메일
    REG_AT          DATE,                               -- 도메인 등록일
    EXPIRE_REG_AT   DATE,                               -- 도메인 만료일
    NAMESERVERS     TEXT,                               -- JSON 배열
    RESOLVE_IPS     TEXT,                               -- 현재 A레코드 IP JSON 배열
    VT_DETECT_CNT   SMALLINT        DEFAULT 0,
    VT_TOTAL_CNT    SMALLINT        DEFAULT 0,
    VT_CATEGORIES   TEXT,                               -- VT 카테고리 JSON 배열
    URLHAUS_ID      VARCHAR(50),                        -- URLhaus 식별자
    PHISHTANK_ID    VARCHAR(50),                        -- PhishTank 식별자
    RAW_RESPONSE    JSONB,
    DATA_SRC        VARCHAR(50)     NOT NULL,
    COLLECT_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    EXPIRE_AT       TIMESTAMP,
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_OSINT_DMN_REP_NM   ON TB_OSINT_DMN_REP (DOMAIN_NM, DOMAIN_TYPE);
CREATE INDEX IX_OSINT_DMN_REP_SCORE       ON TB_OSINT_DMN_REP (REP_SCORE DESC);
CREATE INDEX IX_OSINT_DMN_REP_PHISH       ON TB_OSINT_DMN_REP (IS_PHISHING) WHERE IS_PHISHING = 'Y';
CREATE INDEX IX_OSINT_DMN_REP_REG         ON TB_OSINT_DMN_REP (REG_AT);
CREATE INDEX IX_OSINT_DMN_REP_EXPIRE      ON TB_OSINT_DMN_REP (EXPIRE_AT);

COMMENT ON TABLE  TB_OSINT_DMN_REP             IS 'OSINT - 도메인/URL 평판 정보';
COMMENT ON COLUMN TB_OSINT_DMN_REP.DOMAIN_TYPE IS 'D:도메인 U:URL';
COMMENT ON COLUMN TB_OSINT_DMN_REP.IS_DEFACED  IS '해킹된(변조된) 사이트 여부';
COMMENT ON COLUMN TB_OSINT_DMN_REP.RESOLVE_IPS IS '["1.2.3.4","5.6.7.8"] 형태 JSON';
```

### 3.3 TB_OSINT_HASH_REP (악성코드 해시 평판 정보)

파일 해시(MD5/SHA-1/SHA-256)에 대한 악성코드 탐지 결과를 저장한다.

```sql
CREATE TABLE TB_OSINT_HASH_REP (
    SEQ             BIGSERIAL       PRIMARY KEY,
    HASH_VAL        VARCHAR(128)    NOT NULL,           -- MD5(32)/SHA1(40)/SHA256(64)
    HASH_TYPE       VARCHAR(10)     NOT NULL,           -- MD5/SHA1/SHA256
    FILE_NM         VARCHAR(500),                       -- 원본 파일명 (알려진 경우)
    FILE_SIZE       BIGINT,                             -- 파일 크기 (bytes)
    FILE_TYPE       VARCHAR(100),                       -- MIME 타입
    REP_SCORE       SMALLINT        NOT NULL DEFAULT 0,
    REP_GRADE       CHAR(1)         NOT NULL DEFAULT 'L',
    IS_MALICIOUS    CHAR(1)         NOT NULL DEFAULT 'N',
    MALWARE_FAMILY  VARCHAR(100),                       -- 악성코드 패밀리명 (예: Emotet)
    MALWARE_TYPE    VARCHAR(50),                        -- Trojan/Ransomware/Spyware 등
    VT_DETECT_CNT   SMALLINT        DEFAULT 0,
    VT_TOTAL_CNT    SMALLINT        DEFAULT 0,
    VT_SCAN_AT      TIMESTAMP,                          -- VT 스캔 일시
    VT_PERMALINK    VARCHAR(500),
    MB_ID           VARCHAR(100),                       -- MalwareBazaar 식별자
    MB_TAGS         TEXT,                               -- MalwareBazaar 태그 JSON 배열
    FIRST_SEEN_AT   TIMESTAMP,                          -- 최초 탐지 일시
    LAST_SEEN_AT    TIMESTAMP,                          -- 최근 탐지 일시
    RAW_RESPONSE    JSONB,
    DATA_SRC        VARCHAR(50)     NOT NULL,
    COLLECT_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    EXPIRE_AT       TIMESTAMP,
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_OSINT_HASH_REP_VAL  ON TB_OSINT_HASH_REP (HASH_VAL);
CREATE INDEX IX_OSINT_HASH_REP_TYPE        ON TB_OSINT_HASH_REP (HASH_TYPE);
CREATE INDEX IX_OSINT_HASH_REP_FAMILY      ON TB_OSINT_HASH_REP (MALWARE_FAMILY);
CREATE INDEX IX_OSINT_HASH_REP_SCORE       ON TB_OSINT_HASH_REP (REP_SCORE DESC);
CREATE INDEX IX_OSINT_HASH_REP_EXPIRE      ON TB_OSINT_HASH_REP (EXPIRE_AT);

COMMENT ON TABLE  TB_OSINT_HASH_REP             IS 'OSINT - 악성코드 파일 해시 평판 정보';
COMMENT ON COLUMN TB_OSINT_HASH_REP.HASH_TYPE   IS 'MD5 / SHA1 / SHA256';
COMMENT ON COLUMN TB_OSINT_HASH_REP.MALWARE_TYPE IS 'Trojan/Ransomware/Spyware/Adware/Worm 등';
```

### 3.4 TB_OSINT_PHON_REP (전화번호 평판 정보)

보이스피싱·스팸 관련 전화번호 신고 이력 및 평판 정보를 저장한다.

```sql
CREATE TABLE TB_OSINT_PHON_REP (
    SEQ             BIGSERIAL       PRIMARY KEY,
    TELNO           VARCHAR(30)     NOT NULL,           -- 전화번호 (E.164 정규화)
    TELNO_ORIG      VARCHAR(30),                        -- 원본 입력값
    COUNTRY_CD      CHAR(2),
    CARRIER_NM      VARCHAR(100),                       -- 통신사명
    LINE_TYPE       VARCHAR(20),                        -- MOBILE/LANDLINE/VOIP/UNKNOWN
    REP_SCORE       SMALLINT        NOT NULL DEFAULT 0,
    REP_GRADE       CHAR(1)         NOT NULL DEFAULT 'L',
    IS_VOICEPHISH   CHAR(1)         NOT NULL DEFAULT 'N',-- 보이스피싱 신고 여부
    IS_SPAM         CHAR(1)         NOT NULL DEFAULT 'N',
    REPORT_CNT      INTEGER         DEFAULT 0,           -- 신고 횟수
    FIRST_REPORT_AT TIMESTAMP,                          -- 최초 신고 일시
    LAST_REPORT_AT  TIMESTAMP,                          -- 최근 신고 일시
    REPORT_SRCS     TEXT,                               -- 신고 출처 JSON 배열 (경찰청/금감원 등)
    RELATED_CASES   TEXT,                               -- 연관 사건번호 JSON 배열
    RAW_RESPONSE    JSONB,
    DATA_SRC        VARCHAR(50)     NOT NULL,
    COLLECT_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    EXPIRE_AT       TIMESTAMP,
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_OSINT_PHON_REP_NO   ON TB_OSINT_PHON_REP (TELNO);
CREATE INDEX IX_OSINT_PHON_REP_VOICEPHISH  ON TB_OSINT_PHON_REP (IS_VOICEPHISH) WHERE IS_VOICEPHISH = 'Y';
CREATE INDEX IX_OSINT_PHON_REP_SCORE       ON TB_OSINT_PHON_REP (REP_SCORE DESC);
CREATE INDEX IX_OSINT_PHON_REP_EXPIRE      ON TB_OSINT_PHON_REP (EXPIRE_AT);

COMMENT ON TABLE  TB_OSINT_PHON_REP              IS 'OSINT - 전화번호 평판/신고 정보';
COMMENT ON COLUMN TB_OSINT_PHON_REP.LINE_TYPE    IS 'MOBILE:휴대폰 LANDLINE:유선 VOIP:인터넷전화';
COMMENT ON COLUMN TB_OSINT_PHON_REP.REPORT_SRCS  IS '["경찰청","금감원","민간신고"] 형태 JSON';
```

### 3.5 TB_OSINT_ACNT_REP (금융 계좌 평판 정보)

사기계좌 신고 이력 및 금융정보분석원(FIU) 연계 의심 계좌 정보를 저장한다.

```sql
CREATE TABLE TB_OSINT_ACNT_REP (
    SEQ             BIGSERIAL       PRIMARY KEY,
    BACNT_NO        VARCHAR(50)     NOT NULL,           -- 계좌번호 (마스킹 or 해시)
    BACNT_HASH      VARCHAR(64)     NOT NULL,           -- SHA-256 해시 (검색용)
    BANK_CD         VARCHAR(10),                        -- 금융기관 코드 (금감원 기준)
    BANK_NM         VARCHAR(100),
    REP_SCORE       SMALLINT        NOT NULL DEFAULT 0,
    REP_GRADE       CHAR(1)         NOT NULL DEFAULT 'L',
    IS_FRAUD        CHAR(1)         NOT NULL DEFAULT 'N',-- 사기계좌 신고 여부
    IS_FROZEN       CHAR(1)         NOT NULL DEFAULT 'N',-- 지급정지 여부
    REPORT_CNT      INTEGER         DEFAULT 0,
    TOTAL_FRAUD_AMT BIGINT          DEFAULT 0,          -- 신고된 피해액 합계 (원)
    FIRST_REPORT_AT TIMESTAMP,
    LAST_REPORT_AT  TIMESTAMP,
    REPORT_SRCS     TEXT,                               -- 신고 출처 JSON 배열
    FIU_FLAG        CHAR(1)         DEFAULT 'N',        -- FIU 의심거래 보고 여부
    RELATED_CASES   TEXT,                               -- 연관 사건번호 JSON 배열
    RAW_RESPONSE    JSONB,
    DATA_SRC        VARCHAR(50)     NOT NULL,
    COLLECT_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    EXPIRE_AT       TIMESTAMP,
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_OSINT_ACNT_REP_HASH  ON TB_OSINT_ACNT_REP (BACNT_HASH);
CREATE INDEX IX_OSINT_ACNT_REP_NO           ON TB_OSINT_ACNT_REP (BACNT_NO);
CREATE INDEX IX_OSINT_ACNT_REP_FRAUD        ON TB_OSINT_ACNT_REP (IS_FRAUD) WHERE IS_FRAUD = 'Y';
CREATE INDEX IX_OSINT_ACNT_REP_BANK         ON TB_OSINT_ACNT_REP (BANK_CD);
CREATE INDEX IX_OSINT_ACNT_REP_SCORE        ON TB_OSINT_ACNT_REP (REP_SCORE DESC);

COMMENT ON TABLE  TB_OSINT_ACNT_REP              IS 'OSINT - 금융 계좌 사기 평판 정보';
COMMENT ON COLUMN TB_OSINT_ACNT_REP.BACNT_NO     IS '계좌번호 (운용 정책에 따라 마스킹 적용 가능)';
COMMENT ON COLUMN TB_OSINT_ACNT_REP.BACNT_HASH   IS '계좌번호 SHA-256 해시 (검색 기준키)';
COMMENT ON COLUMN TB_OSINT_ACNT_REP.FIU_FLAG     IS 'Y: FIU 의심거래 보고(STR) 대상';
```

### 3.6 TB_OSINT_WALLET_REP (암호화폐 지갑 평판 정보)

암호화폐 지갑 주소에 대한 다크웹 연계·믹싱 여부·위험도 정보를 저장한다.

```sql
CREATE TABLE TB_OSINT_WALLET_REP (
    SEQ             BIGSERIAL       PRIMARY KEY,
    WALLET_ADDR     VARCHAR(200)    NOT NULL,           -- 지갑 주소
    COIN_TYPE       VARCHAR(20)     NOT NULL,           -- BTC/ETH/USDT/XMR 등
    REP_SCORE       SMALLINT        NOT NULL DEFAULT 0,
    REP_GRADE       CHAR(1)         NOT NULL DEFAULT 'L',
    IS_DARKWEB      CHAR(1)         NOT NULL DEFAULT 'N',-- 다크웹 거래 연계
    IS_MIXING       CHAR(1)         NOT NULL DEFAULT 'N',-- 믹서/텀블러 사용 여부
    IS_SANCTIONED   CHAR(1)         NOT NULL DEFAULT 'N',-- OFAC 제재 대상
    IS_EXCHANGE     CHAR(1)         NOT NULL DEFAULT 'N',-- 거래소 주소 여부
    EXCHANGE_NM     VARCHAR(100),                       -- 거래소명 (식별 시)
    RISK_CATEGORY   VARCHAR(100),                       -- 위험 카테고리
    TOTAL_RECV_BTC  NUMERIC(20,8),                      -- 총 수신액 (BTC 기준)
    TOTAL_SENT_BTC  NUMERIC(20,8),                      -- 총 송신액
    TXN_COUNT       INTEGER         DEFAULT 0,           -- 거래 횟수
    FIRST_SEEN_AT   TIMESTAMP,
    LAST_SEEN_AT    TIMESTAMP,
    CLUSTER_ID      VARCHAR(100),                       -- 클러스터 식별자 (체이널리시스)
    CLUSTER_NM      VARCHAR(200),                       -- 클러스터 이름 (알려진 경우)
    RAW_RESPONSE    JSONB,
    DATA_SRC        VARCHAR(50)     NOT NULL,           -- 'CHAINALYSIS','ELLIPTIC' 등
    COLLECT_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    EXPIRE_AT       TIMESTAMP,
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_OSINT_WALLET_REP_ADDR ON TB_OSINT_WALLET_REP (WALLET_ADDR, COIN_TYPE);
CREATE INDEX IX_OSINT_WALLET_REP_DARK        ON TB_OSINT_WALLET_REP (IS_DARKWEB) WHERE IS_DARKWEB = 'Y';
CREATE INDEX IX_OSINT_WALLET_REP_SANCTION    ON TB_OSINT_WALLET_REP (IS_SANCTIONED) WHERE IS_SANCTIONED = 'Y';
CREATE INDEX IX_OSINT_WALLET_REP_COIN        ON TB_OSINT_WALLET_REP (COIN_TYPE);
CREATE INDEX IX_OSINT_WALLET_REP_SCORE       ON TB_OSINT_WALLET_REP (REP_SCORE DESC);

COMMENT ON TABLE  TB_OSINT_WALLET_REP              IS 'OSINT - 암호화폐 지갑 주소 평판 정보';
COMMENT ON COLUMN TB_OSINT_WALLET_REP.IS_MIXING    IS '믹서/텀블러/CoinJoin 사용 여부';
COMMENT ON COLUMN TB_OSINT_WALLET_REP.IS_SANCTIONED IS 'OFAC SDN 리스트 제재 대상 여부';
COMMENT ON COLUMN TB_OSINT_WALLET_REP.CLUSTER_ID   IS '체이널리시스 체계 클러스터 식별자';
```

### 3.7 TB_OSINT_ID_REP (인터넷 ID 평판 정보)

소셜미디어·다크웹·포럼 등에서 수집된 계정(닉네임/ID)의 활동 기록 및 이상 패턴을 저장한다.

```sql
CREATE TABLE TB_OSINT_ID_REP (
    SEQ             BIGSERIAL       PRIMARY KEY,
    ACNT_ID         VARCHAR(200)    NOT NULL,           -- 인터넷 아이디/닉네임
    PLATFORM_CD     VARCHAR(30)     NOT NULL,           -- TELEGRAM/DARKWEB/FORUM/TWITTER 등
    PLATFORM_URL    VARCHAR(500),                       -- 플랫폼 URL (채널/프로필)
    REP_SCORE       SMALLINT        NOT NULL DEFAULT 0,
    REP_GRADE       CHAR(1)         NOT NULL DEFAULT 'L',
    IS_DARKWEB      CHAR(1)         NOT NULL DEFAULT 'N',
    IS_VENDOR       CHAR(1)         NOT NULL DEFAULT 'N',-- 다크웹 판매자 여부
    ACTIVITY_SUMMARY TEXT,                              -- 활동 요약 (수동 입력 또는 AI 생성)
    KEYWORDS        TEXT,                               -- 관련 키워드 JSON 배열
    LINKED_IPS      TEXT,                               -- 연관 IP JSON 배열
    LINKED_WALLETS  TEXT,                               -- 연관 지갑 JSON 배열
    POST_CNT        INTEGER         DEFAULT 0,           -- 게시물 수 (수집된 범위 내)
    FIRST_SEEN_AT   TIMESTAMP,
    LAST_SEEN_AT    TIMESTAMP,
    SCREENSHOT_PATH VARCHAR(500),                       -- 스크린샷 저장 경로
    COLLECT_METHOD  VARCHAR(20),                        -- AUTO/MANUAL
    RAW_RESPONSE    JSONB,
    DATA_SRC        VARCHAR(50)     NOT NULL,
    COLLECT_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    EXPIRE_AT       TIMESTAMP,
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_OSINT_ID_REP       ON TB_OSINT_ID_REP (ACNT_ID, PLATFORM_CD);
CREATE INDEX IX_OSINT_ID_REP_DARK         ON TB_OSINT_ID_REP (IS_DARKWEB) WHERE IS_DARKWEB = 'Y';
CREATE INDEX IX_OSINT_ID_REP_VENDOR       ON TB_OSINT_ID_REP (IS_VENDOR) WHERE IS_VENDOR = 'Y';
CREATE INDEX IX_OSINT_ID_REP_PLATFORM     ON TB_OSINT_ID_REP (PLATFORM_CD);
CREATE INDEX IX_OSINT_ID_REP_SCORE        ON TB_OSINT_ID_REP (REP_SCORE DESC);

COMMENT ON TABLE  TB_OSINT_ID_REP               IS 'OSINT - 인터넷 계정/닉네임 평판 정보';
COMMENT ON COLUMN TB_OSINT_ID_REP.PLATFORM_CD   IS 'TELEGRAM/DISCORD/DARKWEB/FORUM/TWITTER 등';
COMMENT ON COLUMN TB_OSINT_ID_REP.IS_VENDOR     IS '다크웹 마켓 판매자 여부';
COMMENT ON COLUMN TB_OSINT_ID_REP.COLLECT_METHOD IS 'AUTO:자동수집 MANUAL:수동입력';
```

### 3.8 TB_WEB_DMN (웹 도메인 수집 정보)

인터넷망에서 자동 수집된 사이버범죄 관련 웹 도메인의 상세 정보를 저장한다.
`TB_OSINT_DMN_REP`가 **평판 정보** 중심이라면, 본 테이블은 **도메인 구조 및 인프라** 정보 중심이다.

```sql
CREATE TABLE TB_WEB_DMN (
    SEQ             BIGSERIAL       PRIMARY KEY,
    DOMAIN_NM       VARCHAR(500)    NOT NULL,
    TLD             VARCHAR(50),                        -- 최상위 도메인 (.com/.kr 등)
    STATUS_CD       VARCHAR(20)     NOT NULL DEFAULT 'ACTIVE',-- ACTIVE/INACTIVE/PARKED/SINKHOLE
    IP_ADDRS        TEXT,                               -- 현재 A레코드 JSON 배열
    MX_RECORDS      TEXT,                               -- MX 레코드 JSON 배열
    NS_RECORDS      TEXT,                               -- NS 레코드 JSON 배열
    CERT_ISSUER     VARCHAR(200),                       -- SSL 인증서 발급자
    CERT_SUBJECT    VARCHAR(500),                       -- SSL 인증서 CN
    CERT_VALID_FROM TIMESTAMP,
    CERT_VALID_TO   TIMESTAMP,
    CERT_SAN        TEXT,                               -- SAN(Subject Alternative Name) JSON 배열
    HTTP_TITLE      VARCHAR(500),                       -- HTTP 페이지 제목
    HTTP_SERVER     VARCHAR(200),                       -- Server 헤더
    HTTP_TECH       TEXT,                               -- 사용 기술 스택 JSON 배열 (Wappalyzer)
    SCREENSHOT_PATH VARCHAR(500),                       -- 스크린샷 저장 경로
    REGISTRAR_NM    VARCHAR(200),
    REGISTRANT_NM   VARCHAR(200),
    REG_AT          DATE,
    EXPIRE_REG_AT   DATE,
    HOSTING_IP      VARCHAR(45),                        -- 호스팅 IP
    HOSTING_ASN     VARCHAR(20),
    HOSTING_ORG     VARCHAR(200),
    HOSTING_COUNTRY CHAR(2),
    RELATED_DOMAINS TEXT,                               -- 같은 인프라 연관 도메인 JSON
    PURPOSE_CD      VARCHAR(30),                        -- PHISHING/C2/SCAM/FRAUD/DARKWEB 등
    THREAT_ACTOR    VARCHAR(200),                       -- 알려진 위협 행위자 (있는 경우)
    COLLECT_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    EXPIRE_AT       TIMESTAMP,
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_WEB_DMN_NM       ON TB_WEB_DMN (DOMAIN_NM);
CREATE INDEX IX_WEB_DMN_STATUS          ON TB_WEB_DMN (STATUS_CD);
CREATE INDEX IX_WEB_DMN_PURPOSE         ON TB_WEB_DMN (PURPOSE_CD);
CREATE INDEX IX_WEB_DMN_REG             ON TB_WEB_DMN (REG_AT);
CREATE INDEX IX_WEB_DMN_HOSTING_COUNTRY ON TB_WEB_DMN (HOSTING_COUNTRY);
CREATE INDEX IX_WEB_DMN_EXPIRE          ON TB_WEB_DMN (EXPIRE_AT);

COMMENT ON TABLE  TB_WEB_DMN              IS '인터넷망 수집 - 웹 도메인 인프라 정보';
COMMENT ON COLUMN TB_WEB_DMN.STATUS_CD   IS 'ACTIVE/INACTIVE/PARKED:주차도메인/SINKHOLE:싱크홀처리';
COMMENT ON COLUMN TB_WEB_DMN.PURPOSE_CD  IS 'PHISHING/C2/SCAM/FRAUD/DARKWEB/UNKNOWN';
COMMENT ON COLUMN TB_WEB_DMN.CERT_SAN    IS '와일드카드 인증서 포함 SAN 목록 JSON';
```

### 3.9 TB_WEB_MLGN_IDC (악성 지표 수집 정보)

C2 서버, 익스플로잇 킷, 피싱 페이지 등 인터넷망에서 수집된 악성 지표(IOC)의 상세 정보를 저장한다.

```sql
CREATE TABLE TB_WEB_MLGN_IDC (
    SEQ             BIGSERIAL       PRIMARY KEY,
    IOC_TYPE        VARCHAR(20)     NOT NULL,           -- IP/DOMAIN/URL/HASH/EMAIL/WALLET
    IOC_VAL         VARCHAR(1000)   NOT NULL,           -- IOC 원본값
    IOC_VAL_HASH    VARCHAR(64)     NOT NULL,           -- SHA-256 (빠른 검색용)
    THREAT_TYPE     VARCHAR(50)     NOT NULL,           -- C2/PHISHING/RANSOMWARE/BOTNET/EXPLOIT 등
    THREAT_ACTOR    VARCHAR(200),                       -- 알려진 위협 행위자
    MALWARE_FAMILY  VARCHAR(100),
    CONFIDENCE      SMALLINT        DEFAULT 50,         -- 신뢰도 0~100
    SEVERITY        VARCHAR(10)     DEFAULT 'MEDIUM',   -- LOW/MEDIUM/HIGH/CRITICAL
    TAGS            TEXT,                               -- MITRE ATT&CK 전술 등 JSON 배열
    RELATED_IOCS    TEXT,                               -- 연관 IOC JSON 배열
    TLP             CHAR(1)         DEFAULT 'R',        -- W:WHITE G:GREEN A:AMBER R:RED
    FEED_SRC        VARCHAR(100)    NOT NULL,           -- 피드 출처 (URLhaus/AlienVault/자체 등)
    FEED_ID         VARCHAR(200),                       -- 피드 내 식별자
    FIRST_SEEN_AT   TIMESTAMP,
    LAST_SEEN_AT    TIMESTAMP,
    EXPIRE_AT       TIMESTAMP,                          -- TTL (피드별 상이)
    IS_ACTIVE       CHAR(1)         NOT NULL DEFAULT 'Y',
    RAW_RESPONSE    JSONB,
    COLLECT_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW(),
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX UX_WEB_MLGN_IDC_VAL   ON TB_WEB_MLGN_IDC (IOC_VAL_HASH, FEED_SRC);
CREATE INDEX IX_WEB_MLGN_IDC_TYPE         ON TB_WEB_MLGN_IDC (IOC_TYPE);
CREATE INDEX IX_WEB_MLGN_IDC_THREAT       ON TB_WEB_MLGN_IDC (THREAT_TYPE);
CREATE INDEX IX_WEB_MLGN_IDC_SEVERITY     ON TB_WEB_MLGN_IDC (SEVERITY);
CREATE INDEX IX_WEB_MLGN_IDC_ACTIVE       ON TB_WEB_MLGN_IDC (IS_ACTIVE) WHERE IS_ACTIVE = 'Y';
CREATE INDEX IX_WEB_MLGN_IDC_EXPIRE       ON TB_WEB_MLGN_IDC (EXPIRE_AT);
CREATE INDEX IX_WEB_MLGN_IDC_FEED         ON TB_WEB_MLGN_IDC (FEED_SRC);

COMMENT ON TABLE  TB_WEB_MLGN_IDC             IS '인터넷망 수집 - 악성 지표(IOC) 통합 정보';
COMMENT ON COLUMN TB_WEB_MLGN_IDC.IOC_TYPE   IS 'IP/DOMAIN/URL/HASH/EMAIL/WALLET/CERT';
COMMENT ON COLUMN TB_WEB_MLGN_IDC.THREAT_TYPE IS 'C2:C&C서버 PHISHING/RANSOMWARE/BOTNET/EXPLOIT';
COMMENT ON COLUMN TB_WEB_MLGN_IDC.TLP        IS 'W:공개 G:커뮤니티 A:제한 R:기밀';
COMMENT ON COLUMN TB_WEB_MLGN_IDC.CONFIDENCE IS '0=불확실 100=확실';
```

### 3.10 TB_OSINT_COLLECT_LOG (수집 이력 로그)

외부 API 호출 이력, 성공·실패 여부, 응답 시간 등 운영 감사 정보를 기록한다.

```sql
CREATE TABLE TB_OSINT_COLLECT_LOG (
    SEQ             BIGSERIAL       PRIMARY KEY,
    COLLECT_ID      UUID            NOT NULL DEFAULT gen_random_uuid(),
    TARGET_TYPE     VARCHAR(20)     NOT NULL,           -- IP/DOMAIN/HASH/TELNO/ACNT/WALLET/ID
    TARGET_VAL      VARCHAR(1000)   NOT NULL,           -- 조회 대상 값
    DATA_SRC        VARCHAR(50)     NOT NULL,           -- 'VIRUSTOTAL','ABUSEIPDB' 등
    API_ENDPOINT    VARCHAR(300),                       -- 호출 엔드포인트
    HTTP_STATUS     SMALLINT,                           -- HTTP 응답 코드
    RESULT_CD       VARCHAR(10)     NOT NULL,           -- SUCCESS/FAIL/TIMEOUT/RATE_LIMIT
    RESP_TIME_MS    INTEGER,                            -- 응답 시간 (ms)
    ERR_MSG         TEXT,                               -- 오류 메시지 (실패 시)
    TRIGGER_TYPE    VARCHAR(20),                        -- CRON/ONDEMAND/ETL
    TRIGGERED_BY    VARCHAR(100),                       -- 트리거 주체 (사용자 ID 또는 job명)
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT NOW()
) PARTITION BY RANGE (CREATED_AT);

-- 월별 파티션 (예시: 2026년 4월)
CREATE TABLE TB_OSINT_COLLECT_LOG_202604
    PARTITION OF TB_OSINT_COLLECT_LOG
    FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');

CREATE INDEX IX_OSINT_CLOG_COLLECT_ID  ON TB_OSINT_COLLECT_LOG (COLLECT_ID);
CREATE INDEX IX_OSINT_CLOG_TARGET      ON TB_OSINT_COLLECT_LOG (TARGET_TYPE, TARGET_VAL);
CREATE INDEX IX_OSINT_CLOG_SRC         ON TB_OSINT_COLLECT_LOG (DATA_SRC);
CREATE INDEX IX_OSINT_CLOG_RESULT      ON TB_OSINT_COLLECT_LOG (RESULT_CD);
CREATE INDEX IX_OSINT_CLOG_CREATED     ON TB_OSINT_COLLECT_LOG (CREATED_AT DESC);

COMMENT ON TABLE  TB_OSINT_COLLECT_LOG              IS 'OSINT 수집 API 호출 이력 (파티셔닝)';
COMMENT ON COLUMN TB_OSINT_COLLECT_LOG.RESULT_CD   IS 'SUCCESS/FAIL/TIMEOUT/RATE_LIMIT/SKIP';
COMMENT ON COLUMN TB_OSINT_COLLECT_LOG.TRIGGER_TYPE IS 'CRON:배치 ONDEMAND:즉시조회 ETL:사건등록연동';
```

---

## 4. 공통코드 정의

```sql
-- IOC 타입 코드
INSERT INTO TB_CMCD (CMCD_GRP, CMCD_CD, CMCD_NM, SORT_ORD) VALUES
('IOC_TYPE', 'IP',     'IP 주소',           1),
('IOC_TYPE', 'DOMAIN', '도메인/URL',         2),
('IOC_TYPE', 'HASH',   '파일 해시',          3),
('IOC_TYPE', 'TELNO',  '전화번호',           4),
('IOC_TYPE', 'ACNT',   '금융 계좌',          5),
('IOC_TYPE', 'WALLET', '암호화폐 지갑',       6),
('IOC_TYPE', 'ID',     '인터넷 계정',         7),
('IOC_TYPE', 'EMAIL',  '이메일 주소',         8),
('IOC_TYPE', 'CERT',   'SSL 인증서',         9);

-- 위협 유형 코드
INSERT INTO TB_CMCD (CMCD_GRP, CMCD_CD, CMCD_NM, SORT_ORD) VALUES
('THREAT_TYPE', 'C2',         'C&C 서버',           1),
('THREAT_TYPE', 'PHISHING',   '피싱',               2),
('THREAT_TYPE', 'RANSOMWARE', '랜섬웨어',            3),
('THREAT_TYPE', 'BOTNET',     '봇넷',               4),
('THREAT_TYPE', 'EXPLOIT',    '익스플로잇',           5),
('THREAT_TYPE', 'SCAM',       '스캠/사기',            6),
('THREAT_TYPE', 'FRAUD',      '금융사기',             7),
('THREAT_TYPE', 'DARKWEB',    '다크웹 관련',          8),
('THREAT_TYPE', 'VOICEPHISH', '보이스피싱',           9);

-- 수집 결과 코드
INSERT INTO TB_CMCD (CMCD_GRP, CMCD_CD, CMCD_NM, SORT_ORD) VALUES
('COLLECT_RESULT', 'SUCCESS',    '수집 성공',         1),
('COLLECT_RESULT', 'FAIL',       '수집 실패',         2),
('COLLECT_RESULT', 'TIMEOUT',    '응답 시간 초과',     3),
('COLLECT_RESULT', 'RATE_LIMIT', 'API 호출 한도 초과', 4),
('COLLECT_RESULT', 'SKIP',       '중복 또는 TTL 유효', 5);

-- 평판 등급 코드
INSERT INTO TB_CMCD (CMCD_GRP, CMCD_CD, CMCD_NM, SORT_ORD) VALUES
('REP_GRADE', 'L', 'Low (정상)',       1),
('REP_GRADE', 'M', 'Medium (주의)',    2),
('REP_GRADE', 'H', 'High (위험)',      3),
('REP_GRADE', 'C', 'Critical (매우위험)', 4);

-- 플랫폼 코드 (ID 수집용)
INSERT INTO TB_CMCD (CMCD_GRP, CMCD_CD, CMCD_NM, SORT_ORD) VALUES
('PLATFORM_CD', 'TELEGRAM', '텔레그램',     1),
('PLATFORM_CD', 'DISCORD',  '디스코드',     2),
('PLATFORM_CD', 'DARKWEB',  '다크웹',       3),
('PLATFORM_CD', 'FORUM',    '해킹 포럼',    4),
('PLATFORM_CD', 'TWITTER',  '트위터/X',     5),
('PLATFORM_CD', 'GITHUB',   'GitHub',      6);
```

---

## 5. 수집 파이프라인 서비스 설계

### 5.1 클래스 구조

```python
# app/middleware/services/osint_collect_service.py

class OsintCollectService:
    """
    인터넷망 OSINT 수집 서비스
    외부 API 연동 → TB_OSINT_*_REP UPSERT → TB_OSINT_COLLECT_LOG INSERT
    """

    # API 키 풀 (로테이션)
    _VT_API_KEYS: List[str] = []        # VirusTotal
    _ABUSEIPDB_KEY: str = ""
    _SHODAN_KEY: str = ""
    _CHAINALYSIS_KEY: str = ""

    @staticmethod
    def collect_ip(ip_addr: str, trigger: str = "ONDEMAND") -> Dict:
        """IP 평판 수집 → TB_OSINT_IP_REP UPSERT"""
        # 1. TTL 체크 (EXPIRE_AT > NOW() 면 SKIP)
        # 2. VirusTotal IP 조회
        # 3. AbuseIPDB 조회
        # 4. Shodan 조회
        # 5. 신뢰도 점수 산정 (VT_DETECT_CNT / VT_TOTAL_CNT * 50 + ABUSE_CNT 가중)
        # 6. TB_OSINT_IP_REP UPSERT
        # 7. TB_OSINT_COLLECT_LOG INSERT
        ...

    @staticmethod
    def collect_domain(domain_nm: str, trigger: str = "ONDEMAND") -> Dict:
        """도메인 평판 수집 → TB_OSINT_DMN_REP UPSERT"""
        ...

    @staticmethod
    def collect_hash(hash_val: str, hash_type: str = "SHA256", trigger: str = "ONDEMAND") -> Dict:
        """파일 해시 평판 수집 → TB_OSINT_HASH_REP UPSERT"""
        ...

    @staticmethod
    def collect_phone(telno: str, trigger: str = "ONDEMAND") -> Dict:
        """전화번호 평판 수집 → TB_OSINT_PHON_REP UPSERT"""
        ...

    @staticmethod
    def collect_account(bacnt_no: str, trigger: str = "ONDEMAND") -> Dict:
        """금융 계좌 사기 정보 수집 → TB_OSINT_ACNT_REP UPSERT"""
        ...

    @staticmethod
    def collect_wallet(wallet_addr: str, coin_type: str, trigger: str = "ONDEMAND") -> Dict:
        """암호화폐 지갑 평판 수집 → TB_OSINT_WALLET_REP UPSERT"""
        ...

    @staticmethod
    def collect_batch(graph_name: str = "coop_graph") -> Dict:
        """
        정기 배치 수집 (Cron)
        그래프 노드 전체 순회 → 각 타입별 collect_* 호출
        """
        # vt_ip 노드 → collect_ip()
        # vt_site 노드 → collect_domain()
        # vt_file 노드 → collect_hash()
        # vt_telno 노드 → collect_phone()
        # vt_bacnt 노드 → collect_account()
        ...
```

### 5.2 신뢰도 점수 산정 로직

```python
def _calc_rep_score_ip(vt_detect: int, vt_total: int, abuse_cnt: int,
                        is_tor: bool, is_proxy: bool) -> int:
    """IP 위험도 점수 (0~100) 산정"""
    score = 0

    # VirusTotal 탐지율 (최대 60점)
    if vt_total > 0:
        score += int((vt_detect / vt_total) * 60)

    # AbuseIPDB 신고 횟수 (최대 30점)
    score += min(abuse_cnt * 3, 30)

    # 가산 요소
    if is_tor:    score += 5
    if is_proxy:  score += 5

    return min(score, 100)

def _score_to_grade(score: int) -> str:
    if score < 20:  return 'L'
    if score < 50:  return 'M'
    if score < 80:  return 'H'
    return 'C'
```

### 5.3 TTL(유효기간) 정책

| 데이터 유형 | 기본 TTL | 고위험(H/C) TTL | 비고 |
|------------|---------|----------------|------|
| IP 평판     | 7일      | 3일             | AbuseIPDB 기준 |
| 도메인 평판  | 14일     | 3일             | 도메인 만료일 고려 |
| 파일 해시   | 30일     | 영구 보관        | 악성코드는 삭제 안 함 |
| 전화번호    | 30일     | 14일            | 신고 이력 장기 보관 |
| 금융 계좌   | 30일     | 영구 보관        | 사기계좌 이력 보존 |
| 암호화폐 지갑| 14일    | 영구 보관        | 제재 대상 영구 보관 |
| 인터넷 ID  | 7일      | 14일            | 활동 기반 갱신 |
| 악성 지표   | 피드별 상이 | 피드별 상이    | FEED_SRC TTL 준수 |

---

## 6. 그래프 연동 설계

### 6.1 OSINT → 그래프 노드 매핑

| OSINT 테이블 | 그래프 노드 타입 | 연결 엣지 | evid_grade |
|-------------|----------------|----------|-----------|
| TB_OSINT_IP_REP | vt_ip | sourced_from | C |
| TB_OSINT_DMN_REP | vt_site | sourced_from | C |
| TB_OSINT_HASH_REP | vt_file | sourced_from | C |
| TB_OSINT_PHON_REP | vt_telno | sourced_from | C |
| TB_OSINT_ACNT_REP | vt_bacnt | sourced_from | C |
| TB_OSINT_WALLET_REP | vt_bacnt (type=CRYPTO) | sourced_from | C |
| TB_OSINT_ID_REP | vt_id | sourced_from | C |

### 6.2 OSINT 속성 → 그래프 노드 속성 전파

그래프 노드에 OSINT 수집 결과의 핵심 속성을 전파하여 시각화 및 조회에 활용한다.

```cypher
-- IP 노드 OSINT 속성 업데이트 예시
MATCH (n:vt_ip {ip_addr: $ip_addr})
SET n.rep_score   = $rep_score,
    n.rep_grade   = $rep_grade,
    n.is_malicious= $is_malicious,
    n.country_cd  = $country_cd,
    n.osint_at    = $collect_at
```

### 6.3 bridge_key 구조 (OSINT 역추적)

```json
{
  "table": "TB_OSINT_IP_REP",
  "pk": "SEQ",
  "val": "12345",
  "rep_score": 87,
  "rep_grade": "C",
  "data_src": "VIRUSTOTAL",
  "collect_at": "2026-04-07T10:30:00"
}
```

수사관이 그래프 UI에서 vt_ip 노드를 클릭하면, bridge_key를 통해 TB_OSINT_IP_REP 원본 레코드를 직접 조회하고 VirusTotal 결과 링크(`VT_PERMALINK`)로 이동할 수 있다.

---

## 7. API 엔드포인트 설계

### 7.1 On-Demand 수집 API

```
POST /api/osint/collect
Content-Type: application/json

Request:
{
  "ioc_type": "IP",          // IP/DOMAIN/HASH/TELNO/ACNT/WALLET/ID
  "ioc_val":  "192.168.1.1",
  "force":    false           // TTL 무시하고 강제 재조회
}

Response 200:
{
  "status": "success",
  "ioc_type": "IP",
  "ioc_val": "192.168.1.1",
  "rep_score": 87,
  "rep_grade": "C",
  "is_malicious": true,
  "country_cd": "CN",
  "cached": false,            // true: TTL 유효해서 DB 캐시 반환
  "collect_at": "2026-04-07T10:30:00"
}
```

### 7.2 평판 조회 API

```
GET /api/osint/reputation?ioc_type=IP&ioc_val=192.168.1.1

Response 200:
{
  "found": true,
  "data": {
    "rep_score": 87,
    "rep_grade": "C",
    "is_malicious": true,
    "country_cd": "CN",
    "asn_org": "ChinaTelecom",
    "abuse_cnt": 142,
    "vt_detect_cnt": 48,
    "vt_total_cnt": 72,
    "vt_permalink": "https://www.virustotal.com/...",
    "collect_at": "2026-04-07T10:30:00"
  }
}
```

### 7.3 배치 수집 현황 API

```
GET /api/osint/collect/status

Response 200:
{
  "last_batch_at": "2026-04-07T03:00:00",
  "stats": {
    "total_iocs": 4821,
    "collected_today": 312,
    "failed_today": 8,
    "rate_limited": 3
  },
  "by_type": {
    "IP":     {"total": 1203, "high_risk": 87},
    "DOMAIN": {"total": 892,  "high_risk": 34},
    "HASH":   {"total": 521,  "high_risk": 108}
  }
}
```

---

## 8. 보안 및 운영 고려사항

### 8.1 개인정보 보호

| 데이터 항목 | 보호 조치 |
|------------|---------|
| 금융 계좌번호 | SHA-256 해시 저장 + 마스킹 표시 (앞 6자리만 노출) |
| 전화번호 | 원본 저장 (수사목적 예외), 조회 이력 감사로그 |
| 이메일 주소 | 원본 저장, 외부 노출 시 마스킹 |
| 개인 식별 정보 | TB_OSINT_ID_REP: 범죄관련 활동 증거 목적만 허용 |

### 8.2 API 키 관리

```
- API 키는 환경변수로 관리 (.env, 배포 시 Vault/Secret Manager)
- VirusTotal: 복수 키 풀, 라운드로빈 로테이션 (분당 4회 제한 회피)
- Rate Limit 초과 시: 지수 백오프 (1s → 2s → 4s → 8s)
- 일일 할당량 90% 도달 시: 관리자 알림 발송
```

### 8.3 TLP(Traffic Light Protocol) 준수

```
WHITE  (W): 공개 공유 가능 → 보고서 포함 가능
GREEN  (G): 커뮤니티 내 공유 → 수사기관 내부 공유
AMBER  (A): 조직 내 제한 → 담당 수사팀만 접근
RED    (R): 출처 기관만 → 외부 공유 절대 금지
```

TB_WEB_MLGN_IDC의 `TLP` 컬럼에 따라 API 응답 시 자동 마스킹 처리.

### 8.4 데이터 보존 정책

| 구분 | 보존 기간 | 삭제 방법 |
|------|---------|---------|
| 일반 OSINT 수집 데이터 | TTL 만료 후 90일 | 배치 물리 삭제 |
| 악성코드 해시 (IS_MALICIOUS=Y) | 영구 보관 | 삭제 불가 |
| 제재 대상 지갑 (IS_SANCTIONED=Y) | 영구 보관 | 삭제 불가 |
| 사기계좌 (IS_FRAUD=Y) | 공소시효 + 5년 | 법무부 지침 준수 |
| 수집 이력 로그 | 3년 | 파티션 DROP |

---

## 9. 테이블 목록 요약

| 순번 | 테이블명 | 설명 | 레코드 규모 (예상) |
|-----|---------|------|-----------------|
| 1 | TB_OSINT_IP_REP | IP 평판 정보 | 수만~수십만 |
| 2 | TB_OSINT_DMN_REP | 도메인/URL 평판 | 수만 |
| 3 | TB_OSINT_HASH_REP | 악성코드 해시 평판 | 수천~수만 |
| 4 | TB_OSINT_PHON_REP | 전화번호 평판 | 수만 |
| 5 | TB_OSINT_ACNT_REP | 금융 계좌 평판 | 수만 |
| 6 | TB_OSINT_WALLET_REP | 암호화폐 지갑 평판 | 수천 |
| 7 | TB_OSINT_ID_REP | 인터넷 계정 평판 | 수천 |
| 8 | TB_WEB_DMN | 웹 도메인 인프라 정보 | 수만 |
| 9 | TB_WEB_MLGN_IDC | 악성 지표(IOC) 통합 | 수십만 |
| 10 | TB_OSINT_COLLECT_LOG | 수집 이력 로그 (파티션) | 수백만/년 |

**총 10개 테이블** (기존 DDL 52개 + 10개 = **62개 테이블**)

---

## 10. 변경 이력

| 버전 | 일자 | 내용 |
|------|------|------|
| v1.0 | 2026-04-07 | 최초 작성 (CCOP v3.2 인터넷망 수집DB 설계) |
