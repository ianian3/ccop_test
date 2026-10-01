# tests/test_csv_spec_registry.py
"""
F07 (감사 2026-09-17): 전달 규격과 UI 적재기 간 지원 차이 + 실패의 성공 표시.

- 규격 등록부(app/core/csv_spec_v48.py) == 검증기 SPEC, UI 지원 종류마다 실제 핸들러 존재
- UI 미지원 규격 파일(tbl_eg_ip_use 등)은 success=True/INSERT 0 이 아니라 오류
- 파이프라인 최상위 status 가 하위 단계 실패를 success 로 덮지 않음
"""
import importlib.util
import io
import pathlib

import pytest

from app.core import csv_spec_v48 as spec

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _validator():
    p = ROOT / "handoff/csv_spec_v4.8/validate_csv_v48.py"
    s = importlib.util.spec_from_file_location("_validate_csv_v48", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


class TestRegistry:

    def test_matches_validator_spec(self):
        assert list(spec.SPEC_KINDS) == [kw for kw, *_ in _validator().SPEC]

    def test_ui_supported_have_handlers(self):
        src = (ROOT / "app/services/rdb_service.py").read_text()
        assert spec.UI_SUPPORTED_KINDS <= set(spec.SPEC_KINDS)
        for kind in spec.UI_SUPPORTED_KINDS:
            assert f"'{kind}' in fname" in src, f"{kind} 핸들러 없음"

    @pytest.mark.parametrize("fn,kind,ok", [
        ("tbl_eg_case_prsn.csv", "tbl_eg_case_prsn", True),   # case 보다 먼저 매칭
        ("TBL_EG_CASE.csv", "tbl_eg_case", True),
        ("tbl_eg_ip_use.csv", "tbl_eg_ip_use", False),
        ("tbl_vt_loc_2차.csv", "tbl_vt_loc", False),
        ("tbl_unknown.csv", None, False),
    ])
    def test_ui_support(self, fn, kind, ok):
        k, supported, why = spec.ui_support(fn)
        assert (k, supported) == (kind, ok)
        assert (why is None) == ok


class TestUnsupportedRejectedBeforeDb:

    def test_import_predefined_returns_error_without_touching_db(self, app, monkeypatch):
        import psycopg2
        from app.services.rdb_service import RDBService
        monkeypatch.setattr(psycopg2, "connect",
                            lambda **kw: (_ for _ in ()).throw(AssertionError("DB 접속하면 안 됨")))
        with app.app_context():
            ok, msg = RDBService.import_predefined_schema_to_rdb(
                "/nonexistent.csv", "tbl_eg_ip_use.csv", clear_existing=True)
        assert ok is False and "지원하지 않는" in msg and "load_csv_to_graph.py" in msg

    def test_rdb_import_route_400(self, app, client):
        with client.session_transaction() as s:
            s["ui_authorized"] = True
        r = client.post("/api/rdb/import", content_type="multipart/form-data",
                        data={"file": (io.BytesIO(b"subj_type,subj_id,ip_addr\npsn,a,1.1.1.1\n"),
                                       "tbl_eg_ip_use.csv")})
        assert r.status_code == 400
        assert r.get_json()["unsupported"] is True


class TestPipelineStatus:

    @pytest.fixture
    def run(self, app, client, monkeypatch):
        """RDB 적재·그래프 변환을 대역으로 두고 파이프라인 호출."""
        from app.services.rdb_service import RDBService
        from app.services.rdb_to_graph_service import RdbToGraphService
        import psycopg2
        calls = {"import": [], "transfer": 0}

        def fake_import(path, fname, clear_existing=False, **kw):
            calls["import"].append((fname, clear_existing))
            if "bad" in fname:
                return False, "INSERT 오류"
            return True, {"cases": 1}

        def fake_transfer(graph, source_schema=None):   # 2026-10-01: 스키마는 인자로 전달
            calls["transfer"] += 1
            return (calls.get("l4_ok", True), {"nodes": 3, "edges": 2} if calls.get("l4_ok", True) else "boom")

        monkeypatch.setattr(RDBService, "import_predefined_schema_to_rdb", staticmethod(fake_import))
        monkeypatch.setattr(RdbToGraphService, "transfer_data", staticmethod(fake_transfer))
        monkeypatch.setattr(psycopg2, "connect",
                            lambda **kw: (_ for _ in ()).throw(RuntimeError("no db")))
        with client.session_transaction() as s:
            s["ui_authorized"] = True

        def _post(*names, l4_ok=True):
            calls["l4_ok"] = l4_ok
            files = [(io.BytesIO(b"incdnt_no\nC1\n"), n) for n in names]
            r = client.post("/api/v1/pipeline/csv_to_v40_graph", content_type="multipart/form-data",
                            data={"files": files, "graph_name": "g_pipe"})
            return r, calls
        return _post

    def test_all_supported_success(self, run):
        r, calls = run("tbl_eg_case.csv")
        assert (r.status_code, r.get_json()["status"]) == (200, "success")

    def test_unsupported_file_is_partial_not_success(self, run):
        r, calls = run("tbl_eg_case.csv", "tbl_eg_ip_use.csv")
        body = r.get_json()
        assert (r.status_code, body["status"]) == (200, "partial")
        assert any("tbl_eg_ip_use" in e for e in body["errors"])
        st = {f["name"]: f["status"] for f in body["layers"]["L2"]["files"]}
        assert st == {"tbl_eg_case.csv": "loaded", "tbl_eg_ip_use.csv": "unsupported"}

    def test_rdb_failure_reported(self, run):
        r, _ = run("tbl_eg_case.csv", "tbl_eg_case_bad.csv")
        body = r.get_json()
        assert body["status"] == "partial"
        assert any("INSERT 오류" in e for e in body["errors"])

    def test_only_unsupported_is_error_and_skips_graph(self, run):
        r, calls = run("tbl_eg_ip_use.csv")
        assert (r.status_code, r.get_json()["status"]) == (422, "error")
        assert calls["transfer"] == 0          # 스테이징 잔존분으로 그래프 만들지 않음

    def test_graph_failure_is_error(self, run):
        r, _ = run("tbl_eg_case.csv", l4_ok=False)
        assert (r.status_code, r.get_json()["status"]) == (500, "error")

    def test_fresh_clear_on_first_loaded_file(self, run):
        """미지원 파일이 첫 번째여도 초기화는 실제 적재되는 첫 파일에서."""
        _, calls = run("tbl_eg_ip_use.csv", "tbl_eg_case.csv", "tbl_vt_psn.csv")
        assert calls["import"] == [("tbl_eg_case.csv", True), ("tbl_vt_psn.csv", False)]
