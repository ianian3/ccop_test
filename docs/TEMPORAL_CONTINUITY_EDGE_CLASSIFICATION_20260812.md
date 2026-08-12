# 시간순 연속성 — 엣지 71종 V/E/N 분류표

> **작성일**: 2026-08-12
> **대상**: [시간순 연속성 적용] 기능 — 경로 A-[e1]->B-[e2]->C 에서 T(e1) ≤ T(e2) 보장
> **기준**: CCOP v4.6 온톨로지 71엣지 (설계 원안은 v4.3 63종 → 본 표로 갱신)
> **결론 한 줄**: V형 18 · E형 25 · **N형 28** (보완 4종 E형 승격 반영, 2026-08-12). 최빈 엣지 `has_account`·`owns_phone`·`owns_wallet`·`eg_used_ip`가 E형이 되어 시간순 실효성 확보. 명명 동결 준수(속성 추가만, 재학습 불필요).

---

## 1. 분류 규칙

| 형 | 기준 시각 | 정의 |
|---|---|---|
| **V형** | 경유하는 **Event 노드의 발생시각** | 엣지의 domain/range가 Event 노드(Transfer·Call·Access·Message·Movement·Impersonation) |
| **E형** | 엣지 자체의 **시각 속성** | valid_from · transfer_date · exchanged_at · first_seen · detected_at |
| **N형** | 없음 | 위 어느 것도 없음 → 그 지점에서 조건 끊김, `warnings` 안내 |

**Event 노드 시간속성**(V형 기준): `vt_transfer.dlng_dt` · `vt_call.call_strt_dt` · `vt_access.access_dt` · `vt_msg.dsptch_dt` · `vt_movement.timestamp` · `vt_impersonation.start_dt`
**제외**: `rec_created`(DB 기록축 ≠ 현실축)

## 2. V형 — 18종 (Event 경유 시각)

| 엣지 | 기준 시각 | domain→range |
|---|---|---|
| from_account | vt_transfer.dlng_dt | BankAccount→Transfer |
| to_account | vt_transfer.dlng_dt | Transfer→BankAccount |
| via_ip | vt_transfer.dlng_dt | Transfer→NetworkTrace |
| caller | vt_call.call_strt_dt | Phone→Call |
| callee | vt_call.call_strt_dt | Call→Phone |
| accessed_from | vt_access.access_dt | Access→NetworkTrace |
| accessed_to | vt_access.access_dt | Access→WebTrace/BankAccount |
| access_via | vt_access.access_dt | Access→Phone/DigitalID/BankAccount |
| sent_msg | vt_msg.dsptch_dt | Phone/DigitalID→Message |
| received_msg | vt_msg.dsptch_dt | Message→Phone/DigitalID |
| sent_from_ip | vt_msg.dsptch_dt | Message→NetworkTrace |
| mentions_account | vt_msg.dsptch_dt | Message→BankAccount |
| mentions_id | vt_msg.dsptch_dt | Message→DigitalID |
| mentions_location | vt_msg.dsptch_dt | Message→Location |
| recorded_in | vt_movement.timestamp | Any→Movement |
| targets | vt_impersonation.start_dt | Impersonation→Organization |
| used_for | vt_impersonation.start_dt | Any→Impersonation |
| **occurred_at** ⚠ | 경유 Event 시각 | Any→Location (**조건부**: 실제 경로의 출발이 Event일 때만 V형, 아니면 N형) |

## 3. E형 — 25종 (엣지 시각속성)

| 엣지 | 기준 시각 | 비고 |
|---|---|---|
| used_ip | 엣지.valid_from | ✅ **v4.6 S2에서 실제 백필됨**(접속시각 min/max) |
| eg_used_account | 엣지.valid_from | v4.6 G5 |
| eg_used_phone | 엣지.valid_from | v4.6 G5 |
| registered_to | 엣지.valid_from | v4.6 G5 (명의 등록) |
| suspect_in / victim_in | 엣지.valid_from | 사건 역할 유효구간 |
| member_of | 엣지.valid_from | |
| knows | 엣지.valid_from | |
| uses_device / uses_email / uses_id | 엣지.valid_from | |
| owns_vehicle / drives | 엣지.valid_from | |
| operates | 엣지.valid_from | |
| linked_id | 엣지.valid_from | |
| used_in_device | 엣지.first_seen | |
| hosts | 엣지.detected_at | |
| belongs_to_campaign | 엣지.detected_at | |
| contains_file | 엣지.detected_at | |
| **transferred_to** ✅보정 | 엣지.transfer_date | 자동분류 N형→**E형**(transfer_date 보유). 자금세탁 시간순의 핵심. hop_level(자금단계)로 순서 보조 가능 |
| **exchanged_to** ✅보정 | 엣지.exchanged_at | 자동분류 N형→**E형**(exchanged_at 보유). 계좌→가상자산 전환 시각 |
| **has_account** 🆕반영 | 엣지.valid_from | **보완 반영**(2026-08-12) 계좌 소유/개설 유효구간 — 최빈 엣지 |
| **owns_phone** 🆕반영 | 엣지.valid_from | **보완 반영** 전화 소유/개통 유효구간 — 최빈 엣지 |
| **owns_wallet** 🆕반영 | 엣지.valid_from | **보완 반영** 지갑 소유/최초확인 유효구간 |
| **eg_used_ip** 🆕반영 | 엣지.valid_from | **보완 반영** eg_used_account/phone 일관성 확보 |

