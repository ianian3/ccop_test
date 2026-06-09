# CCOP V3.5 핵심 모듈 인수인계 및 개발 가이드

안녕하세요 개발팀, 
현재까지 완성된 **CCOP V3.5 온톨로지 기반 지능형 수사 엔진**의 핵심 코드를 패키징하여 전달해 드립니다. 테스트 코드, 튜닝용 Raw Data, 불필요한 구버전 산출물을 제외하고 **배포/운영에 필수적인 Core 파이썬 로직만 압축**했습니다.

---

## 1. 📂 전달된 핵심 패키지 구조 (`app/` 디렉토리 기반)

본 패키지의 핵심 비즈니스 로직은 `app/services/` (또는 `app/middleware/services/`) 하위에 집중되어 있습니다. 주요 모듈의 역할은 다음과 같습니다.

### 🧠 AI & LLM 에이전트 모듈
* **`ai_service.py`**: 자연어 질의(NL)를 받아 AgensGraph용 Cypher 쿼리로 변환하는 프롬프트 엔지니어링의 핵심입니다. 이번 V3.5에서 신설된 `vt_impersonation` 사칭 노드를 포함한 23노드/52엣지 매핑 규칙과 방향 자동 교정기(`_fix_relation_direction`)가 완벽히 탑재되어 있습니다.
* **`langgraph_agent.py`**: 단일 쿼리를 넘어 멀티턴(Multi-turn) 수사 추론을 수행하는 오케스트레이션 에이전트 로직입니다.

### 📊 데이터 전환 및 ETL 모듈 (RDB $\rightarrow$ Graph)
* **`rdb_to_graph_service.py`**: RDB(PostgreSQL) 기반 수사 원본 데이터를 AgensGraph로 동기화(ETL) 합니다.
* **`rdb_service.py`**: 레거시 DB와의 조회/연동을 담당합니다.

### 🕸️ 온톨로지 엔진 & 지식 그래프 모듈
* **`ontology_service.py`**: CCOP의 POLE 6-Layer 모델링(23개 노드 딕셔너리)을 코드로 정의하고 강제하는 서비스입니다.
* **`graph_service.py`**: AgensGraph 연결 풀링, 읽기/쓰기 커밋을 수행합니다. `eg_used_account` 같은 증거 엣지 확장 로직이 등록되어 있습니다.
* **`subgraph_service.py`**: UI 화면에 시각화(Network.js 등)를 뿌려주기 위해 특정 피의자 기반 2~3-hop 이내의 연관 그래프만 가볍게 서브그래프로 반환해 주는 API 백엔드입니다.

### 🕵️ 추론(Inference) 로직 모듈
* **`relationship_inferencer.py` & `pattern_analyzer.py`**: 명시적으로 DB에 없는 관계(예: 다단계 모집망 `RecruitChainAccomplice`)를 그래프 알고리즘으로 찾아내 가상의 `accomplice_of`(공범) 엣지로 이어주는 데이터 인텔리전스 핵심 로직입니다.

---

## 2. 🚀 V3.5 아키텍처 연동 상태 (100% 동기화 방점)

이번에 전달해 드리는 코드는 **"아키텍처 문서와 파이썬 코드의 정합성이 100% 일치"**하는 상태입니다.

1. **역방향/예외 엣지 허용 처리**: `registered_to` (`Phone->Person`) 등 수사관들이 자주 묻는 '대포폰 명의자 조회' 쿼리가 에러 없이 파싱되도록 AI Service 단에 예외 처리 반영.
2. **이벤트 고립 방지**: `accessed_from/to` 패치를 통해 접속 로그 추적망 복원.
3. **Cypher 생성 품질 확보**: LangGraph 내부 Prompt에 10여 가지 핵심 Cypher 쿼리 변환 예시(Few-shot)가 최신 명세(`related_case`, `mentions_account`)에 맞춰 하드코딩 업데이트되어 있습니다.

추가적인 개발이나 배포 세팅 중 문의 사항이 있으시면 언제든 연락 부탁드립니다. 수고하십시오!
