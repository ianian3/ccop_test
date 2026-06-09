import sys
import os

# 프로젝트 루트 경로 설정
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.graph_service import GraphService
import json

def test_account_exists():
    app = create_app()
    with app.app_context():
        # 1. 속성 조건 없이 계좌 번호 자체가 있는지 확인 (정규표현식/Like 조회)
        print("\n🔍 DB에서 '110-1111-1111' 데이터 확인 시작...")
        
        # SQL 문으로 직접 질의 (속성 포맷 문제 확인용)
        # actno = '110-1111-1111' 이나 그 유사값을 갖는 vt_bacnt 노드를 모두 찾습니다.
        query1 = """
        SELECT * FROM cypher('tccop_graph_v6', $$
            MATCH (b:vt_bacnt)
            WHERE b->>'actno' = '110-1111-1111' OR b->>'actno' LIKE '%1111-1111%'
            RETURN b
        $$) AS (b agtype);
        """
        
        try:
            results1 = GraphService.execute_cypher(query1, "tccop_graph_v6")
            if results1:
                print(f"✅ DB에 계좌가 존재함! {len(results1)}건 발견.")
                for r in results1:
                    print(f"   - 노드 속성: {r}")
                
                # 2. 관계망(주인)이 엮여있는지 확인 (has_account)
                print("\n🔍 연결된 '주인(vt_psn)' 노드 관계망 확인 중...")
                query2 = """
                SELECT * FROM cypher('tccop_graph_v6', $$
                    MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt)
                    WHERE b->>'actno' = '110-1111-1111'
                    RETURN p, r, b
                $$) AS (p agtype, r agtype, b agtype);
                """
                results2 = GraphService.execute_cypher(query2, "tccop_graph_v6")
                if results2:
                    print(f"✅ 관계망 조회 성공! {len(results2)}건 발견.")
                else:
                    print(f"❌ 계좌 노드는 존재하나, 해당 계좌에 연결된 '주인(vt_psn)' 노드 혹은 'has_account' 연결선(Edge)이 DB에 존재하지 않습니다!")
                    
            else:
                print("❌ DB에 '110-1111-1111' 번호를 가진 계좌가 전혀 없습니다. (속성명이 actno가 아니거나 데이터가 삭제되었을 확률 높음)")
                
        except Exception as e:
            print(f"❌ 질의 에러: {e}")

if __name__ == "__main__":
    test_account_exists()
