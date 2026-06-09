# V4.0 RDB → 그래프 매핑 명세 (L2 → L3 → L4)

**작성일**: 2026-05-21
**상위 표준**: [`CCOP_ONTOLOGY_V4.0.md`](CCOP_ONTOLOGY_V4.0.md)
**전제 문서**: [`V40_RDB_SCHEMA_STANDARD.md`](V40_RDB_SCHEMA_STANDARD.md)
**구현 코드**: `app/services/rdb_to_graph_service.py`, `app/services/osint_v37_postprocess.py`

---

## 0. 매핑 흐름

```
[L2 표준 RDB]                  [L3 매핑/변환]               [L4 그래프]
─────────────                  ──────────────              ─────────────
tccop_official.tb_bacnt   ─→   RDB row 추출            ─→  (:vt_bacnt {
  account_no='110-...'         + 표준화 정규화              account_no: '110-...',
  bank_cd='KB'                 + V4.0 메타 자동 주입        id_format: 'plain_dash',
  is_burner=false              + 라벨/속성 매핑             source_domain: 'investigation',
  source_domain='inv'          + 검증                       reliability_tier: 1,
                                                            bank_cd: 'KB',
                                                            is_burner: false,
                                                            ... })
```

---

## 1. 매핑 표준 원칙

### 1.1 단일 진실
모든 RDB → 노드/엣지 변환 규칙은 본 문서 + `ontology_service.py` 메타에 명시. 코드 산재 금지.

### 1.2 1:1 vs 1:N 노드 생성
- **1:1**: 한 RDB row = 한 그래프 노드 (PK 기준)
- **1:N**: 동일 RDB row가 여러 노드/엣지 생성 (예: cmnty_dtl 1건 → vt_msg + vt_id + sent_msg 엣지)

### 1.3 V4.0 메타 자동 주입
모든 노드에 다음 의무 부착 (L3 변환기 자동):
- `id_format`: NODE_ID_STANDARD[label]['default_format']
- `source_domain`: RDB row의 source_domain 컬럼 또는 도메인 스키마
- `reliability_tier`: RDB row의 reliability_tier (또는 도메인 default)
- `source_id`: vt_src 참조
- `rec_created`: ETL 실행 시점

---

## 2. 노드별 매핑 명세 (25 노드 전체)

### 2.1 Source Layer

#### vt_src
| 속성 | RDB Source | 변환 | id_format |
|---|---|---|---|
| `src_id` | `*.source_id` 또는 어댑터 생성 | 도메인별 prefix (`osint_crawl_*`, `tccop_official_*`) | plain |
| `src_type` | – | 'osint_crawl' / 'official_rdb' / 'partner_api' / 'inference' | – |
| `src_name` | – | 어댑터 작성자 결정 | – |
| `reliability_tier` | – | investigation=1, partner=2-3, osint=4 | – |
| `collector` | – | 어댑터 이름 | – |
| `collected_at` | `*.collected_at` | direct | – |

### 2.2 Case Layer

#### vt_case
| 속성 | RDB Source | 변환 |
|---|---|---|
| **id_format**: plain | – | – |
| **source_domain**: investigation | tccop_official.* | – |
| **reliability_tier**: 1 | – | – |
| `flnm` (PK) | `tccop_official.tb_case.case_id` | direct |
| `incdnt_typ_cd` | `tb_case.incdnt_typ_cd` | tb_cmn_cd[CRIME_TYPE] 검증 |
| `occrn_dt` | `tb_case.occrn_dt` | direct |
| `damage_amount` | `tb_case.damage_amount` | direct (int) |
| `status` | `tb_case.status` | tb_cmn_cd[CASE_STATUS] 검증 |

#### vt_petition
| 속성 | RDB Source | 변환 |
|---|---|---|
| **id_format**: plain / **source_domain**: investigation | – | – |
| `petition_id` (PK) | `tccop_official.tb_petition.petition_id` 또는 `osint.tb_the_cheat_fraud.id` (`the_cheat_*`) | 도메인별 prefix |
| `rcpt_dt` | `tb_petition.rcpt_dt` | direct |
| `crime_type_cd` | `tb_petition.crime_type_cd` | tb_cmn_cd[CRIME_TYPE] 검증 |
| `damage_amt` | `tb_petition.damage_amt` | direct |

