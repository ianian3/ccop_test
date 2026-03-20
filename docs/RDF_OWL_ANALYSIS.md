# CCOP 시스템을 위한 RDF / OWL 적용 리서치 보고서

이 문서는 현재 CCOP 인텔리전스 시스템이 채택하고 있는 **속성 그래프 (Labeled Property Graph, 이하 LPG - AgensGraph 등)** 모델에 웹 표준 온톨로지 기술인 **RDF (Resource Description Framework)** 및 **OWL (Web Ontology Language)** 체계를 적용할 경우의 개념적 차이, 장단점, 그리고 현실적인 적용 구조에 대한 연구 분석입니다.

---

## 1. 개요 및 구조적 차이 비교

### 1-1. 현행 구조: 속성 그래프 (LPG)
*   **특징:** 노드(Node)와 엣지(Edge/Relationship) 양쪽에 여러 개의 속성(Properties, Key-Value)을 가질 수 있습니다.
*   **질의어:** Cypher, Gremlin.
*   **CCOP 현황:** `vt_bacnt`, `vt_transfer` 등 노드에 계좌번호, 금액, 시간 등을 직관적으로 저장하며, 시각화와 '경로 탐색(Pathfinding)' 연산에 극도로 최적화되어 있습니다.

### 1-2. 타겟 구조: RDF / OWL (시맨틱 웹 기반)
*   **RDF (트리플 구조):** 세상의 모든 모델을 `주어(Subject) - 동사(Predicate) - 목적어/값(Object)`이라는 3원자 세트로 분할하여 저장합니다. (예: `피해자3 - has_account - 110-3333-3333`)
    *   **가장 큰 한계:** **동사(Edge)에 속성을 부여할 수 없습니다.** (예: "1시 5분에 이체했다", "10,000원을 이체했다"라는 속성을 달기 위해 데이터가 기하급수적으로 복잡해지는 [*Reification(구체화)*](https://www.w3.org/TR/rdf11-mt/#reification) 과정을 거치거나 별도의 RDF-star 표준을 써야 함).
*   **OWL (Web Ontology Language):** 단순한 RDF 트리플 위에서 **컴퓨터가 논리적으로 추론(Logical Inference)할 수 있는 수학적 분류와 규칙**을 제공합니다.
    *   예: "A는 B의 공범이다", "B는 C의 공범이다" + "공범 관계는 Transitive(추이적)하다" = (컴퓨터가 스스로) "A는 C의 공범이다" 라는 새로운 엣지를 자동 도출해냅니다.

---

## 2. RDF / OWL 방식을 적용했을 때의 장점과 단점

### ✅ 적용 시 주요 장점 (Pros)

1.  **AI 추론 엔진 (Inference & Reasoning) 도입 가능**
    *   OWL 기반의 Reasoner (Pellet, HermiT 등) 소프트웨어를 연결하면, 하드코딩된 파이썬 스크립트 없이도 "정의된 규칙"만으로 숨겨진 범죄 연관성이나 공범 그룹을 **수학적/논리적으로 자동 유추**해냅니다.
2.  **KICS 및 타 기관 시스템과의 상호 운용성 극대화 (Linked Data)**
    *   경찰청, 검찰청, 금융기관 등 타 시스템 역시 RDF를 기반으로 온톨로지가 구축되어 있다면, `URI`를 맞춰주는 것만으로 별개의 DB 데이터를 복잡한 ETL 변환 없이 거대한 하나의 유기적인 그래프망으로 연결할 수 있습니다.
3.  **스키마리스(Schema-less)보다 강력한 시맨틱 검증**
    *   논리적으로 "계좌(BankAccount)는 사람(Person)의 소유(has_account)일 수 있지만, 사람(Person)이 계좌(BankAccount)의 소유(has_account)일 수는 없다"라는 제약(Domain/Range)을 DB 자체에서 엄격하게 통제할 수 있습니다.

### ❌ 적용 시 주요 단점 (Cons) 및 리스크

1.  **"속성" 표현의 어려움 (LPG와의 충돌)**
    *   LPG 기반인 AgensGraph에서는 `(A)-[:TRANSFER {amount: 50000, date: '2025-06-10'}]->(B)` 로 직관적인 표현이 가능합니다.
    *   RDF/OWL에서는 위 정보를 표현하기 위해 `이체 이벤트`라는 노드를 중간에 억지로 만들고(현재 `vt_transfer` 노드화 방식과 유사하지만 훨씬 더 복잡해짐), 거기에 값들을 RDF 트리플 구조로 하나하나 매달아야(Reification) 하여 쿼리 작성이 기하급수적으로 어려워집니다.
2.  **경로 탐색(Pathfinding/BFS) 성능 하락 우려**
    *   LPG(현행)는 이웃 노드 검색 연산이 메모리 포인터 이동 수준으로 매우 빠릅니다(Index-free adjacency).
    *   반면, 거대한 트리플 스토어(Triple Store)에서 N-hop 최단 경로를 탐색하는 것은 테이블 조인 연산이 연속 발생하여, 자금 추적 같은 대규모 경로 탐색에서 퍼포먼스 이슈가 발생하기 쉽습니다.
3.  **Cypher(개발자 친화적) vs SPARQL(학습 곡선 높음)**
    *   RDF 세계에서는 데이터 질의를 위해 `SPARQL` 이라는 언어를 사용해야 합니다. 기존의 `MATCH (p:Person)` 같은 직관적인 Cypher 쿼리를 모두 버려야 하며 개발진의 높은 러닝커브가 동반됩니다.

---

## 3. CCOP 시스템 적용 방안 (결론 및 리서치 제언)

CCOP는 **조사 시간 단축과 시각화, 경로 분석**이 핵심인 정보 수사 시스템입니다. 따라서, 데이터를 저장하는 물리적 DB를 RDF 저장소(GraphDB, Virtuoso 등)로 100% 교체하는 것은 리스크가 크며, **하이브리드 아키텍처(Hybrid Architecture)**를 채택하는 것이 가장 현대적인 모범 사례입니다.

### 💡 제안하는 아키텍처: « Pragmatic Semantic Approach »

1.  **데이터 저장 및 시각화 (Storage & Query) = 현행 유지 (LPG / AgensGraph)**
    *   자금 흐름 파악, 네트워크 시각화, 최단 경로 분석을 위해 빠르고 직관적인 속성 그래프 구조와 Cypher 쿼리 언어를 100% 유지합니다.
2.  **논리적 정의 및 지식(Knowledge/Schema) 통제 = OWL 설계 적용 (Meta-Level)**
    *   시스템 기저의 데이터 모델링(설계도)을 `Protege`와 같은 도구를 이용해 **OWL 파일(.owl)**로 작성하고 표준화합니다.
    *   이 OWL 룰(Rule)을 기반으로, `ontology_service.py`나 `relationship_inferencer.py` (Rule Engine)에서 Python 로직이 **LPG 그래프의 Cypher 쿼리로 번역하여 주기적으로 역방향 추론(Inference)**을 돌리도록 구현합니다.
3.  **데이터 교환 (Data Exchange) = RDF/JSON-LD 내보내기**
    *   타 기관 전송 또는 KICS API 연계 시, CCOP API가 내부의 LPG 데이터를 **JSON-LD (JSON for Linking Data - 웹 표준 RDF 포맷의 일종)** 형태로 변환(Serialization)하여 서비스함으로써 표준 호환성을 100% 달성합니다.

> **최종 요약:** CCOP 시스템의 데이터베이스 백엔드를 RDF/SPARQL 기반의 Triple Store로 바꿀 필요는 없습니다. 
> 현행 **LPG 플랫폼의 막강한 탐색 성능을 유지**하면서, 외부적으로 드러나는 **온톨로지 규격서와 데이터 교환 포맷, 그리고 내부 추론 엔진의 룰(Rule) 로직 설계에만 OWL 개념(Domain, Range, Transitivity 등)을 차용**하는 것이 가장 강력하고 현실적인 접근 방식입니다.
