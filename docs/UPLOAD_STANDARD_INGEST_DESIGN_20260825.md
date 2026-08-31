# 데이터 업로드 → 표준 테이블 적재 설계 — 스테이징 + 양식 등록부 + 검증 게이트

> **작성일**: 2026-08-25
> **상태**: 설계안 (구현 전 — P0 표준 테이블 전환 이후 착수 권장)
> **결론 한 줄**: 업로드 입구의 "정해진 테이블" 전제를 버리고, **원본 무손실 스테이징 → 양식 등록부 기반 컬럼 매핑(자동 추천 + 수사관 확정) → 검증 게이트 → 표준 `TB_*` 적재**의 3계층으로 전환한다. 표준화는 시스템이 하고, 수사관은 확인만 한다.

---

## 1. 현황 진단 (실측)

### 1.1 현재 파이프라인
- `routes_api.py:1585` — L1(CSV 업로드) → L2(test_v40 RDB 적재) → L3(매핑) → L4(그래프) → L5(시각화) 통합 실행 존재
- 적재 목적지가 **레거시 고정 스키마**(test_v40 소문자 / public V2 대문자 혼재) — 표준 DDL과 테이블명 정합 0% (P0 과제, `docs/STANDARD_DDL_ALIGNMENT_REVIEW_20260804.md`)
- 입력도 고정 스키마 전제의 CSV — 양식이 다르면 수사관이 사전 수작업 변환 필요

### 1.2 실데이터는 "입구 고정"을 항상 배반한다 (2차년도 실측)
| 원천 | 실측 이질성 |
|---|---|
| 계좌거래내역 (g3, 17파일) | **예금주마다 다른 컬럼 구조 3양식** (김·신·문 계좌: 입금/지급 분리형 · 구분+단일금액형 · `\xa0` 혼입형) |
| 통화내역 (g5, 13파일) | CSV 2형식 (발착구분형 / 통화월일+통화초 1/10형) |
| 카톡 영장회신 로그 (81파일) | 3형식 (착발신 로그 / 친구목록 카드 / 빈 회신) — 2026-08-25 파서 실증 |
| 은행 접속내역 (g4) | MAC 주소 등 기관 고유 컬럼 |

→ 기관·시점마다 회신 양식이 다른 것이 **정상 상태**다. 양식을 강제하는 순간 수작업 변환이 부활한다(i2 방식 회귀).

### 1.3 재활용 가능한 기존 자산
| 자산 | 위치 | 역할 |
|---|---|---|
| `COLUMN_PATTERNS` | `ontology_service.py:2008` | 헤더 별칭 사전 (사건/계좌/전화/IP… → KICS 라벨·속성) |
| `COLUMN_TYPE_TO_RDB` | `ontology_service.py:2175` | 컬럼 타입 → RDB col_map 키 |
| `StandardCodeMapper` | `etl_service.py:15` | 은행·통신사 약어 → 표준 코드 |
| `STANDARD_TABLE_MAP` | `ontology_service.py:143` | 표준 DDL ↔ 레거시 크로스워크 (적재 목적지 SoT) |
| `std_columns` | SoT 각 노드/엣지 정의 | 표준 컬럼 매핑 + 값 변환 규칙 (예: `CALL_HR` HHMMSS→초) |
| `scripts/osint_staging.sql` | 스크립트 | 스테이징 테이블 패턴 선례 |
| P0-1·P1-3 교훈 | 커밋 이력 | silent loss 금지(명시 경고) · 트랜잭션 원자성 |

---

## 2. 문제 정의

1. **입구 고정의 비용** — 양식 불일치 데이터는 수사관 수작업 변환 후에만 업로드 가능 → 병목 + 변환 실수 위험
2. **표준 DDL 미정합** — 현재 적재 목적지가 레거시라, 표준화 적재를 별도로 또 만들면 이중 작업
3. **매핑 지식이 휘발** — 같은 기관의 같은 양식을 매번 다시 해석 (사람 머릿속에만 존재)
4. **실패 행의 침묵** — 형식 오류 행이 조용히 탈락하면 증거 누락 (P0-1과 동일 유형 리스크)

---

## 3. 설계 원칙

1. **원본 무손실** — 업로드 원본(파일+행)은 스테이징에 그대로 보존, `source_id` 발급으로 provenance 사슬 시작
2. **자동은 추천까지, 확정은 수사관** — 컬럼 오매핑 = 증거 오염. sameAs 해소와 동일한 human-in-the-loop 원칙
3. **매핑 지식의 자산화** — 확정된 매핑은 양식 등록부에 저장 → 같은 양식 재등장 시 전자동. 쓸수록 좋아지는 구조
4. **실패는 격리하고 보고** — 통과분 원자 적재 + 실패분 격리 테이블 + 사유. 조용한 유실 금지
5. **출구는 표준 DDL 단일** — 목적지는 `TB_*`(P0 완료 후). `STANDARD_TABLE_MAP`·`std_columns`만 참조(하드코딩 금지)
6. **폐쇄망 자립** — 핵심 경로(지문 매칭·별칭 사전·값 정규식)는 LLM 없이 동작. LLM은 미지 헤더 의미 "제안"에만 선택 사용

