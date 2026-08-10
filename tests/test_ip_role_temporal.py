"""V4.6 S3+#3 — ip_role 구간 계산 & call_center 분포임계 단위테스트 (순수 함수, DB 무관).

설계: docs/ONTOLOGY_V46_IP_ROLE_BITEMPORAL_DESIGN.md
분류 정의는 번들 CLAUDE.md 실측: single_user(1) / shared_small(2..θ-1) / call_center(≥θ) / infra.
검증 핵심: 시간축 전환 · sameAs 해소 순서(G12) · coalesce · 분포기반 call_center 경계.
"""
from app.services.ip_role_temporal import (
    compute_ip_role_timeline, classify_role, ip_role_current,
    call_center_threshold, derive_valid_interval,
)


def test_transition_shared_to_single():
    """27.193.61.154 시나리오: 3월 3명 공유(shared_small) → 4월 1명 단독(single_user).

    기존 전 기간 통합 계산은 이를 하나로 뭉갰다. 구간 계산은 갈라야 한다.
    """
    edges = [
        {'subject': 'A', 'valid_from': '2017-03-01', 'valid_to': '2017-04-26'},
        {'subject': 'B', 'valid_from': '2017-03-01', 'valid_to': '2017-04-01'},
        {'subject': 'C', 'valid_from': '2017-03-01', 'valid_to': '2017-04-01'},
    ]
    tl = compute_ip_role_timeline(edges)          # 기본 θ=5 → 3명은 shared_small
    assert len(tl) == 2
    assert tl[0]['role'] == 'shared_small' and tl[0]['entity_cnt'] == 3
    assert tl[0]['from'] == '2017-03-01' and tl[0]['to'] == '2017-04-01'
    assert tl[1]['role'] == 'single_user' and tl[1]['entity_cnt'] == 1
    assert ip_role_current(tl) == 'single_user'


def test_call_center_when_over_theta():
    """entity_cnt ≥ θ → call_center (번들 정의: 다수 실체 공유 = 콜센터 인프라)."""
    edges = [{'subject': f's{i}', 'valid_from': '2017-03-01', 'valid_to': '2017-04-01'}
             for i in range(6)]                    # 6명 ≥ θ=5
    tl = compute_ip_role_timeline(edges, theta_call_center=5)
    assert tl[0]['role'] == 'call_center' and tl[0]['entity_cnt'] == 6


def test_sameas_resolution_before_role():
    """G12: subject 3명이 sameAs로 1 entity → single_user (subject 기준 오분류 방지)."""
    edges = [
        {'subject': 'a1', 'valid_from': '2017-03-01', 'valid_to': '2017-03-31'},
        {'subject': 'a2', 'valid_from': '2017-03-01', 'valid_to': '2017-03-31'},
        {'subject': 'a3', 'valid_from': '2017-03-01', 'valid_to': '2017-03-31'},
    ]
    tl = compute_ip_role_timeline(
        edges, sameas_map={'a1': 'A', 'a2': 'A', 'a3': 'A'})
    assert len(tl) == 1
    assert tl[0]['role'] == 'single_user'          # entity 기준 1
    assert tl[0]['entity_cnt'] == 1 and tl[0]['subject_cnt'] == 3


def test_coalesce_adjacent_same_role():
    """맞닿은 동일 role 구간은 하나로 병합."""
    edges = [
        {'subject': 'A', 'valid_from': '2017-01-01', 'valid_to': '2017-02-01'},
        {'subject': 'A', 'valid_from': '2017-02-01', 'valid_to': '2017-03-01'},
    ]
    tl = compute_ip_role_timeline(edges)
    assert len(tl) == 1
    assert tl[0]['from'] == '2017-01-01' and tl[0]['to'] == '2017-03-01'


