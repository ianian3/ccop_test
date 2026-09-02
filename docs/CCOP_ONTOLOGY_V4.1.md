# CCOP 통합 온톨로지 V4.1 — 전체 설계 명세

**작성일**: 2026-07-31 (V4.0 2026-05-21 → V4.1 정합화)
**상태**: 기준 설계 명세 (**현행 SSOT 버전은 V4.8** — §15 변경 이력·코드 docstring 참조, 2026-09-02)
**대체 대상**: V4.0 (→ V4.1로 정합화·승격), V3.5 / V3.6 / V3.7 (deprecated)
**SSOT 코드**: `app/middleware/services/ontology_service.py:KICSCrimeDomainOntology`

> **V3.7 (수사 풀스택) + OSINT V3.6 (공개정보)** 통합 표준
> 단일 SSOT 카탈로그 + 도메인 사용 매트릭스 + 추론 규칙 + 표준 메타
> **V4.1**: V4.0의 카탈로그를 코드와 3자 정합화(엣지 60 확정, id 표준 정정) — §0.1 참조

---

## 0. V4.1 핵심 변화 한눈에

| 차원 | V3.7 (이전) | **V4.1 (현행)** |
|---|---|---|
| 카탈로그 | 25 노드 / 53 엣지(명목) | **25 노드 / 60 엣지** — 정합화로 의미·시각·엑셀 3자 실측 일치 (구 "53"은 명목 오류) |
| 의미론적 레이어 | POLE 6 | **POLE 6 + Hub 7** ⭐ (군집 허브 명시) |
| 도메인 사용 명시 | 암묵적 (보고서 산재) | **DOMAIN_USAGE 표준 메타** ⭐ (25 × 4) |
| 식별자 형식 | 표준 컬럼명만 | **NODE_ID_STANDARD 표준 메타** ⭐ (id_format) |
| 추론 규칙 | 산발적 | **INFERENCE_RULES_V37 표준** ⭐ (10종 카탈로그) |
| Provenance | reliability_tier 부분 | **모든 노드 source_domain + reliability_tier 의무화** ⭐ |
| Deprecated 정책 | 암묵적 | **read-only 표준화** ⭐ (clusters_with) |
| Cross-domain 연결 | 수동 | **sameAs + canonical_id + id_format 자동화 가능** ⭐ |

---

## 0.1 V4.0 → V4.1 변경 이력 (2026-07-31 정합화)

V4.1은 **새 노드/엣지를 추가하지 않는다.** V4.0 문서·코드·엑셀 3자를 대조해 발견한 카탈로그
불일치를 해소하고, 명목 수치를 실측으로 정정한 **정합화 릴리스**다.

### 배경 — 왜 필요했나
V4.0은 "엣지 53종"으로 표기했으나, 코드를 정적 분석하니 **의미 카탈로그(`RELATIONSHIPS`) 52 /
시각 카탈로그(`EDGE_STYLE_V40`) 55**로 셋 다 "53"과 달랐다. 즉 같은 엣지의 정의가 두 곳에
나뉘어(**이원화**) 동기화되지 않았고, "53"은 실측 근거 없는 명목치였다. 특히 **시각 스타일은
있으나 의미 정의가 없는 엣지 8종**은 화면엔 그려지면서도 T2C·검증·비주얼 쿼리에서 인식되지
않는 사각지대였다.

### 변경 항목

| # | 항목 | 내용 |
|---|------|------|
| **A** | 엣지 의미 등재 | 시각-only 8종(`involves`·`communicated_with`·`contacted`·`impersonates`·`owns_wallet`·`performed_by`·`uses_device`·`verified_by`)을 `RELATIONSHIPS`에 의미 정의(출발/도착/의미/법적의미) 등재 |
| **B** | 엣지 시각 등재 | 의미-only 2종(`used_ip`·`owns`)을 `EDGE_STYLE_V40`에 스타일 등재 |
| **C** | 보류 3종 처리 | `controls`(실질지배)·`located_at`(정적위치) 정식 등재, `owns_device`는 `uses_device` 별칭(deprecated) |
| **D** | id 표준 정정 | `NODE_ID_STANDARD.canonical_field`를 실제 MERGE 키에 맞춤: `vt_case` case_no→**flnm**, `vt_email`→**email_addr**, `vt_crypto`→**wallet_addr**, `vt_vhcl`→**vhclno**, `vt_movement`→**mov_id**. 이벤트 6종 id_format을 엑셀에서 plain→**uuid**로 정정(코드 기준) |
| **E** | 수치 삼면 동기화 | 코드 docstring·본 문서·엑셀의 "53" → **60** 통일 |
| **F** | 재발 방지 | `scripts/test_ontology_catalog_sync.py` 회귀 테스트 추가 — 시각-only 엣지 금지 + 노드 5구조 25 정합 검증 |

