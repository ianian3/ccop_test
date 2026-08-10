# v4.6 설계 — ip_role 시간축(bitemporal) 재설계

> **작성일**: 2026-08-10
> **대상**: `DERIVED_PROPERTY_REGISTRY['ip_role']` (V4.5 G12) + `used_ip` 엣지
> **상태**: 설계안 (코드 반영 전 — 검토용)
> **결론 한 줄**: ip_role을 **vt_ip 노드의 전 기간 단일값**에서 **`used_ip` 시간구간 기반 구간별 판정**으로 재설계. 전제는 `used_ip`에 `valid_from/to` 추가(G5를 IP로 확장). 대안 3안 중 **(A) 엣지 시간속성 + 노드 타임라인 하이브리드** 권장.

---

## 1. 현황 진단 (설계 전 실측)

| 구성요소 | 현재 상태 | 근거 |
|---|---|---|
| `ip_role` 규칙 명세 | ✅ 등록부 존재 | `ontology_service.py:173-185` |
| `ip_role` **계산 구현** | ❌ **미구현** (전 코드베이스 0건) | `grep -rn ip_role app/services` → 0 |
| `linked_subject_cnt`/`linked_entity_cnt` 계산 | ❌ 미구현 (규칙만) | 동일 |
| `used_ip` 시간속성 | ❌ `valid_from/to` **정의 없음** | `ontology_service.py:1349-1357` (meaning/label_ko만) |
| G5 유효구간 | ✅ **해소**(2026-08-10) — `eg_used_account`·`eg_used_phone`·`registered_to` properties에 valid_from/to 추가(used_ip와 정합). 값 백필은 후속(DB) | `eg_used_ip`는 제외(IP 시간성은 used_ip) |

> **핵심**: ip_role은 "규칙은 있으나 아무것도 계산하지 않는" 상태. 따라서 이 설계는 *리팩터링*이 아니라 **시간축을 처음부터 넣은 최초 구현 설계**다. 되레 기회 — 잘못된 전 기간 계산을 만들었다가 고치는 부채가 없다.

---

## 2. 문제 정의

IP의 역할(single_user / shared / call_center / hosting)은 **시간에 따라 바뀐다.**

```
IP 27.193.61.154  (HANDOFF G12 실례)
 ├─ 2017-03: 주체 3명 공유           → shared
 └─ 2017-04: 주체 1명 단독            → single_user
```

전 기간 통합 판정은 이 IP를 "shared"로 뭉뚱그려, **4월의 단독 사용(피의자 특정 단서)** 을 놓친다. 이는 G5(계좌·070의 valid_from/to 도입) 철학과 정면 충돌 — 같은 플랫폼이 계좌엔 시간축을 주고 IP엔 안 주는 비일관.

**수사적 손실**: IP 역할 *전환*(공유→단독, 인프라→봇넷 등)은 자금세탁·조직 재편의 신호인데, 통합 판정은 이를 평탄화한다.

---

## 3. 설계 대안 비교

| | (A) 엣지 시간속성 + 노드 타임라인 | (B) ip_role_period reification 노드 | (C) 엣지에 구간별 role 직접 |
|---|---|---|---|
| 구조 | `used_ip`에 `valid_from/to`, `vt_ip`에 `ip_role_timeline`(list)+`ip_role_current` | `(vt_ip)-[:has_role_period]->(:ip_role_period{from,to,role})` | 각 `used_ip` 엣지에 그 구간 `ip_role` |
| G5 일관성 | ◎ 계좌·070과 동일 패턴 | △ 별도 패턴 | ○ |
| 정규화 | ○ (노드에 요약 반정규화) | ◎ 완전 정규화 | ✗ 같은 구간 중복 |
| 노드 폭증 | 없음 | **IP×구간수 만큼 증가** | 없음 |
| Text2Cypher 부담 | 낮음 (노드 속성 조회) | 높음 (조인 1홉↑) | 중 |
| 시점 쿼리 정밀도 | 온디맨드 계산(used_ip 필터) | ◎ 직접 | ○ |
| 승급 여지 | → 필요시 (B)로 | — | — |

**권장: (A)**. 근거 — ① G5와 동일 패턴이라 학습·운영 일관, ② `clusters_with` O(n²) 회피 때 얻은 교훈(**노드/엣지 폭증 경계**)과 일치, ③ Text2Cypher 친화(노드 속성 단순 조회), ④ 정밀 시계열 수요가 커지면 (B)로 무손실 승급 가능. reification은 이벤트(이체·통화)에 쓰고, "구간 상태"인 ip_role엔 과함.

