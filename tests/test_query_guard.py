# tests/test_query_guard.py
"""
F02 (감사 2026-09-17): 읽기 전용 질의 가드와 결과 제한 불완전.

- SQL 쓰기(INSERT/UPDATE/TRUNCATE…)·위험 함수(pg_sleep…)·다중 문장 차단
- 식별자 오탐 없음 ((call:vt_call), s.cluster, n.created_at …)
- DB 세션 읽기 전용 + statement_timeout 적용, 행 수 상한
DB 는 가짜 커서로 대체 — 네트워크 불필요.
"""
import pytest

from app.core import query_guard
from app.core.query_guard import check_read_only


class TestCheckReadOnly:

    @pytest.mark.parametrize("q,token", [
        ("INSERT INTO audit_table VALUES (1) RETURNING 1", "INSERT"),
        ("UPDATE t SET a = 1", "UPDATE"),
        ("TRUNCATE vt_psn", "TRUNCATE"),
        ("WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x", "DELETE"),
        ("MATCH (n) DETACH DELETE n", "DETACH"),
        ("MATCH (n) SET n.x = 1 RETURN n", "SET"),
        ("SELECT pg_sleep(1)", "pg_sleep()"),
        ("SELECT set_config('default_transaction_read_only','off',false)", "set_config()"),
        ("MATCH (n) RETURN n; DROP TABLE t", ";"),
        ("MATCH (n) RETURN n; SELECT 1", ";"),
        ("COPY t TO '/tmp/x'", "COPY"),
        ("  begin", "BEGIN"),
        ("CALL db.labels()", "CALL"),
        # 문자열 속 // 뒤에 숨긴 쓰기 구문 (이전 graph_read 우회 경로)
        ("MATCH (n) WHERE n.u = 'http://x' CREATE (m) RETURN m", "CREATE"),
        ("", "EMPTY"),
    ])
    def test_blocked(self, q, token):
        assert check_read_only(q) == token

    @pytest.mark.parametrize("q", [
        "MATCH (n:vt_psn) RETURN n LIMIT 10",
        "MATCH (n) RETURN n;",                                        # 끝 세미콜론 1개 허용
        "MATCH (d:vt_dev)<-[:used_in_device]-(t:vt_telno)-[:caller]->(call:vt_call) RETURN d, t, call",
        "MATCH (s:site) WHERE s.cluster = 'c1' RETURN count(DISTINCT s)",
        "MATCH (n) WHERE n.created_at > '2026' AND n.update_dt IS NOT NULL RETURN n",
        "SELECT * FROM cypher('g', $$ MATCH (n) RETURN n $$) AS (n agtype)",
    ])
    def test_allowed(self, q):
        assert check_read_only(q) is None


class _FakeCursor:
    def __init__(self, rows=None):
        self.executed = []
        self._rows = list(rows or [])
        self.description = [("c",)]

    def execute(self, sql, params=None):
        self.executed.append((sql, params))

    def fetchmany(self, n):
        return self._rows[:n]

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, cur):
        self.cur, self.closed = cur, False
        self.autocommit = False

    def cursor(self, *a, **k):
        return self.cur

    def close(self):
        self.closed = True


