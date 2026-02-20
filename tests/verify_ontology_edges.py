import sys
import os
from app import create_app
from app.services.graph_service import GraphService

sys.path.append(os.getcwd())

app = create_app()

def verify_ontology():
    with app.app_context():
        graph_name = "investigation_graph"
        print(f"=== Ontology Verification for '{graph_name}' ===\n")

        # 1. Define Expected Patterns (KICS Standard)
        # (Source Label, Edge Type, Target Label)
        expected_patterns = [
            ('vt_flnm', 'used_account', 'vt_bacnt'),
            ('vt_flnm', 'used_phone', 'vt_telno'),
            ('vt_flnm', 'digital_trace', 'vt_site'),
            ('vt_flnm', 'digital_trace', 'vt_file'),
            ('vt_flnm', 'digital_trace', 'vt_ip'),
            ('vt_telno', 'related_to', 'vt_psn'),
            ('vt_bacnt', 'related_to', 'vt_psn')
        ]

        # 2. Check Edge Existence & Counts
        print("Checking Edge Patterns:")
        total_edges_found = 0
        
        for src_label, edge_type, tgt_label in expected_patterns:
            query = f"""
            MATCH (s:{src_label})-[r:{edge_type}]->(t:{tgt_label})
            RETURN id(r), type(r), properties(r) LIMIT 1
            """
            success, res = GraphService.execute_cypher(query, graph_name)
            
            if success and res:
                 print(f"✅ [Verified] ({src_label}) -[:{edge_type}]-> ({tgt_label}) exists.")
                 total_edges_found += 1
            else:
                 print(f"⚠️ [Missing]  ({src_label}) -[:{edge_type}]-> ({tgt_label}) NOT found.")
            # execute_cypher returns (True, elements_list) or (False, error_msg)
            # If elements_list is not empty, it means at least one edge was found.

        print(f"\nTotal Confirmed Patterns: {total_edges_found}/{len(expected_patterns)}")

        # 3. Sample Data Inspection
        print("\n=== Sample Edge Data Inspection ===")
        sample_q = "MATCH (s)-[r]->(t) RETURN labels(s), type(r), labels(t) LIMIT 5"
        success_sample, res_sample = GraphService.execute_cypher(sample_q, graph_name)
        
        if success_sample and res_sample:
            for elem in res_sample:
                # This executes but execute_cypher parses into nodes/edges format.
                # It might be hard to see raw labels if execute_cypher transforms it.
                # However, seeing 'elements' means edges are being returned.
                pass
            print(f"Successfully retrieved {len(res_sample)} generic graph elements (nodes/edges).")
        else:
             print("No global edges found or query failed.")

if __name__ == "__main__":
    try:
        verify_ontology()
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
