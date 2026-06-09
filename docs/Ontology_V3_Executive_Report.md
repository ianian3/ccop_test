> ## ⚠️ DEPRECATED — V4.0 통합본 사용 권장
>
> 이 문서는 **CCOP 온톨로지 V3.0** 명세입니다. **2026-05-21부로 V4.0으로 통합되어 deprecated** 되었습니다.
>
> **현행 SSOT**: [`docs/CCOP_ONTOLOGY_V4.0.md`](CCOP_ONTOLOGY_V4.0.md)
> **코드 SSOT**: `app/middleware/services/ontology_service.py:KICSCrimeDomainOntology`
>
> V4.0은 V3.7 카탈로그(25 노드 / 53 엣지)를 그대로 유지하면서, 도메인 사용 매트릭스 / 식별자 형식 / 추론 규칙을 표준 메타로 격상한 통합본입니다. 본 문서는 **역사적 참고용**으로만 보존됩니다.
>
> ---
>

# CCOP 지식 그래프 V3.1 (POLE 아키텍처) 설계 결과 보고서

**최초 작성일**: 2026-04-03
**최종 업데이트**: 2026-04-06
**문서 상태**: V3.1 (확정)
**주제**: CCOP 지식 그래프 및 RDB 표준 데이터베이스 통합 아키텍처 구축
**구현 파일**: `app/middleware/services/ontology_service.py`, `app/middleware/services/rdb_to_graph_service.py`

---

## 개정 이력

| 버전 | 날짜 | 주요 변경 내용 |
| :--- | :--- | :--- |
| V3.0 | 2026-04-03 | 최초 확정 — POLE 6레이어, 22노드, 49엣지, Bitemporal, Provenance |
| V3.1 | 2026-04-06 | 온톨로지·ETL 정합성 점검 완료, `impersonates` 엣지 신설, 노드 PK 정규화, ETL Phase 6E 추가 |

---

## 1. 개요 및 추진 배경

본 보고서는 CCOP(차세대 사이버범죄 수사 플랫폼)의 핵심 기반 기술인 **지식 그래프 온톨로지의 설계 및 구현 결과**를 보고합니다.

기존 V1.0/V2.0 아키텍처에서 발생했던 노드 종류의 무분별한 팽창, 범죄 사실과 추정 정보의 혼재, 그리고 시계열 추적의 어려움을 근본적으로 해결하기 위해 **경찰청 데이터 표준(RDB)**과 연동되는 고도화된 정규화 아키텍처를 도입했습니다. 특히 도입 예정인 **Text-to-Cypher (sLLM 기반 쿼리 자동 생성)**의 인지 한계와 할루시네이션(환각)을 최소화하는 데 중점을 두어 설계되었습니다.

V3.1은 외부 도메인 전문가(스카이월드와이드) 문서의 온톨로지 설계 관점 분석을 통해 식별된 **사칭(Impersonation) 범죄 모델링 누락**을 보완하고, 코드 파싱 기반 정합성 점검으로 발견된 **7건의 엣지 오류 및 4건의 노드 PK 오류**를 전면 수정한 버전입니다.

---

## 2. 주요 혁신 포인트 (As-Is vs To-Be)

### 2.1 V2 → V3.0 혁신 (기존)

| 구분 | V2 (과거) | V3.0 | 개선 효과 |
| :--- | :--- | :--- | :--- |
| **노드 복잡도** | 28개 (기능별 파편화) | **22개 (핵심 개체 통합)** | 그래프 혼잡도 21% 하락, LLM 추론 속도 상승 |
| **역할 모델링** | 인물 속성에 저장 (`role: '피의자'`) | **방향성 엣지로 분리** (`suspect_in`) | 1명의 인물이 여러 사건에서 다른 역할을 하는 다중성 완벽 지원 |
| **위치 정보** | 기지국, CCTV 등 개별 노드 분리 | **`vt_loc` 통합** (`loc_type`으로 구분) | 공간·위치 기반(Geo-spatial) 질의의 복잡성 제거 |
| **출처/신뢰성** | 노드별 단순 문자열 기록 | **`vt_src` 노드 독립화 및 엣지 메타화** | 증거주의 타당성 확보 (Tier 1~Tier 5 신뢰도 필터링 가능) |
| **시간 모델링** | 시스템 적재 시간 단일 | **Bitemporal (이중 시간) 모델 적용** | 현실 유효 시간(`valid_from`)과 DB 기록 시간(`rec_created`) 분리 추적 |

### 2.2 V3.0 → V3.1 변경 (신규)

