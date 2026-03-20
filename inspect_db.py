import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_host = os.environ.get("DB_HOST", "49.50.128.28")
db_port = os.environ.get("DB_PORT", "5333")
db_name = os.environ.get("DB_NAME", "tccopdb")
db_user = os.environ.get("DB_USER", "ccop")
db_pass = os.environ.get("DB_PASSWORD", "Ccop@2025")

try:
    conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_pass)
    cur = conn.cursor()
    
    # 1. Get all tables in the public schema
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    tables = cur.fetchall()
    
    print(f"=== Database '{db_name}' Analysis ===")
    print(f"Total Tables: {len(tables)}\n")
    
    # 2. For each table, get the count and column info
    for (table_name,) in tables:
        cur.execute(f"SELECT count(*) FROM {table_name};")
        count = cur.fetchone()[0]
        
        cur.execute(f"""
            SELECT column_name, data_type, character_maximum_length, is_nullable
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        
        print(f"Table: {table_name} (Rows: {count})")
        for col in columns:
            col_name, data_type, max_len, is_nullable = col
            opt_len = f"({max_len})" if max_len else ""
            print(f"  - {col_name:<20} {data_type}{opt_len:<10} (Nullable: {is_nullable})")
        print("-" * 50)
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error inspecting database: {e}")
