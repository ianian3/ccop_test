"""
API 인증 미들웨어
파트너의 API 키를 검증하고 요청을 인증합니다.
JSON 파일 기반 영속화를 지원합니다.
"""
from functools import wraps
from flask import request, jsonify, current_app, session
import hashlib
import json
import os
import logging
import fcntl
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)

# ============================================
# JSON 파일 영속화
# ============================================

# 기본 데이터 저장 경로
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
_API_KEYS_FILE = os.path.join(_DATA_DIR, 'api_keys.json')
_PLAINTEXT_KEYS_FILE = os.path.join(_DATA_DIR, 'api_keys_plaintext.json')

# 초기 시드 데이터 — 비워 둠(보안): 알려진 데모 키를 자동 생성하지 않는다.
# 초기 키는 배포 시 /admin 대시보드 또는 generate_api_key.py 로 수동 발급할 것.
_DEFAULT_STORE = {}


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
    """JSON 파일에 파일 락을 사용하여 안전하게 저장 (멀티프로세스 Race Condition 방지)"""
    _ensure_data_dir()
    lock_path = filepath + ".lock"
    try:
        with open(lock_path, 'w') as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                logger.info(f"데이터 저장 완료: {filepath}")
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
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
        # 첫 실행: 빈 저장소로 초기화 + 파일 생성 (데모 키 자동 시드 없음)
        API_KEYS_STORE.update(_DEFAULT_STORE)
        save_api_keys()
        logger.info("API 키 저장소 초기화 완료 (등록된 키 없음 — 수동 발급 필요)")


def save_api_keys():
    """API 키 저장소를 파일에 저장"""
    _save_json(_API_KEYS_FILE, API_KEYS_STORE)


def load_plaintext_keys():
    """평문 키 저장소를 파일에서 로드 (관리자 표시용)"""
    global API_KEYS_PLAINTEXT
    loaded = _load_json(_PLAINTEXT_KEYS_FILE)
    if loaded:
        API_KEYS_PLAINTEXT.update(loaded)


def _mask_api_key(api_key: str) -> str:
    """API 키를 마스킹하여 저장 (앞 4자 + **** + 뒤 4자)"""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return api_key[:4] + "*" * (len(api_key) - 8) + api_key[-4:]


def save_plaintext_keys():
    """API 키를 마스킹하여 파일에 저장 (평문 저장 금지)"""
    masked = {k: _mask_api_key(v) for k, v in API_KEYS_PLAINTEXT.items()}
    _save_json(_PLAINTEXT_KEYS_FILE, masked)


# ============================================
# 인메모리 저장소 (파일 로드 후 사용)
# ============================================

API_KEYS_STORE = {}
API_KEYS_PLAINTEXT = {}

# 인메모리 Rate Limiter: {(partner_name, minute_bucket): request_count}
_rate_limit_counters: dict = defaultdict(int)


def _check_rate_limit(partner_name: str, rate_limit) -> bool:
    """
    분당 요청 수 제한 확인.
    rate_limit 이 None 이면 무제한(enterprise 티어) — 카운트 없이 항상 허용.
    Returns: True(허용) / False(초과)
    """
    if rate_limit is None:
        return True  # 무제한 (None <= int 비교 TypeError 방지)
    minute_bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    key = (partner_name, minute_bucket)
    _rate_limit_counters[key] += 1
    return _rate_limit_counters[key] <= rate_limit


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

        # Rate Limit 검사
        rate_limit = partner_data.get('rate_limit', 60)
        if not _check_rate_limit(request.partner, rate_limit):
            current_app.logger.warning(f"Rate limit exceeded: {request.partner}")
            return jsonify({
                "error": "Rate limit exceeded",
                "message": f"최대 {rate_limit}회/분 요청을 초과했습니다."
            }), 429

        current_app.logger.info(f"API request from partner: {request.partner}")

        return f(*args, **kwargs)

    return decorated_function


def require_api_or_ui(f):
    """UI 세션(same-origin 브라우저) 또는 파트너 Bearer 키 중 하나면 통과.

    - UI: Flask 서명 세션의 'ui_authorized' 플래그(UI 페이지 렌더 시 설정, routes.py)를
      브라우저가 same-origin fetch 에 자동 첨부하는 세션 쿠키로 검증 → 헤더 불필요.
      (SameSite=Lax 라 외부 사이트의 교차출처 요청엔 쿠키가 실리지 않아 방어됨)
    - 파트너: 'Authorization: Bearer <key>' (require_api_key 와 동일 검증 경로)

    UI 가 호출하지만 무인증이던(또는 헤더 불일치로 깨지던) v1 엔드포인트에 적용:
    network/*, visual-style, edge-style, layout-presets, workflows(+execute),
    etl/analyze, gdb/detail-stats, pipeline/csv_to_v40_graph.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1) UI 세션 (same-origin 브라우저) — 하드코딩 데모키 없이 쿠키로 인증
        if session.get('ui_authorized'):
            request.partner = 'ui-session'
            request.partner_data = {'tier': 'ui', 'allowed_endpoints': ['*'], 'rate_limit': None}
            return f(*args, **kwargs)

        # 2) 파트너 Bearer 키
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            api_key = auth_header.replace('Bearer ', '').strip()
            partner_data = validate_api_key(api_key)
            if partner_data:
                request.partner = partner_data['partner_name']
                request.partner_data = partner_data
                rate_limit = partner_data.get('rate_limit', 60)
                if not _check_rate_limit(request.partner, rate_limit):
                    current_app.logger.warning(f"Rate limit exceeded: {request.partner}")
                    return jsonify({
                        "error": "Rate limit exceeded",
                        "message": f"최대 {rate_limit}회/분 요청을 초과했습니다."
                    }), 429
                return f(*args, **kwargs)

        return jsonify({
            "error": "Authentication required",
            "message": "UI 세션 또는 유효한 API 키(Authorization: Bearer)가 필요합니다."
        }), 401

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
