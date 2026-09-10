# CCOP 온톨로지 V4.8 — 전달 패키지

> 사이버범죄 수사 그래프 온톨로지 표준. **노드 25종 · 엣지 72종**(활성 70, deprecated 2).
> 제공: 스카이월드와이드 · 기준일 2026-09-10 · 대상: 통합 플랫폼 구축 기관

---

## 0. 15분 안에 파악하려면 (읽는 순서)

| 순서 | 파일 | 무엇을 얻나 |
|---|---|---|
| 1 | **`spec/SCHEMA_CATALOG_ACTUAL.html`** | 브라우저로 열면 **실제 적재된 스키마**를 노드 클릭으로 탐색. 정의보다 이걸 먼저 보십시오 |
| 2 | `spec/CCOP_Ontology_V4.8_노드엣지속성.xlsx` | 노드·엣지·속성 정본(검토·회신용 시트) |
| 3 | `code/ccop_ontology_v48.py` | 기계가 읽는 정의 SoT — 이식·검증의 기준 |
| 4 | `spec/CYBERCOP_STANDARD_TABLE_DDL.sql` | RDB 표준 51테이블 (온톨로지↔RDB 대응) |
| 5 | `code/audit_ontology_v48.py` | 귀사 적재 결과를 스스로 검증하는 도구 |

---

## 1. 가장 먼저 알아야 할 것 — **정의 72종 ≠ 사용 19종**

V4.8은 3차년도까지의 도메인 확장을 내다본 정의이고, **2차년도 실적재는 그 일부**입니다.
정의 전체를 구현 목표로 잡으면 낭비이니, 아래 구분을 먼저 잡으십시오.

| 구분 | 규모 | 성격 |
|---|---|---|
| 정의된 엣지 | **72종**(활성 70) | 마약·OSINT·차량 등 미도래 도메인 포함 |
| **2차년도 실사용 엣지** | **19종** | EP1~EP10 원본에 실제로 존재한 관계만 |
| 실사용 노드 | **12라벨** / 정의 25 | |
| 실적재 규모 | 24,720 노드 · 26,089 엣지 | 통합 그래프(`ccop_ep_integrated`) |

**우선 구현 대상은 19종**입니다. 목록·의미·방향·속성·건수는 `SCHEMA_CATALOG_ACTUAL.html`
② 섹션에 실측으로 정리돼 있습니다. 나머지 53종은 해당 원본 데이터가 도착할 때 채우면 됩니다
(정의만 있어도 무해합니다 — 런타임에 미사용 정의는 아무 영향이 없습니다).

### 실사용 19종 요약
```
used_ip 15,348 · contacted 4,867 · registered_to 2,112 · owns_phone 1,872 ·
transferred_to 617 · eg_used_account 220 · victim_in 215 · eg_used_phone 191 ·
has_account 151 · eg_used_id 145 · located_at 126 · sourced_from 121 ·
linked_to 57 · belongs_to 26 · suspect_in 6 · performed_by 6 · same_as 4 ·
uses_id 3 · uses_email 2
```

---

## 2. 정의 SoT — `code/ccop_ontology_v48.py`

**외부 의존이 0입니다.** 표준 라이브러리조차 import 하지 않는 순수 선언(dict)이라,
Python 환경에 그대로 두고 참조하거나 JSON으로 덤프해 타 언어에서 쓸 수 있습니다.

```python
from ccop_ontology_v48 import KICSCrimeDomainOntology as O

O.ENTITIES          # 25 — 노드 정의(layer·properties·attributes·description)
O.RELATIONSHIPS     # 72 — 엣지 정의(domain·range·semantic_relation·label_ko·meaning)
O.GDB_LABEL_MAP     # 개념명(Person) ↔ 그래프 라벨(vt_psn)
O.STANDARD_TABLE_MAP  # 온톨로지 ↔ RDB 표준테이블(TB_*) 매핑
O.COLUMN_PATTERNS   # 원본 컬럼명 → 표준 속성 추론 규칙
```

JSON 덤프가 필요하면:
```bash
python3 -c "import json,ccop_ontology_v48 as m; O=m.KICSCrimeDomainOntology; \
print(json.dumps({'entities':O.ENTITIES,'relationships':O.RELATIONSHIPS}, ensure_ascii=False, indent=2))" \
> ontology_v48.json
```

