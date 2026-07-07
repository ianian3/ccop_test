# 벤더링된 프론트엔드 자산

폐쇄망(air-gap) 배포를 위해 CDN 의존을 제거하고 로컬로 반입한 자산입니다.
템플릿(`app/templates/index.html`, `modeler.html`)은 `/static/vendor/...` 로 참조합니다.
CSP(`app/__init__.py`)는 외부 호스트를 허용하지 않습니다(`default-src 'self'`).

| 자산 | 버전 | 원본 |
|------|------|------|
| cytoscape | 3.23.0 | https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.23.0/cytoscape.min.js |
| dagre | 0.7.4 | https://unpkg.com/dagre@0.7.4/dist/dagre.js |
| cytoscape-dagre | 2.5.0 | https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.js |
| Font Awesome (free) | 6.0.0 | https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/ (css + webfonts) |
| Pretendard | 1.3.9 | https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/ (css + woff2) |

## 갱신 방법
1. 위 URL에서 새 버전을 내려받아 해당 디렉토리에 덮어쓴다.
2. Font Awesome 은 `css/all.min.css` 와 `webfonts/*` 를 함께 갱신(css가 `../webfonts/` 참조).
3. Pretendard 는 `pretendard.min.css` 의 woff2 경로가 `./woff2/` 를 가리키도록 유지(원본은 `../../../packages/...`).
4. 버전 변경 시 이 표와 템플릿 주석을 갱신.
