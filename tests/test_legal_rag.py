# tests/test_legal_rag.py
"""
법률 RAG v2 검증 테스트 (오프라인 — DB/LLM/네트워크 불필요)

검증 대상: app/services/legal_rag_service.py + /api/v1/legal/* 라우트
- 토크나이저/BM25/RRF 는 순수 함수 → mock 없이 수학적으로 검증.
- 임베딩/rerank/답변 LLM 은 전부 monkeypatch — 네트워크 호출 0.
- 폐쇄망 강등(BM25-only), 근거 부족 시 거절, rerank 재정렬을 계약으로 고정.
"""
import json

import numpy as np
import pytest

from app.services.legal_rag_service import (
    BM25Index,
    LegalRAGService,
    chunk_text,
    normalize_record,
    rrf_fuse,
    tokenize,
)


# ─── 공용 fixture ──────────────────────────────────────────────
CORPUS = [
    {"doc_id": "fraud", "law_name": "형법", "article_ref": "제347조", "title": "사기",
     "content": "사람을 기망하여 재물의 교부를 받은 자는 십년 이하의 징역에 처한다."},
    {"doc_id": "extort", "law_name": "형법", "article_ref": "제350조", "title": "공갈",
     "content": "사람을 공갈하여 재물의 교부를 받은 자를 처벌한다."},
    {"doc_id": "stop", "law_name": "특별법", "article_ref": "제4조", "title": "지급정지",
     "content": "금융회사는 사기이용계좌에 대하여 지급정지 조치를 하여야 한다."},
    {"doc_id": "account", "law_name": "전자금융거래법", "article_ref": "제6조", "title": "접근매체",
     "content": "접근매체인 통장을 양도하거나 대여하여서는 아니 된다. 대포통장 수사의 기본 조항."},
]


def _mock_vec(text, dim=64):
    """토큰 md5 해시 bag — 결정적 mock 임베딩 (PYTHONHASHSEED 무관)."""
    import hashlib
    v = np.zeros(dim, dtype=np.float32)
    for t in tokenize(text):
        v[int(hashlib.md5(t.encode()).hexdigest(), 16) % dim] += 1.0
    n = np.linalg.norm(v)
    return v / n if n else v


@pytest.fixture(autouse=True)
def _isolate_service(monkeypatch):
    """네트워크 차단 + 상태 격리: 임베딩/rerank 백엔드를 기본 무효화하고 인덱스를 리셋."""
    monkeypatch.setattr(LegalRAGService, "_embed_query", classmethod(lambda cls, q: None))
    monkeypatch.setattr(LegalRAGService, "_rerank_client", classmethod(lambda cls: (None, None)))
    yield
    LegalRAGService._state = None


def _install(records=CORPUS, with_embeddings=False):
    emb = [_mock_vec(f"{r['law_name']} {r['article_ref']} {r['title']} {r['content']}")
           for r in records] if with_embeddings else None
    state = LegalRAGService.build_index(records, emb)
    LegalRAGService.install_index(state)
    return state


# ══════════════════════════════════════════════════════════════
# 1. 토크나이저 — 한글 bigram
# ══════════════════════════════════════════════════════════════
class TestTokenizer:

    def test_hangul_run_and_bigrams(self):
        toks = tokenize("대포통장")
        assert "대포통장" in toks            # 원형
        assert {"대포", "포통", "통장"} <= set(toks)  # bigram

    def test_mixed_language_and_numbers(self):
        toks = tokenize("제347조 BM25 검색")
        assert "347" in toks and "bm25" in toks and "검색" in toks

    def test_single_char_no_bigram(self):
        assert tokenize("제") == ["제"]

    def test_empty_and_none(self):
        assert tokenize("") == []
        assert tokenize(None) == []


