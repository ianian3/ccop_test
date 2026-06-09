> ## ⚠️ DEPRECATED — V4.0 통합본 사용 권장
>
> 이 문서는 **CCOP 온톨로지 V3.6 (RDB 표준화)** 명세입니다. **2026-05-21부로 V4.0으로 통합되어 deprecated** 되었습니다.
>
> **현행 SSOT**: [`docs/CCOP_ONTOLOGY_V4.0.md`](CCOP_ONTOLOGY_V4.0.md)
> **코드 SSOT**: `app/middleware/services/ontology_service.py:KICSCrimeDomainOntology`
>
> V4.0은 V3.7 카탈로그(25 노드 / 53 엣지)를 그대로 유지하면서, 도메인 사용 매트릭스 / 식별자 형식 / 추론 규칙을 표준 메타로 격상한 통합본입니다. 본 문서는 **역사적 참고용**으로만 보존됩니다.
>
> ---
>

# CCOP RDB 데이터베이스 표준화 설계서 v3.6

> **버전:** v3.6
> **작성일:** 2026-04-06 | **최종 수정:** 2026-04-24
> **상태:** 확정
> **관련 문서:** ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md (그래프 대응 기준)

### v3.6 변경 이력 (2026-04-24)

| 변경 항목 | 분류 | 내용 |
|-----------|------|------|
| **sourced_from 엣지 생성 규칙 확정** | 설계 확정 | 온톨로지 v3.6 대응 — tier 1~3 출처는 `sourced_from` 엣지 실제 생성, tier 4~5는 `SRC_ID` 속성만 사용 |
| **sourced_from 적용 노드 명시** | 설계 확정 | `vt_case`, `vt_psn`, `vt_org`, `vt_bacnt`, `vt_telno`, `vt_petition` 6개 노드에 sourced_from 엣지 생성 |
| **`linked_to` 중복 사용 명시** | 문서 | 동명 엣지가 §4.1(Petition→Case)와 §4.5(Object→Object) 두 맥락에서 사용됨을 명시 |
| §9.1 아키텍처 다이어그램 | 갱신 | SOURCE 레이어 sourced_from 방향 표기 수정, IP주소 TB_IP_MST 반영 |
| §9.2 Bridge Keys | 갱신 | sourced_from 엣지 생성 대상 6개 노드 등재 |
| §9.3 테이블 수 집계 | 갱신 | v3.5 보완 컬럼 추가 (TB_VHCL_OWNR_REL, TB_IP_MST) → 51개 확정 |
| 온톨로지 버전 참조 | 전체 갱신 | v3.5 → v3.6 |

---

### v3.5 변경 이력 (2026-04-23)

| 변경 항목 | 분류 | 내용 |
|-----------|------|------|
| **TB_VHCL_OWNR_REL** | 테이블 신규 | 차량 법적 소유/등록 관계 테이블 추가 (온톨로지 `owns_vehicle`, `registered_to` 엣지 대응) |
| **TB_IP_MST** | 테이블 신규 | IP 주소 공식 마스터 테이블 추가 — Phase 6E 7번째 (기존 "그래프 직접 관리" → RDB 마스터 승격) |
| §3.7 차량/이동 | 섹션 확장 | 2개 → 3개 (TB_VHCL_OWNR_REL 추가) |
| §3.15 객체 마스터 | 섹션 확장 | 6개 → 7개 (TB_IP_MST 추가) |
| 엣지 `similar_to` | 명칭 변경 | → `related_case` (v3.5 온톨로지 일치) |
| 엣지 `accessed_to` | 복원 | v3.3에서 제거됐던 `accessed_to` 엣지 Bridge Key 복원 |
| 엣지 `owns_vehicle` | 신규 | TB_VHCL_OWNR_REL.OWNR_TYP_CD='LEGAL' 기반 |
| 엣지 `registered_to` | 신규 | TB_VHCL_OWNR_REL.OWNR_TYP_CD='REGISTERED' 기반 |
| 엣지 `communicated_with` | 신규 | TB_TELNO_CALL_DTL / TB_CHAT_MSG 역방향 집계 Bridge Key 등재 |
| 엣지 `mentions_account` | 신규 | TB_TELNO_SMS_MSG.MNTNS_ACNT_YN / TB_CHAT_MSG.MNTNS_ACNT_YN 기반 |
| 엣지 `eg_used_device`, `eg_used_ip`, `eg_used_account` | 신규 | 디지털 도구 사용 3개 엣지 Bridge Key 등재 |
| 추론 규칙 `RecruitChainAccomplice` | 신규 | §4 추론 규칙 섹션에 등재 (RDB 직접 대응 없음, 그래프 추론 전용) |
| CMN_CD INSERT | 데이터 추가 | VHCL_OWNR_TYP(3개), EDGE_TYP(owns_vehicle 등 4개) 추가 |
| 전체 테이블 수 | 변경 | 49개 → 51개 |
| 온톨로지 버전 참조 | 전체 갱신 | v3.3 → v3.5 |

---

### v3.3 변경 이력 (2026-04-15)

| 변경 항목 | 분류 | 내용 |
|-----------|------|------|
| **TB_IMPRSN_EVT** | 테이블 변경 | `TB_IMPRSN_REL`(엣지)를 `TB_IMPRSN_EVT`(이벤트 노드)로 승격 (온톨로지 v3.3 대응) |
| TB_DATA_SRC SRC_TYP_CD | 컬럼 수정 | PREPROCESSOR 타입 추가 |
| TB_DATA_SRC INSERT | 데이터 추가 | src-etri (ETRI 전처리 기관) |
| TB_DATA_INGEST_LOG | 컬럼 추가 | ACTIVITY_TYP_CD (PROV-O Activity 유형) |
| TB_INCDNT_MST | 컬럼 추가 | CRIME_METHOD_CD, CRIME_STEP_CD, RISK_LEVEL, RISK_SCORE |
| TB_PETTN_MST | 컬럼 추가 | CRIME_METHOD_CD, CRIME_STEP_CN (ETRI crime_meta 연계) |
| TB_CMN_CD INSERT | 데이터 추가 | CRIME_METHOD(10개), CRIME_STEP(6개), SRC_TYP(6개) |
| §4 Bridge Keys | 내용 추가 | Phase 6E 6개 노드 RDB FK 매핑 |
| §3.15 → §3.16 명칭 조정 | 문서 | TB_IMPRSN_EVT 섹션 추가 및 이벤트 노드 대응 변경 |

---

---

## 목차

