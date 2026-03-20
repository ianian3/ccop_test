"""Rebuild graph v6 and verify has_account + used_ip edges."""
from app import create_app
from app.services.graph_service import GraphService
from app.services.rdb_to_graph_service import RdbToGraphService

app = create_app()
with app.app_context():
    # Drop and rebuild
    conn, cur = GraphService.get_db_connection()
    try:
        cur.execute("DROP GRAPH IF EXISTS tccop_graph_v6 CASCADE")
        conn.commit()
        print("Dropped old tccop_graph_v6")
    except Exception as e:
        conn.rollback()
        print(f"Drop error: {e}")
    cur.close()
    conn.close()

    success, result = RdbToGraphService.transfer_data("tccop_graph_v6")
    print(f"\nResult: {success}")
    print(f"Stats: {result}")

    # Verify the new edges
    conn, cur = GraphService.get_db_connection()
    cur.execute("SET graph_path = tccop_graph_v6")
    
    print("\n" + "=" * 60)
    print("Edge Verification:")
    cur.execute("MATCH ()-[r]->() RETURN label(r) as lbl, count(r) as cnt")
    for r in cur.fetchall():
        print(f"  {r[0]}: {r[1]}")
    
    print("\nhas_account details:")
    cur.execute("MATCH (p:vt_psn)-[r:has_account]->(a:vt_bacnt) RETURN p.name, a.actno LIMIT 10")
    for r in cur.fetchall():
        print(f"  {r[0]} → {r[1]}")
    
    print("\nused_ip details:")
    cur.execute("MATCH (p:vt_psn)-[r:used_ip]->(i:vt_ip) RETURN p.name, i.ip LIMIT 10")
    for r in cur.fetchall():
        print(f"  {r[0]} → {r[1]}")
    
    cur.close()
    conn.close()
