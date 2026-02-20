import sys
import os
from app import create_app
from app.services.graph_service import GraphService

sys.path.append(os.getcwd())

app = create_app()

def inspect_sample_edges():
    with app.app_context():
        graph_name = "investigation_graph"
        print(f"=== Sample Edge Inspection for '{graph_name}' ===\n")
        
        # 1. Get raw sample edges
        q = "MATCH (s)-[r]->(t) RETURN labels(s), type(r), labels(t) LIMIT 10"
        conn, cur = GraphService.get_db_connection()
        try:
             cur.execute(f"SET graph_path = {graph_name}")
             cur.execute(q)
             rows = cur.fetchall()
             print(f"Found {len(rows)} sample edges:")
             for r in rows:
                 s_lbl = r[0]
                 e_type = r[1]
                 t_lbl = r[2]
                 print(f" - {s_lbl} -[{e_type}]-> {t_lbl}")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    inspect_sample_edges()
