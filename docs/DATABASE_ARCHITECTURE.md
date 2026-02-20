# CCOP 차세대 통합 DB 아키텍처 설계서 (One-Instance Strategy)

> **Version**: 3.0 (Final)  
> **Date**: 2026-01-28  
> **Design Philosophy**: One Instance, Multi-Model (Zero-Latency)

---

## 1. 아키텍처 설계 철학 (Design Philosophy)

**"One Instance, Multi-Model Strategy"**

과거처럼 RDB, NoSQL, Vector DB를 물리적으로 분리하여 네트워크로 연동하는 방식은 데이터 정합성(Consistency) 깨짐과 네트워크 지연(Latency) 문제를 야기합니다.

우리는 PostgreSQL 생태계의 확장성을 활용하여, 아래 3가지 데이터 모델을 **하나의 메모리 공간**에서 처리하는 **Zero-Latency 아키텍처**를 채택합니다.

1. **Structured (RDB)**: 원천 데이터의 무결성 보장 및 트랜잭션 처리 (System of Record)
2. **Connected (GDB)**: 수사 단서 간의 복잡한 관계(N-Hop) 추적 (Relationship Engine)
3. **Embedded (Vector)**: 텍스트/이미지의 의미론적(Semantic) 검색 지원 (Semantic Engine)

---

## 2. 논리 아키텍처 다이어그램 (Logical Blueprint)

시스템의 데이터 흐름을 4계층(Layer)으로 구조화했습니다.

### [Layer 1] Ingestion Layer (수집 및 변환)
- **Data Sources**: 화이트스캔(OSINT), 경찰청 레거시(KICS), 비정형 파일(PDF 조서)
- **Graphizer (ETL Engine)**: SKAI 자체 개발 모듈
    - Role: RDB의 Row 데이터를 GDB의 Node/Edge로 매핑 변환 (Bulk Loading)
- **Embedding Engine**: sLLM (Solar/Llama-3) 기반
    - Role: 텍스트 데이터를 768~1536차원 벡터로 변환

### [Layer 2] Storage Layer (SKAI Hybrid DBMS)
**Base Engine**: PostgreSQL 14+ (High Availability Cluster)

- **Partition A (RDB): Raw_Data_Store**
    - 수집된 원시 로그 및 시스템 메타데이터 저장
    - 시계열 데이터(트랜잭션)는 월별 파티셔닝(Partitioning) 적용
- **Partition B (GDB): Knowledge_Graph_Store (AgensGraph)**
    - POLE 모델 구현: Person, Object, Location, Event 스키마 적용
    - Index: Graph Traversal을 위한 GIN/GiST 인덱스 최적화
- **Partition C (Vector): Semantic_Store (pgvector)**
    - HNSW Index: 고속 근사치 검색(ANN)을 위한 계층형 인덱스 적용
    - Linkage: Vector ID ↔ Graph Node ID 간 FK(Foreign Key) 연결

### [Layer 3] Intelligence Layer (추론 및 질의)
- **Hybrid Query Processor**:
    - SQL(정형) + Cypher(그래프) + Vector(유사도)를 결합한 복합 쿼리 처리
    - Example: `SELECT * FROM cypher(...) WHERE embedding <-> query_vec < 0.5`
- **Text-to-Cypher**: 자연어 질문을 Cypher 쿼리로 변환하여 실행

### [Layer 4] Service Layer (활용)
- **API Gateway**: KETI(추론), 스톤(시각화), 씨에스리(포털)를 위한 REST/GraphQL API 제공

---

## 3. 상세 데이터 모델링 (Schema Design)

주관기관(한림대)의 온톨로지 설계를 물리적 스키마로 구현합니다.

### A. Graph Model (AgensGraph)

#### Labels (Nodes)
- **:Suspect (용의자)**
  - 속성: `name`, `rrn`, `risk_score`
- **:Account (계좌)**
  - 속성: `bank_code`, `acc_num`, `owner_id`
- **:Phone (전화번호)**
  - 속성: `tel_num`, `carrier`, `imei`

#### Types (Edges)
- **:TRANSFERRED (송금)**
  - 속성: `amount`, `ts` (일시), `method`
- **:CALLED (통화)**
  - 속성: `duration`, `cell_tower_id`
- **:USED_IP (접속)**
  - 속성: `ip_addr`, `device_info`

### B. Vector Model (pgvector)

**Table**: `investigation_embeddings`

| 컬럼명 | 타입 | 설명 |
|--------|------|------|
| `id` | PK | 고유 식별자 |
| `content_text` | TEXT | 진술 조서 원문 |
| `embedding` | VECTOR[1536] | 임베딩 값 (sLLM) |
| `related_node_id` | FK | GDB의 `:Suspect` 또는 `:Event` 노드 ID 참조 |

---

## 4. 핵심 기술적 차별점 (Technical Edge)

이 아키텍처가 경쟁사(Neo4j + Oracle 조합 등) 대비 갖는 우위입니다.

1. **Transactional Integrity (ACID)**
   - 그래프 데이터 수정 시 RDB의 원장 데이터와 단일 트랜잭션으로 묶여 데이터 불일치 원천 차단.

2. **Hybrid Query Performance**
   - "유사한 진술을 한 용의자(Vector)의 자금 흐름(Graph)을 찾아라"와 같은 질의를 네트워크 이동 없이 메모리 내에서 조인(Join) 처리.

3. **Cost Efficiency**
   - 오픈소스 기반(PostgreSQL) 확장으로 라이선스 비용 절감 및 유지보수 포인트 단일화.

---

## 💡 Next Steps (Action Items)

이 설계서는 단순한 그림이 아니라 **'구축 지시서'**입니다.

- **DBA 팀**: "이 아키텍처대로 AgensGraph 위에 pgvector 익스텐션을 올려서 **기능 검증(PoC)**을 이번 주 내로 완료하세요."
- **개발팀**: "RDB의 테이블을 GDB의 노드로 변환하는 Graphizer의 매핑 설정 파일(JSON) 포맷을 정의하세요."
- **대외적으로**: "SKAI는 단순히 DB를 설치하는 것이 아니라, 차세대 수사 시스템의 '두뇌 구조'를 설계했습니다"라고 어필하십시오.