def test_hosting_is_infra_regardless_of_count():
    """호스팅 대역은 사용자 수와 무관하게 infra."""
    edges = [{'subject': s, 'valid_from': '2017-01-01', 'valid_to': '2017-02-01'}
             for s in ('A', 'B', 'C', 'D', 'E', 'F')]
    tl = compute_ip_role_timeline(edges, is_hosting=True)
    assert tl[0]['role'] == 'infra'


def test_open_ended_valid_to():
    """valid_to None(진행중) → 최신까지 유효."""
    edges = [{'subject': 'A', 'valid_from': '2017-01-01', 'valid_to': None}]
    tl = compute_ip_role_timeline(edges)
    assert len(tl) == 1 and tl[0]['role'] == 'single_user'
    assert tl[0]['to'] == '9999-12-31'


def test_empty():
    assert compute_ip_role_timeline([]) == []
    assert ip_role_current([]) is None


def test_classify_thresholds():
    assert classify_role(1, theta_call_center=5) == 'single_user'
    assert classify_role(3, theta_call_center=5) == 'shared_small'
    assert classify_role(5, theta_call_center=5) == 'call_center'
    assert classify_role(10, theta_call_center=5) == 'call_center'
    assert classify_role(0) is None


# ── #3 call_center 분포임계 ───────────────────────────────────────────

def test_call_center_threshold_percentile():
    """골 없는 편중 분포에서 상위 백분위로 경계 산출 (고정 5 대체)."""
    # 공유 IP entity_cnt: 대부분 2~4, 얇은 꼬리 5~12
    cnts = ([1] * 11575 +                          # single(대상 아님, floor로 제외)
            [2] * 1000 + [3] * 300 + [4] * 100 +   # shared_small
            [5, 6, 7, 8, 9, 10, 11, 12] * 4)        # 꼬리(call_center 후보)
    th = call_center_threshold(cnts, method='percentile', p=98)
    assert isinstance(th, int) and th >= 3         # floor+1 이상, 꼬리 반영


def test_call_center_threshold_mad_robust():
    cnts = [2] * 500 + [3] * 200 + [4] * 50 + [8, 9, 10, 11, 12]
    th = call_center_threshold(cnts, method='mad', k=3.0)
    assert th >= 3


def test_call_center_threshold_empty():
    assert call_center_threshold([], floor=2) == 3     # floor+1 fallback
    assert call_center_threshold([1, 1, 1], floor=2) == 3  # 공유 없음


# ── S2 백필 규칙 (접속시각 → valid_from/to) ─────────────────────────

def test_derive_interval_range():
    assert derive_valid_interval('2017-03-01 10:00:00', '2017-04-01 12:00:00') \
        == ('2017-03-01', '2017-04-01')


def test_derive_interval_point_in_time():
    """단일 관측(min==max) → window(기본 1d)로 0폭 구간 방지. graph45 usage_count=1 케이스."""
    assert derive_valid_interval('2017-04-01 21:43:11', '2017-04-01 21:43:11') \
        == ('2017-04-01', '2017-04-02')


def test_derive_interval_window():
    assert derive_valid_interval('2017-04-01', '2017-04-01', window_days=7) \
        == ('2017-04-01', '2017-04-08')


def test_derive_interval_none():
    assert derive_valid_interval(None, None) == (None, None)


def test_backfill_to_timeline_e2e():
    """S2→S3 파이프라인: 접속시각 백필 → 구간계산 → 전환 재현."""
    a = derive_valid_interval('2017-03-01', '2017-04-25')   # A: 3~4월
    b = derive_valid_interval('2017-03-01', '2017-03-20')   # B: 3월만
    edges = [{'subject': 'A', 'valid_from': a[0], 'valid_to': a[1]},
             {'subject': 'B', 'valid_from': b[0], 'valid_to': b[1]}]
    tl = compute_ip_role_timeline(edges, theta_call_center=5)
    roles = [s['role'] for s in tl]
    assert 'shared_small' in roles and 'single_user' in roles  # 공유→단독 전환
