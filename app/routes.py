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
from app.services.langgraph_agent import LangGraphAgent
import logging

logger = logging.getLogger(__name__)

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

@bp.route('/api/graph/node/create', methods=['POST'])
def create_manual_node():
    """수동으로 그래프 노드 추가"""
    try:
        data = request.get_json()
        graph_name = data.get('graph_name')
        label = data.get('label')
        properties = data.get('properties') or data.get('props', {})
        if not graph_name or not label:
            return jsonify({"status": "error", "message": "graph_name and label required"}), 400
        success, res = GraphService.create_manual_node(graph_name, label, properties)
        if success:
            return jsonify({"status": "success", "node_id": res}), 200
        else:
            return jsonify({"status": "error", "message": res}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/graph/edge/create', methods=['POST'])
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

@bp.route('/api/graph/element/delete', methods=['POST'])
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


@bp.route('/api/graph/load', methods=['GET'])
def load_graph_data():
    """선택된 그래프의 전체 노드/엣지 동기식 로드 (최대 N 건)"""
    graph_path = request.args.get('graph_path', 'demo_tst1')
    limit = request.args.get('limit', 300, type=int)
    
    # [Fix] psycopg2가 AgensGraph Vertex/Edge 객체를 직렬화 못하는 문제 해결.
    # RETURN n, r, m → 0 rows 리턴됨 (psycopg2 직렬화 실패)
    # RETURN id(n), labels(n), properties(n), type(r), id(m), labels(m), properties(m) → 정상 리턴
    # 따라서 명시적 컬럼 추출 방식으로 변경하고, 직접 Cytoscape 포맷으로 조립.
    
    from app.services.graph_service import get_db_connection, GraphService
    from app.database import safe_set_graph_path
    conn, cur = get_db_connection()
    if not conn:
        return jsonify([])
    
    elements = []
    node_ids = set()
    edge_counter = 0
    
    try:
        conn.autocommit = False
        safe_set_graph_path(cur, graph_path)
        
        cypher_query = f"""
            MATCH (n)-[r]->(m) 
            RETURN id(n), labels(n), properties(n), id(r), type(r), id(m), labels(m), properties(m) 
            LIMIT {limit}
        """
        logger.info(f"▶ [GraphLoad] 실행 Cypher: {cypher_query.strip()}")
        cur.execute(cypher_query)
        rows = cur.fetchall()
        
        for r in rows:
            if len(r) < 8:
                continue
            
            n_id, n_labels, n_props, r_id, r_type, m_id, m_labels, m_props = r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7]
            
            # 노드 n 추가
            n_id_str = str(n_id)
            if n_id_str not in node_ids:
                node_ids.add(n_id_str)
                n_label = n_labels[0] if isinstance(n_labels, list) and n_labels else str(n_labels)
                elements.append({
                    "group": "nodes",
                    "data": {
                        "id": n_id_str,
                        "label": str(n_label).replace('"', ''),
                        "props": GraphService.safe_props(n_props if isinstance(n_props, dict) else {})
                    }
                })
            
            # 노드 m 추가
            m_id_str = str(m_id)
            if m_id_str not in node_ids:
                node_ids.add(m_id_str)
                m_label = m_labels[0] if isinstance(m_labels, list) and m_labels else str(m_labels)
                elements.append({
                    "group": "nodes",
                    "data": {
                        "id": m_id_str,
                        "label": str(m_label).replace('"', ''),
                        "props": GraphService.safe_props(m_props if isinstance(m_props, dict) else {})
                    }
                })
            
            # 엣지 추가 (n → m)
            edge_id = str(r_id)
            elements.append({
                "group": "edges",
                "data": {
                    "id": edge_id,
                    "source": n_id_str,
                    "target": m_id_str,
                    "label": str(r_type).replace('"', '') if r_type else "관계",
                    "props": {}
                }
            })
        
        return jsonify(elements)
        
    except Exception as e:
        logger.error(f"[GraphLoad Error] {e}")
        return jsonify([])
    finally:
        conn.close()

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

# ============================
# 2.6 Multi-RDB 소스 관리
# ============================
# 등록된 RDB 소스 저장 (in-memory, 서버 재시작 시 초기화)
rdb_sources = {}

def _init_default_rdb_source(app):
    """앱 시작 시 기본 DB를 rdb_sources에 등록"""
    import os
    cfg = app.config.get('DB_CONFIG', {})
    # DB_CONFIG에 host가 있으면 사용, 없으면 환경변수에서 직접 읽기
    host = cfg.get('host') or os.environ.get('DB_HOST', '49.50.128.28')
    port = cfg.get('port') or os.environ.get('DB_PORT', '5333')
    dbname = cfg.get('dbname') or os.environ.get('DB_NAME', 'tccopdb')
    user = cfg.get('user') or os.environ.get('DB_USER', 'ccop')
    password = cfg.get('password') or os.environ.get('DB_PASSWORD', 'Ccop@2025')
    
    rdb_sources['default'] = {
        'alias': 'default',
        'label': f"{dbname} (기본 DB)",
        'host': host,
        'port': int(port),
        'dbname': dbname,
        'user': user,
        'password': password
    }
    logger.info(f"▶ [RDB Sources] 기본 소스 초기화: {dbname}@{host}:{port}")

