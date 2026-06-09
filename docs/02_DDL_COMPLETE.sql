-- ============================================================
--  CCOP RDB 완전 DDL — v3.2
--  작성일: 2026-04-06 | 최종 수정: 2026-04-07
--  대상 DB: PostgreSQL 14+ / AgensGraph
--  총 테이블: 49개
--
--  [v3.2 변경 사항]
--  - TB_CMN_CD: CRIME_METHOD, CRIME_STEP, SRC_TYP 코드 추가 (ETRI crime_meta 연계)
--  - TB_DATA_SRC: SRC_TYP_CD에 PREPROCESSOR 추가, src-etri 기본값 INSERT
--  - TB_DATA_INGEST_LOG: ACTIVITY_TYP_CD 컬럼 추가 (ETRI PROV-O Activity)
--  - TB_PETTN_MST: CRIME_METHOD_CD, CRIME_STEP_CN 컬럼 추가
--
--  [실행 순서]
--  1. 참조 테이블 (TB_CMN_CD, TB_BANK_CD)
--  2. 소스/메타 → 사건/진정 → 사람/기관 → 금융
--  3. 통신 → 차량 → 위치/지리 → 디지털
--  4. OSINT → 마약 → 사기신고 → 엔티티해소
--  5. Phase 6E 마스터 (디지털ID/이메일/가상자산/기기/ATM/위치)
--  6. 사칭 관계 (TB_IMPRSN_REL)
--
--  [그래프 연동 기준]
--  ONTOLOGY_FINAL_ARCHITECTURE.md v3.2 §7 참조
--  Bridge Key 목록은 §7 및 본 파일 인라인 주석 참조
-- ============================================================


-- ============================================================
-- §0. 공통 코드 / 참조 테이블 (2개)
-- ============================================================

-- ① 공통 코드 (사건유형, 역할, 상태 등)
CREATE TABLE TB_CMN_CD (
    CD_GRP_ID       VARCHAR(20)     NOT NULL,               -- 코드 그룹 ID
    CD_VAL          VARCHAR(20)     NOT NULL,               -- 코드 값
    CD_NM           VARCHAR(100)    NOT NULL,               -- 코드명
    CD_ENG_NM       VARCHAR(100)    NULL,                   -- 코드 영문명
    SORT_ORD        SMALLINT        NULL DEFAULT 0,
    USE_YN          CHAR(1)         NOT NULL DEFAULT 'Y',
    RMK_CN          VARCHAR(500)    NULL,
    CONSTRAINT TB_CMN_CD_PK PRIMARY KEY (CD_GRP_ID, CD_VAL)
);

INSERT INTO TB_CMN_CD (CD_GRP_ID, CD_VAL, CD_NM) VALUES
  -- 사건유형
  ('INCDNT_TYP', 'VOICE', '보이스피싱'),
  ('INCDNT_TYP', 'DRUG',  '마약'),
  ('INCDNT_TYP', 'FRAUD', '사기'),
  ('INCDNT_TYP', 'GAMBL', '불법도박'),
  ('INCDNT_TYP', 'CYBER', '사이버범죄'),
  -- 역할코드
  ('ROLE', 'SUSPECT', '피의자'),
  ('ROLE', 'VICTIM',  '피해자'),
  ('ROLE', 'WITNESS', '참고인'),
  -- 소스 신뢰등급
  ('RLBLT_TIER', '1', '공식수사자료'),
  ('RLBLT_TIER', '2', '기관연계'),
  ('RLBLT_TIER', '3', '전처리진정서'),
  ('RLBLT_TIER', '4', 'OSINT'),
  ('RLBLT_TIER', '5', '미확인제보'),
  -- 사칭 유형
  ('IMPRSN_TYP', 'VOICE', '전화 사칭'),
  ('IMPRSN_TYP', 'SMS',   '문자 사칭'),
  ('IMPRSN_TYP', 'APP',   '앱/메신저 사칭'),
  ('IMPRSN_TYP', 'WEB',   '웹사이트 사칭'),
  -- 범행수법 (ETRI crime_meta 연계, v3.2 추가)
  ('CRIME_METHOD', 'VOICE_PHISHING',    '보이스피싱'),
  ('CRIME_METHOD', 'SMS_PHISHING',      '문자사기(스미싱)'),
  ('CRIME_METHOD', 'MESSENGER_FRAUD',   '메신저사기'),
  ('CRIME_METHOD', 'ROMANCE_SCAM',      '로맨스스캠'),
  ('CRIME_METHOD', 'INVEST_FRAUD',      '투자사기'),
  ('CRIME_METHOD', 'FAKE_SHOPPING',     '인터넷쇼핑사기'),
  ('CRIME_METHOD', 'RANSOM',            '랜섬웨어'),
  ('CRIME_METHOD', 'DRUG_ONLINE',       '온라인마약거래'),
  ('CRIME_METHOD', 'GAMBLING_SITE',     '불법도박사이트'),
  ('CRIME_METHOD', 'IDENTITY_THEFT',    '신원도용/명의도용'),
  -- 범죄 단계 (ETRI crime_step 연계, v3.2 추가)
  ('CRIME_STEP', 'RECRUIT',     '모집/유인'),
  ('CRIME_STEP', 'DECEIVE',     '기망/협박'),
  ('CRIME_STEP', 'TRANSFER',    '자금이체'),
  ('CRIME_STEP', 'WITHDRAW',    '현금인출'),
  ('CRIME_STEP', 'LAUNDER',     '자금세탁'),
  ('CRIME_STEP', 'ESCAPE',      '도주/은신'),
  -- 소스 타입 (v3.2 PREPROCESSOR 추가)
  ('SRC_TYP', 'OFFICIAL',     '공식수사자료'),
  ('SRC_TYP', 'AGENCY',       '기관연계'),
  ('SRC_TYP', 'PREPROCESSOR', '전처리기관'),
  ('SRC_TYP', 'PETITION',     '직접접수진정서'),
  ('SRC_TYP', 'OSINT',        '공개인텔리전스'),
  ('SRC_TYP', 'REPORT',       '미확인제보');


-- ② 은행 코드
CREATE TABLE TB_BANK_CD (
    BANK_CD         VARCHAR(10)     NOT NULL,
    BANK_NM         VARCHAR(100)    NOT NULL,
    BANK_ENG_NM     VARCHAR(100)    NULL,
    BANK_TYP_CD     VARCHAR(10)     NULL,                   -- COMMERCIAL|SAVINGS|INTERNET
    USE_YN          CHAR(1)         NOT NULL DEFAULT 'Y',
    CONSTRAINT TB_BANK_CD_PK PRIMARY KEY (BANK_CD)
);

INSERT INTO TB_BANK_CD (BANK_CD, BANK_NM) VALUES
  ('004', 'KB국민은행'),   ('020', '우리은행'),    ('081', '하나은행'),
  ('088', '신한은행'),     ('003', 'IBK기업은행'), ('011', 'NH농협은행'),
  ('023', 'SC제일은행'),   ('032', '부산은행'),    ('045', '새마을금고'),
  ('071', '우체국'),       ('002', 'KDB산업은행'), ('048', '신협중앙회');


-- ============================================================
-- §1. 소스/메타 도메인 (3개)
-- ============================================================

-- ① 데이터 소스 등록 (그래프 vt_src 노드의 RDB 대응)
CREATE TABLE TB_DATA_SRC (
    SRC_ID          VARCHAR(50)     NOT NULL,               -- 소스 ID (예: src-dutcheat)
    SRC_NM          VARCHAR(200)    NOT NULL,               -- 소스명 (예: 더치트)
    SRC_TYP_CD      VARCHAR(20)     NOT NULL,               -- OFFICIAL|AGENCY|PREPROCESSOR|PETITION|OSINT|REPORT
    RLBLT_TIER      SMALLINT        NOT NULL DEFAULT 5,     -- 신뢰등급 1(최고)~5(미확인)
    COLLECTOR_ID    VARCHAR(100)    NULL,                   -- 수집 시스템/수사관 ID
    COLLECTED_AT    TIMESTAMP       NULL,                   -- 최초 수집 일시
    UPDATE_CYCLE    VARCHAR(20)     NULL,                   -- daily|realtime|ondemand|batch
    CONTACT_URL     VARCHAR(500)    NULL,                   -- 소스 기관 연락처/URL
    IS_ACTIVE_YN    CHAR(1)         NOT NULL DEFAULT 'Y',
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_DATA_SRC_PK PRIMARY KEY (SRC_ID)
);
COMMENT ON TABLE  TB_DATA_SRC IS '데이터 소스 등록 (Provenance). 그래프 vt_src 노드 대응';
COMMENT ON COLUMN TB_DATA_SRC.RLBLT_TIER IS '1=공식수사자료, 2=기관연계, 3=전처리진정서(PREPROCESSOR), 4=OSINT, 5=미확인제보';
COMMENT ON COLUMN TB_DATA_SRC.SRC_TYP_CD IS 'OFFICIAL=공식, AGENCY=기관연계, PREPROCESSOR=전처리기관(ETRI 등), PETITION=진정서, OSINT=공개인텔, REPORT=미확인제보';

INSERT INTO TB_DATA_SRC (SRC_ID, SRC_NM, SRC_TYP_CD, RLBLT_TIER, UPDATE_CYCLE) VALUES
  ('src-official',  '공식 수사자료',        'OFFICIAL',     1, 'ondemand'),
  ('src-kics',      'KICS 연동',            'AGENCY',       2, 'realtime'),
  ('src-fss',       '금융감독원 공유DB',     'AGENCY',       2, 'daily'),
  ('src-etri',      'ETRI 전처리 기관',      'PREPROCESSOR', 3, 'batch'),
  ('src-dutcheat',  '더치트',               'OSINT',        4, 'daily'),
  ('src-anon',      '익명 신고',            'REPORT',       5, 'ondemand');


