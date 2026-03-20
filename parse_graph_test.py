import requests
import json

url = 'http://localhost:5001/api/query/ai'
payload = {
    "graph_path": "test_local_data",
    "question": "MATCH (n)-[r]->(m) RETURN r LIMIT 1"
}
try:
    res = requests.post(url, json=payload)
    print("Edge Raw Data:")
    print(json.dumps(res.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print(e)