# ══════════════════════════════════════════════════════════════
# 2. BM25 — 랭킹 수학
# ══════════════════════════════════════════════════════════════
class TestBM25:

    def test_matching_doc_ranked_first(self):
        docs = [tokenize("지급정지 절차"), tokenize("통장 양도 금지"), tokenize("자동차 등록")]
        idx = BM25Index(docs)
        top = idx.search(tokenize("지급정지"), top_n=3)
        assert top and top[0][0] == 0

    def test_no_match_returns_empty(self):
        idx = BM25Index([tokenize("사기죄 처벌")])
        assert idx.search(tokenize("우주여행"), top_n=5) == []

    def test_rare_term_beats_common_term(self):
        """모든 문서에 있는 흔한 토큰보다 희귀 토큰 매치가 높은 점수를 받아야 한다(IDF)."""
        docs = [tokenize("처벌 처벌 지급정지"), tokenize("처벌 양도"), tokenize("처벌 등록")]
        idx = BM25Index(docs)
        top = idx.search(tokenize("지급정지 처벌"), top_n=3)
        assert top[0][0] == 0

    def test_empty_index(self):
        assert BM25Index([]).search(tokenize("사기"), top_n=3) == []


# ══════════════════════════════════════════════════════════════
# 3. RRF 융합
# ══════════════════════════════════════════════════════════════
class TestRRF:

    def test_score_formula(self):
        fused = rrf_fuse([[7], [7]], k=60)
        assert fused[0][0] == 7
        assert fused[0][1] == pytest.approx(2.0 / 61.0)

    def test_doc_in_both_lists_beats_single_list_top(self):
        # doc 1: 양쪽 2위 (1/62+1/62) > doc 0: 한쪽 1위 (1/61)
        fused = rrf_fuse([[0, 1], [2, 1]], k=60)
        assert fused[0][0] == 1

    def test_empty(self):
        assert rrf_fuse([[], []]) == []


# ══════════════════════════════════════════════════════════════
# 4. 레코드 정규화 / 청킹
# ══════════════════════════════════════════════════════════════
class TestNormalizeAndChunk:

    def test_record_without_content_dropped(self):
        assert normalize_record({"law_name": "형법", "content": "  "}) is None

    def test_doc_id_derived_from_law_name(self):
        rec = normalize_record({"law_name": "전자금융거래법", "content": "본문"})
        assert rec["doc_id"] == "전자금융거래법"

    def test_short_text_single_chunk(self):
        assert chunk_text("짧은 조문.") == ["짧은 조문."]

    def test_long_text_split_with_progress(self):
        text = ("가나다라마바사아자차카타파하. " * 100).strip()
        chunks = chunk_text(text, size=200, overlap=20)
        assert len(chunks) > 1
        assert all(len(c) <= 200 for c in chunks)


# ══════════════════════════════════════════════════════════════
# 5. 하이브리드 검색 — 모드/강등/융합
# ══════════════════════════════════════════════════════════════
class TestHybridSearch:

    def test_bm25_mode_finds_relevant_statute(self):
        _install()
        r = LegalRAGService.hybrid_search("대포통장 양도 처벌", top_k=2, mode="bm25", rerank=False)
        assert r["mode_used"] == "bm25"
        assert r["results"][0]["doc_id"] == "account"

    def test_empty_index_returns_note(self):
        _install(records=[])
        r = LegalRAGService.hybrid_search("사기", top_k=3, rerank=False)
        assert r["results"] == [] and r["mode_used"] == "empty"

    def test_hybrid_degrades_to_bm25_without_corpus_embeddings(self):
        """코퍼스 임베딩이 없으면 hybrid 요청도 BM25-only 로 강등 (폐쇄망 시나리오)."""
        _install(with_embeddings=False)
        r = LegalRAGService.hybrid_search("지급정지", top_k=2, mode="hybrid", rerank=False)
        assert "bm25" in r["mode_used"]
        assert any("임베딩" in n for n in r["notes"])
        assert r["results"][0]["doc_id"] == "stop"

    def test_hybrid_degrades_when_query_embedding_fails(self, monkeypatch):
        """코퍼스 벡터는 있어도 질의 임베딩 실패(백엔드 다운) 시 BM25 로 계속 동작."""
        _install(with_embeddings=True)
        monkeypatch.setattr(LegalRAGService, "_embed_query", classmethod(lambda cls, q: None))
        r = LegalRAGService.hybrid_search("지급정지", top_k=2, mode="hybrid", rerank=False)
        assert "bm25" in r["mode_used"] and r["results"]

    def test_full_hybrid_uses_rrf_and_reports_ranks(self, monkeypatch):
        _install(with_embeddings=True)
        monkeypatch.setattr(LegalRAGService, "_embed_query",
                            classmethod(lambda cls, q: _mock_vec(q)))
        r = LegalRAGService.hybrid_search("통장 양도 대포통장", top_k=3, mode="hybrid", rerank=False)
        assert r["mode_used"] == "hybrid"
        top = r["results"][0]
        assert top["doc_id"] == "account"
        assert top["scores"]["rrf"] > 0
        assert top["scores"]["bm25_rank"] is not None

    def test_vector_mode_without_backend_falls_back(self):
        _install(with_embeddings=True)  # autouse fixture 가 _embed_query=None
        r = LegalRAGService.hybrid_search("지급정지", top_k=2, mode="vector", rerank=False)
        assert r["mode_used"] == "bm25_only"