@bp.route('/api/rdb/sources', methods=['GET', 'POST', 'DELETE'])
def rdb_source_management():
    """RDB 소스 관리 API
    GET: 등록된 RDB 소스 목록
    POST: 새 RDB 소스 등록 (연결 테스트 포함)
    DELETE: RDB 소스 삭제
    """
    import psycopg2
    
    # 기본 DB가 없으면 초기화
    if 'default' not in rdb_sources:
        try:
            _init_default_rdb_source(current_app)
        except Exception as e:
            logger.error(f"▶ [RDB Sources] 기본 소스 초기화 실패: {e}")
            # 환경변수 직접 사용 fallback
            import os
            rdb_sources['default'] = {
                'alias': 'default',
                'label': os.environ.get('DB_NAME', 'tccopdb') + ' (기본 DB)',
                'host': os.environ.get('DB_HOST', '49.50.128.28'),
                'port': int(os.environ.get('DB_PORT', '5333')),
                'dbname': os.environ.get('DB_NAME', 'tccopdb'),
                'user': os.environ.get('DB_USER', 'ccop'),
                'password': os.environ.get('DB_PASSWORD', 'Ccop@2025')
            }
    
    if request.method == 'GET':
        # 비밀번호는 마스킹
        result = []
        for alias, src in rdb_sources.items():
            result.append({
                'alias': src['alias'],
                'label': src.get('label', src['alias']),
                'host': src['host'],
                'port': src['port'],
                'dbname': src['dbname'],
                'user': src['user'],
                'is_default': alias == 'default'
            })
        return jsonify({"status": "success", "sources": result})
    
    elif request.method == 'POST':
        data = request.get_json()
        alias = data.get('alias', '').strip()
        host = data.get('host', '').strip()
        port = int(data.get('port', 5432))
        dbname = data.get('dbname', '').strip()
        user = data.get('user', '').strip()
        password = data.get('password', '').strip()
        label = data.get('label', '') or f"{dbname}@{host}"
        
        if not alias or not host or not dbname or not user:
            return jsonify({"status": "error", "message": "alias, host, dbname, user 필수"}), 400
        
        # 연결 테스트
        try:
            test_conn = psycopg2.connect(
                host=host, port=port, dbname=dbname,
                user=user, password=password,
                connect_timeout=5
            )
            test_conn.close()
        except Exception as e:
            return jsonify({"status": "error", "message": f"연결 실패: {e}"}), 400
        
        rdb_sources[alias] = {
            'alias': alias, 'label': label,
            'host': host, 'port': port,
            'dbname': dbname, 'user': user, 'password': password
        }
        logger.info(f"▶ [RDB Sources] 등록: {alias} ({dbname}@{host}:{port})")
        return jsonify({"status": "success", "message": f"'{alias}' RDB 소스 등록 완료"})
    
    elif request.method == 'DELETE':
        data = request.get_json()
        alias = data.get('alias', '')
        if alias == 'default':
            return jsonify({"status": "error", "message": "기본 DB는 삭제할 수 없습니다"}), 400
        if alias in rdb_sources:
            del rdb_sources[alias]
            return jsonify({"status": "success", "message": f"'{alias}' 삭제됨"})
        return jsonify({"status": "error", "message": "존재하지 않는 소스"}), 404

