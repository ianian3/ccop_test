# CCOP 노드·엣지 아키텍처 레퍼런스

> **기반 문서:** ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md (2026-04-21)
> **용도:** 노드·엣지 정의만 빠르게 참조하는 단일 파일
> **노드:** 23개 | **엣지:** 52개 (unique 타입) | **레이어:** 6계층 | **추론 규칙:** 9개
> **최종 검증:** 2026-04-21 (v3.5 코드 교차검증 완전 반영)

---

## 1. 6계층 구조

```
┌──────────────────────────────────────────────────────────────┐
│ SOURCE   — vt_src                                            │
├──────────────────────────────────────────────────────────────┤
│ CASE     — vt_case  vt_petition                              │
├──────────────────────────────────────────────────────────────┤
│ PERSON   — vt_psn  vt_org                                    │
├──────────────────────────────────────────────────────────────┤
│ OBJECT   — vt_bacnt  vt_telno  vt_ip   vt_site  vt_file     │
│            vt_id    vt_vhcl   vt_email vt_crypto vt_dev      │
│            vt_atm                                            │
├──────────────────────────────────────────────────────────────┤
│ LOCATION — vt_loc                                            │
├──────────────────────────────────────────────────────────────┤
│ EVENT    — vt_transfer  vt_call   vt_msg  vt_access          │
│            vt_movement  vt_impersonation                     │
└──────────────────────────────────────────────────────────────┘
```

**레이어 간 허용 엣지 매트릭스**

```
From ↓  To →  │ SRC  CASE  PSN   OBJ   LOC   EVT
──────────────┼──────────────────────────────────
Source        │  -    -     -     -     -     -
Case          │  ✓    ✓     ✓     ✓     -     -
Person        │  -    ✓     ✓     ✓     ✓     ✓
Object        │  -    -    [1]    ✓     ✓     ✓
Location      │  -    -     -     -     -     ✓
Event         │  -    -    [2]    ✓     ✓     -

[1] Object → Person: registered_to 단 1개 허용 (Phone → Person, 명의자 참조)
    원칙상 Object→Person은 금지이나 수사 실무상 예외 허용
[2] Event → Person: targets 단 1개 허용 (vt_impersonation → vt_org)
    ※ vt_org는 Person 레이어이므로 해당
```

---

## 2. 노드 카탈로그 (23개)

### SOURCE (1개)

| 노드 | 한국어 | 식별자 | 핵심 속성 |
|------|--------|--------|----------|
| `vt_src` | 데이터 소스 | `src_id` | src_type, reliability_tier(1~5), collector, collected_at |

**reliability_tier**: 1=공식수사자료 / 2=기관연계 / 3=전처리진정서 / 4=OSINT / 5=미확인제보
**src_type**: OFFICIAL \| AGENCY \| PREPROCESSOR \| PETITION \| OSINT \| REPORT

---

### CASE (2개)

| 노드 | 한국어 | 식별자 | 핵심 속성 |
|------|--------|--------|----------|
| `vt_case` | 수사 사건 | `flnm` | incdnt_no, incdnt_typ_cd, occrn_dt, damage_amount, status, risk_level, risk_score |
| `vt_petition` | 진정서/신고 | `petition_id` | rcpt_dt, rcpt_channel, crime_type_cd, status, linked_case_id, raw_id |

**status (vt_case)**: OPEN \| INVESTIGATING \| CLOSED \| SUSPENDED
**status (vt_petition)**: PENDING \| LINKED \| REJECTED \| CLOSED

---

### PERSON (2개)

| 노드 | 한국어 | 식별자 | 핵심 속성 |
|------|--------|--------|----------|
| `vt_psn` | 인물 | `psn_id` | name, korn_flnm, dob, gender, rrno_hash(SHA-256), risk_level, aliases |
| `vt_org` | 조직/기관 | `org_id` | org_name, org_category, inst_se_cd, hierarchy_level, member_count |

> ⚠️ `vt_psn.role` 속성 없음 — 역할은 `suspect_in` / `victim_in` / `witness_in` 엣지로 표현
> **org_category**: criminal \| institution \| company \| government

---

### OBJECT (11개)

