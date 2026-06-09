# CCOP v1.0 - Cybercrime Investigation Graph Platform

Text2Cypher 기반 범죄수사 그래프 분석 플랫폼. 자연어 → Cypher 쿼리 변환 → AgensGraph 실행 → 시각화.

## Build & Run

```bash
# 로컬 개발
pip install -r requirements.txt
python run.py  # localhost:5002

# Docker
docker-compose up -d  # app:5001, agensgraph:5432
```

## 환경변수 (.env)

필수: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `OPENAI_API_KEY`
선택: `SLLM_ENDPOINT`, `SLLM_MODEL_NAME` (온프레미스 sLLM 사용 시)

## 테스트

```bash
pytest tests/
pytest tests/test_security.py          # 보안 테스트
pytest tests/ --cov=app --cov-report=html
```

## 핵심 아키텍처

- **Flask Factory + Blueprint**: `app/__init__.py` → routes.py(UI), routes_api.py(API), routes_admin.py(Admin)
- **Service Layer**: `app/middleware/services/` 아래 각 서비스 모듈 (static method 패턴)
- **Cypher 실행**: CypherService가 Cypher → AGE SQL 래핑 (`SELECT * FROM cypher('graph', $$ ... $$)`)
- **LLM**: AIService → OpenAI GPT-4o (기본), sLLM fallback 지원
- **Vector RAG**: ChromaDB + sentence-transformers (법률 문서 RAG)

## 주요 서비스 파일

| 파일 | 역할 |
|------|------|
| `app/middleware/services/ai_service.py` | LLM 연동, 의도 분류, Cypher 생성 |
| `app/middleware/services/graph_service.py` | 노드 검색, 확장, 경로 탐색 |
| `app/middleware/services/etl_service.py` | CSV → 그래프 ETL 파이프라인 |
| `app/middleware/services/ontology_service.py` | KICS 4계층 온톨로지 |
| `app/middleware/services/legal_rag_service.py` | ChromaDB 법률 RAG |
| `app/core/cypher_service.py` | Cypher → AGE SQL 변환 엔진 |

## 코드 스타일

- PEP 8 준수
- 클래스: PascalCase, 함수: snake_case, 상수: UPPER_SNAKE_CASE
- 도메인 로직은 한국어 주석 허용
- SQL injection 방지: graph_path 화이트리스트 검증 (`^[a-zA-Z_][a-zA-Z0-9_]*$`)
- 사용자 입력은 반드시 parameterized query 사용

## 그래프 노드 타입 (KICS 기준)

`vt_flnm`(사건번호), `vt_bacnt`(계좌), `vt_telno`(전화), `vt_ip`(IP), `vt_site`(URL), `vt_atm`(ATM), `vt_file`(파일), `vt_id`(ID), `vt_psn`(인물)

## 모델 학습 (train/)

- LLaMA-Factory + EXAONE-3.5-7.8B-Instruct
- LoRA: `train/train_exaone_lora.yaml` (QLoRA 4bit, RTX 5090 32GB)
- Full: `train/train_exaone_full.yaml`
- 데이터셋: korean_cybercrime_sft (10,143 샘플, ShareGPT 포맷)

## 배포

- Gunicorn: `CPU*2+1` workers, 1000 요청마다 재시작
- Nginx 리버스 프록시 (SSL/TLS)
- Docker 헬스체크: 30초 간격, 5회 재시도
