#!/usr/bin/env python3
"""
법률 RAG v2 코퍼스 적재 CLI

사용법:
  python scripts/ingest_legal_corpus.py                       # data/legal/*.json|*.pdf 전체 적재(+임베딩)
  python scripts/ingest_legal_corpus.py --file 계약서.pdf      # 단일 파일 적재 (.pdf 또는 .json)
  python scripts/ingest_legal_corpus.py --no-embed            # BM25-only 적재 (임베딩 백엔드 없이)
  python scripts/ingest_legal_corpus.py --recreate            # 기존 테이블 비우고 재적재
  python scripts/ingest_legal_corpus.py --dry-run             # DB 없이 인덱스 구축 + 샘플 검색 (검증용)
  python scripts/ingest_legal_corpus.py --dir data/legal      # 코퍼스 디렉토리 지정

코퍼스 포맷(JSON): [{doc_id, law_name, article_ref, title, content, source, tags[]}, ...]
PDF: 페이지별로 추출→청킹되어 위 레코드로 변환됨(article_ref=p.N 으로 출처 추적).
golden_qa.json 은 평가셋이므로 적재에서 제외된다.

주의: PDF 파싱은 '적재(개발) 단계' 전용이다. pypdf 는 앱 런타임 의존성이 아니며
(법률 RAG v2 = 신규 런타임 의존성 0 원칙), 이 스크립트에서만 지연 import 한다.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _extract_pdf_pages(path):
    """PDF → [(page_no, text)]. pypdf 는 적재 전용(지연 import)."""
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("PDF 적재엔 pypdf 가 필요합니다(적재/개발 전용): pip install pypdf")
    reader = PdfReader(path)
    return [(i + 1, (pg.extract_text() or "").strip()) for i, pg in enumerate(reader.pages)]


def load_pdf_records(path):
    """PDF → 페이지 단위 레코드. 긴 페이지는 미리 조각내되 페이지 출처(article_ref)를 보존.
    (본문은 적재 시 legal_rag_service.chunk_text 로 한 번 더 정규화됨 — 이미 ≤800자면 그대로 통과)"""
    from app.services.legal_rag_service import chunk_text
    stem = os.path.splitext(os.path.basename(path))[0]
    pages = _extract_pdf_pages(path)
    records = []
    for page_no, text in pages:
        if not text:
            continue
        for piece in chunk_text(text):
            if piece.strip():
                records.append({
                    "doc_id": stem,                       # 문서(PDF) 단위 → legal_documents 1행
                    "law_name": stem,                     # 표시용 문서명
                    "article_ref": f"p.{page_no}",        # 페이지 출처(traceability)
                    "title": "",
                    "content": piece,
                    "source": os.path.basename(path),
                    "tags": ["pdf"],
                })
    total_chars = sum(len(t) for _, t in pages)
    warn = "  ⚠️ 텍스트 거의 없음(스캔 PDF? OCR 필요)" if total_chars < 50 else ""
    print(f"  · {os.path.basename(path)}: {len(pages)}p → {len(records)}청크{warn}")
    return records


def load_json_records(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        print(f"⚠️  {path}: 리스트가 아니라서 건너뜀")
        return []
    print(f"  · {os.path.basename(path)}: {len(data)}건 (json)")
    return data


def load_file(path):
    low = path.lower()
    if low.endswith(".pdf"):
        return load_pdf_records(path)
    if low.endswith(".json"):
        return load_json_records(path)
    print(f"⚠️  {path}: 지원하지 않는 형식(.json/.pdf 만)")
    return []


def load_records(corpus_dir):
    records = []
    paths = sorted(glob.glob(os.path.join(corpus_dir, "*.json")) +
                   glob.glob(os.path.join(corpus_dir, "*.pdf")))
    for path in paths:
        if os.path.basename(path) == "golden_qa.json":
            continue
        records.extend(load_file(path))
    return records


def main():
    parser = argparse.ArgumentParser(description="법률 RAG 코퍼스 적재 (JSON/PDF)")
    parser.add_argument("--dir", default="data/legal", help="코퍼스 디렉토리 (기본 data/legal)")
    parser.add_argument("--file", help="단일 파일 적재 (.pdf 또는 .json)")
    parser.add_argument("--recreate", action="store_true", help="기존 legal_* 테이블 비우고 재적재")
    parser.add_argument("--no-embed", action="store_true", help="임베딩 없이 적재 (BM25-only)")
    parser.add_argument("--dry-run", action="store_true", help="DB 없이 인메모리 인덱스 구축 + 샘플 검색")
    args = parser.parse_args()

    if args.file:
        print(f"▶ 파일 로드: {args.file}")
        records = load_file(args.file)
    else:
        print(f"▶ 코퍼스 로드: {args.dir}/")
        records = load_records(args.dir)
    print(f"▶ 총 {len(records)}개 레코드")
    if not records:
        sys.exit("코퍼스가 비어 있습니다.")

    from app import create_app
    app = create_app()
    with app.app_context():
        from app.services.legal_rag_service import LegalRAGService

        if args.dry_run:
            state = LegalRAGService.build_index(records)
            LegalRAGService.install_index(state)
            print(f"✅ [dry-run] 인메모리 인덱스: 청크 {len(state['chunks'])}개, "
                  f"BM25 어휘 {len(state['bm25'].postings)}개 (임베딩 없음)")
            for q in ["대포통장 양도 처벌", "피해금 7억 가중처벌", "지급정지 절차"]:
                r = LegalRAGService.hybrid_search(q, top_k=3, mode="bm25", rerank=False)
                tops = ", ".join(f"{x['law_name']} {x['article_ref']}" for x in r["results"])
                print(f"  Q: {q}  →  {tops or '(결과 없음)'}")
            return

        stats = LegalRAGService.ingest_records(records, recreate=args.recreate,
                                               embed=not args.no_embed)
        print(f"✅ 적재 완료: 문서 {stats['documents']}개 / 청크 {stats['chunks']}개 / "
              f"임베딩 {stats['embedded']}개 (model={stats['model'] or 'BM25-only'})")
        print("   상태 확인: GET /api/v1/legal/status")


if __name__ == "__main__":
    main()
