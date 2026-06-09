> ## ⚠️ DEPRECATED — V4.0 통합본 사용 권장
>
> 이 문서는 **CCOP 온톨로지 V2.0** 명세입니다. **2026-05-21부로 V4.0으로 통합되어 deprecated** 되었습니다.
>
> **현행 SSOT**: [`docs/CCOP_ONTOLOGY_V4.0.md`](CCOP_ONTOLOGY_V4.0.md)
> **코드 SSOT**: `app/middleware/services/ontology_service.py:KICSCrimeDomainOntology`
>
> V4.0은 V3.7 카탈로그(25 노드 / 53 엣지)를 그대로 유지하면서, 도메인 사용 매트릭스 / 식별자 형식 / 추론 규칙을 표준 메타로 격상한 통합본입니다. 본 문서는 **역사적 참고용**으로만 보존됩니다.
>
> ---
>

# CCOP 온톨로지 v2 설계서
# 경찰청 표준 + POLE + W3C PROV-O + Bitemporal 통합 설계

> **작성일:** 2026-04-01
> **버전:** v2.0
> **전임 문서:** `docs/ONTOLOGY_REDESIGN_PETITION_OSINT.md` (v1.0)
> **대상:** CCOP 개발팀 / 전처리 기관 협의 / 수사 플랫폼 운영기관
> **관련 파일:** `app/middleware/services/ontology_service.py`

---

## 목차

