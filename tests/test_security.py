# tests/test_security.py
"""
보안 기능 단위 테스트

Tests:
1. validate_graph_path — SQL Injection 방어 화이트리스트 검증
2. safe_set_graph_path — 유효/무효 graph_path 처리
3. Admin auth — 환경변수 기반 비밀번호 검증
"""
import pytest
import os
import hashlib
import hmac


# =============================================
# 1. validate_graph_path Tests
# =============================================

class TestValidateGraphPath:
    """graph_path 화이트리스트 검증 테스트"""

    def test_valid_simple_name(self):
        from app.database import validate_graph_path
        assert validate_graph_path("demo_tst1") is True

    def test_valid_alpha_only(self):
        from app.database import validate_graph_path
        assert validate_graph_path("mygraph") is True

    def test_valid_with_numbers(self):
        from app.database import validate_graph_path
        assert validate_graph_path("graph123") is True

    def test_valid_underscore_prefix(self):
        from app.database import validate_graph_path
        assert validate_graph_path("_private_graph") is True

    def test_valid_mixed_case(self):
        from app.database import validate_graph_path
        assert validate_graph_path("CcopTestGraph") is True

    def test_reject_sql_injection_semicolon(self):
        from app.database import validate_graph_path
        assert validate_graph_path("graph; DROP TABLE users;--") is False

    def test_reject_sql_injection_quote(self):
        from app.database import validate_graph_path
        assert validate_graph_path("graph' OR '1'='1") is False

    def test_reject_spaces(self):
        from app.database import validate_graph_path
        assert validate_graph_path("my graph") is False

    def test_reject_hyphen(self):
        from app.database import validate_graph_path
        assert validate_graph_path("my-graph") is False

    def test_reject_number_prefix(self):
        from app.database import validate_graph_path
        assert validate_graph_path("123graph") is False

    def test_reject_empty_string(self):
        from app.database import validate_graph_path
        assert validate_graph_path("") is False

    def test_reject_none(self):
        from app.database import validate_graph_path
        assert validate_graph_path(None) is False

    def test_reject_special_chars(self):
        from app.database import validate_graph_path
        assert validate_graph_path("graph@!#$") is False

    def test_reject_dot_path(self):
        from app.database import validate_graph_path
        assert validate_graph_path("schema.table") is False

    def test_reject_newline_injection(self):
        from app.database import validate_graph_path
        assert validate_graph_path("graph\n; DROP TABLE x;") is False

    def test_reject_unicode(self):
        from app.database import validate_graph_path
        assert validate_graph_path("그래프") is False


# =============================================
# 2. safe_set_graph_path Tests
# =============================================

class TestSafeSetGraphPath:
    """safe_set_graph_path 보안 래퍼 테스트"""

    def test_raises_on_invalid_path(self):
        from app.database import safe_set_graph_path

        class FakeCursor:
            def execute(self, sql):
                pass

        with pytest.raises(ValueError, match="유효하지 않은 graph_path"):
            safe_set_graph_path(FakeCursor(), "graph; DROP TABLE users;--")

    def test_raises_on_empty_path(self):
        from app.database import safe_set_graph_path

        class FakeCursor:
            def execute(self, sql):
                pass

        with pytest.raises(ValueError):
            safe_set_graph_path(FakeCursor(), "")

    def test_raises_on_none(self):
        from app.database import safe_set_graph_path

        class FakeCursor:
            def execute(self, sql):
                pass

        with pytest.raises(ValueError):
            safe_set_graph_path(FakeCursor(), None)

    def test_executes_on_valid_path(self):
        from app.database import safe_set_graph_path

        executed_queries = []

        class FakeCursor:
            def execute(self, sql):
                executed_queries.append(sql)

        safe_set_graph_path(FakeCursor(), "demo_tst1")
        assert len(executed_queries) == 1
        assert "SET graph_path = demo_tst1" in executed_queries[0]

    def test_no_quotes_in_executed_sql(self):
        """SQL Injection 변형이 실행 쿼리에 포함되지 않음을 확인"""
        from app.database import safe_set_graph_path

        executed_queries = []

        class FakeCursor:
            def execute(self, sql):
                executed_queries.append(sql)

        safe_set_graph_path(FakeCursor(), "valid_graph")
        # 실행된 SQL에 싱글/더블 쿼트가 없어야 함
        assert "'" not in executed_queries[0]
        assert '"' not in executed_queries[0]


# =============================================
# 3. Admin Auth Tests
# =============================================

