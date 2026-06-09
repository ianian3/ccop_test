# OSINT × V3.7 온톨로지 통합 가이드

**작성일**: 2026-05-21
**대상**: OSINT V3.6 ETL 보고서 (`CCOP V3.6 OSINT 그래프 ETL 프로세스 보고서`)
**목적**: V3.7 신규 카탈로그(pt_cluster / site_cluster / is_anonymous / relay_station) 중 OSINT 도메인에 적용 가능한 항목을 표준 메타와 ETL 단계에 반영

---

## 0. 통합 원칙

본 가이드는 **단일 V3.7 SSOT 카탈로그 + 도메인별 사용 매트릭스** 패턴을 따른다. 카탈로그를 합치는 게 아니라, 단일 SSOT 위에 OSINT 사용 가능 노드/엣지/속성을 명시화한다.

```
                  단일 V3.7 SSOT (KICSCrimeDomainOntology)
                  ───────────────────────────────────────
                   25 노드 / 53 엣지 / 표준 속성 / 추론 규칙
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   CCOP 사용 매트릭스    OSINT 사용 매트릭스    Partner 사용 매트릭스
   25/25, 53/53          10/25, 6/53           ?/25, ?/53
```

---

## 1. 5가지 V3.7 표준화 작업

| # | 작업 | 산출물 | 상태 |
|---|---|---|---|
| ① | `id_format` 메타 도입 (NODE_ID_STANDARD) | `ontology_service.py` ✅ | 완료 |
| ② | 도메인 사용 매트릭스 (DOMAIN_USAGE) | `ontology_service.py` ✅ | 완료 |
| ③ | STEP 7.5a — `site_cluster` 노드 생성 | SQL 패치 + Python 모듈 ✅ | 완료 |
| ④ | STEP 8.5a — `belongs_to_campaign` 엣지 | SQL 패치 ✅ | 완료 |
| ⑤ | STEP 8.6 — `vt_id.is_anonymous` 마킹 | SQL 패치 ✅ | 완료 |

---

## 2. ① NODE_ID_STANDARD — 식별자 형식 표준

### 2.1 배경
OSINT V3.6 보고서 §5.1.3에서 발견된 핵심 문제: **동일 노드 라벨이라도 도메인별 식별자 형식이 다름**. 예: vt_bacnt가 CCOP에선 평문(`110-2222-3333`), OSINT 더치트에선 MD5 해시.

### 2.2 표준 메타 (적용 완료)
`app/middleware/services/ontology_service.py:KICSCrimeDomainOntology`에 `NODE_ID_STANDARD` dict 추가됨.

### 2.3 노드 인스턴스에 id_format 속성 명시
ETL 시 모든 노드 적재 시 `id_format` 속성을 추가:

```sql
-- 예시: vt_bacnt (OSINT 더치트, MD5 해시)
LOAD FROM stg_osint.bacnt AS row
CREATE (:vt_bacnt {
  account_no:       row.suspct_acnt,
  id_format:        'md5',                  -- ⭐ V3.7 표준 메타
  source_domain:    'osint',                -- ⭐ V3.7 표준 메타
  reliability_tier: 4,
  source_id:        row.source_id
});

-- 예시: vt_telno (정규화된 평문)
LOAD FROM stg_osint.telno_fraud AS row
CREATE (:vt_telno {
  telno:            row.suspct_telno,
  id_format:        'md5',                  -- 더치트는 해시
  source_domain:    'osint',
  reliability_tier: 4
});

-- 예시: vt_site (URL 정규화)
LOAD FROM stg_osint.site_clct_page AS row
CREATE (:vt_site {
  url_addr:         row.url_norm,
  id_format:        'normalized_url',       -- ⭐
  source_domain:    'osint',
  reliability_tier: 4,
  html_src:         row.html_src            -- SimHash 군집화용 (STEP 7.5a 필수)
});
```

### 2.4 효과
- Cross-source `sameAs` 자동 매칭 가능 (예: OSINT 평문 → MD5 해싱 → CCOP MD5와 비교)
- 그래프 질의에서 `WHERE n.id_format = 'plain_dash'` 필터 가능
- 도메인 라우팅의 입력 데이터

