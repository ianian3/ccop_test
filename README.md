# CCOP v1.0 - Graph-based Investigation Platform

AgensGraph 기반 사기 사건 분석 및 시각화 플랫폼입니다. CSV 데이터를 그래프 데이터베이스로 변환하고, AI 기반 자연어 쿼리와 시각적 탐색을 통해 복잡한 관계를 분석합니다.

## 🌟 주요 기능

### 1. **그래프 시각화**
- 💡 **노드 검색**: 키워드로 접수번호, 전화번호, 계좌번호 등 다양한 노드 검색
- 🔍 **노드 확장**: 선택한 노드와 연결된 이웃 노드 탐색
- 🛤️ **경로 찾기**: 두 노드 간 최단 경로 시각화
- 🎨 **자동 타입 분류**: 8가지 노드 타입별 고유 아이콘 및 색상 자동 할당

### 2. **AI 지원 쿼리**
- 🤖 **자연어 쿼리**: "전화번호 010-1234-5678과 연결된 모든 계좌 찾아줘"
- 📊 **RAG 기반 분석**: GraphRAG를 통한 심층 보고서 생성
- 💬 **대화형 인터페이스**: OpenAI GPT 기반 쿼리 이해 및 분석

### 3. **데이터 ETL**
- 📤 **CSV 업로드**: 다양한 포맷의 CSV 파일 지원
- 🧠 **AI 매핑 제안**: 컬럼을 자동으로 노드/엣지 속성으로 매핑 제안
- 🗂️ **유연한 스키마**: 커스텀 속성 키로 노드 타입 자동 분류

### 4. **서브그래프 관리**
- 🔖 **일부 그래프 저장**: 현재 화면의 노드/엣지를 새로운 서브그래프로 저장
- 🗑️ **그래프 초기화**: 전체 그래프 데이터 삭제

## 🏗️ 프로젝트 구조

```
coop_v1.0/
├── app/
│   ├── __init__.py              # Flask 앱 팩토리 패턴
│   ├── routes.py                # 웹 UI 라우트
│   ├── routes_api.py            # REST API v1 엔드포인트
│   ├── routes_admin.py          # 관리자 라우트
│   ├── database.py              # DB 연결 관리
│   ├── core/
│   │   └── cypher_service.py    # Apache AGE Cypher 실행기
│   ├── middleware/
│   │   └── api_auth.py          # API 키 인증 미들웨어
│   ├── models/
│   │   └── api_key.py           # API 키 관리 모델
│   ├── services/
│   │   ├── ai_service.py        # OpenAI GPT 통합
│   │   ├── graph_service.py     # 그래프 검색/확장/경로
│   │   ├── etl_service.py       # CSV 데이터 ETL
│   │   ├── ontology_service.py  # KICS 기반 4-Layer 온톨로지
│   │   ├── pattern_library.py   # 5대 사이버 범죄 패턴
│   │   ├── pattern_analyzer.py  # 범죄 패턴 분석 엔진
│   │   ├── evidence_analyzer.py # 증거 완성도 분석
│   │   ├── legal_rag_service.py # 법률 RAG (ChromaDB)
│   │   ├── schema_mapper.py     # LLM 스키마 자동 매핑
│   │   ├── relationship_inferencer.py # 관계 추론 서비스
│   │   ├── graph_context_extractor.py # 그래프 맥락 추출
│   │   └── subgraph_service.py  # 서브그래프 관리
│   └── templates/
│       └── index.html           # 웹 UI (Cytoscape.js, 다크 모드)
├── docs/                         # 기술 문서
│   ├── ONTOLOGY_GUIDE.md        # KICS 온톨로지 가이드
│   ├── KICS_ONTOLOGY_MAPPING.md # KICS 매핑 정의서
│   ├── KICS_CYBER_CRIME_STANDARD.md # 범죄 유형별 표준
│   ├── API_GUIDE.md             # API 사용 가이드
│   └── ...
├── scripts/
│   └── init.sql                 # RDB + GDB + Vector 통합 스키마
├── tests/
│   └── data/                    # 테스트용 CSV 데이터
├── config.py                    # 환경 설정
├── run.py                       # Flask 서버 실행
├── docker-compose.yml           # Docker 컨테이너 설정
├── Dockerfile                   # 앱 컨테이너 빌드
└── requirements.txt             # Python 의존성
```


## 📦 설치 및 실행

### 1. 환경 설정

```bash
# 1. Python 가상환경 생성 (권장)
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 의존성 설치
pip install flask psycopg2-binary pandas python-dotenv openai

# 3. 환경 변수 설정
cp .env.example .env  # .env 파일 생성 후 아래 내용 입력
```

### 2. `.env` 파일 설정

```env
# PostgreSQL/AgensGraph 설정
DB_NAME=ccopdb
DB_USER=ccop
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=5432

# OpenAI API 키 (AI 쿼리 사용 시 필수)
OPENAI_API_KEY=sk-...
```

