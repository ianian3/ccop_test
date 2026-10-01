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
    # 이용 이력·출처 (2026-10-01 추가)
    'tb_id_use': [('P-1', 'abc', '네이버', '2024-01-01', None, 'S1'), ('P-1', 'dup', '네이버', None, None, 'S1'),
                  ('P-2', 'dup', '카카오톡', None, None, 'S1'), ('', 'nopsn', None, None, None, 'S1')],
    'tb_ip_use': [('id', 'abc', '1.1.1.1', '2024-01-03', '2024-01-03', 'web', 'S1'),
                  ('id', 'abc', '1.1.1.1', '2024-01-01', '2024-01-05', 'banking', 'S1'),
                  ('id', 'dup', '1.1.1.1', None, None, None, 'S1'),                 # 플랫폼 모호 → 건너뜀
                  ('bacnt', '110-123-456', '2.2.2.2', None, None, None, 'S1')],
    'tb_loc_use': [('telno', '010-1234-5678', '서울 강남구', '2024-01-02 10:00', 'S1'),
                   ('telno', '01012345678', '서울 강남구', '2024-01-01 09:00', 'S1'),
                   ('bacnt', 'ATM강남01', '서울 강남구', '2024-01-03 00:00', 'S1')],
    'tb_fin_extrc_bacnt': [('110-123-456', 'P-2', 'S2'), ('ATM강남01', 'ATM출금', 'S2')],
    'tb_entity_source': [('tb_prsn', 'P-1', 'S2', 'KICS', '2024-01-01'),
                         ('tb_fin_bacnt', 'ATM강남01', 'S2', 'KICS', None), ('tb_other', 'x', 'S2', 'KICS', None)],
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


# ── 이용 이력·출처 테이블 (2026-10-01 추가) ───────────────────────

def test_id_use_creates_accounts_and_uses_id(loaded):
    w, ldr = loaded
    ids = w._nodes['vt_id']
    assert ('nopsn', 'unknown') in ids                                  # 플랫폼 빈값 → unknown (키 정렬: id_val, platform)
    uses = w._edges[('uses_id', 'vt_psn', 'vt_id')]
    assert {sk for sk, _ in uses} == {('P-1',), ('P-2',)}                # prsn_id 빈 행은 엣지 없음


def test_ip_use_aggregates_and_skips_ambiguous(loaded):
    w, ldr = loaded
    (e,) = w._edges[('used_ip', 'vt_id', 'vt_ip')].values()
    assert e['p']['usage_count'] == 2 and e['p']['valid_from'] == '2024-01-01' and e['p']['valid_to'] == '2024-01-05'
    assert e['p']['access_type'] == 'web|banking'
    assert ldr.counts['ip_use_skipped'] == 1
    assert ('used_ip', 'vt_bacnt', 'vt_ip') in w._edges


def test_loc_use_normalized_subject_and_aggregation(loaded):
    w, _ = loaded
    (e,) = w._edges[('located_at', 'vt_telno', 'vt_loc')].values()     # 하이픈 유무가 달라도 한 주체
    assert (e['p']['first_dt'], e['p']['last_dt'], e['p']['evt_count']) == ('2024-01-01 09:00', '2024-01-02 10:00', 2)
    assert ('located_at', 'vt_atm', 'vt_loc') in w._edges
    assert w._nodes['vt_loc'][('서울 강남구',)]['address'] == '서울 강남구'


def test_extracted_accounts_skip_atm(loaded):
    w, _ = loaded
    pairs = set(w._edges[('has_account', 'vt_psn', 'vt_bacnt')])
    assert (('P-2',), ('110123456',)) in pairs and all('ATM' not in str(p) for p in pairs)


def test_entity_sources_link_multiple_sources(loaded):
    w, ldr = loaded
    sf = w._edges
    assert (('P-1',), ('S2',)) in sf[('sourced_from', 'vt_psn', 'vt_src')]
    assert ('sourced_from', 'vt_atm', 'vt_src') in sf
    assert ldr.counts['entity_sources_skipped'] == 1