---

## 4. 아키텍처

```
[업로드: xlsx/xls/csv/log 등 임의 양식]
        │
        ▼
┌─[1] 스테이징 ────────────────────────────────┐
│ upload_file(파일 메타·해시·source_id)          │  원본 무손실 보존
│ upload_row_raw(행 단위 원문 JSON)              │  재처리 항상 가능
└──────────────────────────────────────────────┘
        │
        ▼
┌─[2] 양식 인식 · 컬럼 매핑 ─────────────────────┐
│ a. 헤더 시그니처(정규화 헤더열 해시)             │
│    → format_registry 조회 → 적중 시 자동 매핑    │
│ b. 미적중: 매핑 추천 엔진                        │
│    · 헤더 별칭(COLUMN_PATTERNS) 매치             │
│    · 값 패턴 매치(샘플 N행: 계좌/전화/IP/일시 정규식)│
│    · (선택) LLM 의미 제안 — 제안 표시만           │
│ c. 확인 UI: 샘플 5행 미리보기 → 수사관 확정        │
│    → format_registry 저장(다음부터 a로 자동)      │
└──────────────────────────────────────────────┘
        │
        ▼
┌─[3] 검증 게이트 → 표준 적재 ───────────────────┐
│ · 타입/필수키 검증 · 코드값 변환(StandardCodeMapper)│
│ · 값 변환 규칙(std_columns: CALL_HR 시분초→초 등)  │
│ · 멱등 키 중복 처리(upsert)                      │
│ 통과 → TB_*(표준) 트랜잭션 원자 적재              │
│ 실패 → upload_quarantine(행+사유)                │
│ 리포트: 적재 n / 격리 m / 사유 집계               │
└──────────────────────────────────────────────┘
        │
        ▼
   기존 L4 그래프 ETL (rdb_to_graph) → L5 시각화
```

### 4.1 스테이징 스키마 (DDL 초안)

```sql
CREATE TABLE upload_file (
    file_id      BIGSERIAL PRIMARY KEY,
    source_id    VARCHAR(200) NOT NULL,      -- vt_src / TB_DATA_SOU_A 연계
    orig_name    VARCHAR(500) NOT NULL,
    sha256       CHAR(64)     NOT NULL,      -- 중복 업로드 감지
    format_id    BIGINT,                     -- format_registry FK (확정 후)
    row_count    INT,
    status       VARCHAR(20)  NOT NULL DEFAULT 'staged',  -- staged|mapped|loaded|partial|failed
    uploaded_by  VARCHAR(100),
    uploaded_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE upload_row_raw (
    file_id      BIGINT REFERENCES upload_file,
    row_no       INT,
    sheet_name   VARCHAR(200),
    raw          JSONB NOT NULL,             -- 헤더:값 원문 그대로
    PRIMARY KEY (file_id, sheet_name, row_no)
);

CREATE TABLE format_registry (
    format_id    BIGSERIAL PRIMARY KEY,
    signature    CHAR(64) UNIQUE NOT NULL,   -- 정규화 헤더열의 해시
    org_hint     VARCHAR(200),               -- 예: '농협 거래내역', 'SKT 통화내역'
    target_table VARCHAR(100) NOT NULL,      -- 표준 TB_* (STANDARD_TABLE_MAP 검증)
    column_map   JSONB NOT NULL,             -- {원천헤더: {std_col, transform}}
    sample_header JSONB,
    confirmed_by VARCHAR(100),               -- 확정 수사관 (감사)
    confirmed_at TIMESTAMPTZ,
    use_count    INT DEFAULT 0
);

CREATE TABLE upload_quarantine (
    file_id      BIGINT,
    row_no       INT,
    reason       VARCHAR(500) NOT NULL,      -- 예: '거래일자 형식 오류(20170332)'
    raw          JSONB NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT now()
);
```

### 4.2 양식 지문(signature) 산출

```
normalize(header) = strip → 소문자 → 공백/괄호 제거 → NFC
signature = sha256( '|'.join(normalize(h) for h in headers) )
```
- 헤더 순서 포함(순서 다르면 다른 양식 — 매핑도 다르므로 안전측)
- 다중 시트 파일은 시트별 지문

### 4.3 매핑 추천 스코어링 (미지 양식)

```
score(원천컬럼 → 표준컬럼) =
    0.6 × 헤더 별칭 매치(COLUMN_PATTERNS: 정확=1, 부분=0.6)
  + 0.4 × 값 패턴 매치율(샘플 50행: 계좌/전화/IP/일시/금액 정규식)
```
- 임계 미달 컬럼은 "미매핑(무시)"으로 표시 — 수사관이 지정하거나 통과
- (선택) LLM: 미달 컬럼의 의미 제안 1줄 — 배지로 표시만, 자동 확정 금지

