#!/usr/bin/env python3
"""
현재 노드 정보 조회
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

print("=" * 80)
print(f"📊 [{graph_path}] 그래프 현재 노드 현황")
print("=" * 80)

# 1. 전체 노드 수
cur.execute(f'SELECT COUNT(*) FROM "{graph_path}"."vt_psn";')
total = cur.fetchone()[0]
print(f"\n📈 전체 노드 수: {total}개\n")

if total == 0:
    print("⚠️ 노드가 없습니다. CSV를 업로드하세요.")
    conn.close()
    exit()

# 2. 노드 샘플 (최대 10개)
print("🔍 노드 샘플 (최대 10개):\n")
cur.execute(f'SELECT id, properties FROM "{graph_path}"."vt_psn" LIMIT 10;')

for i, row in enumerate(cur.fetchall(), 1):
    node_id = row[0]
    props = row[1] if isinstance(row[1], dict) else {}
    
    # 노드 타입 결정 (간단 버전)
    node_type = "🌐 Site" if 'site' in props else \
                "💰 Account" if 'actno' in props or 'bank' in props else \
                "📱 Phone" if 'telno' in props and 'flnm' not in props else \
                "👤 Person"
    
    print(f"  [{i}] ID: {node_id}")
    print(f"      타입: {node_type}")
    print(f"      속성: {json.dumps(props, ensure_ascii=False, indent=10)}")
    print()

# 3. 속성별 노드 분류
print("\n" + "=" * 80)
print("📋 속성별 노드 분류:")
print("=" * 80 + "\n")

# site 속성
cur.execute(f"SELECT COUNT(*) FROM \"{graph_path}\".\"vt_psn\" WHERE properties::text LIKE '%site%';")
site_count = cur.fetchone()[0]
print(f"  🌐 Site 노드: {site_count}개")

# actno 속성
cur.execute(f"SELECT COUNT(*) FROM \"{graph_path}\".\"vt_psn\" WHERE properties ? 'actno';")
account_count = cur.fetchone()[0]
print(f"  💰 Account 노드: {account_count}개")

# flnm 속성
cur.execute(f"SELECT COUNT(*) FROM \"{graph_path}\".\"vt_psn\" WHERE properties ? 'flnm';")
person_count = cur.fetchone()[0]
print(f"  👤 Person 노드: {person_count}개")

# telno 속성
cur.execute(f"SELECT COUNT(*) FROM \"{graph_path}\".\"vt_psn\" WHERE properties ? 'telno';")
phone_count = cur.fetchone()[0]
print(f"  📱 Phone 노드: {phone_count}개")

# 4. 엣지 정보
print("\n" + "=" * 80)
print("🔗 엣지 현황:")
print("=" * 80 + "\n")

cur.execute(f"""
    SELECT table_name
    FROM information_schema.tables 
    WHERE table_schema = '{graph_path}' 
      AND (table_name LIKE 'eg_%' OR table_name IN ('call', 'used_account'))
""")

for table in cur.fetchall():
    table_name = table[0]
    cur.execute(f'SELECT COUNT(*) FROM "{graph_path}"."{table_name}";')
    count = cur.fetchone()[0]
    print(f"  - {table_name}: {count}개")

conn.close()
print("\n" + "=" * 80)
