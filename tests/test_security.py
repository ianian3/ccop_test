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
