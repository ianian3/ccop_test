#!/usr/bin/env python3
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

print('=' * 80)
print('최종 중복 검증')
print('=' * 80)

# vt_flnm 중복 확인
cur.execute(f'''
    SELECT COUNT(*) as total,
           COUNT(DISTINCT properties->>'flnm') as unique_vals
    FROM "{graph_path}"."vt_flnm"
''')
result = cur.fetchone()
total, unique = result[0], result[1]
dup = total - unique

print(f'\n📋 vt_flnm:')
print(f'   총 노드: {total}개')
print(f'   고유 값: {unique}개')
if dup == 0:
    print(f'   ✅ 중복 없음!')
else:
    print(f'   ❌ 중복: {dup}개')
    
    # 중복 목록
    cur.execute(f'''
        SELECT properties->>'flnm', COUNT(*) 
        FROM "{graph_path}"."vt_flnm"
        GROUP BY properties->>'flnm'
        HAVING COUNT(*) > 1
        LIMIT 3
    ''')
    print(f'\n   중복 예시:')
    for row in cur.fetchall():
        print(f'      - {row[0]}: {row[1]}개')

conn.close()
print('\n' + '=' * 80)
