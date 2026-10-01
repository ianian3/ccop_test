# tests/test_graph_writer.py
"""
공용 그래프 쓰기 계층 GraphWriter (정합 2단계 2a, 2026-10-01).

단위 테스트는 가짜 커서로 생성 쿼리를 검사한다(DB 불필요). 실제 AgensGraph 왕복은
CCOP_LOCAL_AGENS_DSN(예: 'dbname=tccopdb user=ccop password=… host=127.0.0.1 port=5434')이 있을 때만 —
임시 그래프 zz_writer_pytest 를 만들고 지운다. 운영 DB 에는 절대 쓰지 않는다.
"""
import os

import pytest

from app.services.graph_writer import GraphWriter, GraphWriteError


class FakeCursor:
    def __init__(self, counts=None):
        self.sql, self.description, self._rows, self.counts = [], None, [], list(counts or [])

    def execute(self, q, params=None):
        self.sql.append(q)
        if 'RETURN count(' in q:
            self.description = [('count',)]
            n = self.counts.pop(0) if self.counts else q.count('{k0:') + q.count('{a0:')
            self._rows = [(n,)]
        else:
            self.description, self._rows = None, []

    def fetchone(self):
        return self._rows[0] if self._rows else None


def _w(**kw):
    cur = FakeCursor(kw.pop('counts', None))
    return GraphWriter(cur, 'zz_g', **kw), cur


# ── 키 ─────────────────────────────────────────────────────────────

def test_person_key_synthesized_per_scope():
    w, _ = _w(scope='EP5')
    assert w.node('vt_psn', {'name': '김**'}) == {'psn_id': 'psn:EP5:김**'}
    assert w.node('vt_psn', {'name': '김**'}, scope='EP6') == {'psn_id': 'psn:EP6:김**'}   # A안: 다른 출처는 다른 사람
    assert w.node('vt_psn', {'psn_id': 'P-01', 'name': 'x'}) == {'psn_id': 'P-01'}         # ID 가 있으면 그대로


def test_person_without_scope_rejected():
    w, _ = _w()
    with pytest.raises(GraphWriteError):
        w.node('vt_psn', {'name': '홍길동'})


def test_account_normalized_and_deduped():
    w, _ = _w()
    assert w.node('vt_bacnt', {'account_no': '110-123 456', 'bank_cd': '004'}) == {'account_no': '110123456'}
    w.node('vt_bacnt', {'account_no': '110123456', 'bank_nm': '국민'})
    assert len(w._nodes['vt_bacnt']) == 1
    assert w._nodes['vt_bacnt'][('110123456',)] == {'account_no': '110123456', 'bank_cd': '004', 'bank_nm': '국민'}


def test_email_id_lowercased_composite_key():
    w, _ = _w()
    assert w.node('vt_id', {'platform': 'email', 'id_val': 'A@B.com'}) == {'platform': 'email', 'id_val': 'a@b.com'}
    assert w.node('vt_id', {'platform': 'kakao', 'id_val': 'AbC'}) == {'platform': 'kakao', 'id_val': 'AbC'}


# ── 정책 ───────────────────────────────────────────────────────────

@pytest.mark.parametrize('call', [
    lambda w: w.node('vt_email', {'email_addr': 'x'}),                                       # 삭제 라벨
    lambda w: w.node('vt_bacnt', {'account_no': '1', 'dpstr_nm': 'x'}),                      # 옛 속성명
    lambda w: w.edge('hosts', ('vt_ip', {'ip_addr': '1'}), ('vt_site', {'url_addr': 'u'})),  # 삭제 엣지
    lambda w: w.edge('has_account', ('vt_bacnt', {'account_no': '1'}), ('vt_psn', {'psn_id': 'p'})),   # 방향
    lambda w: w.edge('used_ip', ('vt_psn', {'psn_id': 'p'}), ('vt_ip', {'ip_addr': '1'}), {'tx_count': 1}),
])
def test_strict_rejects(call):
    w, _ = _w(scope='S')
    with pytest.raises(GraphWriteError):
        call(w)


