> ## ⚠️ DEPRECATED — V4.0 통합본 사용 권장
>
> 이 문서는 **CCOP 온톨로지 V3.6 (OSINT)** 명세입니다. **2026-05-21부로 V4.0으로 통합되어 deprecated** 되었습니다.
>
> **현행 SSOT**: [`docs/CCOP_ONTOLOGY_V4.0.md`](CCOP_ONTOLOGY_V4.0.md)
> **코드 SSOT**: `app/middleware/services/ontology_service.py:KICSCrimeDomainOntology`
>
> V4.0은 V3.7 카탈로그(25 노드 / 53 엣지)를 그대로 유지하면서, 도메인 사용 매트릭스 / 식별자 형식 / 추론 규칙을 표준 메타로 격상한 통합본입니다. 본 문서는 **역사적 참고용**으로만 보존됩니다.
>
> ---
>

# CCOP 온톨로지 설계 보고서

> **버전:** v3.6
> **작성일:** 2026-04-24
> **작성 기준:** ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md / RDB_STANDARDIZATION_v3.6.md
> **상태:** 확정 — 코드 정합성 최종 검증 완료

---

## 1. 개요

CCOP(사이버범죄 수사 그래프 플랫폼)는 AgensGraph 기반의 지식 그래프를 핵심 분석 엔진으로 사용한다.
본 설계서는 v1(초기 KICS 4계층)부터 v3.6(POLE 정렬 6레이어)까지의 설계 진화를 정리하고,
v3.6에서 확정된 온톨로지 구조와 구현 상태를 기록한다.

---

## 2. 설계 진화 요약

| 버전 | 핵심 변경 | 노드 | 엣지 |
|------|----------|------|------|
| v1 (초기) | KICS 4계층, Provenance 없음 | 21 | 27 |
| v2 | 진정서·OSINT 추가, vt_assertion 실험 | 28+ | 40+ |
| v3.0~v3.2 | POLE 정렬 6레이어 확정, vt_src 도입 | 22 | 42 |
| v3.3 | vt_impersonation 노드 승격 | 23 | 44 |
| v3.4 | operates/recruits/blackmails/hosts/contains_file/located_at 추가 | 23 | 45 |
| v3.5 | 코드 교차검증 10종 반영, accessed_to 복원, eg_used_* 등재 | 23 | **52** |
| **v3.6** | sourced_from 생성 규칙 확정, 코드 버그 3건 수정 | **23** | **52** |

---

## 3. 아키텍처 — 6레이어 POLE 모델

```
╔══════════════════════════════════════════════════════════════════╗
║  LAYER 0. SOURCE — 데이터 출처 (수직 관통)                         ║
║  vt_src  (신뢰등급 Tier 1~5)                                      ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 1. CASE — 수사 맥락                                        ║
║  vt_case  vt_petition                                            ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 2. PERSON — 행위 주체  (POLE-P)                            ║
║  vt_psn   vt_org                                                 ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 3. OBJECT — 객체·증거  (POLE-O)                            ║
║  vt_bacnt  vt_telno  vt_ip   vt_site   vt_file  vt_id           ║
║  vt_vhcl   vt_email  vt_crypto  vt_dev  vt_atm                  ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 4. LOCATION — 위치  (POLE-L)                              ║
║  vt_loc                                                          ║
╠══════════════════════════════════════════════════════════════════╣
║  LAYER 5. EVENT — 시공간 행위  (POLE-E)                           ║
║  vt_transfer  vt_call  vt_msg  vt_access                         ║
║  vt_movement  vt_impersonation                                   ║
╚══════════════════════════════════════════════════════════════════╝
```

**레이어 간 관계 방향 원칙**:
- `Source ← 모든 레이어` — 데이터 노드가 출처를 역참조 (sourced_from)
- `Case ↔ Person` — 역할 엣지 (suspect_in / victim_in / witness_in)
- `Person → Object` — 소유·사용 (has_account / owns_phone / uses_id ...)
- `Object → Location` — 귀속 위치 (located_at)
- `Event → Object/Location` — 이벤트가 주체·위치를 참조

