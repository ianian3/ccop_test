# 2차년도 통화·이체 → 엘리스 V4.0 온톨로지 적재 계획서 (2026-08-13)

> **기준**: 엘리스 운영본 `52866b3`(온톨로지 **V4.0**). 본 문서는 **구현 전 계획서**(조사 결과)로, 실제 코드는 병합 전략 확정 후 작성.
> 관련: `docs/RDB_GDB_PIPELINE_REVIEW_20260813.md`(파이프라인 갭). ⚠️ V4.0 기준이므로 로컬 v4.6 시간속성(valid_from·이체시각 등)은 **범위 밖**.

---

## 1. 목적·범위
- 2차년도 실데이터의 **통화(g5)·이체(g3)**를 엘리스 V4.0 그래프의 **`vt_call`·`vt_transfer`** + 관계 엣지(`caller/callee`, `from_account/to_account`)로 적재.
- V4.0 기본 노드/엣지만 (v4.6 bitemporal·이체시각 valid_from 등 제외).

---

## 2. 데이터 소스 (확인)

| 도메인 | 소스(`ccop-analysis/data`) | 규모 | 형식 |
|---|---|---|---|
| **이체** | g3_계좌거래내역 = 계좌별 원본 엑셀 **17개** | 김은희 584건·신민우 201·문범수 104 등 | .xlsx (계좌별 구조 상이) |
| **통화** | g5_통화내역 = f038.csv(395)·f039.csv(116)·f040.csv(14)·f036.xls(집계) | ~525건 | .csv/.xls |

⚠️ **계좌별 엑셀 구조가 제각각** (유연 파서 필수):
- 김은희: `거래일자·거래시간·입금금액·지급금액·계좌번호·입출금명·[상대명+코드+상대계좌]`
- 신민우: `거래일·시간·구분(입금/출금)·거래금액(단일)·상대계좌번호`
- 문범수: `거래일자·거래시간·거래구분·입금금액·적요·상대계좌번호` (`\xa0` 혼입)

⚠️ **통화 CSV도 2형식**:
- f038/f039: `발신번호·착신번호·통화시작시간·사용시간(초)·발착구분`
- f040: `발신번호·통화월일·통화시분초·착신번호·통화초(1/10)`

---

## 3. 엘리스 V4.0 요구 스키마 (2경로)

### 3-A. fallback `rdb_*` (권장 — 컬럼 단순)
```
rdb_transfers(trx_id, amount, trx_date, sender_actno, receiver_actno)
  → transfer_data 가 감지 시 vt_transfer + from_account/to_account 생성
rdb_calls(call_id, duration, call_date, caller_no, callee_no)
  → vt_call + caller/callee 생성 (rdb_to_graph_service.py:374·392)
```

### 3-B. KICS 표준 `tb_*` (컬럼 많음)
```
tb_fin_bacnt_dlng(dlng_id, src_bacnt_no, dlng_dt, amount, tgt_bacnt_no, dlng_type)  (:579)
tb_telno_call_dtl(call_id, caller_telno, callee_telno, bgng_dt, duration)           (:610)
```

---

## 4. 컬럼 매핑

### 4.1 이체: g3 → `rdb_transfers`
| rdb_transfers | 2차년도 g3 | 변환 규칙 |
|---|---|---|
| `trx_id` | (생성) | `{계좌}-{순번}` |
| `trx_date` | 거래일자 + 거래시간 | `to_datetime` 결합 |
| `amount` | 입금금액 ∪ 지급금액 ∪ 거래금액 | 존재하는 금액 컬럼 |
| `sender_actno` | 방향 판정 | **지급/출금**이면 본계좌, **입금**이면 상대계좌 |
| `receiver_actno` | 방향 판정 | 지급이면 상대계좌, 입금이면 본계좌 |