**L3 변환 SQL 예시**:
```sql
LOAD FROM tccop_official.tb_petition AS row
CREATE (:vt_petition {
    petition_id:      row.petition_id,
    id_format:        'plain',
    source_domain:    'investigation',
    reliability_tier: 1,
    rcpt_dt:          row.rcpt_dt,
    crime_type_cd:    row.crime_type_cd,
    damage_amt:       row.damage_amt,
    source_id:        row.source_id,
    rec_created:      toString(now())
});
```

#### pt_cluster ⭐ V3.7 신규 (추론 결과)
| 속성 | RDB Source | 변환 |
|---|---|---|
| `cluster_id` (PK) | `inference.tb_pt_cluster.cluster_id` | `ptc-YYYY-NNNN` 형식 |
| `cluster_method` | – | 'union_find' (6V-1) |
| `petition_cnt` | 집계 | COUNT(*) FROM tb_petition WHERE cluster_id |
| `damage_amt_sum` | 집계 | SUM(damage_amt) |
| **추론 룰**: PtClusterDetection (TB_PETTN_CLSTR sim_score ≥ 0.7) | – | – |

### 2.3 Person Layer

#### vt_psn (CCOP 전용 — OSINT는 ❌)
| 속성 | RDB Source | 변환 |
|---|---|---|
| **source_domain**: investigation | tccop_official.tb_prsn | – |
| `psn_id` (PK) | `tb_prsn.psn_id` | direct |
| `name` | `tb_prsn.name` | direct |
| `korn_flnm` | `tb_prsn.korn_flnm` | direct |
| `risk_level` | `tb_prsn.risk_level` | tb_cmn_cd[RISK_LEVEL] 검증 |
| `is_anonymous` ⭐ | `tb_prsn.korn_flnm IS NULL OR ''` | **자동 추론** (AnonymousFlagDetection) |

#### vt_org
| 속성 | RDB Source |
|---|---|
| `org_id` (PK) | `tccop_official.tb_org.org_id` |
| `org_name` | direct |
| `brno` | direct |

### 2.4 Object Layer (핵심 — 양쪽 도메인)

#### vt_bacnt ⭐ 양쪽 도메인 사용
| 속성 | CCOP RDB | OSINT RDB | 변환 |
|---|---|---|---|
| **id_format** | plain_dash | **md5** ⭐ | 도메인별 자동 |
| **source_domain** | investigation | osint | – |
| **reliability_tier** | 1 | 4 | – |
| `account_no` | `tccop_official.tb_bacnt.account_no` | `osint.tb_the_cheat_fraud.suspct_acnt` | CCOP: dash-format, OSINT: md5 그대로 |
| `bank_cd` | `tb_bacnt.bank_cd` | `tb_the_cheat_fraud.bank_cd` | tb_bank_cd 검증 |
| `is_burner` | `tb_bacnt.is_burner` | `false` (OSINT 미관측) | – |

**Cross-source sameAs 추론**:
```python
# 같은 계좌가 양쪽에 다른 형식으로 존재 시
ccop_node = vt_bacnt(account_no='110-1111-2222', id_format='plain_dash')
osint_node = vt_bacnt(account_no='abc123...md5', id_format='md5')

# SameAsResolution 추론 (Inference)
if md5(ccop_node.account_no.replace('-', '')) == osint_node.account_no:
    create sameAs(ccop_node, osint_node, confidence=0.95)
```

#### vt_telno ⭐ 양쪽 도메인
| 속성 | CCOP RDB | OSINT RDB | 변환 |
|---|---|---|---|
| **id_format** | no_hyphen_e164 | **md5** | – |
| `telno` | `tccop_official.tb_telno.telno` | `osint.tb_the_cheat_sms.sndr_telno` | CCOP: `public.normalize_telno()` |
| `imei` | `tb_telno.imei` | – | direct (used_in_device 추론 입력) |
| `is_burner` | `tb_telno.is_burner` | – | – |

#### vt_ip
| 속성 | RDB Source | 변환 |
|---|---|---|
| `ip_addr` (PK) | `tccop_official.tb_ip.ip_addr` 또는 `osint.tb_the_cheat_url.ip` | `public.normalize_ipv4()` |
| `country` | `tb_ip.country` | tb_country_cd 검증 |
| `is_vpn` | `tb_ip.is_vpn` | direct |
| `threat_score` | `tb_ip.threat_score` | range 0-100 |

