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

# CCOP 온톨로지 v3.7 피드백 적용 결과 정리

> **기준 버전:** v3.6 → v3.7
> **피드백 수신:** 2026-05-12
> **적용 완료:** 2026-05-12
> **설계 문서:** `docs/ONTOLOGY_FINAL_ARCHITECTURE_v3.7.md`
> **구현 파일:** `app/middleware/services/ontology_service.py`

---

## 피드백 항목별 적용 현황

| # | 피드백 내용 | 결정 | 상태 |
|---|------------|------|------|
| 1 | pt_cluster 노드 추가, clusters_with 엣지 제거 | **수용 — 노드 승격** | ✅ 적용 완료 |
| 2 | site_cluster 노드 추가 (HTML SimHash) | **수용 — 신규 노드** | ✅ 적용 완료 |
| 3 | Person 성명불상 관리 (is_anonymous 필드) | **수용 — 속성 추가** | ✅ 적용 완료 |
| 4 | Phone - IMEI 엣지 추가 (불법중계기 탐지) | **수용 — 엣지 신설** | ✅ 적용 완료 |
| 5 | Phone - Location 직접 엣지 추가 | **기각 — Event 경유 유지** | ✅ 결정 문서화 |

---

## 1. pt_cluster 노드 추가 (clusters_with → 노드 승격)

### 문제
`clusters_with` 엣지가 Petition↔Petition 간 직접 연결로 구성되어 있어,
진정서 N건이 있으면 최악 O(n²)개 엣지 생성. 수천 건 진정서 수신 시 그래프 폭발.

```
[before v3.6]
vt_petition ←→ vt_petition ←→ vt_petition  (O(n²) 엣지)

[after v3.7]
vt_petition → pt_cluster ← vt_petition ← vt_petition  (O(n) 엣지)
```

### 적용 내용

**신규 노드: `pt_cluster` (CASE LAYER)**

| 속성 | 타입 | 설명 |
|------|------|------|
| `cluster_id` | str (PK) | 자동 채번 (예: `ptc-2026-001`) |
| `cluster_method` | str | `simhash` \| `tfidf` \| `manual` |
| `crime_type_cd` | str | 군집 대표 죄명 코드 |
| `damage_amt_sum` | int | 군집 내 피해액 합계 |
| `petition_cnt` | int | 소속 진정서 수 |
| `first_rcpt_dt` | str | 최초 접수일 |
| `last_rcpt_dt` | str | 최종 접수일 |
| `status` | str | `active` \| `merged` \| `closed` |

**신규 엣지: `belongs_to_cluster`** (Petition → pt_cluster)

| 속성 | 타입 |
|------|------|
| `sim_score` | float |
| `rec_created` | str |

**deprecated: `clusters_with`** — 신규 생성 금지, 기존 DB 레거시 조회용만 유지

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| `ontology_service.py` | `ENTITIES['PetitionCluster']` 추가 |
| `ontology_service.py` | `RELATIONSHIPS['belongs_to_cluster']` 추가 |
| `ontology_service.py` | `RELATIONSHIPS['clusters_with']['deprecated'] = True` |
| `ontology_service.py` | `LAYERS`, `GDB_LABEL_MAP`, `CONCEPT_LOOKUP`, `LABEL_KO_MAP`, `LAYERS_GDB` 갱신 |
| `ontology_service.py` | `OntologyEnricher._LABEL_META['pt_cluster']` 추가 |

---

## 2. site_cluster 노드 추가 (피싱 캠페인 군집)

### 문제
악성사이트가 도메인·IP를 교체하면 기존 `vt_site` 단일 노드 추적이 끊김.
동일 피싱 템플릿(HTML 구조)을 공유하는 캠페인 단위 추적 불가.

