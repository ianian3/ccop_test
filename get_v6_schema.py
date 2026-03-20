
import json
import sys
import os
from flask import Flask
from config import Config

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.graph_service import GraphService

def get_schema():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    with app.app_context():
        schema = GraphService.get_current_schema('tccop_graph_v6')
        print(json.dumps(schema, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    get_schema()