@bp.route('/api/rdb/tables', methods=['GET'])
def rdb_list_tables():
    """특정 RDB 소스의 테이블 목록 조회"""
    import psycopg2
    
    source_alias = request.args.get('source', 'default')
    
    # 기본 DB 초기화
    if 'default' not in rdb_sources:
        try:
            _init_default_rdb_source(current_app)
        except Exception as e:
            import os
            rdb_sources['default'] = {
                'alias': 'default', 'label': os.environ.get('DB_NAME', 'tccopdb') + ' (기본 DB)',
                'host': os.environ.get('DB_HOST', '49.50.128.28'),
                'port': int(os.environ.get('DB_PORT', '5333')),
                'dbname': os.environ.get('DB_NAME', 'tccopdb'),
                'user': os.environ.get('DB_USER', 'ccop'),
                'password': os.environ.get('DB_PASSWORD', 'Ccop@2025')
            }
    
    src = rdb_sources.get(source_alias)
    if not src:
        return jsonify({"status": "error", "message": f"'{source_alias}' 소스 없음"}), 404
    
    try:
        conn = psycopg2.connect(
            host=src['host'], port=src['port'], dbname=src['dbname'],
            user=src['user'], password=src['password'],
            connect_timeout=5
        )
        cur = conn.cursor()
        
        # public 스키마의 일반 테이블 목록 + 행 수 (추정치)
        cur.execute("""
            SELECT t.table_name, 
                   COALESCE(c.reltuples::bigint, 0) as row_estimate
            FROM information_schema.tables t
            LEFT JOIN pg_class c ON c.relname = t.table_name
            WHERE t.table_schema = 'public' 
            AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name
        """)
        tables = []
        for row in cur.fetchall():
            tables.append({
                "table_name": row[0],
                "row_count": max(int(row[1]), 0)
            })
        
        conn.close()
        return jsonify({
            "status": "success",
            "source": source_alias,
            "dbname": src['dbname'],
            "tables": tables
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/rdb/browse', methods=['GET'])
def rdb_browse():
    """RDB 테이블 데이터 조회 (페이징, 다중 RDB 지원)"""
    try:
        from flask import current_app
        import psycopg2
        
        table = request.args.get('table', 'rdb_cases')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 50))
        offset = (page - 1) * limit
        source_alias = request.args.get('source', 'default')
        
        # 보안: 기본 DB는 rdb_, TB_, tb_ 접두사만 허용, 외부 DB는 모든 테이블 허용
        if source_alias == 'default':
            if not (table.startswith('rdb_') or table.startswith('TB_') or table.startswith('tb_')):
                return jsonify({"status": "error", "message": "허용되지 않은 테이블"}), 400
        
        # 다중 RDB 소스 연결
        src = rdb_sources.get(source_alias)
        if src:
            conn = psycopg2.connect(
                host=src['host'], port=src['port'], dbname=src['dbname'],
                user=src['user'], password=src['password']
            )
        else:
            cfg = current_app.config['DB_CONFIG']
            conn = psycopg2.connect(**cfg)
        cur = conn.cursor()
        
        # 총 건수
        cur.execute(f'SELECT count(*) FROM {table}')
        total = cur.fetchone()[0]
        
        # 컬럼 정보 (information_schema는 소문자로 저장)
        table_lower = table.lower()
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='{table_lower}' ORDER BY ordinal_position")
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

    # 1. AI 분석 수행 (LangGraph Agent 활용: 성찰 루프 포함)
    try:
        agent = LangGraphAgent()
        agent_res = agent.run(question, graph_path)
        
        if agent_res.get("status") == "error":
            return jsonify({"error": agent_res.get("message", "에이전트 처리 오류")}), 500
        
        # 에이전트 결과에서 인텐트 추출
        intent = agent_res.get("intent", "QUERY")
        
        return jsonify({
            "elements": agent_res.get("elements", []),
            "cypher": agent_res.get("cypher", ""),
            "intent": intent,
            "explanation": agent_res.get("explanation", ""),
            "agent_status": agent_res.get("status")
        })
    except Exception as e:
        logger.error(f"Agent Query Error: {e}")
        return jsonify({"error": f"분석 오류: {str(e)}"}), 500

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

