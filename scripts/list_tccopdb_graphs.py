
import os
import psycopg2
from dotenv import load_dotenv

# .env 로드
load_dotenv()

# 접속 정보
host = os.getenv('DB_HOST', '49.50.128.28')
port = os.getenv('DB_PORT', '5333')
dbname = 'tccopdb'  # 명시적으로 tccopdb 지정
user = os.getenv('DB_USER', 'ccop')
password = os.getenv('DB_PASSWORD', 'Ccop@2025')

print(f"Connecting to {dbname} at {host}:{port} as {user}...")

try:
    conn = psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password
    )
    cur = conn.cursor()
    
    # 그래프(스키마) 목록 조회 쿼리 (시스템 스키마 제외)
    query = """
    SELECT nspname 
    FROM pg_namespace 
    WHERE nspname NOT IN ('pg_catalog','information_schema','public','ag_catalog','pg_toast') 
    AND nspname NOT LIKE 'pg_temp%' 
    AND nspname NOT LIKE 'pg_toast_temp%' 
    ORDER BY nspname;
    """
    
    cur.execute(query)
    graphs = [r[0] for r in cur.fetchall()]
    
    print(f"\n[Graphs in '{dbname}']")
    if not graphs:
        print("No graphs found.")
    else:
        for idx, g in enumerate(graphs):
            print(f"{idx+1}. {g}")
            
    conn.close()

except Exception as e:
    print(f"Error: {e}")
