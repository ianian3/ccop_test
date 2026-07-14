# 법률 RAG v2 설계 — Hybrid Search + Reranker + RAGAS 평가

**작성일**: 2026-07-10
**상태**: 1차 구현 완료 (오프라인 검증 통과 — 테스트 34개, 평가 하니스 동작 확인)
**코드**: `app/services/legal_rag_service.py` · API `/api/v1/legal/*` · CLI `scripts/ingest_legal_corpus.py`, `scripts/eval_legal_rag.py`

---

## 1. 배경

### 1.1 v1 (제거됨)과 재구축 이유

v1(2026-01, `LEGAL_RAG_GUIDE.md`)은 ChromaDB + OpenAI 임베딩의 **순수 벡터 검색**이었고, 다음 이유로 제거되었다:
- chromadb/pypdf/sentence-transformers 의존성이 Docker 이미지를 수 GB 비대화 (제거로 7.8GB→~1GB)
- 폐쇄망 환경에서 OpenAI 임베딩 의존이 치명적
- 사용률 대비 유지비 높음

v2는 같은 기능을 **런타임 신규 의존성 0** (numpy 는 pandas 를 통해 기확보)으로 재구축하고, v1에 없던 3가지를 추가한다: **하이브리드 검색, 리랭킹, 정량 평가 체계**.

### 1.2 v1 → v2 비교

| | v1 (제거됨) | **v2 (현행)** |
|---|---|---|
| 검색 | 벡터 단독 (ChromaDB) | **BM25 + 벡터 → RRF 융합** |
| 토크나이저 | (임베딩에 위임) | 자체 한글 bigram (형태소기 의존성 0) |
| 리랭커 | 없음 | LLM listwise 채점 (gpt-4o-mini, 단일 호출) |
| 저장소 | ChromaDB (별도 파일 DB) | **기존 PostgreSQL** (legal_documents/legal_chunks, BYTEA float32) |
| 임베딩 | OpenAI 고정 | OpenAI 호환 플러그블 (`EMBEDDING_ENDPOINT` — 온프레미스 vLLM/TEI 지원) |
| 폐쇄망 | 동작 불가 | **BM25-only 자동 강등** (임베딩 없이도 서비스 지속) |
| 근거 표시 | 출처 파일명 | **조문 단위 인용 [n]** + 비자문 고지 + 거절 가드 |
| 평가 | 없음 | 2계층: 결정적 검색 지표 + RAGAS |
| 신규 의존성 | chromadb, pypdf, s-transformers | **0** (평가용 ragas 는 별도 requirements) |

---

## 2. 아키텍처

```
질문 ─▶ tokenize(한글 bigram) ─▶ BM25 top-20 ─┐
                                              ├─▶ RRF 융합(k=60) ─▶ LLM rerank(0~3, listwise 1회)
     ─▶ 질의 임베딩(OpenAI 호환) ─▶ cosine top-20 ─┘         │            (실패/키 없음 → 융합 순서 유지)
                                                            ▼
                                    top-k 근거 ─▶ 답변 LLM (근거 인용 [n] 강제, 컨텍스트 밖 추측 금지)
                                                            │
                        rerank 전원 0점 / 근거 없음 ─▶ 거절 응답 (재질문 안내)
```

- **인덱스**: 코퍼스가 작으므로(조문 수백~수천) 프로세스 내 인메모리 (gunicorn 워커별 lazy load, DB 가 SoT)
- **강등 경로**: ① 코퍼스 임베딩 없음 → BM25-only ② 질의 임베딩 실패(백엔드 다운) → BM25-only ③ rerank 실패 → RRF 순서 ④ 답변 LLM 없음 → 검색 결과만 반환. **어느 단계가 죽어도 서비스는 응답한다.**

## 3. 설계 결정과 근거

| # | 결정 | 대안 | 근거 |
|---|---|---|---|
| 1 | **자체 BM25(Okapi) + 한글 bigram** | PostgreSQL FTS / 형태소분석기(kiwi 등) | PG 기본 FTS 는 한국어 사전 부재로 품질 낮음. 형태소기는 폐쇄망 반입 의존성 증가. bigram 은 교착어 recall 을 의존성 0으로 확보 — 코퍼스 규모상 인메모리로 충분 |
| 2 | **RRF(k=60) 융합** | 점수 정규화 가중합 | BM25 점수와 cosine 은 스케일이 달라 정규화 가중합은 튜닝 부채. RRF 는 rank 만 사용해 무튜닝·강건 (Cormack et al.) |
| 3 | **LLM listwise 리랭커 (기본)** | cross-encoder (bge-reranker 등) | cross-encoder 가 표준이지만 torch/s-transformers 재도입 = v1 제거 사유 역행. LLM 채점은 기존 OpenAI 클라이언트 재사용·단일 호출. 인터페이스를 분리해 두어 cross-encoder 교체 가능 (로드맵) |
| 4 | **임베딩 BYTEA(float32) in PostgreSQL** | pgvector 확장 | AgensGraph 이미지에 pgvector 빌드 반입은 폐쇄망 리스크. 코퍼스가 작아 인메모리 브루트포스 cosine 이 ANN 인덱스보다 단순·충분. 스케일 시 pgvector 마이그레이션 (로드맵) |
| 5 | **임베딩 백엔드 플러그블** | OpenAI 고정 | `EMBEDDING_ENDPOINT` 로 OpenAI 호환 서버(vLLM embed/TEI) 지정 — sLLM 과 동일한 폐쇄망 패턴. 키·엔드포인트 모두 없으면 BM25-only |
| 6 | **rerank 0점 전원 → 거절** | 항상 답변 | 법률 도메인 환각 리스크 — 근거 없는 답변보다 거절+재질문 안내. v1 프롬프트의 "문서에 없으면 추측 금지" 원칙을 시스템 레벨로 격상 |

