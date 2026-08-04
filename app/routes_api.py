"""
CCOP 파트너 API v1 엔드포인트
외부 파트너가 CCOP 기능에 접근할 수 있는 REST API
"""
from flask import Blueprint, request, jsonify, current_app
from app.middleware.api_auth import require_api_key, require_endpoint_permission, require_api_or_ui
from app.services.graph_service import GraphService
from app.services.rdb_to_graph_service import RdbToGraphService
from app.services.langgraph_agent import LangGraphAgent
from app.models.api_key import get_tier_config
import re
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

        graph_path = current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6')
        if data.get("schema") and "graph_path" in data.get("schema"):
            graph_path = data["schema"]["graph_path"]

        # LangGraph 에이전트 실행 (Reflection 루프, Vector RAG, Schema Fetching 포함)
        agent = LangGraphAgent()
        result = agent.run(question, graph_path)

        response_time = (time.time() - start_time) * 1000  # ms

        current_app.logger.info(
            f"[API v1] text-to-cypher | partner={request.partner} | "
            f"question_len={len(question)} | intent={result.get('intent', 'UNKNOWN')} | "
            f"response_time={response_time:.2f}ms"
        )

        return jsonify({
            "status": result.get("status", "error"),
            "cypher": result.get("cypher", ""),
            "intent": result.get("intent", "UNKNOWN"),
            "elements": result.get("elements", []),
            "results_count": result.get("results_count", 0),
            "partner": request.partner,
            "response_time_ms": round(response_time, 2)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"[API v1] text-to-cypher error: {e}")
        return jsonify({"error": "Internal server error"}), 500


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

        cypher = data.get('cypher')
        graph_path = data.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))

        if not cypher:
            return jsonify({"error": "cypher field is required"}), 400

        # 읽기 전용 보안 검증 (쓰기 명령어 차단)
        upper_cypher = cypher.upper()
        forbidden = ["DELETE", "SET", "REMOVE", "MERGE", "DROP", "CREATE", "DETACH"]
        for kw in forbidden:
            if re.search(r'\b' + kw + r'\b', upper_cypher):
                return jsonify({
                    "error": "Read-only violation",
                    "message": f"데이터 변경 명령어({kw})는 허용되지 않습니다."
                }), 403

        # 파트너 티어에 따른 결과 제한
        tier_config = get_tier_config(request.partner_data.get('tier', 'free'))
        max_results = tier_config.get('max_results', 50)

        success, results = GraphService.execute_cypher(cypher, graph_path)
        if not success:
            return jsonify({"error": "Query execution failed", "message": str(results)}), 500

        limited_results = results[:max_results] if isinstance(results, list) else results

        response_time = (time.time() - start_time) * 1000

        current_app.logger.info(
            f"[API v1] graph-query | partner={request.partner} | "
            f"graph={graph_path} | response_time={response_time:.2f}ms"
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
# 8. Agentic Text-to-Cypher (LangGraph)
# ============================================

@api_v1.route('/agentic-query', methods=['POST'])
@require_api_key
def agentic_query():
    """
    LangGraph 기반 분석 에이전트 실행 (라우팅 + 성찰 루프)
    """
    try:
        start_time = time.time()
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body required"}), 400
        
        question = data.get('question')
        if not question:
            return jsonify({"error": "question field is required"}), 400
            
        graph_path = data.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
        
        # LangGraph Agent 실행
        agent = LangGraphAgent()
        result = agent.run(question, graph_path)
        
        response_time = (time.time() - start_time) * 1000
        
        return jsonify({
            "status": "success",
            "agent_response": result,
            "partner": request.partner,
            "response_time_ms": round(response_time, 2)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"[API v1] agentic-query error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "error": "Agent execution failed",
            "message": str(e)
        }), 500


# ============================================
# 4. Usage Statistics API
# ============================================

@api_v1.route('/usage', methods=['GET'])
@require_api_key
def get_usage():
    """
    파트너 API 사용량 조회 (TB_AUDIT_LOG 기반 실계수)

    Response:
        {
            "partner": "demo_partner",
            "tier": "free",
            "current_month": { "requests": 150, "limit": 1000, "remaining": 850 },
            "breakdown": { "QUERY": 100, "PATH": 30, "REPORT": 20 },
            "allowed_endpoints": [...]
        }
    """
    try:
        tier_config = get_tier_config(request.partner_data.get('tier', 'free'))
        rate_limit = tier_config.get('rate_limit')

        # TB_AUDIT_LOG 에서 이번 달 실제 호출 수 집계
        total_requests = 0
        breakdown = {}
        try:
            from app.services.rdb_to_graph_service import RdbToGraphService
            conn = RdbToGraphService.get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT ACTION_CD, COUNT(*) AS cnt
                FROM TB_AUDIT_LOG
                WHERE CREATED_AT >= date_trunc('month', CURRENT_DATE)
                  AND RESULT_STATUS != 'FAIL'
                GROUP BY ACTION_CD
            """)
            for row in cur.fetchall():
                breakdown[row[0]] = int(row[1])
                total_requests += int(row[1])
            cur.close()
            conn.close()
        except Exception:
            pass  # TB_AUDIT_LOG 없으면 0으로 유지

        remaining = (rate_limit - total_requests) if rate_limit else None

        return jsonify({
            "partner": request.partner,
            "tier": request.partner_data.get('tier', 'free'),
            "current_month": {
                "requests": total_requests,
                "limit": rate_limit,
                "remaining": max(remaining, 0) if remaining is not None else None
            },
            "breakdown": breakdown,
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
        
        graph_path = data.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
        
        # 패턴 분석 실행
        from app.services.pattern_analyzer import PatternAnalyzer
        
        result = PatternAnalyzer.analyze_case(case_id, graph_path)
        
        if not result.get('matched_patterns'):
            return jsonify({
                "success": False,
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
        graph_path = request.args.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
        
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
@require_api_or_ui
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
        graph = request.form.get('graph', 'tccop_graph_v6')
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
# 9. Network Mode API (1-mode / 2-mode 투영)
# ============================================

@api_v1.route('/network/project', methods=['POST'])
@require_api_or_ui
def network_project_1mode():
    """
    2-mode → 1-mode 투영 (공유 노드 기반 actor-actor 연결)

    2-mode 이분 그래프에서 pivot 노드를 공유하는 actor 노드들을
    직접 연결하는 1-mode 동질 그래프로 투영합니다.

    예) vt_psn -[has_account]-> vt_bacnt <-[has_account]- vt_psn
        → vt_psn -[co_account {via: actno, weight: N}]- vt_psn

    Request:
        {
            "graph_path": "tccop_graph_v6",
            "actor_label": "vt_psn",          // 투영 후 남는 노드 타입
            "pivot_label":  "vt_bacnt",        // 공유 기준 노드 타입 (제거됨)
            "min_shared":   1,                 // 최소 공유 수 (기본: 1)
            "projection_edge": "co_account"    // 생성될 엣지 타입 (기본: co_{pivot})
        }

    Response:
        {
            "status": "success",
            "mode": "1mode",
            "actor_label": "vt_psn",
            "pivot_label": "vt_bacnt",
            "nodes": [...],   // actor 노드 목록
            "edges": [...],   // 투영된 actor-actor 엣지 목록
            "stats": { "actors": N, "pivots": N, "projected_edges": N }
        }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body required"}), 400

        graph_path   = data.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
        actor_label  = data.get('actor_label', 'vt_psn')
        pivot_label  = data.get('pivot_label', 'vt_bacnt')
        min_shared   = int(data.get('min_shared', 1))
        proj_edge    = data.get('projection_edge') or f"co_{pivot_label.replace('vt_', '')}"

        # 입력 검증 — 허용된 레이블만 사용
        allowed_labels = {
            'vt_psn','vt_org','vt_case','vt_petition',
            'vt_bacnt','vt_crypto','vt_telno','vt_ip','vt_site',
            'vt_file','vt_id','vt_email','vt_vhcl','vt_dev','vt_atm',
            'vt_loc','vt_transfer','vt_call','vt_msg','vt_access',
            'vt_movement','vt_impersonation','vt_src'
        }
        if actor_label not in allowed_labels or pivot_label not in allowed_labels:
            return jsonify({"error": "Invalid label"}), 400
        if actor_label == pivot_label:
            return jsonify({"error": "actor_label and pivot_label must be different"}), 400

        # Cypher: 공유 pivot 노드를 통한 actor 쌍 조회
        # actor1 → pivot ← actor2  형태의 경로에서 actor 쌍 추출
        cypher = f"""
MATCH (a1:{actor_label})-[]-(pivot:{pivot_label})-[]-(a2:{actor_label})
WHERE id(a1) < id(a2)
WITH a1, a2, collect(DISTINCT pivot) AS shared_pivots
WHERE size(shared_pivots) >= {min_shared}
RETURN
    a1,
    a2,
    size(shared_pivots)   AS weight,
    [p IN shared_pivots | properties(p)][0..5] AS pivot_samples
ORDER BY weight DESC
LIMIT 200
"""
        success, rows = GraphService.execute_cypher(cypher, graph_path)

        if not success:
            return jsonify({"error": "Projection query failed", "detail": str(rows)}), 500

        # 노드 / 엣지 수집
        node_map = {}
        edges    = []

        for row in (rows or []):
            try:
                a1_data = dict(row[0]) if row[0] else {}
                a2_data = dict(row[1]) if row[1] else {}
                weight  = int(row[2]) if row[2] else 1
                pivots  = list(row[3]) if row[3] else []

                a1_id = a1_data.get('id') or str(id(tuple(sorted(a1_data.items()))))
                a2_id = a2_data.get('id') or str(id(tuple(sorted(a2_data.items()))))

                node_map[a1_id] = {"id": a1_id, "label": actor_label, **a1_data}
                node_map[a2_id] = {"id": a2_id, "label": actor_label, **a2_data}

                edges.append({
                    "source": a1_id,
                    "target": a2_id,
                    "type":   proj_edge,
                    "weight": weight,
                    "pivot_label": pivot_label,
                    "shared_samples": pivots[:3],
                })
            except Exception:
                continue

        nodes = list(node_map.values())

        return jsonify({
            "status": "success",
            "mode": "1mode",
            "actor_label": actor_label,
            "pivot_label": pivot_label,
            "projection_edge": proj_edge,
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "actors": len(nodes),
                "projected_edges": len(edges),
                "min_shared_filter": min_shared,
            }
        }), 200

    except Exception as e:
        current_app.logger.error(f"[API v1] network/project error: {e}")
        return jsonify({"error": "Projection failed", "detail": str(e)}), 500


