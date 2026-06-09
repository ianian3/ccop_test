import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.services.graph_service import GraphService

def test_ai_query_exact():
    app = create_app()
    with app.app_context():
        # AI가 만든 쿼리
        query_ai = """
        SELECT * FROM cypher('tccop_graph_v6', $$ 
            MATCH (p:vt_psn)-[r:has_account]->(b:vt_bacnt {actno: '110-1111-1111'}) 
            RETURN p, r, b 
        $$) AS (p agtype, r agtype, b agtype);
        """
        
        results_ai = GraphService.execute_cypher(query_ai, "tccop_graph_v6")
        if isinstance(results_ai, list):
            print(f"AI 쿼리 결과: {len(results_ai)}건 반환됨.")
        else:
            print(f"AI 쿼리 오류: {results_ai}")

if __name__ == "__main__":
    test_ai_query_exact()
