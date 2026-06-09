# V4.0 시각화 표준 (L5 레이어)

**작성일**: 2026-05-21
**상위 표준**: [`CCOP_ONTOLOGY_V4.0.md`](CCOP_ONTOLOGY_V4.0.md)
**SSOT 코드**: `app/middleware/services/ontology_service.py` (`VISUAL_STYLE_V40`, `EDGE_STYLE_V40`, `LAYOUT_PRESETS_V40`, `INVESTIGATION_WORKFLOWS_V40`)
**구현 대상**: 프론트엔드 (`app/templates/index.html`, `modeler.html`)

> **수사관이 그래프를 시각적으로 수사할 수 있게 하는 표준** — V4.0 데이터 아키텍처의 최종 사용자 인터페이스 레이어.

---

## 0. 위치 — V4.0 5단계 아키텍처에서의 역할

```
L1. 수집 ──→ L2. RDB ──→ L3. 변환 ──→ L4. 그래프 ──→ L5. 시각화 ⭐ 본 문서 범위
                                                          │
                                                          └─→ 수사관 화면
```

---

## 1. 핵심 원칙

### 1.1 단일 시각 진실 (Single Visual Truth)
- 모든 라벨/엣지의 색상·아이콘·모양은 **`ontology_service.py` SSOT에서만 정의**
- 프론트엔드 코드(index.html 등)는 본 SSOT를 import해서 적용
- 색상/아이콘 변경 시 SSOT 한 곳만 수정

### 1.2 의미론적 시각화 (Semantic Visualization)
- **색상 = 의미론적 레이어** (POLE)
  - 회색 계열 = Source
  - 빨강 계열 = Case
  - 파랑 계열 = Person
  - 청록·녹색 = Object (디지털)
  - 주황 = Event
  - 갈색 = Location
  - 노랑/주황(허브) = Hub (군집)
- **모양 = 노드 카테고리**
  - 타원 = 식별 가능한 개체
  - 사각형 = 디지털 객체
  - 마름모 = 이벤트
  - 다이아몬드 = 조직
  - 6각형 = 허브 (군집)
  - 8각형 = relay_station (위험 디바이스)
- **속성 → 외관 변형**: `is_burner`, `is_malicious`, `is_anonymous`, `threat_score` 등이 색상/테두리/크기 조정

### 1.3 수사 친화적 인터랙션
- 클릭 → 이웃 노드 자동 확장
- 우클릭 → 컨텍스트 메뉴 (속성 보기, 관계 확장, 시간 필터)
- 더블클릭 → 노드 중심 재정렬
- 검색창 → Text2Cypher 자연어 질의

---

## 2. 노드 시각 표준 (VISUAL_STYLE_V40)

### 2.1 레이어별 색상 팔레트

| 레이어 | 색 계열 | 대표 색 | 의미 |
|---|---|---|---|
| Source | 회색 | `#95A5A6` | 메타데이터, 출처 |
| Case | 빨강 | `#E74C3C` | 사건, 진정서 |
| Hub | 노랑/주황 | `#FFD93D`, `#F39C12` | 군집 (pt_cluster, site_cluster) |
| Person | 파랑 | `#3498DB` | 실인물, 조직 |
| Object (Account/Phone) | 청록 | `#4ECDC4`, `#16A085` | 금융/통신 객체 |
| Object (IP/Site/File) | 보라/녹색 | `#9B59B6`, `#1ABC9C` | 디지털 인프라 |
| Object (Device) | 자주 | `#7D3C98` | 디바이스 |
| Event | 주황 계열 | `#F39C12`, `#E67E22` | 행위 이벤트 |
| Location | 갈색 | `#A04000` | 위치 |

### 2.2 노드 모양 표준

| 모양 | 사용 | 예시 |
|---|---|---|
| ellipse | 식별 가능한 개체 | vt_case, vt_psn, vt_petition, vt_id |
| rectangle | 디지털 객체 | vt_bacnt, vt_telno, vt_ip, vt_email, vt_atm |
| roundrectangle | 사이트 / URL | vt_site |
| diamond | 이벤트 + 조직 | vt_transfer, vt_call, vt_msg, vt_org |
| hexagon | **군집 허브** ⭐ | pt_cluster, site_cluster |
| octagon | 위험 디바이스 | vt_dev(relay_station) — 자동 변환 |
| pentagon | 위치 | vt_loc |

### 2.3 노드 크기 표준

| size | 사용 | 예시 |
|---|---|---|
| 60 | 허브 노드 | pt_cluster, site_cluster |
| 50 | 핵심 개체 | vt_case |
| 45 | 인물 | vt_psn, vt_org |
| 35-40 | 일반 객체 | vt_bacnt, vt_telno, vt_site, vt_petition |
| 30 | 보조 객체 | vt_ip, vt_file, vt_atm |
| 25 | 이벤트 | vt_call, vt_access, vt_movement |