### 노드 레이어 구성 (25종)
`Object` 12 · `Event` 6 · `Case` 3 · `Person` 2 · `Location` 1 · `Source` 1

### domain/range 규칙
- 대부분 엣지는 `domain`·`range`가 특정 개념으로 고정됩니다(예: `has_account`: Person→Account).
- **8종은 `domain: 'Any'`** (`recorded_in`·`occurred_at`·`linked_to`·`sourced_from`·
  `used_for`·`contains_file` 등) — 여러 주체가 붙을 수 있는 범용 엣지이며, 감사에서
  와일드카드로 취급됩니다. 확장 여유를 여기서 확보하십시오.
- **deprecated 2종**(`clusters_with`·`owns_device`)은 신규 적재에 쓰지 마십시오.

---

## 3. 검증 도구 — `code/audit_ontology_v48.py`

귀사 적재 결과가 V4.8과 맞는지 **스스로 확인**할 수 있습니다. CI 게이트로 쓸 수 있게
위반 시 exit 1 을 반환합니다.

```bash
pip install psycopg2-binary
DB_HOST=... DB_PORT=... DB_NAME=... DB_USER=... DB_PASSWORD=... \
  python3 audit_ontology_v48.py --graph <그래프명> [<그래프명2> ...]
```

검사: ①정경 외 라벨 ②정경 외 엣지 ③deprecated 사용 ④domain/range 위반
⑤키 속성 충전율 ⑥`source_id` 보유율(원본 대조 가능성).

당사 통합 그래프 기준 출력 예 — **이 상태를 목표로 하십시오**:
```
══ ccop_ep_integrated ══
  노드 라벨 12종 · 정경 준수
  엣지 19종 · 정경 준수
  domain/range 준수
  키 충전율: 정상
  source_id 보유: 24,719/24,720 (100%)
✅ 위반 0
```

---

## 4. 적재 시 반드시 지킬 3가지 (당사 실측 근거)

### ① `source_id` 는 전 노드·엣지 필수
원본 대조 가능성이 이 과제의 핵심 요구입니다. 규약: `EP{n}-{문서번호}-{종류}`
(예: `EP5-030-ibk`, `EP3-013-cell`). 당사 보유율 100%.

### ② 수치 속성은 숫자 타입으로 저장
문자열로 넣으면 `>=` 비교와 `ORDER BY` 가 **조용히 틀립니다**(에러 없이 0건).
당사에서 실제로 겪었습니다 — `ep_count`·`total_amount` 를 문자열로 저장해
"1억 이상 이체" 질의가 0건이었고, 숫자화 후 11건이 나왔습니다.

대상: `total_amount` · `txn_count` · `tx_count` · `call_count` · `msg_count` ·
`total_dur_sec` · `ep_count` · `wd_count` · `dep_count`
※ AgensGraph 에는 `toInteger()` 가 없습니다 — 적재 시점에 숫자로 넣거나
   애플리케이션에서 변환해야 합니다.

### ③ 시간은 '첫/마지막' 집계 구조
관계는 쌍당 1엣지로 접고 `first_dt`/`last_dt` + 건수·합계만 남깁니다
(`contacted`·`transferred_to`·`located_at`). **건별 시각은 그래프에 두지 않고**
원본·표준 RDB(`TB_TELNO_CALL_D.CALL_STRT_DT` 등)가 담당합니다.
건별 시각이 필요한 노드는 예외적으로 보유합니다(`vt_movement.mov_dt`·`vt_case.occrn_dt`).

---

## 5. AgensGraph 사용 시 함정 (당사가 겪은 것)

| 함정 | 증상 | 대응 |
|---|---|---|
| `toInteger()` 없음 | 문법 오류 | 적재 시점에 숫자 타입으로 |
| 문자열 날짜에 `min()`/`max()` | `cannot cast ... to numeric` | `ORDER BY <alias> ASC/DESC LIMIT 1` |
| `ORDER BY` 에 속성 직접 참조 | 불안정 | `RETURN x AS a ... ORDER BY a` (alias 경유) |
| 미인용 식별자 소문자화 | `sameAs` → `sameas` | 엣지·라벨명은 **snake_case** 로 |
| 라벨 없는 `MATCH (n)` 후 `MERGE` | 미동작 | 순회 시 라벨 명시 |
| property index 는 별도 구문 | `DROP INDEX` 시 WrongObjectType | `DROP PROPERTY INDEX` |
| 엣지 속성 재생성 | 통짜 JSON `SET e='{...}'` 는 스칼라 오염 | **키별 SET** |

