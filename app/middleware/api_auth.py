"""
API 인증 미들웨어
파트너의 API 키를 검증하고 요청을 인증합니다.
JSON 파일 기반 영속화를 지원합니다.
"""
from functools import wraps
from flask import request, jsonify, current_app
import hashlib
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ============================================
# JSON 파일 영속화
# ============================================

# 기본 데이터 저장 경로
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
_API_KEYS_FILE = os.path.join(_DATA_DIR, 'api_keys.json')
_PLAINTEXT_KEYS_FILE = os.path.join(_DATA_DIR, 'api_keys_plaintext.json')

# 기본 데모 키 (초기 시드 데이터)
_DEFAULT_STORE = {
    # demo-key-12345 의 해시
    "367fe8933ad8bba8f7ff02c047bcb5c00a4fff3ad6e82fef2bf4ee0c850d7c36": {
        "partner_name": "demo_partner",
        "tier": "free",
        "rate_limit": 1000,
        "allowed_endpoints": ["text-to-cypher", "graph-query", "usage"],
        "created_at": "2026-01-15T00:00:00Z",
        "is_active": True
    }
}


def _ensure_data_dir():
    """data/ 디렉토리가 없으면 생성"""
    os.makedirs(_DATA_DIR, exist_ok=True)


def _load_json(filepath, default=None):
    """JSON 파일을 안전하게 로드"""
    if default is None:
        default = {}
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"JSON 파일 로드 실패 ({filepath}): {e}")
    return default


def _save_json(filepath, data):
    """JSON 파일에 안전하게 저장"""
    _ensure_data_dir()
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"데이터 저장 완료: {filepath}")
    except IOError as e:
        logger.error(f"JSON 파일 저장 실패 ({filepath}): {e}")


def load_api_keys():
    """
    API 키 저장소를 파일에서 로드.
    파일이 없으면 기본 데모 키로 초기화.
    """
    global API_KEYS_STORE
    loaded = _load_json(_API_KEYS_FILE)
    if loaded:
        API_KEYS_STORE.update(loaded)
        logger.info(f"API 키 {len(loaded)}개 로드 완료 ({_API_KEYS_FILE})")
    else:
        # 첫 실행: 기본 데이터로 초기화 + 파일 생성
        API_KEYS_STORE.update(_DEFAULT_STORE)
        save_api_keys()
        logger.info("API 키 초기 데이터 생성 완료")


def save_api_keys():
    """API 키 저장소를 파일에 저장"""
    _save_json(_API_KEYS_FILE, API_KEYS_STORE)


def load_plaintext_keys():
    """평문 키 저장소를 파일에서 로드 (관리자 표시용)"""
    global API_KEYS_PLAINTEXT
    loaded = _load_json(_PLAINTEXT_KEYS_FILE)
    if loaded:
        API_KEYS_PLAINTEXT.update(loaded)


def save_plaintext_keys():
    """평문 키 저장소를 파일에 저장"""
    _save_json(_PLAINTEXT_KEYS_FILE, API_KEYS_PLAINTEXT)


# ============================================
# 인메모리 저장소 (파일 로드 후 사용)
# ============================================

API_KEYS_STORE = {}
API_KEYS_PLAINTEXT = {}


# ============================================
# API 키 검증
# ============================================

def generate_api_key_hash(api_key: str) -> str:
    """API 키를 SHA-256으로 해싱"""
    return hashlib.sha256(api_key.encode()).hexdigest()

def validate_api_key(api_key: str) -> dict:
    """
    API 키 검증
    Returns: 파트너 정보 또는 None
    """
    if not api_key:
        return None
    
    key_hash = generate_api_key_hash(api_key)
    partner_data = API_KEYS_STORE.get(key_hash)
    
    if not partner_data:
        return None
    
    if not partner_data.get('is_active', False):
        return None
    
    return partner_data

def require_api_key(f):
    """
    API 키 인증 데코레이터
    
    사용법:
        @app.route('/api/v1/endpoint')
        @require_api_key
        def my_endpoint():
            partner = request.partner
            # ...
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Authorization 헤더에서 API 키 추출
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({
                "error": "Missing or invalid Authorization header",
                "message": "Use 'Authorization: Bearer YOUR_API_KEY'"
            }), 401
        
        api_key = auth_header.replace('Bearer ', '').strip()
        
        # API 키 검증
        partner_data = validate_api_key(api_key)
        
        if not partner_data:
            current_app.logger.warning(f"Invalid API key attempt: {api_key[:10]}...")
            return jsonify({
                "error": "Invalid API key",
                "message": "Please check your API key or contact support"
            }), 403
        
        # 요청 객체에 파트너 정보 추가
        request.partner = partner_data['partner_name']
        request.partner_data = partner_data
        
        current_app.logger.info(f"API request from partner: {request.partner}")
        
        return f(*args, **kwargs)
    
    return decorated_function

def check_endpoint_permission(endpoint: str) -> bool:
    """
    파트너가 특정 엔드포인트에 접근 권한이 있는지 확인
    """
    partner_data = request.partner_data
    allowed_endpoints = partner_data.get('allowed_endpoints', [])
    
    return endpoint in allowed_endpoints or '*' in allowed_endpoints

def require_endpoint_permission(endpoint: str):
    """
    특정 엔드포인트 권한 확인 데코레이터
    
    사용법:
        @app.route('/api/v1/premium-feature')
        @require_api_key
        @require_endpoint_permission('premium-feature')
        def premium_endpoint():
            # ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not check_endpoint_permission(endpoint):
                return jsonify({
                    "error": "Insufficient permissions",
                    "message": f"Your tier does not have access to {endpoint}"
                }), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator
