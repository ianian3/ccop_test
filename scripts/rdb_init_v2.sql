-- CCOP RDB v2 스키마 초기화 스크립트 (2026-02-23)
-- 기반: RDB_DATA_STANDARDIZATION_v2.md

-- A. 사건/관리 도메인 (Case & Control)
CREATE TABLE IF NOT EXISTS TB_INCDNT_MST (
    INCDNT_NO       VARCHAR(20)     NOT NULL, -- 사건번호
    INCDNT_NM       VARCHAR(300)    NOT NULL, -- 사건명
    INCDNT_TYP_CD   VARCHAR(6)      NULL,     -- 사건유형코드
    OCCRN_DT        TIMESTAMP       NULL,     -- 발생일시
    END_DT          TIMESTAMP       NULL,     -- 종료일시
    CHRGDP_NM       VARCHAR(100)    NULL,     -- 담당부서명
    CHRG_PLCMN_NM   VARCHAR(100)    NULL,     -- 담당경찰관명
    INCDNT_SMRY_CN  TEXT            NULL,     -- 사건개요내용
    REG_DT          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP, -- 등록일시
    CONSTRAINT TB_INCDNT_MST_PK PRIMARY KEY (INCDNT_NO)
);

-- B. 사람/주체 도메인 (Actor)
CREATE TABLE IF NOT EXISTS TB_PRSN (
    PRSN_ID         VARCHAR(20)     NOT NULL, -- 사람ID (내부식별자)
    KORN_FLNM       VARCHAR(150)    NULL,     -- 한글성명
    RRNO            CHAR(13)        NULL,     -- 주민등록번호 (암호화 필요)
    PRSN_SE_CD      VARCHAR(4)      NULL,     -- 사람구분코드 (피해자/피의자 등)
    RMK_CN          VARCHAR(4000)   NULL,     -- 비고내용
    REG_DT          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_PRSN_PK PRIMARY KEY (PRSN_ID)
);

CREATE TABLE IF NOT EXISTS TB_INST (
    INST_ID         VARCHAR(20)     NOT NULL, -- 기관ID
    INST_NM         VARCHAR(200)    NOT NULL, -- 기관명
    INST_SE_CD      VARCHAR(4)      NULL,     -- 기관구분코드 (은행/통신사/플랫폼)
    BRNO            VARCHAR(10)     NULL,     -- 사업자등록번호
    ADDR            VARCHAR(200)    NULL,     -- 주소
    CONSTRAINT TB_INST_PK PRIMARY KEY (INST_ID)
);

-- C. 금융 도메인 (Finance)
CREATE TABLE IF NOT EXISTS TB_FIN_BACNT (
    BACNT_NO        VARCHAR(20)     NOT NULL, -- 계좌번호
    BANK_CD         VARCHAR(10)     NOT NULL, -- 은행코드
    BANK_NM         VARCHAR(100)    NULL,     -- 은행명
    DPSTR_NM        VARCHAR(100)    NULL,     -- 예금주명
    BACNT_OPN_DT    CHAR(8)         NULL,     -- 계좌개설일자
    INST_ID         VARCHAR(20)     NULL,     -- 기관ID (FK)
    CONSTRAINT TB_FIN_BACNT_PK PRIMARY KEY (BACNT_NO, BANK_CD)
);

CREATE TABLE IF NOT EXISTS TB_FIN_BACNT_DLNG (
    DLNG_SN         NUMERIC(22)     NOT NULL, -- 거래일련번호
    BACNT_NO        VARCHAR(20)     NOT NULL, -- 계좌번호
    BANK_CD         VARCHAR(10)     NOT NULL, -- 은행코드
    DLNG_DT         TIMESTAMP       NOT NULL, -- 거래일시
    DLNG_SE_CD      VARCHAR(4)      NULL,     -- 거래구분코드 (입금/출금/이체)
    DLNG_AMT        NUMERIC(15)     DEFAULT 0,-- 거래금액
    BLNC_AMT        NUMERIC(15)     DEFAULT 0,-- 잔액금액
    TRRC_PSNNM      VARCHAR(100)    NULL,     -- 송수신자명
    TRRC_BACNT_NO   VARCHAR(20)     NULL,     -- 송수신계좌번호
    DLNG_MEMO_CN    VARCHAR(200)    NULL,     -- 거래메모내용
    ATM_MNG_NO      VARCHAR(20)     NULL,     -- ATM관리번호
    CONSTRAINT TB_FIN_BACNT_DLNG_PK PRIMARY KEY (DLNG_SN)
);

