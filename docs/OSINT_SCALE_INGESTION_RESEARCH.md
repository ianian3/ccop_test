# 수백만건 OSINT RAW → KICS 온톨로지 적재 리서치

**작성일**: 2026-06-17
**범위**: 외부 수백만건 OSINT raw 데이터의 적재·처리·온톨로지 연결 — 현황 분석 + production 설계
**근거**: CCOP 코드/문서 분석 + 실제 `osint_ontology` 그래프(노드 ~6.89M / 엣지 ~10.94M, tccopdb) 구조 계측

---

## 0. 요약 (TL;DR)

- 이미 `osint_ontology` 그래프에 **~689만 노드가 적재**돼 있다. 분포상 **vt_file 3.56M / vt_msg 1.49M / vt_src 1.40M**, sourced_from 엣지 5.89M.
- 파이프라인 **아키텍처(SSOT 메타·도메인격리·신뢰도계층)는 견고**하나, **적재 구현이 샘플 규모(1K건, 1건씩 MERGE)** 라 수백만건 production은 미검증.
- 가장 큰 구조 문제: **vt_src 미정규화(140만 출처노드, 레코드마다 생성)** → 그래프 폭증.
- 핵심 권고: **"정규화·중복제거·엔티티해소를 RDB(set-based)에서 끝내고, 그래프엔 벌크(COPY/배치 UNWIND)로 한 번에 적재"** + **vt_src 레지스트리 정규화**.

---

## 1. 현황 분석

### 1.1 실측 — osint_ontology 라벨별 행수 (pg_class.reltuples 추정)
| 라벨 | 추정 행수 | 해석 |
|------|----------:|------|
| sourced_from | ~5,887,532 | 출처 엣지(모든 노드 → vt_src) |
| contains_file | ~3,864,486 | 파일 포함 엣지 |
| **vt_file** | **~3,560,620** | 첨부/크롤 파일 (최다 노드) |
| **vt_msg** | **~1,491,557** | 메시지/게시글 |
| **vt_src** | **~1,395,015** | 출처 노드 ⚠️ (레코드마다 생성 = 미정규화) |
| sent_msg | ~1,162,238 | 발신 엣지 |
| vt_transfer | ~179,750 | 이체 |
| vt_bacnt / vt_site / vt_id / vt_telno | 74,678 / 74,646 / 73,313 / 52,423 | 계좌/사이트/ID/전화 |
| hosts / resolves_to | 13,769 / 13,769 | 인프라 엣지 |
| vt_ip | ~2,873 | IP |

→ **이미 수백만 규모로 적재된 실적이 있으나**, 아래 1.3처럼 적재 코드는 샘플 수준이다.

### 1.2 파이프라인 단계 (L1→L5)
```
L1 수집   VirusTotal/AbuseIPDB/Shodan/더치트/ETRI STIX → JSON·CSV (월별 파티션 로그)
L2 RDB    표준 10개 테이블 + V4.0 메타 의무화
          (source_id, source_domain, reliability_tier, collected_at, rec_created/updated)
          + 정규화 컬럼(url_norm, telno_norm, account_hash) + normalize_*() 6종
L3 매핑   NODE_ID_STANDARD / DOMAIN_USAGE (SSOT) 검증 → vt_* 라벨/엣지, id_format 전환
L4 적재   AgensGraph: 1건씩 MERGE/CREATE + sourced_from 엣지        ← 병목
L5 추론   SimHash site_cluster, pt_cluster, relay_station, anonymous
```
근거: `docs/10_INTERNET_COLLECTION_DB_DESIGN.md`, `docs/V40_RDB_TO_GRAPH_MAPPING.md`, `docs/OSINT_V37_INTEGRATION_GUIDE.md`, `app/services/{osint_v37_postprocess,rdb_to_graph_service,schema_mapper,relationship_inferencer}.py`, `app/middleware/services/ontology_service.py`(NODE_ID_STANDARD/DOMAIN_USAGE/INFERENCE_RULES), `scripts/build_osint_v40_graph.py`.

