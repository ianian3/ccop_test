import os
import sys
import json
import logging
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
from app import create_app
from app.services.graph_service import GraphService

def inspect_v6_data():
    load_dotenv()
    app = create_app()
    graph_path = "tccop_graph_v6"
    
    with app.app_context():
        # Query to see all relationship types and counts
        cypher = f"SELECT * FROM cypher('{graph_path}', $$ MATCH ()-[r]->() RETURN label(r), count(*) $$) AS (label agtype, count agtype);"
        print(f"🔍 '{graph_path}'의 관계 통계를 조회합니다...")
        success, result = GraphService.execute_cypher(cypher, graph_path)
        
        if not success:
            print(f"❌ 에러 발생: {result}")
        else:
            print("\n[관계 타입 및 건수]")
            for row in result:
                print(f"- {row['label']}: {row['count']}건")

        # Check nodes for '피해자1'
        print(f"\n🔍 '피해자1' 노드 상세 정보:")
        psn_cypher = f"SELECT * FROM cypher('{graph_path}', $$ MATCH (p:vt_psn {{name: '피해자1'}}) RETURN p $$) AS (p agtype);"
        success_psn, psn_result = GraphService.execute_cypher(psn_cypher, graph_path)
        print(json.dumps(psn_result, indent=2, ensure_ascii=False))

        # Check neighbors of '피해자1'
        print(f"\n🔍 '피해자1'의 인접 노드 및 관계 레이블:")
        neighbor_cypher = f"SELECT * FROM cypher('{graph_path}', $$ MATCH (p:vt_psn {{name: '피해자1'}})-[r]->(n) RETURN label(r), label(n) $$) AS (rel agtype, node_label agtype);"
        success_neighbor, neighbor_result = GraphService.execute_cypher(neighbor_cypher, graph_path)
        print(json.dumps(neighbor_result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    inspect_v6_data()