### 3. AgensGraph 설치 및 실행

AgensGraph는 PostgreSQL 기반 그래프 데이터베이스입니다.

```bash
# AgensGraph 설치 (macOS 예시)
# 공식 문서: https://bitnine.net/agensgraph/

# 데이터베이스 및 사용자 생성
createdb ccopdb
psql -d ccopdb -c "CREATE USER ccop WITH PASSWORD 'your_password';"
psql -d ccopdb -c "GRANT ALL PRIVILEGES ON DATABASE ccopdb TO ccop;"
```

### 4. 서버 실행

```bash
python run.py
```

브라우저에서 `http://localhost:5001` 접속

## 🎯 노드 타입 분류 시스템

AgensGraph는 KICS 컬럼 속성을 기반으로 **8가지 노드 타입**을 자동 분류합니다:

| 타입 | Label | 속성 키 예시 | 아이콘 | 색상 |
|------|-------|--------------|--------|------|
| 접수번호 | `vt_flnm` | flnm | 👤 person | 🟠 주황색 |
| 계좌번호 | `vt_bacnt` | actno, bank, account | 💰 account | 🟡 노란색 |
| 사이트 | `vt_site` | site, url, domain | 🌐 site | 🟢 초록색 |
| 전화번호 | `vt_telno` | telno, phone | 📱 phone | 🔵 파란색 |
| IP 주소 | `vt_ip` | ip, ip_addr, ipaddr | 🌐 ip | 🟣 분홍색 |
| ATM | `vt_atm` | atm, atm_id | 🏧 atm | 🟡 밝은 노란색 |
| 파일명 | `vt_file` | file, filename | 📄 person | 🟣 보라색 |
| ID | `vt_id` | id, user_id, userid | 🆔 person | 🟥 연한 빨강 |

자세한 내용은 [NODE_LABELS_GUIDE.md](NODE_LABELS_GUIDE.md)를 참고하세요.

## 📊 사용 예시

### 1. CSV 데이터 업로드

```csv
접수번호,사기범전화,피해자계좌,피싱사이트
2024-001,010-1234-5678,110-123-456789,https://fake-bank.com
2024-002,010-9876-5432,110-987-654321,https://phishing.com
```

**매핑 설정:**
- Source: `접수번호` → 속성 키: `flnm` (vt_flnm)
- Target: `사기범전화` → 속성 키: `telno` (vt_telno)
- 추가 속성:
  - `피해자계좌` → Target 속성: `actno` (vt_bacnt)
  - `피싱사이트` → Target 속성: `site` (vt_site)

### 2. 자연어 쿼리

```
"전화번호 010-1234-5678과 연결된 모든 계좌를 찾아줘"
"접수번호 2024-001과 관련된 모든 IP 주소 보여줘"
"피싱사이트 fake-bank.com과 연결된 사건들 분석해줘"
```

### 3. Python 스크립트로 데이터 확인

```python
# 노드 확인
python show_nodes.py

# 계좌번호 중복 확인
python check_bacnt.py

# 그래프 구조 검증
python check_graph_structure.py
```

## 🛠️ API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/search?keyword={keyword}&graph_path={path}` | 키워드로 노드 검색 |
| `GET` | `/api/expand?id={node_id}&graph_path={path}` | 노드 확장 |
| `POST` | `/api/path` | 최단 경로 찾기 |
| `POST` | `/api/query/ai` | AI 자연어 쿼리 (빠른 조회) |
| `POST` | `/api/query/rag` | RAG 기반 심층 분석 |
| `POST` | `/api/etl/ai-suggest` | CSV 컬럼 매핑 AI 제안 |
| `POST` | `/api/etl/import` | CSV 데이터 임포트 |
| `POST` | `/api/graph/clear` | 그래프 초기화 |

## 🧪 디버깅 유틸리티

```bash
# AgensGraph 연결 테스트
python debug_agensgraph.py

# ETL 프로세스 디버깅
python debug_etl.py

# 노드 확장 로직 테스트
python debug_expand.py

# 중복 노드 체크
python check_duplicates.py

# 엣지 연결 확인
python check_edges.py
```

## 🔑 핵심 기술 스택

- **Backend**: Flask (Python 3.8+)
- **Database**: AgensGraph (PostgreSQL + Graph Extension)
- **Frontend**: HTML5, JavaScript, Cytoscape.js
- **AI**: OpenAI GPT-4 (자연어 쿼리, RAG)
- **Data Processing**: Pandas

## 📝 라이선스

개인 프로젝트용

## 👨‍💻 개발자

Ian Kwon (ianian3)

## 🙏 참고 자료

- [AgensGraph 공식 문서](https://bitnine.net/agensgraph/)
- [Cytoscape.js](https://js.cytoscape.org/)
- [OpenAI API](https://platform.openai.com/docs/)
