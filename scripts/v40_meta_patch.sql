-- ============================================================
--  V4.0 메타 컬럼 일괄 추가 패치 (DA 팀 V3.7 DDL → V4.0 호환)
--  작성일: 2026-05-21
--  목적: DA 팀의 V3.7 DDL이 적용된 후 V4.0 표준 메타 6종을
--        모든 데이터 테이블에 일괄 추가
--
--  V4.0 표준 메타 6종:
--    - source_id          VARCHAR(64)  -- vt_src 참조
--    - source_domain      VARCHAR(16)  -- 'investigation' | 'osint' | 'partner' | 'inference'
--    - reliability_tier   SMALLINT     -- 1~4
--    - collected_at       TIMESTAMP    -- 외부 수집 시점
--    - rec_created        TIMESTAMP    -- DB 입력 시점
--    - rec_updated        TIMESTAMP    -- DB 수정 시점
--
--  사용:
--    1. DA 팀 V3.7 DDL 적용 완료 후 실행
--    2. 도메인별 default 값을 변수로 조정 후 실행
-- ============================================================

-- ──────────────────────────────────────────────────────────
-- §0. 변수 — 도메인 default 값 정의
-- ──────────────────────────────────────────────────────────

-- 도메인별 reliability_tier 기본값:
--   investigation = 1 (공식 수사)
--   partner       = 2 (협력기관)
--   inference     = 3 (추론)
--   osint         = 4 (OSINT)

-- ──────────────────────────────────────────────────────────
-- §1. CCOP 수사 도메인 테이블 (investigation, tier=1)
-- ──────────────────────────────────────────────────────────

-- 대상: TB_PRSN, TB_INST, TB_INCDNT_MST, TB_PETTN_MST, TB_FIN_BACNT,
--       TB_TELNO_MST, TB_VHCL_MST, TB_DEV_MST, TB_ATM_MST, TB_LOC_MST,
--       TB_ID_MST, TB_EMAIL_MST, TB_CRYPTO_MST 등

DO $$
DECLARE
    ccop_tables TEXT[] := ARRAY[
        'TB_PRSN', 'TB_INST', 'TB_INCDNT_MST', 'TB_PETTN_MST',
        'TB_FIN_BACNT', 'TB_FIN_BACNT_DLNG',
        'TB_TELNO_MST', 'TB_TELNO_CALL_DTL', 'TB_TELNO_SMS_MSG', 'TB_TELNO_JOIN',
        'TB_CHAT_MSG', 'TB_VHCL_MST',
        'TB_ID_MST', 'TB_EMAIL_MST', 'TB_CRYPTO_MST',
        'TB_DEV_MST', 'TB_ATM_MST', 'TB_LOC_MST',
        'TB_IMPRSN_REL'
    ];
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ccop_tables LOOP
        IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = LOWER(tbl)) THEN
            EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS source_id        VARCHAR(64)', tbl);
            EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS source_domain    VARCHAR(16) NOT NULL DEFAULT %L', tbl, 'investigation');
            EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS reliability_tier SMALLINT    NOT NULL DEFAULT 1', tbl);
            EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS collected_at     TIMESTAMP', tbl);
            EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS rec_created      TIMESTAMP NOT NULL DEFAULT NOW()', tbl);
            EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS rec_updated      TIMESTAMP NOT NULL DEFAULT NOW()', tbl);
            RAISE NOTICE '✅ %: V4.0 메타 6종 추가 완료', tbl;
        ELSE
            RAISE NOTICE '⚠️ %: 테이블 존재하지 않음 (skip)', tbl;
        END IF;
    END LOOP;
END$$;

-- ──────────────────────────────────────────────────────────
-- §2. OSINT 도메인 테이블 (osint, tier=4)
-- ──────────────────────────────────────────────────────────

