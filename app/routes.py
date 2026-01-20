# app/routes.py
from flask import Blueprint, render_template, request, jsonify
import json

# [서비스 모듈들 Import]
from app.services.ai_service import AIService
from app.services.etl_service import ETLService
from app.services.graph_service import GraphService
from app.services.subgraph_service import SubGraphService
from app.services.legal_rag_service import LegalRAGService

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

@bp.route('/api/graph/list', methods=['GET'])
def list_graphs():
    """그래프 목록 조회"""
    graphs = GraphService.list_graphs()
    return jsonify({"status": "success", "graphs": graphs})

@bp.route('/api/graph/create', methods=['POST'])
def create_graph():
    """새 그래프 생성"""
    data = request.get_json()
    graph_name = data.get('graph_name', '').strip()
    
    if not graph_name:
        return jsonify({"status": "error", "message": "그래프 이름이 필요합니다."}), 400
    
    # 이름 유효성 검사 (영문, 숫자, 언더스코어만)
    import re
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', graph_name):
        return jsonify({"status": "error", "message": "그래프 이름은 영문자로 시작해야 하며, 영문, 숫자, 언더스코어만 사용 가능합니다."}), 400
    
    success, msg = GraphService.create_graph(graph_name)
    if success:
        return jsonify({"status": "success", "message": msg, "graph_name": graph_name})
    else:
        return jsonify({"status": "error", "message": msg}), 500

@bp.route('/api/graph/delete', methods=['POST'])
def delete_graph():
    """그래프 삭제"""
    data = request.get_json()
    graph_name = data.get('graph_name', '').strip()
    
    if not graph_name:
        return jsonify({"status": "error", "message": "그래프 이름이 필요합니다."}), 400
    
    success, msg = GraphService.delete_graph(graph_name)
    if success:
        return jsonify({"status": "success", "message": msg})
    else:
        return jsonify({"status": "error", "message": msg}), 500

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

# ------------------------------
# 5. 법률 RAG 관련 기능 -> LegalRAGService 사용
# ------------------------------
@bp.route('/api/legal/upload', methods=['POST'])
def legal_upload():
    """법률 PDF 업로드 및 벡터화"""
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "파일이 없습니다."}), 400
        
        file = request.files['file']
        if not file.filename.endswith('.pdf'):
            return jsonify({"status": "error", "message": "PDF 파일만 지원합니다."}), 400
        
        success, message, chunk_count = LegalRAGService.add_pdf(file, file.filename)
        
        if success:
            return jsonify({
                "status": "success",
                "message": message,
                "chunks": chunk_count
            })
        else:
            return jsonify({"status": "error", "message": message}), 500
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/legal/query', methods=['POST'])
def legal_query():
    """법률 질의응답"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({"status": "error", "message": "질문을 입력해주세요."}), 400
        
        result = LegalRAGService.query(question)
        
        return jsonify({
            "status": "success" if result['success'] else "error",
            "answer": result['answer'],
            "sources": result['sources']
        })
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/legal/documents', methods=['GET'])
def legal_documents():
    """업로드된 법률 문서 목록"""
    try:
        documents = LegalRAGService.get_documents()
        return jsonify({
            "status": "success",
            "documents": documents
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/legal/delete', methods=['POST'])
def legal_delete():
    """문서 삭제"""
    try:
        data = request.get_json()
        filename = data.get('filename', '')
        
        if not filename:
            return jsonify({"status": "error", "message": "파일명이 필요합니다."}), 400
        
        success, message = LegalRAGService.delete_document(filename)
        
        if success:
            return jsonify({"status": "success", "message": message})
        else:
            return jsonify({"status": "error", "message": message}), 404
            
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
