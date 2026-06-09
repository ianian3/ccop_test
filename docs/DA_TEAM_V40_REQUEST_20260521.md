# DA팀 V3.7 표준 DDL → V4.0 호환화 요청서

- **발신**: 데이터팀 / CCOP V4.0 온톨로지 설계
- **수신**: DA 표준화팀
- **일자**: 2026-05-21
- **대상 문서**: `CYBERCOP_STANDARD_TABLE_DDL_20260518.sql` (V3.7, 16 도메인 / 48 테이블)
- **목적**: 현행 V3.7 DDL을 CCOP V4.0 통합 온톨로지(5계층 아키텍처: L1 수집 → L2 RDB → L3 매핑 → L4 그래프 → L5 시각화)와 100% 호환되도록 보강

---

## 0. 요약

| 항목 | 현재 (V3.7) | 목표 (V4.0) | 격차 |
|------|-------------|-------------|------|
| V4.0 노드 매핑 | 22 / 25 (88%) | 25 / 25 (100%) | 3개 노드 누락 |
| V4.0 메타 컬럼 | 4 / 6 (67%) | 6 / 6 (100%) | 2개 메타 누락 |
| V3.7 신규 속성 | 1 / 4 (25%) | 4 / 4 (100%) | 3개 속성 누락 |
| **종합 호환률** | **~75%** | **100%** | **추가 작업 필요** |

> **첨부 패치 SQL**: `scripts/da_v37_v40_patch.sql`
> — 본 문서의 1~5장 변경 내역을 일괄 적용 가능. DA팀 마스터 DDL에 반영 후 폐기 권장.

---

## 1. 🔴 [긴급] DDL 버그 수정 6건

DA팀 마스터 DDL에 직접 반영 필요. 그래프 적재 시 PK/시퀀스 오류로 ETL 중단 우려.

| ID | 위치 | 현재 | 수정안 | 영향 |
|----|------|------|--------|------|
| **B1** | 3.9.4 절 | `TB_SYS_LGN_EVT` 정의 중복 (2회) | 중복 블록 1개 제거 | DDL 실행 실패 |
| **B2** | `TB_BANK_CD` | PK 컬럼명 `BNAK_CD` | `BANK_CD` 로 정정 | FK 연결 실패 |
| **B3** | `TB_EML_ADDR` | PK 컬럼명 `EML_ADDR_ID` ↔ 본문 `EML_ADDR` 혼용 | 컬럼명 통일 | 무결성 오류 |
| B4 | 다수 도메인 | 일부 시퀀스(`SEQ_*`) 누락 | 누락 시퀀스 일괄 생성 | PK 자동채번 실패 |
| B5 | 공통 메타 | `RLBLT_TIER DEFAULT 5` (가장 낮음) | `DEFAULT 3` (T3 시민제보 기본) | 신뢰도 통계 왜곡 |
| B6 | 코멘트 | `CNTCT` 오기 (다수 위치) | `CONTACT` 통일 | 가독성 |

---

## 2. 🟡 [필수] 누락 테이블 3종 신규 추가

V4.0 온톨로지 25개 노드 중 **3개(12%)** 가 현재 DDL에 미반영.
각 테이블의 책임 도메인 명확화를 위해 도메인 코드(`SOURCE_DOMAIN`) 기본값을 함께 지정.

### 2.1 `TB_DGTL_FILE` — 디지털 증거 파일 (vt_file)
- **사유**: 디지털 포렌식 증거(이미지/문서/실행파일/악성코드 샘플) 표준 저장소 부재
- **도메인**: `DIGITAL`

```sql
CREATE TABLE TB_DGTL_FILE (
    FILE_ID           VARCHAR(64)  PRIMARY KEY,
    FILE_HASH_SHA256  CHAR(64)     NOT NULL,
    FILE_HASH_MD5     CHAR(32),
    FILE_NM           VARCHAR(256),
    FILE_SIZE_BYTES   BIGINT,
    MIME_TYPE         VARCHAR(128),
    EVDC_ID           VARCHAR(64),   -- TB_EVDC_MST 참조
    -- V4.0 공통 메타 6 컬럼
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20)  DEFAULT 'DIGITAL',
    RLBLT_TIER        SMALLINT     DEFAULT 3,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IX_TB_DGTL_FILE_HASH ON TB_DGTL_FILE (FILE_HASH_SHA256);
CREATE INDEX IX_TB_DGTL_FILE_EVDC ON TB_DGTL_FILE (EVDC_ID);
```

### 2.2 `TB_SITE_CLST_MST` — 사이트 클러스터 마스터 (site_cluster)
- **사유**: OSINT 사이트 자동 군집(SimHash 64bit + Union-Find) 결과 허브
- **도메인**: `OSINT`

```sql
CREATE TABLE TB_SITE_CLST_MST (
    CLST_ID           VARCHAR(64)  PRIMARY KEY,
    CLST_NM           VARCHAR(256),
    SIMHASH64         BIGINT       NOT NULL,
    MEMBER_CNT        INTEGER      DEFAULT 0,
    REPRESENTATIVE_URL VARCHAR(2048),
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20)  DEFAULT 'OSINT',
    RLBLT_TIER        SMALLINT     DEFAULT 4,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IX_TB_SITE_CLST_SIMHASH ON TB_SITE_CLST_MST (SIMHASH64);
```

### 2.3 `TB_PT_CLST_MST` — 캠페인/조직 클러스터 마스터 (pt_cluster)
- **사유**: 범죄 캠페인/조직 단위 추론 결과 허브 (Person+Threat 통합)
- **도메인**: `KICS` (수사 추론 결과)

