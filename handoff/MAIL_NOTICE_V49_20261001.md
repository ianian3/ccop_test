# 협력기관 공유용 — 온톨로지 V4.9 변경 안내

> 보내기 전 확인: ①수신자 호칭·기관명 ②발신자 실명·연락처 ③대상 기관에 맞게 2번 표에서 해당 행만 남길지
> 별첨: `ontology_v4.9.zip` (온톨로지 정의를 직접 구현하는 기관에만 — CSV 적재만 하는 기관은 별첨 불요)

---

**제목:** [CCOP] 온톨로지 V4.9 변경 안내 — CSV 적재 규격·참조 적재기는 변경 없음

○○○ 님, 안녕하십니까. 스카이월드와이드입니다.

CCOP 온톨로지를 V4.8 에서 **V4.9** 로 올려 안내드립니다. V4.8 이후 **의미가 바뀐 변경**이 있어
같은 이름으로 재배포하지 않고 버전을 분리했습니다.

## 1. 요약

- **노드 25종 → 24종, 엣지 72종 → 52종.** 중복·추론 결과 엣지를 정리하고 같은 의미의 엣지를 합쳤습니다
  (21종 삭제, 1종 신설). 지금 정의된 엣지에는 추론 표시가 하나도 없고, 모두 원천 기록에서 나오는 관계입니다.
- **CSV 적재 규격(V4.8)과 참조 적재기 `load_csv_to_graph.py`는 바뀌지 않습니다.** 참조 적재기는 이번에
  삭제·통합된 엣지를 원래 만들지 않았고, 사건 식별자도 9/28 보완본부터 V4.9 기준(`incdnt_no`)입니다.
- 영향을 받는 것은 **온톨로지 정의를 직접 구현한 경우**(자체 적재기·검증기·스키마·질의)입니다.

## 2. 귀 기관에 해당하는 조치

| 귀 기관의 사용 방식 | 조치 |
|---|---|
| CSV 규격 + 참조 적재기로 적재 | **조치 없음.** 9/28 보완본 적재기를 쓰고 계신지만 확인 부탁드립니다 |
| 온톨로지 정의를 직접 구현 (자체 적재기·검증기·질의) | 아래 **3번 변경 내역**을 반영해 주십시오. 4번 감사 도구로 남은 옛 표기를 찾을 수 있습니다 |
| OSINT 데이터 제출 | 옛 표기 `hosts`·`sameAs`·`mentions_account`는 당분간 **경고를 남기고 새 표기로 자동 변환해 받습니다.** 다음 제출부터는 새 표기를 써 주십시오 |
| 전처리 도구에 `COLUMN_PATTERNS` 부록 사용 | 아래 **3-5** 를 확인해 주십시오 |

## 3. 변경 내역

### 3-1. 식별자·노드

| 대상 | V4.8 | V4.9 |
|---|---|---|
| 사건 `vt_case` 식별자 | `flnm` | **`incdnt_no`**(경찰청 공식 사건번호). `flnm`(사건파일번호)은 보조 속성 |
| 이메일 `vt_email` | 별도 노드(`email_addr`) | **`vt_id` 로 흡수** — `platform='email'`, `id_val` = 소문자로 정규화한 주소. 법적 분류(통신자료)와 표준 테이블(TB_EML_ADDR_M)은 플랫폼별 정보로 보존 |

### 3-2. 삭제된 엣지와 대체 표기

| 삭제된 엣지 | V4.9 에서 쓰는 표기 |
|---|---|
| `contradicts`·`clusters_with`·`accomplice_of`·`related_case` | **대체 없음.** 추론 결과는 원천 온톨로지가 아니라 분석 산출물로 다룹니다 |
| `owns_device` | `uses_device` |
| `impersonates` | `used_for` · `targets` |
| `involves`(사건→인물) | `witness_in {role:'unknown'}` — **방향이 인물→사건**으로 바뀝니다 |
| `owns` | 구체 소유 엣지(`has_account`·`owns_phone`·`owns_vehicle`·`owns_wallet`·`uses_device`) |
| `verified_by`(엣지) | 엣지 공통 메타 속성 `verified_by` |
| `linked_petition` | `filed_as {status:'linked'}` (전환은 `status:'converted'`) |
| `works_at` | `member_of {role:'employee'}` |
| `uses_email` · `eg_used_email` | `uses_id` · `eg_used_id` (도착 노드는 `vt_id {platform:'email'}`) |
| `mentions_id`·`mentions_account`·`mentions_location` | **`mentions`** 1종(신설) — 기재된 대상의 종류는 도착 노드 라벨로 구분 |
| `via_ip`(이체→IP) · `sent_from_ip`(메시지→IP) | `accessed_from` (접속·이체·메시지 → IP) |
| `occurred_at`(이벤트→위치) | `located_at` (객체·이벤트 → 위치) |
| `linked_id`(객체→계정) | `linked_to` (연결 근거는 `link_basis`) |
| `hosts`(IP→사이트) | `resolves_to {basis:'origin'}` — **방향이 사이트→IP**로 바뀝니다 |

