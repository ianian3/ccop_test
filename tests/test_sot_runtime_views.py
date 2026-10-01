# tests/test_sot_runtime_views.py
"""
정합 1단계 (2026-10-01) — 손사본 방향표·스키마를 SoT 런타임 뷰로 대체, T2C 생성 후 V4.9 표기 변환.

- KICSCrimeDomainOntology.edge_rules / t2c_schema / DEPRECATED_EDGES / DEPRECATED_LABELS / renamed_props
- langgraph _POLE_SCHEMA(= t2c_schema) · 검증기 · 스키마 필터, ai_service 방향 교정, graph_service 방향표
- cypher_compat.rewrite_v49 (데이터 인지 · 절별 속성 변환)
- pattern_library V4.9 번역, temporal_continuity 시각 키, few-shot 예시
DB 없이 실행.
"""
import json
import os
import re

import pytest

from app.services.ontology_service import KICSCrimeDomainOntology as O
from app.services.cypher_compat import rewrite_v49
from app.services.langgraph_agent import LangGraphAgent as A
from app.services.ai_service import AIService

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LABELS = {v['label'] for v in O.ENTITIES.values()}


# ── SoT 뷰 ─────────────────────────────────────────────────────────

def test_edge_rules_cover_sot_and_use_labels():
    rules = O.edge_rules()
    assert set(rules) == set(O.RELATIONSHIPS)
    for e, (src, dst) in rules.items():
        for side in (src, dst):
            assert side is None or (side and side <= LABELS), (e, side)
    assert rules['eg_used_account'] == ({'vt_case'}, {'vt_bacnt'})          # 구 사본 오기(진정서) 재발 방지
    assert {'vt_psn', 'vt_telno', 'vt_id', 'vt_bacnt', 'vt_dev'} <= rules['used_ip'][0]


def test_t2c_schema_is_pole_schema():
    t = O.t2c_schema()
    assert A._POLE_SCHEMA == t
    assert set(t['node_labels']) == LABELS and set(t['edge_types']) == set(O.RELATIONSHIPS)
    assert 'mov_dt' in t['node_labels']['vt_movement'] and 'timestamp' not in t['node_labels']['vt_movement']


def test_deprecated_tables_consistent():
    for old, d in O.DEPRECATED_EDGES.items():
        assert old not in O.RELATIONSHIPS, old
        assert d['replace'] is None or d['replace'] in O.RELATIONSHIPS, (old, d)
        assert d['replace'] is not None or d.get('why'), old
    for old, d in O.DEPRECATED_LABELS.items():
        assert old not in LABELS and d['replace'] in LABELS


def test_v47_prompt_names_covered_by_sot_or_compat():
    """학습 고정 프롬프트가 가르치는 엣지는 SoT 이거나 변환표에 있어야 한다 (프롬프트 자체는 수정 금지)."""
    txt = open(os.path.join(ROOT, 'app/services/prompts/t2c_v47_system.txt'), encoding='utf-8').read()
    edges = set(re.findall(r'\[(?:\w+:)?:?([a-z_][a-zA-Z_]*)\]', txt))   # 프롬프트 표기: -[edge]-> / -[r:edge]->
    assert edges, '프롬프트에서 엣지를 찾지 못함'
    unknown = edges - set(O.RELATIONSHIPS) - set(O.DEPRECATED_EDGES)
    assert not unknown, unknown
    labels = set(re.findall(r'\b(vt_[a-z]+|pt_cluster|site_cluster)\b', txt))
    assert not (labels - LABELS - set(O.DEPRECATED_LABELS)), labels - LABELS


# ── 생성 후 변환 ───────────────────────────────────────────────────

def test_rewrite_label_edge_prop():
    out, ch, err = rewrite_v49("MATCH (p:vt_psn)-[r:uses_email]->(e:vt_email {email_addr:'a@b.c'}) RETURN e.email_addr")
    assert out == "MATCH (p:vt_psn)-[r:uses_id]->(e:vt_id {platform: 'email', id_val:'a@b.c'}) RETURN e.id_val AS email_addr"
    assert not err


def test_rewrite_reverse_edge():
    out, _, _ = rewrite_v49("MATCH (i:vt_ip)-[:hosts]->(s:vt_site) RETURN s")
    assert out == "MATCH (i:vt_ip)<-[:resolves_to]-(s:vt_site) RETURN s"


