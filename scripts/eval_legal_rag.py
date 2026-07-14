#!/usr/bin/env python3
"""
법률 RAG v2 평가 하니스 — 2계층 평가

Tier 1 (결정적, LLM 불필요): golden_qa.json 대비 검색 품질
  - Hit@3 / Hit@5 / MRR@10, 모드별(bm25 / vector / hybrid / hybrid+rerank) 비교
Tier 2 (--ragas, LLM judge 필요): RAGAS 지표
  - faithfulness / answer_relevancy / context_precision / context_recall

사용법:
  # 오프라인 (mock 임베딩 — 하니스 검증용, 품질 수치 아님)
  python scripts/eval_legal_rag.py --mock-embeddings

  # 실제 임베딩 (OPENAI_API_KEY 또는 EMBEDDING_ENDPOINT 필요)
  python scripts/eval_legal_rag.py

  # + rerank 레인 (OPENAI_API_KEY 필요)
  python scripts/eval_legal_rag.py --rerank

  # + RAGAS (pip install -r requirements-rag-eval.txt, OPENAI_API_KEY 필요)
  python scripts/eval_legal_rag.py --ragas

DB 불필요 — data/legal/*.json 에서 직접 인메모리 인덱스를 구축한다.
결과는 results/legal_rag_eval_<label>.json 저장.
"""
import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

MOCK_DIM = 512


def mock_embed(text, tokenize_fn):
    """결정적 mock 임베딩 — 토큰 해시 bag-of-words (어휘 겹침 ≈ 코사인 유사도).
    하니스 배선 검증용이며 실제 의미 검색 품질을 대표하지 않는다."""
    v = np.zeros(MOCK_DIM, dtype=np.float32)
    for t in tokenize_fn(text):
        idx = int(hashlib.md5(t.encode()).hexdigest(), 16) % MOCK_DIM
        v[idx] += 1.0
    n = np.linalg.norm(v)
    return v / n if n else v


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_corpus(corpus_dir):
    import glob
    records = []
    for path in sorted(glob.glob(os.path.join(corpus_dir, "*.json"))):
        if os.path.basename(path) == "golden_qa.json":
            continue
        records.extend(load_json(path))
    return records


def evaluate_mode(service, golden, mode, rerank):
    """모드 하나에 대한 검색 지표. returns (metrics, per_question)."""
    hits3 = hits5 = 0
    rr_sum = 0.0
    per_q = []
    for qa in golden:
        expected = set(qa["expected_doc_ids"])
        r = service.hybrid_search(qa["question"], top_k=10, mode=mode, rerank=rerank)
        got = [x["doc_id"] for x in r["results"]]
        first_hit = next((i + 1 for i, d in enumerate(got) if d in expected), None)
        if first_hit and first_hit <= 3:
            hits3 += 1
        if first_hit and first_hit <= 5:
            hits5 += 1
        rr_sum += (1.0 / first_hit) if first_hit else 0.0
        per_q.append({"id": qa["id"], "first_hit_rank": first_hit,
                      "top3": got[:3], "mode_used": r["mode_used"]})
    n = len(golden)
    return ({"hit@3": round(hits3 / n, 3), "hit@5": round(hits5 / n, 3),
             "mrr@10": round(rr_sum / n, 3), "n": n}, per_q)


def run_ragas(service, golden, top_k=4):
    """RAGAS 평가 — ragas 미설치/키 부재 시 안내 후 None."""
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  RAGAS: OPENAI_API_KEY 필요 — 건너뜀")
        return None
    try:
        from ragas import evaluate
        from ragas.metrics import (answer_relevancy, context_precision,
                                   context_recall, faithfulness)
        from datasets import Dataset
    except ImportError as e:
        print(f"⚠️  RAGAS 미설치({e}) — pip install -r requirements-rag-eval.txt")
        return None

    rows = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
    print("▶ RAGAS 샘플 생성 (answer LLM 호출)...")
    for qa in golden:
        result = service.answer(qa["question"], top_k=top_k)
        contexts = [f"{c['law_name']} {c['article_ref']} {c['title']}"
                    for c in result.get("citations", [])]
        # RAGAS 는 컨텍스트 원문이 필요 — retrieval 에서 복원
        contexts = [r_["content"] for r_ in result["retrieval"]["results"]] \
            if "retrieval" in result else contexts
        rows["question"].append(qa["question"])
        rows["answer"].append(result.get("answer", ""))
        rows["contexts"].append(contexts or [""])
        rows["ground_truth"].append(qa["reference_answer"])
        print(f"  · {qa['id']} answered={result.get('success')}")

    dataset = Dataset.from_dict(rows)
    print("▶ RAGAS 평가 실행...")
    scores = evaluate(dataset, metrics=[faithfulness, answer_relevancy,
                                        context_precision, context_recall])
    # ragas 버전에 따라 반환형이 다름 — dict 화 방어적 처리
    try:
        summary = {k: round(float(v), 4) for k, v in scores.items()}  # 구버전 스타일
    except Exception:
        try:
            df = scores.to_pandas()
            metric_cols = [c for c in df.columns
                           if c not in ("question", "answer", "contexts", "ground_truth",
                                        "user_input", "response", "retrieved_contexts", "reference")]
            summary = {c: round(float(df[c].mean()), 4) for c in metric_cols}
        except Exception as e:
            summary = {"raw": str(scores), "parse_error": str(e)}
    return summary


