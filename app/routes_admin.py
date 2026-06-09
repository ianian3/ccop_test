"""
관리자 페이지 라우트
API 키 관리 및 파트너 관리
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for, current_app
from functools import wraps
from app.models.api_key import APIKey, TIERS
from collections import defaultdict
from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import logging
import os

admin = Blueprint('admin', __name__, url_prefix='/admin')

logger = logging.getLogger(__name__)

# 로그인 실패 추적: {ip: [실패 시각, ...]}
_login_failures: dict = defaultdict(list)
_MAX_LOGIN_ATTEMPTS = 5    # 최대 실패 횟수
_LOCKOUT_SECONDS = 300     # 잠금 시간 (5분)


def _get_admin_password_hash():
    """
    환경변수 ADMIN_PASSWORD에서 관리자 비밀번호 해시를 생성.
    설정되지 않으면 기본값 사용 + 경고 로그 출력.
    """
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        logger.warning("⚠️  ADMIN_PASSWORD 환경변수가 설정되지 않았습니다. 기본 비밀번호가 사용됩니다. 프로덕션 환경에서는 반드시 설정하세요!")
        password = "admin123"  # fallback (개발 환경 전용)
    return hashlib.sha256(password.encode()).hexdigest()


def _is_ip_locked(ip: str) -> bool:
    """IP 잠금 여부 확인 (5분 내 5회 실패 시 잠금)"""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=_LOCKOUT_SECONDS)
    recent = [t for t in _login_failures[ip] if t > cutoff]
    _login_failures[ip] = recent
    return len(recent) >= _MAX_LOGIN_ATTEMPTS


def _record_login_failure(ip: str):
    _login_failures[ip].append(datetime.now(timezone.utc))


def require_admin(f):
    """관리자 인증 데코레이터 (세션 만료 포함)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin.login'))
        # 세션 만료 검사 (1시간)
        login_time = session.get('login_time')
        if login_time:
            elapsed = datetime.now(timezone.utc).timestamp() - login_time
            if elapsed > 3600:
                session.clear()
                return redirect(url_for('admin.login'))
        return f(*args, **kwargs)
    return decorated_function

@admin.route('/login', methods=['GET', 'POST'])
def login():
    """관리자 로그인 (Brute Force 방지)"""
    if request.method == 'POST':
        ip = request.remote_addr

        # IP 잠금 확인
        if _is_ip_locked(ip):
            logger.warning(f"관리자 로그인 잠금 상태 (IP: {ip})")
            return render_template('admin/login.html', error=f"로그인 시도가 너무 많습니다. {_LOCKOUT_SECONDS//60}분 후 재시도하세요.")

        password = request.form.get('password', '')
        password_hash = hashlib.sha256(password.encode()).hexdigest()

        # 타이밍 공격 방어를 위해 hmac.compare_digest 사용
        if hmac.compare_digest(password_hash, _get_admin_password_hash()):
            session['admin_logged_in'] = True
            session['login_time'] = datetime.now(timezone.utc).timestamp()
            session.permanent = True
            _login_failures.pop(ip, None)  # 성공 시 실패 기록 초기화
            logger.info(f"관리자 로그인 성공 (IP: {ip})")
            return redirect(url_for('admin.dashboard'))
        else:
            _record_login_failure(ip)
            remaining = _MAX_LOGIN_ATTEMPTS - len(_login_failures[ip])
            logger.warning(f"관리자 로그인 실패 (IP: {ip}, 남은 시도: {remaining})")
            return render_template('admin/login.html', error=f"잘못된 비밀번호입니다. (남은 시도: {max(remaining, 0)}회)")

    return render_template('admin/login.html')

