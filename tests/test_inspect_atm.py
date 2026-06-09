import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app
from app.services.graph_service import GraphService
import json

def test():
    app = create_app()
    with app.app_context():
        query = """SELECT * FROM cypher('tccop_graph_v6', $$ MATCH (n)-[r]-(a:vt_atm) RETURN n,r,a LIMIT 5 $$) AS (n agtype, r agtype, a agtype);"""
        success, data = GraphService.execute_cypher(query, "tccop_graph_v6")
        if success:
            for x in data:
                print(json.dumps(x, ensure_ascii=False))
        else:
            print("Query failed")

if __name__ == "__main__":
    test()
