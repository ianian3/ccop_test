# CCOP 특허 후보 조사 — 2026-09-11

> 조사 범위: 이 저장소에 **실제로 구현돼 동작하는** 기제만. 아이디어 단계는 §4에 분리.
> 선행기술 조사는 공개 검색(Google Patents·USPTO·arXiv) 기준 1차 스크리닝이며, **변리사 정식
> 선행조사를 대체하지 않는다.**

---

## 0. 먼저 — 기한이 걸려 있습니다 🔴

**`github.com/ianian3/ccop_test` 가 PUBLIC 이고, 후보 기제 전부가 이미 공개돼 있습니다.**

| 기제 | 최초 공개 커밋 | 공개일 |
|---|---|---|
| 값 환각 방어 · 2-hop 브리지 · 앵커 이웃 조회 · 평가 무결성 | `a04770c` | **2026-09-03** |
| 결정론 파서 · 통합그래프 병합 · OSINT 엔티티해소 | `c1e4805` `3bc09a4` | **2026-08-31** |
| 엔진 크래시 탐지·회피 재작성 | `6d6015c` `7bf1752` | 2026-09-08 |

공개 여부는 `git merge-base --is-ancestor <커밋> origin/dev` 로 확인했고, 위 5개 커밋 전부
공개 저장소에 올라가 있습니다(`langgraph_agent.py`·`build_integrated_graph.py`·
`osint_entity_resolution.py` 모두 원격에 존재).

### 그래서 어떻게 되나

- **한국**: 특허법 제30조 **공지예외 적용** 주장 가능 — 자기 공개일로부터 **12개월 내 출원**.
  출원서에 취지를 기재하고 증명서류를 제출해야 합니다.
  → **실질 기한: 2027-08-31** (가장 이른 공개일 기준)
- **미국**: 35 U.S.C. §102(b)(1) 1년 유예 — 동일하게 2027-08-31 전후
- **유럽(EPO)**: 유예가 사실상 없습니다(국제박람회·권리남용 등 예외만). **EP 출원은 이미 곤란**
- **PCT**: 한국 출원을 기초로 우선권 주장은 가능하나, EP 단계에서 위 문제가 그대로 드러납니다

### 지금 해야 할 조치 (우선순위 순)

1. **저장소를 Private 로 전환** — 추가 공개를 멈추는 것이 먼저입니다. 이미 공개된 것은 되돌릴 수
   없지만(포크·캐시·아카이브), 앞으로 출원할 개량 발명의 신규성은 지킬 수 있습니다.
2. **공개 이력 증거 보존** — 공지예외 주장에 커밋 해시·시각·작성자 증명이 필요합니다.
   `git log` 와 GitHub 커밋 URL을 캡처해 보관하십시오.
3. **미공개 개량분을 먼저 출원** — 이번 주 작업한 `load_csv_to_graph.py`(집계 적재기)와
   `handoff/` 패키지는 **아직 미공개**입니다. 여기에 개량 청구항을 얹는 편이 안전합니다.
4. **과제 귀속 확인** — 경찰청 R&D 성과물이면 협약에 따라 **국가·주관기관 공동출원 또는 통보
   의무**가 있을 수 있습니다. 단독 출원 전 협약서 확인이 필수입니다.

---

## 1. 후보 요약

| # | 후보 | 신규성 리스크 | 사업 가치 | 판정 |
|---|---|:---:|:---:|---|
| **A** | **위장계정 → 실사용자 결정론적 역추적** (IP 매개 + 시간구간 교차) | 낮음 | 높음 | **1순위 출원** |
| **B** | **출처 수 기반 단서 순위화** (교차사건 병합 + `ep_count`) | 낮음 | 높음 | **A와 묶어 출원** |
| C | 0건 자동복구 — **중간 라벨 합성 2-hop 브리지** | 중간 | 높음 | 2순위 (청구범위 축소) |
| D | **평가 무결성 계측** (보강행 분리 + 변조 탐지) | 낮음 | 중간 | 3순위 |
| E | 엔진 취약질의 정적탐지 + 의미보존 재작성 | 중간~높음 | 중간 | 4순위 (회피설계 필요) |
| F | 값 환각 검증 (질문∩DB 리터럴 대조) | 높음 | 중간 | 보류 |
| G | 집계 엣지 + bitemporal 2계층 | 높음 | 낮음 | 출원 부적합 |
| H | 온톨로지 정합 감사 자동화 | 높음 | 낮음 | 출원 부적합 |
| I | 학습–추론 프롬프트 정합 / 스키마별 분기 | 높음 | 낮음 | 출원 부적합 |