---

## 4. 노드 카탈로그 (23개 확정)

### 4.1 Source Layer (1)

| 노드 | 역할 | 핵심 식별자 | RDB 테이블 |
|------|------|------------|-----------|
| `vt_src` | 데이터 출처 (Tier 1~5) | `src_id` | TB_DATA_SRC |

**reliability_tier 기준**:

| Tier | 구분 | 예시 |
|------|------|------|
| 1 | 공식 수사자료 | 영장 집행 결과, 금융거래확인서 |
| 2 | 기관 연계 | 금감원·경찰청 공유 DB, KICS 연동 |
| 3 | 전처리 진정서 | OCR/NER 완료 진정서, 배치 유입 |
| 4 | OSINT | 더치트, WHOIS, VirusTotal |
| 5 | 미확인 제보 | 익명 신고, 출처 불명 |

### 4.2 Case Layer (2)

| 노드 | 역할 | 핵심 식별자 | RDB 테이블 |
|------|------|------------|-----------|
| `vt_case` | 정식 수사 사건 | `flnm` | TB_INCDNT_MST |
| `vt_petition` | 진정서/신고 (수사 전·후) | `petition_id` | TB_PETTN_MST |

### 4.3 Person Layer (2)

| 노드 | 역할 | 핵심 식별자 | RDB 테이블 |
|------|------|------------|-----------|
| `vt_psn` | 인물 (피의자·피해자·참고인 통합) | `psn_id` | TB_PRSN |
| `vt_org` | 조직/기관 (범죄단체·합법기관 통합) | `org_id` | TB_INST |

> 역할(Role)은 노드 속성이 아닌 엣지 타입으로 표현. `vt_psn.role` 속성 없음.

### 4.4 Object Layer (11)

| 노드 | 역할 | 핵심 식별자 | RDB 테이블 |
|------|------|------------|-----------|
| `vt_bacnt` | 금융계좌 | `account_no` + `bank_cd` | TB_FIN_BACNT |
| `vt_telno` | 전화번호 | `telno` | TB_TELNO_MST |
| `vt_ip` | IP주소 | `ip_addr` | TB_IP_MST (v3.5 신설) |
| `vt_site` | 웹사이트/URL | `url_addr` | TB_WEB_DMN |
| `vt_file` | 파일/디지털 증거 | `hash_val` (SHA-256) | TB_DGTL_FILE_INVNT |
| `vt_id` | 디지털 식별자 (계정·닉네임) | `id_val` + `platform` | TB_DGTL_ID_MST |
| `vt_vhcl` | 차량 | `vhclno` | TB_VHCL_MST |
| `vt_email` | 이메일 | `email_addr` | TB_EMAIL_MST |
| `vt_crypto` | 가상자산 지갑 | `wallet_addr` | TB_CRYPTO_WALLET_MST |
| `vt_dev` | 기기 (폰·PC) | `device_id` | TB_DEV_MST |
| `vt_atm` | ATM | `atm_id` | TB_ATM_MST |

### 4.5 Location Layer (1)

| 노드 | 역할 | 핵심 식별자 | RDB 테이블 |
|------|------|------------|-----------|
| `vt_loc` | 위치 통합 (주소·기지국·CCTV) | `loc_id` + `loc_type` | TB_LOC_MST |

### 4.6 Event Layer (6)

| 노드 | 역할 | Bridge Key | RDB 테이블 |
|------|------|-----------|-----------|
| `vt_transfer` | 금융 이체 | `dlng_sn` | TB_FIN_BACNT_DLNG |
| `vt_call` | 통화 | `call_sn` | TB_TELNO_CALL_DTL |
| `vt_msg` | 메시지 (SMS·채팅) | `msg_sn` | TB_TELNO_SMS_MSG |
| `vt_access` | 네트워크 접속 | `lgn_sn` | TB_SYS_LGN_EVT |
| `vt_movement` | 이동 이벤트 (LPR·기지국·교통카드 통합) | `rcgn_sn`/`loc_evt_sn`/`mv_sn` | TB_VHCL_LPR_EVT 외 2종 |
| `vt_impersonation` | 사칭 이벤트 (v3.3 노드 승격) | `event_id` | — |

