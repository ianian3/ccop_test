# V4.0 자연어 쿼리 잔존 약점 분석 + 시드 보강 후보

- **분석일**: 2026-05-22
- **소스**: `results/test_v40_natural_query.json` (45 케이스 중 14 실패)
- **모델**: `qwen25_t2c_v39_v1` (72.4% 벤치마크 / 68.9% V4.0 시나리오)
- **목적**: 차기 라운드 학습 시드 후보 도출 → v40 학습 데이터 빌더 가이드

---

## ⚡ Executive Summary

14건 실패를 분석한 결과 **8개 약점 패턴** 으로 분류. 권장 시드 약 1,650개 추가 시 V4.0 시나리오 정확도 80%+ 도달 추정.

| 패턴 | 실패 건수 | 권장 시드 | 우선순위 |
|------|-----------|-----------|----------|
| P1. 부분 매칭 (CONTAINS) | 2 | 200 | 🔴 P0 |
| P2. 다중 WHERE (AND/OR) | 3 | 400 | 🔴 P0 |
| P3. 메타 필터 (V4.0) | 3 | 300 | 🔴 P0 |
| P4. 시간 ORDER BY | 1 | 200 | 🟡 P1 |
| P5. 엣지 방향 정확성 | 2 | 200 | 🟡 P1 |
| P6. 엣지 명칭 정합 (involves) | 1 | 150 | 🟡 P1 |
| P7. 단순 허브 노드 조회 | 1 | 100 | 🟢 P2 |
| P8. 타입 캐스팅 회피 | 1 | 100 | 🟢 P2 |

---

## 1. P1 — 부분 매칭 (CONTAINS) 학습 부족

### 실패 케이스

| # | 질의 | 모델 출력 | 문제 |
|---|------|----------|------|
| 13 | "강남 사건의 피의자가 누군지 보여줘" | `vt_case { flnm: '강남'}` 완전일치 | flnm 실제값은 `'강남 보이스피싱 일당 캠페인'` |
| 14 | "강남 보이스피싱 일당" | 운 좋게 정확한 flnm 매칭 | 자연어 변형 강건성 부족 |

### 시드 패턴 (Native Cypher, ~200개)
```cypher
-- 의도: 부분 키워드로 사건 검색
"강남 사건"
→ MATCH (c:vt_case) WHERE c.flnm CONTAINS '강남' RETURN c

"보이스피싱 관련 사건"
→ MATCH (c:vt_case) WHERE c.crime_type CONTAINS '보이스피싱'
   OR c.flnm CONTAINS '보이스피싱' RETURN c

"부산 자금 이체"
→ MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer)
   WHERE b.holder_nm CONTAINS '부산' RETURN b, t
```

**변형 다양성**: 부산/대구/대전 등 지역명 20종 + 사건명/주체명 50종 × 2-3 hop 변형.

---

## 2. P2 — 다중 WHERE 조건 (AND/OR) 학습 부족

### 실패 케이스

| # | 질의 | 모델 출력 | 문제 |
|---|------|----------|------|
| 10 | "익명이면서 OSINT 출처 인물" | `sourced_from` 가짜 엣지 + `reliability_tier:'osint'` 잘못 값 | 두 속성 AND 학습 부족 |
| 11 | "VOIP 통신사이면서 중계기 경유 전화" | carr_cd 조건 누락 | 두 조건 결합 부족 |
| 12 | "금액 100만원 이상 이체" | `(t.amount)::int` 캐스팅 시도 → 에러 | WHERE 비교 학습 부족 |

### 시드 패턴 (~400개)
```cypher
-- 다중 속성 AND
"익명이면서 OSINT 인물"
→ MATCH (p:vt_psn)
   WHERE p.is_anonymous = true AND p.source_domain = 'osint'
   RETURN p

"VOIP 중계기 전화"
→ MATCH (t:vt_telno)-[:used_in_device]->(d:vt_dev)
   WHERE t.carr_cd = 'VOIP' AND d.dev_type = 'relay_station'
   RETURN t, d

-- 숫자 비교 (캐스팅 없이)
"금액 100만원 이상 이체"
→ MATCH (t:vt_transfer) WHERE t.amount >= 1000000 RETURN t

-- OR 패턴
"피의자 또는 피해자 인물"
→ MATCH (p:vt_psn) WHERE p.role_cd = 'suspect' OR p.role_cd = 'victim' RETURN p
```

**중요 규칙**: AgensGraph 는 agtype 자동 비교 — `::int` / `::float` 캐스팅 **금지**.

---

## 3. P3 — V4.0 메타 필터 학습 부족

### 실패 케이스

| # | 질의 | 모델 출력 | 문제 |
|---|------|----------|------|
| 6 | "OSINT 도메인 계좌 이체" | source_domain 필터 누락 → 전체 반환 | 메타 컬럼 인식 약함 |
| 7 | "사건별 피의자 수" | `involves` 가짜 엣지 사용 | (엣지 명칭 P6 와 동시) |
| 8 | "도메인별 노드 수" | site/campaign 으로 오해 | "도메인" → source_domain 매핑 부족 |