### 1.3 강점 / 약점
**강점**
- V4.0 **SSOT 메타 의무화**(NODE_ID_STANDARD/DOMAIN_USAGE) — 라벨/도메인 적용성 검증
- **도메인 격리 스키마**(investigation/osint/partner/inference) + **신뢰도 계층**(evid_grade A/B/C, reliability_tier 1~4)
- **id_format 기반 cross-source sameAs** 설계(plain_dash ↔ md5) + normalize_*() 6종
- 추론 카탈로그(INFERENCE_RULES) + V3.7 군집(site_cluster/pt_cluster)

**약점 (대용량 관점)**
| # | 약점 | 영향 |
|---|------|------|
| 1 | **1건씩 MERGE/CREATE** (배치/COPY 없음) | 적재 O(n) 트랜잭션 → 수백만건 비현실적 |
| 2 | **vt_src 미정규화(140만)** | 노드/엣지 폭증, 적재·조회 저하 |
| 3 | **sameAs 자동화 미구현** (id_format 이론만) | cross-source 통합 미완 |
| 4 | **SimHash O(n²)** pairwise | 만+ 사이트에서 병목 |
| 5 | 행별 Python 정규화 | set-based 미활용 |
| 6 | 병렬/커넥션풀/벌크 UPSERT 부재 | 처리량 한계 |
| 7 | MERGE vs CREATE 정책 불일치(멱등성) | 재실행 안전성 모호 |

---

## 2. 권장 아키텍처 — "RDB에서 끝내고 그래프엔 벌크로"

**원칙: 그래프(AgensGraph)에서 건건이 MERGE하지 않는다.** 정규화·중복제거·엔티티해소를 RDB의 **set-based SQL**로 완료해 *유니크 노드 + 엣지 팩트* 로 만든 뒤 **벌크 적재**한다.

```
RAW → [Land] → [Normalize] → [Resolve/Dedup] → [Build node/edge sets] → [BULK load] → [Infer] → [Index]
       벌크적재   set-based      blocking+LSH        RDB dim/fact 테이블      COPY/UNWIND   배치    적재후
```

### 2.1 Land (적재)
- raw → **파티션 staging 테이블**(출처·월별)로 `COPY`. 건당 INSERT 금지.
- 증분: `collected_at` 워터마크 기반 델타만(CDC).

### 2.2 Normalize (정규화/표준화) — set-based
- `normalize_telno/account/url/md5/ipv4/email` 을 **bulk UPDATE 또는 generated column**로 staging 전체에 일괄 적용. (행별 Python 루프 금지 — 현재 방식의 핵심 병목)
- 은행/통신사 코드(BANK_CODES/CARRIER_CODES) 매핑도 조인 기반 일괄.

### 2.3 Resolve / Dedup (엔티티 해소) — 그래프 적재 *전* RDB에서
"수백만 raw 행" → "유니크 노드 + 엣지"로 축소하는 가장 중요한 단계.
- **결정적(exact)**: canonical key(telno E.164, account dash, url norm, file hash)로 `GROUP BY` → 유니크 노드. (중복 해시 vt_file 대량 축소 기대)
- **퍼지(fuzzy)**: 사이트/인물 등은 **LSH/MinHash 블로킹**으로 후보만 비교(O(n²)→근사 O(n)). SimHash는 **밴딩(band buckets)** 으로 같은 버킷만 비교.
- 산출물: **node-dimension 테이블(유니크 노드) + edge-fact 테이블**. cross-source `sameAs`도 canonical key 조인으로 **일괄 생성**(Phase B 자동화).

