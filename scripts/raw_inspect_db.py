import psycopg2
import os
from dotenv import load_dotenv

def raw_inspect():
    load_dotenv()
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT'),
        dbname=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    cur = conn.cursor()
    graph_path = "tccop_graph_v6"
    
    try:
        cur.execute("SET search_path = ag_catalog, \"$user\", public;")
        cur.execute(f"SET graph_path = {graph_path};")
        
        print(f"--- '010-1111-2222' 전화번호 노드 직접 조회 ---")
        cur.execute("""
            MATCH (t:vt_telno)
            WHERE t.telno = '010-1111-2222'
            RETURN t
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"노드: {row[0]}")

        print(f"\n--- 임의의 vt_telno 노드 5개 조회 (속성 확인용) ---")
        cur.execute("""
            MATCH (t:vt_telno)
            RETURN t
            LIMIT 5
        """)
        rows = cur.fetchall()
        for row in rows:
            print(f"- {row[0]}")

        print(f"\n--- vt_call 노드와 관계 통계 ---")
        cur.execute("""
            MATCH ()-[r]->(n:vt_call)
            RETURN label(r), count(*)
        """)
        for row in cur.fetchall():
            print(f"관계: {row[0]} -> vt_call ({row[1]}건)")

        cur.execute("""
            MATCH (n:vt_call)
            RETURN n
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            print(f"샘플 vt_call 노드: {row[0]}")
        for row in cur.fetchall():
            print(f"- {row[0]}: {row[1]}건")

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    raw_inspect()
