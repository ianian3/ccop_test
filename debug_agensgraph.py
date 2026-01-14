#!/usr/bin/env python3
"""
AgensGraph 데이터 검증 스크립트
실제로 데이터가 어떻게 저장되어 있는지 확인
"""
import psycopg2
import json

# DB 연결
conn = psycopg2.connect(
    dbname="ccopdb",
    user="ccop",
    password="Ccop@2025",
    host="49.50.128.28",
    port="5333"
)
conn.autocommit = True
cur = conn.cursor()

print("=" * 60)
print("AgensGraph 데이터 검증")
print("=" * 60)

# 1. 그래프 경로 설정
graph_path = "demo_tst1"
cur.execute(f"SET graph_path = {graph_path};")
print(f"✓ Graph path set to: {graph_path}\n")

# 2. 스키마 확인 (테이블 목록)
print("📋 Schema (Tables in graph):")
cur.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{graph_path}' ORDER BY table_name;")
tables = cur.fetchall()
for t in tables:
    print(f"  - {t[0]}")
print()

# 3. 노드 수 확인 (직접 SQL)
if tables:
    node_table = [t[0] for t in tables if not t[0].startswith('eg_')][0] if any(not t[0].startswith('eg_') for t in tables) else None
    if node_table:
        print(f"📊 Node count in '{node_table}':")
        cur.execute(f'SELECT COUNT(*) FROM "{graph_path}"."{node_table}";')
        count = cur.fetchone()[0]
        print(f"  Total nodes: {count}\n")
        
        # 4. 샘플 데이터 조회 (SQL)
        print(f"🔍 Sample data (first 3 rows via SQL):")
        cur.execute(f'SELECT id, properties FROM "{graph_path}"."{node_table}" LIMIT 3;')
        for row in cur.fetchall():
            print(f"  ID: {row[0]}")
            print(f"  Properties: {row[1]}")
            print()

# 5. Cypher 쿼리 테스트
print("🧪 Testing Cypher queries:\n")

# Test 1: 기본 MATCH
print("Test 1: MATCH (v) RETURN v LIMIT 1")
try:
    cur.execute("MATCH (v) RETURN v LIMIT 1")
    result = cur.fetchall()
    print(f"  ✓ Success: {len(result)} rows")
    if result:
        print(f"  Result: {result[0]}")
except Exception as e:
    print(f"  ✗ Error: {e}")
print()

# Test 2: MATCH with id()
print("Test 2: MATCH (v) RETURN id(v), labels(v), properties(v) LIMIT 1")
try:
    cur.execute("MATCH (v) RETURN id(v), labels(v), properties(v) LIMIT 1")
    result = cur.fetchall()
    print(f"  ✓ Success: {len(result)} rows")
    if result:
        print(f"  ID: {result[0][0]} (type: {type(result[0][0])})")
        print(f"  Labels: {result[0][1]} (type: {type(result[0][1])})")
        print(f"  Props: {result[0][2]} (type: {type(result[0][2])})")
except Exception as e:
    print(f"  ✗ Error: {e}")
print()

# Test 3: Property access
print("Test 3: MATCH (v) WHERE v.flnm =~ '.*' RETURN v LIMIT 1")
try:
    cur.execute("MATCH (v) WHERE v.flnm =~ '.*' RETURN v LIMIT 1")
    result = cur.fetchall()
    print(f"  ✓ Success: {len(result)} rows")
except Exception as e:
    print(f"  ✗ Error: {e}")
print()

conn.close()
print("=" * 60)