---

## 5. 엣지 카탈로그 (52개 — 활성 51 unique)

### 5.1 구성 요약

| 카테고리 | 개수 | 대표 엣지 |
|----------|------|---------|
| Case 관련 | 7 | suspect_in / victim_in / witness_in / filed_as / related_case |
| Case → Object 증거 | 3 | eg_used_account / eg_used_phone / eg_used_ip |
| Person 소유·귀속 | 15 | has_account / owns_phone / member_of / sameAs / contradicts |
| Person v3.4 신규 | 3 | operates / recruits / blackmails |
| Object → Person 예외 | 1 | registered_to (⚠️ 레이어 예외 허용) |
| Object 관련 | 9 | transferred_to / resolves_to / hosts / communicated_with |
| Event 관련 | 10 | from_account / to_account / caller / callee / occurred_at |
| 사칭 범죄 | 2 | used_for / targets |
| Meta/Provenance | 2 | sourced_from / verified_by |
| **합계** | **52** | |

> `linked_to`는 §4.1(Petition→Case)과 §4.5(Object→Object) 양쪽에서 동명 사용.
> unique 타입 기준 51개. 쿼리 시 시작/끝 노드 라벨로 맥락 구분 필요.

### 5.2 sourced_from 구현 규칙 (v3.6 확정)

```
tier 1 (OFFICIAL) ─┐
tier 2 (AGENCY)   ─┤→ (node)-[:sourced_from]->(vt_src)  엣지 실제 생성
tier 3 (PETITION) ─┘   적용 노드: vt_case, vt_psn, vt_org,
                                  vt_bacnt, vt_telno, vt_petition

tier 4 (OSINT)    ─┐
tier 5 (REPORT)   ─┘→ node.source_id 속성만 사용 (엣지 폭발 방지)
```

### 5.3 엣지 공통 메타속성

```python
# 모든 엣지 필수
source_id       str   # vt_src.src_id 참조
rec_created     str   # ISO8601 기록 시점
creation_method str   # manual | etl | ocr_ner | osint | inference

# 소유·귀속 엣지 권장
confidence      float # 0.0~1.0
verified        bool  # False=주장, True=수사관 확인

# 소유관계 (시간 변화 가능) 선택
valid_from      str
valid_to        str   # null = 현재진행
```

### 5.4 이중시간 적용 대상

| 적용 ✅ | 비적용 ❌ |
|--------|---------|
| has_account, owns_phone, owns_vehicle, member_of, drives, uses_id, works_at, operates, registered_to | from_account, to_account, caller, callee, occurred_at, sourced_from |

---

## 6. 추론 규칙 (9개)

| 규칙명 | 패턴 | 신뢰도 | 출력 |
|--------|------|--------|------|
| OrganizedCrime | 동일 계좌/전화 3건+ 사건 공유 | 0.80 | accomplice_of |
| MoneyLaundering | 3단계+ 계좌이체 (hop≥3) | 0.75 | suspicious_transfer |
| Accomplice | 5건+ 공통 통화 대상 공유 | 0.70 | accomplice_of |
| BurnerAccount | 1시간 내 10건+ 이체 | 0.85 | vt_bacnt.is_burner=True |
| BurnerPhone | 선불폰 + 스팸신고 3건+ | 0.80 | vt_telno.is_burner=True |
| EntityResolutionCandidate | 동일 전화+계좌 1개 이상 공유 | 0.85 | sameAs (검토 필요) |
| CrossDomainHub | 동일 IP에서 다수 계좌+전화 접속 | 0.80 | hub_suspect 플래그 |
| NightCrimePattern | 00~06시 3건+ 이체/통화 | 0.65 | night_activity 플래그 |
| RecruitChainAccomplice | recruits 체인 2단계+ | 0.75 | accomplice_of |

