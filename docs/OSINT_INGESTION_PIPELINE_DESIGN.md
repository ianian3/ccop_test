# OSINT → 전처리 → CCOP 적재 파이프라인 설계

**작성일**: 2026-06-18
**범위**: 외부 OSINT raw 데이터를 3단계(수집 → 전처리 → CCOP 적재)로 처리해 KICS 온톨로지 그래프(AgensGraph)에 연결하는 구현 설계
**기반 리서치**: `docs/OSINT_SCALE_INGESTION_RESEARCH.md`

---

## 0. 설계 원칙

- **무거운 변환은 전부 STAGE 2(RDB, set-based SQL)** 에서. 그래프 적재(STAGE 3)는 "이미 정제·중복제거된 노드/엣지 테이블을 벌크 COPY"만 — **건건이 MERGE 하지 않는다.**
- 세 단계 사이는 **명시적 데이터 계약(중간 테이블)** 으로 분리 → 단계별 독립 최적화·테스트·재실행 가능.
- 모든 단계 **`canonical_id` 기준 멱등(UPSERT)** + `batch_id`/워터마크 기반 **증분(CDC)**.

---

## 1. 전체 흐름 + 데이터 계약

```
[STAGE 1 수집]            [STAGE 2 전처리]                          [STAGE 3 적재]
외부 OSINT     ──COPY──>  osint.stg_raw_*  ──set-based SQL──>  osint.node / osint.edge  ──벌크──> AgensGraph
(VT/더치트/STIX/크롤)      (랜딩, 가공 안 함)   정규화·표준화·dedup·    (그래프 준비완료:            (COPY/UNWIND)
                                              온톨로지매핑·출처레지스트리   유니크노드 + 엣지팩트)       + 추론 + sameAs + QA
                                                                    ▲ 데이터 계약(핵심)
```

---

## 2. STAGE 1 — 수집 (Land, 가공 없음)

- 외부 OSINT를 **출처·월별 파티션 staging 테이블**(`osint.stg_raw_<source>`)로 **`COPY` 벌크 적재**. 변환하지 않고 원본 그대로(ELT).
- 적재 메타만 부착: `feed_id`(출처 피드), `collected_at`(수집시점), `batch_id`(적재 배치), `raw_payload`(원본 JSON).
- 증분: `collected_at` 워터마크로 델타만 적재.
- **산출 계약**: `osint.stg_raw_*` (원본 + 수집 메타).

---

## 3. STAGE 2 — 전처리 (RDB set-based, 무거운 단계)

순서대로 **집합 연산(SQL)** 으로 처리. 행별 Python 루프 금지.

| 단계 | 처리 | 산출 |
|------|------|------|
| 2a 정규화 | canonical key 생성: 전화 E.164, 계좌 dash, URL norm, 파일 hash, IP/이메일 — `normalize_*()` **일괄 UPDATE / generated column** | 정규화 컬럼 |
| 2b 표준화 | 은행/통신사 코드 매핑(조인), `source_domain='osint'`, `reliability_tier` 부여 | 표준 속성 |
| 2c **출처 레지스트리** | 출처를 **피드 단위로 dedupe** → `osint.vt_src_registry`(수십~수백 개), 각 레코드에 `source_id` 부여 → 기존 vt_src 140만 폭증 해소 (**P0**) | `vt_src_registry` + source_id |
| 2d **엔티티 해소/dedup** | canonical key `GROUP BY` → 유니크 노드(결정적). 사이트/인물 등 퍼지는 **LSH/MinHash 블로킹**. cross-source 후보 식별 | 유니크 노드 집합 |
| 2e **온톨로지 매핑** | SSOT(`NODE_ID_STANDARD`/`DOMAIN_USAGE`) 검증 후 raw → `vt_*` 라벨/엣지로 사상 | 라벨/엣지 확정 |

### 산출 계약 — 그래프 준비완료 테이블 (설계의 핵심)
```sql
osint.node(
  label        TEXT,          -- vt_telno / vt_file / vt_msg ... (SSOT 검증됨)
  canonical_id TEXT,          -- 정규화 식별자 (UPSERT 키)
  id_format    TEXT,          -- no_hyphen_e164 / md5 / normalized_url ...
  props        JSONB,         -- 노드 속성
  source_id    TEXT,          -- vt_src_registry 참조 (엣지 대신 속성화 검토)
  reliability_tier SMALLINT,
  PRIMARY KEY(label, canonical_id)   -- 중복 제거 보장
);
osint.edge(
  edge_type   TEXT,           -- owns_phone / from_account / contains_file ...
  src_label TEXT, src_id TEXT,
  dst_label TEXT, dst_id TEXT,
  props JSONB,
  UNIQUE(edge_type, src_label, src_id, dst_label, dst_id)
);
```
→ 이 두 테이블이 만들어지면 **"수백만 raw 행"이 "유니크 노드 + 엣지 팩트"로 축소**되고, 적재는 단순해진다.