#### vt_site ⭐ OSINT 주, CCOP 보조
| 속성 | RDB Source | 변환 |
|---|---|---|
| **id_format**: normalized_url | – | – |
| **source_domain**: 대부분 osint | – | – |
| `url_addr` (PK) | `osint.clct_page.url_norm` 또는 `osint.tb_the_cheat_url.dmn_nm` | `public.normalize_url()` |
| `is_malicious` | `osint.tb_the_cheat_url` 존재 시 true | – |
| `html_src` | `osint.clct_page.html_src` | direct (site_cluster 추론 입력) |

#### site_cluster ⭐ V3.7 신규 (추론 결과)
| 속성 | RDB Source | 변환 |
|---|---|---|
| `cluster_id` (PK) | `inference.tb_site_cluster.cluster_id` | `osint-sc-NNNN` |
| `html_fingerprint` | 계산값 | SimHash 64-bit |
| `site_cnt` | 집계 | – |
| **추론 룰**: SiteClusterDetection | – | – |

#### vt_file
| 속성 | CCOP RDB | OSINT RDB | 변환 |
|---|---|---|---|
| **id_format**: sha256 (default) | – | – | md5/sha1도 허용 |
| `hash_val` | `tccop_official.tb_file.hash_val` | `osint.atch_file.atch_file_hash_cd` | direct |
| `file_nm` | `tb_file.file_nm` | `atch_file.file_nm` | direct |
| `is_malicious` | `tb_file.is_malicious` | – | – |

#### vt_id ⭐ OSINT 주
| 속성 | RDB Source | 변환 |
|---|---|---|
| **복합 PK**: (platform, id_val) | – | – |
| `platform` | `cmnty_dtl.cmnty_nm`, `sns_dtl.sns_nm`, `chatrm.chatrm_pltfrm_nm` | 도메인 추출 |
| `id_val` | `*.wrtr_nm`, `chat.user_id` | direct |
| `is_anonymous` ⭐ | `wrtr_nm IS NULL OR LIKE '%***%'` | 자동 추론 |
| `is_active` | – | OSINT 미관측, default true |

#### vt_dev ⭐ CCOP 전용
| 속성 | RDB Source | 변환 |
|---|---|---|
| `device_id` (PK) | `tccop_official.tb_dev.device_id` | direct |
| `dev_type` | `tb_dev.dev_type` | tb_cmn_cd[DEV_TYPE] 검증 ('smartphone', 'pc', ..., **'relay_station'** ⭐) |
| `imei` | `tb_dev.imei` | direct |
| **추론**: RelayStationDetection (IMEI 3대+ 공유) | – | – |

#### 기타 Object (vt_email, vt_crypto, vt_vhcl, vt_atm)
**CCOP 전용** — `tccop_official.tb_email`, `tb_crypto`, `tb_vhcl`, `tb_atm` 직접 매핑.

### 2.5 Event Layer

#### vt_transfer
| 속성 | RDB Source |
|---|---|
| `transfer_id` (PK) | `tccop_official.tb_transfer.transfer_id` 또는 `osint.tb_the_cheat_fraud.id` |
| `amount` | direct |
| `dlng_dt` | direct |

#### vt_call, vt_access, vt_movement
**CCOP 전용** — `tccop_official.tb_call`, `tb_access`, `tb_movement` 직접 매핑.

#### vt_msg ⭐ OSINT 주
| 속성 | RDB Source | 변환 |
|---|---|---|
| `msg_id` (PK) | 도메인별 prefix | `cmnt_*`, `sns_*`, `used_*`, `srch_*`, `chat_*`, `spam_sms_*` |
| `msg_type` | – | tb_cmn_cd[MSG_TYPE] 자동 결정 |
| `content_text` | `*.content` | direct |

#### vt_impersonation
| 속성 | RDB Source |
|---|---|
| `imprsn_id` (PK) | `tccop_official.tb_imprsn.imprsn_id` |
| `imprsn_type_cd` | tb_cmn_cd[IMPRSN_TYPE] |

