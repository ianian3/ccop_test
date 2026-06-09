-- =====================================================================
-- DA팀 V3.7 표준 DDL → CCOP V4.0 호환화 패치 SQL
-- =====================================================================
-- 발신     : 데이터팀 (CCOP V4.0 온톨로지 설계)
-- 대상     : CYBERCOP_STANDARD_TABLE_DDL_20260518.sql 적용 환경
-- 작성일   : 2026-05-21
-- 동반문서 : docs/DA_TEAM_V40_REQUEST_20260521.md
-- =====================================================================
-- 적용 순서:
--   §1. DDL 버그 수정 6건 (B1~B6)
--   §2. 누락 테이블 3종 신규 생성 (vt_file, site_cluster, pt_cluster)
--   §3. V4.0 공통 메타 6 컬럼 일괄 부착
--   §4. V3.7 신규 속성 3건 (IS_ANONYMOUS x2, DEV_TYPE 확장)
--   §5. TB_CMN_CD 공통코드 4그룹 (ID_FORMAT, DOMAIN, RLBLT_TIER, DEV_TYPE)
--   §6. 검증 쿼리
-- =====================================================================
-- ⚠️ 운영 적용 전 반드시 백업 후 트랜잭션 단위 실행 권장.
-- =====================================================================

BEGIN;

-- =====================================================================
-- §1. DDL 버그 수정 6건
-- =====================================================================

-- B1. TB_SYS_LGN_EVT 중복 정의 → 마스터 DDL 직접 수정 필요 (SQL 패치 불가)
--     => DA팀 마스터 DDL 3.9.4절 중복 블록 1개 삭제 후 재배포 요청.

-- B2. TB_BANK_CD PK 컬럼명 오타 (BNAK_CD → BANK_CD)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='tb_bank_cd' AND column_name='bnak_cd') THEN
    EXECUTE 'ALTER TABLE TB_BANK_CD RENAME COLUMN BNAK_CD TO BANK_CD';
  END IF;
END $$;

-- B3. TB_EML_ADDR PK 컬럼명 통일 (EML_ADDR_ID ↔ EML_ADDR 혼용)
--     본문에서 EML_ADDR로 참조되므로 EML_ADDR_ID → EML_ADDR 통일
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.columns
             WHERE table_name='tb_eml_addr' AND column_name='eml_addr_id') THEN
    EXECUTE 'ALTER TABLE TB_EML_ADDR RENAME COLUMN EML_ADDR_ID TO EML_ADDR';
  END IF;
END $$;

-- B4. 누락 시퀀스 일괄 생성 (대표 누락 사례)
CREATE SEQUENCE IF NOT EXISTS SEQ_TB_DGTL_FILE START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE IF NOT EXISTS SEQ_TB_SITE_CLST_MST START WITH 1 INCREMENT BY 1;
CREATE SEQUENCE IF NOT EXISTS SEQ_TB_PT_CLST_MST START WITH 1 INCREMENT BY 1;

-- B5. RLBLT_TIER DEFAULT 5 → 3 (T3 시민제보 기본)
--     §3에서 ALTER 시 일괄 적용. 기존 테이블 DEFAULT 보정만 여기서 실행.
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT table_name FROM information_schema.columns
    WHERE column_name='rlblt_tier' AND column_default LIKE '%5%'
  LOOP
    EXECUTE format('ALTER TABLE %I ALTER COLUMN RLBLT_TIER SET DEFAULT 3', r.table_name);
  END LOOP;
END $$;

-- B6. CNTCT → CONTACT 코멘트 통일은 마스터 DDL 코멘트 수정으로 위임.

-- =====================================================================
-- §2. 누락 테이블 3종 신규 생성
-- =====================================================================