-- ② 수집 이력 로그
CREATE TABLE TB_DATA_INGEST_LOG (
    LOG_SN          BIGSERIAL       NOT NULL,
    SRC_ID          VARCHAR(50)     NOT NULL,               -- TB_DATA_SRC.SRC_ID FK
    INGEST_DT       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INGEST_TYP_CD   VARCHAR(20)     NULL,                   -- batch|realtime|manual
    ACTIVITY_TYP_CD VARCHAR(20)     NULL,                   -- ETRI PROV-O Activity 유형: COLLECT|OCR|NER|LINK|ENRICH
    TBL_NM          VARCHAR(100)    NULL,                   -- 대상 테이블명
    TOT_CNT         INTEGER         NULL DEFAULT 0,
    SUCC_CNT        INTEGER         NULL DEFAULT 0,
    FAIL_CNT        INTEGER         NULL DEFAULT 0,
    RESULT_CD       VARCHAR(10)     NULL,                   -- SUCCESS|PARTIAL|FAIL
    ERR_MSG_CN      TEXT            NULL,
    CONSTRAINT TB_DATA_INGEST_LOG_PK PRIMARY KEY (LOG_SN)
);
COMMENT ON TABLE  TB_DATA_INGEST_LOG IS '배치 수집 이력 (감사 전용, 그래프 변환 없음)';
COMMENT ON COLUMN TB_DATA_INGEST_LOG.ACTIVITY_TYP_CD IS 'ETRI PROV-O Activity 유형: COLLECT=원본수집, OCR=문서인식, NER=개체인식, LINK=엔티티연결, ENRICH=속성보강';


-- ③ 데이터 품질 감사 로그
CREATE TABLE TB_DATA_QUALITY_LOG (
    QC_SN           BIGSERIAL       NOT NULL,
    SRC_ID          VARCHAR(50)     NOT NULL,
    TBL_NM          VARCHAR(100)    NOT NULL,
    REC_KEY         VARCHAR(200)    NOT NULL,               -- 검사 대상 레코드 PK
    QC_RULE_CD      VARCHAR(50)     NOT NULL,               -- 품질 규칙 코드
    QC_RESULT_CD    VARCHAR(10)     NOT NULL,               -- PASS|WARN|FAIL
    QC_MSG_CN       TEXT            NULL,
    CHK_DT          TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_DATA_QUALITY_LOG_PK PRIMARY KEY (QC_SN)
);
COMMENT ON TABLE TB_DATA_QUALITY_LOG IS '데이터 품질 감사 (감사 전용, 그래프 변환 없음)';


-- ============================================================
-- §2. 사건/관리 도메인 (2개)
-- ============================================================

-- ① 사건 마스터 (그래프 vt_case 노드 대응)
CREATE TABLE TB_INCDNT_MST (
    INCDNT_NO       VARCHAR(20)     NOT NULL,               -- 사건번호 (경찰청 공식)
    FLNM            VARCHAR(50)     NULL,                   -- CCOP 내부 사건번호
    INCDNT_NM       VARCHAR(300)    NOT NULL,               -- 사건명
    INCDNT_TYP_CD   VARCHAR(6)      NULL,                   -- 사건유형코드
    OCCRN_DT        TIMESTAMP       NULL,                   -- 발생일시 (Valid Time)
    END_DT          TIMESTAMP       NULL,
    CHRGDP_NM       VARCHAR(100)    NULL,                   -- 담당부서명
    CHRG_PLCMN_NM   VARCHAR(100)    NULL,                   -- 담당경찰관명
    PLCS_NM         VARCHAR(100)    NULL,                   -- 담당경찰서명
    INCDNT_SMRY_CN  TEXT            NULL,
    DAM_AMT         NUMERIC(20,0)   NULL,                   -- 피해금액 (원)
    STATUS_CD       VARCHAR(20)     NULL DEFAULT 'OPEN',    -- OPEN|INVESTIGATING|CLOSED|SUSPENDED
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_INCDNT_MST_PK PRIMARY KEY (INCDNT_NO)
);
CREATE INDEX IDX_INCDNT_OCCRN_DT  ON TB_INCDNT_MST (OCCRN_DT);
CREATE INDEX IDX_INCDNT_TYP_CD    ON TB_INCDNT_MST (INCDNT_TYP_CD);
CREATE INDEX IDX_INCDNT_STATUS_CD ON TB_INCDNT_MST (STATUS_CD);


-- ② 사건-인물 관계 (그래프 suspect_in / victim_in / witness_in 엣지 대응)
CREATE TABLE TB_INCDNT_PRSN_REL (
    REL_SN          BIGSERIAL       NOT NULL,
    INCDNT_NO       VARCHAR(20)     NOT NULL,               -- TB_INCDNT_MST FK
    PRSN_ID         VARCHAR(20)     NOT NULL,               -- TB_PRSN FK
    ROLE_CD         VARCHAR(20)     NOT NULL,               -- SUSPECT|VICTIM|WITNESS
    VALID_FROM_DT   TIMESTAMP       NULL,
    VALID_TO_DT     TIMESTAMP       NULL,
    CONFIDENCE      NUMERIC(4,3)    NULL DEFAULT 1.000,
    VERIFIED_YN     CHAR(1)         NULL DEFAULT 'N',
    VERIFIED_BY     VARCHAR(50)     NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_INCDNT_PRSN_REL_PK PRIMARY KEY (REL_SN),
    CONSTRAINT TB_INCDNT_PRSN_REL_UQ UNIQUE (INCDNT_NO, PRSN_ID, ROLE_CD)
);
COMMENT ON COLUMN TB_INCDNT_PRSN_REL.ROLE_CD IS 'SUSPECT=피의자, VICTIM=피해자, WITNESS=참고인 (그래프 엣지 타입으로 변환)';


-- ============================================================
-- §3. 진정서 도메인 (3개)
-- ============================================================

-- ① 진정서 마스터 (그래프 vt_petition 노드 대응)
CREATE TABLE TB_PETTN_MST (
    DCLR_SN         BIGSERIAL       NOT NULL,               -- PK (자동채번)
    PETITION_ID     VARCHAR(50)     NOT NULL,               -- CCOP 내부 ID (예: PTN-2026-00001)
    RCPT_DT         TIMESTAMP       NOT NULL,               -- 접수 일시 (Transaction Time)
    RCPT_CH_CD      VARCHAR(20)     NOT NULL,               -- WEB|VISIT|EMAIL|FAX|API_112|FSS
    RCPT_PLCS_NM    VARCHAR(100)    NULL,
    CRIME_TYP_CD    VARCHAR(6)      NULL,
    CRIME_TYP_NM    VARCHAR(100)    NULL,
    DAM_AMT         NUMERIC(20,0)   NULL,
    INCDT_DT        TIMESTAMP       NULL,                   -- 피해 발생 일시 (Valid Time)
    VICTIM_NM       VARCHAR(150)    NULL,
    VICTIM_CNTCT    VARCHAR(50)     NULL,
    SUMRY_CN        TEXT            NULL,
    STATUS_CD       VARCHAR(20)     NOT NULL DEFAULT 'PENDING', -- PENDING|LINKED|REJECTED|CLOSED
    LINKED_INCDNT_NO VARCHAR(20)    NULL,                   -- 연결 사건번호 (filed_as 엣지 대응)
    PREPROC_ORG_ID  VARCHAR(50)     NULL,
    OCR_CONF        NUMERIC(4,3)    NULL,
    NER_CONF        NUMERIC(4,3)    NULL,
    SCHEMA_VER      VARCHAR(20)     NULL,
    RAW_FILE_PATH   VARCHAR(500)    NULL,
    -- ETRI crime_meta 연계 (v3.2 추가)
    CRIME_METHOD_CD VARCHAR(30)     NULL,                   -- TB_CMN_CD(CRIME_METHOD) 참조
    CRIME_STEP_CN   VARCHAR(200)    NULL,                   -- 범죄 단계 자유기술 (모집/이체/인출/세탁 등)
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_PETTN_MST_PK    PRIMARY KEY (DCLR_SN),
    CONSTRAINT TB_PETTN_MST_ID_UQ UNIQUE (PETITION_ID)
);
COMMENT ON TABLE  TB_PETTN_MST IS '진정서/신고 마스터 (수사 개시 전·후 모두 존재). Bridge Key: vt_petition.raw_id→DCLR_SN, vt_petition.petition_id→PETITION_ID';
COMMENT ON COLUMN TB_PETTN_MST.STATUS_CD IS 'PENDING=미처리, LINKED=사건연결, REJECTED=기각, CLOSED=종결';
COMMENT ON COLUMN TB_PETTN_MST.CRIME_METHOD_CD IS 'ETRI crime_meta 범행수법 코드. TB_CMN_CD(CD_GRP_ID=CRIME_METHOD) 참조';
CREATE INDEX IDX_PETTN_RCPT_DT   ON TB_PETTN_MST (RCPT_DT);
CREATE INDEX IDX_PETTN_STATUS    ON TB_PETTN_MST (STATUS_CD);
CREATE INDEX IDX_PETTN_CRIME_TYP ON TB_PETTN_MST (CRIME_TYP_CD);
CREATE INDEX IDX_PETTN_LINKED    ON TB_PETTN_MST (LINKED_INCDNT_NO);


