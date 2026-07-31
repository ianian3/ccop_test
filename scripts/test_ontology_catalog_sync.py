#!/usr/bin/env python3
"""온톨로지 카탈로그 동기화 회귀 테스트 — 엣지 이원화 재발 방지.

검증 규칙:
  1. EDGE_STYLE_V40(시각) ⊆ RELATIONSHIPS(의미) — "화면엔 그려지는데 의미 정의가 없는" 엣지 금지
  2. 의미-only 엣지는 보류 허용목록(C단계 결정 대기 3종)만 허용 — 새 드리프트 발생 시 실패
  3. 노드 카탈로그 5종 구조(ENTITIES/VISUAL_STYLE_V40/DOMAIN_USAGE/라벨맵)가 모두 25개로 일치

실행: python3 scripts/test_ontology_catalog_sync.py   (의존성 없음 — AST 정적 분석)
근거: docs/CCOP_ONTOLOGY_V4.0.md + CCOP_Ontology_V4.0.xlsx 정합화 (2026-07-31)
"""
import ast
import sys
from pathlib import Path

SOT = Path(__file__).resolve().parent.parent / 'app/middleware/services/ontology_service.py'

# C단계 완료(2026-07-31): controls·located_at 등재, owns_device는 uses_device 별칭 등재 → 보류 0
PENDING_SEMANTIC_ONLY = set()


def dict_keys(tree, name):
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == name and isinstance(node.value, ast.Dict):
                    return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    return set()


def main():
    tree = ast.parse(SOT.read_text(encoding='utf-8'))
    rel = dict_keys(tree, 'RELATIONSHIPS')
    sty = dict_keys(tree, 'EDGE_STYLE_V40')
    failed = 0

    def check(name, cond, detail=''):
        nonlocal failed
        print(('  ✅ ' if cond else '  ❌ ') + name + ('' if cond else f'  ← {detail}'))
        if not cond:
            failed += 1

    print(f'▶ 엣지 카탈로그 (의미 {len(rel)} / 시각 {len(sty)})')
    visual_only = sty - rel
    check('시각-only 엣지 없음 (의미 정의 필수)', not visual_only, f'의미 미정의: {sorted(visual_only)}')
    semantic_only = rel - sty
    unexpected = semantic_only - PENDING_SEMANTIC_ONLY
    check(f'의미-only는 보류 3종 이내 (현재 {sorted(semantic_only)})', not unexpected,
          f'신규 드리프트: {sorted(unexpected)}')

    print('▶ 노드 카탈로그 (5종 구조 정합)')
    ent = dict_keys(tree, 'ENTITIES')
    check(f'ENTITIES = 25 (현재 {len(ent)})', len(ent) == 25)
    for name in ('VISUAL_STYLE_V40', 'DOMAIN_USAGE', 'NODE_ID_STANDARD', 'GDB_LABEL_MAP', 'LABEL_KO_MAP'):
        keys = dict_keys(tree, name)
        check(f'{name} = 25 (현재 {len(keys)})', len(keys) == 25)

    print('\n' + ('✅ 전체 통과' if failed == 0 else f'❌ {failed}건 실패'))
    sys.exit(0 if failed == 0 else 1)


if __name__ == '__main__':
    main()
