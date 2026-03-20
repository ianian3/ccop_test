import requests
import json

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
        
    print(f"=== test_local_data Graph ===")
    print(f"Total Nodes: {len(nodes)}")
    print(f"Total Edges: {len(edges)}\n")

    # Analyze nodes
    node_labels = {}
    for n in nodes:
        label = n.get('label', 'Unknown')
        node_labels[label] = node_labels.get(label, 0) + 1
        
    print("Node Distribution:")
    for lbl, count in sorted(node_labels.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {lbl}: {count}")

    # Analyze edges
    edge_labels = {}
    for e in edges:
        label = e.get('label', 'Unknown')
        if not label or label == 'Unknown':
             label = e.get('type', 'Unknown')
        edge_labels[label] = edge_labels.get(label, 0) + 1
        
    print("\nEdge Distribution:")
    for lbl, count in sorted(edge_labels.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {lbl}: {count}")
else:
    print(f"Failed: {res.status_code} - {res.text}")
