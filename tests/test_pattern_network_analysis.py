"""
패턴/네트워크 분석 기능 검증 테스트 (오프라인 — DB/LLM 불필요)

목적: "차별화 기능(범죄패턴 매칭·증거완성도·네트워크투영)이 실제로 맞는지" 검증.
- 패턴/증거 로직은 순수 함수(인자로 받은 subgraph/checklist 로 동작) → mock 없이 검증.
- 네트워크 라우트는 핵심 투영이 Cypher(DB)에 있으므로, Python 조립부만 execute_cypher
  를 mock 해 검증(투영 정확성 자체는 DB 통합테스트 영역).

⚠️ 이 테스트가 드러낸 실제 버그:
   PatternAnalyzer._match_pattern 은 필수노드를 '라벨별 첫 노드'로만 매칭한다.
   같은 라벨 필수노드가 여러 개인 패턴(자금세탁체인·대포통장·통화네트워크·전화금융사기)
   은 서로 다른 슬롯이 동일 노드로 붕괴 → 올바른 체인도 오탐(false negative).
   → test_money_laundering_valid_chain_should_pass 를 xfail(strict) 로 기록.
"""
import pytest

from app.services.pattern_library import PatternLibrary, CrimePattern
from app.services.pattern_analyzer import PatternAnalyzer
from app.services.evidence_analyzer import EvidenceAnalyzer
from app.services.graph_service import GraphService


# ─── 헬퍼: 몸캠피싱(단일라벨 패턴)용 서브그래프 구성 ────────────────
def _bodycamp_nodes(include_ip=True, include_phone=True, drop_account=False):
    nodes = {
        "n_case": {"label": "vt_flnm", "properties": {"flnm": "2019-000392"}},
        "n_site": {"label": "vt_site", "properties": {}},
        "n_file": {"label": "vt_file", "properties": {}},
    }
    if not drop_account:
        nodes["n_acc"] = {"label": "vt_bacnt", "properties": {}}
    if include_ip:
        nodes["n_ip"] = {"label": "vt_ip", "properties": {}}
    if include_phone:
        nodes["n_tel"] = {"label": "vt_telno", "properties": {}}
    return nodes


def _bodycamp_edges(drop_edge=None):
    edges = [
        {"from": "n_case", "to": "n_site", "type": "digital_trace"},
        {"from": "n_case", "to": "n_file", "type": "related_to"},
        {"from": "n_case", "to": "n_acc", "type": "used_account"},
    ]
    if drop_edge is not None:
        del edges[drop_edge]
    return edges


# ══════════════════════════════════════════════════════════════════
# 1. 패턴 라이브러리 정합성
# ══════════════════════════════════════════════════════════════════
class TestPatternLibraryIntegrity:

    def test_all_patterns_loaded(self):
        pats = PatternLibrary.get_all_patterns()
        assert len(pats) == 8
        assert all(isinstance(p, CrimePattern) for p in pats.values())

    def test_expected_pattern_names_present(self):
        names = PatternLibrary.get_pattern_names()
        for expected in ["몸캠피싱", "보이스피싱", "자금세탁체인", "대포통장"]:
            assert expected in names

    def test_find_by_name(self):
        assert PatternLibrary.find_by_name("몸캠피싱") is not None
        assert PatternLibrary.find_by_name("존재하지않는패턴") is None

    def test_edges_reference_declared_node_keys(self):
        """모든 required_edge 의 from/to 는 선언된 노드 키를 가리켜야 한다(정합성)."""
        for pid, p in PatternLibrary.get_all_patterns().items():
            declared = set(p.required_nodes) | set(p.optional_nodes)
            for e in p.required_edges:
                assert e["from"] in declared, f"{pid}: edge from '{e['from']}' 미선언"
                assert e["to"] in declared, f"{pid}: edge to '{e['to']}' 미선언"

    def test_scoring_weights_sum_to_one(self):
        """required_match + optional_bonus == 1.0 이어야 score 가 [0,1] 범위."""
        for pid, p in PatternLibrary.get_all_patterns().items():
            s = p.scoring["required_match"] + p.scoring["optional_bonus"]
            assert s == pytest.approx(1.0), f"{pid}: score 합 {s}"

    def test_layer_partition_is_consistent(self):
        action = set(PatternLibrary.get_pattern_by_layer("Action"))
        case = set(PatternLibrary.get_pattern_by_layer("Case"))
        allp = set(PatternLibrary.get_all_patterns())
        assert action.isdisjoint(case)
        assert action | case == allp

    def test_to_dict_roundtrip(self):
        p = PatternLibrary.get_pattern("bodycamp_phishing")
        d = p.to_dict()
        assert d["name"] == "몸캠피싱"
        assert set(d) >= {"pattern_id", "name", "required_nodes", "required_edges", "scoring"}


