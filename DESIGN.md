# CCOP Design System — 다크 인베스티게이션 워크벤치 (초안 v0.1)

> 단일 진실 소스(SoT)는 `app/static/css/tokens.css`. 이 문서는 그 토큰의 의미와
> 사용 규칙을 서술한다. 색/치수는 토큰 CSS 변수명(`var(--color-primary)`)으로 참조한다.
> 참고 골격: Meta 커머스 DESIGN.md — **방법론(토큰 SoT·컴포넌트 명세·시맨틱 역할)만
> 차용**하고, 스킨(화이트 캔버스·제품사진·커머스 의미론)은 도입하지 않는다.

## Overview

CCOP는 분석가가 장시간 그래프를 응시하며 사건을 파헤치는 **다크 수사 도구**다.
참조 계열은 커머스 사이트가 아니라 Linear · Vercel 대시보드 · Grafana/Datadog 같은
프로 다크 툴이다. Meta 문서의 "제품 사진이 곧 표면" 원칙을 CCOP식으로 번역하면
**"그래프 캔버스가 곧 표면"** — UI 크롬은 절제하고, 시각적 무게는 그래프의 노드·엣지
색 인코딩이 진다.

**핵심 특징:**
- 다크 캔버스(`var(--color-canvas)` = `#0f0f0f`) 위 저채도 UI + 고채도 데이터(노드).
- **청록-블루** 단일 액센트: primary 청록(`#00cec9`)은 상호작용 신호로만, 블루(`#4dabf7`)는 링크·선택.
- primary(청록)를 데이터/노드 색과 **의도적으로 분리** — "상호작용"과 "데이터"가 다르게 읽히도록.
- 평면 기본 + 선택적 엘리베이션(다크에선 그림자보다 경계선·배경 명도차).
- Pretendard 단일 페이스(로컬 벤더링됨), 본문 13px 밀집 세팅.
- 데이터 툴 특성상 라운딩은 중간값(`--radius-md/lg`) 기본, 칩·배지·탭만 pill.

## Colors

### Primary (청록-블루)
| 토큰 | 값 | 용도 |
|---|---|---|
| `--color-primary` | `#00cec9` | 주요 액션 CTA, 활성 탭, 포커스 링 |
| `--color-primary-hover` | `#12b5b0` | hover |
| `--color-primary-active` | `#0e9b96` | pressed |
| `--color-primary-soft` | `rgba(0,206,201,.14)` | 정보 콜아웃 배경 틴트 |
| `--color-on-primary` | `#06201f` | 밝은 청록 위 텍스트(근흑) |
| `--color-accent-blue` | `#4dabf7` | 링크 · 폼컨트롤 선택 · 정보 |

### Surface (다크 래더)
`--color-canvas` `#0f0f0f` → `--color-surface` `#141414` → `--color-surface-raised` `#1a1a1a`
→ `--color-surface-header` `#1e1e1e` → `--color-surface-hover` `#2d2d2d`. 입력창은 `--color-surface-input` `#2d3436`.

### Text
`--color-text-strong` `#ffffff` · `--color-text` `#e0e0e0` · `--color-text-secondary` `#b2bec3` · `--color-text-muted` `#888888`.

### Border
`--color-border-soft` `#2d2d2d` · `--color-border` `#333333` · `--color-border-strong` `#444444`.

### Semantic (상태)
| 토큰 | 값 | 용도 |
|---|---|---|
| `--color-success` | `#51cf66` | 증거 확보 · 정상 · 완료(✅) |
| `--color-info` | `#4dabf7` | 정보 안내 |
| `--color-warning` | `#fdcb6e` | 경고 · 시한성 |
| `--color-attention` | `#ff922b` | 중우선 알림 |
| `--color-critical` | `#ff6b6b` | 오류 · 파괴적 작업 · 누락(❌) |

> `success` 는 primary 청록과 혼동되지 않도록 명확한 '녹색'으로 둔다.

## Graph Node Legend (시그니처)

CCOP의 브랜드 표면은 **그래프 노드 색 인코딩**이다. 노드 타입 → 색은 시스템 토큰으로
고정하며(`--node-*`), primary 청록은 **쓰지 않는다**(UI 상호작용색과 분리). 아래는 KICS
핵심 9종 확정 범례 — 현재 인라인 cytoscape 스킴의 색 충돌(예: `vt_ip`/`vt_access` 동색)을
해소한 값이므로, 확정 후 `index.html` 의 cytoscape 스타일을 이 토큰으로 치환한다.

