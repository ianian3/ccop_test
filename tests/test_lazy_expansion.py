"""V4.6 #2 E2 — 지연확장 순수로직 단위테스트 (DB 무관).

설계: docs/ONTOLOGY_V46_LAZY_EXPANSION_DESIGN.md
검증: 지연확장 3조건 · Bridge Key 조회대상 · 표본 상한.
"""
import pytest
from app.services.lazy_expansion import (
    should_expand, build_expansion, sample_ids, BRIDGE_KEY, SAMPLE_CAP,
)


def test_should_expand_three_conditions():
    assert should_expand(5, requested=True) is True     # 수사 관심
    assert should_expand(5, evidence=True) is True       # 증거 특정
    assert should_expand(500, theta=100) is True         # 임계 초과
    assert should_expand(5, theta=100) is False          # 미충족 → 경량
    assert should_expand(None) is False                  # 방어


def test_should_expand_theta_boundary():
    assert should_expand(100, theta=100) is True         # 경계 포함(>=)
    assert should_expand(99, theta=100) is False


def test_build_expansion_access():
    r = build_expansion('vt_access', ['lgn-1', 'lgn-2', 'lgn-3'])
    assert r['table'] == 'TB_SYS_LGN_EVT'
    assert r['pk_col'] == 'LGN_SN'
    assert r['count'] == 3 and r['pks'] == ['lgn-1', 'lgn-2', 'lgn-3']


def test_build_expansion_msg():
    r = build_expansion('vt_msg', ['m1'])
    assert r['table'] == 'TB_TELNO_SMS_MSG' and r['pk_col'] == 'MSG_SN'


def test_build_expansion_unsupported_raises():
    with pytest.raises(ValueError):
        build_expansion('vt_ip', ['x'])                  # Bridge Key 없음


def test_sample_ids_cap():
    ids = list(range(100))
    assert sample_ids(ids) == list(range(SAMPLE_CAP))    # 상한 20
    assert sample_ids([1, 2]) == [1, 2]                  # 소량은 그대로
    assert sample_ids(None) == []


def test_bridge_key_covers_aggregatable_nodes():
    # 집약 대상 노드(vt_access·vt_msg)는 모두 Bridge Key 보유
    assert set(BRIDGE_KEY) == {'vt_access', 'vt_msg'}
