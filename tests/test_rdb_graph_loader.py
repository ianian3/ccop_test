# tests/test_rdb_graph_loader.py
"""
RDB(test_v40 스테이징) → 그래프 테이블별 적재기 (정합 2단계 2c, 2026-10-01).

가짜 커서가 스테이징 SELECT 에 고정 행을 돌려주고, GraphWriter 버퍼에 쌓인 노드·엣지를 검사한다(DB 불필요).
로컬 구/신 비교 결과(같은 test_v40 63,172행): to_account +2,857 · from_account +177 · owns_phone +2,252 복원,
하이픈/무하이픈 같은 계좌 6건 병합, 감사 위반 0·vt_psn.psn_id 충전 100%(구 0%).
"""
import pytest

from app.services.rdb_graph_loader import RdbGraphLoader, V40_TABLES
from app.services.graph_writer import GraphWriter, GraphWriteError

ROWS = {
    'tb_incdnt_mst': [('C-1', '보이스피싱 사건', '2024-01-02')],
    'tb_prsn': [('P-1', '홍길동', 'S1'), ('P-2', '', 'S1')],
    'tb_fin_bacnt': [('110-123-456', '004', '국민', '홍길동', 'S1'), ('ATM강남01', '', '', None, 'S1')],
    'tb_telno_mst': [('010-1234-5678', '김가입', 'SKT', 'S1')],
    'tb_fin_bacnt_dlng': [('D-1', '110123456', '2024-01-03', 50000, 'ATM강남01', 'withdraw', 'S1')],
    'tb_telno_call_dtl': [('K-1', '01012345678', '01099998888', '2024-01-04', 30, 'S1')],
    'tb_incdnt_prsn': [('C-1', 'P-1', 'SUSPECT'), ('C-1', 'P-2', 'REPORTER')],
    'tb_telno_join': [('010-1234-5678', 'P-1')],
}
OWN = [('110-123-456', 'P-1')]


class FakeCursor:
    description = None

    def __init__(self):
        self.sql, self._rows = [], []

    def execute(self, q, params=None):
        self.sql.append(q)
        if 'information_schema.tables' in q:
            self._rows = [(t,) for t in V40_TABLES]
        elif 'JOIN' in q and 'tb_fin_bacnt b' in q:
            self._rows = OWN
        else:
            if 'tb_incdnt_prsn ip' in q:
                self._rows = ROWS['tb_incdnt_prsn']
                return
            # 긴 테이블명부터 (tb_fin_bacnt_dlng 가 tb_fin_bacnt 로 잡히지 않게)
            k = next((k for k in sorted(ROWS, key=len, reverse=True) if f'.{k}' in q), None)
            self._rows = ROWS[k] if k else []

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return None


class FakeConn:
    def __init__(self):
        self.c = FakeCursor()

    def cursor(self):
        return self.c

    def commit(self):
        pass


@pytest.fixture
def loaded():
    ldr = RdbGraphLoader(FakeConn(), 'zz_g', 'test_v40')
    w = GraphWriter(ldr.cur, 'zz_g', mode='strict')
    for name in RdbGraphLoader.LOADERS:
        getattr(ldr, name)(w)
    return w, ldr


def test_person_key_is_psn_id_and_anonymity(loaded):
    w, _ = loaded
    p = w._nodes['vt_psn']
    assert set(p) == {('P-1',), ('P-2',)}
    assert p[('P-1',)]['is_anonymous'] is False and p[('P-2',)]['is_anonymous'] is True
    assert 'nickname' not in p[('P-1',)] and 'id' not in p[('P-1',)]


def test_sot_attribute_names(loaded):
    w, _ = loaded
    acct = w._nodes['vt_bacnt'][('110123456',)]
    assert acct['bank_nm'] == '국민' and acct['dpstr'] == '홍길동' and 'bank_name' not in acct
    tel = w._nodes['vt_telno'][('01012345678',)]
    assert tel['subs_holder'] == '김가입' and tel['telco_nm'] == 'SKT'           # 종전엔 가입자명이 통신사명으로
    case = w._nodes['vt_case'][('C-1',)]
    assert case['incdnt_nm'] == '보이스피싱 사건' and 'crime' not in case
    tr = w._nodes['vt_transfer'][('D-1',)]
    assert tr['transfer_id'] == tr['event_id'] == 'D-1' and tr['dlng_amt'] == 50000.0


def test_edges_use_normalized_keys(loaded):
    w, _ = loaded
    edges = {k[0]: v for k, v in w._edges.items()}
    assert ('110123456',) in {sk for (sk, _), _ in edges['from_account'].items()}   # 원천 무하이픈 ↔ 노드 하이픈 → 같은 키
    assert ('vt_atm' in {k[2] for k in w._edges if k[0] == 'to_account'})
    assert ('P-1',) in {sk for (sk, _) in edges['has_account']}
    assert ('01012345678',) in {dk for (_, dk) in edges['owns_phone']}


def test_unknown_role_becomes_witness_unknown(loaded):
    w, _ = loaded
    wit = w._edges[('witness_in', 'vt_psn', 'vt_case')]
    assert [e['p'].get('role') for e in wit.values()] == ['unknown']
    assert ('suspect_in', 'vt_psn', 'vt_case') in w._edges


def test_rejects_bad_names():
    with pytest.raises(GraphWriteError):
        RdbGraphLoader(FakeConn(), 'g; DROP', 'test_v40')
    with pytest.raises(GraphWriteError):
        RdbGraphLoader(FakeConn(), 'g', 'x"; --')


def test_transfer_data_routes_staging_to_new_loader():
    import inspect
    from app.services.rdb_to_graph_service import RdbToGraphService
    src = inspect.getsource(RdbToGraphService.transfer_data)
    assert 'RdbGraphLoader(conn, graph_name, source_schema).run()' in src