CREATE TABLE IF NOT EXISTS TB_FIN_EXTRC_BACNT (
    EXTRC_SN        NUMERIC(22)     NOT NULL, -- 추출일련번호
    SRC_DATA_ID     VARCHAR(50)     NOT NULL, -- 원본데이터ID (카톡/문자 ID)
    EXTRC_BACNT_NO  VARCHAR(20)     NULL,     -- 추출계좌번호
    EXTRC_BANK_NM   VARCHAR(100)    NULL,     -- 추출은행명
    EXTRC_DPSTR_NM  VARCHAR(100)    NULL,     -- 추출예금주명
    EXTRC_DT        TIMESTAMP       DEFAULT CURRENT_TIMESTAMP, -- 추출일시
    CNF_YN          CHAR(1)         DEFAULT 'N', -- 확인여부
    CONSTRAINT TB_FIN_EXTRC_BACNT_PK PRIMARY KEY (EXTRC_SN)
);

-- D. 통신 도메인 (Telecommunication)
CREATE TABLE IF NOT EXISTS TB_TELNO_MST (
    TELNO           VARCHAR(20)     NOT NULL, -- 전화번호
    TELCO_NM        VARCHAR(50)     NULL,     -- 통신사명
    JOIN_TYP_CD     VARCHAR(4)      NULL,     -- 가입유형코드 (개인/법인)
    REG_DT          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_TELNO_MST_PK PRIMARY KEY (TELNO)
);

CREATE TABLE IF NOT EXISTS TB_TELNO_JOIN (
    JOIN_SN         NUMERIC(22)     NOT NULL, -- 가입일련번호
    TELNO           VARCHAR(20)     NOT NULL, -- 전화번호
    JOIN_PSNNM      VARCHAR(100)    NULL,     -- 가입자명
    JOIN_YMD        CHAR(8)         NULL,     -- 가입일자
    CNCLTN_YMD      CHAR(8)         NULL,     -- 해지일자
    INST_ADDR       VARCHAR(200)    NULL,     -- 설치주소
    CONSTRAINT TB_TELNO_JOIN_PK PRIMARY KEY (JOIN_SN)
);

CREATE TABLE IF NOT EXISTS TB_TELNO_CALL_DTL (
    CALL_SN         NUMERIC(22)     NOT NULL, -- 통화내역일련번호
    DSPTCH_TELNO    VARCHAR(20)     NOT NULL, -- 발신전화번호
    RCPTN_TELNO     VARCHAR(20)     NOT NULL, -- 수신전화번호
    CALL_STRT_DT    TIMESTAMP       NOT NULL, -- 통화시작일시
    CALL_DUR_SEC    NUMERIC(10)     NULL,     -- 통화지속시간(초)
    BSST_NM         VARCHAR(100)    NULL,     -- 기지국명
    BSST_ADDR       VARCHAR(200)    NULL,     -- 기지국주소
    CALL_TYP_CD     VARCHAR(4)      NULL,     -- 통화유형코드 (음성/데이터)
    CONSTRAINT TB_TELNO_CALL_DTL_PK PRIMARY KEY (CALL_SN)
);

CREATE TABLE IF NOT EXISTS TB_TELNO_SMS_MSG (
    SMS_SN          NUMERIC(22)     NOT NULL, -- 문자일련번호
    DSPTCH_TELNO    VARCHAR(20)     NOT NULL, -- 발신전화번호
    RCPTN_TELNO     VARCHAR(20)     NOT NULL, -- 수신전화번호
    DSPTCH_DT       TIMESTAMP       NOT NULL, -- 발신일시
    MSG_CN          VARCHAR(4000)   NULL,     -- 문자내용
    SPAM_YN         CHAR(1)         DEFAULT 'N', -- 스팸여부
    CONSTRAINT TB_TELNO_SMS_MSG_PK PRIMARY KEY (SMS_SN)
);