### 2.4 vt_src 정규화 (P0 즉효)
- 현재 140만 출처노드 = 레코드마다 생성. → **출처 레지스트리**(피드/기관 단위 수십~수백개)로 정규화하고, 노드는 `source_id` **속성**으로 참조.
- 효과: vt_src 140만 → 수백개, sourced_from 590만 엣지 대폭 감소(또는 속성화 검토). **그래프 크기·적재시간 최대 절감 포인트.**

### 2.5 Bulk Load (적재) — AgensGraph
- **1순위 `COPY`**: 라벨별 vertex 테이블(`"graph"."vt_file"` 등)에 정제 노드를 COPY (초~분, 수백만건).
- **2순위 배치 `UNWIND $rows AS r MERGE ...`**: 1만건 단위 파라미터 배치 + canonical key **유니크 인덱스 1개**로 idempotent UPSERT.
- **적재 중 보조 인덱스 drop → 적재 후 재생성**, `maintenance_work_mem`/`work_mem` 상향, autocommit off + 배치 커밋.
- 커넥션 풀 + 파티션별 **병렬 워커**.
- **멱등성 정책 통일**: canonical key 기준 UPSERT(MERGE/ON CONFLICT)로 재실행 안전 명문화.

### 2.6 Infer (추론) at scale — 적재 후 배치
- site_cluster/pt_cluster: SimHash + **LSH 밴딩**(pairwise 제거).
- relay/anonymous: `GROUP BY imei` / `WHERE name ~ '%***%'` 등 **set-based SQL** 배치.

### 2.7 Index / Partition
- canonical key 유니크 인덱스(UPSERT) + 조회 인덱스. 대용량 라벨(vt_file/vt_msg)은 시간/출처 파티션 검토.

---

## 3. 성능 분석
| 방식 | 100만건 추정 | 비고 |
|------|------------:|------|
| 현행 1건씩 MERGE | **~83시간** | 1K=수분 선형추정(비현실적) |
| RDB 사전 dedup + COPY 벌크 | **분~저시간** | 인덱스 drop/rebuild·병렬 가정 |

---

## 4. 개선 우선순위
| 순위 | 작업 | 효과 |
|------|------|------|
| **P0** | vt_src 레지스트리 정규화 | 노드/엣지 수백만↓, 즉효 |
| **P0** | 그래프 적재 COPY/배치 UNWIND 전환 | 적재 83h→분 |
| **P1** | RDB set-based 정규화 + canonical-key dedup | 처리량·중복 해소 |
| **P1** | sameAs cross-source 자동화(canonical join) | 통합 품질 |
| **P2** | LSH 밴딩으로 SimHash/퍼지매칭 | O(n²) 제거 |
| **P2** | CDC 증분 ETL + 병렬/커넥션풀 | 운영 지속성 |

---

## 5. 다음 단계 후보
- AgensGraph **COPY 벌크 적재 PoC** (라벨별 vertex 테이블 직접 COPY 검증)
- **vt_src 레지스트리 정규화 마이그레이션** 설계 (기존 140만 → 레지스트리 + source_id 속성)
- **실측 벤치마크**: 현 파이프라인 10만건 적재로 병목 계측 후 위 설계 효과 정량화

---

### 부록 — 참조 위치
- 메타/SSOT: `app/middleware/services/ontology_service.py` (NODE_ID_STANDARD, DOMAIN_USAGE, INFERENCE_RULES)
- 변환/매핑: `app/services/{rdb_to_graph_service,schema_mapper}.py`
- 후처리/추론: `app/services/{osint_v37_postprocess,relationship_inferencer}.py`
- 적재 스크립트: `scripts/build_osint_v40_graph.py`, `scripts/build_v40_standard_pipeline.py`
- 설계 문서: `docs/10_INTERNET_COLLECTION_DB_DESIGN.md`, `docs/V40_RDB_TO_GRAPH_MAPPING.md`, `docs/OSINT_V37_INTEGRATION_GUIDE.md`, `docs/V40_RDB_SCHEMA_STANDARD.md`
