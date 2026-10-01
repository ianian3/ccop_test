# tests/test_etl_manual_writer.py
"""
CSV ETL · 수동 생성 API · 모델러 적재의 GraphWriter 이관 (정합 2단계 2d, 2026-10-01).

로컬 AgensGraph 임시 그래프(zz_*) 실측: CSV 하이픈/무하이픈 계좌 병합·인물 키 psn:csv:<파일명>:<이름>·
역방향·삭제 엣지 행 거부 / 수동 생성 MERGE(같은 계좌 재입력 → 같은 노드)·vt_email 거부·id 주입 거부 /
모델러 test_v40 계좌 899행 → 893노드(하이픈 중복 6 병합)·SoT 밖 라벨·엣지는 경고만.
"""
import inspect

from app.services.etl_service import ETLService
from app.services.graph_service import GraphService


def test_user_key_column_moves_to_canonical_key():
    assert ETLService._to_canonical_key('vt_bacnt', {'actno': '1-2', 'x': 1}, 'actno') == {'account_no': '1-2', 'x': 1}
    assert ETLService._to_canonical_key('vt_psn', {'name': '홍'}, 'name') == {'name': '홍'}        # 합성 키에 맡김
    assert ETLService._to_canonical_key('vt_id', {'id': 'abc'}, 'id') == {'id_val': 'abc', 'platform': 'unknown'}
    assert ETLService._to_canonical_key('my_lbl', {'k': 1}, 'k') == {'k': 1}                       # SoT 밖 라벨은 그대로


def test_csv_scope_from_filename():
    class F:
        filename = 'EP 3/사건 목록.csv'
    assert ETLService._csv_scope(F(), {}) == 'csv:사건_목록'
    assert ETLService._csv_scope(F(), {'scope': 'ep3'}) == 'csv:ep3'
    assert ETLService._csv_scope(object(), {}) == 'csv'


def test_etl_no_longer_matches_endpoints_by_any_label():
    src = inspect.getsource(ETLService.import_csv)
    assert 'GraphWriter(cur, target_graph, mode=\'strict\', prop_mode=\'warn\'' in src
    assert 'properties @> %s::jsonb' not in src            # 라벨 무관 LIMIT 1 검색(다른 노드에 붙음) 제거
    assert "'vt_flnm'" not in src                          # 폐기 라벨 인덱스 목록 제거


def test_manual_key_generation():
    p = GraphService._manual_key('vt_psn', {'name': '홍'})
    assert p['psn_id'].startswith('psn:manual:') and p['creation_method'] == 'manual'
    assert len(GraphService._manual_key('vt_transfer', {})['transfer_id']) == 36
    assert 'account_no' not in GraphService._manual_key('vt_bacnt', {'bank_nm': 'x'})   # 자연 키는 만들지 않음


def test_manual_create_uses_writer_policy():
    for fn in (GraphService.create_manual_node, GraphService.create_manual_edge):
        assert "GraphWriter(cur, graph_name, mode='strict', prop_mode='warn'" in inspect.getsource(fn)
    assert 'safe_elem_id(element_id)' in inspect.getsource(GraphService.delete_element)


def test_modeler_uses_warn_mode():
    from app import routes
    src = inspect.getsource(routes.modeler_load_data)
    assert "mode='warn'" in src and 'key_override=_ko' in src
    assert 'ON CREATE SET n =' not in src
