import psycopg2
import json
from flask import current_app

def get_db_connection():
    """AgensGraph DB 연결 (네이티브 Cypher 지원)"""
    try:
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()
        return conn, cur
    except Exception as e:
        print(f"DB 접속 오류: {e}")
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
            cur.execute(f"SET graph_path = {graph_path};")
        
        cur.execute(query)
        
        if fetch:
            return cur.fetchall()
        return None
    except Exception as e:
        print(f"Query Error: {e}")
        return None
    finally:
        conn.close()