### 2.4 속성 기반 외관 변형 (style_modifier)

| 라벨 | 트리거 속성 | 시각 변형 |
|---|---|---|
| vt_psn | `is_anonymous=true` | 회색 + 테두리 dashed |
| vt_psn | `risk_level=HIGH` | size 55, 테두리 굵게 |
| vt_psn | `risk_level=CRITICAL` | size 65, 빨강 테두리 굵게 |
| vt_bacnt | `is_burner=true` | 주황 + 테두리 dashed (대포통장) |
| vt_bacnt | `is_frozen=true` | 50% 투명 |
| vt_telno | `is_burner=true` | 주황 + 테두리 dashed (대포폰) |
| vt_ip | `is_vpn=true` | 테두리 dotted |
| vt_ip | `threat_score>=80` | 빨강 + 테두리 굵게 |
| vt_site | `is_malicious=true` | 진한 보라 + 빨강 테두리 굵게 |
| vt_file | `is_malicious=true` | 빨강 |
| vt_id | `is_anonymous=true` | 회색 + 테두리 dashed |
| **vt_dev** | `dev_type='relay_station'` ⭐ | **빨강 + 8각형 + size 50** (중계기 강조) |

---

## 3. 엣지 시각 표준 (EDGE_STYLE_V40)

### 3.1 카테고리별 색상

| 카테고리 | 색 | 예시 |
|---|---|---|
| 사건 역할 | 빨강 (suspect), 녹색 (victim), 주황 (witness) | suspect_in, victim_in, witness_in |
| 증거 | 파랑 계열 | eg_used_account, eg_used_phone, eg_used_ip |
| 인물 관계 (positive) | 파랑 | has_account, owns_phone |
| 인물 관계 (negative) | 빨강 | accomplice_of, recruits, blackmails |
| 자금 흐름 | 주황 | from_account, to_account, transferred_to |
| 통신 | 주황 계열 | caller, callee, sent_msg, received_msg |
| 인프라 | 청록 | hosts, resolves_to |
| 군집 (V3.7 신규) | 노랑/주황 | belongs_to_cluster, belongs_to_campaign |
| 중계기 (V3.7 신규) | 진한 주황 | used_in_device |
| 출처/메타 | 회색 | sourced_from, verified_by |
| 동일성 | 회색 + dashed | sameAs |
| Deprecated | 흐린 회색 + dotted | clusters_with |

### 3.2 엣지 굵기 표준

| width | 사용 | 예시 |
|---|---|---|
| 3 | 강한 의미 / 핵심 관계 | suspect_in, victim_in, recruits, used_in_device |
| 2 | 일반 관계 | 대부분의 엣지 |
| 1 | 보조 관계 | mentions_account, sourced_from |

### 3.3 엣지 스타일

| style | 사용 |
|---|---|
| solid | 직접 관계 (대부분) |
| dashed | 추론된 동일성 (sameAs), 사칭 (impersonates) |
| dotted | 메타/시간 관계 (sourced_from, occurred_at), Deprecated |

### 3.4 화살표 모양

| arrow | 사용 |
|---|---|
| triangle | 일반 방향성 |
| triangle-tee | 대칭/양방향성 강조 (accomplice_of, sameAs, related_case) |
| tee | 모순 (contradicts) |
| none | 무방향 (sameAs 등) |

---

## 4. 레이아웃 프리셋 (LAYOUT_PRESETS_V40)

### 4.1 case_centric — 사건 중심 트리
```
        vt_case (root)
       /     |     \
suspect victim witness
   |      |      |
  vt_psn  vt_psn  vt_psn
```
- Cytoscape: `breadthfirst` 알고리즘
- 사용 시나리오: 사건 하나의 전체 인물/증거 관계 시각화

### 4.2 cluster_view — 군집 허브 중심
```
            pt_cluster (center)
          / | | | \
    p1 p2 p3 p4 p5  (멤버 진정서)
```
- Cytoscape: `concentric` 알고리즘
- 사용 시나리오: 진정서 군집 / 피싱 캠페인 멤버십 시각화

### 4.3 timeline — 시간순 이벤트 흐름
```
시간축 ──────────────────────────→
  call(10:00) → transfer(10:15) → access(10:30) → msg(11:00)
```
- 커스텀 알고리즘 (X축 = `occurred_at`)
- 사용 시나리오: 사건 발생 시계열 추적

### 4.4 investigation — 수사 종합 뷰
- Cytoscape: `cose` (force-directed)
- 엣지 길이 = `reliability_tier` (tier 낮을수록 가까이 = 신뢰도 높은 노드 클러스터링)
- 사용 시나리오: 자유 탐색

