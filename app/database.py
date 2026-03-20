import psycopg2
import json
import re
import logging
from flask import current_app

logger = logging.getLogger(__name__)


def validate_graph_path(name):
    """
    그래프 경로명 화이트리스트 검증 (SQL Injection 방어)
    영문자, 숫자, 언더스코어만 허용합니다.
    """
    if not name or not isinstance(name, str):
        return False
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))


def safe_set_graph_path(cur, graph_path):
    """
    검증된 graph_path로 SET graph_path 실행 (SQL Injection 방어)
    
    Args:
        cur: DB 커서
        graph_path: 그래프 경로명 (영문자/숫자/언더스코어만 허용)
    
    Raises:
        ValueError: 유효하지 않은 graph_path
    """
    if not validate_graph_path(graph_path):
        raise ValueError(f"유효하지 않은 graph_path: '{graph_path}' (영문자, 숫자, 언더스코어만 허용)")
    cur.execute(f"SET graph_path = {graph_path};")


def get_db_connection():
    """AgensGraph DB 연결 (네이티브 Cypher 지원)"""
    try:
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()
        return conn, cur
    except Exception as e:
        logger.error(f"DB 접속 오류: {e}")
        return None, None

def safe_props(val):
    """JSON 파싱 안전장치"""
    if val is None: return {}
    if isinstance(val, dict): return val
    try:
        if isinstance(val, str) and not val.strip(): return {}
        return json.loads(val)
    except Exception:
        return {}

def execute_query(query, graph_path=None, fetch=True):
    """쿼리 실행을 단순화하는 헬퍼 함수"""
    conn, cur = get_db_connection()
    if not conn: return None
    
    try:
        if graph_path:
            safe_set_graph_path(cur, graph_path)
        
        cur.execute(query)
        
        if fetch:
            return cur.fetchall()
        return None
    except Exception as e:
        logger.error(f"Query Error: {e}")
        return None
    finally:
        conn.close()