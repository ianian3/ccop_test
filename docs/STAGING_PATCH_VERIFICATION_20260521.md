# Phase 1.4 — 스테이징 패치 SQL 검증 리포트

- **실시일**: 2026-05-21
- **대상**: `scripts/da_v37_v40_patch.sql`
- **검증 환경**: Docker `postgres:15-alpine` (격리 컨테이너, port 55433, DB `tccopdb_stg`)
- **부트스트랩**: `scripts/stg_bootstrap_v37_mini.sql` (V3.7 미니 12 테이블)
- **결과**: ✅ **전 항목 통과**

---

## 검증 매트릭스

| # | 항목 | 기대값 | 실측값 | 결과 |
|---|------|--------|--------|------|
| 0 | 정적 SQL parse (sqlglot) | 27 statement 무오류 | 27 statement, ERROR 0 | ✅ |
| 1 | BEGIN/COMMIT 트랜잭션 | 1 / 1 | 1 / 1 | ✅ |
| §6.1 | 누락 테이블 3종 생성 | 3 rows | `tb_dgtl_file`, `tb_pt_clst_mst`, `tb_site_clst_mst` | ✅ |
| §6.2 | 메타 6 컬럼 미충족 마스터 | 0 rows | 0 rows (10/10 마스터 6/6) | ✅ |
| §6.3 | IS_ANONYMOUS 신규 컬럼 | 2 rows | `tb_psn`, `tb_dgtl_id_mst` | ✅ |
| §6.4 | TB_CMN_CD 4그룹 | 9/4/5/6 | 9/4/5/6 | ✅ |
| B2 | BNAK_CD → BANK_CD RENAME | bank_cd 존재 | bank_cd ✅ | ✅ |
| B3 | EML_ADDR_ID → EML_ADDR RENAME | eml_addr 존재 | eml_addr ✅ | ✅ |
| B5 | RLBLT_TIER DEFAULT 3 (TB_PSN) | 3 | 3 | ✅ |
| Idem | 패치 재실행 멱등성 | ERROR 0, 중복 INSERT 0 | ERROR 0, `INSERT 0 0` × 4 | ✅ |

---

## 단계별 실행 결과

### Step 1. 부트스트랩 (V3.7 미니 12 테이블)
```
CREATE TABLE × 12   ← TB_CMN_CD, TB_PSN, TB_BANK_CD(BNAK_CD 오타),
                      TB_EML_ADDR(EML_ADDR_ID 혼용), TB_DEV_MST,
                      TB_DGTL_ID_MST, TB_CASE_MST, TB_BACNT_MST,
                      TB_TELNO_MST, TB_IP_MST, TB_SITE_INFO, TB_SYS_LGN_EVT
```

### Step 2. 패치 SQL 1차 적용
```
BEGIN
DO × 4              ← B2/B3/B5/메타루프 모두 정상 실행
CREATE SEQUENCE × 3 ← SEQ_TB_DGTL_FILE / SITE_CLST / PT_CLST
CREATE TABLE × 3    ← V4.0 누락 노드 3종
CREATE INDEX × 3
COMMENT × 5
ALTER TABLE × 2     ← IS_ANONYMOUS 2건
INSERT 0 9          ← ID_FORMAT
INSERT 0 4          ← DOMAIN
INSERT 0 5          ← RLBLT_TIER
INSERT 0 6          ← DEV_TYPE
COMMIT
```
> NOTICE: `tb_site_clst_mst`/`tb_pt_clst_mst` 의 메타 컬럼이 이미 존재 → §2 CREATE 시 기본 부착됐고 §3 ADD IF NOT EXISTS 가 안전하게 스킵. **정상 동작**.

### Step 3. 멱등성 재실행
```
BEGIN
INSERT 0 0 × 4      ← ON CONFLICT DO NOTHING 정상
ALTER TABLE × 2     ← ADD COLUMN IF NOT EXISTS 정상
CREATE TABLE × 3    ← IF NOT EXISTS 정상
CREATE SEQUENCE × 3 ← IF NOT EXISTS 정상
CREATE INDEX × 3    ← IF NOT EXISTS 정상
ERROR 0
COMMIT
```

### Step 4. 마스터 테이블 메타 분포
```
tb_bacnt_mst     6/6 ✅
tb_case_mst      6/6 ✅
tb_dev_mst       6/6 ✅
tb_dgtl_id_mst   6/6 ✅
tb_ip_mst        6/6 ✅
tb_pt_clst_mst   6/6 ✅
tb_site_clst_mst 6/6 ✅
tb_site_info     6/6 ✅
tb_sys_lgn_evt   6/6 ✅
tb_telno_mst     6/6 ✅
─────────────────────────
충족률 10/10 = 100%
```

---

## 발견 사항 및 운영 적용 시 주의점

### 🟢 정상
- DO 익명블록 4종 모두 PostgreSQL 15에서 무결함
- `information_schema.tables` 동적 루프가 `TB_*_MST/INFO/EVT` 패턴을 정확히 캡처
- `ON CONFLICT (CD_GRP_ID, CD_ID) DO NOTHING` — `TB_CMN_CD` PK 가정과 일치

### ⚠️ DA팀 환경 변수 확인 필요
1. **`TB_CMN_CD` PK 구성** — 본 패치는 `(CD_GRP_ID, CD_ID)` 복합 PK 가정. DA 표준이 단일 PK면 ON CONFLICT 절 조정 필요.
2. **`information_schema` 검색 스키마** — 본 검증은 단일 스키마 환경. 운영 DB가 다중 스키마면 `table_schema = current_schema()` 조건 강화 필요.
3. **`TB_DEV_MST.DEV_TYPE` CHECK 제약** — 운영 DB에 CHECK 존재 여부 확인 후 §4.3 주석 해제 결정.

### ⚠️ B1 (TB_SYS_LGN_EVT 정의 중복)
- SQL 패치로 해결 불가 — DA팀 마스터 DDL 직접 수정 필요.
- 운영 적용 전 DA팀 확정 회신 대기.

---

## 결론

`scripts/da_v37_v40_patch.sql` 은 격리 환경에서 **무결성·멱등성·검증 쿼리 4종 전부 통과**.
DA팀 회신 수령 후 `TB_CMN_CD` PK 구성 / CHECK 제약 운영 여부 2건만 확인되면 **운영 DB 적용 준비 완료**.

### 다음 단계
- ⏳ Phase 1.2 — DA팀 검토 회신 (D+2)
- 🟢 Phase 2.1 — ETL V4.0 메타 주입 점검 (병렬 진행 가능)

---

## 스테이징 컨테이너 (재사용 가능)
```bash
# 컨테이너: ccop_stg_pg (port 55433)
docker exec -it ccop_stg_pg psql -U ccop -d tccopdb_stg
# 종료
docker rm -f ccop_stg_pg
```