## 4. 데이터

- **코퍼스** `data/legal/*.json` — 레코드: `{doc_id, law_name, article_ref, title, content, source, tags[]}`
  - `statutes_core.json` (5건): 리포 내 `docs/test_law.pdf` 발췌 (형법 347/348, 특경법 3조, 환급법 벌칙, 판례 양형)
  - `statutes_extended.json` (11건): 사이버범죄 수사 핵심 조문 **요약** — `(요약)` 표기 + 원문 확인 안내(law.go.kr). ⚠️ 운영 투입 전 공식 원문(국가법령정보센터 Open API)으로 교체할 것
- **골든 평가셋** `data/legal/golden_qa.json` (14문항): `{question, expected_doc_ids(any-of), reference_answer}` — 수사 실무형 질문 (인출책 양형, 대포통장, 지급정지, 가중처벌 기준 등)
- 조문 단위 레코드는 1청크 원칙, 800자 초과 시 문장 경계 분할(80자 오버랩, v1 계승)
- **색인 텍스트 = 법령명+조문번호+제목+본문** — "제347조" 같은 조문 질의 recall 확보

## 5. 평가 — 2계층

### Tier 1: 결정적 검색 지표 (LLM 불필요, CI 가능 수준)

`python scripts/eval_legal_rag.py [--mock-embeddings|--rerank]` — Hit@3 / Hit@5 / MRR@10, 레인별 비교. DB 불필요(인메모리 구축).

**1차 결과 (mock 임베딩 — 배선 검증용, 의미 검색 품질 아님)**:

| 레인 | Hit@3 | Hit@5 | MRR@10 |
|---|---|---|---|
| bm25 | 0.929 | 1.000 | 0.946 |
| vector(mock) | 0.929 | 0.929 | 0.893 |
| **hybrid(RRF)** | **1.000** | **1.000** | 0.929 |

mock 기준으로도 융합이 단일 레인의 실패 문항을 보완함을 확인. **실제 임베딩 수치는 `OPENAI_API_KEY` 설정 후 `--rerank` 포함 재실행해 이 표를 갱신할 것.**

### Tier 2: RAGAS (LLM judge)

`pip install -r requirements-rag-eval.txt && python scripts/eval_legal_rag.py --ragas`
- faithfulness / answer_relevancy / context_precision / context_recall
- answer() 실경로(검색→rerank→생성)를 그대로 사용, ground_truth 는 골든셋 reference_answer
- ragas 는 버전 간 API 변동이 잦아 스크립트가 반환형을 방어적으로 처리 — 검증 후 버전 핀 고정 권장

## 6. 운영

### API (전부 `@require_api_key`)

| 엔드포인트 | 용도 |
|---|---|
| `POST /api/v1/legal/search` | 검색만 — 점수 분해(bm25_rank/vector_rank/rrf/rerank) 포함, 품질 디버깅용 |
| `POST /api/v1/legal/answer` | 근거 인용 답변 `{answer, citations[], disclaimer}` |
| `GET /api/v1/legal/status` | 인덱스/임베딩 백엔드/DB 적재 현황 |

### 설정 (.env)

```
# 미설정 시: OPENAI_API_KEY 로 임베딩 → 그것도 없으면 BM25-only
EMBEDDING_ENDPOINT=http://<온프레미스-임베딩-서버>/v1   # 선택
EMBEDDING_MODEL_NAME=text-embedding-3-small
RAG_RERANK=auto   # auto(OpenAI 키 있으면 on) | on | off
```

### 적재

```bash
python scripts/ingest_legal_corpus.py --dry-run     # DB 없이 검증
python scripts/ingest_legal_corpus.py               # 적재 + 임베딩
python scripts/ingest_legal_corpus.py --no-embed    # 폐쇄망: BM25-only 적재
```

### 폐쇄망 시나리오

1차(현행 가능): `--no-embed` 적재 → BM25-only 서비스. 2차: 온프레미스 임베딩 서버(vLLM `--task embed` 또는 TEI) 기동 → `EMBEDDING_ENDPOINT` 지정 → 재적재로 하이브리드 활성. rerank 는 규칙상 OpenAI 전용이므로 폐쇄망에선 자동 생략(RRF 순서 사용).

## 7. 품질 게이트

- `tests/test_legal_rag.py` **34개** (오프라인, 네트워크 0) — 토크나이저/BM25 수학/RRF 공식/강등 경로/rerank 재정렬·실패 무해화/거절 가드/API 계약. CI `deploy.yml` 게이트에 포함 (총 170 passed + 1 xfailed)

## 8. 한계와 로드맵

1. **코퍼스가 데모 수준** (16건, 일부 요약) → 국가법령정보센터 Open API 로 공식 원문 파이프라인 구축이 최우선
2. 실제 임베딩·rerank 레인의 Tier 1 수치 미측정 (키 필요) → 측정 후 §5 표 갱신
3. cross-encoder 리랭커 옵션 (별도 requirements, 서빙 GPU 여유 시) — LLM 리랭커와 A/B
4. pgvector 마이그레이션 (코퍼스 1만+ 청크 스케일 시)
5. LangGraph 라우터에 `LEGAL` intent 추가 — 자연어 질의창에서 법률 질문 자동 분기 (현재는 별도 API)
6. 판례 코퍼스 확장 (대법원 종합법률정보) + 사건 그래프 연계(그래프에서 확인된 행위 패턴 → 적용 법조 추천)