### 2.6 Location Layer

#### vt_loc
| 속성 | RDB Source |
|---|---|
| `loc_id` (PK) | `tccop_official.tb_loc.loc_id` |
| `address` | direct |
| `lat`, `lng` | direct |

---

## 3. 엣지별 매핑 명세 (53 엣지 중 주요 — 전체는 ontology_service.py 참조)

### 3.1 Case 관련

| 엣지 | RDB Source | 매칭 키 | 변환 |
|---|---|---|---|
| **suspect_in** | `tb_role` WHERE role_type='suspect' | (psn_id, case_id) | (vt_psn)-[:suspect_in]->(vt_case) |
| **victim_in** | `tb_role` WHERE role_type='victim' | 동일 | 동일 |
| **witness_in** | `tb_role` WHERE role_type='witness' | 동일 | 동일 |
| **eg_used_account** | `tb_evidence` WHERE evidence_type='account' | (case_id, account_no) | (vt_case)-[:eg_used_account]->(vt_bacnt) |
| **filed_as** | `tb_petition.linked_case_id` IS NOT NULL | (petition_id, linked_case_id) | (vt_petition)-[:filed_as]->(vt_case) |
| **belongs_to_cluster** ⭐ | 6V-1 추론 결과 | (petition_id, cluster_id) | (vt_petition)-[:belongs_to_cluster]->(pt_cluster) |

### 3.2 Person 관련

| 엣지 | RDB Source | 변환 |
|---|---|---|
| **has_account** | `tb_prsn_acnt` (psn_id, account_no) | (vt_psn)-[:has_account]->(vt_bacnt) |
| **owns_phone** | `tb_prsn_telno` | (vt_psn)-[:owns_phone]->(vt_telno) |
| **drives** | `tb_prsn_vhcl` WHERE rel_type='driver' | (vt_psn)-[:drives]->(vt_vhcl) |
| **owns_vehicle** | `tb_prsn_vhcl` WHERE rel_type='owner' | (vt_psn)-[:owns_vehicle]->(vt_vhcl) |
| **member_of** | `tb_prsn_org` | (vt_psn)-[:member_of]->(vt_org) |
| **accomplice_of** | `tb_prsn_rel` WHERE rel_type='accomplice' | (vt_psn)-[:accomplice_of]->(vt_psn) |
| **recruits** | `tb_prsn_rel` WHERE rel_type='recruits' | – |
| **registered_to** | `tb_telno.registered_psn_id` | (vt_telno)-[:registered_to]->(vt_psn) |

### 3.3 Event 관련

| 엣지 | RDB Source | 변환 |
|---|---|---|
| **from_account** | `tb_transfer.from_acnt_no` | (vt_bacnt)-[:from_account]->(vt_transfer) |
| **to_account** | `tb_transfer.to_acnt_no` | (vt_transfer)-[:to_account]->(vt_bacnt) |
| **caller** | `tb_call.caller_telno` | (vt_telno)-[:caller]->(vt_call) |
| **callee** | `tb_call.callee_telno` | (vt_call)-[:callee]->(vt_telno) |
| **sent_msg** | OSINT: `cmnty_dtl/sns_dtl/used_mkt_dtl/chat/spam_sms` 발신 | (vt_id\|vt_telno)-[:sent_msg]->(vt_msg) |
| **received_msg** | OSINT: SMS 등 | (vt_msg)-[:received_msg]->(vt_telno) |

### 3.4 V3.7 신규 엣지

| 엣지 | 추론 룰 | 변환 |
|---|---|---|
| **belongs_to_cluster** ⭐ | PtClusterDetection | (vt_petition)-[:belongs_to_cluster {sim_score, rec_created}]->(pt_cluster) |
| **belongs_to_campaign** ⭐ | SiteClusterDetection | (vt_site)-[:belongs_to_campaign {sim_score, detected_at}]->(site_cluster) |
| **used_in_device** ⭐ | RelayStationDetection | (vt_telno)-[:used_in_device {first_seen, last_seen}]->(vt_dev) |

### 3.5 Cross-Domain sameAs

| 엣지 | 매칭 방법 | 신뢰도 |
|---|---|---|
| **sameAs** | id_format 기반 정규화 + 해싱 (SameAsResolution) | confidence 0.7~0.99 |