-- ② 진정서 군집 (그래프 clusters_with 엣지 대응)
CREATE TABLE TB_PETTN_CLSTR (
    CLSTR_SN        BIGSERIAL       NOT NULL,
    PETTN_SN_A      BIGINT          NOT NULL,               -- 진정서 A (TB_PETTN_MST FK)
    PETTN_SN_B      BIGINT          NOT NULL,               -- 진정서 B
    CLSTR_ID        VARCHAR(50)     NULL,                   -- 군집 ID (같은 군집 동일 값)
    SIM_SCORE       NUMERIC(4,3)    NULL,                   -- 유사도 0.000~1.000
    SIM_BASIS_CD    VARCHAR(50)     NULL,                   -- SAME_ACNT|SAME_PHON|SAME_IP|COMBINED
    AUTO_YN         CHAR(1)         NOT NULL DEFAULT 'Y',
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_PETTN_CLSTR_PK PRIMARY KEY (CLSTR_SN),
    CONSTRAINT TB_PETTN_CLSTR_UQ UNIQUE (PETTN_SN_A, PETTN_SN_B)
);
COMMENT ON TABLE TB_PETTN_CLSTR IS '진정서 유사 군집 (clusters_with 엣지 대응). ⚠ ETL 미구현 — OPEN ISSUE #3';


-- ③ 진정서 처리 이력 (감사)
CREATE TABLE TB_PETTN_PROC_LOG (
    LOG_SN          BIGSERIAL       NOT NULL,
    PETTN_SN        BIGINT          NOT NULL,               -- TB_PETTN_MST FK
    PROC_DT         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PREV_STATUS_CD  VARCHAR(20)     NULL,
    NEW_STATUS_CD   VARCHAR(20)     NOT NULL,
    PROC_USR_ID     VARCHAR(50)     NULL,
    PROC_RSN_CN     TEXT            NULL,
    CONSTRAINT TB_PETTN_PROC_LOG_PK PRIMARY KEY (LOG_SN)
);
COMMENT ON TABLE TB_PETTN_PROC_LOG IS '진정서 상태 변경 감사 (그래프 변환 없음)';


-- ============================================================
-- §4. 사람/주체 도메인 (2개)
-- ============================================================

-- ① 사람 마스터 (그래프 vt_psn 노드 대응)
CREATE TABLE TB_PRSN (
    PRSN_ID         VARCHAR(20)     NOT NULL,
    KORN_FLNM       VARCHAR(150)    NULL,                   -- 한글성명
    RRNO_HASH       CHAR(64)        NULL,                   -- 주민번호 SHA-256 ⚠ 평문 절대 금지
    RRNO_ENC        BYTEA           NULL,                   -- 주민번호 AES-256 암호화 (영장 집행 시만 복호화)
    GNDR_CD         CHAR(1)         NULL,                   -- M|F|U
    NATL_CD         VARCHAR(3)      NULL,                   -- 국적 ISO 3166-1
    DOB             CHAR(8)         NULL,                   -- 생년월일 YYYYMMDD
    PSPRT_NO        VARCHAR(20)     NULL,                   -- 여권번호 (외국인)
    CNTCT           VARCHAR(50)     NULL,
    RISK_LEVEL      SMALLINT        NULL DEFAULT 1,         -- 위험도 1~5
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_PRSN_PK PRIMARY KEY (PRSN_ID)
);
COMMENT ON COLUMN TB_PRSN.RRNO_HASH IS 'SHA-256 해시. 평문 주민번호 저장 절대 금지';
COMMENT ON COLUMN TB_PRSN.RRNO_ENC  IS 'AES-256 암호화. 영장 집행 시에만 복호화 허용';


-- ② 조직/기관 마스터 (그래프 vt_org 노드 대응)
CREATE TABLE TB_INST (
    INST_ID         VARCHAR(20)     NOT NULL,
    INST_NM         VARCHAR(200)    NOT NULL,
    INST_SE_CD      VARCHAR(4)      NULL,                   -- BANK|TELECOM|PLATFORM|GOVT|CRIMINAL
    BRNO            VARCHAR(10)     NULL,                   -- 사업자등록번호
    BANK_CD         VARCHAR(10)     NULL,
    ADDR            VARCHAR(200)    NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_INST_PK PRIMARY KEY (INST_ID)
);


-- ============================================================
-- §5. 금융 도메인 (2개)
-- ============================================================

-- ① 금융 계좌 (복합 PK: 계좌번호 + 은행코드, 그래프 vt_bacnt 노드 대응)
CREATE TABLE TB_FIN_BACNT (
    BACNT_NO        VARCHAR(20)     NOT NULL,               -- 계좌번호
    BANK_CD         VARCHAR(10)     NOT NULL,               -- 은행코드 (복합 PK)
    BANK_NM         VARCHAR(100)    NULL,
    DPSTR_NM        VARCHAR(100)    NULL,                   -- 예금주명
    ACNT_TYP_CD     VARCHAR(10)     NULL,                   -- DEPOSIT|SAVING|INVEST|CORP
    BACNT_OPN_DT    CHAR(8)         NULL,                   -- 개설일자 YYYYMMDD
    INST_ID         VARCHAR(20)     NULL,
    IS_FRZNACNT_YN  CHAR(1)         NULL DEFAULT 'N',       -- 지급정지 여부
    IS_BRNER_YN     CHAR(1)         NULL DEFAULT 'N',       -- 대포통장 의심
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_FIN_BACNT_PK PRIMARY KEY (BACNT_NO, BANK_CD)
);
COMMENT ON TABLE TB_FIN_BACNT IS '금융 계좌 마스터. PK = 계좌번호+은행코드 (경찰청 표준)';
CREATE INDEX IDX_FIN_BACNT_DPSTR ON TB_FIN_BACNT (DPSTR_NM);
CREATE INDEX IDX_FIN_BACNT_INST  ON TB_FIN_BACNT (INST_ID);


-- ② 금융 거래 내역 (대용량 RDB 유지, Bridge Key로 그래프 vt_transfer 연동)
CREATE TABLE TB_FIN_BACNT_DLNG (
    DLNG_SN         BIGSERIAL       NOT NULL,               -- Bridge Key → vt_transfer.dlng_sn
    BACNT_NO        VARCHAR(20)     NOT NULL,
    BANK_CD         VARCHAR(10)     NOT NULL,
    DLNG_DT         TIMESTAMP       NOT NULL,               -- 거래일시 (Valid Time)
    DLNG_SE_CD      VARCHAR(10)     NOT NULL,               -- DEPOSIT|WITHDRAW|TRANSFER|ATM
    DLNG_AMT        NUMERIC(20,0)   NOT NULL,
    BLNC_AMT        NUMERIC(20,0)   NULL,
    RLT_BACNT_NO    VARCHAR(20)     NULL,
    RLT_BANK_CD     VARCHAR(10)     NULL,
    RLT_DPSTR_NM    VARCHAR(100)    NULL,
    DLNG_MEMO_CN    VARCHAR(500)    NULL,
    ATM_MNG_NO      VARCHAR(20)     NULL,                   -- ATM 관리번호 (ATM 출금 시)
    HOP_LVL         SMALLINT        NULL DEFAULT 1,         -- 자금흐름 단계
    IS_SUSPCS_YN    CHAR(1)         NULL DEFAULT 'N',
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_FIN_BACNT_DLNG_PK PRIMARY KEY (DLNG_SN)
);
COMMENT ON COLUMN TB_FIN_BACNT_DLNG.DLNG_SN IS 'Bridge Key: vt_transfer.dlng_sn 참조';
CREATE INDEX IDX_DLNG_ACNT     ON TB_FIN_BACNT_DLNG (BACNT_NO, BANK_CD);
CREATE INDEX IDX_DLNG_DT       ON TB_FIN_BACNT_DLNG (DLNG_DT);
CREATE INDEX IDX_DLNG_RLT_ACNT ON TB_FIN_BACNT_DLNG (RLT_BACNT_NO, RLT_BANK_CD);
CREATE INDEX IDX_DLNG_AMT      ON TB_FIN_BACNT_DLNG (DLNG_AMT);
CREATE INDEX IDX_DLNG_SUSPCS   ON TB_FIN_BACNT_DLNG (IS_SUSPCS_YN);


-- ============================================================
-- §6. 통신 도메인 (5개)
-- ============================================================

-- ① 전화번호 마스터 (그래프 vt_telno 노드 대응)
CREATE TABLE TB_TELNO_MST (
    TELNO           VARCHAR(20)     NOT NULL,               -- 전화번호 (정규화: 숫자만)
    COUNTRY_CD      CHAR(4)         NULL DEFAULT '+82',
    TELCO_NM        VARCHAR(50)     NULL,                   -- SKT|KT|LGU+|MVNO
    JOIN_TYP_CD     VARCHAR(20)     NULL,                   -- INDIVIDUAL|CORPORATE|PREPAID
    IS_RGST_YN      CHAR(1)         NULL DEFAULT 'Y',
    IS_BRNER_YN     CHAR(1)         NULL DEFAULT 'N',       -- 선불폰/대포폰 의심
    SUBS_HLDR_NM    VARCHAR(150)    NULL,
    IMSI            VARCHAR(20)     NULL,
    SPAM_CNT        INTEGER         NULL DEFAULT 0,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    CONSTRAINT TB_TELNO_MST_PK PRIMARY KEY (TELNO)
);
CREATE INDEX IDX_TELNO_BRNER ON TB_TELNO_MST (IS_BRNER_YN);
CREATE INDEX IDX_TELNO_SPAM  ON TB_TELNO_MST (SPAM_CNT);


