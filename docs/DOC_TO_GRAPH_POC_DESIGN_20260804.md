# 비정형 수사문서 → 그래프 자동화 PoC 설계

> **작성일**: 2026-08-04
> **목표**: 수사보고서·카톡·영장 등 **비정형 문서를 LLM으로 자동 파싱·추출**해 CCOP 온톨로지(V4.4) 그래프로 적재. i2 iBase의 최대 약점(**수동 입력**)을 AI로 뒤집는 결정적 차별 기능.
> **핵심 원칙**: 신규 코드 최소화 — 파싱·스키마·MERGE·LLM은 **기존 자산 재활용**, 신규는 "LLM 추출" 서비스 하나.

---

## 0. 차별성 — i2 Text Chart vs CCOP

| | i2 iBase (Text Chart) | **CCOP (본 PoC)** |
|---|---|---|
| 문서→엔티티 | 분석가가 **손으로 마크업** | **LLM 자동 추출** |
| 스키마 준수 | 수동 매핑 | **온톨로지 스키마 제약**(할루시네이션 방지) |
| 정규화 | 수동 | 식별자 표준·엔티티 해소 자동 |
| 소요 | 수십 시간/사건 | **수 분/문서** |

## 1. 파이프라인 아키텍처

```
비정형 문서(PDF/hwp/카톡)
   │  ① 파싱      ← scripts/ingest_legal_corpus.py (pypdf, 재활용)
   ▼
페이지 텍스트
   │  ② 청킹      ← legal_rag_service.chunk_text (재활용)
   ▼
청크
   │  ③ LLM 추출  ← 🆕 document_extraction_service (온톨로지 스키마 제약)
   ▼
{entities:[{type,id,props}], relations:[{type,from,to,props}]}
   │  ④ 정규화    ← NODE_ID_STANDARD·norm_telno·LABEL_ALIASES·sameAs (재활용)
   ▼
정규화된 엔티티/관계
   │  ⑤ MERGE 적재 ← rdb_to_graph_service MERGE 패턴 (재활용) + source_id provenance
   ▼
AgensGraph
   │  ⑥ 검증·시각화 ← Cytoscape + 정확도 스팟체크
   ▼
수사 그래프
```

## 2. 단계별 설계

### ① 파싱 (재활용)
- `ingest_legal_corpus.parse_pdf(path)` → `[(page_no, text)]` (pypdf, 지연 import)
- 확장: hwp(hwp5txt), 카톡 txt, docx — 어댑터 추가
- 2차년도 데이터셋이 정확히 이 입력(PDF 수사보고·영장·카톡)

### ② 청킹 (재활용)
- `legal_rag_service.chunk_text(text, size, overlap)` — 긴 문서를 LLM 컨텍스트에 맞게 분할
- 청크별 추출 → 병합 (엔티티 해소 단계에서 중복 통합)

### ③ LLM 추출 🆕 (유일한 신규 서비스 `document_extraction_service.py`)
**온톨로지 스키마 제약 추출** — Text2Cypher와 동일 철학(스키마로 할루시네이션 억제, arXiv 2505.05118):

```
[system]
당신은 수사문서에서 CCOP 온톨로지 스키마에 맞는 엔티티·관계만 추출하는 AI입니다.
반드시 아래 스키마의 노드/엣지 타입만 사용하세요 (스키마 밖 타입 생성 금지).

[스키마]   ← LangGraphAgent._format_schema_b(_POLE_SCHEMA) 재활용
[노드] (vt_psn {name, korn_flnm, ...}) (vt_bacnt {account_no, ...}) ... (25종)
[관계] (vt_psn)-[:has_account]->(vt_bacnt) (vt_telno)-[:contacted]->(vt_telno) ... (66종)

[few-shot 예시] (수사보고 문장 → JSON 2~3개)

[출력 JSON]
{
  "entities": [{"type":"vt_psn","local_id":"e1","props":{"name":"김OO"}}, ...],
  "relations": [{"type":"has_account","from":"e1","to":"e2","props":{"confidence":0.9}}]
}

[user]
{문서 청크}
```

- **모델**: gpt-4o(추출 정확도) 또는 v46(온프레미스). `AIService.get_client` 재활용
- **JSON 강제**: `response_format={"type":"json_object"}`
- **local_id**: 청크 내 임시 ID → ④에서 정식 식별자로 해소

### ④ 정규화·엔티티 해소 (재활용)
- **식별자 표준**: 전화 `norm_telno`(no_hyphen_e164), 계좌 plain_dash, `NODE_ID_STANDARD`
- **타입 검증**: 추출 type이 온톨로지 25노드/66엣지에 있는지 (밖이면 폐기 + 로그)
- **엔티티 해소**: 문서 내/간 동일 실체 통합 — 이름/식별자 매칭 + `sameAs`(review_pending), `LABEL_ALIASES` 활용
- **관계 방향 교정**: `_fix_relation_direction`(ai_service) 재활용

