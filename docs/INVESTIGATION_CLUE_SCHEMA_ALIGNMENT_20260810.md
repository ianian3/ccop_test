# 수사단서 연관관계 스키마 — CCOP 온톨로지 정합 검토 및 개선안

> **작성일**: 2026-08-10
> **대상**: `수사단서 연관관계분석 스키마_20260810.pptx` (1슬라이드 · 개인·법인·사건 3중심 엔티티-속성 스키마)
> **대조 기준**: CCOP v4.6 온톨로지 (`app/middleware/services/ontology_service.py` — 25노드 / 71엣지, `NODE_ID_STANDARD`)
> **결론 한 줄**: 원본은 CCOP와 **충돌 없이 100% 매핑되는 견고한 수사 스키마**. ERD(속성 집약) → 그래프(엣지)로의 5개 정합 개선을 적용하면 개인정보 안전성·공유 탐지력·법정 증거력이 강화되며, **신규 노드·엣지 0**이라 sLLM 재학습이 불필요하다.
> **시각화**: claude.ai/code/artifact/04caff69 (개선안) · 529476d6 (온톨로지 역할·수사활용)

---

## 1. 개요

원본 PPTX는 수사 실무 관점의 **엔티티-속성 스키마**다. 세 중심 엔티티(개인·법인·사건)에 식별자([대괄호]=키)와 속성을 붙이고, 사건이 여러 객체(전화·계좌·IP·이메일 등)를 연결하는 구조.

CCOP v4.6 온톨로지와 대조한 결과, **엔티티 커버리지는 완전 정합**이며 차이는 "모델링 패러다임"(ERD vs 그래프)에 있다. 이 문서는 매핑·차이·개선안을 정리한다.

## 2. 엔티티 매핑 — 11종 전부 CCOP에 존재

| PPTX 엔티티 | 식별자 | CCOP 노드 | CCOP PK | 정합 |
|---|---|---|---|---|
| 개인 | 주민번호 | `vt_psn` | `psn_id` (+ `rrno_hash`) | ⚠ PK 방식 |
| 법인 | 사업자번호 | `vt_org` | `org_id` (+ `brno`) | ⚠ PK 방식 |
| 사건 | 사건번호(접수번호) | `vt_case` | `flnm`/`incdnt_no` | ✅ |
| 전화 | 전화번호 | `vt_telno` | `telno` | ✅ |
| 계좌 | 계좌번호 | `vt_bacnt` | `account_no` | ✅ |
| 가상자산지갑 | 지갑주소 | `vt_crypto` | `wallet_addr` | ✅ |
| 범죄 IP | — | `vt_ip` | `ip_addr` | ✅ |
| 이메일 | — | `vt_email` | `email_addr` | ✅ |
| 사이트 URL | — | `vt_site` | `url_addr` | ✅ |
| 주소 | — | `vt_loc` | `loc_id` | ✅ |
| SNS ID / 닉네임 | — | `vt_id` | `(platform, id_val)` | ⚠ 통합/분리 |

**누락 없음.** CCOP가 오히려 상위집합(이벤트 노드 `vt_transfer`·`vt_call`·`vt_access`·`vt_msg`, `vt_file`·`vt_dev`·`vt_atm`·`vt_vhcl`, provenance `vt_src` 추가).

## 3. 핵심 차이 — 모델링 패러다임

| | PPTX (원본) | CCOP (온톨로지) |
|---|---|---|
| 모델 | **ERD / 속성 집약** — 개인 카드에 "전화번호(복수)" | **그래프 / 엣지** — `owns_phone` 1:N |
| 강점 | 개인 프로파일을 한눈에 | **공유 탐지**(같은 전화 = 여러 개인 = 공범) |
| 시간·다단계 | 표로 표현 어려움 | valid_from/to·추론 엣지 내장 |

두 모델은 **상호 변환 가능**하다. PPTX의 "(복수)" 속성이 CCOP에선 엣지가 되고, 개인/법인/사건 3중심 구조와 계좌·전화 속성은 그대로 유지된다.

## 4. 5가지 개선 — Before → After

> 각 개선은 CCOP v4.6 **기존** 노드·엣지를 재사용 → Text2Cypher 재학습 불필요.

### 4.1 식별자 — 개인정보 보호 ⚠
- **Before**: 개인 PK = `[주민번호]`, 법인 PK = `[사업자번호]` — 자연키를 직접 PK로 사용 → 민감정보가 그래프 전역 키로 노출.
- **After**: 개인 = `psn_id`(대리키) + `rrno_hash`(주민번호 해시), 법인 = `org_id` + `brno`(속성).
- **효과**: 매칭은 해시로, 표시·연결은 대리키로 — 개인정보보호법 정합. **최우선 개선.**