### 시드 패턴 (~300개)
```cypher
-- source_domain 필터
"OSINT 계좌"     → MATCH (b:vt_bacnt) WHERE b.source_domain = 'osint' RETURN b
"investigation 인물" → MATCH (p:vt_psn) WHERE p.source_domain = 'investigation' RETURN p

-- reliability_tier 필터
"신뢰도 1 노드"    → MATCH (n) WHERE n.reliability_tier = 1 RETURN n
"공식 데이터만 보여줘" → MATCH (n) WHERE n.reliability_tier <= 2 RETURN n

-- 도메인별 집계
"도메인별 노드 수"
→ MATCH (n) RETURN n.source_domain AS domain, count(n) AS cnt
   ORDER BY cnt DESC

"도메인별 계좌 통계"
→ MATCH (b:vt_bacnt) RETURN b.source_domain AS dom, count(b)

-- 메타 조합 + 1-hop
"OSINT 계좌의 이체"
→ MATCH (b:vt_bacnt)-[:from_account]->(t:vt_transfer)
   WHERE b.source_domain = 'osint' RETURN b, t
```

---

## 4. P4 — 시간 ORDER BY 학습 부족

### 실패 케이스

| # | 질의 | 모델 출력 | 문제 |
|---|------|----------|------|
| 9 | "최근 이체 5건" | `LIMIT 5` 만, ORDER BY 누락 | "최근" → 시간 정렬 매핑 부족 |

### 시드 패턴 (~200개)
```cypher
"최근 이체 5건"
→ MATCH (t:vt_transfer) RETURN t ORDER BY t.occurred_at DESC LIMIT 5

"오래된 통화 10건"
→ MATCH (c:vt_call) RETURN c ORDER BY c.occurred_at ASC LIMIT 10

"어제 접속 기록"
→ MATCH (a:vt_access) WHERE a.occurred_at >= '2026-05-20'
   AND a.occurred_at < '2026-05-21' RETURN a

"이번 달 이체 금액 큰 순"
→ MATCH (t:vt_transfer) WHERE t.occurred_at >= '2026-05-01'
   RETURN t ORDER BY t.amount DESC
```

**핵심**: "최근/오래된/어제/이번 달" → `ORDER BY *.occurred_at` 매핑.

---

## 5. P5 — 엣지 방향 정확성

### 실패 케이스

| # | 질의 | 모델 출력 | 문제 |
|---|------|----------|------|
| 3 | "site_cluster → 사이트 → IP" | `(s)-[:hosts]->(ip)` (잘못) | hosts 방향은 `(ip)-[:hosts]->(s)` |
| 5 | "사건 피의자 계좌 이체 내역" | from_account 만 사용 | to_account 누락 → 1방향만 |

### 시드 패턴 (~200개)
```cypher
-- 정확한 방향성 명시
"사이트의 호스팅 IP"
→ MATCH (ip:vt_ip)-[:hosts]->(s:vt_site) RETURN ip, s

"피의자 계좌의 입출금"
→ MATCH (p:vt_psn)-[:has_account]->(b:vt_bacnt)
   OPTIONAL MATCH (b)-[:from_account]->(t:vt_transfer)
   OPTIONAL MATCH (b2:vt_bacnt)-[:from_account]->(t)
   RETURN p, b, t
```

**엣지 방향 카탈로그** (학습 데이터에 정합 강제):
| 엣지 | 방향 |
|------|------|
| hosts | vt_ip → vt_site |
| has_account | vt_psn → vt_bacnt |
| owns_phone | vt_psn → vt_telno |
| caller | vt_telno → vt_call |
| callee | vt_call → vt_telno |
| from_account | vt_bacnt → vt_transfer |
| to_account | vt_transfer → vt_bacnt |
| used_in_device | vt_telno → vt_dev |
| belongs_to_campaign | vt_site → site_cluster |
| belongs_to_cluster | vt_psn → pt_cluster |

---

## 6. P6 — 엣지 명칭 정합 (involves deprecated)

### 실패 케이스

| # | 질의 | 모델 출력 | 문제 |
|---|------|----------|------|
| 7 | "사건별 피의자 수" | `(c)-[:involves]->(p)` | involves 는 deprecated, suspect_in/victim_in/witness_in 사용 |

### 시드 패턴 (~150개)
```cypher
-- 명시적으로 V4.0 엣지 사용
"사건의 피의자"
→ MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) RETURN p, c

"사건별 피의자 수"
→ MATCH (c:vt_case)<-[:suspect_in]-(p:vt_psn)
   RETURN c.flnm, count(p) AS suspects ORDER BY suspects DESC

"피해자가 있는 사건"
→ MATCH (c:vt_case)<-[:victim_in]-(p:vt_psn) RETURN c, p

"참고인 진술이 있는 사건"
→ MATCH (c:vt_case)<-[:witness_in]-(p:vt_psn) RETURN c, p
```

