# Provenance 정규화 전환 설계 (CCOP inline → 표준 SRC_ID FK)

> **작성일**: 2026-08-04
> **배경**: 표준 DDL 정합 검토(`STANDARD_DDL_ALIGNMENT_REVIEW_20260804.md` §3)에서 드러난 provenance 구조 차이(P1) 해소 설계.
> **범위**: 설계만(코드 변경 없음). 실 전환은 P0 명명 마이그레이션과 함께 계획.

---

## 0. 문제 요약

| | CCOP 적재/온톨로지 | 표준 DDL |
|---|---|---|
| 구조 | **inline 비정규화** (노드에 직접) | **SRC_ID FK + 마스터 정규화** |
| 컬럼 | `source_domain`·`source_id`·`reliability_tier`·`collected_at` | `SRC_ID` → `TB_DATA_SOU_A`(`SRC_TYP_CD`·`CFRT_GRD_CD`·`CLCT_DT`) |
| 적용 | 전 테이블 균일(`v40_meta_patch.sql`) | 30 FK-only / 17 inline / 4 없음 (비일관) |

## 1. 핵심 통찰 — `source_domain`과 `SRC_TYP_CD`는 **직교 축** (단순 리네임 불가)

이게 설계의 핵심이다. 두 값은 다른 질문에 답한다:

- **CCOP `source_domain` = 처리 계보** (*누가 이 데이터를 파이프라인에 넣었나*): `investigation`(수사팀 ETL) / `osint`(OSINT 수집) / `partner`(외부기관) / `inference`(추론 생성). `_postprocess_v40_meta`가 ETL 종류에 따라 주입.
- **표준 `SRC_TYP_CD` = 출처 시스템** (*어느 원천 시스템의 자료인가*): KICS / OSINT / 디지털증거 등 (실제 코드값은 `TB_COM_C` 공통코드에서 확정 필요).

→ 둘은 **겹치지만 같지 않다**. 예: 수사팀(investigation 계보)이 KICS 시스템(KICS 출처) 자료를 넣을 수도, 파트너 자료를 넣을 수도 있다. 전환 시 **둘 다 보존**해야 정보 손실이 없다.

## 2. 척도 매핑 — `reliability_tier`(1~4) ↔ `CFRT_GRD_CD`(1~5)

| CCOP tier | 계보 | 표준 CFRT_GRD_CD(1~5, 낮을수록 신뢰↑, default 3) |
|---|---|---|
| 1 | investigation(공식 수사) | 1 (최고) |
| 2 | partner(외부기관) | 2 |
| 3 | inference(추론) | 3~4 |
| 4 | osint(미확인 공개출처) | 4~5 |

- 방향 동일(1=최고신뢰). 척도만 4단계 vs 5단계.
- **리매핑 함수** 필요: `tier_from_grade(CFRT_GRD_CD 1~5) → reliability_tier 1~4` (5→4 압축) 및 역함수.
- 주의: 현재 적재는 `reliability_tier`를 코드에 **하드코딩 `1`**(`rdb_service.py:111,124,135`)로 고정 삽입 → 표준 등급 다양성을 못 살림. 전환 시 TB_DATA_SOU_A의 실제 CFRT_GRD_CD를 읽어야.

## 3. 전환 아키텍처 — 하이브리드(정규화 + 계보 inline)

정규화(표준 준수)와 계보(그래프 분석 친화)를 **둘 다** 취한다:

```
[RDB]  TB_*_M.SRC_ID  ──FK──▶  TB_DATA_SOU_A (SRC_TYP_CD, CFRT_GRD_CD, CLCT_DT, SRC_NM)
                                     │  적재 SELECT 시 JOIN
                                     ▼
[그래프]  (vt_xxx 노드)
           ├ inline: source_domain (계보, 파이프라인 주입 유지)
           ├ inline: reliability_tier (CFRT_GRD_CD → 리매핑)
           ├ inline: source_id (= SRC_ID)
           └─[sourced_from]─▶ (vt_src 노드 = TB_DATA_SOU_A 1행)
                                 ├ src_type (= SRC_TYP_CD, 출처 시스템)
                                 ├ src_name (= SRC_NM)
                                 └ reliability_tier (= CFRT_GRD_CD 리매핑)
```

