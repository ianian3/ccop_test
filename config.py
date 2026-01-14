import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    DB_CONFIG = {
        "dbname": os.getenv("DB_NAME", "ccopdb"),
        "user": os.getenv("DB_USER", "ccop"),
        "password": os.getenv("DB_PASSWORD"),
        "host": os.getenv("DB_HOST", "127.0.0.1"),
        "port": os.getenv("DB_PORT", "5432")
    }
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    DEFAULT_GRAPH_PATH = "ccop_tst_graph3"