# CCOP 적재용 CSV 규격 — 온톨로지 V4.8 개정판

> 2026-08-27 배포본(`CCOP_CSV_적재규격_배포패키지`)의 후속. **기존 9종 파일은 그대로 쓰시면 됩니다.**
> V4.8에서 달라지는 것은 *추가 컬럼*과 *신규 파일 종류*이고, 기존 컬럼은 이름·의미가 그대로입니다.
> 동봉: `examples/` 아래 예제 CSV 16종 · 자체 검증 도구 `validate_csv_v48.py`

---

## 0. 먼저 확인 — `tbl_eg_mtl.csv`

보내주신 목록 9종 중 **`tbl_eg_mtl.csv`는 당사 규격에 없는 이름**입니다. 나머지 8종은 정확히 일치하고,
당사 9번째 파일은 **`tbl_eg_rmt.csv`(계좌 이체)** 입니다. 파일 수와 자리가 맞아떨어지므로 같은 파일을
가리키는 것으로 보고 이 문서는 `tbl_eg_rmt` 기준으로 작성했습니다.

`mtl`이 다른 데이터(예: 물품·매물 정보)라면 **헤더 1행만 보내주시면** 해당 항목을 추가해 회신하겠습니다.

---

## 1. 세 줄 요약

1. **기존 9종의 기존 컬럼은 변경 없음.** 그대로 주셔도 적재됩니다 (하위호환).
2. **모든 파일에 `source_id` 한 컬럼을 추가**해 주십시오. V4.8에서 가장 중요한 변경입니다.
3. 나머지 추가 컬럼은 **있으면 채우고 없으면 비워두시면 됩니다**(선택). 다만 `tbl_vt_bacnt.bank_cd`와
   `tbl_eg_call.channel`은 비면 데이터가 잘못 합쳐지므로 가능한 한 채워주십시오(§3에 이유).

---

## 2. 파일별 변경 요약표

`★` 필수 · `＋` V4.8에서 새로 추가(선택, 있으면) · 취소선 없음 = **삭제되는 컬럼은 하나도 없습니다**

| 파일 | 기존 컬럼(유지) | ＋ 추가 컬럼 |
|---|---|---|
| `tbl_vt_psn` | `flnm`★ | `psn_id` · `dob` · `gender` · `nationality` · `occp_nm` · `source_id`★ |
| `tbl_vt_telno` | `telno`★ | `telco_nm` · `join_typ_cd` · `subs_holder` · `is_burner` · `source_id`★ |
| `tbl_vt_bacnt` | `actno`★ · `bank` · `dpstr` | **`bank_cd`** · `account_type` · `bacnt_opn_dt` · `source_id`★ |
| `tbl_eg_case` | `incdnt_no`★ · `incdnt_nm` · `incdnt_typ_cd` · `occrn_dt` · `incdnt_smry_cn` | `damage_amt` · `crime_site` · `source_id`★ |
| `tbl_eg_case_prsn` | `incdnt_no`★ · `prsn_id`★ · `role` | `source_id`★ |
| `tbl_eg_call` | `dsptch_no`★ · `rcptn_no`★ · `bgng_ymdhm` · `end_ymdhm` · `tlcmco` | **`channel`** · `bsst_addr` · `source_id`★ |
| `tbl_eg_telno_poss` | `flnm`★ · `telno`★ | `prsn_id` · `valid_from` · `valid_to` · `source_id`★ |
| `tbl_eg_bactno_poss` | `flnm`★ · `actno`★ | `prsn_id` · `bank_cd` · `valid_from` · `valid_to` · `source_id`★ |
| `tbl_eg_rmt` | `se`★ · `actno`★ · `bank` · `dpstr` · `rlt_actno`★ · `rlt_bank` · `rlt_dpstr` · `rmt_ymdhm` · `dpst_amt` · `tkmny_amt` | `bank_cd` · `rlt_bank_cd` · `ip_addr` · `brnch_nm` · `source_id`★ |

### 신규 파일 7종 (선택 — 해당 데이터가 있을 때만)

2차년도 실적재에서 **가장 많이 쓰인 관계가 IP 접속(15,348건)** 인데 기존 9종으로는 표현할 수 없었습니다.