**핵심 결정**:
1. **`TB_DATA_SOU_A` → `vt_src` 노드로 정규화 적재** (온톨로지에 vt_src·`sourced_from` 엣지 이미 존재).
2. 각 엔티티 노드는 `SRC_ID`로 `sourced_from` 엣지를 vt_src에 연결(정규화 준수).
3. 동시에 노드 inline `source_domain`(계보)·`reliability_tier`는 **유지** — 그래프 필터·클러스터링·엣지 신뢰도가 이미 이 inline을 참조(`rdb_to_graph:484,489`)하므로 JOIN 없이 빠른 접근 보장.
4. `SRC_TYP_CD`(시스템)는 vt_src 노드 속성으로만(계보 source_domain과 구분).

→ **정보 무손실**: 계보(source_domain)와 시스템(src_type) 둘 다 보존, 표준 FK 구조도 vt_src 정규화로 충족.

## 4. 코드 변경 지점 (전환 시)

| 파일 | 변경 |
|---|---|
| `rdb_service.py` | INSERT 시 `SRC_ID`를 실제 `TB_DATA_SOU_A` 참조로(현재 하드코딩 tier=1 제거), source_id 길이 64→200 |
| `rdb_to_graph_service.py` | 각 엔티티 SELECT에 `JOIN TB_DATA_SOU_A ON SRC_ID` 추가, `make_node_props_v40`에 `reliability_tier ← tier_from_grade(CFRT_GRD_CD)` |
| `scripts/v40_meta_patch.sql` | inline 컬럼 유지(하이브리드), source_id VARCHAR(64→200) |
| 신규 유틸 | `tier_from_grade`/`grade_from_tier` 리매핑 + `SRC_TYP_CD→source_domain` 힌트 매핑(확인 후) |
| 온톨로지 | vt_src `NODE_ID_STANDARD`에 src_type 필드 명시 |

## 5. 단계적 로드맵

1. **[확인]** `TB_COM_C`에서 `SRC_TYP_CD` 실제 코드값 확정 + `CFRT_GRD_CD` 등급 정의 (DA팀). → 값어휘 매핑표 완성.
2. **[유틸]** `tier_from_grade`/역함수 + 값어휘 매핑 상수(온톨로지 SoT에 `PROVENANCE_MAP`).
3. **[적재]** `TB_DATA_SOU_A` → vt_src 노드 적재 + `sourced_from` 엣지 (P0 명명 마이그레이션과 동시).
4. **[JOIN]** 엔티티 SELECT에 TB_DATA_SOU_A JOIN, tier 리매핑 적용.
5. **[검증]** vt_src 커버리지(고아 SRC_ID 0), tier 분포가 하드코딩 1에서 실제 등급으로 다양화됐는지.

## 6. 리스크

| 리스크 | 완화 |
|---|---|
| 계보(source_domain)와 시스템(SRC_TYP_CD) 혼동으로 정보 손실 | §1 직교 축 원칙 — 둘 다 별도 필드 보존 |
| FK 미강제(표준 SRC_ID→TB_DATA_SOU_A DB제약 0건) → 고아 SRC_ID | 적재 시 애플리케이션 검증 + vt_src 커버리지 테스트 |
| tier 5→4 리매핑 경계값 애매(3~4) | DA팀 등급 정의 확정 후 매핑표 고정 |
| JOIN 추가로 적재 성능 저하 | vt_src 선적재 + 인덱스(SRC_ID) |
| 하드코딩 tier=1 잔존 | 전환 시 전량 제거, 테스트로 하드코딩 금지 |

---

## 부록 — 근거
- CCOP 값어휘·척도: `rdb_to_graph_service.py:1888`(`tier_map`), `_postprocess_v40_meta:1870`
- inline 패치: `scripts/v40_meta_patch.sql`
- 표준 provenance: `TB_DATA_SOU_A`(DDL L26), 30 FK-only/17 inline (검토 §3)
- 온톨로지 vt_src·sourced_from: `ontology_service.py`