# ══════════════════════════════════════════════════════════════
# 6. LLM Rerank — 재정렬/실패 무해화
# ══════════════════════════════════════════════════════════════
class _FakeCompletion:
    def __init__(self, content):
        self.choices = [type("C", (), {"message": type("M", (), {"content": content})()})()]


class _FakeLLM:
    def __init__(self, content):
        self._content = content
        self.calls = 0
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.calls += 1
                outer.last_kwargs = kwargs
                return _FakeCompletion(outer._content)

        self.chat = type("Chat", (), {"completions": _Completions()})()


class TestRerank:

    def test_rerank_reorders_by_llm_scores(self, monkeypatch):
        _install()
        state = LegalRAGService._state
        # "재물 교부"는 사기(fraud)·공갈(extort) 두 조문에 매칭 → 2위 문서가 존재
        r0 = LegalRAGService.hybrid_search("재물 교부", top_k=4, mode="bm25", rerank=False)
        assert len(r0["results"]) >= 2, "테스트 전제: 질의가 2개 이상 문서에 매칭되어야 함"
        loser = next(x for x in r0["results"] if x["rank"] > 1)
        loser_idx = next(i for i, c in enumerate(state["chunks"]) if c["doc_id"] == loser["doc_id"])
        scores = {str(i): 0 for i in range(len(state["chunks"]))}
        scores[str(loser_idx)] = 3
        fake = _FakeLLM(json.dumps({"scores": scores}))
        monkeypatch.setattr(LegalRAGService, "_rerank_client",
                            classmethod(lambda cls: (fake, "fake-model")))

        r = LegalRAGService.hybrid_search("재물 교부", top_k=4, mode="bm25", rerank=True)
        assert r["rerank_used"] is True
        assert r["results"][0]["doc_id"] == loser["doc_id"]
        assert fake.calls == 1  # listwise 단일 호출

    def test_rerank_failure_keeps_fusion_order(self, monkeypatch):
        _install()
        broken = _FakeLLM("not-json{{{")
        monkeypatch.setattr(LegalRAGService, "_rerank_client",
                            classmethod(lambda cls: (broken, "fake-model")))
        r = LegalRAGService.hybrid_search("대포통장 양도", top_k=2, mode="bm25", rerank=True)
        assert r["rerank_used"] is False          # 실패 → 융합 순서 유지
        assert r["results"][0]["doc_id"] == "account"

    def test_rerank_off_never_calls_llm(self, monkeypatch):
        _install()
        fake = _FakeLLM(json.dumps({"scores": {}}))
        monkeypatch.setattr(LegalRAGService, "_rerank_client",
                            classmethod(lambda cls: (fake, "fake-model")))
        LegalRAGService.hybrid_search("사기", top_k=2, mode="bm25", rerank=False)
        assert fake.calls == 0


