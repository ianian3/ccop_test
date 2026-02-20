"""
CCOP 파트너 API v1 엔드포인트
외부 파트너가 CCOP 기능에 접근할 수 있는 REST API
"""
from flask import Blueprint, request, jsonify, current_app
from app.middleware.api_auth import require_api_key, require_endpoint_permission
from app.services.ai_service import AIService
from app.services.graph_service import GraphService
from app.services.rdb_to_graph_service import RdbToGraphService
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


# ============================================
# 6. 범죄 패턴 분석 API (Phase 2)
# ============================================

@api_v1.route('/analyze-pattern', methods=['POST'])
@require_api_key
def analyze_pattern():
    """
    사건의 범죄 패턴 자동 인식
    
    Request:
        {
            "case_id": "2019-000392",
            "graph_path": "demo_tst1"  // 선택사항
        }
    
    Response:
        {
            "success": true,
            "case_id": "2019-000392",
            "matched_patterns": [
                {
                    "pattern_name": "몸캠피싱",
                    "confidence": 0.95,
                    "missing_elements": ["IP주소"]
                }
            ],
            "primary_pattern": "몸캠피싱",
            "analysis_summary": "..."
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        case_id = data.get('case_id')
        if not case_id:
            return jsonify({"error": "case_id field is required"}), 400
        
        graph_path = data.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'demo_tst1'))
        
        # 패턴 분석 실행
        from app.services.pattern_analyzer import PatternAnalyzer
        
        result = PatternAnalyzer.analyze_case(case_id, graph_path)
        
        if not result.get('matched_patterns'):
            return jsonify({
                "success": false,
                "case_id": case_id,
                "message": "No pattern matched. Evidence may be insufficient."
            }), 200
        
        return jsonify({
            "success": True,
            "case_id": result["case_id"],
            "matched_patterns": result["matched_patterns"],
            "primary_pattern": result["primary_pattern"],
            "confidence": result["confidence"],
            "analysis_summary": result["analysis_summary"]
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": "Pattern analysis failed",
            "details": str(e)
        }), 500


@api_v1.route('/evidence-completeness/<case_id>', methods=['GET'])
@require_api_key
def evidence_completeness(case_id):
    """
    사건의 증거 완성도 평가
    
    Query Parameters:
        - graph_path: 그래프 경로 (선택)
    
    Response:
        {
            "success": true,
            "case_id": "2019-000392",
            "pattern": "몸캠피싱",
            "completeness_score": 0.75,
            "missing_evidence": [...],
            "next_steps": [...]
        }
    """
    try:
        graph_path = request.args.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'demo_tst1'))
        
        # 1. 패턴 분석
        from app.services.pattern_analyzer import PatternAnalyzer
        from app.services.evidence_analyzer import EvidenceAnalyzer
        
        pattern_result = PatternAnalyzer.analyze_case(case_id, graph_path)
        
        if not pattern_result.get('matched_patterns'):
            return jsonify({
                "success": False,
                "case_id": case_id,
                "message": "No pattern matched. Cannot evaluate completeness."
            }), 200
        
        # 2. 서브그래프 추출
        subgraph = PatternAnalyzer._extract_case_subgraph(case_id, graph_path)
        
        if not subgraph:
            return jsonify({
                "success": False,
                "case_id": case_id,
                "message": "Case not found"
            }), 404
        
        # 3. 증거 완성도 분석
        matched_pattern = pattern_result['matched_patterns'][0]  # 최고 점수 패턴
        completeness_result = EvidenceAnalyzer.evaluate_completeness(
            case_id,
            matched_pattern,
            subgraph
        )
        
        return jsonify({
            "success": True,
            **completeness_result
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": "Evidence evaluation failed",
            "details": str(e)
        }), 500


@api_v1.route('/patterns', methods=['GET'])
@require_api_key
def list_patterns():
    """
    지원하는 범죄 패턴 목록 조회
    
    Response:
        {
            "patterns": [
                {
                    "pattern_id": "bodycamp_phishing_v1",
                    "name": "몸캠피싱",
                    "description": "..."
                }
            ]
        }
    """
    try:
        from app.services.pattern_library import PatternLibrary
        
        patterns = PatternLibrary.get_all_patterns()
        pattern_list = []
        
        for pattern_id, pattern in patterns.items():
            pattern_list.append({
                "pattern_id": pattern.pattern_id,
                "name": pattern.name,
                "description": pattern.description,
                "required_nodes": len(pattern.required_nodes),
                "required_edges": len(pattern.required_edges),
                "min_threshold": pattern.scoring["min_threshold"]
            })
        
        return jsonify({
            "patterns": pattern_list,
            "total": len(pattern_list)
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": "Failed to retrieve patterns",
            "details": str(e)
        }), 500


# ============================================
# 7. LLM 관계 추론 API (Phase 1)
# ============================================

@api_v1.route('/etl/analyze', methods=['POST'])
def analyze_csv_for_inference():
    """
    CSV 업로드 후 자동 관계 추론 (인증 불필요 - 내부 사용)
    
    Request:
        multipart/form-data
        - file: CSV 파일
        - graph: 그래프 이름 (선택)
    
    Response:
        {
            "status": "success",
            "columns": [...],
            "relationships": [...],
            "suggested_mappings": [...]
        }
    """
    import pandas as pd
    from app.services.relationship_inferencer import RelationshipInferencer
    
    try:
        # 파일 확인
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "Only CSV files are supported"}), 400
        
        # CSV 로드
        df = pd.read_csv(file)
        df = df.fillna('')
        df.columns = df.columns.str.strip()
        
        # 관계 추론 실행
        result = RelationshipInferencer.analyze_csv(df)
        
        return jsonify(result), 200
        
    except Exception as e:
        current_app.logger.error(f"[API v1] etl/analyze error: {e}")
        return jsonify({
            "error": "CSV analysis failed",
            "details": str(e)
        }), 500


@api_v1.route('/etl/infer-import', methods=['POST'])
def import_with_inference():
    """
    추론된 매핑으로 그래프 적재
    
    Request:
        multipart/form-data
        - file: CSV 파일
        - graph: 대상 그래프 이름
        - mapping: 선택한 매핑 (JSON 문자열)
    
    Response:
        {
            "status": "success",
            "nodes_created": 10,
            "edges_created": 5
        }
    """
    import pandas as pd
    from app.services.etl_service import ETLService
    from app.services.relationship_inferencer import RelationshipInferencer
    import json
    
    try:
        # 파일 확인
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        graph = request.form.get('graph', 'demo_tst1')
        mapping_json = request.form.get('mapping')
        
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "Only CSV files are supported"}), 400
        
        # 매핑 파싱
        if mapping_json:
            mapping = json.loads(mapping_json)
        else:
            # 매핑이 없으면 자동 추론
            df = pd.read_csv(file)
            df = df.fillna('')
            df.columns = df.columns.str.strip()
            
            infer_result = RelationshipInferencer.analyze_csv(df)
            
            if not infer_result.get('suggested_mappings'):
                return jsonify({
                    "error": "No relationships could be inferred from CSV"
                }), 400
            
            # 첫 번째 매핑 사용
            mapping = infer_result['suggested_mappings'][0]
            
            # 파일 포인터 리셋
            file.seek(0)
        
        # 매핑 검증
        validation = RelationshipInferencer.validate_mapping(mapping)
        if not validation['valid']:
            return jsonify({
                "error": "Invalid mapping",
                "details": validation['errors']
            }), 400
        
        # ETL 실행
        success, node_count, edge_count, message = ETLService.import_csv(
            file, mapping, graph
        )
        
        if success:
            return jsonify({
                "status": "success",
                "nodes_created": node_count,
                "edges_created": edge_count,
                "graph": graph,
                "mapping_used": mapping
            }), 200
        else:
            return jsonify({
                "error": "ETL failed",
                "message": message
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"[API v1] etl/infer-import error: {e}")
        return jsonify({
            "error": "Import failed",
            "details": str(e)
        }), 500


# ============================================
# 8. KICS 확장 스키마 LLM 맵핑 API
# ============================================

@api_v1.route('/etl/analyze-extended', methods=['POST'])
def analyze_csv_extended():
    """
    KICS 확장 스키마 기반 CSV 분석 (4-Layer)
    
    Request:
        multipart/form-data
        - file: CSV 파일
    
    Response:
        {
            "status": "success",
            "source": "llm",
            "mapping": {
                "layer_mapping": {...},
                "detected_action": {...},
                "relationships": [...],
                "etl_config": {...}
            }
        }
    """
    import pandas as pd
    from app.services.schema_mapper import KICSSchemaMapper
    
    try:
        # 파일 확인
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "Only CSV files are supported"}), 400
        
        # CSV 로드
        df = pd.read_csv(file)
        df = df.fillna('')
        df.columns = df.columns.str.strip()
        
        # KICS 확장 스키마 매핑
        columns = list(df.columns)
        sample_rows = df.head(5).to_dict('records')
        
        result = KICSSchemaMapper.analyze_csv(columns, sample_rows)
        
        # Action 타입 정보 추가
        action_detection = KICSSchemaMapper.detect_action_type(columns, sample_rows)
        
        # ETL 설정 생성
        if result.get("success"):
            etl_configs = KICSSchemaMapper.generate_etl_config(result)
            result["etl_configs"] = etl_configs
        
        # 온톨로지 메타데이터 추가
        from app.services.ontology_service import KICSCrimeDomainOntology
        result["schema_info"] = {
            "layers": KICSCrimeDomainOntology.LAYERS,
            "entity_count": len(KICSCrimeDomainOntology.ENTITIES),
            "relationship_count": len(KICSCrimeDomainOntology.RELATIONSHIPS)
        }
        
        return jsonify({
            "status": "success",
            "columns": columns,
            "row_count": len(df),
            "action_detection": action_detection,
            **result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"[API v1] etl/analyze-extended error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "CSV analysis failed",
            "details": str(e)
        }), 500


@api_v1.route('/etl/import-extended', methods=['POST'])
def import_with_extended_schema():
    """
    KICS 확장 스키마 기반 그래프 적재
    
    Action 노드(Transfer/Call/Access/Message) 자동 생성 포함
    
    Request:
        multipart/form-data
        - file: CSV 파일
        - graph: 대상 그래프 이름
    
    Response:
        {
            "status": "success",
            "action_nodes": 10,
            "entity_nodes": 50,
            "relationships": 30
        }
    """
    from app.services.etl_service import ETLService
    
    try:
        # 파일 확인
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        graph = request.form.get('graph', 'demo_tst1')
        
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "Only CSV files are supported"}), 400
        
        # KICS 확장 스키마 기반 ETL 실행
        success, results = ETLService.import_with_schema_mapping(file, graph)
        
        if success:
            return jsonify({
                "status": "success",
                "graph": graph,
                "action_nodes": results.get("action_nodes", 0),
                "entity_nodes": results.get("entity_nodes", 0),
                "relationships": results.get("relationships", 0),
                "mapping": results.get("mapping", {})
            }), 200
        else:
            return jsonify({
                "error": "ETL failed",
                "details": results.get("error", "Unknown error")
            }), 500
        
    except Exception as e:
        current_app.logger.error(f"[API v1] etl/import-extended error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "Import failed",
            "details": str(e)
        }), 500


@api_v1.route('/schema/layers', methods=['GET'])
def get_schema_layers():
    """
    KICS 확장 스키마 Layer 정보 조회
    
    Response:
        {
            "layers": {
                "Case": [...],
                "Actor": [...],
                "Action": [...],
                "Evidence": [...]
            },
            "entities": {...},
            "relationships": {...}
        }
    """
    try:
        from app.services.ontology_service import KICSCrimeDomainOntology
        
        # Layer 정보
        layers = KICSCrimeDomainOntology.LAYERS
        
        # 엔티티 정보 (간략화)
        entities = {}
        for name, info in KICSCrimeDomainOntology.ENTITIES.items():
            entities[name] = {
                "layer": info.get("layer", "Unknown"),
                "label": info.get("label", ""),
                "label_ko": info.get("label_ko", ""),
                "legal_category": info.get("legal_category", "")
            }
        
        # 관계 정보 (간략화)
        relationships = {}
        for name, info in KICSCrimeDomainOntology.RELATIONSHIPS.items():
            relationships[name] = {
                "domain": info.get("domain", ""),
                "range": info.get("range", ""),
                "label_ko": info.get("label_ko", ""),
                "legal_significance": info.get("legal_significance", "")
            }
        
        return jsonify({
            "layers": layers,
            "entities": entities,
            "relationships": relationships,
            "entity_count": len(entities),
            "relationship_count": len(relationships)
        }), 200
        
    except Exception as e:
        return jsonify({
            "error": "Failed to retrieve schema",
            "details": str(e)
        }), 500


# ============================================
# 9. Graph Management API
# ============================================

@api_v1.route('/graph/list', methods=['GET'])
# @require_api_key
def list_graphs():
    """그래프 목록 조회"""
    try:
        graphs = GraphService.list_graphs()
        return jsonify({
            "status": "success",
            "graphs": graphs
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@api_v1.route('/graph/create', methods=['POST'])
# @require_api_key
# @require_endpoint_permission('admin')
def create_graph():
    """그래프 생성"""
    try:
        data = request.get_json()
        graph_name = data.get('graph_name')
        if not graph_name:
            return jsonify({"status": "error", "message": "graph_name required"}), 400
            
        success, msg = GraphService.create_graph(graph_name)
        if success:
            return jsonify({"status": "success", "message": msg}), 200
        else:
            return jsonify({"status": "error", "message": msg}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@api_v1.route('/graph/delete', methods=['POST'])
# @require_api_key
# @require_endpoint_permission('admin')
def delete_graph():
    """그래프 삭제 (위험)"""
    try:
        data = request.get_json()
        graph_name = data.get('graph_name')
        if not graph_name:
            return jsonify({"status": "error", "message": "graph_name required"}), 400
            
        success, msg = GraphService.delete_graph(graph_name)
        if success:
            return jsonify({"status": "success", "message": msg}), 200
        else:
            return jsonify({"status": "error", "message": msg}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@api_v1.route('/rdb/to-graph', methods=['POST'])
@require_api_key
def rdb_to_graph():
    """RDB 데이터를 그래프로 변환"""
    try:
        data = request.get_json() or {}
        graph_name = data.get('graph_name', 'test_ai01')
        
        success, stats = RdbToGraphService.transfer_data(graph_name)
        
        if success:
            return jsonify({
                "status": "success", 
                "message": "RDB -> Graph 변환 완료",
                "stats": stats
            }), 200
        else:
            return jsonify({
                "status": "error", 
                "message": str(stats)
            }), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ============================================
# 11. RDB 조회 및 대시보드 API
# ============================================

@api_v1.route('/rdb/stats', methods=['GET'])
def rdb_gdb_stats():
    """RDB 및 GDB 통합 통계 조회 (대시보드용)"""
    import psycopg2
    try:
        graph_name = request.args.get('graph_name', 'test_ai01') # 기본값 유지
        
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        cur = conn.cursor()
        
        stats = {"rdb": {}, "gdb": {}}
        
        # RDB 통계
        rdb_tables = ['rdb_cases', 'rdb_suspects', 'rdb_accounts', 'rdb_phones', 
                      'rdb_transfers', 'rdb_calls', 'rdb_relations']
        for table in rdb_tables:
            try:
                cur.execute(f"SELECT count(*) FROM {table}")
                stats["rdb"][table.replace('rdb_', '')] = cur.fetchone()[0]
            except:
                stats["rdb"][table.replace('rdb_', '')] = 0
        
        # GDB 통계 (그래프 목록 및 노드 수)
        try:
            cur.execute("SELECT graphname FROM ag_graph LIMIT 10")
            graphs = [r[0] for r in cur.fetchall()]
            stats["gdb"]["graphs"] = graphs
            stats["gdb"]["graph_count"] = len(graphs)
            
            # 선택된 그래프의 노드/엣지 수
            try:
                # AgensGraph에서 graph_path 설정 시 식별자(identifier)로 처리해야 함
                # SQL injection 방지를 위해 포맷팅 사용 시 주의 필요 (graph_name은 검증 필요)
                # 여기서는 간단히 따옴표 없이 사용 (AgensGraph 문법)
                cur.execute(f"SET graph_path = {graph_name}")
                cur.execute("MATCH (n) RETURN count(n)")
                stats["gdb"]["nodes"] = cur.fetchone()[0]
                cur.execute("MATCH ()-[r]->() RETURN count(r)")
                stats["gdb"]["edges"] = cur.fetchone()[0]
            except:
                stats["gdb"]["nodes"] = 0
                stats["gdb"]["edges"] = 0
        except Exception as e:
            stats["gdb"]["error"] = str(e)
        
        conn.close()
        return jsonify({"status": "success", "stats": stats}), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@api_v1.route('/gdb/detail-stats', methods=['GET'])
def gdb_detail_stats():
    """GDB 상세 통계: 노드 라벨별 수, 엣지 타입별 수"""
    import psycopg2
    try:
        graph_name = request.args.get('graph_name', 'test_ai01')
        
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        cur = conn.cursor()
        
        result = {"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0}
        
        try:
            cur.execute(f"SET graph_path = {graph_name}")
            
            # 노드 라벨별 카운트
            cur.execute("MATCH (n) RETURN label(n) as lbl, count(n) as cnt ORDER BY cnt DESC")
            for row in cur.fetchall():
                result["nodes"].append({"label": row[0], "count": row[1]})
                result["total_nodes"] += row[1]
            
            # 엣지 타입별 카운트
            cur.execute("MATCH ()-[r]->() RETURN type(r) as tp, count(r) as cnt ORDER BY cnt DESC")
            for row in cur.fetchall():
                result["edges"].append({"type": row[0], "count": row[1]})
                result["total_edges"] += row[1]
                
        except Exception as e:
            result["error"] = str(e)
        
        conn.close()
        return jsonify({"status": "success", "data": result}), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@api_v1.route('/rdb/tables', methods=['GET'])
def list_rdb_tables():
    """RDB 테이블 목록 조회"""
    tables = [
        {"name": "rdb_cases", "label": "사건", "icon": "folder"},
        {"name": "rdb_suspects", "label": "피의자", "icon": "user"},
        {"name": "rdb_accounts", "label": "계좌", "icon": "credit-card"},
        {"name": "rdb_phones", "label": "전화번호", "icon": "phone"},
        {"name": "rdb_transfers", "label": "이체내역", "icon": "exchange-alt"},
        {"name": "rdb_calls", "label": "통화내역", "icon": "phone-volume"},
        {"name": "rdb_relations", "label": "관계", "icon": "project-diagram"}
    ]
    return jsonify({"status": "success", "tables": tables}), 200


@api_v1.route('/rdb/query/<table_name>', methods=['GET'])
def query_rdb_table(table_name):
    """RDB 테이블 데이터 조회"""
    import psycopg2
    
    # 허용된 테이블만 조회 (SQL Injection 방지)
    allowed_tables = ['rdb_cases', 'rdb_suspects', 'rdb_accounts', 'rdb_phones',
                      'rdb_transfers', 'rdb_calls', 'rdb_relations', 'rdb_ips']
    
    if table_name not in allowed_tables:
        return jsonify({"status": "error", "message": "Invalid table name"}), 400
    
    limit = min(int(request.args.get('limit', 50)), 500)  # 최대 500건
    offset = int(request.args.get('offset', 0))
    search = request.args.get('search', '')
    
    try:
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        cur = conn.cursor()
        
        # 컬럼 정보 조회
        cur.execute(f"""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = '{table_name}' ORDER BY ordinal_position
        """)
        columns = [r[0] for r in cur.fetchall()]
        
        # 데이터 조회
        query = f"SELECT * FROM {table_name}"
        if search:
            # 첫 번째 텍스트 컬럼에서 검색
            search_col = columns[1] if len(columns) > 1 else columns[0]
            query += f" WHERE {search_col}::text ILIKE '%{search}%'"
        query += f" ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"
        
        cur.execute(query)
        rows = cur.fetchall()
        
        # 전체 건수
        cur.execute(f"SELECT count(*) FROM {table_name}")
        total = cur.fetchone()[0]
        
        conn.close()
        
        # 결과 변환
        data = []
        for row in rows:
            item = {}
            for i, col in enumerate(columns):
                val = row[i]
                # datetime 등 JSON 직렬화 불가 타입 처리
                if hasattr(val, 'isoformat'):
                    val = val.isoformat()
                item[col] = val
            data.append(item)
        
        return jsonify({
            "status": "success",
            "table": table_name,
            "columns": columns,
            "data": data,
            "total": total,
            "limit": limit,
            "offset": offset
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
