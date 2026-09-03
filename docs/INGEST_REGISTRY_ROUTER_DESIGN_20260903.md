# 양식 등록부 라우팅 엔진 — 상세 설계 (전처리기 1순위)

> **작성일**: 2026-09-03
> **선행 문서**: `RAW_TO_STANDARD_PREPROCESSOR_GAP_20260903.md`(갭 분석), `UPLOAD_STANDARD_INGEST_DESIGN_20260825.md`(청사진)
> **목표**: `scripts/`에 흩어진 검증된 결정론 파서 9종을 **하나의 등록부 라우팅 엔진**으로 통합해 플랫폼 UI에 연결. 기관 회신 원본을 그대로 업로드 → 자동 인식 → v4.8 온톨로지 그래프.
> **핵심 원칙**: 신규 파서를 만들지 않는다. 기존 파서의 *추출 로직*을 어댑터로 감싸고, *적재/그래프화*는 기존 표준 경로(`rdb_service` → `transfer_data`)로 일원화한다.

---

## 1. 설계 목표와 비목표

**목표**
- 기관 회신 원본(이질적 xlsx/csv/docx/log)을 UI 업로드만으로 v4.8 그래프까지 자동 적재
- 기존 9종 파서 로직 재활용 (재작성 최소화)
- 미지 양식은 수사관 1회 매핑 확정 → 등록부 저장 → 이후 전자동 (쓸수록 좋아짐)
- 실패 행 격리·보고 (silent loss 금지)

**비목표 (이 과제 범위 밖)**
- OCR 트랙(스캔 PDF) — 별도 대형 과제(3순위)
- 비정형 문서 LLM 추출(`batch_doc_to_graph`) — 기존 트랙 유지
- 온톨로지 스키마 변경 — v4.8은 고정 타겟

---

## 2. 아키텍처 개요

```
┌── 업로드 ──┐   ┌───────────── 등록부 라우팅 엔진 ─────────────┐   ┌── 표준 적재 ──┐
│  기관 원본  │   │  ① 지문 추출  → ② 등록부 조회 → ③ 어댑터    │   │  tb_* 표준     │
│ xlsx/csv/  │──▶│  (확장자·시트·   (fingerprint    라우팅·파싱   │──▶│  테이블 적재    │──▶ transfer_data
│ docx/log   │   │   헤더 시그니처)   → format_id)   → 정규화레코드 │   │ (rdb_service)  │      → v4.8 그래프
└────────────┘   │        │                              │        │   └───────────────┘
                 │        │ 미지 지문                     │ 검증 게이트
                 │        ▼                              ▼
                 │   ④ 미분류 큐                    ⑤ 실패행 격리
                 │   (수사관 매핑 확정 → 등록부 저장)   (사유 기록)
                 └──────────────────────────────────────────────┘
```

**단일 중간표현(IR)**: 모든 어댑터는 raw를 `NormalizedRecord` 스트림으로 변환한다. → "무엇을 추출하는가"(어댑터)와 "어디에 쓰는가"(엔진)를 분리.

**적재 백엔드 2원화** (2026-09-03 검토 반영): IR의 목적지는 rtype에 따라 두 갈래다.

| 백엔드 | 대상 rtype | 경로 |
|---|---|---|
| **(a) RDB-경로** | psn·bacnt·telno·case·call·transfer·소유/연루 관계 | 표준테이블 INSERT → `transfer_data` → 그래프 (기존 경로 재사용) |
| **(b) 그래프-직행 (GraphWriter)** | msg(일 집계)·ip(valid_from/to)·id·src, 집계엣지(`transferred_to`·`contacted`·`linked_to`·`registered_to`) | IR → Cypher MERGE 공용 계층 |

> **근거(코드 실측)**: 집계형 엣지(`transferred_to`/`contacted` 등)는 `transfer_data`에 생성 로직이 없고(개별 이벤트 방식만 존재), 표준테이블 적재기는 9개 테이블만 INSERT 하므로 msg/ip/id/src 수용처가 없다. 기존 파서들이 그래프에 직접 MERGE 한 것은 우회가 아니라 **RDB 수용처 부재** 때문 — 이를 GraphWriter 한 계층으로 수렴시킨다(V4.0 메타·provenance·이스케이프 일괄 처리, 파서별 산재 MERGE 제거). 장기적으로는 표준 DDL 정합(P0) 완료 후 (b)의 일부를 (a)로 이관.

---

## 3. 핵심 컴포넌트

### 3.1 지문(Fingerprint) 추출기

파일을 열지 않고 양식을 식별하는 안정적 키. 개인정보(값)는 지문에 넣지 않는다 — **구조만** 사용.