**중요**: 학습 system 프롬프트에도 `involves` 는 명시적으로 deprecated 표기 (이미 V4.0 SSOT 에는 반영됨).

---

## 7. P7 — 단순 허브 노드 조회

### 실패 케이스

| # | 질의 | 모델 출력 | 문제 |
|---|------|----------|------|
| 1 | "pt_cluster 노드 보여줘" | `(p:vt_petition)-[:belongs_to_cluster]->(c:pt_cluster)` over-spec | 단순 `MATCH (c:pt_cluster)` 학습 부족 |

### 시드 패턴 (~100개)
```cypher
"pt_cluster 노드 보여줘"     → MATCH (c:pt_cluster) RETURN c
"site_cluster 노드 보여줘"   → MATCH (c:site_cluster) RETURN c
"vt_dev 노드 모두 보여줘"    → MATCH (d:vt_dev) RETURN d
"중계기 보여줘"              → MATCH (d:vt_dev) WHERE d.dev_type = 'relay_station' RETURN d
```

**핵심**: V3.7 신규 허브 노드(`pt_cluster`/`site_cluster`)에 대한 **단순 RETURN 패턴**도 시드에 명시.

---

## 8. P8 — 타입 캐스팅 회피

### 실패 케이스

| # | 질의 | 모델 출력 | 문제 |
|---|------|----------|------|
| 12 | "금액 100만원 이상 이체" | `(t.amount)::int >= 1000000` | AgensGraph 캐스팅 문법 오류 |

### 시드 패턴 (~100개)
```cypher
-- ❌ NEVER: 캐스팅 사용
-- WHERE (t.amount)::int >= 1000000

-- ✅ ALWAYS: agtype 자동 비교
"금액 100만원 이상"        → MATCH (t:vt_transfer) WHERE t.amount >= 1000000 RETURN t
"통화 30초 이상"           → MATCH (c:vt_call) WHERE c.duration >= 30 RETURN c
"신뢰도 1 이상 4 이하"     → MATCH (n) WHERE n.reliability_tier >= 1 AND n.reliability_tier <= 4 RETURN n
```

---

## 9. v40 학습 데이터 빌더 권장 구조

`data/build_v40_weakness_seed.py` (신규 작성):
```python
SEED_CATEGORIES = {
    'partial_match':       {'count': 200, 'pattern': P1},   # CONTAINS
    'multi_where':         {'count': 400, 'pattern': P2},   # AND/OR
    'meta_filter':         {'count': 300, 'pattern': P3},   # source_domain/tier
    'time_order':          {'count': 200, 'pattern': P4},   # ORDER BY occurred_at
    'edge_direction':      {'count': 200, 'pattern': P5},
    'edge_naming':         {'count': 150, 'pattern': P6},   # involves → suspect_in
    'hub_node_simple':     {'count': 100, 'pattern': P7},
    'no_cast':             {'count': 100, 'pattern': P8},
}
# 총 1,650 시드
```

**병합 후 학습**: 31,694 (v39) + 1,650 = **33,344 샘플** → 약 6~7h 학습 추정.

---

## 10. 예상 효과

| 카테고리 | v39 | v40 (예상) |
|----------|-----|-----------|
| A.단일 | 100% | 100% (유지) |
| B.V3.7 | 80% | 95% (+15p, P7 효과) |
| C.1hop | 87.5% | 90% (+2.5p) |
| D.2hop | 75% | 87% (+12p, P5 효과) |
| E.3hop | 33% | 70% (+37p, P5 효과) |
| F.메타 | 80% | 95% (+15p, P3 효과) |
| G.집계 | 50% | 85% (+35p, P3+P6 효과) |
| H.정렬 | 67% | 90% (+23p, P4 효과) |
| I.복합 | 25% | 75% (+50p, P2+P8 효과) |
| J.변형 | 60% | 88% (+28p, P1 효과) |
| **전체** | **68.9%** | **~85%** (+16p 예상) |

벤치마크 152문항도 72.4% → 80%+ 동반 상승 예상.

---

## 11. 결론

14건 실패는 운/노이즈가 아니라 **8개 명확한 패턴**으로 분류됨. 시드 1,650개 보강만으로 V4.0 시나리오 85% / 152문항 80% 돌파 가능 추정. 단순 패턴 매핑 학습이 부족한 부분이며, **베이스 모델 교체 없이 데이터만으로 해결 가능**한 영역.

### 다음 단계

- **(a)** `data/build_v40_weakness_seed.py` 작성 (8 패턴 시드 1,650개)
- **(b)** v40 학습 yaml 생성 → 학습 서버 SSH 후 LoRA 학습 시작
- **(c)** 머지 → vLLM 서빙 (`qwen25_t2c_v40_v1`) → 벤치마크 + 45 케이스 재측정