### 4.2 법인 대표 — 관계로 정규화
- **Before**: 법인 속성에 `대표이름`·`대표주민번호` (문자열).
- **After**: `vt_org` ─[대표자]→ `vt_psn` (독립 인물 노드 + 관계 엣지).
- **효과**: "한 사람이 대표인 여러 법인"(바지사장·연결고리)을 즉시 탐지.

### 4.3 사건–인물 — 수사 역할 부여
- **Before**: 사건 → 개인 (역할 구분 없음).
- **After**: 사건 ─[`suspect_in`/`victim_in`/`witness_in`]→ 개인.
- **효과**: 피의자·피해자·참고인 구분 → 역할별 필터, 피해 집계, 피의자 네트워크 분리.

### 4.4 닉네임 / SNS ID — 통합 정책
- **Before**: `SNS ID`와 `닉네임`이 별도 엔티티.
- **After**: `vt_id` 단일 노드 + `id_type`(sns/nickname) + `platform`.
- **효과**: 플랫폼·유형별 조회, 동일 계정의 ID/표시명 통합.

### 4.5 속성 보강 + 시간축 (v4.6)
- **Before**: 전화 `개통일`·개인 `직업`이 PPTX엔 있으나 CCOP `vt_telno`/`vt_psn`엔 미정의.
- **After**: `vt_psn.occupation` 추가 · 개통일/개설일 → v4.6 `valid_from`(유효구간).
- **효과**: 속성 보강 + 시간축 분석(ip_role bitemporal 등)과 정합.

## 5. 개선된 통합 스키마 (그래프 모델)

```
                          ┌─────────────┐
              suspect_in  │ 사건 vt_case │  eg_used_*
          ┌───────────────│    flnm     │───────────┐
          │               └─────────────┘           │ (점선)
          ▼                                          ▼
   ┌──────────────┐   대표자(굵은선)   ┌──────────────┐
   │  개인 vt_psn  │◄─────────────────│  법인 vt_org  │
   │ psn_id·rrno# │                   │  org_id·brno │
   └──────┬───────┘                   └──────────────┘
          │ owns_phone·has_account·used_ip·uses_id·uses_email·owns_wallet
          ▼
   [vt_telno] [vt_bacnt] [vt_ip] [vt_crypto] [vt_id] [vt_email] [vt_loc]
```

개인·법인이 **같은 객체(전화·계좌·IP)를 공유**하면 엣지가 한 노드로 모여 **공범·공용자원**이 드러난다. PPTX의 "(복수)" 속성이 이 엣지들로 자연 변환된다.

## 6. 마이그레이션 경로

PPTX 스키마 → CCOP 적재는 **기존 파이프라인 재사용**으로 가능:

1. 엔티티 → 노드 (11종 매핑 완료)
2. "(복수)" 속성 → 엣지 (`owns_phone`·`has_account`·`used_ip`·`uses_id`·`uses_email`·`owns_wallet`…)
3. 주민/사업자번호 → 대리키 + 해시 (`psn_id`+`rrno_hash` / `org_id`+`brno`)
4. 대표·역할 → 관계 엣지 (대표자 / `suspect_in`·`victim_in`)
5. 개통·개설일 → `valid_from` (v4.6 유효구간)

**신규 노드·엣지 0** — 전부 CCOP v4.6 기존 스키마로 흡수되므로 sLLM 재학습·파이프라인 개조가 불필요.

## 7. 결론

- 원본 PPTX는 **CCOP 온톨로지와 충돌 없이 매핑되는 견고한 수사 스키마**다.
- 개선 5건 중 **①식별자 개인정보**·**②법인대표·역할의 관계화**가 우선 — 그래프 모델로 정규화하면 CCOP와 완전 합류.
- 강점(개인/법인 이원화, 계좌 속성 정합)은 그대로 유지.
- 모든 개선이 기존 스키마 재사용이라 **저비용·무재학습**으로 적용 가능.

---

## 부록 — 출처·참조
- 원본: `수사단서 연관관계분석 스키마_20260810.pptx` (1슬라이드)
- 대조 기준: CCOP v4.6 `ontology_service.py` (ENTITIES 25노드, RELATIONSHIPS 71엣지, NODE_ID_STANDARD)
- 시각화: claude.ai/code/artifact/04caff69 (개선안 before/after + 그래프)
- 관련: `docs/ONTOLOGY_V46_IP_ROLE_BITEMPORAL_DESIGN.md`, `docs/STANDARD_DDL_ALIGNMENT_REVIEW_20260804.md`