def main():
    parser = argparse.ArgumentParser(description="법률 RAG 평가")
    parser.add_argument("--dir", default="data/legal")
    parser.add_argument("--mock-embeddings", action="store_true",
                        help="결정적 mock 임베딩 (오프라인 하니스 검증용 — 품질 수치 아님)")
    parser.add_argument("--rerank", action="store_true", help="hybrid+rerank 레인 추가 (OpenAI 키 필요)")
    parser.add_argument("--ragas", action="store_true", help="RAGAS 지표 실행 (키+의존성 필요)")
    parser.add_argument("--out", default=None, help="결과 JSON 경로")
    args = parser.parse_args()

    golden = load_json(os.path.join(args.dir, "golden_qa.json"))
    records = load_corpus(args.dir)
    print(f"▶ 코퍼스 {len(records)}건 / 골든 QA {len(golden)}건")

    from app import create_app
    app = create_app()
    with app.app_context():
        from app.services.legal_rag_service import LegalRAGService, tokenize, _index_text, normalize_record

        chunks = [c for c in (normalize_record(r) for r in records) if c]
        if args.mock_embeddings:
            embeddings = [mock_embed(_index_text(c), tokenize) for c in chunks]
            label = "mock"
            print("⚠️  mock 임베딩 모드 — vector/hybrid 수치는 배선 검증용입니다")
            # 질의 임베딩도 동일 mock 사용
            LegalRAGService._embed_query = classmethod(
                lambda cls, q: mock_embed(q, tokenize))
        else:
            client, model = LegalRAGService._embedding_backend()
            if client is None:
                sys.exit("임베딩 백엔드 없음 — --mock-embeddings 를 쓰거나 OPENAI_API_KEY/EMBEDDING_ENDPOINT 설정")
            label = model
            print(f"▶ 실제 임베딩 생성: {model}")
            texts = [_index_text(c) for c in chunks]
            embeddings = []
            for i in range(0, len(texts), 64):
                resp = client.embeddings.create(model=model, input=texts[i:i + 64])
                embeddings.extend(item.embedding for item in
                                  sorted(resp.data, key=lambda x: x.index))

        LegalRAGService.install_index(LegalRAGService.build_index(records, embeddings))

        lanes = [("bm25", False), ("vector", False), ("hybrid", False)]
        if args.rerank:
            lanes.append(("hybrid", True))

        report = {"corpus": len(chunks), "golden": len(golden),
                  "embedding": label, "lanes": {}}
        print(f"\n{'레인':<18}{'Hit@3':>8}{'Hit@5':>8}{'MRR@10':>9}")
        print("─" * 45)
        for mode, rr in lanes:
            name = f"{mode}+rerank" if rr else mode
            metrics, per_q = evaluate_mode(LegalRAGService, golden, mode, rr)
            report["lanes"][name] = {"metrics": metrics, "per_question": per_q}
            print(f"{name:<18}{metrics['hit@3']:>8}{metrics['hit@5']:>8}{metrics['mrr@10']:>9}")

        if args.ragas:
            ragas_summary = run_ragas(LegalRAGService, golden)
            if ragas_summary:
                report["ragas"] = ragas_summary
                print("\nRAGAS:", json.dumps(ragas_summary, ensure_ascii=False))

        out = args.out or f"results/legal_rag_eval_{label.replace('/', '_')}.json"
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 결과 저장: {out}")


if __name__ == "__main__":
    main()
