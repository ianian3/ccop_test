# CCOP V4.0 온톨로지 종합 점검 리포트

- **점검일**: 2026-05-21
- **범위**: 5개 영역 (수량 정합성 / 5계층 매핑 / V3.7 반영 / 도메인 매트릭스 / 추론룰)
- **방법**: 정적 검토(Explore 에이전트) + 동적 시뮬레이션(`make_node_props_v40`, 5종 API 실측)
- **결론**: 🔴 **치명적 결함 1건 (도메인 키 명명 분기)** + ⚠️ 경고 2건

---

## ⚡ 핵심 발견 (Executive Summary)

| 영역 | 판정 | 즉시 조치 필요 |
|------|------|----------------|
| 1. 노드/엣지 수량 | ✅ OK | - |
| 2. 5계층 SSOT | ✅ OK | - |
| 3. V3.7 신규 반영 | ✅ OK | - |
| 4. **도메인 명명 분기** | 🔴 **치명** | **24h 내 통일** |
| 5. 추론룰 4종 무결성 | ⚠️ 경고 | AnonymousFlag 스키마 정정 |
| 6. NODE_ID_STANDARD 부분 정의 | ⚠️ 경고 | 16개 노드 추가 |

---

## 1. ✅ 노드/엣지 수량 정합성 (PASS)

| 컬렉션 | 카운트 | V4.0 사양 |
|--------|--------|-----------|
| `VISUAL_STYLE_V40` | **25** | 25 ✅ |
| `EDGE_STYLE_V40` | **55** | 55 ✅ |
| `DOMAIN_USAGE` | **25** | 25 ✅ |
| `ENTITIES` | **25** | 25 ✅ |
| `LAYOUT_PRESETS_V40` | **5** | 5 ✅ |
| `INVESTIGATION_WORKFLOWS_V40` | **6** | 6 ✅ |
| `INFERENCE_RULES_V37` | **4** | 4 ✅ |
| 시각화 기본색 미정의 | **0**/25 | 0 ✅ |
| 아이콘 정의 | **25**/25 | 25 ✅ |

---

## 2. ✅ 5계층 SSOT 무결성 (PASS)

`ontology_service.py` ↔ `CCOP_ONTOLOGY_V4.0.md` ↔ `V40_RDB_SCHEMA_STANDARD.md` ↔ `V40_RDB_TO_GRAPH_MAPPING.md` ↔ `V40_VISUALIZATION_STANDARD.md` 5개 SSOT 노드 명칭/카운트 일치.

---

## 3. ✅ V3.7 신규 7요소 반영도 (PASS)

| V3.7 신규 | VISUAL | NODE_ID | DOMAIN | ENTITY | EDGE_STYLE |
|-----------|--------|---------|--------|--------|------------|
| `pt_cluster` | ✅ | ✅ | ✅ | ✅ | - |
| `site_cluster` | ✅ | ✅ | ✅ | ✅ | - |
| `vt_psn.is_anonymous` | - | - | - | (속성) | - |
| `vt_dev.dev_type='relay_station'` | - | - | - | (속성) | - |
| `belongs_to_cluster` | - | - | - | - | ✅ |
| `belongs_to_campaign` | - | - | - | - | ✅ |
| `used_in_device` | - | - | - | - | ✅ |

---

## 4. 🔴 [치명] 도메인 키 명명 4중 분기

서로 다른 4개 SSOT가 동일 개념을 다른 키로 사용 — **데이터 흐름 단절 실증**.

### 4.1 발견된 4중 분기

| SSOT 위치 | 도메인 키 집합 |
|-----------|----------------|
| `ontology_service.py::DOMAIN_USAGE` | `investigation, osint, partner, inference` |
| `rdb_to_graph_service.py::make_node_props_v40::tier_map` | `investigation, osint, partner, inference` |
| `da_v37_v40_patch.sql::TB_CMN_CD.DOMAIN` | **`KICS, OSINT, DIGITAL, EXT`** |
| `docs/CCOP_ONTOLOGY_V4.0.md` (본문) | **`KICS, OSINT, DIGITAL, EXT`** |

### 4.2 실증: 시뮬레이션 결과

```python
# RDB SOURCE_DOMAIN='KICS' (DA팀 표준) → make_node_props_v40 호출
props = RdbToGraphService.make_node_props_v40(
    'vt_telno', {'telno':'010-1234-5678'},
    source_domain='KICS', source_id='tccop_kics_001'
)
# 결과: reliability_tier = 3  ← ❌ (기대값 1, fallback 발생)

# vs.
props = RdbToGraphService.make_node_props_v40(
    'vt_telno', {'telno':'010-1234-5678'},
    source_domain='investigation'
)
# 결과: reliability_tier = 1  ← ✅
```

**파급**: RDB에 `SOURCE_DOMAIN='KICS'` 로 적재된 모든 데이터가 그래프 변환 시 `reliability_tier=3` 으로 잘못 매핑됨. KICS 공식 데이터(tier 1)가 시민제보 수준(tier 3)으로 강등.

### 4.3 권장 조치 — 24h 내 통일