```
fingerprint = sha1(
    ext                                   # '.xlsx' | '.csv' | '.docx' | '.log'
    + '|' + sorted(sheet_names)           # xlsx 시트명 집합 (없으면 '')
    + '|' + sorted(normalized_headers)    # 헤더 컬럼명 정규화(공백/특수문자 제거·소문자) 집합
)[:16]
```

- **헤더 정규화**: 공백·`\xa0`·괄호 제거, 소문자화 (계좌 3양식 편차 흡수의 1차 신호)
- **보조 힌트**(지문 충돌 시 tie-break): 파일명 패턴(정규식), 상단 N행의 "예금주:" 같은 앵커 문자열
- 헤더가 다중행/병합인 경우: 첫 유효 헤더행 자동 탐지(기존 `ingest_receipt_ledger` 로직 재사용)

### 3.2 양식 등록부 (Format Registry)

지문 → 처리 방법의 매핑을 영속 저장. 폐쇄망 자립을 위해 DB 테이블 + 시드 JSON 병행.

```sql
CREATE TABLE ingest_format_registry (
    format_id       VARCHAR(64) PRIMARY KEY,   -- 예: 'fin_txn_v1', 'kakao_log_v1'
    fingerprint     VARCHAR(32) NOT NULL,       -- 3.1 산출값 (충돌 대비 UNIQUE 아님)
    display_name    VARCHAR(200) NOT NULL,      -- '계좌거래내역(금융회신) 3양식'
    adapter_name    VARCHAR(100) NOT NULL,      -- 어댑터 클래스명 (FinTxnAdapter)
    column_mapping  JSONB,                      -- 신양식 사람이 확정한 컬럼→표준필드 매핑
    hint_regex      VARCHAR(300),               -- 파일명/앵커 보조 힌트 (선택)
    status          VARCHAR(20) DEFAULT 'active',-- active | pending | disabled
    created_by      VARCHAR(100),
    created_at      TIMESTAMP DEFAULT now(),
    sample_ref      VARCHAR(300)                -- 대표 샘플 파일 경로/해시 (재현용)
);
CREATE INDEX ix_ifr_fingerprint ON ingest_format_registry(fingerprint);
```

- **시드**: 기존 9종 파서를 초기 등록 (adapter_name만 지정, column_mapping은 어댑터 내장이라 NULL 가능)
- **버전 표기**: `_v1`, `_v2` — 같은 데이터종류의 양식 변형을 별 레코드로 관리

### 3.3 파서 어댑터 인터페이스

기존 파서 로직을 감싸는 공통 플러그인. `app/services/format_adapters/` 아래 배치.

```python
class FormatAdapter:
    name: str                     # 'FinTxnAdapter'
    record_types: list[str]       # 산출 IR 타입: ['bacnt', 'psn', 'transfer', ...]

    def detect(self, ctx: FileContext) -> float:
        """이 어댑터가 처리 가능한 확신도 0.0~1.0.
        지문 매칭 실패(신양식) 시 엔진이 모든 어댑터의 detect 를 호출해 최고 점수 선택."""

    def parse(self, ctx: FileContext, mapping: dict | None) -> Iterator[NormalizedRecord]:
        """raw → 정규화 레코드 스트림. mapping 은 등록부의 column_mapping(있으면).
        그래프 MERGE 하지 않는다 — IR 만 방출."""
```

```python
@dataclass
class NormalizedRecord:
    rtype: str                    # 'bacnt' | 'telno' | 'psn' | 'case' | 'transfer' | 'call' | ...
    key: dict                     # 식별키 (정규화 후) — {'account_no': '...'}
    attrs: dict                   # 속성 — {'bank_nm': '국민', 'dpstr': '...'}
    edges: list[dict] = None      # 관계 — [{'type':'has_account','to_rtype':'psn','to_key':{...}}]
    source_id: str = None         # provenance
    row_no: int = None            # 원본 행번호 (실패격리·감사)
```

**어댑터화 우선순위(1차 4종)**: `FinTxnAdapter`(계좌거래·3양식), `CallRecordAdapter`(통화), `ReceiptLedgerAdapter`(접수내역), `KakaoLogAdapter`(카톡 .log). 각각 기존 `scripts/ingest_account_txn.py`·`ingest_call_records.py`·`ingest_receipt_ledger.py`·`parse_kakao_logs.py`의 **추출부만 발췌**해 `parse()`로 이식(그래프 MERGE 부분 제거).

### 3.4 라우팅 로직

```
1. 지문 추출
2. 등록부 조회(fingerprint):
   - 정확 매치 1건        → 해당 어댑터로 parse (자동)
   - 매치 다수(충돌)      → hint_regex/detect() 로 tie-break, 실패 시 미분류 큐
   - 매치 0건(신양식)     → 모든 어댑터 detect() 실행
                            · 최고점 ≥ 0.7  → 후보 제시 + 수사관 확인 후 등록
                            · 그 외          → 미분류 큐(수동 매핑)
```