### 결과
- **엣지 60종**: `RELATIONSHIPS`(의미) = `EDGE_STYLE_V40`(시각) = 엑셀 = **60 완전 일치**
- **노드 25종**: 변동 없음 (id 표준 필드명만 실측 정정)
- 8종 엣지가 이제 T2C 스키마·검증 화이트리스트·비주얼 쿼리 컴파일러에서 **정식 인식**
- **D의 함의**: 표준 정의(NODE_ID_STANDARD)가 실제 ETL과 여러 곳 달랐고, **실제 MERGE 키가 현실**이었다(vt_case는 `case_no`가 아닌 `flnm`으로 저장). 표준을 현실에 맞춤

### 남은 과제 (V4.2 후보)
- 추론 규칙 이원화: `INFERENCE_RULES`(리스트 10) ↔ `INFERENCE_RULES_V37`(딕셔너리 4)의 구조 통합, `RelayStationDetection` 중복 정리, 문서가 약속한 `SameAsResolution` 구현/삭제 결정

---

## 1. 7 레이어 통합 아키텍처 (POLE + Hub)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CCOP V4.0 통합 온톨로지 (SSOT)                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ⓢ SOURCE        (1 노드 — 수직 관통, 모든 노드가 참조)                       │
│  ──────────                                                                 │
│   vt_src                                                                    │
│                                                                             │
│  ⓒ CASE          (3 노드 — 수사 사건/진정/군집)                              │
│  ──────────                                                                 │
│   vt_case          vt_petition         pt_cluster ⭐V4.0                    │
│                                                                             │
│  ⓟ PERSON        (2 노드 — 실인물/조직)                                     │
│  ──────────                                                                 │
│   vt_psn           vt_org                                                  │
│   └ is_anonymous⭐                                                          │
│                                                                             │
│  ⓞ OBJECT        (11 노드 — 디지털/물리 객체)                                │
│  ──────────                                                                 │
│   vt_bacnt         vt_telno            vt_ip            vt_site            │
│   vt_file          vt_id               vt_email         vt_crypto          │
│   vt_vhcl          vt_dev              vt_atm                              │
│                    └ dev_type='relay_station' ⭐                            │
│                                                                             │
│  ⓔ EVENT         (6 노드 — 행위/이벤트)                                     │
│  ──────────                                                                 │
│   vt_transfer      vt_call             vt_access        vt_msg             │
│   vt_movement      vt_impersonation                                        │
│                                                                             │
│  ⓛ LOCATION      (1 노드)                                                   │
│  ──────────                                                                 │
│   vt_loc                                                                   │
│                                                                             │
│  ─────────────────────────────────────────────────────────────              │
│  ⓗ HUB ⭐V4.0   (2 노드 — 자동 군집 허브)                                   │
│  ─────────────────────────────────────────────────────────────              │
│   pt_cluster                                                                │
│     └ Case 멤버 군집 (진정서 SimHash union-find)                            │
│   site_cluster                                                              │
│     └ Object 멤버 군집 (사이트 HTML SimHash union-find)                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 노드 카탈로그 25종

(범례: **P** = primary 데이터 소스, A = possible/aux, ❌ = never)

### 2.1 Source Layer

| # | 라벨 | 표준 식별자 | id_format | 핵심 속성 | CCOP | OSINT | Partner | Inference |
|---|---|---|---|---|---|---|---|---|
| 1 | `vt_src` | src_id | plain | reliability_tier, src_type, collector | P | **P** | A | – |

### 2.2 Case Layer

| # | 라벨 | 표준 식별자 | id_format | 핵심 속성 | CCOP | OSINT | Partner | Inference |
|---|---|---|---|---|---|---|---|---|
| 2 | `vt_case` | flnm | plain | incdnt_typ_cd, damage_amount | **P** | ❌ | A | – |
| 3 | `vt_petition` | petition_id | plain | rcpt_dt, crime_type_cd | **P** | A (더치트) | A | – |
| 4 | `pt_cluster` ⭐ | cluster_id | `ptc-YYYY-NNNN` | cluster_method, petition_cnt | **P** | ❌ | – | **P** |

### 2.3 Person Layer

| # | 라벨 | 표준 식별자 | id_format | 핵심 속성 | CCOP | OSINT | Partner | Inference |
|---|---|---|---|---|---|---|---|---|
| 5 | `vt_psn` | psn_id | plain | name, **is_anonymous** ⭐, risk_level | **P** | ❌ | A | A |
| 6 | `vt_org` | org_id | plain | org_name, org_category | **P** | A | A | – |

### 2.4 Object Layer

