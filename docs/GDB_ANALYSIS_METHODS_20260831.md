# 그래프 데이터베이스(GDB) 분석 방법·알고리즘 — CCOP 수사 그래프 적용

> **작성일**: 2026-08-31
> **목적**: 그래프 분석의 대표 알고리즘을 정리하고, CCOP 통합 수사 그래프(`ccop_ep_integrated`)에 적용한 방법·실측·도구를 문서화.
> **한 줄**: 그래프 분석은 **중심성·커뮤니티·경로·링크예측·패턴** 5대 축. CCOP는 AgensGraph(Cypher) + NetworkX(PageRank·Louvain)로 "핵심 거점·조직·자금흐름·동일인"을 정량화한다.

---

## 1. 그래프 분석 5대 알고리즘 카테고리

| 카테고리 | 대표 알고리즘 | 수사에서 답하는 질문 | CCOP 적용 |
|---|---|---|---|
| **중심성** Centrality | Degree · Betweenness · Closeness · **PageRank** · Eigenvector | 누가 핵심 거점·영향력자인가 | PageRank 적용(아래 실측) · `ep_count` 근사 |
| **커뮤니티** Community | **Louvain** · Label Propagation · Connected Components | 어떤 무리가 한 조직인가 | Louvain 적용 · `belongs_to`(수동) |
| **경로** Pathfinding | 최단경로(Dijkstra/BFS) · All-paths · DFS | A→B 자금이 어떻게 흘렀나 | `/api/path` · `transferred_to` |
| **링크예측/유사도** Link prediction | 공통이웃(Jaccard) · node2vec · GNN | 이 둘이 동일인/공범인가 | `sameAs`(공유 계좌·전화 규칙) |
| **패턴/모티프** Pattern/Motif | 순환 탐지 · 서브그래프 매칭 · motif | 자금세탁 구조가 있나 | 콜센터 fan-in·집금(수동) |

---

## 2. 수사 특화 — 자금세탁/사기 typology (AML)
금융범죄 그래프 분석의 핵심은 **"구조가 곧 증거"**([TigerGraph](https://www.tigergraph.com/blog/aml-graph-analytics-money-laundering/), [Neo4j AML](https://neo4j.com/blog/fraud-detection/combating-money-laundering-aml-graph-algorithms/)):
- **순환 흐름**(circular flow) A→B→C→A · **집금**(fan-in) 다수→1 · **분산**(fan-out) 1→다수
- **은닉 수익자**(hidden beneficial owner) — 명의 뒤 실사용자 · **mule network**(대포통장망) · **layered path**(다단계 경유)
- 관계기반 피처: 유입 집중도 · 순환 참여 · 공통 수익자 · 소유 깊이 · 확정 typology 유사도
- **효과**: 그래프 AML 도입 시 오탐률 **95% → 10~20%**로 감소.

CCOP 대응(이미 그래프로 표현됨): 집금(피어스미디어 25계좌) · 분산(204-852140 → 수취인) · 은닉수익자(콜센터 IP→네이버 실명) · mule(대포통장 다수).

---

## 3. CCOP 실측 — PageRank·Louvain (2026-08-31, `ccop_ep_integrated`)
`scripts/graph_analytics.py`로 AgensGraph → NetworkX export(노드 24,287·엣지 25,573) 후 계산·되쓰기(`pagerank`·`community_id` 속성).

### PageRank 상위 (영향력 자동 랭킹)
| 유형 | Top (score) | 수사 의미 |
|---|---|---|
| **IP** | **122.54.197.66**(0.0011) · 122.54.197.65 · 124.111.91.100 | 콜센터 거점 IP를 **자동 최상위** 식별(수동 ep_count와 일치) |
| **계좌** | **조지영**(0.0034) · 김은희 · 박민서 · 길민지 · 이진아 | 집금·대포통장 명의자 자동 랭킹 |
| **조직** | **피어스미디어**(0.0014) · 유니크프로젝트 | 집금 조직 최상위 |
| **전화** | 01008682731(0.0022) · 01000952731 · 070-7889-1960 | 통화·연락 허브 |

→ **수동으로 "거점·집금책"을 찾던 판정을 PageRank가 정량 자동화**. 조지영·김은희 등 집금 계좌가 영향력 상위로 자동 부상.

### Louvain 자동 조직 (커뮤니티 1,743개)
- 최대 커뮤니티 1,624노드. 상위 조직은 **카톡 IP/계정 클러스터**가 부피를 지배(EP6·8 통신망 특성).
- 인물 조직은 조직#2(1,099노드, 인물 42·전화 44 포함: 남남수·박준우 등)처럼 혼재.
- **교훈**: 전체 그래프 Louvain은 카톡 IP 노이즈로 조직 경계가 IP클러스터 위주 → **인물·계좌·조직 중심 서브그래프**에 적용하면 진짜 조직 커뮤니티가 선명해짐(후속 개선).

---

## 4. 실행 도구 (AgensGraph 한계 + 보강)
- **AgensGraph**: Cypher로 **경로·패턴·집계**는 가능하나 **전용 GDS(그래프 알고리즘) 라이브러리 없음** — 중심성·Louvain은 직접 구현하거나 export 필요.
- **CCOP 채택**: Python이라 **AgensGraph → NetworkX export → PageRank·Louvain → 노드 속성 SET**(`scripts/graph_analytics.py`). 24k 노드 수초 계산.
- **대안 GDB**: Neo4j **GDS**(65+ 알고리즘 내장) · TigerGraph · Memgraph MAGE · cuGraph(GPU).

---

## 5. 재현·활용
```bash
python3 scripts/graph_analytics.py --graph ccop_ep_integrated        # Top 리포트만
python3 scripts/graph_analytics.py --graph ccop_ep_integrated --set  # 노드에 pagerank·community_id 부여
```
- 활용: 브리핑에 "영향력 Top 인물·계좌·거점" 추가 · 시각화 노드 크기를 pagerank로 · community_id로 조직 색상.
- 후속(P2): 인물중심 서브그래프 Louvain(조직 선명화) · betweenness(중개 노드) · node2vec 링크예측(동일인 고도화) · 순환 탐지(자금세탁 typology).

**Sources:**
- [Neo4j — Graph algorithms: community detection & recommendations](https://neo4j.com/blog/graph-data-science/graph-algorithms-community-detection-recommendations/)
- [Neo4j — Combating money laundering: AML graph algorithms](https://neo4j.com/blog/fraud-detection/combating-money-laundering-aml-graph-algorithms/)
- [TigerGraph — AML with Graph Analytics](https://www.tigergraph.com/blog/aml-graph-analytics-money-laundering/)
- [Communications of the ACM — Graph Databases for Fraud Detection](https://cacm.acm.org/blogcacm/leveraging-graph-databases-for-fraud-detection-in-financial-systems/)
- [arXiv — A Comprehensive Review of Community Detection in Graphs](https://arxiv.org/html/2309.11798v4)
- [Linkurious — Financial crime investigations best practices](https://linkurious.com/blog/financial-crime-investigations-graph-technology-best-practices/)