---

## 2. 1~3순위 상세

### A. 위장계정 → 실사용자 결정론적 역추적 — **1순위**

**무엇** — 메신저·포털 계정으로 위장한 피의자의 실사용자를 확정한다. 계정의 프로필·행태가 아니라
**압수자료의 IP 접속기록을 매개**로 계정↔인물을 역연결한다.

**구현** — `scripts/osint_entity_resolution.py`, EP7 처리 결과.
실증: IP 역조회로 특정한 62명·40명이 수사기록의 64명·40명과 일치.

**기술 구성**
1. 압수자료에서 `(계정, IP, 접속시각)`과 `(인물, IP, 점유구간)`을 각각 추출해 그래프에 적재
2. 계정 접속시각이 인물 IP 점유구간에 **포함되는** 쌍만 후보로 채택 (시간구간 교차)
3. 동일 IP를 **다수 사건에서 공유**하는 경우(콜센터·VPN 등 기반시설) 후보에서 배제하거나 가중치를
   낮춤 — 오연결의 주된 원인을 구조적으로 차단
4. LLM·확률모델 없이 결정론적으로 산출 → 결과가 재현되고 근거를 문서까지 추적 가능

**선행기술 대비 차별점**

| 선행 | 접근 | 우리와 다른 점 |
|---|---|---|
| [US8484744](https://patents.google.com/patent/US8484744) · [US8225413](https://patents.google.com/patent/US8225413) (Detecting impersonation on a social network) | 프로필 텍스트·이미지 유사도 | 우리는 유사도를 쓰지 않음. 접속 기록의 물리 식별자만 |
| [US10320811B1](https://patents.google.com/patent/US10320811B1) | 계정명·신원정보 일치 탐지 | 동일 인물 판정이 아니라 **제3자 실사용자 특정** |
| [US20140317736A1](https://patents.google.com/patent/US20140317736A1) | 소셜그래프 신뢰값 power iteration | 확률·반복계산 없음. 결정론 |

→ 기존은 모두 **플랫폼 내부 데이터로 가짜계정을 판별**하는 것이고, 우리는 **수사기관이 확보한
여러 출처의 압수자료를 교차**해 실사용자를 지목합니다. 목적·입력·판정방식이 다릅니다.

**청구항 골격(초안)**
```
[독립항] 위장 계정의 실사용자 식별 방법으로서,
 (a) 복수의 출처별 자료로부터 계정-주소 접속기록과 인물-주소 점유기록을 각각 추출해
     그래프의 노드·엣지로 적재하는 단계 — 각 엣지에 출처식별자를 부여;
 (b) 상기 접속기록의 시점이 상기 점유기록의 유효구간에 포함되는 쌍을 후보로 선별하는 단계;
 (c) 상기 주소가 사전 임계치 이상의 서로 다른 사건에서 관측되는 경우 해당 후보의 채택을
     보류하거나 순위를 낮추는 단계;
 (d) 채택된 후보를 출처식별자와 함께 제시하는 단계를 포함하는 방법
[종속항] (c)의 임계치를 주소별 관측 사건 수의 분포 기반 이상치로 정하는 …
[종속항] (a)의 그래프가 노드 25종·엣지 72종의 온톨로지 정경을 준수하는지 검증하는 …
```

### B. 출처 수 기반 단서 순위화 — **A와 함께**

**무엇** — 서로 다른 사건·문서에서 온 자료를 **물리 식별자**(계좌·전화·IP·계정)로 병합하고, 각
노드에 **몇 개 출처에서 관측됐는지(`ep_count`)를 숫자로** 남겨 "3개 이상 사건에 걸친 IP" 같은
질의로 조직 기반시설을 찾아낸다.

**구현** — `scripts/build_integrated_graph.py` (`ep_origin`·`ep_count`).
실증: IP `27.193.61.154` 가 5개 사건에 교차 등장 → 조직 공용 인프라로 확정.
협력기관 CSV로도 재현 확인(`vt_telno 01002478573`, `ep_origin='ep3,partner_demo'`).

**차별점** — 그래프 병합·요약 특허([US8126926](https://patents.google.com/patent/US8126926B2)
summary graph)는 시각화용 통계 요약입니다. 우리는 **병합 과정에서 출처 다중도를 1급 속성으로
보존**하고 그것을 **수사 단서의 우선순위**로 쓰는 것이라 목적이 다릅니다. 숫자 타입으로 저장해
범위 비교가 성립하게 하는 것도 구성요소입니다(문자열이면 비교가 조용히 실패).

### C. 0건 자동복구 — 중간 라벨 합성 2-hop 브리지 — **2순위, 범위 축소 필요**

**무엇** — 생성된 그래프 질의가 **0건**이면, 앵커 노드의 **실제 이웃 분포를 DB에서 조회**하고
온톨로지 엣지 카탈로그와 교차해 **중간 노드를 끼운 2-hop 경로로 재합성**한다.

**구현** — `app/services/langgraph_agent.py`
`_anchor_neighborhood`(55행) · `_bridge_two_hop`(104행) · `_augment_anchor_node`

**리스크** — [Multi-Agent GraphRAG](https://arxiv.org/abs/2511.08274) (2025-11) 이 이미
"database-grounded feedback 으로 관계 방향·타입 오류를 교정"을 공개했습니다. **방향 반전 부분은
포기**하고 아래로 좁혀야 합니다.

**살릴 수 있는 차별점**
1. 트리거가 문법오류가 아니라 **실행 결과 0건**
2. 앵커의 **실측 이웃 분포**(라벨별 빈도)를 조회해 후보를 정함 — 스키마가 아니라 데이터
3. 두 라벨이 직접 인접하지 않을 때 **중간 라벨을 합성**해 경로를 만듦
4. `WHERE id(t) <> id(a)` 자기참조 배제, 앵커·경로 포함 반환
5. 재작성 결과가 **여전히 0건이면 제시하지 않고** 0건임을 명시(거짓 보강 차단 — D와 연결)

### D. 평가 무결성 계측 — **3순위, 신규성 양호**

**무엇** — 자연어 질의응답 시스템의 성능 측정에서 **거짓 통과**를 구조적으로 차단한다.

두 가지 구성:
1. **보강행 분리 계측** — 시스템이 결과를 보기 좋게 만들려 덧붙인 요소(앵커 노드 보강 등)와
   **모델이 실제로 산출한 행**을 분리해 세고, 성공 판정은 후자로만 한다.
   실측 근거: 이 분리를 넣기 전 100문항 벤치가 88%로 보였는데 실제는 81%였습니다(7건 거짓 통과).
2. **무결성 스냅샷** — 평가 실행 전후로 데이터 상태를 스냅샷해, 평가 중 실행된 쓰기 질의가
   데이터를 변조했는지 탐지한다. 실측 근거: 가드 문항의 `SET` 이 통과해 주범 이름이 변조된 사고.

**구현** — `scripts/bench_integrated_t2c.py` (`integrity_snapshot`),
`langgraph_agent.py` (`n_model_rows` / `n_anchor_added` 분리)

**선행기술** — 환각 탐지([SQLHD](https://arxiv.org/html/2512.22250v1) 메타모픽 테스팅,
[GROUND](https://arxiv.org/html/2608.26157))는 **질의 자체의 정확성**을 봅니다. **평가 절차의
신뢰성을 보증하는 장치**는 1차 검색에서 대응물을 찾지 못했습니다. 공공조달·인증 맥락에서
"성능수치 신뢰성 검증 장치"로 값이 있습니다.

---

## 3. 출원 부적합 판정 (근거)

| 후보 | 판정 근거 |
|---|---|
| E. 엔진 크래시 회피 | [US10303686](https://patents.google.com/patent/US10303686) 이 **OLAP 엔진 버그로 인한 DB 크래시를 힌트로 회피**하는 것을 이미 청구. 우리는 힌트 대신 의미보존 재작성이라 수단은 다르나 목적이 동일해 진보성 다툼이 큽니다. [US10083208](https://patents.google.com/patent/US10083208)·US10255324(실패 질의 자동 재작성)도 있습니다. 출원한다면 "**실행 전 정적 패턴 탐지 + 앵커 승격 재작성**"으로 한정해야 합니다 |
| F. 값 환각 검증 | Multi-Agent GraphRAG 의 entity verification, SQLHD, GROUND 로 포화. 질문·DB 양쪽 대조라는 구체적 수단만 남는데 진보성 인정 난망 |
| G. 집계엣지 + bitemporal | [Bitemporal Property Graphs](https://arxiv.org/pdf/2111.13499)(2021) 및 후속 연구가 valid/transaction time 을 엣지 1급 속성으로 다루는 것을 이미 공개. 설계 노하우로 유지 |
| H. 온톨로지 정합 감사 | SHACL 검증이 표준이고 [OntoLogX](https://arxiv.org/pdf/2510.01409)·OntoMetric·ANCHOR 등 다수 공개. domain/range 검증은 공지기술 |
| I. 프롬프트 정합 | "추론 프롬프트를 학습 데이터 형식과 정확히 일치시킨다"는 이미 통용되는 실무. prompt routing 특허도 다수 |

---

## 4. 신규 아이디어 (미구현 — 여기에 개량 발명을 얹을 수 있음)

공개 저장소 문제를 피하려면 **아직 공개되지 않은 개량**에 청구항을 두는 것이 유리합니다.

### 아이디어 1. 식별자 신뢰등급에 따른 **병합 보류 게이트** ★ 추천
계좌를 계좌번호만으로 병합하면 타행 동일번호가 한 노드로 합쳐집니다(현행 결함 — 은행코드를
`999` 고정 저장). 이를 일반화해 **식별자의 신뢰등급**(단독 식별 가능 / 보조키 필요 / 불충분)을
정의하고, 등급 미달이면 **병합을 보류하고 별도 큐로 보내** 사람이 판단하게 한다.

- 수사에서 오병합은 무고로 직결되므로 "합치지 않음"이 안전한 기본값
- 청구 포인트: 병합 실패가 아니라 **보류 상태를 그래프에 표현**하고, 보조키가 나중에 도착하면
  자동 승격
- A·B와 결합하면 하나의 출원으로 묶을 수 있음

### 아이디어 2. 근거 없는 속성 생성을 막는 **추정 금지 적재 게이트** ★ 추천
현재 ATM 46건 중 주소가 없는 17건은 **위치 노드를 만들지 않습니다**(지점명으로 지역을 추정하면
근거 없는 위치가 그래프에 들어가므로). 이 원칙을 게이트로 일반화한다.

- 원본에 근거가 없는 속성·관계는 생성하지 않고 **미확정 큐**에 적재 사실만 남긴다
- 증거능력 관점에서 "추정으로 생성된 요소가 그래프에 섞이지 않음"을 보증
- LLM 추출 파이프라인의 환각 차단에도 그대로 적용 (문서 추출 31% 오류 이력)

### 아이디어 3. 질의응답 결과에 **원본 문서 근거를 동봉**
`source_id` 를 노드·엣지 전량(100%)이 보유하는 구조를 활용해, 질의 결과의 **각 요소마다 원본
문서 위치를 붙여 반환**한다. 수사관이 그래프 화면에서 곧바로 원본 대조로 넘어갈 수 있게 한다.

- 청구 포인트: 집계 엣지의 경우 **집계에 기여한 원본 건들의 출처 집합**을 복원해 제시
- 현재 `source_id` 를 `'DOC-008|DOC-009'` 처럼 이어붙이는데, 이를 구조화하면 구성요소가 됨

### 아이디어 4. 크래시 형태 **자동 학습** 가드
현재는 크래시 유발 형태를 사람이 패턴으로 적어 넣습니다. 크래시가 실제로 발생하면 그 질의에서
**형태를 일반화해 차단 규칙을 자동 생성**하고, 이후 동일 형태를 사전 차단·재작성한다.

- E의 진보성 약점(US10303686)을 **학습 루프**로 보강하는 방향
- 폐쇄망에서 엔진 교체가 불가능한 환경에 실효

---

## 5. 실행 권고

| 순서 | 할 일 | 기한 |
|---|---|---|
| 1 | 저장소 **Private 전환** | 즉시 |
| 2 | 경찰청 과제 협약서의 **특허 귀속·통보 조항** 확인 | 출원 전 필수 |
| 3 | 공개 이력 증거(커밋 해시·URL·시각) 보존 | 즉시 |
| 4 | **A+B+아이디어1** 을 하나의 출원으로 묶어 명세서 작성 | 2027-08-31 이전, 가급적 2026년 내 |
| 5 | D(평가 무결성) 별건 출원 검토 | 2027-08-31 이전 |
| 6 | C는 청구범위 축소 후 판단, E는 회피설계 검토 | — |

**출원 전 보완이 필요한 실증**
- A: IP 역추적의 정밀도·재현율을 수사기록 정답과 대조한 수치를 **문서로** 남기십시오
  (62/64·40/40 은 대화 기록에만 있습니다). 명세서의 효과 입증에 씁니다.
- D: 88% → 81% 거짓통과 7건의 **문항별 내역**을 보존하십시오.
- 아이디어 1·2: 최소 구현 + 오병합 방지 건수 측정이 있으면 명세서가 훨씬 강해집니다.

---

## 출처

- [US7657567B2 — Method and system for rewriting a database query](https://patents.google.com/patent/US7657567)
- [US10303686 — Query plan optimization by persisting a hint table](https://patents.google.com/patent/US10303686)
- [US10083208 / US10255324 — Query modification in a database management system](https://patents.google.com/patent/US10083208)
- [US20190114295A1 — Incremental simplification and optimization of complex queries using dynamic result feedback](https://patents.google.com/patent/US20190114295A1/en)
- [US8484744 / US8225413 — Detecting impersonation on a social network](https://patents.google.com/patent/US8484744)
- [US10320811B1 — Impersonation detection and abuse prevention machines](https://patents.google.com/patent/US10320811B1/en)
- [US20140317736A1 — Detecting fake accounts in online social networks](https://patents.google.com/patent/US20140317736A1/en)
- [US10558797B2 — Identifying compromised credentials and controlling account access](https://patents.google.com/patent/US10558797B2/en)
- [US8126926B2 — Data visualization with summary graphs](https://patents.google.com/patent/US8126926B2/en)
- [US20250086211 — Grounding large language models using real-time content feeds and reference data](https://patents.justia.com/patent/20250086211)
- [Multi-Agent GraphRAG: A Text-to-Cypher Framework for Labeled Property Graphs](https://arxiv.org/html/2511.08274v1)
- [Hallucination Detection for LLM-based Text-to-SQL Generation via Two-Stage Metamorphic Testing (SQLHD)](https://arxiv.org/html/2512.22250v1)
- [GROUND: Reducing Hallucinations in LLM-Based Enterprise Analytics Through Governed Semantic Definitions](https://arxiv.org/html/2608.26157)
- [Bitemporal Property Graphs to Organize Evolving Systems](https://arxiv.org/pdf/2111.13499)
- [OntoLogX: Ontology-Guided Knowledge Graph Extraction from Cybersecurity Logs with LLMs](https://arxiv.org/pdf/2510.01409)
- [Achieving Precise Text-To-Cypher Via Grounded Knowledge Graph Data Generation](https://arxiv.org/pdf/2606.14325)
- [KIPRIS 특허정보검색](https://www.kipris.or.kr/)