-- ② 통화 내역 (대용량 RDB 유지, Bridge Key로 그래프 vt_call 연동)
CREATE TABLE TB_TELNO_CALL_DTL (
    CALL_SN         BIGSERIAL       NOT NULL,               -- Bridge Key → vt_call.call_sn
    DSPTCH_TELNO    VARCHAR(20)     NOT NULL,
    RCPTN_TELNO     VARCHAR(20)     NOT NULL,
    CALL_STRT_DT    TIMESTAMP       NOT NULL,               -- 통화 시작 일시 (Valid Time)
    CALL_DUR_SEC    INTEGER         NULL DEFAULT 0,
    CALL_TYP_CD     VARCHAR(10)     NULL,                   -- VOICE|DATA|SMS_ALT
    BSST_NM         VARCHAR(100)    NULL,
    BSST_LAT        NUMERIC(12,10)  NULL,
    BSST_LOT        NUMERIC(13,10)  NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_TELNO_CALL_DTL_PK PRIMARY KEY (CALL_SN)
);
COMMENT ON COLUMN TB_TELNO_CALL_DTL.CALL_SN IS 'Bridge Key: vt_call.call_sn 참조';
CREATE INDEX IDX_CALL_DSPTCH  ON TB_TELNO_CALL_DTL (DSPTCH_TELNO);
CREATE INDEX IDX_CALL_RCPTN   ON TB_TELNO_CALL_DTL (RCPTN_TELNO);
CREATE INDEX IDX_CALL_STRT_DT ON TB_TELNO_CALL_DTL (CALL_STRT_DT);


-- ③ SMS 메시지 (대용량 RDB 유지, 분석 시 JOIN)
CREATE TABLE TB_TELNO_SMS_MSG (
    MSG_SN          BIGSERIAL       NOT NULL,
    DSPTCH_TELNO    VARCHAR(20)     NOT NULL,
    RCPTN_TELNO     VARCHAR(20)     NOT NULL,
    DSPTCH_DT       TIMESTAMP       NOT NULL,
    MSG_CN_HASH     CHAR(64)        NULL,                   -- 내용 SHA-256 (원문 저장 금지)
    IS_SPAM_YN      CHAR(1)         NULL DEFAULT 'N',
    SENTMT_CD       VARCHAR(20)     NULL,                   -- THREAT|LURE|NORMAL|UNKNOWN
    MNTNS_ACNT_YN   CHAR(1)         NULL DEFAULT 'N',
    MNTNS_URL_YN    CHAR(1)         NULL DEFAULT 'N',
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_TELNO_SMS_MSG_PK PRIMARY KEY (MSG_SN)
);


-- ④ 가입 정보 (통신사 제출)
CREATE TABLE TB_TELNO_JOIN (
    JOIN_SN              BIGSERIAL       NOT NULL,
    TELNO                VARCHAR(20)     NOT NULL,
    JOIN_DT              TIMESTAMP       NULL,              -- Valid Time 시작
    WTHDRW_DT            TIMESTAMP       NULL,              -- Valid Time 종료
    SUBS_HLDR_NM         VARCHAR(150)    NULL,
    SUBS_HLDR_RRNO_HASH  CHAR(64)        NULL,
    TELECOM_NM           VARCHAR(50)     NULL,
    SRC_ID               VARCHAR(50)     NULL,
    REC_CREATED_DT       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_TELNO_JOIN_PK PRIMARY KEY (JOIN_SN)
);


-- ⑤ 메신저/채팅 메시지 (대용량 RDB 유지)
CREATE TABLE TB_CHAT_MSG (
    MSG_SN          BIGSERIAL       NOT NULL,
    APP_NM          VARCHAR(50)     NOT NULL,               -- KakaoTalk|Telegram|SMS|iMessage
    ROOM_ID         VARCHAR(200)    NULL,
    SENDER_ID       VARCHAR(200)    NULL,
    DSPTCH_DT       TIMESTAMP       NOT NULL,
    MSG_CN_HASH     CHAR(64)        NULL,                   -- 내용 SHA-256
    MNTNS_ACNT_YN   CHAR(1)         NULL DEFAULT 'N',
    MNTNS_URL_YN    CHAR(1)         NULL DEFAULT 'N',
    SENTMT_CD       VARCHAR(20)     NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_CHAT_MSG_PK PRIMARY KEY (MSG_SN)
);


-- ============================================================
-- §7. 차량/이동 도메인 (2개)
-- ============================================================

-- ① 차량 마스터 (그래프 vt_vhcl 노드 대응)
CREATE TABLE TB_VHCL_MST (
    VHCLNO          VARCHAR(20)     NOT NULL,
    CARMDL_NM       VARCHAR(100)    NULL,
    CARMDL_DTL_NM   VARCHAR(200)    NULL,
    COLOR_NM        VARCHAR(50)     NULL,
    OWNR_NM         VARCHAR(150)    NULL,
    RGST_DT         CHAR(8)         NULL,
    IS_STLN_YN      CHAR(1)         NULL DEFAULT 'N',
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_VHCL_MST_PK PRIMARY KEY (VHCLNO)
);


-- ② LPR 번호판 인식 이벤트 (Bridge Key → vt_movement.rcgn_sn)
CREATE TABLE TB_VHCL_LPR_EVT (
    RCGN_SN         BIGSERIAL       NOT NULL,               -- Bridge Key → vt_movement.rcgn_sn
    VHCLNO          VARCHAR(20)     NOT NULL,
    RCGN_DT         TIMESTAMP       NOT NULL,
    LAT             NUMERIC(12,10)  NULL,
    LOT             NUMERIC(13,10)  NULL,
    CCTV_ID         VARCHAR(50)     NULL,
    INST_LOC_NM     VARCHAR(200)    NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_VHCL_LPR_EVT_PK PRIMARY KEY (RCGN_SN)
);
COMMENT ON COLUMN TB_VHCL_LPR_EVT.RCGN_SN IS 'Bridge Key: vt_movement.rcgn_sn 참조';
CREATE INDEX IDX_LPR_VHCLNO  ON TB_VHCL_LPR_EVT (VHCLNO);
CREATE INDEX IDX_LPR_RCGN_DT ON TB_VHCL_LPR_EVT (RCGN_DT);


-- ============================================================
-- §8. 위치/지리 도메인 (2개)
-- ============================================================

-- ① 기지국 위치 이벤트 (Bridge Key → vt_movement.loc_evt_sn)
CREATE TABLE TB_GEO_MBL_LOC_EVT (
    LOC_EVT_SN      BIGSERIAL       NOT NULL,               -- Bridge Key → vt_movement.loc_evt_sn
    TELNO           VARCHAR(20)     NOT NULL,
    OCCRN_DT        TIMESTAMP       NOT NULL,
    EVT_TYP_NM      VARCHAR(50)     NULL,                   -- 발신|착신|위치등록
    BSST_NM         VARCHAR(100)    NULL,
    BSST_ADDR       VARCHAR(300)    NULL,
    BSST_LAT        NUMERIC(12,10)  NULL,
    BSST_LOT        NUMERIC(13,10)  NULL,
    TELECOM_NM      VARCHAR(50)     NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_GEO_MBL_LOC_EVT_PK PRIMARY KEY (LOC_EVT_SN)
);
COMMENT ON COLUMN TB_GEO_MBL_LOC_EVT.LOC_EVT_SN IS 'Bridge Key: vt_movement.loc_evt_sn 참조';
CREATE INDEX IDX_GEO_LOC_TELNO ON TB_GEO_MBL_LOC_EVT (TELNO);
CREATE INDEX IDX_GEO_LOC_DT    ON TB_GEO_MBL_LOC_EVT (OCCRN_DT);


-- ② 교통카드 이동 이력 (Bridge Key → vt_movement.mv_sn)
CREATE TABLE TB_GEO_TRST_CARD_TRIP (
    MV_SN           BIGSERIAL       NOT NULL,               -- Bridge Key → vt_movement.mv_sn
    CARD_NO         VARCHAR(30)     NOT NULL,
    USE_DT          TIMESTAMP       NOT NULL,
    TK_PNM          VARCHAR(200)    NULL,                   -- 승차장소명
    GF_PNM          VARCHAR(200)    NULL,                   -- 하차장소명
    VHCL_NO         VARCHAR(20)     NULL,
    FARE_AMT        NUMERIC(10,0)   NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_GEO_TRST_CARD_TRIP_PK PRIMARY KEY (MV_SN)
);
COMMENT ON COLUMN TB_GEO_TRST_CARD_TRIP.MV_SN IS 'Bridge Key: vt_movement.mv_sn 참조';


-- ============================================================
-- §9. 디지털 도메인 (4개)
-- ============================================================

-- ① 웹 도메인/URL (그래프 vt_site 노드 대응)
CREATE TABLE TB_WEB_DMN (
    URL_ADDR        VARCHAR(2000)   NOT NULL,
    DMN_ADDR        VARCHAR(500)    NULL,
    SITE_TYP_CD     VARCHAR(20)     NULL,                   -- phishing|malware|fraud|normal
    IS_MLGN_YN      CHAR(1)         NULL DEFAULT 'N',
    IP_ADDR         VARCHAR(45)     NULL,
    PAGE_HASH       CHAR(64)        NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_WEB_DMN_PK PRIMARY KEY (URL_ADDR)
);
COMMENT ON COLUMN TB_WEB_DMN.URL_ADDR IS 'v3.0: domain → url_addr 표준화 (구 domain 컬럼 제거)';


