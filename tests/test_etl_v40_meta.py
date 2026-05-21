"""Phase 2.1 회귀: ETL이 V4.0 메타 6 컬럼을 적재 시 자동 주입하는지 검증.

대상: app/services/etl_service.py L362 (메인 ETL), L732 (확장 ETL)
헬퍼: app.services.rdb_to_graph_service.RdbToGraphService.make_node_props_v40
"""
import warnings
warnings.filterwarnings('ignore')

from app.services.rdb_to_graph_service import RdbToGraphService


REQUIRED_META = {'id_format', 'source_domain', 'reliability_tier', 'rec_created'}


def test_main_etl_meta_injection_with_default_domain():
    """node_data.source_domain 미지정 → 기본 'KICS' 사용 → investigation/tier1."""
    props = RdbToGraphService.make_node_props_v40(
        'vt_telno', {'telno': '01012345678'}, source_domain='KICS',
    )
    assert REQUIRED_META.issubset(props.keys())
    assert props['source_domain'] == 'investigation'
    assert props['reliability_tier'] == 1
    assert props['id_format'] == 'no_hyphen_e164'


def test_main_etl_meta_injection_with_explicit_osint():
    props = RdbToGraphService.make_node_props_v40(
        'vt_site', {'url_addr': 'https://x.com'}, source_domain='OSINT',
    )
    assert props['source_domain'] == 'osint'
    assert props['reliability_tier'] == 4
    assert props['id_format'] == 'normalized_url'


def test_main_etl_meta_injection_partner_digital():
    props = RdbToGraphService.make_node_props_v40(
        'vt_file', {'hash_val': 'abc'}, source_domain='DIGITAL',
    )
    assert props['source_domain'] == 'partner'
    assert props['reliability_tier'] == 2


def test_main_etl_meta_injection_partner_ext():
    props = RdbToGraphService.make_node_props_v40(
        'vt_bacnt', {'account_no': '110-2222-3333'}, source_domain='EXT',
    )
    assert props['source_domain'] == 'partner'
    assert props['reliability_tier'] == 2


def test_source_id_propagation():
    props = RdbToGraphService.make_node_props_v40(
        'vt_psn', {'psn_id': 'p001'}, source_domain='KICS', source_id='kics_evt_001',
    )
    assert props['source_id'] == 'kics_evt_001'


def test_existing_props_not_overwritten():
    """이미 source_domain 이 있는 dict 는 보존."""
    base = {'telno': '01012345678', 'source_domain': 'osint', 'reliability_tier': 4}
    props = RdbToGraphService.make_node_props_v40(
        'vt_telno', base, source_domain='KICS',  # 강제 KICS 시도해도
    )
    # setdefault 이므로 기존 값 유지
    assert props['source_domain'] == 'osint'
    assert props['reliability_tier'] == 4


def test_v37_new_nodes_meta():
    """V3.7 신규 노드(pt_cluster, site_cluster) 도 정상 적용."""
    for label in ('pt_cluster', 'site_cluster'):
        p = RdbToGraphService.make_node_props_v40(
            label, {'cluster_id': 'c1'}, source_domain='KICS',
        )
        assert p['id_format'] == 'plain'
        assert p['source_domain'] == 'investigation'


def test_etl_service_imports_helper():
    """etl_service.py 가 RdbToGraphService.make_node_props_v40 을 실제로 import 하는지."""
    import app.services.etl_service as etl
    src = open(etl.__file__).read()
    assert 'make_node_props_v40' in src, "etl_service.py 에 V4.0 헬퍼 호출 누락"
    # 두 패치 지점(L362 메인 + L732 확장) 모두 적용되어야 → 최소 2회 등장
    assert src.count('make_node_props_v40') >= 2, "두 패치 지점 중 일부 누락"


# =========================================================================
# Phase 2.1.D — 엣지 V4.0 메타 회귀
# =========================================================================

EDGE_REQUIRED_META = {'source_domain', 'collected_at', 'rec_created'}


def test_edge_meta_default_domain():
    p = RdbToGraphService.make_edge_props_v40('holds', source_domain='KICS')
    assert EDGE_REQUIRED_META.issubset(p.keys())
    assert p['source_domain'] == 'investigation'


def test_edge_meta_osint_partner_inference():
    p1 = RdbToGraphService.make_edge_props_v40('belongs_to_campaign', source_domain='OSINT')
    p2 = RdbToGraphService.make_edge_props_v40('transferred', source_domain='DIGITAL')
    p3 = RdbToGraphService.make_edge_props_v40('used_in_device', source_domain='INFERENCE')
    assert p1['source_domain'] == 'osint'
    assert p2['source_domain'] == 'partner'
    assert p3['source_domain'] == 'inference'


def test_edge_meta_preserves_existing_props():
    base = {'from_dt': '2026-01-01', 'amount': 100000}
    p = RdbToGraphService.make_edge_props_v40('transferred', base, source_domain='KICS')
    assert p['from_dt'] == '2026-01-01'
    assert p['amount'] == 100000
    assert p['source_domain'] == 'investigation'


def test_edge_meta_source_id_optional():
    p_with = RdbToGraphService.make_edge_props_v40(
        'holds', source_domain='KICS', source_id='kics_evt_42',
    )
    p_without = RdbToGraphService.make_edge_props_v40('holds', source_domain='KICS')
    assert p_with['source_id'] == 'kics_evt_42'
    assert 'source_id' not in p_without


def test_edge_meta_no_reliability_tier():
    """엣지는 reliability_tier / id_format 미보유 (노드와 구분)."""
    p = RdbToGraphService.make_edge_props_v40('holds', source_domain='KICS')
    assert 'reliability_tier' not in p
    assert 'id_format' not in p


def test_etl_service_imports_edge_helper():
    import app.services.etl_service as etl
    src = open(etl.__file__).read()
    assert 'make_edge_props_v40' in src, "etl_service.py 에 V4.0 엣지 헬퍼 호출 누락"
    # 두 패치 지점(L440 메인 엣지 + L820 확장 엣지) 모두 → 최소 2회
    assert src.count('make_edge_props_v40') >= 2, "두 엣지 패치 중 일부 누락"
