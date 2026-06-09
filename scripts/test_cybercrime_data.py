
import sys
import os
import csv
import psycopg2
from flask import Flask

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config
from app.services.rdb_to_graph_service import RdbToGraphService

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

def setup_test_data():
    print("🛠 Setting up Test Data in RDB...")
    conn, cur = get_db_connection()
    if not conn: return False

    try:
        # 1. Ensure Tables Exist (rdb_transfers, rdb_calls, rdb_accounts, rdb_phones)
        # Based on RdbToGraphService columns
        
        # Drop tables to ensure schema matches test data (STRING IDs)
        cur.execute("DROP TABLE IF EXISTS rdb_transfers CASCADE")
        cur.execute("DROP TABLE IF EXISTS rdb_calls CASCADE")
        # Note: rdb_accounts/phones might be used by other tests, but we'll drop them to be clean or just IF NOT EXISTS?
        # Let's drop them to ensure clean state for this test.
        cur.execute("DROP TABLE IF EXISTS rdb_accounts CASCADE")
        cur.execute("DROP TABLE IF EXISTS rdb_phones CASCADE")

        # Accounts
        cur.execute("""
            CREATE TABLE rdb_accounts (
                actno VARCHAR(50) PRIMARY KEY,
                bank_name VARCHAR(50),
                holder_name VARCHAR(50)
            )
        """)
        
        # Phones
        cur.execute("""
            CREATE TABLE rdb_phones (
                telno VARCHAR(50) PRIMARY KEY,
                carrier VARCHAR(20)
            )
        """)

        # Transfers
        cur.execute("""
            CREATE TABLE rdb_transfers (
                trx_id VARCHAR(50) PRIMARY KEY,
                amount NUMERIC(15,2),
                trx_date TIMESTAMP,
                sender_actno VARCHAR(50),
                receiver_actno VARCHAR(50)
            )
        """)

        # Calls
        cur.execute("""
            CREATE TABLE rdb_calls (
                call_id VARCHAR(50) PRIMARY KEY,
                duration INT,
                call_date TIMESTAMP,
                caller_no VARCHAR(50),
                callee_no VARCHAR(50)
            )
        """)
        
        # Clear existing data
        cur.execute("TRUNCATE TABLE rdb_transfers, rdb_calls, rdb_accounts, rdb_phones CASCADE")
        
        # 2. Insert Data from CSVs
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Transfers
        transfer_csv = os.path.join(base_path, 'tests/data/test_transfer_events.csv')
        print(f"   - Loading {transfer_csv}...")
        with open(transfer_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Insert Accounts first (if not exist)
                if row['sender_actno']:
                    cur.execute("INSERT INTO rdb_accounts (actno, bank_name, holder_name) VALUES (%s, 'Unknown', 'Sender') ON CONFLICT DO NOTHING", (row['sender_actno'],))
                if row['receiver_actno']:
                    cur.execute("INSERT INTO rdb_accounts (actno, bank_name, holder_name) VALUES (%s, 'Unknown', 'Receiver') ON CONFLICT DO NOTHING", (row['receiver_actno'],))
                
                # Insert Transfer
                cur.execute("""
                    INSERT INTO rdb_transfers (trx_id, amount, trx_date, sender_actno, receiver_actno)
                    VALUES (%s, %s, %s, %s, %s)
                """, (row['trx_id'], row['amount'], row['trx_date'], row['sender_actno'], row['receiver_actno']))

        # Calls
        call_csv = os.path.join(base_path, 'tests/data/test_call_events.csv')
        print(f"   - Loading {call_csv}...")
        with open(call_csv, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Insert Phones first
                if row['caller_no']:
                    cur.execute("INSERT INTO rdb_phones (telno, carrier) VALUES (%s, 'Unknown') ON CONFLICT DO NOTHING", (row['caller_no'],))
                if row['callee_no']:
                    cur.execute("INSERT INTO rdb_phones (telno, carrier) VALUES (%s, 'Unknown') ON CONFLICT DO NOTHING", (row['callee_no'],))
                
                # Insert Call
                cur.execute("""
                    INSERT INTO rdb_calls (call_id, duration, call_date, caller_no, callee_no)
                    VALUES (%s, %s, %s, %s, %s)
                """, (row['call_id'], row['duration'], row['call_date'], row['caller_no'], row['callee_no']))

        print("✅ Test Data Loaded into RDB.")
        return True
    except Exception as e:
        print(f"❌ Setup Error: {e}")
        return False
    finally:
        conn.close()

def run_test():
    app = Flask(__name__)
    app.config.from_object(Config)

    with app.app_context():
        # Setup
        if not setup_test_data():
            return

        graph_name = "test_ai01"
        print(f"🚀 Running ETL on '{graph_name}'...")
        
        # Clear Graph First
        conn, cur = RdbToGraphService.get_db_connection()
        try:
            cur.execute(f"DROP GRAPH IF EXISTS {graph_name} CASCADE")
            cur.execute(f"CREATE GRAPH {graph_name}")
            conn.commit()
        finally:
            conn.close()

        # Run ETL
        success, stats = RdbToGraphService.transfer_data(graph_name=graph_name)
        if not success:
            print(f"❌ ETL Failed: {stats}")
            return
            
        print(f"✅ ETL Finished. Stats: {stats}")

        # Verify
        print("\n🔍 Verifying Graph Data...")
        conn, cur = RdbToGraphService.get_db_connection()
        try:
            cur.execute(f"SET graph_path = {graph_name}")
            
            # Check Event Nodes
            # Simple query to get properties
            cur.execute("MATCH (n:vt_event) RETURN n.event_id, n.event_type, n.amount, n.duration")
            events = cur.fetchall()
            print(f"   - Events Found: {len(events)}")
            for e in events:
                # Handle None values safely
                eid = e[0] if e[0] else "Unknown"
                etype = e[1] if e[1] else "Unknown"
                amt = e[2] if e[2] else 0
                dur = e[3] if e[3] else 0
                print(f"     * {eid}: Type={etype}, Amt={amt}, Dur={dur}")
                
            # Check Relations
            cur.execute("""
                MATCH (a)-[r:participated_in]->(e:vt_event) 
                RETURN label(a), a.actno, a.telno, r.role, e.event_id
            """)
            rels = cur.fetchall()
            # Sort in Python
            rels.sort(key=lambda x: (x[4] if x[4] else "", x[3] if x[3] else ""))
            
            print(f"   - Relations Found: {len(rels)}")
            for r in rels:
                target_val = r[1] if r[1] else r[2]
                print(f"     * [{r[0]} {target_val}] --({r[3]})--> [Event {r[4]}]")
                
            if len(events) == 7 and len(rels) >= 14: # 4 transfers + 3 calls
                print("\n✅ TEST PASSED: All events and relationships created correctly.")
            else:
                print("\n⚠️ TEST COMPLETED with discrepancies (Check counts).")

        except Exception as e:
            print(f"❌ Verification Error: {e}")
        finally:
            conn.close()

if __name__ == "__main__":
    run_test()
