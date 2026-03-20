import os
import psycopg2
from dotenv import load_dotenv

def init_v2_database():
    """
    RDB_DATA_STANDARDIZATION_v2.md 기반의 27개 RDB 테이블(v2)을
    tccopdb PostgreSQL 데이터베이스에 생성하는 스크립트.
    """
    load_dotenv()
    
    # 데이터베이스 연결 정보 (환경변수 또는 기본값)
    db_host = os.environ.get("DB_HOST", "49.50.128.28")
    db_port = os.environ.get("DB_PORT", "5333")
    db_name = os.environ.get("DB_NAME", "tccopdb")
    db_user = os.environ.get("DB_USER", "ccop")
    db_pass = os.environ.get("DB_PASSWORD", "Ccop@2025")

    print(f"[Init DB V2] 호스트 {db_host}:{db_port}의 '{db_name}' 데이터베이스에 연결 중...")
    
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            dbname=db_name,
            user=db_user,
            password=db_pass
        )
        # 자동 커밋 모드 활성화 (테이블 생성 등 DDL 실행 시 유용)
        conn.autocommit = True
        cur = conn.cursor()

        # V2 초기화 SQL 스크립트 경로 파악
        script_dir = os.path.dirname(os.path.abspath(__file__))
        sql_path = os.path.join(script_dir, "rdb_init_v2.sql")
        
        if not os.path.exists(sql_path):
            print(f"❌ [에러] SQL 스크립트를 찾을 수 없습니다: {sql_path}")
            return
            
        print(f"[Init DB V2] '{sql_path}' 내용을 읽어 실행을 시작합니다...")
        
        # 파일 내용을 하나의 큰 문자열로 읽어들임
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_script = f.read()

        # Execute the entire script
        cur.execute(sql_script)

        print(f"✅ [성공] V2 27개 RDB 테이블 스키마 적용을 완료했습니다.")

    except psycopg2.Error as e:
        print(f"❌ [DB 에러] 쿼리 실행 중 오류가 발생했습니다:")
        print(e)
    except Exception as e:
        print(f"❌ [일반 에러] 오류가 발생했습니다:")
        print(e)
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals() and conn is not None:
            conn.close()
            print("[Init DB V2] 데이터베이스 연결을 종료했습니다.")

if __name__ == "__main__":
    init_v2_database()
