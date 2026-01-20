# Legal RAG System - 법률 자문 시스템 개발 문서

> **Version**: 1.0  
> **Last Updated**: 2026-01-20  
> **Author**: CCOP Development Team

---

## 1. 개요

### 1.1 목적
수사관에게 법률 문서 기반의 AI 자문을 제공하는 RAG(Retrieval-Augmented Generation) 시스템.
법률 PDF를 벡터화하여 저장하고, 질문에 대해 관련 법률을 검색하여 GPT로 답변을 생성합니다.

### 1.2 기술 스택

| 구성요소 | 기술 | 버전 |
|----------|------|------|
| Vector Database | ChromaDB | 0.4.22 |
| Embedding Model | OpenAI text-embedding-3-small | - |
| LLM | GPT-4o-mini | - |
| PDF Parser | PyPDF | 3.17.4 |
| Backend | Flask | 3.0.0 |

---

## 2. 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        CCOP Frontend                            │
│                   (법률 자문 모달 UI)                            │
└─────────────────────┬───────────────────────────────────────────┘
                      │ HTTP API
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Flask Backend                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │   routes.py     │  │ legal_rag_      │  │   ai_service   │  │
│  │  /api/legal/*   │──│ service.py      │──│   .py          │  │
│  └─────────────────┘  └────────┬────────┘  └────────────────┘  │
└────────────────────────────────┼────────────────────────────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │   ChromaDB   │    │  OpenAI API  │    │   PyPDF      │
    │ (Vector DB)  │    │ (Embedding)  │    │ (PDF Parse)  │
    │              │    │ (GPT)        │    │              │
    └──────────────┘    └──────────────┘    └──────────────┘
```

---

## 3. 핵심 프로세스

### 3.1 PDF 저장 (Indexing) 플로우

```
1. PDF 업로드
   └─▶ POST /api/legal/upload
   
2. 텍스트 추출
   └─▶ PyPDF로 페이지별 텍스트 추출
   
3. 청킹 (Chunking)
   └─▶ 500자 단위, 50자 오버랩
   └─▶ 문장 끝에서 자르기 최적화
   
4. 임베딩 생성
   └─▶ OpenAI text-embedding-3-small
   └─▶ 배치 처리로 비용 최적화
   └─▶ 1536차원 벡터 생성
   
5. ChromaDB 저장
   └─▶ embeddings + documents + metadata
```

### 3.2 질의응답 (Query) 플로우

```
1. 사용자 질문 입력
   └─▶ POST /api/legal/query
   
2. 질문 임베딩
   └─▶ OpenAI text-embedding-3-small
   └─▶ 동일 모델로 일관성 보장
   
3. 유사도 검색
   └─▶ ChromaDB 코사인 유사도
   └─▶ Top-5 관련 문서 반환
   
4. 컨텍스트 구성
   └─▶ 검색된 문서들을 프롬프트에 포함
   
5. GPT 답변 생성
   └─▶ GPT-4o-mini
   └─▶ 법률 자문 형식으로 응답
```

---

## 4. API 명세

### 4.1 PDF 업로드

```http
POST /api/legal/upload
Content-Type: multipart/form-data

file: [PDF 파일]
```

**Response:**
```json
{
  "status": "success",
  "message": "'형법.pdf' 업로드 완료 (OpenAI 임베딩)",
  "chunks": 25
}
```

### 4.2 법률 질의

```http
POST /api/legal/query
Content-Type: application/json

{
  "question": "보이스피싱 피해자가 300만원 송금했을 때 적용 가능한 법조항은?"
}
```

**Response:**
```json
{
  "status": "success",
  "answer": "📖 관련 법률:\n1. 형법 제347조 (사기) - 10년 이하 징역...\n⚖️ 법적 해석:...\n💡 수사 권고:...",
  "sources": [
    {"content": "형법 제347조 사기...", "source": "형법.pdf"},
    {"content": "전기통신금융사기법...", "source": "특별법.pdf"}
  ]
}
```

### 4.3 문서 목록

```http
GET /api/legal/documents
```

**Response:**
```json
{
  "status": "success",
  "documents": [
    {"name": "형법.pdf", "chunks": 25},
    {"name": "특경법.pdf", "chunks": 12}
  ]
}
```

### 4.4 문서 삭제

```http
POST /api/legal/delete
Content-Type: application/json

{
  "filename": "형법.pdf"
}
```

---

## 5. 핵심 코드 설명

### 5.1 임베딩 생성 (`_get_embeddings_batch`)

```python
@classmethod
def _get_embeddings_batch(cls, texts: List[str]) -> List[List[float]]:
    """OpenAI 배치 임베딩 생성 (비용 효율적)"""
    client = cls.get_openai_client()
    response = client.embeddings.create(
        model=cls.EMBEDDING_MODEL,  # text-embedding-3-small
        input=texts
    )
    # 순서 보장을 위해 index 기준 정렬
    sorted_data = sorted(response.data, key=lambda x: x.index)
    return [item.embedding for item in sorted_data]
```

**특징:**
- 배치 처리로 API 호출 최소화
- 순서 보장을 위한 정렬 처리
- 1536차원 벡터 반환

### 5.2 청킹 (`_chunk_text`)

```python
CHUNK_SIZE = 500   # 문자 수
CHUNK_OVERLAP = 50 # 오버랩

@classmethod
def _chunk_text(cls, text: str) -> List[str]:
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + cls.CHUNK_SIZE
        chunk = text[start:end]
        
        # 문장 끝에서 자르기 시도
        if end < len(text):
            cut_point = max(chunk.rfind('.'), chunk.rfind('\n'))
            if cut_point > cls.CHUNK_SIZE // 2:
                chunk = chunk[:cut_point + 1]
                end = start + cut_point + 1
        
        chunks.append(chunk.strip())
        start = end - cls.CHUNK_OVERLAP
    
    return [c for c in chunks if c]
```

**특징:**
- 500자 단위로 분할
- 50자 오버랩으로 문맥 연결성 유지
- 문장 끝에서 자르기로 의미 보존

### 5.3 유사도 검색 (`query`)

```python
# 질문 임베딩
question_embedding = cls._get_embedding(question)

# ChromaDB 검색 (코사인 유사도)
results = collection.query(
    query_embeddings=[question_embedding],
    n_results=5
)
```

---

## 6. 데이터 저장 구조

### 6.1 ChromaDB 컬렉션

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | string | 문서 고유 ID (예: `abc123_0`) |
| `embedding` | float[1536] | OpenAI 임베딩 벡터 |
| `document` | string | 원본 텍스트 청크 |
| `metadata.source` | string | 원본 파일명 |
| `metadata.chunk_index` | int | 청크 순서 |

### 6.2 저장 경로

```
coop_v1.0/
└── chroma_data/
    └── legal_documents_openai/  # OpenAI 임베딩 컬렉션
        ├── data_level0.bin
        ├── length.bin
        └── ...
```

---

## 7. 비용 분석

### 7.1 OpenAI 임베딩 비용

| 항목 | 단가 | 예시 |
|------|------|------|
| text-embedding-3-small | $0.00002/1K 토큰 | 100페이지 PDF ≈ $0.02 |

### 7.2 GPT-4o-mini 비용

| 항목 | 단가 |
|------|------|
| Input | $0.00015/1K 토큰 |
| Output | $0.0006/1K 토큰 |

---

## 8. UI 사용법

### 8.1 법률 자문 모달 접근
1. 헤더의 **⚖️ 법률 자문** 버튼 클릭
2. 3개 탭 제공: PDF 업로드 / 법률 질의 / 문서 목록

### 8.2 PDF 업로드
1. "PDF 업로드" 탭 선택
2. 법률 PDF 파일 선택
3. "업로드 및 벡터화" 클릭
4. 청크 수 확인

### 8.3 법률 질의
1. "법률 질의" 탭 선택
2. 질문 입력 (예: "보이스피싱 300만원 피해 시 적용 법조항?")
3. "법률 자문 요청" 클릭
4. AI 답변 및 참고 문서 확인

---

## 9. 향후 개선 방향

### 9.1 GDB + Vector DB 통합
- 그래프 노드 선택 시 관련 법률 자동 제안
- 사건 그래프 + 법률 근거 통합 보고서

### 9.2 성능 최적화
- 임베딩 캐싱
- 대용량 PDF 스트리밍 처리

### 9.3 기능 확장
- 판례 검색 전용 컬렉션
- 수사 매뉴얼 통합

---

## 10. 관련 파일

| 파일 | 설명 |
|------|------|
| [legal_rag_service.py](../app/services/legal_rag_service.py) | 핵심 RAG 서비스 |
| [routes.py](../app/routes.py) | API 엔드포인트 (5. 법률 RAG 섹션) |
| [index.html](../app/templates/index.html) | 프론트엔드 UI (법률 자문 모달) |
| [requirements.txt](../requirements.txt) | 의존성 패키지 |