| # | 라벨 | 표준 식별자 | id_format | 핵심 속성 | CCOP | OSINT | Partner | Inference |
|---|---|---|---|---|---|---|---|---|
| 7 | `vt_bacnt` | account_no | **plain_dash / md5 / sha256** | bank_cd, is_burner | **P** | **P** | **P** | – |
| 8 | `vt_telno` | telno | **no_hyphen_e164 / md5** | telco_nm, is_burner, imei | **P** | **P** | **P** | – |
| 9 | `vt_ip` | ip_addr | ipv4_dotted / ipv6 | country, is_vpn, threat_score | **P** | **P** | A | – |
| 10 | `vt_site` | url_addr | normalized_url | is_malicious, site_type | A | **P** | A | – |
| 11 | `site_cluster` ⭐ | cluster_id | `sc-NNNN` / `osint-sc-NNNN` | html_fingerprint, site_cnt | ❌ | **P** | – | **P** |
| 12 | `vt_file` | hash_val | md5 / sha1 / sha256 | file_nm, is_malicious | A | **P** | A | – |
| 13 | `vt_id` | (platform, id_val) | plain | platform, **is_anonymous** ⭐ | A | **P** | ❌ | – |
| 14 | `vt_email` | email_addr | plain | domain, is_disposable | **P** | ❌ | A | – |
| 15 | `vt_crypto` | wallet_addr | plain | blockchain, risk_score | **P** | ❌ | A | – |
| 16 | `vt_vhcl` | vhclno | plain | vhcl_model | **P** | ❌ | A | – |
| 17 | `vt_dev` | device_id | plain | **dev_type** (smartphone\|pc\|tablet\|**relay_station**⭐\|router\|other), imei | **P** | ❌ | A | **P** |
| 18 | `vt_atm` | atm_id | plain | bank_nm, address | **P** | ❌ | A | – |

### 2.5 Event Layer

| # | 라벨 | 표준 식별자 | id_format | 핵심 속성 | CCOP | OSINT | Partner | Inference |
|---|---|---|---|---|---|---|---|---|
| 19 | `vt_transfer` | transfer_id | plain | amount, dlng_dt | **P** | A | **P** | – |
| 20 | `vt_call` | call_id | plain | call_dt, duration | **P** | ❌ | **P** | – |
| 21 | `vt_access` | access_id | plain | access_dt | **P** | ❌ | A | – |
| 22 | `vt_msg` | msg_id | plain | msg_type, content_text | A | **P** | ❌ | – |
| 23 | `vt_movement` | mvmt_id | plain | mvmt_dt, lat, lng | **P** | ❌ | A | – |
| 24 | `vt_impersonation` | imprsn_id | plain | imprsn_type_cd | **P** | A | ❌ | – |

### 2.6 Location Layer

| # | 라벨 | 표준 식별자 | id_format | 핵심 속성 | CCOP | OSINT | Partner | Inference |
|---|---|---|---|---|---|---|---|---|
| 25 | `vt_loc` | loc_id | plain | address, lat, lng | **P** | A | A | – |

---

## 3. 엣지 카탈로그 60종

> **2026-07-31 정합화**: 의미 카탈로그(`RELATIONSHIPS`)와 시각 카탈로그(`EDGE_STYLE_V40`)를 대조해
> 실사용되나 한쪽에만 등록됐던 엣지를 양쪽에 등재 → **60종으로 일치**. 과거 "53종"은 명목 수치였다
> (실제 의미 52 / 시각 55). 신규 등재: involves·communicated_with·contacted·impersonates·owns_wallet·
> performed_by·uses_device·verified_by·used_ip·owns·controls·located_at (owns_device는 uses_device 별칭).

### 3.1 V4.0 신규 엣지 (V3.7 → V4.0)

| 엣지 | 방향 | 의미 | 속성 | 주 도메인 |
|---|---|---|---|---|
| `belongs_to_cluster` ⭐ | vt_petition → pt_cluster | 진정서 군집 멤버십 | sim_score, rec_created | CCOP / Inference |
| `belongs_to_campaign` ⭐ | vt_site → site_cluster | 피싱 캠페인 멤버십 | sim_score, detected_at | OSINT / Inference |
| `used_in_device` ⭐ | vt_telno → vt_dev | 전화-디바이스 사용 (중계기 탐지) | first_seen, last_seen | CCOP / Inference |

### 3.2 기존 엣지 50종 (V3.7 그대로)

