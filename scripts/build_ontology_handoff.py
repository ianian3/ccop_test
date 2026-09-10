#!/usr/bin/env python3
"""온톨로지 전달본 생성기 — SoT에서 '외부에 꼭 필요한 것만' 추려 슬림 스펙 모듈을 만든다.

SoT(app/middleware/services/ontology_service.py, 2,684행)에는 우리 앱 전용 정보가 섞여 있다
(UI 색·아이콘, 수사 워크플로 프리셋, T2C 어휘 별칭, 미구현 추론 로드맵). 이를 그대로 넘기면
받는 쪽이 '구현해야 할 목록'으로 오해하고, 스펙의 신호대잡음비가 떨어진다.

수작업으로 잘라내면 SoT가 바뀔 때마다 전달본이 낡는다. 그래서 화이트리스트 기반 생성기로 둔다.
SoT 갱신 후 이 스크립트만 다시 돌리면 전달본이 따라온다.

실행: python3 scripts/build_ontology_handoff.py
산출: handoff/ontology_v4.8/code/ccop_ontology_v48.py
"""
import os
import pprint
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.middleware.services.ontology_service import KICSCrimeDomainOntology as O  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   'handoff', 'ontology_v4.8', 'code', 'ccop_ontology_v48.py')

# ── 전달 대상: (속성명, 섹션 주석) ──
KEEP = [
    ('LAYERS',             '4계층 구조 — 온톨로지 골격'),
    ('LAYERS_GDB',         '계층별 그래프 라벨 소속'),
    ('ENTITIES',           '노드 25종 — layer·properties(키)·attributes(전속성)·legal_category'),
    ('RELATIONSHIPS',      '엣지 72종 — domain/range·properties·meaning·legal_significance'),
    ('GDB_LABEL_MAP',      '개념명 → 그래프 라벨 (Person → vt_psn)'),
    ('CONCEPT_LOOKUP',     '그래프 라벨 → 개념명 (역방향)'),
    ('LABEL_KO_MAP',       '라벨 → 한글명 (UI·보고서 표기용)'),
    ('EDGE_META_SCHEMA',   '전 엣지 공통 메타 속성과 타입'),
    ('NODE_ID_STANDARD',   '노드 식별자 규약 — canonical_field·정규화·해시 형식 (적재 멱등성의 근거)'),
    ('STANDARD_TABLE_MAP', 'RDB 표준테이블 크로스워크 (standard 키가 현행)'),
    ('COLUMN_PATTERNS',    '[부록] 원본 컬럼명 → 표준 속성 추론 규칙 (전처리 힌트)'),
    ('COLUMN_TYPE_TO_RDB', '[부록] 속성 타입 → RDB 타입'),
]

# ── 항목 내부에서 빼는 키 ──
DROP_KEYS = {
    # semantic_relation: RDF식 camelCase 별칭(suspectIn 등). AgensGraph 는 미인용 식별자를
    #   소문자화하므로 이 이름을 엣지 라벨로 오인해 쓰면 깨진다 → 혼선 방지로 제외.
    # source_types: 우리 CSV 파서가 쓰는 원본 컬럼쌍. 우리 ETL 내부사정.
    'RELATIONSHIPS': {'semantic_relation', 'source_types'},
}

# ── 제외 사유 (헤더에 그대로 기록) ──
EXCLUDED = [
    ('EDGE_STYLE_V40 · VISUAL_STYLE_V40 · LAYOUT_PRESETS_V40', '당사 UI 렌더링 값(색·아이콘·레이아웃)'),
    ('INVESTIGATION_WORKFLOWS_V40', '당사 UI 수사 시나리오 프리셋'),
    ('LABEL_ALIASES', '당사 Text2Cypher 모델의 자연어 어휘 매핑'),
    ('DOMAIN_USAGE', '당사 데이터 출처 정책(수사/OSINT/제공)'),
    ('INFERENCE_RULES · INFERENCE_RULES_V37 · DERIVED_PROPERTY_REGISTRY',
     '추론·파생속성 로드맵. 대부분 미구현 상태라 구현 의무로 오해될 수 있어 제외'),
    ('메서드 14종', '당사 앱 헬퍼(프롬프트 생성·키워드 매칭 등). 아래 4개 함수로 대체'),
]

TYPE_MARK = '!!PYTYPE:'


