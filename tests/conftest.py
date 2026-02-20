# tests/conftest.py
"""
Pytest fixtures for CCOP tests
"""
import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def app():
    """Create Flask app for testing"""
    # Set test environment
    os.environ['FLASK_ENV'] = 'testing'
    os.environ['DB_HOST'] = '127.0.0.1'
    os.environ['DB_NAME'] = 'ccopdb'
    os.environ['DB_USER'] = 'ccop'
    os.environ['DB_PASSWORD'] = 'test_password'
    os.environ['OPENAI_API_KEY'] = 'sk-test-key'
    
    from app import create_app
    app = create_app()
    app.config['TESTING'] = True
    
    yield app


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def sample_csv_data():
    """Sample CSV data for ETL tests"""
    return """접수번호,출금계좌,입금계좌,이체금액,이체일시
2026-00001,110-123-456789,221-987-654321,1000000,2026-01-15 10:30:00
2026-00001,221-987-654321,332-555-888777,950000,2026-01-15 11:45:00
2026-00002,443-111-222333,554-666-999000,500000,2026-01-16 09:00:00"""


@pytest.fixture
def sample_ontology_node():
    """Sample node data for ontology tests"""
    return {
        "flnm": "2026-00001",
        "label": "vt_flnm",
        "properties": {
            "crime_type": "보이스피싱",
            "damage_amount": 1000000
        }
    }


@pytest.fixture
def sample_pattern_subgraph():
    """Sample subgraph for pattern matching tests"""
    return {
        "case_node_id": "1",
        "nodes": {
            "1": {"label": "vt_flnm", "properties": {"flnm": "2026-00001"}},
            "2": {"label": "vt_telno", "properties": {"telno": "010-1234-5678"}},
            "3": {"label": "vt_bacnt", "properties": {"actno": "110-123-456789"}},
            "4": {"label": "vt_file", "properties": {"filename": "malware.apk"}}
        },
        "edges": [
            {"from": "1", "to": "2", "type": "used_phone", "properties": {}},
            {"from": "1", "to": "3", "type": "used_account", "properties": {}},
            {"from": "1", "to": "4", "type": "digital_trace", "properties": {}}
        ]
    }
