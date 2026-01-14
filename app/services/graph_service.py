import json
from app.database import get_db_connection, safe_props
from app.services.subgraph_service import SubGraphService
from app.services.ai_service import AIService
import psycopg2
from flask import current_app

class GraphService:
    
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
            print(f"DB 접속 오류: {e}")
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
    def clear_graph(graph_path):
        """그래프 데이터 전체 초기화"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, "DB 연결 실패"
        try:
            cur.execute(f"SET graph_path = {graph_path};")
            cur.execute("MATCH (n) DETACH DELETE n")
            return True, "삭제 완료"
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
                    print(f"Search error in {table_name}: {table_error}")
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
                                
                                # 엣지 추가
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
                        except Exception as edge_error:
                            print(f"Edge search error in {edge_table}: {edge_error}")
                            continue
                            
                except Exception as e:
                    print(f"Edge retrieval error: {e}")
            
            return elements
        except Exception as e:
            print(f"Search Error: {e}")
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
            # 1. 엣지 테이블 목록 동적 조회
            cur.execute(f"""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = '{graph_path}' 
                  AND (table_name LIKE 'eg_%' OR table_name IN ('call', 'used_account', 'digital_trace', 'used_phone'))
            """)
            edge_tables = [r[0] for r in cur.fetchall()]
            
            # 2. 각 엣지 테이블에서 연결된 엣지 조회
            for edge_table in edge_tables:
                try:
                    # AgensGraph는 ag_vertex 베이스 테이블에 모든 노드가 있음
                    edge_query = f"""
                    SELECT e.id, e.start, e."end", e.properties, 
                           vs.id as src_id, vs.properties as src_props,
                           vt.id as tgt_id, vt.properties as tgt_props
                    FROM "{graph_path}"."{edge_table}" e
                    LEFT JOIN "{graph_path}"."ag_vertex" vs ON e.start = vs.id
                    LEFT JOIN "{graph_path}"."ag_vertex" vt ON e."end" = vt.id
                    WHERE e.start = '{node_id}' OR e."end" = '{node_id}'
                    LIMIT 50
                    """
                    
                    cur.execute(edge_query)
                    for r in cur.fetchall():
                        edge_id = str(r[0])
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
                        
                        # 엣지 추가
                        elements.append({
                            "group": "edges",
                            "data": {
                                "id": edge_id,
                                "source": start_id,
                                "target": end_id,
                                "label": edge_table,  # 엣지 타입은 테이블명
                                "props": edge_props
                            }
                        })
                
                except Exception as table_error:
                    print(f"Expand Error in table {edge_table}: {table_error}")
                    continue
            
            return elements
        except Exception as e:
            print(f"Expand Error: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def find_shortest_path(src, tgt, graph_path):
        """최단 경로 탐색 (BFS)"""
        conn, cur = GraphService.get_db_connection()
        if not conn: return False, []
        
        try:
            cur.execute(f"SET graph_path = {graph_path};")
            
            # BFS 탐색
            queue = [[src]]
            visited = {src}
            found_path = None
            
            while queue:
                path = queue.pop(0)
                curr = path[-1]
                if curr == tgt:
                    found_path = path; break
                if len(path) > 4: continue # 깊이 제한
                
                # 이웃 노드 검색
                cur.execute(f"MATCH (u)-[]-(v) WHERE id(u) = {curr} RETURN id(v)")
                for row in cur.fetchall():
                    neighbor_id = str(row[0])
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        queue.append(path + [neighbor_id])
            
            if not found_path: return False, []
            
            # 경로 시각화 데이터 생성
            elements = []
            for nid in found_path:
                cur.execute(f"MATCH (n) WHERE id(n) = {nid} RETURN id(n), labels(n), properties(n)")
                r = cur.fetchone()
                if r:
                    node_id = str(r[0])
                    elements.append({"group": "nodes", "data": {"id": node_id, "label": r[1][0], "props": GraphService.safe_props(r[2])}})
            
            # 엣지 연결
            for i in range(len(found_path)-1):
                u, v = found_path[i], found_path[i+1]
                cur.execute(f"MATCH (u)-[r]-(v) WHERE id(u) = {u} AND id(v) = {v} RETURN id(r), type(r), properties(r)")
                edge_res = cur.fetchone()
                
                if edge_res:
                    edge_id = str(edge_res[0])
                    elements.append({"group": "edges", "data": {"id": edge_id, "source": str(u), "target": str(v), "label": edge_res[1], "props": GraphService.safe_props(edge_res[2])}})
                else:
                    # 논리적 연결일 경우 점선 처리
                    elements.append({"group": "edges", "data": {"id": f"v_{u}_{v}", "source": u, "target": v, "label": "Same Info", "props": {"type":"virtual"}}, "classes": "virtual-edge"})
                    
            return True, elements
            
        except Exception as e:
            print(f"Path Error: {e}")
            return False, []
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
            cur.execute(f"SET graph_path = {graph_path};")

            # 2. 직접 Cypher 실행 (ag_catalog 래퍼 불필요)
            real_query = cypher_query.strip()
            
            print(f"▶ [GraphService] 실행 Cypher: {real_query}")
            cur.execute(real_query)
            
            # 3. 결과 파싱
            rows = cur.fetchall()
            elements = []
            
            for r in rows:
                # AgensGraph 결과: (id, label, props) 또는 변형된 형태
                if len(r) >= 3:
                    node_id = str(r[0])
                    # 라벨이 배열이나 문자열로 올 수 있음
                    raw_label = r[1]
                    if isinstance(raw_label, list):
                        raw_label = raw_label[0] if raw_label else 'Unknown'
                    else:
                        raw_label = str(raw_label).replace('"', '')
                    
                    props = GraphService.safe_props(r[2])
                    
                    elements.append({
                        "group": "nodes", 
                        "data": { 
                            "id": node_id, 
                            "label": raw_label, 
                            "props": props 
                        }
                    })
            
            return True, elements

        except Exception as e:
            print(f"Query Error: {e}")
            return False, str(e)
        finally:
            conn.close()

    # ---------------------------------------------------------
    # 📚 [Feature 5] GraphRAG (AIService 연동)
    # ---------------------------------------------------------
    @staticmethod
    def quick_query(question, graph_path):
        """빠른 그래프 조회 (보고서 없이 elements만 반환)"""
        target_kw = AIService.extract_keywords(question)
        print(f"▶ [Quick Query] 키워드 추출: '{target_kw}'")
        
        conn, cur = get_db_connection()
        if not conn: return []
        try:
            conn.autocommit = False 
            cur.execute(f"SET graph_path = {graph_path}")
            
            # CONTAINS 사용 (regex 이스케이프 문제 방지)
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
            RETURN id(v), labels(v), properties(v), 
                   id(r), type(r), properties(r), 
                   id(n), labels(n), properties(n) 
            LIMIT 30
            """
            print(f"▶ [Quick Query] 실행 Cypher:\n{q}")
            cur.execute(q)
            rows = cur.fetchall()
            conn.commit()
            
            print(f"▶ [Quick Query] 결과: {len(rows)}개 행")
            
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
            print(f"Quick Query Error: {e}")
            return []
        finally:
            if conn: conn.close()
    
    @staticmethod
    def rag_query(question, graph_path):
        """그래프 조회 + AI 보고서 생성"""
        target_kw = AIService.extract_keywords(question)
        print(f"▶ [RAG] 키워드 추출: '{target_kw}'")
        
        conn, cur = get_db_connection()
        if not conn: return "DB Fail", []
        try:
            conn.autocommit = False 
            cur.execute(f"SET graph_path = {graph_path}")
            
            # CONTAINS 사용 (regex 이스케이프 문제 방지)
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
            RETURN id(v), labels(v), properties(v), 
                   id(r), type(r), properties(r), 
                   id(n), labels(n), properties(n) 
            LIMIT 30
            """
            print(f"▶ [RAG] 실행 Cypher:\n{q}")
            cur.execute(q)
            rows = cur.fetchall()
            conn.commit()
            
            print(f"▶ [RAG] 결과: {len(rows)}개 행")
            
            if not rows: return "No Data", []

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