### ⑤ MERGE 적재 (재활용 + provenance)
- `rdb_to_graph_service` MERGE 패턴 재활용:
  `MERGE (n:vt_psn {id:'...'}) ON CREATE SET n = {props}`
- 관계: `MATCH (a),(b) MERGE (a)-[:rel]->(b)`
- **provenance 필수**: 각 노드·엣지에 `source_id`(=vt_src 문서), `reliability_tier`, `confidence`(LLM 추출 신뢰도), `extracted_from`(문서·페이지) → **법정 증거 추적**(#4 무기와 연결)

### ⑥ 검증·시각화
- **정확도**: 문서 1건 gold(수동 라벨) 대비 엔티티/관계 precision·recall
- **무결성**: 온톨로지 스키마 준수(catalog_sync 정신), 고아노드 0
- **시각화**: Cytoscape로 추출 그래프 즉시 표시 (기존 뷰 재활용)

## 3. PoC 최소 범위 (1스프린트)

| 항목 | 범위 |
|---|---|
| 입력 | 2차년도 **수사문서 1건** (예: EP1 접수내역·수사보고 PDF) |
| 파싱·청킹 | 재활용 (pypdf + chunk_text) |
| 추출 | `document_extraction_service` 신규 (gpt-4o, 온톨로지 스키마 제약) |
| 정규화·적재 | 재활용 (norm·MERGE) |
| 검증 | 추출 엔티티/관계 스팟체크 + Cytoscape 표시 |
| **산출** | 문서 → 그래프 자동 생성 데모 (수 분) |

## 4. 검증 메트릭 (확장 시)

- **추출 정확도**: 엔티티 P/R, 관계 P/R (gold 대비)
- **스키마 준수율**: 온톨로지 밖 타입 생성 비율(목표 0%)
- **엔티티 해소 정확도**: 동일 실체 통합 정확도
- **처리 시간**: 문서/그래프 (vs i2 수동 추정)

## 5. 리스크·완화

| 리스크 | 완화 |
|---|---|
| LLM 추출 할루시네이션(없는 엔티티/관계) | 온톨로지 스키마 제약 + ④ 타입 검증 폐기 + confidence 임계 |
| 관계 방향 오류 | `_fix_relation_direction` 재활용 |
| 엔티티 해소 오통합 | 사람/조직 fuzzy는 `sameAs review_pending`(자동 확정 금지) |
| 문서 형식 다양(hwp/카톡) | 파서 어댑터 점진 추가 |
| 민감 수사정보 | 온프레미스 v46 추출(폐쇄망), 감사 로깅 |

## 6. 로드맵

1. **PoC** (본 설계): 문서 1건 → 그래프 (신규 = `document_extraction_service` 하나)
2. **정확도 튜닝**: few-shot·스키마 프롬프트 개선, 추출 A/B (v46 vs gpt-4o)
3. **다형식 파서**: hwp·카톡·docx 어댑터
4. **자동 인사이트 연계**(#2 무기): 추출 그래프 → 중심성/커뮤니티 + XAI 설명
5. **파이프라인 UI**: 문서 업로드 → 추출 미리보기 → 승인 → 적재 (human-in-the-loop)

---

## 부록 — 재활용 자산 매핑

| 단계 | 재활용 파일 | 신규 |
|---|---|---|
| 파싱 | `scripts/ingest_legal_corpus.py` (parse_pdf) | 파서 어댑터(hwp/카톡) |
| 청킹 | `app/services/legal_rag_service.py` (chunk_text) | — |
| 스키마 주입 | `langgraph_agent._format_schema_b` + `_POLE_SCHEMA` | — |
| **추출** | `AIService.get_client` | **`document_extraction_service.py`** |
| 정규화 | `rdb_service.norm_telno`, `NODE_ID_STANDARD`, `LABEL_ALIASES` | 타입 검증기 |
| 적재 | `rdb_to_graph_service` (MERGE 패턴) | provenance 필드 |
| 시각화 | Cytoscape (기존 뷰) | — |

**결론**: 신규 코드는 실질적으로 **`document_extraction_service.py`(LLM 추출) 하나**. 나머지는 CCOP가 이미 가진 파싱·스키마·정규화·MERGE·시각화를 조립하면 되므로, PoC를 **1스프린트**에 만들 수 있다. 이것이 "부품은 이미 다 있다"는 판단의 근거다.
