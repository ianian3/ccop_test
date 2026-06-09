# CCOP RDB/Graph 표준화 미결 사항 (Open Issues)

> **버전**: v3.3 기준 점검 결과
> **작성일**: 2026-04-06 | **최종 수정**: 2026-04-16
> **대상 파일**: `app/middleware/services/rdb_to_graph_service.py`, `docs/02_DDL_COMPLETE.sql`
> **전체 완료율**: ~95%

---

## 요약

| # | 이슈 | 분류 | 우선순위 | 상태 |
|---|------|------|----------|------|
| 1 | TB_SYS_LGN_EVT 컬럼명 불일치 (ETL ↔ DDL) | ETL + DDL | 🔴 HIGH | 미해결 (DB팀 결정 필요) |
| 2 | `contradicts` 엣지 ETL 미구현 | ETL | 🟡 MEDIUM | ✅ 해소 (2026-04-07) |
| 3 | `clusters_with` 엣지 ETL 미구현 | ETL | 🟡 MEDIUM | ✅ 해소 (2026-04-07) |
| 4 | `edge_labels` 선언 리스트 미동기화 | ETL | 🟡 MEDIUM | ✅ 해소 (2026-04-07) |
| 5 | Phase 6E DDL RDB 문서 누락 | 문서 | 🔴 HIGH | ✅ 해소 (`02_DDL_COMPLETE.sql`로 공식화) |
| 6 | TB_IMPRSN_REL DDL RDB 문서 누락 | 문서 | 🔴 HIGH | ✅ 해소 (`02_DDL_COMPLETE.sql`로 공식화) |
| 7 | ETRI 메타데이터 연계 DDL/온톨로지 미반영 | DDL + 온톨로지 | 🟢 LOW | ✅ 해소 (2026-04-07, v3.2) |
| 8 | `contradicts` ETL: `psn_id` → `id` 속성키 불일치 | ETL | 🔴 HIGH | ✅ 해소 (2026-04-06, v3.2) |
| 9 | `clusters_with` ETL: `raw_id` 따옴표 누락 (타입 불일치) | ETL | 🔴 HIGH | ✅ 해소 (2026-04-06, v3.2) |
| 10 | `impersonates` 엣지 ETL 미구현 (TB_IMPRSN_REL → 그래프) | ETL | 🔴 HIGH | ✅ 해소 (2026-04-06, Phase 6J 추가) |
| 12 | `impersonates` 엣지 → v3.3 `used_for`/`targets` 2-홉 패턴으로 마이그레이션 | 온톨로지 + ETL | 🔴 HIGH | ✅ 해소 (2026-04-16, v3.3 vt_impersonation 노드 승격) |
| 11 | Phase 레이블 "6E" 중복 (마스터 노드 적재 vs. contradicts 엣지) | ETL | 🟡 MEDIUM | ✅ 해소 (2026-04-06, 6G/6H/6I/6J 재번호) |

---

## ISSUE #1 — TB_SYS_LGN_EVT 컬럼명 불일치

### 증상

ETL 코드(`rdb_to_graph_service.py` L246-251)와 DDL(`RDB_STANDARDIZATION_v3.6.md`) 사이에
동일 테이블의 컬럼명이 다르게 정의되어 있어 실 DB 구축 시 SELECT 오류 발생 가능.

### 상세 비교

| 항목 | ETL 코드 (L246-251) | DDL 문서 (§3.9) |
|------|---------------------|-----------------|
| IP 주소 컬럼 | `CNNT_IP_ADDR` | `IP_ADDR` |
| 접속 일시 컬럼 | `LGN_DT` | `ACCESS_DT` |
| 행위 코드 컬럼 | `LGN_RSLT_CD` (로그인 결과) | `ACTN_CD` (HTTP 메서드) |
| 사용자 ID 컬럼 | `USER_ID` | 없음 (누락) |

