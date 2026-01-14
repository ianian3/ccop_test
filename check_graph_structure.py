#!/usr/bin/env python
# -*- coding: utf-8 -*-
import psycopg2

# 직접 DB 연결
conn = psycopg2.connect(
    host='49.50.128.28',
    port=5333,
    database='ccopdb',
    user='ccop',
    password='Ccop@2025',
    connect_timeout=3
)

cur = conn.cursor()
cur.execute("SET graph_path = demo_tst1")

# 1. 노드 개수
print("=== 노드 개수 ===")
cur.execute("MATCH (n:vt_flnm) RETURN count(*)")
print(f"vt_flnm: {cur.fetchone()[0]}개")

cur.execute("MATCH (n:vt_id) RETURN count(*)")
print(f"vt_id: {cur.fetchone()[0]}개")

# 2. 엣지 타입별 개수
print("\n=== 엣지 타입별 개수 ===")
cur.execute("MATCH ()-[r]->() RETURN type(r), count(*)")
for edge_type, count in cur.fetchall():
    print(f"{edge_type}: {count}개")

# 3. 연결 샘플 (접수번호 <-> ID)
print("\n=== 접수번호-ID 연결 샘플 ===")
cur.execute("""
    MATCH (f:vt_flnm)-[r]-(i:vt_id)
    RETURN f.flnm, type(r), i.id
    LIMIT 5
""")
samples = cur.fetchall()
if samples:
    for flnm, rel, id_val in samples:
        print(f"{flnm} -[{rel}]- {id_val}")
else:
    print("❌ 접수번호-ID 간 연결 없음!")

# 4. 고아 노드 확인
print("\n=== 고아 노드 (연결 없는 노드) ===")
cur.execute("MATCH (f:vt_flnm) WHERE NOT (f)-[]-() RETURN count(*)")
orphan_flnm = cur.fetchone()[0]
print(f"vt_flnm 고아: {orphan_flnm}개")

cur.execute("MATCH (i:vt_id) WHERE NOT (i)-[]-() RETURN count(*)")
orphan_id = cur.fetchone()[0]
print(f"vt_id 고아: {orphan_id}개")

# 5. Source/Target 방향 확인
print("\n=== 엣지 방향 확인 ===")
cur.execute("MATCH (f:vt_flnm)-[r]->(i:vt_id) RETURN count(*)")
flnm_to_id = cur.fetchone()[0]
print(f"vt_flnm -> vt_id: {flnm_to_id}개")

cur.execute("MATCH (i:vt_id)-[r]->(f:vt_flnm) RETURN count(*)")
id_to_flnm = cur.fetchone()[0]
print(f"vt_id -> vt_flnm: {id_to_flnm}개")

conn.close()
print("\n✅ 분석 완료")