@bp.route('/api/rdb/analyze-csv', methods=['POST'])
def rdb_analyze_csv():
    """CSV 파일의 컬럼을 분석하여 RDB 매핑 초안을 반환 (2-Stage AI Mapping Step 1)"""
    try:
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400
        
        file = request.files['file']
        import pandas as pd
        
        # CSV 로드
        df = pd.read_csv(file).fillna('')
        sample_rows = df.head(3).to_dict('records')
        cols = df.columns
        
        # --- Column Mapping 추론 (rdb_service와 동일한 방식) ---
        from app.services.ontology_service import KICSCrimeDomainOntology
        from app.services.ai_service import AIService
        
        col_map = {}
        patterns = KICSCrimeDomainOntology.COLUMN_PATTERNS
        type_to_rdb = KICSCrimeDomainOntology.COLUMN_TYPE_TO_RDB
        
        priority_order = ['caller', 'callee', 'sender', 'receiver', 'nickname']
        sorted_patterns = {t: patterns[t] for t in priority_order if t in patterns}
        for t, cfg in patterns.items():
            if t not in sorted_patterns: sorted_patterns[t] = cfg
        
        # Pass 1: Exact matches
        unmatched_cols = []
        for c in cols:
            c_lower = c.lower().strip()
            matched = False
            for type_name, config in sorted_patterns.items():
                for pattern in config["patterns"]:
                    if c_lower == pattern.lower():
                        col_type = type_to_rdb.get(type_name, type_name)
                        if col_type not in col_map:
                            col_map[col_type] = c
                            matched = True
                        elif col_map[col_type] != c:
                            if "actno" in c_lower or "dpstr" in c_lower:
                                col_map[col_type] = c
                        break
                if matched: break
            if not matched: unmatched_cols.append(c)
        
        # Pass 2: Partial matches
        still_unmatched = []
        for c in unmatched_cols:
            c_lower = c.lower().strip()
            matched = False
            for type_name, config in sorted_patterns.items():
                for pattern in config["patterns"]:
                    if pattern.lower() in c_lower or c_lower in pattern.lower():
                        col_type = type_to_rdb.get(type_name, type_name)
                        if col_type not in col_map:
                            col_map[col_type] = c
                            matched = True
                        elif col_map[col_type] != c:
                            if "actno" in c_lower or "dpstr" in c_lower:
                                col_map[col_type] = c
                        break
                if matched: break
            if not matched: still_unmatched.append(c)
            
        # Pass 3: LLM Inference
        llm_inferred_types = {}
        if still_unmatched:
            llm_result = AIService.infer_column_mapping_for_rdb(still_unmatched, sample_rows)
            for c, type_name in llm_result.items():
                if type_name and type_name != 'ignore':
                    col_type = type_to_rdb.get(type_name, type_name)
                    # 기존 매핑을 덮어쓰지 않고 추가
                    if col_type not in col_map:
                        col_map[col_type] = c
                        llm_inferred_types[c] = col_type
        
        # UI 형태로 변환
        ui_mapping = []
        for c in cols:
            mapped_type = None
            method = 'unmapped'
            for k, v in col_map.items():
                if v == c:
                    mapped_type = k
                    if c in llm_inferred_types:
                        method = 'llm'
                    elif c not in unmatched_cols:
                        method = 'exact'
                    else:
                        method = 'partial'
                    break
            
            ui_mapping.append({
                "column": c,
                "mapped_type": mapped_type,
                "method": method
            })
            
        return jsonify({
            "status": "success",
            "mapping": ui_mapping,
            "sample_data": sample_rows
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@bp.route('/api/rdb/import', methods=['POST'])
def rdb_import():
    """CSV 파일을 RDB 테이블에 적재"""
    try:
        import json
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file part"}), 400
        
        file = request.files['file']
        
        # 임시 파일 저장 (RDBService가 파일 경로를 요구함)
        import os
        from app.services.rdb_service import RDBService
        
        temp_path = f"/tmp/{file.filename}"
        file.save(temp_path)
        
        clear_rdb = request.form.get('clear_rdb', 'false').lower() == 'true'
        
        # 프론트엔드에서 확정한 매핑 정보 (선택적)
        frontend_mapping_str = request.form.get('column_mapping')
        frontend_mapping = None
        if frontend_mapping_str:
            try:
                frontend_mapping = json.loads(frontend_mapping_str)
            except:
                pass
        
        try:
            # 스마트 라우팅 분기: 파일명이 tbl_ 로 시작하면 사전 정의된 RDB 스키마로 간주
            if file.filename.lower().startswith('tbl_'):
                success, result = RDBService.import_predefined_schema_to_rdb(temp_path, file.filename, clear_existing=clear_rdb)
            else:
                success, result = RDBService.import_csv_to_rdb(temp_path, clear_existing=clear_rdb, custom_mapping=frontend_mapping)
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


# ------------------------------
# 8. 그래프 분석 API (Enhancement Area 2 & 4)
# ------------------------------
@bp.route('/api/analysis/anomaly', methods=['GET'])
def analysis_anomaly():
    """이상 점수 분석"""
    graph = request.args.get('graph', 'test_local_data')
    from app.services.analysis_service import AnalysisService
    result = AnalysisService.run_anomaly_scoring(graph)
    return jsonify({"status": "success", "data": result})

@bp.route('/api/analysis/centrality', methods=['GET'])
def analysis_centrality():
    """중심성 분석 — 핵심 노드 식별"""
    graph = request.args.get('graph', 'test_local_data')
    from app.services.analysis_service import AnalysisService
    result = AnalysisService.run_centrality_analysis(graph)
    return jsonify({"status": "success", "data": result})

@bp.route('/api/analysis/inference', methods=['GET'])
def analysis_inference():
    """추론 엔진 — 범죄 패턴 탐지"""
    graph = request.args.get('graph', 'test_local_data')
    from app.services.analysis_service import AnalysisService
    result = AnalysisService.run_inference_engine(graph)
    return jsonify({"status": "success", "data": result})

@bp.route('/api/analysis/summary', methods=['GET'])
def analysis_summary():
    """사건 종합 요약"""
    graph = request.args.get('graph', 'test_local_data')
    from app.services.analysis_service import AnalysisService
    result = AnalysisService.get_case_summary(graph)
    return jsonify({"status": "success", "data": result})