---

## 4. 권장안 (A) 상세 설계

### 4.1 스키마 변경

**① `used_ip` 엣지 — 시간속성 추가 (기존 시간엣지 패턴과 일관)** ✅ *S1 반영됨*
```python
'used_ip': {
    'domain': 'Person|Phone|DigitalID|Device',
    'range': 'NetworkTrace',
    # properties 는 list 형식(RELATIONSHIPS 전 엣지 통일). 타입은 EDGE_META_SCHEMA 공통정의
    'properties': ['valid_from', 'valid_to', 'confidence', 'source_id', 'rec_created'],  # ← 신규
    ...
}
```
> **bitemporal 2축**: `valid_from/to`(현실 유효구간) vs `rec_created`(DB 기록축) — 기존 스키마가 이미 2축이므로 설계 초안의 `observed_*`는 tritemporal 과설계라 **제외**. 원본 이벤트 시각은 기록축(`rec_created`)/백필 window로 흡수.

**② `vt_ip` 노드 — 파생속성 2종 신규**
| 속성 | 타입 | 의미 |
|---|---|---|
| `ip_role_current` | str | 최근(=마지막 valid_to) 구간의 역할 — 기존 단일 `ip_role` 대체 |
| `ip_role_timeline` | JSON list | `[{from, to, role, entity_cnt, subject_cnt}]` 구간별 판정(감사·표시용) |

> 하위호환: 기존 `ip_role`(단일)은 `ip_role_current`의 alias로 유지 → 기존 쿼리/시각화 무중단.

**③ 등록부 — `ip_role` 규칙 갱신 + 신규 2종 등록**
- `ip_role`의 `known_limitation` 제거, `temporal_rule` 추가(구간 산출 규칙).
- `ip_role_current`·`ip_role_timeline` 등록. `role_resolution_stage`에 `'period'` 단계 추가.

### 4.2 계산 알고리즘 — 구간 분할 (coalescing)

```
입력:  IP v 의 모든 used_ip 엣지 E = {(subject, valid_from, valid_to)}
출력:  ip_role_timeline, ip_role_current

1. 경계점 B = sort(unique( ∪ {valid_from, valid_to} ))         # 모든 시점
2. for each 인접 구간 [B[i], B[i+1]):
     active = { e ∈ E : e.valid_from ≤ B[i] AND e.valid_to > B[i] }
     subject_cnt = |distinct subject(active)|                    # 해소 전
     entity_cnt  = |distinct entity(active via sameAs)|          # 해소 후 (G12 순서)
     role = classify(entity_cnt, active 패턴)                     # 4.3
     구간 판정 push {from:B[i], to:B[i+1], role, entity_cnt, subject_cnt}
3. coalesce: 인접 구간이 role 동일하면 병합 (구간 폭발 방지)
4. ip_role_timeline = 병합 결과
   ip_role_current  = timeline[-1].role                          # 최신 구간
```

> **재계산 순서 불변**: `sameAs` 해소 **후** entity 기준 (G12) — 구간 단위로도 그대로 적용. subject 선계산은 여전히 오분류.

### 4.3 role 분류 규칙 (구간 내)

