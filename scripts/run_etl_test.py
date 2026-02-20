
import sys
import os
import psycopg2
from flask import Flask

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.services.rdb_to_graph_service import RdbToGraphService
from config import Config

def run_etl_test():
    app = Flask(__name__)
    app.config.from_object(Config)

    with app.app_context():
        print("🚀 Running ETL on 'test_ai01' (using new Event logic)...")
        # Using 'test_ai01' to match what's usually used or a new one
        graph_name = "test_ai01"
        
        # 1. Run ETL
        success, stats = RdbToGraphService.transfer_data(graph_name=graph_name)
        
        if not success:
            print(f"❌ ETL Failed: {stats}")
            return

        print(f"✅ ETL Success: {stats}")
        
        # 2. Verify Event Nodes
        print("\n🔍 Verifying Event Nodes in Graph...")
        conn, cur = RdbToGraphService.get_db_connection()
        try:
            cur.execute(f"SET graph_path = {graph_name}")
            
            # Count vt_event
            cur.execute("MATCH (n:vt_event) RETURN count(n), n.event_type limit 5")
            rows = cur.fetchall()
            event_count = 0
            for r in rows:
                print(f"   - Found Event: Count={r[0]}, Type={r[1]}")
                if r[0]: event_count += int(r[0])
            
            if event_count > 0:
                print(f"✅ Verified {event_count} Event nodes created.")
            else:
                print("⚠️ No Event nodes found. (Is RDB data empty?)")

            # Verify inferred relationships
            print("\n🔍 Verifying 'participated_in' Edges...")
            cur.execute("MATCH ()-[r:participated_in]->() RETURN count(r)")
            rel_count = cur.fetchone()[0]
            if rel_count > 0:
                print(f"✅ Verified {rel_count} 'participated_in' edges.")
            else:
                print("⚠️ No 'participated_in' edges found.")
                
        except Exception as e:
            print(f"❌ Verification Error: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    run_etl_test()