-- ② 웹 악성 지표 (vt_site 속성 갱신용)
CREATE TABLE TB_WEB_MLGN_IDC (
    IDC_SN          BIGSERIAL       NOT NULL,
    URL_ADDR        VARCHAR(2000)   NOT NULL,               -- TB_WEB_DMN FK
    RISK_GRD_CD     VARCHAR(10)     NOT NULL,               -- HIGH|MEDIUM|LOW
    SIGN_KWRD_CN    VARCHAR(500)    NULL,
    DETCT_DT        TIMESTAMP       NULL,
    REGISTRAR_NM    VARCHAR(200)    NULL,
    WHOIS_ORG_NM    VARCHAR(200)    NULL,
    REG_DT          TIMESTAMP       NULL,
    EXP_DT          TIMESTAMP       NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_WEB_MLGN_IDC_PK PRIMARY KEY (IDC_SN)
);


-- ③ 시스템 접속 이벤트 (그래프 vt_access 노드 대응)
-- ⚠ OPEN ISSUE #1: ETL코드(CNNT_IP_ADDR/LGN_DT) vs 이 DDL(IP_ADDR/ACCESS_DT) 컬럼명 불일치
CREATE TABLE TB_SYS_LGN_EVT (
    LGN_SN          BIGSERIAL       NOT NULL,
    IP_ADDR         VARCHAR(45)     NOT NULL,               -- ⚠ ETL은 CNNT_IP_ADDR 사용 중 → 통일 필요
    ACCESS_DT       TIMESTAMP       NOT NULL,               -- ⚠ ETL은 LGN_DT 사용 중 → 통일 필요
    ACTN_CD         VARCHAR(20)     NULL,                   -- GET|POST|DOWNLOAD|UPLOAD  (⚠ ETL은 LGN_RSLT_CD 사용)
    USER_AGENT_CN   TEXT            NULL,
    STATUS_CODE     SMALLINT        NULL,
    BYTES_SENT      BIGINT          NULL,
    BYTES_RECV      BIGINT          NULL,
    TGT_URL         VARCHAR(2000)   NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_SYS_LGN_EVT_PK PRIMARY KEY (LGN_SN)
);
COMMENT ON TABLE TB_SYS_LGN_EVT IS '⚠ OPEN ISSUE #1: ETL(rdb_to_graph_service.py L246-251)은 CNNT_IP_ADDR/LGN_DT/USER_ID/LGN_RSLT_CD 사용. 이 DDL과 컬럼명 불일치. 한쪽 기준으로 통일 후 마이그레이션 필요';
CREATE INDEX IDX_LGN_IP ON TB_SYS_LGN_EVT (IP_ADDR);
CREATE INDEX IDX_LGN_DT ON TB_SYS_LGN_EVT (ACCESS_DT);


-- ④ 디지털 파일 증거 목록 (그래프 vt_file 노드 대응)
CREATE TABLE TB_DGTL_FILE_INVNT (
    FILE_SN         BIGSERIAL       NOT NULL,
    HASH_VAL        CHAR(64)        NOT NULL,               -- SHA-256 (필수 식별자)
    FILE_NM         VARCHAR(500)    NULL,
    FILE_EXTSN_NM   VARCHAR(20)     NULL,
    FILE_SZ         BIGINT          NULL,
    FILE_PATH_CN    VARCHAR(2000)   NULL,
    CREAT_DT        TIMESTAMP       NULL,
    MDFR_DT         TIMESTAMP       NULL,
    IS_MLGN_YN      CHAR(1)         NULL DEFAULT 'N',
    VT_SCORE_CN     VARCHAR(20)     NULL,                   -- VirusTotal 탐지율 (예: '35/72')
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_DGTL_FILE_INVNT_PK PRIMARY KEY (FILE_SN),
    CONSTRAINT TB_DGTL_FILE_HASH_UQ UNIQUE (HASH_VAL)
);
COMMENT ON COLUMN TB_DGTL_FILE_INVNT.HASH_VAL IS 'v3.0: SHA-256 단일 식별자. hash_md5 컬럼 제거';


-- ============================================================
-- §10. OSINT 도메인 (7개) — 그래프 노드 속성 갱신용, 직접 변환 없음
-- ============================================================

-- ① IP 평판 (AbuseIPDB, VirusTotal, Shodan 등 → vt_ip 속성 갱신)
CREATE TABLE TB_OSINT_IP_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    IP_ADDR         VARCHAR(45)     NOT NULL,
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    IS_VPN_YN       CHAR(1)         NULL DEFAULT 'N',
    IS_TOR_YN       CHAR(1)         NULL DEFAULT 'N',
    IS_PROXY_YN     CHAR(1)         NULL DEFAULT 'N',
    IS_HOSTING_YN   CHAR(1)         NULL DEFAULT 'N',
    ABUSE_SCORE     SMALLINT        NULL,                   -- 0~100
    ISP_NM          VARCHAR(200)    NULL,
    ASN_NO          VARCHAR(20)     NULL,
    COUNTRY_CD      CHAR(2)         NULL,
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_IP_REP_PK PRIMARY KEY (REP_SN),
    CONSTRAINT TB_OSINT_IP_REP_UQ  UNIQUE (IP_ADDR, SRC_ID, QUERY_DT)
);
CREATE INDEX IDX_OSINT_IP_ADDR  ON TB_OSINT_IP_REP (IP_ADDR);
CREATE INDEX IDX_OSINT_IP_SCORE ON TB_OSINT_IP_REP (ABUSE_SCORE);


-- ② 도메인 평판 (WHOIS, VirusTotal, URLhaus → vt_site 속성 갱신)
CREATE TABLE TB_OSINT_DMN_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    DMN_ADDR        VARCHAR(500)    NOT NULL,
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    RISK_GRD_CD     VARCHAR(10)     NULL,
    IS_MLGN_YN      CHAR(1)         NULL DEFAULT 'N',
    REGISTRAR_NM    VARCHAR(200)    NULL,
    REG_DT          TIMESTAMP       NULL,
    EXP_DT          TIMESTAMP       NULL,
    REGISTRANT_NM   VARCHAR(200)    NULL,
    REGISTRANT_EMAIL VARCHAR(200)   NULL,
    WHOIS_ORG_NM    VARCHAR(200)    NULL,
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_DMN_REP_PK PRIMARY KEY (REP_SN)
);
CREATE INDEX IDX_OSINT_DMN ON TB_OSINT_DMN_REP (DMN_ADDR);


-- ③ 파일 해시 평판 (VirusTotal → vt_file 속성 갱신)
CREATE TABLE TB_OSINT_HASH_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    HASH_VAL        CHAR(64)        NOT NULL,               -- SHA-256
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    IS_MLGN_YN      CHAR(1)         NULL DEFAULT 'N',
    DETCT_CNT       SMALLINT        NULL,
    TOTAL_CNT       SMALLINT        NULL,
    MLGN_NM         VARCHAR(200)    NULL,
    FILE_TYP_NM     VARCHAR(100)    NULL,
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_HASH_REP_PK PRIMARY KEY (REP_SN)
);
CREATE INDEX IDX_OSINT_HASH ON TB_OSINT_HASH_REP (HASH_VAL);


-- ④ 전화번호 평판 (더치트, 경찰청 스팸DB → vt_telno 속성 갱신)
CREATE TABLE TB_OSINT_PHON_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    TELNO           VARCHAR(20)     NOT NULL,
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    SPAM_CNT        INTEGER         NULL DEFAULT 0,
    CRIME_TYP_CD    VARCHAR(6)      NULL,
    FIRST_RPT_DT    TIMESTAMP       NULL,
    LAST_RPT_DT     TIMESTAMP       NULL,
    IS_CONFRMD_YN   CHAR(1)         NULL DEFAULT 'N',
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_PHON_REP_PK PRIMARY KEY (REP_SN)
);
CREATE INDEX IDX_OSINT_PHON      ON TB_OSINT_PHON_REP (TELNO);
CREATE INDEX IDX_OSINT_PHON_SPAM ON TB_OSINT_PHON_REP (SPAM_CNT);


-- ⑤ 계좌 피해 신고 (더치트, 금감원 → vt_bacnt 속성 갱신)
CREATE TABLE TB_OSINT_ACNT_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    BACNT_NO        VARCHAR(20)     NOT NULL,
    BANK_CD         VARCHAR(10)     NOT NULL,
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    RPT_CNT         INTEGER         NULL DEFAULT 0,
    TTL_DAM_AMT     NUMERIC(20,0)   NULL,
    FIRST_RPT_DT    TIMESTAMP       NULL,
    LAST_RPT_DT     TIMESTAMP       NULL,
    IS_FRZNACNT_YN  CHAR(1)         NULL DEFAULT 'N',
    CONFRMD_YN      CHAR(1)         NULL DEFAULT 'N',
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_ACNT_REP_PK PRIMARY KEY (REP_SN)
);
CREATE INDEX IDX_OSINT_ACNT ON TB_OSINT_ACNT_REP (BACNT_NO, BANK_CD);


