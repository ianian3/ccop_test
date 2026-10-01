# tests/test_source_attr_alignment.py
"""
원천 속성명 ↔ 속성 사전(SoT) 정합 (2026-10-01).

협력기관 지적: 사전 기준으로 노드 속성을 출력하면 원천에 값이 있어도 null —
사전 damage_amount ↔ 원천 damage_amt, 사전 dpstr_nm ↔ 원천 dpstr. 원인은 협력기관이 적재에 쓰는
참조 적재기(handoff/csv_spec_v4.8/load_csv_to_graph.py, CSV 적재 규격 V4.8)의 속성명을 사전이 따르지 않은 것.

이 테스트는 참조 적재기가 만드는 노드·엣지 속성명을 AST 로 전부 뽑아 SoT 정의(속성·공통 메타)에
있는지 확인한다. 규격이나 SoT 한쪽만 바꾸면 실패한다.
"""
import ast
import os

import pytest

from app.services.ontology_service import KICSCrimeDomainOntology as O

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOADER = os.path.join(ROOT, 'handoff', 'csv_spec_v4.8', 'load_csv_to_graph.py')

NODE_ATTRS = {v['label']: set(v.get('properties', [])) | set(v.get('attributes', [])) for v in O.ENTITIES.values()}
NODE_COMMON = set(O.ATTRIBUTE_DICTIONARY.get('common_attrs', {})) | {a for g in O.NODE_COMMON_GROUPS.values() for a in g}
EDGE_META = set(O.EDGE_META_SCHEMA)


def _const(n):
    return n.value if isinstance(n, ast.Constant) else None


def _dict_keys(n):
    return [k.value for k in n.keys if isinstance(k, ast.Constant)] if isinstance(n, ast.Dict) else []


def _loader_usage():
    tree = ast.parse(open(LOADER, encoding='utf-8').read())
    nodes, edges = {}, {}
    for call in ast.walk(tree):
        if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)):
            continue
        name, args = call.func.attr, call.args
        if name == 'node' and len(args) >= 2 and _const(args[0]):
            s = nodes.setdefault(args[0].value, set())
            if _const(args[1]):
                s.add(args[1].value)
            if len(args) >= 4:
                s.update(_dict_keys(args[3]))
        elif name in ('edge', 'agg_edge') and args and _const(args[0]) and args[0].value in O.RELATIONSHIPS:
            s = edges.setdefault(args[0].value, set())
            if len(args) >= 4:
                s.update(_dict_keys(args[3]))
    return nodes, edges


NODES, EDGES = _loader_usage()


def test_loader_parsed():
    assert {'vt_bacnt', 'vt_case', 'vt_ip', 'vt_telno', 'vt_psn'} <= set(NODES)
    assert EDGES, '참조 적재기에서 엣지 호출을 찾지 못함'


@pytest.mark.parametrize('label', sorted(NODES))
def test_loader_node_attrs_in_dictionary(label):
    assert label in NODE_ATTRS, f'SoT 밖 노드 라벨: {label}'
    extra = NODES[label] - NODE_ATTRS[label] - NODE_COMMON
    assert not extra, f'{label}: 참조 적재기 속성이 사전에 없음 {sorted(extra)} — SoT ENTITIES 또는 규격 정정'


@pytest.mark.parametrize('edge', sorted(EDGES))
def test_loader_edge_props_in_dictionary(edge):
    extra = EDGES[edge] - set(O.RELATIONSHIPS[edge].get('properties') or []) - EDGE_META
    assert not extra, f'{edge}: 참조 적재기 속성이 사전에 없음 {sorted(extra)}'


def test_reported_pairs_fixed():
    """협력기관 지적 2건 — 사전이 원천명을 쓰고, 옛 이름은 별칭으로만 남는다."""
    assert 'damage_amt' in NODE_ATTRS['vt_case'] and 'damage_amount' not in NODE_ATTRS['vt_case']
    assert 'dpstr' in NODE_ATTRS['vt_bacnt'] and 'dpstr_nm' not in NODE_ATTRS['vt_bacnt']
    al = O.ATTRIBUTE_DICTIONARY['aliases']['node']
    assert al['vt_case']['damage_amt'] == ['damage_amount'] and al['vt_bacnt']['dpstr'] == ['dpstr_nm']


def test_aliases_point_to_sot_attrs():
    """원천 별칭표의 대상은 SoT 속성이어야 하고, 별칭(구 이름)은 SoT 에 남아 있으면 안 된다.
    예외: event_id — 이벤트 노드에 정경 ID 와 같은 값으로 함께 기록하는 호환 별칭(SoT attributes 에 명시)."""
    DUAL_WRITTEN = {'event_id'}
    for label, m in O.ATTRIBUTE_DICTIONARY['aliases']['node'].items():
        for attr, olds in m.items():
            assert attr in NODE_ATTRS[label], (label, attr)
            assert not ((set(olds) - DUAL_WRITTEN) & NODE_ATTRS[label]), (label, olds)
    for edge, m in O.ATTRIBUTE_DICTIONARY['aliases']['edge'].items():
        props = set(O.RELATIONSHIPS[edge].get('properties') or [])
        for attr, olds in m.items():
            assert attr in props, (edge, attr)
            assert not (set(olds) & props), (edge, olds)
