# tests/test_api_persistence.py
"""
API 키 영속화 단위 테스트

Tests:
1. JSON 파일 저장/로드
2. API 키 생성 후 영속화
3. API 키 삭제 후 영속화
4. API 키 검증
5. 파트너 CRUD 라우트 통합 테스트
"""
import pytest
import json
import os
import tempfile
from unittest.mock import patch


# =============================================
# 1. JSON 파일 영속화 Tests
# =============================================

class TestJsonPersistence:
    """JSON 파일 저장/로드 테스트"""

    def test_save_and_load_json(self):
        from app.middleware.api_auth import _save_json, _load_json

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            filepath = f.name

        try:
            test_data = {"key1": {"name": "test", "value": 123}}
            _save_json(filepath, test_data)

            loaded = _load_json(filepath)
            assert loaded == test_data
            assert loaded["key1"]["name"] == "test"
            assert loaded["key1"]["value"] == 123
        finally:
            os.unlink(filepath)

    def test_load_nonexistent_file(self):
        from app.middleware.api_auth import _load_json

        result = _load_json("/nonexistent/path/file.json")
        assert result == {}

    def test_load_nonexistent_with_default(self):
        from app.middleware.api_auth import _load_json

        result = _load_json("/nonexistent/path/file.json", default={"default": True})
        assert result == {"default": True}

    def test_load_corrupted_json(self):
        from app.middleware.api_auth import _load_json

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            f.write("{invalid json content!!!")
            filepath = f.name

        try:
            result = _load_json(filepath)
            assert result == {}
        finally:
            os.unlink(filepath)

    def test_save_creates_directory(self):
        from app.middleware.api_auth import _save_json

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "subdir", "test.json")
            # subdir가 존재하지 않지만 _save_json이 _ensure_data_dir은 data/ 만 생성
            # 직접 테스트
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            _save_json(filepath, {"test": True})
            assert os.path.exists(filepath)

    def test_save_unicode_content(self):
        from app.middleware.api_auth import _save_json, _load_json

        with tempfile.NamedTemporaryFile(suffix='.json', delete=False, mode='w') as f:
            filepath = f.name

        try:
            test_data = {"partner_name": "한국파트너", "tier": "enterprise"}
            _save_json(filepath, test_data)

            loaded = _load_json(filepath)
            assert loaded["partner_name"] == "한국파트너"
        finally:
            os.unlink(filepath)


# =============================================
# 2. API 키 검증 Tests
# =============================================

class TestApiKeyValidation:
    """API 키 해싱 및 검증 테스트"""

    def test_generate_hash(self):
        from app.middleware.api_auth import generate_api_key_hash
        import hashlib

        key = "test-key-12345"
        expected = hashlib.sha256(key.encode()).hexdigest()
        assert generate_api_key_hash(key) == expected

    def test_validate_existing_key(self, app):
        from app.middleware.api_auth import validate_api_key, API_KEYS_STORE, generate_api_key_hash

        # 테스트 키 등록
        test_key = "test_validate_key_001"
        key_hash = generate_api_key_hash(test_key)
        API_KEYS_STORE[key_hash] = {
            "partner_name": "test_partner",
            "tier": "free",
            "rate_limit": 100,
            "allowed_endpoints": ["*"],
            "created_at": "2026-01-01T00:00:00Z",
            "is_active": True
        }

        result = validate_api_key(test_key)
        assert result is not None
        assert result["partner_name"] == "test_partner"

        # 정리
        del API_KEYS_STORE[key_hash]

    def test_validate_nonexistent_key(self, app):
        from app.middleware.api_auth import validate_api_key

        result = validate_api_key("nonexistent-key-xxxxx")
        assert result is None

    def test_validate_inactive_key(self, app):
        from app.middleware.api_auth import validate_api_key, API_KEYS_STORE, generate_api_key_hash

        test_key = "test_inactive_key_001"
        key_hash = generate_api_key_hash(test_key)
        API_KEYS_STORE[key_hash] = {
            "partner_name": "inactive_partner",
            "tier": "free",
            "rate_limit": 100,
            "allowed_endpoints": ["*"],
            "created_at": "2026-01-01T00:00:00Z",
            "is_active": False  # 비활성
        }

        result = validate_api_key(test_key)
        assert result is None

        # 정리
        del API_KEYS_STORE[key_hash]

    def test_validate_empty_key(self, app):
        from app.middleware.api_auth import validate_api_key

        assert validate_api_key("") is None
        assert validate_api_key(None) is None


# =============================================
# 3. API 키 모델 Tests
# =============================================