### 3.5 검증 게이트 + 실패행 격리

```
- 행 단위 검증: 필수 키 존재, 값 형식(날짜 YYYY-MM-DD[ HH:MM:SS], 계좌/전화 정규화 성공)
- 통과분: 원자 트랜잭션으로 표준테이블 적재 (rdb_service 경로 재사용)
- 실패분: ingest_reject 에 원본행+사유 기록 (버리지 않음)
- 배치 요약: 총행/적재/거부/거부율 → 임계 초과 시 경고
```

```sql
CREATE TABLE ingest_batch (
    batch_id     VARCHAR(64) PRIMARY KEY,
    source_id    VARCHAR(100),
    file_name    VARCHAR(300),
    format_id    VARCHAR(64),
    status       VARCHAR(20),          -- parsed | loaded | partial | failed
    stats        JSONB,               -- {total, loaded, rejected, ...}
    created_at   TIMESTAMP DEFAULT now()
);
CREATE TABLE ingest_reject (
    batch_id     VARCHAR(64),
    row_no       INT,
    raw_row      JSONB,
    reason       VARCHAR(300)
);
```

---

## 4. 기존 코드 통합 지점

| 신규 | 위치 | 역할 |
|---|---|---|
| `IngestRegistryService` | `app/services/ingest_registry_service.py` | 지문·등록부·라우팅·검증 오케스트레이션 |
| 어댑터 | `app/services/format_adapters/*.py` | 기존 파서 추출부 이식 |
| IR 적재기 (a) | `IngestRegistryService._load_records()` | RDB-경로 rtype → 표준테이블 (내부적으로 `rdb_service` 패턴 재사용) |
| **GraphWriter (b)** | `app/services/graph_writer.py` | 그래프-직행 rtype/집계엣지 → Cypher MERGE (V4.0 메타·provenance·이스케이프 일괄; 기존 파서 MERGE부 수렴) |
| 라우트 | `app/routes.py` 또는 신규 `routes_ingest.py` | 업로드/프리뷰/매핑확정/상태 API |

**재활용(수정 없음)**: `rdb_to_graph_service.transfer_data`(표준테이블→v4.8 그래프), `rdb_service.import_predefined_schema_to_rdb`(tbl_* 경로는 그대로 유지 — 등록부는 그 상위 계층).

**출력 계약 정합**: IR의 `rtype`은 `tbl_*` 규격(`docs/csv_templates/`)의 노드/엣지와 1:1 대응. 즉 어댑터는 결국 "기관 원본 → tbl_* 상당의 표준 레코드"를 만드는 것.

---

## 5. API 설계

```
POST /api/ingest/upload
     multipart: file[], source_id, graph_name
     → 각 파일 지문 추출·라우팅. 자동매치면 즉시 적재, 미지면 pending 반환
     ← { batch_id, files:[{name, format_id|null, status, stats}] }

GET  /api/ingest/preview?batch_id=...
     → 파싱 미리보기(상위 N행 IR) + 검증 결과. 적재 전 확인용

POST /api/ingest/mapping/confirm
     { file_ref, adapter_name, column_mapping, display_name }
     → 미분류 양식에 대해 수사관이 매핑 확정 → 등록부 등록 → 재파싱·적재

GET  /api/ingest/status?batch_id=...
     → { status, stats, rejects:[{row_no, reason}] }

POST /api/ingest/to-graph
     { source_id, graph_name }
     → 적재된 표준테이블 → transfer_data 실행 (기존 경로)
```

기존 `/api/v1/pipeline/csv_to_v40_graph`와 공존: 파이프라인은 `tbl_*` 고정양식 전용, 신규 `/api/ingest/*`는 이질적 원본 전용.

---

## 6. 처리 흐름 (엔드투엔드 예시 — 계좌거래내역)

```
1. 수사관이 '금융회신_홍길동.xlsx' 업로드 (source_id=EP3-012)
2. 지문 추출: .xlsx | 시트['거래내역'] | 헤더{거래일시,입금액,지급액,상대계좌,...}
3. 등록부 매치 → format_id='fin_txn_v1' → FinTxnAdapter
4. FinTxnAdapter.parse():
   - 3양식 중 '입금/지급 분리형' 자동 판정 (기존 로직)
   - 계좌 정규화(norm_account), 금액 콤마 제거, 방향 판정
   - NormalizedRecord 방출: bacnt×N, psn×M, transfer(edges: from/to account)
5. 검증 게이트: 날짜·계좌 형식 통과분 적재, 실패행 격리
6. 표준테이블(tb_fin_bacnt, tb_fin_bacnt_dlng, ...) 적재
7. /api/ingest/to-graph → transfer_data → v4.8 그래프(vt_bacnt, vt_transfer, transferred_to)
```

---

## 7. 단계적 구현 로드맵

