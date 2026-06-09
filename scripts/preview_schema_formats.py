"""
세 가지 스키마 포맷이 실제로 어떻게 출력되는지 확인하는 미리보기 도구.
벤치마크 실행 전 프롬프트 품질을 육안으로 검토하세요.

사용법:
    python scripts/preview_schema_formats.py
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.schema_format_benchmark import (
    CANONICAL_SCHEMA, FORMATS, build_prompt, BENCHMARK_QUERIES
)

SAMPLE_QUESTION = BENCHMARK_QUERIES[5][0]  # 방향성 추적 예시

for fmt_name, fmt_fn in FORMATS.items():
    schema_str = fmt_fn(CANONICAL_SCHEMA)
    prompt = build_prompt(SAMPLE_QUESTION, schema_str, "ccop_graph")
    tok_approx = len(prompt.split())

    print(f"\n{'#'*70}")
    print(f"  Format: {fmt_name}  (토큰 근사: ~{tok_approx})")
    print(f"{'#'*70}")
    print(f"\n--- 스키마 문자열 단독 ---")
    print(schema_str)
    print(f"\n--- 최종 프롬프트 (샘플 질문: {SAMPLE_QUESTION[:40]}...) ---")
    print(prompt[:1200], "... [truncated]" if len(prompt) > 1200 else "")