```
Case/Petition (10):
  suspect_in, victim_in, witness_in, involves, eg_used_account, eg_used_phone,
  eg_used_ip, filed_as, related_case, linked_to

Person 관계 (12):
  has_account, owns_phone, owns_vehicle, drives, used_ip, member_of, works_at,
  accomplice_of, sameAs, recruits, blackmails, contradicts

Person → Digital (5):
  uses_id, uses_email, owns_wallet, uses_device, owns

Identity / Site (3):
  registered_to, operates, hosts

Event Edges (10):
  from_account, to_account, transferred_to,
  caller, callee, contacted,
  sent_msg, received_msg, recorded_in, occurred_at

Access / Movement (3):
  accessed_from, accessed_to, performed_by

Object 관계 (5):
  belongs_to, resolves_to, contains_file, mentions_account, communicated_with

Source / Verification (2):
  sourced_from, verified_by

Impersonation V3.3 (3):
  used_for, targets, impersonates (read-only)

DEPRECATED (read-only, 신규 생성 금지):
  clusters_with → belongs_to_cluster via pt_cluster
```

---

## 4. 도메인 사용 매트릭스 (DOMAIN_USAGE)

```
              │ CCOP수사 │ OSINT   │ Partner │ Inference│
─────────────┼──────────┼─────────┼─────────┼──────────┤
 vt_src       │    P     │    P    │    A    │    -     │
 vt_case      │    P     │    -    │    A    │    -     │
 vt_petition  │    P     │    A    │    A    │    -     │
 pt_cluster ⭐│    P     │    -    │    -    │    P     │
 vt_psn       │    P     │    -    │    A    │    A     │
 vt_org       │    P     │    A    │    A    │    -     │
 vt_bacnt     │    P     │    P    │    P    │    -     │
 vt_telno     │    P     │    P    │    P    │    -     │
 vt_ip        │    P     │    P    │    A    │    -     │
 vt_site      │    A     │    P    │    A    │    -     │
 site_cluster⭐│   -     │    P    │    -    │    P     │
 vt_file      │    A     │    P    │    A    │    -     │
 vt_id        │    A     │    P    │    -    │    -     │
 vt_email     │    P     │    -    │    A    │    -     │
 vt_crypto    │    P     │    -    │    A    │    -     │
 vt_vhcl      │    P     │    -    │    A    │    -     │
 vt_dev       │    P     │    -    │    A    │    P     │
 vt_atm       │    P     │    -    │    A    │    -     │
 vt_loc       │    P     │    A    │    A    │    -     │
 vt_msg       │    A     │    P    │    -    │    -     │
 vt_transfer  │    P     │    A    │    P    │    -     │
 vt_call      │    P     │    -    │    P    │    -     │
 vt_access    │    P     │    -    │    A    │    -     │
 vt_movement  │    P     │    -    │    A    │    -     │
 vt_impersn   │    P     │    A    │    -    │    -     │
─────────────┴──────────┴─────────┴─────────┴──────────┘
```

**도메인 분리의 핵심**:
- **CCOP 전속** (11종): vt_case, pt_cluster, vt_psn, vt_email, vt_crypto, vt_vhcl, vt_dev, vt_atm, vt_call, vt_access, vt_movement
- **OSINT 전속** (1종): site_cluster ⭐
- **양쪽 공통** (9종): vt_src, vt_bacnt, vt_telno, vt_ip, vt_site, vt_file, vt_id, vt_msg, vt_transfer ← **sameAs 자동 매칭 핵심 영역**

---

## 5. 노드 표준 메타 (V4.0 의무화)

```cypher
(:any_label {
    // ── 필수 메타 (V4.0 의무) ──────────────────
    <canonical_id>:    '...',           // 노드별 표준 식별자
    id_format:         '...',           // NODE_ID_STANDARD 참조
    source_domain:     '...',           // investigation | osint | partner | inference
    source_id:         '<vt_src 참조>',
    reliability_tier:  1-4,             // 1=공식, 4=OSINT
    rec_created:       '<ISO8601>',
    
    // ── 도메인별 속성 ─────────────────────────
    ...
})
```

---

## 6. 식별자 형식 표준 (NODE_ID_STANDARD)

| 노드 | canonical_field | 가능 formats | 기본 | 정규화 |
|---|---|---|---|---|
| vt_bacnt | account_no | plain_dash, md5, sha256 | plain_dash | strip + lowercase |
| vt_telno | telno | no_hyphen_e164, md5 | no_hyphen_e164 | – |
| vt_site | url_addr | normalized_url | normalized_url | https://, no www, no trailing / |
| vt_id | (platform, id_val) | plain | plain | – |
| vt_ip | ip_addr | ipv4_dotted, ipv6 | ipv4_dotted | – |
| vt_file | hash_val | md5, sha1, sha256 | sha256 | – |
| vt_psn | psn_id | plain | plain | – |
| pt_cluster | cluster_id | plain | plain | `ptc-YYYY-NNNN` |
| site_cluster | cluster_id | plain | plain | `sc-NNNN` or `osint-sc-NNNN` |