# ══════════════════════════════════════════════════════════════
# 7. 근거 인용 답변 — 거절/인용 계약
# ══════════════════════════════════════════════════════════════
class TestAnswer:

    def test_refuses_when_no_evidence(self):
        _install(records=[])
        out = LegalRAGService.answer("아무 질문")
        assert out["success"] is False
        assert out["citations"] == []
        assert "disclaimer" in out

    def test_refuses_when_all_rerank_scores_zero(self, monkeypatch):
        _install()
        fake = _FakeLLM(json.dumps({"scores": {str(i): 0 for i in range(len(CORPUS))}}))
        monkeypatch.setattr(LegalRAGService, "_rerank_client",
                            classmethod(lambda cls: (fake, "fake-model")))
        out = LegalRAGService.answer("오늘 점심 메뉴 추천해줘")
        assert out["success"] is False

    def test_grounded_answer_includes_citations_and_disclaimer(self, monkeypatch):
        _install()
        fake_answer = _FakeLLM("📖 관련 법률: 전자금융거래법 제6조 [1]")
        monkeypatch.setattr(LegalRAGService, "_answer_backend",
                            classmethod(lambda cls: (fake_answer, "fake-model", None)))
        out = LegalRAGService.answer("대포통장 양도 처벌", top_k=2)
        assert out["success"] is True
        assert out["citations"][0]["n"] == 1
        assert out["citations"][0]["doc_id"] == "account"
        assert "법률 자문이 아닙니다" in out["disclaimer"]
        assert out["retrieval"]["results"]  # RAGAS 컨텍스트 복원용

    def test_no_answer_backend_returns_search_only(self, monkeypatch):
        _install()
        monkeypatch.setattr(LegalRAGService, "_answer_backend",
                            classmethod(lambda cls: (None, None, None)))
        out = LegalRAGService.answer("대포통장 양도 처벌")
        assert out["success"] is False
        assert out["citations"]  # 검색 결과는 제공


# ══════════════════════════════════════════════════════════════
# 8. API 계약 — /api/v1/legal/*
# ══════════════════════════════════════════════════════════════
@pytest.fixture
def authed(client):
    """유효 API 키를 저장소에 주입해 @require_api_key 통과 (기존 네트워크 테스트 관례)."""
    from app.middleware import api_auth
    key = "pytest-legal-key"
    h = api_auth.generate_api_key_hash(key)
    api_auth.API_KEYS_STORE[h] = {
        "partner_name": "pytest", "tier": "test",
        "rate_limit": 100000, "allowed_endpoints": ["*"], "is_active": True,
    }
    yield client, {"Authorization": f"Bearer {key}"}
    api_auth.API_KEYS_STORE.pop(h, None)


class TestLegalAPI:

    def test_endpoints_require_auth(self, client):
        assert client.post("/api/v1/legal/search", json={"question": "x"}).status_code == 401
        assert client.post("/api/v1/legal/answer", json={"question": "x"}).status_code == 401
        assert client.get("/api/v1/legal/status").status_code == 401

    def test_search_requires_question(self, authed):
        c, h = authed
        assert c.post("/api/v1/legal/search", json={}, headers=h).status_code == 400

    def test_search_rejects_bad_mode(self, authed):
        c, h = authed
        r = c.post("/api/v1/legal/search",
                   json={"question": "사기", "mode": "quantum"}, headers=h)
        assert r.status_code == 400

    def test_search_contract(self, authed):
        c, h = authed
        _install()
        r = c.post("/api/v1/legal/search",
                   json={"question": "대포통장 양도", "top_k": 3, "mode": "bm25",
                         "rerank": False}, headers=h)
        assert r.status_code == 200
        body = r.get_json()
        assert body["status"] == "success"
        assert body["results"][0]["doc_id"] == "account"
        assert {"rank", "law_name", "article_ref", "scores"} <= set(body["results"][0])

    def test_answer_contract(self, authed, monkeypatch):
        c, h = authed
        canned = {"success": True, "answer": "ok [1]", "citations": [],
                  "retrieval_mode": "bm25", "rerank_used": False, "disclaimer": "d"}
        monkeypatch.setattr(LegalRAGService, "answer",
                            classmethod(lambda cls, q, top_k=4: canned))
        r = c.post("/api/v1/legal/answer", json={"question": "인출책 처벌"}, headers=h)
        assert r.status_code == 200
        assert r.get_json()["answer"] == "ok [1]"

    def test_status_contract_without_db(self, authed):
        c, h = authed
        _install()
        r = c.get("/api/v1/legal/status", headers=h)
        assert r.status_code == 200
        body = r.get_json()
        assert body["index_loaded"] is True
        assert "embedding_backend" in body and "db" in body