**옵션 A** (추천): 코드 ↔ RDB 매핑 테이블 도입
```python
RDB_TO_CODE_DOMAIN = {
    'KICS':    'investigation',
    'OSINT':   'osint',
    'DIGITAL': 'partner',      # 또는 별도 'digital' 신설
    'EXT':     'partner',
}
```

**옵션 B**: 전면 통일 (DA팀과 협의 — Phase 1.2 회신과 묶기)
- 양쪽 모두 `KICS/OSINT/DIGITAL/EXT` 4종으로 변경
- 또는 양쪽 모두 `investigation/osint/partner/inference` 4종으로 변경

> Phase 1.2 DA팀 회신 시 함께 협의 필요. **D+2 이전 결정 권장**.

---

## 5. ⚠️ AnonymousFlagDetection 추론룰 스키마 불일치

다른 3개 룰과 키 구조가 다름.

| 룰 | 보유 키 |
|----|---------|
| SiteClusterDetection | description, input_nodes, input_attributes, algorithm, output_nodes, **output_edges**, min_cluster_size, applicable_domains, frequency |
| PtClusterDetection | description, input_nodes, input_attributes, algorithm, output_nodes, **output_edges**, applicable_domains, frequency |
| RelayStationDetection | description, input_nodes, input_attributes, algorithm, output_nodes, output_attributes, **output_edges**, applicable_domains, frequency |
| **AnonymousFlagDetection** | description, input_nodes, algorithm, output_attributes, applicable_domains ❌ |

**누락**: `input_attributes`, `output_nodes`, `output_edges`, `frequency`

**권장**:
```python
'AnonymousFlagDetection': {
    'description': '익명 사용자 식별 (닉네임 only, 본명 없음)',
    'input_nodes': ['vt_psn', 'vt_id'],
    'input_attributes': ['nickname', 'real_name'],
    'algorithm': 'real_name IS NULL AND nickname IS NOT NULL',
    'output_nodes': [],           # 신규 노드 생성 없음 (속성 플래그만)
    'output_attributes': {'vt_psn.is_anonymous': True, 'vt_id.is_anonymous': True},
    'output_edges': [],           # 신규 엣지 없음
    'applicable_domains': ['osint', 'investigation'],
    'frequency': 'on_ingest',
}
```

---

## 6. ⚠️ NODE_ID_STANDARD 부분 정의 (9/25)

`NODE_ID_STANDARD` 가 25 노드 중 9개만 정의:
```
정의됨 (9): pt_cluster, site_cluster, vt_bacnt, vt_file, vt_id,
            vt_ip, vt_psn, vt_site, vt_telno
누락 (16): vt_access, vt_atm, vt_call, vt_case, vt_crypto, vt_dev,
            vt_email, vt_impersonation, vt_loc, vt_movement, vt_msg,
            vt_org, vt_petition, vt_src, vt_transfer, vt_vhcl
```

`make_node_props_v40` 가 `id_format` 기본값을 `'plain'`으로 폴백하므로 적재 실패는 없으나, V4.0 사양 "전 노드 id_format 의무" 충족 불가.

**권장**: 16개 노드의 id_format 추가 (대부분 `plain` 또는 `uuid` 일괄 지정 가능).

---

## 7. 동적 시뮬레이션 결과 — 정상 항목

| 시뮬 | 결과 |
|------|------|
| 추론룰 출력 엣지 ⊂ EDGE_STYLE_V40 | ✅ 누락 0 (3/3 모두 정의됨) |
| 워크플로 6종 스키마 일관성 | ✅ start/hops/description 공통 |
| visual-style API 5종 응답 | ✅ 200 OK (`/visual-style`, `/edge-style`, `/layout-presets`, `/workflows`, `/ontology/meta`) |
| 노드 25개 색상/아이콘 완비 | ✅ 25/25, 25/25 |

---

## 8. 우선순위별 조치 계획

| 우선 | 작업 | 영향 | 예상 소요 | 종속 |
|------|------|------|-----------|------|
| 🔴 P0 | 도메인 키 명명 통일 (옵션 A 매핑 테이블 도입) | 데이터 신뢰도 등급 전체 영향 | 30분 | DA 회신 |
| 🟡 P1 | `AnonymousFlagDetection` 스키마 정정 | 추론룰 일관성 | 15분 | 없음 |
| 🟡 P2 | `NODE_ID_STANDARD` 16노드 추가 | V4.0 사양 충족률 9/25 → 25/25 | 1h | 없음 |
| 🟢 P3 | 변경 후 회귀: V40 시뮬레이션 + API 재실행 | 검증 | 30분 | P0-P2 |

---

## 9. 권장 다음 행동

DA팀 회신 대기 중 다음 작업이 안전하게 가능:

- **(A)** 🔴 P0 도메인 키 매핑 즉시 패치 (옵션 A) — RDB 적재 시 tier 매핑 오류 차단
- **(B)** 🟡 P1+P2 일괄 (AnonymousFlag + NODE_ID 16개 보강) — V4.0 사양 충족률 100%
- **(C)** P0+P1+P2 통합 패치 + 회귀 (~2h) ⭐ 추천

본 검토 결과 **V4.0 설계 자체는 견고**하나 **도메인 명명 일관성 1건이 데이터 신뢰도 매핑을 망가뜨림**. P0 즉시 패치 권장.