---

## 4. STAGE 3 — CCOP 적재 (벌크 → AgensGraph)

`osint.node`/`osint.edge`를 **그래프로 벌크 적재**(건건 MERGE 아님).

1. **노드 벌크**: 라벨별로 `osint.node` → AgensGraph vertex 테이블 **`COPY`** (가장 빠름). 또는 `UNWIND $rows MERGE` 1만 건 배치.
2. **인덱스**: 적재 전 보조 인덱스 drop → 적재 후 재생성. `(label, canonical_id)` **유니크 인덱스**로 idempotent UPSERT.
3. **엣지 벌크**: `osint.edge` → ELABEL **COPY/배치**. `source_id`는 속성(또는 vt_src_registry로의 sourced_from을 출처당 1엣지로 축약).
4. **추론(적재 후 배치)**: site_cluster(SimHash + **LSH 밴딩**), relay_station/anonymous(set-based SQL).
5. **cross-source sameAs**: `osint.node` ↔ investigation 그래프 노드를 canonical key 조인으로 **일괄 링크**(Phase B 자동화).
6. **QA·노출**: 노드/엣지 카운트 + 온톨로지 적합성 검증 → 앱 graph 목록에 노출(검색/확장/T2C 가능).

---

## 5. 멱등성 / 증분 / 재실행

- **멱등 키**: 모든 단계가 `canonical_id` 기준 → 재실행해도 중복 없음(UPSERT).
- **증분(CDC)**: STAGE1 워터마크 → STAGE2는 델타만 dedupe → STAGE3는 변경 노드/엣지만 UPSERT(append-merge).
- **배치 추적**: `batch_id`로 단계별 진행/롤백 추적.

---

## 6. CCOP 코드 연결점

| 단계 | 확장할 컴포넌트 |
|------|----------------|
| 2a/2b | `app/services/schema_mapper.py`(normalize_*, 코드 매핑) — set-based 버전 추가 |
| 2c | 신규 `SourceRegistryService` (출처 dedupe) |
| 2d/2e | `app/services/rdb_to_graph_service.py`(SSOT 검증) → `osint.node/edge` 빌더로 확장 |
| 3 | 신규 `BulkGraphLoader` (COPY/UNWIND 벌크) — 현재 1건 MERGE 대체 |
| 3 추론 | `app/services/relationship_inferencer.py` + LSH 모듈 |
| SSOT | `app/middleware/services/ontology_service.py`(검증 기준, 불변) |

> 참고: 활성 서비스는 `app/services/` (routes 임포트 기준). `app/middleware/services/` 는 중복본 — 온톨로지 SoT(ontology_service)만 예외.

---

## 7. 왜 이 설계인가 (리서치 매핑)

- STAGE2 dedup + STAGE3 벌크 = **적재 83h → 분** (리서치 §3)
- 2c 출처 레지스트리 = **vt_src 140만 → 수백 개** (P0)
- 2d LSH = SimHash **O(n²) 제거** (P2)
- 데이터 계약(node/edge 테이블) = 전처리/적재 **결합도 분리** → 각 단계 독립 최적화·테스트 가능

---

## 8. 구현 우선순위 (제안)

1. **P0** `osint.node/edge` 계약 테이블 + `BulkGraphLoader`(COPY) — 적재 병목 해소
2. **P0** `vt_src_registry` 정규화 — 그래프 폭증 해소
3. **P1** STAGE2 set-based 정규화/표준화 + canonical-key dedup
4. **P1** cross-source sameAs 자동화
5. **P2** LSH 밴딩 추론 + CDC 증분 + 병렬/커넥션풀

### 다음 단계 후보
- STAGE3 **BulkGraphLoader PoC** (AgensGraph COPY 벌크 적재 검증)
- STAGE2c **vt_src 레지스트리 스키마/마이그레이션 SQL**
- 10만 건 **실측 벤치마크**로 효과 정량화
