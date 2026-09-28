# tests/test_csv_mapping_api.py
"""
F04 (감사 2026-09-17): CSV 매핑 API 가 삭제된 AIService 메서드를 호출해 500 반환하던 결함.

- /api/etl/ai-suggest      → AIService.suggest_mapping
- /api/rdb/analyze-csv     → AIService.infer_column_mapping_for_rdb (규칙 미매칭 컬럼)
LLM 은 가짜 클라이언트로 대체 — 네트워크 불필요.
"""
import io
import json

import pytest

from app.services.ai_service import AIService


class _FakeClient:
    """chat.completions.create 가 고정 content 를 돌려주는 OpenAI 대역."""

    def __init__(self, content=None, exc=None):
        self._content, self._exc = content, exc
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        if self._exc:
            raise self._exc
        msg = type("M", (), {"content": self._content})
        return type("R", (), {"choices": [type("C", (), {"message": msg})]})


def _patch_llm(monkeypatch, content=None, exc=None):
    monkeypatch.setattr(AIService, "get_client",
                        staticmethod(lambda: _FakeClient(content, exc)))


def _csv(text):
    return {"file": (io.BytesIO(text.encode("utf-8")), "t.csv")}


class TestEtlAiSuggest:

    def test_single_row_csv_returns_mapping(self, client, monkeypatch):
        _patch_llm(monkeypatch, "```json\n" + json.dumps({
            "sourceCol": "접수번호", "targetCol": "계좌번호", "edgeType": "USED_ACCOUNT",
            "properties": [
                {"col": "피해금액", "target": "edge", "key": "amount_krw"},
                {"col": "환각컬럼", "target": "edge", "key": "x"},     # 헤더에 없음 → 제거
                {"col": "은행", "target": "weird", "key": "bank_nm"},  # target 교정 → edge
            ]}) + "\n```")
        r = client.post("/api/etl/ai-suggest", data=_csv("접수번호,계좌번호,피해금액,은행\n2026-1,110-1,1000,KB\n"),
                        content_type="multipart/form-data")
        assert r.status_code == 200
        m = r.get_json()["mapping"]
        assert (m["sourceCol"], m["targetCol"], m["edgeType"]) == ("접수번호", "계좌번호", "USED_ACCOUNT")
        assert [p["col"] for p in m["properties"]] == ["피해금액", "은행"]
        assert m["properties"][1]["target"] == "edge"

    def test_hallucinated_columns_nulled(self, client, monkeypatch):
        _patch_llm(monkeypatch, json.dumps({"sourceCol": "없는컬럼", "targetCol": "계좌번호",
                                            "edgeType": "BAD TYPE;DROP", "properties": []}))
        r = client.post("/api/etl/ai-suggest", data=_csv("계좌번호\n110-1\n"),
                        content_type="multipart/form-data")
        m = r.get_json()["mapping"]
        assert m["sourceCol"] is None and m["targetCol"] == "계좌번호"
        assert m["edgeType"] == "RELATED_TO"

    def test_missing_file_is_400(self, client):
        assert client.post("/api/etl/ai-suggest", data={}).status_code == 400

    def test_llm_failure_is_502_not_500(self, client, monkeypatch):
        _patch_llm(monkeypatch, exc=RuntimeError("connection refused"))
        r = client.post("/api/etl/ai-suggest", data=_csv("a,b\n1,2\n"),
                        content_type="multipart/form-data")
        assert r.status_code == 502
        assert "connection refused" not in r.get_data(as_text=True)


class TestRdbAnalyzeCsv:

    def test_unknown_column_inferred_by_llm(self, client, monkeypatch):
        _patch_llm(monkeypatch, json.dumps({"zz_mystery": "ip", "zz_other": "not-a-type",
                                            "hallucinated": "phone"}))
        r = client.post("/api/rdb/analyze-csv",
                        data=_csv("zz_mystery,zz_other\n1.2.3.4,x\n"),
                        content_type="multipart/form-data")
        assert r.status_code == 200, r.get_data(as_text=True)
        by_col = {m["column"]: m for m in r.get_json()["mapping"]}
        assert (by_col["zz_mystery"]["mapped_type"], by_col["zz_mystery"]["method"]) == ("ip", "llm")
        assert by_col["zz_other"]["method"] == "unmapped"   # 허용 외 타입은 버림

    def test_llm_failure_degrades_to_rule_mapping(self, client, monkeypatch):
        _patch_llm(monkeypatch, exc=RuntimeError("down"))
        r = client.post("/api/rdb/analyze-csv",
                        data=_csv("zz_mystery\nabc\n"),
                        content_type="multipart/form-data")
        assert r.status_code == 200


class TestInferColumnMappingFilter:

    def test_filters_unknown_columns_and_types(self, app, monkeypatch):
        _patch_llm(monkeypatch, 'noise {"c1": "ip", "c2": "bogus", "c9": "phone"} trailing')
        with app.app_context():
            out = AIService.infer_column_mapping_for_rdb(["c1", "c2"], [{"c1": "1.1.1.1"}])
        assert out == {"c1": "ip"}

    def test_empty_columns_skips_llm(self, app, monkeypatch):
        _patch_llm(monkeypatch, exc=AssertionError("LLM 호출되면 안 됨"))
        with app.app_context():
            assert AIService.infer_column_mapping_for_rdb([], []) == {}
