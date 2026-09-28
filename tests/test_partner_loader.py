# tests/test_partner_loader.py
"""
F05·F06 (감사 2026-09-17): 전달용 CSV 적재기(load_csv_to_graph.py / load_partner_csv.py)

F05 재실행 멱등성 — 기존 그래프를 읽어 중복 CREATE 방지, 2차 납품분 보강·집계 누적
F06 식별 충돌 — 같은 식별 키에 다른 bank_cd·psn_id·platform 이 오면 조용히 합치지 않고 보고
DB 는 가짜 커서로 대체.
"""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATHS = {
    "handoff": ROOT / "handoff/csv_spec_v4.8/load_csv_to_graph.py",
    "scripts": ROOT / "scripts/load_partner_csv.py",
}


def _load(path):
    spec = importlib.util.spec_from_file_location(f"_loader_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(params=sorted(PATHS))
def M(request):
    return _load(PATHS[request.param])


class FakeCursor:
    """preload 쿼리에 미리 정한 결과를 돌려주고, 쓰기 문장은 기록만 한다."""

    def __init__(self, nodes=None, agg=None):
        self.nodes = nodes or {}     # label → [props]
        self.agg = agg or {}         # el → [(xprops, yprops, rprops)]
        self.executed = []
        self._result = []

    def execute(self, q, params=None):
        self.executed.append(q)
        self._result = []
        if q.startswith("MATCH (n:") and "RETURN properties(n)" in q:
            label = q[len("MATCH (n:"):q.index(")")]
            self._result = [(p,) for p in self.nodes.get(label, [])]
        elif "RETURN properties(x), properties(y), properties(r)" in q:
            el = q.split("[r:")[1].split("]")[0]
            la = q.split("(x:")[1].split(")")[0]
            self._result = [row for row in self.agg.get(el, []) if row[3] == la]
            self._result = [row[:3] for row in self._result]

    def fetchall(self):
        return self._result

    def creates(self):
        return [q for q in self.executed if q.startswith("CREATE")]

    def sets(self):
        return [q for q in self.executed if q.startswith("MATCH (n:") and " SET " in q]


def _run(M, cur, fn):
    L = M.Loader(cur)
    L.preload([("vt_bacnt", "account_no"), ("vt_psn", "name"), ("vt_telno", "telno"),
               ("vt_id", "id_val")],
              [("contacted", "vt_telno", "telno", "vt_telno", "telno"),
               ("transferred_to", "vt_bacnt", "account_no", "vt_bacnt", "account_no"),
               ("used_ip", "vt_telno", "telno", "vt_ip", "ip_addr")])
    fn(L)
    L.flush()
    return L


class TestIdempotency:

    def test_rerun_same_data_creates_nothing(self, M):
        def load(L):
            L.node("vt_bacnt", "account_no", "110-1", {"bank_cd": "004", "source_id": "DOC-1"})
            L.node("vt_psn", "name", "홍길동", {"source_id": "DOC-1"})
        first = FakeCursor()
        _run(M, first, load)
        assert len(first.creates()) == 2
        # 2회차: 1회차 결과가 그래프에 있는 상태
        second = FakeCursor(nodes={
            "vt_bacnt": [{"account_no": "110-1", "bank_cd": "004", "source_id": "DOC-1"}],
            "vt_psn": [{"name": "홍길동", "source_id": "DOC-1"}],
        })
        L = _run(M, second, load)
        assert second.creates() == [] and second.sets() == []
        assert (L.n_node, L.n_enriched) == (0, 0)

    def test_second_delivery_enriches_existing_node(self, M):
        cur = FakeCursor(nodes={"vt_bacnt": [{"account_no": "110-1", "source_id": "DOC-1"}]})
        L = _run(M, cur, lambda L: L.node("vt_bacnt", "account_no", "110-1",
                                          {"dpstr": "홍길동", "source_id": "DOC-2"}))
        assert cur.creates() == []
        (q,) = cur.sets()
        assert "n.dpstr = '홍길동'" in q and "n.source_id = 'DOC-1|DOC-2'" in q
        assert L.n_enriched == 1

    def test_existing_props_not_overwritten(self, M):
        cur = FakeCursor(nodes={"vt_psn": [{"name": "김철수", "dob": "1990", "source_id": "A"}]})
        _run(M, cur, lambda L: L.node("vt_psn", "name", "김철수", {"dob": "1991", "source_id": "A"}))
        assert cur.sets() == []   # dob 는 기존 값 유지, 출처도 동일 → 쓰기 없음

    def test_same_node_many_rows_single_write(self, M):
        cur = FakeCursor()
        def load(L):
            for i in range(50):
                L.node("vt_telno", "telno", "01011112222", {"source_id": f"S{i % 2}"})
        _run(M, cur, load)
        (q,) = cur.creates()
        assert "source_id: 'S0|S1'" in q   # 출처 합집합 보존 (이전: 첫 행 출처만)


class TestAggregatedEdges:

    def _contacted(self, src, calls=2):
        return lambda L: L.edge("contacted", ("vt_telno", "telno", "A"), ("vt_telno", "telno", "B"),
                                {"channel": "call", "call_count": calls, "first_dt": "2026-01-02",
                                 "last_dt": "2026-01-05", "source_id": src},
                                match_props={"channel": "call"})

    def _existing(self, src):
        return {"contacted": [({"telno": "A"}, {"telno": "B"},
                               {"channel": "call", "call_count": 3, "first_dt": "2026-01-01",
                                "last_dt": "2026-01-03", "source_id": src}, "vt_telno")]}

    def test_rerun_same_source_skipped(self, M):
        cur = FakeCursor(agg=self._existing("DOC-1"))
        L = _run(M, cur, self._contacted("DOC-1"))
        assert not any("MERGE" in q for q in cur.executed)
        assert L.n_edge_skipped == 1

    def test_new_source_accumulates(self, M):
        cur = FakeCursor(agg=self._existing("DOC-1"))
        _run(M, cur, self._contacted("DOC-2", calls=2))
        (q,) = [q for q in cur.executed if "MERGE" in q]
        assert "r.call_count = 5" in q
        assert "r.first_dt = '2026-01-01'" in q and "r.last_dt = '2026-01-05'" in q
        assert "r.source_id = 'DOC-1|DOC-2'" in q

    def test_partial_overlap_not_double_counted(self, M):
        cur = FakeCursor(agg=self._existing("DOC-1"))
        L = _run(M, cur, self._contacted("DOC-1|DOC-2"))
        assert not any("MERGE" in q for q in cur.executed)
        assert ("contacted", "source_id(부분중복)") in L.conflicts


class TestIdentityConflicts:

    def test_same_account_different_bank_reported(self, M):
        L = _run(M, FakeCursor(), lambda L: (
            L.node("vt_bacnt", "account_no", "110-1", {"bank_cd": "004"}),
            L.node("vt_bacnt", "account_no", "110-1", {"bank_cd": "088"})))
        assert L.conflicts[("vt_bacnt", "bank_cd")] == {("110-1", "004", "088")}

    def test_homonym_different_psn_id_reported(self, M):
        cur = FakeCursor(nodes={"vt_psn": [{"name": "홍길동", "psn_id": "P-1"}]})
        L = _run(M, cur, lambda L: L.node("vt_psn", "name", "홍길동", {"psn_id": "P-2"}))
        assert L.conflicts[("vt_psn", "psn_id")] == {("홍길동", "P-1", "P-2")}

    def test_same_id_different_platform_reported(self, M):
        L = _run(M, FakeCursor(), lambda L: (
            L.node("vt_id", "id_val", "abc", {"platform": "kakao"}),
            L.node("vt_id", "id_val", "abc", {"platform": "telegram"})))
        assert ("vt_id", "platform") in L.conflicts

    def test_non_identity_prop_difference_not_reported(self, M):
        L = _run(M, FakeCursor(), lambda L: (
            L.node("vt_bacnt", "account_no", "110-1", {"dpstr": "A"}),
            L.node("vt_bacnt", "account_no", "110-1", {"dpstr": "B"})))
        assert not L.conflicts


def test_two_loader_copies_in_sync():
    """전달본과 내부본의 코드 본문(docstring 제외)이 같아야 한다."""
    bodies = [p.read_text().split("import argparse", 1)[1] for p in PATHS.values()]
    assert bodies[0] == bodies[1]


class TestTimeAggregation:
    """협력기관 질의(2026-09-28): used_ip·located_at 이 시각이 달라도 1엣지로 합쳐지며
    시각이 사라지던 문제 — 쌍당 1엣지는 유지하되 기간·건수 보존."""

    def _ip(self, L, vf, vt=None, at=None, src="DOC-1"):
        L.agg_edge("used_ip", ("vt_telno", "telno", "010"), ("vt_ip", "ip_addr", "1.2.3.4"),
                   {"valid_from": vf, "valid_to": vt or vf, "usage_count": 1, "access_type": at},
                   source_id=src)

    def _merges(self, cur, el):
        return [q for q in cur.executed if f"[r:{el}" in q and "MERGE" in q]

    def test_used_ip_keeps_first_last_and_count(self, M):
        cur = FakeCursor()
        _run(M, cur, lambda L: (self._ip(L, "2026-03-01 09:00:00", at="banking"),
                                self._ip(L, "2026-03-05 14:00:00", at="web"),
                                self._ip(L, "2026-03-03 11:00:00", at="banking", src="DOC-2")))
        (q,) = self._merges(cur, "used_ip")
        assert "r.valid_from = '2026-03-01 09:00:00'" in q
        assert "r.valid_to = '2026-03-05 14:00:00'" in q
        assert "r.usage_count = 3" in q
        assert "r.access_type = 'banking|web'" in q
        assert "r.source_id = 'DOC-1|DOC-2'" in q

    def test_used_ip_explicit_valid_to_wins(self, M):
        cur = FakeCursor()
        _run(M, cur, lambda L: self._ip(L, "2026-03-01", vt="2026-06-30"))
        (q,) = self._merges(cur, "used_ip")
        assert "r.valid_to = '2026-06-30'" in q

    def test_used_ip_second_delivery_accumulates(self, M):
        cur = FakeCursor(agg={"used_ip": [({"telno": "010"}, {"ip_addr": "1.2.3.4"},
                                           {"valid_from": "2026-02-01", "valid_to": "2026-02-10",
                                            "usage_count": 4, "access_type": "web",
                                            "source_id": "DOC-0"}, "vt_telno")]})
        _run(M, cur, lambda L: self._ip(L, "2026-03-01", at="banking", src="DOC-1"))
        (q,) = self._merges(cur, "used_ip")
        assert "r.usage_count = 5" in q
        assert "r.valid_from = '2026-02-01'" in q and "r.valid_to = '2026-03-01'" in q
        assert "r.access_type = 'banking|web'" in q

    def test_located_at_with_and_without_time(self, M):
        cur = FakeCursor()
        def load(L):
            for t in ("2026-03-02 10:00:00", "2026-03-09 18:00:00", None):
                L.agg_edge("located_at", ("vt_telno", "telno", "010"), ("vt_loc", "loc_id", "L1"),
                           {"first_dt": t, "last_dt": t, "evt_count": 1 if t else 0}, source_id="D")
            L.agg_edge("located_at", ("vt_atm", "atm_nm", "ATM1"), ("vt_loc", "loc_id", "L1"),
                       {"first_dt": None, "last_dt": None, "evt_count": 0}, source_id="D")
        _run(M, cur, load)
        tel = [q for q in self._merges(cur, "located_at") if "vt_telno" in q][0]
        atm = [q for q in self._merges(cur, "located_at") if "vt_atm" in q][0]
        assert "r.evt_count = 2" in tel and "r.first_dt = '2026-03-02 10:00:00'" in tel
        assert "r.last_dt = '2026-03-09 18:00:00'" in tel
        assert "first_dt" not in atm and "evt_count" not in atm   # 정적 위치는 시각 속성 없음


def test_agg_rules_match_sot():
    """적재기 집계 규칙 == 온톨로지 SoT RELATIONSHIPS[*]['aggregation'] (used_ip·located_at)."""
    from app.middleware.services.ontology_service import KICSCrimeDomainOntology as O
    M = _load(PATHS["handoff"])
    for el in ("used_ip", "located_at"):
        sot = O.RELATIONSHIPS[el]
        rule = M.AGG_RULES[el]
        agg = sot["aggregation"]
        assert set(rule["sum"]) == set(agg["sum"])
        assert set(rule["min"]) == set(agg["min"]) and set(rule["max"]) == set(agg["max"])
        assert set(rule["union"]) | {"source_id"} == set(agg["union"])
        written = set(rule["sum"]) | set(rule["min"]) | set(rule["max"]) | set(rule["union"])
        assert written <= set(sot["properties"]), f"{el}: SoT properties 에 없는 속성 적재"