CREATE TABLE IF NOT EXISTS TB_CHAT_MSG (
    CHAT_SN         NUMERIC(22)     NOT NULL, -- 대화일련번호
    ROOM_ID         VARCHAR(50)     NULL,     -- 채팅방ID
    DSPTCH_USER_ID  VARCHAR(50)     NULL,     -- 발신사용자ID
    MSG_CN          TEXT            NULL,     -- 메시지내용
    DSPTCH_DT       TIMESTAMP       NOT NULL, -- 발신일시
    APP_NM          VARCHAR(50)     NULL,     -- 앱명 (카카오톡/텔레그램)
    CONSTRAINT TB_CHAT_MSG_PK PRIMARY KEY (CHAT_SN)
);

-- E. 위치/이동 도메인 (Location & Movement)
CREATE TABLE IF NOT EXISTS TB_GEO_MBL_LOC_EVT (
    LOC_EVT_SN      NUMERIC(22)     NOT NULL, -- 위치이벤트일련번호
    TELNO           VARCHAR(20)     NOT NULL, -- 전화번호
    BSST_LAT        NUMERIC(12,10)  NULL,     -- 기지국위도
    BSST_LOT        NUMERIC(13,10)  NULL,     -- 기지국경도
    OCCRN_DT        TIMESTAMP       NOT NULL, -- 발생일시
    EVT_TYP_NM      VARCHAR(50)     NULL,     -- 이벤트유형명 (발신/착신/위치등록)
    CONSTRAINT TB_GEO_MBL_LOC_EVT_PK PRIMARY KEY (LOC_EVT_SN)
);

CREATE TABLE IF NOT EXISTS TB_GEO_TRST_CARD_TRIP (
    MV_SN           NUMERIC(22)     NOT NULL, -- 이동일련번호
    TRST_CARD_NO    VARCHAR(20)     NOT NULL, -- 카드번호
    TK_PLC_NM       VARCHAR(100)    NULL,     -- 승차장소명
    TK_DT           TIMESTAMP       NULL,     -- 승차일시
    GF_PLC_NM       VARCHAR(100)    NULL,     -- 하차장소명
    GF_DT           TIMESTAMP       NULL,     -- 하차일시
    VHCLNO          VARCHAR(20)     NULL,     -- 차량번호 (버스/택시)
    RT_NM           VARCHAR(50)     NULL,     -- 노선명
    CONSTRAINT TB_GEO_TRST_CARD_TRIP_PK PRIMARY KEY (MV_SN)
);

-- F. 차량 도메인 (Vehicle)
CREATE TABLE IF NOT EXISTS TB_VHCL_MST (
    VHCLNO          VARCHAR(20)     NOT NULL, -- 차량번호
    CARMDL_NM       VARCHAR(50)     NULL,     -- 차종명
    CARMDL_DTL_NM   VARCHAR(100)    NULL,     -- 차명(모델명)
    OWNR_NM         VARCHAR(100)    NULL,     -- 소유자명
    CONSTRAINT TB_VHCL_MST_PK PRIMARY KEY (VHCLNO)
);

CREATE TABLE IF NOT EXISTS TB_VHCL_LPR_EVT (
    RCGN_SN         NUMERIC(22)     NOT NULL, -- 인식일련번호
    VHCLNO          VARCHAR(20)     NOT NULL, -- 차량번호
    CCTV_ID         VARCHAR(20)     NULL,     -- CCTV ID
    INST_LOC_NM     VARCHAR(100)    NULL,     -- 설치장소명
    RCGN_DT         TIMESTAMP       NOT NULL, -- 인식일시
    LAT             NUMERIC(12,10)  NULL,     -- 위도
    LOT             NUMERIC(13,10)  NULL,     -- 경도
    CONSTRAINT TB_VHCL_LPR_EVT_PK PRIMARY KEY (RCGN_SN)
);