## 4. N형 — 28종 (기준 없음 → warnings)

```
accomplice_of  belongs_to  belongs_to_cluster  blackmails  clusters_with
communicated_with  contacted  contradicts  controls  eg_used_email
eg_used_id  filed_as  impersonates  involves  linked_petition  linked_to
located_at  owns  owns_device  performed_by  recruits  related_case
resolves_to  sameAs  sourced_from  verified_by  witness_in  works_at
```
> 2026-08-12 보완으로 `has_account`·`owns_phone`·`owns_wallet`·`eg_used_ip` 4종이 E형으로 이동(§3).

> `performed_by`는 원안에서 V형(vt_access 경유)으로 봤으나, 실제 domain=Any→Person이라 **Access 노드를 직접 경유하지 않음** → N형. (접속주체는 `accessed_from`+`performed_by` 조합으로 표현되므로, 경로에 vt_access가 있으면 그 지점 V형으로 커버됨.)

## 5. 시간순 적용 함의 & 보완 우선순위

**N형 28/71 = 39%** (보완 후) — 최빈 엣지가 E형이 되어 시간순 실효성이 확보됐다.

**보완 우선순위 및 진행**:
| 우선 | 엣지 | 보완 방법 | 상태 |
|---|---|---|---|
| 🔴 1 | `has_account`·`owns_phone`·`owns_wallet` | valid_from 추가(계좌 개설일·전화 개통일·지갑 최초확인) | ✅ **반영 완료**(2026-08-12) |
| 🟡 2 | `eg_used_ip` | valid_from 추가(eg_used_*와 일관) | ✅ **반영 완료**(2026-08-12) |
| 🟡 3 | `contacted`·`communicated_with` | 통신 시각 속성 추가 or vt_call 경유로 V형화 | ⬜ 검토 |
| 🟢 4 | `located_at`·`resolves_to` | valid_from(위치/해석 시점) | ⬜ 선택 |

우선순위 1·2 반영으로 **최빈 엣지 4종이 N형에서 빠져** 시간순 warnings가 크게 줄었다. 단 **valid_from 값 자체는 적재 시 백필** 필요(스키마 자리만 등록, used_ip S2와 동일).

## 6. 구현 노트

- **타입 정합**: V형 Event 시각은 `timestamp`(초), E형 valid_from은 `date`(일). 비교 시 **일 단위로 절사 통일**(v4.6 S2 백필과 동일 기준) 권장.
- **Cypher 주입**: 인접 구간 s1,s2에 `WHERE T(s1) <= T(s2)`. V형은 경유 Event 노드 속성 참조, E형은 엣지 속성 참조로 분기.
- **N형 처리**: 해당 구간 조건 생략 + 응답 `warnings`에 "구간 [s1→s2]는 시간기준 없음(N형: <엣지>)" 명시.
- **transferred_to 특례**: `transfer_date` 우선, 없으면 `hop_level` 오름차순으로 순서 보장(추론엣지라 시각 결측 가능).
- **v4.6 연계**: `used_ip.valid_from`은 이미 백필(S2)되어 E형이 즉시 작동. bitemporal(ip_role 구간)과 결합하면 "특정 시점 경로"도 가능.

---

## 부록
- 분류 기준: `ontology_service.py` RELATIONSHIPS(71), ENTITIES(Event 노드 시간속성)
- 자동분류 보정 2건: `exchanged_to`(exchanged_at)·`transferred_to`(transfer_date) N형→E형, `occurred_at` 조건부 V형
- 관련: `docs/ONTOLOGY_V46_IP_ROLE_BITEMPORAL_DESIGN.md`(시간축), memory `project_ontology_v46_todo`