1. [설계 배경 및 목표](#1-설계-배경-및-목표)
2. [리서치 기반: 참조 표준 요약](#2-리서치-기반-참조-표준-요약)
3. [현행 CCOP vs 표준 격차 분석](#3-현행-ccop-vs-표준-격차-분석)
4. [설계 원칙 5가지](#4-설계-원칙-5가지)
5. [6레이어 아키텍처](#5-6레이어-아키텍처)
6. [노드 카탈로그 v2](#6-노드-카탈로그-v2)
7. [Provenance 메타 레이어 설계](#7-provenance-메타-레이어-설계)
8. [엣지 메타속성 표준 v2](#8-엣지-메타속성-표준-v2)
9. [이중시간 모델 (Bitemporal)](#9-이중시간-모델-bitemporal)
10. [엔티티 해소 패턴](#10-엔티티-해소-패턴)
11. [경찰청 표준 컬럼 정렬표](#11-경찰청-표준-컬럼-정렬표)
12. [RDB-Graph 하이브리드 분담](#12-rdb-graph-하이브리드-분담)
13. [구현 로드맵 (Phase 1~3)](#13-구현-로드맵)

---

## 1. 설계 배경 및 목표

### 1.1 v1.0에서 식별된 한계

| 문제 | 설명 | 영향 |
|------|------|------|
| 출처(Provenance) 부재 | 엔티티가 어느 소스에서 왔는지 표현 불가 | 법정 증거 진정성립 불가 |
| 신뢰도 체계 부재 | NER 추출값과 수사관 확인값을 동일 취급 | 분석 결과 신뢰도 평가 불가 |
| 시간적 유효성 미흡 | 계좌 소유권 변경 이력 표현 불가 | 이력 분석 오류 |
| 역할 속성 충돌 | 동일 인물이 사건별로 다른 역할일 때 덮어쓰기 | 다중 사건 분석 오류 |
| 위치 정보 분산 | 좌표가 노드 속성으로 흩어져 있어 위치 기반 교차 분석 불가 | 기지국·ATM·LPR 공간 분석 제한 |
| 경찰청 표준 미정렬 | TB_ 테이블 기준 필드와 vt_ 노드 속성 불일치 | 전처리 기관 데이터 매핑 오류 가능성 |

### 1.2 v2.0 설계 목표

```
1. 경찰청 표준 28개 테이블 Coverage 확보 (차량·위치·기관·마약 도메인 추가)
2. 출처 추적 (Provenance): 모든 사실에 소스·수집일·신뢰 등급 부여
3. 사실과 주장의 분리: 검증되지 않은 데이터는 Assertion으로 관리
4. 이중시간 표준화: 현실 시간(Valid Time) vs 기록 시간(Transaction Time)
5. 엔티티 해소: 다중 소스의 동일 인물/계좌를 병합 또는 모순 표시
6. 그래프-RDB 하이브리드: 이벤트 대용량 데이터는 RDB, 관계망은 Graph
```

---

## 2. 리서치 기반: 참조 표준 요약

### 2.1 POLE 모델 (UK National Police — NPCC 표준)

**P**erson · **O**bject · **L**ocation · **E**vent — 영국 국가경찰청이 채택한 수사 데이터 조직 표준.

- **Person**: 4+1 최소 데이터 기준 (이름·생년월일·성별·연락처 + 식별참조)
- **Object**: 차량·계좌·전화·기기·파일 등 모든 유형의 객체
- **Location**: 물리적·디지털 위치 (주소, 좌표, IP, 기지국)
- **Event**: 시공간이 있는 행위 (이체, 통화, 접속, 이동, 범행)

> 참고: [Neo4j POLE Crime Investigation Example](https://github.com/neo4j-graph-examples/pole),
> [UK Police Digital Service POLE Standards v1.1](https://www.npcc.police.uk/SysSiteAssets/media/downloads/publications/disclosure-logs/dei-coordination-committee/2023/274-2023-pole-data-standards-catalogue-v1.1-1-1.pdf)

### 2.2 W3C PROV-O (출처 추적 온톨로지)

W3C 권고 표준 — 데이터의 **생산(Generation)·사용(Usage)·파생(Derivation)** 관계 표준화.

```
prov:Entity   → 데이터 그 자체 (노드, 엣지)
prov:Activity → 수집·분석·입력 활동
prov:Agent    → 소스 기관, 수사관, 자동화 시스템
```

핵심 패턴: `wasGeneratedBy`, `wasAttributedTo`, `wasDerivedFrom`

수사 맥락 적용:
```
(vt_bacnt:계좌) wasGeneratedBy (Activity:더치트수집_2026-03-15)
(Activity) wasAssociatedWith (Agent:더치트DB, reliability_tier=4)
```

### 2.3 이중시간 모델링 (Bitemporal)

수사 데이터에 필요한 **두 개의 독립 시간 축**:

| 시간 축 | 정의 | 수사 예시 |
|---------|------|----------|
| **Valid Time** (현실 유효기간) | 이 사실이 현실에서 참인 기간 | 계좌 개설일~해지일 |
| **Transaction Time** (기록 시점) | DB에 기록된 시점 | 수사관 입력일 |

> 참고: [Bitemporal Property Graphs (Springer)](https://link.springer.com/chapter/10.1007/978-3-032-05281-0_15),
> [Towards Probabilistic Bitemporal KGs (ACM)](https://dl.acm.org/doi/fullHtml/10.1145/3184558.3191637)

### 2.4 UCO / STIX 2.1 (사이버 범죄 온톨로지)

- **STIX 2.1** (OASIS 표준): JSON 기반 사이버 위협 정보 표현 언어. `confidence` 필드 0–100 정수.
- **UCO** (Unified Cybersecurity Ontology): STIX를 OWL로 확장, 포렌식 증거·IP·악성코드 정의.
- **TAXII 2.1**: STIX 데이터 전송 프로토콜.

> 참고: [STIX v2.1 OASIS Standard](https://docs.oasis-open.org/cti/stix/v2.1/os/stix-v2.1-os.html),
> [UCO Paper (UMBC)](https://ebiquity.umbc.edu/_file_directory_/papers/781.pdf)

### 2.5 Dempster-Shafer 이론 (다중 소스 증거 융합)

베이즈 확률론과 달리 **무지(ignorance)와 불확실성을 명시적으로 구분**하는 증거 융합 프레임워크.

수사 적용:
```
소스1 더치트:    "계좌 X = 사기"  confidence 0.80
소스2 VirusTotal: "연관 URL 악성"  confidence 0.60
소스3 수사관 확인: "계좌 조회 일치" confidence 0.95

→ D-S 결합: belief(사기 계좌) ≈ 0.98  (교차검증 시 급상승)
```

> 참고: [D-S Theory Applied to Legal Evidence (Cambridge Core)](https://www.cambridge.org/core/journals/judgment-and-decision-making/article/application-of-dempstershafer-theory-demonstrated-with-justification-provided-by-legal-evidence/92A1AFBF2609F82D5278CA5C27A84017)

### 2.6 GraphAware 수사 그래프 패턴 (실무 사례)

GraphAware "Graphs in Law Enforcement" 시리즈에서 확립된 실무 패턴:

- **Source Reliability** 5단계: A(검증기관) ~ E(익명제보)
- **Information Credibility** 5단계: 1(확인됨) ~ 5(사실 여부 미상)
- **Entity Fusion**: 동일 엔티티 병합 시 각 소스 레코드는 보존

> 참고: [GraphAware - Graphs in Law Enforcement #2](https://graphaware.com/blog/business/graphs-in-law-enforcement-2-data-quality-and-credibility.html),
> [GraphAware - Fused Entities #3](https://graphaware.com/blog/graphs-in-law-enforcement-3-fused-entities/)

---

## 3. 현행 CCOP vs 표준 격차 분석

```
               POLE   경찰청28  W3C-PROV  Bitemporal  STIX   CCOP현행
─────────────────────────────────────────────────────────────────────────
Person           ✅      ✅        ✅         ✅         ✅       ✅
Object           ✅      ✅        ✅         △          △        ✅
Location         ✅      ✅        ✅         △          △        △ (속성)
Event            ✅      ✅        ✅         ✅         ✅       △ (Action혼재)
─────────────────────────────────────────────────────────────────────────
Provenance Node  —       —        ✅         —          —        ✗ 없음
Source Reliability—      —        ✅         —          ✅       ✗ 없음
Info Credibility —       —        ✅         —          ✅       △ confidence만
─────────────────────────────────────────────────────────────────────────
Valid Time       —       △        ✅         ✅         —        △ 일부
Transaction Time —       ✗        ✅         ✅         —        ✗ 없음
─────────────────────────────────────────────────────────────────────────
Entity Resolution—       ✗        ✅         —          ✅       △ sameAs설계
Confidence Fusion—       ✗        ✅         —          ✅       ✗ 없음
─────────────────────────────────────────────────────────────────────────
Vehicle          ✅      ✅        —          —          —        △ v2추가
Organization     ✅      ✅        ✅         —          ✅       ✅ vt_org
Drug Domain      ✗       ✅        —          —          —        ✗ 없음
Telecom CDR      ✅      ✅        ✅         ✅         —        ✗ 없음
─────────────────────────────────────────────────────────────────────────
```

**핵심 격차**: 노드 구조는 양호하나 **출처·시간·신뢰도 3대 메타 레이어** 부재.

---

## 4. 설계 원칙 5가지

### 원칙 1: POLE 정렬 (Structural Alignment)

모든 노드를 **Person / Object / Location / Event** 4범주로 분류.
Case는 조직화 컨테이너(Layer 0), Provenance는 수직 관통 메타 레이어.

### 원칙 2: 사실과 주장의 분리 (Assertion vs Fact)

```
주장(Assertion): "더치트에 따르면 홍길동이 이 계좌를 가지고 있다"
                 → vt_assertion 노드로 저장, verified = false

사실(Fact):     "영장 집행으로 계좌 소유 확인됨"
                → 엣지 verified = true로 승격
```

### 원칙 3: 이중 시간축 (Bitemporal Mandatory)

모든 엣지에 현실 시간(`valid_from`/`valid_to`)과 기록 시간(`rec_created`/`rec_updated`) 분리 필수.

### 원칙 4: 소스 계층 신뢰도 (Source Tiering)

```
Tier 1 — 공식 수사자료    : 영장, 금융거래확인서, 법원 결정문
Tier 2 — 기관 연계 데이터 : 금감원, 경찰청 공유 DB, 통신사 제출
Tier 3 — 전처리 데이터    : OCR/NER 완료 진정서, 전처리 기관 배치
Tier 4 — OSINT           : 더치트, WHOIS, VirusTotal, SNS
Tier 5 — 미확인 제보      : 익명 신고, 자진 제보
```

### 원칙 5: 그래프-RDB 하이브리드

- **이벤트 대용량 데이터 → RDB**: 경찰청 TB_ 표준 명명 규칙 적용
- **핵심 엔티티 관계망 → Graph**: CCOP vt_ 노드, Provenance 메타 레이어

---

## 5. 6레이어 아키텍처

```
┌─────────────────────────────────────────────────────────────────────┐
│  META LAYER  ── Provenance (출처·신뢰도)                             │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  vt_src (소스 기관)   vt_assertion (검증 전 주장 레코드)        │  │
│  └───────────────────────────────────────────────────────────────┘  │
│         ↑ 모든 레이어에 수직으로 관통 (엣지 source_id 참조)            │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 0: CASE ── 수사 컨텍스트                                      │
│  vt_case (사건)   vt_petition (진정서)   vt_petition_cluster (군집)  │
│  vt_crime_event (범죄 이벤트 — 수사 대상 사건의 최소 단위)              │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 1: PERSON (POLE-P) ── 행위 주체                              │
│  vt_psn (인물)   vt_org (조직/기관)   vt_persona (디지털 페르소나)    │
│  [CCOP 고유: vt_persona → 닉네임·계정 분리 표현]                      │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 2: OBJECT (POLE-O) ── 객체·증거                              │
│  vt_bacnt   vt_telno   vt_ip    vt_site   vt_file   vt_id          │
│  vt_vhcl    vt_email   vt_crypto  vt_dev   vt_atm                   │
│  [vt_keyword — 마약 은어 등 분석 키워드 사전, 경찰청 TB_DRUG_SLANG 대응] │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 3: LOCATION (POLE-L) ── 위치 [v2 신규 독립화]                 │
│  vt_loc (주소/좌표)   vt_bsst (기지국)   vt_cctv (CCTV 설치지점)     │
│  [기존: 각 노드의 속성으로 흩어진 좌표 → 독립 노드로 참조]               │
├─────────────────────────────────────────────────────────────────────┤
│  LAYER 4: EVENT (POLE-E) ── 시공간 행위                              │
│  vt_transfer (이체)   vt_call (통화)    vt_access (접속)             │
│  vt_msg (메시지)      vt_lpr_evt (LPR)  vt_loc_evt (기지국위치)      │
│  [RDB의 TB_FIN_BACNT_DLNG / TB_TELNO_CALL_DTL과 연결 포인트]         │
└─────────────────────────────────────────────────────────────────────┘
```

**레이어 간 허용 관계 방향**:

```
Case    → Person, Object, Event          (사건이 행위자·증거·이벤트와 연결)
Person  → Object, Location, Event        (인물이 객체 소유·위치 방문·이벤트 참여)
Object  → Object, Location, Event        (객체 간 연결, 위치 귀속, 이벤트 연루)
Location → Event                         (위치에서 이벤트 발생)
Event   → Object, Location               (이벤트가 객체·위치를 포함)
Meta    ↕ 모든 레이어                     (출처·신뢰도는 양방향 관통)
```

---

## 6. 노드 카탈로그 v2

### META LAYER

| 노드 | GDB 라벨 | 핵심 속성 | 경찰청 대응 | 신규 |
|------|---------|----------|------------|------|
| 소스 | `vt_src` | src_id, src_name, src_type, reliability_tier, collector, collected_at | — | ✅ |
| 주장 레코드 | `vt_assertion` | assertion_id, claim_type, subject_id, object_id, credibility, confidence, verified | — | ✅ |

### LAYER 0: CASE

| 노드 | GDB 라벨 | 핵심 속성 | 경찰청 대응 | 신규 |
|------|---------|----------|------------|------|
| 사건 | `vt_case` | flnm, receipt_no, crime_type, damage_amount, status | TB_INCDNT_MST | — |
| 진정서 | `vt_petition` | petition_id, channel, ocr_confidence, submitted_at | TB_FRD_VCTM_RPT | ✅ |
| 진정서 군집 | `vt_petition_cluster` | cluster_id, cluster_type, member_count, similarity | — | ✅ |
| 범죄 이벤트 | `vt_crime_event` | event_id, event_type, occurred_at, location_id | — | ✅ |

### LAYER 1: PERSON

| 노드 | GDB 라벨 | 핵심 속성 | 경찰청 대응 |
|------|---------|----------|------------|
| 인물 | `vt_psn` | name, id_no_hash, rrno_hash | TB_PRSN |
| 조직/기관 | `vt_org` | org_name, org_id, org_type_cd, brno | TB_INST |
| 디지털 페르소나 | `vt_persona` | persona_id, persona_type, identifier, platform | — |

> ⚠️ `vt_psn.role` 속성 제거 → 역할은 엣지 타입으로 표현
> (`suspect_in`, `victim_in`, `witness_in` 엣지가 `vt_psn → vt_case`를 연결)

### LAYER 2: OBJECT

| 노드 | GDB 라벨 | 핵심 속성 | 경찰청 대응 | 비고 |
|------|---------|----------|------------|------|
| 계좌 | `vt_bacnt` | account_no, bank_cd, bank_nm, dpstr_nm | TB_FIN_BACNT | bank_cd 추가 |
| 전화번호 | `vt_telno` | telno, telco_nm, join_type_cd | TB_TELNO_MST | telco_nm 추가 |
| IP주소 | `vt_ip` | ip_addr, isp, country, vpn | — | CCOP 고유 |
| 사이트/도메인 | `vt_site` | url, dmn_addr, risk_grd, is_malicious | TB_WEB_DMN+URL | dmn_addr 분리 |
| 파일 | `vt_file` | file_nm, hash_val, file_sz, file_extsn_nm | TB_DGTL_FILE_INVNT | hash_val 통일 |
| 사용자 ID | `vt_id` | user_id, platform, nickname | — | — |
| 차량 | `vt_vhcl` | vhclno, carmdl_nm, ownr_nm | TB_VHCL_MST | — |
| 이메일 | `vt_email` | email_addr, domain | TB_EML_TRNS_EVT | ✅ 신규 |
| 가상자산 | `vt_crypto` | wallet_addr, asset_type, exchange | — | — |
| 기기 | `vt_dev` | device_id, imei, mac_addr, device_type | — | — |
| ATM | `vt_atm` | atm_id, bank, address, loc_id | — | CCOP 고유 |
| 키워드 | `vt_keyword` | keyword_id, keyword_nm, real_mean_nm, category | TB_DRUG_SLANG | ✅ 신규 |

### LAYER 3: LOCATION

| 노드 | GDB 라벨 | 핵심 속성 | 경찰청 대응 | 비고 |
|------|---------|----------|------------|------|
| 위치 | `vt_loc` | loc_id, address, lat, lng, place_name, place_type | 다수 테이블 좌표 컬럼 | ✅ 독립화 |
| 기지국 | `vt_bsst` | bsst_id, bsst_nm, bsst_addr, lat, lng | TB_GEO_MBL_LOC_EVT | ✅ 신규 |
| CCTV | `vt_cctv` | cctv_id, inst_loc_nm, lat, lng, operator | TB_VHCL_LPR_EVT | ✅ 신규 |

### LAYER 4: EVENT

| 노드 | GDB 라벨 | 핵심 속성 | 경찰청 대응 |
|------|---------|----------|------------|
| 이체 | `vt_transfer` | transfer_id, amount, dlng_se_cd, dlng_memo_cn | TB_FIN_BACNT_DLNG |
| 통화 | `vt_call` | call_id, call_dur_sec, call_typ_cd | TB_TELNO_CALL_DTL |
| 접속 | `vt_access` | access_id, url, access_time, user_agent | — |
| 메시지 | `vt_msg` | msg_id, content_hash, platform, spam_yn | TB_TELNO_SMS_MSG + TB_CHAT_MSG |
| LPR 인식 | `vt_lpr_evt` | rcgn_sn, vhclno, cctv_id, timestamp | TB_VHCL_LPR_EVT |
| 기지국 위치 | `vt_loc_evt` | loc_evt_sn, telno, evt_typ_nm, timestamp | TB_GEO_MBL_LOC_EVT |

---

## 7. Provenance 메타 레이어 설계

### 7.1 현행 방식의 한계

```cypher
-- 현재 (문제: 소스 추적 불가, 교차검증 불가)
(vt_psn:홍길동)-[has_account {confidence: 0.8}]->(vt_bacnt:110-xxx)
```

어느 기관에서 제공한 데이터인지, 언제 수집되었는지, 독립적으로 확인되었는지 알 수 없음.

### 7.2 vt_src 소스 노드

```cypher
-- 소스 노드 (수집 기관별 한 번만 생성, 재사용)
CREATE (:vt_src {
    src_id:           'src-dutcheat-2026',
    src_name:         '더치트',
    src_type:         'OSINT',            -- OFFICIAL / AGENCY / PETITION / OSINT / REPORT
    reliability_tier: 4,                  -- 1=최고신뢰 ~ 5=미확인
    collector:        'batch-etl-v2',     -- 수집 시스템/수사관 ID
    collected_at:     '2026-03-15T09:00:00',
    contact:          'https://thecheat.co.kr'
})
```

**src_type 분류**:

| src_type | 설명 | reliability_tier |
|----------|------|-----------------|
| `OFFICIAL` | 영장·법원 결정·금융거래확인서 | 1 |
| `AGENCY` | 금감원·경찰청 공유·통신사 제출 | 2 |
| `PETITION` | OCR/NER 완료 진정서 | 3 |
| `OSINT` | 더치트, WHOIS, VirusTotal, SNS | 4 |
| `REPORT` | 익명 제보, 자진 신고 | 5 |

### 7.3 vt_assertion 주장 노드

검증되지 않은 주장을 엔티티로 분리 저장:

```cypher
-- 더치트에서 수집된 주장 (아직 수사관 검증 전)
CREATE (a:vt_assertion {
    assertion_id:  'asrt-20260315-001',
    claim_type:    'has_account',          -- 주장 유형
    subject_id:    'psn-홍길동-001',        -- 주어 노드 ID
    object_id:     'bacnt-110-1234-5678',  -- 목적어 노드 ID
    credibility:   3,                      -- 1=확인됨 ~ 5=미상 (GraphAware 기준)
    confidence:    0.80,                   -- 0.0~1.0
    valid_from:    '2024-01-15',
    valid_to:      null,
    rec_created:   '2026-03-15T09:05:00',
    verified:      false,
    verified_by:   null,
    verified_at:   null,
    notes:         '더치트 피해신고 3건에서 동일 계좌 언급'
})-[:SOURCED_FROM]->(:vt_src {src_id: 'src-dutcheat-2026'})
```

### 7.4 주장 → 사실 승격 규칙

```python
# 자동 승격 조건 (confidence_fusion 서비스)
PROMOTION_RULES = {
    # 단일 소스 검증 (수사관 직접 확인)
    'manual_verify': lambda a: a.credibility == 1 and a.verified_by is not None,

    # 다중 소스 교차검증 (D-S 결합 스코어)
    'multi_source':  lambda assertions: (
        len(set(a.src_type for a in assertions)) >= 2 and
        dempster_shafer_combine([a.confidence for a in assertions]) >= 0.90
    ),

    # Tier 1 소스 단독 (공식 문서)
    'official_doc':  lambda a: a.src_type == 'OFFICIAL' and a.confidence >= 0.95
}
```

---

## 8. 엣지 메타속성 표준 v2

### 8.1 EDGE_META_SCHEMA_V2

```python
EDGE_META_SCHEMA_V2 = {
    # ── 출처 추적 (Provenance) ──────────────────────────────────────
    'source_id':        str,    # vt_src.src_id 참조 (필수)
    'assertion_id':     str,    # vt_assertion.assertion_id 참조 (선택)

    # ── 신뢰도 (Confidence) ─────────────────────────────────────────
    'confidence':       float,  # 0.0~1.0 (STIX 컨벤션 기반)
    'credibility':      int,    # 1~5 (GraphAware 5단계)
                                #   1=확인됨, 2=거의확실, 3=가능성있음,
                                #   4=의심스러움, 5=사실여부미상
    'verified':         bool,   # False=주장, True=검증완료
    'verified_by':      str,    # 검증 수사관 ID (verified=True 시 필수)
    'verified_at':      str,    # 검증 일시 ISO8601

    # ── 이중시간 (Bitemporal) ──────────────────────────────────────
    'valid_from':       str,    # ISO8601 — 현실에서 유효한 시작 시점
    'valid_to':         str,    # ISO8601 — 현실에서 유효한 종료 시점 (null=현재진행)
    'rec_created':      str,    # ISO8601 — DB 기록 시점 (Transaction Time 시작)
    'rec_updated':      str,    # ISO8601 — 마지막 수정 시점

    # ── 생성 주체 ────────────────────────────────────────────────────
    'created_by':       str,    # 수사관 ID 또는 시스템 식별자
    'creation_method':  str,    # 'direct_input' | 'ocr_ner' | 'osint' | 'inference' | 'etl'
}
```

### 8.2 주요 엣지 타입 정의 (역할 표현 포함)

```
[Case → Person]
  suspect_in      : 피의자로서 사건에 연루
  victim_in       : 피해자로서 사건에 연루
  witness_in      : 참고인으로서 사건에 연루
  investigated_by : 수사관이 사건을 담당

[Person → Object]
  has_account     : 계좌 소유 (valid_from/to로 소유 기간 표현)
  owns_phone      : 전화번호 소유 또는 사용
  drives_vehicle  : 차량 운행 또는 소유
  uses_email      : 이메일 주소 사용
  used_ip         : IP 주소 사용 이력
  uses_id         : 디지털 ID/닉네임 사용

[Object → Object]
  transferred_to  : 계좌 간 자금 이체 (amount, hop_level 포함)
  contacted       : 전화번호 간 통화 (count, duration 집계)
  linked_to       : 일반 연결 (구체적 관계 미확인 시)
  accessed        : IP → 사이트 접속

[Event → Object/Location]
  from_account    : 이체 출발 계좌
  to_account      : 이체 도착 계좌
  caller          : 발신 전화번호
  callee          : 수신 전화번호
  occurred_at     : 이벤트 발생 위치

[Entity Resolution]
  sameAs          : 동일 엔티티 (다른 소스, 다른 이름)
  contradicts     : 모순 관계 (명의도용, 위장 신분)
  derived_from    : 파생 엔티티 (원본 → 복사본)
```

---

## 9. 이중시간 모델 (Bitemporal)

### 9.1 시간 혼동 문제 예시

```
상황: 전처리 기관이 2023년 진정서와 2026년 진정서를 오늘(2026-04-01) 동시 전송

created_at만 사용 시:
  - 두 진정서 모두 rec_created = '2026-04-01'
  - "이 정보는 언제의 현실을 반영하는가?" → 알 수 없음

이중시간 적용 시:
  - 진정서A: valid_from='2023-05-10', rec_created='2026-04-01'
  - 진정서B: valid_from='2026-03-15', rec_created='2026-04-01'
  → "2023년에 이 계좌가 사기에 사용되었다"는 별도 사실로 분리 가능
```

### 9.2 Cypher 쿼리 패턴

```cypher
-- 특정 시점 기준 유효한 엣지만 조회 (Valid Time 쿼리)
MATCH (p:vt_psn)-[r:has_account]->(a:vt_bacnt)
WHERE r.valid_from <= '2024-06-01'
  AND (r.valid_to IS NULL OR r.valid_to >= '2024-06-01')
RETURN p, r, a

-- 특정 날짜에 기록된 엣지 감사 (Transaction Time 쿼리)
MATCH ()-[r]->()
WHERE r.rec_created >= '2026-03-01'
  AND r.rec_created < '2026-04-01'
  AND r.created_by = 'etl-batch-v2'
RETURN type(r), count(r) AS count

-- 이중시간 복합 쿼리: "2024년 실제 상황을 2026년 3월에 입력한 엣지"
MATCH (p:vt_psn)-[r:has_account]->(a:vt_bacnt)
WHERE r.valid_from <= '2024-12-31'
  AND r.rec_created >= '2026-03-01'
RETURN p.name, a.account_no, r.valid_from, r.rec_created, r.source_id
```

---

## 10. 엔티티 해소 패턴

### 10.1 sameAs 엣지 (동일 엔티티 연결)

```cypher
-- 동일 인물이 다른 소스에서 다른 이름으로 등장
CREATE (psn_a)-[:sameAs {
    match_score:    0.92,
    match_basis:    ['phone', 'account', 'name_similar'],
    reviewed_by:    'investigator-01',
    review_status:  'confirmed',   -- pending | confirmed | rejected
    rec_created:    '2026-03-20',
    source_id:      'src-system-er'
}]->(psn_b)
```

### 10.2 자동 후보 생성 규칙

```python
ENTITY_RESOLUTION_RULES = {
    'vt_psn': [
        # 강한 후보: 전화번호 + 계좌 2개 이상 공유
        {'criteria': ['shared_phone', 'shared_account'], 'min_count': 2, 'initial_score': 0.85},
        # 약한 후보: 이름 유사도 + 전화번호 1개 공유
        {'criteria': ['name_similarity >= 0.9', 'shared_phone'], 'initial_score': 0.70},
    ],
    'vt_bacnt': [
        # 동일 계좌번호, 다른 은행코드 → 명백히 다름
        {'criteria': ['same_account_no', 'diff_bank_cd'], 'action': 'skip'},
        # 동일 계좌번호 + 동일 은행코드, 다른 소스
        {'criteria': ['same_account_no', 'same_bank_cd'], 'initial_score': 0.99},
    ]
}
```

### 10.3 contradicts 엣지 (모순 표시)

```cypher
-- 명의도용 또는 위장 신분 탐지
CREATE (psn_a)-[:contradicts {
    conflict_field:  'rrno',
    conflict_detail: '주민번호 불일치 (A:850101, B:901215)',
    detected_by:     'er-service-v2',
    rec_created:     '2026-03-22'
}]->(psn_b)
```

---

## 11. 경찰청 표준 컬럼 정렬표

### 11.1 기존 노드 속성 수정

| 경찰청 표준 컬럼 | CCOP 노드 | 현행 속성 | v2 변경 |
|----------------|-----------|----------|---------|
| `TB_PRSN.RRNO` | `vt_psn` | id_no | `rrno_hash` (SHA-256, 평문 미저장) |
| `TB_PRSN.PRSN_SE_CD` | `vt_psn` | role (속성) | **속성 제거** → 역할 엣지로 이동 |
| `TB_FIN_BACNT.BANK_CD` | `vt_bacnt` | 없음 | `bank_cd` 추가 (복합 PK 정렬) |
| `TB_FIN_BACNT.BANK_NM` | `vt_bacnt` | bank (문자열) | `bank_nm` 로 변경 |
| `TB_FIN_BACNT.DPSTR_NM` | `vt_bacnt` | account_holder | `dpstr_nm` 추가 (명의자) |
| `TB_TELNO_MST.TELCO_NM` | `vt_telno` | telecom | `telco_nm` 정렬 |
| `TB_TELNO_MST.JOIN_TYP_CD` | `vt_telno` | 없음 | `join_typ_cd` 추가 (개인/법인) |
| `TB_INST.INST_SE_CD` | `vt_org` | org_type | `inst_se_cd` 코드화 |
| `TB_INST.BRNO` | `vt_org` | 없음 | `brno` 추가 (사업자등록번호) |
| `TB_WEB_DMN.IP_ADDR` | `vt_site` | 속성 | `vt_ip` 노드로 분리 후 엣지 연결 |
| `TB_DGTL_FILE_INVNT.HASH_VAL` | `vt_file` | hash_sha256 | `hash_val` 로 통일 (SHA-256, 64자) |

### 11.2 신규 노드 (경찰청 표준 기반)

| 경찰청 테이블 | CCOP 신규 노드 | 레이어 |
|-------------|--------------|--------|
| TB_VHCL_MST | `vt_vhcl` | Object | 이미 v2 추가됨 |
| TB_INST | `vt_org` 확장 | Person | 기존 vt_org에 컬럼 추가 |
| TB_EML_TRNS_EVT | `vt_email` | Object | 신규 |
| TB_GEO_MBL_LOC_EVT | `vt_bsst` + `vt_loc_evt` | Location + Event | 신규 |
| TB_VHCL_LPR_EVT | `vt_cctv` + `vt_lpr_evt` | Location + Event | 신규 |
| TB_DRUG_SLANG | `vt_keyword` | Object | 신규 |

### 11.3 RDB 보관 (그래프에 올리지 않는 대용량 이벤트)

| 경찰청 테이블 | 이유 | 그래프 연결 방식 |
|-------------|------|----------------|
| TB_FIN_BACNT_DLNG (거래내역) | 건당 레코드, 수백만 건 가능 | `vt_transfer` 노드로 집계 요약만 |
| TB_TELNO_CALL_DTL (CDR) | 통화 건수 대용량 | 통화 횟수·총시간만 엣지 속성으로 |
| TB_TELNO_SMS_MSG (SMS) | 메시지 원문 포함 | `vt_msg` 노드로 해시·메타만 |
| TB_CHAT_MSG (메신저) | 대화 내용 대용량 | `vt_msg` 노드로 content_hash만 |
| TB_GEO_TRST_CARD_TRIP (교통카드) | 이동 기록 대용량 | 주요 장소만 `vt_loc_evt`로 |
| TB_SYS_LGN_EVT (로그인) | 시스템 감사 로그 | 의심 패턴 감지 시에만 `vt_access`로 |

---

## 12. RDB-Graph 하이브리드 분담

```
┌─────────────────────────────────────────────────────────────┐
│  AgensGraph (그래프 DB) — 관계망·분석·시각화               │
│                                                             │
│  • 핵심 엔티티 노드 (vt_* 22종)                            │
│  • 출처 메타 레이어 (vt_src, vt_assertion)                  │
│  • 관계 엣지 (소유·이체·통화·접속 관계망)                   │
│  • 엔티티 해소 (sameAs, contradicts)                        │
│  • Multi-hop 경로 분석 (자금흐름, 연락망)                   │
│  • 커뮤니티 탐지, 중심성 분석                               │
└────────────────────┬────────────────────────────────────────┘
                     │ Cypher SELECT / JOIN
┌────────────────────▼────────────────────────────────────────┐
│  PostgreSQL (RDB) — 대용량 이벤트·감사·코드 테이블           │
│                                                             │
│  • TB_FIN_BACNT_DLNG  (거래내역 수백만 건)                  │
│  • TB_TELNO_CALL_DTL  (CDR)                                │
│  • TB_TELNO_SMS_MSG   (문자 메시지)                         │
│  • TB_CHAT_MSG        (메신저 대화)                         │
│  • TB_GEO_TRST_CARD_TRIP (교통카드)                        │
│  • TB_SYS_LGN_EVT    (시스템 감사 로그)                    │
│  • 코드 테이블 (사건유형, 은행코드, 범죄유형 등)             │
└─────────────────────────────────────────────────────────────┘
```

**연결 포인트**: Graph의 `vt_transfer` 노드가 RDB의 `TB_FIN_BACNT_DLNG` 상세 레코드를 `dlng_sn`으로 참조. 분석은 그래프에서, 원본 데이터 드릴다운은 RDB에서.

---

## 13. 구현 로드맵

### Phase 1 — 메타속성 표준화 (즉시 가능, 코드 변경 최소)

```
목표: 기존 노드/엣지 구조 변경 없이 출처·시간 속성 추가

[ ] EDGE_META_SCHEMA_V2 ontology_service.py 반영
[ ] 엣지 생성 시 source_id, rec_created 필수 입력 강제
[ ] valid_from / rec_created 분리 (기존 created_at → rec_created 백필)
[ ] vt_src 노드 타입 등록 (소스 기관 5개 우선 등록)
[ ] creation_method 필드 추가 (etl/manual/osint/inference)
```

### Phase 2 — 노드 확장 + Location 독립화 (단기)

```
목표: 경찰청 표준 Coverage + 공간 분석 강화

[ ] vt_loc 독립 노드 생성 (ATM/CCTV/기지국 좌표 참조로 전환)
[ ] vt_email 노드 신규 추가
[ ] vt_keyword 노드 신규 추가 (마약 은어 사전 → ChromaDB RAG 연동)
[ ] vt_bacnt에 bank_cd 추가 + 경찰청 복합 PK 정렬
[ ] vt_psn.role 속성 제거 → suspect_in/victim_in/witness_in 엣지 생성
[ ] credibility 1~5 필드 추가 (기존 confidence와 병행)
[ ] vt_bsst, vt_cctv 노드 추가
```

### Phase 3 — Assertion + 엔티티 해소 + Confidence Fusion (중기)

```
목표: 다중 소스 교차검증 자동화, D-S 증거 융합

[ ] vt_assertion 노드 타입 구현
[ ] 전처리 기관 유입 데이터 → assertion으로 저장 후 검증 UI
[ ] sameAs/contradicts 자동 후보 탐지 서비스
[ ] 수사관 검토 UI (엔티티 해소 승인/거부 화면)
[ ] confidence_fusion 서비스 (D-S 결합 스코어 계산)
[ ] 자동 verified 승격 로직 (임계값 0.90 + 2개 이상 소스)
[ ] 이중시간 쿼리 지원 (Valid Time / Transaction Time 독립 조회)
```

---

## 변경 요약 (Keep / Modify / Add)

| 분류 | 항목 | 내용 |
|------|------|------|
| **Keep** | vt_psn, vt_bacnt, vt_telno, vt_ip, vt_site, vt_file, vt_id, vt_atm | 기존 노드 유지 (속성 일부 추가) |
| **Keep** | vt_vhcl, vt_org, vt_persona, vt_dev, vt_crypto | v2에서 추가된 노드 유지 |
| **Keep** | vt_transfer, vt_call, vt_access, vt_msg, vt_loc_evt, vt_lpr_evt | 이벤트 노드 유지 |
| **Modify** | vt_psn | role 속성 제거, id_no → id_no_hash |
| **Modify** | vt_bacnt | bank_cd, dpstr_nm 추가 |
| **Modify** | vt_telno | telco_nm, join_typ_cd 추가 |
| **Modify** | vt_org | inst_se_cd, brno 추가 |
| **Modify** | vt_file | hash_val 표준화 (64자 SHA-256) |
| **Modify** | 모든 엣지 | EDGE_META_SCHEMA_V2 적용 |
| **Add** | `vt_src` | 소스 기관 노드 (Provenance) |
| **Add** | `vt_assertion` | 검증 전 주장 레코드 |
| **Add** | `vt_loc` | 위치 독립 노드 |
| **Add** | `vt_bsst` | 기지국 노드 |
| **Add** | `vt_cctv` | CCTV 설치지점 노드 |
| **Add** | `vt_email` | 이메일 주소 노드 |
| **Add** | `vt_keyword` | 분석 키워드·은어 사전 노드 |
| **Add** | `suspect_in`, `victim_in`, `witness_in` | 역할 엣지 (기존 role 속성 대체) |
| **Add** | `sameAs`, `contradicts` | 엔티티 해소 엣지 (v1 설계 → v2 구현) |

---

*본 문서는 CCOP 온톨로지 v2 설계의 기준 문서입니다.*
*구현 시 이 문서를 기준으로 `ontology_service.py`를 업데이트하고 변경 이력을 git으로 관리합니다.*
