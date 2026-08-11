# v4.6 설계 — #2 지연 확장 저장소 (lazy expansion)

> **작성일**: 2026-08-12
> **대상**: `aggregation_level`·`event_count`·`sample_event_ids` (V4.5 G9, 집약 노드 `vt_access`·`vt_msg`)
> **상태**: 설계안 (코드 반영 전 — 검토용)
> **결론 한 줄**: **신규 저장소는 불필요하다.** 원본 RDB(Bridge Key)가 이미 저장소이며, 미정의였던 것은 "저장소"가 아니라 **`sample_event_ids` 명세 + 지연확장 조건 + 조회 경로**다. 이 셋을 확정하면 지연 확장이 구현된다.

---

## 1. 현황 진단

| 구성요소 | 상태 | 근거 |
|---|---|---|
| `aggregation_level`(raw/hourly/daily) | 규칙만 | 등록부 |
| `event_count`(집약 원본 수) | 표시만 | 등록부 |
| `sample_event_ids`(지연확장 참조 키) | **명세 부재** | known_limitation |
| 원본 저장소 | **이미 존재** | Bridge Key 정의됨 (아래) |

**핵심**: `vt_access.sample_event_ids`가 409,941건을 "펼칠 경로가 없다"고 기록됐으나, 실제로는 **Bridge Key가 이미 원본으로의 경로**다:
- `vt_access` → `lgn_sn` → **`TB_SYS_LGN_EVT`**
- `vt_msg` → `msg_sn` → **`TB_TELNO_SMS_MSG` / `TB_CHAT_MSG`**

즉 저장소(원본 RDB)는 있고, `sample_event_ids`에 **무엇을(원본 PK) 담고 어떻게 조회하는가**의 명세만 없었다.

---

## 2. 핵심 통찰 — 저장소는 이미 있다

```
[집약 노드]                    [참조 키]              [원본 저장소 = 기존 RDB]
vt_access(event_count:8,203) → sample_event_ids  →  TB_SYS_LGN_EVT (lgn_sn PK)
   aggregation_level: daily     = [lgn_sn 표본]      ← Bridge Key 로 직접 SELECT
```

- **신규 이벤트 저장소 신설 불필요** — 원본 RDB가 SoT(신뢰의 원본)이자 저장소.
- `sample_event_ids` = 원본 PK(`lgn_sn`/`msg_sn`) 목록. 이것만 그래프에 두면 Bridge Key로 원본 전량 재조회 가능.
- 그래프는 "집약 + 표본 포인터"만 보유(경량), 상세는 필요시 RDB에서 펼침(**지연**).

---

## 3. 설계

### 3.1 `sample_event_ids` 명세
- **값**: 원본 PK 목록 — `vt_access`는 `lgn_sn`, `vt_msg`는 `msg_sn`.
- **상한**: 표본 `N`개(기본 20). 전량은 `event_count`가 가리키고, 상세는 Bridge Key 재조회.
- **선정**: aggregation_key 그룹 내 대표(시간 경계·이상치 우선).
- **저장**: 그래프 노드 속성(JSON list). 원본 전량은 저장 안 함(경량 유지).

### 3.2 aggregation_key (집약 기준)
```
key = (subject_id, bucket(access_dt, aggregation_level), event_type)
  aggregation_level: raw(무집약) | hourly | daily
```
같은 key의 원본 이벤트들이 하나의 집약 노드로 접힌다. `event_count` = 그룹 크기.

### 3.3 지연 확장 3조건 (언제 펼치나)
전량 펼침은 낭비(409,941건). **아래 중 하나 충족 시에만** 원본 조회:
1. **수사 관심** — 사용자가 해당 노드를 선택/확장 요청
2. **임계 초과** — `event_count ≥ θ_expand`(대량 집약이라 표본만으론 부족)
3. **증거 특정** — 특정 시각/조건의 개별 이벤트가 필요(법정 증거)

→ 미충족 시 `event_count`·`sample_event_ids`(표본)만으로 응답(경량).

### 3.4 조회 경로 (2단계)
```
① 그래프(Cypher):  MATCH (a:vt_access {access_id})
                    RETURN a.event_count, a.sample_event_ids, a.aggregation_level
② 확장 판정:        should_expand(event_count, context) == True 이면 ↓
③ 원본(SQL):        SELECT * FROM TB_SYS_LGN_EVT
                    WHERE LGN_SN = ANY(:pks)          -- Bridge Key
```
표본만 필요하면 ①에서 종료, 전량이면 `sample_event_ids`(또는 aggregation_key 재질의)로 ③ 실행.

### 3.5 순수 로직 (DB 없이 구현·테스트 가능)
```python
def should_expand(event_count, *, requested=False, evidence=False, theta=100):
    """지연확장 3조건. requested/evidence 는 컨텍스트, theta 는 임계."""
    return requested or evidence or event_count >= theta

def build_expansion(label, pks):
    """집약노드 label + 원본 PK 목록 → (원본테이블, PK컬럼, 조회키).
    Bridge Key 매핑으로 SQL 대상 확정 (실행은 어댑터)."""
    BRIDGE = {
        'vt_access': ('TB_SYS_LGN_EVT', 'LGN_SN'),
        'vt_msg':    ('TB_TELNO_SMS_MSG', 'MSG_SN'),  # 또는 TB_CHAT_MSG
    }
    table, pk = BRIDGE[label]
    return {'table': table, 'pk_col': pk, 'pks': pks}
```

---

## 4. 구현 단계

- [ ] **E1. 명세 반영** — 등록부 `sample_event_ids`에 "원본 PK(lgn_sn/msg_sn), 상한 N" 명시 + `aggregation_key` 정의 (`ontology_service.py`)
- [ ] **E2. 순수 로직** — `should_expand`·`build_expansion`(Bridge Key 매핑) + 단위테스트 (신규 모듈 `app/services/lazy_expansion.py`)
- [ ] **E3. 조회 어댑터** — 그래프 조회 → 확장 판정 → RDB SELECT (운영 DB 실행 시)
- [ ] **E4. 적재 연동** — 집약 시 `sample_event_ids`에 원본 PK 표본 기록 (`rdb_to_graph_service`)

> **E1·E2는 DB 없이 지금 가능**(#1 S1/S3와 동일 접근). E3·E4는 운영 DB 의존.

## 5. 리스크 · 결정

| 항목 | 결정 |
|---|---|
| 저장소 신설 | **불필요** — 원본 RDB 재사용 (본 설계의 핵심) |
| 표본 상한 N | 기본 20 (전량은 Bridge Key 재조회) |
| Bridge Key 무결성 | 원본 삭제/보존 정책과 연동 필요(운영) |
| θ_expand | v4.6 #3 분포임계처럼 데이터 기반 산출 여지 |

## 6. 다른 파생속성과의 관계
- `event_count`는 이미 표시 중 → 본 설계는 그 **드릴다운 경로**를 추가.
- `is_anonymous`(vt_psn) 등 다른 G9/후처리 파생과 독립.

---

## 부록 — 관련
- 현황: `ontology_service.py` DERIVED_PROPERTY_REGISTRY(aggregation_level/event_count/sample_event_ids), ENTITIES(Access/Message Bridge Key)
- 로드맵: memory `project_ontology_v46_todo`(#2), HANDOFF G9
- 관련 설계: `docs/ONTOLOGY_V46_IP_ROLE_BITEMPORAL_DESIGN.md`(#1 — 동일한 "순수 로직 + 어댑터 분리" 패턴)