-- §2.1 TB_DGTL_FILE (vt_file)
CREATE TABLE IF NOT EXISTS TB_DGTL_FILE (
    FILE_ID            VARCHAR(64)   PRIMARY KEY,
    FILE_HASH_SHA256   CHAR(64)      NOT NULL,
    FILE_HASH_MD5      CHAR(32),
    FILE_NM            VARCHAR(256),
    FILE_SIZE_BYTES    BIGINT,
    MIME_TYPE          VARCHAR(128),
    EVDC_ID            VARCHAR(64),
    SOURCE_ID          VARCHAR(64),
    SOURCE_DOMAIN      VARCHAR(20)   DEFAULT 'DIGITAL',
    RLBLT_TIER         SMALLINT      DEFAULT 3,
    COLLECTED_AT       TIMESTAMP,
    REC_CREATED        TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED        TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_TB_DGTL_FILE_HASH ON TB_DGTL_FILE (FILE_HASH_SHA256);
CREATE INDEX IF NOT EXISTS IX_TB_DGTL_FILE_EVDC ON TB_DGTL_FILE (EVDC_ID);
COMMENT ON TABLE TB_DGTL_FILE IS '디지털 증거 파일 마스터 (V4.0 vt_file 매핑)';

-- §2.2 TB_SITE_CLST_MST (site_cluster)
CREATE TABLE IF NOT EXISTS TB_SITE_CLST_MST (
    CLST_ID            VARCHAR(64)   PRIMARY KEY,
    CLST_NM            VARCHAR(256),
    SIMHASH64          BIGINT        NOT NULL,
    MEMBER_CNT         INTEGER       DEFAULT 0,
    REPRESENTATIVE_URL VARCHAR(2048),
    SOURCE_ID          VARCHAR(64),
    SOURCE_DOMAIN      VARCHAR(20)   DEFAULT 'OSINT',
    RLBLT_TIER         SMALLINT      DEFAULT 4,
    COLLECTED_AT       TIMESTAMP,
    REC_CREATED        TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED        TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS IX_TB_SITE_CLST_SIMHASH ON TB_SITE_CLST_MST (SIMHASH64);
COMMENT ON TABLE TB_SITE_CLST_MST IS 'OSINT 사이트 자동 군집 (SimHash 64bit + Union-Find)';

-- §2.3 TB_PT_CLST_MST (pt_cluster)
CREATE TABLE IF NOT EXISTS TB_PT_CLST_MST (
    CLST_ID            VARCHAR(64)   PRIMARY KEY,
    CAMPAIGN_NM        VARCHAR(256),
    THREAT_LEVEL       SMALLINT,
    START_DT           DATE,
    END_DT             DATE,
    MEMBER_CNT         INTEGER       DEFAULT 0,
    SOURCE_ID          VARCHAR(64),
    SOURCE_DOMAIN      VARCHAR(20)   DEFAULT 'KICS',
    RLBLT_TIER         SMALLINT      DEFAULT 2,
    COLLECTED_AT       TIMESTAMP,
    REC_CREATED        TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED        TIMESTAMP     DEFAULT CURRENT_TIMESTAMP
);
COMMENT ON TABLE TB_PT_CLST_MST IS '범죄 캠페인/조직 클러스터 마스터 (V4.0 pt_cluster)';

-- =====================================================================
-- §3. V4.0 공통 메타 6 컬럼 전면 부착 (마스터 테이블 48개 대상)
-- =====================================================================
-- 적용 대상: TB_*_MST, TB_*_INFO, TB_*_EVT
-- =====================================================================
DO $$
DECLARE r RECORD;
BEGIN
  FOR r IN
    SELECT t.table_name
    FROM information_schema.tables t
    WHERE t.table_schema = current_schema()
      AND t.table_type = 'BASE TABLE'
      AND (t.table_name LIKE 'tb\_%\_mst'  ESCAPE '\'
        OR t.table_name LIKE 'tb\_%\_info' ESCAPE '\'
        OR t.table_name LIKE 'tb\_%\_evt'  ESCAPE '\')
  LOOP
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS SOURCE_ID     VARCHAR(64)', r.table_name);
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS SOURCE_DOMAIN VARCHAR(20)', r.table_name);
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS RLBLT_TIER    SMALLINT DEFAULT 3', r.table_name);
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS COLLECTED_AT  TIMESTAMP', r.table_name);
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS REC_CREATED   TIMESTAMP DEFAULT CURRENT_TIMESTAMP', r.table_name);
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS REC_UPDATED   TIMESTAMP DEFAULT CURRENT_TIMESTAMP', r.table_name);
  END LOOP;
END $$;

-- =====================================================================
-- §4. V3.7 신규 속성 3건
-- =====================================================================

-- §4.1 TB_PSN.IS_ANONYMOUS
ALTER TABLE TB_PSN ADD COLUMN IF NOT EXISTS IS_ANONYMOUS BOOLEAN DEFAULT FALSE;
COMMENT ON COLUMN TB_PSN.IS_ANONYMOUS IS '익명 인물(닉네임 only) 여부';

-- §4.2 TB_DGTL_ID_MST.IS_ANONYMOUS
ALTER TABLE TB_DGTL_ID_MST ADD COLUMN IF NOT EXISTS IS_ANONYMOUS BOOLEAN DEFAULT FALSE;
COMMENT ON COLUMN TB_DGTL_ID_MST.IS_ANONYMOUS IS '익명 ID 추론 플래그';

-- §4.3 TB_DEV_MST.DEV_TYPE enum 확장 ('relay_station' 추가)
--      DDL 측 CHECK 제약이 있다면 DROP 후 재생성 필요. 여기서는 TB_CMN_CD 참조 방식 가정.
--      DA팀이 CHECK 제약을 사용 중이라면 아래 주석 해제:
-- ALTER TABLE TB_DEV_MST DROP CONSTRAINT IF EXISTS CK_TB_DEV_MST_DEV_TYPE;
-- ALTER TABLE TB_DEV_MST ADD CONSTRAINT CK_TB_DEV_MST_DEV_TYPE
--   CHECK (DEV_TYPE IN ('phone','sim','imei','relay_station','modem','router'));

-- =====================================================================
-- §5. TB_CMN_CD 공통코드 4그룹 추가
-- =====================================================================
-- 가정 컬럼: (CD_GRP_ID, CD_ID, CD_NM, CD_DESC, USE_YN, SORT_ORDER)
-- DA팀 표준 컬럼명과 다른 경우 컬럼명만 치환 후 적용.
-- =====================================================================

-- §5.1 ID_FORMAT
INSERT INTO TB_CMN_CD (CD_GRP_ID, CD_ID, CD_NM, CD_DESC, USE_YN, SORT_ORDER) VALUES
  ('ID_FORMAT','email',         '이메일',          'RFC 5322 정규화',                 'Y', 10),
  ('ID_FORMAT','phone_e164',    '국제전화',        'E.164 (+82-10-…)',                'Y', 20),
  ('ID_FORMAT','account_hash',  '계좌해시',        'SHA256(BANK_CD || ACCT_NO)',      'Y', 30),
  ('ID_FORMAT','url_norm',      'URL정규화',       'scheme+host+path lowercase',      'Y', 40),
  ('ID_FORMAT','ip_v4',         'IPv4',           'dotted-decimal',                  'Y', 50),
  ('ID_FORMAT','ip_v6',         'IPv6',           'RFC 5952 권장 표기',              'Y', 60),
  ('ID_FORMAT','imei',          'IMEI',           '15자리 숫자',                     'Y', 70),
  ('ID_FORMAT','imsi',          'IMSI',           '15자리 숫자',                     'Y', 80),
  ('ID_FORMAT','bitcoin_addr',  '비트코인주소',    'Base58Check',                     'Y', 90)
ON CONFLICT (CD_GRP_ID, CD_ID) DO NOTHING;

-- §5.2 DOMAIN
INSERT INTO TB_CMN_CD (CD_GRP_ID, CD_ID, CD_NM, CD_DESC, USE_YN, SORT_ORDER) VALUES
  ('DOMAIN','KICS',    'KICS',     '경찰 형사사법시스템',          'Y', 10),
  ('DOMAIN','OSINT',   'OSINT',    '공개정보 수집',                'Y', 20),
  ('DOMAIN','DIGITAL', 'DIGITAL',  '디지털 포렌식',                'Y', 30),
  ('DOMAIN','EXT',     'EXT',      '외부기관 제공',                'Y', 40)
ON CONFLICT (CD_GRP_ID, CD_ID) DO NOTHING;

-- §5.3 RLBLT_TIER
INSERT INTO TB_CMN_CD (CD_GRP_ID, CD_ID, CD_NM, CD_DESC, USE_YN, SORT_ORDER) VALUES
  ('RLBLT_TIER','1','T1 공식',     '공식 기관/판결 수준',          'Y', 10),
  ('RLBLT_TIER','2','T2 수사',     '수사 진행 중 확인',            'Y', 20),
  ('RLBLT_TIER','3','T3 시민제보',  '시민 제보/신고 (기본값)',      'Y', 30),
  ('RLBLT_TIER','4','T4 웹수집',   'OSINT 자동 수집',              'Y', 40),
  ('RLBLT_TIER','5','T5 추정',     '추론/유추 결과',               'Y', 50)
ON CONFLICT (CD_GRP_ID, CD_ID) DO NOTHING;

-- §5.4 DEV_TYPE
INSERT INTO TB_CMN_CD (CD_GRP_ID, CD_ID, CD_NM, CD_DESC, USE_YN, SORT_ORDER) VALUES
  ('DEV_TYPE','phone',         '휴대폰',       '일반 휴대전화',                  'Y', 10),
  ('DEV_TYPE','sim',           'SIM',         'SIM 카드',                       'Y', 20),
  ('DEV_TYPE','imei',          'IMEI',        '단말기 식별번호',                 'Y', 30),
  ('DEV_TYPE','relay_station', '중계기',       'V3.7 신규 - 중계기/IMEI 분기',   'Y', 40),
  ('DEV_TYPE','modem',         '모뎀',         '유선/무선 모뎀',                  'Y', 50),
  ('DEV_TYPE','router',        '라우터',       '네트워크 라우터',                 'Y', 60)
ON CONFLICT (CD_GRP_ID, CD_ID) DO NOTHING;

COMMIT;

-- =====================================================================
-- §6. 검증 쿼리 (적용 후 수동 실행 권장)
-- =====================================================================

-- §6.1 누락 테이블 생성 확인
-- SELECT table_name FROM information_schema.tables
--  WHERE table_name IN ('tb_dgtl_file','tb_site_clst_mst','tb_pt_clst_mst');
-- ▷ 기대: 3 rows

-- §6.2 V4.0 메타 6 컬럼 충족률
-- SELECT table_name,
--        COUNT(*) FILTER (WHERE column_name IN
--          ('source_id','source_domain','rlblt_tier','collected_at','rec_created','rec_updated')) AS meta_cnt
--   FROM information_schema.columns
--  WHERE table_name LIKE 'tb\_%\_mst' ESCAPE '\'
--  GROUP BY table_name
--  HAVING COUNT(*) FILTER (WHERE column_name IN
--          ('source_id','source_domain','rlblt_tier','collected_at','rec_created','rec_updated')) < 6;
-- ▷ 기대: 0 rows (모든 마스터 테이블 6/6 충족)

-- §6.3 V3.7 신규 속성 확인
-- SELECT table_name, column_name FROM information_schema.columns
--  WHERE (table_name='tb_psn' AND column_name='is_anonymous')
--     OR (table_name='tb_dgtl_id_mst' AND column_name='is_anonymous');
-- ▷ 기대: 2 rows

-- §6.4 공통코드 4그룹 등록 확인
-- SELECT cd_grp_id, COUNT(*) FROM TB_CMN_CD
--  WHERE cd_grp_id IN ('ID_FORMAT','DOMAIN','RLBLT_TIER','DEV_TYPE')
--  GROUP BY cd_grp_id;
-- ▷ 기대: ID_FORMAT=9, DOMAIN=4, RLBLT_TIER=5, DEV_TYPE=6

-- =====================================================================
-- 종료. 적용 결과 데이터팀(ian.kwon@skaiworldwide.co.kr) 회신 요망.
-- =====================================================================
