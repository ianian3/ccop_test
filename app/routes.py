# app/routes.py
from flask import Blueprint, render_template, request, jsonify
import json

# [서비스 모듈들 Import]
from app.services.ai_service import AIService
from app.services.etl_service import ETLService
from app.services.graph_service import GraphService
from app.services.subgraph_service import SubGraphService
from app.services.legal_rag_service import LegalRAGService
from app.services.rdb_to_graph_service import RdbToGraphService

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
    graph_path = data.get('graph_path', '').strip()
    
    if not graph_path: return jsonify({"status": "error", "message": "그래프 이름 없음"}), 400
    
    # 보안: 그래프 이름 유효성 검사
    import re
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', graph_path):
        return jsonify({"status": "error", "message": "유효하지 않은 그래프 이름입니다."}), 400
    
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
    
    # 보안: 그래프 이름 유효성 검사
    import re
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*$', graph_name):
        return jsonify({"status": "error", "message": "유효하지 않은 그래프 이름입니다."}), 400
    
    success, msg = GraphService.delete_graph(graph_name)
    if success:
        return jsonify({"status": "success", "message": msg})
    else:
        return jsonify({"status": "error", "message": msg}), 500

@bp.route('/api/graph/load', methods=['GET'])
def load_graph_data():
    """선택된 그래프의 전체 노드/엣지 로드 (최대 300 노드)"""
    graph_path = request.args.get('graph_path', 'demo_tst1')
    limit = request.args.get('limit', 300, type=int)
    
    conn, cur = GraphService.get_db_connection()
    if not conn:
        return jsonify([])
    
    try:
        elements = []
        node_ids = set()
        
        # 1. 모든 vertex 라벨 테이블 찾기
        cur.execute(f"""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = '{graph_path}' 
              AND table_name LIKE 'vt_%'
        """)
        vertex_tables = [r[0] for r in cur.fetchall()]
        
        if not vertex_tables:
            conn.close()
            return jsonify([])
        
        # 2. 각 테이블에서 노드 가져오기
        per_table_limit = max(limit // len(vertex_tables), 10)
        
        for table_name in vertex_tables:
            try:
                cur.execute(f"""
                    SELECT id, properties 
                    FROM "{graph_path}"."{table_name}"
                    LIMIT {per_table_limit}
                """)
                for r in cur.fetchall():
                    node_id = str(r[0])
                    props = r[1] if isinstance(r[1], dict) else {}
                    node_ids.add(node_id)
                    elements.append({
                        "group": "nodes",
                        "data": {"id": node_id, "label": table_name, "props": props}
                    })
            except Exception as e:
                print(f"Load error in {table_name}: {e}")
                continue
        
        # 3. 엣지 찾기
        if node_ids:
            try:
                cur.execute(f"""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = '{graph_path}' 
                      AND table_name NOT LIKE 'vt_%'
                      AND table_name != 'ag_label'
                      AND table_name != 'ag_vertex'
                """)
                edge_tables = [r[0] for r in cur.fetchall()]
                node_id_list = ','.join([f"'{nid}'" for nid in node_ids])
                
                for edge_table in edge_tables:
                    try:
                        cur.execute(f"""
                            SELECT e.id, e.start, e."end", e.properties
                            FROM "{graph_path}"."{edge_table}" e
                            WHERE e.start IN ({node_id_list}) AND e."end" IN ({node_id_list})
                            LIMIT 500
                        """)
                        for edge_row in cur.fetchall():
                            edge_id = str(edge_row[0])
                            src_id = str(edge_row[1])
                            tgt_id = str(edge_row[2])
                            edge_props = edge_row[3] if isinstance(edge_row[3], dict) else {}
                            elements.append({
                                "group": "edges",
                                "data": {
                                    "id": edge_id,
                                    "source": src_id,
                                    "target": tgt_id,
                                    "label": edge_table,
                                    "props": edge_props
                                }
                            })
                    except Exception as e:
                        continue
            except Exception as e:
                print(f"Edge load error: {e}")
        
        conn.close()
        return jsonify(elements)
        
    except Exception as e:
        conn.close()
        return jsonify([])

@bp.route('/api/search', methods=['GET'])
def search_node():
    keyword = request.args.get('keyword', '').strip()
    graph_path = request.args.get('graph_path', 'demo_tst1')
    
    # 서비스 호출
    elements = GraphService.search_nodes(keyword, graph_path)
    return jsonify(elements)

@bp.route('/api/expand', methods=['GET'])
def expand_node():
    # 'id' 또는 'node_id' 둘 다 지원
    node_id = request.args.get('id') or request.args.get('node_id')
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

# ------------------------------
# 2.1 N-depth 다단계 추적 API
# ------------------------------
@bp.route('/api/expand/multi', methods=['GET'])
def multi_hop_expand():
    """N-hop 다단계 확장"""
    node_id = request.args.get('id') or request.args.get('node_id')
    depth = request.args.get('depth', 2, type=int)
    graph_path = request.args.get('graph_path', 'demo_tst1')
    
    if not node_id:
        return jsonify({"error": "node id required"}), 400
    
    result = GraphService.multi_hop_expand(node_id, depth, graph_path)
    return jsonify(result)

@bp.route('/api/network/accomplice', methods=['GET'])
def accomplice_network():
    """공범 네트워크 조회"""
    node_id = request.args.get('id') or request.args.get('node_id')
    graph_path = request.args.get('graph_path', 'demo_tst1')
    
    if not node_id:
        return jsonify({"error": "node id required"}), 400
    
    result = GraphService.find_accomplice_network(node_id, graph_path)
    return jsonify(result)

@bp.route('/api/network/hubs', methods=['GET'])
def hub_nodes():
    """허브 노드 탐지"""
    graph_path = request.args.get('graph_path', 'demo_tst1')
    top_n = request.args.get('top_n', 10, type=int)
    
    hubs = GraphService.find_hub_nodes(graph_path, top_n)
    return jsonify({"hubs": hubs})

# ------------------------------
# 2.5 RDB → GDB 온톨로지 기반 변환
# ------------------------------
@bp.route('/api/rdb/to-graph', methods=['POST'])
def rdb_to_graph():
    """RDB 데이터를 KICS 온톨로지 기반으로 GDB에 변환"""
    try:
        data = request.get_json() or {}
        graph_name = data.get('graph_name', 'test_ai01')
        
        success, stats = RdbToGraphService.transfer_data(graph_name)
        
        if success:
            return jsonify({
                "status": "success",
                "message": "RDB → GDB 온톨로지 기반 변환 완료",
                "stats": stats
            })
        else:
            return jsonify({
                "status": "error",
                "message": str(stats)
            }), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/rdb/conversion-preview', methods=['GET'])
def rdb_conversion_preview():
    """변환 전 미리보기 (각 테이블의 레코드 수 확인)"""
    try:
        preview = RdbToGraphService.get_conversion_preview()
        if preview:
            return jsonify({"status": "success", "preview": preview})
        else:
            return jsonify({"status": "error", "message": "미리보기 생성 실패"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# DB 정보 조회
@bp.route('/api/db/info', methods=['GET'])
def db_info():
    """현재 접속 DB 정보 반환"""
    try:
        from flask import current_app
        import psycopg2
        cfg = current_app.config['DB_CONFIG']
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        cur.execute('SELECT current_database(), version()')
        db_name, version = cur.fetchone()
        
        # RDB 테이블 목록 + 건수
        tables = {}
        rdb_tables = ['rdb_cases', 'rdb_suspects', 'rdb_accounts', 'rdb_phones', 
                       'rdb_transfers', 'rdb_calls', 'rdb_relations', 'rdb_ips']
        for t in rdb_tables:
            try:
                cur.execute(f'SELECT count(*) FROM {t}')
                tables[t] = cur.fetchone()[0]
            except:
                conn.rollback()
                tables[t] = -1  # 테이블 없음
        
        # 그래프 목록
        cur.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT IN ('pg_catalog','information_schema','public','ag_catalog','pg_toast') AND nspname NOT LIKE 'pg_temp%' AND nspname NOT LIKE 'pg_toast_temp%' ORDER BY nspname")
        graphs = [r[0] for r in cur.fetchall()]
        
        conn.close()
        return jsonify({
            "status": "success",
            "db_name": db_name,
            "host": cfg.get("host", ""),
            "port": cfg.get("port", ""),
            "version": version[:60] if version else "",
            "rdb_tables": tables,
            "graphs": graphs
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# DB 목록 조회
@bp.route('/api/db/list', methods=['GET'])
def db_list():
    """서버의 전체 데이터베이스 목록 반환"""
    try:
        from flask import current_app
        import psycopg2
        cfg = current_app.config['DB_CONFIG']
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        
        cur.execute("SELECT datname FROM pg_database WHERE datistemplate = false AND datname NOT IN ('postgres', 'agens') ORDER BY datname")
        databases = [r[0] for r in cur.fetchall()]
        current_db = cfg.get('dbname', '')
        
        conn.close()
        return jsonify({
            "status": "success",
            "databases": databases,
            "current": current_db,
            "host": cfg.get("host", ""),
            "port": cfg.get("port", "")
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# DB 전환
@bp.route('/api/db/switch', methods=['POST'])
def db_switch():
    """활성 데이터베이스 전환 (런타임)"""
    try:
        from flask import current_app
        import psycopg2
        data = request.get_json()
        target_db = data.get('db_name', '')
        
        if not target_db:
            return jsonify({"status": "error", "message": "db_name 필요"}), 400
        
        cfg = current_app.config['DB_CONFIG']
        old_db = cfg.get('dbname', '')
        
        # 연결 테스트
        test_cfg = dict(cfg)
        test_cfg['dbname'] = target_db
        try:
            test_conn = psycopg2.connect(**test_cfg)
            test_cur = test_conn.cursor()
            test_cur.execute('SELECT current_database()')
            confirmed = test_cur.fetchone()[0]
            
            # RDB 테이블 존재 여부
            rdb_tables = {}
            for t in ['rdb_cases', 'rdb_suspects', 'rdb_accounts', 'rdb_phones', 'rdb_transfers', 'rdb_calls', 'rdb_relations']:
                try:
                    test_cur.execute(f'SELECT count(*) FROM {t}')
                    rdb_tables[t] = test_cur.fetchone()[0]
                except:
                    test_conn.rollback()
                    rdb_tables[t] = -1
            
            # 그래프 목록
            test_cur.execute("SELECT nspname FROM pg_namespace WHERE nspname NOT IN ('pg_catalog','information_schema','public','ag_catalog','pg_toast') AND nspname NOT LIKE 'pg_temp%' AND nspname NOT LIKE 'pg_toast_temp%' ORDER BY nspname")
            graphs = [r[0] for r in test_cur.fetchall()]
            
            test_conn.close()
        except Exception as e:
            return jsonify({"status": "error", "message": f"DB 연결 실패: {target_db} — {str(e)}"}), 400
        
        # 전환 실행
        cfg['dbname'] = target_db
        current_app.config['DB_CONFIG'] = cfg
        
        return jsonify({
            "status": "success",
            "message": f"DB 전환 완료: {old_db} → {target_db}",
            "db_name": confirmed,
            "rdb_tables": rdb_tables,
            "graphs": graphs
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/rdb/browse', methods=['GET'])
def rdb_browse():
    """RDB 테이블 데이터 조회 (페이징)"""
    try:
        from flask import current_app
        import psycopg2
        
        table = request.args.get('table', 'rdb_cases')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit
        
        # 보안: rdb_ 접두사 테이블만 허용
        if not table.startswith('rdb_'):
            return jsonify({"status": "error", "message": "rdb_ 테이블만 조회 가능"}), 400
        
        cfg = current_app.config['DB_CONFIG']
        conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        
        # 총 건수
        cur.execute(f'SELECT count(*) FROM {table}')
        total = cur.fetchone()[0]
        
        # 컬럼 정보
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{table}' ORDER BY ordinal_position")
        columns = [{"name": r[0], "type": r[1]} for r in cur.fetchall()]
        col_names = [c["name"] for c in columns]
        
        # 데이터 조회
        cur.execute(f'SELECT * FROM {table} ORDER BY 1 LIMIT {limit} OFFSET {offset}')
        rows = []
        for r in cur.fetchall():
            row = {}
            for i, val in enumerate(r):
                row[col_names[i]] = str(val) if val is not None else None
            rows.append(row)
        
        conn.close()
        return jsonify({
            "status": "success",
            "table": table,
            "columns": columns,
            "rows": rows,
            "total": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if limit > 0 else 0
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# ------------------------------
# 3. AI 관련 기능 (RAG, Query) -> AIService + GraphService 협업
# ------------------------------
@bp.route('/api/query/ai', methods=['POST'])
def query_ai():
    data = request.get_json()
    question = data.get('question')
    graph_path = data.get('graph_path', 'demo_tst1')

    # [Update] AI가 생성한 Cypher 쿼리 사용 (표준 코드 지원)
    cypher_query = AIService.generate_cypher(question)
    
    if not cypher_query:
        return jsonify({"error": "Failed to generate query"}), 500
        
    success, elements = GraphService.execute_cypher(cypher_query, graph_path)
    
    if not success:
        return jsonify({"error": str(elements)}), 500
        
    return jsonify({"elements": elements, "cypher": cypher_query})

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

@bp.route('/api/rdb/import', methods=['POST'])
def rdb_import():
    """CSV 파일을 RDB 테이블에 적재"""
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400
        
        file = request.files['file']
        
        # 임시 파일 저장 (RDBService가 파일 경로를 요구함)
        import os
        from app.services.rdb_service import RDBService
        
        temp_path = f"/tmp/{file.filename}"
        file.save(temp_path)
        
        try:
            success, result = RDBService.import_csv_to_rdb(temp_path)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        if success:
            return jsonify({
                "status": "success", 
                "stats": result,
                "message": f"RDB 적재 완료! (사건 {result['cases']}건, 피의자 {result['suspects']}명)"
            })
        else:
            return jsonify({"status": "error", "message": result}), 500
            
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


# ------------------------------
# 6. LegalGraphRAG - 그래프 맥락 기반 법률 자문 (Phase 2)
# ------------------------------
@bp.route('/api/legal/graph-query', methods=['POST'])
def legal_graph_query():
    """
    그래프 맥락 기반 법률 질의 (LegalGraphRAG)
    
    Request:
        {
            "question": "이 사건에서 기소에 필요한 증거는?",
            "case_id": "2024-001",
            "graph_path": "demo_tst1"  (선택)
        }
    
    Response:
        {
            "status": "success",
            "answer": "맥락 반영 법률 자문...",
            "case_context": {...},
            "evidence_analysis": {...},
            "prosecution_readiness": {...}
        }
    """
    try:
        data = request.get_json()
        
        question = data.get('question', '').strip()
        case_id = data.get('case_id', '').strip()
        graph_path = data.get('graph_path', 'demo_tst1')
        
        if not question:
            return jsonify({
                "status": "error", 
                "message": "질문을 입력해주세요."
            }), 400
        
        if not case_id:
            return jsonify({
                "status": "error", 
                "message": "사건번호(case_id)가 필요합니다."
            }), 400
        
        # LegalGraphRAG 호출
        result = LegalRAGService.query_with_context(
            question=question,
            case_id=case_id,
            graph_path=graph_path
        )
        
        if result.get('success'):
            return jsonify({
                "status": "success",
                **result
            })
        else:
            return jsonify({
                "status": "error",
                "message": result.get('answer', '분석 중 오류 발생')
            }), 500
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e)
        }), 500


# ------------------------------
# 7. 시스템 모니터링 (Hybrid DB Monitoring)
# ------------------------------
@bp.route('/api/admin/monitoring', methods=['GET'])
def admin_monitoring():
    """시스템 전체 모니터링 데이터 반환"""
    try:
        from app.services.monitoring_service import MonitoringService
        stats = MonitoringService.get_all_stats()
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