**⚠ 엔진 버전 주의**: 당사 운영 DB가 `AgensGraph 2.16-devel / PostgreSQL 16beta2`
(개발·베타 빌드)인데, **'경로 순회 + 비앵커 노드 속성 조건'** 형태 질의에서 백엔드가
비정상 종료(전 연결 강제 종료 → 복구 모드)합니다. 예:
```
MATCH (p:vt_psn {name:'홍길동'})-[:uses_id]->(i:vt_id {platform:'kakao'}) RETURN i   ← 크래시
MATCH (i:vt_id) WHERE i.platform='kakao' MATCH (p:vt_psn {name:'홍길동'})-[:uses_id]->(i) RETURN i   ← 정상
```
같은 쿼리가 PostgreSQL 13 기반 안정판에서는 정상입니다. **운영에는 안정판 사용을 권고**합니다.

---

## 6. RDB 표준과의 관계

`spec/CYBERCOP_STANDARD_TABLE_DDL.sql` — 51테이블/전컬럼이 테이블명세서와 정합합니다.
온톨로지↔RDB 매핑은 `O.STANDARD_TABLE_MAP` 에 선언돼 있고, **실사용 12라벨 전부(12/12)**
표준 테이블을 갖습니다. 값은 표준 이력별로 3키를 갖는 중첩 구조이니 `standard` 를 쓰십시오:

```python
O.STANDARD_TABLE_MAP['vt_loc']
# {'standard': 'TB_PSTN_M', 'public_v2': ..., 'test_v40': ...}   ← 'standard' 가 현행
```
| 라벨 | standard | | 라벨 | standard |
|---|---|---|---|---|
| `vt_psn` | `TB_PSN_M` | | `vt_telno` | `TB_TELNO_M` |
| `vt_bacnt` | `TB_FNNC_BACNT_M` | | `vt_loc` | `TB_PSTN_M` |

※ 마스터(`_M`)와 상세(`_D`)는 구분됩니다. 통화 **건별** 상세는 `TB_TELNO_CALL_D`
(`CALL_STRT_DT` 등)이고, 그래프의 `contacted` 엣지는 이를 쌍 단위로 집계한 결과입니다(§4-③).

권고 인터페이스: **원본 → 표준 RDB(TB_*) → 그래프(vt_*)**.
표준 RDB를 경계로 두면 원본 양식별 파싱(인코딩·병합셀·버전 혼재 등)은 전처리 측에서,
그래프 변환·검증은 분석 측에서 각자 책임지게 됩니다.

---

## 7. 파일 목록

```
handoff/ontology_v4.8/
├── README.md                                  ← 이 문서
├── spec/
│   ├── SCHEMA_CATALOG_ACTUAL.html             실측 스키마 (인터랙티브 — 먼저 보십시오)
│   ├── CCOP_Ontology_V4.8_노드엣지속성.xlsx    정본 (노드·엣지·속성)
│   ├── CCOP_ONTOLOGY_DESIGN_HISTORY.md        V4.0→V4.8 설계 이력·변경 사유
│   ├── CYBERCOP_STANDARD_TABLE_DDL.sql        RDB 표준 51테이블
│   └── PARTNER_DATA_STANDARD.md               협력기관 데이터 표준 가이드
└── code/
    ├── ccop_ontology_v48.py                   정의 SoT (외부 의존 0)
    └── audit_ontology_v48.py                  정합 감사 도구 (CI 게이트 가능)
```

## 8. 미포함 항목

- **T2C 학습모델(v48 LoRA)** 과 서빙·후처리 코드는 별도 패키지입니다(요청 시 제공).
  어댑터만으로는 성능이 나오지 않고 system 프롬프트·후처리 로직이 함께 필요합니다.
- 실데이터(EP1~EP10)는 비식별화본이라도 포함하지 않았습니다.
- 문의: 스카이월드와이드 기술지원팀