-- ⑥ 가상자산 지갑 위험 (Chainalysis, 업비트 FDS → vt_crypto 속성 갱신)
CREATE TABLE TB_OSINT_WALLET_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    WALLET_ADDR     VARCHAR(200)    NOT NULL,
    BLOCKCHAIN_NM   VARCHAR(20)     NOT NULL,
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    RISK_SCORE      SMALLINT        NULL,                   -- 0~100
    RISK_TYP_CD     VARCHAR(50)     NULL,                   -- dark_market|stolen|mixer|scam
    KYC_VRFY_YN     CHAR(1)         NULL DEFAULT 'N',
    TX_CNT          INTEGER         NULL,
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_WALLET_REP_PK PRIMARY KEY (REP_SN)
);
CREATE INDEX IDX_OSINT_WALLET ON TB_OSINT_WALLET_REP (WALLET_ADDR, BLOCKCHAIN_NM);


-- ⑦ 디지털 ID/계정 평판 (SNS 플랫폼, 더치트 → vt_id 속성 갱신)
CREATE TABLE TB_OSINT_ID_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    ID_VAL          VARCHAR(200)    NOT NULL,
    PLATFORM_NM     VARCHAR(100)    NOT NULL,
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    RPT_CNT         INTEGER         NULL DEFAULT 0,
    IS_ACTIVE_YN    CHAR(1)         NULL,
    PROFILE_URL     VARCHAR(500)    NULL,
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_ID_REP_PK PRIMARY KEY (REP_SN)
);
CREATE INDEX IDX_OSINT_ID ON TB_OSINT_ID_REP (ID_VAL, PLATFORM_NM);


-- ============================================================
-- §11. 마약 도메인 (2개)
-- ============================================================

-- ① 마약 은어 사전 (분석 참조용)
CREATE TABLE TB_DRUG_SLANG (
    SLANG_SN        BIGSERIAL       NOT NULL,
    SLANG_WRD_NM    VARCHAR(100)    NOT NULL,
    DRUG_TYP_CD     VARCHAR(20)     NULL,
    DRUG_TYP_NM     VARCHAR(100)    NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_DRUG_SLANG_PK     PRIMARY KEY (SLANG_SN),
    CONSTRAINT TB_DRUG_SLANG_WRD_UQ UNIQUE (SLANG_WRD_NM)
);


-- ② 마약 거래 이력 (그래프 vt_transfer 연동 가능)
CREATE TABLE TB_DRUG_TRDE (
    TRDE_SN         BIGSERIAL       NOT NULL,
    TRDE_DT         TIMESTAMP       NULL,
    DRUG_TYP_CD     VARCHAR(20)     NULL,
    TRDE_AMT_KRW    NUMERIC(20,0)   NULL,
    BUYER_ID        VARCHAR(50)     NULL,
    SELLER_ID       VARCHAR(50)     NULL,
    PLATFORM_NM     VARCHAR(100)    NULL,                   -- 텔레그램|다크웹 등
    INCDNT_NO       VARCHAR(20)     NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_DRUG_TRDE_PK PRIMARY KEY (TRDE_SN)
);


-- ============================================================
-- §12. 사기신고 도메인 (2개)
-- ============================================================

-- ① 사기 피해자 신고 (Bridge Key → vt_petition.raw_id)
CREATE TABLE TB_FRD_VCTM_RPT (
    DCLR_SN         BIGSERIAL       NOT NULL,               -- Bridge Key → vt_petition.raw_id
    RCPT_DT         TIMESTAMP       NOT NULL,
    RCPT_CH_CD      VARCHAR(20)     NOT NULL,               -- WEB|VISIT|EMAIL|API_112
    VICTIM_NM       VARCHAR(150)    NULL,
    VICTIM_CNTCT    VARCHAR(50)     NULL,
    CRIME_TYP_CD    VARCHAR(6)      NULL,
    FRAUD_ACNT_NO   VARCHAR(20)     NULL,
    FRAUD_BANK_CD   VARCHAR(10)     NULL,
    DAM_AMT         NUMERIC(20,0)   NULL,
    INCDT_DT        TIMESTAMP       NULL,
    SUMRY_CN        TEXT            NULL,
    STATUS_CD       VARCHAR(20)     NOT NULL DEFAULT 'PENDING',
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_FRD_VCTM_RPT_PK PRIMARY KEY (DCLR_SN)
);
COMMENT ON COLUMN TB_FRD_VCTM_RPT.DCLR_SN IS 'Bridge Key: vt_petition.raw_id 참조';


-- ② 사기 계좌 지급정지 목록 (vt_bacnt 속성 갱신)
CREATE TABLE TB_FRD_ACNT_BLK (
    BLK_SN          BIGSERIAL       NOT NULL,
    BACNT_NO        VARCHAR(20)     NOT NULL,
    BANK_CD         VARCHAR(10)     NOT NULL,
    BLK_DT          TIMESTAMP       NOT NULL,               -- Valid Time 시작
    UNBLK_DT        TIMESTAMP       NULL,                   -- Valid Time 종료
    BLK_RSN_CD      VARCHAR(20)     NULL,                   -- FRAUD|INVESTIGATE|COURT
    INCDNT_NO       VARCHAR(20)     NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_FRD_ACNT_BLK_PK PRIMARY KEY (BLK_SN)
);


-- ============================================================
-- §13. 엔티티 해소 도메인 (2개)
-- ============================================================

-- ① 동일 인물 해소 (그래프 sameAs 엣지 대응)
CREATE TABLE TB_ENTITY_SAME_AS (
    MATCH_SN        BIGSERIAL       NOT NULL,
    PRSN_ID_A       VARCHAR(20)     NOT NULL,               -- TB_PRSN FK
    PRSN_ID_B       VARCHAR(20)     NOT NULL,
    MATCH_SCORE     NUMERIC(4,3)    NOT NULL,               -- 유사도 0.000~1.000
    MATCH_BASIS_CD  VARCHAR(100)    NOT NULL,               -- SAME_PHONE|SAME_ACNT|SAME_IP|COMBINED
    REVIEW_STATUS_CD VARCHAR(20)    NOT NULL DEFAULT 'PENDING', -- PENDING|CONFIRMED|REJECTED
    AUTO_YN         CHAR(1)         NOT NULL DEFAULT 'Y',
    REVIEWER_ID     VARCHAR(50)     NULL,
    REVIEW_DT       TIMESTAMP       NULL,
    REVIEW_CMT_CN   TEXT            NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_ENTITY_SAME_AS_PK PRIMARY KEY (MATCH_SN),
    CONSTRAINT TB_ENTITY_SAME_AS_UQ UNIQUE (PRSN_ID_A, PRSN_ID_B)
);
COMMENT ON TABLE TB_ENTITY_SAME_AS IS '동일 인물 해소 후보 (sameAs 엣지 생성 전 검토). CONFIRMED 상태만 그래프 엣지로 변환';
CREATE INDEX IDX_SAMEAS_STATUS ON TB_ENTITY_SAME_AS (REVIEW_STATUS_CD);


-- ② 모순/충돌 정보 기록 (그래프 contradicts 엣지 대응)
CREATE TABLE TB_ENTITY_CONFLICT (
    CNFL_SN         BIGSERIAL       NOT NULL,
    PRSN_ID_A       VARCHAR(20)     NOT NULL,
    PRSN_ID_B       VARCHAR(20)     NOT NULL,
    CNFL_FIELD_NM   VARCHAR(100)    NULL,                   -- 충돌 필드명 (예: RRNO_HASH)
    CNFL_DTL_CN     TEXT            NULL,
    CNFL_TYP_CD     VARCHAR(30)     NULL,                   -- ID_THEFT|DATA_ERROR|ALIAS
    RESOLVED_YN     CHAR(1)         NULL DEFAULT 'N',
    RESOLVED_BY     VARCHAR(50)     NULL,
    RESOLVED_DT     TIMESTAMP       NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_ENTITY_CONFLICT_PK PRIMARY KEY (CNFL_SN)
);
COMMENT ON TABLE TB_ENTITY_CONFLICT IS '인물 정보 모순 기록 (contradicts 엣지 대응). ⚠ ETL 미구현 — OPEN ISSUE #2';


-- ============================================================
-- §14. Phase 6E 마스터 도메인 (6개) — 신규 추가
--      ETL 구현 완료 (rdb_to_graph_service.py L864-1036)
--      ⚠ RDB 문서 v3.1 DDL 누락 → 이 파일이 최초 공식 DDL
-- ============================================================

-- ① 디지털 식별자 마스터 (그래프 vt_id 노드 대응)
CREATE TABLE TB_DGTL_ID_MST (
    ID_SN           BIGSERIAL       NOT NULL,               -- PK (자동채번)
    ID_VAL          VARCHAR(200)    NOT NULL,               -- 식별자 값 (예: 'gildong99')
    PLATFORM_NM     VARCHAR(100)    NOT NULL,               -- KakaoTalk|Telegram|Instagram|Naver|Discord
    ID_TYP_CD       VARCHAR(30)     NULL,                   -- account_id|nickname|email_id|user_no
    PROFILE_URL     VARCHAR(500)    NULL,
    IS_ACTIVE_YN    CHAR(1)         NULL DEFAULT 'Y',       -- 현재 활성 여부
    REAL_NM         VARCHAR(150)    NULL,                   -- 실명 (확인된 경우)
    RPT_CNT         INTEGER         NULL DEFAULT 0,         -- 피해 신고 건수
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_DGTL_ID_MST_PK PRIMARY KEY (ID_SN),
    CONSTRAINT TB_DGTL_ID_MST_UQ  UNIQUE (ID_VAL, PLATFORM_NM)
);
COMMENT ON TABLE TB_DGTL_ID_MST IS '디지털 식별자/계정 마스터 (그래프 vt_id 노드 대응). 기존 vt_persona 흡수';
CREATE INDEX IDX_DGTL_ID_PLATFORM ON TB_DGTL_ID_MST (PLATFORM_NM);
CREATE INDEX IDX_DGTL_ID_RPT_CNT  ON TB_DGTL_ID_MST (RPT_CNT);