def test_identifier_injection_always_rejected():
    with pytest.raises(GraphWriteError):
        GraphWriter(FakeCursor(), 'g; DROP GRAPH x')
    w, _ = _w(mode='off')
    with pytest.raises(ValueError):
        w.node('vt_bacnt', {'account_no': '1', "x}) DETACH DELETE n //": 'v'})


def test_warn_mode_for_free_design():
    w, cur = _w(mode='warn')
    w.node('custom_lbl', {'k': '1', 'x': 2})
    stats = w.flush()
    assert stats['warnings'] == ['SoT 밖 노드 라벨: custom_lbl'] and stats['nodes'] == 1


# ── 집계·기록 ─────────────────────────────────────────────────────

def test_used_ip_pair_aggregation():
    w, _ = _w()
    for t, a in (('2024-01-03', 'web'), ('2024-01-01', 'banking'), ('2024-02-01', 'web')):
        w.edge('used_ip', ('vt_bacnt', {'account_no': '1'}), ('vt_ip', {'ip_addr': '1.2.3.4'}),
               {'valid_from': t, 'valid_to': t, 'usage_count': 1, 'access_type': a})
    (e,) = w._edges[('used_ip', 'vt_bacnt', 'vt_ip')].values()
    assert e['p'] == {'valid_from': '2024-01-01', 'valid_to': '2024-02-01', 'usage_count': 3, 'access_type': 'web|banking'}


def test_flush_sql_shape_and_escaping():
    w, cur = _w(scope='S')
    w.node('vt_psn', {'name': "O'Brien"})
    w.node('vt_bacnt', {'account_no': '1', 'note': 'C:\\p'})
    w.flush()
    merges = [q for q in cur.sql if q.startswith('UNWIND')]
    assert any("MERGE (n:vt_psn {psn_id: r.k0}) SET n += r.p" in q for q in merges)
    joined = '\n'.join(merges)
    assert "'psn:S:O''Brien'" in joined and "'C:\\\\p'" in joined
    assert 'SET n = ' not in joined                         # 다른 적재기 속성을 지우는 전체 대입 금지


def test_unmatched_edges_counted():
    w, cur = _w(counts=[1, 0])                              # 노드 1건 MERGE, 엣지 MATCH 0건
    w.node('vt_bacnt', {'account_no': '1'})
    w.edge('transferred_to', ('vt_bacnt', {'account_no': '1'}), ('vt_bacnt', {'account_no': '999'}), {'txn_count': 1})
    s = w.flush()
    assert (s['nodes'], s['edges'], s['edges_unmatched']) == (1, 0, 1)


# ── 실제 AgensGraph 왕복 (로컬 전용) ──────────────────────────────

@pytest.mark.skipif(not os.getenv('CCOP_LOCAL_AGENS_DSN'), reason='로컬 AgensGraph DSN 미설정')
def test_roundtrip_local_agensgraph():
    import psycopg2
    conn = psycopg2.connect(os.environ['CCOP_LOCAL_AGENS_DSN'])
    conn.autocommit = True
    cur = conn.cursor()
    g = 'zz_writer_pytest'
    cur.execute(f'DROP GRAPH IF EXISTS {g} CASCADE')
    cur.execute(f'CREATE GRAPH {g}')
    try:
        w = GraphWriter(cur, g, scope='EP5')
        w.node('vt_psn', {'name': "O'Brien"})
        w.node('vt_bacnt', {'account_no': '110-123', 'note': 'C:\\p'})
        w.edge('has_account', ('vt_psn', {'name': "O'Brien"}), ('vt_bacnt', {'account_no': '110123'}))
        assert w.flush()['edges'] == 1
        w2 = GraphWriter(cur, g, scope='EP5')
        w2.node('vt_bacnt', {'account_no': '110123', 'bank_nm': '국민'})
        w2.flush()
        cur.execute(f'SET graph_path = {g}')
        cur.execute('MATCH (b:vt_bacnt) RETURN b.note, b.bank_nm')
        assert cur.fetchall() == [('C:\\p', '국민')]          # SET += 로 기존 속성 보존 · 백슬래시 왕복
    finally:
        cur.execute(f'DROP GRAPH {g} CASCADE')
        conn.close()