@admin.route('/logout')
def logout():
    """관리자 로그아웃"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin.login'))

@admin.route('/dashboard')
@require_admin
def dashboard():
    """관리자 대시보드"""
    return render_template('admin/dashboard.html')

@admin.route('/api/partners/create', methods=['POST'])
@require_admin
def create_partner():
    """새 파트너 API 키 생성"""
    try:
        data = request.get_json()
        
        partner_name = data.get('partner_name')
        tier = data.get('tier', 'free')
        
        if not partner_name:
            return jsonify({"error": "partner_name is required"}), 400
        
        if tier not in TIERS:
            return jsonify({"error": f"Invalid tier. Must be one of: {list(TIERS.keys())}"}), 400
        
        # API 키 생성
        result = APIKey.create_partner_key(
            partner_name=partner_name,
            tier=tier,
            rate_limit=TIERS[tier]['rate_limit'],
            allowed_endpoints=TIERS[tier]['allowed_endpoints']
        )
        
        # 저장소에 추가
        from app.middleware.api_auth import API_KEYS_STORE, API_KEYS_PLAINTEXT, save_api_keys, save_plaintext_keys
        API_KEYS_STORE[result['key_hash']] = result['partner_data']
        
        # 평문 키 저장 (관리자가 나중에 볼 수 있도록)
        API_KEYS_PLAINTEXT[result['key_hash']] = result['api_key']
        
        # 파일 영속화
        save_api_keys()
        save_plaintext_keys()
        
        return jsonify({
            "status": "success",
            "api_key": result['api_key'],  # 평문 (단 한 번만 표시)
            "key_hash": result['key_hash'],
            "partner_data": result['partner_data']
        }), 201
        
    except Exception as e:
        logger.error(f"Admin API error: {e}")
        return jsonify({"error": "내부 서버 오류가 발생했습니다."}), 500

@admin.route('/api/partners/list', methods=['GET'])
@require_admin
def list_partners():
    """파트너 목록 조회"""
    try:
        from app.middleware.api_auth import API_KEYS_STORE, API_KEYS_PLAINTEXT
        
        partners = []
        for key_hash, data in API_KEYS_STORE.items():
            # 평문 키 가져오기 (있으면)
            plaintext_key = API_KEYS_PLAINTEXT.get(key_hash, None)
            
            partners.append({
                "key_hash": key_hash,  # 전체 해시 (삭제용)
                "key_hash_short": key_hash[:16] + "...",  # 짧은 해시 (표시용)
                "api_key": plaintext_key,  # 평문 키 (마스킹되어 표시)
                "partner_name": data['partner_name'],
                "tier": data['tier'],
                "rate_limit": data['rate_limit'],
                "created_at": data['created_at'],
                "is_active": data.get('is_active', True)
            })
        
        return jsonify({"partners": partners}), 200
        
    except Exception as e:
        logger.error(f"Admin API error: {e}")
        return jsonify({"error": "내부 서버 오류가 발생했습니다."}), 500

@admin.route('/api/partners/deactivate', methods=['POST'])
@require_admin
def deactivate_partner():
    """파트너 API 키 비활성화"""
    try:
        data = request.get_json()
        key_hash = data.get('key_hash')
        
        if not key_hash:
            return jsonify({"error": "key_hash is required"}), 400
        
        from app.middleware.api_auth import API_KEYS_STORE, save_api_keys
        
        if key_hash in API_KEYS_STORE:
            API_KEYS_STORE[key_hash]['is_active'] = False
            save_api_keys()
            return jsonify({"status": "success", "message": "Partner deactivated"}), 200
        else:
            return jsonify({"error": "Partner not found"}), 404
        
    except Exception as e:
        logger.error(f"Admin API error: {e}")
        return jsonify({"error": "내부 서버 오류가 발생했습니다."}), 500

@admin.route('/api/partners/delete', methods=['POST'])
@require_admin
def delete_partner():
    """파트너 완전 삭제"""
    try:
        data = request.get_json()
        key_hash = data.get('key_hash')
        
        if not key_hash:
            return jsonify({"error": "key_hash is required"}), 400
        
        from app.middleware.api_auth import API_KEYS_STORE, API_KEYS_PLAINTEXT, save_api_keys, save_plaintext_keys
        
        if key_hash in API_KEYS_STORE:
            partner_name = API_KEYS_STORE[key_hash]['partner_name']
            del API_KEYS_STORE[key_hash]
            API_KEYS_PLAINTEXT.pop(key_hash, None)
            save_api_keys()
            save_plaintext_keys()
            return jsonify({
                "status": "success", 
                "message": f"Partner {partner_name} deleted"
            }), 200
        else:
            return jsonify({"error": "Partner not found"}), 404
        
    except Exception as e:
        logger.error(f"Admin API error: {e}")
        return jsonify({"error": "내부 서버 오류가 발생했습니다."}), 500
