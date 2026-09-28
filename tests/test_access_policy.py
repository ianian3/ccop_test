# tests/test_access_policy.py
"""
F01 (감사 2026-09-17, P0): 인증과 그래프 접근 제한이 전체 경로에 적용되지 않던 결함.

재현 고정:
- 익명 /api/graph/clear 가 200 으로 변경 서비스까지 도달
- ALLOWED_GRAPHS 를 graph_name·다른 Blueprint·중첩 필드·기본 그래프로 우회
전역 정책: app/core/access_policy.py
"""
import pytest

from app.core import access_policy


def _inject_key(key, allowed):
    from app.middleware import api_auth
    h = api_auth.generate_api_key_hash(key)
    api_auth.API_KEYS_STORE[h] = {"partner_name": "pytest", "tier": "test", "rate_limit": 100000,
                                  "allowed_endpoints": allowed, "is_active": True}
    return h


@pytest.fixture
def spy_clear(monkeypatch):
    """GraphService.clear_graph 대역 — 호출 여부 기록 (DB 불필요)."""
    from app.services.graph_service import GraphService
    calls = []
    monkeypatch.setattr(GraphService, "clear_graph",
                        staticmethod(lambda g: calls.append(g) or (True, "cleared")))
    return calls


class TestCallerAuth:

    def test_anonymous_clear_blocked_before_service(self, client, spy_clear):
        r = client.post("/api/graph/clear", json={"graph_path": "g1"})
        assert r.status_code == 401
        assert r.get_json()["reauth"] is True
        assert spy_clear == []

    def test_ui_session_passes(self, client, spy_clear):
        with client.session_transaction() as s:
            s["ui_authorized"] = True
        assert client.post("/api/graph/clear", json={"graph_path": "g1"}).status_code == 200
        assert spy_clear == ["g1"]

    def test_ui_page_grants_session(self, client, spy_clear):
        assert client.get("/").status_code == 200
        assert client.post("/api/graph/clear", json={"graph_path": "g1"}).status_code == 200

    def test_admin_bearer_passes_non_admin_rejected(self, client, spy_clear):
        from app.middleware import api_auth
        h1 = _inject_key("pytest-pol-admin", ["*"])
        h2 = _inject_key("pytest-pol-partner", ["text-to-cypher"])
        try:
            ok = client.post("/api/graph/clear", json={"graph_path": "g1"},
                             headers={"Authorization": "Bearer pytest-pol-admin"})
            ng = client.post("/api/graph/clear", json={"graph_path": "g1"},
                             headers={"Authorization": "Bearer pytest-pol-partner"})
            assert (ok.status_code, ng.status_code) == (200, 401)
        finally:
            api_auth.API_KEYS_STORE.pop(h1, None)
            api_auth.API_KEYS_STORE.pop(h2, None)

    def test_anonymous_db_switch_blocked(self, client):
        assert client.post("/api/db/switch", json={"db_name": "x"}).status_code == 401

    def test_previously_open_v1_rdb_query_blocked(self, client):
        assert client.get("/api/v1/rdb/query/tb_prsn").status_code == 401

    def test_public_endpoints_open(self, client):
        assert client.get("/").status_code == 200
        assert client.get("/modeler").status_code == 200
        assert client.get("/api/v1/health").status_code != 401


class TestRouteInventory:
    """정책 표가 실제 라우트와 어긋나지 않는지 — 이름 오타 하나가 헬스체크 401 → 재시작 루프."""

    def test_policy_endpoints_exist(self, app):
        names = set(app.view_functions)
        assert access_policy.PUBLIC_ENDPOINTS <= names
        assert set(access_policy.IMPLICIT_DEFAULT_GRAPHS) <= names

    def test_every_v1_route_declares_auth(self, app):
        """api_v1 라우트는 Bearer 표식(파트너 사용 가능) 또는 public 이어야 한다."""
        missing = [ep for ep, v in app.view_functions.items()
                   if ep.startswith("api_v1.") and ep not in access_policy.PUBLIC_ENDPOINTS
                   and not getattr(v, "_accepts_bearer", False)]
        assert missing == []

    def test_admin_routes_protected(self, app):
        """admin Blueprint 은 자체 인증 — login/logout 외에는 require_admin."""
        from app import routes_admin
        open_ok = {"admin.login", "admin.logout"}
        for ep, v in app.view_functions.items():
            if ep.startswith("admin.") and ep not in open_ok:
                assert v.__code__.co_name == "decorated_function", f"{ep} require_admin 누락"


class TestGraphRestriction:

    @pytest.fixture
    def restricted(self, monkeypatch, app):
        from config import Config
        monkeypatch.setenv("ALLOWED_GRAPHS", f"g_ok,{Config.DEFAULT_GRAPH_PATH}")
        c = app.test_client()
        with c.session_transaction() as s:
            s["ui_authorized"] = True
        return c

    def test_graph_path_blocked(self, restricted, spy_clear):
        assert restricted.post("/api/graph/clear", json={"graph_path": "bad"}).status_code == 403
        assert spy_clear == []

    def test_allowed_graph_passes(self, restricted, spy_clear):
        assert restricted.post("/api/graph/clear", json={"graph_path": "g_ok"}).status_code == 200

    def test_graph_name_bypass_blocked(self, restricted):
        assert restricted.post("/api/graph/delete", json={"graph_name": "bad"}).status_code == 403

    def test_nested_field_blocked(self, restricted):
        r = restricted.post("/api/modeler/load-data",
                            json={"schema": {"target": {"graph_path": "bad"}}})
        assert r.status_code == 403

    def test_form_graph_field_blocked(self, restricted):
        r = restricted.post("/api/v1/etl/infer-import", data={"graph": "bad"})
        assert r.status_code == 403

    def test_implicit_default_graph_blocked(self, restricted, monkeypatch):
        """graph_path 생략 → 라우트 하드코딩 기본값으로 실행되던 우회."""
        monkeypatch.setitem(access_policy.IMPLICIT_DEFAULT_GRAPHS, "main.graph_algo", "bad_default")
        assert restricted.post("/api/graph/algo", json={"algo": "top"}).status_code == 403

    def test_other_blueprints_blocked(self, restricted, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "k")
        r = restricted.post("/api/v1/graph/read", headers={"X-API-Key": "k"},
                            json={"cypher": "MATCH (n) RETURN n", "graph_path": "bad"})
        assert r.status_code == 403
        r = restricted.get("/api/v1/graph/dump?graph_path=bad", headers={"X-API-Key": "k"})
        assert r.status_code == 403

    def test_graph_list_filtered(self, restricted, monkeypatch):
        from app.services.graph_service import GraphService
        monkeypatch.setattr(GraphService, "list_graphs",
                            staticmethod(lambda: [{"name": "g_ok"}, {"name": "bad"}]))
        names = [g["name"] for g in restricted.get("/api/graph/list").get_json()["graphs"]]
        assert names == ["g_ok"]

    def test_default_graph_outside_allowlist_fails_startup(self, monkeypatch):
        monkeypatch.setenv("ALLOWED_GRAPHS", "g_ok_only")
        from app import create_app
        with pytest.raises(RuntimeError, match="DEFAULT_GRAPH_PATH"):
            create_app()
