# 온톨로지 엣지 71 건강성 검토

> **작성일**: 2026-08-10
> **대상**: CCOP 온톨로지 V4.5 엣지 71종 (60→63→66→71 증가 추세)
> **결론 한 줄**: 증가는 실데이터 근거로 **정당**하나, deprecated 위생·명명 일관성·다형화 정책이 관리 과제. **명명 rename은 학습데이터 40만+ 참조 → 재학습 필요라 비현실적**이며, 혼동은 주석·few-shot·pruning으로 관리.

---

## 1. 구성

| 구분 | 수 | 비고 |
|---|---|---|
| 전체 | 71 | |
| **활성** | **69** | `active_relationships()` (deprecated 제외) |
| deprecated | 2 | `clusters_with`→belongs_to_cluster · `owns_device`→uses_device |
| 추론 | 7 | sameAs·transferred_to·accomplice_of 등 (정상) |
| Any(범용) | 10 | linked_to·performed_by·located_at 등 |

**유사군**: `owns_*`(5) · `eg_used_*`(5) · `linked_*`(3) · `mentions_*`(3) · `belongs_*`(3) · `uses_*`(3) · `used_*`(3) · `accessed_*`(2)

## 2. 증가 정당성 — 근거 있음

60→71 증가는 전부 **실데이터 검증 갭**(V4.3→4.5, HANDOFF G1~R8)에서 도출. 근거 없는 팽창이 아니라 "실제로 표현 못 하던 것"을 메운 것. 추론/Any 비율도 정상 → **엣지 수 자체는 아직 건강**.

## 3. 검토 지적 3건

### ① deprecated 카운트 혼입 — ✅ 해소 (커밋 37f6bed)
- `active_relationships()` 헬퍼(활성 69만 반환) + 대체재 명시(replaced_by/alias_of) + docstring 정확화.
- 실제 제거는 하위호환(기존 그래프 참조) 위해 보류 — 레거시 조회용 유지.

### ② 명명 일관성 — rename 비현실적, 혼동 관리로 전환
**문제**: `used_*` 접두 우연일치(의미 상이: IP사용/사칭수단/유심-기기) → sLLM 혼동 위험. 소유가 두 접두사(owns_ vs has_account).

**영향 범위 조사 (rename 시)**:
| 엣지 | app | **학습데이터(data/)** |
|---|---|---|
| `used_for` | 21 | **59,819** |
| `used_ip` | 20 | **346,508** |
| `used_in_device` | 16 | **49,273** |
| `has_account` | 59 | **405,091** |

→ **학습데이터에 수십만 참조**. rename = 학습데이터 40만+ 치환 + **sLLM 재학습 필수** + 전 파이프라인 치환. 재학습 리스크(v45 실패 전례) 감안 시 **비용 ≫ 이득**.

**판정**: **rename 하지 말 것.** 대신:
- 온톨로지에 `used_*` 의미 구분 **주석** (저리스크)
- **schema pruning + few-shot** 방어 (기존 구축) — used_* 혼동 케이스 few-shot 보강
- **신규 엣지만** 일관 명명 규칙 적용 (기존 유지)

### ③ 다형화 정책 미확정 — 신규 게이트
`eg_used_*`(5)·`owns_*`(4)·`uses_*`(3)이 "대상별 엣지" 방식. Text2Cypher 명확성엔 유리하나 정책 없으면 대상 추가 시마다 증가. **기존 통합은 재학습이라 불가**, 신규만 정책 적용.

## 4. 권장 결론

- **엣지 71(활성 69)은 유지** — 증가가 근거 있고 관리 가능.
- **rename 금지** — 학습데이터 대량 참조 + 재학습 리스크. 기존 명명 동결.
- **혼동 관리** — 주석 + schema pruning + few-shot (기존 인프라 활용).
- **신규 엣지 게이트** — ①실데이터 근거 ②기존 재사용 불가 확인 ③일관 명명 후에만 추가.
- Text2Cypher 부담은 schema pruning으로 완화됨(질문별 관련 엣지만 주입).

## 부록 — 근거
- 구성: `ontology_service.py` RELATIONSHIPS(71) · `active_relationships()`(69)
- 영향범위: grep(app/data/scripts/tests) — 학습데이터 참조 수십만
- 관련: `docs/PROVENANCE_NORMALIZATION_DESIGN_20260804.md`, HANDOFF(ccop-analysis)