### 4.5 cross_domain — 도메인 분리 시각화
- Cytoscape: `cose-bilkent` (subgraph clustering)
- `source_domain`별 클러스터링 (investigation / osint 분리)
- sameAs 엣지로 연결된 cross-domain 매칭 강조
- 사용 시나리오: CCOP-OSINT 통합 분석

---

## 5. 수사 워크플로 (INVESTIGATION_WORKFLOWS_V40)

V4.0 표준 수사 시나리오 6종:

| 워크플로 | 시작점 | 경로 | 도착점 | 시각화 권장 |
|---|---|---|---|---|
| **case_to_suspects** | vt_case | ←suspect_in | vt_psn | case_centric |
| **suspect_to_assets** | vt_psn | →has_account, →owns_phone | vt_bacnt, vt_telno | investigation |
| **phishing_campaign_view** | site_cluster | ←belongs_to_campaign | vt_site | cluster_view |
| **fund_flow** | vt_bacnt | →from_account→to_account (depth 5) | vt_bacnt | timeline |
| **relay_station_network** | vt_dev(relay_station) | ←used_in_device | vt_telno | cluster_view |
| **cross_graph_sameAs** | vt_bacnt (CCOP) | ↔sameAs↔ | vt_bacnt (OSINT) | cross_domain |

### 5.1 워크플로 → Cypher 자동 생성

```python
from app.middleware.services.ontology_service import KICSCrimeDomainOntology as Onto

wf = Onto.get_workflow('case_to_suspects')
# {
#   'start': 'vt_case',
#   'hops': [('suspect_in', '<-')],
#   'end': 'vt_psn',
#   'description': '사건 → 피의자 목록'
# }

# 자동 생성 Cypher:
# MATCH (c:vt_case {flnm: $case_id})<-[:suspect_in]-(p:vt_psn) RETURN c, p
```

---

## 6. 프론트엔드 적용 가이드

### 6.1 SSOT import (Flask Jinja 또는 API)

#### A. API endpoint로 export (권장)
```python
# app/routes_api.py 추가
@api_v1.route('/visual-style', methods=['GET'])
def get_visual_style():
    from app.middleware.services.ontology_service import KICSCrimeDomainOntology as O
    return jsonify({
        'nodes': O.VISUAL_STYLE_V40,
        'edges': O.EDGE_STYLE_V40,
        'layouts': O.LAYOUT_PRESETS_V40,
        'workflows': O.INVESTIGATION_WORKFLOWS_V40,
    })
```

#### B. 프론트엔드 fetch (index.html)
```javascript
// 페이지 로드 시 SSOT 가져와 Cytoscape 스타일 자동 생성
const visualSSOT = await fetch('/api/v1/visual-style').then(r => r.json());

const cy = cytoscape({
    container: document.getElementById('graph'),
    style: buildCytoscapeStyle(visualSSOT),  // SSOT → Cytoscape style 변환
    elements: []
});

function buildCytoscapeStyle(ssot) {
    const styles = [];
    // 노드 스타일
    for (const [label, conf] of Object.entries(ssot.nodes)) {
        styles.push({
            selector: `node[label = "${label}"]`,
            style: {
                'background-color': conf.color,
                'shape': conf.shape,
                'width':  conf.size,
                'height': conf.size,
                'label':  `data(${conf.label_property})`,
                'background-image': `/static/images/${conf.icon}`,
            }
        });
        // style_modifier 적용
        if (conf.style_modifier) {
            for (const [trigger, mod] of Object.entries(conf.style_modifier)) {
                styles.push({
                    selector: `node[label = "${label}"][${trigger}]`,
                    style: mod
                });
            }
        }
    }
    // 엣지 스타일
    for (const [edge_label, conf] of Object.entries(ssot.edges)) {
        styles.push({
            selector: `edge[label = "${edge_label}"]`,
            style: {
                'line-color':         conf.color,
                'target-arrow-color': conf.color,
                'target-arrow-shape': conf.arrow,
                'line-style':         conf.style,
                'width':              conf.width,
            }
        });
    }
    return styles;
}
```

### 6.2 인터랙션 표준

| 동작 | 결과 |
|---|---|
| 노드 클릭 | 우측 패널에 속성 표시 (id_format, source_domain, tier 포함) |
| 노드 더블클릭 | 노드 중심 재정렬 + 1-hop 이웃 자동 확장 |
| 노드 우클릭 | 컨텍스트 메뉴 (확장, 필터, 시간슬라이드, 워크플로 적용) |
| 엣지 클릭 | 엣지 속성 표시 (sim_score, confidence 등) |
| 검색창 | Text2Cypher 호출 → Cypher 생성 → 그래프 그리기 |
| 워크플로 버튼 | INVESTIGATION_WORKFLOWS_V40에서 선택 → 자동 Cypher → 시각화 |