| 구분 | V3.0 | V3.1 | 개선 효과 |
| :--- | :--- | :--- | :--- |
| **사칭 범죄 모델링** | 표현 불가 (case_summary 문자열 의존) | **`impersonates` 엣지 신설** | 사칭 번호↔피사칭 기관 직접 연결, 패턴 탐지 가능 |
| **노드 PK 정규화** | vt_psn·vt_org 복합 PK 혼용 | **단일 PK 확정** (psn_id, org_id) | ETL MERGE 충돌 제거 |
| **복합 PK 명시** | vt_crypto·vt_id PK 불명확 | **복합 PK 확정** (wallet_addr+blockchain, id_val+platform) | 동일 주소 다중 체인 구분 |
| **이벤트 PK 통일** | transfer_id/call_id/msg_id 혼재 | **event_id 단일화** | ETL·온톨로지 정합성 확보 |
| **ETL 커버리지** | 27개 테이블 (vt_id/email/crypto/dev/atm/loc 미적재) | **49개 테이블 전체 (Phase 6E 추가)** | v3.0 신규 6개 노드 타입 완전 적재 |
| **엣지 수** | 활성 49개 | **활성 50개** | impersonates 신설 |
| **ETL 엣지 정합성** | filed_as 미구현 (linked_to 오용) | **filed_as 정정** (Petition→Case 표준) | 온톨로지 선언과 ETL 일치 |

---

## 3. 핵심 아키텍처: 6계층 POLE 모델

지식 그래프는 전 세계 수사 기관의 표준 관점인 **POLE (Person, Object, Location, Event)** 모델을 확장하여, 직관적이고 강력한 6계층 다층(Layered) 구조로 정립되었습니다.

1. **Source Layer (출처 계층, 1종)**
   * `vt_src`: KICS(경찰청), 더치트(OSINT) 등 데이터의 원천과 신뢰도 부여 (Tier 1~5).
2. **Case Layer (사건 계층, 2종)**
   * `vt_case` (공식 사건), `vt_petition` (수사 전 접수된 진정서). 진정서→사건 연결: `filed_as` 엣지.
3. **Person Layer (인물/조직 계층, 2종)**
   * `vt_psn` (사람, PK: psn_id), `vt_org` (조직명/기관명, PK: org_id).
   * 역할은 엣지로 표현: `suspect_in` / `victim_in` / `witness_in`.
4. **Object Layer (사물/매체 계층, 11종)**
   * 계좌(`vt_bacnt`, PK: account_no+bank_cd), 전화(`vt_telno`), IP(`vt_ip`), 디지털ID(`vt_id`, PK: id_val+platform), 가상자산지갑(`vt_crypto`, PK: wallet_addr+blockchain), 기기(`vt_dev`) 등.
5. **Location Layer (위치 계층, 1종)**
   * `vt_loc`: 주소, 기지국, 접속 위치 등 공간 정보를 단일 노드로 강력하게 묶음.
6. **Event Layer (행위/이벤트 계층, 5종)**
   * 이체(`vt_transfer`), 통화(`vt_call`), 이동(`vt_movement`), 접속(`vt_access`), 메시지(`vt_msg`). 모두 PK: `event_id`.

> **기술 인사이트:**
> 대용량 이벤트 정보(자금 이체내역, 통화 기록)는 RDB(PostgreSQL)에 보존하여 부하를 제어하고, 그래프에서는 핵심 흐름(Edge)과 식별 브릿지 키(Bridge Key)만을 가져가 시각적 '헤어볼(Hairball)' 현상을 방지합니다.

---

## 4. V3.1 신설: 사칭(Impersonation) 모델

### 4.1 신설 배경

전기통신금융사기(보이스피싱)의 핵심 수법인 **기관 사칭**이 V3.0에서 그래프 관계로 표현되지 못했습니다. 수사관이 "국민은행 사칭 번호 전체 조회"를 요청해도 `vt_case.case_summary` 자유문자열 검색에 의존해야 했으며, 동일 기관을 반복 사칭하는 조직 패턴 탐지가 불가능했습니다.

### 4.2 `impersonates` 엣지 스펙

```
(vt_telno) -[:impersonates]-> (vt_org)
(vt_id)    -[:impersonates]-> (vt_org)
(vt_email) -[:impersonates]-> (vt_org)
```

| 속성 | 타입 | 설명 |
| :--- | :--- | :--- |
| `impersonation_method` | string | `caller_id_spoofing` \| `fake_site` \| `fake_account` \| `email_spoofing` |
| `verified` | bool | 수사관 확인 여부 |
| `confidence` | float | 0.0~1.0 |
| `source_id` | string | 출처 소스 (MANDATORY) |
| `rec_created` | string | DB 기록 시점 ISO8601 (MANDATORY) |
| `valid_from` | string | 사칭 활동 시작일 |
| `valid_to` | string | 사칭 활동 종료일 (null=현재진행) |