class TestExecuteCypherGuard:

    def _patch(self, monkeypatch, rows=None):
        from app.services.graph_service import GraphService
        cur = _FakeCursor(rows)
        conn = _FakeConn(cur)
        monkeypatch.setattr(GraphService, "get_db_connection", staticmethod(lambda: (conn, cur)))
        return GraphService, cur, conn

    def test_sql_insert_blocked_before_db(self, app, monkeypatch):
        GS, cur, _ = self._patch(monkeypatch)
        with app.app_context():
            ok, msg = GS.execute_cypher("INSERT INTO audit_table VALUES (1) RETURNING 1", "my_graph")
        assert ok is False and "WRITE_BLOCKED" in msg and "INSERT" in msg
        assert not any("INSERT" in sql for sql, _ in cur.executed)

    def test_read_query_runs_in_read_only_session(self, app, monkeypatch):
        GS, cur, conn = self._patch(monkeypatch)
        with app.app_context():
            ok, _ = GS.execute_cypher("MATCH (n) RETURN n", "my_graph")
        assert ok is True
        sqls = [sql for sql, _ in cur.executed]
        assert "SET default_transaction_read_only = on" in sqls
        assert any(sql.startswith("SET statement_timeout") for sql in sqls)
        # 읽기 전용 설정이 실제 질의보다 먼저
        assert sqls.index("SET default_transaction_read_only = on") < sqls.index("MATCH (n) RETURN n")
        assert conn.closed

    def test_row_cap(self, app, monkeypatch):
        monkeypatch.setenv("CYPHER_MAX_ROWS", "3")
        GS, cur, _ = self._patch(monkeypatch, rows=[(i,) for i in range(10)])
        fetched = []
        orig = cur.fetchmany
        cur.fetchmany = lambda n: fetched.append(n) or orig(n)
        with app.app_context():
            GS.execute_cypher("MATCH (n) RETURN n", "my_graph")
        assert fetched == [4]  # limit+1 로 절단 여부 판별

    def test_writable_sandbox_graph_skips_read_only_session(self, app, monkeypatch):
        GS, cur, _ = self._patch(monkeypatch)
        with app.app_context():
            GS.execute_cypher("MATCH (n) RETURN n", "ccop_test_graph")
        assert "SET default_transaction_read_only = on" not in [s for s, _ in cur.executed]


class TestGraphReadApi:

    @pytest.fixture
    def read_client(self, app, monkeypatch):
        monkeypatch.setenv("LLM_API_KEY", "pytest-llm-key")
        return app.test_client(), {"X-API-Key": "pytest-llm-key"}

    def _patch_db(self, monkeypatch, rows):
        import app.routes_graph_read as m
        cur = _FakeCursor(rows)
        conn = _FakeConn(cur)
        monkeypatch.setattr(m.psycopg2, "connect", lambda **kw: conn)
        return cur, conn

    def test_pg_sleep_rejected(self, read_client, monkeypatch):
        client, hdr = read_client
        cur, _ = self._patch_db(monkeypatch, [])
        r = client.post("/api/v1/graph/read", headers=hdr,
                        json={"cypher": "SELECT pg_sleep(1)", "graph_path": "g"})
        assert r.status_code == 403
        assert cur.executed == []

    def test_comment_hidden_write_rejected(self, read_client, monkeypatch):
        client, hdr = read_client
        self._patch_db(monkeypatch, [])
        r = client.post("/api/v1/graph/read", headers=hdr, json={
            "cypher": "MATCH (n) WHERE n.u = 'http://x' CREATE (m) RETURN m", "graph_path": "g"})
        assert r.status_code == 403

    def test_request_limit_caps_rows_despite_query_limit(self, read_client, monkeypatch):
        client, hdr = read_client
        cur, conn = self._patch_db(monkeypatch, [(i,) for i in range(10)])
        r = client.post("/api/v1/graph/read", headers=hdr, json={
            "cypher": "MATCH (n) RETURN n LIMIT 999999", "graph_path": "g", "limit": 1})
        body = r.get_json()
        assert r.status_code == 200
        assert body["row_count"] == 1 and body["truncated"] is True
        assert cur.executed[0][0] == "SET default_transaction_read_only = on"
        assert conn.closed

    def test_bad_limit_is_not_500(self, read_client, monkeypatch):
        client, hdr = read_client
        self._patch_db(monkeypatch, [])
        r = client.post("/api/v1/graph/read", headers=hdr, json={
            "cypher": "MATCH (n) RETURN n", "graph_path": "g", "limit": "abc"})
        assert r.status_code == 200