| 노드 | 한국어 | 식별자 | 핵심 속성 |
|------|--------|--------|----------|
| `vt_bacnt` | 금융계좌 | `account_no` + `bank_cd` (복합) | bank_nm, dpstr_nm, is_burner, is_frozen, total_received, inst_id |
| `vt_telno` | 전화번호 | `telno` | telco_nm, join_typ_cd, imsi, is_burner, spam_cnt, subs_holder |
| `vt_ip` | IP주소 | `ip_addr` | isp, asn, country, is_vpn, is_tor, is_proxy, is_hosting, abuse_score |
| `vt_site` | 웹사이트 | `url_addr` | dmn_addr, site_type, is_malicious, risk_grd, page_hash, registrar |
| `vt_file` | 파일/증거 | `hash_val` (SHA-256) | file_nm, file_extsn_nm, file_sz, is_malicious, vt_score |
| `vt_id` | 디지털 식별자 | `id_val` | platform, id_type, profile_url, is_active, real_name |
| `vt_vhcl` | 차량 | `vhclno` | carmdl_nm, color, ownr_nm, stolen_yn, rgst_dt |
| `vt_email` | 이메일 | `email_addr` | domain, provider, is_disposable |
| `vt_crypto` | 가상자산 지갑 | `wallet_addr` | blockchain, exchange, balance, risk_score, kyc_verified, tx_cnt |
| `vt_dev` | 기기 | `device_id` | dev_type, imei, mac_addr, model, os, os_version |
| `vt_atm` | ATM | `atm_id` | bank_nm, bank_cd, loc_id(→vt_loc FK), address, is_outdoor |

**join_typ_cd (vt_telno)**: INDIVIDUAL \| CORPORATE \| PREPAID
**dev_type (vt_dev)**: smartphone \| pc \| tablet \| iot \| pos

---

### LOCATION (1개)

| 노드 | 한국어 | 식별자 | 핵심 속성 |
|------|--------|--------|----------|
| `vt_loc` | 위치 | `loc_id` | loc_type, address, lat, lng, sido_nm, sigungu_nm, bsst_nm(기지국), cctv_id |

**loc_type**: address \| cell_tower \| cctv \| atm_loc \| transit \| poi

---

### EVENT (6개)

| 노드 | 한국어 | 식별자 | 핵심 속성 | RDB Bridge Key |
|------|--------|--------|----------|---------------|
| `vt_transfer` | 금융 이체 | `transfer_id` | dlng_amt, dlng_dt, dlng_se_cd, hop_level, is_suspicious | dlng_sn → TB_FIN_BACNT_DLNG |
| `vt_call` | 통화 | `call_id` | call_strt_dt, call_dur_sec, dsptch_telno, rcptn_telno, bsst_loc_id | call_sn → TB_TELNO_CALL_DTL |
| `vt_msg` | 메시지 | `msg_id` | msg_type, app_nm, dsptch_dt, content_hash, sentiment_cd, spam_yn | msg_sn → TB_TELNO_SMS_MSG |
| `vt_access` | 네트워크 접속 | `access_id` | access_dt, action, user_agent, status_code, bytes_sent, bytes_recv | lgn_sn → TB_SYS_LGN_EVT |
| `vt_movement` | 이동 이벤트 | `mov_id` | mov_type, timestamp, loc_id | rcgn_sn / loc_evt_sn / mv_sn |
| `vt_impersonation` | 사칭 이벤트 | `event_id` | method, fake_name, script_type, start_dt, end_dt | — |

**mov_type**: lpr(번호판인식) \| cell_tower(기지국) \| transit_card(교통카드)
**dlng_se_cd**: DEPOSIT \| WITHDRAW \| TRANSFER \| ATM
**sentiment_cd (vt_msg)**: THREAT \| LURE \| NORMAL \| UNKNOWN

---

## 3. 엣지 카탈로그 (52개)

### 3.1 Case 관련 (7개)