| 노드 | 토큰 | 값 | 의미 |
|---|---|---|---|
| `vt_flnm` | `--node-flnm` | `#ff6b6b` | 사건번호 |
| `vt_psn` | `--node-psn` | `#b197fc` | 인물 |
| `vt_bacnt` | `--node-bacnt` | `#ffd43b` | 계좌 |
| `vt_telno` | `--node-telno` | `#4dabf7` | 전화 |
| `vt_ip` | `--node-ip` | `#f06595` | IP |
| `vt_site` | `--node-site` | `#20c997` | URL/사이트 |
| `vt_atm` | `--node-atm` | `#ff922b` | ATM |
| `vt_file` | `--node-file` | `#5c7cfa` | 파일/증거 |
| `vt_id` | `--node-id` | `#ffa8a8` | 계정 ID |

확장 노드(조직·가상자산·이메일·통화·메시지·이체·위치·차량·단말)는 `--node-*` 로 2차 정의.
선택 상태는 노드 색 채도 유지 + `2px solid var(--color-primary)` 링(스와치 선택도 동일).

## Typography

**Pretendard**(로컬 벤더링: `/static/vendor/pretendard`) 단일 표시+본문 페이스.
기술 미세문구는 `--font-mono`(JetBrains Mono). 밀도 높은 도구라 본문 기준 **13px**.

| 토큰 | 크기 | 권장 weight | 용도 |
|---|---|---|---|
| `--text-display` | 32px | 600 | 화면 타이틀/히어로 |
| `--text-h1` | 24px | 600 | 섹션 제목 |
| `--text-h2` | 20px | 600 | 서브섹션 |
| `--text-h3` | 16px | 600 | 카드/패널 헤더 |
| `--text-body-lg` | 14px | 400 | 여유 본문 |
| `--text-body` | 13px | 400 | 기본 본문(밀집) |
| `--text-sm` | 12px | 400/600 | 보조·헬퍼·버튼 라벨 |
| `--text-caption` | 11px | 400 | 캡션·범례·타임스탬프 |

원칙: 라인하이트 본문 `--lh-normal`(1.5) 유지. 제목은 `--lh-tight`(1.25). weight 는
300~700 범위(Pretendard). 강조는 색이 아니라 weight/크기로 — 색은 데이터에 양보.

## Layout & Spacing

4px 베이스: `--space-1`(4) … `--space-16`(64). 패널 내부 패딩 `--space-4`~`--space-6`,
섹션 리듬 `--space-8`~`--space-12`. 워크벤치 레이아웃은 헤더(`--color-surface-header`) +
좌/우 패널(`--color-surface-raised`) + 중앙 그래프 캔버스(`--color-canvas`) 3분할.

## Elevation

다크에선 그림자보다 경계선·배경 명도차가 1차. 그림자는 부유 레이어에만.

| 레벨 | 토큰 | 용도 |
|---|---|---|
| 0 | `--elev-0` (none) + `--color-border-soft` | 기본 카드/행 |
| 1 | `--elev-1` `0 2px 6px rgba(0,0,0,.4)` | 카드 부유 |
| 2 | `--elev-2` `0 2px 8px rgba(0,0,0,.5)` | 패널/스티키 |
| 3 | `--elev-3` `0 12px 40px rgba(0,0,0,.75)` | 모달 |

## Shapes (Radius)

`--radius-xs`(3) · `--radius-sm`(6) · `--radius-md`(8, 입력/버튼 기본) · `--radius-lg`(12, 카드)
· `--radius-xl`(16, 패널/모달) · `--radius-pill`(999, 칩·배지·탭) · `--radius-circle`(노드 스와치·아이콘 버튼).

> Meta 는 "모든 버튼 pill"이지만, 밀도 높은 데이터 툴에선 버튼 기본을 `--radius-md`(8)로
> 두고 pill 은 칩·배지·탭·필터에 한정한다. 값보다 **일관성**이 우선.

## Components

> hover 상태는 문서화하지 않는다(토큰 `--color-*-hover` 로 일괄). 기본/pressed/disabled/선택만.

### Buttons
- **`btn-primary`** — 주요 액션. bg `var(--color-primary)`, text `var(--color-on-primary)`, radius `--radius-md`, padding `10px 20px`, weight 600. pressed → bg `--color-primary-active`. disabled → bg `--color-surface-hover`, text `--color-text-muted`.
- **`btn-secondary`** — 아웃라인. bg transparent, text `var(--color-text)`, border `1px solid var(--color-border-strong)`, radius `--radius-md`.
- **`btn-ghost`** — 크롬 없는 텍스트 버튼. text `var(--color-text-secondary)`.
- **`btn-danger`** — 파괴적 작업(그래프 삭제 등). bg `var(--color-critical)`, text `#0f0f0f`.
- **`btn-icon`** — 32×32 원형 유틸(줌/확장/공유). radius `--radius-circle`, icon `var(--color-text-secondary)`.
- **`tab-pill` / `tab-pill-active`** — 카테고리/뷰 전환. radius `--radius-pill`. inactive: border `1px solid var(--color-border)`, text `--color-text-secondary`. active: bg `var(--color-primary)`, text `var(--color-on-primary)`, 무보더.

