# raw→표준 전처리기 (v4.8 타겟) — 커버리지 갭 분석

> **작성일**: 2026-09-03
> **과제 재정의**: "온톨로지 v4.8 개발"이 아니라 **"이질적 raw 원천을 v4.8 온톨로지 표준으로 떨어뜨리는 전처리기"** 구축. 온톨로지 v4.8은 이미 완성된 *타겟*(EP1~10 전건 적재·감사 위반 0)이며, 개발 대상은 *입구*이다.
> **결론 한 줄**: 진짜 갭은 "파서가 없어서"가 아니라 **"검증된 결정론 파서 9종이 `scripts/` 일회성 CLI로 흩어져 플랫폼 UI와 분리돼 있어서"**다. 1차 과제는 신규 트랙(OCR 등)이 아니라 **기존 파서를 양식 등록부 엔진으로 통합해 UI에 연결**하는 것.

---

## 1. 과제 재정의

| 구분 | 잘못된 프레이밍 | 올바른 프레이밍 |
|---|---|---|
| 대상 | "온톨로지 v4.8을 개발한다" | "raw→표준 전처리기를 v4.8 타겟으로 만든다" |
| 온톨로지 | 개발 대상 | **완성된 목표(출력 계약)** — v4.7 마감·v4.8 최신, EP1~10 완료 |
| 개발 초점 | 스키마 | **입구(전처리·적재 자동화)** |
| 출력 | 미정 | **이미 확정** — `tbl_*` 표준 CSV → v4.8 그래프 |

전처리기 파이프라인:
```
기관 회신 원본(이질적)  →  [양식 지문 인식 → 파서 라우팅 → 정규화 → 검증]  →  tbl_* 표준 CSV  →  v4.8 온톨로지 그래프
```

---

## 2. 갭 분석 — 3구간

### ✅ 구간 A — 이미 자동화됨 (결정론 파서 존재, 재활용)

실제 기관 회신 양식이 이미 결정론(LLM 무관) 파서로 커버되어 있다.

| raw 양식 | 파서 (`scripts/`) | 생성 노드/엣지 | 양식 편차 처리 |
|---|---|---|---|
| 접수내역·범죄일람표 xlsx (EP1/2) | `ingest_receipt_ledger.py` | vt_case·psn·bacnt·telno·id / has_account·victim_in·eg_used_* | 병합/단일헤더 자동판별, 숨김시트 거부 |
| 더치트 검색확장 xlsx (EP1/2) | `ingest_thecheat_search.py` | vt_bacnt·telno·psn·src / linked_to·sourced_from | 피해금 유/무 컬럼차 대응 |
| 계좌거래내역 금융회신 xlsx (EP3) | `ingest_account_txn.py` | vt_bacnt·psn·org / transferred_to·belongs_to | **3양식 자동판정**(분리형·단일금액형·\xa0혼입) |
| 통화내역 통신회신 csv/xls (EP3) | `ingest_call_records.py` | vt_telno·ip / contacted·used_ip | euc-kr/utf-8/cp949 인코딩 |
| 070 가입자회신 docx (EP3) | `ingest_070_subscriber.py` | vt_telno·psn·ip / registered_to·used_ip | 단일양식, NFC 정규화 |
| 영장계좌 거래내역 다중시트 xlsx (EP5 030) | `ingest_030_seized_accounts.py` | vt_bacnt·org / transferred_to·belongs_to | 시트별 명의 자동추출, 명의오추출 차단 |
| 직후계좌 구조화 xlsx 2종 (EP5 031) | `ingest_031_subsequent.py` | vt_bacnt·atm / transferred_to·sourced_from | 구조화 2종만 |
| 은행별 표준화 xlsx (EP7 043) | `ingest_043_standard.py` | vt_psn·bacnt / has_account·transferred_to | 은행마다 다른 헤더 + "예금주:OOO" 행 |
| 카카오 통신영장 회신 .log (EP6~8) | `parse_kakao_logs.py`, `ingest_kakao_ep6.py` | vt_telno·msg·ip·id / sent/received_msg·used_ip·contacted | **3형식**(착발신·친구목록·빈회신) |
| 데모/OSINT 정형 (CSV/JSON/RDB) | `build_2025_demo_graph.py`, `osint_ingest.py`, `build_osint_v40_graph.py` | 범용 | 고정스키마/자연키 정규화 |
| UI 고정양식 CSV (`tbl_*`) | `rdb_service.import_predefined_schema_to_rdb` | 9종 노드/엣지 | 파일명 매칭 |

**추가 자산**: 출력 계약(`docs/csv_templates/` 규격서 + `reference_loader.py`), 설계 청사진(`UPLOAD_STANDARD_INGEST_DESIGN_20260825.md`).

> 입력 파서 + 출력 포맷 + 설계도가 모두 갖춰져 있다 — 착수 비용이 낮은 핵심 근거.

### ⚠️ 구간 B — 파서는 있으나 "전처리기"로 통합 안 됨 (이 과제의 핵심)

| 갭 | 현황 | 영향 |
|---|---|---|
| **플랫폼 UI 미연결** | UI 업로드는 `tbl_*` 고정양식 CSV만 수신. 실제 회신 원본은 `scripts/` CLI 수동 실행 | 정형 180건이 UI 경로 밖 |
| **양식 등록부 없음** | 9종 파서가 파일명·규칙으로 개별 동작. 지문→라우팅→신양식 1회 매핑·재사용 구조 부재 | 신양식마다 코드 추가 필요 |
| **스테이징·검증게이트·실패행 격리 미구현** | 설계안(P0 이후 착수)에만 존재 | silent loss 위험(P0 교훈) |

