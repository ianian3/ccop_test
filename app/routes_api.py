"""
CCOP 파트너 API v1 엔드포인트
외부 파트너가 CCOP 기능에 접근할 수 있는 REST API
"""
from flask import Blueprint, request, jsonify, current_app
from app.middleware.api_auth import require_api_key, require_endpoint_permission
from app.services.ai_service import AIService
from app.services.graph_service import GraphService
from app.models.api_key import get_tier_config
import time

# Blueprint 생성
api_v1 = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# ============================================
# 1. Text-to-Cypher API
# ============================================

@api_v1.route('/text-to-cypher', methods=['POST'])
@require_api_key
def text_to_cypher():
    """
    자연어 질문을 Cypher 쿼리로 변환
    
    Request:
        {
            "question": "접수번호 2019-000392와 관련된 모든 계좌 찾기",
            "schema": {  // 선택사항
                "node_labels": ["vt_flnm", "vt_bacnt"],
                "edge_types": ["USED_ACCOUNT"]
            }
        }
    
    Response:
        {
            "status": "success",
            "cypher": "MATCH ...",
            "partner": "demo_partner"
        }
    """
    try:
        start_time = time.time()
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        question = data.get('question')
        if not question:
            return jsonify({"error": "question field is required"}), 400
        
        # Cypher 쿼리 생성
        cypher = AIService.generate_cypher(question)
        
        response_time = (time.time() - start_time) * 1000  # ms
        
        current_app.logger.info(
            f"[API v1] text-to-cypher | partner={request.partner} | "
            f"question_len={len(question)} | response_time={response_time:.2f}ms"
        )
        
        return jsonify({
            "status": "success",
            "cypher": cypher,
            "partner": request.partner,
            "response_time_ms": round(response_time, 2)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"[API v1] text-to-cypher error: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500


# ============================================
# 2. Graph Query API (읽기 전용)
# ============================================

@api_v1.route('/graph-query', methods=['POST'])
@require_api_key
@require_endpoint_permission('graph-query')
def graph_query():
    """
    Cypher 쿼리 실행 (읽기 전용)
    
    Request:
        {
            "cypher": "MATCH (v:vt_flnm) RETURN v LIMIT 10",
            "graph_path": "demo_tst1"
        }
    
    Response:
        {
            "status": "success",
            "results": [...],
            "count": 10
        }
    """
    try:
        start_time = time.time()
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        keyword = data.get('keyword')
        graph_path = data.get('graph_path', 'demo_tst1')
        
        if not keyword:
            return jsonify({"error": "keyword field is required"}), 400
        
        # 파트너 티어에 따른 결과 제한
        tier_config = get_tier_config(request.partner_data.get('tier', 'free'))
        max_results = tier_config.get('max_results', 50)
        
        # GraphService를 통한 검색 (보안이 검증된 메서드)
        results = GraphService.search_nodes(keyword, graph_path)
        
        # 결과 제한
        limited_results = results[:max_results] if isinstance(results, list) else results
        
        response_time = (time.time() - start_time) * 1000
        
        current_app.logger.info(
            f"[API v1] graph-query | partner={request.partner} | "
            f"graph={graph_path} | keyword={keyword} | "
            f"response_time={response_time:.2f}ms"
        )
        
        return jsonify({
            "status": "success",
            "results": limited_results,
            "count": len(limited_results) if isinstance(limited_results, list) else 0,
            "limited": isinstance(results, list) and len(results) > max_results,
            "graph_path": graph_path,
            "response_time_ms": round(response_time, 2)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"[API v1] graph-query error: {e}")
        return jsonify({
            "error": "Query execution failed",
            "message": str(e)
        }), 500


# ============================================
# 3. Cypher Validation API
# ============================================

@api_v1.route('/validate-cypher', methods=['POST'])
@require_api_key
def validate_cypher():
    """
    Cypher 쿼리 문법 검증 (실행하지 않음)
    
    Request:
        {
            "cypher": "MATCH (v) RETURN v"
        }
    
    Response:
        {
            "status": "valid",
            "is_safe": true,
            "warnings": []
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        cypher = data.get('cypher')
        if not cypher:
            return jsonify({"error": "cypher field is required"}), 400
        
        # 기본 검증
        warnings = []
        dangerous_keywords = ['DELETE', 'DROP', 'CREATE', 'MERGE', 'SET', 'REMOVE']
        cypher_upper = cypher.upper()
        
        is_safe = True
        for keyword in dangerous_keywords:
            if keyword in cypher_upper:
                warnings.append(f"Query contains potentially dangerous keyword: {keyword}")
                is_safe = False
        
        # MATCH 키워드 확인
        if 'MATCH' not in cypher_upper and 'RETURN' not in cypher_upper:
            warnings.append("Query should contain MATCH and RETURN clauses")
        
        return jsonify({
            "status": "valid" if is_safe else "warning",
            "is_safe": is_safe,
            "warnings": warnings,
            "cypher": cypher
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": "Validation failed",
            "message": str(e)
        }), 500


# ============================================
# 4. Usage Statistics API
# ============================================

@api_v1.route('/usage', methods=['GET'])
@require_api_key
def get_usage():
    """
    파트너의 API 사용량 조회
    
    Response:
        {
            "partner": "demo_partner",
            "tier": "free",
            "current_month": {
                "requests": 150,
                "limit": 1000,
                "remaining": 850
            }
        }
    """
    try:
        # 향후 구현: 데이터베이스에서 실제 사용량 조회
        # 현재는 더미 데이터 반환
        
        tier_config = get_tier_config(request.partner_data.get('tier', 'free'))
        rate_limit = tier_config.get('rate_limit')
        
        return jsonify({
            "partner": request.partner,
            "tier": request.partner_data.get('tier', 'free'),
            "current_month": {
                "requests": 0,  # 임시
                "limit": rate_limit,
                "remaining": rate_limit if rate_limit else None
            },
            "allowed_endpoints": request.partner_data.get('allowed_endpoints', [])
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": "Failed to retrieve usage",
            "message": str(e)
        }), 500


# ============================================
# 5. Health Check (인증 불필요)
# ============================================

@api_v1.route('/health', methods=['GET'])
def health_check():
    """
    API 헬스 체크
    
    Response:
        {
            "status": "healthy",
            "version": "1.0.0"
        }
    """
    return jsonify({
        "status": "healthy",
        "version": "1.0.0",
        "service": "CCOP Partner API"
    }), 200
