import json
from app import create_app
from app.services.rdb_to_graph_service import RdbToGraphService

app = create_app()
with app.app_context():
    success, result = RdbToGraphService.transfer_data(graph_name="test_overlap")
    print(f"ETL Result: {success}")
    print(json.dumps(result, indent=2, ensure_ascii=False))