| 신규 파일 | 담는 것 | 만들어지는 그래프 |
|---|---|---|
| `tbl_vt_ip` / `tbl_eg_ip_use` | IP와 그 사용 주체 | `vt_ip` / `used_ip` |
| `tbl_vt_id` / `tbl_eg_id_use` | 메신저·포털 계정과 소유자 | `vt_id` / `uses_id` |
| `tbl_eg_id_msg` | 계정 간 메시지 | `contacted`(channel=kakao 등) |
| `tbl_vt_loc` / `tbl_eg_loc_use` | 기지국·ATM·영업점 위치 | `vt_loc` / `located_at` |

---

## 3. 추가 컬럼 설명 (왜 필요한지)

### 3.1 `source_id` — 전 파일 필수 ★

**원본 문서 대조 가능성**이 이 과제의 핵심 요구라 V4.8에서는 모든 노드·엣지가 출처를 갖습니다.
당사 통합 그래프는 24,720 노드 전부(100%) 보유하고 있습니다.

- 값은 **그 행이 어느 원본 문서에서 왔는지** 구분할 수 있으면 무엇이든 됩니다.
  예: `DOC-001`, `2026-00123-계좌영장-3`, `EP5-030-ibk`
- 파일 단위로 같은 값이어도 되고(문서 1개 = 파일 1개), 행마다 달라도 됩니다(여러 문서 병합 시).
- **이 값이 없으면 나중에 "이 관계는 어느 자료에서 나왔나"에 답할 수 없습니다.** 수사 산출물로
  쓰려면 필요한 정보라, 다른 어떤 추가 컬럼보다 우선입니다.

### 3.2 `bank_cd` — 계좌가 잘못 합쳐지는 문제 (중요)

현행 적재는 **은행코드를 고정값 `999`로 저장**합니다. 그 결과 *은행이 달라도 계좌번호 문자열이 같으면
한 계좌로 합쳐집니다.* V4.8의 계좌 식별자는 `account_no` + `bank_cd` 조합이므로, `bank_cd`를 주시면
이 오병합이 사라집니다.

- 값: 금융결제원 3자리 기관코드 (국민 `004`, 신한 `088`, 카카오뱅크 `090`, 기업 `003` …)
- 코드를 모르시면 `bank`(은행명 원문)만 주셔도 됩니다 — 플랫폼이 코드로 변환합니다.
- **계좌번호 표기(하이픈 유무)는 기관 내부에서 하나로 통일**해 주십시오. 이건 종전과 같습니다.

### 3.3 `channel` — 통화·문자·메신저 구분

V4.8은 연락 관계를 `contacted` 하나로 모으고 **수단을 `channel` 속성으로 구분**합니다.
비어 있으면 전부 음성통화로 간주돼 문자·메신저가 통화 건수에 섞입니다.

- 값: `call`(음성) · `sms`(문자) · `kakao` · `naver` · `telegram` 등
- 문자·메신저는 종료시각이 없으므로 `end_ymdhm`은 비워두십시오.

### 3.4 `psn_id` — 동명이인 분리 (권장)

현행은 **인물을 이름 문자열로만 식별**합니다. 그래서 동명이인은 한 명으로 합쳐지고, 표기가 한 글자만
달라도 다른 사람이 됩니다. `psn_id`(기관 내부 관리번호·비식별 ID 등 무엇이든 일관되면 됨)를 주시면
이 문제가 해소됩니다.

- `psn_id`를 주시면 관계 파일(`tbl_eg_*_poss`, `tbl_eg_case_prsn`)에서도 **같은 `psn_id`로** 참조해 주십시오.
- 주지 않으시면 종전대로 `flnm`(이름)으로 연결합니다 — **이름은 모든 파일에서 완전히 동일한 문자열**이어야 합니다.

> 참고: 당사 2차년도 데이터는 비식별화본이라 인물 ID가 없어 지금도 이름으로 식별하고 있습니다.
> 귀 기관 데이터에 관리번호가 있다면 채워주시는 편이 정확합니다.

### 3.5 `valid_from` / `valid_to` — 명의 변경 이력

같은 전화·계좌의 명의자가 바뀌는 경우를 담기 위한 기간입니다(대포폰·대포통장 추적에 쓰입니다).