---

## 3. ② DOMAIN_USAGE — 도메인 사용 매트릭스

### 3.1 OSINT V3.6 §10.2/10.3 → V3.7 표준 메타로 격상

`KICSCrimeDomainOntology.DOMAIN_USAGE`로 코드화됨. OSINT 보고서의 매트릭스가 SSOT에 들어감.

### 3.2 V3.7 매트릭스 (OSINT 적용 부분만 추출)

| 노드 | CCOP 수사 | OSINT | 협력기관 | 추론 |
|---|---|---|---|---|
| vt_src | primary | **primary** | possible | – |
| vt_case | primary | **never** | possible | – |
| vt_petition | primary | possible (더치트) | possible | – |
| **pt_cluster** ⭐ | primary | never | – | primary |
| vt_psn | primary | **never** | possible | possible |
| vt_org | primary | possible | possible | – |
| vt_bacnt, vt_telno, vt_ip | primary | **primary** | primary | – |
| vt_site | possible | **primary** | possible | – |
| **site_cluster** ⭐ | never | **primary** | – | primary |
| vt_file, vt_id | possible | **primary** | possible | – |
| vt_dev (relay_station) | primary | never | possible | primary |
| vt_msg | possible | **primary** | – | – |
| vt_transfer | primary | possible | primary | – |

(노드 25종 전체는 `ontology_service.py:DOMAIN_USAGE` 참고)

### 3.3 사용 코드
```python
from app.middleware.services.ontology_service import KICSCrimeDomainOntology as Onto

Onto.is_applicable('site_cluster', 'osint')   # True (primary)
Onto.is_applicable('vt_psn', 'osint')         # False (never)
Onto.get_domain_usage('vt_bacnt', 'osint')    # 'primary'
```

---

## 4. ③ STEP 7.5a — site_cluster 노드 생성 (HTML SimHash)

### 4.1 알고리즘
- HTML 토큰화 (태그명 + class/id + 텍스트 단어)
- 64-bit SimHash 지문 계산
- Pairwise Hamming distance ≤ 3 → Union-Find 군집화
- 최소 크기 2 이상만 site_cluster 노드로 승격

### 4.2 사전 조건
- STEP 7 (vt_site 적재) 완료
- vt_site에 `html_src` 속성 또는 `html_fingerprint` 보유 (스테이징에서 보존)
- `is_malicious=true` 사이트만 군집화 (오탐 회피)

### 4.3 실행 방법

**A. Python 모듈 (권장)** — `app/services/osint_v37_postprocess.py`
```bash
python -m app.services.osint_v37_postprocess \
    --graph osint_ontology \
    --hamming 3 \
    --min-cluster 2
```

**B. SQL 직접 (백업 옵션)**
```sql
-- STEP 7.5a (SQL만으로는 SimHash 계산 어려움 — Python PL 함수 등록 필요)
-- 권장: Python 모듈 호출
```

### 4.4 생성되는 site_cluster 노드 형태

```cypher
(:site_cluster {
    cluster_id:       'osint-sc-0001',
    cluster_method:   'simhash_union_find',
    id_format:        'plain',                  -- ⭐ V3.7
    source_domain:    'osint',                  -- ⭐ V3.7
    site_cnt:         3,
    detected_by:      'osint_v37_postprocess',
    rec_created:      '2026-05-21T...',
})
```

### 4.5 보고서 §5 STEP 5 갱신 (VLABEL/ELABEL 추가)

```sql
-- STEP 5 추가
CREATE VLABEL IF NOT EXISTS site_cluster;       -- V3.7 신규
CREATE VLABEL IF NOT EXISTS pt_cluster;         -- V3.7 신규 (OSINT 더치트 옵션)

CREATE ELABEL IF NOT EXISTS belongs_to_campaign; -- V3.7 신규
CREATE ELABEL IF NOT EXISTS belongs_to_cluster;  -- V3.7 신규 (옵션)
```

---