---

## 4. OSINT 1:N 변환 패턴 (특수 케이스)

OSINT 데이터는 1 RDB row가 여러 그래프 요소를 생성하는 경우가 많음:

### 4.1 osint.clct_page → 다중 노드/엣지
```
clct_page (1 row)
  ├─→ vt_src (clct_page_id)
  ├─→ vt_site (url_norm)
  ├─→ sourced_from(vt_site → vt_src)
  └─→ (조건부) vt_file via atch_file FK 조인
```

### 4.2 osint.cmnty_dtl → 다중
```
cmnty_dtl (1 row, 댓글 N개)
  ├─→ vt_msg ('cmnt_<dtl_id>')
  ├─→ vt_id (cmnty_nm, wrtr_nm)  -- 작성자
  ├─→ sent_msg(vt_id → vt_msg)
  ├─→ sourced_from(vt_msg → vt_src)
  └─→ (cmnt_list 처리 시) 댓글별 vt_msg + sent_msg
```

### 4.3 osint.chat → 다중
```
chat (1 row, chatrm.chatrm_id FK)
  ├─→ vt_msg ('chat_<chat_id>')
  ├─→ vt_id (chatrm_pltfrm_nm, user_id)
  ├─→ sent_msg(vt_id → vt_msg)
  └─→ sourced_from(vt_msg → vt_src via chatrm.clct_page_id)
```

### 4.4 osint.tb_the_cheat_fraud → 다중
```
tb_the_cheat_fraud (1 row, 더치트 사기 신고)
  ├─→ vt_src ('the_cheat_fraud_<id>')
  ├─→ vt_bacnt (suspct_acnt, id_format='md5')  -- 사기 계좌
  ├─→ vt_telno (suspct_telno, id_format='md5') -- 사기 전화
  ├─→ vt_site (fraud_acdnt_site, id_format='normalized_url') -- 사기 사이트
  ├─→ vt_transfer ('fraud_<id>')
  ├─→ sourced_from (각 노드 → vt_src)
  └─→ (옵션 B) vt_petition (id_format='plain', source_domain='osint', tier=4)
```

---

## 5. ID 형식 변환 매핑 (RDB → 그래프)

| RDB 컬럼 | 원본 형식 | 그래프 노드 id_format | 변환 함수 |
|---|---|---|---|
| `tb_bacnt.account_no` | dash-separated | plain_dash | `public.normalize_account()` |
| `tb_telno.telno` | 다양 | no_hyphen_e164 | `public.normalize_telno()` |
| `tb_the_cheat_fraud.suspct_acnt` | MD5 | md5 | (그대로) |
| `tb_the_cheat_fraud.suspct_telno` | MD5 | md5 | (그대로) |
| `clct_page.url` | 정규화 전 URL | normalized_url | `public.normalize_url()` |
| `tb_ip.ip_addr` | IPv4 | ipv4_dotted | `public.normalize_ipv4()` |
| `tb_email.email_addr` | 대소문자 혼재 | plain | `public.normalize_email()` |
| `atch_file.atch_file_hash_cd` | md5 (보통) | md5 / sha256 | `public.normalize_md5()` |

---

## 6. L3 변환기 표준 워크플로

### 6.1 단일 노드 변환 표준 (psuedo-code)

```python
from app.middleware.services.ontology_service import KICSCrimeDomainOntology as Onto
from app.services.rdb_to_graph_service import RdbToGraphService

def transform_rdb_row_to_node(label: str, rdb_row: dict, source_domain: str) -> str:
    """L2 RDB row → L4 그래프 노드 변환 표준."""
    
    # 1. 라벨 유효성 (V4.0 SSOT 검증)
    if label not in Onto.NODE_ID_STANDARD:
        raise OntologyViolation(f"Unknown label: {label}")
    if not Onto.is_applicable(label, source_domain):
        raise OntologyViolation(f"{label} not applicable in {source_domain}")
    
    # 2. RDB → 노드 속성 매핑
    id_meta = Onto.get_id_format(label)
    canonical_field = id_meta['canonical_field']
    canonical_id = rdb_row[canonical_field]  # 이미 L2에서 정규화됨
    
    # 3. V4.0 메타 자동 주입
    props = RdbToGraphService.make_node_props_v40(
        label,
        base_props=rdb_row,
        source_domain=source_domain,
        source_id=rdb_row.get('source_id'),
    )
    
    # 4. Cypher 생성 + 실행
    cypher = f"MERGE (n:{label} {{{canonical_field}: '{canonical_id}'}}) SET n += {props}"
    return cypher
```