```sql
CREATE TABLE TB_PT_CLST_MST (
    CLST_ID           VARCHAR(64)  PRIMARY KEY,
    CAMPAIGN_NM       VARCHAR(256),
    THREAT_LEVEL      SMALLINT,                 -- 1(낮음) ~ 5(높음)
    START_DT          DATE,
    END_DT            DATE,
    MEMBER_CNT        INTEGER      DEFAULT 0,
    SOURCE_ID         VARCHAR(64),
    SOURCE_DOMAIN     VARCHAR(20)  DEFAULT 'KICS',
    RLBLT_TIER        SMALLINT     DEFAULT 2,
    COLLECTED_AT      TIMESTAMP,
    REC_CREATED       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    REC_UPDATED       TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. 🟢 [표준] V4.0 공통 메타 6 컬럼 전면 부착

현재 모든 마스터 테이블 48개에 다음 6 컬럼이 **표준 부착**되어야 함.
현재 충족률 4/6 (67%) — `SOURCE_DOMAIN`, `RLBLT_TIER` 누락 또는 전파 불완전.

```sql
SOURCE_ID         VARCHAR(64)              -- 원천 시스템 레코드 ID
SOURCE_DOMAIN     VARCHAR(20)              -- KICS | OSINT | DIGITAL | EXT  ★ 신규
RLBLT_TIER        SMALLINT  DEFAULT 3      -- 1(공식) ~ 5(추정)            ★ DEFAULT 정정
COLLECTED_AT      TIMESTAMP                -- 수집 시각
REC_CREATED       TIMESTAMP  DEFAULT CURRENT_TIMESTAMP   -- 적재 시각
REC_UPDATED       TIMESTAMP  DEFAULT CURRENT_TIMESTAMP   -- 최종 수정 시각
```

> **적용 범위**: 모든 마스터 테이블 (`TB_*_MST`, `TB_*_INFO`, `TB_*_EVT` 포함).
> 부속 테이블(매핑/이력/코드) 적용 여부는 DA팀 판단에 위임.

---

## 4. 🟢 [신규 속성] V3.7 신규 컬럼 3건

| 테이블 | 추가 컬럼 | 타입 / 기본값 | 용도 |
|--------|-----------|---------------|------|
| `TB_PSN` | `IS_ANONYMOUS` | `BOOLEAN DEFAULT FALSE` | 익명 인물(닉네임 only) 표기 |
| `TB_DGTL_ID_MST` | `IS_ANONYMOUS` | `BOOLEAN DEFAULT FALSE` | 익명 ID 추론 플래그 |
| `TB_DEV_MST` | `DEV_TYPE` enum 확장 | `+ 'relay_station'` | 중계기/IMEI 분기 |

`DEV_TYPE` 의 경우 enum 제약 또는 `TB_CMN_CD` 참조 중 DA팀 표준 방식 적용.

---

## 5. 🟢 [공통코드] `TB_CMN_CD` 추가 코드 그룹 4종

V4.0 표준 enum 값 RDB 측 SSOT 확보를 위해 `TB_CMN_CD` 에 다음 4개 그룹 추가:

| 그룹 ID | 코드 | 설명 |
|---------|------|------|
| **`ID_FORMAT`** | `email`, `phone_e164`, `account_hash`, `url_norm`, `ip_v4`, `ip_v6`, `imei`, `imsi`, `bitcoin_addr` | 노드 ID 정규화 형식 |
| **`DOMAIN`** | `KICS`, `OSINT`, `DIGITAL`, `EXT` | 데이터 원천 도메인 |
| **`RLBLT_TIER`** | `1`=공식, `2`=수사, `3`=시민제보, `4`=웹수집, `5`=추정 | 신뢰도 등급 |
| **`DEV_TYPE`** | `phone`, `sim`, `imei`, `relay_station`, `modem`, `router` | 기기 유형 |

상세 INSERT 문은 첨부 패치 SQL 5장 참조.

---

## 6. 적용 일정 및 협의 사항

| 단계 | 작업 | 담당 | 기한(제안) |
|------|------|------|-----------|
| ① | 본 요청서 검토 / 이견 회신 | DA팀 | D+2 |
| ② | 마스터 DDL 1~5장 반영 | DA팀 | D+5 |
| ③ | 패치 적용 검증 (스키마 diff) | 데이터팀 | D+6 |
| ④ | ETL/RDB→Graph 파이프라인 회귀 테스트 | 데이터팀 | D+8 |
| ⑤ | V4.0 L2 매핑 명세 갱신 (`V40_RDB_TO_GRAPH_MAPPING.md`) | 데이터팀 | D+8 |

### 협의 필요 사항
1. **누락 테이블 3종 명명 규칙** — `TB_DGTL_FILE` / `TB_SITE_CLST_MST` / `TB_PT_CLST_MST` 의 도메인 prefix 정책이 DA 표준과 충돌하는지 확인.
2. **`DEV_TYPE` enum 확장 방식** — DDL CHECK 제약 vs `TB_CMN_CD` 참조 중 DA팀 표준 선택.
3. **`RLBLT_TIER DEFAULT` 정책** — 기존 DEFAULT 5 사용 테이블이 운영 중이라면 마이그레이션 전략 협의.

---

## 7. 참고 문서

- `docs/CCOP_ONTOLOGY_V4.0.md` — V4.0 통합 온톨로지 본문
- `docs/V40_RDB_SCHEMA_STANDARD.md` — L2 RDB 스키마 표준
- `docs/V40_RDB_TO_GRAPH_MAPPING.md` — L3 매핑 명세 (25 노드)
- `docs/V40_VISUALIZATION_STANDARD.md` — L5 시각화 표준
- `scripts/da_v37_v40_patch.sql` — **본 요청서의 즉시 적용 패치 SQL**

---

**문의**: ian.kwon@skaiworldwide.co.kr (CCOP V4.0 온톨로지 설계 담당)
