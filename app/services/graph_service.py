import json
import logging
from app.database import get_db_connection, safe_props, safe_set_graph_path, validate_graph_path
from app.services.subgraph_service import SubGraphService
from app.services.ai_service import AIService
import psycopg2
from flask import current_app

logger = logging.getLogger(__name__)

class GraphService:
    
    # 스키마 캐시 (graph_path 별 저장)
    _SCHEMA_CACHE = {}
    _CACHE_TTL = 300 # 5분
    
    @staticmethod
    def get_db_connection():
        """DB 연결 헬퍼"""
        try:
            conn = psycopg2.connect(
                dbname=current_app.config['DB_CONFIG']['dbname'],
                user=current_app.config['DB_CONFIG']['user'],
                password=current_app.config['DB_CONFIG']['password'],
                host=current_app.config['DB_CONFIG']['host'],
                port=current_app.config['DB_CONFIG']['port']
            )
            conn.autocommit = True
            return conn, conn.cursor()
        except Exception as e:
            logger.error(f"DB 접속 오류: {e}")
            return None, None

    @staticmethod
    def safe_props(val):
        """JSON 속성 파싱 안전장치"""
        if val is None: return {}
        if isinstance(val, dict): return val
        try:
            if isinstance(val, str) and not val.strip(): return {}
            return json.loads(val)
        except:
            return {}
    
    @staticmethod
    def determine_node_label(props):
        """
        노드 속성을 기반으로 적절한 label(타입) 결정
        KICS 컬럼 속성 기준으로 라벨 자동 분류
        
        Returns:
            - 'vt_flnm': 접수번호 (flnm)
            - 'vt_bacnt': 계좌번호 (actno, bank)
            - 'vt_site': 사이트 (site, url, domain)
            - 'vt_telno': 전화번호 (telno, phone)
            - 'vt_ip': IP 주소 (ip, ip_addr)
            - 'vt_atm': ATM (atm, atm_id)
            - 'vt_file': 파일명 (file, filename)
            - 'vt_id': ID (id, user_id)
            - 기본값: 'vt_psn'
        """
        if not props or not isinstance(props, dict):
            return 'vt_psn'
        
        # 우선순위 기반 분류
        
        # 0. 이벤트 (Dynamic Ontology)
        if 'event_type' in props or 'event_id' in props:
            return 'vt_event'

        # 0.1 페르소나
        if 'persona_type' in props or 'persona_id' in props:
            return 'vt_persona'

        # 1. IP 주소 (가장 구체적)
        if 'ip' in props or 'ip_addr' in props or 'ipaddr' in props:
            return 'vt_ip'
        
        # 2. ATM
        if 'atm' in props or 'atm_id' in props:
            return 'vt_atm'
        
        # 3. 사이트/URL
        if 'site' in props or 'url' in props or 'domain' in props:
            return 'vt_site'
        
        # 4. 계좌번호
        if 'actno' in props or 'bank' in props or 'account' in props or 'bacnt' in props:
            return 'vt_bacnt'
        
        # 5. 전화번호
        if 'telno' in props or 'phone' in props:
            return 'vt_telno'
        
        # 6. 파일명
        if 'file' in props or 'filename' in props or 'filepath' in props:
            return 'vt_file'
        
        # 7. 접수번호 (flnm)
        if 'flnm' in props:
            return 'vt_flnm'
        
        # 8. ID
        if 'id' in props or 'user_id' in props or 'userid' in props:
            return 'vt_id'
        
        # 9. 이름 (person)
        if 'name' in props:
            return 'vt_psn'
        
        # 기본값
        return 'vt_psn'

    @staticmethod
    def get_current_schema(graph_path, force_refresh=False):
        """현재 그래프의 활성 VLABEL 및 ELABEL 정보와 각 속성 키들을 동적으로 조회 (캐시 적용)"""
        import time
        from flask import current_app
        
        # 캐시 확인
        if not force_refresh and graph_path in GraphService._SCHEMA_CACHE:
            cached_data, timestamp = GraphService._SCHEMA_CACHE[graph_path]
            if time.time() - timestamp < GraphService._CACHE_TTL:
                logger.info(f"▶ [SchemaCache] 캐시 히트: {graph_path}")
                return cached_data

        conn, cur = GraphService.get_db_connection()
        if not conn: return {"node_labels": {}, "edge_types": []}
        try:
            # Vertex 라벨 및 대표 속성 샘플링 조회
            cur.execute(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = '{graph_path}' 
                  AND table_name LIKE 'vt_%'
            """)
            vertex_labels = [r[0] for r in cur.fetchall()]
            
            node_info = {}
            for label in vertex_labels:
                # 각 라벨의 컬럼(속성) 목록 조회
                cur.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = '{graph_path}' AND table_name = '{label}'
                      AND column_name NOT IN ('id', 'properties')
                """)
                cols = [r[0] for r in cur.fetchall()]
                # JSONB properties 내부의 키 샘플링
                cur.execute(f"SELECT jsonb_object_keys(properties) FROM \"{graph_path}\".\"{label}\" LIMIT 10")
                prop_keys = list(set([r[0] for r in cur.fetchall()]))
                node_info[label] = list(set(cols + prop_keys))

            # Edge 라벨 조회
            cur.execute(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = '{graph_path}' 
                  AND table_name NOT LIKE 'vt_%'
                  AND table_name NOT IN ('ag_vertex', 'ag_label', 'ag_edge')
            """)
            edge_labels = [r[0] for r in cur.fetchall()]
            
            schema_data = {
                "node_labels": node_info,
                "edge_types": edge_labels
            }
            
            # 캐시 저장
            GraphService._SCHEMA_CACHE[graph_path] = (schema_data, time.time())
            return schema_data

        except Exception as e:
            logger.error(f"Get Schema Error: {e}")
            return {"node_labels": {}, "edge_types": []}
        finally:
            conn.close()

    @staticmethod
    def clear_graph(graph_path):
        """그래프 데이터 전체 초기화"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            safe_set_graph_path(cur, graph_path)
            cur.execute("MATCH (n) DETACH DELETE n")
            return True, "삭제 완료"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def list_graphs():
        """모든 그래프 목록 조회 (성능 최적화: 카운트 제외)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return []
        try:
            # AgensGraph에서 그래프 목록 조회
            cur.execute("""
                SELECT graphname
                FROM pg_catalog.ag_graph
                ORDER BY graphname;
            """)
            graphs = []
            for row in cur.fetchall():
                graph_name = row[0]
                # 외부 DB 연결 시 COUNT(*)는 매우 느리므로 0으로 반환하거나 생략
                # 필요시 별도 API로 상세 정보 조회하도록 변경 권장
                graphs.append({
                    "name": graph_name,
                    "node_count": 0  # 성능을 위해 0으로 고정
                })
            return graphs
        except Exception as e:
            logger.error(f"List Graphs Error: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def create_graph(graph_name):
        """새 그래프 생성"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            # AgensGraph에서 그래프 생성
            cur.execute(f"CREATE GRAPH IF NOT EXISTS {graph_name};")
            safe_set_graph_path(cur, graph_name)
            
            # 기본 vertex/edge 라벨 생성
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_psn;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_bacnt;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_telno;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_site;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_ip;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_flnm;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_id;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_atm;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_event;")
            cur.execute("CREATE VLABEL IF NOT EXISTS vt_persona;")
            
            cur.execute("CREATE ELABEL IF NOT EXISTS related_to;")
            cur.execute("CREATE ELABEL IF NOT EXISTS uses_persona;")
            cur.execute("CREATE ELABEL IF NOT EXISTS participated_in;")
            cur.execute("CREATE ELABEL IF NOT EXISTS event_involved;")
            cur.execute("CREATE ELABEL IF NOT EXISTS supported_by;")
            cur.execute("CREATE ELABEL IF NOT EXISTS used_account;")
            cur.execute("CREATE ELABEL IF NOT EXISTS used_phone;")
            cur.execute("CREATE ELABEL IF NOT EXISTS digital_trace;")
            
            return True, f"그래프 '{graph_name}' 생성 완료"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def delete_graph(graph_name):
        """그래프 삭제"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            # 보호: 기본 그래프는 삭제 방지
            if graph_name in ['agens_graph', 'public']:
                return False, "시스템 그래프는 삭제할 수 없습니다."
            
            # AgensGraph에서 그래프 삭제
            cur.execute(f"DROP GRAPH IF EXISTS {graph_name} CASCADE;")
            return True, f"그래프 '{graph_name}' 삭제 완료"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def search_nodes(keyword, graph_path):
        """키워드로 노드 검색 (모든 라벨 타입) + 연결된 엣지 포함"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return []
        
        try:
            # 1. 모든 vertex 라벨 테이블 찾기
            cur.execute(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = '{graph_path}' 
                  AND table_name LIKE 'vt_%'
            """)
            vertex_tables = [r[0] for r in cur.fetchall()]
            
            if not vertex_tables:
                return []
            
            # 2. 각 테이블에서 노드 검색
            elements = []
            node_ids = set()  # 검색된 노드 ID 저장
            
            for table_name in vertex_tables:
                try:
                    query = f"""
                    SELECT id, properties 
                    FROM "{graph_path}"."{table_name}"
                    WHERE properties::text LIKE '%{keyword}%'
                    LIMIT 50
                    """
                    cur.execute(query)
                    
                    for r in cur.fetchall():
                        node_id = str(r[0])
                        props = r[1] if isinstance(r[1], dict) else {}
                        
                        node_ids.add(node_id)  # ID 저장
                        
                        # 테이블명으로부터 라벨 추출
                        node_label = table_name
                        
                        elements.append({
                            "group": "nodes", 
                            "data": { 
                                "id": node_id, 
                                "label": node_label,
                                "props": props 
                            }
                        })
                except Exception as table_error:
                    logger.info(f"Search error in {table_name}: {table_error}")
                    continue
            
            # 3. 검색된 노드들 간의 엣지 찾기
            if node_ids:
                try:
                    # 모든 엣지 테이블 찾기
                    cur.execute(f"""
                        SELECT table_name 
                        FROM information_schema.tables 
                        WHERE table_schema = '{graph_path}' 
                          AND table_name NOT LIKE 'vt_%'
                          AND table_name != 'ag_label'
                          AND table_name != 'ag_vertex'
                          AND table_name != 'ag_edge'
                    """)
                    edge_tables = [r[0] for r in cur.fetchall()]
                    
                    node_id_list = ','.join([f"'{nid}'" for nid in node_ids])
                    
                    for edge_table in edge_tables:
                        try:
                            edge_query = f"""
                            SELECT e.id, e.start, e."end", e.properties,
                                   vs.properties as src_props, vt.properties as tgt_props
                            FROM "{graph_path}"."{edge_table}" e
                            LEFT JOIN "{graph_path}"."ag_vertex" vs ON e.start = vs.id
                            LEFT JOIN "{graph_path}"."ag_vertex" vt ON e."end" = vt.id
                            WHERE e.start IN ({node_id_list}) OR e."end" IN ({node_id_list})
                            LIMIT 100
                            """
                            cur.execute(edge_query)
                            
                            for edge_row in cur.fetchall():
                                edge_id = str(edge_row[0])
                                src_id = str(edge_row[1])
                                tgt_id = str(edge_row[2])
                                edge_props = edge_row[3] if isinstance(edge_row[3], dict) else {}
                                
                                # 엣지 양쪽 노드를 elements에 추가 (중복 방지)
                                if src_id not in node_ids:
                                    src_props = edge_row[4] if isinstance(edge_row[4], dict) else {}
                                    # 올바른 라벨 결정
                                    src_label = GraphService.determine_node_label(src_props)
                                    elements.append({
                                        "group": "nodes",
                                        "data": {"id": src_id, "label": src_label, "props": src_props}
                                    })
                                    node_ids.add(src_id)
                                
                                if tgt_id not in node_ids:
                                    tgt_props = edge_row[5] if isinstance(edge_row[5], dict) else {}
                                    # 올바른 라벨 결정  
                                    tgt_label = GraphService.determine_node_label(tgt_props)
                                    elements.append({
                                        "group": "nodes",
                                        "data": {"id": tgt_id, "label": tgt_label, "props": tgt_props}
                                    })
                                    node_ids.add(tgt_id)
                                
                                # 엣지 추가 - 라벨 결정
                                # ag_edge 테이블인 경우 properties에서 실제 관계 타입 추출
                                edge_label = edge_table
                                if edge_table == 'ag_edge':
                                    # 속성에서 실제 관계 타입 찾기
                                    edge_label = (
                                        edge_props.get('semantic_relation') or 
                                        edge_props.get('domain_meaning') or
                                        edge_props.get('edge_type') or
                                        edge_props.get('type') or
                                        'related_to'  # 기본값
                                    )
                                    # 대문자를 소문자로 변환 (USED_ACCOUNT -> used_account)
                                    if isinstance(edge_label, str):
                                        edge_label = edge_label.lower()
                                
                                elements.append({
                                    "group": "edges",
                                    "data": {
                                        "id": edge_id,
                                        "source": src_id,
                                        "target": tgt_id,
                                        "label": edge_label,
                                        "props": edge_props
                                    }
                                })
                        except Exception as edge_error:
                            logger.debug(f"Edge search error in {edge_table}: {edge_error}")
                            continue
                            
                except Exception as e:
                    logger.error(f"Edge retrieval error: {e}")
            
            return elements
        except Exception as e:
            logger.error(f"Search Error: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def expand_node(node_id, graph_path):
        """노드 확장 (SQL 기반 엣지 조회 - 모든 엣지 테이블 동적 조회)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return []
        
        elements = []
        try:
            # 1. 엣지 테이블 목록 동적 조회 - 모든 엣지 테이블 포함
            cur.execute(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = '{graph_path}' 
                  AND table_name NOT IN ('ag_vertex', 'ag_label', 'ag_edge')
                  AND table_name NOT LIKE 'vt_%'
            """)
            edge_tables = [r[0] for r in cur.fetchall()]
            
            # 기본 엣지 테이블 추가 (4-Layer 모델 기반)
            core_edge_tables = [
                'involves', 'owns', 'has_account', 'transferred_to', 
                'contacted', 'communicated_with', 'accessed', 'linked_to',
                'performed', 'from_account', 'to_account', 'caller', 'callee',
                'uses_persona', 'participated_in', 'event_involved', 'supported_by'
            ]
            for t in core_edge_tables:
                if t not in edge_tables:
                    edge_tables.append(t)
            
            logger.debug(f"[expand_node] 조회할 엣지 테이블: {edge_tables}")
            
            # 중복 엣지 방지를 위한 ID 추적
            added_edge_ids = set()
            
            # 2. 각 엣지 테이블에서 연결된 엣지 조회
            for edge_table in edge_tables:
                try:
                    # AgensGraph graphid 형식 처리
                    edge_query = f"""
                    SELECT e.id, e.start, e."end", e.properties, 
                           vs.id as src_id, vs.properties as src_props,
                           vt.id as tgt_id, vt.properties as tgt_props
                    FROM "{graph_path}"."{edge_table}" e
                    LEFT JOIN "{graph_path}"."ag_vertex" vs ON e.start = vs.id
                    LEFT JOIN "{graph_path}"."ag_vertex" vt ON e."end" = vt.id
                    WHERE e.start::text = '{node_id}' OR e."end"::text = '{node_id}'
                    LIMIT 50
                    """
                    
                    cur.execute(edge_query)
                    for r in cur.fetchall():
                        edge_id = str(r[0])
                        
                        # 이미 추가된 엣지면 건너뜀
                        if edge_id in added_edge_ids:
                            continue
                            
                        start_id = str(r[1])
                        end_id = str(r[2])
                        edge_props = r[3] if isinstance(r[3], dict) else {}
                        
                        src_id = str(r[4]) if r[4] else start_id
                        src_props = r[5] if isinstance(r[5], dict) else {}
                        
                        tgt_id = str(r[6]) if r[6] else end_id
                        tgt_props = r[7] if isinstance(r[7], dict) else {}
                        
                        # 소스 노드 추가 (현재 노드가 아닌 경우)
                        if src_id != node_id:
                            src_label = GraphService.determine_node_label(src_props)
                            elements.append({
                                "group": "nodes",
                                "data": {"id": src_id, "label": src_label, "props": src_props}
                            })
                        
                        # 타겟 노드 추가 (현재 노드가 아닌 경우)
                        if tgt_id != node_id:
                            tgt_label = GraphService.determine_node_label(tgt_props)
                            elements.append({
                                "group": "nodes",
                                "data": {"id": tgt_id, "label": tgt_label, "props": tgt_props}
                            })
                        
                        # 엣지 추가 - 라벨 결정 로직 적용
                        edge_label = edge_table
                        if edge_table == 'ag_edge':
                            edge_label = (
                                edge_props.get('semantic_relation') or 
                                edge_props.get('domain_meaning') or
                                edge_props.get('edge_type') or
                                edge_props.get('type') or
                                'related_to'
                            )
                            if isinstance(edge_label, str):
                                edge_label = edge_label.lower()

                        elements.append({
                            "group": "edges",
                            "data": {
                                "id": edge_id,
                                "source": start_id,
                                "target": end_id,
                                "label": edge_label,
                                "props": edge_props
                            }
                        })
                        added_edge_ids.add(edge_id)
                
                except Exception as table_error:
                    # 테이블이 없는 경우는 무시 (동적으로 추가된 테이블 목록이므로)
                    continue
            
            return elements
        except Exception as e:
            logger.error(f"Expand Error: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def find_shortest_path(src, tgt, graph_path):
        """최단 경로 탐색 (BFS)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, []
        
        try:
            safe_set_graph_path(cur, graph_path)
            
            # BFS 탐색
            queue = [[src]]
            visited = {src}
            found_path = None
            
            while queue:
                path = queue.pop(0)
                curr = path[-1]
                if curr == tgt:
                    found_path = path; break
                if len(path) > 6: continue # 깊이 제한
                
                # 이웃 노드 검색
                cur.execute(f"MATCH (u)-[]-(v) WHERE id(u) = '{curr}' RETURN id(v)")
                for row in cur.fetchall():
                    neighbor_id = str(row[0])
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append(path + [neighbor_id])
            
            if not found_path: return False, []
            
            # 경로 시각화 데이터 생성
            elements = []
            for nid in found_path:
                cur.execute(f"MATCH (n) WHERE id(n) = '{nid}' RETURN id(n), labels(n), properties(n)")
                r = cur.fetchone()
                if r:
                    node_id = str(r[0])
                    elements.append({"group": "nodes", "data": {"id": node_id, "label": r[1][0], "props": GraphService.safe_props(r[2])}})
            
            # 엣지 연결
            for i in range(len(found_path)-1):
                u, v = found_path[i], found_path[i+1]
                cur.execute(f"MATCH (u)-[r]-(v) WHERE id(u) = '{u}' AND id(v) = '{v}' RETURN id(r), type(r), properties(r)")
                edge_res = cur.fetchone()
                
                if edge_res:
                    edge_id = str(edge_res[0])
                    elements.append({"group": "edges", "data": {"id": edge_id, "source": str(u), "target": str(v), "label": edge_res[1], "props": GraphService.safe_props(edge_res[2])}})
                else:
                    # 논리적 연결일 경우 점선 처리
                    elements.append({"group": "edges", "data": {"id": f"v_{u}_{v}", "source": u, "target": v, "label": "Same Info", "props": {"type":"virtual"}}, "classes": "virtual-edge"})
                    
            return True, elements
            
        except Exception as e:
            logger.error(f"Path Error: {e}")
            return False, []
        finally:
            conn.close()

    @staticmethod
    def multi_hop_expand(node_id, depth, graph_path, max_nodes=200):
        """N-hop 다단계 확장 (Cypher 변수 길이 경로)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return {'nodes': [], 'edges': [], 'stats': {}}
        
        depth = min(int(depth), 5)  # 최대 5-hop
        
        try:
            safe_set_graph_path(cur, graph_path)
            
            elements_nodes = []
            elements_edges = []
            node_set = set()
            edge_set = set()
            
            # 시작 노드 정보
            cur.execute(f"MATCH (n) WHERE id(n) = '{node_id}' RETURN id(n), labels(n), properties(n)")
            start = cur.fetchone()
            if start:
                sid = str(start[0])
                node_set.add(sid)
                elements_nodes.append({
                    "group": "nodes",
                    "data": {"id": sid, "label": start[1][0] if isinstance(start[1], list) else str(start[1]),
                             "props": GraphService.safe_props(start[2]), "hop": 0}
                })
            
            # 단일 hop 단계 (exact depth) 확장으로 변경
            try:
                if depth == 1:
                    query = f"""
                        MATCH (start)-[r]-(end_node)
                        WHERE id(start) = '{node_id}'
                        RETURN id(end_node), labels(end_node), properties(end_node),
                               id(r), type(r), properties(r), id(start) AS prev_id
                        LIMIT {max_nodes}
                    """
                else:
                    # 중간 경로는 무시하고 가장 마지막 단계의 노드(end_node)와 그 직전 엣지(r)만 반환
                    prev_hops = depth - 1
                    query = f"""
                        MATCH (start)-[*{prev_hops}..{prev_hops}]-(prev)-[r]-(end_node)
                        WHERE id(start) = '{node_id}'
                        RETURN id(end_node), labels(end_node), properties(end_node),
                               id(r), type(r), properties(r), id(prev) AS prev_id
                        LIMIT {max_nodes}
                    """
                
                cur.execute(query)
                exact_hop_results = cur.fetchall()
                
                for r_row in exact_hop_results:
                    nid = str(r_row[0])
                    n_label = r_row[1][0] if isinstance(r_row[1], list) else str(r_row[1])
                    n_props = GraphService.safe_props(r_row[2])
                    
                    eid = str(r_row[3])
                    e_label_raw = str(r_row[4])
                    e_props = GraphService.safe_props(r_row[5])
                    prev_id = str(r_row[6])
                    
                    # 노드 추가
                    if nid not in node_set:
                        node_set.add(nid)
                        elements_nodes.append({
                            "group": "nodes",
                            "data": {
                                "id": nid,
                                "label": n_label,
                                "props": n_props,
                                "hop": depth
                            }
                        })
                    
                    # 직전 노드(prev)도 현재 elements_nodes에 없다면 시각화를 위해 최소한의 형태로 추가
                    # (화면에 둥둥 떠다니는 걸 방지하려면 연결될 부모 노드가 필요함.
                    # 단, 중간 과정이 전부 나오는게 싫다면 이 prev 노드들은 투명하게 처리하거나
                    # 프론트엔드에서 레이아웃만 맞추는 용도로 쓸 수 있지만, 선행 노드가 화면에 없으면 Cytoscape에서 엣지가 그려지지 않음)
                    if prev_id not in node_set and prev_id != sid:
                        node_set.add(prev_id)
                        elements_nodes.append({
                            "group": "nodes",
                            "data": {
                                "id": prev_id,
                                "label": "Unknown", # 최소 정보만
                                "props": {},
                                "hop": depth - 1,
                                "hidden_intermediate": True # 프론트에서 숨김 처리 가능하도록 플래그
                            }
                        })
                        
                    # 엣지 추가
                    if eid not in edge_set:
                        edge_set.add(eid)
                        
                        # 엣지 라벨 재확인 (ag_edge일 경우 실제 타입 추출)
                        edge_label = e_label_raw
                        if edge_label == 'ag_edge' or not edge_label:
                            edge_label = (
                                e_props.get('semantic_relation') or 
                                e_props.get('domain_meaning') or
                                e_props.get('edge_type') or
                                e_props.get('type') or
                                'related_to'
                            )
                            if isinstance(edge_label, str):
                                edge_label = edge_label.lower()
                                
                        elements_edges.append({
                            "group": "edges",
                            "data": {
                                "id": eid,
                                "source": prev_id,
                                "target": nid,
                                "label": edge_label,
                                "props": e_props
                            }
                        })
                            
            except Exception as hop_err:
                logger.error(f"Exact Hop {depth} error: {hop_err}")
            
            stats = {
                'total_nodes': len(elements_nodes),
                'total_edges': len(elements_edges),
                'depth': depth,
                'start_node': node_id
            }
            
            return {
                'nodes': elements_nodes,
                'edges': elements_edges,
                'stats': stats
            }
        except Exception as e:
            logger.error(f"Multi-hop Error: {e}")
            return {'nodes': [], 'edges': [], 'stats': {'error': str(e)}}
        finally:
            conn.close()

    @staticmethod
    def find_accomplice_network(node_id, graph_path):
        """공범 네트워크 탐색 — 선택 노드에서 accomplice_of 관계 + 공유 자원 추적"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return {'nodes': [], 'edges': [], 'shared': []}
        
        try:
            safe_set_graph_path(cur, graph_path)
            
            elements_nodes = []
            elements_edges = []
            shared_resources = []
            node_set = set()
            edge_set = set()
            
            # 1. 시작 Person 노드
            cur.execute(f"MATCH (p) WHERE id(p) = '{node_id}' RETURN id(p), labels(p), properties(p)")
            start = cur.fetchone()
            if not start:
                return {'nodes': [], 'edges': [], 'shared': [], 'error': 'Node not found'}
            
            sid = str(start[0])
            node_set.add(sid)
            elements_nodes.append({
                "group": "nodes",
                "data": {"id": sid, "label": start[1][0] if isinstance(start[1], list) else str(start[1]),
                         "props": GraphService.safe_props(start[2]), "role": "center"}
            })
            
            # 2. accomplice_of 관계로 연결된 인물들 (2-hop)
            try:
                cur.execute(f"""
                    MATCH (p1)-[r:accomplice_of]-(p2)
                    WHERE id(p1) = '{node_id}'
                    RETURN id(p2), labels(p2), properties(p2), id(r), properties(r)
                """)
                for r in cur.fetchall():
                    pid = str(r[0])
                    if pid not in node_set:
                        node_set.add(pid)
                        elements_nodes.append({
                            "group": "nodes",
                            "data": {"id": pid, "label": r[1][0] if isinstance(r[1], list) else str(r[1]),
                                     "props": GraphService.safe_props(r[2]), "role": "accomplice"}
                        })
                    eid = str(r[3])
                    if eid not in edge_set:
                        edge_set.add(eid)
                        eprops = GraphService.safe_props(r[4])
                        elements_edges.append({
                            "group": "edges",
                            "data": {"id": eid, "source": sid, "target": pid,
                                     "label": "accomplice_of", "props": eprops}
                        })
            except Exception as e:
                logger.error(f"Accomplice query error: {e}")
            
            # 3. 공유 자원 (계좌/전화) 추적
            for rel, res_label, prop_name in [
                ('has_account', 'vt_bacnt', 'actno'),
                ('owns_phone', 'vt_telno', 'telno'),
                ('used_ip', 'vt_ip', 'ip_addr')
            ]:
                try:
                    cur.execute(f"""
                        MATCH (p)-[r:{rel}]->(res:{res_label})
                        WHERE id(p) = '{node_id}'
                        RETURN id(res), labels(res), properties(res), id(r)
                    """)
                    for r in cur.fetchall():
                        rid = str(r[0])
                        if rid not in node_set:
                            node_set.add(rid)
                            rprops = GraphService.safe_props(r[2])
                            elements_nodes.append({
                                "group": "nodes",
                                "data": {"id": rid, "label": r[1][0] if isinstance(r[1], list) else str(r[1]),
                                         "props": rprops, "role": "resource"}
                            })
                            shared_resources.append({
                                'type': rel,
                                'value': rprops.get(prop_name, ''),
                                'id': rid
                            })
                        eid_r = str(r[3])
                        if eid_r not in edge_set:
                            edge_set.add(eid_r)
                            elements_edges.append({
                                "group": "edges",
                                "data": {"id": eid_r, "source": sid, "target": rid,
                                         "label": rel, "props": {}}
                            })
                except:
                    continue
            
            # 4. 관련 사건도 추가
            try:
                cur.execute(f"""
                    MATCH (c:vt_case)-[:involves]->(p)
                    WHERE id(p) = '{node_id}'
                    RETURN id(c), labels(c), properties(c)
                """)
                for r in cur.fetchall():
                    cid = str(r[0])
                    if cid not in node_set:
                        node_set.add(cid)
                        elements_nodes.append({
                            "group": "nodes",
                            "data": {"id": cid, "label": r[1][0] if isinstance(r[1], list) else str(r[1]),
                                     "props": GraphService.safe_props(r[2]), "role": "case"}
                        })
                        elements_edges.append({
                            "group": "edges",
                            "data": {"id": f"inv_{cid}_{sid}", "source": cid, "target": sid,
                                     "label": "involves", "props": {}}
                        })
            except:
                pass
            
            return {
                'nodes': elements_nodes,
                'edges': elements_edges,
                'shared': shared_resources,
                'stats': {
                    'accomplices': sum(1 for n in elements_nodes if n['data'].get('role') == 'accomplice'),
                    'cases': sum(1 for n in elements_nodes if n['data'].get('role') == 'case'),
                    'resources': len(shared_resources)
                }
            }
        except Exception as e:
            logger.error(f"Accomplice Network Error: {e}")
            return {'nodes': [], 'edges': [], 'shared': [], 'error': str(e)}
        finally:
            conn.close()

    @staticmethod
    def find_hub_nodes(graph_path, top_n=10):
        """허브 노드 탐지 (연결 수 상위 N개)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return []
        
        try:
            safe_set_graph_path(cur, graph_path)
            
            hubs = []
            # Person 허브
            try:
                cur.execute(f"""
                    MATCH (p:vt_psn)
                    WHERE p.name <> '불상' AND p.name <> '미상'
                    RETURN id(p), p.name,
                           size((p)<-[:involves]-()) AS cases,
                           size((p)-[:has_account]->()) AS accounts,
                           size((p)-[:owns_phone]->()) AS phones,
                           size((p)-[:accomplice_of]-()) AS accomplices
                    ORDER BY cases + accounts + phones + accomplices DESC
                    LIMIT {top_n}
                """)
                for r in cur.fetchall():
                    hubs.append({
                        'id': str(r[0]), 'name': r[1], 'type': 'person',
                        'cases': r[2], 'accounts': r[3], 'phones': r[4],
                        'accomplices': r[5],
                        'total': r[2] + r[3] + r[4] + r[5]
                    })
            except Exception as e:
                logger.error(f"Person hub error: {e}")
            
            # Account 허브
            try:
                cur.execute(f"""
                    MATCH (a:vt_bacnt)
                    RETURN id(a), a.actno,
                           size((a)<-[:eg_used_account]-()) AS cases,
                           size((a)<-[:has_account]-()) AS persons
                    ORDER BY cases + persons DESC
                    LIMIT {top_n}
                """)
                for r in cur.fetchall():
                    hubs.append({
                        'id': str(r[0]), 'name': r[1], 'type': 'account',
                        'cases': r[2], 'persons': r[3],
                        'total': r[2] + r[3]
                    })
            except Exception as e:
                logger.error(f"Account hub error: {e}")
            
            # 전체 정렬
            hubs.sort(key=lambda x: x.get('total', 0), reverse=True)
            return hubs[:top_n]
            
        except Exception as e:
            logger.error(f"Hub Error: {e}")
            return []
        finally:
            conn.close()

    # ---------------------------------------------------------
    # 🤖 [Feature 4] AI Text-to-Cypher (AIService 연동)
    # ---------------------------------------------------------
    @staticmethod
    def execute_cypher(cypher_query, graph_path):
        """
        AgensGraph 네이티브 Cypher 쿼리 실행
        """
        if not cypher_query: return False, "Empty Query"

        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB Connection Failed"

        try:
            # 1. Graph Path 설정 (AgensGraph 필수)
            safe_set_graph_path(cur, graph_path)

            # 2. SQL Wrapper (SELECT * FROM cypher...) 형식인 경우 내부 Cypher만 추출
            # (Native AgensGraph에서는 직접 MATCH를 선호하므로 호환성을 위해 처리)
            real_query = cypher_query.strip()
            if real_query.upper().startswith("SELECT") and "$$" in real_query:
                import re
                match = re.search(r"\$\$(.*)\$\$", real_query, re.DOTALL)
                if match:
                    real_query = match.group(1).strip()
                    logger.info(f"▶ [GraphService] SQL Wrapper에서 내부 Cypher 추출 완료")
            
            logger.info(f"▶ [GraphService] 실행 Cypher: {real_query}")
            cur.execute(real_query)
            
            # 3. 결과 파싱 (노드와 엣지 구분 처리)
            rows = cur.fetchall()
            elements = []
            
            node_ids = set()
            edge_ids = set()
            
            import re
            import json
            
            # AgensGraph raw string regex patterns
            # Node: label[id]{props} e.g. vt_psn[4.2]{"name":"foo"}
            # Edge: label[id][src,dst]{props} e.g. involves[19.2][3.1,4.2]{"role":"bar"}
            node_pattern = re.compile(r'^([a-zA-Z0-9_]+)\[([\d\.]+)\](\{.*\})$')
            edge_pattern = re.compile(r'^([a-zA-Z0-9_]+)\[([\d\.]+)\]\[([\d\.]+),([\d\.]+)\](\{.*\})$')
            
            def parse_item(item):
                if not item: return
                item_type = type(item).__name__
                
                # 리스트나 튜플인 경우 내부 아이템들 재귀 처리 (Variable length path 대응)
                if isinstance(item, (list, tuple)):
                    for sub_item in item:
                        parse_item(sub_item)
                    return

                # 1. 노드 (Vertex) 파싱
                if item_type in ('Vertex', 'agtype_vertex') or (isinstance(item, dict) and 'id' in item and 'label' in item and 'properties' in item) or (hasattr(item, 'id') and hasattr(item, 'label') and hasattr(item, 'properties')):
                    try:
                        n_id = str(item.get('id', '')) if isinstance(item, dict) else str(getattr(item, 'id', ''))
                        if n_id and n_id not in node_ids:
                            n_label = item.get('label', 'Unknown') if isinstance(item, dict) else getattr(item, 'label', 'Unknown')
                            n_props = item.get('properties', {}) if isinstance(item, dict) else getattr(item, 'properties', {})
                            node_ids.add(n_id)
                            elements.append({
                                "group": "nodes",
                                "data": {"id": n_id, "label": str(n_label).replace('"', ''), "props": GraphService.safe_props(n_props)}
                            })
                    except Exception as e:
                        logger.error(f"[Node Parse Error] {e}")
                        
                # 2. 엣지 (Edge) 파싱
                elif item_type in ('Edge', 'agtype_edge') or (isinstance(item, dict) and 'start_id' in item and 'end_id' in item) or (hasattr(item, 'start_id') and hasattr(item, 'end_id')):
                    try:
                        e_id = str(item.get('id', '')) if isinstance(item, dict) else str(getattr(item, 'id', ''))
                        if e_id and e_id not in edge_ids:
                            e_label = item.get('label', 'Unknown') if isinstance(item, dict) else getattr(item, 'label', 'Unknown')
                            s_id = str(item.get('start_id', '')) if isinstance(item, dict) else str(getattr(item, 'start_id', ''))
                            t_id = str(item.get('end_id', '')) if isinstance(item, dict) else str(getattr(item, 'end_id', ''))
                            e_props = item.get('properties', {}) if isinstance(item, dict) else getattr(item, 'properties', {})
                            
                            edge_ids.add(e_id)
                            elements.append({
                                "group": "edges",
                                "data": {"id": e_id, "source": s_id, "target": t_id, "label": str(e_label).replace('"', ''), "props": GraphService.safe_props(e_props)}
                            })
                    except Exception as e:
                        logger.error(f"[Edge Parse Error] {e}")
                        
                # 3. Raw String 파싱 (AgensGraph 포맷)
                elif isinstance(item, str) and ('[' in item and ']' in item and '{' in item and '}' in item):
                    edge_match = edge_pattern.match(item)
                    if edge_match:
                        try:
                            e_label, e_id, s_id, t_id, props_str = edge_match.groups()
                            if e_id not in edge_ids:
                                edge_ids.add(e_id)
                                e_props = json.loads(props_str) if props_str else {}
                                elements.append({
                                    "group": "edges",
                                    "data": {"id": e_id, "source": s_id, "target": t_id, "label": e_label, "props": GraphService.safe_props(e_props)}
                                })
                        except: pass
                    else:
                        node_match = node_pattern.match(item)
                        if node_match:
                            try:
                                n_label, n_id, props_str = node_match.groups()
                                if n_id not in node_ids:
                                    node_ids.add(n_id)
                                    n_props = json.loads(props_str) if props_str else {}
                                    elements.append({
                                        "group": "nodes",
                                        "data": {"id": n_id, "label": n_label, "props": GraphService.safe_props(n_props)}
                                    })
                            except: pass

            for r in rows:
                for item in r:
                    parse_item(item)
                            
                # 3. 폴백 (Tuples/Lists) 또는 연속된 원시 타입 시퀀스 (id, label, props)
                try:
                    if len(r) >= 3:
                        # RDB 드라이버 업데이트 후 PyGreSQL이 객체를 리턴하지 않고 [id, label(List), props(Dict)] 형태로 반환할 때 방어
                        for i in range(len(r) - 2):
                            item1, item2, item3 = r[i], r[i+1], r[i+2]
                            if isinstance(item1, str) and '.' in item1 and item1.split('.')[0].isdigit() and isinstance(item2, list) and isinstance(item3, dict):
                                # 노드 식별 성공. ex: ('9.1', ['vt_transfer'], {'amount': '0'})
                                n_id = item1
                                if n_id not in node_ids:
                                    node_ids.add(n_id)
                                    raw_label = item2[0] if item2 else 'Unknown'
                                    elements.append({"group": "nodes", "data": {"id": n_id, "label": str(raw_label).replace('"', ''), "props": GraphService.safe_props(item3)}})
                                    
                    if len(r) >= 5:
                        # 엣지 방어 [Edge_ID(str), Label(str), Source_ID(str), Target_ID(str), Props(dict)]
                        for i in range(len(r) - 4):
                            item1, item2, item3, item4, item5 = r[i], r[i+1], r[i+2], r[i+3], r[i+4]
                            
                            # Type matching for destructured PyGreSQL edge object
                            if isinstance(item1, str) and isinstance(item2, str) and isinstance(item3, str) and isinstance(item4, str) and isinstance(item5, dict):
                                # Verify items 1, 3, 4 are valid AgensGraph internal IDs (ex: '9.13')
                                if '.' in item1 and '.' in item3 and '.' in item4:
                                    # Validate they are numeric IDs safely
                                    if not (item1.split('.')[0].isdigit() and item3.split('.')[0].isdigit() and item4.split('.')[0].isdigit()):
                                        continue
                                        
                                    e_id = item1
                                    if e_id not in edge_ids:
                                        edge_ids.add(e_id)
                                        raw_label = item2 if item2 else 'Unknown'
                                        elements.append({
                                            "group": "edges",
                                            "data": {"id": e_id, "source": item3, "target": item4, "label": str(raw_label).replace('"', ''), "props": GraphService.safe_props(item5)}
                                        })
                except Exception as e:
                    logger.error(f"[Fallback Sequence Parse Error] {e}")
                
            return True, elements

        except Exception as e:
            logger.error(f"Query Error: {e}")
            return False, str(e)
        finally:
            conn.close()

    # ---------------------------------------------------------
    # 📚 [Feature 5] GraphRAG (AIService 연동)
    # ---------------------------------------------------------
    @staticmethod
    def quick_query(question, graph_path):
        """빠른 그래프 조회 (온톨로지 인식 강화 - 노드 + 엣지 속성)"""
        target_kw = AIService.extract_keywords(question)
        logger.info(f"▶ [Quick Query] 키워드 추출: '{target_kw}'")
        
        conn, cur = get_db_connection()
        if not conn: return []
        try:
            conn.autocommit = False 
            safe_set_graph_path(cur, graph_path)
            
            # 🎯 온톨로지 인식: 노드 + 엣지 속성 모두 검색
            q = f"""
            MATCH (v)-[r]-(n) 
            WHERE v.flnm CONTAINS '{target_kw}'
               OR v.telno CONTAINS '{target_kw}'
               OR v.phone CONTAINS '{target_kw}'
               OR v.bacnt CONTAINS '{target_kw}'
               OR v.actno CONTAINS '{target_kw}'
               OR v.account CONTAINS '{target_kw}'
               OR v.site CONTAINS '{target_kw}'
               OR v.url CONTAINS '{target_kw}'
               OR v.ip CONTAINS '{target_kw}'
               OR v.file CONTAINS '{target_kw}'
               OR v.crime_type CONTAINS '{target_kw}'
               OR v.ontology_type CONTAINS '{target_kw}'
               OR v.entity_subtype CONTAINS '{target_kw}'
               OR v.domain_concept CONTAINS '{target_kw}'
               OR r.crime_type CONTAINS '{target_kw}'
               OR r.crime_name CONTAINS '{target_kw}'
            RETURN id(v), labels(v), properties(v), 
                   id(r), type(r), properties(r), 
                   id(n), labels(n), properties(n) 
            LIMIT 30
            """
            logger.info(f"▶ [Quick Query] 실행 Cypher:\n{q}")
            cur.execute(q)
            rows = cur.fetchall()
            conn.commit()
            
            logger.info(f"▶ [Quick Query] 결과: {len(rows)}개 행")
            
            elements = []
            for r in rows:
                v_id = str(r[0])
                r_id = str(r[3])
                n_id = str(r[6])
                v_p = safe_props(r[2])
                n_p = safe_props(r[8])
                
                elements.append({"group": "nodes", "data": {"id": v_id, "label": r[1][0], "props": v_p}})
                elements.append({"group": "nodes", "data": {"id": n_id, "label": r[7][0], "props": n_p}})
                elements.append({"group": "edges", "data": {"id": r_id, "source": v_id, "target": n_id, "label": r[4], "props": safe_props(r[5])}})
            
            return elements
        except Exception as e:
            logger.error(f"Quick Query Error: {e}")
            return []
        finally:
            if conn: conn.close()
    
    @staticmethod
    def rag_query(question, graph_path):
        """그래프 조회 + AI 보고서 생성 (온톨로지 인식 강화 - 노드 + 엣지)"""
        target_kw = AIService.extract_keywords(question)
        logger.info(f"▶ [RAG] 키워드 추출: '{target_kw}'")
        
        conn, cur = get_db_connection()
        if not conn: return "DB Fail", []
        try:
            conn.autocommit = False 
            safe_set_graph_path(cur, graph_path)
            
            # 🎯 온톨로지 인식: 노드 + 엣지 속성 모두 검색
            q = f"""
            MATCH p=(v)-[*1..6]-(n) 
            WHERE v.flnm CONTAINS '{target_kw}'
               OR v.name CONTAINS '{target_kw}'
               OR v.nickname CONTAINS '{target_kw}'
               OR v.org_name CONTAINS '{target_kw}'
               OR v.telno CONTAINS '{target_kw}'
               OR v.phone CONTAINS '{target_kw}'
               OR v.bacnt CONTAINS '{target_kw}'
               OR v.actno CONTAINS '{target_kw}'
               OR v.account CONTAINS '{target_kw}'
               OR v.site CONTAINS '{target_kw}'
               OR v.url CONTAINS '{target_kw}'
               OR v.ip CONTAINS '{target_kw}'
               OR v.file CONTAINS '{target_kw}'
               OR v.crime_type CONTAINS '{target_kw}'
               OR v.ontology_type CONTAINS '{target_kw}'
               OR v.entity_subtype CONTAINS '{target_kw}'
               OR v.domain_concept CONTAINS '{target_kw}'
            UNWIND edges(p) as r
            RETURN id(startNode(r)), label(startNode(r)), properties(startNode(r)), 
                   id(r), label(r), properties(r), 
                   id(endNode(r)), label(endNode(r)), properties(endNode(r)) 
            LIMIT 50
            """
            logger.info(f"▶ [RAG] 실행 Cypher:\n{q}")
            cur.execute(q)
            rows = cur.fetchall()
            conn.commit()
            
            logger.info(f"▶ [RAG] 결과: {len(rows)}개 행")
            
            if not rows: 
                return f"그래프 데이터페이스에서 '{target_kw}' 키워드와 연관된 데이터를 찾을 수 없습니다.\n검색기반(RAG) 보고서 생성을 위해서는 특정 사건번호, 피의자 이름, 또는 계좌번호 등을 프롬프트에 명시해주세요. (예: 'CASE-2025-0610 분석 보고서 작성해줘')", []

            context_texts = []
            elements = []
            for r in rows:
                v_id = str(r[0])
                r_id = str(r[3])
                n_id = str(r[6])
                v_p = safe_props(r[2])
                n_p = safe_props(r[8])
                r_p = safe_props(r[5])  # 엣지 속성
                
                # 노드 타입별 주요 속성 추출
                src_name = (v_p.get('flnm') or v_p.get('telno') or v_p.get('phone') or 
                           v_p.get('actno') or v_p.get('bacnt') or v_p.get('account') or
                           v_p.get('site') or v_p.get('url') or v_p.get('ip') or 
                           v_p.get('file') or v_p.get('name') or "Unknown")
                tgt_name = (n_p.get('flnm') or n_p.get('telno') or n_p.get('phone') or 
                           n_p.get('actno') or n_p.get('bacnt') or n_p.get('account') or
                           n_p.get('site') or n_p.get('url') or n_p.get('ip') or 
                           n_p.get('file') or n_p.get('name') or "Unknown")
                
                # 엣지 상세 정보 추출 (source, updated 제외)
                edge_details = []
                if r_p:
                    for k, v in r_p.items():
                        if k not in ['source', 'updated'] and v:
                            edge_details.append(f"{k}={v}")
                
                # 풍부한 컨텍스트 생성
                edge_type = r[4]
                if edge_details:
                    edge_info = ", ".join(edge_details)
                    context_texts.append(f"{src_name} -[{edge_type}: {edge_info}]-> {tgt_name}")
                else:
                    context_texts.append(f"{src_name} -[{edge_type}]-> {tgt_name}")
                
                elements.append({"group": "nodes", "data": {"id": v_id, "label": r[1][0], "props": v_p}})
                elements.append({"group": "nodes", "data": {"id": n_id, "label": r[7][0], "props": n_p}})
                elements.append({"group": "edges", "data": {"id": r_id, "source": v_id, "target": n_id, "label": r[4], "props": safe_props(r[5])}})


            # 온톨로지 기반 분석
            from app.services.ontology_service import SemanticAnalyzer
            semantic_analysis = SemanticAnalyzer.analyze(elements, context_texts)
            
            report = AIService.generate_rag_report(question, context_texts, semantic_analysis)
            return report, elements
        except Exception as e:
            return str(e), []
        finally:
            conn.close()

    @staticmethod
    def create_manual_node(graph_name, label, properties):
        """수동으로 노드를 생성하는 함수 (i2 기능)
        
        Note: AgensGraph의 ccop_fraud_graph에서 Cypher CREATE는 label ID 0으로 
        노드를 생성하는 알려진 이슈가 있습니다. 이 경우 삭제 시 raw SQL을 사용합니다.
        """
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            conn.autocommit = True
            safe_set_graph_path(cur, graph_name)
            
            # Cypher CREATE로 노드 생성
            props_str = "{}"
            if properties:
                prop_list = []
                for k, v in properties.items():
                    k_str = str(k).replace('"', '').replace("'", "")
                    if isinstance(v, (int, float)):
                        prop_list.append(f"{k_str}: {v}")
                    else:
                        v_str = str(v).replace("'", "''")
                        prop_list.append(f"{k_str}: '{v_str}'")
                props_str = "{" + ", ".join(prop_list) + "}"
                
            cur.execute(f"CREATE (n:{label} {props_str}) RETURN id(n)")
            new_id = cur.fetchone()[0]
            logger.info(f"▶ [CreateNode] Cypher CREATE → {graph_name}.{label}, ID: {new_id}")
            return True, str(new_id)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def create_manual_edge(graph_name, src_id, tgt_id, label, properties):
        """수동으로 엣지를 생성하는 함수 (i2 기능)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            safe_set_graph_path(cur, graph_name)
            
            props_str = "{}"
            if properties:
                prop_list = []
                for k, v in properties.items():
                    k_str = str(k).replace('"', '').replace("'", "")
                    if isinstance(v, (int, float)):
                        prop_list.append(f"{k_str}: {v}")
                    else:
                        v_str = str(v).replace("'", "''") 
                        prop_list.append(f"{k_str}: '{v_str}'")
                props_str = "{" + ", ".join(prop_list) + "}"
                
            q = f"MATCH (a), (b) WHERE id(a) = '{src_id}' AND id(b) = '{tgt_id}' CREATE (a)-[r:{label} {props_str}]->(b) RETURN id(r)"
            cur.execute(q)
            new_id = cur.fetchone()[0]
            conn.commit()
            return True, str(new_id)
        except Exception as e:
            import traceback
            traceback.print_exc()
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    @staticmethod
    def delete_element(graph_name, element_id, is_edge=False):
        """수동으로 노드/엣지를 삭제하는 함수
        
        Cypher MATCH + DELETE를 사용합니다.
        Note: label ID가 0인 노드(AgensGraph CREATE 버그)는 삭제 불가 → 
        프론트엔드에서 '화면에서만 제거' 옵션을 제공합니다.
        """
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            conn.autocommit = True
            safe_set_graph_path(cur, graph_name)
            if is_edge:
                cur.execute(f"MATCH ()-[r]-() WHERE id(r) = '{element_id}' DELETE r")
            else:
                cur.execute(f"MATCH (n) WHERE id(n) = '{element_id}' DETACH DELETE n")
            logger.info(f"▶ [DeleteElement] Cypher DELETE, graph={graph_name}, ID: {element_id}")
            return True, "삭제 완료"
        except Exception as e:
            logger.error(f"▶ [DeleteElement] ERROR: {e}")
            return False, str(e)
        finally:
            conn.close()