```python
# ETL 코드 현재 상태 (rdb_to_graph_service.py L246-251)
cur.execute("""
    SELECT LGN_SN, CNNT_IP_ADDR, USER_ID, LGN_DT, LGN_RSLT_CD, SVC_NM
    FROM TB_SYS_LGN_EVT
""")
```

```sql
-- DDL 문서 현재 상태 (RDB_STANDARDIZATION_v3.6.md §3.9, 02_DDL_COMPLETE.sql §9)
CREATE TABLE TB_SYS_LGN_EVT (
    LGN_SN      BIGSERIAL,
    IP_ADDR     VARCHAR(45),      -- ETL은 CNNT_IP_ADDR
    ACCESS_DT   TIMESTAMP,        -- ETL은 LGN_DT
    ACTN_CD     VARCHAR(20),      -- ETL은 LGN_RSLT_CD (의미 다름!)
    USER_AGENT_CN TEXT,
    ...
);
```

### 원인 분석

- DDL v3.0은 "시스템 접속 로그" 목적으로 HTTP 방식(`IP_ADDR`, `ACTN_CD`, `ACCESS_DT`) 설계
- ETL은 "로그인 이벤트" 목적으로 경찰청 KICS 원본 컬럼명(`CNNT_IP_ADDR`, `LGN_DT`) 기반 구현
- 두 버전이 별도로 진화하면서 충돌 발생

### 해결 방안 (선택 필요)

**Option A — DDL을 ETL 기준으로 수정** (추천: ETL이 이미 운영 중인 경우)
```sql
-- 02_DDL_COMPLETE.sql §9 수정
ALTER TABLE TB_SYS_LGN_EVT
  RENAME COLUMN IP_ADDR TO CNNT_IP_ADDR;
ALTER TABLE TB_SYS_LGN_EVT
  RENAME COLUMN ACCESS_DT TO LGN_DT;
ALTER TABLE TB_SYS_LGN_EVT
  RENAME COLUMN ACTN_CD TO LGN_RSLT_CD;
ALTER TABLE TB_SYS_LGN_EVT
  ADD COLUMN USER_ID VARCHAR(100);
ALTER TABLE TB_SYS_LGN_EVT
  ADD COLUMN SVC_NM  VARCHAR(100);
```

**Option B — ETL을 DDL 기준으로 수정** (추천: DB 신규 구축인 경우)
```python
# rdb_to_graph_service.py L246-251 수정
cur.execute("""
    SELECT LGN_SN, IP_ADDR AS CNNT_IP_ADDR, ACCESS_DT AS LGN_DT,
           ACTN_CD AS LGN_RSLT_CD, NULL AS USER_ID, NULL AS SVC_NM
    FROM TB_SYS_LGN_EVT
""")
```

### 결정 필요 사항

- [ ] DB 담당자: Option A / B 중 하나 선택 후 ETL 또는 DDL 확정 버전 수정
- [ ] 확정 후 `02_DDL_COMPLETE.sql` §9 의 `⚠` 주석 제거

---

## ISSUE #2 — `contradicts` 엣지 ETL 미구현 ✅ 해소됨

### 해소 내용 (2026-04-07)

`rdb_to_graph_service.py`에 Phase 6E 블록(6E) 이후 6E. 섹션으로 ETL 블록 구현 완료.

```python
# rdb_to_graph_service.py — 6E. 모순 정보 블록 (추가됨)
# TB_ENTITY_CONFLICT WHERE RESOLVED_YN='N' → contradicts 엣지
# MERGE (a:vt_psn)-[e:contradicts {cnfl_field, cnfl_type, rec_created}]->(b:vt_psn)
```

### 후속 조치 필요

- [ ] TB_ENTITY_CONFLICT 테이블이 실제 DB에 생성되어 있어야 ETL 동작 (02_DDL_COMPLETE.sql §13 참조)

---

## ISSUE #3 — `clusters_with` 엣지 ETL 미구현 ✅ 해소됨

### 해소 내용 (2026-04-07)

`rdb_to_graph_service.py`에 Phase 6F 블록으로 ETL 구현 완료. 유사도 임계값 0.7 적용.

