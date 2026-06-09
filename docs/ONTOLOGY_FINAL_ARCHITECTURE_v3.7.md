> ## ⚠️ DEPRECATED — V4.0 통합본 사용 권장
>
> 이 문서는 **CCOP 온톨로지 V3.7** 명세입니다. **2026-05-21부로 V4.0으로 통합되어 deprecated** 되었습니다.
>
> **현행 SSOT**: [`docs/CCOP_ONTOLOGY_V4.0.md`](CCOP_ONTOLOGY_V4.0.md)
> **코드 SSOT**: `app/middleware/services/ontology_service.py:KICSCrimeDomainOntology`
>
> V4.0은 V3.7 카탈로그(25 노드 / 53 엣지)를 그대로 유지하면서, 도메인 사용 매트릭스 / 식별자 형식 / 추론 규칙을 표준 메타로 격상한 통합본입니다. 본 문서는 **역사적 참고용**으로만 보존됩니다.
>
> ---
>

# CCOP 온톨로지 최종 아키텍처 설계서

> **버전:** v3.7 (2026-05-12 업데이트)
> **작성일:** 2026-04-06 | **최종 수정:** 2026-05-12
> **상태:** 확정 — 이 문서가 구현의 단일 기준
> **대체:** ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md (이전 버전)
> **구현 대상:** `app/middleware/services/ontology_service.py`
>
> **v3.7 변경 요약 (2026-05-12):**
> 1. `pt_cluster` 노드 신설 (CASE LAYER) — `clusters_with` 엣지 제거, 진정서 군집을 노드로 승격.
>    `(vt_petition) -[belongs_to_cluster]-> (pt_cluster)` 패턴으로 교체.
> 2. `site_cluster` 노드 신설 (OBJECT LAYER) — 동일 HTML 지문 악성사이트 군집화.
>    `(vt_site|vt_ip) -[belongs_to_cluster]-> (site_cluster)`.
> 3. `vt_psn.is_anonymous` 필드 추가 — 성명불상 피의자 명시적 관리 패턴 확정.
> 4. `used_in_device` 엣지 신설 (Phone → Device) — 불법 사설중계기·동일 기기 다번호 추적.
>    `vt_dev.dev_type`에 `relay_station` 추가.
> 5. Phone → Location 직접 엣지 **의도적 미추가 결정** — 기존 Event-mediated 패턴
>    `(vt_telno) -[recorded_in]-> (vt_movement) -[occurred_at]-> (vt_loc)` 유지.
>    이유: 시간 정보(timestamp, evt_typ_nm) 보존 + `used_in_device`와의 경로 모호성 방지.
>    위치 조회는 쿼리 패턴 §6.12로 표준화.
>
> **v3.6 변경 요약 (2026-04-23):** Source 레이어 연결 구조 확정.
> `sourced_from` 엣지 실제 생성 규칙 확정 — tier 1~3 출처는 엣지 생성, tier 4~5는 속성만 사용.
> 엣지 매트릭스 SRC 컬럼 보완. `linked_to` 동명 엣지 중복 사용 명시.
> `app/services/rdb_to_graph_service.py` sourced_from 방향 버그 문서화.
>
> **v3.5 변경 요약 (2026-04-21):** 코드 교차검증으로 발견된 10개 불일치 전량 반영.
> 노드 23개(확정), 엣지 52개(확정).

---

## 설계 결정 배경

이전 세 차례 설계(초기 KICS 4계층 → v1 진정서·OSINT → v2 경찰청 표준 통합)에서
반복적으로 등장한 핵심 문제를 하나의 아키텍처로 해소한다.

| 문제 | 원인 | 이번 해결 방식 |
|------|------|--------------|
| 출처 불명 데이터 | Provenance 레이어 없음 | `vt_src` 단일 소스 노드 + 엣지 `source_id` 의무화 |
| 추론값 = 사실 혼동 | confidence 체계 없음 | 엣지 `verified` + `confidence` 2-트랙 |
| 역할 속성 덮어쓰기 | `vt_psn.role` 속성 방식 | 역할을 엣지 타입으로 완전 이동 |
| 시간 혼동 | 단일 `created_at` | `valid_from/to` + `rec_created` 분리 |
| 노드 수 과다 | 유사 개념 중복 | 25개로 통폐합, 속성으로 분기 |
| 레이어 경계 불명 | Action/Event/Evidence 혼재 | POLE 정렬 6레이어 확정 |
| 경찰청 표준 불일치 | 독자 명명 규칙 | 주요 속성명 TB_ 기준 정렬 |
| 진정서 군집 엣지 폭발 | clusters_with P→P O(n²) | pt_cluster 노드 승격 (v3.7) |
| 악성사이트 캠페인 추적 불가 | 사이트 간 연결 없음 | site_cluster 노드 신설 (v3.7) |
| 성명불상 피의자 관리 불명확 | is_anonymous 필드 없음 | 명시적 플래그 + 운영 패턴 (v3.7) |
| 중계기·다번호 기기 추적 불가 | Phone-Device 연결 없음 | used_in_device 엣지 신설 (v3.7) |
| Phone 위치 직접 엣지 요청 | 2홉 쿼리 불편 | Event-mediated 유지 + 표준 쿼리 패턴 §6.12 (v3.7) |

---

## 목차

