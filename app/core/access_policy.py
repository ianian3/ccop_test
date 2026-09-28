"""
access_policy.py — 앱 전역 접근 정책 (감사 F01).

모든 Blueprint 요청에 하나의 before_request 로 적용:

1) 호출 주체 (기본 거부)
   - PUBLIC_ENDPOINTS           : 인증 없음 (UI 페이지·헬스체크·정적)
   - SELF_AUTH_BLUEPRINTS       : 자체 인증 (admin=관리자 세션, graph_read=X-API-Key)
   - Bearer 표식 라우트          : require_api_key / require_api_or_ui 가 경로에서 검증
   - 그 외 전부(main 내부 API 등): UI 세션 · 관리자 세션 · admin('*') Bearer 키 중 하나
   UI 세션은 UI 페이지 렌더 시 발급되는 same-origin 표식일 뿐 사용자 로그인이 아니다.
   실제 사용자 인증 경계는 Basic Auth(BASIC_AUTH_USER/PASS)와 네트워크다.

2) 그래프 접근 (ALLOWED_GRAPHS 설정 시)
   요청의 모든 그래프 지정 필드(graph_path·graph_name·graph …; JSON 중첩·query·form·URL 변수)
   와, 그래프를 생략했을 때 라우트가 쓰는 기본 그래프까지 모두 검사한다.
"""
import logging
import os

from flask import current_app, jsonify, request, session

logger = logging.getLogger(__name__)

PUBLIC_ENDPOINTS = frozenset({
    'static',
    'main.index',        # UI 페이지 — 세션 발급
    'main.modeler',      # 모델러 페이지 — 세션 발급
    'api_v1.health_check',   # /api/v1/health — watchdog·헬스체크 (인증 걸면 정상 앱 재시작 루프)
})
SELF_AUTH_BLUEPRINTS = frozenset({'admin', 'graph_read'})

GRAPH_PARAM_KEYS = ('graph_path', 'graph_name', 'graph', 'target_graph')

# 그래프 필드를 생략하면 라우트가 쓰는 하드코딩 기본값 (config DEFAULT_GRAPH_PATH 가 아닌 것).
# 라우트의 기본값을 바꾸면 여기도 갱신 — tests/test_access_policy.py 가 엔드포인트 존재를 검사.
IMPLICIT_DEFAULT_GRAPHS = {
    'main.graph_algo': 'ccop_ep_integrated',
    'main.rdb_to_graph': 'test_ai01',
    'main.modeler_generate_cypher': 'new_graph',
    'api_v1.import_with_inference': 'tccop_graph_v6',
    'api_v1.rdb_to_graph': 'test_ai01',
    'api_v1.rdb_gdb_stats': 'test_ai01',
    'api_v1.gdb_detail_stats': 'test_ai01',
    'graph_read.graph_read': 'my_v40_demo',
}


def allowed_graphs():
    """ALLOWED_GRAPHS(콤마 구분). 비어 있으면 제한 없음."""
    return frozenset(g.strip() for g in os.getenv('ALLOWED_GRAPHS', '').split(',') if g.strip())


def graph_allowed(name) -> bool:
    allowed = allowed_graphs()
    return (not allowed) or (name in allowed)


def _collect_graph_values(obj, out, depth=0):
    """JSON 중첩 구조에서 그래프 지정 필드 값을 모은다 (깊이 5 제한)."""
    if depth > 5:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in GRAPH_PARAM_KEYS and isinstance(v, str) and v.strip():
                out.add(v.strip())
            elif isinstance(v, (dict, list)):
                _collect_graph_values(v, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _collect_graph_values(v, out, depth + 1)


def requested_graphs():
    """요청이 명시한 그래프 이름 집합."""
    found = set()
    body = request.get_json(silent=True) if request.is_json else None
    _collect_graph_values(body, found)
    for src in (request.args, request.form):
        for k in GRAPH_PARAM_KEYS:
            for v in src.getlist(k):
                if v and v.strip():
                    found.add(v.strip())
    _collect_graph_values(request.view_args or {}, found)
    return found


def _effective_graphs(endpoint):
    """검사 대상 그래프 = 명시 그래프, 없으면 라우트 기본 그래프."""
    found = requested_graphs()
    if not found and endpoint in IMPLICIT_DEFAULT_GRAPHS:
        found.add(IMPLICIT_DEFAULT_GRAPHS[endpoint])
    return found


def _is_ui_or_admin() -> bool:
    if session.get('ui_authorized') or session.get('admin_logged_in'):
        return True
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '):
        from app.middleware.api_auth import validate_api_key
        partner = validate_api_key(auth[len('Bearer '):].strip())
        if partner and '*' in (partner.get('allowed_endpoints') or []):
            return True
    return False


def check_request():
    """before_request 훅. 통과면 None, 거부면 응답."""
    endpoint = request.endpoint
    if endpoint is None:          # 404/405 — Flask 기본 처리
        return None
    view = current_app.view_functions.get(endpoint)
    blueprint = endpoint.split('.', 1)[0] if '.' in endpoint else ''

    # 1) 호출 주체
    if not (endpoint in PUBLIC_ENDPOINTS
            or blueprint in SELF_AUTH_BLUEPRINTS
            or getattr(view, '_accepts_bearer', False)
            or _is_ui_or_admin()):
        return jsonify({
            "status": "error", "error": "Authentication required", "reauth": True,
            "message": "UI 세션이 없거나 만료되었습니다. 화면을 새로고침하세요.",
        }), 401

    # 2) 그래프 접근
    if allowed_graphs():
        for g in _effective_graphs(endpoint):
            if not graph_allowed(g):
                logger.warning(f"⛔ 허용되지 않은 그래프 접근 차단: {g} ({endpoint})")
                return jsonify({"status": "error",
                                "message": f"이 배포에서는 '{g}' 그래프에 접근할 수 없습니다."}), 403
    return None


def init_app(app):
    """Blueprint 등록 후 호출."""
    app.before_request(check_request)
    allowed = allowed_graphs()
    default = app.config.get('DEFAULT_GRAPH_PATH')
    # 그래프를 생략한 요청은 대개 DEFAULT_GRAPH_PATH 로 실행된다 — 기본 그래프가 허용 목록
    # 밖이면 생략만으로 제한을 우회하므로 기동을 거부한다 (fail-fast).
    if allowed and default and default not in allowed:
        raise RuntimeError(f"DEFAULT_GRAPH_PATH '{default}' 가 ALLOWED_GRAPHS 에 없습니다. "
                           f"기본 그래프를 허용 목록에 넣거나 DEFAULT_GRAPH_PATH 를 바꾸세요.")