### 6.3 권장 화면 구성

```
┌──────────────────────────────────────────────────────────────────┐
│ [검색창 — 자연어 질의]  [그래프 선택] [워크플로 ▼] [레이아웃 ▼] │
├──────────────────────────────────────────────────────────────────┤
│                                            ┌──────────────────┐  │
│                                            │ 속성 패널         │  │
│              ┌─────────┐                  │  ─────────       │  │
│             ●● 그래프  ●●                 │  선택된 노드:    │  │
│              \   |   /                    │  vt_bacnt        │  │
│               ●─●─●                       │  account_no: ... │  │
│                                            │  id_format: ...  │  │
│                                            │  source_domain:..│  │
│                                            │  reliability: 1  │  │
│                                            │  is_burner: true │  │
│                                            │                  │  │
│                                            │ [확장] [필터]    │  │
│                                            └──────────────────┘  │
├──────────────────────────────────────────────────────────────────┤
│ 결과: 5 노드 / 8 엣지 │ 시간 슬라이더 ───●──── │ 응답시간 1.4s   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 7. 색맹 / 접근성 고려

### 7.1 색상 외 시각 신호 의무화
색맹 사용자를 위해 색상만으로 의미 구분 금지 — 다음 보조 신호 사용:
- 모양(shape) — 노드 카테고리 (이중 표시)
- 테두리 스타일(border_style) — solid/dashed/dotted
- 아이콘(icon) — 라벨 식별

### 7.2 WCAG 2.1 AA 색상 대비
- 노드 색 vs 라벨 텍스트: contrast ratio ≥ 4.5
- 다크 모드 지원 (옵션)

---

## 8. 성능 표준

### 8.1 그래프 크기 가이드

| 노드 수 | 권장 레이아웃 | 응답 시간 목표 |
|---|---|---|
| ~50 | breadthfirst, concentric | < 100ms |
| 50~500 | cose | < 500ms |
| 500~5,000 | cose-bilkent | < 2s |
| > 5,000 | sample / paginate | 별도 검토 |

### 8.2 대용량 처리
- 5,000+ 노드 그래프는 **샘플링/페이지네이션** 적용
- 검색 결과는 기본 LIMIT 200, 사용자 요청 시 확장

### 8.3 캐싱
- Cytoscape style은 페이지 로드 시 1회 fetch + localStorage 캐시
- SSOT 버전 변경 시 자동 무효화 (`/api/v1/visual-style/version` 비교)

---

## 9. 운영 모니터링 지표

| 지표 | 측정 |
|---|---|
| 평균 시각화 응답시간 | API → 그래프 그리기 완료까지 |
| 워크플로별 사용 빈도 | 어느 워크플로가 많이 쓰이는지 |
| Layout 선택 분포 | 사용자가 선호하는 레이아웃 |
| Text2Cypher → 시각화 성공률 | end-to-end |
| 노드 클릭 → 확장 빈도 | 사용자 인터랙션 활성도 |

---

## 10. V4.0 시각화 산출물

| # | 산출물 | 위치 | 상태 |
|---|---|---|---|
| 1 | 본 문서 (시각화 표준) | `docs/V40_VISUALIZATION_STANDARD.md` | ✅ |
| 2 | SSOT 코드 (VISUAL_STYLE_V40 등 4 dict) | `ontology_service.py` | ✅ |
| 3 | API endpoint (`/api/v1/visual-style`) | `app/routes_api.py` | ⏳ 추가 필요 |
| 4 | 프론트엔드 SSOT 적용 (index.html) | `app/templates/index.html` | ⏳ 리팩토링 필요 |
| 5 | 노드 아이콘 PNG 25종 | `app/static/images/` | △ 일부 존재 |
| 6 | 워크플로 UI (버튼 + 자동 Cypher) | `app/templates/index.html` | ⏳ 추가 필요 |

---

## 11. 변경 이력

| 일자 | 버전 | 변경 |
|---|---|---|
| 2026-05-21 | V4.0 | L5 시각화 표준 신설 — VISUAL_STYLE/EDGE_STYLE/LAYOUT/WORKFLOWS SSOT 격상 |

---

## 12. 핵심 결론

> **V4.0 L5 시각화 표준은 25 노드 / 55 엣지의 색상·모양·크기·인터랙션을 `ontology_service.py` SSOT로 일원화한다.** 프론트엔드는 본 SSOT를 API로 받아 Cytoscape에 자동 매핑하며, 라벨/엣지 추가/변경 시 SSOT 한 곳만 수정하면 시각화에 즉시 반영된다. 6종의 표준 수사 워크플로(case_to_suspects, fund_flow, relay_station_network 등)가 자연어 질의 없이도 클릭 한 번으로 동작한다.

---

**문서 끝**
