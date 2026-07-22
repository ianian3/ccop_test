from flask import Flask, request
from flask_cors import CORS
import logging
from logging.handlers import RotatingFileHandler
import os
import gzip
import io
import hmac
from config import Config

def create_app():
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(Config)

    # Enable CORS
    CORS(app, origins=Config.CORS_ORIGINS)

    # 선택적 Basic Auth — BASIC_AUTH_USER/PASS env 설정 시에만 활성 (공개 데모 보호용).
    # env 미설정 시 완전 무동작 (예: skai2_vm). 헬스체크는 모니터링/watchdog 위해 예외.
    _ba_user = os.getenv('BASIC_AUTH_USER')
    _ba_pass = os.getenv('BASIC_AUTH_PASS')
    if _ba_user and _ba_pass:
        from flask import Response

        @app.before_request
        def _require_basic_auth():
            if request.path == '/api/v1/health':
                return None
            auth = request.authorization
            if (auth and (auth.password is not None) and
                    hmac.compare_digest((auth.username or '').encode('utf-8'), _ba_user.encode('utf-8')) and
                    hmac.compare_digest((auth.password or '').encode('utf-8'), _ba_pass.encode('utf-8'))):
                return None
            return Response('Authentication required', 401,
                            {'WWW-Authenticate': 'Basic realm="CCOP"'})

    # Sprint 1 — gzip 응답 압축 (JSON/text 응답 -60~80% 네트워크)
    @app.after_request
    def _gzip_response(response):
        accept = request.headers.get('Accept-Encoding', '')
        if ('gzip' not in accept.lower() or
                response.status_code < 200 or response.status_code >= 300 or
                response.direct_passthrough or
                'Content-Encoding' in response.headers):
            return response
        try:
            data = response.get_data()
        except Exception:
            return response
        if len(data) < 1024:
            return response
        ctype = (response.content_type or '').lower()
        if not any(t in ctype for t in
                   ('application/json', 'text/', 'application/javascript', 'image/svg')):
            return response
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode='wb', compresslevel=5) as gz:
            gz.write(data)
        compressed = buf.getvalue()
        response.set_data(compressed)
        response.headers['Content-Encoding'] = 'gzip'
        response.headers['Content-Length'] = str(len(compressed))
        vary = response.headers.get('Vary')
        response.headers['Vary'] = f"{vary}, Accept-Encoding" if vary else 'Accept-Encoding'
        return response


    # Configure logging
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            # 로그 파일 무한 증가 방지: 20MB × 10개 로테이션 (~200MB 상한)
            RotatingFileHandler(Config.LOG_FILE, maxBytes=20 * 1024 * 1024,
                                backupCount=10, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    app.logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    app.logger.info('CCOP application starting up...')

    # 프로덕션인데 앱 레벨 인증(Basic Auth)이 꺼져 있으면 경고 (UI/데이터 API 무인증 노출)
    if os.getenv('FLASK_ENV') == 'production' and not (_ba_user and _ba_pass):
        app.logger.warning(
            '프로덕션 모드이나 BASIC_AUTH_USER/PASS 미설정 — UI/데이터 API가 무인증 노출됩니다. '
            '네트워크 경계로 접근을 통제하거나 Basic Auth 를 설정하세요.'
        )
    
    # API 키 파일 로드 (영속화)
    from app.middleware.api_auth import load_api_keys, load_plaintext_keys
    load_api_keys()
    load_plaintext_keys()
    
    # Security headers
    @app.after_request
    def add_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # 프론트 자산을 로컬 벤더링(app/static/vendor) 후 외부 CDN 호스트 제거.
        # ('unsafe-inline' 은 템플릿의 대량 인라인 JS/CSS 때문에 유지 — 별도 하드닝 과제)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "frame-ancestors 'none';"
        )
        if os.getenv('FLASK_ENV') == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # 라우트 등록
    from app.routes import bp
    app.register_blueprint(bp)
    
    # API v1 라우트 등록
    from app.routes_api import api_v1
    app.register_blueprint(api_v1)

    # 외부 LLM/시스템용 read-only 그래프 접근 API
    from app.routes_graph_read import graph_read_bp
    app.register_blueprint(graph_read_bp)

    # Admin 라우트 등록
    from app.routes_admin import admin
    app.register_blueprint(admin)

    return app