| 엣지 | 방향 | 의미 | 핵심 속성 |
|------|------|------|----------|
| `suspect_in` | Person → Case | 피의자로 관련 | confidence, verified, valid_from |
| `victim_in` | Person → Case | 피해자로 관련 | damage_amount, valid_from |
| `witness_in` | Person → Case | 참고인으로 관련 | statement_date |
| `filed_as` | Petition → Case | 진정서 → 사건 전환 | converted_dt, converted_by |
| `related_case` | Case → Case | 사건 유사성 (공유 증거 기반) | confidence(0.75), inference=True |
| `linked_to` | Petition → Case \| Object → Object | 진정서-사건 연결 / 범용 임시 연결 | link_reason \| link_type, confidence |
| `clusters_with` | Petition → Petition | 유사 진정서 군집 | sim_score, cluster_id |

> `similar_to` 명칭 없음 — 코드에서 `related_case`로 구현됨

---

### 3.2 Case → Object 증거 연결 (3개)

| 엣지 | 방향 | 의미 | 핵심 속성 |
|------|------|------|----------|
| `eg_used_account` | Case → BankAccount | 사건에 사용된 계좌 증거 | source_id, rec_created |
| `eg_used_phone` | Case → Phone | 사건에 사용된 전화번호 증거 | source_id, rec_created |
| `eg_used_ip` | Case → IP | 사건에 사용된 IP 증거 | source_id, rec_created |

