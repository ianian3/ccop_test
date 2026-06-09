# Phase 2.1 — ETL V4.0 메타 주입 갭 리포트

- **실시일**: 2026-05-21
- **검토 대상**: `app/services/etl_service.py` (활성 ETL, 856 라인)
- **참조 헬퍼**: `app/services/rdb_to_graph_service.py::make_node_props_v40` (라인 1762)
- **목적**: ETL이 V4.0 표준 6 메타 컬럼을 노드 적재 시 자동 주입하는지 확인

---

## ⚠️ 핵심 결론

> **현재 ETL은 V4.0 메타 6 컬럼 중 0/6 자동 주입.** Phase 2 진입 전 ETL 패치 필수.

| 메타 컬럼 | ETL 자동 주입 | 비고 |
|-----------|---------------|------|
| `id_format` | ❌ 0% | `make_node_props_v40` 미호출 |
| `source_domain` | ❌ 0% | OntologyEnricher 는 도메인 메타 미지원 |
| `reliability_tier` | ❌ 0% | StandardCodeMapper 미지원 |
| `source_id` | ❌ 0% | 누락 |
| `collected_at` | ❌ 0% | 누락 |
| `rec_created` | ❌ 0% | 누락 |

---

## 1. 현 ETL 노드 적재 흐름

```
[etl_service.py L346~402]
  for node_data in unique_nodes:
      node_props = node_data['props']
      dynamic_label = manual_label or GraphService.determine_node_label(...)
      ↓
      enriched_props = OntologyEnricher.enrich_node(dynamic_label, node_props)   ← (a)
      ↓
      enriched_props = StandardCodeMapper.auto_enrich(dynamic_label, enriched_props)  ← (b)
      ↓
      ★★ V4.0 메타 주입 누락 지점 ★★
      ↓
      CREATE (n:label {enriched_props})
```

- (a) `OntologyEnricher.enrich_node` — 온톨로지 속성(layer/legal_category 등) 추가
- (b) `StandardCodeMapper.auto_enrich` — 은행/통신사 코드 정규화
- **(c) V4.0 메타 6 컬럼 주입 단계 = 부재**

---

## 2. 필요 패치 위치 (3곳)

| # | 파일:라인 | 함수 | 패치 내용 |
|---|-----------|------|-----------|
| 2.1 | `app/services/etl_service.py:362` | (CSV ETL 노드 적재 루프) | `enriched_props = RdbToGraphService.make_node_props_v40(dynamic_label, enriched_props, source_domain=...)` 추가 |
| 2.2 | `app/services/etl_service.py:732` | (확장 ETL 노드 루프) | 동일 |
| 2.3 | `app/services/etl_service.py:430` | (엣지 enrich) | 엣지 V4.0 메타는 `source_domain/source_id/collected_at` 3개만. 별도 헬퍼 `make_edge_props_v40` 신설 권장 |

> `rdb_to_graph_service.py::transfer_data` 는 `_postprocess_v40_meta()` 로 후처리 보정 중 (라인 1696, 1705). 정상.

---

## 3. 권장 패치 패턴

### 3.1 노드 적재 (CSV ETL)
```python
# Before (L362)
enriched_props = StandardCodeMapper.auto_enrich(dynamic_label, enriched_props)

# After
enriched_props = StandardCodeMapper.auto_enrich(dynamic_label, enriched_props)

# V4.0 메타 주입 (Phase 2.1)
from app.services.rdb_to_graph_service import RdbToGraphService
enriched_props = RdbToGraphService.make_node_props_v40(
    dynamic_label,
    enriched_props,
    source_domain=node_data.get('source_domain', 'investigation'),
    source_id=node_data.get('source_id'),
)
```

### 3.2 ETL 입력 스펙 확장
CSV 업로드 시 `source_domain` 컬럼 옵션화 — 미지정 시 ETL 호출 컨텍스트에서 기본값 결정:
- 사용자 업로드 CSV → `'investigation'` (KICS 기본)
- OSINT 수집기 자동 호출 → `'osint'`
- 파트너 API → `'partner'` (API key tier 기반)

### 3.3 reliability_tier 자동 결정
`make_node_props_v40` 내부 `tier_map` 활용:
```python
tier_map = {'investigation': 1, 'partner': 2, 'osint': 4, 'inference': 3}
```

---

## 4. 영향도 분석

| 호출 경로 | 라우터 | 호출 메서드 | 영향 |
|-----------|--------|-------------|------|
| 사용자 CSV 업로드 | `routes_api.py:613` `/api/v1/etl/infer-import` | `ETLService.infer_import_csv` | ★ 패치 필요 |
| 확장 ETL | `routes_api.py:788` `/api/v1/etl/import-extended` | `ETLService.import_extended` | ★ 패치 필요 |
| UI ETL | `routes.py:24` | `ETLService.*` | ★ 패치 필요 |
| RDB → Graph 변환 | `routes_api.py:1217` `/api/v1/etl/transfer` | `RdbToGraphService.transfer_data` | ✅ 이미 `_postprocess_v40_meta()` 보정 |

---

## 5. 검증 시나리오 (스테이징 컨테이너에서 실행 가능)

```bash
# 패치 후 회귀 테스트
# 1. 샘플 CSV 업로드 (TB_PSN 형식)
curl -X POST :5002/api/v1/etl/infer-import -F file=@sample_psn.csv

# 2. AgensGraph에서 적재 확인
MATCH (n:vt_psn) RETURN n.id_format, n.source_domain, n.reliability_tier LIMIT 5

# 기대 결과:
# n.id_format='plain', n.source_domain='investigation', n.reliability_tier=1
```

---

## 6. 권장 우선순위 및 작업량

| 순위 | 작업 | 예상 소요 | 종속성 |
|------|------|-----------|--------|
| 🔴 1순위 | etl_service.py L362, L732 패치 (노드 V4.0 메타 주입) | 1h | 없음 (즉시 가능) |
| 🟡 2순위 | 엣지 V4.0 메타 (make_edge_props_v40 신설) | 1.5h | 1순위 후 |
| 🟢 3순위 | CSV 업로드 스펙에 `source_domain` 옵션 컬럼 추가 | 30분 | UI 수정 동반 |
| 🟢 4순위 | 회귀 테스트 (`tests/test_etl_v40_meta.py` 신설) | 1h | 1-3 완료 후 |

**총 예상 작업량**: ~4h (DA팀 회신 대기 중 충분히 완료 가능)

---

## 7. 결론 및 다음 단계

- ETL 노드 적재 경로 3곳에 V4.0 메타 주입 누락 — Phase 2 게이트(SOURCE_DOMAIN NULL = 0) 미충족 위험.
- `RdbToGraphService.make_node_props_v40` 헬퍼는 이미 구현됨 → **호출부만 연결하면 됨** (저위험 패치).
- Phase 1.2 (DA팀 회신) 대기 중 **1순위 패치 즉시 진행 가능**.

### 사용자 결정 요청
다음 중 진행 방향 선택:
- **(A)** 1순위 ETL 패치 즉시 실행 → 회귀 테스트까지 (~2h)
- **(B)** 갭 리포트만 남기고 DA팀 회신 후 일괄 패치 (안전, ~D+5)
- **(C)** 전체 4단계 일괄 진행 (~4h)
