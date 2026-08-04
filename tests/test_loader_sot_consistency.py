"""적재 코드 ↔ 온톨로지 SoT 카탈로그 정합 회귀 테스트.

적재 코드(rdb_to_graph_service)가 선언·사용하는 노드/엣지 라벨과
Text2Cypher 스키마(_POLE_SCHEMA)가 SoT를 벗어나면(오타·드리프트) 실패한다.
`resolved_to` 오타, 하드코딩 라벨 드리프트, POLE↔SoT 불일치를 자동 검출.
(조사에서 드러난 P1 '하드코딩 드리프트 + 대조 테스트 부재'의 안전망.)
"""
import re

from app.middleware.services.ontology_service import KICSCrimeDomainOntology as O
import app.services.rdb_to_graph_service as loader


def sot_nodes():
    return set(O.LABEL_KO_MAP.keys())          # 25 (vt_* + pt_cluster + site_cluster)


def sot_edges():
    return set(O.RELATIONSHIPS.keys())         # 66


_SRC = open(loader.__file__).read()


def _extract_list(src, name):
    """`name = [ ... ]` 리스트 리터럴에서 'xxx' 문자열 요소 집합 추출."""
    m = re.search(rf'{name}\s*=\s*\[(.*?)\]', src, re.DOTALL)
    assert m, f'{name} 리스트를 소스에서 찾을 수 없음'
    return set(re.findall(r"'([A-Za-z_]\w*)'", m.group(1)))


# ── 적재 하드코딩 카탈로그 ⊆ SoT ──

def test_loader_vertex_labels_subset_of_sot():
    vlabels = _extract_list(_SRC, 'vertex_labels')
    extra = vlabels - sot_nodes()
    assert not extra, f'적재가 선언한 SoT 밖 노드 라벨: {sorted(extra)}'


def test_loader_edge_labels_subset_of_sot():
    elabels = _extract_list(_SRC, 'edge_labels')
    extra = elabels - sot_edges()
    assert not extra, f'적재가 선언한 SoT 밖 엣지 라벨(오타·드리프트): {sorted(extra)}'


# ── Text2Cypher 스키마(_POLE_SCHEMA) ⊆ SoT ──

def _pole_edge_dirs():
    from app.services.langgraph_agent import LangGraphAgent
    return LangGraphAgent._POLE_SCHEMA.get('edge_directions', {})


def test_pole_schema_edges_subset_of_sot():
    extra = set(_pole_edge_dirs().keys()) - sot_edges()
    assert not extra, f'POLE_SCHEMA(Text2Cypher)에 SoT 밖 엣지: {sorted(extra)}'


def test_pole_schema_node_labels_subset_of_sot():
    labels = set()
    for pair in _pole_edge_dirs().values():
        f, t = (pair if isinstance(pair, (list, tuple)) else (None, None))
        if f:
            labels.add(f)
        if t:
            labels.add(t)
    extra = labels - sot_nodes()
    assert not extra, f'POLE_SCHEMA에 SoT 밖 노드 라벨: {sorted(extra)}'
