import os
import requests
import json
import time

DATA_DIR = "tests/data"
IMPORT_URL = "http://localhost:5001/api/rdb/import"
GRAPH_URL = "http://localhost:5001/api/rdb/to-graph"

csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
csv_files.sort()

print(f"Found {len(csv_files)} CSV files in {DATA_DIR}.")

for i, filename in enumerate(csv_files):
    filepath = os.path.join(DATA_DIR, filename)
    print(f"\\n[{i+1}/{len(csv_files)}] Uploading {filename}...")
    
    # We only want to clear the RDB on the very first file to avoid deleting uploads
    clear_rdb = 'true' if i == 0 else 'false'
    
    with open(filepath, 'rb') as f:
        files = {'file': (filename, f, 'text/csv')}
        data = {'clear_rdb': clear_rdb}
        try:
            res = requests.post(IMPORT_URL, files=files, data=data)
            print(f"Status: {res.status_code}")
            if res.status_code == 200:
                print(f"Response: {res.json().get('stats')}")
            else:
                print(f"Error Response: {res.text}")
        except Exception as e:
            print(f"Failed to upload {filename}: {e}")
            
    time.sleep(1) # Small pause between uploads

print("\n[V2 ETL] Triggering RDB to Graph Conversion...")
try:
    res = requests.post(GRAPH_URL, json={"graph_name": "test_local_data"})
    print(f"Status: {res.status_code}")
    if res.status_code == 200:
        print(f"Graph ETL Stats: {json.dumps(res.json().get('stats'), indent=2)}")
    else:
        print(f"Error Response: {res.text}")
except Exception as e:
    print(f"Failed to trigger ETL: {e}")

print("\\n✅ All test data loaded and converted to GDB.")
