#!/usr/bin/env python3
"""
ETL 결과 검증 스크립트 - 노드와 엣지 상태 확인
"""
import psycopg2
import json

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
print("ETL 결과 검증")
print("=" * 70)

# 1. 노드 테이블 확인
print(f"\n📊 노드 테이블 (vt_psn) 상태:")
cur.execute(f'SELECT COUNT(*) FROM "{graph_path}"."vt_psn";')
node_count = cur.fetchone()[0]
print(f"  총 노드 수: {node_count}")

# 샘플 노드 3개 조회
print(f"\n🔍 샘플 노드 (처음 3개):")
cur.execute(f'SELECT id, properties FROM "{graph_path}"."vt_psn" LIMIT 3;')
for i, row in enumerate(cur.fetchall(), 1):
    print(f"\n  [{i}] Node ID: {row[0]}")
    props = row[1]
    if props:
        print(f"      Properties Type: {type(props)}")
        if isinstance(props, dict):
            print(f"      Properties: {json.dumps(props, indent=8, ensure_ascii=False)}")
        else:
            print(f"      Properties (raw): {props}")
    else:
        print(f"      ⚠️ Properties: None/Empty")

# 2. 엣지 테이블 확인
print(f"\n\n📊 엣지 테이블 목록:")
cur.execute(f"""
    SELECT table_name
    FROM information_schema.tables 
    WHERE table_schema = '{graph_path}' 
      AND (table_name LIKE 'eg_%' OR table_name IN ('call', 'used_account'))
    ORDER BY table_name;
""")
edge_table_names = [r[0] for r in cur.fetchall()]

if not edge_table_names:
    print("  ⚠️ 엣지 테이블이 없습니다!")
    edge_tables = []
else:
    edge_tables = []
    for table_name in edge_table_names:
        cur.execute(f'SELECT COUNT(*) FROM "{graph_path}"."{table_name}";')
        count = cur.fetchone()[0]
        edge_tables.append((table_name, count))
        print(f"  - {table_name}: {count}개 엣지")
        
        # 각 테이블의 샘플 데이터
        if count > 0:
            cur.execute(f'SELECT id, start, "end", properties FROM "{graph_path}"."{table_name}" LIMIT 2;')
            for edge in cur.fetchall():
                print(f"      Edge ID: {edge[0]}, Start: {edge[1]}, End: {edge[2]}")
                if edge[3]:
                    print(f"      Props: {edge[3]}")

# 3. 연결성 체크
print(f"\n\n🔗 연결성 검증:")
if node_count > 0:
    # 첫 번째 노드 가져오기
    cur.execute(f'SELECT id FROM "{graph_path}"."vt_psn" LIMIT 1;')
    sample_node = cur.fetchone()[0]
    print(f"  샘플 노드: {sample_node}")
    
    # 이 노드와 연결된 엣지 찾기
    total_connections = 0
    for table_name, _ in edge_tables:
        cur.execute(f"""
            SELECT COUNT(*) 
            FROM "{graph_path}"."{table_name}" 
            WHERE start = '{sample_node}' OR "end" = '{sample_node}'
        """)
        connections = cur.fetchone()[0]
        if connections > 0:
            print(f"    - {table_name}: {connections}개 연결")
            total_connections += connections
    
    if total_connections == 0:
        print(f"  ⚠️ 경고: 노드 {sample_node}에 연결된 엣지가 없습니다!")

# 4. Cypher 테스트
print(f"\n\n🧪 Cypher 쿼리 테스트:")
try:
    cur.execute(f"SET graph_path = {graph_path};")
    cur.execute("MATCH (v) RETURN count(v);")
    cypher_count = cur.fetchone()[0]
    print(f"  MATCH (v) RETURN count(v): {cypher_count}개")
    
    if cypher_count != node_count:
        print(f"  ⚠️ 경고: Cypher 결과({cypher_count})와 SQL 결과({node_count})가 다릅니다!")
except Exception as e:
    print(f"  ❌ Cypher 실행 실패: {e}")

conn.close()
print("\n" + "=" * 70)
