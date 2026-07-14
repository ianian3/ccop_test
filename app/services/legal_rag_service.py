"""
법률 RAG v2 — Hybrid Search (BM25 + Vector) + RRF 융합 + LLM Rerank

v1(ChromaDB + 순수 벡터 검색, 제거됨)의 재구축.
설계 결정 근거는 docs/LEGAL_RAG_V2_DESIGN.md 참조.

- BM25: 자체 구현(Okapi) + 한글 bigram 토크나이저 — 외부 형태소기 의존성 없이 폐쇄망 동작
- Vector: OpenAI 호환 임베딩(EMBEDDING_ENDPOINT 로 온프레미스 vLLM/TEI 지원, 기본 text-embedding-3-small)
- 융합: Reciprocal Rank Fusion (k=60)
- Rerank: LLM listwise 채점(gpt-4o-mini, JSON) — OPENAI 키 없으면 자동 생략
- 저장: 기존 PostgreSQL(legal_documents / legal_chunks), 임베딩은 BYTEA(float32)
- 강등(degradation): 임베딩 백엔드 부재/실패 시 BM25-only 모드로 계속 동작 (폐쇄망 friendly)
"""
import json
import logging
import os
import re
import threading
from collections import defaultdict

import numpy as np
from openai import OpenAI

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 스키마 SoT — ingest CLI 가 ensure_schema() 로 적용
# ─────────────────────────────────────────────────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS legal_documents (
    doc_id      TEXT PRIMARY KEY,
    law_name    TEXT NOT NULL,
    source      TEXT,
    version     TEXT,
    chunk_count INT DEFAULT 0,
    ingested_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS legal_chunks (
    id              BIGSERIAL PRIMARY KEY,
    doc_id          TEXT NOT NULL REFERENCES legal_documents(doc_id) ON DELETE CASCADE,
    article_ref     TEXT,
    title           TEXT,
    content         TEXT NOT NULL,
    tags            TEXT[],
    embedding       BYTEA,
    embedding_model TEXT,
    embedding_dim   INT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_legal_chunks_doc ON legal_chunks(doc_id);
"""

DISCLAIMER = "본 답변은 수사 참고용 정보 검색 결과이며, 법률 자문이 아닙니다. 적용 전 원문(law.go.kr)과 법률 전문가 확인이 필요합니다."

# 청킹 파라미터 (v1 계승) — 조문 단위 레코드는 대부분 분할 없이 1청크
CHUNK_SIZE = 800
CHUNK_OVERLAP = 80

_RRF_K = 60
_CANDIDATE_POOL = 20  # BM25/Vector 각 레인의 후보 수


# ─────────────────────────────────────────────────────────────
# 토크나이저 — 한글 어절 + 문자 bigram (형태소기 없이 교착어 recall 확보)
# ─────────────────────────────────────────────────────────────
_TOKEN_RE = re.compile(r"[0-9a-zA-Z]+|[가-힣]+")
_HANGUL_RE = re.compile(r"[가-힣]")


def tokenize(text):
    """소문자화 → 한글/영숫자 런 추출 → 한글 런은 원형 + 문자 bigram 동시 색인."""
    if not text:
        return []
    tokens = []
    for run in _TOKEN_RE.findall(str(text).lower()):
        tokens.append(run)
        if _HANGUL_RE.match(run) and len(run) >= 2:
            tokens.extend(run[i:i + 2] for i in range(len(run) - 1))
    return tokens


# ─────────────────────────────────────────────────────────────
# BM25 (Okapi) — 코퍼스가 작아(조문 수백 건) 순수 파이썬 인메모리로 충분
# ─────────────────────────────────────────────────────────────
class BM25Index:
    def __init__(self, docs_tokens, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.n_docs = len(docs_tokens)
        self.doc_len = [len(t) for t in docs_tokens]
        self.avgdl = (sum(self.doc_len) / self.n_docs) if self.n_docs else 0.0
        self.postings = defaultdict(dict)  # term -> {doc_idx: tf}
        for idx, toks in enumerate(docs_tokens):
            for t in toks:
                self.postings[t][idx] = self.postings[t].get(idx, 0) + 1
        self.idf = {}
        for term, posting in self.postings.items():
            df = len(posting)
            self.idf[term] = float(np.log(1.0 + (self.n_docs - df + 0.5) / (df + 0.5)))

    def search(self, query_tokens, top_n=10):
        """[(doc_idx, score)] — score > 0 만, 내림차순."""
        if not self.n_docs or not query_tokens:
            return []
        scores = defaultdict(float)
        for t in query_tokens:
            posting = self.postings.get(t)
            if not posting:
                continue
            idf = self.idf[t]
            for idx, tf in posting.items():
                dl = self.doc_len[idx] or 1
                denom = tf + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1))
                scores[idx] += idf * (tf * (self.k1 + 1)) / denom
        ranked = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
        return [(i, s) for i, s in ranked[:top_n] if s > 0]


def rrf_fuse(rank_lists, k=_RRF_K):
    """Reciprocal Rank Fusion. rank_lists: [[doc_idx, ...], ...] → [(doc_idx, rrf_score)] 내림차순."""
    scores = defaultdict(float)
    for lst in rank_lists:
        for rank, idx in enumerate(lst):
            scores[idx] += 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """긴 본문 분할(문장 경계 우선). 조문 단위 레코드는 대부분 그대로 통과."""
    text = (text or "").strip()
    if len(text) <= size:
        return [text] if text else []
    chunks, start = [], 0
    while start < len(text):
        end = start + size
        piece = text[start:end]
        if end < len(text):
            cut = max(piece.rfind("."), piece.rfind("\n"), piece.rfind("。"))
            if cut > size // 2:
                piece = piece[:cut + 1]
                end = start + cut + 1
        piece = piece.strip()
        if piece:
            chunks.append(piece)
        start = max(end - overlap, start + 1)
    return chunks


def normalize_record(rec):
    """코퍼스 레코드 정규화. content 없는 레코드는 None."""
    content = (rec.get("content") or "").strip()
    if not content:
        return None
    law_name = (rec.get("law_name") or "기타").strip()
    article_ref = (rec.get("article_ref") or "").strip()
    doc_id = (rec.get("doc_id") or "").strip()
    if not doc_id:
        doc_id = re.sub(r"[^0-9a-zA-Z가-힣]+", "_", law_name).strip("_") or "doc"
    return {
        "doc_id": doc_id,
        "law_name": law_name,
        "article_ref": article_ref,
        "title": (rec.get("title") or "").strip(),
        "content": content,
        "source": (rec.get("source") or "").strip(),
        "tags": rec.get("tags") or [],
    }


def _index_text(c):
    """색인 대상 텍스트 — 법령명/조문번호/제목을 본문과 함께 색인해 조문 질의 recall 확보."""
    return f"{c['law_name']} {c['article_ref']} {c['title']} {c['content']}"


# ─────────────────────────────────────────────────────────────
# 서비스 본체
# ─────────────────────────────────────────────────────────────
class LegalRAGService:
    """법률 근거 하이브리드 검색·자문 서비스 (프로젝트 관례: classmethod 패턴)."""

    _state = None          # {"chunks": [...], "bm25": BM25Index, "emb": np.ndarray|None, "emb_model": str|None}
    _lock = threading.Lock()

    # ── 설정/클라이언트 해석 ─────────────────────────────
    @staticmethod
    def _cfg(key, default=None):
        try:
            from flask import current_app
            val = current_app.config.get(key)
            if val is not None:
                return val
        except Exception:
            pass
        return os.getenv(key, default)

    @classmethod
    def _embedding_backend(cls):
        """(client, model) — 온프레미스 엔드포인트 우선, 없으면 OpenAI, 둘 다 없으면 (None, None)."""
        model = cls._cfg("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
        endpoint = cls._cfg("EMBEDDING_ENDPOINT")
        if endpoint:
            return OpenAI(base_url=endpoint, api_key=os.getenv("EMBEDDING_API_KEY", "EMPTY"),
                          max_retries=1, timeout=30), model
        api_key = cls._cfg("OPENAI_API_KEY")
        if api_key:
            return OpenAI(api_key=api_key, max_retries=1, timeout=30), model
        return None, None

    @classmethod
    def _answer_backend(cls):
        """답변 생성용 (client, model, note). OpenAI 우선, 폐쇄망은 sLLM 폴백(품질 주의 note)."""
        api_key = cls._cfg("OPENAI_API_KEY")
        if api_key:
            return OpenAI(api_key=api_key, max_retries=1, timeout=30), "gpt-4o-mini", None
        sllm = cls._cfg("SLLM_ENDPOINT")
        if sllm:
            return (OpenAI(base_url=sllm, api_key="EMPTY", max_retries=0, timeout=20),
                    cls._cfg("SLLM_MODEL_NAME", "gpt-4o"),
                    "sllm_fallback: t2c 특화 모델이라 자문 품질이 제한될 수 있음")
        return None, None, None

    @classmethod
    def _rerank_enabled(cls):
        mode = (cls._cfg("RAG_RERANK", "auto") or "auto").lower()
        if mode == "off":
            return False
        if mode == "on":
            return True
        return bool(cls._cfg("OPENAI_API_KEY"))  # auto: OpenAI 키 있을 때만

    # ── 인덱스 구축/로드 ────────────────────────────────
    @classmethod
    def build_index(cls, records, embeddings=None):
        """레코드 리스트로 인메모리 인덱스 생성 (DB 불필요 — 테스트/평가 하니스 공용)."""
        chunks = [c for c in (normalize_record(r) for r in records) if c]
        bm25 = BM25Index([tokenize(_index_text(c)) for c in chunks])
        emb, emb_model = None, None
        if embeddings is not None and len(chunks) > 0 and len(embeddings) == len(chunks):
            m = np.asarray(embeddings, dtype=np.float32)
            norms = np.linalg.norm(m, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            emb = m / norms
            emb_model = "injected"
        return {"chunks": chunks, "bm25": bm25, "emb": emb, "emb_model": emb_model}

    @classmethod
    def install_index(cls, state):
        """인덱스 교체 (테스트/ingest 후 리로드용)."""
        with cls._lock:
            cls._state = state

    @classmethod
    def reload(cls):
        with cls._lock:
            cls._state = None

    @classmethod
    def _load_state_from_db(cls):
        from app.database import get_db_connection, release_db_connection
        conn, cur = get_db_connection()
        if not conn:
            return None
        try:
            cur.execute("""
                SELECT c.doc_id, d.law_name, c.article_ref, c.title, c.content, c.tags,
                       c.embedding, c.embedding_dim, c.embedding_model, d.source
                FROM legal_chunks c JOIN legal_documents d ON d.doc_id = c.doc_id
                ORDER BY c.id
            """)
            rows = cur.fetchall()
        except Exception as e:
            logger.warning(f"[LegalRAG] 인덱스 로드 실패(테이블 미생성?): {e}")
            return None
        finally:
            release_db_connection(conn)

        records, vectors, dims, models = [], [], set(), set()
        for r in rows:
            records.append({"doc_id": r[0], "law_name": r[1], "article_ref": r[2],
                            "title": r[3], "content": r[4], "tags": r[5] or [], "source": r[9]})
            if r[6] is not None and r[7]:
                vectors.append(np.frombuffer(bytes(r[6]), dtype=np.float32))
                dims.add(int(r[7]))
                models.add(r[8])
            else:
                vectors.append(None)

        embeddings = None
        if records and all(v is not None for v in vectors) and len(dims) == 1:
            embeddings = np.stack(vectors)
        state = cls.build_index(records, embeddings)
        if embeddings is not None:
            state["emb_model"] = next(iter(models), None)
        logger.info(f"[LegalRAG] 인덱스 로드: 청크 {len(records)}개, 벡터 "
                    f"{'있음(' + str(state['emb'].shape) + ')' if state['emb'] is not None else '없음(BM25-only)'}")
        return state

    @classmethod
    def _ensure_index(cls):
        if cls._state is None:
            with cls._lock:
                if cls._state is None:
                    cls._state = cls._load_state_from_db() or cls.build_index([])
        return cls._state

    # ── 질의 임베딩 (실패 시 None → BM25-only 강등) ──────
    @classmethod
    def _embed_query(cls, question):
        client, model = cls._embedding_backend()
        if client is None:
            return None
        try:
            resp = client.embeddings.create(model=model, input=question)
            v = np.asarray(resp.data[0].embedding, dtype=np.float32)
            n = np.linalg.norm(v)
            return v / n if n else v
        except Exception as e:
            logger.warning(f"[LegalRAG] 질의 임베딩 실패 → BM25-only 강등: {e}")
            return None

    # ── 하이브리드 검색 ─────────────────────────────────
    @classmethod
    def hybrid_search(cls, question, top_k=5, mode="hybrid", rerank=None):
        """
        Returns:
            {"question", "mode_used", "rerank_used", "notes": [...],
             "results": [{"rank", "doc_id", "law_name", "article_ref", "title", "content",
                          "source", "scores": {"bm25_rank", "vector_rank", "rrf", "rerank"}}]}
        """
        state = cls._ensure_index()
        chunks = state["chunks"]
        notes = []
        result = {"question": question, "mode_used": mode, "rerank_used": False,
                  "notes": notes, "results": []}
        if not chunks:
            notes.append("인덱스가 비어 있음 — scripts/ingest_legal_corpus.py 로 코퍼스를 적재하세요")
            result["mode_used"] = "empty"
            return result

        q_tokens = tokenize(question)
        bm25_ranked = state["bm25"].search(q_tokens, top_n=_CANDIDATE_POOL)
        bm25_rank_of = {idx: r for r, (idx, _s) in enumerate(bm25_ranked)}

        vec_rank_of = {}
        want_vector = mode in ("hybrid", "vector")
        if want_vector and state["emb"] is not None:
            qv = cls._embed_query(question)
            if qv is not None and qv.shape[0] == state["emb"].shape[1]:
                sims = state["emb"] @ qv
                order = np.argsort(-sims)[:_CANDIDATE_POOL]
                vec_rank_of = {int(i): r for r, i in enumerate(order)}
            else:
                if mode == "vector":
                    notes.append("질의 임베딩 불가 → BM25 로 대체")
                mode = "bm25_only" if mode == "vector" else "hybrid(bm25-only 강등)"
        elif want_vector:
            notes.append("코퍼스 임베딩 없음(BM25-only) — 임베딩 백엔드 설정 후 재적재 필요")
            mode = "bm25_only" if mode == "vector" else "hybrid(bm25-only 강등)"

        if vec_rank_of and mode in ("hybrid",):
            fused = rrf_fuse([[i for i, _ in bm25_ranked], sorted(vec_rank_of, key=vec_rank_of.get)])
            result["mode_used"] = "hybrid"
        elif vec_rank_of and mode == "vector":
            fused = [(i, 1.0 / (_RRF_K + r + 1)) for i, r in sorted(vec_rank_of.items(), key=lambda x: x[1])]
            result["mode_used"] = "vector"
        else:
            fused = [(i, 1.0 / (_RRF_K + r + 1)) for r, (i, _s) in enumerate(bm25_ranked)]
            result["mode_used"] = mode if mode.startswith("hybrid(") or mode == "bm25_only" else "bm25"

        if not fused:
            notes.append("질문과 겹치는 법률 근거 없음")
            return result

        # rerank 후보: top_k*2 (최소 8)
        pool = fused[:max(top_k * 2, 8)]
        use_rerank = cls._rerank_enabled() if rerank is None else bool(rerank)
        rerank_scores = {}
        if use_rerank and len(pool) > 1:
            rerank_scores = cls._llm_rerank(question, [(i, chunks[i]) for i, _ in pool]) or {}
            result["rerank_used"] = bool(rerank_scores)

        def sort_key(item):
            idx, rrf = item
            return (-(rerank_scores.get(idx, -1)), -rrf) if rerank_scores else (-rrf,)

        final = sorted(pool, key=sort_key)[:top_k]
        for rank, (idx, rrf) in enumerate(final, start=1):
            c = chunks[idx]
            result["results"].append({
                "rank": rank, "doc_id": c["doc_id"], "law_name": c["law_name"],
                "article_ref": c["article_ref"], "title": c["title"],
                "content": c["content"], "source": c.get("source", ""),
                "scores": {
                    "bm25_rank": bm25_rank_of.get(idx),
                    "vector_rank": vec_rank_of.get(idx),
                    "rrf": round(rrf, 6),
                    "rerank": rerank_scores.get(idx),
                },
            })
        return result

    # ── LLM Rerank (listwise, 단일 호출) ─────────────────
    @classmethod
    def _llm_rerank(cls, question, indexed_chunks):
        """{chunk_idx: 0~3 점수} 반환. 실패 시 None (융합 순서 유지)."""
        client, model = cls._rerank_client()
        if client is None:
            return None
        passages = "\n\n".join(
            f"[{i}] {c['law_name']} {c['article_ref']} {c['title']}\n{c['content'][:400]}"
            for i, c in indexed_chunks
        )
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": (
                        "당신은 법률 검색 결과 평가자입니다. 질문에 대한 각 문서의 관련성을 "
                        "0(무관)~3(직접 관련) 정수로 채점해 JSON 으로만 답하세요. "
                        '형식: {"scores": {"<문서번호>": <0-3>, ...}}')},
                    {"role": "user", "content": f"질문: {question}\n\n문서들:\n{passages}"},
                ],
                temperature=0,
                max_tokens=300,
                response_format={"type": "json_object"},
            )
            data = json.loads(resp.choices[0].message.content)
            raw = data.get("scores", {})
            out = {}
            for k, v in raw.items():
                try:
                    out[int(k)] = max(0, min(3, int(v)))
                except (ValueError, TypeError):
                    continue
            return out or None
        except Exception as e:
            logger.warning(f"[LegalRAG] rerank 실패(융합 순서 유지): {e}")
            return None

    @classmethod
    def _rerank_client(cls):
        api_key = cls._cfg("OPENAI_API_KEY")
        if api_key:
            return OpenAI(api_key=api_key, max_retries=1, timeout=20), "gpt-4o-mini"
        return None, None

    # ── 근거 인용 답변 ──────────────────────────────────
    _ANSWER_SYSTEM = """당신은 수사관을 돕는 법률 자문 AI입니다.
반드시 아래 '참고 법률 근거'에 있는 내용만 사용해 답하고, 각 주장 끝에 근거 번호 [n] 을 표기하세요.

답변 형식:
1. 📖 관련 법률: 적용 가능한 법조항 (근거 번호 표기)
2. ⚖️ 법적 해석: 해당 상황에 대한 법적 분석
3. 💡 수사 권고: 실무적 조언

중요: 근거 문서에 없는 내용은 "제공된 근거에서 확인되지 않음"이라고 명시하고 추측하지 마세요."""

    @classmethod
    def answer(cls, question, top_k=4):
        retrieval = cls.hybrid_search(question, top_k=top_k)
        kept = [r for r in retrieval["results"]
                if r["scores"]["rerank"] is None or r["scores"]["rerank"] > 0]
        if not kept:
            return {
                "success": False,
                "answer": "질문과 관련된 법률 근거를 찾지 못했습니다. 죄명·법령명·행위 유형(예: 대포통장 양도, 지급정지)을 명시해 다시 질문해 주세요.",
                "citations": [], "retrieval": retrieval, "disclaimer": DISCLAIMER,
            }
        client, model, note = cls._answer_backend()
        if client is None:
            return {
                "success": False,
                "answer": "답변 생성 LLM 이 설정되지 않았습니다(OPENAI_API_KEY 또는 SLLM_ENDPOINT). 검색 결과만 반환합니다.",
                "citations": cls._citations(kept), "retrieval": retrieval, "disclaimer": DISCLAIMER,
            }
        context = "\n\n".join(
            f"[{i}] {r['law_name']} {r['article_ref']} {r['title']}\n{r['content']}"
            for i, r in enumerate(kept, start=1)
        )
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": cls._ANSWER_SYSTEM},
                    {"role": "user", "content": f"질문: {question}\n\n참고 법률 근거:\n{context}"},
                ],
                temperature=0.2,
                max_tokens=900,
            )
            answer_text = resp.choices[0].message.content
        except Exception as e:
            logger.error(f"[LegalRAG] 답변 생성 실패: {e}")
            return {
                "success": False,
                "answer": f"답변 생성 중 오류가 발생했습니다: {e}",
                "citations": cls._citations(kept), "retrieval": retrieval, "disclaimer": DISCLAIMER,
            }
        out = {
            "success": True, "answer": answer_text, "citations": cls._citations(kept),
            "retrieval_mode": retrieval["mode_used"], "rerank_used": retrieval["rerank_used"],
            "retrieval": retrieval, "disclaimer": DISCLAIMER,
        }
        if note:
            out["note"] = note
        return out

    @staticmethod
    def _citations(kept):
        return [{"n": i, "doc_id": r["doc_id"], "law_name": r["law_name"],
                 "article_ref": r["article_ref"], "title": r["title"], "source": r["source"]}
                for i, r in enumerate(kept, start=1)]

    # ── 적재 (CLI 전용 경로) ────────────────────────────
    @classmethod
    def ensure_schema(cls, cur):
        cur.execute(SCHEMA_SQL)

    @classmethod
    def ingest_records(cls, records, recreate=False, embed=True):
        """코퍼스 레코드를 DB 에 적재(+임베딩). returns stats dict."""
        from app.database import get_db_connection, release_db_connection
        chunks = []
        for rec in records:
            c = normalize_record(rec)
            if not c:
                continue
            for piece in chunk_text(c["content"]):
                chunks.append({**c, "content": piece})
        if not chunks:
            return {"documents": 0, "chunks": 0, "embedded": 0, "model": None}

        vectors, model = [None] * len(chunks), None
        if embed:
            client, model_name = cls._embedding_backend()
            if client is None:
                logger.warning("[LegalRAG] 임베딩 백엔드 없음 → BM25-only 로 적재")
            else:
                model = model_name
                for i in range(0, len(chunks), 64):
                    batch = chunks[i:i + 64]
                    resp = client.embeddings.create(
                        model=model_name, input=[_index_text(c) for c in batch])
                    for item in sorted(resp.data, key=lambda x: x.index):
                        vectors[i + item.index] = np.asarray(item.embedding, dtype=np.float32)

        conn, cur = get_db_connection()
        if not conn:
            raise RuntimeError("DB 연결 실패 — .env 의 DB_* 설정을 확인하세요")
        try:
            import psycopg2
            cls.ensure_schema(cur)
            if recreate:
                cur.execute("TRUNCATE legal_chunks, legal_documents")
            docs = {}
            for c in chunks:
                docs.setdefault(c["doc_id"], c)
            for doc_id, c in docs.items():
                cur.execute(
                    """INSERT INTO legal_documents (doc_id, law_name, source)
                       VALUES (%s, %s, %s)
                       ON CONFLICT (doc_id) DO UPDATE
                       SET law_name = EXCLUDED.law_name, source = EXCLUDED.source,
                           ingested_at = NOW()""",
                    (doc_id, c["law_name"], c["source"]))
                cur.execute("DELETE FROM legal_chunks WHERE doc_id = %s", (doc_id,))
            embedded = 0
            for c, v in zip(chunks, vectors):
                emb_bytes = psycopg2.Binary(v.tobytes()) if v is not None else None
                if v is not None:
                    embedded += 1
                cur.execute(
                    """INSERT INTO legal_chunks
                       (doc_id, article_ref, title, content, tags, embedding, embedding_model, embedding_dim)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (c["doc_id"], c["article_ref"], c["title"], c["content"], c["tags"],
                     emb_bytes, model if v is not None else None,
                     int(v.shape[0]) if v is not None else None))
            cur.execute("""UPDATE legal_documents d SET chunk_count =
                           (SELECT COUNT(*) FROM legal_chunks c WHERE c.doc_id = d.doc_id)""")
        finally:
            release_db_connection(conn)
        cls.reload()
        return {"documents": len(docs), "chunks": len(chunks), "embedded": embedded, "model": model}

    # ── 상태 ────────────────────────────────────────────
    @classmethod
    def status(cls):
        info = {"index_loaded": cls._state is not None}
        state = cls._state
        if state:
            info.update({
                "chunks_in_memory": len(state["chunks"]),
                "vector_enabled": state["emb"] is not None,
                "embedding_model": state.get("emb_model"),
            })
        client, model = cls._embedding_backend()
        info["embedding_backend"] = ("endpoint" if cls._cfg("EMBEDDING_ENDPOINT")
                                     else ("openai" if client else "none(bm25-only)"))
        info["rerank"] = "enabled" if cls._rerank_enabled() else "disabled"
        try:
            from app.database import get_db_connection, release_db_connection
            conn, cur = get_db_connection()
            if conn:
                try:
                    cur.execute("SELECT COUNT(*), COUNT(embedding) FROM legal_chunks")
                    total, with_emb = cur.fetchone()
                    cur.execute("SELECT COUNT(*) FROM legal_documents")
                    info["db"] = {"documents": cur.fetchone()[0],
                                  "chunks": total, "chunks_with_embedding": with_emb}
                finally:
                    release_db_connection(conn)
            else:
                info["db"] = "unavailable"
        except Exception as e:
            info["db"] = f"unavailable ({type(e).__name__})"
        return info