def demark(v):
    """EDGE_META_SCHEMA 등에 들어있는 파이썬 타입 객체를 재생성 가능한 형태로 치환."""
    if isinstance(v, type):
        return f'{TYPE_MARK}{v.__name__}!!'
    if isinstance(v, dict):
        return {k: demark(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        out = [demark(x) for x in v]
        return tuple(out) if isinstance(v, tuple) else out
    return v


def _untype(s):
    """'!!PYTYPE:str!!' → str  (따옴표까지 걷어내 유효한 파이썬으로)"""
    import re
    return re.sub(rf"'{TYPE_MARK}(\w+)!!'", r'\1', s)


def emit(name, v, indent=4):
    """dict 를 '항목 1개 = 1행' 으로 낸다.

    pprint 기본 출력은 깊은 들여쓰기에 공백을 크게 낭비하고(전달본이 SoT보다 길어질 정도),
    한 항목이 여러 행에 걸쳐 grep·diff 도 불편하다. 스펙 파일은 '엣지 1종 = 1행' 이 읽기 좋다.
    다만 한 줄이 너무 길어지면(속성 배열이 긴 노드 정의 등) 그때만 여러 행으로 편다.
    """
    pad, ipad = ' ' * indent, ' ' * (indent + 4)
    if not isinstance(v, dict):
        return f'{pad}{name} = ' + _untype(pprint.pformat(demark(v), width=100, sort_dicts=False))
    lines = [f'{pad}{name} = {{']
    for k, item in v.items():
        one = _untype(repr(demark(item)))
        if len(one) + len(repr(k)) + len(ipad) <= 150:
            lines.append(f'{ipad}{k!r}: {one},')
        else:
            block = _untype(pprint.pformat(demark(item), width=150 - len(ipad),
                                           sort_dicts=False, indent=1))
            block = block.replace('\n', '\n' + ipad + ' ' * (len(repr(k)) + 2))
            lines.append(f'{ipad}{k!r}: {block},')
    lines.append(f'{pad}}}')
    return '\n'.join(lines)


def main():
    src_total = len(open(O.__module__.replace('.', '/') + '.py', encoding='utf-8').read()) \
        if os.path.exists(O.__module__.replace('.', '/') + '.py') else 0

    L = []
    L.append('"""CCOP 온톨로지 V4.8 — 정의 스펙 (전달본)')
    L.append('')
    L.append('노드 25종 · 엣지 72종(활성 70, deprecated 2). 사이버범죄 수사 그래프 표준.')
    L.append('제공: 스카이월드와이드 · 기준 V4.8')
    L.append('')
    L.append('외부 의존 0 — 표준 라이브러리조차 import 하지 않는 순수 선언이므로')
    L.append('파일 하나만 반입해 참조하거나 JSON 으로 덤프해 타 언어에서 쓸 수 있다.')
    L.append('')
    L.append('당사 운영본(SoT)에서 외부에 필요한 정의만 추려 생성했다. 제외한 것과 이유:')
    for name, why in EXCLUDED:
        L.append(f'  · {name}')
        L.append(f'      → {why}')
    L.append('')
    L.append('RELATIONSHIPS 항목에서 제외한 키:')
    L.append('  · semantic_relation — RDF식 camelCase 별칭(suspectIn 등). AgensGraph 는 미인용')
    L.append('      식별자를 소문자화하므로 엣지 라벨로 오인해 쓰면 깨진다.')
    L.append('  · source_types — 당사 CSV 파서가 참조하는 원본 컬럼쌍(내부 사정).')
    L.append('"""')
    L.append('')
    L.append('')
    L.append('class KICSCrimeDomainOntology:')
    L.append('    """온톨로지 V4.8 정의. 모든 속성은 순수 데이터이며 인스턴스화가 필요 없다."""')
    L.append('')

    kept_chars = 0
    for name, note in KEEP:
        v = getattr(O, name)
        if name in DROP_KEYS:
            drop = DROP_KEYS[name]
            v = {k: ({kk: vv for kk, vv in item.items() if kk not in drop}
                     if isinstance(item, dict) else item)
                 for k, item in v.items()}
        body = emit(name, v)
        kept_chars += len(body)
        n = len(v) if hasattr(v, '__len__') else '-'
        L.append(f'    # ── {note}  ({n}종) ──')
        L.append(body)
        L.append('')

    # ── 최소 헬퍼: 스펙만으로 답이 나오는 4가지 ──
    L.append('''    # ── 헬퍼 (스펙에서 바로 파생되는 것만) ──

    @classmethod
    def active_relationships(cls):
        """deprecated 를 제외한 엣지 정의."""
        return {k: v for k, v in cls.RELATIONSHIPS.items()
                if not (isinstance(v, dict) and v.get('deprecated'))}

    @classmethod
    def label_of(cls, concept_or_label):
        """개념명 → 그래프 라벨. 이미 라벨이면 그대로 돌려준다."""
        return cls.GDB_LABEL_MAP.get(concept_or_label, concept_or_label)

    @classmethod
    def concept_of(cls, label):
        """그래프 라벨 → 개념명."""
        return cls.CONCEPT_LOOKUP.get(label, label)

    @classmethod
    def key_field(cls, label):
        """라벨의 식별 속성명. NODE_ID_STANDARD 가 우선, 없으면 ENTITIES.properties[0]."""
        std = cls.NODE_ID_STANDARD.get(label)
        if isinstance(std, dict) and std.get('canonical_field'):
            return std['canonical_field']
        ent = cls.ENTITIES.get(cls.concept_of(label))
        props = ent.get('properties') if isinstance(ent, dict) else None
        return props[0] if props else None
''')

    out = '\n'.join(L)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, 'w', encoding='utf-8').write(out)
    print(f'생성: {OUT}')
    print(f'  {len(out):,}자 · {out.count(chr(10)):,}행'
          + (f'  (SoT {src_total:,}자 대비 {len(out)/src_total:.0%})' if src_total else ''))
    print(f'  전달 속성 {len(KEEP)}종 · 제외 {len(EXCLUDED)}묶음')


if __name__ == '__main__':
    main()
