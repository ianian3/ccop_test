import os
from dotenv import load_dotenv

load_dotenv()

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
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_ENV", "development") != "production"

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