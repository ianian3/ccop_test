from flask import Flask, request
from flask_cors import CORS
import logging
import os
import gzip
import io
from config import Config

def create_app():
    app = Flask(__name__)

    # Load configuration
    app.config.from_object(Config)

    # Enable CORS
    CORS(app, origins=Config.CORS_ORIGINS)

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
            logging.FileHandler(Config.LOG_FILE),
            logging.StreamHandler()
        ]
    )
    
    app.logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    app.logger.info('CCOP application starting up...')
    
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
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdn.jsdelivr.net unpkg.com cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self' cdn.jsdelivr.net cdnjs.cloudflare.com; "
            "frame-ancestors 'none';"
        )
        if not Config.DEBUG:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    # 라우트 등록
    from app.routes import bp
    app.register_blueprint(bp)
    
    # API v1 라우트 등록
    from app.routes_api import api_v1
    app.register_blueprint(api_v1)
    
    # Admin 라우트 등록
    from app.routes_admin import admin
    app.register_blueprint(admin)

    return app