### 4.4 검증 게이트 규칙

| 검증 | 예 | 실패 처리 |
|---|---|---|
| 타입/형식 | 일시 파싱, 계좌 숫자열 | 행 격리 |
| 필수 키 | 거래내역의 계좌번호·일시 | 행 격리 |
| 값 변환 | `CALL_HR` HHMMSS→초, 은행명→코드 | 변환 후 적재 |
| 멱등 | 파일 sha256 중복, 행 자연키 upsert | 중복 스킵 카운트 |
| 원자성 | 파일 단위 트랜잭션 | 부분 실패 시 전체 롤백 + 격리 사유 |

### 4.5 API·UI 흐름 (초안)

| 단계 | API | UI |
|---|---|---|
| 업로드 | `POST /api/v1/ingest/files` | 드래그앤드롭, 다중 파일 |
| 감지 결과 | `GET /api/v1/ingest/files/{id}/mapping` | 지문 적중 시 "자동 매핑됨(농협 거래내역, 14회 사용)" 배지 / 미지 양식은 추천 매핑 + 샘플 5행 미리보기 |
| 확정 | `POST .../mapping/confirm` | 컬럼별 드롭다운(표준 컬럼), 확정자 기록 |
| 적재·리포트 | `POST .../load` → `GET .../report` | "적재 1,240 / 격리 3 (일시 형식 2·필수키 1) / 중복 12" |

---

## 5. 대안 비교

| | (A) 업로드 템플릿 강제 | (B) LLM 전자동 매핑 | **(C) 스테이징+등록부+확인 (권장)** |
|---|---|---|---|
| 수사관 부담 | 매번 수작업 변환 | 없음 | 신규 양식 1회 확인, 이후 자동 |
| 신뢰성 | 변환 실수 위험 | **오매핑=증거 오염, 감사 불가** | 확정자 기록·재처리 가능 |
| 폐쇄망 | 동작 | LLM 의존 | 핵심 경로 LLM 무관 |
| 지식 축적 | 없음 | 없음 | **양식 등록부 = 자산** |
| RDB 우선 원칙 | 부합 | 위배 소지 | 부합 |

---

## 6. 구현 단계 (P0와 정렬)

- [ ] **S0. 선행 — P0 표준 테이블 전환** (기존 계획 ~1.5주): 적재 목적지 확정. 본 설계의 `target_table`이 여기 의존
- [ ] **S1. 스테이징 스키마** — §4.1 DDL 4테이블 + `upload_file.source_id`의 provenance 연계 (0.5일)
- [ ] **S2. 양식 등록부 + 매핑 추천 엔진** — 지문 매칭, `COLUMN_PATTERNS`+값 정규식 스코어링. 순수 모듈 + 단위테스트(2차년도 실양식 g1~g7 + 계좌 3양식을 픽스처로) (2일)
- [ ] **S3. 검증 게이트 + 표준 적재** — `std_columns` 변환·격리·원자성·리포트 (2일)
- [ ] **S4. UI** — 업로드→감지→확정→리포트 4화면, 기존 L1~L5 흐름에 삽입 (2일)
- [ ] **S5. 검증** — 2차년도 정형 70파일 재적재로 등록부 축적·격리율 측정, 기존 그래프 수치와 대조 (1일)

> 공수 합계 ≈ 7.5일 (P0 제외). S2가 핵심 — 픽스처를 실양식으로 잡으면 완성도가 실측으로 증명됨.

---

## 7. 리스크

| 리스크 | 평가 · 대응 |
|---|---|
| 헤더 없는/병합셀 엑셀 (g7 역조회 회신형) | 지문 불가 → "헤더행 지정" UI 폴백 + 등록부에 헤더행 오프셋 저장 |
| 같은 지문, 다른 의미 (동명 헤더 충돌) | 지문에 시트명 포함 + 등록부 `org_hint` 구분, 확정 시 덮어쓰기 대신 신규 버전 |
| 대용량 (수십만 행) | row_raw JSONB 적재는 COPY 배치, 검증은 스트리밍 |
| 표준 DDL 변경 (DA 협의 진행형) | `target_table`을 `STANDARD_TABLE_MAP` 검증으로 강제 — 크로스워크 갱신 시 등록부 일괄 점검 쿼리 제공 |
| 격리 행 방치 | 리포트에 격리 잔량 노출 + 재처리 API (`재검증 후 적재`) |

---

## 8. 관련 문서·SoT

- 크로스워크 SoT: `docs/STANDARD_DDL_ALIGNMENT_REVIEW_20260804.md` · `ontology_service.py` `STANDARD_TABLE_MAP`/`std_columns`
- 파이프라인 이음새 교훈: `docs/PIPELINE_SEAM 검토(20260804)` — P0-1 silent loss, P1-3 원자성
- 실양식 실측: `docs/Y2_EP_DATASET_DIGEST_20260825.md` (g1~g7·카톡 로그 3형식)
- 스테이징 선례: `scripts/osint_staging.sql`