**Cross-source sameAs 추론 흐름**:
```
[CCOP vt_bacnt]                [OSINT vt_bacnt]
account_no='110-1111-2222'    account_no='abc123...md5'
id_format='plain_dash'         id_format='md5'
        │                              │
        ▼ (canonical 정규화)            ▼
   '11011112222'  ─── md5() ──→   'abc123...'  ← 비교 → 매칭!
                                        │
                                        ▼
                             sameAs 엣지 자동 생성
                             (confidence: 0.95)
```

---

## 7. 추론 규칙 카탈로그 (INFERENCE_RULES_V37)

| 규칙 | 입력 | 알고리즘 | 출력 | 도메인 | 주기 |
|---|---|---|---|---|---|
| **SiteClusterDetection** | vt_site (html_src) | SimHash64 + UnionFind (Hamming ≤ 3) | site_cluster + belongs_to_campaign | OSINT, Inference | daily |
| **PtClusterDetection** | vt_petition (TB_PETTN_CLSTR) | UnionFind (sim ≥ 0.7) | pt_cluster + belongs_to_cluster | CCOP, Inference | daily |
| **RelayStationDetection** | vt_telno (imei) | group_by imei, count ≥ 3 | vt_dev(relay_station) + used_in_device | CCOP, Inference | daily |
| **AnonymousFlagDetection** | vt_psn, vt_id | WHERE name NULL/empty | is_anonymous=true | CCOP, OSINT | on-load |
| **SameAsResolution** | 양쪽 도메인의 동일 canonical_id | id_format별 정규화 + 해싱 | sameAs 엣지 | Inference | weekly |
| 외 5종 (향후 정의) | – | – | – | – | – |

---

## 8. Cross-Domain 통합 패턴

### 8.1 분리 그래프 + 브릿지 추론
```
CCOP 수사 그래프                          OSINT 공개정보 그래프
(tccop_graph_v6)                         (osint_ontology)
   │                                          │
   ├ vt_psn ─ has_account ─ vt_bacnt          │
   │                          │               │
   │                       ┌──┴───────────────┴──┐
   │                       │ Cross-graph sameAs  │
   │                       │ (id_format 기반)    │
   │                       └─────────┬───────────┘
   │                                 │
   │                          vt_bacnt ─ sourced_from ─ vt_msg (피싱 SMS)
   │                                                       │
   │                                              sent_msg │
   │                                                       │
   │                                                    vt_id (닉네임)
```

### 8.2 V4.0 권장 통합 모델: **Modular Asymmetric Merge with LLM-aided Bridge**
- **Modular**: 도메인별 그래프 자율 (성능/권한 격리)
- **Asymmetric**: V4.0 SSOT가 superset, OSINT는 사용 매트릭스로 부분 사용
- **LLM-aided Bridge**: Qwen v38 학습 모델이 자연어 ↔ 카탈로그 매핑을 학습 → cross-source 식별자 매칭에 재활용

---

## 9. Provenance / 신뢰도 계층

| Tier | 출처 | 적용 도메인 | 예시 |
|---|---|---|---|
| **1** | 공식 진정서·수사 시스템 | investigation | vt_petition, vt_case |
| **2** | 검찰·금융기관 공식 데이터 | investigation, partner | 협력 은행 계좌 데이터 |
| **3** | 협력기관 공유 | partner | 통신사 통화 메타 |
| **4** | OSINT 크롤링·민간 신고 | osint | 더치트, 크롤링 사이트 |

**원칙**:
- 노드는 자신을 생성한 vt_src의 `reliability_tier` 상속
- 동일 식별자가 여러 tier로 등장 시 **가장 높은 tier** 우선 사용
- sameAs 엣지는 두 tier 간 차이를 속성으로 표시 (`from_tier`, `to_tier`)

---

## 10. Deprecated 정책

| Deprecated 엣지 | 폐기 시점 | 대체 | 접근 |
|---|---|---|---|
| `clusters_with` | V4.0 | `belongs_to_cluster` via pt_cluster | **read-only** (신규 생성 금지) |

**거버넌스**:
- 카탈로그에서 삭제하지 않고 SSOT에 `deprecated: True` 메타 유지
- ETL/매퍼에서 신규 MERGE/CREATE 차단
- 기존 데이터 읽기는 허용

---

## 11. 거버넌스 (V4.0 RFC 절차)