> `eg_used_*` 엣지는 RELATIONSHIPS dict 미등재 — [graph_service.py:69-71](app/services/graph_service.py#L69)에만 존재. 향후 RELATIONSHIPS 등재 필요

---

### 3.3 Person 소유/귀속 (15개)

| 엣지 | 방향 | 의미 | 핵심 속성 |
|------|------|------|----------|
| `has_account` | Person → BankAccount | 계좌 소유 | valid_from, valid_to, verified |
| `controls` | Person → BankAccount | 실질 지배 (명의 무관) | control_type, confidence, transitive |
| `owns_phone` | Person → Phone | 전화번호 소유 | valid_from, valid_to |
| `owns_device` | Person → Device | 기기 소유 | valid_from, valid_to |
| `drives` | Person → Vehicle | 차량 **운행** (일시 사용 포함) | valid_from, valid_to |
| `owns_vehicle` | Person → Vehicle | 차량 **법적 소유** (등록 명의) | valid_from, valid_to |
| `uses_id` | Person → DigitalID | 플랫폼 ID 사용 | platform, valid_from |
| `uses_email` | Person → Email | 이메일 사용 | valid_from, valid_to |
| `used_ip` | Person → IP | IP 사용 이력 | last_seen, usage_count |
| `member_of` | Person → Org | 조직 소속 | role, valid_from, valid_to |
| `works_at` | Person → Org | 합법 기관 재직 | position, valid_from |
| `accomplice_of` | Person → Person | 공범 관계 (추론) | confidence, inference_basis |
| `sameAs` | Person → Person | 동일 인물 (엔티티 해소) | match_score, match_basis, review_status |
| `contradicts` | Person → Person | 모순 정보 / 명의도용 | conflict_field, conflict_detail |
| `owns` | Person → Any | 범용 소유 (구체적 엣지 우선) | — |

> `drives` vs `owns_vehicle`: 운행 이력(LPR·CDR 유추)은 `drives`, 차량등록원부 기반 소유는 `owns_vehicle`

---

### 3.4 Person 관련 — v3.4 신규 (3개)

| 엣지 ★ | 방향 | 의미 | 핵심 속성 |
|--------|------|------|----------|
| `operates` | Person/Org → Site/DigitalID | 플랫폼·채널 운영자 식별 | valid_from, valid_to, role |
| `recruits` | Person → Person | 조직 모집 계층 추적 | recruit_type, date, payment |
| `blackmails` | Person → Person | 협박 행위 (몸캠피싱·랜섬웨어) | method, date |

---

### 3.5 Object → Person (1개) — 예외 허용

| 엣지 | 방향 | 의미 | 비고 |
|------|------|------|------|
| `registered_to` | Phone → Person | 전화번호 등록 명의자 참조 | 레이어 매트릭스 예외 — 수사 실무 필요성으로 허용 |

> ⚠️ 원칙상 Object→Person은 금지. 이 엣지는 명의자 역추적 단 한 건만 예외 허용.
> 새로운 Object→Person 엣지는 설계위원회 승인 필요.

---

### 3.6 Object 관련 (9개)

| 엣지 | 방향 | 의미 | 핵심 속성 | 비고 |
|------|------|------|----------|------|
| `transferred_to` | Account → Account | 계좌 간 추론 연결 | hop_level | 추론 전용, ETL 직접 생성 금지 |
| `resolves_to` | Site → IP | DNS 해석 결과 | resolved_dt | — |
| `belongs_to` | Account → Org | 계좌 소속 금융기관 | — | — |
| `hosts` ★ | IP → Site | 서버 IP가 사이트를 호스팅 | port, detected_at | v3.4 신규 |
| `contains_file` ★ | Site/Msg/ID → File | 파일 내장·배포 경로 | file_role, detected_at | v3.4 신규 |
| `located_at` ★ | ATM/Device/Org → Location | 객체 고정 위치 귀속 | verified | v3.4 신규 |
| `communicated_with` | IP → IP | IP 간 직접 통신 | — | 네트워크 분석용 |
| `mentions_account` | Message → BankAccount | 메시지 내 계좌번호 언급 | confidence(0.85) | 보이스피싱 핵심 증거, 추론 엣지 |
| `linked_to` | Object → Object | 범용 임시 연결 | link_type, confidence | Case 섹션과 동일 엣지 타입 |

**deprecated (DB 호환용, 신규 생성 금지)**:

| 엣지 | 방향 | 대체 | 비고 |
|------|------|------|------|
| `hosted_at` | Site → IP | `hosts` (방향 역전) | graph_service에 호환성 유지 중 |
| `contacted` | Phone → Phone | `caller`/`callee` | 집계 엣지, 신규 생성 금지 |

---

### 3.7 Event 관련 (10개)

| 엣지 | 방향 | 의미 | 연결 패턴 |
|------|------|------|----------|
| `from_account` | Account → Transfer | 이체 출금 계좌 | `(vt_bacnt)-[from_account]->(vt_transfer)` |
| `to_account` | Transfer → Account | 이체 입금 계좌 | `(vt_transfer)-[to_account]->(vt_bacnt)` |
| `caller` | Phone → Call | 발신 번호 | `(vt_telno)-[caller]->(vt_call)` |
| `callee` | Call → Phone | 수신 번호 | `(vt_call)-[callee]->(vt_telno)` |
| `accessed_from` | Access → IP | 접속 출발 IP | `(vt_access)-[accessed_from]->(vt_ip)` |
| `accessed_to` | Access → Site | 접속 목적지 사이트 | `(vt_access)-[accessed_to]->(vt_site)` |
| `sent_msg` | Phone/ID → Message | 메시지 발신 | `(vt_telno)-[sent_msg]->(vt_msg)` |
| `received_msg` | Message → Phone | 메시지 수신 | `(vt_msg)-[received_msg]->(vt_telno)` |
| `occurred_at` | Event → Location | 이벤트 발생 위치 | `(vt_transfer/call/movement)-[occurred_at]->(vt_loc)` |
| `recorded_in` | Vehicle/Phone → Movement | 이동 기록 주체 | `(vt_vhcl/vt_telno)-[recorded_in]->(vt_movement)` |

> **`accessed_from` + `accessed_to` 함께 사용**: vt_access 노드가 두 엣지로 출발 IP와 목적지 사이트를 동시에 참조
> 이전 아키텍처 문서에서 "accessed_to 제거됨"으로 잘못 기재됨 — 코드에 존재하며 설계상 필수

**deprecated (DB 호환용, 신규 생성 금지)**:

| 엣지 | 방향 | 대체 |
|------|------|------|
| `performed_by` | Transfer → Person | v3.4 제거 (수사관 역할은 verified_by로) |
| `sent_via` | Phone → Message | `sent_msg` |
| `received_by` | Message → Phone | `received_msg` |

---

### 3.8 사칭 범죄 엣지 (2개)

| 엣지 | 방향 | 의미 |
|------|------|------|
| `used_for` | Object → vt_impersonation | 연락처/계정/사이트가 사칭 수단으로 활용됨 |
| `targets` | vt_impersonation → vt_org | 사칭 행위의 타겟 기관 |

```
전체 패턴: (vt_telno|vt_id|vt_site|vt_email)
              -[used_for]->(vt_impersonation)-[targets]->(vt_org)
```

> `impersonates` 엣지는 v3.3 deprecated, v3.4 완전 제거

---

### 3.9 Meta / Provenance (2개)

| 엣지 | 방향 | 의미 | 구현 방식 |
|------|------|------|----------|
| `sourced_from` | Any → Source | 데이터 출처 참조 | 실제로는 엣지 속성 `source_id`로 대체 구현 (엣지 폭발 방지) |
| `verified_by` | Person → Person | 수사관이 다른 정보를 검증 | verified_dt 속성 포함 |

---

### 3.10 호환성 유지 엣지 (신규 생성 금지)

> 기존 DB 데이터 호환을 위해 방향 정보만 유지. 쿼리에서 읽기만 허용, ETL에서 생성 금지.

| 엣지 | 방향 | 대체 엣지 |
|------|------|----------|
| `involves` | Case → Person | `suspect_in` / `victim_in` / `witness_in` |
| `involves_org` | Case → Org | `member_of` + `suspect_in` 조합 |

---

## 4. 엣지 공통 메타속성

```python
# ── 필수 (모든 엣지) ──────────────────────────────────
source_id:       str    # vt_src.src_id 참조 (MANDATORY)
rec_created:     str    # ISO8601 DB 기록 시점 (MANDATORY)
creation_method: str    # 'manual'|'etl'|'ocr_ner'|'osint'|'inference'

# ── 신뢰도 (소유·귀속·추론 엣지) ─────────────────────
confidence:      float  # 0.0~1.0 (1.0 = 공식 문서)
credibility:     int    # 1~5 (source reliability_tier와 별도)
verified:        bool   # False=주장, True=수사관/공식문서 확인

# ── 이중시간 (소유·관계 엣지만) ─────────────────────
valid_from:      str    # 현실 유효 시작 (ISO8601)
valid_to:        str    # 현실 유효 종료 (null=현재 진행)

# ── 검증 정보 (verified=True 시 필수) ────────────────
verified_by:     str    # 수사관 ID
verified_at:     str    # 검증 일시
```

**이중시간 적용 범위**:

```
✅ 적용 (소유권·관계가 시간에 따라 변함):
   has_account, owns_phone, owns_device, owns_vehicle, member_of,
   drives, uses_id, uses_email, works_at, operates, registered_to

❌ 불필요 (이벤트 노드 자체가 시간 정보 보유):
   from_account, to_account, caller, callee, occurred_at, accessed_from/to
   → 이벤트 노드의 timestamp/dlng_dt/call_strt_dt가 Valid Time 역할
```

---

## 5. 핵심 이벤트 연결 패턴

```cypher
-- 금융 이체
(vt_bacnt:A)-[from_account]->(vt_transfer)-[to_account]->(vt_bacnt:B)
(vt_transfer)-[occurred_at]->(vt_loc)      -- ATM 출금 시

-- 통화
(vt_telno:발신)-[caller]->(vt_call)-[callee]->(vt_telno:수신)
(vt_call)-[occurred_at]->(vt_loc)          -- 기지국 위치

-- 메시지
(vt_telno)-[sent_msg]->(vt_msg)-[received_msg]->(vt_telno)

-- 네트워크 접속 (접속 출발 IP + 목적지 사이트 동시 참조)
(vt_access)-[accessed_from]->(vt_ip)       -- 출발 IP
(vt_access)-[accessed_to]->(vt_site)       -- 목적지 사이트

-- 이동 (LPR / 기지국 / 교통카드)
(vt_vhcl|vt_telno)-[recorded_in]->(vt_movement)-[occurred_at]->(vt_loc)

-- 사칭
(vt_telno|vt_id|vt_site)-[used_for]->(vt_impersonation)-[targets]->(vt_org)

-- 인프라 역추적
(vt_ip)-[hosts]->(vt_site)-[contains_file]->(vt_file)

-- 보이스피싱 핵심 패턴
(vt_telno)-[sent_msg]->(vt_msg)-[mentions_account]->(vt_bacnt)

-- 사건 증거 연결
(vt_case)-[eg_used_account]->(vt_bacnt)
(vt_case)-[eg_used_phone]->(vt_telno)
(vt_case)-[eg_used_ip]->(vt_ip)

-- 차량 추적 (소유 vs 운행)
(vt_psn)-[owns_vehicle]->(vt_vhcl)-[recorded_in]->(vt_movement)   -- 등록 소유주
(vt_psn)-[drives]->(vt_vhcl)                                       -- 실제 운전자
```

---

## 6. 버전별 변경 이력

| 버전 | 주요 변경 |
|------|----------|
| v3.0 | POLE 6레이어 확정, vt_src Provenance 도입, 22개→23개 노드 통폐합 |
| v3.1 | 엣지 메타속성 의무화 (source_id, rec_created), Bitemporal 선택적 적용 |
| v3.2 | Bridge Keys 체계화 (vt_id/email/crypto/dev/atm/loc ↔ RDB FK) |
| v3.3 | vt_impersonation 이벤트 노드 신설, used_for/targets 엣지 추가 |
| v3.4 | operates/recruits/blackmails/hosts/contains_file/located_at 6종 신규 |
|      | sent_msg(←sent_via), received_msg(←received_by) 명칭 변경 |
|      | performed_by 제거, accessed/hosted_at → hosts(방향 역전)로 대체 |

---

## 7. 노드·엣지 수 현황

| 구분 | 카운트 | 비고 |
|------|--------|------|
| 노드 타입 | **23개** | 원본 문서 요약표 "22개"는 vt_impersonation(v3.3) 미반영 오류 |
| 엣지 타입 | **52개** | 코드 교차검증 후 확정 (아래 상세) |
| 레이어 | **6계층** | Source / Case / Person / Object / Location / Event |

**엣지 52개 구성**:

| 카테고리 | 개수 | 엣지 목록 |
|----------|------|----------|
| Case 관련 | 7 | suspect_in, victim_in, witness_in, filed_as, related_case, linked_to, clusters_with |
| Case→Object 증거 | 3 | eg_used_account, eg_used_phone, eg_used_ip |
| Person 소유/귀속 | 15 | has_account, controls, owns_phone, owns_device, drives, owns_vehicle, uses_id, uses_email, used_ip, member_of, works_at, accomplice_of, sameAs, contradicts, owns |
| Person v3.4 신규 | 3 | operates, recruits, blackmails |
| Object→Person 예외 | 1 | registered_to |
| Object 관련 | 9 | transferred_to, resolves_to, belongs_to, hosts, contains_file, located_at, communicated_with, mentions_account, linked_to |
| Event 관련 | 10 | from_account, to_account, caller, callee, accessed_from, accessed_to, sent_msg, received_msg, occurred_at, recorded_in |
| 사칭 범죄 | 2 | used_for, targets |
| Meta/Provenance | 2 | sourced_from, verified_by |
| **합계** | **52** | `linked_to`는 Case/Object 양쪽에서 공유 (unique 타입 기준) |

**deprecated (코드 존재, 신규 생성 금지)**: `involves`, `involves_org`, `contacted`, `hosted_at`, `performed_by`, `sent_via`, `received_by`

---

## 8. 미결 항목 (향후 처리 필요)

| 항목 | 내용 | 우선순위 |
|------|------|---------|
| `eg_used_account/phone/ip` RELATIONSHIPS 미등재 | graph_service에만 존재, RELATIONSHIPS dict에 추가 필요 | Medium |
| `registered_to` 아키텍처 위반 검토 | Phone→Person이 레이어 매트릭스 예외 허용인지 공식 결정 필요 | Medium |
| `accessed_to` 아키텍처 문서 정정 | 원본 문서(§4.4)에 "제거됨"으로 잘못 기재됨 | Low |
| `hosted_at` 완전 제거 결정 | hosts로 대체 완료 후 graph_service에서 삭제 여부 결정 | Low |
| `contacted` 완전 제거 결정 | caller/callee로 대체 완료 후 삭제 여부 결정 | Low |

---

*이 파일은 ONTOLOGY_FINAL_ARCHITECTURE_v3.6.md + 코드(ontology_service.py, graph_service.py) 교차검증 결과입니다.*
*변경 시 원본 문서를 먼저 수정하고 이 파일을 동기화하세요.*
