import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.services.graph_service import GraphService

def test_phone_exists():
    app = create_app()
    with app.app_context():
        print("\n🔍 DB에서 '010-1111-1111' 데이터 확인 시작...")
        
        # 1. 폰 번호 노드 자체가 존재하는지
        query1 = """
        SELECT * FROM cypher('tccop_graph_v6', $$
            MATCH (t:vt_telno)
            WHERE t->>'telno' = '010-1111-1111' OR t->>'telno' LIKE '%010-1111-1111%'
            RETURN t
        $$) AS (t agtype);
        """
        
        try:
            results1 = GraphService.execute_cypher(query1, "tccop_graph_v6")
            success1, data1 = results1
            if success1 and data1:
                print(f"✅ DB에 통신기기 노드가 존재함! {len(data1)}건 발견.")
                for r in data1:
                    print(f"   - 노드 속성: {json.dumps(r, ensure_ascii=False)}")
                
                # 2. 소유자 관계 확인
                print("\n🔍 연결된 '소유자(vt_psn)' 노드 관계망 확인 중...")
                query2 = """
                SELECT * FROM cypher('tccop_graph_v6', $$
                    MATCH (p:vt_psn)-[r:owns_phone]-(t:vt_telno)
                    WHERE t->>'telno' = '010-1111-1111'
                    RETURN p, r, t
                $$) AS (p agtype, r agtype, t agtype);
                """
                results2 = GraphService.execute_cypher(query2, "tccop_graph_v6")
                success2, data2 = results2
                if success2 and data2:
                    print(f"✅ 관계망 조회 성공! {len(data2)}건 발견.")
                else:
                    print(f"❌ 기기 노드는 존재하나, 해당 번호에 연결된 '소유자(vt_psn)' 노드 혹은 'owns_phone' 연결선(Edge)이 DB에 존재하지 않습니다!")
                    
            else:
                print("❌ DB에 '010-1111-1111' 번호를 가진 통신기기 노드가 전혀 없습니다!")
                
        except Exception as e:
            print(f"❌ 질의 에러: {e}")

if __name__ == "__main__":
    test_phone_exists()