- **방향 판정**: 지급금액 notna / 구분='출금' → 지급, 입금금액 notna / 구분='입금' → 입금.
- **상대계좌**: 신민우·문범수는 `상대계좌번호` 컬럼, 김은희는 `[상대명+코드+상대계좌]` 문자열 파싱. 부재 시 `입출금명`(명의)로 대체 → §7 이슈.

### 4.2 통화: g5 → `rdb_calls`
| rdb_calls | 2차년도 g5 | 변환 규칙 |
|---|---|---|
| `call_id` | 순번 | `{파일}-{순번}` |
| `call_date` | 통화시작시간(f038) / 통화월일+시분초(f040) | 형식별 파싱 |
| `duration` | 사용시간(초) / 통화초(1/10 → ÷10) | 초 단위 통일 |
| `caller_no` | 발신번호 | `norm_telno`(선행0 보존) |
| `callee_no` | 착신번호 | `norm_telno` |

---

## 5. 표준화 규칙 (엘리스 52866b3 기준)
- **전화번호**: `norm_telno` — no_hyphen_e164, 숫자만·선행0 보존 (`rdb_service.py` 52866b3). ⚠️ CSV 숫자추론으로 선행0 소실 값은 복원 불가.
- **계좌번호**: `_norm_account` — 대시·공백 제거 (`rdb_to_graph_service.py:33`).
- **일시**: `거래일자+거래시간`, `통화시작시간`, `통화월일+시분초` 각 형식 파싱 → ISO.
- **적재 방식**: 52866b3 **fresh 스테이징**(첫 파일 clear 후 누적) 활용 권장.

---

## 6. 필요 작업 (5단계)
1. **유연 파서** — g3 17엑셀(계좌별 상이 헤더) + g5 2형식 CSV를 흡수하는 컬럼 자동매핑 로더 (기존 `load_transfer_time2.py:extract_all` 패턴 재사용).
2. **정규화** — 계좌/전화 표준화 + 일시 파싱 + 이체 방향 판정.
3. **RDB 적재** — `rdb_transfers`/`rdb_calls`(또는 tb_*) 스테이징 INSERT.
4. **그래프 변환** — `POST /api/rdb/to-graph`(fallback 경로) → vt_transfer/vt_call MERGE.
5. **검증** — 통화망(`caller/callee`)·자금흐름(`from/to_account`) 카운트·샘플 시각화.

---

## 7. 이슈·갭 (사전 인지)
| 이슈 | 내용 | 대응 |
|---|---|---|
| **이체 상대계좌 불완전** | 일부 거래는 상대계좌번호 없이 명의(`입출금명`)만 | 명의자↔계좌 사전 매핑 테이블 구성, 미매칭은 명의 노드로 대체 |
| **provenance 없음** | rdb_* fallback 경로엔 `source_id` 미부여 (설계서 P1 갭) | 적재 후 batch로 source_id 보완 or KICS 경로 사용 |
| **V4.0 한계** | 이체시각 valid_from·통화 시간축(v4.6) 미지원 | 기본 노드만. v4.6 배포 후 재적재 |
| **통화 발착 중복** | f038 발신/착신 양방향 행 | 중복 제거 후 caller/callee 정규화 |
| **파일 구조 상이** | 계좌 17종·통화 2형식 헤더 제각각 | 유연 파서(헤더 탐색 + 컬럼 별칭) 필수 |

---

## 8. 결론 — 최소 작업 경로
**g3/g5 → `rdb_transfers`/`rdb_calls` 변환 → `/api/rdb/to-graph`(rdb fallback)** 가 엘리스 V4.0에서 가장 단순.
KICS 표준(`tb_*`) 경로·v4.6 시간속성은 **온톨로지 병합·배포 이후**로 미룬다.

**참조**: `~/ccop_app/app/services/rdb_to_graph_service.py`(52866b3, :353-395 fallback / :579·610 KICS), `data/sheets_result.json`(g3·g5), `docs/RDB_GDB_PIPELINE_REVIEW_20260813.md`.