```
[before v3.7] 사이트 교체 시 연결 끊김
vt_site(domain-A) -[resolves_to]-> vt_ip(1.2.3.4)
                                    ↑ IP 교체 → 추적 불가

[after v3.7] SimHash로 캠페인 동일성 유지
vt_site(domain-A) -[belongs_to_campaign]-> site_cluster(sc-2026-001)
vt_site(domain-B) -[belongs_to_campaign]-> site_cluster(sc-2026-001)
vt_ip(1.2.3.4)   -[belongs_to_campaign]-> site_cluster(sc-2026-001)
```

### 적용 내용

**신규 노드: `site_cluster` (OBJECT LAYER)**

| 속성 | 타입 | 설명 |
|------|------|------|
| `cluster_id` | str (PK) | 자동 채번 (예: `sc-2026-001`) |
| `html_fingerprint` | str | DOM SimHash 64bit hex — 불변 캠페인 식별자 |
| `campaign_name` | str | 수사관 명명 (예: `카카오뱅크사칭-2026-04`) |
| `cluster_method` | str | `simhash` \| `manual` |
| `site_cnt` | int | 소속 vt_site 수 |
| `ip_cnt` | int | 관련 vt_ip 수 |
| `first_seen` | str | 최초 발견일 |
| `last_seen` | str | 최종 발견일 |

**신규 엣지: `belongs_to_campaign`** (WebTrace → site_cluster)

| 속성 | 타입 |
|------|------|
| `sim_score` | float |
| `detected_at` | str |
| `source_id` | str |
| `rec_created` | str |

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| `ontology_service.py` | `ENTITIES['SiteCluster']` 추가 |
| `ontology_service.py` | `RELATIONSHIPS['belongs_to_campaign']` 추가 |
| `ontology_service.py` | `OntologyEnricher._LABEL_META['site_cluster']` 추가 |

---

## 3. Person 성명불상 관리 (is_anonymous 필드)

### 문제
성명불상 피의자를 관리하는 표준 패턴이 없어 수사관마다 다르게 처리.
신원 확인 후 기존 노드 업데이트 vs 새 노드 생성 혼용 → 데이터 일관성 문제.

### 적용 내용

**`vt_psn` 속성 추가:**

```python
'is_anonymous': bool  # True = 성명불상 (v3.7 신규)
# is_anonymous=True 시: name='성명불상', rrno_hash=None
# 신원 확인 후: name·rrno_hash 업데이트, is_anonymous=False 전환
```

**운영 패턴 확정:**

```cypher
-- 성명불상 피의자 생성
CREATE (p:vt_psn {
    psn_id: 'psn-anon-' + randomUUID(),
    name: '성명불상',
    is_anonymous: true,
    rec_created: toString(datetime())
})

-- 신원 확인 후 업데이트 (노드 교체 아님 — 엣지 보존)
MATCH (p:vt_psn {psn_id: $psn_id})
SET p.is_anonymous = false,
    p.name = $real_name,
    p.rrno_hash = $rrno_hash,
    p.verified = true

-- 동일인물 가능성 시 sameAs 연결 (수사관 검토 후)
MATCH (anon:vt_psn {is_anonymous: true}), (known:vt_psn {psn_id: $known_id})
MERGE (anon)-[r:sameAs]->(known)
SET r.match_score = $score, r.review_status = 'pending'
```

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| `ontology_service.py` | `ENTITIES['Person']['attributes']`에 `is_anonymous` 추가 |

---

## 4. Phone - IMEI 엣지 추가 (불법중계기 탐지)

### 문제
전화번호(USIM)와 기기(IMEI) 연결 정보가 없어,
동일 기기에 여러 번호를 꽂아 사용하는 불법 사설중계기 패턴 탐지 불가.

```
[before v3.7] Phone과 Device 간 직접 연결 없음
vt_psn -[owns_phone]-> vt_telno
vt_psn -[owns_device]-> vt_dev
(telno와 dev 간 관계 불명)

[after v3.7]
vt_telno -[used_in_device]-> vt_dev
(IMEI 공유 3번호+ → relay_station 의심)
```

### 적용 내용

**신규 엣지: `used_in_device`** (Phone → Device)