CREATE TABLE IF NOT EXISTS TB_VHCL_TOLL_EVT (
    TOLL_SN         NUMERIC(22)     NOT NULL, -- 톨게이트일련번호
    VHCLNO          VARCHAR(20)     NOT NULL, -- 차량번호
    ENTR_TOLGT_NM   VARCHAR(100)    NULL,     -- 진입영업소명
    ENTR_DT         TIMESTAMP       NULL,     -- 진입일시
    EXIT_TOLGT_NM   VARCHAR(100)    NULL,     -- 진출영업소명
    EXIT_DT         TIMESTAMP       NULL,     -- 진출일시
    CONSTRAINT TB_VHCL_TOLL_EVT_PK PRIMARY KEY (TOLL_SN)
);

-- G. 웹/디지털 도메인 (Web & Digital)
CREATE TABLE IF NOT EXISTS TB_WEB_DMN (
    DMN_ADDR        VARCHAR(200)    NOT NULL, -- 도메인주소
    IP_ADDR         VARCHAR(15)     NULL,     -- IP주소
    REG_DT          TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_WEB_DMN_PK PRIMARY KEY (DMN_ADDR)
);

CREATE TABLE IF NOT EXISTS TB_WEB_URL (
    URL_ADDR        VARCHAR(2000)   NOT NULL, -- URL주소
    DMN_ADDR        VARCHAR(200)    NOT NULL, -- 도메인주소 (FK 준비)
    URL_DESC_CN     VARCHAR(4000)   NULL,     -- URL설명내용
    CONSTRAINT TB_WEB_URL_PK PRIMARY KEY (URL_ADDR)
);

CREATE TABLE IF NOT EXISTS TB_WEB_PAGE (
    PAGE_SN         NUMERIC(22)     NOT NULL, -- 페이지일련번호
    URL_ADDR        VARCHAR(2000)   NOT NULL, -- URL주소
    PAGE_TITLE      VARCHAR(256)    NULL,     -- 페이지제목
    HTML_CN         TEXT            NULL,     -- HTML내용
    HASH_VAL        VARCHAR(64)     NULL,     -- 해시값
    CLCT_DT         TIMESTAMP       NULL,     -- 수집일시
    CONSTRAINT TB_WEB_PAGE_PK PRIMARY KEY (PAGE_SN)
);

CREATE TABLE IF NOT EXISTS TB_WEB_ATCH (
    AHFL_SN         NUMERIC(22)     NOT NULL, -- 첨부일련번호
    PAGE_SN         NUMERIC(22)     NOT NULL, -- 페이지일련번호 (FK 준비)
    FILE_NM         VARCHAR(300)    NULL,     -- 파일명
    FILE_SZ         NUMERIC(15)     NULL,     -- 파일크기
    HASH_VAL        VARCHAR(64)     NULL,     -- 해시값
    CONSTRAINT TB_WEB_ATCH_PK PRIMARY KEY (AHFL_SN)
);

CREATE TABLE IF NOT EXISTS TB_WEB_MLGN_IDC (
    INDCTR_SN       NUMERIC(22)     NOT NULL, -- 지표일련번호
    MLGN_URL_ADDR   VARCHAR(2000)   NULL,     -- 악성URL주소
    SIGN_KWRD       VARCHAR(100)    NULL,     -- 시그니처키워드
    DETCT_DT        TIMESTAMP       DEFAULT CURRENT_TIMESTAMP, -- 탐지일시
    RISK_GRD        VARCHAR(10)     NULL,     -- 위험등급
    CONSTRAINT TB_WEB_MLGN_IDC_PK PRIMARY KEY (INDCTR_SN)
);

-- H. 범죄 특화 도메인 (Crime Specific)
CREATE TABLE IF NOT EXISTS TB_FRD_VCTM_RPT (
    DCLR_SN         NUMERIC(22)     NOT NULL, -- 신고일련번호
    DAM_AMT         NUMERIC(15)     DEFAULT 0,-- 피해금액
    DCLR_DT         TIMESTAMP       NOT NULL, -- 신고일시
    SUSPCT_TELNO    VARCHAR(20)     NULL,     -- 용의전화번호
    SUSPCT_BACNT_NO VARCHAR(20)     NULL,     -- 용의계좌번호
    DAM_CN          TEXT            NULL,     -- 피해내용
    CONSTRAINT TB_FRD_VCTM_RPT_PK PRIMARY KEY (DCLR_SN)
);

