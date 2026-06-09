import psycopg2
import psycopg2.pool
import json
import re
import logging
from flask import current_app

logger = logging.getLogger(__name__)

# 커넥션 풀 싱글톤
_connection_pool: psycopg2.pool.SimpleConnectionPool = None


def get_connection_pool() -> psycopg2.pool.SimpleConnectionPool:
    """앱 설정 기반 커넥션 풀 싱글톤 반환 (최소 2, 최대 10 연결)"""
    global _connection_pool
    if _connection_pool is None or _connection_pool.closed:
        db_config = current_app.config['DB_CONFIG']
        _connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=2,
            maxconn=10,
            **db_config
        )
        logger.info("DB 커넥션 풀 초기화 완료 (min=2, max=10)")
    return _connection_pool


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
    """커넥션 풀에서 연결 획득. 사용 후 반드시 release_db_connection() 호출 필요."""
    try:
        pool = get_connection_pool()
        conn = pool.getconn()
        conn.autocommit = True
        cur = conn.cursor()
        return conn, cur
    except Exception as e:
        logger.error(f"DB 접속 오류: {e}")
        return None, None


def release_db_connection(conn):
    """커넥션을 풀에 반환"""
    if conn is None:
        return
    try:
        pool = get_connection_pool()
        pool.putconn(conn)
    except Exception as e:
        logger.error(f"DB 커넥션 반환 오류: {e}")

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
    if not conn:
        return None
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
        release_db_connection(conn)