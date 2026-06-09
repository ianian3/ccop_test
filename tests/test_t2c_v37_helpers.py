"""
test_t2c_v37_helpers.py — LangGraphAgent 헬퍼 단위 테스트

대상:
- LangGraphAgent._wrap_native_cypher
- LangGraphAgent._rewrite_order_by_dot_access
"""
from app.services.langgraph_agent import LangGraphAgent


# ──────────────────────────────────────────────────────────────────────────────
# _wrap_native_cypher
# ──────────────────────────────────────────────────────────────────────────────

class TestWrapNativeCypher:
    def test_simple_node_return(self):
        out = LangGraphAgent._wrap_native_cypher(
            "MATCH (p:vt_psn) RETURN p LIMIT 5", "tccop_graph_v6"
        )
        assert "SELECT * FROM cypher('tccop_graph_v6'" in out
        assert "AS (p agtype)" in out
        assert "LIMIT 5" in out

    def test_dot_access_return_uses_col_alias(self):
        out = LangGraphAgent._wrap_native_cypher(
            "MATCH (d:vt_dev) RETURN d.device_id, d.imei", "tccop_graph_v6"
        )
        assert "(col0 agtype, col1 agtype)" in out

    def test_mixed_var_and_dot_access(self):
        out = LangGraphAgent._wrap_native_cypher(
            "MATCH (s:vt_site)-[:belongs_to_campaign]->(c:site_cluster) RETURN s, c, s.sim_score",
            "tccop_graph_v6",
        )
        assert "s agtype" in out and "c agtype" in out

    def test_already_wrapped_passthrough(self):
        wrapped = "SELECT * FROM cypher('g', $$ MATCH (n) RETURN n $$) AS (n agtype)"
        out = LangGraphAgent._wrap_native_cypher(wrapped, "tccop_graph_v6")
        assert out.startswith("SELECT")
        assert out.endswith(";")

    def test_empty_input(self):
        assert LangGraphAgent._wrap_native_cypher("", "g") == ""
        assert LangGraphAgent._wrap_native_cypher("   ", "g").strip() == ""

    def test_graph_path_with_quote_escaped(self):
        out = LangGraphAgent._wrap_native_cypher(
            "MATCH (n) RETURN n", "my'graph"
        )
        assert "'my''graph'" in out

    def test_shortest_path(self):
        out = LangGraphAgent._wrap_native_cypher(
            "MATCH p=shortestPath((a:vt_psn {name:'A'})-[*..6]-(b:vt_psn {name:'B'})) RETURN p",
            "tccop_graph_v6",
        )
        assert "(p agtype)" in out


# ──────────────────────────────────────────────────────────────────────────────
# _rewrite_order_by_dot_access
# ──────────────────────────────────────────────────────────────────────────────

class TestRewriteOrderBy:
    def test_simple_dot_access_order_by(self):
        cypher = "MATCH (c:pt_cluster) RETURN c.cluster_id, c.damage_amt_sum ORDER BY c.damage_amt_sum DESC LIMIT 5"
        out = LangGraphAgent._rewrite_order_by_dot_access(cypher)
        assert "AS _ord_0" in out
        assert "ORDER BY _ord_0 DESC" in out
        assert "LIMIT 5" in out  # LIMIT 보존

    def test_simple_variable_unchanged(self):
        cypher = "MATCH (p:vt_psn) RETURN p ORDER BY p"
        out = LangGraphAgent._rewrite_order_by_dot_access(cypher)
        # 단순 변수(p)는 변경하지 않음
        assert "ORDER BY p" in out
        assert "_ord_" not in out

    def test_existing_alias_reused(self):
        cypher = "MATCH (c:pt_cluster) RETURN c.damage_amt_sum AS amt ORDER BY amt DESC"
        out = LangGraphAgent._rewrite_order_by_dot_access(cypher)
        # 이미 alias 있으면 그대로
        assert "_ord_" not in out
        assert "ORDER BY amt DESC" in out

    def test_no_order_by_unchanged(self):
        cypher = "MATCH (n) RETURN n LIMIT 10"
        out = LangGraphAgent._rewrite_order_by_dot_access(cypher)
        assert out == cypher

    def test_multiple_order_by_keys(self):
        cypher = "MATCH (s:vt_site) RETURN s.url_addr, s.sim_score ORDER BY s.sim_score DESC, s.url_addr"
        out = LangGraphAgent._rewrite_order_by_dot_access(cypher)
        assert "_ord_0" in out and "_ord_1" in out
        assert "ORDER BY _ord_0 DESC, _ord_1" in out

    def test_order_by_followed_by_limit(self):
        cypher = "MATCH (d:vt_dev) RETURN d.device_id ORDER BY d.device_id LIMIT 3"
        out = LangGraphAgent._rewrite_order_by_dot_access(cypher)
        assert "LIMIT 3" in out

    def test_integration_wrap_with_order_by(self):
        cypher = "MATCH (c:pt_cluster) RETURN c.cluster_id, c.damage_amt_sum ORDER BY c.damage_amt_sum DESC LIMIT 5"
        out = LangGraphAgent._wrap_native_cypher(cypher, "tccop_graph_v6")
        assert "SELECT * FROM cypher('tccop_graph_v6'" in out
        assert "AS _ord_0" in out
        assert "LIMIT 5" in out
        assert "_ord_0 agtype" in out


# ──────────────────────────────────────────────────────────────────────────────
# _validate_cypher_schema (Phase 3-A)
# ──────────────────────────────────────────────────────────────────────────────

class TestValidateCypherSchema:
    def test_valid_v36_pattern(self):
        ok, err = LangGraphAgent._validate_cypher_schema(
            "MATCH (p:vt_psn)-[:suspect_in]->(c:vt_case) RETURN p, c"
        )
        assert ok is True and err == ""

    def test_valid_v37_pattern(self):
        ok, err = LangGraphAgent._validate_cypher_schema(
            "MATCH (p:vt_petition)-[:belongs_to_cluster]->(c:pt_cluster) RETURN p, c"
        )
        assert ok is True

    def test_invalid_label(self):
        ok, err = LangGraphAgent._validate_cypher_schema(
            "MATCH (p:vt_unknown)-[:suspect_in]->(c:vt_case) RETURN p, c"
        )
        assert ok is False
        assert "vt_unknown" in err

    def test_invalid_edge(self):
        ok, err = LangGraphAgent._validate_cypher_schema(
            "MATCH (p:vt_psn)-[:nonexistent_rel]->(c:vt_case) RETURN p, c"
        )
        assert ok is False
        assert "nonexistent_rel" in err

    def test_pt_site_cluster_labels_accepted(self):
        ok, err = LangGraphAgent._validate_cypher_schema(
            "MATCH (s:vt_site)-[:belongs_to_campaign]->(c:site_cluster) RETURN s, c"
        )
        assert ok is True

    def test_variable_length_path_not_rejected(self):
        ok, err = LangGraphAgent._validate_cypher_schema(
            "MATCH p=shortestPath((a:vt_psn)-[*..6]-(b:vt_psn)) RETURN p"
        )
        assert ok is True
