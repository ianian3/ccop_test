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
    DEFAULT_GRAPH_PATH = os.getenv("DEFAULT_GRAPH_PATH", "ccop_tst_graph3")
    
    # Flask Configuration
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_ENV", "development") != "production"
    
    # Admin Authentication
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")  # 환경변수에서 관리자 비밀번호 로드
    
    # CORS Settings
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    
    # sLLM Configuration
    SLLM_ENDPOINT = os.getenv("SLLM_ENDPOINT")
    SLLM_MODEL_NAME = os.getenv("SLLM_MODEL_NAME", "gpt-4o")

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "logs/app.log")