DO $$
DECLARE
    osint_tables TEXT[] := ARRAY[
        'clct_page', 'atch_file', 'scrn_file', 'orgnl_html',
        'cmnty_dtl', 'sns_dtl', 'used_mkt_dtl', 'srch_engn_dtl',
        'chatrm', 'chat',
        'tb_the_cheat_fraud_m', 'tb_the_cheat_malicious_url_m', 'tb_the_cheat_spam_sms_m'
    ];
    tbl TEXT;
    osint_schema TEXT := 'test_ccop_cp';  -- DA 팀이 osint 스키마로 변경하면 'osint'
BEGIN
    FOREACH tbl IN ARRAY osint_tables LOOP
        IF EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = osint_schema AND table_name = LOWER(tbl)
        ) THEN
            EXECUTE format('ALTER TABLE %I.%I ADD COLUMN IF NOT EXISTS source_id        VARCHAR(64)', osint_schema, tbl);
            EXECUTE format('ALTER TABLE %I.%I ADD COLUMN IF NOT EXISTS source_domain    VARCHAR(16) NOT NULL DEFAULT %L', osint_schema, tbl, 'osint');
            EXECUTE format('ALTER TABLE %I.%I ADD COLUMN IF NOT EXISTS reliability_tier SMALLINT    NOT NULL DEFAULT 4', osint_schema, tbl);
            EXECUTE format('ALTER TABLE %I.%I ADD COLUMN IF NOT EXISTS collected_at     TIMESTAMP', osint_schema, tbl);
            EXECUTE format('ALTER TABLE %I.%I ADD COLUMN IF NOT EXISTS rec_created      TIMESTAMP NOT NULL DEFAULT NOW()', osint_schema, tbl);
            EXECUTE format('ALTER TABLE %I.%I ADD COLUMN IF NOT EXISTS rec_updated      TIMESTAMP NOT NULL DEFAULT NOW()', osint_schema, tbl);
            RAISE NOTICE '✅ %.%: V4.0 메타 6종 추가 완료', osint_schema, tbl;
        ELSE
            RAISE NOTICE '⚠️ %.%: 테이블 존재하지 않음 (skip)', osint_schema, tbl;
        END IF;
    END LOOP;
END$$;

-- ──────────────────────────────────────────────────────────
-- §3. 정규화 컬럼 (Generated Column) 추가
-- ──────────────────────────────────────────────────────────

-- URL 정규화 (osint.clct_page, osint.tb_the_cheat_malicious_url_m)
ALTER TABLE test_ccop_cp.clct_page
    ADD COLUMN IF NOT EXISTS url_norm TEXT
        GENERATED ALWAYS AS (public.normalize_url(url)) STORED;
CREATE INDEX IF NOT EXISTS ix_clct_page_url_norm ON test_ccop_cp.clct_page (url_norm);

-- 전화번호 정규화 (TB_TELNO_MST)
ALTER TABLE TB_TELNO_MST
    ADD COLUMN IF NOT EXISTS telno_norm VARCHAR(20)
        GENERATED ALWAYS AS (public.normalize_telno(telno)) STORED;
CREATE INDEX IF NOT EXISTS ix_tb_telno_norm ON TB_TELNO_MST (telno_norm);

-- 계좌번호 정규화 (TB_FIN_BACNT)
-- 이미 표준 형식 사용 가정 — 검증만
ALTER TABLE TB_FIN_BACNT
    ADD COLUMN IF NOT EXISTS account_no_norm VARCHAR(30)
        GENERATED ALWAYS AS (public.normalize_account(account_no)) STORED;
CREATE INDEX IF NOT EXISTS ix_tb_fin_bacnt_norm ON TB_FIN_BACNT (account_no_norm);

-- ──────────────────────────────────────────────────────────
-- §4. V4.0 표준 메타 SSOT 테이블 (tb_cmn_cd 확장)
-- ──────────────────────────────────────────────────────────

