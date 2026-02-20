
import sys
import os
import psycopg2
from flask import Flask

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

def get_db_connection():
    try:
        conn = psycopg2.connect(
            dbname=Config.DB_CONFIG['dbname'],
            user=Config.DB_CONFIG['user'],
            password=Config.DB_CONFIG['password'],
            host=Config.DB_CONFIG['host'],
            port=Config.DB_CONFIG['port']
        )
        conn.autocommit = True
        return conn, conn.cursor()
    except Exception as e:
        print(f"DB Connection Error: {e}")
        return None, None

def migrate_events(graph_name="test_ai01"):
    print(f"🚀 Starting Event Migration on graph: {graph_name}")
    
    conn, cur = get_db_connection()
    if not conn: return

    try:
        cur.execute(f"SET graph_path = {graph_name}")
        
        # 1. Migrate Transfer Nodes (Create New -> Link -> Delete Old)
        print("📦 Migrating Transfers...")
        # Note: AgensGraph doesn't support changing VLABEL via SET. We must CREATE and DELETE.
        # We do this in one transaction. 
        # However, for safety, we process by matching and creating.
        
        # 1-1. Create Event Nodes from Transfers
        query_transfer_migration = """
        MATCH (t:vt_transfer)
        MERGE (e:vt_event {event_id: t.transfer_id})
        SET e.event_type = 'transfer', 
            e.amount = t.amount,
            e.timestamp = t.trx_date,
            e.layer = 'Event',
            e.status = 'completed',
            e.source = t.source,
            e.ontology = t.ontology,
            e.legal_category = t.legal_category
        """
        cur.execute(query_transfer_migration)
        print("   ✓ Created Event nodes for Transfers")
        
        # 1-2. Migrate Relations (Sender)
        query_rel_sender = """
        MATCH (t:vt_transfer)-[r:from_account]->(a:vt_bacnt),
              (e:vt_event {event_id: t.transfer_id})
        MERGE (a)-[:participated_in {role: 'sender'}]->(e)
        """
        cur.execute(query_rel_sender)

        # 1-3. Migrate Relations (Receiver)
        query_rel_receiver = """
        MATCH (t:vt_transfer)-[r:to_account]->(a:vt_bacnt),
              (e:vt_event {event_id: t.transfer_id})
        MERGE (a)-[:participated_in {role: 'receiver'}]->(e)
        """
        cur.execute(query_rel_receiver)
        
        # 1-4. Delete Old Transfer Nodes (will detach relations)
        cur.execute("MATCH (t:vt_transfer) DETACH DELETE t")
        print("   ✓ Deleted old vt_transfer nodes")


        # 2. Migrate Call Nodes
        print("📦 Migrating Calls...")
        
        # 2-1. Create Event Nodes from Calls
        query_call_migration = """
        MATCH (c:vt_call)
        MERGE (e:vt_event {event_id: c.call_id})
        SET e.event_type = 'call', 
            e.duration = c.duration,
            e.timestamp = c.call_date,
            e.layer = 'Event',
            e.status = 'completed',
            e.source = c.source,
            e.ontology = c.ontology,
            e.legal_category = c.legal_category
        """
        cur.execute(query_call_migration)
        print("   ✓ Created Event nodes for Calls")
        
        # 2-2. Migrate Relations (Caller)
        query_rel_caller = """
        MATCH (c:vt_call)-[r:caller]->(p:vt_telno),
              (e:vt_event {event_id: c.call_id})
        MERGE (p)-[:participated_in {role: 'caller'}]->(e)
        """
        cur.execute(query_rel_caller)

        # 2-3. Migrate Relations (Callee)
        query_rel_callee = """
        MATCH (c:vt_call)-[r:callee]->(p:vt_telno),
              (e:vt_event {event_id: c.call_id})
        MERGE (p)-[:participated_in {role: 'callee'}]->(e)
        """
        cur.execute(query_rel_callee)
        
        # 2-4. Delete Old Call Nodes
        cur.execute("MATCH (c:vt_call) DETACH DELETE c")
        print("   ✓ Deleted old vt_call nodes")

        # 3. Clean up Legacy Direct Edges
        print("🧹 Cleaning up Legacy Direct Edges...")
        # Note: 'transferred_to' and 'contacted' edges might exist between accounts/phones directly.
        # We can keep them if we want backward compatibility, or delete them.
        # Plan says "Delete r".
        
        cur.execute("MATCH ()-[r:transferred_to]->() DELETE r")
        cur.execute("MATCH ()-[r:contacted]->() DELETE r")
        
        print("✅ Migration Complete!")

    except Exception as e:
        print(f"❌ Migration Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    app = Flask(__name__)
    # Dummy config loading if needed, or rely on Config import
    migrate_events()
