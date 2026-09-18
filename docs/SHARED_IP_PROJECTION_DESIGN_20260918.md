# 공유-IP 관계: Projection 기반 설계

> "같은 IP를 쓴 계정 쌍"을 bipartite projection 으로 설계하는 방안.
> 앞선 조합론 근거([[SAME_IP_EDGE_COMBINATORICS_20260918]])의 후속 — 저장할지/어떻게 저장할지.
> 수치는 로컬 `ccop_ep_integrated` 실측(2026-09-18).

---

## 1. Projection 이란

현 그래프는 **이분(bipartite)** 구조다 — 계정층(`vt_id`)과 IP층(`vt_ip`)이 `used_ip` 로 연결된다.

```
vt_id ──used_ip──▶ vt_ip ◀──used_ip── vt_id      (2-mode / bipartite)
```

"같은 IP를 쓴 계정 쌍"은 이 이분 그래프를 **계정–계정 단일층으로 투영(one-mode projection)** 한
것이다. IP를 매개(축)로 없애고 계정끼리 직접 잇는다.

```
vt_id ──shares_ip──▶ vt_id                        (1-mode / projected)
```

이는 그래프 이론의 표준 기법(co-occurrence projection)이며, 공저자망·구매자-상품망 등에서
쓰는 것과 동일하다.

## 2. AgensGraph 현실 — 네이티브 GDS projection 은 없다

Neo4j GDS 의 `gds.graph.project`(인메모리 서브그래프)나 monopartite projection API 같은 것은
**AgensGraph(PostgreSQL 기반)에 없다.** 따라서 projection 은 아래 셋 중 하나로 구현한다.

| 방식 | 설명 | 적합 |
|---|---|---|
| **A. 온디맨드 Cypher** | 조회 시 `(a)-[:used_ip]->(ip)<-[:used_ip]-(b)` 로 투영 유도. 저장 안 함 | 기본값 |
| **B. 실체화(materialized)** | `shares_ip` 엣지를 물리 생성해 저장 | 반복 분석·중심성 계산 시 |
| **C. 하이브리드** | 가중치 임계 이상만 실체화, 나머지는 온디맨드 | **권장** |

## 3. 단순 projection 의 함정 — 콜센터 노이즈

단순히 "공유하면 엣지"로 투영하면 두 문제가 겹친다(조합론 문서 참조).

1. **폭발**: Σ C(Nₚ,2), 이차. 한 IP에 N계정이면 N²/2 쌍.
2. **노이즈 지배**: 실측상 **콜센터급 IP 1개(83계정)가 전체 쌍의 43%**를 만든다.
   83개 계정이 "우연히 같은 공용망/콜센터"인 것은 **약한 신호**인데, 단순 projection 에선
   이 약한 신호가 그래프를 뒤덮는다.

| IP 공유도 Nₚ | IP 수 | projection 쌍 | 비중 | 신호 |
|---|---|---|---|---|
| 2–3계정 | 1,437 | 1,809 | 23% | **강함**(특정 소규모) |
| 4–10계정 | 44 | 566 | 7% | 중간 |
| 11–50계정 | 7 | 2,034 | 26% | 약함 |
| 51+계정 | 1 | 3,403 | **43%** | **노이즈**(콜센터) |

## 4. 핵심 설계 — 가중 projection (IP 희귀도 반영)

단순 존재(0/1)가 아니라 **연결 강도**를 가중치로 준다. IP의 **희귀도**로 가중하면(공유 계정이
많은 IP일수록 낮은 가중), 콜센터 노이즈가 자동으로 억제된다 — 정보검색의 IDF 와 같은 원리다.

계정 쌍 (a,b) 의 가중치:

  **w(a,b) = Σ_{공유 IP p} 1 / Nₚ**       (Nₚ = 그 IP를 쓴 계정 수)

- 콜센터 IP(Nₚ=83)만 공유한 쌍: w = 1/83 ≈ **0.012** → 바닥으로 밀림
- 소수 공유 IP(Nₚ=2) 하나: w = 0.5. **여러 개 함께 공유할수록 합산되어 상위**

### 실측 — 가중 projection 상위 쌍

| 공유 IP 수 | 가중치 w | 해석 |
|---|---|---|
| 49 | **16.27** | 두 계정이 49개 IP를 함께 씀 → 동일인/밀접 (최강 신호) |
| 8 | 4.00 | 소수-공유 IP 8개 공유 |
| 16 | 2.99 | |
| 19 | 2.91 | |
| … | … | 콜센터만 공유한 쌍(w≈0.012)은 **하위로** |

