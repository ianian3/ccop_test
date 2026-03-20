import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_host = os.environ.get("DB_HOST", "49.50.128.28")
db_port = os.environ.get("DB_PORT", "5333")
db_name = os.environ.get("DB_NAME", "tccopdb")
db_user = os.environ.get("DB_USER", "ccop")
db_pass = os.environ.get("DB_PASSWORD", "Ccop@2025")

try:
    conn = psycopg2.connect(host=db_host, port=db_port, dbname=db_name, user=db_user, password=db_pass)
    cur = conn.cursor()
    
    # Initialize AGE
    cur.execute("LOAD 'age';")
    cur.execute("SET search_path = ag_catalog, \"$user\", public;")
    
    # Check if graph exists
    cur.execute("SELECT count(*) FROM ag_catalog.ag_graph WHERE name = 'test_local_data';")
    exists = cur.fetchone()[0]
    
    if exists:
        cur.execute("SET graph_path = test_local_data;")
        
        print(f"=== AgensGraph [test_local_data] Summary ===")
        
        # Nodes
        cur.execute("SELECT label(v), count(v) FROM test_local_data.v v GROUP BY label(v) ORDER BY count(v) DESC;")
        nodes = cur.fetchall()
        total_nodes = sum(n[1] for n in nodes)
        print(f"\\nNodes (Total: {total_nodes}):")
        for label, count in nodes:
            print(f"  - {label:<15}: {count} nodes")
            
        # Edges
        cur.execute("SELECT label(e), count(e) FROM test_local_data.e e GROUP BY label(e) ORDER BY count(e) DESC;")
        edges = cur.fetchall()
        total_edges = sum(e[1] for e in edges)
        print(f"\\nEdges (Total: {total_edges}):")
        for label, count in edges:
            print(f"  - {label:<15}: {count} edges")
            
        # Extract a few transfer examples directly parsing json properties using age functions
        # This requires cypher syntax via postgres wrapper
        cur.execute("""
            SELECT * FROM cypher('test_local_data', $$
                MATCH (a:vt_bacnt)-[r1:from_account]->(t:vt_transfer)-[r2:to_account]->(b:vt_bacnt)
                RETURN a.actno, t.amount, b.actno
                LIMIT 5
            $$) as (from_act agtype, amount agtype, to_act agtype);
        """)
        transfers = cur.fetchall()
        print(f"\\nSample Transfers (LIMIT 5):")
        for t in transfers:
            print(f"  {t[0]} --[{t[1]}원]--> {t[2]}")
            
    else:
        print("Graph 'test_local_data' does not exist.")
        
    cur.close()
    conn.close()
except Exception as e:
    print(f"Error: {e}")
