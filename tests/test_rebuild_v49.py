# tests/test_rebuild_v49.py
"""2e 재구축 스크립트·V4.9 감사 (2026-10-01). DB 없이 계획·비교·감사 판정만 검사."""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, 'scripts', f'{name}.py'))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Cur:
    """ag_graph·ag_label·count 쿼리에 고정 응답."""
    def __init__(self, graphs=(), labels=(), counts=None, edges=None):
        self.graphs, self.labels, self.counts, self.edges = graphs, labels, counts or {}, edges or {}
        self._r = []

    def execute(self, q, params=None):
        if 'FROM ag_graph' in q:
            self._r = [(g,) for g in self.graphs]
        elif 'FROM ag_label' in q:
            self._r = list(self.labels)
        elif 'source_id FROM' in q:
            self._r = [('v40_20260922_01',), ('v40_20260804_01',)]
        elif q.startswith('MATCH (a)-[e:'):
            t = q.split('[e:')[1].split(']')[0]
            self._r = self.edges.get(t, [])
        elif q.startswith('MATCH (n:'):
            lab = q.split('(n:')[1].split(')')[0]
            self._r = [(0 if 'IS NULL' in q else self.counts.get(lab, 0),)]
        else:
            self._r = []

    def fetchall(self):
        return self._r

    def fetchone(self):
        return self._r[0] if self._r else None


def test_plan_targets_suffixed_and_skips_unmatched():
    rb = _load('rebuild_v49')
    have = ['ep%d_graph' % i for i in range(1, 11)]
    steps, notes = rb.plan(Cur(graphs=have), Cur(graphs=['ccop_ep_integrated', 'v40_20260922_01']),
                           '_v49', ['integrated', 'v40'])
    assert [s['target'] for s in steps] == ['ccop_ep_integrated_v49', 'v40_20260922_01_v49']
    assert all(s['target'].endswith('_v49') for s in steps)
    assert any('v40_20260804_01' in n for n in notes)


def test_audit_flags_deprecated_and_direction():
    au = _load('audit_v49')
    cur = Cur(labels=[('vt_psn', 'v'), ('vt_bacnt', 'v'), ('vt_email', 'v'), ('has_account', 'e'), ('hosts', 'e')],
              counts={'vt_psn': 2, 'vt_bacnt': 1, 'vt_email': 1},
              edges={'has_account': [('vt_psn', 'vt_bacnt', 3), ('vt_bacnt', 'vt_psn', 1)], 'hosts': [('vt_ip', 'vt_site', 2)]})
    r = au.audit(cur, 'zz_g')
    v = r['violations']
    assert v['label_deprecated'] == {'vt_email': 1}
    assert v['edge_direction'] == {'has_account|vt_bacnt|vt_psn': 1}
    assert v['edge_outside'] == {'hosts|vt_ip|vt_site': 2}
    assert r['violation_count'] == 4


def test_compare_reports_only_changes():
    rb = _load('rebuild_v49')
    old = {'nodes': 3, 'edges': 2, 'labels': {'vt_psn': 2, 'vt_email': 1}, 'edge_types': {'has_account|vt_psn|vt_bacnt': 2}}
    new = {'nodes': 2, 'edges': 2, 'labels': {'vt_psn': 2}, 'edge_types': {'has_account|vt_psn|vt_bacnt': 2}}
    c = rb.compare(old, new)
    assert c['labels'] == {'vt_email': [1, 0]} and c['edge_types'] == {}


def test_rebuilt_integrated_graph_gets_integrated_prompt():
    from app.services import langgraph_agent as la
    if not la.T2C_INTEGRATED_SYSTEM_PROMPT:
        return
    for g in ('ccop_ep_integrated', 'ccop_ep_integrated_v49', 'ccop_test_graph'):
        assert la._system_prompt_for(g) is la.T2C_INTEGRATED_SYSTEM_PROMPT
    for g in ('ccop_ep_integrated_x', 'v40_20260922_01', ''):
        assert la._system_prompt_for(g) is la.T2C_V37_SYSTEM_PROMPT