---

## 7. RDB 연동 구조 (v3.6 기준 51개 테이블)

### 7.1 테이블 구성

| 영역 | 테이블 수 | 대표 테이블 |
|------|----------|-----------|
| 사건/진정서 | 4 | TB_INCDNT_MST, TB_PETTN_MST |
| 인물/조직 | 4 | TB_PRSN, TB_INST |
| 금융 | 5 | TB_FIN_BACNT, TB_FIN_BACNT_DLNG |
| 통신 | 6 | TB_TELNO_MST, TB_TELNO_CALL_DTL |
| 디지털 객체 | 8 | TB_DGTL_ID_MST, TB_EMAIL_MST, TB_IP_MST ★ |
| 차량/이동 | 3 | TB_VHCL_MST, TB_VHCL_LPR_EVT, TB_VHCL_OWNR_REL ★ |
| 위치 | 3 | TB_LOC_MST, TB_GEO_MBL_LOC_EVT |
| 출처 | 1 | TB_DATA_SRC |
| 법규/코드 | 8 | TB_CMN_CD, TB_CRIME_LAW_MAP |
| OSINT | 5 | TB_OSINT_IP_REP, TB_OSINT_SITE_REP |
| 시스템 | 4 | TB_SYS_LGN_EVT, TB_AUDIT_LOG |
| **합계** | **51** | ★ = v3.5 신설 |

### 7.2 핵심 Bridge Key 매핑

```
vt_transfer  ←→  TB_FIN_BACNT_DLNG  (dlng_sn)
vt_call      ←→  TB_TELNO_CALL_DTL  (call_sn)
vt_movement  ←→  TB_VHCL_LPR_EVT   (rcgn_sn)
vt_movement  ←→  TB_GEO_MBL_LOC_EVT (loc_evt_sn)
vt_movement  ←→  TB_GEO_TRST_CARD_TRIP (mv_sn)
vt_petition  ←→  TB_FRD_VCTM_RPT   (dclr_sn → raw_id)

# sourced_from Bridge (v3.6 확정)
vt_case/vt_psn/vt_org/vt_bacnt/vt_telno/vt_petition
  → TB_DATA_SRC.SRC_ID  (tier 1~3만 엣지 생성)
```

---

## 8. 구현 파일 현황

| 파일 | 역할 | 상태 |
|------|------|------|
| [docs/ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md](../docs/ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md) | 온톨로지 단일 기준 문서 | ✅ v3.6 확정 |
| [docs/RDB_STANDARDIZATION_v3.6.md](../docs/RDB_STANDARDIZATION_v3.6.md) | RDB 표준화 설계서 | ✅ v3.6 확정 |
| [app/middleware/services/ontology_service.py](../app/middleware/services/ontology_service.py) | 온톨로지 EDGE_CATALOG (1,742줄) | ✅ v3.6 갱신 |
| [app/middleware/services/rdb_to_graph_service.py](../app/middleware/services/rdb_to_graph_service.py) | 주력 ETL 서비스 (1,262줄) | ✅ sourced_from 추가 |
| [app/services/rdb_to_graph_service.py](../app/services/rdb_to_graph_service.py) | 레거시 ETL (transfer_case) | ✅ sourced_from 버그 수정 |
| app/middleware/services/graph_service.py | 그래프 탐색·시각화 (1,456줄) | ✅ 기존 유지 |

---

## 9. v3.6 코드 수정 내역

### 9.1 버그 수정 — app/services/rdb_to_graph_service.py

**문제**: `transfer_case()` 함수에서 `sourced_from` 엣지가 `vt_src` 대신 `vt_case`를 가리키고 있었음.