| 속성 | 타입 | 설명 |
|------|------|------|
| `first_seen` | str | 해당 기기에서 최초 사용 일시 |
| `last_seen` | str | 해당 기기에서 최종 사용 일시 |
| `source_id` | str | 출처 (CDR 제공 통신사) |
| `rec_created` | str | DB 기록 시점 |

**`vt_dev.dev_type` 허용값 확장:**

| 값 | 설명 |
|----|------|
| `smartphone` | 일반 스마트폰 |
| `pc` | 데스크탑·노트북 |
| `tablet` | 태블릿 |
| `router` | 공유기 |
| **`relay_station`** ★ | 불법 사설중계기 (v3.7 신규) |
| `other` | 기타 |

**신규 추론 규칙: `RelayStationDetection`**

```python
{
    'name': 'RelayStationDetection',
    'pattern': 'multi_phone_same_imei',
    'trigger': '동일 IMEI(vt_dev)에 used_in_device 전화번호 3개+',
    'threshold': 3,
    'confidence': 0.90,
    'output_node_flag': 'vt_dev.dev_type = relay_station',
    'legal_basis': '전기통신사업법 제30조 (불법중계기 제조·사용 금지)'
}
```

**탐지 쿼리 (§6.8):**

```cypher
MATCH (t:vt_telno)-[:used_in_device]->(d:vt_dev)
WITH d, collect(t) AS phones
WHERE size(phones) >= 3
RETURN d.imei, d.dev_type, size(phones) AS phone_count,
       [p IN phones | p.telno] AS telno_list
ORDER BY phone_count DESC
```

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| `ontology_service.py` | `RELATIONSHIPS['used_in_device']` 추가 |
| `ontology_service.py` | `ENTITIES['Device']` 설명에 `relay_station` dev_type 명시 |
| `ontology_service.py` | `INFERENCE_RULES`에 `RelayStationDetection` 추가 (10번째) |
| `ontology_service.py` | `COLUMN_PATTERNS['device']` 추가 (`imei`, `중계기` 패턴 포함) |
| `ontology_service.py` | `OntologyEnricher.enrich_edge` EDGE_SEMANTICS에 `used_in_device` 추가 |

---

## 5. Phone - Location 직접 엣지 (결정: 미추가, Option B 선택)

### 요청 내용
전화번호 위치를 1홉으로 조회할 수 있도록 `vt_telno → vt_loc` 직접 엣지 추가.

### 검토

| 항목 | Option A (직접 엣지) | Option B (Event 경유 유지) |
|------|--------------------|-----------------------|
| 쿼리 복잡도 | 1홉 (`pinged_at`) | 2홉 (`recorded_in` → `occurred_at`) |
| 시간 정보 | ❌ 손실 | ✅ `vt_movement.timestamp` 보존 |
| 중복 데이터 | ❌ `vt_movement`와 동일 정보 이중 저장 | ✅ 단일 소스 |
| `used_in_device`와의 모호성 | ❌ Phone→Location 경로 2개 생성 | ✅ 경로 명확 |
| POLE 원칙 준수 | △ 레이어 직접 점프 | ✅ Event 레이어 경유 |

### 결정 사유
1. `vt_movement`가 이미 `mov_type='cell_tower'`로 기지국 데이터 처리 중 — 중복 저장
2. `used_in_device` (Phone→Device) 신설로 인해 Phone에서 Location으로의 경로가 2개 생기면
   "이 번호 어디 있어?" 쿼리 시 의미론적 혼란 발생 가능
3. 이동 패턴 분석(연속 이동, 동선 교차)에서 Movement 이벤트의 시간 정보가 필수

### 대안: 표준 쿼리 패턴 (§6.12) 문서화

