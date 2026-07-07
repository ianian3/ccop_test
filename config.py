import os
import secrets
from dotenv import load_dotenv

load_dotenv()


def _resolve_secret_key():
    """SECRET_KEY 를 안전하게 결정.

    - 환경변수에 있으면 그대로 사용.
    - 프로덕션(FLASK_ENV=production)인데 미설정이면 기동 실패(fail-closed).
    - 그 외(개발/테스트)에는 임시 랜덤 키 생성(재시작 시 세션 무효화).
    """
    secret = os.getenv("SECRET_KEY")
    if secret:
        return secret
    if os.getenv("FLASK_ENV") == "production":
        raise RuntimeError(
            "SECRET_KEY 환경변수가 설정되지 않았습니다. 프로덕션에서는 필수입니다. "
            "생성 예: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
    return secrets.token_hex(32)


class Config:
    # Database Configuration
    DB_CONFIG = {
        "dbname": os.getenv("DB_NAME", "ccopdb"),
        "user": os.getenv("DB_USER", "ccop"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": os.getenv("DB_PORT", "5432")
    }
    
    # OpenAI API
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    # Graph Path
    DEFAULT_GRAPH_PATH = os.getenv("DEFAULT_GRAPH_PATH", "tccop_graph_v6")

    # RDB 스키마 (표준화 테이블이 위치한 PostgreSQL 스키마)
    RDB_SCHEMA = os.getenv("RDB_SCHEMA", "test_ccop")
    
    # Flask Configuration
    SECRET_KEY = _resolve_secret_key()
    # DEBUG 는 기본 비활성(default-secure). 개발 시에만 FLASK_ENV=development 로 활성화.
    DEBUG = os.getenv("FLASK_ENV") == "development"

    # Session Security
    SESSION_COOKIE_SECURE = os.getenv("FLASK_ENV") == "production"  # HTTPS 전용 (프로덕션)
    SESSION_COOKIE_HTTPONLY = True   # JS 접근 차단
    SESSION_COOKIE_SAMESITE = "Lax"  # CSRF 방지
    PERMANENT_SESSION_LIFETIME = 3600  # 세션 만료: 1시간 (초)

    # Admin Authentication
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")  # 환경변수에서 관리자 비밀번호 로드

    # CORS Settings
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5002").split(",")
    
    # sLLM Configuration
    SLLM_ENDPOINT = os.getenv("SLLM_ENDPOINT")
    SLLM_MODEL_NAME = os.getenv("SLLM_MODEL_NAME", "gpt-4o")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")