```python
# rdb_to_graph_service.py — 6F. 유사 진정서 군집 블록 (추가됨)
# TB_PETTN_CLSTR WHERE SIM_SCORE >= 0.7 → clusters_with 엣지
# MERGE (a:vt_petition)-[e:clusters_with {sim_score, basis, rec_created}]->(b:vt_petition)
```

### 후속 조치 필요

- [ ] TB_PETTN_CLSTR 테이블이 실제 DB에 생성되어 있어야 ETL 동작 (02_DDL_COMPLETE.sql §3 참조)
- [ ] 유사도 임계값 0.7이 운영 정책으로 확정되면 이슈 완전 종결

---

## ISSUE #4 — `edge_labels` 선언 리스트 미동기화 ✅ 해소됨

### 해소 내용 (2026-04-07)

`rdb_to_graph_service.py` `edge_labels` 리스트에 3개 엣지 추가 완료.
(`contradicts`는 기존에 이미 등재되어 있었음)

| 엣지 | 구현 여부 | 선언 여부 |
|------|-----------|-----------|
| `impersonates` | ⚠️ ETL 구현됨 (v3.2 레거시, deprecated) | ✅ 등재 완료 (읽기 전용 유지) |
| `used_for` | ✅ ETL 구현됨 (v3.3 신규) | ✅ 등재 완료 |
| `targets` | ✅ ETL 구현됨 (v3.3 신규) | ✅ 등재 완료 |
| `filed_as` | ✅ ETL 구현됨 | ✅ 등재 완료 |
| `clusters_with` | ✅ ETL 구현됨 (ISSUE #3) | ✅ 등재 완료 |
| `contradicts` | ✅ ETL 구현됨 (ISSUE #2) | ✅ 기존 등재 |

---

## ISSUE #5 — Phase 6E DDL RDB 문서 누락 ✅ 해소됨

### 해소 내용

`RDB_STANDARDIZATION_v3.6.md`에 아래 6개 테이블 DDL이 누락되어 있었으나
`02_DDL_COMPLETE.sql §14`에 공식 DDL을 신규 작성하여 해소.

| 테이블 | 그래프 노드 | 위치 |
|--------|------------|------|
| `TB_DGTL_ID_MST` | `vt_id` | 02_DDL_COMPLETE.sql §14-① |
| `TB_EMAIL_MST` | `vt_email` | 02_DDL_COMPLETE.sql §14-② |
| `TB_CRYPTO_WALLET_MST` | `vt_crypto` | 02_DDL_COMPLETE.sql §14-③ |
| `TB_DEV_MST` | `vt_dev` | 02_DDL_COMPLETE.sql §14-④ |
| `TB_ATM_MST` | `vt_atm` | 02_DDL_COMPLETE.sql §14-⑤ |
| `TB_LOC_MST` | `vt_loc` | 02_DDL_COMPLETE.sql §14-⑥ |

### 후속 조치 필요

- [ ] `RDB_STANDARDIZATION_v3.6.md` §3에 Phase 6E 섹션(3.15) 추가하여 두 문서 동기화

---

## ISSUE #6 — TB_IMPRSN_REL DDL RDB 문서 누락 ✅ 해소됨

### 해소 내용

`RDB_STANDARDIZATION_v3.6.md §4` 그래프 연동 경계 테이블에 `TB_IMPRSN_REL → impersonates`가 참조되었으나
§3 DDL 명세가 없었음. `02_DDL_COMPLETE.sql §15`에 공식 DDL 신규 작성.

```
그래프 impersonates 엣지 대응:
  vt_telno / vt_id / vt_email → vt_org
  법적 근거: 전기통신금융사기법 제3조
```

### 후속 조치 필요

- [ ] `RDB_STANDARDIZATION_v3.6.md §3`에 §3.15 사칭관계 도메인 섹션 추가

---

## ISSUE #7 — ETRI 메타데이터 연계 DDL/온톨로지 미반영 ✅ 해소됨

### 해소 내용 (2026-04-07, v3.2)

ETRI "사이버범죄 메타데이터 체계 v0.8" 문서 기반으로 아래 항목 반영 완료.

| 파일 | 변경 내용 |
|------|---------|
| `02_DDL_COMPLETE.sql` | TB_CMN_CD에 CRIME_METHOD(10개)/CRIME_STEP(6개)/SRC_TYP(6개) 코드 추가 |
| `02_DDL_COMPLETE.sql` | TB_DATA_SRC SRC_TYP_CD에 PREPROCESSOR 추가, src-etri 등록 |
| `02_DDL_COMPLETE.sql` | TB_DATA_INGEST_LOG에 ACTIVITY_TYP_CD 컬럼 추가 (PROV-O Activity 유형) |
| `02_DDL_COMPLETE.sql` | TB_PETTN_MST에 CRIME_METHOD_CD, CRIME_STEP_CN 컬럼 추가 |
| `ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md` | vt_src에 preprocessor_version, activity_typ_cd 속성 추가 |
| `ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md` | vt_case에 crime_method, crime_step, risk_level, risk_score 속성 추가 |
| `ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md` | vt_petition에 crime_method_cd, crime_step_cn 속성 추가 |
| `ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md` | src_type 목록에 PREPROCESSOR 공식 추가 |

### 후속 조치 (중장기)

- [ ] TB_NER_RESULT 신규 테이블 생성 (ETRI crime_meta NER 엔티티 수신 저장)
- [ ] TB_RISK_ASSESSMENT 신규 테이블 생성 (risk_meta 위험도 평가 저장)

---

## 조치 우선순위 체크리스트

```
🔴 유일한 미결 (DB 구축 전 반드시 해결)
   [ ] ISSUE #1: TB_SYS_LGN_EVT 컬럼명 기준 확정 (Option A or B 선택)

✅ 완료
   [x] ISSUE #2: contradicts 엣지 ETL 구현 (2026-04-07)
   [x] ISSUE #3: clusters_with 엣지 ETL 구현 (2026-04-07)
   [x] ISSUE #4: edge_labels 선언 리스트 동기화 (2026-04-07)
   [x] ISSUE #5: Phase 6E DDL 공식화 (02_DDL_COMPLETE.sql §14)
   [x] ISSUE #6: TB_IMPRSN_REL DDL 공식화 (02_DDL_COMPLETE.sql §15)
   [x] ISSUE #7: ETRI 메타데이터 연계 v3.2 반영 (2026-04-07)
   [x] ISSUE #8: contradicts ETL psn_id→id 수정 (2026-04-06)
   [x] ISSUE #9: clusters_with ETL raw_id 타입 수정 (2026-04-06)
   [x] ISSUE #10: impersonates ETL Phase 6J 구현 (2026-04-06)
   [x] ISSUE #11: Phase 번호 6G/6H/6I/6J 재정렬 (2026-04-06)

🟢 후속 (문서 동기화, 중장기)
   [ ] RDB_STANDARDIZATION_v3.6.md §3.15 Phase 6E DDL 추가 (선택)
   [ ] RDB_STANDARDIZATION_v3.6.md §3.16 TB_IMPRSN_REL DDL 추가 (선택)
   [ ] TB_NER_RESULT 신규 테이블 (전처리 기관 연동 확정 후)
   [ ] TB_RISK_ASSESSMENT 신규 테이블 (전처리 기관 연동 확정 후)
```

---

## 관련 파일

| 파일 | 역할 | 버전 |
|------|------|------|
| `docs/02_DDL_COMPLETE.sql` | 49개 전체 테이블 완전 DDL (최신 기준) | v3.3 |
| `docs/ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md` | 그래프 온톨로지 설계 (구현 기준) | v3.3 |
| `app/middleware/services/rdb_to_graph_service.py` | ETL 구현 | v3.3 |
| `docs/RDB_STANDARDIZATION_v3.6.md` | RDB 설계 원칙 문서 (참고용, §3.15/3.16 미동기화) | v3.0 |
