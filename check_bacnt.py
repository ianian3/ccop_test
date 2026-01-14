#!/usr/bin/env python3
"""
vt_bacnt 노드 확인
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

print("=" * 70)
print(f"vt_bacnt 노드 확인")
print("=" * 70)

# 1. vt_bacnt 테이블 존재 확인
print("\n📋 테이블 목록:")
cur.execute(f"""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = '{graph_path}'
    ORDER BY table_name;
""")
for table in cur.fetchall():
    print(f"  - {table[0]}")

# 2. vt_bacnt 테이블이 있는지 확인
try:
    cur.execute(f'SELECT COUNT(*) FROM "{graph_path}"."vt_bacnt";')
    count = cur.fetchone()[0]
    print(f"\n✅ vt_bacnt 테이블: {count}개 노드")
    
    if count > 0:
        print(f"\n🔍 샘플 노드 (최대 5개):")
        cur.execute(f'SELECT id, properties FROM "{graph_path}"."vt_bacnt" LIMIT 5;')
        for i, row in enumerate(cur.fetchall(), 1):
            print(f"  [{i}] ID: {row[0]}")
            print(f"      Props: {row[1]}")
except Exception as e:
    print(f"\n❌ vt_bacnt 테이블 없음: {e}")

# 3. vt_psn 테이블 확인
try:
    cur.execute(f'SELECT COUNT(*) FROM "{graph_path}"."vt_psn";')
    psn_count = cur.fetchone()[0]
    print(f"\n📊 vt_psn 테이블: {psn_count}개 노드")
except Exception as e:
    print(f"\n❌ vt_psn 테이블 없음: {e}")

conn.close()
print("\n" + "=" * 70)