**법적 근거**: 전기통신금융사기 피해 방지 및 피해금 환급에 관한 특별법 제3조

### 4.3 활성화된 수사 쿼리 패턴

```cypher
-- 특정 기관 사칭에 사용된 번호 전체 조회
MATCH (tel:vt_telno)-[:impersonates]->(org:vt_org {org_nm: '국민은행'})
RETURN tel.telno, org.org_nm

-- 동일 번호의 다기관 사칭 탐지
MATCH (tel:vt_telno)-[:impersonates]->(org:vt_org)
WITH tel, count(org) AS target_cnt
WHERE target_cnt > 1
RETURN tel.telno, target_cnt ORDER BY target_cnt DESC

-- 사칭 기관별 피해 사건 규모
MATCH (tel)-[:impersonates]->(org:vt_org)
MATCH (tel)-[:used_in]->(c:vt_case)
RETURN org.org_nm, count(DISTINCT c) AS case_cnt,
       sum(c.damage_amount) AS total_damage
ORDER BY case_cnt DESC
```

---

## 5. 증거주의적 접근: 메타 엣지와 엔티티 해소

### 5.1 Provenance (데이터의 이력과 근거)

수사관의 주관적 추정인지, 기관이 발급한 공식 데이터인지 분리합니다. 모든 그래프 엣지는 다음과 같은 속성을 의무 보유합니다.

* `confidence`: 0.0 ~ 1.0 (신뢰도 점수)
* `verified`: True / False (수사관 육안 검증 여부)
* `source_id`: 해당 관계를 수집한 원천 소스 (예: src-dutcheat)
* `rec_created`: ISO8601 DB 기록 시점 (MANDATORY)
* `creation_method`: `manual` \| `etl` \| `ocr_ner` \| `osint` \| `inference`

### 5.2 Entity Resolution (동일 인물 해소)

IP, 사용 기기, 유사 계좌 패턴 등을 기반으로 시스템이 "동일인(`sameAs` 엣지)" 가능성이 높은 대상을 추천합니다. 수사관이 이를 '승인(Confirmed)'하면 뿔뿔이 흩어져 있던 범죄 이력이 단일 노드 관점으로 통합되어 시각화됩니다.

---

## 6. 온톨로지·ETL 정합성 점검 결과 (V3.1 신규)

V3.0 설계 확정 후 코드 파싱 기반 자동 점검을 수행하여 아래 불일치를 발견하고 전면 수정했습니다.

### 6.1 노드 정합성 수정 (4건)

| 항목 | 문제 | 조치 |
| :--- | :--- | :--- |
| N-1: vt_psn PK | `[psn_id, name, korn_flnm]` 복합 → ETL MERGE 충돌 | 단일 PK `[psn_id]` 로 수정 |
| N-2: vt_org PK | `[org_id, org_name]` 복합 → org_name 변경 시 중복 생성 | 단일 PK `[org_id]` 로 수정 |
| N-3: vt_crypto PK | `[wallet_addr]` 단일 → 동일 주소 다중 체인 구분 불가 | 복합 PK `[wallet_addr, blockchain]` 로 수정 |
| N-4: 이벤트 노드 PK | transfer_id/call_id/msg_id 혼재 → ETL event_id와 불일치 | `event_id` 단일화 |

### 6.2 엣지 정합성 수정 (7건)

| 항목 | 문제 | 조치 |
| :--- | :--- | :--- |
| E-1: 미정의 타입 5건 | `owns`, `eg_used_ip`, `registered_to`, `contacted`, `performed`의 domain/range에 존재하지 않는 타입 참조 | 실제 레이어 타입으로 수정 |
| E-2: `resolved_to` 방향 역전 | 온톨로지 IP→도메인 / DNS 표준 도메인→IP 역방향 | `resolves_to`로 키명 변경 + domain/range 반전 |
| E-3: `transferred_to` 의미 불명 | 직접 생성 금지 추론 엣지임을 미명시 | `inferred: True` 명시 + meaning 수정 |
| E-4: `received_msg` 미등재 | ETL에서 사용 중이나 RELATIONSHIPS에 없음 | 신규 추가 (Message→Phone) |
| E-5: `sourced_from` 미등재 | ETL에서 사용 중이나 RELATIONSHIPS에 없음 | 신규 추가 (Any→Source) |
| E-6: `owns_vehicle` 미등재 | ETL에서 사용 중이나 RELATIONSHIPS에 없음 | 신규 추가 (Person→Vehicle) |
| E-7: `filed_as` 오용 | ETL에서 `linked_to`(범용) 사용, 온톨로지 표준 `filed_as` 미사용 | ETL 수정 (Petition→Case) |

