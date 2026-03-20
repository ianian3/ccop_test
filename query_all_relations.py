import requests

url = "http://localhost:5001/api/graph/load?graph_path=test_local_data&limit=1000"
res = requests.get(url)

if res.status_code == 200:
    data = res.json()
    if isinstance(data, dict):
        nodes = data.get('nodes', [])
        edges = data.get('edges', [])
    elif isinstance(data, list):
        nodes = [x['data'] for x in data if x.get('group') == 'nodes']
        edges = [x['data'] for x in data if x.get('group') == 'edges']
    else:
        print("Unknown format")
        nodes, edges = [], []
        
    node_map = {}
    
    for n in nodes:
        node_id = n.get('id')
        props = n.get('props', {})
        label = n.get('label', 'Unknown')
        
        # Determine meaningful display name
        display_name = props.get('actno') or props.get('telno') or props.get('event_type') or props.get('id', '') or str(node_id)
        if label == 'vt_transfer':
            display_name = f"이체({props.get('amount', 0)}원)"
        elif label == 'vt_call':
            display_name = f"통화({props.get('duration', 0)}초)"
            
        node_map[node_id] = f"[{label}: {display_name}]"
        
    print(f"Total Connections Found: {len(edges)}\n")
    print("=== Sample Connections (All 220, Truncated to first 20 for preview) ===")
    
    for i, e in enumerate(edges[:20]):
        src_id = e.get('source')
        tgt_id = e.get('target')
        rel_label = e.get('label', 'Unknown')
        
        src_str = node_map.get(src_id, f"[ID:{src_id}]")
        tgt_str = node_map.get(tgt_id, f"[ID:{tgt_id}]")
        
        print(f"{src_str} --({rel_label})--> {tgt_str}")
        
    print("\n... remaining edges omitted for brevity.")
else:
    print(f"Query Failed: {res.status_code} - {res.text}")