| 단계 | 범위 | 산출 | 검증 |
|---|---|---|---|
| **P1a** | 어댑터 인터페이스 + IR + 지문 + 등록부 최소구현 + 4종 어댑터 이식(계좌·통화·접수·카톡) | `ingest_registry_service.py`, `format_adapters/` | 4종 원본으로 IR 산출 골든테스트 |
| **P1b** | IR 적재기(a: 표준테이블 / b: GraphWriter) + 검증게이트 + 실패격리 + `/api/ingest/upload,status` | 라우트, `graph_writer.py`, ingest_batch/reject | EP1~3 원본 재적재 → 기존 그래프와 노드/엣지 수 대조 |
| **P1c** | UI 업로드 연결 + `/api/ingest/preview` | index.html 업로드 탭 | 수사관 실사용 |
| **P1d** | human-in-the-loop 매핑(`/mapping/confirm`) + 등록부 영속화 | 매핑 UI | 미지 양식 1회 확정→재사용 |
| **P2** | 나머지 5종 어댑터(070·030·031·043·더치트) + 신양식 자동확장 | 어댑터 추가 | 커버리지 확대 |

**골든테스트 원칙**: 각 어댑터 이식 후, 기존 `scripts/` 파서 결과와 신규 엔진 결과의 **노드/엣지 수·키 집합이 일치**하는지 회귀 대조(동일 원본 입력). 리팩터링 손실 0 보장.

---

## 8. 리스크와 대응

| 리스크 | 대응 |
|---|---|
| **지문 충돌** (다른 양식, 같은 헤더 집합) | hint_regex(파일명/앵커) + detect() 확신도 tie-break, 애매하면 미분류 큐로 안전 강등 |
| **추출부 분리 리팩터링 비용** (기존 파서가 그래프 직접 MERGE) | parse()는 IR만 방출하도록 발췌 — 골든테스트로 동치성 보장. 원본 스크립트는 당분간 병존 |
| **provenance 일관성** | source_id를 배치·레코드·엣지까지 관통(기존 V4.0 메타 규칙 준수) |
| **오매핑 = 증거 오염** | 신양식 자동확정 금지. 확신도 높아도 수사관 확인 필수(human-in-the-loop) |
| **폐쇄망** | 지문·매핑·정규화 전부 결정론. LLM은 미지 헤더 의미 "제안"에만(선택) |
| **부분 적재** | 파일 단위 원자 트랜잭션 + 실패행 격리(기존 rdb_service 원자성 패턴 계승) |
| **search_path public 폴백** — `transfer_data`가 `SET search_path = "{schema}", public`이라 소스 스키마에 없는 테이블 조회가 운영 public 데이터로 조용히 폴백 | 엔진 경유 호출 시 폴백 제거(`SET search_path = "{schema}"`) 또는 쿼리 스키마 명시 접두 — 격리 적재에 운영 데이터 혼입 차단 |
| **집계 재현 불가** — 카카오 일 집계(G9)·valid_from/to 백필 등은 transfer_data가 재현 못 함 | 해당 로직은 어댑터→GraphWriter 경로(b)에 유지. transfer_data 로 강제 이관하지 않음 |

---

## 9. 성공 기준

- EP1~3 기관 회신 원본을 **UI 업로드만으로** v4.8 그래프까지 적재 (CLI 무관)
- 4종 어댑터 골든테스트 통과(기존 파서 대비 노드/엣지 손실 0)
- 미지 양식 1건을 수사관이 매핑 확정 → 등록부 저장 → 동일 양식 재업로드 시 전자동
- 실패행 0건 silent loss (전건 격리·사유 기록)

---

## 부록 — 재활용 대상 파서(추출부 이식원)

| 어댑터 | 이식원 | 산출 IR 타입 |
|---|---|---|
| FinTxnAdapter | `scripts/ingest_account_txn.py` | bacnt, psn, org, transfer |
| CallRecordAdapter | `scripts/ingest_call_records.py` | telno, ip, call |
| ReceiptLedgerAdapter | `scripts/ingest_receipt_ledger.py` | case, psn, bacnt, telno, id |
| KakaoLogAdapter | `scripts/parse_kakao_logs.py` | telno, msg, ip, id |
| (P2) SubscriberAdapter | `scripts/ingest_070_subscriber.py` | telno, psn, ip |
| (P2) SeizedAcctAdapter | `scripts/ingest_030_seized_accounts.py` | bacnt, org, transfer |
| (P2) SubseqAcctAdapter | `scripts/ingest_031_subsequent.py` | bacnt, atm, transfer |
| (P2) BankStdAdapter | `scripts/ingest_043_standard.py` | psn, bacnt |
| (P2) TheCheatAdapter | `scripts/ingest_thecheat_search.py` | bacnt, telno, psn, src |
