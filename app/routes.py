# app/routes.py
from flask import Blueprint, render_template, request, jsonify
import json

# [서비스 모듈들 Import]
from app.services.ai_service import AIService
from app.services.etl_service import ETLService
from app.services.graph_service import GraphService
from app.services.subgraph_service import SubGraphService

bp = Blueprint('main', __name__)

# ------------------------------
# 1. 기본 페이지
# ------------------------------
@bp.route('/')
def index():
    return render_template('index.html')

# ------------------------------
# 2. 그래프 기본 기능 (검색, 초기화, 확장, 경로) -> GraphService 사용
# ------------------------------
@bp.route('/api/graph/clear', methods=['POST'])
def clear_graph():
    data = request.get_json()
    graph_path = data.get('graph_path')
    if not graph_path: return jsonify({"status": "error", "message": "그래프 이름 없음"}), 400
    
    success, msg = GraphService.clear_graph(graph_path)
    if success: return jsonify({"status": "success", "message": msg})
    else: return jsonify({"status": "error", "message": msg}), 500

@bp.route('/api/search', methods=['GET'])
def search_node():
    keyword = request.args.get('keyword', '').strip()
    graph_path = request.args.get('graph_path', 'demo_tst1')
    
    # 서비스 호출
    elements = GraphService.search_nodes(keyword, graph_path)
    return jsonify(elements)

@bp.route('/api/expand', methods=['GET'])
def expand_node():
    node_id = request.args.get('id')
    graph_path = request.args.get('graph_path', 'demo_tst1')
    
    if not node_id: return jsonify([])
    
    # 서비스 호출
    elements = GraphService.expand_node(node_id, graph_path)
    return jsonify(elements)

@bp.route('/api/path', methods=['POST'])
def find_path():
    data = request.get_json()
    src = data.get('source')
    tgt = data.get('target')
    graph_path = data.get('graph_path', 'demo_tst1')
    
    found, elements = GraphService.find_shortest_path(src, tgt, graph_path)
    
    if found: return jsonify({"found": True, "elements": elements})
    else: return jsonify({"found": False, "message": "경로를 찾을 수 없습니다."})

# app/routes.py (Refactored)

# ... (이전 import 및 라우트들은 동일)

# ------------------------------
# 3. AI 관련 기능 (RAG, Query) -> AIService + GraphService 협업
# ------------------------------
@bp.route('/api/query/ai', methods=['POST'])
def query_ai():
    data = request.get_json()
    question = data.get('question')
    graph_path = data.get('graph_path', 'demo_tst1')

    # quick_query 사용 - 빠른 그래프 조회만 (보고서 없음)
    elements = GraphService.quick_query(question, graph_path)
    
    return jsonify({"elements": elements})

@bp.route('/api/query/rag', methods=['POST'])
def query_rag():
    data = request.get_json()
    question = data.get('question')
    graph_path = data.get('graph_path', 'demo_tst1')
    
    # GraphService.rag_query가 report와 elements를 모두 반환
    report, elements = GraphService.rag_query(question, graph_path)
    
    return jsonify({"explanation": report, "elements": elements})


# ------------------------------
# 4. ETL 관련 기능 -> ETLService 사용
# ------------------------------
@bp.route('/api/etl/ai-suggest', methods=['POST'])
def etl_suggest():
    try:
        file = request.files['file']
        import pandas as pd
        df = pd.read_csv(file, nrows=3)
        headers = df.columns.tolist()
        sample = df.iloc[0].astype(str).tolist()
        
        mapping = AIService.suggest_mapping(headers, sample)
        return jsonify({"status": "success", "mapping": mapping})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/etl/import', methods=['POST'])
def etl_import():
    try:
        file = request.files['file']
        mapping = json.loads(request.form.get('mapping'))
        graph_path = request.form.get('graph_path', 'demo_tst1')
        
        success, nodes, edges, msg = ETLService.import_csv(file, mapping, graph_path)
        
        if success:
            return jsonify({"status": "success", "nodes_created": nodes, "edges_created": edges, "target_graph": graph_path})
        else:
            return jsonify({"status": "error", "message": msg}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