# ══════════════════════════════════════════════════════════════════
# 2. 패턴 매칭 로직 (몸캠피싱 = 라벨 전부 고유 → 정상 동작 검증)
# ══════════════════════════════════════════════════════════════════
class TestPatternMatching:

    def _pattern(self):
        return PatternLibrary.get_pattern("bodycamp_phishing")

    def test_full_match_scores_one(self):
        r = PatternAnalyzer._match_pattern(
            {"nodes": _bodycamp_nodes(), "edges": _bodycamp_edges()}, self._pattern())
        assert r["score"] == 1.0
        assert r["missing"] == []
        assert len(set(r["matched_nodes"].values())) == 4  # 노드 4개 모두 고유 매핑

    def test_missing_required_node_scores_zero(self):
        r = PatternAnalyzer._match_pattern(
            {"nodes": _bodycamp_nodes(drop_account=True), "edges": _bodycamp_edges(drop_edge=2)},
            self._pattern())
        assert r["score"] == 0.0
        assert r["missing"]  # 누락 사유 존재

    def test_required_only_no_optional(self):
        """필수 노드+엣지 완비, 선택노드 0 → required_match(0.7)만."""
        r = PatternAnalyzer._match_pattern(
            {"nodes": _bodycamp_nodes(include_ip=False, include_phone=False),
             "edges": _bodycamp_edges()}, self._pattern())
        assert r["score"] == pytest.approx(0.7)
        assert r["optional_matched"] == 0

    def test_one_missing_edge_reduces_score(self):
        """엣지 1개 누락 → edge_match_rate 2/3, 선택노드 전부 있음(0.3) 포함."""
        r = PatternAnalyzer._match_pattern(
            {"nodes": _bodycamp_nodes(), "edges": _bodycamp_edges(drop_edge=0)}, self._pattern())
        expected = (2 / 3) * 0.7 + 1.0 * 0.3
        assert r["score"] == pytest.approx(round(expected, 3))
        assert len(r["missing"]) == 1

    def test_edge_direction_matters(self):
        """엣지 방향이 반대면 매칭되지 않아야 한다(digital_trace 를 site→case 로)."""
        edges = _bodycamp_edges()
        edges[0] = {"from": "n_site", "to": "n_case", "type": "digital_trace"}
        r = PatternAnalyzer._match_pattern({"nodes": _bodycamp_nodes(), "edges": edges}, self._pattern())
        assert any("digital_trace" in m for m in r["missing"])

    def test_generate_summary(self):
        assert "실패" in PatternAnalyzer._generate_summary([])
        matched = [{"pattern_name": "몸캠피싱", "confidence": 0.9, "missing_elements": []}]
        assert "몸캠피싱" in PatternAnalyzer._generate_summary(matched)