def test_rewrite_props_clause_aware():
    out, _, _ = rewrite_v49("MATCH (c:vt_case) WHERE c.damage_amount > 1 RETURN c.damage_amount ORDER BY c.damage_amount DESC")
    assert out == ("MATCH (c:vt_case) WHERE coalesce(c.damage_amt, c.damage_amount) > 1 "
                   "RETURN coalesce(c.damage_amt, c.damage_amount) AS damage_amount ORDER BY damage_amount DESC")


def test_rewrite_rejects_deleted_without_successor():
    _, _, err = rewrite_v49("MATCH (a:vt_psn)-[:accomplice_of]-(b:vt_psn) RETURN b")
    assert err and 'accomplice_of' in err[0]


def test_rewrite_keeps_names_present_in_graph():
    q = "MATCH (p:vt_psn)-[r:uses_email]->(e:vt_email) RETURN e"
    assert rewrite_v49(q, present={'vt_email', 'uses_email'})[0] == q


def test_rewrite_noop_on_v49_query():
    q = "MATCH (a:vt_bacnt)-[:transferred_to]->(b:vt_bacnt) RETURN b.account_no"
    assert rewrite_v49(q) == (q, [], [])


# ── 검증기·필터·방향 ────────────────────────────────────────────────

@pytest.mark.parametrize('edge', ['registered_to', 'exchanged_to', 'accessed_to', 'represents', 'eg_used_id'])
def test_validator_accepts_sot_edges(edge):
    assert A._validate_cypher_schema(f"MATCH (a)-[:{edge}]->(b) RETURN b")[0]


def test_validator_accepts_legacy_present_in_graph():
    q = "MATCH (p:vt_psn)-[:uses_email]->(e:vt_email) RETURN e"
    assert not A._validate_cypher_schema(q)[0]
    assert A._validate_cypher_schema(q, {'vt_email', 'uses_email'})[0]


def test_filter_one_hop_not_transitive():
    f = A._filter_schema_by_labels(A._POLE_SCHEMA, ['vt_loc'])
    assert 'vt_loc' in f['node_labels'] and len(f['node_labels']) < len(LABELS) // 2


def test_direction_fix_polymorphic_domain():
    assert AIService._fix_relation_direction("MATCH (t:vt_telno)-[:used_ip]->(i:vt_ip) RETURN t") == \
        "MATCH (t:vt_telno)-[:used_ip]->(i:vt_ip) RETURN t"
    assert AIService._fix_relation_direction("MATCH (i:vt_ip)-[:used_ip]->(t:vt_telno) RETURN t") == \
        "MATCH (i:vt_ip)<-[:used_ip]-(t:vt_telno) RETURN t"


def test_graph_service_directions_from_sot():
    from app.services.graph_service import GraphService as G
    d = G._KICS_EDGE_DIRECTIONS
    assert set(O.RELATIONSHIPS) <= set(d)
    assert set(d) - set(O.RELATIONSHIPS) <= set(O.DEPRECATED_EDGES)       # 나머지는 이전 적재분 조회 호환뿐


# ── 소비자 ─────────────────────────────────────────────────────────

def test_temporal_event_time_keys_in_sot():
    from app.services.temporal_continuity import EVENT_VT
    node = {v['label']: set(v['properties']) | set(v['attributes']) for v in O.ENTITIES.values()}
    for label, attr in EVENT_VT.items():
        assert attr in node[label], (label, attr)


def test_pattern_library_v49():
    from app.services.pattern_library import PatternLibrary as P
    for pid, p in P.get_all_patterns().items():
        for n in p.required_nodes.values() if isinstance(p.required_nodes, dict) else []:
            if isinstance(n, dict) and n.get('label'):
                assert n['label'] in LABELS, (pid, n['label'])
        if p.supported:
            ok, msg = A._validate_cypher_schema(p.cypher_query)
            assert ok, (pid, msg)
        else:
            assert set(p.unsupported_edges) <= {'digital_trace', 'related_to'}, (pid, p.unsupported_edges)


def test_few_shot_examples_v49():
    d = json.load(open(os.path.join(ROOT, 'data/few_shot_examples.json'), encoding='utf-8'))
    bad = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and 'MATCH' in x.upper():
            ok, msg = A._validate_cypher_schema(x)
            if not ok:
                bad.append((x[:80], msg))
    walk(d)
    assert not bad, bad


def test_ontology_endpoint(client):
    with client.session_transaction() as sess:
        sess['ui_authorized'] = True
    r = client.get('/api/v1/ontology')
    assert r.status_code == 200
    body = r.get_json()
    assert body['node_count'] == len(LABELS) and body['edge_count'] == len(O.RELATIONSHIPS)
    assert body['edges']['eg_used_account']['domain'] == ['vt_case']
    assert 'hosts' in body['deprecated']['edges']