### 3-3. 속성·규칙

- **쌍 단위 집계 규칙 명시** (9/28 회신드린 내용의 정식 반영) — 관계는 (출발, 도착) 쌍당 엣지 1개로 접습니다.
  - `used_ip`: `valid_from`=최초 접속, `valid_to`=마지막 관측, `usage_count`, `access_type`(여러 값은 `|`로 결합)
  - `located_at`: `first_dt`·`last_dt`·`evt_count`
  - `contacted`: `first_dt`·`last_dt`·`call_count`·`msg_count`·`total_dur_sec`
  - `transferred_to`: "추론 엣지·직접 생성 금지"에서 **원천 사실 집계 엣지**로 정정 — `txn_count`·`total_amount`·`first_dlng_dt`·`last_dlng_dt`·`channel`
  - 집계 규칙은 정의 스펙의 `RELATIONSHIPS[...]['aggregation']` 에 기계 판독 형태로 들어 있습니다.
- **`same_as` 속성명 통일:** `confidence`(숫자)·`match_basis`·`review_status`(`pending`|`confirmed`|`rejected` — `traversal_policy` `candidate_only`|`follow`|`block` 와 1:1)·`traversal_policy`.
  구 이름은 `match_score`·`conf`·`method`입니다. 양끝은 같은 라벨끼리만 연결합니다.
- **`resolves_to` 근거 속성 `basis` 신설:** `'dns'`(DNS 조회로 관측, 미기재 시 기본값) · `'origin'`(호스팅사 회신·압수 등으로 원본 서버 확인).
  CDN·가상호스팅 사이트는 `dns` 연결만으로 서버를 단정하지 마십시오.
- **파생 엣지 표시:** `belongs_to_cluster`·`belongs_to_campaign`은 유지하되, 원천 사실이 아닌 군집 결과(`derived`)로 표시합니다.

### 3-4. 도메인 확장

`accessed_from`(접속 → 접속·이체·메시지), `located_at`(고정 객체 → 객체·이벤트), `linked_to`(계좌·전화·IP → 계정 연결 포함)는
통합된 엣지를 받아들이도록 출발 노드 범위가 넓어졌습니다.

### 3-5. [부록] `COLUMN_PATTERNS` (전처리 힌트)

| 항목 | V4.8 | V4.9 |
|---|---|---|
| `case` | 사건번호 → `flnm` | 사건번호 → **`incdnt_no`** |
| `case_file` | — | **신설** — `flnm`·사건파일명·파일번호 → `vt_case.flnm`(보조 속성) |
| `sender`·`receiver` | 이체 이벤트 노드(`vt_transfer`) | 출금·입금 **계좌**(`vt_bacnt.account_no` + 방향 `direction`) |

컬럼명을 부분 일치로 판정한다면, `to`·`ip`·`tel` 같은 **짧은 영문 패턴은 단어 단위로만** 비교하시길 권합니다.
그렇게 하지 않으면 `customer`가 입금 계좌로, `zip_code`가 IP로 잘못 판정됩니다(당사에서 실제로 발견해 수정했습니다).

## 4. 기존 V4.8 적재 데이터가 있다면

- **원본에서 다시 적재하는 방법이 가장 안전합니다.** 적재는 MERGE 라서 같은 원본을 다시 넣어도 중복이 생기지 않습니다.
  AgensGraph 는 노드 라벨을 제자리에서 바꿀 수 없어서, 그래프 안에서 바로 이관하면 연결을 다시 만들어야 합니다.
- 다시 적재한 뒤에는 동봉한 감사 도구로 남은 옛 표기를 확인하실 수 있습니다. 정경 외 라벨·엣지가 0건이면 V4.9 정합입니다.
  ```bash
  python3 audit_ontology_v49.py --graph <그래프명>
  ```

## 5. 참고 자료 (`ontology_v4.9.zip`)

- `README.md` — 변경점 표(12항목)와 적재 시 주의사항
- `spec/CCOP_Ontology_V4.9_node_edge_attrs.xlsx` — 노드·엣지·속성 정본, `변경이력` 시트 R18~R30 · `후보 속성(미확정)` 시트(설계 근거 확인 전 속성 — 구현 대상 아님)
- `code/ccop_ontology_v49.py` — 기계가 읽는 정의 스펙 / `code/audit_ontology_v49.py` — 감사 도구

확인하시다가 궁금한 점이나 귀 기관 데이터에 맞지 않는 부분이 있으면 편하게 말씀해 주십시오.

감사합니다.
스카이월드와이드 ○○○ 드림