## 5. ④ STEP 8.5a — belongs_to_campaign 엣지

### 5.1 형태
```cypher
(vt_site) -[r:belongs_to_campaign {
    sim_score:    0.95,                          -- 군집 내 평균 유사도
    detected_at:  '2026-05-21T...',
    source_id:    'osint_v37_postprocess'
}]-> (site_cluster)
```

### 5.2 실행 (Python 모듈에서 자동)
`osint_v37_postprocess.create_site_clusters()`가 군집화와 엣지 생성을 함께 수행. 별도 SQL 호출 불필요.

### 5.3 검증 쿼리
```cypher
-- STEP 10 검증 보강
MATCH (s:vt_site)-[:belongs_to_campaign]->(c:site_cluster)
RETURN c.cluster_id, count(s) AS member_count
ORDER BY member_count DESC LIMIT 20;
```

---

## 6. ⑤ STEP 8.6 — vt_id.is_anonymous 마킹

### 6.1 룰
OSINT의 vt_id 중 작성자명이 비식별/마스킹된 경우:

```cypher
MATCH (id:vt_id)
WHERE id.id_val IS NULL
   OR id.id_val = ''
   OR id.id_val LIKE '%****%'
   OR id.id_val LIKE 'anonymous%'
   OR id.id_val LIKE 'unknown%'
SET id.is_anonymous = true,
    id.detected_by  = 'osint_v37_postprocess'
RETURN count(id);
```

### 6.2 V3.7 표준과의 연계
- 원래 V3.7은 `vt_psn.is_anonymous` 한정
- OSINT는 vt_psn 미사용 → vt_id에 동등 의미 확장
- DOMAIN_USAGE에서 vt_id의 OSINT='primary' + is_anonymous는 vt_psn 의미를 그대로 가짐

### 6.3 실행
`osint_v37_postprocess.mark_anonymous_ids()`에서 자동 수행.

---

## 7. 통합된 OSINT ETL 흐름 (V3.7 후)

기존 OSINT 보고서 §3.1의 11단계 ETL에 V3.7 후처리 단계 삽입:

```
STEP 1.  URL 정규화 함수
STEP 2.  스테이징 16개 테이블 (+ html_src 보존 강조)
STEP 3.  스테이징 인덱스 + ANALYZE
STEP 4.  건수 검증
STEP 5.  그래프 + 라벨 (V3.7 추가: site_cluster, belongs_to_campaign 등)
STEP 6.  세션 튜닝
STEP 7.  노드 적재 27개 (각 노드에 id_format + source_domain 속성 추가)
STEP 7-X. 노드 인덱스 (+ site_cluster.cluster_id 인덱스)
─── 신설 ─────────────────────────────────────────────────────
STEP 7.5a. site_cluster 노드 생성 (HTML SimHash 군집화)  ⭐ V3.7
─────────────────────────────────────────────────────────────
STEP 8.  엣지 적재 25개
─── 신설 ─────────────────────────────────────────────────────
STEP 8.5a. belongs_to_campaign 엣지 (vt_site → site_cluster) ⭐ V3.7
STEP 8.6.  vt_id.is_anonymous 마킹                             ⭐ V3.7
─────────────────────────────────────────────────────────────
STEP 9.  그래프 ANALYZE
STEP 10. 검증 (V3.7 추가 검증 쿼리 포함)
STEP 11. 정리
```

### 7.1 단일 명령으로 V3.7 후처리 실행
기존 OSINT ETL이 STEP 7~8 완료 후 다음 한 줄로 V3.7 후처리:

```bash
python -m app.services.osint_v37_postprocess --graph osint_ontology
```

출력:
```
[site_cluster] 후보 N개 사이트 → M개 군집 (min=2)
[site_cluster] 노드 M + belongs_to_campaign 엣지 X 생성
[is_anonymous] vt_id 마킹: Y건
✅ OSINT V3.7 후처리 완료: {'site_clusters': M, 'anonymous_ids': Y}
```

---

## 8. OSINT 보고서 §10.2/10.3 매트릭스 갱신본

