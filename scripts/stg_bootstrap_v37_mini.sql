-- =====================================================================
-- 스테이징 검증용 V3.7 미니 부트스트랩
-- 목적: da_v37_v40_patch.sql 적용 전 최소한의 V3.7 표준 테이블 시드 생성
-- =====================================================================

-- ---- 공통코드 ----
CREATE TABLE IF NOT EXISTS TB_CMN_CD (
    CD_GRP_ID   VARCHAR(40)  NOT NULL,
    CD_ID       VARCHAR(40)  NOT NULL,
    CD_NM       VARCHAR(100),
    CD_DESC     VARCHAR(400),
    USE_YN      CHAR(1)      DEFAULT 'Y',
    SORT_ORDER  INTEGER      DEFAULT 0,
    PRIMARY KEY (CD_GRP_ID, CD_ID)
);

-- ---- 인물 (V3.7) ----
CREATE TABLE IF NOT EXISTS TB_PSN (
    PSN_ID        VARCHAR(64) PRIMARY KEY,
    PSN_NM        VARCHAR(100),
    BRTH_DT       DATE,
    SOURCE_ID     VARCHAR(64),
    RLBLT_TIER    SMALLINT DEFAULT 5,    -- 일부러 5로 둠 (B5 검증)
    COLLECTED_AT  TIMESTAMP,
    REC_CREATED   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---- 은행코드 (B2 검증용: 의도적 오타) ----
CREATE TABLE IF NOT EXISTS TB_BANK_CD (
    BNAK_CD     VARCHAR(10) PRIMARY KEY,   -- B2 오타 시뮬레이션
    BANK_NM     VARCHAR(80)
);

-- ---- 이메일주소 (B3 검증용: 의도적 컬럼명 혼용) ----
CREATE TABLE IF NOT EXISTS TB_EML_ADDR (
    EML_ADDR_ID VARCHAR(128) PRIMARY KEY,  -- B3: 본문에서 EML_ADDR로 참조됨
    OWNER_PSN   VARCHAR(64)
);

-- ---- 기기마스터 (V3.7 신규 dev_type 검증) ----
CREATE TABLE IF NOT EXISTS TB_DEV_MST (
    DEV_ID      VARCHAR(64) PRIMARY KEY,
    DEV_TYPE    VARCHAR(40),
    IMEI        VARCHAR(20)
);

-- ---- 디지털 ID 마스터 (V3.7 익명 플래그 검증) ----
CREATE TABLE IF NOT EXISTS TB_DGTL_ID_MST (
    DGTL_ID     VARCHAR(64) PRIMARY KEY,
    ID_TYPE     VARCHAR(40),
    ID_VALUE    VARCHAR(256)
);

-- ---- 마스터 sample (메타 전파 검증용) ----
CREATE TABLE IF NOT EXISTS TB_CASE_MST (
    CASE_ID     VARCHAR(64) PRIMARY KEY,
    CASE_NM     VARCHAR(200)
);
CREATE TABLE IF NOT EXISTS TB_BACNT_MST (
    BACNT_ID    VARCHAR(64) PRIMARY KEY,
    BANK_CD     VARCHAR(10),
    ACCT_NO     VARCHAR(40)
);
CREATE TABLE IF NOT EXISTS TB_TELNO_MST (
    TELNO_ID    VARCHAR(64) PRIMARY KEY,
    TELNO       VARCHAR(20)
);
CREATE TABLE IF NOT EXISTS TB_IP_MST (
    IP_ID       VARCHAR(64) PRIMARY KEY,
    IP_ADDR     VARCHAR(45)
);
CREATE TABLE IF NOT EXISTS TB_SITE_INFO (
    SITE_ID     VARCHAR(64) PRIMARY KEY,
    URL         VARCHAR(2048)
);
CREATE TABLE IF NOT EXISTS TB_SYS_LGN_EVT (
    EVT_ID      VARCHAR(64) PRIMARY KEY,
    EVT_TS      TIMESTAMP
);