### 6.3 ETL Phase 6E 추가 (6개 마스터 테이블)

V3.0 신규 노드 타입 6종이 ETL 파이프라인에서 적재되지 않던 문제를 해결했습니다.

| Phase | 원본 테이블 | 생성 노드 |
| :--- | :--- | :--- |
| 6E-1 | TB_DGTL_ID_MST | `vt_id` (PK: id_val+platform) |
| 6E-2 | TB_EMAIL_MST | `vt_email` |
| 6E-3 | TB_CRYPTO_WALLET_MST | `vt_crypto` (PK: wallet_addr+blockchain) |
| 6E-4 | TB_DEV_MST | `vt_dev` |
| 6E-5 | TB_ATM_MST | `vt_atm` |
| 6E-6 | TB_LOC_MST | `vt_loc` |

---

## 7. 온톨로지 현황 (V3.1 확정)

| 구분 | V3.0 | V3.1 |
| :--- | :--- | :--- |
| 노드 타입 | 22개 | **22개** (수 변동 없음, PK 정규화) |
| 활성 엣지 | 49개 | **50개** (+impersonates) |
| Deprecated 엣지 | 3개 | **3개** (involves, involves_org, involves_device) |
| 전체 엣지 | 52개 | **53개** |
| ETL 커버 테이블 | 27개 | **49개** (+TB_IMPRSN_REL 포함) |

---

## 8. 단계별 추진 과제

* **[Phase 1] 데이터 적재 파이프라인(ETL) 고도화 — 완료**
  * RDB 49개 마스터/관계 테이블 데이터를 V3.1 온톨로지 포맷에 맞게 AgensGraph로 마이그레이션.
  * `suspect_in` 역할 엣지, `filed_as` 진정서-사건 연결, Phase 6E 신규 6종 노드 적재, `impersonates` 사칭 엣지 포함.

* **[Phase 2] 고품질 평가/학습 데이터셋(SFT) 구축 — 진행 예정**
  * V3.1 온톨로지 기준으로 EXAONE sLLM 훈련을 위한 "질문-Cypher" 페어 데이터 재생성.
  * `impersonates` 엣지 활용 쿼리 500건 이상 포함 권장.
  * 범죄 분류 3계층(대/중/소) 기반 통계 쿼리 추가 예정.

* **[Phase 3] Text-to-Cypher 에이전트 연동 인프라 점검 — 예정**
  * 수사관이 웹에서 "2024년에 홍길동이 쓴 가상자산 지갑"을 치면, LangGraph RAG 에이전트가 V3.1 구조를 기반으로 정확한 Cypher를 생성하여 Bitemporal 쿼리 결과를 시각화.

---

## 9. 향후 검토 과제 (V3.2 후보)

| 항목 | 내용 | 우선순위 |
| :--- | :--- | :--- |
| 범죄 분류 3계층 속성 분리 | `crime_type` 단일 → `crime_cls_cd` / `crime_method_cd` / `crime_detail_cd` 3속성 분리 | MEDIUM |
| 경찰청 분류 코드 체계 확인 | 기존 `incdnt_typ_cd`와 독자 분류 체계 이중화 리스크 해소 | MEDIUM (선결 조건) |
| `impersonates` ETL 구현 | TB_SWINDL_DCLR 등 사칭기관 컬럼 매핑, OCR/NER verified=False 적재 | MEDIUM |
| SFT 데이터셋 재생성 | V3.1 신규 엣지 반영, Text2Cypher 정확도 +12%p 목표 | HIGH |

---

## 10. 결론 및 기대효과

CCOP 지식 그래프 V3.1 아키텍처는 **경찰 수사의 가장 근본적인 체계(정보 출처, 다중적 역할, 이중 시간대)**를 IT 시스템 언어(그래프 모델)로 번역한 V3.0 기반 위에, **전기통신금융사기의 핵심 수법인 사칭 범죄를 최초로 그래프 관계로 완전 표현**한 버전입니다.

코드 파싱 기반 정합성 점검을 통해 온톨로지 선언과 ETL 구현 간의 불일치 11건을 발견하고 전면 수정함으로써, 설계와 구현의 일치성을 보장하는 **검증된 아키텍처**로 격상되었습니다.

이 구조는 향후 고도화될 **'AI 정보분석관(Text2Cypher)'**이 범죄 수익의 다세대 세탁 계좌를 추적하고, 사칭 기관을 반복 활용하는 보이스피싱 조직의 은닉된 공범 네트워크를 역추적하는 데 있어 **가장 견고한 두뇌(Knowledge Base)** 역할을 수행하게 될 것입니다.