```
┌─────────────────────────────────────────────────────────┐
│  SSOT 변경 요청 (노드/엣지/속성 추가, 변경, 폐기)         │
│                        │                                │
│                        ▼                                │
│  [RFC 작성] — 변경 사항, 영향, 대안, 마이그레이션 명시   │
│                        │                                │
│                        ▼                                │
│  [온톨로지 위원회 검토] — V4.0 표준 위배 여부            │
│                        │                                │
│              ┌─────────┴────────┐                       │
│              ▼                  ▼                       │
│        승인 → SSOT 갱신    반려 → 추가 검토              │
│              │                                          │
│              ▼                                          │
│  [도구/ETL 갱신] — ontology_service.py 우선 갱신         │
│                  → 모든 도메인 ETL 어댑터 검증           │
│                  → 벤치마크/추론 룰 영향 평가            │
│                        │                                │
│                        ▼                                │
│  [전 시스템 배포]                                       │
└─────────────────────────────────────────────────────────┘
```

**변경 권한**:
- L4 SSOT(ontology_service.py) — 온톨로지 위원회만
- L5 도메인 ETL — 데이터 엔지니어 (SSOT 참조 유지 필수)
- L6 그래프 인스턴스 — DBA

---

## 12. 핵심 운영 가치

### 12.1 단일 코드 진입점 (SSOT)
```python
from app.middleware.services.ontology_service import KICSCrimeDomainOntology as Onto

# 모든 도메인/추론 룰/식별자 정보를 SSOT에서 조회
Onto.is_applicable('site_cluster', 'osint')        # True
Onto.get_id_format('vt_bacnt')['default_format']   # 'plain_dash'
Onto.INFERENCE_RULES_V37['SiteClusterDetection']   # 알고리즘 명세
Onto.DOMAIN_USAGE['vt_psn']                        # 도메인 사용 dict
```

### 12.2 자동화 가능 작업
| 자동화 | 입력 메타 | 출력 |
|---|---|---|
| Cross-source sameAs 추론 | id_format, canonical_id | sameAs 엣지 |
| 도메인 적합성 검증 | DOMAIN_USAGE | ETL 어댑터 검증 |
| 추론 룰 적용 | INFERENCE_RULES_V37 | site_cluster, pt_cluster 등 |
| Text2Cypher 검증 | NODE_CATALOG + DOMAIN_USAGE | LLM 응답 schema 검증 |
| STIX 2.1 export | 사용 매트릭스 | 국제 표준 매핑 |

### 12.3 도메인 확장 시 부담
새 데이터 소스(예: 통신사 API) 추가 시:
- SSOT 변경 ❌ 불필요
- DOMAIN_USAGE에 행 추가만 ✅
- 도메인 ETL 어댑터 작성 ✅
- 추론 룰은 SSOT 그대로 활용 ✅

---

## 13. V4.0 vs V3.7 vs OSINT V3.6 비교

| 항목 | V3.7 | OSINT V3.6 | **V4.0 (통합)** |
|---|---|---|---|
| 카탈로그 노드 | 25 | 9 (사용) | **25 SSOT + 사용 매트릭스** |
| 카탈로그 엣지 | 60 | 5 (사용) | **60 SSOT + 사용 매트릭스** (2026-07-31 정합화, 구 53 명목치) |
| 레이어 | POLE 6 | POLE 6 | **POLE 6 + Hub 7** ⭐ |
| 식별자 형식 메타 | – | – | **NODE_ID_STANDARD** ⭐ |
| 도메인 사용 명시 | 암묵적 | 보고서 §10.2/3 | **DOMAIN_USAGE 코드 메타** ⭐ |
| 추론 룰 | – | – | **INFERENCE_RULES_V37** ⭐ |
| Provenance | reliability_tier | 부분 | **모든 노드 의무화** ⭐ |
| Deprecated | – | – | **read-only 정책** ⭐ |
| Cross-domain 연결 | 수동 | 수동 | **자동화 가능 인프라** ⭐ |
| SSOT 코드 | ontology_service.py (부분) | – | **ontology_service.py 강화** ⭐ |

---

## 14. V4.0 산출물

| # | 산출물 | 위치 | 상태 |
|---|---|---|---|
| 1 | SSOT 코드 (NODE_ID_STANDARD, DOMAIN_USAGE, INFERENCE_RULES_V37, 헬퍼) | `app/middleware/services/ontology_service.py` | ✅ |
| 2 | OSINT × V4.0 후처리 모듈 (SimHash 군집화) | `app/services/osint_v37_postprocess.py` | ✅ |
| 3 | OSINT × V4.0 통합 가이드 | `docs/OSINT_V37_INTEGRATION_GUIDE.md` | ✅ |
| 4 | Text2Cypher 학습/평가 (Qwen v37/v38) | `docs/TEXT2CYPHER_V37_EVAL_REPORT.md` | ✅ |
| 5 | **V4.0 정식 명세 (본 문서)** | `docs/CCOP_ONTOLOGY_V4.0.md` | ✅ |

---

## 15. 변경 이력