# ══════════════════════════════════════════════════════════════════
# 3. 증거 완성도 점수 로직
# ══════════════════════════════════════════════════════════════════
class TestEvidenceScoring:

    def _checklist(self, req_done, req_total, opt_done, opt_total):
        DONE, MISS = "✅ 완료", "❌ 누락"
        req = {f"r{i}": {"status": DONE if i < req_done else MISS} for i in range(req_total)}
        opt = {f"o{i}": {"status": DONE if i < opt_done else MISS} for i in range(opt_total)}
        return {"required": req, "optional": opt}

    def test_full_completeness(self):
        assert EvidenceAnalyzer._calculate_completeness(self._checklist(4, 4, 2, 2)) == pytest.approx(1.0)

    def test_required_only_is_point_seven(self):
        assert EvidenceAnalyzer._calculate_completeness(self._checklist(4, 4, 0, 2)) == pytest.approx(0.7)

    def test_half_required_no_optional(self):
        assert EvidenceAnalyzer._calculate_completeness(self._checklist(2, 4, 0, 0)) == pytest.approx(0.35)

    def test_evaluate_completeness_end_to_end(self):
        """몸캠피싱: 필수 4/4 + 선택 1/2(ip만) → 0.7 + 0.15 = 0.85."""
        matched_pattern = {
            "pattern_name": "몸캠피싱",
            "matched_nodes": {"case": "n_case", "site": "n_site", "file": "n_file", "account": "n_acc"},
        }
        subgraph = {"nodes": _bodycamp_nodes(include_ip=True, include_phone=False), "edges": []}
        res = EvidenceAnalyzer.evaluate_completeness("2019-000392", matched_pattern, subgraph)
        assert res["completeness_score"] == pytest.approx(0.85)
        assert set(res["evidence_checklist"]) == {"required", "optional"}
        assert isinstance(res["next_steps"], list)
        # 선택증거(연락처) 누락이 missing 에 잡혀야
        assert any(m["category"] == "optional" for m in res["missing_evidence"])

    def test_evaluate_no_pattern(self):
        res = EvidenceAnalyzer.evaluate_completeness("X", None, {"nodes": {}, "edges": []})
        assert res["completeness_score"] == 0.0
        assert "message" in res

    def test_analyze_missing_sorts_required_first(self):
        p = PatternLibrary.get_pattern("bodycamp_phishing")
        # 필수 계좌 누락 + 선택 전부 누락인 체크리스트
        checklist = EvidenceAnalyzer._create_checklist(
            p,
            {"nodes": {}, "edges": []},
            {"matched_nodes": {"case": "x", "site": "x", "file": "x"}},  # account 누락
        )
        missing = EvidenceAnalyzer._analyze_missing(p, checklist)
        assert missing[0]["category"] == "required"  # 필수가 항상 앞


# ══════════════════════════════════════════════════════════════════
# 4. 같은-라벨 필수노드 버그 (핵심 발견)
# ══════════════════════════════════════════════════════════════════
class TestSameLabelRequiredNodeBug:

    def _laundering_chain_subgraph(self):
        """서로 다른 계좌 4개·이체 3개로 올바른 3-hop 자금세탁 체인."""
        nodes = {
            "t1": {"label": "vt_transfer", "properties": {}},
            "t2": {"label": "vt_transfer", "properties": {}},
            "t3": {"label": "vt_transfer", "properties": {}},
            "a1": {"label": "vt_bacnt", "properties": {"actno": "1"}},
            "a2": {"label": "vt_bacnt", "properties": {"actno": "2"}},
            "a3": {"label": "vt_bacnt", "properties": {"actno": "3"}},
            "a4": {"label": "vt_bacnt", "properties": {"actno": "4"}},
        }
        edges = [
            {"from": "t1", "to": "a1", "type": "from_account"},
            {"from": "t1", "to": "a2", "type": "to_account"},
            {"from": "t2", "to": "a2", "type": "from_account"},
            {"from": "t2", "to": "a3", "type": "to_account"},
            {"from": "t3", "to": "a3", "type": "from_account"},
            {"from": "t3", "to": "a4", "type": "to_account"},
        ]
        return {"nodes": nodes, "edges": edges}

    def test_same_label_required_nodes_collapse(self):
        """현재 동작(버그) 문서화: 필수노드 7개가 라벨별 첫 노드로 붕괴 → 고유 2개."""
        p = PatternLibrary.get_pattern("money_laundering_chain")
        r = PatternAnalyzer._match_pattern(self._laundering_chain_subgraph(), p)
        # vt_transfer 3슬롯 → 1개, vt_bacnt 4슬롯 → 1개 = 고유 2개 (정상이라면 7이어야 함)
        assert len(set(r["matched_nodes"].values())) == 2

    @pytest.mark.xfail(strict=True,
                       reason="_match_pattern 이 같은 라벨 필수노드를 구분하지 못함 "
                              "→ 올바른 자금세탁 체인도 0.4점(임계 0.75 미만)으로 오탐")
    def test_money_laundering_valid_chain_should_pass(self):
        """올바른 3-hop 체인은 min_threshold 이상이어야 한다(기대 동작)."""
        p = PatternLibrary.get_pattern("money_laundering_chain")
        r = PatternAnalyzer._match_pattern(self._laundering_chain_subgraph(), p)
        assert r["score"] >= p.scoring["min_threshold"]