- `valid_to`가 비면 "현재까지 유효"로 봅니다.
- 이력이 없으면 두 컬럼 모두 비워두십시오. 종전처럼 동작합니다.

### 3.6 `bsst_addr` — 발신기지국 주소

통화의 발신 기지국 주소를 주시면 **위치 노드(`vt_loc`)로 정규화**해 통화 위치를 조회할 수 있습니다.
(EP3 비식별화 통화 자료에 이 컬럼이 있어 2차년도에 34개 기지국을 적재했습니다.)

- 값은 원문 주소 그대로면 됩니다. 시·도/시·군·구 분해는 플랫폼이 합니다.
- **주소가 없으면 비워두십시오.** 기지국명만으로 위치를 추정하지 않습니다(근거 없는 위치가 됩니다).

### 3.7 `ip_addr` · `brnch_nm` (이체) — 거래 IP와 거래점

은행 제출자료에 거래 IP나 거래점이 있으면 주십시오. IP는 **여러 사건을 잇는 가장 강력한 단서**이고
(2차년도 통합 그래프에서 IP 접속이 15,348건으로 최다), 거래점은 위치 노드로 연결됩니다.

---

## 4. 구조에 관한 질문 — 건별로 줄까, 집계해서 줄까

**건별 원본 그대로 주십시오.** 집계는 플랫폼이 합니다.

V4.8 그래프는 통화·이체를 **쌍당 1개 엣지로 접고** 첫/마지막 시각과 건수·합계를 속성으로 답니다.
예를 들어 `tbl_eg_call`에 홍길동→김영희 통화가 2건 있으면 그래프에는 이렇게 한 줄이 남습니다.

```
(010-1234-5678)-[:contacted {channel:'call', first_dt:'2026-03-11', last_dt:'2026-03-11',
                             call_count:2, total_dur_sec:224, source_id:'DOC-008'}]->(010-9999-0000)
```

**건별 시각은 그래프가 아니라 표준 RDB(`TB_TELNO_CALL_D` 등)가 보관**하므로, 원본을 건별로 주셔야
"3월 11일 14시대 통화" 같은 질의가 가능합니다. 미리 집계해 주시면 그 정보가 사라집니다.

---

## 5. 값 형식 (종전과 동일)

| 항목 | 형식 | 예 |
|---|---|---|
| 날짜 | `YYYY-MM-DD` | `2026-03-11` |
| 일시 | `YYYY-MM-DD HH:MM:SS` | `2026-03-11 14:22:05` |
| 유효기간(`valid_from`·`valid_to`) | 날짜·일시 **둘 다 허용** — 자료에 있는 정밀도 그대로 | 명의변경 `2024-03-01` · IP접속 `2026-03-11 15:02:00` |
| 금액·건수 | 숫자만 (쉼표 허용, 단위문자 불가) | `1500000` 또는 `1,500,000` · `1,500,000원` ✗ |
| 인코딩 | UTF-8 (Excel "CSV UTF-8" 저장 = BOM 포함 허용) | |
| 구분자 | 쉼표. 값에 쉼표가 있으면 `"`로 감쌈 | |
| 빈 값 | 그냥 비움 (`NULL`·`-`·`N/A` 쓰지 마십시오) | |

> **숫자에 단위문자를 넣지 마십시오.** 문자열로 저장되면 "1억 이상" 같은 비교가 **오류 없이 조용히
> 0건**이 됩니다. 당사도 실제로 겪어 뒤늦게 발견한 적이 있습니다.

파일명 규칙·업로드 순서(노드 파일 먼저)·한 데이터셋 일괄 업로드는 **종전 규격 그대로**입니다.

---

## 6. 납품 전 자체 검증

동봉한 `validate_csv_v48.py`로 보내시기 전에 직접 확인하실 수 있습니다. DB 없이 CSV만 봅니다.

```bash
python3 validate_csv_v48.py <CSV들이 있는 폴더>
```

검사: 파일명 인식 · 인코딩/BOM · 필수 컬럼 · 규격 외 컬럼 · 날짜/일시 형식 · 숫자에 섞인 문자 ·
`source_id` 누락 · **파일 간 참조 정합**(관계 파일이 가리키는 인물·전화·계좌가 노드 파일에 있는지) ·
`role`·`se`·`channel` 등 코드값. 문제가 있으면 파일·행·컬럼을 찍어줍니다.

