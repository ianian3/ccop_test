# CCOP (지능형 범죄 수사 시스템) - 온톨로지 변환 자동화 엔진

본 저장소는 CCOP 플랫폼의 핵심 데이터 파이프라인인 **KICS(형사사법정보시스템) 기반 RDB to Graph(AgensGraph) 온톨로지 변환 엔진**의 소스코드를 포함하고 있습니다.

## 📌 주요 기능
관계형 데이터베이스(RDB)나 원시 CSV 파일로 수집된 수사 데이터를 AgensGraph 기반의 지식 그래프(Knowledge Graph) 포맷으로 매핑하고, 수사 도메인(KICS 표준)에 맞게 **표준화(Standardization)** 및 **엔티티 강화(Enrichment)**를 자동으로 수행합니다.

### 1. KICS 온톨로지 표준화 (Standard Code Mapper)
다양한 형태로 수집되는 원시 데이터(약어, 오타 등)를 한국은행 및 표준 약관 코드 체계에 맞춰 자동으로 정제합니다.
* **은행 코드 정규화**: `국민은행`, `KB`, `국민` ➡️ `004`
* **통신사 코드 정규화**: `SKT`, `SK텔레콤`, `SK` ➡️ `01`
* **해시 알고리즘 정규화**: `md5`, `SHA-1`, `sha256` ➡️ `MD5`, `SHA1`, `SHA256`

### 2. 동적 그래프 라벨링 및 관계 추론 (Ontology Service)
* `app/services/ontology_service.py`를 통해 데이터의 속성을 분석하고, 최적의 노드 라벨(`vt_psn`, `vt_bacnt`, `vt_telno` 등)을 실시간으로 추론합니다.
* 노드 간의 숨겨진 연관성(예: 특정 사건에 연루된 피의자들의 공통 접속 IP)을 추적하여 자동으로 엣지(Edge)를 생성하고 가중치를 부여합니다.

---

## 📁 디렉토리 및 핵심 아키텍처 (Directory Structure)

```text
skai-vm/
├── app/
│   └── services/
│       ├── etl_service.py            # 고속 Batch 데이터 적재 및 GIN 인덱스 자동 생성 모듈
│       ├── schema_mapper.py          # LLM 구조 기반 데이터 스키마 자동 인식 모듈
│       ├── ontology_service.py       # 노드/엣지 동적 설계 및 KICS 확장 메타데이터 주입
│       └── rdb_to_graph_service.py   # RDB 데이터를 Graph 기반으로 치환하는 주력 서비스 엔진
├── tests/
│   └── verify_standardization.py     # 표준화 룰셋(StandardCodeMapper) 단위 검증 스크립트
└── README.md                         # 현재 문서
```

---

## ⚙️ 아키텍처 상세 가이드

### `app/services/etl_service.py`
이 모듈 내부에 위치한 `StandardCodeMapper` 클래스는 AI가 Cypher 쿼리를 만들 때나 데이터를 적재할 때 데이터 무결성을 보장하는 가장 중요한 방어벽 역할을 합니다. `auto_enrich` 메서드를 호출하면 지정된 라벨(예: `vt_bacnt`)에 맞춰 필요한 표준 코드를 엔티티 Properties 내부에 자동으로 끼워 넣습니다.

### `app/services/rdb_to_graph_service.py`
거대한 테이블 형태의 RDB 수사 데이터를 청크(Chunk) 단위로 매핑하여 AgensGraph 엔진으로 밀어 넣는 파이프라인의 중심입니다. `SchemaMapper`의 결과값을 받아 Action 노드와 Entity 노드를 분리하여 생성합니다.

---

## 🚀 시작하기 및 테스트 (Getting Started)

본 파이프라인의 독립성 및 표준화 룰셋을 검증하고 싶으시다면, 제공된 단위 테스트 스크립트를 실행해 보십시오.

```bash
# 파이썬 환경에서 표준화 로직 작동 확인
python tests/verify_standardization.py
```

### 💡 (참고) AI Text-to-Cypher 자동 변환 연동
해당 온톨로지 데이터베이스 구축 스크립트는 CCOP의 "자연어 기반 Cypher 자동 변환(Text-to-Cypher) 모델"과 연결되어 작동하도록 설계되었습니다. 백엔드에서 사용자 질의가 들어오면, 이 시스템에서 정의한 KICS 코드가 프롬프트에 자동으로 치환되어 100% 문법이 호환되는 쿼리가 생성됩니다.

---
**Maintainer:** CCOP AI R&D Team
