
import psycopg2
import json

def find_data_everywhere(target_val):
    conn = psycopg2.connect(host='49.50.128.28', port=5333, dbname='tccopdb', user='ccop', password='Ccop@2025')
    cur = conn.cursor()
    
    # 모든 스키마 목록 가져오기
    cur.execute("SELECT nspname FROM pg_namespace;")
    schemas = [r[0] for r in cur.fetchall() if not r[0].startswith('pg_')]
    
    print(f"🔍 Searching for '{target_val}' in {len(schemas)} schemas...")
    
    results = []
    
    for schema in schemas:
        # 해당 스키마에 vt_psn (인물) 테이블이 있는지 확인
        try:
            cur.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema='{schema}' AND table_name='vt_psn';")
            if cur.fetchone():
                cur.execute(f"SELECT '{schema}', count(*) FROM {schema}.vt_psn WHERE props::text LIKE %s OR name::text LIKE %s;", (f'%{target_val}%', f'%{target_val}%'))
                res = cur.fetchone()
                if res[1] > 0:
                    print(f"  ✨ Found {res[1]} match(es) in {schema}.vt_psn")
                    results.append((schema, 'vt_psn', res[1]))
            
            # vt_bacnt (계좌) 테이블 확인
            cur.execute(f"SELECT table_name FROM information_schema.tables WHERE table_schema='{schema}' AND table_name='vt_bacnt';")
            if cur.fetchone():
                cur.execute(f"SELECT '{schema}', count(*) FROM {schema}.vt_bacnt WHERE props::text LIKE %s OR actno::text LIKE %s;", (f'%{target_val}%', f'%{target_val}%'))
                res = cur.fetchone()
                if res[1] > 0:
                    print(f"  ✨ Found {res[1]} match(es) in {schema}.vt_bacnt")
                    results.append((schema, 'vt_bacnt', res[1]))
        except:
            conn.rollback()
            continue
            
    conn.close()
    return results

if __name__ == "__main__":
    find_data_everywhere('피의자1')
    find_data_everywhere('110-1111-1111')