class TestAdminAuth:
    """관리자 인증 환경변수 기반 테스트"""

    def test_missing_password_disables_login(self):
        """ADMIN_PASSWORD 미설정 시 None 반환 → 로그인 비활성화(fail-closed).

        (구 admin123 fallback 취약점 제거를 검증)
        """
        # 환경변수 제거
        os.environ.pop("ADMIN_PASSWORD", None)

        from app.routes_admin import _get_admin_password_hash
        assert _get_admin_password_hash() is None

    def test_custom_password(self):
        """ADMIN_PASSWORD 설정 시 해당 비밀번호 사용"""
        os.environ["ADMIN_PASSWORD"] = "MySecureP@ss!"

        from app.routes_admin import _get_admin_password_hash
        expected = hashlib.sha256("MySecureP@ss!".encode()).hexdigest()
        assert _get_admin_password_hash() == expected

        # 정리
        os.environ.pop("ADMIN_PASSWORD", None)

    def test_timing_safe_comparison(self):
        """hmac.compare_digest이 올바르게 매칭되는지 확인"""
        password = "test_password"
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        os.environ["ADMIN_PASSWORD"] = password

        from app.routes_admin import _get_admin_password_hash
        stored_hash = _get_admin_password_hash()

        assert hmac.compare_digest(password_hash, stored_hash) is True
        assert hmac.compare_digest("wrong_hash", stored_hash) is False

        os.environ.pop("ADMIN_PASSWORD", None)

    def test_login_with_correct_password(self, app, client):
        """올바른 비밀번호로 로그인 성공"""
        os.environ["ADMIN_PASSWORD"] = "test_admin"

        response = client.post('/admin/login', data={'password': 'test_admin'})
        # 성공 시 대시보드로 리다이렉트 (302)
        assert response.status_code == 302

        os.environ.pop("ADMIN_PASSWORD", None)

    def test_login_with_wrong_password(self, app, client):
        """잘못된 비밀번호로 로그인 실패"""
        os.environ["ADMIN_PASSWORD"] = "correct_password"

        response = client.post('/admin/login', data={'password': 'wrong_password'})
        # 실패 시 로그인 페이지 렌더 (200)
        assert response.status_code == 200

        os.environ.pop("ADMIN_PASSWORD", None)

    def test_admin_required_redirect(self, app, client):
        """인증 없이 대시보드 접근 시 리다이렉트"""
        response = client.get('/admin/dashboard')
        assert response.status_code == 302
        assert '/admin/login' in response.headers.get('Location', '')


# ══════════════════════════════════════════════════════════════════
# 파괴적 그래프 관리 엔드포인트 인증 (2026-07 하드닝)
#   이전: @require_api_key 주석 처리 → 무인증 graph/delete 등 노출.
#   수정: mutating graph/* 에 require_api_key + require_endpoint_permission('admin').
#   'admin' 권한은 allowed_endpoints 에 '*' 인 티어(enterprise)만 통과.
# ══════════════════════════════════════════════════════════════════
class TestGraphAdminAuth:

    _MUTATING = [
        ("post", "/api/v1/graph/create", {"graph_name": "x"}),
        ("post", "/api/v1/graph/delete", {"graph_name": "x"}),
        ("post", "/api/v1/graph/node/create", {"graph_name": "x", "label": "vt_psn"}),
        ("post", "/api/v1/graph/edge/create",
         {"graph_name": "x", "src_id": "1", "tgt_id": "2", "label": "e"}),
        ("post", "/api/v1/graph/element/delete", {"graph_name": "x", "element_id": "1"}),
    ]

    def _inject_key(self, key, allowed):
        from app.middleware import api_auth
        h = api_auth.generate_api_key_hash(key)
        api_auth.API_KEYS_STORE[h] = {
            "partner_name": "pytest", "tier": "test",
            "rate_limit": 100000, "allowed_endpoints": allowed, "is_active": True,
        }
        return h

    def test_mutating_endpoints_require_auth(self, app, client):
        """키 없이 호출 시 401 (무인증 노출 회귀 방지)."""
        for method, path, body in self._MUTATING:
            r = getattr(client, method)(path, json=body)
            assert r.status_code == 401, f"{path} 는 무인증이면 안 됨 (got {r.status_code})"

    def test_mutating_endpoints_reject_non_admin(self, app, client):
        """유효 키라도 admin('*') 권한 없으면 403."""
        h = self._inject_key("pytest-nonadmin", ["text-to-cypher"])
        try:
            hdr = {"Authorization": "Bearer pytest-nonadmin"}
            for method, path, body in self._MUTATING:
                r = getattr(client, method)(path, json=body, headers=hdr)
                assert r.status_code == 403, f"{path} 는 비-admin 이면 403 (got {r.status_code})"
        finally:
            from app.middleware import api_auth
            api_auth.API_KEYS_STORE.pop(h, None)

    def test_mutating_endpoints_pass_auth_for_admin(self, app, client):
        """admin('*') 키는 인증/권한 통과 (이후 400/500 은 무방 — 401/403 이 아니면 됨)."""
        h = self._inject_key("pytest-admin", ["*"])
        try:
            hdr = {"Authorization": "Bearer pytest-admin"}
            for method, path, body in self._MUTATING:
                r = getattr(client, method)(path, json=body, headers=hdr)
                assert r.status_code not in (401, 403), \
                    f"{path} admin 인증 통과해야 함 (got {r.status_code})"
        finally:
            from app.middleware import api_auth
            api_auth.API_KEYS_STORE.pop(h, None)

    def test_graph_list_requires_auth(self, app, client):
        """graph/list(읽기)도 유효 키 필요(401), admin 권한까지는 불요."""
        assert client.get("/api/v1/graph/list").status_code == 401


class TestRateLimitUnlimited:
    """enterprise rate_limit=None 이 TypeError(500) 없이 무제한 허용되는지."""

    def test_none_rate_limit_is_unlimited(self):
        from app.middleware.api_auth import _check_rate_limit
        for _ in range(5):
            assert _check_rate_limit("pytest-enterprise", None) is True

    def test_int_rate_limit_still_enforced(self):
        from app.middleware.api_auth import _check_rate_limit
        # 고유 파트너명으로 버킷 격리
        allowed = sum(1 for _ in range(3) if _check_rate_limit("pytest-rl-cap-2026", 2))
        assert allowed == 2  # 3번째부터 초과(False)