→ 단순 count 에선 43%를 차지하던 콜센터 쌍이, 가중 projection 에선 **자동으로 최하위**가 되고,
"여러 희귀 IP를 함께 쓴 밀접한 쌍"이 최상위로 올라온다. 수사적으로 의미 있는 순서다.

## 5. 권장 설계 (하이브리드 C)

### 5.1 IP 희귀도 사전계산 (1회, 갱신 시 재계산)
각 `vt_ip` 에 공유 계정 수를 속성으로 저장 → 가중치 계산을 빠르게.
```cypher
MATCH (i:vt_id)-[:used_ip]->(x:vt_ip)
WITH x, count(DISTINCT i) AS n
SET x.shared_id_cnt = n
```

### 5.2 강한 쌍만 실체화 (콜센터 제외 + 가중 하한)
노이즈(고공유 IP)를 빼고, 가중치가 임계 이상인 쌍만 `shares_ip` 엣지로 저장.
```cypher
MATCH (a:vt_id)-[:used_ip]->(x:vt_ip)<-[:used_ip]-(b:vt_id)
WHERE id(a) < id(b) AND x.shared_id_cnt <= 50      -- 콜센터급 IP 제외(노이즈 컷)
WITH a, b, count(DISTINCT x) AS shared_ips,
     sum(1.0 / x.shared_id_cnt) AS weight
WHERE weight >= 1.0                                 -- 강한 쌍만(임계는 튜닝)
MERGE (a)-[r:shares_ip]->(b)
SET r.weight = weight, r.shared_ips = shared_ips
```
- 콜센터 IP 제외로 쌍의 43%(노이즈) 제거 → 엣지 수·폭발 동시 완화
- `weight`·`shared_ips` 속성으로 순위·필터 지원
- 나머지 약한 쌍은 실체화하지 않고 필요 시 §A 온디맨드

### 5.3 갱신
계정의 `used_ip` 가 바뀌면 그 IP의 `shared_id_cnt` 와, 그 IP를 공유하는 쌍의 `weight` 만
재계산(전체 재빌드 불필요). 배치 주기로 처리.

## 6. 방식 선택 기준

| 상황 | 권장 |
|---|---|
| 단발 조회("이 계정과 같은 IP 쓴 계정") | **A. 온디맨드** — 저장 불필요 |
| 군집·중심성 등 반복 그래프 분석 | **B/C. 실체화** — 매번 경로 유도는 비쌈 |
| 대규모·실데이터 | **C. 가중+임계 실체화** — 폭발·노이즈 둘 다 제어 |

## 7. 결론

- projection 자체는 표준 기법이나, AgensGraph 엔 네이티브 GDS 가 없어 Cypher/실체화로 구현한다.
- **단순 projection 은 콜센터 노이즈(43%)에 지배**되므로, **IP 희귀도 가중(w=Σ1/Nₚ)** 이 필수다.
- 가중 projection 은 (1) 콜센터를 자동 억제하고 (2) 밀접 쌍을 상위로 올리며 (3) 임계로 엣지 수를
  제어한다 — 폭발·노이즈·의미없음을 한 번에 해결.
- 권장은 **희귀도 사전계산 + 강한 쌍만 실체화(하이브리드)**.

## 부록 — 검증 쿼리 (실행 확인, AgensGraph)

```cypher
-- 가중 projection 상위 쌍 (콜센터 억제 확인)
MATCH (a:vt_id)-[:used_ip]->(x:vt_ip)<-[:used_ip]-(b:vt_id) WHERE id(a) < id(b)
MATCH (x)<-[:used_ip]-(u:vt_id)
WITH id(a) AS pa, id(b) AS pb, id(x) AS ipid, count(DISTINCT u) AS Np
WITH pa, pb, count(DISTINCT ipid) AS shared_ips, sum(1.0/Np) AS weight
RETURN pa, pb, shared_ips, weight ORDER BY weight DESC LIMIT 10;
```
※ AgensGraph 주의: `any` 는 예약어(변수명 금지, u 등 사용) · `coalesce(sum(..))` 불가
   (aggregate 단독) · id 대소비교(`id(a)<id(b)`)는 정상 동작.
