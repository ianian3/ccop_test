"""
법률 RAG — Chroma 벡터 스토어 어댑터 (선택적 벡터 백엔드)

역할: 하이브리드 검색의 '벡터 레인'을 Chroma(임베디드/persistent)로 제공.
      PostgreSQL 은 청크 원문·BM25·표시용 저장을 계속 담당하고, Chroma 는
      임베딩 ANN 인덱스만 담당한다(둘을 RRF 로 융합).

활성 조건: 환경변수 LEGAL_VECTOR_BACKEND=chroma  (미설정/그 외 → 기존 PostgreSQL BYTEA + numpy 브루트포스)

폐쇄망 주의:
  - 우리가 직접 만든 임베딩을 add/query 하므로 Chroma 기본 임베딩함수(ONNX 모델 다운로드)를 쓰지 않는다.
  - 익명 텔레메트리(anonymized_telemetry)는 꺼서 외부 통신 0 을 보장한다.
  - chromadb 는 지연 import — 백엔드를 켜지 않으면 의존성이 전혀 로드되지 않는다.
"""
import logging
import os

import numpy as np

logger = logging.getLogger(__name__)

_COLLECTION = "legal_chunks"


def _persist_path():
    return os.getenv("LEGAL_CHROMA_PATH", "data/legal_chroma")


class ChromaVectorStore:
    """Chroma persistent 컬렉션 래퍼 (classmethod 패턴, 지연 초기화)."""

    _client = None
    _collection = None

    @classmethod
    def available(cls):
        """chromadb import 가능 여부 (백엔드 켜져 있어도 미설치면 BM25-only 로 안전 강등)."""
        try:
            import chromadb  # noqa: F401
            return True
        except Exception:
            return False

    @classmethod
    def _coll(cls):
        if cls._collection is None:
            import chromadb
            from chromadb.config import Settings
            cls._client = chromadb.PersistentClient(
                path=_persist_path(),
                settings=Settings(anonymized_telemetry=False, allow_reset=True),
            )
            # 우리 임베딩이 L2 정규화돼 있으므로 cosine 공간 사용 (embedding_function 미지정 → 모델 다운로드 없음)
            cls._collection = cls._client.get_or_create_collection(
                name=_COLLECTION, metadata={"hnsw:space": "cosine"})
        return cls._collection

    @classmethod
    def upsert(cls, ids, embeddings, documents=None, metadatas=None):
        """ids/embeddings(list[list[float]]) 업서트. documents·metadatas 는 선택(검사/삭제용)."""
        if not ids:
            return 0
        cls._coll().upsert(ids=ids, embeddings=embeddings,
                           documents=documents, metadatas=metadatas)
        return len(ids)

    @classmethod
    def delete_by_doc(cls, doc_ids):
        """재적재 시 해당 문서의 기존 벡터 제거(청크 수가 줄어든 경우 잔재 방지)."""
        if not doc_ids:
            return
        try:
            cls._coll().delete(where={"doc_id": {"$in": list(doc_ids)}})
        except Exception as e:
            logger.warning(f"[Chroma] delete_by_doc 실패: {e}")

    @classmethod
    def query(cls, embedding, n):
        """질의 벡터 → [(id, distance)] 유사도 내림차순(=distance 오름차순). 실패 시 []."""
        # chromadb 는 네이티브 float 리스트만 허용(np.float32 거부) → 평탄화 + float 캐스팅
        q = [float(x) for x in np.asarray(embedding, dtype=np.float32).ravel()]
        try:
            res = cls._coll().query(
                query_embeddings=[q], n_results=n, include=["distances"])
        except Exception as e:
            logger.warning(f"[Chroma] query 실패: {e}")
            return []
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        return list(zip(ids, dists))

    @classmethod
    def count(cls):
        try:
            return cls._coll().count()
        except Exception:
            return 0

    @classmethod
    def reset(cls):
        """컬렉션 비우기(--recreate). 컬렉션 삭제 후 캐시 무효화."""
        try:
            cls._coll()  # 클라이언트 초기화 보장
            cls._client.delete_collection(_COLLECTION)
        except Exception as e:
            logger.warning(f"[Chroma] reset 실패(무시): {e}")
        cls._collection = None
