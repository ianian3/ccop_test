"""RDB 적재 식별자 정규화 단위 테스트 — 계좌/전화 파편화 방지 (P1 정확성).

norm_account/norm_telno는 L2 표준화 단일 지점. 대시·공백 유무로 동일 실체가
별개 노드로 분기되는 것을 막아 그래프 정확성을 보장한다.
"""
from app.services.rdb_service import norm_account, norm_telno


class TestNormAccount:
    def test_dash_removed(self):
        assert norm_account('110-2222-3333') == '11022223333'

    def test_dash_vs_plain_unified(self):
        # 같은 계좌를 대시 있게/없게 표기해도 동일 키 → 노드 통합
        assert norm_account('352-1204-075933') == norm_account('3521204075933')

    def test_whitespace_removed(self):
        assert norm_account(' 123 456 789 ') == '123456789'

    def test_md5_preserved(self):
        h = '5d41402abc4b2a76b9719d911017c592'
        assert norm_account(h) == h                      # OSINT 해시 식별자 원형 유지

    def test_sha256_preserved(self):
        h = 'a' * 64
        assert norm_account(h) == h

    def test_uppercase_hash_lowered(self):
        assert norm_account('5D41402ABC4B2A76B9719D911017C592') == '5d41402abc4b2a76b9719d911017c592'

    def test_empty_and_none(self):
        assert norm_account('') == ''
        assert norm_account(None) == ''


class TestNormTelno:
    def test_hyphen_removed(self):
        assert norm_telno('010-1234-5678') == '01012345678'

    def test_leading_zero_preserved(self):
        assert norm_telno('01012345678') == '01012345678'

    def test_dash_vs_plain_unified(self):
        assert norm_telno('010-1234-5678') == norm_telno('01012345678')

    def test_empty_and_none(self):
        assert norm_telno('') == ''
        assert norm_telno(None) == ''
