import psycopg2

def generate_overlapping_test_data():
    """RDB 테이블에 거미줄 모양(공유 자원)이 형성되는 고의적인 오버랩 테스트 데이터 적재"""
    print("▶ Generating overlapping test data for RDB...")
    
    # DB 연결 (환경 변수 읽기 또는 고정값)
    conn = psycopg2.connect("dbname=tccopdb user=ccop password=Ccop@2025 host=49.50.128.28 port=5333")
    conn.autocommit = True
    cur = conn.cursor()
    
    try:
        # 기존 RDB 데이터 초기화 (선택 사항: 주석 해제 시 완전히 새로운 데이터만 생성)
        # tables = ['rdb_relations', 'rdb_transfers', 'rdb_calls', 'rdb_ips', 'rdb_phones', 'rdb_accounts', 'rdb_suspects', 'rdb_cases']
        # for t in tables: cur.execute(f"TRUNCATE TABLE {t} CASCADE")
        
        # 1. 공통 증거 자원 (이것들이 교차점=거미줄의 중심이 됨)
        shared_account = "110-123-OVERLAP"  # 공용 대포통장
        shared_phone = "010-9999-OVERLAP"  # 공용 단말기 번호
        shared_ip = "192.168.0.OVERLAP"    # 공용 VPN IP
        
        # 2. 사건 A (보이스피싱 조직 A팀)
        case_a = "CASE_2024_A"
        cur.execute("INSERT INTO rdb_cases (case_no, crime_name, reg_date) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (case_a, "사기(보이스피싱 A팀)", "2024-01-10"))
        
        suspect_a1 = "USER_A1"
        cur.execute("INSERT INTO rdb_suspects (user_id, name, nickname) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (suspect_a1, "김철수(A팀)", "총책A"))
        
        cur.execute("INSERT INTO rdb_accounts (actno, bank_name) VALUES (%s, %s) ON CONFLICT DO NOTHING", (shared_account, "대포은행"))
        cur.execute("INSERT INTO rdb_phones (telno, carrier) VALUES (%s, %s) ON CONFLICT DO NOTHING", (shared_phone, "알뜰폰"))
        cur.execute("INSERT INTO rdb_ips (ip_addr) VALUES (%s) ON CONFLICT DO NOTHING", (shared_ip,))
        
        # 사건 A 관계 (A팀이 공용 자원 사용)
        cur.execute("INSERT INTO rdb_relations (source_type, source_value, target_type, target_value, rel_type) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    ('case', case_a, 'suspect', suspect_a1, 'involves'))
        cur.execute("INSERT INTO rdb_relations (source_type, source_value, target_type, target_value, rel_type) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    ('suspect', suspect_a1, 'account', shared_account, 'owns'))
        cur.execute("INSERT INTO rdb_relations (source_type, source_value, target_type, target_value, rel_type) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    ('suspect', suspect_a1, 'phone', shared_phone, 'owns'))
        cur.execute("INSERT INTO rdb_relations (source_type, source_value, target_type, target_value, rel_type) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    ('suspect', suspect_a1, 'ip', shared_ip, 'used'))
                    
        # 3. 사건 B (보이스피싱 조직 B팀 - A팀과 독립적이나 자원 공유)
        case_b = "CASE_2024_B"
        cur.execute("INSERT INTO rdb_cases (case_no, crime_name, reg_date) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (case_b, "사기(보이스피싱 B팀)", "2024-02-15"))
        
        suspect_b1 = "USER_B1"
        cur.execute("INSERT INTO rdb_suspects (user_id, name, nickname) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (suspect_b1, "박영희(B팀)", "수금책B"))
                    
        # 사건 B 관계 (B팀도 동일한 공용 자원 사용!)
        cur.execute("INSERT INTO rdb_relations (source_type, source_value, target_type, target_value, rel_type) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    ('case', case_b, 'suspect', suspect_b1, 'involves'))
        cur.execute("INSERT INTO rdb_relations (source_type, source_value, target_type, target_value, rel_type) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    ('suspect', suspect_b1, 'account', shared_account, 'owns')) # 겹치는 계좌
        cur.execute("INSERT INTO rdb_relations (source_type, source_value, target_type, target_value, rel_type) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    ('suspect', suspect_b1, 'phone', shared_phone, 'owns'))   # 겹치는 번호
        
        # 4. 사건 C (독립적인 사건 - 아예 겹치지 않는 정상 사용자)
        case_c = "CASE_2024_C"
        cur.execute("INSERT INTO rdb_cases (case_no, crime_name, reg_date) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (case_c, "일반 사기(C)", "2024-03-01"))
        suspect_c1 = "USER_C1"
        cur.execute("INSERT INTO rdb_suspects (user_id, name, nickname) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                    (suspect_c1, "이민기(C)", "개인사기꾼"))
        
        # C의 고유 자원
        c_account = "999-999-UNIQUE"
        cur.execute("INSERT INTO rdb_accounts (actno, bank_name) VALUES (%s, %s) ON CONFLICT DO NOTHING", (c_account, "정상은행"))
        cur.execute("INSERT INTO rdb_relations (source_type, source_value, target_type, target_value, rel_type) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    ('case', case_c, 'suspect', suspect_c1, 'involves'))
        cur.execute("INSERT INTO rdb_relations (source_type, source_value, target_type, target_value, rel_type) VALUES (%s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                    ('suspect', suspect_c1, 'account', c_account, 'owns'))

        # DB 커밋
        conn.commit()
        print("✅ 오버랩(Entity Resolution) 테스트 데이터 3건(Case A, B, C) 적재 완료!")
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    generate_overlapping_test_data()