-- ② 이메일 주소 마스터 (그래프 vt_email 노드 대응)
CREATE TABLE TB_EMAIL_MST (
    EMAIL_SN        BIGSERIAL       NOT NULL,
    EMAIL_ADDR      VARCHAR(200)    NOT NULL,               -- 이메일 주소 (필수 식별자)
    DMN_ADDR        VARCHAR(200)    NULL,                   -- 도메인 부분 (추출 캐시)
    PROVIDER_NM     VARCHAR(50)     NULL,                   -- Gmail|Naver|Daum|Unknown
    IS_DISPOSBL_YN  CHAR(1)         NULL DEFAULT 'N',       -- 일회용 이메일 여부
    RPT_CNT         INTEGER         NULL DEFAULT 0,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_EMAIL_MST_PK      PRIMARY KEY (EMAIL_SN),
    CONSTRAINT TB_EMAIL_MST_ADDR_UQ UNIQUE (EMAIL_ADDR)
);
COMMENT ON TABLE TB_EMAIL_MST IS '이메일 주소 마스터 (그래프 vt_email 노드 대응)';
CREATE INDEX IDX_EMAIL_DMN      ON TB_EMAIL_MST (DMN_ADDR);
CREATE INDEX IDX_EMAIL_PROVIDER ON TB_EMAIL_MST (PROVIDER_NM);


-- ③ 가상자산 지갑 마스터 (그래프 vt_crypto 노드 대응)
CREATE TABLE TB_CRYPTO_WALLET_MST (
    WALLET_SN       BIGSERIAL       NOT NULL,
    WALLET_ADDR     VARCHAR(200)    NOT NULL,               -- 지갑 주소 (필수 식별자)
    BLOCKCHAIN_NM   VARCHAR(20)     NOT NULL,               -- BTC|ETH|USDT|XMR
    ASSET_TYP_CD    VARCHAR(20)     NULL,                   -- coin|token|nft
    EXCH_NM         VARCHAR(100)    NULL,                   -- 거래소명 (Upbit|Bithumb|Binance)
    BALANCE         NUMERIC(30,10)  NULL,                   -- 잔액 (분석 시점)
    RISK_SCORE      SMALLINT        NULL,                   -- 0~100 (체인분석 위험도)
    RISK_TYP_CD     VARCHAR(50)     NULL,                   -- dark_market|stolen|mixer|scam
    KYC_VRFY_YN     CHAR(1)         NULL DEFAULT 'N',
    TX_CNT          INTEGER         NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_CRYPTO_WALLET_MST_PK PRIMARY KEY (WALLET_SN),
    CONSTRAINT TB_CRYPTO_WALLET_MST_UQ UNIQUE (WALLET_ADDR, BLOCKCHAIN_NM)
);
COMMENT ON TABLE TB_CRYPTO_WALLET_MST IS '가상자산 지갑 마스터 (그래프 vt_crypto 노드 대응)';
CREATE INDEX IDX_CRYPTO_BLOCKCHAIN ON TB_CRYPTO_WALLET_MST (BLOCKCHAIN_NM);
CREATE INDEX IDX_CRYPTO_RISK_SCORE ON TB_CRYPTO_WALLET_MST (RISK_SCORE);


-- ④ 기기 마스터 (그래프 vt_dev 노드 대응)
CREATE TABLE TB_DEV_MST (
    DEV_SN          BIGSERIAL       NOT NULL,
    DEV_TYP_CD      VARCHAR(20)     NULL,                   -- smartphone|pc|tablet|iot|pos
    IMEI            VARCHAR(20)     NULL,                   -- IMEI (스마트폰 필수)
    MAC_ADDR        VARCHAR(17)     NULL,                   -- MAC 주소 (XX:XX:XX:XX:XX:XX)
    MODEL_NM        VARCHAR(200)    NULL,
    OS_NM           VARCHAR(20)     NULL,                   -- Android|iOS|Windows|Linux
    OS_VER_NM       VARCHAR(50)     NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_DEV_MST_PK PRIMARY KEY (DEV_SN)
);
COMMENT ON TABLE TB_DEV_MST IS '기기 마스터 (그래프 vt_dev 노드 대응). 스마트폰/PC/태블릿/IoT/POS 통합';
CREATE UNIQUE INDEX IDX_DEV_IMEI    ON TB_DEV_MST (IMEI) WHERE IMEI IS NOT NULL;
CREATE UNIQUE INDEX IDX_DEV_MAC     ON TB_DEV_MST (MAC_ADDR) WHERE MAC_ADDR IS NOT NULL;
CREATE        INDEX IDX_DEV_TYP_CD  ON TB_DEV_MST (DEV_TYP_CD);


-- ⑤ ATM 마스터 (그래프 vt_atm 노드 대응)
CREATE TABLE TB_ATM_MST (
    ATM_MNG_NO      VARCHAR(20)     NOT NULL,               -- ATM 관리번호 (경찰청 ATM_MNG_NO 정렬)
    BANK_NM         VARCHAR(100)    NULL,
    BANK_CD         VARCHAR(10)     NULL,
    ADDR            VARCHAR(300)    NULL,
    LAT             NUMERIC(12,10)  NULL,
    LOT             NUMERIC(13,10)  NULL,
    IS_OUTDOOR_YN   CHAR(1)         NULL DEFAULT 'N',
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_ATM_MST_PK PRIMARY KEY (ATM_MNG_NO)
);
COMMENT ON TABLE TB_ATM_MST IS 'ATM 마스터 (그래프 vt_atm 노드 대응). TB_FIN_BACNT_DLNG.ATM_MNG_NO 참조';
CREATE INDEX IDX_ATM_BANK_CD ON TB_ATM_MST (BANK_CD);
CREATE INDEX IDX_ATM_LAT_LOT ON TB_ATM_MST (LAT, LOT);


-- ⑥ 위치 마스터 (그래프 vt_loc 노드 대응)
-- 물리주소·좌표·기지국·CCTV 설치점을 LOC_TYP_CD 속성으로 통합
CREATE TABLE TB_LOC_MST (
    LOC_SN          BIGSERIAL       NOT NULL,
    LOC_TYP_CD      VARCHAR(20)     NOT NULL,               -- address|cell_tower|cctv|atm_loc|transit|poi
    ADDR            VARCHAR(300)    NULL,                   -- 도로명 주소
    LAT             NUMERIC(12,10)  NULL,
    LOT             NUMERIC(13,10)  NULL,
    PLACE_NM        VARCHAR(200)    NULL,
    SIDO_NM         VARCHAR(50)     NULL,
    SIGUNGU_NM      VARCHAR(100)    NULL,
    -- LOC_TYP_CD = 'cell_tower' 전용
    BSST_NM         VARCHAR(100)    NULL,                   -- 기지국명
    BSST_ADDR       VARCHAR(300)    NULL,
    TELECOM_NM      VARCHAR(50)     NULL,
    -- LOC_TYP_CD = 'cctv' 전용
    CCTV_ID         VARCHAR(50)     NULL,
    CCTV_OPRT_NM    VARCHAR(100)    NULL,                   -- 경찰청|지자체|민간
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_LOC_MST_PK PRIMARY KEY (LOC_SN)
);
COMMENT ON TABLE TB_LOC_MST IS '위치 통합 마스터 (그래프 vt_loc 노드 대응). vt_bsst·vt_cctv를 LOC_TYP_CD 속성으로 흡수';
CREATE INDEX IDX_LOC_TYP_CD ON TB_LOC_MST (LOC_TYP_CD);
CREATE INDEX IDX_LOC_LAT_LOT ON TB_LOC_MST (LAT, LOT);
CREATE INDEX IDX_LOC_BSST_NM ON TB_LOC_MST (BSST_NM) WHERE BSST_NM IS NOT NULL;
CREATE INDEX IDX_LOC_CCTV_ID ON TB_LOC_MST (CCTV_ID) WHERE CCTV_ID IS NOT NULL;


-- ============================================================
-- §15. 사칭 관계 도메인 (1개) — 신규
--      그래프 impersonates 엣지 대응 (ONTOLOGY v3.1 §4 기준)
--      전기통신금융사기법 제3조 근거
-- ============================================================

CREATE TABLE TB_IMPRSN_REL (
    IMPRSN_SN       BIGSERIAL       NOT NULL,
    -- 사칭 주체 (Phone/DigitalID/Email 중 하나)
    SRC_ENTTY_TYP   VARCHAR(20)     NOT NULL,               -- TELNO|DGTL_ID|EMAIL
    SRC_ENTTY_KEY   VARCHAR(200)    NOT NULL,               -- 사칭 주체 식별값
    -- 사칭 대상 기관
    TGT_INST_ID     VARCHAR(20)     NOT NULL,               -- TB_INST.INST_ID (피사칭 기관)
    -- 사칭 정보
    IMPRSN_TYP_CD   VARCHAR(30)     NULL,                   -- VOICE|SMS|APP|WEB
    FSTD_DETCT_DT   TIMESTAMP       NULL,                   -- 최초 탐지 일시
    EVDC_CN         TEXT            NULL,                   -- 근거 내용
    CONFIDENCE      NUMERIC(4,3)    NULL DEFAULT 1.000,
    VERIFIED_YN     CHAR(1)         NULL DEFAULT 'N',
    INCDNT_NO       VARCHAR(20)     NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_IMPRSN_REL_PK PRIMARY KEY (IMPRSN_SN)
);
COMMENT ON TABLE  TB_IMPRSN_REL IS '사칭 관계 (impersonates 엣지 대응). 전기통신금융사기법 제3조 근거. ⚠ ETL 구현 완료 (rdb_to_graph_service.py)';
COMMENT ON COLUMN TB_IMPRSN_REL.SRC_ENTTY_TYP IS 'TELNO=전화번호(→TB_TELNO_MST), DGTL_ID=디지털계정(→TB_DGTL_ID_MST), EMAIL=이메일(→TB_EMAIL_MST)';
CREATE INDEX IDX_IMPRSN_SRC_ENTTY ON TB_IMPRSN_REL (SRC_ENTTY_TYP, SRC_ENTTY_KEY);
CREATE INDEX IDX_IMPRSN_TGT_INST  ON TB_IMPRSN_REL (TGT_INST_ID);
CREATE INDEX IDX_IMPRSN_INCDNT_NO ON TB_IMPRSN_REL (INCDNT_NO);