-- ID 형식 표준 코드 추가
INSERT INTO TB_CMN_CD (CD_GRP_ID, CD_VAL, CD_NM) VALUES
    ('ID_FORMAT', 'plain',            '평문'),
    ('ID_FORMAT', 'plain_dash',       '평문 (대시 구분, 계좌번호 등)'),
    ('ID_FORMAT', 'md5',              'MD5 해시 (32자)'),
    ('ID_FORMAT', 'sha1',             'SHA1 해시 (40자)'),
    ('ID_FORMAT', 'sha256',           'SHA256 해시 (64자)'),
    ('ID_FORMAT', 'no_hyphen_e164',   '전화번호 (no-hyphen)'),
    ('ID_FORMAT', 'normalized_url',   '정규화 URL'),
    ('ID_FORMAT', 'ipv4_dotted',      'IPv4 dotted'),
    ('ID_FORMAT', 'ipv6',             'IPv6')
ON CONFLICT (CD_GRP_ID, CD_VAL) DO NOTHING;

-- 도메인 코드 추가
INSERT INTO TB_CMN_CD (CD_GRP_ID, CD_VAL, CD_NM) VALUES
    ('DOMAIN', 'investigation', 'CCOP 수사 (tier 1)'),
    ('DOMAIN', 'partner',       '협력기관 (tier 2-3)'),
    ('DOMAIN', 'osint',         'OSINT 공개정보 (tier 4)'),
    ('DOMAIN', 'inference',     '추론 결과')
ON CONFLICT (CD_GRP_ID, CD_VAL) DO NOTHING;

-- 신뢰도 tier 코드
INSERT INTO TB_CMN_CD (CD_GRP_ID, CD_VAL, CD_NM) VALUES
    ('RELIABILITY_TIER', '1', 'tier 1 — 공식 수사'),
    ('RELIABILITY_TIER', '2', 'tier 2 — 협력기관 공식'),
    ('RELIABILITY_TIER', '3', 'tier 3 — 추론/협력기관 비공식'),
    ('RELIABILITY_TIER', '4', 'tier 4 — OSINT/민간 신고')
ON CONFLICT (CD_GRP_ID, CD_VAL) DO NOTHING;

-- V3.7 신규 enum 추가
INSERT INTO TB_CMN_CD (CD_GRP_ID, CD_VAL, CD_NM) VALUES
    ('DEV_TYPE', 'smartphone',    '스마트폰'),
    ('DEV_TYPE', 'pc',            'PC'),
    ('DEV_TYPE', 'tablet',        '태블릿'),
    ('DEV_TYPE', 'relay_station', '불법중계기'),
    ('DEV_TYPE', 'router',        '라우터'),
    ('DEV_TYPE', 'other',         '기타')
ON CONFLICT (CD_GRP_ID, CD_VAL) DO NOTHING;

-- ──────────────────────────────────────────────────────────
-- §5. 검증 — V4.0 메타 적용 결과 확인
-- ──────────────────────────────────────────────────────────

-- 5-1. 모든 데이터 테이블에 V4.0 메타 컬럼 6종이 있는지
SELECT
    table_schema,
    table_name,
    SUM(CASE WHEN column_name = 'source_id'        THEN 1 ELSE 0 END) AS has_source_id,
    SUM(CASE WHEN column_name = 'source_domain'    THEN 1 ELSE 0 END) AS has_source_domain,
    SUM(CASE WHEN column_name = 'reliability_tier' THEN 1 ELSE 0 END) AS has_tier,
    SUM(CASE WHEN column_name = 'collected_at'     THEN 1 ELSE 0 END) AS has_collected_at,
    SUM(CASE WHEN column_name = 'rec_created'      THEN 1 ELSE 0 END) AS has_rec_created,
    SUM(CASE WHEN column_name = 'rec_updated'      THEN 1 ELSE 0 END) AS has_rec_updated
FROM information_schema.columns
WHERE table_name LIKE 'tb\_%' OR table_schema = 'test_ccop_cp'
GROUP BY table_schema, table_name
ORDER BY table_schema, table_name;

-- 5-2. V4.0 코드가 tb_cmn_cd에 있는지
SELECT cd_grp_id, COUNT(*) FROM tb_cmn_cd
WHERE cd_grp_id IN ('ID_FORMAT', 'DOMAIN', 'RELIABILITY_TIER', 'DEV_TYPE')
GROUP BY cd_grp_id ORDER BY cd_grp_id;

-- ============================================================
-- 패치 끝
-- ============================================================
