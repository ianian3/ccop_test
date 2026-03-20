# CCOP 시맨틱 추론 엔진 (Semantic Inference Engine) 도입 전략 및 룰 설계

LPG(속성 그래프) 기반인 현 CCOP 시스템에 시맨틱 웹의 "추론(Reasoning)" 개념을 차용하여, 하이브리드 형태의 **추론 엔진(Inference Engine)**을 도입할 때 사용할 수 있는 구체적인 시맨틱 룰(Semantic Rule) 패턴들입니다.

이 엔진은 야간 배치(Batch)나 데이터 적재 직후 `relationship_inferencer.py` 같은 모듈을 통해 실행되며, 수사관이 눈치채지 못한 숨겨진 범죄 연관성(새로운 Edge)을 자동으로 생성합니다.

---

## 1. 노드 간의 속성 공유 기반 추론 규칙 (Shared-Entity Rules)

사이버 수사에서 가장 기본적인 공범/조직 추론 방식입니다. 물리적으로 분리된 인물이나 계좌가 동일한 인프라(IP, 전화번호)를 공유할 때 작동합니다.

### 룰 1-1. `same_location` (동일 접속지 기반 연관성)
*   **시맨틱 논리 (OWL 개념화):** `has_ip(Person A, IP x) ^ has_ip(Person B, IP x) -> same_location(Person A, Person B)`
*   **수사적 의미:** 서로 다른 피의자 A와 피의자 B가 **동일한 해외 IP**나 **동일한 Mac 주소**로 접속한 기록이 있다면, 이들은 같은 조직이거나 합숙 중일 확률이 높습니다.
*   **LPG 구현 (Cypher):**
    ```cypher
    MATCH (p1:vt_psn)-[:used_ip]->(ip:vt_ip)<-[:used_ip]-(p2:vt_psn)
    WHERE id(p1) > id(p2)
    MERGE (p1)-[r:same_location {ip: ip.ip_addr, weight: 0.8}]-(p2)
    ```

### 룰 1-2. `shared_device` (대포폰/기기 공유 기반 연관성)
*   **시맨틱 논리:** `owns_phone(Person A, Phone x) ^ owns_phone(Person B, Phone x) -> shared_device(Person A, Person B)`
*   **수사적 의미:** 명의자와 실사용자가 다르거나(대포폰), 하나의 텔레그램 계정을 여러 피의자가 돌려 썼다는 강력한 증거입니다.

---

## 2. 그래프 구조 기반 논리적 추이 규칙 (Transitive & Structural Rules)

시맨틱 추론의 꽃인 "A=B 이고 B=C 이면 A=C 이다" (Transitivity) 와 같은 구조적 논리 규칙입니다.

### 룰 2-1. `accomplice_of` (공범 확률 추론 - Transitive)
*   **시맨틱 논리 (OWL 개념화):** `accomplice_of` 속성을 **Transitive Property**로 선언. 즉, `accomplice_of(A, B) ^ accomplice_of(B, C) -> accomplice_of(A, C)`
*   **수사적 의미:** 점조직으로 운영되는 보이스피싱 하부 조직원들을 하나로 묶어 일망타진하기 위한 연결 고리를 찾습니다.
*   **LPG 구현 (Cypher):** 공범 증거가 N단계 이상 이어질 경우 새로운 `accomplice_of` 엣지를 생성.

### 룰 2-2. `indirect_transfer` (자금 세탁/세탁 계좌 추론 - Chaining)
*   **시맨틱 논리:** `transfer(Account A, Account B) ^ transfer(Account B, Account C) [조건: 시간차 < 10분, 금액 거의 일치] -> indirect_transfer(Account A, Account C)`
*   **수사적 의미:** 전형적인 **자금 세탁(Money Laundering) 및 대포통장 징검다리** 수법입니다. 중간의 B 계좌는 통과점(Pass-through)이며, 종착지인 C 계좌가 진짜 피의자의 은닉 계좌임을 보여주는 추론입니다.

---

## 3. 시계열/패턴 기반 행동 추론 규칙 (Behavioral/Temporal Rules)

단순 연결이 아닌, 특정 시간대(Time-Window)에 반복되는 행동 패턴을 통해 행위자의 의도나 역할을 시맨틱하게 분류하는 고급 룰입니다.

### 룰 3-1. `is_cash_mule` (인출책 역할 추론)
*   **시맨틱 논리:** 반복문자 수신(사기지시) 직후 -> 다수 계좌에서 입금 -> 즉시 ATM 출금(vt_atm) 이벤트가 24시간 내 N회 발생 -> `role: 'Cash Mule'(인출책)` 속성 부여.
*   **수사적 의미:** 그래프 알고리즘(Centrality, In/Out Degree)과 시간차를 분석해, 단순 피의자가 아닌 조직 내 **'수거책/인출책' 역할을 컴퓨터가 자동으로 라벨링**합니다.

### 룰 3-2. `is_headquarters` (총책/콜센터 역할 추론)
*   **시맨틱 논리:** 다수에게 발신(콜/문자) 빈도 높음 ^ 돈은 받기만 하고 출금 기록이 없음 ^ 해외 IP 접속 -> `role: 'Headquarters'(총책)`
*   **수사적 의미:** 조직의 꼭대기, 지시만 내리고 자금이 최종적으로 모이는 핵심 인물을 식별합니다.

---

## 4. 엔진 아키텍처 (어떻게 시스템에 녹여낼 것인가?)

### 단계별 적용 시나리오 (CCOP Inference Engine)

1.  **룰셋 정의서 (Rule Repository):** 
    *   `rules/semantic_rules.yaml` 파일에 위 규칙들을 논리식으로 정의해둡니다. (누구나 룰을 추가/수정할 수 있도록)
2.  **추론 엔진 구동 (Inference Worker):**
    *   `relationship_inferencer.py` 가 백그라운드에서 주기적으로 (또는 새로운 데이터 적재 시 마다) YAML 룰셋을 읽어 **동적 Cypher 쿼리**로 변환하여 AgensGraph를 질의합니다.
3.  **추론 결과 적재 (Virtual Edges):**
    *   찾아낸 새로운 연결선들은 기존의 확정된 증거 엣지(실선)와 구분하기 위해 **추론 엣지(점선, 가상 노드)** 형태로 저장합니다. 엣지에 `confidence_score` (추론 신뢰도, 예: 85%) 와 `reason` (추론 근거, 예: '동일 IP 3회 공유') 을 반드시 기록합니다.
4.  **수사관 UI 제공:**
    *   수사관 화면에 **✨ "새로운 연결고리(공범 가능성)가 3건 발견되었습니다."** 라는 알림창을 띄워줍니다.
    *   수사관이 해당 점선 엣지를 클릭하면, 우측 패널에 *[AI 추론 근거: 피의자A와 B가 06월 10일에 동일한 IP 103.38.1.169로 접속함]* 이라고 설명(Explainable AI)을 보여줍니다. 수사관이 이를 "증거 채택" 누르면 실선으로 바뀝니다.

이러한 **룰 기반 전문가 시스템(Expert System)** 접근 방식이 현재 글로벌 범죄 분석 트렌드에 가장 완벽하게 부합합니다.
