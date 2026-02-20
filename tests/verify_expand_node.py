import sys
import os
import json
from app import create_app
from app.services.graph_service import GraphService

sys.path.append(os.getcwd())

app = create_app()

def verify_expand_node():
    with app.app_context():
        graph_name = "investigation_graph"
        print(f"=== Verifying expand_node for '{graph_name}' ===\n")
        
        # 1. Find a node with edges (preferably a Case node or Account node)
        # We know vt_case has edges like [used_account] -> vt_bacnt
        q_find = """
        MATCH (s)-[r]->(t) 
        RETURN id(s), labels(s), id(t), labels(t), type(r) 
        LIMIT 1
        """
        success, res = GraphService.execute_cypher(q_find, graph_name)
        
        if not success or not res:
            print("❌ Could not find any edges to test expansion.")
            return

        # Extract node ID to expand
        # res is a list of elements dict, but execute_cypher parses them. 
        # Wait, execute_cypher returns a list of *Elements* (nodes/edges).
        # But the query 'RETURN id(s)...' returns scalar values which execute_cypher might not parse well into elements if they are not nodes/edges.
        # Let's use a query that returns the NODE object itself so execute_cypher parses it correctly.
        
        # GraphService.execute_cypher expects (id, label, props) columns to parse elements correctly.
        q_node = "MATCH (n)-[r]->() RETURN id(n), labels(n), properties(n) LIMIT 1"
        success_node, res_node = GraphService.execute_cypher(q_node, graph_name)
        
        if not success_node or not res_node:
             print("❌ Failed to fetch a source node.")
             return
             
        target_node = res_node[0]
        target_id = target_node['data']['id']
        target_label = target_node['data']['label']
        print(f"🎯 Target Node for Expansion: ID={target_id}, Label={target_label}")
        
        # 2. Perform Expansion
        print(f"▶ Calling GraphService.expand_node({target_id})...")
        expanded_elements = GraphService.expand_node(target_id, graph_path=graph_name)
        
        # 3. Validation
        print(f"▶ Result Count: {len(expanded_elements)}")
        
        nodes_found = [e for e in expanded_elements if e['group'] == 'nodes']
        edges_found = [e for e in expanded_elements if e['group'] == 'edges']
        
        print(f" - Nodes found: {len(nodes_found)}")
        print(f" - Edges found: {len(edges_found)}")
        
        if len(edges_found) > 0:
            print("✅ Expand Node functionality is WORKING.")
            print("\nSample Edge:")
            print(json.dumps(edges_found[0], indent=2, ensure_ascii=False))
        else:
            print("⚠️ Expand Node returned 0 edges. Something might be wrong (or node has no edges in the checked tables).")

if __name__ == "__main__":
    try:
        verify_expand_node()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