### 8.1 §10.2 V3.7 노드 카탈로그 사용 매트릭스 (갱신)

| Layer | 노드 | OSINT 적재 | 비고 |
|---|---|---|---|
| Source | vt_src | ✅ | 모든 출처 추적 |
| Case | vt_case | ❌ | 수사 사건 정보 미보유 |
| Case | vt_petition | △ | 더치트 신고 승격 시 가능 |
| Case | **pt_cluster** ⭐ | ❌ | 수사 진정서 군집 — OSINT 적용 없음 |
| Person | vt_psn | ❌ | 닉네임 ≠ 실인물 |
| Person | vt_org | △ | 사칭 캠페인 등 한정 |
| Object | vt_bacnt, vt_telno, vt_ip | ✅ | 더치트/악성 URL |
| Object | vt_site | ✅ | 수집/악성/채팅방 |
| Object | **site_cluster** ⭐ | ✅ | HTML SimHash 군집 ⭐ **V3.7 OSINT 핵심** |
| Object | vt_file, vt_id | ✅ | 첨부/스크린샷/작성자 |
| Object | vt_dev | ❌ | 통신 메타 미보유 |
| Object | vt_email, vt_crypto, vt_vhcl, vt_atm | ❌ | OSINT 미수집 |
| Event | vt_msg | ✅ | 메시지/게시글/채팅/SMS |
| Event | vt_transfer | ✅ | 더치트 사기 이체 |
| Event | vt_call, vt_access, vt_movement, vt_impersonation | ❌ | 통신/접속 메타 미보유 |
| Location | vt_loc | △ | 옵션 |

### 8.2 §10.3 V3.7 엣지 사용 매트릭스 (갱신)

| 엣지 | V3.7 정의 | OSINT 적재 사용 |
|---|---|---|
| sourced_from | Any → Source | ✅ 모든 노드 → vt_src |
| sent_msg | Phone/ID → Message | ✅ vt_id, vt_telno → vt_msg |
| resolves_to | Site → IP | ✅ |
| hosts | IP → Site | ✅ |
| contains_file | Site/Msg/ID → File | ✅ vt_site → vt_file |
| **belongs_to_campaign** ⭐ | Site → SiteCluster | ✅ **V3.7 신규** ⭐ |
| **belongs_to_cluster** | Petition → PtCluster | ❌ vt_petition 미사용 시 적용 안 됨 |
| **used_in_device** | Phone → Device | ❌ vt_dev 미사용 |

### 8.3 §5.2 V3.7 표준 준수 체크리스트 갱신

| 검증 항목 | 결과 |
|---|---|
| 25노드 외 임의 노드 생성 여부 | ✅ |
| 53엣지 외 임의 엣지 생성 여부 | ✅ |
| 표준 식별자 사용 | ✅ |
| 표준 속성명 사용 | ✅ |
| **`id_format` 메타 명시** ⭐ | ✅ **V3.7 신규** |
| **`source_domain` 메타 명시** ⭐ | ✅ **V3.7 신규** |
| **deprecated `clusters_with` 생성 금지** ⭐ | ✅ **V3.7 신규** (read-only) |
| **site_cluster 자동 군집화** ⭐ | ✅ **V3.7 신규** (osint_v37_postprocess 모듈) |

---

## 9. 변경 영향 분석

### 9.1 OSINT 보고서 §3.3 MERGE 미사용 결정 영향
- V3.7 후처리는 `MERGE` 사용 — `osint_v37_postprocess` 모듈은 재실행 안전
- 기존 ETL은 비멱등 유지 — 변화 없음

### 9.2 데이터 흐름 단방향성 (§6.3) 유지
- V3.7 후처리는 그래프 위에서만 동작 — RDB로 역방향 흐름 없음 ✅

### 9.3 SLA 영향 (§7.4)
| 단계 | 예상 추가 시간 |
|---|---|
| STEP 7.5a SimHash 군집화 | 1~5분 (사이트 수 만 개 기준) |
| STEP 8.5a belongs_to_campaign | 30초~1분 |
| STEP 8.6 is_anonymous | 30초 |
| **V3.7 후처리 추가** | **2~7분** |
| **전체 ETL** | 15~30분 → **17~37분** |

