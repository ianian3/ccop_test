#!/usr/bin/env python3
"""
확장 기능 디버깅 - 특정 노드의 엣지 확인
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
node_id = "3.46"  # 사용자가 확장하려는 노드

print("=" * 60)
print(f"노드 {node_id} 확장 디버깅")
print("=" * 60)

# 1. 노드 정보 확인
print(f"\n📌 노드 정보:")
cur.execute(f'SELECT id, properties FROM "{graph_path}"."vt_psn" WHERE id = \'{node_id}\';')
node = cur.fetchone()
if node:
    print(f"  ID: {node[0]}")
    print(f"  Props: {node[1]}")
else:
    print(f"  ⚠️ 노드를 찾을 수 없음!")

# 2. 모든 엣지 테이블 확인
print(f"\n📋 엣지 테이블 목록:")
cur.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{graph_path}' AND table_name LIKE 'eg_%' OR table_name IN ('call', 'used_account');")
edge_tables = [r[0] for r in cur.fetchall()]
for t in edge_tables:
    print(f"  - {t}")

# 3. 각 엣지 테이블에서 해당 노드 연결 확인
print(f"\n🔗 노드 {node_id}와 연결된 엣지:")
for table in edge_tables:
    try:
        query = f"""
        SELECT COUNT(*) 
        FROM "{graph_path}"."{table}" 
        WHERE start = '{node_id}' OR "end" = '{node_id}'
        """
        cur.execute(query)
        count = cur.fetchone()[0]
        if count > 0:
            print(f"\n  ✓ {table}: {count}개 엣지 발견")
            
            # 샘플 데이터 조회
            sample_query = f"""
            SELECT id, start, "end", properties 
            FROM "{graph_path}"."{table}" 
            WHERE start = '{node_id}' OR "end" = '{node_id}'
            LIMIT 3
            """
            cur.execute(sample_query)
            for row in cur.fetchall():
                print(f"    - Edge ID: {row[0]}, Start: {row[1]}, End: {row[2]}")
                print(f"      Props: {row[3]}")
    except Exception as e:
        print(f"  ✗ {table}: 에러 - {e}")

conn.close()
print("\n" + "=" * 60)