| 일자 | 버전 | 주요 변경 | 작성자 |
|---|---|---|---|
| (과거) | V3.0~V3.3 | POLE 6 레이어, V3.3 사칭 패턴 (vt_impersonation) | CCOP 팀 |
| (과거) | V3.5 | 23 노드 / 52 엣지 카탈로그 표준 | CCOP 팀 |
| (과거) | V3.6 | OSINT ETL 보고서 (9 노드 / 5 엣지 사용 결정) | CCOP 팀 |
| 2026-03 (추정) | V3.7 | pt_cluster, site_cluster, is_anonymous, relay_station 신설 (25/53) | CCOP 팀 |
| **2026-05-21** | **V4.0** | **OSINT × V3.7 통합 표준화 + Hub 레이어 신설 + SSOT 메타 격상** | **CCOP 팀** |
| **2026-07-31** | **V4.0 정합화** | **엣지 카탈로그 이원화 해소(의미↔시각 60 일치, 구 53 명목치 정정) + id 표준을 실 MERGE 키로 정정 + 회귀 테스트** | **CCOP 팀** |
| 2026-08-03 | V4.3~V4.4 | 시나리오 직접 엣지 3종(knows·linked_id·mentions_id) + reification 확장(access_via 등, 60→66) | CCOP 팀 |
| 2026-08-06 | V4.5 | 2차년도 실적재 검증 대조 — 신규 5종·확장 5종(66→71) + edge_id·파생속성 등록부 | CCOP 팀 |
| 2026-08-13 | V4.6~V4.7 | bitemporal 정착(used_ip 등 valid_from/to·ip_role·R8 access_type) → represents·occp_nm·std_columns 표준 DDL 정합(71→72) | CCOP 팀 |
| **2026-09-02** | **V4.8** | **EP1~8 실적재 전수감사 기반 도메인 확장 3종(contacted·registered_to+DigitalID, used_ip+BankAccount, channel 속성) + sameAs→same_as 개명(AgensGraph 소문자화 정합). 엣지 72 불변 — 감사 위반 0** | **CCOP 팀** |

> **⚠ 현행 버전 안내**: 본 문서는 V4.1 시점의 전체 설계 명세이며, **현행 SSOT는 V4.8**
> (코드 `ontology_service.py` docstring 버전 이력 + 엑셀 `CCOP_Ontology_V4.8_노드 엣지 속성 정보.xlsx`가 최신 정본).
> V4.2 이후 변경은 위 표·코드 docstring·`docs/EP1_EP8_V47_AUDIT_20260902.md` 참조.

---

## 16. 핵심 결론

> **V4.0은 새로운 노드/엣지를 추가하지 않는다.** V3.7 카탈로그(25노드 / 엣지 60 — 정합화 실측, 구 "53"은 명목치)는 그대로 유지하면서, **OSINT V3.6의 도메인 결정과 신뢰도 분류를 SSOT 메타로 정식 격상**하고, **POLE에 Hub 레이어를 신설**하여 군집 노드의 의미론적 위치를 명확히 한다. **단일 카탈로그 + 다중 사용 매트릭스 + 자동화 가능 메타** 3원칙이 V4.0의 본질이다.

---

## 17. V4.0 변경 이력 — 2026-05-21 패치 적용

> 본 절은 2026-05-21 작업으로 적용된 모든 변경 사항을 SSOT 와 동기화하기 위한 정식 변경 이력. 별도 보조 문서(`docs/V40_ONTOLOGY_AUDIT_20260521.md` 등) 의 결정 사항을 본 문서로 통합.

### 17.1 🔴 P0 — 도메인 키 명명 통일 (canonical 매핑 레이어)

**문제**: 4개 SSOT 가 동일 개념을 서로 다른 키로 사용 — RDB `KICS` 입력이 그래프 변환 시 `reliability_tier=3` 으로 강등되는 결함 실증.

**조치**: `RdbToGraphService.make_node_props_v40` / `make_edge_props_v40` 진입 시 RDB 키(`KICS/OSINT/DIGITAL/EXT`)를 코드 키(`investigation/osint/partner/inference`)로 정규화하는 매핑 레이어 도입.

| RDB SOURCE_DOMAIN | canonical (코드) | reliability_tier (자동) |
|-------------------|-----------------|-------------------------|
| `KICS` | `investigation` | **1** (공식) |
| `OSINT` | `osint` | **4** (웹수집) |
| `DIGITAL` | `partner` | **2** (수사) |
| `EXT` | `partner` | **2** (수사) |

