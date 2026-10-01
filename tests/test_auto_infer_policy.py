# tests/test_auto_infer_policy.py
"""
V4.9 (2026-10-01) CSV 관계 자동 추론 정책 — 같은 행에 함께 있다는 사실만으로 관계를 단정하던 결함.

- RelationshipInferencer: 인물 두 컬럼 → recruits(모집)·자기 루프, 계정 두 컬럼 → same_as,
  사건 CSV 의 인물 → 전부 witness_in(피의자·피해자 규칙이 (person, case) 키 충돌로 덮어써짐)
- KICSSchemaMapper(LLM 실패 fallback): IP 두 컬럼 → communicated_with, 'customer' 의 'to' → 도착 역할,
  SoT 밖 엣지명(accessed·sent_message·related_to)
- /api/v1/etl/infer-import: mapping 없이 호출하면 첫 추천 매핑으로 검토 없이 적재
DB·LLM 무관.
"""
import io

import pytest

from app.services.ontology_service import KICSCrimeDomainOntology as O
from app.services.relationship_inferencer import RelationshipInferencer as R
from app.services.schema_mapper import KICSSchemaMapper as M


def _infer(cols):
    return R._infer_relationships(R._infer_column_types_by_rules(cols, []))


def _edges(rels):
    return {(r["source_col"], r["target_col"], r["relation_type"]): r["policy"] for r in rels}


# ── SoT 정책 ────────────────────────────────────────────────────────

def test_policy_lists_are_sot_edges():
    for tier in ('allow', 'deny'):
        assert O.AUTO_INFER_POLICY[tier] <= set(O.RELATIONSHIPS), tier
    assert not (O.AUTO_INFER_POLICY['allow'] & O.AUTO_INFER_POLICY['deny'])


def test_deny_edges_excluded_from_rules():
    used = {v['type'] for v in O.get_relationship_rules().values()}
    assert not (used & O.AUTO_INFER_POLICY['deny'])
    assert O.infer_policy('accessed') == 'deny'          # SoT 밖 이름
    assert O.infer_policy('has_account') == 'suggest'


@pytest.mark.parametrize('col,expected', [
    ('customer_ip', None), ('photo', None), ('src_ip', 'source'), ('dst_ip', 'target'),
    ('출금계좌', 'source'), ('입금계좌', 'target'), ('발신번호', 'source'), ('수신번호', 'target'),
])
def test_column_direction_token_based(col, expected):
    assert O.column_direction(col) == expected


def test_short_pattern_matches_whole_word_only():
    assert not O.pattern_in_column('ip', 'zip_code')
    assert not O.pattern_in_column('to', 'photo')
    assert O.pattern_in_column('ip', '접속IP')
    assert O.pattern_in_column('ip', 'src_ip')


# ── RelationshipInferencer ─────────────────────────────────────────

def test_two_person_columns_no_recruits_no_self_loop():
    rels = _infer(['이름', '성명'])
    assert all(r['relation_type'] != 'recruits' for r in rels)
    assert all(r['source_col'] != r['target_col'] for r in rels)


def test_two_id_columns_no_same_as():
    assert all(r['relation_type'] != 'same_as' for r in _infer(['user_id', 'login_id']))


def test_transfer_direction_allowed():
    e = _edges(_infer(['출금계좌', '입금계좌', '거래금액']))
    assert e == {('출금계좌', '입금계좌', 'transferred_to'): 'allow'}


def test_call_record_contacted():
    assert _edges(_infer(['발신번호', '수신번호'])) == {('발신번호', '수신번호', 'contacted'): 'allow'}


def test_role_edges_from_column_names():
    rels = _infer(['사건번호', '피의자명', '피해자', '이름'])
    e = _edges(rels)
    assert e[('피의자명', '사건번호', 'suspect_in')] == 'allow'
    assert e[('피해자', '사건번호', 'victim_in')] == 'allow'
    assert e[('이름', '사건번호', 'witness_in')] == 'suggest'
    unknown = [r for r in rels if r['relation_type'] == 'witness_in'][0]
    assert unknown['edge_props'] == {'role': 'unknown'} and unknown['requires_review']


def test_person_object_is_suggestion_and_allow_first():
    rels = _infer(['사건번호', '이름', '계좌번호'])
    assert rels[0]['policy'] == 'allow'                       # eg_used_account 가 앞
    assert _edges(rels)[('이름', '계좌번호', 'has_account')] == 'suggest'


# ── KICSSchemaMapper fallback / LLM 후처리 ────────────────────────

def _fallback(cols):
    return M._fallback_mapping(cols, [])['mapping']['relationships']


def test_mapper_ip_pair_no_communicated_with():
    assert _fallback(['login_ip', 'customer_ip']) == []
    assert _fallback(['src_ip', 'dst_ip']) == []


def test_mapper_transfer_and_call():
    assert [(r['from_col'], r['to_col'], r['type']) for r in _fallback(['출금계좌', '입금계좌'])] == \
        [('출금계좌', '입금계좌', 'transferred_to')]
    assert [(r['type'], r['policy']) for r in _fallback(['발신번호', '수신번호'])] == [('contacted', 'allow')]


def test_mapper_site_ip_stored_site_to_ip():
    rels = _fallback(['site_url', 'server_ip'])
    assert [(r['from_col'], r['to_col'], r['type']) for r in rels] == [('site_url', 'server_ip', 'resolves_to')]


def test_mapper_llm_result_drops_deny_and_non_sot():
    out = M._post_process({'relationships': [
        {'type': 'recruits', 'from_col': 'a', 'to_col': 'b'},
        {'type': 'accessed', 'from_col': 'a', 'to_col': 'b'},
        {'type': 'transferred_to', 'from_col': 'a', 'to_col': 'b'}]}, ['a', 'b'])
    assert [r['type'] for r in out['relationships']] == ['transferred_to']


# ── infer-import: 검토 없는 자동 적재 금지 ───────────────────────

def test_infer_import_without_mapping_returns_suggestions(client):
    with client.session_transaction() as sess:
        sess['ui_authorized'] = True                         # UI 세션 인증 (require_api_or_ui)
    csv = "사건번호,계좌번호\nC-1,110-123\n".encode('utf-8')
    r = client.post('/api/v1/etl/infer-import',
                    data={'file': (io.BytesIO(csv), 't.csv')}, content_type='multipart/form-data')
    assert r.status_code == 400
    body = r.get_json()
    assert body['error'] == 'mapping_required'
    assert body['suggested_mappings'] and body['suggested_mappings'][0]['policy'] == 'allow'