CREATE TABLE IF NOT EXISTS TB_DRUG_CLUE (
    CLUE_SN         NUMERIC(22)     NOT NULL, -- 단서일련번호
    CLUE_TY_NM      VARCHAR(50)     NULL,     -- 단서유형명 (거래/투약/광고)
    DTCT_KWD        VARCHAR(100)    NULL,     -- 탐지키워드
    REL_DATA_ID     VARCHAR(50)     NULL,     -- 관련데이터ID (URL/메시지 등)
    CONSTRAINT TB_DRUG_CLUE_PK PRIMARY KEY (CLUE_SN)
);

CREATE TABLE IF NOT EXISTS TB_DRUG_SLANG (
    SLANG_ID        VARCHAR(20)     NOT NULL, -- 은어ID
    SLANG_NM        VARCHAR(100)    NOT NULL, -- 은어명
    REAL_MEAN_NM    VARCHAR(100)    NULL,     -- 실제의미명 (필로폰/대마 등)
    USE_EX_CN       VARCHAR(4000)   NULL,     -- 사용예시내용
    CONSTRAINT TB_DRUG_SLANG_PK PRIMARY KEY (SLANG_ID)
);

-- I. 시스템/증거 도메인 (System & Evidence)
CREATE TABLE IF NOT EXISTS TB_SYS_LGN_EVT (
    LGN_EVT_SN      NUMERIC(22)     NOT NULL, -- 로그인이벤트일련번호
    USER_ID         VARCHAR(20)     NOT NULL, -- 사용자ID
    CNNT_IP_ADDR    VARCHAR(15)     NOT NULL, -- 접속IP주소
    LGN_DT          TIMESTAMP       NOT NULL, -- 로그인일시
    LGN_RESULT_CD   CHAR(1)         NULL,     -- 로그인결과코드 (S/F)
    CONSTRAINT TB_SYS_LGN_EVT_PK PRIMARY KEY (LGN_EVT_SN)
);

CREATE TABLE IF NOT EXISTS TB_EML_TRNS_EVT (
    EML_TRNS_SN     NUMERIC(22)     NOT NULL, -- 이메일전송일련번호
    DSPTCH_EML_ADDR VARCHAR(200)    NOT NULL, -- 발신이메일주소
    RCPTN_EML_ADDR  VARCHAR(200)    NOT NULL, -- 수신이메일주소
    EML_TITLE       VARCHAR(256)    NULL,     -- 이메일제목
    DSPTCH_DT       TIMESTAMP       NOT NULL, -- 발신일시
    EML_PURP_CN     VARCHAR(1000)   NULL,     -- 이메일목적내용
    CONSTRAINT TB_EML_TRNS_EVT_PK PRIMARY KEY (EML_TRNS_SN)
);

CREATE TABLE IF NOT EXISTS TB_DGTL_FILE_INVNT (
    FILE_SN         NUMERIC(22)     NOT NULL, -- 파일일련번호
    FILE_NM         VARCHAR(300)    NOT NULL, -- 파일명
    FILE_EXTSN_NM   VARCHAR(10)     NULL,     -- 파일확장자명
    FILE_SZ         NUMERIC(15)     NULL,     -- 파일크기
    HASH_VAL        VARCHAR(64)     NOT NULL, -- 해시값 (무결성 검증)
    CREAT_DT        TIMESTAMP       NULL,     -- 생성일시
    MDFR_DT         TIMESTAMP       NULL,     -- 수정일시
    CONSTRAINT TB_DGTL_FILE_INVNT_PK PRIMARY KEY (FILE_SN)
);

-- Constraints
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'tb_web_url_fk1'
    ) THEN
        ALTER TABLE TB_WEB_URL 
        ADD CONSTRAINT tb_web_url_fk1 FOREIGN KEY (DMN_ADDR) 
        REFERENCES TB_WEB_DMN (DMN_ADDR);
    END IF;
END $$;