# ══════════════════════════════════════════════════════════════════
# 5. 네트워크 분석 라우트 (검증 400 + execute_cypher mock 조립)
# ══════════════════════════════════════════════════════════════════
@pytest.fixture
def authed(client):
    """유효 API 키를 저장소에 주입해 @require_api_key 통과."""
    from app.middleware import api_auth
    key = "pytest-net-key"
    h = api_auth.generate_api_key_hash(key)
    api_auth.API_KEYS_STORE[h] = {
        "partner_name": "pytest", "tier": "test",
        "rate_limit": 100000, "allowed_endpoints": ["*"], "is_active": True,
    }
    yield client, {"Authorization": f"Bearer {key}"}
    api_auth.API_KEYS_STORE.pop(h, None)


class TestNetworkAnalysisAPI:

    def test_project_requires_auth(self, client):
        assert client.post("/api/v1/network/project", json={"actor_label": "vt_psn"}).status_code == 401

    def test_project_invalid_label(self, authed):
        c, h = authed
        r = c.post("/api/v1/network/project", json={"actor_label": "DROP_TABLE"}, headers=h)
        assert r.status_code == 400

    def test_project_actor_equals_pivot(self, authed):
        c, h = authed
        r = c.post("/api/v1/network/project",
                   json={"actor_label": "vt_psn", "pivot_label": "vt_psn"}, headers=h)
        assert r.status_code == 400

    def test_project_assembles_and_dedups(self, authed, monkeypatch):
        c, h = authed
        rows = [
            [{"id": "p1", "name": "김철수"}, {"id": "p2", "name": "이영희"}, 3, [{"actno": "111"}]],
            [{"id": "p1", "name": "김철수"}, {"id": "p3", "name": "박민수"}, 1, [{"actno": "111"}]],
        ]
        monkeypatch.setattr(GraphService, "execute_cypher",
                            staticmethod(lambda cypher, graph_path: (True, rows)))
        r = c.post("/api/v1/network/project",
                   json={"actor_label": "vt_psn", "pivot_label": "vt_bacnt",
                         "projection_edge": "co_account"}, headers=h)
        assert r.status_code == 200
        data = r.get_json()
        assert data["stats"]["actors"] == 3       # p1,p2,p3 중복 제거
        assert data["stats"]["projected_edges"] == 2
        assert data["edges"][0]["type"] == "co_account"
        assert data["edges"][0]["weight"] == 3

    def test_bipartite_invalid_label(self, authed):
        c, h = authed
        r = c.post("/api/v1/network/bipartite", json={"actor_label": "bad"}, headers=h)
        assert r.status_code == 400

    def test_bipartite_assembles_counts(self, authed, monkeypatch):
        c, h = authed

        def fake(cypher, graph_path):
            if "actor_props" in cypher:
                return True, [[{"id": "p1"}, 5]]
            if "pivot_props" in cypher:
                return True, [[{"actno": "111"}, 7]]
            return True, [[10, 20, 35]]  # count 쿼리

        monkeypatch.setattr(GraphService, "execute_cypher", staticmethod(fake))
        r = c.post("/api/v1/network/bipartite",
                   json={"actor_label": "vt_psn", "pivot_label": "vt_bacnt"}, headers=h)
        assert r.status_code == 200
        data = r.get_json()
        assert data["actor_count"] == 10
        assert data["pivot_count"] == 20
        assert data["edge_count"] == 35
        assert data["top_actors"][0]["degree"] == 5
        assert data["top_pivots"][0]["degree"] == 7