1. [아키텍처 원칙 (5)](#1-아키텍처-원칙)
2. [6레이어 구조 다이어그램](#2-6레이어-구조)
3. [노드 카탈로그 (25개)](#3-노드-카탈로그)
4. [엣지 카탈로그](#4-엣지-카탈로그)
5. [엣지 공통 메타속성](#5-엣지-공통-메타속성)
6. [핵심 수사 시나리오 쿼리 패턴](#6-핵심-쿼리-패턴)
7. [RDB 연동 경계](#7-rdb-연동-경계)
8. [COLUMN_PATTERNS 완전판](#8-column_patterns)
9. [INFERENCE_RULES 보완](#9-inference_rules)
10. [구현 체크리스트](#10-구현-체크리스트)

---

## 1. 아키텍처 원칙

### 원칙 1: POLE 정렬 + Case·Source 확장

```
Source(출처) → Case(사건) → Person(행위자) → Object(객체) → Location(위치) → Event(행위)
```
모든 노드는 이 6레이어 중 하나에 속한다. 레이어 간 관계 방향은 단방향으로 정의하며,
역방향이 필요한 경우 별도 역관계 엣지를 명시한다.

### 원칙 2: 노드 수 최소화, 속성으로 분기

- 유사 개념은 하나의 노드 타입으로 통합하고 `_type` 속성으로 구분
- 예) `vt_lpr_evt` + `vt_loc_evt` → `vt_movement` (`mov_type: 'lpr'|'cell'|'transit'`)
- 군집(cluster)은 엣지가 아닌 노드로 표현 → pt_cluster, site_cluster (v3.7)

### 원칙 3: 사실과 주장의 명시적 분리

```
verified = True  → 수사관 직접 확인 또는 공식 문서
verified = False → 진정서 / OSINT / NER 추출 (추가 검증 필요)
confidence ∈ [0,1] → 소스 신뢰도 기반 수치화
```
`vt_assertion` 노드는 구현 복잡도 대비 효과가 낮아 제외.
엣지 속성으로 동등한 표현력 확보.

### 원칙 4: 선택적 이중시간 (Pragmatic Bitemporal)

모든 엣지에 `rec_created` (기록 시점) 의무화.
소유·관계 엣지에만 `valid_from/valid_to` (현실 유효기간) 추가.
이벤트 노드의 `timestamp`가 Valid Time 역할을 담당.

### 원칙 5: 이벤트는 노드로, 관계는 엣지로

```
# 다중 발생 가능한 이벤트 → 노드
(vt_bacnt:A) -[from_account]-> (vt_transfer) -[to_account]-> (vt_bacnt:B)

# 단일 귀속 관계 → 엣지
(vt_psn:홍길동) -[has_account {valid_from, verified}]-> (vt_bacnt:A)
```

---

## 2. 6레이어 구조

```
╔══════════════════════════════════════════════════════════════════════╗
║  SOURCE LAYER — 데이터 출처 (수직 관통, 모든 엣지가 참조)              ║
║                                                                      ║
║  vt_src   소스 기관/채널                                              ║
║  Tier 1:공식수사자료  2:기관연계  3:전처리진정서  4:OSINT  5:미확인제보  ║
╠══════════════════════════════════════════════════════════════════════╣
║  CASE LAYER — 수사 맥락                                               ║
║                                                                      ║
║  vt_case      수사 사건 (수사 개시 후)                                 ║
║  vt_petition  진정서/신고 (수사 개시 전·후 모두)                        ║
║  pt_cluster ★ 진정서 군집 허브 (v3.7 신설)                            ║
╠══════════════════════════════════════════════════════════════════════╣
║  PERSON LAYER (POLE-P) — 행위 주체                                    ║
║                                                                      ║
║  vt_psn   인물 (피의자/피해자/참고인 — 역할은 엣지로, is_anonymous★)    ║
║  vt_org   조직 (범죄단체 + 합법기관 — org_category로 분기)              ║
╠══════════════════════════════════════════════════════════════════════╣
║  OBJECT LAYER (POLE-O) — 객체·증거                                    ║
║                                                                      ║
║  vt_bacnt   금융계좌      vt_telno  전화번호    vt_ip    IP주소         ║
║  vt_site    웹사이트      vt_file   파일        vt_id    디지털ID       ║
║  vt_vhcl    차량          vt_email  이메일      vt_crypto 가상자산      ║
║  vt_dev     기기(폰/PC/중계기★)   vt_atm    ATM                       ║
║  site_cluster ★ 악성사이트 캠페인 군집 (v3.7 신설)                     ║
╠══════════════════════════════════════════════════════════════════════╣
║  LOCATION LAYER (POLE-L) — 위치                                       ║
║                                                                      ║
║  vt_loc   위치 (주소·좌표·기지국·CCTV설치점 통합)                       ║
╠══════════════════════════════════════════════════════════════════════╣
║  EVENT LAYER (POLE-E) — 시공간 행위                                    ║
║                                                                      ║
║  vt_transfer  금융이체    vt_call  통화         vt_msg   메시지         ║
║  vt_access    네트워크접속  vt_movement  이동이벤트  vt_impersonation 사칭 ║
╚══════════════════════════════════════════════════════════════════════╝

레이어 간 관계 방향 (원칙):
  Source  ← 모든 레이어 (sourced_from — 데이터 노드가 출처를 역참조)
            ※ tier 1~3: sourced_from 엣지 실제 생성 / tier 4~5: source_id 속성만 사용
  Case    ↔ Person  (사건↔인물, 역할 엣지)
  Case    → Object  (사건에 사용된 증거)
  Person  → Object  (소유/사용)
  Person  → Person  (공범/동일인물)
  Object  → Object  (이체/접속/연결/군집)
  Object  → Location (귀속 위치)
  Event   → Object  (이벤트의 주체/대상)
  Event   → Location (발생 위치)
  Petition→ pt_cluster (진정서 군집 허브 ★)
  Site/IP → site_cluster (악성사이트 캠페인 군집 ★)
```

**레이어 간 허용 엣지 매트릭스**:

```
From ↓  To →  | SRC  CASE  PSN  OBJ  LOC  EVT
──────────────┼──────────────────────────────
Source        |  -    -    -    -    -    -
Case          |  ✓    ✓    ✓    ✓    -    -
Person        |  ✓†   ✓    ✓    ✓    ✓    ✓
Object        |  ✓†   -    ✓*   ✓    ✓    ✓
Location      |  -    -    -    -    -    ✓
Event         |  ✓†   -    ✓    ✓    ✓    -

* Object → Event: used_for 전용 (vt_telno/vt_id/vt_email/vt_site → vt_impersonation)
* Event → PSN: targets 전용 (vt_impersonation → vt_org)
† sourced_from 전용 — tier 1(OFFICIAL)·tier 2(AGENCY/KICS)·tier 3(PETITION) 출처에 한해 엣지 생성.
  tier 4(OSINT)·tier 5(REPORT)는 source_id 속성만 사용 (엣지 폭발 방지).
  적용 노드: vt_case, vt_psn, vt_org, vt_bacnt, vt_telno, vt_petition
```

---

## 3. 노드 카탈로그

### 3.0 SOURCE LAYER

---
#### `vt_src` — 데이터 소스
**역할**: 모든 데이터의 출처. 수집 기관, 채널, 신뢰 등급을 표현.
한 번 생성 후 재사용 (수집 기관당 1개).

```python
{
    # 식별자
    'src_id':          str,   # 'src-dutcheat', 'src-financial-fss' 등 (필수·고유)

    # 소스 정보
    'src_name':        str,   # '더치트', '금융감독원', '경찰청 공유 DB'
    'src_type':        str,   # OFFICIAL | AGENCY | PETITION | OSINT | REPORT
    'reliability_tier': int,  # 1=최고신뢰 ~ 5=미확인 (Tier 정의 아래 참조)

    # 수집 정보
    'collector':       str,   # 수집 시스템 또는 수사관 ID
    'collected_at':    str,   # ISO8601 최초 수집 일시
    'update_cycle':    str,   # daily | realtime | ondemand | batch

    # 검증 정보
    'contact':         str,   # 소스 기관 연락처 또는 URL

    # 전처리 기관 연계 (src_type = 'PREPROCESSOR' 시 추가)
    'preprocessor_version': str,  # 전처리 표준 버전 (예: 'ETRI-v0.8')
    'activity_typ_cd': str,  # ETRI PROV-O Activity 유형 코드 (COLLECT | OCR | NER | LINK)
}
```

**reliability_tier 기준**:
```
1 — 공식 수사자료 : 영장 집행 결과, 금융거래확인서, 법원 결정문
2 — 기관 연계    : 금감원·경찰청 공유 DB, 통신사 제출 자료, KICS 연동
3 — 전처리 진정서 : OCR/NER 완료 진정서, 전처리 기관 배치 유입
4 — OSINT       : 더치트, WHOIS, VirusTotal, SNS 공개 데이터
5 — 미확인 제보  : 익명 신고, 자진 제보, 출처 불명
```

**src_type 전체 목록**:
```
OFFICIAL    — 공식 수사자료 (Tier 1)
AGENCY      — 기관 연계 (Tier 2)
PREPROCESSOR — 전처리 기관 배치 유입 (Tier 3, ETRI 등)
PETITION    — 직접 접수 진정서 (Tier 3)
OSINT       — 공개 인텔리전스 (Tier 4)
REPORT      — 미확인 제보 (Tier 5)
```

---

### 3.1 CASE LAYER

---
#### `vt_case` — 수사 사건
**역할**: 정식 수사 개시 후 생성되는 사건 레코드. `vt_petition`이 사건으로 전환되거나 수사관이 직접 생성.

```python
{
    # 식별자 (경찰청 TB_INCDNT_MST 정렬)
    'flnm':            str,   # 사건번호 (CCOP 내부, 예: 2026-CYBER-00123)
    'incdnt_no':       str,   # 경찰청 공식 사건번호 (연동 시)

    # 사건 정보
    'incdnt_nm':       str,   # 사건명
    'incdnt_typ_cd':   str,   # 사건유형코드 (VOICE_PHISHING | DRUG | FRAUD | ...)
    'crime_type':      str,   # 죄명 (자유기술)
    'occrn_dt':        str,   # 발생일시 (현실 시간 — rec_created와 구분)
    'end_dt':          str,   # 종료일시
    'damage_amount':   int,   # 피해금액 (원)

    # 담당 정보
    'chrgdp_nm':       str,   # 담당부서명
    'chrg_plcmn_nm':   str,   # 담당경찰관명
    'police_station':  str,   # 담당 경찰서

    # 진행 상태
    'status':          str,   # OPEN | INVESTIGATING | CLOSED | SUSPENDED
    'case_summary':    str,   # 사건개요 (자유기술)

    # 범죄 분석 (ETRI crime_meta / risk_meta 연계)
    'crime_method':    str,   # 범행수법 코드 (TB_CMN_CD.CRIME_METHOD_CD 참조)
    'crime_step':      str,   # 범죄 단계 (RECRUIT | TRANSFER | WITHDRAW | LAUNDER)
    'risk_level':      int,   # 위험도 1~5 (1=저, 5=최고, ETRI risk_meta 연계)
    'risk_score':      float, # 위험 점수 0~100 (ETRI risk_score 직접 매핑)

    # 메타
    'rec_created':     str,   # DB 기록 일시
    'source_id':       str,   # vt_src 참조 (항상 필수)
}
```

---
#### `vt_petition` — 진정서/신고
**역할**: 수사 개시 전·후 모두 존재. 전처리 기관에서 배치 유입되거나 수사관이 직접 입력.
`vt_case`로 전환(linked) 되거나 기각(closed) 됨.

```python
{
    # 식별자
    'petition_id':     str,   # 접수번호 (자동 채번)

    # 접수 정보
    'rcpt_dt':         str,   # 접수 일시
    'rcpt_channel':    str,   # WEB | VISIT | EMAIL | FAX | API_112 | FSS
    'rcpt_station':    str,   # 접수 경찰서

    # 사건 정보
    'crime_type_cd':   str,   # 표준 죄명 코드
    'damage_amt':      int,   # 피해금액 (원)
    'incdt_dt':        str,   # 피해 발생 일시 (= valid_from)

    # 처리 상태
    'status':          str,   # PENDING | LINKED | REJECTED | CLOSED
    'linked_case_id':  str,   # 연결된 vt_case.flnm

    # 전처리 메타 (기관 배치 유입 시)
    'preprocessed_by': str,   # 전처리 기관 ID
    'ocr_confidence':  float, # OCR 신뢰도 (자동 처리 시)
    'schema_version':  str,   # 전처리 표준 버전
    'raw_id':          int,   # RDB 원본 레코드 FK

    # 범죄 분류 (ETRI crime_meta 연계)
    'crime_method_cd': str,   # 범행수법 코드 (TB_CMN_CD.CRIME_METHOD_CD 참조)
    'crime_step_cn':   str,   # 범죄 단계 자유기술 (모집/이체/인출/세탁 등)

    # 메타
    'source_id':       str,   # vt_src 참조 (필수)
    'rec_created':     str,
}
```

---
#### `pt_cluster` — 진정서 군집 ★ v3.7 신설
**역할**: 유사 진정서들의 군집 허브 노드. v3.6의 `clusters_with` (Petition↔Petition) 엣지를 대체.
군집 자체를 노드로 승격하여 O(n²) 엣지 문제 해소 및 군집 메타데이터 관리 가능.

```python
{
    # 식별자
    'cluster_id':        str,   # 자동 채번 (예: 'ptc-2026-001')

    # 군집 정보
    'crime_type_cd':     str,   # 군집 대표 죄명 코드
    'crime_method_cd':   str,   # 군집 대표 범행수법 코드
    'sim_threshold':     float, # 군집화 적용 유사도 기준값 (0.0~1.0)
    'cluster_size':      int,   # 소속 진정서 수 (집계 캐시, 쿼리 성능용)
    'representative_id': str,   # 대표 vt_petition.petition_id

    # 군집 상태
    'cluster_status':    str,   # ACTIVE | MERGED | DISSOLVED
    'linked_case_id':    str,   # 군집이 단일 vt_case로 전환된 경우 FK

    # 메타
    'rec_created':       str,
    'last_updated':      str,
}
```

**운영 패턴**:
```cypher
-- 진정서를 군집에 소속
MATCH (p:vt_petition {petition_id: $pid})
MATCH (c:pt_cluster {cluster_id: $cid})
MERGE (p)-[r:belongs_to_cluster]->(c)
ON CREATE SET r.sim_score = $score, r.rec_created = toString(datetime())

-- 같은 군집의 모든 진정서 조회 (v3.6 clusters_with 대비 단순)
MATCH (c:pt_cluster {cluster_id: $cid})<-[:belongs_to_cluster]-(p:vt_petition)
RETURN p ORDER BY p.rcpt_dt
```

> **deprecated (v3.7)**: `clusters_with` (Petition → Petition) — 신규 생성 금지.
> 기존 DB 호환용으로 읽기만 허용.

---

### 3.2 PERSON LAYER

---
#### `vt_psn` — 인물
**역할**: 피의자·피해자·참고인 통합. 역할(Role)은 vt_case와의 엣지 타입으로 표현.
POLE 4+1 최소 기준 충족.

```python
{
    # 식별자
    'psn_id':          str,   # 내부 ID (자동 채번, UUID)

    # 인물 정보 (POLE 4+1 + 경찰청 TB_PRSN 정렬)
    'name':            str,   # 성명 (표시용, 성명불상인 경우 '성명불상')
    'korn_flnm':       str,   # 한글성명
    'dob':             str,   # 생년월일 YYYYMMDD   ← POLE 필수
    'gender':          str,   # M | F | U           ← POLE 필수
    'nationality':     str,   # 국적 (ISO 3166-1)

    # 식별자 (보안 처리)
    'rrno_hash':       str,   # 주민번호 SHA-256 (64자, 평문 절대 미저장)
    'passport_no':     str,   # 여권번호 (외국인)

    # 연락처 (POLE +1)
    'contact':         str,   # 주요 연락처

    # 수사 정보
    'aliases':         list,  # 알려진 별칭 목록 (배열)
    'risk_level':      int,   # 1~5 (1=저위험, 5=최고위험)

    # 성명불상 관리 ★ v3.7 신설
    'is_anonymous':    bool,  # True = 성명불상 (신원 미확인 피의자)
    # is_anonymous=True인 경우 name='성명불상', rrno_hash=None
    # 신원 확인 후 name·rrno_hash 업데이트, is_anonymous=False 전환

    # ⚠️ role 속성 없음 — 엣지로 표현 (suspect_in / victim_in / witness_in)

    # 메타
    'source_id':       str,   # vt_src 참조
    'rec_created':     str,
    'verified':        bool,  # 실존 인물 확인 여부
    'confidence':      float, # 0.0~1.0
}
```

**성명불상 운영 패턴** (v3.7 확정):
```
사건 개시 시
  → vt_psn 자동 생성: psn_id=UUID, name='성명불상', is_anonymous=True,
                      verified=False, confidence=0.3
  → suspect_in 엣지로 vt_case에 연결

수사 진행 중
  → 동일 전화/계좌 패턴 발견 시 EntityResolution → sameAs 엣지 생성
  → 여러 성명불상이 동일인임이 확인되면 sameAs 엣지로 병합

신원 확인 후
  → name, rrno_hash 업데이트
  → is_anonymous = False, verified = True 전환
```

> 수사관 UI: `is_anonymous=True` 필터로 미확인 피의자 일괄 조회 가능.

---
#### `vt_org` — 조직/기관
**역할**: 범죄 조직과 합법 기관(은행·통신사·플랫폼) 통합.
`org_category`로 속성 분기. 경찰청 TB_INST 정렬.

```python
{
    # 식별자
    'org_id':          str,

    # 공통 정보
    'org_name':        str,   # 조직명/기관명
    'org_category':    str,   # criminal | institution | company | government

    # institution 계열 (org_category = 'institution', TB_INST 정렬)
    'inst_se_cd':      str,   # 기관구분코드 (BANK | TELECOM | PLATFORM | GOVT)
    'brno':            str,   # 사업자등록번호
    'bank_cd':         str,   # 은행코드 (금융기관인 경우)
    'addr':            str,   # 주소

    # criminal 계열 (org_category = 'criminal')
    'member_count':    int,   # 추정 조직원 수
    'activity_type':   str,   # 활동 유형 (VOICE_PHISHING | DRUG | GAMBLING | ...)
    'hierarchy_level': str,   # 총책 | 모집책 | 인출책 | 말단

    # 메타
    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---

### 3.3 OBJECT LAYER

---
#### `vt_bacnt` — 금융계좌
```python
{
    # 식별자 (경찰청 복합 PK 정렬)
    'account_no':      str,   # 계좌번호 (필수)
    'bank_cd':         str,   # 은행코드 (필수 — account_no와 복합 키)

    # 계좌 정보
    'bank_nm':         str,   # 은행명
    'dpstr_nm':        str,   # 예금주명 (명의자)
    'account_type':    str,   # 입출금 | 적금 | 투자 | 법인
    'bacnt_opn_dt':    str,   # 개설일자 YYYYMMDD
    'inst_id':         str,   # vt_org.org_id FK (소속 금융기관)

    # 수사 분석
    'is_burner':       bool,  # 대포통장 의심
    'is_frozen':       bool,  # 지급정지 여부
    'total_received':  int,   # 총 입금액 (집계 캐시)
    'total_sent':      int,   # 총 출금액
    'transaction_cnt': int,   # 거래 건수

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---
#### `vt_telno` — 전화번호
```python
{
    'telno':           str,   # 전화번호 (정규화: 숫자만, 예: 01012345678)
    'country_code':    str,   # 국가코드 (기본 +82)
    'telco_nm':        str,   # 통신사명 (SKT | KT | LGU+ | MVNO)
    'join_typ_cd':     str,   # 가입유형 INDIVIDUAL | CORPORATE | PREPAID
    'is_registered':   bool,  # 정식 가입 여부
    'is_burner':       bool,  # 선불폰/대포폰 의심
    'subs_holder':     str,   # 명의자 이름
    'imsi':            str,   # IMSI (SIM 식별, 기기 추적용)
    'spam_cnt':        int,   # 스팸 신고 건수

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---
#### `vt_ip` — IP주소
```python
{
    'ip_addr':         str,   # IP 주소 (IPv4 또는 IPv6)
    'version':         str,   # IPv4 | IPv6
    'isp':             str,   # ISP 명
    'asn':             str,   # AS Number
    'org':             str,   # IP 등록 조직
    'country':         str,   # 국가 (ISO 2자리)
    'geo_region':      str,   # 지역 (시도)
    'city':            str,   # 도시

    # 위협 정보
    'is_vpn':          bool,
    'is_tor':          bool,  # 토르 출구 노드
    'is_proxy':        bool,
    'is_hosting':      bool,  # 클라우드/호스팅
    'abuse_score':     int,   # 0~100 (AbuseIPDB 기준)

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---
#### `vt_site` — 웹사이트/URL
```python
{
    'url_addr':        str,   # 전체 URL (필수 식별자)
    'dmn_addr':        str,   # 도메인 (url_addr에서 추출·캐시)
    'site_type':       str,   # phishing | malware | fraud | normal | unknown

    # 위험 정보 (경찰청 TB_WEB_MLGN_IDC 정렬)
    'is_malicious':    bool,
    'risk_grd':        str,   # HIGH | MEDIUM | LOW | UNKNOWN
    'sign_kwrd':       str,   # 탐지 시그니처 키워드
    'detct_dt':        str,   # 최초 탐지 일시

    # WHOIS 정보
    'registrar':       str,   # 도메인 등록기관
    'whois_org':       str,   # 등록 조직
    'reg_dt':          str,   # 도메인 등록일
    'exp_dt':          str,   # 만료일
    'page_title':      str,   # 페이지 제목
    'page_hash':       str,   # 페이지 SHA-256 해시

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---
#### `vt_file` — 파일/디지털 증거
```python
{
    # 식별자 (경찰청 TB_DGTL_FILE_INVNT 정렬)
    'hash_val':        str,   # SHA-256 해시 (64자, 필수 식별자)
    'file_nm':         str,   # 파일명
    'file_extsn_nm':   str,   # 확장자 (.exe/.pdf/.jpg 등)
    'file_sz':         int,   # 파일 크기 (바이트)
    'file_path':       str,   # 원본 경로

    # 시간 정보
    'creat_dt':        str,   # 파일 생성일시
    'mdfr_dt':         str,   # 파일 수정일시

    # 위협 분석
    'is_malicious':    bool,
    'vt_score':        str,   # VirusTotal 탐지율 (예: '35/72')

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---
#### `vt_id` — 디지털 식별자 (계정·닉네임)
**역할**: 플랫폼 계정 ID, 닉네임, 디지털 가면. 기존 `vt_persona`를 흡수·단순화.

```python
{
    'id_val':          str,   # 식별자 값 (예: 'gildong99', 'user_12345')
    'platform':        str,   # KakaoTalk | Telegram | Instagram | Naver | ...
    'id_type':         str,   # account_id | nickname | email_id | user_no
    'profile_url':     str,   # 프로필 URL
    'is_active':       bool,  # 현재 활성 여부
    'real_name':       str,   # 실명 (확인된 경우)

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---
#### `vt_vhcl` — 차량
```python
{
    'vhclno':          str,   # 차량번호 (번호판, 필수 식별자)
    'carmdl_nm':       str,   # 차종명 (경찰청 CARMDL_NM 정렬)
    'carmdl_dtl_nm':   str,   # 차명/모델명
    'color':           str,   # 차량 색상
    'ownr_nm':         str,   # 소유자명
    'rgst_dt':         str,   # 등록일자
    'stolen_yn':       bool,  # 도난 차량 여부

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---
#### `vt_email` — 이메일 주소
```python
{
    'email_addr':      str,   # 이메일 주소 (필수 식별자)
    'domain':          str,   # 도메인 부분 (email_addr에서 추출)
    'provider':        str,   # Gmail | Naver | Daum | Unknown
    'is_disposable':   bool,  # 일회용 이메일 여부

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---
#### `vt_crypto` — 가상자산 지갑
```python
{
    'wallet_addr':     str,   # 지갑 주소 (필수 식별자)
    'blockchain':      str,   # BTC | ETH | USDT | XMR | ...
    'asset_type':      str,   # coin | token | nft
    'exchange':        str,   # 연결 거래소 (Upbit | Bithumb | Binance | ...)
    'balance':         float, # 잔액 (분석 시점)
    'risk_score':      int,   # 0~100 체인분석 위험도 (Chainalysis 등)
    'kyc_verified':    bool,  # KYC 인증 여부
    'tx_cnt':          int,   # 총 트랜잭션 수

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---
#### `vt_dev` — 기기 ★ v3.7 변경
```python
{
    'device_id':       str,   # 내부 ID
    'dev_type':        str,   # smartphone | pc | tablet | iot | pos | relay_station ★
    # relay_station: 불법 사설중계기 (동일 기기에 다수 전화번호 연결)
    'imei':            str,   # IMEI (스마트폰·중계기 식별 핵심)
    'mac_addr':        str,   # MAC 주소
    'model':           str,   # 기기 모델명
    'os':              str,   # Android | iOS | Windows | Linux
    'os_version':      str,

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---
#### `vt_atm` — ATM
```python
{
    'atm_id':          str,   # ATM 관리번호 (경찰청 ATM_MNG_NO 정렬)
    'bank_nm':         str,   # 소속 은행
    'bank_cd':         str,   # 은행코드
    'loc_id':          str,   # vt_loc.loc_id 참조 (설치 위치)
    'address':         str,   # 설치 주소 (캐시)
    'is_outdoor':      bool,  # 실외 설치 여부

    'source_id':       str,
    'rec_created':     str,
}
```

---
#### `site_cluster` — 악성사이트 캠페인 군집 ★ v3.7 신설
**역할**: 도메인·IP가 달라도 동일 HTML 지문(피싱 템플릿)을 공유하는 악성사이트들의 군집 허브.
피싱 캠페인 단위 추적 및 IP 교체 대응에 필수.

```python
{
    # 식별자
    'cluster_id':      str,   # 자동 채번 (예: 'sc-2026-001')

    # 캠페인 정보
    'html_fingerprint': str,  # DOM 구조 SimHash (64bit hex) — 군집화 기준 핵심
    'phishing_type':   str,   # FINANCIAL | TELECOM | PORTAL | SHOPPING | GOVERNMENT
    'campaign_name':   str,   # 수사관 명명 (예: '카카오뱅크사칭-2026-04')

    # 시간 정보
    'first_seen':      str,   # 최초 발견일 (캠페인 시작 추정)
    'last_seen':       str,   # 최종 발견일

    # 집계 캐시 (쿼리 성능)
    'site_count':      int,   # 소속 vt_site 수
    'ip_count':        int,   # 소속 vt_ip 수

    # 상태
    'cluster_status':  str,   # ACTIVE | INACTIVE | TAKEDOWN

    # 메타
    'source_id':       str,
    'rec_created':     str,
}
```

**운영 패턴**:
```cypher
-- 새 악성사이트를 기존 캠페인 군집에 추가
MATCH (s:vt_site {url_addr: $url})
MATCH (c:site_cluster {cluster_id: $cid})
MERGE (s)-[r:belongs_to_cluster]->(c)
ON CREATE SET r.sim_score = $html_sim, r.rec_created = toString(datetime())

-- IP 교체 후에도 캠페인 추적
MATCH (c:site_cluster)<-[:belongs_to_cluster]-(n)
WHERE n:vt_site OR n:vt_ip
RETURN c.campaign_name, labels(n)[0] AS type, n
ORDER BY type
```

---

### 3.4 LOCATION LAYER

---
#### `vt_loc` — 위치
**역할**: 모든 위치 정보 통합. 물리 주소·좌표·기지국·CCTV 설치점을 `loc_type`으로 구분.
`vt_bsst`(기지국), `vt_cctv`(CCTV)는 별도 노드 없이 이 노드의 `loc_type` 속성으로 표현.

```python
{
    'loc_id':          str,   # 내부 ID (자동 채번)
    'loc_type':        str,   # address | cell_tower | cctv | atm_loc | transit | poi

    # 공통
    'address':         str,   # 주소 (도로명)
    'lat':             float, # 위도 (NUMERIC 12,10)
    'lng':             float, # 경도 (NUMERIC 13,10)
    'place_name':      str,   # 장소명
    'sido_nm':         str,   # 시도명
    'sigungu_nm':      str,   # 시군구명

    # loc_type = 'cell_tower' 시 추가
    'bsst_nm':         str,   # 기지국명 (경찰청 TB_TELNO_CALL_DTL.BSST_NM)
    'bsst_addr':       str,   # 기지국주소
    'telecom':         str,   # 통신사

    # loc_type = 'cctv' 시 추가
    'cctv_id':         str,   # CCTV 관리 ID
    'cctv_operator':   str,   # 운영 주체 (경찰청 | 지자체 | 민간)

    'source_id':       str,
    'rec_created':     str,
}
```

---

### 3.5 EVENT LAYER

---
#### `vt_transfer` — 금융 이체
```python
{
    'transfer_id':     str,   # 내부 ID
    'dlng_sn':         int,   # RDB FK (TB_FIN_BACNT_DLNG.DLNG_SN)

    # 거래 정보 (경찰청 TB_FIN_BACNT_DLNG 정렬)
    'dlng_amt':        int,   # 거래금액 (원)
    'blnc_amt':        int,   # 거래 후 잔액
    'dlng_se_cd':      str,   # 거래구분 DEPOSIT | WITHDRAW | TRANSFER | ATM
    'dlng_dt':         str,   # 거래일시 (= valid_from, 실제 발생 시간)
    'dlng_memo_cn':    str,   # 거래메모
    'trrc_psnnm':      str,   # 송수신자명
    'atm_mng_no':      str,   # ATM관리번호 (ATM 출금 시)

    # 수사 분석
    'hop_level':       int,   # 자금흐름 단계 (1=직접, N=N단계 세탁)
    'is_suspicious':   bool,  # 의심 거래 플래그

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
# 연결: (vt_bacnt) -[from_account]-> (vt_transfer) -[to_account]-> (vt_bacnt)
#       (vt_transfer) -[occurred_at]-> (vt_loc)  ← ATM 출금 시
```

---
#### `vt_call` — 통화
```python
{
    'call_id':         str,
    'call_sn':         int,   # RDB FK (TB_TELNO_CALL_DTL.CALL_SN)

    # 통화 정보 (경찰청 TB_TELNO_CALL_DTL 정렬)
    'call_strt_dt':    str,   # 통화시작일시 (= valid_from)
    'call_dur_sec':    int,   # 통화시간(초)
    'call_typ_cd':     str,   # VOICE | DATA | SMS_ALT
    'dsptch_telno':    str,   # 발신번호 (캐시)
    'rcptn_telno':     str,   # 수신번호 (캐시)
    'bsst_loc_id':     str,   # 기지국 vt_loc.loc_id 참조

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
# 연결: (vt_telno) -[caller]-> (vt_call) -[callee]-> (vt_telno)
#       (vt_call) -[occurred_at]-> (vt_loc)
```

---
#### `vt_msg` — 메시지 (SMS/채팅)
```python
{
    'msg_id':          str,
    'msg_type':        str,   # SMS | CHAT | EMAIL | PUSH

    # 메시지 정보 (경찰청 TB_TELNO_SMS_MSG + TB_CHAT_MSG 정렬)
    'app_nm':          str,   # KakaoTalk | Telegram | SMS | iMessage
    'room_id':         str,   # 채팅방 ID (단체채팅 추적)
    'dsptch_dt':       str,   # 발신일시 (= valid_from)
    'content_hash':    str,   # 메시지 내용 SHA-256 (원문 저장 금지)
    'spam_yn':         bool,  # 스팸 여부

    # NLP 분석 플래그 (자동 태깅)
    'mentions_account': bool, # 계좌번호 언급
    'mentions_url':     bool, # URL 포함
    'sentiment_cd':     str,  # THREAT | LURE | NORMAL | UNKNOWN

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
```

---
#### `vt_access` — 네트워크 접속
```python
{
    'access_id':       str,
    'access_dt':       str,   # 접속일시 (= valid_from)
    'action':          str,   # GET | POST | DOWNLOAD | UPLOAD
    'user_agent':      str,   # HTTP User-Agent
    'status_code':     int,   # HTTP 응답 코드
    'bytes_sent':      int,
    'bytes_recv':      int,

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
# 연결: (vt_ip) -[accessed_from]-> (vt_access) -[accessed_to]-> (vt_site)
```

---
#### `vt_movement` — 이동 이벤트 (통합 노드)
**역할**: LPR(번호판 인식) + 기지국 위치 + 교통카드 이동을 하나로 통합.

```python
{
    'mov_id':          str,
    'mov_type':        str,   # lpr | cell_tower | transit_card

    # 공통
    'timestamp':       str,   # 발생 일시 (= valid_from)
    'loc_id':          str,   # vt_loc.loc_id 참조 (발생 위치)

    # mov_type = 'lpr' 시 (경찰청 TB_VHCL_LPR_EVT 정렬)
    'vhclno':          str,   # 차량번호 (캐시)
    'cctv_id':         str,   # CCTV ID
    'rcgn_sn':         int,   # RDB FK

    # mov_type = 'cell_tower' 시 (경찰청 TB_GEO_MBL_LOC_EVT 정렬)
    'telno':           str,   # 전화번호 (캐시)
    'evt_typ_nm':      str,   # 발신 | 착신 | 위치등록
    'loc_evt_sn':      int,   # RDB FK

    # mov_type = 'transit_card' 시 (경찰청 TB_GEO_TRST_CARD_TRIP 정렬)
    'card_no':         str,   # 교통카드번호
    'tk_pnm':          str,   # 승차장소명
    'gf_pnm':          str,   # 하차장소명
    'vhcl_no':         str,   # 버스/택시 차량번호
    'mv_sn':           int,   # RDB FK

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
# 연결: (vt_vhcl) -[recorded_in]-> (vt_movement) -[occurred_at]-> (vt_loc)  [lpr]
#       (vt_telno) -[recorded_in]-> (vt_movement) -[occurred_at]-> (vt_loc)  [cell]
```

---
#### `vt_impersonation` — 사칭 이벤트 (V3.3 신설)
```python
{
    'event_id':        str,   # 내부 ID
    'method':          str,   # TELNO | EMAIL | ID | SITE
    'fake_name':       str,   # 사용된 사칭 가명 (예: '김민수 검사')
    'script_type':     str,   # 사칭 시나리오 종류 (예: '보이스피싱-대출사기')
    'start_dt':        str,   # 사칭 발생/확인 시작 시간 (= valid_from)
    'end_dt':          str,   # 사칭 확인 종료 시간

    'source_id':       str,
    'rec_created':     str,
    'verified':        bool,
    'confidence':      float,
}
# 연결: (Object) -[used_for]-> (vt_impersonation) -[targets]-> (vt_org)
```

---

## 4. 엣지 카탈로그

### 4.1 Case 관련 (7개)

| 엣지 | 방향 | 의미 | 주요 속성 |
|------|------|------|---------|
| `suspect_in` | Person → Case | 피의자로 관련 | confidence, verified, valid_from |
| `victim_in` | Person → Case | 피해자로 관련 | damage_amount, valid_from |
| `witness_in` | Person → Case | 참고인으로 관련 | statement_date |
| `filed_as` | Petition → Case | 진정서가 사건으로 전환 | converted_dt, converted_by |
| `related_case` | Case → Case | 사건 유사성 (공유 증거 기반, 추론) | confidence(0.75), inference=True |
| `linked_to` ⚠️ | Petition → Case | 진정서와 기존 사건 연결 | link_reason |
| `belongs_to_cluster` ★ | Petition → pt_cluster | 진정서가 군집에 소속 | sim_score, rec_created |

> ⚠️ `linked_to`는 §4.5 Object 관련에도 동일 이름으로 등재됨 (Object→Object 범용 연결).
> ★ `belongs_to_cluster`는 §4.5 site_cluster에도 동일 타입으로 재사용 (시작/끝 노드 라벨로 구분).
>
> **deprecated (v3.7)**: `clusters_with` (Petition → Petition) — 신규 생성 금지, DB 호환 읽기만 허용.

### 4.2 Case → Object 증거 연결 엣지 (3개)

| 엣지 | 방향 | 의미 | 주요 속성 |
|------|------|------|---------|
| `eg_used_account` | Case → BankAccount | 사건에 사용된 계좌 증거 | source_id, rec_created |
| `eg_used_phone` | Case → Phone | 사건에 사용된 전화번호 증거 | source_id, rec_created |
| `eg_used_ip` | Case → IP | 사건에 사용된 IP 증거 | source_id, rec_created |

### 4.3 Person 관련 (15개)

| 엣지 | 방향 | 의미 | 주요 속성 |
|------|------|------|---------|
| `has_account` | Person → BankAccount | 계좌 소유 | valid_from, valid_to, verified |
| `controls` | Person → BankAccount | 실질 지배 (명의 무관) | control_type, confidence |
| `owns_phone` | Person → Phone | 전화번호 소유/사용 | valid_from, valid_to |
| `owns_device` | Person → Device | 기기 소유/사용 | valid_from, valid_to |
| `uses_id` | Person → DigitalID | 플랫폼 ID 사용 | platform, valid_from |
| `uses_email` | Person → Email | 이메일 사용 | valid_from, valid_to |
| `drives` | Person → Vehicle | 차량 운행 (일시 사용·LPR 추론 포함) | valid_from, valid_to |
| `owns_vehicle` | Person → Vehicle | 차량 법적 소유 (차량등록원부 기준) | valid_from, valid_to |
| `used_ip` | Person → IP | IP 사용 이력 | last_seen, usage_count |
| `member_of` | Person → Org | 조직 소속 | role, valid_from, valid_to |
| `works_at` | Person → Org | 합법 기관 재직 | position, valid_from |
| `accomplice_of` | Person → Person | 공범 관계 (추론) | confidence, inference_basis |
| `sameAs` | Person → Person | 동일 인물 (엔티티 해소) | match_score, match_basis, review_status |
| `contradicts` | Person → Person | 모순 정보 (명의도용 등) | conflict_field, conflict_detail |
| `owns` | Person → Any | 범용 소유 (구체적 엣지 우선 사용) | — |

### 4.4 Object → Person 예외 엣지 (1개)

| 엣지 | 방향 | 의미 | 주요 속성 |
|------|------|------|---------|
| `registered_to` | Phone → Person | 전화번호 등록 명의자 | source_id, rec_created |

> ⚠️ **레이어 예외**: 원칙상 Object→Person 방향은 금지이나,
> 명의자 역추적은 수사 실무에서 필수적이므로 이 엣지에 한해 예외 허용.

### 4.5 Object 관련 (11개) ★ v3.7 +2

| 엣지 | 방향 | 의미 | 주요 속성 | 버전 |
|------|------|------|---------|------|
| `transferred_to` | Account → Account | 계좌 간 추론 연결 (ETL 직접 생성 금지) | hop_level | — |
| `resolves_to` | Site → IP | DNS 해석 결과 | resolved_dt | — |
| `linked_to` ⚠️ | Object → Object | 범용 연결 (임시/추론) | link_type, confidence | — |
| `belongs_to` | Account → Org | 계좌 소속 금융기관 | — | — |
| `hosts` | IP → Site | 서버 IP가 사이트를 호스팅 | port, detected_at | v3.4 |
| `contains_file` | Site/Msg/ID → File | 파일 내장·배포 | file_role, detected_at | v3.4 |
| `located_at` | ATM/Device/Org → Location | 객체 고정 위치 | verified | v3.4 |
| `communicated_with` | IP → IP | IP 간 직접 통신 | — | v3.5 |
| `mentions_account` | Message → BankAccount | 메시지 내 계좌번호 언급 (추론) | confidence(0.85) | v3.5 |
| `belongs_to_cluster` ★ | Site/IP → site_cluster | 악성사이트 캠페인 군집 소속 | sim_score, rec_created | v3.7 |
| `used_in_device` ★ | Phone → Device | 전화번호가 기기(IMEI)에서 사용됨 | valid_from, valid_to, source_id | v3.7 |

> `used_in_device` **설계 의도 (v3.7)**:
> - 같은 `vt_dev` (IMEI)에 `used_in_device`로 연결된 `vt_telno`가 3개 이상 → 불법 사설중계기 의심
> - Apple COD(계속 발신번호) 기능 사용 추적에도 활용
> - `vt_dev.dev_type = 'relay_station'` 플래그와 함께 운영
>
> **deprecated (신규 생성 금지, DB 호환 유지)**:
> `accessed` (→ `hosts`), `hosted_at` (→ `hosts` 방향 역전), `contacted` (→ `caller`/`callee`)

### 4.6 Event 관련 (10개)

| 엣지 | 방향 | 의미 | 주요 속성 |
|------|------|------|---------|
| `from_account` | Account → Transfer | 이체 출금 계좌 | — |
| `to_account` | Transfer → Account | 이체 입금 계좌 | — |
| `caller` | Phone → Call | 발신 번호 | — |
| `callee` | Call → Phone | 수신 번호 | — |
| `accessed_from` | Access → NetworkTrace | 접속 출발 IP | — |
| `accessed_to` | Access → WebTrace | 접속 목적지 사이트 | — |
| `sent_msg` | Phone/ID → Message | 메시지 발신 | — |
| `received_msg` | Message → Phone | 메시지 수신 | — |
| `occurred_at` | Event → Location | 이벤트 발생 위치 | — |
| `recorded_in` | Vehicle/Phone → Movement | 이동 기록의 주체 | — |

### 4.7 Meta 관련 — Provenance (2개)

| 엣지 | 방향 | 의미 | 주요 속성 |
|------|------|------|---------|
| `sourced_from` | Any → Source | 데이터 출처 참조 | src_tier, rec_created |
| `verified_by` | Person → Person | 수사관이 정보를 검증 | verified_dt |

> **구현 규칙 (v3.6 확정)**:
> - **tier 1~3** → `sourced_from` 엣지 실제 생성
> - **tier 4~5** → `source_id` 속성만 사용, 엣지 생성 안 함
>
> ⚠️ `app/services/rdb_to_graph_service.py`의 `sourced_from` 대상이
> `vt_case`로 잘못 연결됨 — `vt_src`로 수정 필요 (버그, v3.6 문서화).

### 4.8 Person v3.4 신규 엣지 (3개)

| 엣지 ★ | 방향 | 의미 | 주요 속성 |
|--------|------|------|---------|
| `operates` | Person/Org → Site/DigitalID | 플랫폼·채널·사이트 운영자 식별 | valid_from, valid_to, role |
| `recruits` | Person → Person | 조직 모집 계층 추적 | recruit_type, date, payment |
| `blackmails` | Person → Person | 협박 행위 (몸캠피싱·랜섬웨어) | method, date |

### 4.9 사칭 범죄 엣지 (2개)

| 엣지 | 방향 | 의미 |
|------|------|------|
| `used_for` | Object → vt_impersonation | 특정 연락처/계정이 사칭 행위에 활용됨 |
| `targets` | vt_impersonation → vt_org | 사칭 행위의 타겟 조직/기관 |

### 4.10 호환성 유지 엣지 — 신규 생성 금지

| 엣지 | 원래 방향 | 대체 엣지 |
|------|----------|----------|
| `involves` | Case → Person | `suspect_in` / `victim_in` / `witness_in` |
| `involves_org` | Case → Org | `member_of` + `suspect_in` 조합 |
| `clusters_with` ★ | Petition → Petition | `belongs_to_cluster` (Petition → pt_cluster) |

---

## 5. 엣지 공통 메타속성

### 5.1 EDGE_META_SCHEMA (최종)

```python
EDGE_META_SCHEMA = {
    # ══ 필수 (모든 엣지) ══════════════════════════════════════
    'source_id':       str,    # vt_src.src_id 참조 (MANDATORY)
    'rec_created':     str,    # ISO8601 — DB 기록 시점 (MANDATORY)
    'creation_method': str,    # 'manual' | 'etl' | 'ocr_ner' | 'osint' | 'inference'

    # ══ 신뢰도 (소유·귀속 엣지에 적용) ══════════════════════
    'confidence':      float,  # 0.0~1.0 (1.0 = 공식 문서)
    'credibility':     int,    # 1~5 (GraphAware 기준)
    'verified':        bool,   # False=주장, True=수사관·공식문서 확인

    # ══ 이중시간 (소유·관계 엣지에 적용) ════════════════════
    'valid_from':      str,    # 현실에서 유효 시작 (ISO8601)
    'valid_to':        str,    # 현실에서 유효 종료 (null=현재진행)

    # ══ 검증 정보 (verified=True 시 필수) ════════════════════
    'verified_by':     str,    # 수사관 ID
    'verified_at':     str,    # 검증 일시
}
```

**이중시간 적용 여부 기준**:
```
✅ 적용 (소유권·관계가 시간에 따라 변함)
  has_account, owns_phone, owns_device, owns_vehicle, member_of,
  drives, uses_id, uses_email, works_at, operates, registered_to,
  used_in_device ★(v3.7)

❌ 불필요 (이벤트 자체가 시간 정보 보유)
  from_account, to_account, caller, callee, occurred_at,
  accessed_from, accessed_to

❌ 불필요 (출처는 불변)
  sourced_from, belongs_to_cluster
```

---

## 6. 핵심 쿼리 패턴

### 6.1 자금 흐름 추적 (N-Hop)
```cypher
MATCH path = (start:vt_bacnt {account_no: '110-1234-5678'})
             -[:from_account|to_account*2..8]->(end:vt_bacnt)
WHERE ALL(r IN relationships(path) WHERE r.verified = true OR r.confidence >= 0.7)
RETURN path, length(path)/2 AS hop_count
ORDER BY hop_count
```

### 6.2 동일 인물 교차 사건 탐색
```cypher
MATCH (c1:vt_case {flnm: '2026-001'})<-[:suspect_in]-(p:vt_psn)
      -[:suspect_in]->(c2:vt_case)
WHERE c1 <> c2
RETURN p.name, p.rrno_hash, collect(c2.flnm) AS related_cases
```

### 6.3 출처별 신뢰도 필터링
```cypher
MATCH (p:vt_psn)-[r:has_account]->(a:vt_bacnt)
WHERE r.verified = true
  AND EXISTS {
    MATCH (src:vt_src {src_id: r.source_id})
    WHERE src.reliability_tier <= 2
  }
RETURN p, a
```

### 6.4 시점 기준 유효 관계 조회 (Valid Time 쿼리)
```cypher
MATCH (p:vt_psn)-[r:has_account]->(a:vt_bacnt)
WHERE r.valid_from <= '2024-01-31'
  AND (r.valid_to IS NULL OR r.valid_to >= '2024-01-01')
RETURN p.name, a.account_no, a.bank_nm
```

### 6.5 이동 패턴 교차 분석 (위치 기반)
```cypher
MATCH (loc:vt_loc)<-[:occurred_at]-(m:vt_movement)
      <-[:recorded_in]-(subj)
WHERE loc.lat BETWEEN 37.495 AND 37.505
  AND loc.lng BETWEEN 127.025 AND 127.035
  AND m.timestamp >= '2026-01-15' AND m.timestamp < '2026-01-16'
RETURN m.mov_type, labels(subj), subj, m.timestamp
ORDER BY m.timestamp
```

### 6.6 엔티티 해소 후 통합 뷰
```cypher
MATCH (p:vt_psn {psn_id: 'psn-001'})
OPTIONAL MATCH (p)-[:sameAs*1..2]-(same:vt_psn)
WITH collect(p) + collect(same) AS all_persons
UNWIND all_persons AS person
MATCH (person)-[r:has_account|owns_phone|used_ip]-(obj)
RETURN person.name, type(r), labels(obj)[0], obj
```

### 6.7 범죄 조직망 탐지
```cypher
MATCH (a:vt_bacnt)<-[:has_account|controls]-(p:vt_psn)
WITH a, collect(p) AS persons
WHERE size(persons) >= 2
UNWIND persons AS p1
UNWIND persons AS p2
WHERE p1 <> p2
MERGE (p1)-[r:accomplice_of]-(p2)
ON CREATE SET r.inference_basis = 'shared_account',
              r.confidence = 0.75,
              r.rec_created = toString(datetime()),
              r.creation_method = 'inference',
              r.source_id = 'src-system-inference'
```

### 6.8 불법 사설중계기 탐지 ★ v3.7
```cypher
-- 동일 기기(IMEI)에 연결된 전화번호 3개 이상 → 중계기 의심
MATCH (t:vt_telno)-[:used_in_device]->(d:vt_dev)
WITH d, collect(t) AS phones
WHERE size(phones) >= 3
RETURN d.imei, d.dev_type, size(phones) AS phone_count,
       [p IN phones | p.telno] AS telno_list
ORDER BY phone_count DESC
```

### 6.9 동일 기지국 다수 범죄번호 발신 탐지 ★ v3.7
```cypher
-- 동일 기지국에서 발신된 범죄 관련 전화 5건+ → 중계기 설치 위치 의심
MATCH (t:vt_telno)<-[:caller]-(c:vt_call)-[:occurred_at]->(loc:vt_loc)
WHERE loc.loc_type = 'cell_tower'
WITH loc, collect(DISTINCT t) AS phones, count(c) AS call_count
WHERE size(phones) >= 5
RETURN loc.bsst_nm, loc.address, loc.lat, loc.lng,
       size(phones) AS suspect_phone_count, call_count
ORDER BY suspect_phone_count DESC
```

### 6.10 피싱 캠페인 군집 추적 ★ v3.7
```cypher
-- 동일 캠페인 군집의 모든 사이트와 IP 조회 (IP 교체 후에도 추적 가능)
MATCH (c:site_cluster {cluster_id: $cid})<-[:belongs_to_cluster]-(n)
RETURN c.campaign_name, c.phishing_type,
       labels(n)[0] AS node_type,
       CASE labels(n)[0]
         WHEN 'vt_site' THEN n.url_addr
         WHEN 'vt_ip'   THEN n.ip_addr
       END AS identifier,
       n.rec_created
ORDER BY n.rec_created DESC
```

### 6.11 성명불상 피의자 현황 조회 ★ v3.7
```cypher
-- 미확인 피의자 목록 (수사관 검토 대상)
MATCH (p:vt_psn {is_anonymous: true})-[:suspect_in]->(c:vt_case)
RETURN p.psn_id, c.flnm, c.crime_type,
       collect(DISTINCT type(r2)) AS linked_objects
OPTIONAL MATCH (p)-[r2:has_account|owns_phone|used_ip]->(obj)
ORDER BY c.rec_created DESC
```

### 6.12 전화번호 위치 이력 조회 (Event-mediated 표준 패턴) ★ v3.7 결정
```cypher
-- [결정] Phone → Location 직접 엣지 미추가 (v3.7 §5번 피드백)
-- 이유: Movement 이벤트가 시간·타입 정보(timestamp, mov_type)를 보유하므로 직접 엣지는 중복
-- 표준 조회 패턴으로 대체

-- 특정 전화번호의 기지국 이동 경로 (시간순)
MATCH (t:vt_telno {telno: $telno})
      -[:recorded_in]->(m:vt_movement {mov_type: 'cell_tower'})
      -[:occurred_at]->(loc:vt_loc)
RETURN t.telno, m.timestamp, loc.bsst_nm, loc.address, loc.lat, loc.lng
ORDER BY m.timestamp

-- 최근 위치 1건
MATCH (t:vt_telno {telno: $telno})
      -[:recorded_in]->(m:vt_movement {mov_type: 'cell_tower'})
      -[:occurred_at]->(loc:vt_loc)
RETURN loc ORDER BY m.timestamp DESC LIMIT 1

-- 복수 전화번호 동선 교차 (같은 기지국 + 시간대 겹침)
MATCH (t1:vt_telno {telno: $telno1})-[:recorded_in]->(m1:vt_movement)-[:occurred_at]->(loc:vt_loc),
      (t2:vt_telno {telno: $telno2})-[:recorded_in]->(m2:vt_movement)-[:occurred_at]->(loc)
WHERE abs(duration.inSeconds(m1.timestamp, m2.timestamp).seconds) <= 3600
RETURN loc.bsst_nm, m1.timestamp, m2.timestamp
ORDER BY m1.timestamp
```

---

## 7. RDB 연동 경계

### 그래프 DB (AgensGraph) 담당
```
핵심 엔티티 관계망, 분석·시각화, Multi-hop 경로, 커뮤니티 탐지
→ 25개 vt_/pt_/site_ 노드 전체
→ Source Meta (vt_src)
→ 엔티티 해소 (sameAs, contradicts)
→ 군집 허브 (pt_cluster, site_cluster) ★
```

### RDB (PostgreSQL / tccopdb) 담당
```
대용량 이벤트 원본, 감사 로그, 코드 테이블
→ TB_FIN_BACNT_DLNG   (거래내역, 수백만 건)
→ TB_TELNO_CALL_DTL   (CDR)
→ TB_TELNO_SMS_MSG    (문자 메시지)
→ TB_CHAT_MSG         (메신저 대화)
→ TB_GEO_TRST_CARD_TRIP (교통카드)
→ TB_SYS_LGN_EVT     (시스템 감사)
→ 코드 테이블 (은행코드, 죄명코드 등)
```

### 연결 포인트 (Bridge Keys)
```
vt_transfer.event_id   → TB_FIN_BACNT_DLNG.DLNG_SN
vt_call.event_id       → TB_TELNO_CALL_DTL.CALL_SN
vt_access.event_id     → TB_SYS_LGN_EVT.LGN_SN
vt_msg.event_id        → TB_TELNO_SMS_MSG.MSG_SN
vt_movement.event_id   → TB_VHCL_LPR_EVT.RCGN_SN
vt_movement.event_id   → TB_GEO_MBL_LOC_EVT.LOC_EVT_SN
vt_movement.event_id   → TB_GEO_TRST_CARD_TRIP.MV_SN
vt_petition.petition_id→ TB_PETTN_MST.PETITION_ID
vt_petition.raw_id     → TB_FRD_VCTM_RPT.DCLR_SN
vt_id.id_val           → TB_DGTL_ID_MST.ID_SN
vt_email.email_addr    → TB_EMAIL_MST.EMAIL_SN
vt_crypto.wallet_addr  → TB_CRYPTO_WALLET_MST.WALLET_SN
vt_dev.device_id       → TB_DEV_MST.DEV_SN
vt_atm.atm_id          → TB_ATM_MST.ATM_MNG_NO
vt_loc.loc_id          → TB_LOC_MST.LOC_SN
```

---

## 8. COLUMN_PATTERNS (완전판)

```python
COLUMN_PATTERNS = {
    'case': {
        'patterns': ['사건', 'case', '사건번호', '접수번호', 'flnm', 'incdnt_no'],
        'kics_label': 'vt_case', 'kics_property': 'flnm'
    },
    'petition': {
        'patterns': ['진정서', 'petition', '신고번호', 'dclr_sn', 'complaint', '민원'],
        'kics_label': 'vt_petition', 'kics_property': 'petition_id'
    },
    'person': {
        'patterns': ['이름', 'name', '성명', '피해자', '피의자', '인물', 'korn_flnm'],
        'kics_label': 'vt_psn', 'kics_property': 'name'
    },
    'suspect': {
        'patterns': ['피의자', 'suspect', '용의자', '범인', 'rrno', '주민번호'],
        'kics_label': 'vt_psn', 'kics_property': 'rrno_hash'
    },
    'account': {
        'patterns': ['계좌', 'account', 'bacnt', 'actno', 'bank', '은행', 'account_no'],
        'kics_label': 'vt_bacnt', 'kics_property': 'account_no'
    },
    'bank_cd': {
        'patterns': ['은행코드', 'bank_cd', 'bank_code', '금융기관코드'],
        'kics_label': 'vt_bacnt', 'kics_property': 'bank_cd', 'is_attribute': True
    },
    'phone': {
        'patterns': ['전화', 'phone', 'telno', 'tel', 'mobile', '휴대폰', '연락처'],
        'kics_label': 'vt_telno', 'kics_property': 'telno'
    },
    'ip': {
        'patterns': ['IP', 'ip주소', 'ip_addr', 'ipaddr', '아이피'],
        'kics_label': 'vt_ip', 'kics_property': 'ip_addr'
    },
    'site': {
        'patterns': ['사이트', 'site', 'url', 'url_addr', 'domain', '웹', '링크'],
        'kics_label': 'vt_site', 'kics_property': 'url_addr'
    },
    'file': {
        'patterns': ['파일', 'file', 'filename', 'file_nm', 'hash', 'hash_val'],
        'kics_label': 'vt_file', 'kics_property': 'hash_val'
    },
    'user_id': {
        'patterns': ['사용자ID', 'user_id', 'login_id', 'account_id', 'uid', '아이디'],
        'kics_label': 'vt_id', 'kics_property': 'id_val'
    },
    'nickname': {
        'patterns': ['닉네임', 'nickname', 'nick', '별명', 'alias'],
        'kics_label': 'vt_id', 'kics_property': 'id_val'
    },
    'vehicle': {
        'patterns': ['차량', 'vehicle', '차량번호', 'vhclno', 'car', '번호판'],
        'kics_label': 'vt_vhcl', 'kics_property': 'vhclno'
    },
    'email': {
        'patterns': ['이메일', 'email', 'e-mail', 'mail', 'email_addr', '전자우편'],
        'kics_label': 'vt_email', 'kics_property': 'email_addr'
    },
    'crypto': {
        'patterns': ['지갑', 'wallet', 'wallet_addr', '가상자산', 'crypto', 'btc', 'eth'],
        'kics_label': 'vt_crypto', 'kics_property': 'wallet_addr'
    },
    'atm': {
        'patterns': ['atm', 'atm_id', 'atm_mng_no', '현금인출기'],
        'kics_label': 'vt_atm', 'kics_property': 'atm_id'
    },
    'org': {
        'patterns': ['조직', 'org', '기관', '회사', '은행명', 'institution', 'inst_nm'],
        'kics_label': 'vt_org', 'kics_property': 'org_name'
    },
    'device': {
        'patterns': ['기기', 'device', 'imei', '단말기', 'smartphone', '중계기'],
        'kics_label': 'vt_dev', 'kics_property': 'device_id'
    },

    # 속성 패턴 (노드 생성 없음)
    'date': {
        'patterns': ['일시', 'date', '시간', 'time', '발생일시', '거래일시', 'occrn_dt', 'dlng_dt'],
        'kics_label': '', 'kics_property': 'timestamp', 'is_attribute': True
    },
    'amount': {
        'patterns': ['금액', 'amount', '거래금액', '피해금액', 'dlng_amt', 'dam_amt'],
        'kics_label': '', 'kics_property': 'amount', 'is_attribute': True
    },
    'damage_amt': {
        'patterns': ['피해금액', 'damage_amount', '피해액', 'dam_amt'],
        'kics_label': '', 'kics_property': 'damage_amount', 'is_attribute': True
    },
    'sender': {
        'patterns': ['출금', '송금계좌', '보낸사람', 'from', 'dsptch', 'sender'],
        'kics_label': 'vt_transfer', 'kics_property': 'from_account'
    },
    'receiver': {
        'patterns': ['입금', '수취계좌', '받는사람', 'to', 'rcptn', 'receiver'],
        'kics_label': 'vt_transfer', 'kics_property': 'to_account'
    },
    'caller': {
        'patterns': ['발신', 'caller', '발신번호', 'dsptch_telno'],
        'kics_label': 'vt_telno', 'kics_property': 'telno'
    },
    'callee': {
        'patterns': ['수신', 'callee', '수신번호', 'rcptn_telno'],
        'kics_label': 'vt_telno', 'kics_property': 'telno'
    },
    'duration': {
        'patterns': ['통화시간', 'duration', 'call_dur_sec'],
        'kics_label': '', 'kics_property': 'call_dur_sec', 'is_attribute': True
    },
    'lat': {
        'patterns': ['위도', 'lat', 'latitude', 'bsst_lat'],
        'kics_label': '', 'kics_property': 'lat', 'is_attribute': True
    },
    'lng': {
        'patterns': ['경도', 'lng', 'longitude', 'bsst_lot'],
        'kics_label': '', 'kics_property': 'lng', 'is_attribute': True
    },
    'crime': {
        'patterns': ['죄명', '범죄유형', 'crime', '범죄유형명', 'incdnt_typ_cd'],
        'kics_label': 'vt_case', 'kics_property': 'crime_type', 'is_attribute': True
    },
    'message': {
        'patterns': ['메시지', 'message', '내용', 'content', '문자내용', '채팅'],
        'kics_label': 'vt_msg', 'kics_property': 'content_hash'
    },
}
```

---

## 9. INFERENCE_RULES (v3.7 — 10개)

```python
INFERENCE_RULES = [
    {
        'name': 'OrganizedCrime',
        'pattern': 'shared_resource_usage',
        'trigger': '동일 계좌/전화가 3건+ 사건에서 사용',
        'threshold': 3,
        'confidence': 0.80,
        'output_edge': 'accomplice_of',
        'legal_basis': '범죄수익은닉규제법'
    },
    {
        'name': 'MoneyLaundering',
        'pattern': 'multi_hop_transfer',
        'trigger': '3단계+ 계좌이체 (hop_level >= 3)',
        'threshold': 3,
        'confidence': 0.75,
        'output_edge': 'suspicious_transfer',
        'legal_basis': '특정금융거래정보법'
    },
    {
        'name': 'Accomplice',
        'pattern': 'shared_contacts',
        'trigger': '2인 이상이 5건+ 공통 통화 대상 공유',
        'threshold': 5,
        'confidence': 0.70,
        'output_edge': 'accomplice_of',
        'legal_basis': '형법 제30조 공동정범'
    },
    {
        'name': 'BurnerAccount',
        'pattern': 'high_frequency_transfer',
        'trigger': '1시간 내 10건+ 이체 또는 3일 이내 개설·사용·해지',
        'threshold': 10,
        'confidence': 0.85,
        'output_node_flag': 'vt_bacnt.is_burner = True',
        'legal_basis': '전자금융거래법'
    },
    {
        'name': 'BurnerPhone',
        'pattern': 'prepaid_high_activity',
        'trigger': '선불폰 (join_typ_cd=PREPAID) + 스팸신고 3건+',
        'threshold': 3,
        'confidence': 0.80,
        'output_node_flag': 'vt_telno.is_burner = True',
        'legal_basis': '전기통신사업법'
    },
    {
        'name': 'EntityResolutionCandidate',
        'pattern': 'shared_phone_and_account',
        'trigger': '두 vt_psn이 동일 전화번호 + 계좌 1개 이상 공유',
        'threshold': 1,
        'confidence': 0.85,
        'output_edge': 'sameAs',
        'review_required': True,
        'legal_basis': None
    },
    {
        'name': 'CrossDomainHub',
        'pattern': 'ip_account_phone_correlation',
        'trigger': '동일 IP에서 다수 계좌+전화 접속',
        'threshold': 2,
        'confidence': 0.80,
        'output_flag': 'hub_suspect',
        'legal_basis': '정보통신망법'
    },
    {
        'name': 'NightCrimePattern',
        'pattern': 'night_time_activity',
        'trigger': '00~06시 3건+ 이체/통화',
        'threshold': 3,
        'confidence': 0.65,
        'output_flag': 'night_activity',
        'legal_basis': '야간 범행 가중처벌'
    },
    {
        'name': 'RecruitChainAccomplice',
        'pattern': 'recruits_chain',
        'trigger': '총책 → 조직원 → 말단 recruits 체인 2단계+',
        'threshold': 2,
        'confidence': 0.75,
        'output_edge': 'accomplice_of',
        'legal_basis': '형법 제30조 공동정범'
    },
    {
        'name': 'RelayStationDetection',
        'pattern': 'multi_telno_per_device',
        'trigger': '동일 IMEI(vt_dev)에 used_in_device로 연결된 vt_telno 3개+',
        'threshold': 3,
        'confidence': 0.85,
        'output_node_flag': 'vt_dev.dev_type = relay_station',
        'legal_basis': '전기통신사업법 제97조 (불법 통신중계)',
        'note': '동일 기지국 5번호+ 발신 패턴과 교차 검증 시 신뢰도 0.92로 상향'
    },
]
```

---

## 10. 구현 체크리스트

### Phase 1 (v3.7 — 즉시, 기존 코드 수정)

```
[ ] rdb_to_graph_service.py — sourced_from 방향 버그 수정 (vt_case → vt_src)
[ ] vt_psn에 is_anonymous: bool 속성 추가
[ ] vt_dev.dev_type에 'relay_station' 값 추가 (enum 확장)
[ ] ontology_service.py ENTITIES에 pt_cluster, site_cluster 노드 정의 추가
[ ] ontology_service.py RELATIONSHIPS에 belongs_to_cluster, used_in_device 엣지 추가
[ ] COLUMN_PATTERNS에 'device' 패턴 추가 (중계기 포함)
[ ] GDB_LABEL_MAP, CONCEPT_LOOKUP, LABEL_KO_MAP 갱신 (pt_cluster, site_cluster)
[ ] INFERENCE_RULES에 RelayStationDetection 추가
[ ] clusters_with deprecated 처리 (신규 생성 차단 로직)
```

### Phase 1 (v3.6 인계 — 즉시, 아직 미완)

```
[ ] vt_psn.role 속성 제거 → suspect_in/victim_in/witness_in 엣지로 이전
[ ] 모든 엣지에 source_id, rec_created 필드 의무화
[ ] vt_src 기본 소스 5개 등록 (src-official, src-kics, src-petition, src-osint, src-report)
```

### Phase 2 (단기, 분석 기능)

```
[ ] pt_cluster 자동 생성 서비스 — 진정서 유사도 분석 → belongs_to_cluster 엣지 생성
[ ] site_cluster 자동 생성 서비스 — HTML SimHash 비교 → belongs_to_cluster 엣지 생성
[ ] used_in_device 자동 매핑 — CDR IMSI/IMEI 데이터 기반 자동 연결
[ ] is_anonymous=True 피의자 검토 UI (수사관 신원 확인 워크플로)
[ ] valid_from / valid_to 소유 엣지 12종 적용 (used_in_device 포함)
```

### Phase 3 (중기)

```
[ ] EntityResolution 서비스 — sameAs 후보 자동 생성
[ ] RelayStationDetection 자동 실행 스케줄러
[ ] 피싱 캠페인 대시보드 (site_cluster 기반 시각화)
[ ] Bitemporal 쿼리 UI — 날짜 슬라이더로 Valid Time 필터
[ ] INFERENCE_RULES 자동 실행 스케줄러 (전체 10개)
```

---

## 노드/엣지 수 요약

| 구분 | v1 (초기) | v2 (중간) | v3.0~v3.4 | v3.5 | v3.6 | **v3.7 (확정)** |
|------|---------|---------|-----------|------|------|--------------|
| 노드 타입 | 21개 | 28개+ | 22개→23개 | 23개 | 23개 | **25개** |
| 엣지 타입 | 27개 | 40개+ | 42개 | 52개 | 52개 | **53개** |
| 레이어 | 4계층 | 6계층 | 6계층 | 6계층 | 6계층 | **6계층** |
| 추론 규칙 | — | — | 8개 | 9개 | 9개 | **10개** |
| 군집 표현 | 없음 | 없음 | 없음 | 엣지 | 엣지 | **노드 허브** |

**v3.7 노드 변경 상세 (23 → 25)**:

| 추가 노드 | 레이어 | 대체 대상 |
|----------|-------|---------|
| `pt_cluster` | CASE | `clusters_with` 엣지 (O(n²) 해소) |
| `site_cluster` | OBJECT | 신규 (피싱 캠페인 추적) |

**v3.7 엣지 변경 상세 (52 → 53)**:

| 변경 | 엣지 | 비고 |
|------|------|------|
| 제거 (deprecated) | `clusters_with` | -1 |
| 신설 | `belongs_to_cluster` | +1 (Petition→pt_cluster, Site/IP→site_cluster 공용) |
| 신설 | `used_in_device` | +1 (Phone→Device) |
| **합계** | | **+1 → 53개** |

---

*이 문서는 CCOP ontology_service.py 구현의 유일한 기준입니다.*
*변경 시 반드시 이 문서를 먼저 수정하고 코드에 반영합니다.*
*이전 버전: ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md*
