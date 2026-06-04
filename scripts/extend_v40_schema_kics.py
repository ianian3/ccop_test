"""
test_v40 스키마에 KICS 측 V4.0 표준 RDB 테이블 추가
============================================================
CSV 업로드 시 import_predefined_schema_to_rdb 가 사용하는 8 테이블을
test_v40 스키마에 V4.0 메타 6컬럼 포함하여 생성.

대상 테이블 (CSV→RDB 마법사가 INSERT 하는 곳):
  TB_INCDNT_MST    (사건)
  TB_PRSN          (인물)
  TB_INST          (기관)
  TB_FIN_BACNT     (계좌)
  TB_FIN_BACNT_DLNG (이체)
  TB_FIN_EXTRC_BACNT (계좌 소유)
  TB_TELNO_MST     (전화)  ← 이미 OSINT 측에서 생성, ALTER 만
  TB_TELNO_JOIN    (전화 소유)
  TB_TELNO_CALL_DTL (통화)
"""
import sys, logging
sys.path.insert(0, '/Users/iankwon/test/coop_v1.0')
from app import create_app
from app.services.rdb_to_graph_service import RdbToGraphService
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('schema_ext')
_app = create_app(); _app.app_context().push()

DDL = """
-- 사건 마스터
CREATE TABLE IF NOT EXISTS test_v40.TB_INCDNT_MST (
    INCDNT_NO         VARCHAR(64) PRIMARY KEY,
    FLNM              VARCHAR(200),
    CRIME_TYPE        VARCHAR(80),
    DAMAGE_AMOUNT     BIGINT,
    OCCURRED_AT       DATE,
    STATUS            VARCHAR(20),
    EVID_GRADE        CHAR(1),
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'investigation',
    RELIABILITY_TIER  SMALLINT    DEFAULT 1,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 인물 마스터
CREATE TABLE IF NOT EXISTS test_v40.TB_PRSN (
    PRSN_ID           VARCHAR(64) PRIMARY KEY,
    KORN_FLNM         VARCHAR(80),
    PRSN_SE_CD        VARCHAR(8),
    DOB               DATE,
    GENDER            CHAR(1),
    RRNO_HASH         VARCHAR(128),
    ROLE_CD           VARCHAR(20),
    RISK_LEVEL        VARCHAR(10),
    IS_ANONYMOUS      BOOLEAN     DEFAULT FALSE,
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'investigation',
    RELIABILITY_TIER  SMALLINT    DEFAULT 1,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 기관 마스터
CREATE TABLE IF NOT EXISTS test_v40.TB_INST (
    INST_ID           VARCHAR(64) PRIMARY KEY,
    INST_NM           VARCHAR(200),
    INST_TYPE         VARCHAR(40),
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'investigation',
    RELIABILITY_TIER  SMALLINT    DEFAULT 1,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 금융 계좌 마스터
CREATE TABLE IF NOT EXISTS test_v40.TB_FIN_BACNT (
    BACNT_ID          VARCHAR(64) PRIMARY KEY,
    BACNT_NO          VARCHAR(40),
    BANK_NM           VARCHAR(80),
    BNK_CD            VARCHAR(10),
    DPSTR             VARCHAR(80),
    IS_BURNER         BOOLEAN     DEFAULT FALSE,
    IS_FROZEN         BOOLEAN     DEFAULT FALSE,
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'investigation',
    RELIABILITY_TIER  SMALLINT    DEFAULT 1,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 금융 거래 (이체)
CREATE TABLE IF NOT EXISTS test_v40.TB_FIN_BACNT_DLNG (
    DLNG_ID           VARCHAR(64) PRIMARY KEY,
    SRC_BACNT_NO      VARCHAR(40),
    TGT_BACNT_NO      VARCHAR(40),
    AMOUNT            BIGINT,
    DLNG_DT           TIMESTAMP,
    DLNG_TYPE         VARCHAR(20),
    EVID_GRADE        CHAR(1),
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'investigation',
    RELIABILITY_TIER  SMALLINT    DEFAULT 1,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 계좌 소유 (사건 ↔ 계좌)
CREATE TABLE IF NOT EXISTS test_v40.TB_FIN_EXTRC_BACNT (
    EXTRC_ID          VARCHAR(64) PRIMARY KEY,
    INCDNT_NO         VARCHAR(64),
    BACNT_NO          VARCHAR(40),
    PRSN_ID           VARCHAR(64),
    EXTRC_DT          TIMESTAMP,
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'investigation',
    RELIABILITY_TIER  SMALLINT    DEFAULT 1,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 전화 소유 (인물 ↔ 전화)
CREATE TABLE IF NOT EXISTS test_v40.TB_TELNO_JOIN (
    JOIN_ID           VARCHAR(64) PRIMARY KEY,
    PRSN_ID           VARCHAR(64),
    TELNO             VARCHAR(64),
    JOIN_TYPE         VARCHAR(20),
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'investigation',
    RELIABILITY_TIER  SMALLINT    DEFAULT 1,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);

-- 통화 상세
CREATE TABLE IF NOT EXISTS test_v40.TB_TELNO_CALL_DTL (
    CALL_ID           VARCHAR(64) PRIMARY KEY,
    CALLER_TELNO      VARCHAR(64),
    CALLEE_TELNO      VARCHAR(64),
    BGNG_DT           TIMESTAMP,
    END_DT            TIMESTAMP,
    DURATION          INTEGER,
    CARR_CD           VARCHAR(20),
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20) DEFAULT 'investigation',
    RELIABILITY_TIER  SMALLINT    DEFAULT 1,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
);
"""

def main():
    conn, cur = RdbToGraphService.get_db_connection()
    conn.autocommit = True
    log.info("test_v40 KICS 표준 8 테이블 추가...")
    for stmt in DDL.split(';'):
        s = stmt.strip()
        if not s: continue
        try:
            cur.execute(s + ';')
        except Exception as e:
            log.warning(f"  실패(무시): {str(e)[:80]}")
    cur.execute("""SELECT table_name FROM information_schema.tables
                   WHERE table_schema='test_v40' AND table_name LIKE 'tb_%'
                   ORDER BY table_name;""")
    tables = [r[0] for r in cur.fetchall()]
    log.info(f"✅ test_v40 스키마 총 {len(tables)} 표준 테이블:")
    for t in tables: log.info(f"    - {t}")
    cur.close(); conn.close()


if __name__ == '__main__':
    main()
