"""V4.6 S3 — ip_role 구간 계산 단위테스트 (순수 함수, DB 무관).

설계: docs/ONTOLOGY_V46_IP_ROLE_BITEMPORAL_DESIGN.md
검증 핵심: 시간축 전환 · sameAs 해소 순서(G12) · coalesce.
"""
from app.services.ip_role_temporal import (
    compute_ip_role_timeline, classify_role, ip_role_current,
)


def test_transition_shared_to_single():
    """27.193.61.154 시나리오: 3월 3명 공유 → 4월 1명 단독 (시간축 핵심).

    기존 전 기간 통합 계산은 이를 'shared' 하나로 뭉갰다. 구간 계산은 갈라야 한다.
    """
    edges = [
        {'subject': 'A', 'valid_from': '2017-03-01', 'valid_to': '2017-04-26'},
        {'subject': 'B', 'valid_from': '2017-03-01', 'valid_to': '2017-04-01'},
        {'subject': 'C', 'valid_from': '2017-03-01', 'valid_to': '2017-04-01'},
    ]
    tl = compute_ip_role_timeline(edges, theta_shared=3)
    assert len(tl) == 2
    assert tl[0]['role'] == 'shared' and tl[0]['entity_cnt'] == 3
    assert tl[0]['from'] == '2017-03-01' and tl[0]['to'] == '2017-04-01'
    assert tl[1]['role'] == 'single_user' and tl[1]['entity_cnt'] == 1
    assert ip_role_current(tl) == 'single_user'


def test_sameas_resolution_before_role():
    """G12: subject 3명이 sameAs로 1 entity → single_user (subject 기준 오분류 방지)."""
    edges = [
        {'subject': 'a1', 'valid_from': '2017-03-01', 'valid_to': '2017-03-31'},
        {'subject': 'a2', 'valid_from': '2017-03-01', 'valid_to': '2017-03-31'},
        {'subject': 'a3', 'valid_from': '2017-03-01', 'valid_to': '2017-03-31'},
    ]
    tl = compute_ip_role_timeline(
        edges, sameas_map={'a1': 'A', 'a2': 'A', 'a3': 'A'}, theta_shared=3)
    assert len(tl) == 1
    assert tl[0]['role'] == 'single_user'          # entity 기준 1
    assert tl[0]['entity_cnt'] == 1 and tl[0]['subject_cnt'] == 3


def test_coalesce_adjacent_same_role():
    """맞닿은 동일 role 구간은 하나로 병합."""
    edges = [
        {'subject': 'A', 'valid_from': '2017-01-01', 'valid_to': '2017-02-01'},
        {'subject': 'A', 'valid_from': '2017-02-01', 'valid_to': '2017-03-01'},
    ]
    tl = compute_ip_role_timeline(edges, theta_shared=3)
    assert len(tl) == 1
    assert tl[0]['from'] == '2017-01-01' and tl[0]['to'] == '2017-03-01'


def test_hosting_is_infra_regardless_of_count():
    """호스팅 대역은 사용자 수와 무관하게 infra."""
    edges = [{'subject': s, 'valid_from': '2017-01-01', 'valid_to': '2017-02-01'}
             for s in ('A', 'B', 'C', 'D', 'E')]
    tl = compute_ip_role_timeline(edges, is_hosting=True, theta_shared=3)
    assert tl[0]['role'] == 'infra'


def test_open_ended_valid_to():
    """valid_to None(진행중) → 최신까지 유효."""
    edges = [{'subject': 'A', 'valid_from': '2017-01-01', 'valid_to': None}]
    tl = compute_ip_role_timeline(edges, theta_shared=3)
    assert len(tl) == 1 and tl[0]['role'] == 'single_user'
    assert tl[0]['to'] == '9999-12-31'


def test_empty():
    assert compute_ip_role_timeline([]) == []
    assert ip_role_current([]) is None


def test_classify_thresholds():
    assert classify_role(1, theta_shared=5) == 'single_user'
    assert classify_role(3, theta_shared=5) == 'shared_small'
    assert classify_role(5, theta_shared=5) == 'shared'
    assert classify_role(2, theta_shared=5, is_call_center=True) == 'call_center'
    assert classify_role(0) is None