@api_v1.route('/network/bipartite', methods=['POST'])
@require_api_or_ui
def network_bipartite_stats():
    """
    2-mode 이분 그래프 통계 — actor ↔ pivot 연결 분포

    Request:
        {
            "graph_path":   "tccop_graph_v6",
            "actor_label":  "vt_psn",
            "pivot_label":  "vt_bacnt"
        }

    Response:
        {
            "status": "success",
            "mode": "2mode",
            "actor_count": N,
            "pivot_count": N,
            "edge_count":  N,
            "top_actors":  [...],   // pivot 연결 수 Top 10 actor
            "top_pivots":  [...]    // actor 연결 수 Top 10 pivot
        }
    """
    try:
        data        = request.get_json() or {}
        graph_path  = data.get('graph_path', current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_graph_v6'))
        actor_label = data.get('actor_label', 'vt_psn')
        pivot_label = data.get('pivot_label', 'vt_bacnt')

        allowed = {
            'vt_psn','vt_org','vt_bacnt','vt_telno','vt_ip',
            'vt_site','vt_file','vt_id','vt_email','vt_dev','vt_atm'
        }
        if actor_label not in allowed or pivot_label not in allowed:
            return jsonify({"error": "Invalid label"}), 400

        # Actor degree 분포
        cypher_actors = f"""
MATCH (a:{actor_label})-[]-(p:{pivot_label})
WITH a, count(DISTINCT p) AS degree
RETURN properties(a) AS actor_props, degree
ORDER BY degree DESC LIMIT 10
"""
        # Pivot degree 분포
        cypher_pivots = f"""
MATCH (a:{actor_label})-[]-(p:{pivot_label})
WITH p, count(DISTINCT a) AS degree
RETURN properties(p) AS pivot_props, degree
ORDER BY degree DESC LIMIT 10
"""
        # 전체 카운트
        cypher_count = f"""
MATCH (a:{actor_label})-[]-(p:{pivot_label})
RETURN count(DISTINCT a) AS actors, count(DISTINCT p) AS pivots, count(*) AS edges
"""
        ok1, actors = GraphService.execute_cypher(cypher_actors, graph_path)
        ok2, pivots = GraphService.execute_cypher(cypher_pivots, graph_path)
        ok3, counts = GraphService.execute_cypher(cypher_count,  graph_path)

        count_row   = counts[0] if ok3 and counts else [0, 0, 0]

        return jsonify({
            "status":       "success",
            "mode":         "2mode",
            "actor_label":  actor_label,
            "pivot_label":  pivot_label,
            "actor_count":  int(count_row[0]) if count_row else 0,
            "pivot_count":  int(count_row[1]) if count_row else 0,
            "edge_count":   int(count_row[2]) if count_row else 0,
            "top_actors":   [{"props": dict(r[0]) if r[0] else {}, "degree": int(r[1])} for r in (actors or [])],
            "top_pivots":   [{"props": dict(r[0]) if r[0] else {}, "degree": int(r[1])} for r in (pivots or [])],
        }), 200

    except Exception as e:
        current_app.logger.error(f"[API v1] network/bipartite error: {e}")
        return jsonify({"error": "Bipartite stats failed", "detail": str(e)}), 500


# ============================================
# 10. Graph Management API
# ============================================

@api_v1.route('/graph/list', methods=['GET'])
@require_api_key
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
@require_api_key
@require_endpoint_permission('admin')
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
@require_api_key
@require_endpoint_permission('admin')
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

@api_v1.route('/graph/node/create', methods=['POST'])
@require_api_key
@require_endpoint_permission('admin')
def create_manual_node():
    """수동으로 그래프 노드 추가"""
    try:
        data = request.get_json()
        graph_name = data.get('graph_name')
        label = data.get('label')
        properties = data.get('properties', {})
        if not graph_name or not label:
            return jsonify({"status": "error", "message": "graph_name and label required"}), 400
        success, res = GraphService.create_manual_node(graph_name, label, properties)
        if success:
            return jsonify({"status": "success", "node_id": res}), 200
        else:
            return jsonify({"status": "error", "message": res}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@api_v1.route('/graph/edge/create', methods=['POST'])
@require_api_key
@require_endpoint_permission('admin')
def create_manual_edge():
    """수동으로 그래프 엣지 추가"""
    try:
        data = request.get_json()
        graph_name = data.get('graph_name')
        src_id = data.get('src_id')
        tgt_id = data.get('tgt_id')
        label = data.get('label')
        properties = data.get('properties', {})
        if not all([graph_name, src_id, tgt_id, label]):
            return jsonify({"status": "error", "message": "graph_name, src_id, tgt_id, label required"}), 400
        success, res = GraphService.create_manual_edge(graph_name, src_id, tgt_id, label, properties)
        if success:
            return jsonify({"status": "success", "edge_id": res}), 200
        else:
            return jsonify({"status": "error", "message": res}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@api_v1.route('/graph/element/delete', methods=['POST'])
@require_api_key
@require_endpoint_permission('admin')
def delete_manual_element():
    """수동으로 노드/엣지 삭제"""
    try:
        data = request.get_json()
        graph_name = data.get('graph_name')
        element_id = data.get('element_id')
        is_edge = data.get('is_edge', False)
        if not graph_name or not element_id:
            return jsonify({"status": "error", "message": "graph_name and element_id required"}), 400
        success, res = GraphService.delete_element(graph_name, element_id, is_edge)
        if success:
            return jsonify({"status": "success", "message": res}), 200
        else:
            return jsonify({"status": "error", "message": res}), 400
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
        
        # RDB 통계 (V2 표준화 테이블)
        rdb_v2_tables = {
            'cases': 'TB_INCDNT_MST',
            'suspects': 'TB_PRSN',
            'accounts': 'TB_FIN_BACNT',
            'phones': 'TB_TELNO_MST',
            'transfers': 'TB_FIN_BACNT_DLNG',
            'calls': 'TB_TELNO_CALL_DTL',
            'ips': 'TB_SYS_LGN_EVT',
            'reports': 'TB_FRD_VCTM_RPT',
            'orgs': 'TB_INST',
            'sms': 'TB_TELNO_SMS_MSG',
            'vehicles': 'TB_VHCL_MST',
            'locations': 'TB_GEO_MBL_LOC_EVT',
            'domains': 'TB_WEB_DMN',
            'files': 'TB_DGTL_FILE_INVNT',
        }
        for key, table in rdb_v2_tables.items():
            try:
                cur.execute(f"SELECT count(*) FROM {table}")
                stats["rdb"][key] = cur.fetchone()[0]
            except:
                conn.rollback()
                stats["rdb"][key] = 0
        
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
                from app.database import safe_set_graph_path
                safe_set_graph_path(cur, graph_name)
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
@require_api_or_ui
def gdb_detail_stats():
    """GDB 상세 통계: 노드 라벨별 수, 엣지 타입별 수"""
    import psycopg2
    try:
        graph_name = request.args.get('graph_name', 'test_ai01')
        
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        cur = conn.cursor()
        
        result = {"nodes": [], "edges": [], "total_nodes": 0, "total_edges": 0}
        
        try:
            from app.database import safe_set_graph_path
            safe_set_graph_path(cur, graph_name)
            
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
        {"name": "TB_INCDNT_MST", "label": "사건", "icon": "folder"},
        {"name": "TB_PRSN", "label": "인물", "icon": "user"},
        {"name": "TB_FIN_BACNT", "label": "계좌", "icon": "credit-card"},
        {"name": "TB_TELNO_MST", "label": "전화번호", "icon": "phone"},
        {"name": "TB_FIN_BACNT_DLNG", "label": "이체내역", "icon": "exchange-alt"},
        {"name": "TB_TELNO_CALL_DTL", "label": "통화내역", "icon": "phone-volume"},
        {"name": "TB_FRD_VCTM_RPT", "label": "사기신고", "icon": "exclamation-triangle"},
        {"name": "TB_INST", "label": "조직", "icon": "building"},
        {"name": "TB_SYS_LGN_EVT", "label": "IP접속", "icon": "globe"},
        {"name": "TB_TELNO_SMS_MSG", "label": "SMS", "icon": "envelope"},
        {"name": "TB_VHCL_MST", "label": "차량", "icon": "car"},
        {"name": "TB_GEO_MBL_LOC_EVT", "label": "위치", "icon": "map-marker-alt"},
    ]
    return jsonify({"status": "success", "tables": tables}), 200


@api_v1.route('/rdb/query/<table_name>', methods=['GET'])
def query_rdb_table(table_name):
    """RDB 테이블 데이터 조회"""
    import psycopg2
    
    # 허용된 테이블만 조회 (SQL Injection 방지) — V2 표준화
    allowed_tables = [
        'TB_INCDNT_MST', 'TB_PRSN', 'TB_FIN_BACNT', 'TB_TELNO_MST',
        'TB_FIN_BACNT_DLNG', 'TB_TELNO_CALL_DTL', 'TB_FRD_VCTM_RPT',
        'TB_INST', 'TB_SYS_LGN_EVT', 'TB_TELNO_SMS_MSG', 'TB_TELNO_JOIN',
        'TB_CHAT_MSG', 'TB_VHCL_MST', 'TB_VHCL_LPR_EVT', 'TB_GEO_MBL_LOC_EVT',
        'TB_WEB_DMN', 'TB_WEB_URL', 'TB_DGTL_FILE_INVNT',
    ]
    
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
        
        # 데이터 조회 (search 값은 파라미터 바인딩으로 SQL 인젝션 방지;
        # table_name 은 상단 화이트리스트, search_col 은 DB 스키마에서 유래한 식별자)
        params = []
        query = f"SELECT * FROM {table_name}"
        if search:
            # 첫 번째 텍스트 컬럼에서 검색
            search_col = columns[1] if len(columns) > 1 else columns[0]
            query += f" WHERE {search_col}::text ILIKE %s"
            params.append(f"%{search}%")
        query += " LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        cur.execute(query, params)
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


# ============================================
# V4.0 시각화 SSOT API (Phase 4.1)
# ============================================
# 프론트엔드가 ontology_service.py 의 VISUAL_STYLE_V40 / EDGE_STYLE_V40 /
# LAYOUT_PRESETS_V40 / INVESTIGATION_WORKFLOWS_V40 을 단일 출처(SSOT)로 참조하도록 노출

@api_v1.route('/visual-style', methods=['GET'])
@require_api_or_ui
def visual_style():
    """V4.0 노드 시각화 표준 (색상/모양/크기/아이콘) 전체 반환."""
    from app.services.ontology_service import KICSCrimeDomainOntology as Ont
    label = request.args.get('label')
    if label:
        return jsonify({"status": "success", "label": label,
                        "style": Ont.get_visual_style(label)}), 200
    return jsonify({"status": "success", "version": "v4.0",
                    "count": len(Ont.VISUAL_STYLE_V40),
                    "styles": Ont.VISUAL_STYLE_V40}), 200


@api_v1.route('/edge-style', methods=['GET'])
@require_api_or_ui
def edge_style():
    """V4.0 엣지 시각화 표준 (색상/굵기/화살표/선종류) 전체 반환."""
    from app.services.ontology_service import KICSCrimeDomainOntology as Ont
    edge = request.args.get('edge')
    if edge:
        return jsonify({"status": "success", "edge": edge,
                        "style": Ont.get_edge_style(edge)}), 200
    return jsonify({"status": "success", "version": "v4.0",
                    "count": len(Ont.EDGE_STYLE_V40),
                    "styles": Ont.EDGE_STYLE_V40}), 200


@api_v1.route('/layout-presets', methods=['GET'])
@require_api_or_ui
def layout_presets():
    """V4.0 그래프 레이아웃 프리셋 5종 반환."""
    from app.services.ontology_service import KICSCrimeDomainOntology as Ont
    name = request.args.get('name')
    if name:
        return jsonify({"status": "success", "name": name,
                        "preset": Ont.get_layout_preset(name)}), 200
    return jsonify({"status": "success", "version": "v4.0",
                    "count": len(Ont.LAYOUT_PRESETS_V40),
                    "presets": Ont.LAYOUT_PRESETS_V40}), 200


@api_v1.route('/workflows', methods=['GET'])
@require_api_or_ui
def investigation_workflows():
    """V4.0 수사 워크플로 6종 반환."""
    from app.services.ontology_service import KICSCrimeDomainOntology as Ont
    name = request.args.get('name')
    if name:
        return jsonify({"status": "success", "name": name,
                        "workflow": Ont.get_workflow(name)}), 200
    return jsonify({"status": "success", "version": "v4.0",
                    "count": len(Ont.INVESTIGATION_WORKFLOWS_V40),
                    "workflows": Ont.INVESTIGATION_WORKFLOWS_V40}), 200


@api_v1.route('/workflows/<name>/execute', methods=['GET'])
@require_api_or_ui
def execute_workflow(name):
    """V4.0 수사 워크플로우 실행 (Phase 4.4 실제 동작 패치).

    workflow name → 사전 정의된 Cypher 패턴을 현재 graph_path 에 실행하고
    Cytoscape 호환 elements (nodes + edges) 반환. /api/graph/load 와 동일 포맷.

    Query:
        graph_path (선택): 기본 'tccop_v40_demo'
        limit      (선택): 기본 200
    """
    import psycopg2 as _pg2
    from app.services.graph_service import GraphService
    from app.database import safe_set_graph_path

    graph_path = request.args.get('graph_path') or current_app.config.get('DEFAULT_GRAPH_PATH', 'tccop_v40_demo')
    limit = request.args.get('limit', 200, type=int)

    # 워크플로우 이름 → Cypher 매핑 (V4.0 SSOT 와 정합)
    WORKFLOWS_CYPHER = {
        'case_to_suspects':
            "MATCH (n:vt_case)<-[r:suspect_in]-(m:vt_psn) "
            "RETURN id(n), labels(n), properties(n), id(r), type(r), id(m), labels(m), properties(m)",
        'suspect_to_assets':
            "MATCH (n:vt_psn)-[r:has_account]->(m:vt_bacnt) "
            "RETURN id(n), labels(n), properties(n), id(r), type(r), id(m), labels(m), properties(m)",
        'phishing_campaign_view':
            "MATCH (n:site_cluster)<-[r:belongs_to_campaign]-(m:vt_site) "
            "RETURN id(n), labels(n), properties(n), id(r), type(r), id(m), labels(m), properties(m)",
        'fund_flow':
            "MATCH (n:vt_bacnt)-[r:from_account]->(m:vt_transfer) "
            "RETURN id(n), labels(n), properties(n), id(r), type(r), id(m), labels(m), properties(m) "
            "UNION ALL "
            "MATCH (n:vt_transfer)-[r:to_account]->(m:vt_bacnt) "
            "RETURN id(n), labels(n), properties(n), id(r), type(r), id(m), labels(m), properties(m)",
        'relay_station_network':
            "MATCH (n:vt_dev)<-[r:used_in_device]-(m:vt_telno) "
            "WHERE n.dev_type = 'relay_station' "
            "RETURN id(n), labels(n), properties(n), id(r), type(r), id(m), labels(m), properties(m)",
        'cross_graph_sameAs':
            "MATCH (n:vt_psn)-[r:sameAs]->(m:vt_psn) "
            "WHERE n.source_domain <> m.source_domain "
            "RETURN id(n), labels(n), properties(n), id(r), type(r), id(m), labels(m), properties(m)",
    }
    if name not in WORKFLOWS_CYPHER:
        return jsonify({"status": "error",
                        "message": f"Unknown workflow '{name}'. "
                                   f"Available: {sorted(WORKFLOWS_CYPHER.keys())}"}), 404

    cypher_inner = WORKFLOWS_CYPHER[name] + f" LIMIT {int(limit)}"

    try:
        conn = _pg2.connect(**current_app.config['DB_CONFIG'])
        conn.autocommit = True
        cur = conn.cursor()
    except Exception as e:
        return jsonify({"status": "error", "message": f"DB 연결 실패: {e}"}), 500

    elements = []
    node_ids = set()
    try:
        safe_set_graph_path(cur, graph_path)
        cur.execute(cypher_inner)
        rows = cur.fetchall()
        for r in rows:
            if len(r) < 8:
                continue
            n_id, n_labels, n_props, r_id, r_type, m_id, m_labels, m_props = r[:8]
            for vid, vlabels, vprops in [(n_id, n_labels, n_props), (m_id, m_labels, m_props)]:
                vid_s = str(vid)
                if vid_s in node_ids:
                    continue
                node_ids.add(vid_s)
                vlabel = vlabels[0] if isinstance(vlabels, list) and vlabels else str(vlabels)
                elements.append({
                    "group": "nodes",
                    "data": {
                        "id": vid_s,
                        "label": str(vlabel).replace('"', ''),
                        "props": GraphService.safe_props(vprops if isinstance(vprops, dict) else {}),
                    }
                })
            elements.append({
                "group": "edges",
                "data": {
                    "id": str(r_id),
                    "source": str(n_id),
                    "target": str(m_id),
                    "label": str(r_type).replace('"', '') if r_type else "관계",
                    "props": {},
                }
            })
        return jsonify({"status": "success", "workflow": name,
                        "graph_path": graph_path,
                        "node_count": len(node_ids),
                        "edge_count": len(elements) - len(node_ids),
                        "elements": elements}), 200
    except Exception as e:
        return jsonify({"status": "error", "workflow": name,
                        "message": str(e), "elements": []}), 500
    finally:
        try: cur.close()
        except: pass
        try: conn.close()
        except: pass


@api_v1.route('/ontology/meta', methods=['GET'])
def ontology_meta():
    """V4.0 온톨로지 메타 (NODE_ID_STANDARD / DOMAIN_USAGE / INFERENCE_RULES_V37) 통합 반환."""
    from app.services.ontology_service import KICSCrimeDomainOntology as Ont
    return jsonify({
        "status": "success",
        "version": "v4.0",
        "node_id_standard": getattr(Ont, 'NODE_ID_STANDARD', {}),
        "domain_usage": getattr(Ont, 'DOMAIN_USAGE', {}),
        "inference_rules": getattr(Ont, 'INFERENCE_RULES_V37', {}),
    }), 200


# ============================================================
# V4.0 L1→L5 통합 파이프라인 API (학습 진행 중 신규)
# ============================================================
@api_v1.route('/pipeline/csv_to_v40_graph', methods=['POST'])
@require_api_or_ui
def pipeline_csv_to_v40_graph():
    """L1(CSV 업로드) → L2(test_v40 RDB 적재) → L3(매핑) → L4(그래프) → L5(시각화) 통합 실행.

    multipart/form-data:
        file:           CSV 파일 (1개 또는 여러개 — 각 파일은 tbl_* 형식 권장)
        graph_name:     생성할 그래프 이름 (예: my_pipeline_demo)
        source_domain:  KICS / OSINT / DIGITAL / EXT (기본 KICS)
        source_id:      (선택) 원천 시스템 레코드 ID

    반환:
        각 계층별 결과 + 통계 + 다음 행동 안내
    """
    import os, time
    from app.services.rdb_service import RDBService
    from app.services.rdb_to_graph_service import RdbToGraphService
    from app.database import safe_set_graph_path
    import psycopg2 as _pg2

    t0 = time.time()
    layer_results = {}

    # ─── L1. CSV 수신 ───────────────────────────────────────
    if 'file' not in request.files and 'files' not in request.files:
        return jsonify({"status": "error", "message": "CSV 파일이 필요합니다 (file 또는 files)"}), 400
    files = request.files.getlist('files') or [request.files['file']]
    graph_name = (request.form.get('graph_name') or 'v40_pipeline_demo').strip()
    source_domain = (request.form.get('source_domain') or 'KICS').upper()
    source_id = request.form.get('source_id') or None

    if source_domain not in {'KICS', 'OSINT', 'DIGITAL', 'EXT',
                              'INVESTIGATION', 'PARTNER', 'INFERENCE'}:
        return jsonify({"status": "error", "message": f"Invalid source_domain: {source_domain}"}), 400

    layer_results['L1'] = {
        'layer': 'L1 수집',
        'files': [],
        'total_rows': 0,
    }
    temp_paths = []
    try:
        from werkzeug.utils import secure_filename
        for f in files:
            if not f or not f.filename: continue
            # secure_filename: 업로드 파일명 경로조작 방지 (라우팅용 원본명은 별도 유지)
            safe_name = secure_filename(f.filename) or f"upload_{int(time.time() * 1000)}.csv"
            temp_path = f"/tmp/{safe_name}"
            f.save(temp_path)
            temp_paths.append((temp_path, f.filename))
            # 행수 카운트
            try:
                with open(temp_path) as fp:
                    row_count = sum(1 for _ in fp) - 1
            except Exception: row_count = -1
            layer_results['L1']['files'].append({'name': f.filename, 'rows': row_count})
            if row_count > 0: layer_results['L1']['total_rows'] += row_count

        # ─── L2. test_v40 RDB 적재 ─────────────────────────
        target_schema = 'test_v40'
        current_app.config['_V40_TARGET_SCHEMA'] = target_schema
        # fresh=1(기본): 첫 파일 적재 전 test_v40 스테이징 초기화 → 이 업로드분만으로 그래프 구성.
        #   여러 파일이면 첫 파일만 clear, 이후 파일은 누적. fresh=0이면 기존 스테이징에 누적.
        fresh = (request.form.get('fresh', '1') != '0')
        layer_results['L2'] = {'layer': 'L2 표준화 (test_v40 RDB)', 'tables': {}, 'total_inserted': 0, 'fresh': fresh}

        for _idx, (temp_path, fname) in enumerate(temp_paths):
            clear_now = fresh and _idx == 0   # 첫 파일에서만 초기화
            try:
                if fname.lower().startswith('tbl_'):
                    success, result = RDBService.import_predefined_schema_to_rdb(
                        temp_path, fname, clear_existing=clear_now,
                        source_domain=source_domain, source_id=source_id,
                    )
                else:
                    # P0-1(silent data loss 방지): 비-tbl_ 파일은 import_csv_to_rdb가 public 스키마에
                    # 적재되어 test_v40 그래프 파이프라인(transfer_data)에 도달하지 않는다.
                    # 조용히 사라지지 않도록 명시적 경고를 결과에 포함(사용자가 그래프 미변환을 인지).
                    current_app.logger.warning(
                        f"L2: '{fname}'은 tbl_* 고정스키마 형식이 아님 → public 적재(그래프 미변환)")
                    layer_results['L2'].setdefault('warnings', []).append(
                        f"'{fname}': tbl_* 형식이 아니어서 그래프에 반영되지 않습니다(public 적재만 됨). "
                        f"그래프 변환은 tbl_ 접두 고정스키마 CSV를 사용하세요.")
                    success, result = RDBService.import_csv_to_rdb(
                        temp_path, clear_existing=clear_now,
                        source_domain=source_domain, source_id=source_id,
                    )
                if success:
                    for k, v in (result.items() if isinstance(result, dict) else []):
                        if isinstance(v, int) and v > 0:
                            layer_results['L2']['tables'][k] = layer_results['L2']['tables'].get(k, 0) + v
                            layer_results['L2']['total_inserted'] += v
            except Exception as e:
                current_app.logger.warning(f"L2 적재 실패 {fname}: {e}")

        # 적재 후 test_v40 실제 row count 직접 검증 (정확한 통계)
        try:
            verify_conn = _pg2.connect(**current_app.config['DB_CONFIG'])
            verify_conn.autocommit = True
            verify_cur = verify_conn.cursor()
            l2_actual = {}
            for tbl in ['tb_prsn','tb_fin_bacnt','tb_telno_mst','tb_fin_bacnt_dlng',
                        'tb_telno_call_dtl','tb_fin_extrc_bacnt','tb_telno_join',
                        'tb_incdnt_mst','tb_inst']:
                try:
                    verify_cur.execute(f'SELECT COUNT(*) FROM test_v40."{tbl}";')
                    cnt = verify_cur.fetchone()[0]
                    if cnt > 0: l2_actual[tbl] = cnt
                except Exception: pass
            verify_cur.close(); verify_conn.close()
            if l2_actual:
                layer_results['L2']['rdb_actual'] = l2_actual
                layer_results['L2']['rdb_actual_total'] = sum(l2_actual.values())
        except Exception as e:
            current_app.logger.warning(f"L2 verify 실패: {e}")

        # ─── L3. 매핑 카탈로그 (V4.0 SSOT 참조) ────────────
        from app.services.ontology_service import KICSCrimeDomainOntology as Ont
        # 적재된 RDB 테이블 → V4.0 노드/엣지 라벨 매핑 카탈로그
        L2_TO_V40 = {
            'cases': 'vt_case', 'suspects': 'vt_psn', 'accounts': 'vt_bacnt',
            'phones': 'vt_telno', 'transfers': 'vt_transfer', 'calls': 'vt_call',
        }
        v40_labels = sorted(set(L2_TO_V40[k] for k in layer_results['L2']['tables']
                                 if k in L2_TO_V40))
        layer_results['L3'] = {
            'layer': 'L3 매핑 (V4.0 SSOT)',
            'expected_v40_labels': v40_labels,
            'visual_style_count': len(Ont.VISUAL_STYLE_V40),
            'edge_style_count': len(Ont.EDGE_STYLE_V40),
            'meta_columns': ['id_format', 'source_domain', 'reliability_tier',
                              'source_id', 'collected_at', 'rec_created'],
        }

        # ─── L4. 그래프 변환 ─────────────────────────────
        layer_results['L4'] = {'layer': 'L4 그래프 (AgensGraph)', 'graph': graph_name}
        try:
            success, stats = RdbToGraphService.transfer_data(graph_name)
            if success and isinstance(stats, dict):
                layer_results['L4'].update({
                    'success': True,
                    'nodes_total': stats.get('nodes', 0),
                    'edges_total': stats.get('edges', 0),
                    'cases': stats.get('cases', 0),
                    'persons': stats.get('persons', 0),
                    'accounts': stats.get('accounts', 0),
                    'phones': stats.get('phones', 0),
                    'transfers': stats.get('transfers', 0),
                    'calls': stats.get('calls', 0),
                    'relations': stats.get('relations', 0),
                })
            else:
                layer_results['L4']['success'] = False
                layer_results['L4']['error'] = str(stats)[:200]
        except Exception as e:
            layer_results['L4']['success'] = False
            layer_results['L4']['error'] = str(e)[:200]

        # ─── L5. 시각화 안내 ─────────────────────────────
        layer_results['L5'] = {
            'layer': 'L5 시각화 (Cytoscape)',
            'graph_url': f'/?graph={graph_name}',
            'recommendations': [
                f'그래프 셀렉터에서 "{graph_name}" 선택',
                '자연어 질의: "사건의 피의자 보여줘"',
                '워크플로우 6종 + 레이아웃 5종 시연 가능',
            ],
        }

    finally:
        for tp, _ in temp_paths:
            if os.path.exists(tp):
                try: os.remove(tp)
                except: pass

    elapsed = time.time() - t0
    return jsonify({
        'status': 'success',
        'pipeline': 'V4.0 L1→L5',
        'graph_name': graph_name,
        'source_domain': source_domain,
        'target_schema': 'test_v40',
        'elapsed_sec': round(elapsed, 2),
        'layers': layer_results,
    }), 200


# ============================================
# 12. Legal RAG API (법률 근거 검색·자문) — v2 재구축
#     hybrid(BM25+Vector) + RRF + LLM rerank. 설계: docs/LEGAL_RAG_V2_DESIGN.md
# ============================================

@api_v1.route('/legal/search', methods=['POST'])
@require_api_key
def legal_search():
    """
    법률 근거 하이브리드 검색 (답변 생성 없음 — 검색 품질 디버깅/평가용 점수 분해 포함)

    Request:  {"question": "대포통장 양도 처벌", "top_k": 5, "mode": "hybrid", "rerank": true}
    Response: {"status": "success", "mode_used": ..., "rerank_used": ..., "results": [...]}
    """
    from app.services.legal_rag_service import LegalRAGService
    try:
        data = request.get_json(silent=True) or {}
        question = (data.get('question') or '').strip()
        if not question:
            return jsonify({"error": "question field is required"}), 400
        if len(question) > 2000:
            return jsonify({"error": "question too long (max 2000 chars)"}), 400
        try:
            top_k = max(1, min(20, int(data.get('top_k', 5))))
        except (TypeError, ValueError):
            return jsonify({"error": "top_k must be an integer"}), 400
        mode = data.get('mode', 'hybrid')
        if mode not in ('hybrid', 'bm25', 'vector'):
            return jsonify({"error": "mode must be one of: hybrid, bm25, vector"}), 400
        rerank = data.get('rerank')
        if rerank is not None and not isinstance(rerank, bool):
            return jsonify({"error": "rerank must be a boolean"}), 400

        t0 = time.time()
        result = LegalRAGService.hybrid_search(question, top_k=top_k, mode=mode, rerank=rerank)
        current_app.logger.info(
            f"[API v1] legal/search | partner={request.partner} | mode={result['mode_used']} | "
            f"hits={len(result['results'])} | {(time.time() - t0) * 1000:.0f}ms")
        return jsonify({"status": "success", **result}), 200
    except Exception as e:
        current_app.logger.error(f"[API v1] legal/search error: {e}")
        return jsonify({"error": "internal error", "detail": str(e)}), 500


@api_v1.route('/legal/answer', methods=['POST'])
@require_api_key
def legal_answer():
    """
    법률 근거 기반 자문 답변 (근거 인용 [n] + 비자문 고지 포함)

    Request:  {"question": "인출책 처벌 수위는?", "top_k": 4}
    Response: {"status": "success", "success": bool, "answer": ..., "citations": [...]}
    """
    from app.services.legal_rag_service import LegalRAGService
    try:
        data = request.get_json(silent=True) or {}
        question = (data.get('question') or '').strip()
        if not question:
            return jsonify({"error": "question field is required"}), 400
        if len(question) > 2000:
            return jsonify({"error": "question too long (max 2000 chars)"}), 400
        try:
            top_k = max(1, min(10, int(data.get('top_k', 4))))
        except (TypeError, ValueError):
            return jsonify({"error": "top_k must be an integer"}), 400

        t0 = time.time()
        result = LegalRAGService.answer(question, top_k=top_k)
        current_app.logger.info(
            f"[API v1] legal/answer | partner={request.partner} | success={result['success']} | "
            f"{(time.time() - t0) * 1000:.0f}ms")
        return jsonify({"status": "success", **result}), 200
    except Exception as e:
        current_app.logger.error(f"[API v1] legal/answer error: {e}")
        return jsonify({"error": "internal error", "detail": str(e)}), 500


@api_v1.route('/legal/status', methods=['GET'])
@require_api_key
def legal_status():
    """법률 RAG 상태 (인덱스/임베딩 백엔드/DB 적재 현황) — 운영 점검용"""
    from app.services.legal_rag_service import LegalRAGService
    try:
        return jsonify({"status": "success", **LegalRAGService.status()}), 200
    except Exception as e:
        current_app.logger.error(f"[API v1] legal/status error: {e}")
        return jsonify({"error": "internal error", "detail": str(e)}), 500
