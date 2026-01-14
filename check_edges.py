#!/usr/bin/env python3
"""
엣지 연결 확인
"""
import psycopg2

conn = psycopg2.connect(
    dbname="ccopdb",
    user="ccop",
    password="Ccop@2025",
    host="49.50.128.28",
    port="5333"
)
conn.autocommit = True
cur = conn.cursor()

graph_path = "demo_tst1"

print("=" * 80)
print(f"엣지 테이블 및 연결 확인")
print("=" * 80)

# 1. 엣지 테이블 목록
print("\n📋 엣지 테이블 목록:")
cur.execute(f"""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = '{graph_path}' 
      AND (table_name LIKE 'eg_%' OR table_name IN ('call', 'used_account', 'digital_trace'))
    ORDER BY table_name;
""")
edge_tables = [r[0] for r in cur.fetchall()]
for table in edge_tables:
    cur.execute(f'SELECT COUNT(*) FROM "{graph_path}"."{table}";')
    count = cur.fetchone()[0]
    print(f"  - {table}: {count}개")

# 2. vt_flnm 노드 하나 선택해서 엣지 확인
print(f"\n🔍 vt_flnm 노드의 엣지 연결 확인:")
cur.execute(f'SELECT id FROM "{graph_path}"."vt_flnm" LIMIT 1;')
sample_node = cur.fetchone()
if sample_node:
    node_id = sample_node[0]
    print(f"   샘플 노드 ID: {node_id}")
    
    for edge_table in edge_tables:
        cur.execute(f'''
            SELECT COUNT(*) 
            FROM "{graph_path}"."{edge_table}" 
            WHERE start = '{node_id}' OR "end" = '{node_id}'
        ''')
        edge_count = cur.fetchone()[0]
        if edge_count > 0:
            print(f"   ✅ {edge_table}: {edge_count}개 연결")
            
            # 샘플 엣지 정보
            cur.execute(f'''
                SELECT id, start, "end", properties 
                FROM "{graph_path}"."{edge_table}" 
                WHERE start = '{node_id}' OR "end" = '{node_id}'
                LIMIT 1
            ''')
            sample_edge = cur.fetchone()
            if sample_edge:
                print(f"      샘플: start={sample_edge[1]}, end={sample_edge[2]}")

conn.close()
print("\n" + "=" * 80)