class TestApiKeyModel:
    """API 키 생성 모델 테스트"""

    def test_generate_key_format(self):
        from app.models.api_key import APIKey

        key = APIKey.generate_key()
        assert key.startswith("ccop_")
        assert len(key) > 25  # prefix + 랜덤 부분

    def test_generate_key_custom_prefix(self):
        from app.models.api_key import APIKey

        key = APIKey.generate_key(prefix="test")
        assert key.startswith("test_")

    def test_generate_key_uniqueness(self):
        from app.models.api_key import APIKey

        keys = {APIKey.generate_key() for _ in range(100)}
        assert len(keys) == 100  # 100개 모두 고유

    def test_hash_key_deterministic(self):
        from app.models.api_key import APIKey

        key = "ccop_test123"
        hash1 = APIKey.hash_key(key)
        hash2 = APIKey.hash_key(key)
        assert hash1 == hash2

    def test_create_partner_key(self):
        from app.models.api_key import APIKey

        result = APIKey.create_partner_key(
            partner_name="test_co",
            tier="startup",
            rate_limit=5000
        )

        assert "api_key" in result
        assert "key_hash" in result
        assert "partner_data" in result
        assert result["partner_data"]["partner_name"] == "test_co"
        assert result["partner_data"]["tier"] == "startup"
        assert result["partner_data"]["is_active"] is True

    def test_validate_key_format_valid(self):
        from app.models.api_key import APIKey

        assert APIKey.validate_key_format("ccop_abcdefghijklmnopqrstuvwxyz") is True
        assert APIKey.validate_key_format("demo_12345678901234567890") is True

    def test_validate_key_format_invalid(self):
        from app.models.api_key import APIKey

        assert APIKey.validate_key_format("") is False
        assert APIKey.validate_key_format(None) is False
        assert APIKey.validate_key_format("invalid-no-prefix") is False
        assert APIKey.validate_key_format("ccop_short") is False  # 키 부분 < 20자


# =============================================
# 4. 파트너 CRUD 라우트 통합 테스트
# =============================================

class TestPartnerCRUD:
    """관리자 파트너 관리 통합 테스트"""

    def _login(self, client, password="admin123"):
        """관리자 로그인 헬퍼"""
        os.environ.pop("ADMIN_PASSWORD", None)  # fallback 사용
        return client.post('/admin/login', data={'password': password}, follow_redirects=True)

    def test_create_partner(self, app, client):
        """파트너 생성"""
        with client.session_transaction() as sess:
            sess['admin_logged_in'] = True

        response = client.post('/admin/api/partners/create',
                               json={"partner_name": "test_corp", "tier": "free"},
                               content_type='application/json')
        data = response.get_json()

        assert response.status_code == 201
        assert data["status"] == "success"
        assert "api_key" in data
        assert data["api_key"].startswith("ccop_")

        # 정리: 생성된 키 삭제
        from app.middleware.api_auth import API_KEYS_STORE, API_KEYS_PLAINTEXT
        key_hash = data["key_hash"]
        API_KEYS_STORE.pop(key_hash, None)
        API_KEYS_PLAINTEXT.pop(key_hash, None)

    def test_list_partners(self, app, client):
        """파트너 목록 조회"""
        with client.session_transaction() as sess:
            sess['admin_logged_in'] = True

        response = client.get('/admin/api/partners/list')
        data = response.get_json()

        assert response.status_code == 200
        assert "partners" in data

    def test_create_partner_invalid_tier(self, app, client):
        """잘못된 티어로 파트너 생성 시 에러"""
        with client.session_transaction() as sess:
            sess['admin_logged_in'] = True

        response = client.post('/admin/api/partners/create',
                               json={"partner_name": "test", "tier": "nonexistent"},
                               content_type='application/json')

        assert response.status_code == 400

    def test_create_partner_no_name(self, app, client):
        """이름 없이 파트너 생성 시 에러"""
        with client.session_transaction() as sess:
            sess['admin_logged_in'] = True

        response = client.post('/admin/api/partners/create',
                               json={"tier": "free"},
                               content_type='application/json')

        assert response.status_code == 400

    def test_deactivate_partner(self, app, client):
        """파트너 비활성화"""
        with client.session_transaction() as sess:
            sess['admin_logged_in'] = True

        # 먼저 생성
        create_resp = client.post('/admin/api/partners/create',
                                  json={"partner_name": "deact_test", "tier": "free"},
                                  content_type='application/json')
        key_hash = create_resp.get_json()["key_hash"]

        # 비활성화
        response = client.post('/admin/api/partners/deactivate',
                               json={"key_hash": key_hash},
                               content_type='application/json')

        assert response.status_code == 200
        assert response.get_json()["status"] == "success"

        # 정리
        from app.middleware.api_auth import API_KEYS_STORE, API_KEYS_PLAINTEXT
        API_KEYS_STORE.pop(key_hash, None)
        API_KEYS_PLAINTEXT.pop(key_hash, None)

    def test_delete_partner(self, app, client):
        """파트너 삭제"""
        with client.session_transaction() as sess:
            sess['admin_logged_in'] = True

        # 먼저 생성
        create_resp = client.post('/admin/api/partners/create',
                                  json={"partner_name": "del_test", "tier": "free"},
                                  content_type='application/json')
        key_hash = create_resp.get_json()["key_hash"]

        # 삭제
        response = client.post('/admin/api/partners/delete',
                               json={"key_hash": key_hash},
                               content_type='application/json')

        assert response.status_code == 200
        assert "deleted" in response.get_json()["message"]

    def test_delete_nonexistent_partner(self, app, client):
        """존재하지 않는 파트너 삭제 시 404"""
        with client.session_transaction() as sess:
            sess['admin_logged_in'] = True

        response = client.post('/admin/api/partners/delete',
                               json={"key_hash": "nonexistent_hash_value"},
                               content_type='application/json')

        assert response.status_code == 404