예제 폴더로 돌려보시면 통과 상태가 어떤 모습인지 보실 수 있습니다.

```bash
python3 validate_csv_v48.py examples/
```

---

## 7. 예제 파일 (`examples/`)

16종 모두 **같은 시나리오로 연결**돼 있어, 그대로 적재하면 하나의 작은 사건 그래프가 만들어집니다
(인물 3 · 전화 3 · 계좌 2 · 사건 2 · IP 2 · 계정 2 · 위치 2). 컬럼 채우는 방식의 참고용입니다.

| 예제 | 비고 |
|---|---|
| `tbl_vt_psn.csv` · `tbl_vt_telno.csv` · `tbl_vt_bacnt.csv` | 노드 3종 + 추가 컬럼 |
| `tbl_eg_case.csv` · `tbl_eg_case_prsn.csv` | 사건과 연루자(`role`) |
| `tbl_eg_telno_poss.csv` · `tbl_eg_bactno_poss.csv` | 명의 관계 + 기간(`valid_from/to`) |
| `tbl_eg_call.csv` | 통화 2건·문자 1건으로 `channel` 사용 예 · 기지국 주소 포함 |
| `tbl_eg_rmt.csv` | 이체 2건 · 거래 IP·거래점 포함 |
| `tbl_vt_ip.csv` · `tbl_eg_ip_use.csv` | IP와 사용 주체(`subj_type`=psn/telno/id/bacnt) |
| `tbl_vt_id.csv` · `tbl_eg_id_use.csv` · `tbl_eg_id_msg.csv` | 메신저 계정·소유·대화 |
| `tbl_vt_loc.csv` · `tbl_eg_loc_use.csv` | 기지국·ATM 위치 |

> 예제의 IP는 문서 예시 전용 대역(`203.0.113.0/24`, RFC 5737)이라 실제 호스트와 무관합니다.

---

## 8. 적재하면 만들어지는 그래프 (V4.8)

| 출처 파일 | 노드 | 엣지 |
|---|---|---|
| `tbl_vt_psn` | `vt_psn` | |
| `tbl_vt_telno` | `vt_telno` | |
| `tbl_vt_bacnt` | `vt_bacnt` | |
| `tbl_eg_case` | `vt_case` | |
| `tbl_eg_case_prsn` | | `suspect_in` · `victim_in` · `witness_in` (role별) |
| `tbl_eg_telno_poss` | | `owns_phone`(인물→전화) · `registered_to`(전화→인물) |
| `tbl_eg_bactno_poss` | | `has_account` |
| `tbl_eg_call` | (`vt_loc`) | `contacted` · `located_at` |
| `tbl_eg_rmt` | (`vt_ip`·`vt_loc`) | `transferred_to` · `used_ip` · `located_at` |
| `tbl_vt_ip` / `tbl_eg_ip_use` | `vt_ip` | `used_ip` |
| `tbl_vt_id` / `tbl_eg_id_use` / `tbl_eg_id_msg` | `vt_id` | `uses_id` · `contacted` |
| `tbl_vt_loc` / `tbl_eg_loc_use` | `vt_loc` | `located_at` |

> **종전 규격과의 차이**: 이전에는 통화·이체마다 이벤트 노드(`vt_call`·`vt_transfer`)를 만들고
> `caller`/`callee`/`from_account`/`to_account`로 연결했습니다. 두 방식 모두 V4.8 정의 안에 있어
> **어느 쪽도 규격 위반이 아닙니다.** 다만 당사 2차년도 통합 그래프는 집계 방식(`contacted`·
> `transferred_to`)으로 적재돼 있어, 같은 질의가 동작하려면 통합 플랫폼도 집계 방식으로 맞추는 편이
> 좋습니다. **이 선택은 CSV 규격과 무관합니다** — 어느 쪽이든 위 CSV 그대로 받을 수 있습니다.

---

## 9. 문의

- 규격에 없는 데이터(차량·가상자산·이메일·파일 등)는 헤더 1행을 보내주시면 매핑해 회신합니다.
- 온톨로지 정의 원본·감사 도구는 별도 패키지 `handoff/ontology_v4.8/` 로 전달드렸습니다.