```cypher
-- 최근 위치 1건
MATCH (t:vt_telno {telno: $telno})
      -[:recorded_in]->(m:vt_movement {mov_type: 'cell_tower'})
      -[:occurred_at]->(loc:vt_loc)
RETURN loc ORDER BY m.timestamp DESC LIMIT 1

-- 시간순 이동 경로
MATCH (t:vt_telno {telno: $telno})
      -[:recorded_in]->(m:vt_movement {mov_type: 'cell_tower'})
      -[:occurred_at]->(loc:vt_loc)
RETURN m.timestamp, loc.bsst_nm, loc.address, loc.lat, loc.lng
ORDER BY m.timestamp

-- 복수 번호 동선 교차 (같은 기지국 + 1시간 내)
MATCH (t1:vt_telno {telno: $telno1})-[:recorded_in]->(m1)-[:occurred_at]->(loc),
      (t2:vt_telno {telno: $telno2})-[:recorded_in]->(m2)-[:occurred_at]->(loc)
WHERE abs(duration.inSeconds(m1.timestamp, m2.timestamp).seconds) <= 3600
RETURN loc.bsst_nm, m1.timestamp, m2.timestamp
```

### 변경 파일

| 파일 | 변경 내용 |
|------|---------|
| `docs/ONTOLOGY_FINAL_ARCHITECTURE_v3.7.md` | 헤더에 5번 결정 명시 |
| `docs/ONTOLOGY_FINAL_ARCHITECTURE_v3.7.md` | §6.12 쿼리 패턴 추가 |
| `docs/ONTOLOGY_FINAL_ARCHITECTURE_v3.7.md` | 설계 결정 배경 테이블에 5번 항목 추가 |

> **향후 재검토 조건**: 수사관이 "단말기 등록 주소"와 같이 *정적 위치*를 별도 관리해야 한다는
> 운영 요구가 발생하면 `registered_location` 엣지(Phone→Location) 추가를 재논의한다.

---

## 적용 후 온톨로지 스펙 변화

| 항목 | v3.6 | v3.7 | 변화 |
|------|------|------|------|
| 노드 타입 | 23개 | **25개** | +2 (pt_cluster, site_cluster) |
| 엣지 타입 | 52개 | **53개** | +3 신설, -1 deprecated = +2 순증, 문서화 53개 |
| 추론 규칙 | 9개 | **10개** | +1 (RelayStationDetection) |
| 군집 표현 방식 | 엣지 (O(n²)) | **허브 노드 (O(n))** | 아키텍처 개선 |

### 노드 변경 상세

| 변경 | 노드 | 레이어 |
|------|------|-------|
| 신설 | `pt_cluster` | CASE |
| 신설 | `site_cluster` | OBJECT |
| 속성 추가 | `vt_psn.is_anonymous` | PERSON |
| dev_type 확장 | `vt_dev` (`relay_station`) | OBJECT |

### 엣지 변경 상세

| 변경 | 엣지 | 방향 |
|------|------|------|
| 신설 | `belongs_to_cluster` | Petition → pt_cluster |
| 신설 | `belongs_to_campaign` | WebTrace → site_cluster |
| 신설 | `used_in_device` | Phone → Device |
| deprecated | `clusters_with` | Petition → Petition |
| 미추가 (결정) | `pinged_at` 또는 유사 | Phone → Location |

---

## 미완료 항목 (후속 작업)

| 우선순위 | 항목 | 파일 | 내용 |
|---------|------|------|------|
| 🔴 High | sourced_from 버그 수정 | `app/services/rdb_to_graph_service.py` | `sourced_from` 대상이 `vt_case`로 잘못 연결 → `vt_src`로 수정 |
| 🟡 Medium | pt_cluster 자동 생성 서비스 | 신규 파일 | 진정서 유사도 분석 → belongs_to_cluster 엣지 자동 생성 |
| 🟡 Medium | site_cluster 자동 생성 서비스 | 신규 파일 | HTML SimHash 비교 → belongs_to_campaign 엣지 자동 생성 |
| 🟡 Medium | used_in_device 자동 매핑 | ETL 서비스 | CDR IMSI/IMEI 데이터 기반 자동 연결 |
| 🟢 Low | 성명불상 검토 UI | 프론트엔드 | is_anonymous=True 피의자 수사관 검토 워크플로 |