**구현**: [app/services/rdb_to_graph_service.py:1775](../app/services/rdb_to_graph_service.py#L1775)

### 17.2 🟡 P1 — `AnonymousFlagDetection` 추론룰 스키마 정합

다른 3개 추론룰과 키 구조 불일치 — `input_attributes`, `output_nodes`, `output_edges`, `frequency` 4키 누락. 9-키 표준 스키마로 통일 (익명 플래그는 속성만 갱신이므로 `output_nodes=[]`, `output_edges=[]`).

**구현**: [app/middleware/services/ontology_service.py:171](../app/middleware/services/ontology_service.py#L171)

### 17.3 🟡 P2 — `NODE_ID_STANDARD` 25노드 전수 정의

**이전**: 9 노드만 정의. **현행**: 25 노드 전수 (V4.0 사양 "전 노드 id_format 의무" 100% 충족). 신규 16노드 default_format: `vt_email→normalized`, `vt_crypto→base58check`, `vt_transfer/vt_call/vt_access/vt_msg/vt_movement/vt_impersonation→uuid`, 나머지 9노드 `plain`.

**구현**: [app/middleware/services/ontology_service.py:98](../app/middleware/services/ontology_service.py#L98)

### 17.4 ETL V4.0 메타 주입 (노드 + 엣지)

**노드 메타 6컬럼**: `id_format`, `source_domain`, `reliability_tier`, `source_id`, `collected_at`, `rec_created`
**엣지 메타 4컬럼**: `source_domain`, `source_id`, `collected_at`, `rec_created` (엣지 `id_format`/`reliability_tier` 없음)

**패치 지점**:
- [etl_service.py:357](../app/services/etl_service.py#L357) — 메인 ETL 노드
- [etl_service.py:734](../app/services/etl_service.py#L734) — 확장 ETL 노드
- [etl_service.py:447](../app/services/etl_service.py#L447) — 메인 ETL 엣지
- [etl_service.py:828](../app/services/etl_service.py#L828) — 확장 ETL 엣지 + fallback
- [rdb_to_graph_service.py:1819](../app/services/rdb_to_graph_service.py#L1819) — `make_edge_props_v40` 신설

**회귀**: [tests/test_etl_v40_meta.py](../tests/test_etl_v40_meta.py) 14/14 PASS.

### 17.5 L5 시각화 SSOT API + 프론트 동적 오버레이

| Endpoint | 내용 | 카운트 |
|----------|------|--------|
| `GET /api/v1/visual-style` | 노드 시각화 | 25 |
| `GET /api/v1/edge-style` | 엣지 시각화 | 55 |
| `GET /api/v1/layout-presets` | 레이아웃 프리셋 | 5 |
| `GET /api/v1/workflows` | 수사 워크플로우 | 6 |
| `GET /api/v1/ontology/meta` | NODE_ID + DOMAIN + INFERENCE 통합 | - |

**구현**: [app/routes_api.py:1437](../app/routes_api.py#L1437)

**프론트 (`index.html`)**:
- `loadV40Styles()` — Cytoscape 스타일을 SSOT 로 동적 오버레이 (범례 헤더 `V4.0 SSOT ✓` 뱃지)
- `loadV40Toolbar()` — 우측 상단 V4.0 툴바에 레이아웃 프리셋 5종 + 워크플로우 6종 렌더
- `applyV40LayoutPreset(name)` / `runV40Workflow(name)` 인터랙션
- API 실패 시 기존 정적 스타일로 graceful degradation (비파괴)

### 17.6 CSV 업로드 폼 SOURCE_DOMAIN 옵션

CSV 업로드 폼 Step 2.3 에 SOURCE_DOMAIN 라디오 4종 + SOURCE_ID 옵션 입력 추가. 백엔드 [routes.py:1163](../app/routes.py#L1163) 검증 후 RDBService 로 전달 (실제 RDB INSERT 는 DA팀 V3.7 DDL 운영 적용 — Phase 1.7 이후 활성화).

### 17.7 검증 산출물

| 문서 | 내용 |
|------|------|
| [V40_ONTOLOGY_AUDIT_20260521.md](V40_ONTOLOGY_AUDIT_20260521.md) | 5영역 정합성 감사 + P0~P2 식별 |
| [STAGING_PATCH_VERIFICATION_20260521.md](STAGING_PATCH_VERIFICATION_20260521.md) | DA팀 패치 SQL 격리 dry-run 8/8 |
| [ETL_V40_GAP_REPORT_20260521.md](ETL_V40_GAP_REPORT_20260521.md) | ETL V4.0 메타 갭 분석 |
| [DA_TEAM_V40_REQUEST_20260521.md](DA_TEAM_V40_REQUEST_20260521.md) | DA팀 호환화 요청서 |
| [scripts/da_v37_v40_patch.sql](../scripts/da_v37_v40_patch.sql) | DA팀 즉시 적용 패치 SQL |

---

**문서 끝 (V4.0 패치 적용 — 2026-05-21)**