### 6.2 추론 엣지 변환 표준

```python
def apply_inference_rule(rule_name: str, graph_name: str):
    """V4.0 추론 규칙 카탈로그 기반 자동 추론."""
    rule = Onto.INFERENCE_RULES_V37[rule_name]
    
    # 입력 노드 검증
    for label in rule['input_nodes']:
        if not Onto.DOMAIN_USAGE[label].get(source_domain) in ('primary', 'possible'):
            return  # 도메인 적용 불가
    
    # 알고리즘 실행 → 출력 노드/엣지 생성
    # ...
```

---

## 7. 매핑 무결성 검증 (Quality Checks)

### 7.1 매핑 검증 항목

| # | 검증 | 방법 |
|---|---|---|
| M1 | 모든 노드에 V4.0 메타 6종 존재 | `MATCH (n) WHERE n.id_format IS NULL RETURN ...` |
| M2 | canonical_id가 NODE_ID_STANDARD 형식 | 정규식 검증 |
| M3 | enum 속성이 tb_cmn_cd에 존재 | join 검증 |
| M4 | 엣지 src/tgt 라벨이 EDGE_CATALOG 정의와 일치 | EDGE_DIRECTIONS 검증 |
| M5 | OSINT 그래프에 vt_psn 노드 없음 (DOMAIN_USAGE 일관성) | – |
| M6 | reliability_tier가 source_domain의 기본값과 일치 | tier_map 검증 |
| M7 | deprecated 엣지(`clusters_with`) 신규 생성 0건 | – |

### 7.2 검증 실행
```bash
python -m app.services.ontology_validator --graph tccop_graph_v6
python -m app.services.ontology_validator --graph osint_ontology
```

(`ontology_validator`는 향후 산출물 — `docs/V40_VALIDATION_GUIDE.md` 참조 예정)

---

## 8. 신규 노드/엣지 추가 시 절차 (RFC)

```
1. SSOT 갱신 — ontology_service.py
   ├─ ENTITIES (라벨 정의)
   ├─ RELATIONSHIPS (엣지 방향성)
   ├─ NODE_ID_STANDARD (id_format)
   ├─ DOMAIN_USAGE (도메인 사용)
   └─ tb_cmn_cd 코드 추가 (필요 시)

2. RDB 스키마 갱신 — V40_RDB_SCHEMA_STANDARD.md
   ├─ 신규 테이블 또는 컬럼 추가
   └─ V4.0 메타 컬럼 6종 의무 포함

3. 본 매핑 명세 갱신 — V40_RDB_TO_GRAPH_MAPPING.md
   ├─ §2 노드별 매핑에 행 추가
   └─ §3 엣지별 매핑에 행 추가

4. L3 변환기 코드 갱신 — rdb_to_graph_service.py
   └─ 신규 라벨/엣지 처리 추가

5. 시각화 표준 갱신 — V40_VISUALIZATION_STANDARD.md
   └─ 색상/아이콘 결정

6. 벤치마크/테스트 갱신
   └─ benchmark_t2c_v2.py 등에 신규 패턴 케이스 추가
```

---

## 9. 매핑 변경 이력

| 일자 | 버전 | 변경 |
|---|---|---|
| 2026-03 (추정) | V3.7 | pt_cluster, site_cluster, used_in_device 매핑 신설 |
| 2026-05-21 | V4.0 | RDB 도메인 스키마 분리 + V4.0 메타 의무화 + 매핑 SSOT 격상 |

---

## 10. 핵심 결론

> **본 매핑 명세는 V4.0의 L3 (변환) 레이어의 진실(SSOT)**. 모든 L3 코드(`rdb_to_graph_service.py`, `osint_v37_postprocess.py`)는 본 문서를 기준으로 구현되어야 하며, 변경 시 본 문서를 우선 갱신한 뒤 코드를 따라가야 한다.

---

**문서 끝**