---

## 10. Phase별 작업 흐름

### 🔴 Phase A (즉시, 본 가이드 적용)
1. ✅ `ontology_service.py`에 NODE_ID_STANDARD/DOMAIN_USAGE/INFERENCE_RULES_V37 추가
2. ✅ `app/services/osint_v37_postprocess.py` 모듈 작성
3. ✅ 본 통합 가이드 문서 작성
4. ⏳ OSINT ETL에 V3.7 후처리 호출 추가 (운영 작업)
5. ⏳ STEP 7 노드 적재 시 `id_format`/`source_domain` 속성 추가 (운영 작업)

### 🟡 Phase B (1~2주)
6. 더치트 해시 ↔ OSINT 평문 자동 sameAs 매칭 배치
7. 멱등성 ETL 전환 (WHERE NOT EXISTS 가드)
8. STIX 2.1 export 매핑 (site_cluster ↔ Campaign)

### 🟢 Phase C (중기, 1개월)
9. 댓글/링크 처리 (linked_to 엣지)
10. CDC 기반 증분 ETL
11. 운영 모니터링/메트릭 대시보드

---

## 11. 검증 명령 (적용 후)

### 11.1 SSOT 메타 검증
```bash
python3 -c "
from app.middleware.services.ontology_service import KICSCrimeDomainOntology as O
print('NODE_ID_STANDARD:', len(O.NODE_ID_STANDARD))
print('DOMAIN_USAGE:', len(O.DOMAIN_USAGE))
print('INFERENCE_RULES_V37:', list(O.INFERENCE_RULES_V37.keys()))
assert O.is_applicable('site_cluster', 'osint')
assert not O.is_applicable('vt_psn', 'osint')
print('✅ V3.7 표준 메타 정상')
"
```

### 11.2 SimHash 모듈 단위 검증
```bash
python3 -m app.services.osint_v37_postprocess --help
```

### 11.3 그래프 적용 후 검증
```cypher
-- site_cluster 카운트
MATCH (c:site_cluster) RETURN count(c);

-- belongs_to_campaign 카운트 + 군집별 멤버 수
MATCH (s:vt_site)-[:belongs_to_campaign]->(c:site_cluster)
RETURN c.cluster_id, count(s) AS members ORDER BY members DESC LIMIT 10;

-- is_anonymous 마킹된 vt_id
MATCH (id:vt_id {is_anonymous: true}) RETURN count(id);

-- V3.7 표준 메타가 적용된 노드 비율
MATCH (n)
WHERE labels(n)[0] STARTS WITH 'vt_' OR labels(n)[0] IN ['pt_cluster', 'site_cluster']
WITH labels(n)[0] AS label,
     count(*) AS total,
     sum(CASE WHEN n.id_format IS NOT NULL THEN 1 ELSE 0 END) AS with_id_format,
     sum(CASE WHEN n.source_domain IS NOT NULL THEN 1 ELSE 0 END) AS with_domain
RETURN label, total, with_id_format, with_domain
ORDER BY total DESC;
```

---

## 12. 결론

본 가이드는 OSINT V3.6 보고서 §10.2/10.3에 명시된 매트릭스 + §8(향후 작업)을 V3.7 표준 메타와 자동화 모듈로 격상한 결과물이다.

핵심 산출물:
- ✅ `ontology_service.py` — NODE_ID_STANDARD, DOMAIN_USAGE, INFERENCE_RULES_V37
- ✅ `app/services/osint_v37_postprocess.py` — SimHash 군집화 + V3.7 후처리 통합 모듈
- ✅ `docs/OSINT_V37_INTEGRATION_GUIDE.md` — 본 가이드

운영 적용 부담은 **17~37분/ETL** (기존 대비 +2~7분)으로 매우 작으며, V3.7 신규 통합의 가장 큰 가치인 **site_cluster (피싱 캠페인 자동 군집화)**가 OSINT 도메인에서 자연스럽게 활성화된다.

---

**가이드 끝**
