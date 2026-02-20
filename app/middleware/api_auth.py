"""
API 인증 미들웨어
파트너의 API 키를 검증하고 요청을 인증합니다.
"""
from functools import wraps
from flask import request, jsonify, current_app
import hashlib
import time
from datetime import datetime

# 임시 메모리 저장소 (프로덕션에서는 데이터베이스 사용)
API_KEYS_STORE = {
    # SHA-256 해시된 API 키 -> 파트너 정보
    # demo-key-12345 의 해시: 367fe8933ad8bba8f7ff02c047bcb5c00a4fff3ad6e82fef2bf4ee0c850d7c36
    "367fe8933ad8bba8f7ff02c047bcb5c00a4fff3ad6e82fef2bf4ee0c850d7c36": {
        "partner_name": "demo_partner",
        "tier": "free",
        "rate_limit": 1000,  # requests per hour
        "allowed_endpoints": ["text-to-cypher", "graph-query", "usage"],
        "created_at": "2026-01-15T00:00:00Z",
        "is_active": True
    }
}

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