### ❌ 구간 C — 완전히 비어 있음 (신규 트랙)

| 미지원 | 규모 | 성격 |
|---|---|---|
| **스캔 PDF 수사서류 (OCR)** | **135건** | 최대 관문. 2차년도 수사보고·영장·공소장 전부 스캔본(표본 10/10 0자). EP1 001·EP2 014/016 미적재 |
| hwp 구형 OLE 본문 | 66건 | `olefile` PrvText(미리보기)만 — 본문 손실 |
| 헤더없는 역조회 회신·기관고유 컬럼(MAC 등) | g4/g7 | 범용 매핑 없음, 등록부 대기 |
| 출입국 정형 | 0건 | 실데이터 미확보(v4.7 스키마만 준비) |
| anb (i2 정답) | 19건 | 대조평가용 전용 파서 없음 |
| EP9/EP10 확정 사실 | — | 정형 없음(PDF) → 사람이 판독해 `ingest_ep9_seed.py`/`ingest_ep910_seed.py`에 하드코딩(수작업 시드) |

---

## 3. 문서 추출 지원 현황 (`app/services/document_extraction_service.py`)

- 지원 포맷: `hwpx`, `docx`, `pdf`, `hwp`, `txt`
  - **pdf**: `pypdf` — **텍스트 레이어만**. 스캔 PDF는 빈 문자열
  - **hwp**: `olefile` PrvText(미리보기) 스트림만 (선택 의존성)
  - **OCR 없음**: 스캔 이미지 PDF/jpg → 텍스트 0 (트랙 D 미구축)

---

## 4. EP 데이터셋 트랙별 인벤토리

출처: `YEAR1_YEAR2_DATA_REVIEW_20260804.md`, `Y2_EP_DATASET_DIGEST_20260825.md`

| 트랙 | 1차년도 | 2차년도 | 합계 | 자동화 상태 |
|---|---|---|---|---|
| **A 정형** (xlsx/xls/csv) | 110 | 70 | **180** | 파서 존재, **UI 트랙 A 미연결**(병목) |
| **B 비정형-즉시** (pdf텍스트/hwpx/docx/txt) | ~60 | ~43 | **~103** | ✅ `batch_doc_to_graph.py` LLM 트랙 |
| **B 비정형-hwp** (olefile) | 56 | 10 | **66** | ⚠️ 설치 시 PrvText만 |
| **C anb 정답** | 17 | 2 | **19** | ⚠️ 전용 파서 없음 |
| **D 이미지/스캔** (OCR) | 57 | **78** | **135** | ❌ **OCR 미구축(최대 관문)** |

---

## 5. 권고 — 우선순위 (커버리지 ÷ 노력)

### 1순위 · 최고 ROI — 등록부 라우팅 엔진 + UI 연결 (구간 B-1,2)
기존 9종 파서를 **양식 등록부 + 라우팅 엔진**으로 감싸 플랫폼 UI에 연결. 기관 회신 원본을 그대로 업로드 → 지문 인식 → 파서 자동 선택 → `tbl_*` 산출 → v4.8 그래프. **신규 파서 개발 없이 정형 180건 병목 해소.** 출력 계약·검증 도구(`reference_loader`)가 이미 있어 즉시 효과.

### 2순위 — human-in-the-loop 매핑 (구간 B, C-일부)
미지원 정형 양식(역조회 회신 헤더없음, 기관고유 컬럼)을 등록부의 수사관 1회 확정 매핑으로 흡수 → 재사용. `UPLOAD_STANDARD_INGEST_DESIGN` 설계안 실체화.

### 3순위 · 무겁고 환각 위험 — OCR 트랙 (구간 C)
스캔 PDF 135건. 최대 관문이나 별도 대형 과제. **RDB 우선·환각 회피 원칙**상 신중히: OCR은 결정론, 의미 해석은 human-in-the-loop로 경계. LLM 자동 확정 금지.

### 보조 — hwp 본문 파서 개선
`olefile` PrvText 한계 극복(본문 스트림 파싱). 중간 난이도.

---

## 6. 설계 원칙 (기존 프로젝트 원칙과 정합)

1. **결정론 우선** — 핵심 경로(지문·매핑·정규화·키판정)는 규칙 기반. 폐쇄망 동작. LLM은 미지 헤더 의미 "제안"에만.
2. **원본 무손실 + 실패행 격리** — silent loss 금지(P0 교훈).
3. **매핑 지식 자산화** — 확정 매핑은 등록부 저장, 쓸수록 좋아지는 구조.
4. **출구는 표준 단일** — `tbl_*`(현행) → 표준 `TB_*`(DDL 정합 P0 완료 후).
5. **자동은 추천까지, 확정은 사람** — 오매핑=증거 오염. sameAs 해소와 동일 원칙.

---

## 부록 — 관련 파일

- 파서: `scripts/ingest_*.py`, `scripts/parse_kakao_logs.py`, `scripts/build_*graph*.py`, `scripts/osint_*.py`
- 적재기: `app/services/rdb_service.py` (`import_predefined_schema_to_rdb`), `app/services/rdb_to_graph_service.py` (`transfer_data`)
- 문서추출: `app/services/document_extraction_service.py`
- 출력 계약: `docs/csv_templates/` (규격서 + `reference_loader.py` + 샘플 CSV 9종)
- 설계 청사진: `docs/UPLOAD_STANDARD_INGEST_DESIGN_20260825.md`
- 데이터셋: `docs/Y2_EP_DATASET_DIGEST_20260825.md`, `docs/YEAR1_YEAR2_DATA_REVIEW_20260804.md`