1. [설계 배경 및 원칙](#1-설계-배경-및-원칙)
2. [전체 테이블 구조 (51개)](#2-전체-테이블-구조)
3. [도메인별 DDL 명세](#3-도메인별-ddl-명세)
   - 3.1 [소스/메타 도메인 (신규)](#31-소스메타-도메인-신규--3개)
   - 3.2 [사건/관리 도메인](#32-사건관리-도메인--2개)
   - 3.3 [진정서 도메인 (신규)](#33-진정서-도메인-신규--3개)
   - 3.4 [사람/주체 도메인](#34-사람주체-도메인--2개)
   - 3.5 [금융 도메인](#35-금융-도메인--2개)
   - 3.6 [통신 도메인](#36-통신-도메인--5개)
   - 3.7 [차량/이동 도메인](#37-차량이동-도메인--3개) ★v3.5
   - 3.8 [위치/지리 도메인](#38-위치지리-도메인--2개)
   - 3.9 [디지털 도메인](#39-디지털-도메인--4개)
   - 3.10 [OSINT 도메인 (신규)](#310-osint-도메인-신규--7개)
   - 3.11 [마약 도메인](#311-마약-도메인--2개)
   - 3.12 [사기신고 도메인](#312-사기신고-도메인--2개)
   - 3.13 [엔티티 해소 도메인 (신규)](#313-엔티티-해소-도메인-신규--2개)
   - 3.14 [공통 코드 도메인](#314-공통-코드-도메인--2개)
   - 3.15 [Phase 6E 객체 마스터 도메인](#315-객체-마스터-도메인-v35-신규-보완--7개) ★v3.5
   - 3.16 [사칭 관계 도메인](#316-사칭-관계-도메인--1개)
4. [그래프 DB 연동 경계 (Bridge Keys)](#4-그래프-db-연동-경계)
5. [공통 설계 원칙](#5-공통-설계-원칙)
6. [데이터 흐름 파이프라인](#6-데이터-흐름-파이프라인)
7. [보안 및 개인정보 처리 기준](#7-보안-및-개인정보-처리-기준)

---

## 1. 설계 배경 및 원칙

### 현재 상태 분석

| 구분 | 테이블 수 | 문제점 |
|------|-----------|--------|
| 경찰청 표준 28개 | TB_ 기반 | 진정서·OSINT·소스메타 누락 |
| CCOP 레거시 8개 | rdb_ 소문자 | 명명 비일관, 경찰청 표준 불일치 |
| **신규 추가 6개** | TB_ 기반 | 진정서(3) + OSINT(7) + 엔티티해소(2) |

### 3가지 핵심 추가 요구

```
① 진정서(Petition) — 수사 개시 전 신고 데이터 체계화
   → 전처리 기관 배치 유입 / OCR 결과 / 유사 진정서 군집

② OSINT — 더치트·VirusTotal·AbuseIPDB·WHOIS 외부 데이터
   → IP·도메인·해시·전화·계좌 각 위협 평판 별도 테이블

③ 소스 메타(Source Meta) — 모든 데이터의 출처 추적
   → vt_src 노드의 RDB 대응 테이블 (Provenance 기반)
```

### 표준화 5원칙

| 원칙 | 내용 |
|------|------|
| **P1. 통일 접두어** | 모든 테이블 `TB_` 접두어, UPPER_SNAKE_CASE |
| **P2. 접미어 규칙** | `_SN`(일련번호), `_DT`(일시), `_CD`(코드), `_NM`(명), `_CN`(내용), `_YN`(여부), `_NO`(번호), `_AMT`(금액) |
| **P3. 복합 PK 준수** | 계좌 = `BACNT_NO + BANK_CD`, 이체 = `DLNG_SN` (경찰청 표준) |
| **P4. 공통 감사 컬럼** | `REC_CREATED_DT`(Transaction Time), `UPD_DT`, `REG_USR_ID` 전 테이블 의무 |
| **P5. 개인정보 보호** | RRNO(주민번호) 암호화 저장, 평문 절대 금지; 해시 방식 선택 시 SHA-256 의무 |

---

## 2. 전체 테이블 구조

```
┌─────────────────────────────────────────────────────────────────┐
│  도메인              │  테이블명              │  GDB 대응       │
├──────────────────────┼────────────────────────┼─────────────────┤
│ [신규] 소스/메타      │ TB_DATA_SRC            │ vt_src          │
│                      │ TB_DATA_INGEST_LOG     │ (감사)          │
│                      │ TB_DATA_QUALITY_LOG    │ (감사)          │
├──────────────────────┼────────────────────────┼─────────────────┤
│ 사건/관리             │ TB_INCDNT_MST          │ vt_case         │
│                      │ TB_INCDNT_PRSN_REL     │ suspect_in 엣지 │
├──────────────────────┼────────────────────────┼─────────────────┤
│ [신규] 진정서         │ TB_PETTN_MST           │ vt_petition     │
│                      │ TB_PETTN_CLSTR         │ clusters_with   │
│                      │ TB_PETTN_PROC_LOG      │ (감사)          │
├──────────────────────┼────────────────────────┼─────────────────┤
│ 사람/주체             │ TB_PRSN                │ vt_psn          │
│                      │ TB_INST                │ vt_org          │
├──────────────────────┼────────────────────────┼─────────────────┤
│ 금융                  │ TB_FIN_BACNT           │ vt_bacnt        │
│                      │ TB_FIN_BACNT_DLNG      │ vt_transfer     │
├──────────────────────┼────────────────────────┼─────────────────┤
│ 통신                  │ TB_TELNO_MST           │ vt_telno        │
│                      │ TB_TELNO_CALL_DTL      │ vt_call         │
│                      │ TB_TELNO_SMS_MSG       │ vt_msg          │
│                      │ TB_TELNO_JOIN          │ (속성)          │
│                      │ TB_CHAT_MSG            │ vt_msg          │
├──────────────────────┼────────────────────────┼─────────────────┤
│ 차량/이동             │ TB_VHCL_MST            │ vt_vhcl         │
│                      │ TB_VHCL_LPR_EVT        │ vt_movement     │
│                      │ TB_VHCL_OWNR_REL  ★   │ owns_vehicle/   │
│                      │                        │ registered_to   │
├──────────────────────┼────────────────────────┼─────────────────┤
│ 위치/지리             │ TB_GEO_MBL_LOC_EVT     │ vt_movement     │
│                      │ TB_GEO_TRST_CARD_TRIP  │ vt_movement     │
├──────────────────────┼────────────────────────┼─────────────────┤
│ [신규] IP 마스터 ★    │ TB_IP_MST              │ vt_ip           │
├──────────────────────┼────────────────────────┼─────────────────┤
│ 디지털                │ TB_WEB_DMN             │ vt_site         │
│                      │ TB_WEB_MLGN_IDC        │ vt_site (속성)  │
│                      │ TB_SYS_LGN_EVT         │ vt_access       │
│                      │ TB_DGTL_FILE_INVNT     │ vt_file         │
├──────────────────────┼────────────────────────┼─────────────────┤
│ [신규] OSINT          │ TB_OSINT_IP_REP        │ vt_ip (속성)    │
│                      │ TB_OSINT_DMN_REP       │ vt_site (속성)  │
│                      │ TB_OSINT_HASH_REP      │ vt_file (속성)  │
│                      │ TB_OSINT_PHON_REP      │ vt_telno (속성) │
│                      │ TB_OSINT_ACNT_REP      │ vt_bacnt (속성) │
│                      │ TB_OSINT_WALLET_REP    │ vt_crypto (속성)│
│                      │ TB_OSINT_ID_REP        │ vt_id (속성)    │
├──────────────────────┼────────────────────────┼─────────────────┤
│ 마약                  │ TB_DRUG_SLANG          │ (참조)          │
│                      │ TB_DRUG_TRDE           │ vt_transfer     │
├──────────────────────┼────────────────────────┼─────────────────┤
│ 사기신고              │ TB_FRD_VCTM_RPT        │ vt_petition     │
│                      │ TB_FRD_ACNT_BLK        │ vt_bacnt (속성) │
├──────────────────────┼────────────────────────┼─────────────────┤
│ [신규] 엔티티 해소    │ TB_ENTITY_SAME_AS      │ sameAs 엣지     │
│                      │ TB_ENTITY_CONFLICT     │ contradicts 엣지│
├──────────────────────┼────────────────────────┼─────────────────┤
│ 공통 코드             │ TB_CMN_CD              │ (참조)          │
│                      │ TB_BANK_CD             │ (참조)          │
└──────────────────────┴────────────────────────┴─────────────────┘
총 51개 테이블 (경찰청 표준 28 + 신규 23)  ★ v3.5: TB_VHCL_OWNR_REL, TB_IP_MST 추가
```

---

## 3. 도메인별 DDL 명세

### 3.1 소스/메타 도메인 (신규) — 3개

**설계 의도**: 모든 데이터의 출처(Provenance)를 RDB에서 관리.
그래프 `vt_src` 노드의 영구 저장소이며, 배치 수집 이력과 품질 감사 기록.

```sql
-- ① 데이터 소스 등록 (vt_src의 RDB 대응)
CREATE TABLE TB_DATA_SRC (
    SRC_ID          VARCHAR(50)     NOT NULL,               -- 소스 ID (예: src-dutcheat)
    SRC_NM          VARCHAR(200)    NOT NULL,               -- 소스명 (예: 더치트)
    SRC_TYP_CD      VARCHAR(20)     NOT NULL,               -- 소스유형: OFFICIAL|AGENCY|PREPROCESSOR|PETITION|OSINT|REPORT
    RLBLT_TIER      SMALLINT        NOT NULL DEFAULT 5,     -- 신뢰등급 1(최고)~5(미확인)
    COLLECTOR_ID    VARCHAR(100)    NULL,                   -- 수집 시스템/수사관 ID
    COLLECTED_AT    TIMESTAMP       NULL,                   -- 최초 수집 일시
    UPDATE_CYCLE    VARCHAR(20)     NULL,                   -- daily|realtime|ondemand|batch
    CONTACT_URL     VARCHAR(500)    NULL,                   -- 소스 기관 연락처/URL
    IS_ACTIVE_YN    CHAR(1)         NOT NULL DEFAULT 'Y',  -- 활성 여부
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_DATA_SRC_PK PRIMARY KEY (SRC_ID)
);
COMMENT ON TABLE  TB_DATA_SRC IS '데이터 소스 등록 (Provenance)';
COMMENT ON COLUMN TB_DATA_SRC.RLBLT_TIER IS '1=공식수사자료, 2=기관연계, 3=전처리기관(PREPROCESSOR), 4=OSINT, 5=미확인제보';
COMMENT ON COLUMN TB_DATA_SRC.SRC_TYP_CD IS 'OFFICIAL=공식, AGENCY=기관연계, PREPROCESSOR=전처리기관(ETRI 등), PETITION=진정서, OSINT=공개인텔, REPORT=미확인제보';

-- 기본 소스 6개 초기 데이터 (v3.2: src-etri 추가)
INSERT INTO TB_DATA_SRC (SRC_ID, SRC_NM, SRC_TYP_CD, RLBLT_TIER, UPDATE_CYCLE) VALUES
  ('src-official',  '공식 수사자료',        'OFFICIAL',     1, 'ondemand'),
  ('src-kics',      'KICS 연동',            'AGENCY',       2, 'realtime'),
  ('src-fss',       '금융감독원 공유DB',     'AGENCY',       2, 'daily'),
  ('src-etri',      'ETRI 전처리 기관',      'PREPROCESSOR', 3, 'batch'),
  ('src-dutcheat',  '더치트',               'OSINT',        4, 'daily'),
  ('src-anon',      '익명 신고',            'REPORT',       5, 'ondemand');


-- ② 수집 이력 로그
CREATE TABLE TB_DATA_INGEST_LOG (
    LOG_SN          BIGSERIAL       NOT NULL,               -- 로그 일련번호
    SRC_ID          VARCHAR(50)     NOT NULL,               -- TB_DATA_SRC.SRC_ID FK
    INGEST_DT       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INGEST_TYP_CD   VARCHAR(20)     NULL,                   -- batch|realtime|manual
    ACTIVITY_TYP_CD VARCHAR(20)     NULL,                   -- ETRI PROV-O Activity: COLLECT|OCR|NER|LINK|ENRICH (v3.2 추가)
    TBL_NM          VARCHAR(100)    NULL,                   -- 대상 테이블명
    TOT_CNT         INTEGER         NULL DEFAULT 0,         -- 처리 건수
    SUCC_CNT        INTEGER         NULL DEFAULT 0,         -- 성공 건수
    FAIL_CNT        INTEGER         NULL DEFAULT 0,         -- 실패 건수
    RESULT_CD       VARCHAR(10)     NULL,                   -- SUCCESS|PARTIAL|FAIL
    ERR_MSG_CN      TEXT            NULL,                   -- 오류 내용
    CONSTRAINT TB_DATA_INGEST_LOG_PK PRIMARY KEY (LOG_SN)
);
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
```

---

### 3.2 사건/관리 도메인 — 2개

```sql
-- ① 사건 마스터 (경찰청 표준 + 그래프 연동 컬럼 추가)
CREATE TABLE TB_INCDNT_MST (
    INCDNT_NO       VARCHAR(20)     NOT NULL,               -- 사건번호 (경찰청 공식)
    FLNM            VARCHAR(50)     NULL,                   -- CCOP 내부 사건번호
    INCDNT_NM       VARCHAR(300)    NOT NULL,               -- 사건명
    INCDNT_TYP_CD   VARCHAR(6)      NULL,                   -- 사건유형코드
    OCCRN_DT        TIMESTAMP       NULL,                   -- 발생일시 (Valid Time)
    END_DT          TIMESTAMP       NULL,                   -- 종료일시
    CHRGDP_NM       VARCHAR(100)    NULL,                   -- 담당부서명
    CHRG_PLCMN_NM   VARCHAR(100)    NULL,                   -- 담당경찰관명
    PLCS_NM         VARCHAR(100)    NULL,                   -- 담당경찰서명
    INCDNT_SMRY_CN  TEXT            NULL,                   -- 사건개요내용
    DAM_AMT         NUMERIC(20,0)   NULL,                   -- 피해금액 (원)
    STATUS_CD       VARCHAR(20)     NULL DEFAULT 'OPEN',    -- OPEN|INVESTIGATING|CLOSED|SUSPENDED
    -- ETRI crime_meta / risk_meta 연계 (v3.2 추가)
    CRIME_METHOD_CD VARCHAR(30)     NULL,                   -- TB_CMN_CD(CRIME_METHOD) 참조
    CRIME_STEP_CD   VARCHAR(20)     NULL,                   -- TB_CMN_CD(CRIME_STEP) 참조
    RISK_LEVEL      SMALLINT        NULL,                   -- 위험도 1~5 (ETRI risk_meta 연계)
    RISK_SCORE      NUMERIC(5,2)    NULL,                   -- 위험 점수 0~100 (ETRI risk_score 직접 매핑)
    SRC_ID          VARCHAR(50)     NULL,                   -- TB_DATA_SRC.SRC_ID FK
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_INCDNT_MST_PK PRIMARY KEY (INCDNT_NO)
);
COMMENT ON COLUMN TB_INCDNT_MST.CRIME_METHOD_CD IS 'ETRI crime_meta 범행수법 코드. TB_CMN_CD(CD_GRP_ID=CRIME_METHOD) 참조';
COMMENT ON COLUMN TB_INCDNT_MST.RISK_LEVEL IS 'ETRI risk_meta 위험도 1(저)~5(최고)';
CREATE INDEX IDX_INCDNT_OCCRN_DT   ON TB_INCDNT_MST (OCCRN_DT);
CREATE INDEX IDX_INCDNT_TYP_CD     ON TB_INCDNT_MST (INCDNT_TYP_CD);
CREATE INDEX IDX_INCDNT_STATUS_CD  ON TB_INCDNT_MST (STATUS_CD);
CREATE INDEX IDX_INCDNT_CRIME_MTH  ON TB_INCDNT_MST (CRIME_METHOD_CD);
CREATE INDEX IDX_INCDNT_RISK       ON TB_INCDNT_MST (RISK_LEVEL);


-- ② 사건-인물 관계 (역할: 피의자/피해자/참고인)
-- 그래프의 suspect_in / victim_in / witness_in 엣지 대응
CREATE TABLE TB_INCDNT_PRSN_REL (
    REL_SN          BIGSERIAL       NOT NULL,
    INCDNT_NO       VARCHAR(20)     NOT NULL,               -- TB_INCDNT_MST FK
    PRSN_ID         VARCHAR(20)     NOT NULL,               -- TB_PRSN FK
    ROLE_CD         VARCHAR(20)     NOT NULL,               -- SUSPECT|VICTIM|WITNESS
    VALID_FROM_DT   TIMESTAMP       NULL,                   -- 관계 유효 시작 (Valid Time)
    VALID_TO_DT     TIMESTAMP       NULL,                   -- 관계 유효 종료
    CONFIDENCE      NUMERIC(4,3)    NULL DEFAULT 1.000,     -- 신뢰도 0.000~1.000
    VERIFIED_YN     CHAR(1)         NULL DEFAULT 'N',
    VERIFIED_BY     VARCHAR(50)     NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_INCDNT_PRSN_REL_PK PRIMARY KEY (REL_SN),
    CONSTRAINT TB_INCDNT_PRSN_REL_UQ UNIQUE (INCDNT_NO, PRSN_ID, ROLE_CD)
);
COMMENT ON COLUMN TB_INCDNT_PRSN_REL.ROLE_CD IS 'SUSPECT=피의자, VICTIM=피해자, WITNESS=참고인';
```

---

### 3.3 진정서 도메인 (신규) — 3개

**설계 의도**: 수사 개시 전 신고·진정을 독립 테이블로 체계화.
전처리 기관에서 OCR/NER 결과를 배치로 적재하거나 수사관이 직접 입력.
`vt_petition` 그래프 노드의 영구 저장소.

```sql
-- ① 진정서 마스터
CREATE TABLE TB_PETTN_MST (
    DCLR_SN         BIGSERIAL       NOT NULL,               -- 진정서 일련번호 (PK, 자동채번)
    PETITION_ID     VARCHAR(50)     NOT NULL,               -- CCOP 내부 ID (예: PTN-2026-00001)
    RCPT_DT         TIMESTAMP       NOT NULL,               -- 접수 일시 (Transaction Time)
    RCPT_CH_CD      VARCHAR(20)     NOT NULL,               -- 접수 채널: WEB|VISIT|EMAIL|FAX|API_112|FSS
    RCPT_PLCS_NM    VARCHAR(100)    NULL,                   -- 접수 경찰서명
    CRIME_TYP_CD    VARCHAR(6)      NULL,                   -- 죄명 코드
    CRIME_TYP_NM    VARCHAR(100)    NULL,                   -- 죄명 (자유기술)
    DAM_AMT         NUMERIC(20,0)   NULL,                   -- 피해금액 (원)
    INCDT_DT        TIMESTAMP       NULL,                   -- 피해 발생 일시 (Valid Time)
    VICTIM_NM       VARCHAR(150)    NULL,                   -- 피해자 성명
    VICTIM_CNTCT    VARCHAR(50)     NULL,                   -- 피해자 연락처
    SUMRY_CN        TEXT            NULL,                   -- 피해 내용 요약
    STATUS_CD       VARCHAR(20)     NOT NULL DEFAULT 'PENDING', -- PENDING|LINKED|REJECTED|CLOSED
    LINKED_INCDNT_NO VARCHAR(20)    NULL,                   -- 연결 사건번호 (filed_as 엣지 대응)
    -- 전처리 메타 (기관 배치 유입 시)
    PREPROC_ORG_ID  VARCHAR(50)     NULL,                   -- 전처리 기관 ID
    OCR_CONF        NUMERIC(4,3)    NULL,                   -- OCR 신뢰도 0.000~1.000
    NER_CONF        NUMERIC(4,3)    NULL,                   -- NER 신뢰도
    SCHEMA_VER      VARCHAR(20)     NULL,                   -- 전처리 표준 버전
    RAW_FILE_PATH   VARCHAR(500)    NULL,                   -- 원본 파일 경로
    -- ETRI crime_meta 연계 (v3.2 추가)
    CRIME_METHOD_CD VARCHAR(30)     NULL,                   -- TB_CMN_CD(CRIME_METHOD) 참조
    CRIME_STEP_CN   VARCHAR(200)    NULL,                   -- 범죄 단계 자유기술 (모집/이체/인출/세탁 등)
    SRC_ID          VARCHAR(50)     NULL,                   -- TB_DATA_SRC.SRC_ID FK
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_PETTN_MST_PK PRIMARY KEY (DCLR_SN),
    CONSTRAINT TB_PETTN_MST_ID_UQ UNIQUE (PETITION_ID)
);
COMMENT ON TABLE  TB_PETTN_MST IS '진정서/신고 마스터 (수사 개시 전·후 모두 존재). Bridge Key: vt_petition.raw_id→DCLR_SN';
COMMENT ON COLUMN TB_PETTN_MST.STATUS_CD IS 'PENDING=미처리, LINKED=사건연결, REJECTED=기각, CLOSED=종결';
COMMENT ON COLUMN TB_PETTN_MST.CRIME_METHOD_CD IS 'ETRI crime_meta 범행수법 코드. TB_CMN_CD(CD_GRP_ID=CRIME_METHOD) 참조';

CREATE INDEX IDX_PETTN_RCPT_DT    ON TB_PETTN_MST (RCPT_DT);
CREATE INDEX IDX_PETTN_STATUS     ON TB_PETTN_MST (STATUS_CD);
CREATE INDEX IDX_PETTN_CRIME_TYP  ON TB_PETTN_MST (CRIME_TYP_CD);
CREATE INDEX IDX_PETTN_LINKED     ON TB_PETTN_MST (LINKED_INCDNT_NO);
CREATE INDEX IDX_PETTN_CRIME_MTH  ON TB_PETTN_MST (CRIME_METHOD_CD);


-- ② 진정서 군집 (유사 진정서 연결 — clusters_with 엣지 대응)
CREATE TABLE TB_PETTN_CLSTR (
    CLSTR_SN        BIGSERIAL       NOT NULL,
    PETTN_SN_A      BIGINT          NOT NULL,               -- 진정서 A (TB_PETTN_MST FK)
    PETTN_SN_B      BIGINT          NOT NULL,               -- 진정서 B
    CLSTR_ID        VARCHAR(50)     NULL,                   -- 군집 ID (같은 군집은 동일 값)
    SIM_SCORE       NUMERIC(4,3)    NULL,                   -- 유사도 0.000~1.000
    SIM_BASIS_CD    VARCHAR(50)     NULL,                   -- 유사 근거: SAME_ACNT|SAME_PHON|SAME_IP|COMBINED
    AUTO_YN         CHAR(1)         NOT NULL DEFAULT 'Y',   -- 자동군집 여부
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_PETTN_CLSTR_PK PRIMARY KEY (CLSTR_SN),
    CONSTRAINT TB_PETTN_CLSTR_UQ UNIQUE (PETTN_SN_A, PETTN_SN_B)
);
COMMENT ON TABLE TB_PETTN_CLSTR IS '진정서 유사 군집 (clusters_with 엣지 대응)';


-- ③ 진정서 처리 이력 (상태 변경 감사)
CREATE TABLE TB_PETTN_PROC_LOG (
    LOG_SN          BIGSERIAL       NOT NULL,
    PETTN_SN        BIGINT          NOT NULL,               -- TB_PETTN_MST FK
    PROC_DT         TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PREV_STATUS_CD  VARCHAR(20)     NULL,
    NEW_STATUS_CD   VARCHAR(20)     NOT NULL,
    PROC_USR_ID     VARCHAR(50)     NULL,
    PROC_RSN_CN     TEXT            NULL,                   -- 처리 사유
    CONSTRAINT TB_PETTN_PROC_LOG_PK PRIMARY KEY (LOG_SN)
);
```

---

### 3.4 사람/주체 도메인 — 2개

```sql
-- ① 사람 마스터 (경찰청 표준 + 보안 강화)
CREATE TABLE TB_PRSN (
    PRSN_ID         VARCHAR(20)     NOT NULL,
    KORN_FLNM       VARCHAR(150)    NULL,                   -- 한글성명
    RRNO_HASH       CHAR(64)        NULL,                   -- 주민번호 SHA-256 (64자, 평문 절대 금지)
    RRNO_ENC        BYTEA           NULL,                   -- 주민번호 AES-256 암호화 (수사 목적)
    GNDR_CD         CHAR(1)         NULL,                   -- 성별 M|F|U
    NATL_CD         VARCHAR(3)      NULL,                   -- 국적 ISO 3166-1
    DOB             CHAR(8)         NULL,                   -- 생년월일 YYYYMMDD
    PSPRT_NO        VARCHAR(20)     NULL,                   -- 여권번호 (외국인)
    CNTCT           VARCHAR(50)     NULL,                   -- 주요 연락처
    RISK_LEVEL      SMALLINT        NULL DEFAULT 1,         -- 위험도 1~5
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_PRSN_PK PRIMARY KEY (PRSN_ID)
);
COMMENT ON COLUMN TB_PRSN.RRNO_HASH IS 'SHA-256 해시. 평문 주민번호 저장 절대 금지';
COMMENT ON COLUMN TB_PRSN.RRNO_ENC  IS 'AES-256 암호화. 영장 집행 시에만 복호화 허용';


-- ② 조직/기관 마스터
CREATE TABLE TB_INST (
    INST_ID         VARCHAR(20)     NOT NULL,
    INST_NM         VARCHAR(200)    NOT NULL,
    INST_SE_CD      VARCHAR(4)      NULL,                   -- BANK|TELECOM|PLATFORM|GOVT|CRIMINAL
    BRNO            VARCHAR(10)     NULL,                   -- 사업자등록번호
    BANK_CD         VARCHAR(10)     NULL,                   -- 은행코드 (금융기관인 경우)
    ADDR            VARCHAR(200)    NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_INST_PK PRIMARY KEY (INST_ID)
);
```

---

### 3.5 금융 도메인 — 2개

```sql
-- ① 금융 계좌 (복합 PK: 계좌번호 + 은행코드)
CREATE TABLE TB_FIN_BACNT (
    BACNT_NO        VARCHAR(20)     NOT NULL,               -- 계좌번호
    BANK_CD         VARCHAR(10)     NOT NULL,               -- 은행코드 (복합 PK)
    BANK_NM         VARCHAR(100)    NULL,
    DPSTR_NM        VARCHAR(100)    NULL,                   -- 예금주명
    ACNT_TYP_CD     VARCHAR(10)     NULL,                   -- 계좌유형: DEPOSIT|SAVING|INVEST|CORP
    BACNT_OPN_DT    CHAR(8)         NULL,                   -- 개설일자 YYYYMMDD
    INST_ID         VARCHAR(20)     NULL,                   -- TB_INST FK
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


-- ② 금융 거래 내역 (대용량 — 그래프에 적재하지 않고 RDB 유지)
CREATE TABLE TB_FIN_BACNT_DLNG (
    DLNG_SN         BIGSERIAL       NOT NULL,               -- 거래 일련번호 (Bridge Key → vt_transfer)
    BACNT_NO        VARCHAR(20)     NOT NULL,               -- 계좌번호
    BANK_CD         VARCHAR(10)     NOT NULL,               -- 은행코드
    DLNG_DT         TIMESTAMP       NOT NULL,               -- 거래일시 (Valid Time)
    DLNG_SE_CD      VARCHAR(10)     NOT NULL,               -- DEPOSIT|WITHDRAW|TRANSFER|ATM
    DLNG_AMT        NUMERIC(20,0)   NOT NULL,               -- 거래금액 (원)
    BLNC_AMT        NUMERIC(20,0)   NULL,                   -- 거래 후 잔액
    RLT_BACNT_NO    VARCHAR(20)     NULL,                   -- 상대 계좌번호
    RLT_BANK_CD     VARCHAR(10)     NULL,                   -- 상대 은행코드
    RLT_DPSTR_NM    VARCHAR(100)    NULL,                   -- 상대 예금주명
    DLNG_MEMO_CN    VARCHAR(500)    NULL,                   -- 거래 메모
    ATM_MNG_NO      VARCHAR(20)     NULL,                   -- ATM 관리번호 (ATM 출금 시)
    HOP_LVL         SMALLINT        NULL DEFAULT 1,         -- 자금흐름 단계
    IS_SUSPCS_YN    CHAR(1)         NULL DEFAULT 'N',       -- 의심 거래 플래그
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_FIN_BACNT_DLNG_PK PRIMARY KEY (DLNG_SN)
);
COMMENT ON TABLE TB_FIN_BACNT_DLNG IS '금융 거래 내역 (대용량. RDB 유지, Bridge Key로 그래프 연동)';
COMMENT ON COLUMN TB_FIN_BACNT_DLNG.DLNG_SN IS 'Bridge Key: vt_transfer.dlng_sn 참조';

CREATE INDEX IDX_DLNG_ACNT      ON TB_FIN_BACNT_DLNG (BACNT_NO, BANK_CD);
CREATE INDEX IDX_DLNG_DT        ON TB_FIN_BACNT_DLNG (DLNG_DT);
CREATE INDEX IDX_DLNG_RLT_ACNT  ON TB_FIN_BACNT_DLNG (RLT_BACNT_NO, RLT_BANK_CD);
CREATE INDEX IDX_DLNG_AMT       ON TB_FIN_BACNT_DLNG (DLNG_AMT);
CREATE INDEX IDX_DLNG_SUSPCS    ON TB_FIN_BACNT_DLNG (IS_SUSPCS_YN);
```

---

### 3.6 통신 도메인 — 5개

```sql
-- ① 전화번호 마스터
CREATE TABLE TB_TELNO_MST (
    TELNO           VARCHAR(20)     NOT NULL,               -- 전화번호 (정규화: 숫자만)
    COUNTRY_CD      CHAR(4)         NULL DEFAULT '+82',
    TELCO_NM        VARCHAR(50)     NULL,                   -- 통신사 (SKT|KT|LGU+|MVNO)
    JOIN_TYP_CD     VARCHAR(20)     NULL,                   -- INDIVIDUAL|CORPORATE|PREPAID
    IS_RGST_YN      CHAR(1)         NULL DEFAULT 'Y',       -- 정식 가입 여부
    IS_BRNER_YN     CHAR(1)         NULL DEFAULT 'N',       -- 선불폰/대포폰 의심
    SUBS_HLDR_NM    VARCHAR(150)    NULL,                   -- 명의자 성명
    IMSI            VARCHAR(20)     NULL,                   -- IMSI (SIM 식별)
    SPAM_CNT        INTEGER         NULL DEFAULT 0,         -- 스팸 신고 건수
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    CONSTRAINT TB_TELNO_MST_PK PRIMARY KEY (TELNO)
);
CREATE INDEX IDX_TELNO_BRNER  ON TB_TELNO_MST (IS_BRNER_YN);
CREATE INDEX IDX_TELNO_SPAM   ON TB_TELNO_MST (SPAM_CNT);


-- ② 통화 내역 (대용량 — RDB 유지)
CREATE TABLE TB_TELNO_CALL_DTL (
    CALL_SN         BIGSERIAL       NOT NULL,               -- Bridge Key → vt_call.call_sn
    DSPTCH_TELNO    VARCHAR(20)     NOT NULL,               -- 발신번호
    RCPTN_TELNO     VARCHAR(20)     NOT NULL,               -- 수신번호
    CALL_STRT_DT    TIMESTAMP       NOT NULL,               -- 통화 시작 일시 (Valid Time)
    CALL_DUR_SEC    INTEGER         NULL DEFAULT 0,         -- 통화 시간 (초)
    CALL_TYP_CD     VARCHAR(10)     NULL,                   -- VOICE|DATA|SMS_ALT
    BSST_NM         VARCHAR(100)    NULL,                   -- 기지국명
    BSST_LAT        NUMERIC(12,10)  NULL,                   -- 기지국 위도
    BSST_LOT        NUMERIC(13,10)  NULL,                   -- 기지국 경도
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_TELNO_CALL_DTL_PK PRIMARY KEY (CALL_SN)
);
COMMENT ON COLUMN TB_TELNO_CALL_DTL.CALL_SN IS 'Bridge Key: vt_call.call_sn 참조';
CREATE INDEX IDX_CALL_DSPTCH    ON TB_TELNO_CALL_DTL (DSPTCH_TELNO);
CREATE INDEX IDX_CALL_RCPTN     ON TB_TELNO_CALL_DTL (RCPTN_TELNO);
CREATE INDEX IDX_CALL_STRT_DT   ON TB_TELNO_CALL_DTL (CALL_STRT_DT);


-- ③ SMS 메시지
CREATE TABLE TB_TELNO_SMS_MSG (
    MSG_SN          BIGSERIAL       NOT NULL,
    DSPTCH_TELNO    VARCHAR(20)     NOT NULL,
    RCPTN_TELNO     VARCHAR(20)     NOT NULL,
    DSPTCH_DT       TIMESTAMP       NOT NULL,
    MSG_CN_HASH     CHAR(64)        NULL,                   -- 내용 SHA-256 (원문 저장 금지)
    IS_SPAM_YN      CHAR(1)         NULL DEFAULT 'N',
    SENTMT_CD       VARCHAR(20)     NULL,                   -- THREAT|LURE|NORMAL|UNKNOWN
    MNTNS_ACNT_YN   CHAR(1)         NULL DEFAULT 'N',       -- 계좌번호 언급 여부
    MNTNS_URL_YN    CHAR(1)         NULL DEFAULT 'N',       -- URL 포함 여부
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_TELNO_SMS_MSG_PK PRIMARY KEY (MSG_SN)
);


-- ④ 가입 정보 (통신사 제출)
CREATE TABLE TB_TELNO_JOIN (
    JOIN_SN         BIGSERIAL       NOT NULL,
    TELNO           VARCHAR(20)     NOT NULL,
    JOIN_DT         TIMESTAMP       NULL,                   -- 가입일 (Valid Time 시작)
    WTHDRW_DT       TIMESTAMP       NULL,                   -- 해지일 (Valid Time 종료)
    SUBS_HLDR_NM    VARCHAR(150)    NULL,
    SUBS_HLDR_RRNO_HASH CHAR(64)    NULL,
    TELECOM_NM      VARCHAR(50)     NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_TELNO_JOIN_PK PRIMARY KEY (JOIN_SN)
);


-- ⑤ 메신저/채팅 메시지 (카카오톡·텔레그램 등)
CREATE TABLE TB_CHAT_MSG (
    MSG_SN          BIGSERIAL       NOT NULL,
    APP_NM          VARCHAR(50)     NOT NULL,               -- KakaoTalk|Telegram|SMS|iMessage
    ROOM_ID         VARCHAR(200)    NULL,                   -- 채팅방 ID
    SENDER_ID       VARCHAR(200)    NULL,                   -- 발신자 ID/전화번호
    DSPTCH_DT       TIMESTAMP       NOT NULL,
    MSG_CN_HASH     CHAR(64)        NULL,                   -- 내용 SHA-256
    MNTNS_ACNT_YN   CHAR(1)         NULL DEFAULT 'N',
    MNTNS_URL_YN    CHAR(1)         NULL DEFAULT 'N',
    SENTMT_CD       VARCHAR(20)     NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_CHAT_MSG_PK PRIMARY KEY (MSG_SN)
);
```

---

### 3.7 차량/이동 도메인 — 3개 ★v3.5

```sql
-- ① 차량 마스터
CREATE TABLE TB_VHCL_MST (
    VHCLNO          VARCHAR(20)     NOT NULL,               -- 차량번호판
    CARMDL_NM       VARCHAR(100)    NULL,                   -- 차종명
    CARMDL_DTL_NM   VARCHAR(200)    NULL,                   -- 차명/모델명
    COLOR_NM        VARCHAR(50)     NULL,
    OWNR_NM         VARCHAR(150)    NULL,                   -- 소유자명
    RGST_DT         CHAR(8)         NULL,                   -- 등록일자
    IS_STLN_YN      CHAR(1)         NULL DEFAULT 'N',       -- 도난 여부
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_VHCL_MST_PK PRIMARY KEY (VHCLNO)
);


-- ② LPR 번호판 인식 이벤트
-- vt_movement (mov_type='lpr') Bridge Key: RCGN_SN
CREATE TABLE TB_VHCL_LPR_EVT (
    RCGN_SN         BIGSERIAL       NOT NULL,               -- Bridge Key → vt_movement.rcgn_sn
    VHCLNO          VARCHAR(20)     NOT NULL,
    RCGN_DT         TIMESTAMP       NOT NULL,               -- 인식 일시
    LAT             NUMERIC(12,10)  NULL,
    LOT             NUMERIC(13,10)  NULL,
    CCTV_ID         VARCHAR(50)     NULL,                   -- CCTV 관리 ID
    INST_LOC_NM     VARCHAR(200)    NULL,                   -- 설치 위치명
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_VHCL_LPR_EVT_PK PRIMARY KEY (RCGN_SN)
);
COMMENT ON COLUMN TB_VHCL_LPR_EVT.RCGN_SN IS 'Bridge Key: vt_movement.rcgn_sn 참조';
CREATE INDEX IDX_LPR_VHCLNO  ON TB_VHCL_LPR_EVT (VHCLNO);
CREATE INDEX IDX_LPR_RCGN_DT ON TB_VHCL_LPR_EVT (RCGN_DT);


-- ─────────────────────────────────────────────────────────────────
-- ③ 차량 소유/등록 관계 (v3.5 신규) ★
-- 그래프 owns_vehicle (법적 소유) / registered_to (차량 등록) 엣지 대응.
-- TB_VHCL_LPR_EVT(관측 이동)와 구분: 이 테이블은 법적 소유권/명의 기록.
-- Bridge Key: OWNR_TYP_CD='LEGAL' → owns_vehicle, 'REGISTERED' → registered_to
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE TB_VHCL_OWNR_REL (
    REL_SN          BIGSERIAL       NOT NULL,               -- 내부 일련번호
    VHCLNO          VARCHAR(20)     NOT NULL,               -- 차량번호 (TB_VHCL_MST FK)
    OWNR_TYP_CD     VARCHAR(20)     NOT NULL,               -- LEGAL=법적소유, REGISTERED=명의등록, DRIVER=상시운전
    PRSN_ID         VARCHAR(20)     NULL,                   -- 소유자 개인 (TB_PRSN FK, 개인인 경우)
    INST_ID         VARCHAR(20)     NULL,                   -- 소유자 법인 (TB_INST FK, 법인인 경우)
    VALID_FROM_DT   TIMESTAMP       NULL,                   -- 관계 유효 시작 (Valid Time — 등록일)
    VALID_TO_DT     TIMESTAMP       NULL,                   -- 관계 유효 종료 (양도/폐차 등)
    RGST_NO         VARCHAR(50)     NULL,                   -- 등록증 번호 (차량등록증 공식번호)
    RGST_ORG_NM     VARCHAR(100)    NULL,                   -- 등록 기관명 (시청·구청 등)
    CONFIDENCE      NUMERIC(4,3)    NULL DEFAULT 1.000,     -- 신뢰도 0.000~1.000
    VERIFIED_YN     CHAR(1)         NULL DEFAULT 'N',
    SRC_ID          VARCHAR(50)     NULL,                   -- TB_DATA_SRC.SRC_ID FK
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_VHCL_OWNR_REL_PK PRIMARY KEY (REL_SN),
    CONSTRAINT TB_VHCL_OWNR_REL_CHK CHECK (PRSN_ID IS NOT NULL OR INST_ID IS NOT NULL)
);
COMMENT ON TABLE  TB_VHCL_OWNR_REL IS '차량 소유/등록 관계 (v3.5 신규). owns_vehicle(법적소유) / registered_to(명의등록) 엣지 대응';
COMMENT ON COLUMN TB_VHCL_OWNR_REL.OWNR_TYP_CD IS 'LEGAL=법적소유(owns_vehicle), REGISTERED=명의등록(registered_to), DRIVER=상시운전자';
COMMENT ON COLUMN TB_VHCL_OWNR_REL.PRSN_ID IS 'TB_PRSN FK. PRSN_ID와 INST_ID 중 하나는 반드시 NOT NULL';
COMMENT ON COLUMN TB_VHCL_OWNR_REL.INST_ID IS 'TB_INST FK. 법인 소유 차량인 경우 사용';
CREATE INDEX IDX_VHCL_OWNR_VHCLNO   ON TB_VHCL_OWNR_REL (VHCLNO);
CREATE INDEX IDX_VHCL_OWNR_PRSN     ON TB_VHCL_OWNR_REL (PRSN_ID);
CREATE INDEX IDX_VHCL_OWNR_INST     ON TB_VHCL_OWNR_REL (INST_ID);
CREATE INDEX IDX_VHCL_OWNR_TYP      ON TB_VHCL_OWNR_REL (OWNR_TYP_CD);
CREATE INDEX IDX_VHCL_OWNR_VALID_DT ON TB_VHCL_OWNR_REL (VALID_FROM_DT, VALID_TO_DT);
```

---

### 3.8 위치/지리 도메인 — 2개

```sql
-- ① 기지국 위치 이벤트
-- vt_movement (mov_type='cell_tower') Bridge Key: LOC_EVT_SN
CREATE TABLE TB_GEO_MBL_LOC_EVT (
    LOC_EVT_SN      BIGSERIAL       NOT NULL,               -- Bridge Key → vt_movement.loc_evt_sn
    TELNO           VARCHAR(20)     NOT NULL,
    OCCRN_DT        TIMESTAMP       NOT NULL,               -- 발생 일시
    EVT_TYP_NM      VARCHAR(50)     NULL,                   -- 발신|착신|위치등록
    BSST_NM         VARCHAR(100)    NULL,                   -- 기지국명
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


-- ② 교통카드 이동 이력
-- vt_movement (mov_type='transit_card') Bridge Key: MV_SN
CREATE TABLE TB_GEO_TRST_CARD_TRIP (
    MV_SN           BIGSERIAL       NOT NULL,               -- Bridge Key → vt_movement.mv_sn
    CARD_NO         VARCHAR(30)     NOT NULL,               -- 교통카드번호
    USE_DT          TIMESTAMP       NOT NULL,               -- 사용 일시
    TK_PNM          VARCHAR(200)    NULL,                   -- 승차장소명
    GF_PNM          VARCHAR(200)    NULL,                   -- 하차장소명
    VHCL_NO         VARCHAR(20)     NULL,                   -- 버스/택시 차량번호
    FARE_AMT        NUMERIC(10,0)   NULL,                   -- 요금
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_GEO_TRST_CARD_TRIP_PK PRIMARY KEY (MV_SN)
);
COMMENT ON COLUMN TB_GEO_TRST_CARD_TRIP.MV_SN IS 'Bridge Key: vt_movement.mv_sn 참조';
```

---

### 3.9 디지털 도메인 — 4개

```sql
-- ① 웹 도메인/URL (vt_site)
CREATE TABLE TB_WEB_DMN (
    URL_ADDR        VARCHAR(2000)   NOT NULL,               -- 전체 URL (PK)
    DMN_ADDR        VARCHAR(500)    NULL,                   -- 도메인 추출
    SITE_TYP_CD     VARCHAR(20)     NULL,                   -- phishing|malware|fraud|normal
    IS_MLGN_YN      CHAR(1)         NULL DEFAULT 'N',       -- 악성 여부
    IP_ADDR         VARCHAR(45)     NULL,                   -- 호스팅 IP
    PAGE_HASH       CHAR(64)        NULL,                   -- 페이지 SHA-256
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_WEB_DMN_PK PRIMARY KEY (URL_ADDR)
);
COMMENT ON COLUMN TB_WEB_DMN.URL_ADDR IS 'v3.0: domain → url_addr 표준화 (구 domain 컬럼 제거)';


-- ② 웹 악성 지표 (위협 정보)
CREATE TABLE TB_WEB_MLGN_IDC (
    IDC_SN          BIGSERIAL       NOT NULL,
    URL_ADDR        VARCHAR(2000)   NOT NULL,               -- TB_WEB_DMN FK
    RISK_GRD_CD     VARCHAR(10)     NOT NULL,               -- HIGH|MEDIUM|LOW
    SIGN_KWRD_CN    VARCHAR(500)    NULL,                   -- 탐지 시그니처 키워드
    DETCT_DT        TIMESTAMP       NULL,                   -- 최초 탐지 일시
    REGISTRAR_NM    VARCHAR(200)    NULL,                   -- 도메인 등록기관
    WHOIS_ORG_NM    VARCHAR(200)    NULL,
    REG_DT          TIMESTAMP       NULL,                   -- 도메인 등록일
    EXP_DT          TIMESTAMP       NULL,                   -- 만료일
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_WEB_MLGN_IDC_PK PRIMARY KEY (IDC_SN)
);


-- ③ 시스템 접속 이벤트 (vt_access)
CREATE TABLE TB_SYS_LGN_EVT (
    LGN_SN          BIGSERIAL       NOT NULL,
    IP_ADDR         VARCHAR(45)     NOT NULL,
    ACCESS_DT       TIMESTAMP       NOT NULL,
    ACTN_CD         VARCHAR(20)     NULL,                   -- GET|POST|DOWNLOAD|UPLOAD
    USER_AGENT_CN   TEXT            NULL,
    STATUS_CODE     SMALLINT        NULL,
    BYTES_SENT      BIGINT          NULL,
    BYTES_RECV      BIGINT          NULL,
    TGT_URL         VARCHAR(2000)   NULL,                   -- 접속 대상 URL
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_SYS_LGN_EVT_PK PRIMARY KEY (LGN_SN)
);
CREATE INDEX IDX_LGN_IP      ON TB_SYS_LGN_EVT (IP_ADDR);
CREATE INDEX IDX_LGN_DT      ON TB_SYS_LGN_EVT (ACCESS_DT);


-- ④ 디지털 파일 증거 목록 (vt_file)
CREATE TABLE TB_DGTL_FILE_INVNT (
    FILE_SN         BIGSERIAL       NOT NULL,
    HASH_VAL        CHAR(64)        NOT NULL,               -- SHA-256 (필수 식별자)
    FILE_NM         VARCHAR(500)    NULL,
    FILE_EXTSN_NM   VARCHAR(20)     NULL,                   -- 확장자
    FILE_SZ         BIGINT          NULL,                   -- 파일 크기 (바이트)
    FILE_PATH_CN    VARCHAR(2000)   NULL,
    CREAT_DT        TIMESTAMP       NULL,                   -- 파일 생성일시
    MDFR_DT         TIMESTAMP       NULL,                   -- 수정일시
    IS_MLGN_YN      CHAR(1)         NULL DEFAULT 'N',
    VT_SCORE_CN     VARCHAR(20)     NULL,                   -- VirusTotal 탐지율 (예: '35/72')
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_DGTL_FILE_INVNT_PK PRIMARY KEY (FILE_SN),
    CONSTRAINT TB_DGTL_FILE_HASH_UQ UNIQUE (HASH_VAL)
);
COMMENT ON COLUMN TB_DGTL_FILE_INVNT.HASH_VAL IS 'v3.0: SHA-256 단일 식별자. hash_md5 컬럼 제거';
```

---

### 3.10 OSINT 도메인 (신규) — 7개

**설계 의도**: 외부 오픈소스 정보(더치트·VirusTotal·AbuseIPDB·WHOIS·Chainalysis 등)를
경찰청 수사자료와 명확히 분리 저장. `SRC_ID`로 신뢰 등급 구분.

그래프에서는 OSINT 테이블을 직접 노드로 변환하지 않고, 해당 vt_ 노드의 속성(`abuse_score`, `is_tor`, `risk_score` 등)으로 조회해 갱신하는 방식으로 사용.

```sql
-- ① IP 평판 (AbuseIPDB, VirusTotal, Shodan 등)
CREATE TABLE TB_OSINT_IP_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    IP_ADDR         VARCHAR(45)     NOT NULL,               -- 대상 IP
    SRC_ID          VARCHAR(50)     NOT NULL,               -- 수집 소스 (src-abuseipdb 등)
    QUERY_DT        TIMESTAMP       NOT NULL,               -- 조회 일시
    IS_VPN_YN       CHAR(1)         NULL DEFAULT 'N',
    IS_TOR_YN       CHAR(1)         NULL DEFAULT 'N',
    IS_PROXY_YN     CHAR(1)         NULL DEFAULT 'N',
    IS_HOSTING_YN   CHAR(1)         NULL DEFAULT 'N',
    ABUSE_SCORE     SMALLINT        NULL,                   -- 0~100 (AbuseIPDB)
    ISP_NM          VARCHAR(200)    NULL,
    ASN_NO          VARCHAR(20)     NULL,
    COUNTRY_CD      CHAR(2)         NULL,
    RAW_JSON_CN     TEXT            NULL,                   -- 원본 API 응답 (JSON)
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_IP_REP_PK PRIMARY KEY (REP_SN),
    CONSTRAINT TB_OSINT_IP_REP_UQ UNIQUE (IP_ADDR, SRC_ID, QUERY_DT)
);
CREATE INDEX IDX_OSINT_IP_ADDR  ON TB_OSINT_IP_REP (IP_ADDR);
CREATE INDEX IDX_OSINT_IP_SCORE ON TB_OSINT_IP_REP (ABUSE_SCORE);


-- ② 도메인 평판 (WHOIS, VirusTotal, URLhaus 등)
CREATE TABLE TB_OSINT_DMN_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    DMN_ADDR        VARCHAR(500)    NOT NULL,               -- 대상 도메인
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    RISK_GRD_CD     VARCHAR(10)     NULL,                   -- HIGH|MEDIUM|LOW|UNKNOWN
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


-- ③ 파일 해시 평판 (VirusTotal)
CREATE TABLE TB_OSINT_HASH_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    HASH_VAL        CHAR(64)        NOT NULL,               -- SHA-256
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    IS_MLGN_YN      CHAR(1)         NULL DEFAULT 'N',
    DETCT_CNT       SMALLINT        NULL,                   -- 탐지 엔진 수 (예: 35)
    TOTAL_CNT       SMALLINT        NULL,                   -- 전체 엔진 수 (예: 72)
    MLGN_NM         VARCHAR(200)    NULL,                   -- 악성코드명 (대표)
    FILE_TYP_NM     VARCHAR(100)    NULL,
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_HASH_REP_PK PRIMARY KEY (REP_SN)
);
CREATE INDEX IDX_OSINT_HASH ON TB_OSINT_HASH_REP (HASH_VAL);


-- ④ 전화번호 평판 (더치트, 경찰청 스팸DB)
CREATE TABLE TB_OSINT_PHON_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    TELNO           VARCHAR(20)     NOT NULL,
    SRC_ID          VARCHAR(50)     NOT NULL,               -- src-dutcheat | src-kics-spam
    QUERY_DT        TIMESTAMP       NOT NULL,
    SPAM_CNT        INTEGER         NULL DEFAULT 0,         -- 스팸/피해 신고 건수
    CRIME_TYP_CD    VARCHAR(6)      NULL,                   -- 관련 범죄 유형
    FIRST_RPT_DT    TIMESTAMP       NULL,                   -- 최초 신고 일시
    LAST_RPT_DT     TIMESTAMP       NULL,                   -- 최근 신고 일시
    IS_CONFRMD_YN   CHAR(1)         NULL DEFAULT 'N',       -- 기관 확인 여부
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_PHON_REP_PK PRIMARY KEY (REP_SN)
);
CREATE INDEX IDX_OSINT_PHON      ON TB_OSINT_PHON_REP (TELNO);
CREATE INDEX IDX_OSINT_PHON_SPAM ON TB_OSINT_PHON_REP (SPAM_CNT);


-- ⑤ 계좌 피해 신고 (더치트, 금감원)
CREATE TABLE TB_OSINT_ACNT_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    BACNT_NO        VARCHAR(20)     NOT NULL,
    BANK_CD         VARCHAR(10)     NOT NULL,
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    RPT_CNT         INTEGER         NULL DEFAULT 0,         -- 피해 신고 건수
    TTL_DAM_AMT     NUMERIC(20,0)   NULL,                   -- 총 피해금액 (원)
    FIRST_RPT_DT    TIMESTAMP       NULL,
    LAST_RPT_DT     TIMESTAMP       NULL,
    IS_FRZNACNT_YN  CHAR(1)         NULL DEFAULT 'N',       -- 지급정지 여부
    CONFRMD_YN      CHAR(1)         NULL DEFAULT 'N',
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_ACNT_REP_PK PRIMARY KEY (REP_SN)
);
CREATE INDEX IDX_OSINT_ACNT ON TB_OSINT_ACNT_REP (BACNT_NO, BANK_CD);


-- ⑥ 가상자산 지갑 위험 (Chainalysis, 업비트 FDS 등)
CREATE TABLE TB_OSINT_WALLET_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    WALLET_ADDR     VARCHAR(200)    NOT NULL,               -- 지갑 주소
    BLOCKCHAIN_NM   VARCHAR(20)     NOT NULL,               -- BTC|ETH|USDT|XMR
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    RISK_SCORE      SMALLINT        NULL,                   -- 0~100 (체인분석)
    RISK_TYP_CD     VARCHAR(50)     NULL,                   -- dark_market|stolen|mixer|scam
    KYC_VRFY_YN     CHAR(1)         NULL DEFAULT 'N',
    TX_CNT          INTEGER         NULL,
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_WALLET_REP_PK PRIMARY KEY (REP_SN)
);
CREATE INDEX IDX_OSINT_WALLET ON TB_OSINT_WALLET_REP (WALLET_ADDR, BLOCKCHAIN_NM);


-- ⑦ 디지털 ID/계정 평판 (SNS 플랫폼, 더치트)
CREATE TABLE TB_OSINT_ID_REP (
    REP_SN          BIGSERIAL       NOT NULL,
    ID_VAL          VARCHAR(200)    NOT NULL,               -- 계정 ID/닉네임
    PLATFORM_NM     VARCHAR(100)    NOT NULL,               -- KakaoTalk|Telegram|Naver
    SRC_ID          VARCHAR(50)     NOT NULL,
    QUERY_DT        TIMESTAMP       NOT NULL,
    RPT_CNT         INTEGER         NULL DEFAULT 0,         -- 피해 신고 건수
    IS_ACTIVE_YN    CHAR(1)         NULL,                   -- 현재 활성 여부
    PROFILE_URL     VARCHAR(500)    NULL,
    RAW_JSON_CN     TEXT            NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_OSINT_ID_REP_PK PRIMARY KEY (REP_SN)
);
CREATE INDEX IDX_OSINT_ID ON TB_OSINT_ID_REP (ID_VAL, PLATFORM_NM);
```

---

### 3.11 마약 도메인 — 2개

```sql
-- ① 마약 은어 사전 (분석 참조용)
CREATE TABLE TB_DRUG_SLANG (
    SLANG_SN        BIGSERIAL       NOT NULL,
    SLANG_WRD_NM    VARCHAR(100)    NOT NULL,               -- 은어
    DRUG_TYP_CD     VARCHAR(20)     NULL,                   -- 마약 유형 코드
    DRUG_TYP_NM     VARCHAR(100)    NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_DRUG_SLANG_PK PRIMARY KEY (SLANG_SN),
    CONSTRAINT TB_DRUG_SLANG_WRD_UQ UNIQUE (SLANG_WRD_NM)
);


-- ② 마약 거래 이력
CREATE TABLE TB_DRUG_TRDE (
    TRDE_SN         BIGSERIAL       NOT NULL,
    TRDE_DT         TIMESTAMP       NULL,
    DRUG_TYP_CD     VARCHAR(20)     NULL,
    TRDE_AMT_KRW    NUMERIC(20,0)   NULL,                   -- 거래 금액 (원)
    BUYER_ID        VARCHAR(50)     NULL,
    SELLER_ID       VARCHAR(50)     NULL,
    PLATFORM_NM     VARCHAR(100)    NULL,                   -- 텔레그램|다크웹 등
    INCDNT_NO       VARCHAR(20)     NULL,                   -- 연결 사건번호
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_DRUG_TRDE_PK PRIMARY KEY (TRDE_SN)
);
```

---

### 3.12 사기신고 도메인 — 2개

```sql
-- ① 사기 피해자 신고 (vt_petition으로 그래프 변환 대상)
CREATE TABLE TB_FRD_VCTM_RPT (
    DCLR_SN         BIGSERIAL       NOT NULL,               -- Bridge Key → vt_petition.raw_id
    RCPT_DT         TIMESTAMP       NOT NULL,
    RCPT_CH_CD      VARCHAR(20)     NOT NULL,               -- WEB|VISIT|EMAIL|API_112
    VICTIM_NM       VARCHAR(150)    NULL,
    VICTIM_CNTCT    VARCHAR(50)     NULL,
    CRIME_TYP_CD    VARCHAR(6)      NULL,
    FRAUD_ACNT_NO   VARCHAR(20)     NULL,                   -- 피해 계좌번호
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


-- ② 사기 계좌 지급정지 목록
CREATE TABLE TB_FRD_ACNT_BLK (
    BLK_SN          BIGSERIAL       NOT NULL,
    BACNT_NO        VARCHAR(20)     NOT NULL,
    BANK_CD         VARCHAR(10)     NOT NULL,
    BLK_DT          TIMESTAMP       NOT NULL,               -- 지급정지 일시 (Valid Time 시작)
    UNBLK_DT        TIMESTAMP       NULL,                   -- 해제 일시
    BLK_RSN_CD      VARCHAR(20)     NULL,                   -- FRAUD|INVESTIGATE|COURT
    INCDNT_NO       VARCHAR(20)     NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_FRD_ACNT_BLK_PK PRIMARY KEY (BLK_SN)
);
```

---

### 3.13 엔티티 해소 도메인 (신규) — 2개

**설계 의도**: 그래프의 `sameAs` / `contradicts` 엣지를 RDB에서도 관리.
수사관 검토 워크플로우 지원. 엔티티 해소 결과의 감사 이력 보존.

```sql
-- ① 동일 인물 해소 (sameAs 엣지 대응)
CREATE TABLE TB_ENTITY_SAME_AS (
    MATCH_SN        BIGSERIAL       NOT NULL,
    PRSN_ID_A       VARCHAR(20)     NOT NULL,               -- TB_PRSN FK
    PRSN_ID_B       VARCHAR(20)     NOT NULL,
    MATCH_SCORE     NUMERIC(4,3)    NOT NULL,               -- 유사도 0.000~1.000
    MATCH_BASIS_CD  VARCHAR(100)    NOT NULL,               -- SAME_PHONE|SAME_ACNT|SAME_IP|COMBINED
    REVIEW_STATUS_CD VARCHAR(20)    NOT NULL DEFAULT 'PENDING', -- PENDING|CONFIRMED|REJECTED
    AUTO_YN         CHAR(1)         NOT NULL DEFAULT 'Y',   -- 자동탐지 여부
    REVIEWER_ID     VARCHAR(50)     NULL,                   -- 검토 수사관 ID
    REVIEW_DT       TIMESTAMP       NULL,
    REVIEW_CMT_CN   TEXT            NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_ENTITY_SAME_AS_PK PRIMARY KEY (MATCH_SN),
    CONSTRAINT TB_ENTITY_SAME_AS_UQ UNIQUE (PRSN_ID_A, PRSN_ID_B)
);
COMMENT ON TABLE TB_ENTITY_SAME_AS IS '동일 인물 해소 후보 (sameAs 엣지 생성 전 검토 테이블)';
CREATE INDEX IDX_SAMEAS_STATUS ON TB_ENTITY_SAME_AS (REVIEW_STATUS_CD);


-- ② 모순/충돌 정보 기록 (contradicts 엣지 대응)
CREATE TABLE TB_ENTITY_CONFLICT (
    CNFL_SN         BIGSERIAL       NOT NULL,
    PRSN_ID_A       VARCHAR(20)     NOT NULL,
    PRSN_ID_B       VARCHAR(20)     NOT NULL,
    CNFL_FIELD_NM   VARCHAR(100)    NULL,                   -- 충돌 필드명 (예: RRNO_HASH)
    CNFL_DTL_CN     TEXT            NULL,                   -- 충돌 상세 내용
    CNFL_TYP_CD     VARCHAR(30)     NULL,                   -- ID_THEFT|DATA_ERROR|ALIAS
    RESOLVED_YN     CHAR(1)         NULL DEFAULT 'N',
    RESOLVED_BY     VARCHAR(50)     NULL,
    RESOLVED_DT     TIMESTAMP       NULL,
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_ENTITY_CONFLICT_PK PRIMARY KEY (CNFL_SN)
);
COMMENT ON TABLE TB_ENTITY_CONFLICT IS '인물 정보 모순 기록 (명의도용, 데이터 오류 등)';
```

---

### 3.14 공통 코드 도메인 — 2개

```sql
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

-- 주요 코드 그룹 데이터
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
  -- 소스 타입 (v3.2 추가)
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
  ('004', 'KB국민은행'), ('020', '우리은행'), ('081', '하나은행'),
  ('088', '신한은행'), ('003', 'IBK기업은행'), ('011', 'NH농협은행'),
  ('023', 'SC제일은행'), ('032', '부산은행'), ('045', '새마을금고');
```

---

## 4. 그래프 DB 연동 경계

### RDB → Graph 변환 대상 (51개 중 26개가 직접 변환)

```
┌───────────────────────────────────────────────────────────────────┐
│  RDB 테이블               │  그래프 노드    │  변환 방식           │
├───────────────────────────┼─────────────────┼──────────────────────┤
│ TB_DATA_SRC               │ vt_src          │ 전체 변환            │
│ TB_INCDNT_MST             │ vt_case         │ 전체 변환            │
│ TB_INCDNT_PRSN_REL        │ 엣지 3종        │ suspect/victim/witness_in │
│ TB_PETTN_MST              │ vt_petition     │ 전체 변환            │
│ TB_PETTN_CLSTR            │ clusters_with   │ 엣지 변환            │
│ TB_PETTN_MST (연결)        │ filed_as        │ 엣지 변환            │
│ TB_PRSN                   │ vt_psn          │ 전체 변환            │
│ TB_INST                   │ vt_org          │ 전체 변환            │
│ TB_FIN_BACNT              │ vt_bacnt        │ 전체 변환            │
│ TB_TELNO_MST              │ vt_telno        │ 전체 변환            │
│ TB_VHCL_MST               │ vt_vhcl         │ 전체 변환            │
│ TB_WEB_DMN                │ vt_site         │ 전체 변환            │
│ TB_DGTL_FILE_INVNT        │ vt_file         │ 전체 변환            │
│ TB_IMPRSN_EVT             │ vt_impersonation│ 전체 변환            │
│ TB_VHCL_OWNR_REL ★       │ owns_vehicle 엣지│ OWNR_TYP_CD='LEGAL' │
│                           │ registered_to 엣지│OWNR_TYP_CD='REGISTERED'│
│ TB_IP_MST ★              │ vt_ip           │ 전체 변환            │
│ TB_ENTITY_SAME_AS         │ sameAs 엣지     │ CONFIRMED만 변환     │
│ TB_ENTITY_CONFLICT        │ contradicts 엣지│ RESOLVED_YN='N' 변환  │
│ TB_PETTN_CLSTR            │ clusters_with   │ SIM_SCORE>=0.7 변환  │
├───────────────────────────┼─────────────────┼──────────────────────┤
│  Phase 6E Master (v3.5)   │                 │                      │
├───────────────────────────┼─────────────────┼──────────────────────┤
│ TB_IP_MST ★              │ vt_ip           │ 전체 변환 (v3.5)     │
│ TB_DGTL_ID_MST            │ vt_id           │ 전체 변환            │
│ TB_EMAIL_MST              │ vt_email        │ 전체 변환            │
│ TB_CRYPTO_WALLET_MST      │ vt_crypto       │ 전체 변환            │
│ TB_DEV_MST                │ vt_dev          │ 전체 변환            │
│ TB_ATM_MST                │ vt_atm          │ 전체 변환            │
│ TB_LOC_MST                │ vt_loc          │ 전체 변환            │
├───────────────────────────┼─────────────────┼──────────────────────┤
│  RDB 유지 (Bridge Key)     │  그래프 연동    │                      │
├───────────────────────────┼─────────────────┼──────────────────────┤
│ TB_FIN_BACNT_DLNG         │ vt_transfer     │ 대표 건만 → DLNG_SN  │
│ TB_TELNO_CALL_DTL         │ vt_call         │ 대표 건만 → CALL_SN  │
│ TB_VHCL_LPR_EVT           │ vt_movement     │ 전체 → RCGN_SN       │
│ TB_GEO_MBL_LOC_EVT        │ vt_movement     │ 전체 → LOC_EVT_SN    │
│ TB_GEO_TRST_CARD_TRIP     │ vt_movement     │ 전체 → MV_SN         │
│ TB_FRD_VCTM_RPT           │ vt_petition     │ 전체 → DCLR_SN       │
├───────────────────────────┼─────────────────┼──────────────────────┤
│  RDB 전용 (그래프 변환 없음) │               │                      │
├───────────────────────────┼─────────────────┼──────────────────────┤
│ TB_OSINT_*_REP (7개)      │ 속성 갱신       │ vt_ 노드 속성 업데이트│
│ TB_DATA_INGEST_LOG        │ 없음            │ 감사 전용             │
│ TB_DATA_QUALITY_LOG       │ 없음            │ 감사 전용             │
│ TB_PETTN_PROC_LOG         │ 없음            │ 감사 전용             │
│ TB_TELNO_SMS_MSG          │ 없음            │ 대용량, 분석 시 JOIN  │
│ TB_CHAT_MSG               │ 없음            │ 대용량, 분석 시 JOIN  │
│ TB_DRUG_SLANG             │ 없음            │ 참조 테이블           │
│ TB_CMN_CD, TB_BANK_CD     │ 없음            │ 코드 참조             │
└───────────────────────────┴─────────────────┴──────────────────────┘
```

### Bridge Key 목록 (완전판)

```sql
-- ── Event 노드 Bridge Keys ─────────────────────────────────────────
vt_transfer (PK: event_id) dlng_sn    → TB_FIN_BACNT_DLNG.DLNG_SN
vt_call (PK: event_id) call_sn        → TB_TELNO_CALL_DTL.CALL_SN
vt_access.event_id                    → TB_SYS_LGN_EVT.LGN_SN
vt_msg.event_id                       → TB_TELNO_SMS_MSG.MSG_SN
vt_movement (PK: event_id) rcgn_sn    → TB_VHCL_LPR_EVT.RCGN_SN
vt_movement (PK: event_id) loc_evt_sn → TB_GEO_MBL_LOC_EVT.LOC_EVT_SN
vt_movement (PK: event_id) mv_sn      → TB_GEO_TRST_CARD_TRIP.MV_SN

-- ── Case/Petition Bridge Keys ─────────────────────────────────────
vt_petition.raw_id      → TB_FRD_VCTM_RPT.DCLR_SN
vt_petition.petition_id → TB_PETTN_MST.PETITION_ID
vt_src.src_id           → TB_DATA_SRC.SRC_ID

-- ── Phase 6E Master Node Bridge Keys (v3.2 추가) ─────────────────
vt_id.id_val            → TB_DGTL_ID_MST.ID_SN      (Bridge: id_sn)
vt_email.email_addr     → TB_EMAIL_MST.EMAIL_SN      (Bridge: email_sn)
vt_crypto.wallet_addr   → TB_CRYPTO_WALLET_MST.WALLET_SN (Bridge: wallet_sn)
vt_dev.device_id        → TB_DEV_MST.DEV_SN          (Bridge: dev_sn)
vt_atm.atm_id           → TB_ATM_MST.ATM_MNG_NO      (Bridge: atm_mng_no)
vt_loc.loc_id           → TB_LOC_MST.LOC_SN          (Bridge: loc_sn)
```

---

## 5. 공통 설계 원칙

### 5.1 명명 규칙 (Naming Convention)

```
테이블명:   TB_{도메인}_{개체}_{유형}
            TB_FIN_BACNT_DLNG  (금융_계좌_거래)
            TB_OSINT_IP_REP    (OSINT_IP_평판)

컬럼명 접미어:
  _SN    Serial Number   일련번호 (자동채번 PK)
  _NO    Number          번호 (외부 식별자)
  _ID    Identifier      내부 식별자 (VARCHAR)
  _NM    Name            명칭
  _CD    Code            코드 (FK or enum)
  _DT    DateTime        일시 (TIMESTAMP)
  _CN    Content         내용 (TEXT 계열)
  _AMT   Amount          금액 (NUMERIC)
  _CNT   Count           건수 (INTEGER)
  _YN    Yes/No          여부 (CHAR(1) 'Y'/'N')
  _HASH  Hash            해시값 (CHAR(64) SHA-256)
  _ENC   Encrypted       암호화 값 (BYTEA)
  _SCORE Score           점수 (NUMERIC or SMALLINT)
```

### 5.2 공통 컬럼 (모든 테이블 의무)

```sql
-- 전 테이블에 아래 3개 컬럼 필수
REC_CREATED_DT  TIMESTAMP  NOT NULL DEFAULT CURRENT_TIMESTAMP  -- Transaction Time
UPD_DT          TIMESTAMP  NULL                                 -- 최종 수정 일시
REG_USR_ID      VARCHAR(50) NULL                               -- 등록/수정 사용자 ID

-- OSINT·이벤트 테이블 추가
SRC_ID          VARCHAR(50) NULL    -- TB_DATA_SRC.SRC_ID FK (모든 테이블 권장)
```

### 5.3 인덱스 전략

| 기준 | 인덱스 생성 대상 |
|------|-----------------|
| 검색 빈도 높은 FK | 모든 FK 컬럼 |
| 시간 범위 쿼리 | `*_DT` 컬럼 (이체일시, 통화일시, 발생일시) |
| 금액 분석 | `DLNG_AMT`, `DAM_AMT` |
| 플래그 필터 | `IS_*_YN`, `STATUS_CD` |
| 복합 검색 | (계좌번호 + 은행코드), (IP + 조회일시) |

### 5.4 데이터 타입 매핑

| 속성 성질 | PostgreSQL 타입 | 비고 |
|-----------|----------------|------|
| 주요 식별자 | `VARCHAR(20~50)` | BIGSERIAL 대신 사용 (외부 연동 키) |
| 자동채번 PK | `BIGSERIAL` | 내부 로그·이벤트 테이블 |
| 금액 | `NUMERIC(20,0)` | 원화 기준, 외화는 별도 통화코드 |
| 위도/경도 | `NUMERIC(12,10)` / `NUMERIC(13,10)` | 소수점 10자리 |
| 신뢰도·유사도 | `NUMERIC(4,3)` | 0.000~1.000 |
| 위험점수 | `SMALLINT` | 0~100 |
| SHA-256 | `CHAR(64)` | 고정 길이 |
| 주민번호(암호화) | `BYTEA` | AES-256 |
| 긴 텍스트 | `TEXT` | 내용·요약·JSON |
| 여부 | `CHAR(1)` | 'Y'/'N', NULL=미확인 |
| URL | `VARCHAR(2000)` | 최대 URL 길이 고려 |

---

## 6. 데이터 흐름 파이프라인

```
[외부 데이터 입수]
        │
        ├── 경찰청 KICS 연동 ──────────────────────────┐
        │   (실시간 REST API / 배치)                   │
        │                                             │
        ├── 전처리 기관 배치 ─────────────────────────┤
        │   (진정서 OCR/NER 결과)                      │
        │   → TB_PETTN_MST                            │
        │                                             │
        ├── OSINT 수집기 (배치, 일 1회) ───────────────┤
        │   더치트 / AbuseIPDB / VirusTotal            │
        │   → TB_OSINT_*_REP                          │
        │                                             │
        └── 수사관 직접 입력 (Web UI) ─────────────────┤
            CSV 업로드 → rdb_service.py               │
                                                      ↓
                                            [RDB: PostgreSQL]
                                            TB_DATA_SRC ← 소스 등록
                                            TB_DATA_INGEST_LOG ← 수집 이력
                                                      │
                          ┌───────────────────────────┘
                          │ rdb_to_graph_service.py
                          │ (배치 또는 이벤트 트리거)
                          ↓
                    [Graph DB: AgensGraph]
                    vt_src → vt_case → vt_psn → vt_bacnt ...
                          │
                          │ (OSINT 속성 병합)
                          │ TB_OSINT_IP_REP → vt_ip.abuse_score 갱신
                          │ TB_OSINT_PHON_REP → vt_telno.is_burner 갱신
                          │ TB_OSINT_ACNT_REP → vt_bacnt.is_burner 갱신
                          ↓
                    [분석 서비스 / 시각화]
```

### OSINT 속성 병합 규칙

```sql
-- OSINT 데이터를 vt_ 노드 속성으로 반영하는 기준
-- (정기 배치: 매일 02:00 실행)

-- 예) IP 위험 점수 그래프 반영
UPDATE vt_ip SET abuse_score = (
    SELECT MAX(ABUSE_SCORE)
    FROM TB_OSINT_IP_REP
    WHERE IP_ADDR = vt_ip.ip_addr
      AND QUERY_DT >= NOW() - INTERVAL '7 days'
);

-- 예) 전화번호 대포폰 플래그 반영 (스팸신고 3건 이상)
UPDATE vt_telno SET is_burner = true
WHERE telno IN (
    SELECT TELNO FROM TB_OSINT_PHON_REP
    WHERE SPAM_CNT >= 3
      AND IS_CONFRMD_YN = 'Y'
);
```

---

## 7. 보안 및 개인정보 처리 기준

### 개인정보 민감도 분류

| 등급 | 컬럼 | 처리 방식 |
|------|------|----------|
| **극비** | RRNO (주민번호) | AES-256 암호화 (`RRNO_ENC`) + SHA-256 해시 (`RRNO_HASH`) 병행. 복호화는 영장 집행 기록 필수 |
| **기밀** | KORN_FLNM, CNTCT, VICTIM_NM | DB 접근 로그 의무화, 마스킹 뷰 제공 |
| **제한** | TELNO, BACNT_NO | 조회 쿼리 감사, 외부 반출 금지 |
| **내부** | URL_ADDR, IP_ADDR, HASH_VAL | 일반 접근 허용, 외부 공개 금지 |
| **공개** | CRIME_TYP_CD, STATUS_CD | 제한 없음 |

### 데이터 보존 기간

| 테이블 | 보존 기간 | 근거 |
|--------|-----------|------|
| TB_INCDNT_MST | 사건 종결 후 5년 | 형사소송법 |
| TB_FIN_BACNT_DLNG | 거래 발생 후 5년 | 금융실명법 |
| TB_TELNO_CALL_DTL | 최대 1년 | 통신비밀보호법 |
| TB_PETTN_MST | 처리 후 3년 | 민원처리법 |
| TB_OSINT_*_REP | 조회 후 90일 | 내부 규정 |
| TB_DATA_INGEST_LOG | 영구 | 감사 목적 |
| TB_ENTITY_SAME_AS | 해소 후 2년 | 내부 규정 |

### SQL Injection 방지 체크리스트

```python
# rdb_service.py 적용 기준
✅ 모든 사용자 입력은 psycopg2 parameterized query 사용
✅ graph_path 화이트리스트 검증: r'^[a-zA-Z_][a-zA-Z0-9_]*$'
✅ 동적 테이블명은 허용 목록(allowlist)에서만 선택
✅ OSINT API 응답은 RAW_JSON_CN에 TEXT로 저장, 절대 직접 실행 금지
✅ Bridge Key(DLNG_SN 등)는 INTEGER로 타입 강제 변환 후 사용
```

---

## 8. Phase 6E 마스터 테이블 + 사칭 관계 (7개)

> **v3.1 (2026-04-06) 확정**: v3 온톨로지 22개 노드 중
> `vt_id`, `vt_email`, `vt_crypto`, `vt_dev`, `vt_atm`, `vt_loc` 6개 노드에
> OSINT 평판 테이블은 있으나 공식 수사 마스터 테이블이 누락됨.
> 6개 마스터 + TB_IMPRSN_EVT 1개 추가로 v3.3 기준 **49개** 테이블 확정.
>
> **v3.5 (2026-04-23) 보완**: `vt_ip` 노드도 마스터 테이블 부재 확인.
> `TB_IP_MST` 추가 (Phase 6E 7번째) + `TB_VHCL_OWNR_REL` 추가 (owns_vehicle/registered_to 엣지 대응)
> → 총 **51개** 테이블 확정.

### 3.15 객체 마스터 도메인 (Phase 6E) — 7개 ★v3.5

```sql
-- ─────────────────────────────────────────────────────────────────
-- ① IP 주소 마스터 (vt_ip 대응, v3.5 신규) ★
-- v3.3까지 "그래프 직접 관리"였으나 v3.5에서 공식 마스터 테이블로 승격.
-- Bridge Key: vt_ip.ip_addr → IP_ADDR
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE TB_IP_MST (
    IP_SN           BIGSERIAL       NOT NULL,               -- 내부 일련번호
    IP_ADDR         VARCHAR(45)     NOT NULL,               -- IP 주소 (IPv4 또는 IPv6)
    IP_VER_CD       CHAR(4)         NOT NULL DEFAULT 'IPv4',-- IPv4|IPv6
    ISP_NM          VARCHAR(200)    NULL,                   -- ISP/통신사명
    ASN_NO          VARCHAR(20)     NULL,                   -- AS 번호 (예: AS4766)
    COUNTRY_CD      CHAR(2)         NULL,                   -- 국가코드 ISO 3166-1 (예: KR)
    CITY_NM         VARCHAR(100)    NULL,                   -- 도시명
    IS_VPN_YN       CHAR(1)         NULL DEFAULT 'N',       -- VPN 여부
    IS_TOR_YN       CHAR(1)         NULL DEFAULT 'N',       -- Tor 여부
    IS_PROXY_YN     CHAR(1)         NULL DEFAULT 'N',       -- 프록시 여부
    IS_HOSTING_YN   CHAR(1)         NULL DEFAULT 'N',       -- 호스팅/클라우드 여부
    ABUSE_SCORE     SMALLINT        NULL,                   -- 위험점수 0~100 (AbuseIPDB 기준)
    RISK_LEVEL      SMALLINT        NULL,                   -- 위험도 1~5
    FIRST_SEEN_DT   TIMESTAMP       NULL,                   -- 최초 관측 일시
    LAST_SEEN_DT    TIMESTAMP       NULL,                   -- 최근 관측 일시
    CONFIDENCE      NUMERIC(4,3)    NULL DEFAULT 1.000,
    VERIFIED_YN     CHAR(1)         NULL DEFAULT 'N',
    SRC_ID          VARCHAR(50)     NULL,                   -- TB_DATA_SRC.SRC_ID FK
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_IP_MST_PK PRIMARY KEY (IP_SN),
    CONSTRAINT TB_IP_MST_ADDR_UQ UNIQUE (IP_ADDR)
);
COMMENT ON TABLE  TB_IP_MST IS 'IP 주소 마스터 — vt_ip 노드 대응 (v3.5 신규, Phase 6E 7번째 마스터)';
COMMENT ON COLUMN TB_IP_MST.IP_ADDR IS 'Bridge Key: vt_ip.ip_addr 참조. TB_OSINT_IP_REP.IP_ADDR과 JOIN으로 OSINT 속성 보강';
COMMENT ON COLUMN TB_IP_MST.ABUSE_SCORE IS 'TB_OSINT_IP_REP 배치 병합값 (정기 업데이트)';
CREATE INDEX IDX_IP_COUNTRY  ON TB_IP_MST (COUNTRY_CD);
CREATE INDEX IDX_IP_ABUSE    ON TB_IP_MST (ABUSE_SCORE);
CREATE INDEX IDX_IP_RISK     ON TB_IP_MST (RISK_LEVEL);
CREATE INDEX IDX_IP_TOR      ON TB_IP_MST (IS_TOR_YN);


-- ─────────────────────────────────────────────────────────────────
-- ② 디지털 ID 마스터 (vt_id 대응)
-- 플랫폼 계정·닉네임·디지털 식별자 (구 vt_persona 흡수)
-- Bridge Key: vt_id.id_val + vt_id.platform → 복합 PK 사용
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE TB_DGTL_ID_MST (
    ID_SN           BIGSERIAL       NOT NULL,               -- 내부 일련번호
    ID_VAL          VARCHAR(200)    NOT NULL,               -- 식별자 값 (예: 'gildong99')
    PLATFORM_NM     VARCHAR(100)    NOT NULL,               -- KakaoTalk|Telegram|Instagram|Naver|...
    ID_TYP_CD       VARCHAR(30)     NULL,                   -- account_id|nickname|email_id|user_no
    PROFILE_URL     VARCHAR(500)    NULL,                   -- 프로필 URL
    IS_ACTIVE_YN    CHAR(1)         NULL DEFAULT 'Y',       -- 현재 활성 여부
    REAL_NM         VARCHAR(150)    NULL,                   -- 실명 (확인된 경우)
    CONFIDENCE      NUMERIC(4,3)    NULL DEFAULT 1.000,
    VERIFIED_YN     CHAR(1)         NULL DEFAULT 'N',
    SRC_ID          VARCHAR(50)     NULL,                   -- TB_DATA_SRC.SRC_ID FK
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_DGTL_ID_MST_PK PRIMARY KEY (ID_SN),
    CONSTRAINT TB_DGTL_ID_MST_UQ UNIQUE (ID_VAL, PLATFORM_NM)   -- 복합 유니크 (플랫폼별 ID 고유)
);
COMMENT ON TABLE  TB_DGTL_ID_MST IS '디지털 ID 마스터 — vt_id 노드 대응 (구 vt_persona 흡수)';
COMMENT ON COLUMN TB_DGTL_ID_MST.ID_VAL IS 'Bridge Key: vt_id.id_val 참조';
CREATE INDEX IDX_DGTL_ID_PLATFORM ON TB_DGTL_ID_MST (PLATFORM_NM);
CREATE INDEX IDX_DGTL_ID_ACTIVE   ON TB_DGTL_ID_MST (IS_ACTIVE_YN);


-- ─────────────────────────────────────────────────────────────────
-- ③ 이메일 주소 마스터 (vt_email 대응)
-- Bridge Key: vt_email.email_addr → EMAIL_ADDR
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE TB_EMAIL_MST (
    EMAIL_SN        BIGSERIAL       NOT NULL,
    EMAIL_ADDR      VARCHAR(320)    NOT NULL,               -- 이메일 주소 (RFC 5321 최대 320자)
    DMN_ADDR        VARCHAR(255)    NULL,                   -- 도메인 부분 (email_addr에서 추출)
    PROVIDER_NM     VARCHAR(100)    NULL,                   -- Gmail|Naver|Daum|Unknown
    IS_DISPSBL_YN   CHAR(1)         NULL DEFAULT 'N',       -- 일회용 이메일 여부
    IS_VALID_YN     CHAR(1)         NULL DEFAULT 'Y',       -- 유효 여부 (bounce 확인 결과)
    CONFIDENCE      NUMERIC(4,3)    NULL DEFAULT 1.000,
    VERIFIED_YN     CHAR(1)         NULL DEFAULT 'N',
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_EMAIL_MST_PK PRIMARY KEY (EMAIL_SN),
    CONSTRAINT TB_EMAIL_MST_ADDR_UQ UNIQUE (EMAIL_ADDR)
);
COMMENT ON TABLE  TB_EMAIL_MST IS '이메일 주소 마스터 — vt_email 노드 대응';
COMMENT ON COLUMN TB_EMAIL_MST.EMAIL_ADDR IS 'Bridge Key: vt_email.email_addr 참조';
CREATE INDEX IDX_EMAIL_DOMAIN ON TB_EMAIL_MST (DMN_ADDR);


-- ─────────────────────────────────────────────────────────────────
-- ④ 가상자산 지갑 마스터 (vt_crypto 대응)
-- Bridge Key: vt_crypto.wallet_addr + vt_crypto.blockchain → 복합 PK
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE TB_CRYPTO_WALLET_MST (
    WALLET_SN       BIGSERIAL       NOT NULL,
    WALLET_ADDR     VARCHAR(200)    NOT NULL,               -- 지갑 주소
    BLOCKCHAIN_NM   VARCHAR(20)     NOT NULL,               -- BTC|ETH|USDT|XMR|...
    ASSET_TYP_CD    VARCHAR(20)     NULL,                   -- coin|token|nft
    EXCHANGE_NM     VARCHAR(100)    NULL,                   -- Upbit|Bithumb|Binance|...
    BALANCE         NUMERIC(30,8)   NULL,                   -- 잔액 (분석 시점)
    RISK_SCORE      SMALLINT        NULL,                   -- 0~100 체인분석 위험도
    KYC_VRFY_YN     CHAR(1)         NULL DEFAULT 'N',       -- KYC 인증 여부
    TX_CNT          INTEGER         NULL DEFAULT 0,         -- 총 트랜잭션 수
    CONFIDENCE      NUMERIC(4,3)    NULL DEFAULT 1.000,
    VERIFIED_YN     CHAR(1)         NULL DEFAULT 'N',
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_CRYPTO_WALLET_MST_PK PRIMARY KEY (WALLET_SN),
    CONSTRAINT TB_CRYPTO_WALLET_MST_UQ UNIQUE (WALLET_ADDR, BLOCKCHAIN_NM)
);
COMMENT ON TABLE  TB_CRYPTO_WALLET_MST IS '가상자산 지갑 마스터 — vt_crypto 노드 대응';
COMMENT ON COLUMN TB_CRYPTO_WALLET_MST.WALLET_ADDR IS 'Bridge Key: vt_crypto.wallet_addr 참조';
CREATE INDEX IDX_CRYPTO_BLOCKCHAIN ON TB_CRYPTO_WALLET_MST (BLOCKCHAIN_NM);
CREATE INDEX IDX_CRYPTO_RISK       ON TB_CRYPTO_WALLET_MST (RISK_SCORE);


-- ─────────────────────────────────────────────────────────────────
-- ⑤ 기기 마스터 (vt_dev 대응)
-- 스마트폰·PC·태블릿·IoT 기기
-- Bridge Key: vt_dev.device_id → DEVICE_ID
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE TB_DEV_MST (
    DEVICE_SN       BIGSERIAL       NOT NULL,
    DEVICE_ID       VARCHAR(100)    NOT NULL,               -- 내부 ID (자동 채번 UUID 또는 외부 ID)
    DEV_TYP_CD      VARCHAR(20)     NULL,                   -- smartphone|pc|tablet|iot|pos
    IMEI            VARCHAR(20)     NULL,                   -- IMEI (스마트폰 고유 식별)
    MAC_ADDR        VARCHAR(20)     NULL,                   -- MAC 주소
    MODEL_NM        VARCHAR(200)    NULL,                   -- 기기 모델명
    OS_NM           VARCHAR(50)     NULL,                   -- Android|iOS|Windows|Linux
    OS_VER          VARCHAR(50)     NULL,                   -- OS 버전
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_DEV_MST_PK PRIMARY KEY (DEVICE_SN),
    CONSTRAINT TB_DEV_MST_ID_UQ UNIQUE (DEVICE_ID)
);
COMMENT ON TABLE  TB_DEV_MST IS '기기 마스터 — vt_dev 노드 대응';
COMMENT ON COLUMN TB_DEV_MST.IMEI IS 'IMEI 중복 허용 (공장 초기화 후 재사용 가능)';
CREATE INDEX IDX_DEV_IMEI ON TB_DEV_MST (IMEI);
CREATE INDEX IDX_DEV_MAC  ON TB_DEV_MST (MAC_ADDR);


-- ─────────────────────────────────────────────────────────────────
-- ⑥ ATM 마스터 (vt_atm 대응)
-- Bridge Key: vt_atm.atm_id → ATM_MNG_NO
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE TB_ATM_MST (
    ATM_SN          BIGSERIAL       NOT NULL,
    ATM_MNG_NO      VARCHAR(20)     NOT NULL,               -- ATM 관리번호 (경찰청 표준 키)
    BANK_NM         VARCHAR(100)    NULL,                   -- 소속 은행명
    BANK_CD         VARCHAR(10)     NULL,                   -- 은행코드 (TB_BANK_CD FK)
    LOC_ID          VARCHAR(50)     NULL,                   -- vt_loc.loc_id 참조 (설치 위치)
    INST_ADDR       VARCHAR(300)    NULL,                   -- 설치 주소 (캐시)
    INST_LAT        NUMERIC(12,10)  NULL,                   -- 설치 위도 (캐시)
    INST_LOT        NUMERIC(13,10)  NULL,                   -- 설치 경도 (캐시)
    IS_OUTDR_YN     CHAR(1)         NULL DEFAULT 'N',       -- 실외 설치 여부
    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UPD_DT          TIMESTAMP       NULL,
    REG_USR_ID      VARCHAR(50)     NULL,
    CONSTRAINT TB_ATM_MST_PK PRIMARY KEY (ATM_SN),
    CONSTRAINT TB_ATM_MST_NO_UQ UNIQUE (ATM_MNG_NO)
);
COMMENT ON TABLE  TB_ATM_MST IS 'ATM 마스터 — vt_atm 노드 대응 (경찰청 ATM_MNG_NO 기준)';
COMMENT ON COLUMN TB_ATM_MST.ATM_MNG_NO IS 'Bridge Key: vt_atm.atm_id 참조; TB_FIN_BACNT_DLNG.ATM_MNG_NO FK';
CREATE INDEX IDX_ATM_BANK ON TB_ATM_MST (BANK_CD);


-- ─────────────────────────────────────────────────────────────────
-- ⑦ 위치 마스터 (vt_loc 대응)
-- 물리주소·좌표·기지국·CCTV 설치점을 LOC_TYP_CD로 통합
-- 기존 이벤트 테이블의 위도/경도 내장 컬럼은 캐시로 유지
-- Bridge Key: vt_loc.loc_id → LOC_ID
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE TB_LOC_MST (
    LOC_SN          BIGSERIAL       NOT NULL,
    LOC_ID          VARCHAR(50)     NOT NULL,               -- Bridge Key → vt_loc.loc_id
    LOC_TYP_CD      VARCHAR(20)     NOT NULL,               -- address|cell_tower|cctv|atm_loc|transit|poi
    ADDR_NM         VARCHAR(300)    NULL,                   -- 주소 (도로명)
    LAT             NUMERIC(12,10)  NULL,                   -- 위도
    LOT             NUMERIC(13,10)  NULL,                   -- 경도
    PLACE_NM        VARCHAR(200)    NULL,                   -- 장소명
    SIDO_NM         VARCHAR(50)     NULL,                   -- 시도명
    SIGUNGU_NM      VARCHAR(50)     NULL,                   -- 시군구명

    -- LOC_TYP_CD = 'cell_tower' 시 추가
    BSST_NM         VARCHAR(100)    NULL,                   -- 기지국명 (TB_TELNO_CALL_DTL.BSST_NM 참조)
    BSST_ADDR       VARCHAR(300)    NULL,                   -- 기지국 주소
    TELECOM_NM      VARCHAR(50)     NULL,                   -- 통신사

    -- LOC_TYP_CD = 'cctv' 시 추가
    CCTV_ID         VARCHAR(50)     NULL,                   -- CCTV 관리 ID
    CCTV_OPRT_NM    VARCHAR(100)    NULL,                   -- 운영 주체 (경찰청|지자체|민간)

    SRC_ID          VARCHAR(50)     NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_LOC_MST_PK PRIMARY KEY (LOC_SN),
    CONSTRAINT TB_LOC_MST_ID_UQ UNIQUE (LOC_ID)
);
COMMENT ON TABLE  TB_LOC_MST IS '위치 마스터 — vt_loc 노드 대응 (LOC_TYP_CD로 다목적 통합)';
COMMENT ON COLUMN TB_LOC_MST.LOC_ID IS 'Bridge Key: vt_loc.loc_id 참조';
CREATE INDEX IDX_LOC_TYP  ON TB_LOC_MST (LOC_TYP_CD);
CREATE INDEX IDX_LOC_SIDO ON TB_LOC_MST (SIDO_NM, SIGUNGU_NM);
CREATE INDEX IDX_LOC_GEO  ON TB_LOC_MST (LAT, LOT);   -- 위치 범위 쿼리용
```

### 3.16 사칭 관계 도메인 — 1개

-- ─────────────────────────────────────────────────────────────────
-- 사칭 범죄 캠페인/이벤트 (vt_impersonation 노드 대응, v3.3 개편)
-- ─────────────────────────────────────────────────────────────────
CREATE TABLE TB_IMPRSN_EVT (
    EVENT_ID        VARCHAR(50)     NOT NULL,
    IMPRSN_MTHD_CD  VARCHAR(50)     NULL,                   -- TELNO|EMAIL|ID|SITE
    FAKE_NAME       VARCHAR(100)    NULL,                   -- 사칭 가명 (예: 김민수 검사)
    SCRIPT_TYP      VARCHAR(50)     NULL,                   -- 보이스피싱 시나리오 등
    START_DT        TIMESTAMP       NULL,
    END_DT          TIMESTAMP       NULL,
    CONFIDENCE      NUMERIC(4,3)    NULL DEFAULT 1.000,
    VERIFIED_YN     CHAR(1)         NULL DEFAULT 'Y',
    SRC_ID          VARCHAR(50)     NOT NULL,
    REC_CREATED_DT  TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT TB_IMPRSN_EVT_PK PRIMARY KEY (EVENT_ID)
);
COMMENT ON TABLE TB_IMPRSN_EVT IS '보이스피싱 등 사칭 범죄 캠페인 (vt_impersonation 노드 대응)';


---

## 9. 전체 아키텍처 다이어그램 (49개 테이블 완전판)

### 9.1 도메인 레이어 맵

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  CCOP RDB 아키텍처 v3.6 — 51개 테이블                                             │
│  PostgreSQL (tccopdb)  ↔  AgensGraph (그래프 DB)                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────────┐ │
│  │  [SOURCE / META] — 출처 추적 (Provenance)                                    │ │
│  │  TB_DATA_SRC ──→ vt_src                                                     │ │
│  │  TB_DATA_INGEST_LOG  (감사 전용)                                              │ │
│  │  TB_DATA_QUALITY_LOG (감사 전용)                                              │ │
│  └─────────────────────────────────────────────────────────────────────────────┘ │
│    ↑ sourced_from 엣지 (tier 1~3만 실제 생성)     SRC_ID 속성 (tier 4~5, 전 테이블) │
│    적용: vt_case, vt_psn, vt_org, vt_bacnt, vt_telno, vt_petition                │
│  ┌──────────────────────────┐  ┌──────────────────────────────────────────────┐  │
│  │  [CASE LAYER]            │  │  [PERSON LAYER]                               │  │
│  │  TB_INCDNT_MST → vt_case │  │  TB_PRSN → vt_psn                            │  │
│  │  TB_INCDNT_PRSN_REL      │  │  TB_INST → vt_org                            │  │
│  │    → suspect_in/victim_in│  │                                               │  │
│  │      /witness_in (엣지)  │  │                                               │  │
│  │  TB_PETTN_MST → vt_petition│                                                │  │
│  │  TB_PETTN_CLSTR → clusters_with                                              │  │
│  │  TB_PETTN_PROC_LOG (감사) │                                                  │  │
│  └──────────────────────────┘  └──────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐    │
│  │  [OBJECT LAYER] — 11개 노드 → 11개 마스터 테이블                           │    │
│  │                                                                          │    │
│  │  금융계좌   TB_FIN_BACNT         → vt_bacnt                              │    │
│  │  전화번호   TB_TELNO_MST         → vt_telno                              │    │
│  │  IP주소     TB_IP_MST        ★★ → vt_ip      ← TB_OSINT_IP_REP 속성     │    │
│  │  사이트     TB_WEB_DMN           → vt_site    ← TB_WEB_MLGN_IDC 속성     │    │
│  │  파일       TB_DGTL_FILE_INVNT   → vt_file    ← TB_OSINT_HASH_REP 속성   │    │
│  │  디지털ID   TB_DGTL_ID_MST  ★   → vt_id      ← TB_OSINT_ID_REP 속성     │    │
│  │  차량       TB_VHCL_MST          → vt_vhcl                              │    │
│  │  이메일     TB_EMAIL_MST     ★   → vt_email                             │    │
│  │  가상자산   TB_CRYPTO_WALLET_MST ★→ vt_crypto ← TB_OSINT_WALLET_REP 속성 │    │
│  │  기기       TB_DEV_MST       ★   → vt_dev                               │    │
│  │  ATM        TB_ATM_MST       ★   → vt_atm                               │    │
│  └──────────────────────────────────────────────────────────────────────────┘    │
│                                                                                  │
│  ┌────────────────────────┐   ┌────────────────────────────────────────────┐     │
│  │  [LOCATION LAYER]      │   │  [EVENT LAYER] — RDB 대용량 보관           │     │
│  │  TB_LOC_MST ★ → vt_loc │   │                                            │     │
│  │                        │   │  이체   TB_FIN_BACNT_DLNG → vt_transfer    │     │
│  │                        │   │  통화   TB_TELNO_CALL_DTL → vt_call        │     │
│  │                        │   │  메시지 TB_TELNO_SMS_MSG  → vt_msg (SMS)   │     │
│  │                        │   │         TB_CHAT_MSG        → vt_msg (채팅)  │     │
│  │                        │   │  접속   TB_SYS_LGN_EVT    → vt_access ★    │     │
│  │                        │   │  이동   TB_VHCL_LPR_EVT   → vt_movement    │     │
│  │                        │   │         TB_GEO_MBL_LOC_EVT → vt_movement   │     │
│  │                        │   │         TB_GEO_TRST_CARD_TRIP → vt_movement │     │
│  │                        │   │  사칭   TB_IMPRSN_EVT     → vt_impersonation│     │
│  └────────────────────────┘   └────────────────────────────────────────────┘     │
│                                                                                  │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  [OSINT DOMAIN] — 외부 위협 평판 (그래프 노드 속성 갱신용)                    │  │
│  │  TB_OSINT_IP_REP / DMN_REP / HASH_REP / PHON_REP / ACNT_REP               │  │
│  │  TB_OSINT_WALLET_REP / ID_REP                                              │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  ┌──────────────────────┐  ┌─────────────────────┐  ┌────────────────────────┐  │
│  │  [ENTITY RESOLUTION] │  │  [SPECIALIZED]       │  │  [CODE TABLES]         │  │
│  │  TB_ENTITY_SAME_AS   │  │  TB_DRUG_SLANG       │  │  TB_CMN_CD             │  │
│  │  TB_ENTITY_CONFLICT  │  │  TB_DRUG_TRDE        │  │  TB_BANK_CD            │  │
│  │                      │  │  TB_FRD_VCTM_RPT     │  │                        │  │
│  │                      │  │  TB_FRD_ACNT_BLK     │  │                        │  │
│  └──────────────────────┘  └─────────────────────┘  └────────────────────────┘  │
│                                                                                  │
│  ★  = v3.1~v3.3 보완 신규 추가                                                    │
│  ★★ = v3.5 신규 (TB_IP_MST, TB_VHCL_OWNR_REL)                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 9.2 RDB ↔ Graph Bridge Key 완전판 (보완)

```sql
-- ════════ Master 테이블 (전체 변환) ════════
vt_src.src_id          → TB_DATA_SRC.SRC_ID
vt_case.flnm           → TB_INCDNT_MST.FLNM
vt_case.incdnt_no      → TB_INCDNT_MST.INCDNT_NO
vt_petition.petition_id → TB_PETTN_MST.PETITION_ID
vt_petition.raw_id     → TB_FRD_VCTM_RPT.DCLR_SN
vt_psn.psn_id          → TB_PRSN.PRSN_ID
vt_org.org_id          → TB_INST.INST_ID
vt_bacnt.account_no + bank_cd → TB_FIN_BACNT.BACNT_NO + BANK_CD
vt_telno.telno         → TB_TELNO_MST.TELNO
vt_site.url_addr       → TB_WEB_DMN.URL_ADDR
vt_file.hash_val       → TB_DGTL_FILE_INVNT.HASH_VAL
vt_vhcl.vhclno         → TB_VHCL_MST.VHCLNO
vt_id.id_val + platform → TB_DGTL_ID_MST.ID_VAL + PLATFORM_NM   ★
vt_email.email_addr    → TB_EMAIL_MST.EMAIL_ADDR                  ★
vt_crypto.wallet_addr + blockchain → TB_CRYPTO_WALLET_MST.WALLET_ADDR + BLOCKCHAIN_NM  ★
vt_dev.device_id       → TB_DEV_MST.DEVICE_ID                    ★
vt_atm.atm_id          → TB_ATM_MST.ATM_MNG_NO                   ★
vt_loc.loc_id          → TB_LOC_MST.LOC_ID                       ★

-- ════════ 이벤트 테이블 (Bridge Key 참조) ════════
vt_transfer (PK: event_id) dlng_sn    → TB_FIN_BACNT_DLNG.DLNG_SN
vt_call (PK: event_id) call_sn        → TB_TELNO_CALL_DTL.CALL_SN
vt_access (PK: event_id) lgn_sn       → TB_SYS_LGN_EVT.LGN_SN                  ★ (기존 누락)
vt_msg (PK: event_id) msg_sn          → TB_TELNO_SMS_MSG.MSG_SN                  ★ (기존 누락)
                           (또는 TB_CHAT_MSG.MSG_SN — msg_type으로 구분)
vt_movement (PK: event_id) rcgn_sn    → TB_VHCL_LPR_EVT.RCGN_SN
vt_movement (PK: event_id) loc_evt_sn → TB_GEO_MBL_LOC_EVT.LOC_EVT_SN
vt_movement (PK: event_id) mv_sn      → TB_GEO_TRST_CARD_TRIP.MV_SN

-- ════════ 엔티티 해소 ════════
vt_psn sameAs 엣지     → TB_ENTITY_SAME_AS (CONFIRMED만 그래프 반영)
vt_psn contradicts 엣지 → TB_ENTITY_CONFLICT

-- ════════ sourced_from 엣지 (v3.6 확정) ★★ ════════
-- tier 1~3 출처 노드에 한해 실제 생성: (node)-[:sourced_from]->(vt_src)
vt_case      sourced_from → TB_DATA_SRC.SRC_ID  (OFFICIAL·AGENCY 출처)
vt_psn       sourced_from → TB_DATA_SRC.SRC_ID  (OFFICIAL·AGENCY·PETITION 출처)
vt_org       sourced_from → TB_DATA_SRC.SRC_ID  (OFFICIAL·AGENCY 출처)
vt_bacnt     sourced_from → TB_DATA_SRC.SRC_ID  (OFFICIAL·AGENCY·PETITION 출처)
vt_telno     sourced_from → TB_DATA_SRC.SRC_ID  (OFFICIAL·AGENCY·PETITION 출처)
vt_petition  sourced_from → TB_DATA_SRC.SRC_ID  (PETITION·PREPROCESSOR 출처)
-- tier 4(OSINT)·tier 5(REPORT): SRC_ID 속성만 사용, 엣지 미생성

-- ★  = v3.1~v3.3 보완 신규 등재
-- ★★ = v3.5~v3.6 신규 등재
```

### 9.3 테이블 수 최종 집계

| 도메인 | 기존(v3.0) | 보완(v3.1) | v3.5 추가 | 합계 |
|--------|-----------|-----------|----------|------|
| 소스/메타 | 3 | 0 | 0 | 3 |
| 사건/관리 | 2 | 0 | 0 | 2 |
| 진정서 | 3 | 0 | 0 | 3 |
| 사람/주체 | 2 | 0 | 0 | 2 |
| 금융 | 2 | 0 | 0 | 2 |
| 통신 | 5 | 0 | 0 | 5 |
| 차량/이동 | 2 | 0 | **1** | **3** |
| 위치/지리 | 2 | 0 | 0 | 2 |
| 디지털 | 4 | 0 | 0 | 4 |
| OSINT | 7 | 0 | 0 | 7 |
| 마약 | 2 | 0 | 0 | 2 |
| 사기신고 | 2 | 0 | 0 | 2 |
| 엔티티 해소 | 2 | 0 | 0 | 2 |
| 공통 코드 | 2 | 0 | 0 | 2 |
| **객체 마스터** | 0 | **6** | **1** | **7** |
| **사칭 (신설)** | 0 | **1** | 0 | **1** |
| **합계** | **42** | **7** | **2** | **51** |

> v3.5 추가: `TB_VHCL_OWNR_REL`(차량/이동), `TB_IP_MST`(객체 마스터 7번째)

---

> **다음 단계**: `rdb_to_graph_service.py`에서 TB_PETTN_MST, TB_OSINT_*_REP 변환 로직 구현
> (OSINT 속성 병합 배치 스케줄러 포함)