-- ============================================================
-- §16 수사지원   : 3개  (TB_INVEST_SESSION, TB_INVEST_NOTE, TB_AUDIT_LOG)
-- ============================================================

-- 수사 세션 (LangGraph run() 단위 세션 추적)
CREATE TABLE IF NOT EXISTS TB_INVEST_SESSION (
    SESSION_ID      VARCHAR(64)     PRIMARY KEY,                     -- UUID
    INCDNT_NO       VARCHAR(30)     REFERENCES TB_INCDNT_MST(INCDNT_NO) ON DELETE SET NULL,
    GRAPH_PATH      VARCHAR(100)    NOT NULL,                        -- AgensGraph 그래프명
    INVEST_SN       VARCHAR(20),                                     -- 수사관 번호 (TB_PRSN.PRSN_ID)
    STATUS_CD       VARCHAR(20)     NOT NULL DEFAULT 'OPEN',         -- OPEN/IN_PROGRESS/CLOSED (TB_CMN_CD.CMN_CD)
    QUESTION_CN     TEXT,                                            -- 최초 질문 원문
    ENTITY_CTX      JSONB,                                           -- InvestigationSession.entity_context 스냅샷
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPDATED_AT      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IDX_INVEST_SESSION_INCDNT ON TB_INVEST_SESSION (INCDNT_NO);
CREATE INDEX IDX_INVEST_SESSION_STATUS ON TB_INVEST_SESSION (STATUS_CD);

-- 수사 메모 (수사관 자유 메모, 세션·사건 연동)
CREATE TABLE IF NOT EXISTS TB_INVEST_NOTE (
    NOTE_ID         SERIAL          PRIMARY KEY,
    SESSION_ID      VARCHAR(64)     REFERENCES TB_INVEST_SESSION(SESSION_ID) ON DELETE CASCADE,
    INCDNT_NO       VARCHAR(30)     REFERENCES TB_INCDNT_MST(INCDNT_NO) ON DELETE SET NULL,
    INVEST_SN       VARCHAR(20),
    NOTE_CN         TEXT            NOT NULL,                        -- 메모 본문
    EVID_GRADE_CD   CHAR(1),                                         -- A/B/C (TB_CMN_CD.CMN_CD)
    REF_NODE_ID     VARCHAR(200),                                    -- 참조 그래프 노드 ID
    REF_TABLE_NM    VARCHAR(100),                                    -- 참조 RDB 테이블명
    REF_PK_VAL      VARCHAR(200),                                    -- 참조 RDB PK 값
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IDX_INVEST_NOTE_SESSION ON TB_INVEST_NOTE (SESSION_ID);
CREATE INDEX IDX_INVEST_NOTE_INCDNT  ON TB_INVEST_NOTE (INCDNT_NO);

-- 감사 로그 (API 호출·그래프 쿼리 이력)
CREATE TABLE IF NOT EXISTS TB_AUDIT_LOG (
    LOG_ID          BIGSERIAL       PRIMARY KEY,
    SESSION_ID      VARCHAR(64),
    INVEST_SN       VARCHAR(20),
    ACTION_CD       VARCHAR(50)     NOT NULL,                        -- QUERY/ETL/PATH/REPORT/LOGIN 등
    GRAPH_PATH      VARCHAR(100),
    CYPHER_CN       TEXT,                                            -- 실행된 Cypher 원문
    INPUT_CN        TEXT,                                            -- 사용자 입력 원문
    RESULT_STATUS   VARCHAR(20),                                     -- SUCCESS/FAIL/PARTIAL
    RESULT_CNT      INTEGER,                                         -- 결과 노드/엣지 수
    EXEC_MS         INTEGER,                                         -- 실행 소요 시간(ms)
    IP_ADDR         VARCHAR(45),
    CREATED_AT      TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IDX_AUDIT_LOG_SESSION   ON TB_AUDIT_LOG (SESSION_ID);
CREATE INDEX IDX_AUDIT_LOG_ACTION    ON TB_AUDIT_LOG (ACTION_CD);
CREATE INDEX IDX_AUDIT_LOG_CREATED   ON TB_AUDIT_LOG (CREATED_AT);

-- ============================================================
-- 공통코드 초기 데이터 (TB_CMN_CD)
-- ============================================================

-- 수사 세션 상태
INSERT INTO TB_CMN_CD (GRP_CD, CMN_CD, CMN_CD_NM, SORT_SQ, USE_YN) VALUES
    ('INVEST_STATUS', 'OPEN',        '수사중',         1, 'Y'),
    ('INVEST_STATUS', 'IN_PROGRESS', '진행중',         2, 'Y'),
    ('INVEST_STATUS', 'CLOSED',      '종결',           3, 'Y'),
    ('INVEST_STATUS', 'SUSPENDED',   '중단',           4, 'Y')
ON CONFLICT (GRP_CD, CMN_CD) DO NOTHING;

-- 증거 등급
INSERT INTO TB_CMN_CD (GRP_CD, CMN_CD, CMN_CD_NM, SORT_SQ, USE_YN) VALUES
    ('EVID_GRADE', 'A', '공식증거(KICS 원자료)',   1, 'Y'),
    ('EVID_GRADE', 'B', '간접증거(명의조인 추론)', 2, 'Y'),
    ('EVID_GRADE', 'C', '추정(OSINT/이름매칭)',    3, 'Y')
ON CONFLICT (GRP_CD, CMN_CD) DO NOTHING;

-- 감사 액션
INSERT INTO TB_CMN_CD (GRP_CD, CMN_CD, CMN_CD_NM, SORT_SQ, USE_YN) VALUES
    ('AUDIT_ACTION', 'QUERY',  '그래프 조회',    1, 'Y'),
    ('AUDIT_ACTION', 'PATH',   '경로 탐색',      2, 'Y'),
    ('AUDIT_ACTION', 'REPORT', '보고서 생성',    3, 'Y'),
    ('AUDIT_ACTION', 'ETL',    'RDB→Graph ETL',  4, 'Y'),
    ('AUDIT_ACTION', 'LOGIN',  '로그인',         5, 'Y')
ON CONFLICT (GRP_CD, CMN_CD) DO NOTHING;

-- ============================================================
-- END OF DDL
-- 총 52개 테이블 (49 + 3 수사지원)
-- §0  공통코드   : 2개  (TB_CMN_CD, TB_BANK_CD)
-- §1  소스/메타  : 3개  (TB_DATA_SRC, TB_DATA_INGEST_LOG, TB_DATA_QUALITY_LOG)
-- §2  사건/관리  : 2개  (TB_INCDNT_MST, TB_INCDNT_PRSN_REL)
-- §3  진정서     : 3개  (TB_PETTN_MST, TB_PETTN_CLSTR, TB_PETTN_PROC_LOG)
-- §4  사람/주체  : 2개  (TB_PRSN, TB_INST)
-- §5  금융       : 2개  (TB_FIN_BACNT, TB_FIN_BACNT_DLNG)
-- §6  통신       : 5개  (TB_TELNO_MST, TB_TELNO_CALL_DTL, TB_TELNO_SMS_MSG, TB_TELNO_JOIN, TB_CHAT_MSG)
-- §7  차량/이동  : 2개  (TB_VHCL_MST, TB_VHCL_LPR_EVT)
-- §8  위치/지리  : 2개  (TB_GEO_MBL_LOC_EVT, TB_GEO_TRST_CARD_TRIP)
-- §9  디지털     : 4개  (TB_WEB_DMN, TB_WEB_MLGN_IDC, TB_SYS_LGN_EVT, TB_DGTL_FILE_INVNT)
-- §10 OSINT      : 7개  (TB_OSINT_IP/DMN/HASH/PHON/ACNT/WALLET/ID_REP)
-- §11 마약       : 2개  (TB_DRUG_SLANG, TB_DRUG_TRDE)
-- §12 사기신고   : 2개  (TB_FRD_VCTM_RPT, TB_FRD_ACNT_BLK)
-- §13 엔티티해소 : 2개  (TB_ENTITY_SAME_AS, TB_ENTITY_CONFLICT)
-- §14 Phase 6G   : 6개  (TB_DGTL_ID_MST, TB_EMAIL_MST, TB_CRYPTO_WALLET_MST, TB_DEV_MST, TB_ATM_MST, TB_LOC_MST)
-- §15 사칭관계   : 1개  (TB_IMPRSN_REL)
-- §16 수사지원   : 3개  (TB_INVEST_SESSION, TB_INVEST_NOTE, TB_AUDIT_LOG)
-- ============================================================