```
is_hosting(호스팅 대역/PTR)          → infra            # 최우선: 사용자수 무관 인프라
entity_cnt == 1                      → single_user
2 ≤ entity_cnt < θ_call_center       → shared_small
entity_cnt ≥ θ_call_center           → call_center      # 다수 실체 공유 = 콜센터 인프라
```
> 우선순위(구현): hosting > single_user > shared_small > call_center. `ip_role_temporal.classify_role()`.
> **정의 근거**(번들 CLAUDE.md 실측): single_user 11,575 · shared_small 1,457 · call_center 32 · infra 29. call_center 는 "착신전용"이 아니라 **entity_cnt 상위 구간**(다수 실체 공유) — 초기 설계의 pred 모델을 실측에 맞춰 정정.
> **θ_call_center(#3)**: 고정 5(임의값)를 `call_center_threshold()` 분포기반 이상치로 대체 — 골 없는 편중 분포라 percentile/MAD.
θ_shared, call_center 경계는 **고정값이 아닌 분포 기반**(v4.6 #3과 공유) — 구간별 활성 주체 분포에서 산출.

### 4.4 Cypher 예시 (시점 쿼리 — 신규로 가능해지는 것)

```cypher
-- "2017-03 시점에 이 IP를 공유한 주체" (구간 온디맨드)
MATCH (s)-[u:used_ip]->(ip:vt_ip {addr:'27.193.61.154'})
WHERE u.valid_from <= date('2017-03-15') AND u.valid_to > date('2017-03-15')
RETURN ip.addr, collect(DISTINCT s) AS subjects_at_t

-- "역할이 전환된 IP" (수사 신호)
MATCH (ip:vt_ip)
WHERE size(apoc.convert.fromJsonList(ip.ip_role_timeline)) >= 2
RETURN ip.addr, ip.ip_role_timeline
```

---

## 5. 마이그레이션 / 백필

1. **`used_ip` valid_from/to 백필**: 원본 접속·로그인 이벤트(`TB_SYS_LGN_EVT` 등)의 시각에서 유도.
   - point-in-time 로그면 구간화 규칙: `valid_from = min(관측)`, `valid_to = max(관측) + window(기본 1d)`.
   - 원본 이벤트 실제 시각은 기록축(`rec_created`)에 보존(별도 관측축 신설 안 함).
2. **ip_role 재계산**: sameAs 해소 완료 후 §4.2 실행 → timeline·current 채움.
3. 기존 단일 `ip_role` 값 → `ip_role_current`로 이관(alias), timeline은 신규 생성.

---

## 6. Text2Cypher / 하위 영향

- **긍정**: "언제 공유였나", "역할 바뀐 IP" 등 **시간 질의가 처음으로 가능**. few-shot에 시점/전환 쿼리 2~3개 보강.
- **주의**: `used_ip`에 시간조건이 붙으므로 schema pruning 시 `used_ip` 주입에 `valid_from/to` 동반. 기존 무시간 쿼리는 `ip_role_current`로 그대로 동작(하위호환).
- 엣지 명명 동결 원칙 유지 — **신규 엣지 없음**(속성만 추가), 재학습 불필요.

---

## 7. 리스크 · 난이도

| 항목 | 평가 |
|---|---|
| 스키마 변경 | used_ip properties + vt_ip 파생 2종 (중) |
| 신규 구현 | 구간분할 계산 = **신규 코드**(기존 부채 없음) (중) |
| 백필 정확도 | 원본 이벤트 시각 품질에 의존 — window 규칙 검증 필요 (중) |
| 재학습 | **불필요** (엣지 명명 불변, 속성 추가만) (저) |
| 성능 | IP당 구간분할 O(E log E), coalesce로 구간 억제 (저) |

---

## 8. 단계별 실행 계획

- [x] **S1. 스키마 반영** — `used_ip` properties(valid_from/to) + `vt_ip` 파생 2종(ip_role_current/timeline) + 등록부 갱신 (`ontology_service.py`) ✅ 2026-08-10, 테스트 18 passed
- [ ] **S2. 백필 규칙** — 원본 이벤트 → `used_ip.valid_from/to` window 규칙 확정·검증
- [x] **S3. 계산 구현** — **순수 모듈** `app/services/ip_role_temporal.py`(구간분할·coalesce·role분류, DB 의존 0) + 단위테스트 `tests/test_ip_role_temporal.py` **7 passed**(전환/G12 sameAs 순서/coalesce/hosting/open-ended/thresholds). 연동 호출은 S4. ✅ 2026-08-10
- [ ] **S4. 재계산 실행** — sameAs 후 timeline/current 산출
- [ ] **S5. 검증** — 27.193.61.154 등 전환 IP로 3월 shared / 4월 single 재현 확인
- [ ] **S6. Text2Cypher** — 시점/전환 few-shot 보강, pruning 동반속성

> **선행 의존**: S3의 role 분류(§4.3)는 v4.6 #3(call_center 분포임계)과 규칙을 공유 — 함께 확정하면 중복 없음.
>
> **#3 call_center 분포임계 — 함께 구현됨** ✅: `call_center_threshold()`(percentile/MAD)로 고정 5 대체. call_center 정의를 번들 실측(entity_cnt 상위 구간)에 맞춰 정정. 단위테스트 **11 passed**. 남은 것은 운영 분포로 θ 실산출(S4 연동 시).

---

## 부록 — 관련
- 현황: `ontology_service.py` DERIVED_PROPERTY_REGISTRY(ip_role/linked_*), RELATIONSHIPS(used_ip)
- 원칙: `docs/ONTOLOGY_EDGE_REVIEW_20260810.md`(명명 동결·속성 추가는 무재학습)
- 로드맵: memory `project_ontology_v46_todo`(#1 최우선), HANDOFF G5/G12