```python
# Before (버그) — 사건 노드로 연결
MATCH (c:vt_case {flnm: '...'}) MERGE (p)-[:sourced_from]->(c)

# After (수정) — 출처 노드로 연결
MERGE (s:vt_src {src_id: 'src-kics-official'})  # 함수 진입 시 보장
MATCH (s:vt_src {src_id: 'src-kics-official'})
MERGE (p)-[:sourced_from {src_tier: 1, rec_created: toString(datetime())}]->(s)
```

수정 위치: vt_psn(1645), vt_bacnt(1674), vt_telno(1700) 각 1행씩, 총 3행.

### 9.2 기능 추가 — app/middleware/services/rdb_to_graph_service.py

**문제**: 벌크 변환 시 vt_case, vt_psn, vt_org, vt_bacnt, vt_telno에 `sourced_from` 엣지가 생성되지 않았음.

**해결**: Phase 6A(vt_src 생성) 직후 `6A-post` 블록 추가. 5개 노드 타입에 대해:
1. 해당 RDB 테이블에 SRC_ID 컬럼이 있으면 → 개별 vt_src 노드로 연결
2. SRC_ID 컬럼 없으면 → `src-kics-agency`(tier 2) 기본 노드로 일괄 연결

### 9.3 버전 갱신 — app/middleware/services/ontology_service.py

- 모듈 docstring: v3.5 → v3.6
- 클래스 docstring: v3.5 → v3.6
- `sourced_from` 의미 설명: tier 기반 생성 규칙 반영

---

## 10. 설계 결정 사항 — 미해결 이슈

### 10.1 linked_to 중복 엣지명

현황: `linked_to`가 두 맥락에서 동명 사용.
- §4.1: `Petition → Case` (진정서와 기존 사건 연결)
- §4.5: `Object → Object` (범용 연결, 임시/추론)

대안:
- **A안 (현재)**: 노드 라벨로 맥락 구분, 쿼리 시 명시. DB 변경 없음.
- **B안**: §4.1의 `linked_to`를 `case_linked_to`로 rename. 기존 DB 마이그레이션 필요.

결정 기준: 운영 DB 레코드 존재 시 A안 유지. 신규 설치 또는 전체 재구성 시 B안.

### 10.2 Phase 3 미구현 기능

| 기능 | 설명 | 우선순위 |
|------|------|---------|
| EntityResolution 서비스 | sameAs 후보 자동 생성 | 높음 |
| confidence_fusion | D-S 결합 스코어 | 중간 |
| INFERENCE_RULES 자동 스케줄러 | 9개 규칙 자동 실행 | 중간 |
| Bitemporal UI | 날짜 슬라이더 Valid Time 필터 | 낮음 |

---

## 11. 핵심 쿼리 패턴 (참고용)

```cypher
-- 자금 흐름 3단계 추적
MATCH path = (start:vt_bacnt {account_no: '110-1234-5678'})
             -[:from_account|to_account*2..8]->(end:vt_bacnt)
WHERE ALL(r IN relationships(path) WHERE r.confidence >= 0.7)
RETURN path, length(path)/2 AS hop_count

-- 동일 인물 교차 사건
MATCH (c1:vt_case)<-[:suspect_in]-(p:vt_psn)-[:suspect_in]->(c2:vt_case)
WHERE c1 <> c2
RETURN p.name, collect(c2.flnm) AS related_cases

-- 출처 신뢰도 기반 필터 (tier 1~2만)
MATCH (p:vt_psn)-[r:has_account]->(a:vt_bacnt)
WHERE r.verified = true
  AND EXISTS {
    MATCH (src:vt_src {src_id: r.source_id})
    WHERE src.reliability_tier <= 2
  }
RETURN p, a

-- sourced_from 연결 현황 확인
MATCH (n)-[:sourced_from]->(s:vt_src)
RETURN labels(n)[0] AS node_type, s.src_name, s.reliability_tier, count(*) AS cnt
ORDER BY node_type, s.reliability_tier
```

---

*이 보고서는 CCOP 온톨로지 v3.6 설계의 단일 요약 기준입니다.*
*세부 명세는 ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md, RDB_STANDARDIZATION_v3.6.md를 참조하십시오.*