### Cards & Panels
- **`panel`** — 좌/우 사이드 패널. bg `var(--color-surface-raised)`, border `1px solid var(--color-border-soft)`.
- **`card`** — 정보 카드/행. bg `var(--color-surface)`, radius `--radius-lg`, padding `--space-4`, border `1px solid var(--color-border-soft)`, `--elev-0`.
- **`card-raised`** — 결과/디테일 부유 카드. `card` + `--elev-1`.
- **`modal`** — bg `var(--color-surface-header)`, radius `--radius-xl`, `--elev-3`.

### Inputs & Forms
- **`input`** — bg `var(--color-surface-input)`, text `var(--color-text)`, border `1px solid var(--color-border)`, radius `--radius-md`, height 36px(밀집)~40px.
- **`input-focused`** — border `2px solid var(--color-primary)`.
- **`input-error`** — border `1px solid var(--color-critical)`; 하단 라벨 `--color-critical` `--text-sm`.
- **`search-pill`** — 상단 검색. bg `var(--color-surface-input)`, radius `--radius-pill`, text `--color-text-secondary`.
- **`radio-option` / `-selected`** — 선택: border `2px solid var(--color-primary)` (청록 선택 신호를 폼까지 일관).
- **`node-swatch`** — 노드 타입 색 스와치. `--radius-circle`, 선택 시 `2px solid var(--color-primary)` 링.

### Badges & Status
공통: radius `--radius-pill`, `--text-caption`/600, padding `3px 8px`, text `var(--color-on-semantic)`.
- **`badge-success`** bg `--color-success` (확보/정상) · **`badge-warning`** bg `--color-warning` · **`badge-attention`** bg `--color-attention` · **`badge-critical`** bg `--color-critical` (누락/오류).

### Navigation
- **`app-header`** — bg `var(--color-surface-header)`, 하단 `1px solid var(--color-border-soft)`, 높이 ~56px. 좌: 로고/사건 컨텍스트, 중: 뷰 탭(`tab-pill`), 우: 검색 + 아이콘 버튼.
- **`breadcrumb`** — `--text-sm`, 구분자 `--color-text-muted`, 활성 `--color-text`, 상위 `--color-text-secondary`.

## Do's and Don'ts

### Do
- primary 청록(`--color-primary`)은 **상호작용에만** — 데이터/노드 색으로 쓰지 말 것.
- 노드 타입 색은 반드시 `--node-*` 토큰으로. 하드코딩 금지(현재 인라인 스킴을 이 토큰으로 치환).
- 강조는 색이 아니라 weight/크기로. 색 대비는 그래프 데이터에 양보.
- 다크 엘리베이션은 경계선·배경 명도차 우선, 그림자는 부유 레이어에만.
- 칩·배지·탭만 pill, 나머지 버튼은 `--radius-md`.

### Don't
- 라이트 캔버스/화이트 배경 도입 금지 — 장시간 그래프 응시 도구의 정체성 훼손.
- primary 청록을 성공(success) 녹색과 겹치게 쓰지 말 것(둘을 명확히 분리).
- 화면마다 새 액센트(인디고 등) 만들지 말 것 — 청록-블루 하나로 통일.
- 노드 색을 UI 액센트(청록)와 겹치게 배정하지 말 것.
- 커머스 요소(구매 CTA·프로모 배너·보증 카드) 이식 금지 — CCOP 의미론과 무관.

## Responsive

- 데스크톱 우선(분석 도구). 3분할(좌패널·캔버스·우패널)이 기본.
- < 1024px: 우패널이 그래프 위 오버레이/드로어로. 좌패널은 아이콘 레일로 축소.
- < 768px: 단일 컬럼, 패널은 전체화면 드로어, 그래프 캔버스가 주 뷰.
- 터치 타깃 최소 40px(모바일 44px). 노드 스와치는 여유 히트존 확보.

## Known Gaps / 다음 단계

1. **cytoscape 스타일 치환**: `index.html`/`modeler.html` 의 하드코딩 노드색을 `--node-*` 토큰 참조로 교체(현 스킴엔 색 충돌 존재).
2. **인라인 :root 제거**: 각 템플릿이 `tokens.css` 를 `<link>` 하고 인라인 토큰 삭제 → back-compat 별칭 덕에 무중단.
3. **`ui_search_mockup.html` 통합**: 인디고(`#4F46E5`) → 청록-블루로 재정렬.
4. **컴포넌트 CSS 레이어**: 위 컴포넌트 명세를 `app/static/css/components.css` 로 구현(인라인 중복 제거).
5. 확장 노드 색·모션 타이밍·라이트모드(미정)는 값 검토 후 확정.

> 값은 모두 초안(v0.1). 확정 후 `tokens.css` 를 SoT로 고정하고 이 문서를 갱신한다.
