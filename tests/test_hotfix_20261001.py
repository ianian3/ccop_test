# tests/test_hotfix_20261001.py
"""
0단계 핫픽스 회귀 (2026-10-01 코드 정합 검토 P0).

1. T2C 방향 교정기가 출발·도착 라벨이 같은 엣지(transferred_to·same_as)를 항상 뒤집던 결함
2. RDB 적재기 교차 조인(TB_PRSN × TB_FRD_VCTM_RPT) → 거짓 has_account·owns_phone
3. Cypher 문자열 이스케이프 — AgensGraph 는 \\' 를 이스케이프로 보지 않음(행 누락·주입), '' + 백슬래시 2배가 정답
4. 요청값 식별자(그래프명·스키마명·라벨·속성 키·요소 id) 검증, ETL SQL 파라미터 바인딩
DB 없이 실행.
"""
import os
import re

import pytest

from app.database import cypher_str, safe_ident, safe_elem_id
from app.services.ai_service import AIService

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _src(rel):
    return open(os.path.join(ROOT, rel), encoding='utf-8').read()


# ── 1. 방향 교정 ────────────────────────────────────────────────────

@pytest.mark.parametrize('q', [
    "MATCH (a:vt_bacnt {account_no:'1'})-[r:transferred_to]->(b:vt_bacnt) RETURN b",   # 나간 돈
    "MATCH (a:vt_bacnt {account_no:'1'})<-[r:transferred_to]-(b:vt_bacnt) RETURN b",   # 들어온 돈
    "MATCH (a:vt_psn)-[r:same_as]->(b:vt_psn) RETURN b",
    "MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt) RETURN b",
    "MATCH (b:vt_bacnt)<-[r:has_account]-(p:vt_psn) RETURN b",
])
def test_direction_fix_keeps_valid_queries(q):
    assert AIService._fix_relation_direction(q) == q


def test_direction_fix_still_corrects_reversed():
    q = "MATCH (b:vt_bacnt)-[r:has_account]->(p:vt_psn) RETURN b"
    assert AIService._fix_relation_direction(q) == "MATCH (b:vt_bacnt)<-[r:has_account]-(p:vt_psn) RETURN b"


# ── 2. 교차 조인 제거 ──────────────────────────────────────────────

def test_no_cross_join_ownership_inference():
    s = '\n'.join(l for l in _src('app/services/rdb_to_graph_service.py').splitlines()
                  if not l.lstrip().startswith('#'))          # 제거 경위를 적은 주석은 제외
    assert 'FROM TB_PRSN P, TB_FRD_VCTM_RPT R' not in s
    # transfer_case: 사건 참여자 → 신고서 피의자 계좌 명의(has_account·owns_phone) 생성 금지
    assert "(p:vt_psn {{id: '{pid_s}'}}), (a:vt_bacnt" not in s
    assert "(p:vt_psn {{id: '{pid_s}'}}), (t:vt_telno" not in s


# ── 3. 이스케이프 ──────────────────────────────────────────────────

@pytest.mark.parametrize('raw,esc', [
    ("O'Brien", "O''Brien"),
    ("C:\\path", "C:\\\\path"),
    ("x' OR 1=1 //", "x'' OR 1=1 //"),
    (None, ''),
])
def test_cypher_str(raw, esc):
    assert cypher_str(raw) == esc


def test_no_backslash_quote_escaping_left():
    """\\' 이스케이프는 AgensGraph 에서 문자열을 끝내 주입 경로가 된다 — 앱·주요 적재 스크립트에 남지 않게."""
    bad = re.compile(r"""replace\(\s*["']'["']\s*,\s*["']\\\\'["']\s*\)""")
    files = [os.path.join(dp, f) for dp, _, fs in os.walk(os.path.join(ROOT, 'app')) for f in fs if f.endswith('.py')]
    files += [os.path.join(ROOT, 'scripts', f) for f in ('osint_ingest.py', 'add_evidence_csv.py')]
    hits = [f for f in files if bad.search(open(f, encoding='utf-8').read())]
    assert not hits, hits


# ── 4. 식별자 검증 ─────────────────────────────────────────────────

@pytest.mark.parametrize('ok', ['vt_psn', 'has_account', 'account_no', '_x1'])
def test_safe_ident_ok(ok):
    assert safe_ident(ok) == ok


@pytest.mark.parametrize('bad', ['', 'vt psn', "a'b", 'x})-[r]-(', '1abc', None, 'n.name'])
def test_safe_ident_rejects(bad):
    with pytest.raises(ValueError):
        safe_ident(bad)


def test_safe_elem_id():
    assert safe_elem_id('3.17') == '3.17'
    for bad in ("3.17' OR 1=1", 'abc', ''):
        with pytest.raises(ValueError):
            safe_elem_id(bad)


def test_transfer_data_rejects_bad_names(app):
    from app.services.rdb_to_graph_service import RdbToGraphService as R
    with app.app_context():
        ok, msg = R.transfer_data("g; DROP GRAPH x", source_schema='test_v40')
        assert ok is False and '그래프명' in msg
        ok, msg = R.transfer_data('test_ai01', source_schema='x", public; --')
        assert ok is False and '스키마명' in msg


def test_etl_additional_relations_parameterized():
    s = _src('app/services/etl_service.py')
    assert "cur.execute(edge_create_query, (add_src_key, add_src_val, add_tgt_key, add_tgt_val))" in s
    assert "'{add_src_val}'" not in s and "'{add_tgt_val}'" not in s
